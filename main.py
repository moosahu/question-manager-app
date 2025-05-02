# src/main.py
import os
from flask import Flask, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, current_user
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()

# Define the User model loader function
# Moved User import inside the function to avoid circular import during init
@login_manager.user_loader
def load_user(user_id):
    from src.models import User
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__, template_folder=\'templates\', static_folder=\'static\')

    # Configuration
    app.config[\'SECRET_KEY\'] = os.getenv(\'SECRET_KEY\', \'fallback_secret_key_12345\')

    # Database Configuration (Prioritize Render PostgreSQL, then local, then fallback MySQL)
    render_db_url = os.getenv(\'DATABASE_URL\')
    # --- DEBUGGING LINE ADDED ---
    print(f"DEBUG: Read DATABASE_URL from environment: {render_db_url}")
    # --- END DEBUGGING LINE ---
    local_db_url = os.getenv(\'LOCAL_DATABASE_URI\')
    fallback_db_url = f"mysql+mysqlconnector://{os.getenv(\'DB_USER\', \'default_user\')}:{os.getenv(\'DB_PASSWORD\', \'default_password\')}@{os.getenv(\'DB_HOST\', \'localhost\')}/{os.getenv(\'DB_NAME\', \'default_db\')}"

    if render_db_url and render_db_url.startswith("postgresql://"):
        # No replacement needed if URL already starts with postgresql://
        app.config[\'SQLALCHEMY_DATABASE_URI\'] = render_db_url
        print("Using Render PostgreSQL database.")
    elif local_db_url:
        app.config[\'SQLALCHEMY_DATABASE_URI\'] = local_db_url
        print("Using local PostgreSQL database.")
    else:
        app.config[\'SQLALCHEMY_DATABASE_URI\'] = fallback_db_url
        print("Using fallback MySQL database.")

    app.config[\'SQLALCHEMY_TRACK_MODIFICATIONS\'] = False

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    # Login view and message category
    login_manager.login_view = \'auth.login\' # Endpoint name for the login route within the auth_bp blueprint
    login_manager.login_message_category = \'info\'

    # Import Blueprints (inside create_app to avoid circular imports)
    from src.routes.auth import auth_bp
    from src.routes.questions import question_bp
    from src.routes.user import user_bp

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(question_bp, url_prefix="/questions")
    app.register_blueprint(user_bp, url_prefix="/user")

    # Basic route for index/home page
    @app.route(\'/\')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for(\'questions.list_questions\'))
        else:
            return redirect(url_for(\'auth.login\'))

    # Context processor to make username available to all templates
    @app.context_processor
    def inject_user():
        return dict(current_username=current_user.username if current_user.is_authenticated else None)

    return app

# Create the Flask app instance
app = create_app()

if __name__ == \'__main__\':
    # Note: For production, use a WSGI server like Gunicorn
    # The host=\'0.0.0.0\' makes it accessible on the network
    port = int(os.environ.get(\'PORT\', 5000))
    app.run(host=\'0.0.0.0\', port=port, debug=False) # Set debug=False for production

