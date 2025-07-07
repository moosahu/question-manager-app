# complete_app_with_google_drive.py
# تطبيق Flask متكامل مع نظام مزامنة Google Drive

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
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

# إنشاء التطبيق
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

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

class User:
    """نموذج شامل للمستخدم"""
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

# مستخدم تجريبي
current_user = User()

# ===== النماذج =====

class ProfileSettingsForm(FlaskForm):
    full_name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    bio = TextAreaField('نبذة تعريفية', validators=[Optional(), Length(max=500)])
    submit = SubmitField('حفظ الملف الشخصي')

class NotificationSettingsForm(FlaskForm):
    email_notifications = BooleanField('تلقي الإشعارات عبر البريد الإلكتروني')
    app_notifications = BooleanField('تلقي الإشعارات داخل التطبيق')
    notification_frequency = SelectField('تكرار الإشعارات', 
                                        choices=[('immediate', 'فوري'), 
                                                ('daily', 'يومي'), 
                                                ('weekly', 'أسبوعي')])
    submit = SubmitField('حفظ إعدادات الإشعارات')

class SecuritySettingsForm(FlaskForm):
    two_factor_auth = BooleanField('تفعيل المصادقة الثنائية')
    login_alerts = BooleanField('تلقي تنبيهات عند تسجيل الدخول من جهاز جديد')
    submit = SubmitField('حفظ إعدادات الأمان')

class IntegrationSettingsForm(FlaskForm):
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

class UIPreferencesForm(FlaskForm):
    theme = SelectField('المظهر',
                       choices=[('default', 'افتراضي'), ('dark', 'داكن'), ('light', 'فاتح')])
    language = SelectField('اللغة',
                          choices=[('ar', 'العربية'), ('en', 'English')])
    font_size = SelectField('حجم الخط',
                           choices=[('small', 'صغير'), ('medium', 'متوسط'), ('large', 'كبير')])
    submit = SubmitField('حفظ تفضيلات الواجهة')

class ChangePasswordForm(FlaskForm):
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

def encrypt_data(data):
    """تشفير البيانات"""
    try:
        json_data = json.dumps(data, ensure_ascii=False)
        encrypted_data = cipher_suite.encrypt(json_data.encode('utf-8'))
        return base64.b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        print(f"خطأ في التشفير: {e}")
        return None

def decrypt_data(encrypted_data):
    """فك تشفير البيانات"""
    try:
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted_data = cipher_suite.decrypt(encrypted_bytes)
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        print(f"خطأ في فك التشفير: {e}")
        return None

# ===== وظائف إدارة البيانات =====

def get_user_settings():
    """جمع جميع إعدادات المستخدم"""
    return {
        'profile': {
            'full_name': current_user.full_name,
            'email': current_user.email,
            'bio': current_user.bio
        },
        'notifications': {
            'email_notifications': current_user.email_notifications,
            'app_notifications': current_user.app_notifications,
            'notification_frequency': current_user.notification_frequency
        },
        'security': {
            'two_factor_auth': current_user.two_factor_auth,
            'login_alerts': current_user.login_alerts,
            'totp_secret': current_user.totp_secret
        },
        'integrations': {
            'google_integration': current_user.google_integration,
            'microsoft_integration': current_user.microsoft_integration,
            'api_key': current_user.api_key
        },
        'google_drive': {
            'connected': current_user.google_drive_connected,
            'backup_destination': current_user.backup_destination,
            'auto_backup': current_user.auto_backup,
            'backup_frequency': current_user.backup_frequency
        },
        'ui_preferences': {
            'theme': current_user.theme,
            'language': current_user.language,
            'font_size': current_user.font_size
        },
        'metadata': {
            'user_id': current_user.id,
            'username': current_user.username,
            'created_at': current_user.created_at.isoformat(),
            'last_backup': current_user.last_backup.isoformat() if current_user.last_backup else None,
            'export_date': datetime.now().isoformat()
        }
    }

