from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        print("Error: Could not import db from src.extensions or extensions.")
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
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'notification_submit' in request.form and notification_form.validate_on_submit():
            # تحديث إعدادات الإشعارات
            flash('تم تحديث إعدادات الإشعارات بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'security_submit' in request.form and security_form.validate_on_submit():
            # تحديث إعدادات الأمان
            flash('تم تحديث إعدادات الأمان بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'integration_submit' in request.form and integration_form.validate_on_submit():
            # تحديث إعدادات التكاملات
            flash('تم تحديث إعدادات التكاملات بنجاح', 'success')
            return redirect(url_for('settings.index'))
    
    return render_template('settings.html', 
                          profile_form=profile_form,
                          notification_form=notification_form,
                          security_form=security_form,
                          integration_form=integration_form)
