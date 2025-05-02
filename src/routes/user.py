from flask import Blueprint, render_template, redirect, url_for, flash, request
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

# Assuming you have forms defined in src/forms.py
try:
    from src.forms import ChangePasswordForm
except ImportError:
    # Define a basic form here if forms.py or ChangePasswordForm doesn't exist
    from flask_wtf import FlaskForm
    from wtforms import PasswordField, SubmitField
    from wtforms.validators import DataRequired, EqualTo, Length
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
                flash("تم تغيير كلمة المرور بنجاح!", "success")
                return redirect(url_for("index")) # Redirect to dashboard or profile
            except Exception as e:
                db.session.rollback()
                flash(f"حدث خطأ أثناء تحديث كلمة المرور: {e}", "danger")
    return render_template("user/change_password.html", form=form, title="تغيير كلمة المرور")

# Add other user-related routes here if needed (e.g., profile page)
