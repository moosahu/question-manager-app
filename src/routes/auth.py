from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required
from src.models.user import User, db # Import User model and db instance
from src.forms import LoginForm # Import the LoginForm

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth") # Define template folder relative to blueprint

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm() # Instantiate the form
    if form.validate_on_submit(): # Check if form is submitted and valid
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user) # Log in the user
            flash("تم تسجيل الدخول بنجاح.", "success")
            # Redirect to index (main page) after login
            return redirect(url_for("index")) # Corrected redirect
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "danger")
    # Pass the form object to the template
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout")
@login_required # User must be logged in to logout
def logout():
    logout_user()
    flash("تم تسجيل الخروج بنجاح.", "success")
    return redirect(url_for("auth.login"))

# Optional: Add a registration route if needed later
# @auth_bp.route("/register", methods=["GET", "POST"])
# def register():
#     # Implementation for user registration
#     pass