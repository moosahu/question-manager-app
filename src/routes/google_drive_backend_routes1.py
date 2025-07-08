# google_drive_backend_routes_fixed.py
# تم تحويل التطبيق الكامل إلى Blueprint مع الحفاظ على جميع الوظائف

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
import os
import json
import uuid
from datetime import datetime
import secrets
import base64
from cryptography.fernet import Fernet
import pyotp
import qrcode
import io

# إنشاء Blueprint بدلاً من تطبيق منفصل
google_drive_backend_bp = Blueprint('google_drive_backend', __name__)

# ===== إعدادات التشفير =====

def generate_encryption_key():
    """توليد مفتاح تشفير"""
    return Fernet.generate_key()

def get_encryption_key():
    """الحصول على مفتاح التشفير أو إنشاء واحد جديد"""
    key_file = 'encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = generate_encryption_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

# مفتاح التشفير
ENCRYPTION_KEY = get_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# ===== نماذج البيانات =====

class GoogleDriveUser:
    """نموذج شامل للمستخدم - Google Drive Backend"""
    def __init__(self, username="مستخدم تجريبي", email="user@example.com"):
        self.id = str(uuid.uuid4())[:8]
        self.username = username
        self.email = email
        self.full_name = username
        self.bio = ""
        
        # إعدادات الإشعارات
        self.email_notifications = True
        self.app_notifications = True
        self.notification_frequency = "immediate"
        
        # إعدادات الأمان
        self.two_factor_auth = False
        self.login_alerts = True
        self.totp_secret = None
        
        # إعدادات التكامل
        self.google_integration = False
        self.microsoft_integration = False
        self.api_key = str(uuid.uuid4())
        
        # إعدادات Google Drive
        self.google_drive_connected = False
        self.google_drive_token = None
        self.backup_destination = "local"  # local, google_drive
        self.auto_backup = False
        self.backup_frequency = "daily"
        
        # تفضيلات الواجهة
        self.theme = "default"
        self.language = "ar"
        self.font_size = "medium"
        
        # معلومات إضافية
        self.created_at = datetime.now()
        self.last_login = datetime.now()
        self.last_backup = None

# مستخدم تجريبي للـ Google Drive Backend
google_drive_current_user = GoogleDriveUser()

# ===== النماذج =====

class GoogleDriveProfileSettingsForm(FlaskForm):
    full_name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    bio = TextAreaField('نبذة تعريفية', validators=[Optional(), Length(max=500)])
    submit = SubmitField('حفظ الملف الشخصي')

class GoogleDriveNotificationSettingsForm(FlaskForm):
    email_notifications = BooleanField('تلقي الإشعارات عبر البريد الإلكتروني')
    app_notifications = BooleanField('تلقي الإشعارات داخل التطبيق')
    notification_frequency = SelectField('تكرار الإشعارات', 
                                        choices=[('immediate', 'فوري'), 
                                                ('daily', 'يومي'), 
                                                ('weekly', 'أسبوعي')])
    submit = SubmitField('حفظ إعدادات الإشعارات')

class GoogleDriveSecuritySettingsForm(FlaskForm):
    two_factor_auth = BooleanField('تفعيل المصادقة الثنائية')
    login_alerts = BooleanField('تلقي تنبيهات عند تسجيل الدخول من جهاز جديد')
    submit = SubmitField('حفظ إعدادات الأمان')

class GoogleDriveIntegrationSettingsForm(FlaskForm):
    google_integration = BooleanField('تكامل مع Google Classroom')
    microsoft_integration = BooleanField('تكامل مع Microsoft Teams')
    submit = SubmitField('حفظ إعدادات التكامل')

class GoogleDriveSettingsForm(FlaskForm):
    backup_destination = SelectField('وجهة النسخ الاحتياطي',
                                   choices=[('local', 'محلي'), ('google_drive', 'Google Drive')])
    auto_backup = BooleanField('نسخ احتياطي تلقائي')
    backup_frequency = SelectField('تكرار النسخ الاحتياطي',
                                 choices=[('daily', 'يومي'), ('weekly', 'أسبوعي'), ('monthly', 'شهري')])
    submit = SubmitField('حفظ إعدادات Google Drive')

