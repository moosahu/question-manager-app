import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, url_for, flash, render_template_string
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# Import models AFTER db is defined in one of the model files (e.g., user.py)
from src.models.user import db, User
from src.models.curriculum import Course, Unit, Lesson # Import curriculum models
from src.models.question import Question, Option # Import question models

# Import blueprints
from src.routes.auth import auth_bp # Auth blueprint
from src.routes.question import question_bp # Question management blueprint
from src.routes.curriculum import curriculum_bp # Curriculum management blueprint
from src.routes.user import user_bp # User settings blueprint

# Configure static folder relative to the application root (src)
static_dir = os.path.join(os.path.dirname(__file__), 'static')

app = Flask(__name__, static_folder=static_dir, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_that_should_be_changed') # Use environment variable or change default
# Define upload folder relative to the instance path or a dedicated directory outside 'src'
# Using static folder for simplicity now, but consider a dedicated volume in real production
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Limit uploads to 16MB

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Ensure subfolders for uploads exist (optional, can be created on demand)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'questions'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'options'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'explanations'), exist_ok=True)

# Database Configuration - Prioritize Heroku DATABASE_URL
database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    # Heroku provides postgres:// but SQLAlchemy needs postgresql://
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Fallback for local development (using MySQL as previously configured)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{os.getenv("DB_USERNAME", "root")}:{os.getenv("DB_PASSWORD", "password")}@{os.getenv("DB_HOST", "localhost")}:{os.getenv("DB_PORT", "3306")}/{os.getenv("DB_NAME", "mydb")}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' # Redirect to login page if user is not logged in
login_manager.login_message = u"الرجاء تسجيل الدخول للوصول إلى هذه الصفحة."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register Blueprints
app.register_blueprint(auth_bp, url_prefixapp.register_blueprint(question_bp, url_prefix=\"/questions\")
app.register_blueprint(curriculum_bp, url_prefix=\"/curriculum\")
app.register_blueprint(user_bp, url_prefix=\"/user\") # Register user settings blueprint
# Create database tables within app context
with app.app_context():
    db.create_all()
    # Optional: Create a default admin user if none exists
    if not User.query.filter_by(username='admin').first():
        print("Creating default admin user...")
        admin_user = User(username='admin', email='admin@example.com')
        admin_user.set_password('password') # Change this default password!
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created with username 'admin' and password 'password'. Please change the password.")

# Simple Dashboard Route
@app.route('/dashboard')
@login_required
def dashboard():
    # Using a simple string template for the dashboard
    dashboard_html = """
    {% extends "base.html" %}
    {% block title %}لوحة التحكم{% endblock %}
    {% block content %}
    <h1>لوحة التحكم</h1>
    <p>مرحباً, {{ current_user.username }}!</p>
    <div class="list-group">
      <a href="{{ url_for('curriculum.list_courses') }}" class="list-group-item list-group-item-action">إدارة المنهج</a>
      <a href="{{ url_for('question.list_questions') }}" class="list-group-item list-group-item-action">إدارة الأسئلة</a>
    </div>
    {% endblock %}
    """
    return render_template_string(dashboard_html)

# Root route
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('auth.login'))

# Route to serve uploaded files
# This is needed because UPLOAD_FOLDER is inside static_folder
# Flask's default static handler serves from static_url_path (default '/static')
# We need to serve '/uploads/...' directly
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Ensure the path is safe and within the UPLOAD_FOLDER
    safe_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    if not safe_path.startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
        return "Forbidden", 403 # Prevent directory traversal
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    # Debug should be False in production
    app.run(host='0.0.0.0', port=5000, debug=False)

