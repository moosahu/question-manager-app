from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user, login_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
from werkzeug.security import check_password_hash, generate_password_hash
import pyotp
import qrcode
import io
import base64

try:
    from extensions import db
    from sqlalchemy import Column, Integer, String
except ImportError:
    try:
        from src.extensions import db
        from sqlalchemy import Column, Integer, String
    except ImportError:
        print("Error: Could not import db from extensions or src.extensions.")
        raise

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

class ProfileSettingsForm(FlaskForm):
    full_name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    bio = TextAreaField('نبذة تعريفية', validators=[Optional(), Length(max=500)])

class NotificationSettingsForm(FlaskForm):
    email_notifications = BooleanField('تلقي الإشعارات عبر البريد الإلكتروني')
    app_notifications = BooleanField('تلقي الإشعارات داخل التطبيق')
    notification_frequency = SelectField('تكرار الإشعارات', 
                                        choices=[('immediate', 'فوري'), 
                                                ('daily', 'يومي'), 
                                                ('weekly', 'أسبوعي')])

class SecuritySettingsForm(FlaskForm):
    two_factor_auth = BooleanField('تفعيل المصادقة الثنائية')
    login_alerts = BooleanField('تلقي تنبيهات عند تسجيل الدخول من جهاز جديد')

class IntegrationSettingsForm(FlaskForm):
    google_integration = BooleanField('تكامل مع Google Classroom')
    microsoft_integration = BooleanField('تكامل مع Microsoft Teams')

