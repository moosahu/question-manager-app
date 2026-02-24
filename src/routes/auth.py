from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from src.models.user import User, db
from src.forms import LoginForm, TwoFactorForm  # تأكد من تعريف هذا النموذج
import pyotp
import random
import string
from datetime import datetime, timedelta

# إضافة استيراد نظام الإشعارات
try:
    from src.utils.notification_system import UserNotifications, SystemNotifications
    notifications_available = True
except ImportError:
    try:
        from utils.notification_system import UserNotifications, SystemNotifications
        notifications_available = True
    except ImportError:
        print("Warning: Could not import notification system for auth")
        UserNotifications = None
        SystemNotifications = None
        notifications_available = False

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # ✅ الأدمن: يُجبر دائماً على التحقق الثنائي
            if user.is_admin:
                if not user.totp_secret:
                    # الأدمن لم يُعدّ 2FA بعد — أجبره على الإعداد أولاً
                    login_user(user)
                    flash("يجب إعداد التحقق الثنائي قبل الدخول كمدير.", "warning")
                    return redirect(url_for('settings.setup_2fa'))
                session['pre_2fa_user_id'] = user.id
                session['pre_2fa_remember'] = getattr(form, 'remember_me', False).data if hasattr(form, 'remember_me') else False
                return redirect(url_for('auth.verify_2fa'))

            # غير أدمن: تحقق من إعداد 2FA الاختياري
            if user.two_factor_auth and user.totp_secret:
                session['pre_2fa_user_id'] = user.id
                session['pre_2fa_remember'] = getattr(form, 'remember_me', False).data if hasattr(form, 'remember_me') else False
                return redirect(url_for('auth.verify_2fa'))

            # بدون 2FA، سجّل الدخول مباشرة
            login_user(user, remember=getattr(form, 'remember_me', False).data)
            
            # === إضافة الإشعارات ===
            if notifications_available and UserNotifications:
                try:
                    UserNotifications.notify_user_login(
                        username=user.username,
                        user_id=user.id
                    )
                    current_app.logger.info(f"Login notification sent for user: {user.username}")
                except Exception as e:
                    current_app.logger.error(f"Error sending login notification: {e}")
            
            flash("تم تسجيل الدخول بنجاح.", "success")
            return redirect(url_for("dashboard"))
        else:
            # === إشعار محاولة دخول فاشلة ===
            try:
                ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
                notify_failed_login_attempt(username, ip_address)
            except Exception as e:
                current_app.logger.error(f"Error in failed login notification: {e}")
            
            flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "danger")
    return render_template("auth/login.html", form=form)

