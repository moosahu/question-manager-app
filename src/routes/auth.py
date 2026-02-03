from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from src.models.user import User, db
from src.forms import LoginForm, TwoFactorForm  # تأكد من تعريف هذا النموذج
import pyotp

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
            # إذا كان 2FA مفعلًا، نفّذ خطوة التحقق قبل تسجيل الدخول
            if user.two_factor_auth:
                session['pre_2fa_user_id'] = user.id
                # تأكد من وجود حقل remember_me في النموذج
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
    # تأكد من وجود معرف المستخدم المؤقت في الجلسة
    if 'pre_2fa_user_id' not in session:
        return redirect(url_for('auth.login'))

    form = TwoFactorForm()
    if form.validate_on_submit():
        user = User.query.get(session['pre_2fa_user_id'])
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(form.otp_code.data):
            # تسجيل الدخول النهائي
            login_user(user, remember=session.pop('pre_2fa_remember', False))
            session.pop('pre_2fa_user_id', None)
            
            # === إضافة الإشعارات ===
            if notifications_available and UserNotifications:
                try:
                    UserNotifications.notify_user_login_2fa(
                        username=user.username,
                        user_id=user.id
                    )
                    current_app.logger.info(f"2FA login notification sent for user: {user.username}")
                except Exception as e:
                    current_app.logger.error(f"Error sending 2FA login notification: {e}")
            
            flash('تم التحقق وتسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('رمز التحقق غير صحيح', 'danger')

    return render_template('auth/verify_2fa.html', form=form)

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

