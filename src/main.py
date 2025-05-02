import os
from flask import Flask, render_template, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash
from flask_login import current_user

# Import db and login_manager from the new extensions file
from src.extensions import db, login_manager

# Import blueprints AFTER defining db and login_manager
from src.routes.auth import auth_bp
from src.routes.user import user_bp
# --- Re-enabled these lines (ensure files exist) --- 
from src.routes.question import question_bp
from src.routes.curriculum import curriculum_bp
# --- END Re-enabled --- 

# Import User model AFTER defining db
from src.models.user import User

def create_app():
    # --- Ensure NO backslashes around quotes here --- 
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # --- Configuration --- 
    # --- Ensure NO backslashes around quotes here --- 
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key_for_dev_only")
    render_db_url = os.getenv("DATABASE_URL")
    print(f"DEBUG: Read DATABASE_URL from environment: {render_db_url}")
    if render_db_url and render_db_url.startswith("postgresql://"):
        print("Using Render PostgreSQL database.")
        # --- Ensure NO backslashes around quotes here --- 
        app.config["SQLALCHEMY_DATABASE_URI"] = render_db_url
    else:
        print("DATABASE_URL not found or not PostgreSQL, falling back to local SQLite.")
        basedir = os.path.abspath(os.path.dirname(__file__))
        # --- Ensure NO backslashes around quotes here --- 
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "app.db")
        instance_path = os.path.join(basedir, "instance")
        if not os.path.exists(instance_path):
             try:
                 os.makedirs(instance_path)
                 print(f"Created instance folder: {instance_path}")
             except OSError as e:
                 print(f"Error creating instance folder {instance_path}: {e}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- Initialize Extensions --- 
    db.init_app(app)
    login_manager.init_app(app)
    # --- Ensure NO backslashes around quotes here --- 
    login_manager.login_view = "auth.login"
    login_manager.login_message = "الرجاء تسجيل الدخول للوصول إلى هذه الصفحة."
    login_manager.login_message_category = "info"

    # --- User Loader for Flask-Login --- 
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Register Blueprints --- 
    # --- Ensure NO backslashes around quotes here --- 
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/user")
    # --- Re-enabled these lines (ensure files exist and NO backslashes) --- 
    app.register_blueprint(question_bp, url_prefix="/questions")
    app.register_blueprint(curriculum_bp, url_prefix="/curriculum")
    # --- END Re-enabled --- 

    # --- Create Database Tables and Default User (within app context) --- 
    with app.app_context():
        print("Attempting to create database tables...")
        try:
            db.create_all()
            print("Database tables created successfully (if they didn't exist).") # Corrected quote
        except Exception as e:
            print(f"Error creating database tables: {e}")
        try:
            # --- Ensure NO backslashes around quotes here --- 
            if not User.query.filter_by(username="admin").first():
                print("Creating default admin user...")
                # --- Ensure NO backslashes around quotes here --- 
                admin_password = os.environ.get("ADMIN_PASSWORD", "password")
                hashed_password = generate_password_hash(admin_password)
                # --- Ensure NO backslashes around quotes here --- 
                admin_user = User(username="admin", password_hash=hashed_password, is_admin=True)
                db.session.add(admin_user)
                db.session.commit()
                print("Default admin user created.")
            else:
                print("Admin user already exists.")
        except Exception as e:
            print(f"Error checking or creating admin user: {e}")
            db.session.rollback()

    # --- Routes --- 
    @app.route("/")
    def index():
        if not current_user.is_authenticated:
             # --- Ensure NO backslashes around quotes here --- 
             return redirect(url_for('auth.login'))
        return f"Welcome, {current_user.username}! (Placeholder Index Page)" 

    # Error Handling
    @app.errorhandler(404)
    def page_not_found(e):
        # --- Ensure NO backslashes around quotes here --- 
        return "Page Not Found", 404
    @app.errorhandler(500)
    def internal_server_error(e):
        print(f"Internal Server Error: {e}")
        db.session.rollback()
        # --- Ensure NO backslashes around quotes here --- 
        return "Internal Server Error", 500

    return app

# Create the app instance for Gunicorn to find
app = create_app()

if __name__ == "__main__":
    # --- Ensure NO backslashes around quotes here --- 
    app.run(host='0.0.0.0', port=5000, debug=True)
