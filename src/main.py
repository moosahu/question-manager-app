import os
from flask import Flask, render_template, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required # Added login_required

# Import db and login_manager from the new extensions file
from src.extensions import db, login_manager

# Import blueprints AFTER defining db and login_manager
from src.routes.auth import auth_bp
from src.routes.user import user_bp
from src.routes.question import question_bp
from src.routes.curriculum import curriculum_bp

# Import User model AFTER defining db
from src.models.user import User

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key_for_development")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///instance/mydatabase.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login" # Set the login view

    # User loader function for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create database tables and default admin if needed
    with app.app_context():
        try:
            db.create_all()
            # Check if admin user exists
            admin_user = User.query.filter_by(username="admin").first()
            if not admin_user:
                admin_password = os.environ.get("ADMIN_PASSWORD", "password")
                hashed_password = generate_password_hash(admin_password)
                new_admin = User(username="admin", password_hash=hashed_password, is_admin=True)
                db.session.add(new_admin)
                db.session.commit()
                print("Admin user created.")
        except Exception as e:
            print(f"Error during database initialization or admin creation: {e}")
            db.session.rollback()

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(question_bp, url_prefix="/questions")
    app.register_blueprint(curriculum_bp, url_prefix="/curriculum")

    @app.route("/")
    @login_required
    def index():
        # Render the index.html template which extends base.html
        return render_template("index.html")

    # Error Handling
    @app.errorhandler(404)
    def page_not_found(e):
        # You might want to render a custom 404 template later
        return "Page Not Found", 404
    @app.errorhandler(500)
    def internal_server_error(e):
        print(f"Internal Server Error: {e}")
        db.session.rollback()
        # You might want to render a custom 500 template later
        return "Internal Server Error", 500

    return app

# Create the app instance for Gunicorn to find
app = create_app()

if __name__ == "__main__":
    # --- Ensure NO backslashes here --- #
    app.run(host='0.0.0.0', port=5000, debug=True)

