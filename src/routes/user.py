from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash

# Assuming db is imported from extensions or main app
# If you have src/extensions.py, use: from src.extensions import db
# Otherwise, adjust the import based on your structure
try:
    from src.extensions import db
except ImportError:
    # Fallback if extensions.py doesn't exist (adjust as needed)
    from src.main import db

# Assuming User model is imported
from src.models.user import User

# إضافة استيراد نظام الإشعارات
try:
    from src.utils.notification_system import UserNotifications, SystemNotifications
    notifications_available = True
except ImportError:
    try:
        from utils.notification_system import UserNotifications, SystemNotifications
        notifications_available = True
    except ImportError:
        print("Warning: Could not import notification system for users")
        UserNotifications = None
        SystemNotifications = None
        notifications_available = False

# Assuming you have forms defined in src/forms.py
try:
    from src.forms import ChangePasswordForm, ProfileForm
except ImportError:
    # Define a basic form here if forms.py or ChangePasswordForm doesn't exist
    from flask_wtf import FlaskForm
    from wtforms import PasswordField, SubmitField, StringField, TextAreaField, EmailField
    from wtforms.validators import DataRequired, EqualTo, Length, Email, Optional
    
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
    
    class ProfileForm(FlaskForm):
        full_name = StringField('الاسم الكامل', validators=[Optional(), Length(max=100)])
        email = EmailField('البريد الإلكتروني', validators=[Optional(), Email()])
        bio = TextAreaField('نبذة تعريفية', validators=[Optional()])
        submit = SubmitField('حفظ التغييرات')

user_bp = Blueprint("user", __name__, template_folder="../templates/user")

@user_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Check current password
        if not current_user.check_password(form.current_password.data):
            flash("كلمة المرور الحالية غير صحيحة.", "danger")
        elif form.new_password.data == form.current_password.data:
            flash("كلمة المرور الجديدة يجب أن تكون مختلفة عن الحالية.", "warning")
        else:
            # Update password
            try:
                current_user.set_password(form.new_password.data)
                db.session.commit()
                
                # === إضافة الإشعارات ===
                if notifications_available and SystemNotifications:
                    try:
                        SystemNotifications.notify_settings_updated(
                            setting_name="كلمة المرور",
                            user_id=current_user.id
                        )
                        current_app.logger.info(f"Password change notification sent for user: {current_user.username}")
                    except Exception as e:
                        current_app.logger.error(f"Error sending password change notification: {e}")
                
                flash("تم تغيير كلمة المرور بنجاح!", "success")
                return redirect(url_for("index")) # Redirect to dashboard or profile
            except Exception as e:
                db.session.rollback()
                flash(f"حدث خطأ أثناء تحديث كلمة المرور: {e}", "danger")
    return render_template("user/change_password.html", form=form, title="تغيير كلمة المرور")

@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm()
    
    # عند فتح الصفحة، املأ النموذج بالبيانات الحالية
    if request.method == 'GET':
        form.full_name.data = current_user.full_name
        form.email.data = current_user.email
        form.bio.data = current_user.bio
    
    # عند إرسال النموذج، تحقق من صحة البيانات وحفظها
    if form.validate_on_submit():
        try:
            current_user.full_name = form.full_name.data
            current_user.email = form.email.data
            current_user.bio = form.bio.data
            db.session.commit()
            
            # === إضافة الإشعارات ===
            if notifications_available and SystemNotifications:
                try:
                    SystemNotifications.notify_settings_updated(
                        setting_name="الملف الشخصي",
                        user_id=current_user.id
                    )
                    current_app.logger.info(f"Profile update notification sent for user: {current_user.username}")
                except Exception as e:
                    current_app.logger.error(f"Error sending profile update notification: {e}")
            
            flash("تم تحديث الملف الشخصي بنجاح!", "success")
            return redirect(url_for("user.profile"))
        except Exception as e:
            db.session.rollback()
            flash(f"حدث خطأ أثناء تحديث الملف الشخصي: {e}", "danger")
    
    return render_template("user/profile.html", form=form, title="الملف الشخصي")

# === دوال مساعدة للإشعارات ===

def notify_user_operation(operation_type, details=None):
    """
    دالة مساعدة موحدة لإرسال إشعارات عمليات المستخدمين
    """
    if not notifications_available or not SystemNotifications:
        return
    
    try:
        if operation_type == "password_change":
            SystemNotifications.notify_settings_updated(
                setting_name="كلمة المرور",
                user_id=current_user.id
            )
        elif operation_type == "profile_update":
            SystemNotifications.notify_settings_updated(
                setting_name="الملف الشخصي",
                user_id=current_user.id
            )
        elif operation_type == "email_change":
            SystemNotifications.notify_settings_updated(
                setting_name="البريد الإلكتروني",
                user_id=current_user.id
            )
        elif operation_type == "account_settings":
            SystemNotifications.notify_settings_updated(
                setting_name=details or "إعدادات الحساب",
                user_id=current_user.id
            )
            
        current_app.logger.info(f"User {operation_type} notification sent successfully")
        
    except Exception as e:
        current_app.logger.error(f"Error sending user {operation_type} notification: {e}")

# Add other user-related routes here if needed (e.g., profile page)