@auth_bp.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa():
    if 'pre_2fa_user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['pre_2fa_user_id'])
    if not user:
        session.pop('pre_2fa_user_id', None)
        return redirect(url_for('auth.login'))

    # ✅ تحديد طريقة التحقق المتاحة
    has_totp = bool(user.totp_secret)
    email_otp_sent = session.get('admin_otp_email') == user.email

    form = TwoFactorForm()
    if form.validate_on_submit():
        code = form.otp_code.data.strip()
        verified = False

        # ✅ التحقق من كود الإيميل أولاً (إذا أُرسل)
        if email_otp_sent and session.get('admin_otp_code'):
            otp_expires = session.get('admin_otp_expires')
            if otp_expires and datetime.utcnow() < datetime.fromisoformat(otp_expires):
                if session['admin_otp_code'] == code:
                    verified = True
                    # مسح كود الإيميل بعد الاستخدام
                    session.pop('admin_otp_code', None)
                    session.pop('admin_otp_expires', None)
                    session.pop('admin_otp_email', None)

        # ✅ أو التحقق من TOTP (تطبيق authenticator)
        if not verified and has_totp:
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(code):
                verified = True

        if verified:
            login_user(user, remember=session.pop('pre_2fa_remember', False))
            session.pop('pre_2fa_user_id', None)

            if notifications_available and UserNotifications:
                try:
                    UserNotifications.notify_user_login_2fa(
                        username=user.username,
                        user_id=user.id
                    )
                except Exception as e:
                    current_app.logger.error(f"Error sending 2FA login notification: {e}")

            flash('تم التحقق وتسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('رمز التحقق غير صحيح أو منتهي الصلاحية', 'danger')

    import os
    return render_template(
        'auth/verify_2fa.html',
        form=form,
        has_totp=has_totp,
        email_otp_sent=email_otp_sent,
        admin_email_masked=_mask_email(user.email) if user.email else None,
        firebase_api_key=os.environ.get('FIREBASE_WEB_API_KEY', ''),
        firebase_project_id=os.environ.get('FIREBASE_PROJECT_ID', 'chem-tahsili'),
        # ✅ رقم مخفي فقط للعرض — الرقم الكامل يُطلب عند الحاجة عبر /get-admin-phone
        saved_phone_masked=_mask_phone(user.phone_number) if user.phone_number else None
    )


@auth_bp.route("/get-admin-phone", methods=["POST"])
def get_admin_phone():
    """إرجاع الرقم الكامل للـ JS فقط عند بدء Firebase Auth (محمي بالجلسة)"""
    if 'pre_2fa_user_id' not in session:
        return jsonify({'success': False}), 400
    user = User.query.get(session['pre_2fa_user_id'])
    if not user or not user.is_admin or not user.phone_number:
        return jsonify({'success': False}), 403
    return jsonify({'success': True, 'phone': user.phone_number})


@auth_bp.route("/send-admin-otp", methods=["POST"])
def send_admin_otp():
    """إرسال كود OTP للأدمن عبر الإيميل"""
    if 'pre_2fa_user_id' not in session:
        return jsonify({'success': False, 'message': 'جلسة غير صالحة'}), 400

    user = User.query.get(session['pre_2fa_user_id'])
    if not user or not user.is_admin or not user.email:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    # توليد كود عشوائي 6 أرقام
    code = ''.join(random.choices(string.digits, k=6))
    expires = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    session['admin_otp_code'] = code
    session['admin_otp_expires'] = expires
    session['admin_otp_email'] = user.email

    try:
        from src.services.email_service import email_service
        success, msg = email_service.send_admin_login_otp(user.email, code, user.username)
        if success:
            return jsonify({'success': True, 'message': f'تم إرسال الكود إلى {_mask_email(user.email)}'})
        else:
            return jsonify({'success': False, 'message': f'فشل الإرسال: {msg}'})
    except Exception as e:
        current_app.logger.error(f"Error sending admin OTP: {e}")
        return jsonify({'success': False, 'message': 'خطأ في إرسال الكود'})


def _mask_email(email):
    """إخفاء جزء من الإيميل: a***@domain.com"""
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    masked = local[0] + '***' if len(local) > 1 else '***'
    return f"{masked}@{domain}"


def _mask_phone(phone):
    """إخفاء جزء من رقم الجوال: +966 5XX XXX X89"""
    if not phone or len(phone) < 4:
        return phone
    return phone[:-4].replace(phone[4:-4], '*' * len(phone[4:-4])) if len(phone) > 8 else phone[:3] + '****'

@auth_bp.route("/logout")
@login_required
def logout():
    # === إضافة الإشعارات قبل تسجيل الخروج ===
    if notifications_available and UserNotifications:
        try:
            UserNotifications.notify_user_logout(
                username=current_user.username,
                user_id=current_user.id
            )
            current_app.logger.info(f"Logout notification sent for user: {current_user.username}")
        except Exception as e:
            current_app.logger.error(f"Error sending logout notification: {e}")
    
    logout_user()
    flash("تم تسجيل الخروج بنجاح.", "success")
    return redirect(url_for("auth.login"))

# === دوال مساعدة للإشعارات ===

def notify_failed_login_attempt(username, ip_address=None):
    """
    دالة مساعدة لإرسال إشعار محاولة تسجيل دخول فاشلة
    """
    if notifications_available and SystemNotifications:
        try:
            message = f"محاولة تسجيل دخول فاشلة للمستخدم: {username}"
            if ip_address:
                message += f" من العنوان: {ip_address}"
                
            SystemNotifications.notify_security_alert(message)
            current_app.logger.warning(f"Failed login attempt notification sent for: {username}")
        except Exception as e:
            current_app.logger.error(f"Error sending failed login notification: {e}")

@auth_bp.route("/enable_2fa_notification", methods=["POST"])
@login_required
def enable_2fa_notification():
    """
    إرسال إشعار تفعيل التحقق الثنائي
    """
    try:
        if notifications_available and SystemNotifications:
            SystemNotifications.notify_settings_updated(
                setting_name="التحقق الثنائي (تفعيل)",
                user_id=current_user.id
            )
            return jsonify({"success": True, "message": "تم إرسال إشعار تفعيل التحقق الثنائي"})
        else:
            return jsonify({"success": False, "message": "نظام الإشعارات غير متاح"})
    except Exception as e:
        current_app.logger.error(f"Error in enable_2fa_notification: {e}")
        return jsonify({"success": False, "message": "حدث خطأ في إرسال الإشعار"})

@auth_bp.route("/verify-firebase-phone", methods=["POST"])
def verify_firebase_phone():
    """التحقق من Firebase Phone Auth ID token وإتمام تسجيل الدخول"""
    if 'pre_2fa_user_id' not in session:
        return jsonify({'success': False, 'message': 'جلسة منتهية، أعد تسجيل الدخول'}), 400

    data = request.get_json() or {}
    id_token = data.get('id_token', '').strip()
    phone_number = data.get('phone_number', '').strip()

    if not id_token:
        return jsonify({'success': False, 'message': 'الـ token مفقود'}), 400

    user = User.query.get(session['pre_2fa_user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth

        # التحقق من الـ ID token باستخدام Firebase Admin SDK
        decoded = firebase_auth.verify_id_token(id_token)
        verified_phone = decoded.get('phone_number', '')

        if not verified_phone:
            return jsonify({'success': False, 'message': 'لا يوجد رقم جوال في الـ token'}), 400

        # ✅ إذا كان الأدمن سبق وحفظ رقمه — تحقق أنه نفسه
        if user.phone_number and user.phone_number != verified_phone:
            return jsonify({'success': False, 'message': 'رقم الجوال لا يطابق الحساب'}), 403

        # ✅ حفظ الرقم إذا كان أول مرة
        if not user.phone_number:
            user.phone_number = verified_phone
            db.session.commit()

        # ✅ إتمام تسجيل الدخول
        login_user(user, remember=session.pop('pre_2fa_remember', False))
        session.pop('pre_2fa_user_id', None)

        if notifications_available and UserNotifications:
            try:
                UserNotifications.notify_user_login_2fa(
                    username=user.username,
                    user_id=user.id
                )
            except Exception:
                pass

        current_app.logger.info(f"✅ Admin {user.username} logged in via Firebase Phone Auth")
        return jsonify({'success': True, 'redirect': url_for('dashboard')})

    except firebase_admin.auth.InvalidIdTokenError:
        return jsonify({'success': False, 'message': 'كود غير صالح أو منتهي الصلاحية'}), 401
    except firebase_admin.auth.ExpiredIdTokenError:
        return jsonify({'success': False, 'message': 'انتهت صلاحية الكود، أعد المحاولة'}), 401
    except Exception as e:
        current_app.logger.error(f"Firebase phone verify error: {e}")
        return jsonify({'success': False, 'message': f'خطأ: {str(e)}'}), 500


@auth_bp.route("/disable_2fa_notification", methods=["POST"])
@login_required
def disable_2fa_notification():
    """
    إرسال إشعار إلغاء التحقق الثنائي
    """
    try:
        if notifications_available and SystemNotifications:
            SystemNotifications.notify_settings_updated(
                setting_name="التحقق الثنائي (إلغاء)",
                user_id=current_user.id
            )
            return jsonify({"success": True, "message": "تم إرسال إشعار إلغاء التحقق الثنائي"})
        else:
            return jsonify({"success": False, "message": "نظام الإشعارات غير متاح"})
    except Exception as e:
        current_app.logger.error(f"Error in disable_2fa_notification: {e}")
        return jsonify({"success": False, "message": "حدث خطأ في إرسال الإشعار"})