def apply_user_settings(settings):
    """تطبيق إعدادات المستخدم"""
    try:
        if 'profile' in settings:
            current_user.full_name = settings['profile'].get('full_name', current_user.full_name)
            current_user.email = settings['profile'].get('email', current_user.email)
            current_user.bio = settings['profile'].get('bio', current_user.bio)
        
        if 'notifications' in settings:
            current_user.email_notifications = settings['notifications'].get('email_notifications', current_user.email_notifications)
            current_user.app_notifications = settings['notifications'].get('app_notifications', current_user.app_notifications)
            current_user.notification_frequency = settings['notifications'].get('notification_frequency', current_user.notification_frequency)
        
        if 'security' in settings:
            current_user.two_factor_auth = settings['security'].get('two_factor_auth', current_user.two_factor_auth)
            current_user.login_alerts = settings['security'].get('login_alerts', current_user.login_alerts)
            current_user.totp_secret = settings['security'].get('totp_secret', current_user.totp_secret)
        
        if 'integrations' in settings:
            current_user.google_integration = settings['integrations'].get('google_integration', current_user.google_integration)
            current_user.microsoft_integration = settings['integrations'].get('microsoft_integration', current_user.microsoft_integration)
            current_user.api_key = settings['integrations'].get('api_key', current_user.api_key)
        
        if 'google_drive' in settings:
            current_user.google_drive_connected = settings['google_drive'].get('connected', current_user.google_drive_connected)
            current_user.backup_destination = settings['google_drive'].get('backup_destination', current_user.backup_destination)
            current_user.auto_backup = settings['google_drive'].get('auto_backup', current_user.auto_backup)
            current_user.backup_frequency = settings['google_drive'].get('backup_frequency', current_user.backup_frequency)
        
        if 'ui_preferences' in settings:
            current_user.theme = settings['ui_preferences'].get('theme', current_user.theme)
            current_user.language = settings['ui_preferences'].get('language', current_user.language)
            current_user.font_size = settings['ui_preferences'].get('font_size', current_user.font_size)
        
        return True
    except Exception as e:
        print(f"خطأ في تطبيق الإعدادات: {e}")
        return False

def save_user_data_local():
    """حفظ بيانات المستخدم محلياً"""
    try:
        user_settings = get_user_settings()
        
        # حفظ غير مشفر للاستخدام المحلي
        with open('user_data.json', 'w', encoding='utf-8') as f:
            json.dump(user_settings, f, ensure_ascii=False, indent=2)
        
        # حفظ مشفر للنسخ الاحتياطي
        encrypted_data = encrypt_data(user_settings)
        if encrypted_data:
            with open('user_data_encrypted.json', 'w', encoding='utf-8') as f:
                json.dump({'encrypted_data': encrypted_data}, f)
        
        return True
    except Exception as e:
        print(f"خطأ في حفظ البيانات محلياً: {e}")
        return False