@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    profile_form = ProfileSettingsForm()
    notification_form = NotificationSettingsForm()
    security_form = SecuritySettingsForm()
    integration_form = IntegrationSettingsForm()
    
    # تعبئة النماذج بالبيانات الحالية
    if request.method == 'GET':
        if hasattr(current_user, 'full_name'):
            profile_form.full_name.data = current_user.full_name
        else:
            profile_form.full_name.data = current_user.username
            
        if hasattr(current_user, 'email'):
            profile_form.email.data = current_user.email
            
        if hasattr(current_user, 'bio'):
            profile_form.bio.data = current_user.bio
    
    # معالجة النماذج عند الإرسال
    if request.method == 'POST':
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            # تحديث بيانات الملف الشخصي
            if hasattr(current_user, 'full_name'):
                current_user.full_name = profile_form.full_name.data
            if hasattr(current_user, 'email'):
                current_user.email = profile_form.email.data
            if hasattr(current_user, 'bio'):
                current_user.bio = profile_form.bio.data
            db.session.commit()
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'notification_submit' in request.form and notification_form.validate_on_submit():
            # تحديث إعدادات الإشعارات
            if hasattr(current_user, 'email_notifications'):
                current_user.email_notifications = notification_form.email_notifications.data
            if hasattr(current_user, 'app_notifications'):
                current_user.app_notifications = notification_form.app_notifications.data
            if hasattr(current_user, 'notification_frequency'):
                current_user.notification_frequency = notification_form.notification_frequency.data
            db.session.commit()
            flash('تم تحديث إعدادات الإشعارات بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'security_submit' in request.form and security_form.validate_on_submit():
            # تحديث إعدادات الأمان
            if hasattr(current_user, 'two_factor_auth'):
                current_user.two_factor_auth = security_form.two_factor_auth.data
            if hasattr(current_user, 'login_alerts'):
                current_user.login_alerts = security_form.login_alerts.data
            db.session.commit()
            flash('تم تحديث إعدادات الأمان بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'integration_submit' in request.form and integration_form.validate_on_submit():
            # تحديث إعدادات التكاملات
            if hasattr(current_user, 'google_integration'):
                current_user.google_integration = integration_form.google_integration.data
            if hasattr(current_user, 'microsoft_integration'):
                current_user.microsoft_integration = integration_form.microsoft_integration.data
                
            # إعادة توليد مفتاح API إذا تم طلب ذلك
            if 'regenerate_api_key' in request.form:
                import uuid
                
                # استخدام المفتاح المرسل من JavaScript أو توليد مفتاح جديد
                new_api_key = request.form.get('new_api_key')
                if not new_api_key:
                    new_api_key = str(uuid.uuid4())
                
                if hasattr(current_user, 'api_key'):
                    current_user.api_key = new_api_key
                else:
                    # إذا لم يكن الحقل موجود، إنشاؤه ديناميكياً
                    setattr(current_user, 'api_key', new_api_key)
                
                print(f"✅ تم تحديث مفتاح API: {new_api_key}")
                flash('تم توليد مفتاح API جديد بنجاح', 'success')
                
            db.session.commit()
            flash('تم تحديث إعدادات التكاملات بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'change_password_submit' in request.form:
            # تغيير كلمة المرور
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # التحقق من صحة البيانات
            if not current_password or not new_password or not confirm_password:
                flash('جميع الحقول مطلوبة', 'error')
            elif new_password != confirm_password:
                flash('كلمة المرور الجديدة وتأكيدها غير متطابقين', 'error')
            elif len(new_password) < 6:
                flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'error')
            elif not check_password_hash(current_user.password_hash, current_password):
                flash('كلمة المرور الحالية غير صحيحة', 'error')
            else:
                # تحديث كلمة المرور
                current_user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash('تم تغيير كلمة المرور بنجاح', 'success')
                return redirect(url_for('settings.index'))
    
    # إصلاح مسار template
    return render_template('settings.html', 
                          profile_form=profile_form,
                          notification_form=notification_form,
                          security_form=security_form,
                          integration_form=integration_form)

@settings_bp.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """إعداد المصادقة الثنائية"""
    if request.method == 'GET':
        # توليد مفتاح سري جديد
        secret = pyotp.random_base32()
        
        # حفظ المفتاح السري مؤقتاً في الجلسة
        session['temp_2fa_secret'] = secret
        
        # إنشاء QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=current_user.username,
            issuer_name="نظام الكيمياء التحصيلي"
        )
        
        # توليد QR code كصورة
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # تحويل الصورة إلى base64
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        # إرجاع البيانات كـ JSON مع HTML محدث
        qr_html = f'<img src="data:image/png;base64,{img_base64}" alt="QR Code" style="max-width: 200px; height: auto;" />'
        
        return jsonify({
            'success': True,
            'qr_code': img_base64,
            'qr_html': qr_html,
            'secret': secret,
            'message': 'تم توليد رمز QR بنجاح'
        })
    
    # معالجة POST (تفعيل المصادقة الثنائية)
    elif request.method == 'POST':
        verification_code = request.form.get('verification_code')
        temp_secret = session.get('temp_2fa_secret')
        
        if not temp_secret:
            return jsonify({
                'success': False,
                'message': 'انتهت صلاحية الجلسة. يرجى إعادة المحاولة.'
            }), 400
        
        if not verification_code:
            return jsonify({
                'success': False,
                'message': 'يرجى إدخال رمز التحقق'
            }), 400
        
        # التحقق من رمز TOTP
        totp = pyotp.TOTP(temp_secret)
        if totp.verify(verification_code):
            # حفظ المفتاح السري في قاعدة البيانات
            if not hasattr(current_user, 'totp_secret'):
                # إضافة الحقل إذا لم يكن موجوداً
                setattr(current_user, 'totp_secret', temp_secret)
                setattr(current_user, 'two_factor_auth', True)
            else:
                current_user.totp_secret = temp_secret
                current_user.two_factor_auth = True
            
            db.session.commit()
            
            # إزالة المفتاح المؤقت من الجلسة
            session.pop('temp_2fa_secret', None)
            
            return jsonify({
                'success': True,
                'message': 'تم تفعيل المصادقة الثنائية بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'رمز التحقق غير صحيح'
            }), 400

@settings_bp.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    """إلغاء تفعيل المصادقة الثنائية"""
    verification_code = request.form.get('verification_code')
    
    if not verification_code:
        return jsonify({
            'success': False,
            'message': 'يرجى إدخال رمز التحقق'
        }), 400
    
    # التحقق من رمز TOTP
    if hasattr(current_user, 'totp_secret') and current_user.totp_secret:
        totp = pyotp.TOTP(current_user.totp_secret)
        if totp.verify(verification_code):
            # إلغاء تفعيل المصادقة الثنائية
            current_user.two_factor_auth = False
            current_user.totp_secret = None
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'تم إلغاء تفعيل المصادقة الثنائية بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'رمز التحقق غير صحيح'
            }), 400
    else:
        return jsonify({
            'success': False,
            'message': 'المصادقة الثنائية غير مفعلة'
        }), 400

@settings_bp.route('/verify-2fa', methods=['POST'])
@login_required
def verify_2fa():
    """التحقق من المصادقة الثنائية"""
    data = request.get_json()
    verification_code = data.get('code')
    temp_secret = session.get('temp_2fa_secret')
    
    if not temp_secret:
        return jsonify({
            'success': False,
            'message': 'انتهت صلاحية الجلسة. يرجى إعادة المحاولة.'
        }), 400
    
    if not verification_code:
        return jsonify({
            'success': False,
            'message': 'يرجى إدخال رمز التحقق'
        }), 400
    
    # التحقق من رمز TOTP
    totp = pyotp.TOTP(temp_secret)
    if totp.verify(verification_code):
        # حفظ المفتاح السري في قاعدة البيانات
        if not hasattr(current_user, 'totp_secret'):
            # إضافة الحقل إذا لم يكن موجوداً
            setattr(current_user, 'totp_secret', temp_secret)
            setattr(current_user, 'two_factor_auth', True)
        else:
            current_user.totp_secret = temp_secret
            current_user.two_factor_auth = True
        
        db.session.commit()
        
        # إزالة المفتاح المؤقت من الجلسة
        session.pop('temp_2fa_secret', None)
        
        return jsonify({
            'success': True,
            'message': 'تم تفعيل المصادقة الثنائية بنجاح'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'رمز التحقق غير صحيح'
        }), 400