class GoogleDriveUIPreferencesForm(FlaskForm):
    theme = SelectField('المظهر',
                       choices=[('default', 'افتراضي'), ('dark', 'داكن'), ('light', 'فاتح')])
    language = SelectField('اللغة',
                          choices=[('ar', 'العربية'), ('en', 'English')])
    font_size = SelectField('حجم الخط',
                           choices=[('small', 'صغير'), ('medium', 'متوسط'), ('large', 'كبير')])
    submit = SubmitField('حفظ تفضيلات الواجهة')

class GoogleDriveChangePasswordForm(FlaskForm):
    current_password = PasswordField('كلمة المرور الحالية', validators=[DataRequired()])
    new_password = PasswordField('كلمة المرور الجديدة', validators=[
        DataRequired(),
        Length(min=6, message='يجب أن تكون كلمة المرور 6 أحرف على الأقل.')
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور الجديدة', validators=[
        DataRequired(),
        EqualTo('new_password', message='كلمتا المرور غير متطابقتين.')
    ])
    submit = SubmitField('تغيير كلمة المرور')

# ===== وظائف التشفير =====

def encrypt_google_drive_data(data):
    """تشفير البيانات"""
    try:
        json_data = json.dumps(data, ensure_ascii=False)
        encrypted_data = cipher_suite.encrypt(json_data.encode('utf-8'))
        return base64.b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        print(f"خطأ في التشفير: {e}")
        return None

def decrypt_google_drive_data(encrypted_data):
    """فك تشفير البيانات"""
    try:
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted_data = cipher_suite.decrypt(encrypted_bytes)
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        print(f"خطأ في فك التشفير: {e}")
        return None

# ===== وظائف إدارة البيانات =====

def get_google_drive_user_settings():
    """جمع جميع إعدادات المستخدم"""
    return {
        'profile': {
            'full_name': google_drive_current_user.full_name,
            'email': google_drive_current_user.email,
            'bio': google_drive_current_user.bio
        },
        'notifications': {
            'email_notifications': google_drive_current_user.email_notifications,
            'app_notifications': google_drive_current_user.app_notifications,
            'notification_frequency': google_drive_current_user.notification_frequency
        },
        'security': {
            'two_factor_auth': google_drive_current_user.two_factor_auth,
            'login_alerts': google_drive_current_user.login_alerts,
            'totp_secret': google_drive_current_user.totp_secret
        },
        'integrations': {
            'google_integration': google_drive_current_user.google_integration,
            'microsoft_integration': google_drive_current_user.microsoft_integration,
            'api_key': google_drive_current_user.api_key
        },
        'google_drive': {
            'connected': google_drive_current_user.google_drive_connected,
            'backup_destination': google_drive_current_user.backup_destination,
            'auto_backup': google_drive_current_user.auto_backup,
            'backup_frequency': google_drive_current_user.backup_frequency
        },
        'ui_preferences': {
            'theme': google_drive_current_user.theme,
            'language': google_drive_current_user.language,
            'font_size': google_drive_current_user.font_size
        },
        'metadata': {
            'user_id': google_drive_current_user.id,
            'username': google_drive_current_user.username,
            'created_at': google_drive_current_user.created_at.isoformat(),
            'last_backup': google_drive_current_user.last_backup.isoformat() if google_drive_current_user.last_backup else None,
            'export_date': datetime.now().isoformat()
        }
    }

def apply_google_drive_user_settings(settings):
    """تطبيق إعدادات المستخدم"""
    try:
        if 'profile' in settings:
            google_drive_current_user.full_name = settings['profile'].get('full_name', google_drive_current_user.full_name)
            google_drive_current_user.email = settings['profile'].get('email', google_drive_current_user.email)
            google_drive_current_user.bio = settings['profile'].get('bio', google_drive_current_user.bio)
        
        if 'notifications' in settings:
            google_drive_current_user.email_notifications = settings['notifications'].get('email_notifications', google_drive_current_user.email_notifications)
            google_drive_current_user.app_notifications = settings['notifications'].get('app_notifications', google_drive_current_user.app_notifications)
            google_drive_current_user.notification_frequency = settings['notifications'].get('notification_frequency', google_drive_current_user.notification_frequency)
        
        if 'security' in settings:
            google_drive_current_user.two_factor_auth = settings['security'].get('two_factor_auth', google_drive_current_user.two_factor_auth)
            google_drive_current_user.login_alerts = settings['security'].get('login_alerts', google_drive_current_user.login_alerts)
            google_drive_current_user.totp_secret = settings['security'].get('totp_secret', google_drive_current_user.totp_secret)
        
        if 'integrations' in settings:
            google_drive_current_user.google_integration = settings['integrations'].get('google_integration', google_drive_current_user.google_integration)
            google_drive_current_user.microsoft_integration = settings['integrations'].get('microsoft_integration', google_drive_current_user.microsoft_integration)
            google_drive_current_user.api_key = settings['integrations'].get('api_key', google_drive_current_user.api_key)
        
        if 'google_drive' in settings:
            google_drive_current_user.google_drive_connected = settings['google_drive'].get('connected', google_drive_current_user.google_drive_connected)
            google_drive_current_user.backup_destination = settings['google_drive'].get('backup_destination', google_drive_current_user.backup_destination)
            google_drive_current_user.auto_backup = settings['google_drive'].get('auto_backup', google_drive_current_user.auto_backup)
            google_drive_current_user.backup_frequency = settings['google_drive'].get('backup_frequency', google_drive_current_user.backup_frequency)
        
        if 'ui_preferences' in settings:
            google_drive_current_user.theme = settings['ui_preferences'].get('theme', google_drive_current_user.theme)
            google_drive_current_user.language = settings['ui_preferences'].get('language', google_drive_current_user.language)
            google_drive_current_user.font_size = settings['ui_preferences'].get('font_size', google_drive_current_user.font_size)
        
        return True
    except Exception as e:
        print(f"خطأ في تطبيق الإعدادات: {e}")
        return False