def load_user_data_local():
    """تحميل بيانات المستخدم محلياً"""
    try:
        if os.path.exists('user_data.json'):
            with open('user_data.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            return apply_user_settings(settings)
        return False
    except Exception as e:
        print(f"خطأ في تحميل البيانات محلياً: {e}")
        return False

def save_to_google_drive():
    """حفظ البيانات في Google Drive (محاكاة)"""
    try:
        user_settings = get_user_settings()
        encrypted_data = encrypt_data(user_settings)
        
        if not encrypted_data:
            return False, "فشل في تشفير البيانات"
        
        # محاكاة رفع البيانات إلى Google Drive
        google_drive_data = {
            'file_name': f'user_settings_{current_user.id}.json',
            'encrypted_data': encrypted_data,
            'upload_date': datetime.now().isoformat(),
            'file_size': len(encrypted_data),
            'checksum': hash(encrypted_data)
        }
        
        # حفظ محاكاة Google Drive محلياً
        with open('google_drive_backup.json', 'w', encoding='utf-8') as f:
            json.dump(google_drive_data, f, ensure_ascii=False, indent=2)
        
        # تحديث تاريخ آخر نسخة احتياطية
        current_user.last_backup = datetime.now()
        save_user_data_local()
        
        return True, "تم حفظ البيانات في Google Drive بنجاح"
        
    except Exception as e:
        return False, f"خطأ في حفظ البيانات في Google Drive: {str(e)}"

def load_from_google_drive():
    """تحميل البيانات من Google Drive (محاكاة)"""
    try:
        if not os.path.exists('google_drive_backup.json'):
            return False, "لا توجد نسخة احتياطية في Google Drive"
        
        with open('google_drive_backup.json', 'r', encoding='utf-8') as f:
            google_drive_data = json.load(f)
        
        encrypted_data = google_drive_data.get('encrypted_data')
        if not encrypted_data:
            return False, "البيانات المشفرة غير موجودة"
        
        # فك تشفير البيانات
        settings = decrypt_data(encrypted_data)
        if not settings:
            return False, "فشل في فك تشفير البيانات"
        
        # تطبيق الإعدادات
        if apply_user_settings(settings):
            save_user_data_local()  # حفظ محلي أيضاً
            return True, "تم تحميل البيانات من Google Drive بنجاح"
        else:
            return False, "فشل في تطبيق الإعدادات"
            
    except Exception as e:
        return False, f"خطأ في تحميل البيانات من Google Drive: {str(e)}"

def get_dashboard_stats():
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

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    stats = get_dashboard_stats()
    return render_template('index_complete.html', **stats, current_user=current_user)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """صفحة الإعدادات الشاملة"""
    # تحميل بيانات المستخدم
    load_user_data_local()
    
    # إنشاء النماذج
    profile_form = ProfileSettingsForm()
    notification_form = NotificationSettingsForm()
    security_form = SecuritySettingsForm()
    integration_form = IntegrationSettingsForm()
    google_drive_form = GoogleDriveSettingsForm()
    ui_form = UIPreferencesForm()
    password_form = ChangePasswordForm()
    
    # تعبئة النماذج بالبيانات الحالية
    if request.method == 'GET':
        # الملف الشخصي
        profile_form.full_name.data = current_user.full_name
        profile_form.email.data = current_user.email
        profile_form.bio.data = current_user.bio
        
        # الإشعارات
        notification_form.email_notifications.data = current_user.email_notifications
        notification_form.app_notifications.data = current_user.app_notifications
        notification_form.notification_frequency.data = current_user.notification_frequency
        
        # الأمان
        security_form.two_factor_auth.data = current_user.two_factor_auth
        security_form.login_alerts.data = current_user.login_alerts
        
        # التكاملات
        integration_form.google_integration.data = current_user.google_integration
        integration_form.microsoft_integration.data = current_user.microsoft_integration
        
        # Google Drive
        google_drive_form.backup_destination.data = current_user.backup_destination
        google_drive_form.auto_backup.data = current_user.auto_backup
        google_drive_form.backup_frequency.data = current_user.backup_frequency
        
        # تفضيلات الواجهة
        ui_form.theme.data = current_user.theme
        ui_form.language.data = current_user.language
        ui_form.font_size.data = current_user.font_size
    
    # معالجة النماذج عند الإرسال
    if request.method == 'POST':
        success = False
        message = ""
        
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            current_user.full_name = profile_form.full_name.data
            current_user.email = profile_form.email.data
            current_user.bio = profile_form.bio.data
            success = save_user_data_local()
            message = 'تم تحديث الملف الشخصي بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'notification_submit' in request.form and notification_form.validate_on_submit():
            current_user.email_notifications = notification_form.email_notifications.data
            current_user.app_notifications = notification_form.app_notifications.data
            current_user.notification_frequency = notification_form.notification_frequency.data
            success = save_user_data_local()
            message = 'تم تحديث إعدادات الإشعارات بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'security_submit' in request.form and security_form.validate_on_submit():
            current_user.two_factor_auth = security_form.two_factor_auth.data
            current_user.login_alerts = security_form.login_alerts.data
            success = save_user_data_local()
            message = 'تم تحديث إعدادات الأمان بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'integration_submit' in request.form and integration_form.validate_on_submit():
            current_user.google_integration = integration_form.google_integration.data
            current_user.microsoft_integration = integration_form.microsoft_integration.data
            
            if 'regenerate_api_key' in request.form:
                current_user.api_key = str(uuid.uuid4())
            
            success = save_user_data_local()
            message = 'تم تحديث إعدادات التكاملات بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'google_drive_submit' in request.form and google_drive_form.validate_on_submit():
            current_user.backup_destination = google_drive_form.backup_destination.data
            current_user.auto_backup = google_drive_form.auto_backup.data
            current_user.backup_frequency = google_drive_form.backup_frequency.data
            success = save_user_data_local()
            message = 'تم تحديث إعدادات Google Drive بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'ui_submit' in request.form and ui_form.validate_on_submit():
            current_user.theme = ui_form.theme.data
            current_user.language = ui_form.language.data
            current_user.font_size = ui_form.font_size.data
            success = save_user_data_local()
            message = 'تم تحديث تفضيلات الواجهة بنجاح' if success else 'حدث خطأ في حفظ البيانات'
            
        elif 'password_submit' in request.form and password_form.validate_on_submit():
            # تغيير كلمة المرور (محاكاة)
            success = True
            message = 'تم تغيير كلمة المرور بنجاح'
        
        flash(message, 'success' if success else 'error')
        return redirect(url_for('settings'))
    
    return render_template('settings_complete.html', 
                          profile_form=profile_form,
                          notification_form=notification_form,
                          security_form=security_form,
                          integration_form=integration_form,
                          google_drive_form=google_drive_form,
                          ui_form=ui_form,
                          password_form=password_form,
                          current_user=current_user)

# ===== مسارات Google Drive API =====

@app.route('/api/v1/google-drive/connect', methods=['POST'])
def connect_google_drive():
    """ربط Google Drive"""
    try:
        # محاكاة عملية الربط
        current_user.google_drive_connected = True
        current_user.google_drive_token = f"token_{uuid.uuid4()}"
        
        if save_user_data_local():
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

@app.route('/api/v1/google-drive/disconnect', methods=['POST'])
def disconnect_google_drive():
    """قطع الاتصال مع Google Drive"""
    try:
        current_user.google_drive_connected = False
        current_user.google_drive_token = None
        current_user.backup_destination = "local"
        
        if save_user_data_local():
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

@app.route('/api/v1/google-drive/connection-status')
def google_drive_status():
    """فحص حالة اتصال Google Drive"""
    return jsonify({
        'success': True,
        'connected': current_user.google_drive_connected,
        'backup_destination': current_user.backup_destination,
        'last_backup': current_user.last_backup.isoformat() if current_user.last_backup else None,
        'auto_backup': current_user.auto_backup
    })

@app.route('/api/google-drive/save-settings', methods=['POST'])
def save_settings_to_google_drive():
    """حفظ الإعدادات في Google Drive"""
    if not current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    success, message = save_to_google_drive()
    
    return jsonify({
        'success': success,
        'message': message,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/google-drive/load-settings', methods=['POST'])
def load_settings_from_google_drive():
    """تحميل الإعدادات من Google Drive"""
    if not current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    success, message = load_from_google_drive()
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'settings': get_user_settings()
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 500

@app.route('/api/google-drive/sync', methods=['POST'])
def sync_with_google_drive():
    """مزامنة شاملة مع Google Drive"""
    if not current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        # حفظ أولاً
        save_success, save_message = save_to_google_drive()
        if not save_success:
            return jsonify({
                'success': False,
                'message': f'فشل في الحفظ: {save_message}'
            }), 500
        
        # ثم تحميل للتأكد من التزامن
        load_success, load_message = load_from_google_drive()
        if not load_success:
            return jsonify({
                'success': False,
                'message': f'فشل في التحميل: {load_message}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم إجراء مزامنة شاملة بنجاح',
            'timestamp': datetime.now().isoformat(),
            'settings': get_user_settings()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في المزامنة: {str(e)}'
        }), 500

# ===== مسارات إضافية =====

@app.route('/add_question')
def add_question():
    """صفحة إضافة سؤال"""
    return render_template('add_question.html', current_user=current_user)

@app.route('/manage_questions')
def manage_questions():
    """صفحة إدارة الأسئلة"""
    return render_template('manage_questions.html', current_user=current_user)

@app.route('/api/user/export')
def export_user_data():
    """تصدير جميع بيانات المستخدم"""
    user_settings = get_user_settings()
    return jsonify({
        'success': True,
        'data': user_settings,
        'message': 'تم تصدير البيانات بنجاح'
    })

@app.route('/api/user/import', methods=['POST'])
def import_user_data():
    """استيراد بيانات المستخدم"""
    try:
        data = request.get_json()
        
        if apply_user_settings(data):
            save_user_data_local()
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

@app.route('/api/v1/user-settings/sync-to-drive', methods=['POST'])
def sync_settings_to_drive():
    """رفع الإعدادات إلى Google Drive"""
    if not current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        success, message = save_to_google_drive()
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

@app.route('/api/v1/user-settings/download-from-drive', methods=['POST'])
def download_settings_from_drive():
    """تحميل الإعدادات من Google Drive"""
    if not current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        success, message = load_from_google_drive()
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

@app.route('/api/v1/user-settings/quick-sync', methods=['POST'])
def quick_sync():
    """مزامنة سريعة للإعدادات"""
    if not current_user.google_drive_connected:
        return jsonify({
            'success': False,
            'message': 'يجب ربط Google Drive أولاً'
        }), 400
    
    try:
        # رفع الإعدادات أولاً
        save_success, save_message = save_to_google_drive()
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

# ===== تشغيل التطبيق =====

if __name__ == '__main__':
    print("🚀 بدء تشغيل التطبيق الكامل مع نظام Google Drive")
    print("📱 الوصول للتطبيق: http://localhost:5001")
    print("⚙️ صفحة الإعدادات: http://localhost:5001/settings")
    print("☁️ مزامنة Google Drive متاحة")
    
    # تحميل بيانات المستخدم عند بدء التشغيل
    load_user_data_local()
    
    app.run(host='0.0.0.0', port=5002, debug=True)

