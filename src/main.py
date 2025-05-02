import os
from flask import Flask, render_template, redirect, url_for, flash, current_app # Added current_app import
from werkzeug.security import generate_password_hash
from flask_login import current_user # Added current_user import

# Import db and login_manager from the new extensions file
from src.extensions import db, login_manager

# Import blueprints AFTER defining db and login_manager
from src.routes.auth import auth_bp
from src.routes.user import user_bp
# Import other blueprints if you have them (e.g., question_bp, curriculum_bp)
# from src.routes.question import question_bp
# from src.routes.curriculum import curriculum_bp

# Import User model AFTER defining db
from src.models.user import User

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # --- Configuration --- 
    # Load secret key from environment variable or use a default (change in production!)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key_for_dev_only")

    # Database Configuration
    render_db_url = os.getenv("DATABASE_URL")
    print(f"DEBUG: Read DATABASE_URL from environment: {render_db_url}") # Keep for debugging

    if render_db_url and render_db_url.startswith("postgresql://"):
        print("Using Render PostgreSQL database.")
        app.config["SQLALCHEMY_DATABASE_URI"] = render_db_url
    else:
        # Fallback to a local SQLite database if DATABASE_URL is not set or not PostgreSQL
        print("DATABASE_URL not found or not PostgreSQL, falling back to local SQLite.")
        basedir = os.path.abspath(os.path.dirname(__file__))
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "app.db")
        # Ensure the instance folder exists
        instance_path = os.path.join(basedir, "instance")
        if not os.path.exists(instance_path):
             try:
                 os.makedirs(instance_path)
                 print(f"Created instance folder: {instance_path}")
             except OSError as e:
                 print(f"Error creating instance folder {instance_path}: {e}")

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- Initialize Extensions --- 
    # Initialize db and login_manager with the app instance
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login" # Redirect to login page if user is not authenticated
    login_manager.login_message = "الرجاء تسجيل الدخول للوصول إلى هذه الصفحة."
    login_manager.login_message_category = "info"

    # --- User Loader for Flask-Login --- 
    @login_manager.user_loader
    def load_user(user_id):
        # Ensure this runs within an app context or handles it properly
        # Using User.query might require an app context if called outside a request
        # However, Flask-Login usually handles this correctly.
        return User.query.get(int(user_id))

    # --- Register Blueprints --- 
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/user")
    # Register other blueprints
    # app.register_blueprint(question_bp, url_prefix="/questions")
    # app.register_blueprint(curriculum_bp, url_prefix="/curriculum")

    # --- Create Database Tables and Default User (within app context) --- 
    with app.app_context():
        print("Attempting to create database tables...")
        try:
            db.create_all()
            print("Database tables created successfully (if they didn't exist).")
        except Exception as e:
            print(f"Error creating database tables: {e}")

        # Create a default admin user if none exists
        try:
            if not User.query.filter_by(username="admin").first():
                print("Creating default admin user...")
                admin_password = os.environ.get("ADMIN_PASSWORD", "password") # Get password from env or use default
                hashed_password = generate_password_hash(admin_password)
                admin_user = User(username="admin", password_hash=hashed_password, is_admin=True)
                db.session.add(admin_user)
                db.session.commit()
                print("Default admin user created.")
            else:
                print("Admin user already exists.")
        except Exception as e:
            print(f"Error checking or creating admin user: {e}")
            db.session.rollback() # Rollback in case of error during commit

    # --- Routes --- 
    @app.route("/")
    def index():
        # Redirect to login page if not authenticated, otherwise show a simple dashboard
        if not current_user.is_authenticated:
             return redirect(url_for('auth.login'))
        # Simple placeholder for authenticated users
        return f"Welcome, {current_user.username}! (Placeholder Index Page)" 

    # Error Handling (Optional but recommended)
    # Make sure you have templates/errors/404.html and templates/errors/500.html
    @app.errorhandler(404)
    def page_not_found(e):
        # return render_template("errors/404.html"), 404
        return "Page Not Found", 404 # Placeholder if template doesn't exist

    @app.errorhandler(500)
    def internal_server_error(e):
        # Log the error e
        print(f"Internal Server Error: {e}") # Print error to logs
        db.session.rollback() # Rollback any potential failed DB transactions
        # return render_template("errors/500.html"), 500
        return "Internal Server Error", 500 # Placeholder if template doesn't exist

    return app

# Create the app instance for Gunicorn to find
# This line MUST be outside the if __name__ == "__main__" block
app = create_app()

# This block allows running the app directly using `python src/main.py` for local development
if __name__ == "__main__":
    # Use the app instance created above for local execution
    # Host='0.0.0.0' makes it accessible on your network, port 5000 is default for Flask
    app.run(host='0.0.0.0', port=5000, debug=True) # debug=True is helpful for development