def save_google_drive_user_data_local():
    """حفظ بيانات المستخدم محلياً"""
    try:
        user_settings = get_google_drive_user_settings()
        
        # حفظ غير مشفر للاستخدام المحلي
        with open('google_drive_user_data.json', 'w', encoding='utf-8') as f:
            json.dump(user_settings, f, ensure_ascii=False, indent=2)
        
        # حفظ مشفر للنسخ الاحتياطي
        encrypted_data = encrypt_google_drive_data(user_settings)
        if encrypted_data:
            with open('google_drive_user_data_encrypted.json', 'w', encoding='utf-8') as f:
                json.dump({'encrypted_data': encrypted_data}, f)
        
        return True
    except Exception as e:
        print(f"خطأ في حفظ البيانات محلياً: {e}")
        return False

def load_google_drive_user_data_local():
    """تحميل بيانات المستخدم محلياً"""
    try:
        if os.path.exists('google_drive_user_data.json'):
            with open('google_drive_user_data.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            return apply_google_drive_user_settings(settings)
        return False
    except Exception as e:
        print(f"خطأ في تحميل البيانات محلياً: {e}")
        return False

def save_to_google_drive_backend():
    """حفظ البيانات في Google Drive (محاكاة)"""
    try:
        user_settings = get_google_drive_user_settings()
        encrypted_data = encrypt_google_drive_data(user_settings)
        
        if not encrypted_data:
            return False, "فشل في تشفير البيانات"
        
        # محاكاة رفع البيانات إلى Google Drive
        google_drive_data = {
            'file_name': f'google_drive_user_settings_{google_drive_current_user.id}.json',
            'encrypted_data': encrypted_data,
            'upload_date': datetime.now().isoformat(),
            'file_size': len(encrypted_data),
            'checksum': hash(encrypted_data)
        }
        
        # حفظ محاكاة Google Drive محلياً
        with open('google_drive_backend_backup.json', 'w', encoding='utf-8') as f:
            json.dump(google_drive_data, f, ensure_ascii=False, indent=2)
        
        # تحديث تاريخ آخر نسخة احتياطية
        google_drive_current_user.last_backup = datetime.now()
        save_google_drive_user_data_local()
        
        return True, "تم حفظ البيانات في Google Drive بنجاح"
        
    except Exception as e:
        return False, f"خطأ في حفظ البيانات في Google Drive: {str(e)}"

def load_from_google_drive_backend():
    """تحميل البيانات من Google Drive (محاكاة)"""
    try:
        if not os.path.exists('google_drive_backend_backup.json'):
            return False, "لا توجد نسخة احتياطية في Google Drive"
        
        with open('google_drive_backend_backup.json', 'r', encoding='utf-8') as f:
            google_drive_data = json.load(f)
        
        encrypted_data = google_drive_data.get('encrypted_data')
        if not encrypted_data:
            return False, "البيانات المشفرة غير موجودة"
        
        # فك تشفير البيانات
        settings = decrypt_google_drive_data(encrypted_data)
        if not settings:
            return False, "فشل في فك تشفير البيانات"
        
        # تطبيق الإعدادات
        if apply_google_drive_user_settings(settings):
            save_google_drive_user_data_local()  # حفظ محلي أيضاً
            return True, "تم تحميل البيانات من Google Drive بنجاح"
        else:
            return False, "فشل في تطبيق الإعدادات"
            
    except Exception as e:
        return False, f"خطأ في تحميل البيانات من Google Drive: {str(e)}"

def get_google_drive_dashboard_stats():
    """إحصائيات لوحة التحكم"""
    return {
        'total_questions': 93,
        'active_questions': 70,
        'total_users': 51,
        'pending_questions': 14,
        'monthly_stats': [12, 19, 3, 5, 2, 3],
        'question_types': {
            'عضوية': 45,
            'غير_عضوية': 25,
            'فيزيائية': 15,
            'تحليلية': 8
        }
    }

# ===== المسارات الرئيسية =====

@google_drive_backend_bp.route('/google-drive-dashboard')
def google_drive_index():
    """الصفحة الرئيسية لـ Google Drive Backend"""
    stats = get_google_drive_dashboard_stats()
    return render_template('google_drive_index_complete.html', **stats, current_user=google_drive_current_user)

@google_drive_backend_bp.route('/google-drive-settings', methods=['GET', 'POST'])
def google_drive_settings():
    """صفحة الإعدادات الشاملة لـ Google Drive"""
    # تحميل بيانات المستخدم
    load_google_drive_user_data_local()
    
    # إنشاء النماذج
    profile_form = GoogleDriveProfileSettingsForm()
    notification_form = GoogleDriveNotificationSettingsForm()
    security_form = GoogleDriveSecuritySettingsForm()
    integration_form = GoogleDriveIntegrationSettingsForm()
    google_drive_form = GoogleDriveSettingsForm()
    ui_form = GoogleDriveUIPreferencesForm()
    password_form = GoogleDriveChangePasswordForm()
    
    # تعبئة النماذج بالبيانات الحالية
    if request.method == 'GET':
        # الملف الشخصي
        profile_form.full_name.data = google_drive_current_user.full_name
        profile_form.email.data = google_drive_current_user.email
        profile_form.bio.data = google_drive_current_user.bio
        
        # الإشعارات
        notification_form.email_notifications.data = google_drive_current_user.email_notifications
        notification_form.app_notifications.data = google_drive_current_user.app_notifications
        notification_form.notification_frequency.data = google_drive_current_user.notification_frequency
        
        # الأمان
        security_form.two_factor_auth.data = google_drive_current_user.two_factor_auth
        security_form.login_alerts.data = google_drive_current_user.login_alerts
        
        # التكاملات
        integration_form.google_integration.data = google_drive_current_user.google_integration
        integration_form.microsoft_integration.data = google_drive_current_user.microsoft_integration
        
        # Google Drive
        google_drive_form.backup_destination.data = google_drive_current_user.backup_destination
        google_drive_form.auto_backup.data = google_drive_current_user.auto_backup
        google_drive_form.backup_frequency.data = google_drive_current_user.backup_frequency
        
        # تفضيلات الواجهة
        ui_form.theme.data = google_drive_current_user.theme
        ui_form.language.data = google_drive_current_user.language
        ui_form.font_size.data = google_drive_current_user.font_size
    
    # معالجة النماذج عند الإرسال
    if request.method == 'POST':
        success = False
        message = ""
        
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            google_drive_current_user.full_name = profile_form.full_name.data
            google_drive_current_user.email = profile_form.email.data
            google_drive_current_user.bio = profile_form.bio.data
            success = save_google_drive_user_data_local()
            message = 'تم تحديث الملف الشخصي بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'notification_submit' in request.form and notification_form.validate_on_submit():
            google_drive_current_user.email_notifications = notification_form.email_notifications.data
            google_drive_current_user.app_notifications = notification_form.app_notifications.data
            google_drive_current_user.notification_frequency = notification_form.notification_frequency.data
            success = save_google_drive_user_data_local()
            message = 'تم تحديث إعدادات الإشعارات بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'security_submit' in request.form and security_form.validate_on_submit():
            google_drive_current_user.two_factor_auth = security_form.two_factor_auth.data
            google_drive_current_user.login_alerts = security_form.login_alerts.data
            success = save_google_drive_user_data_local()
            message = 'تم تحديث إعدادات الأمان بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'integration_submit' in request.form and integration_form.validate_on_submit():
            google_drive_current_user.google_integration = integration_form.google_integration.data
            google_drive_current_user.microsoft_integration = integration_form.microsoft_integration.data
            
            if 'regenerate_api_key' in request.form:
                google_drive_current_user.api_key = str(uuid.uuid4())
            
            success = save_google_drive_user_data_local()
            message = 'تم تحديث إعدادات التكاملات بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'google_drive_submit' in request.form and google_drive_form.validate_on_submit():
            google_drive_current_user.backup_destination = google_drive_form.backup_destination.data
            google_drive_current_user.auto_backup = google_drive_form.auto_backup.data
            google_drive_current_user.backup_frequency = google_drive_form.backup_frequency.data
            success = save_google_drive_user_data_local()
            message = 'تم تحديث إعدادات Google Drive بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'ui_submit' in request.form and ui_form.validate_on_submit():
            google_drive_current_user.theme = ui_form.theme.data
            google_drive_current_user.language = ui_form.language.data
            google_drive_current_user.font_size = ui_form.font_size.data
            success = save_google_drive_user_data_local()
            message = 'تم تحديث تفضيلات الواجهة بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'password_submit' in request.form and password_form.validate_on_submit():
            # تغيير كلمة المرور (محاكاة)
            success = True
            message = 'تم تغيير كلمة المرور بنجاح'
        
        flash(message, 'success' if success else 'error')
        return redirect(url_for('google_drive_backend.google_drive_settings'))
    
    return render_template('google_drive_settings_complete.html', 
                          profile_form=profile_form,
                          notification_form=notification_form,
                          security_form=security_form,
                          integration_form=integration_form,
                          google_drive_form=google_drive_form,
                          ui_form=ui_form,
                          password_form=password_form,
                          current_user=google_drive_current_user)

# ===== مسارات Google Drive API =====

@google_drive_backend_bp.route('/api/v1/google-drive-backend/connect', methods=['POST'])
def connect_google_drive_backend():
    """ربط Google Drive"""
    try:
        # محاكاة عملية الربط
        google_drive_current_user.google_drive_connected = True
        google_drive_current_user.google_drive_token = f"token_{uuid.uuid4()}"
        
        if save_google_drive_user_data_local():
            return jsonify({
                'success': True,
                'message': 'تم ربط Google Drive بنجاح',
                'connected': True
            })
        else:
            return jsonify({
                'success': False,
                'message': 'فشل في حفظ معلومات الاتصال'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في ربط Google Drive: {str(e)}'
        }), 500

@google_drive_backend_bp.route('/api/v1/google-drive-backend/disconnect', methods=['POST'])
def disconnect_google_drive_backend():
    """قطع الاتصال مع Google Drive"""
    try:
        google_drive_current_user.google_drive_connected = False
        google_drive_current_user.google_drive_token = None
        google_drive_current_user.backup_destination = "local"
        
        if save_google_drive_user_data_local():
            return jsonify({
                'success': True,
                'message': 'تم قطع الاتصال مع Google Drive',
                'connected': False
            })
        else:
            return jsonify({
                'success': False,
                'message': 'فشل في حفظ التغييرات'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في قطع الاتصال: {str(e)}'
        }), 500

@google_drive_backend_bp.route('/api/v1/google-drive-backend/connection-status')
def google_drive_backend_status():
    """فحص حالة اتصال Google Drive"""
    return jsonify({
        'success': True,
        'connected': google_drive_current_user.google_drive_connected,
        'backup_destination': google_drive_current_user.backup_destination,
        'last_backup': google_drive_current_user.last_backup.isoformat() if google_drive_current_user.last_backup else None,
        'auto_backup': google_drive_current_user.auto_backup
    })

@google_drive_backend_bp.route('/api/google-drive-backend/save-settings', methods=['POST'])
def save_settings_to_google_drive_backend():
    """حفظ الإعدادات في Google Drive"""
    if not google_drive_current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    success, message = save_to_google_drive_backend()
    
    return jsonify({
        'success': success,
        'message': message,
        'timestamp': datetime.now().isoformat()
    })

@google_drive_backend_bp.route('/api/google-drive-backend/load-settings', methods=['POST'])
def load_settings_from_google_drive_backend():
    """تحميل الإعدادات من Google Drive"""
    if not google_drive_current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    success, message = load_from_google_drive_backend()
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'settings': get_google_drive_user_settings()
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 500

@google_drive_backend_bp.route('/api/google-drive-backend/sync', methods=['POST'])
def sync_with_google_drive_backend():
    """مزامنة شاملة مع Google Drive"""
    if not google_drive_current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        # حفظ أولاً
        save_success, save_message = save_to_google_drive_backend()
        if not save_success:
            return jsonify({
                'success': False,
                'message': f'فشل في الحفظ: {save_message}'
            }), 500
        
        # ثم تحميل للتأكد من التزامن
        load_success, load_message = load_from_google_drive_backend()
        if not load_success:
            return jsonify({
                'success': False,
                'message': f'فشل في التحميل: {load_message}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم إجراء مزامنة شاملة بنجاح',
            'timestamp': datetime.now().isoformat(),
            'settings': get_google_drive_user_settings()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في المزامنة: {str(e)}'
        }), 500

# ===== مسارات إضافية =====

@google_drive_backend_bp.route('/google-drive-add-question')
def google_drive_add_question():
    """صفحة إضافة سؤال"""
    return render_template('google_drive_add_question.html', current_user=google_drive_current_user)

@google_drive_backend_bp.route('/google-drive-manage-questions')
def google_drive_manage_questions():
    """صفحة إدارة الأسئلة"""
    return render_template('google_drive_manage_questions.html', current_user=google_drive_current_user)

@google_drive_backend_bp.route('/api/google-drive-backend/user/export')
def export_google_drive_user_data():
    """تصدير جميع بيانات المستخدم"""
    user_settings = get_google_drive_user_settings()
    return jsonify({
        'success': True,
        'data': user_settings,
        'message': 'تم تصدير البيانات بنجاح'
    })

@google_drive_backend_bp.route('/api/google-drive-backend/user/import', methods=['POST'])
def import_google_drive_user_data():
    """استيراد بيانات المستخدم"""
    try:
        data = request.get_json()
        
        if apply_google_drive_user_settings(data):
            save_google_drive_user_data_local()
            return jsonify({
                'success': True,
                'message': 'تم استيراد البيانات بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'فشل في تطبيق البيانات'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في استيراد البيانات: {str(e)}'
        }), 400

# ===== مسارات user-settings للمزامنة =====

@google_drive_backend_bp.route('/api/v1/google-drive-backend/user-settings/sync-to-drive', methods=['POST'])
def sync_settings_to_drive_backend():
    """رفع الإعدادات إلى Google Drive"""
    if not google_drive_current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        success, message = save_to_google_drive_backend()
        return jsonify({
            'success': success,
            'message': message,
            'last_sync': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في المزامنة: {str(e)}'
        }), 500

@google_drive_backend_bp.route('/api/v1/google-drive-backend/user-settings/download-from-drive', methods=['POST'])
def download_settings_from_drive_backend():
    """تحميل الإعدادات من Google Drive"""
    if not google_drive_current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        success, message = load_from_google_drive_backend()
        return jsonify({
            'success': success,
            'message': message,
            'last_sync': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في التحميل: {str(e)}'
        }), 500

@google_drive_backend_bp.route('/api/v1/google-drive-backend/user-settings/quick-sync', methods=['POST'])
def quick_sync_backend():
    """مزامنة سريعة للإعدادات"""
    if not google_drive_current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        # رفع الإعدادات أولاً
        save_success, save_message = save_to_google_drive_backend()
        if not save_success:
            return jsonify({
                'success': False,
                'message': f'فشل في رفع الإعدادات: {save_message}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تمت المزامنة السريعة بنجاح',
            'last_sync': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في المزامنة السريعة: {str(e)}'
        }), 500

# ===== دالة تسجيل Blueprint =====

def register_google_drive_backend_routes(app):
    """تسجيل Google Drive Backend routes في التطبيق الرئيسي"""
    try:
        app.register_blueprint(google_drive_backend_bp, url_prefix='/google-drive-backend')
        
        # تحميل بيانات المستخدم عند بدء التشغيل
        load_google_drive_user_data_local()
        
        print("🚀 تم تسجيل Google Drive Backend routes بنجاح")
        print("📱 الوصول للتطبيق: /google-drive-backend/google-drive-dashboard")
        print("⚙️ صفحة الإعدادات: /google-drive-backend/google-drive-settings")
        print("☁️ مزامنة Google Drive متاحة")
        
        return True
    except Exception as e:
        print(f"خطأ في تسجيل Google Drive Backend routes: {e}")
        return False

# معلومات Blueprint للتصدير
__all__ = ['google_drive_backend_bp', 'register_google_drive_backend_routes']

