import os
from flask import Flask, render_template, redirect, url_for, flash, current_app, request, jsonify
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFProtect

# Import db and login_manager from the new extensions file
try:
    from src.extensions import db, login_manager
except ImportError:
    try:
        from extensions import db, login_manager
    except ImportError:
        print("Error: Could not import db and login_manager from src.extensions or extensions.")
        raise

# Import blueprints AFTER defining db and login_manager
try:
    from src.routes.auth import auth_bp
    from src.routes.user import user_bp
    from src.routes.question import question_bp
    from src.routes.curriculum import curriculum_bp
    from src.routes.api import api_bp
    # استيراد settings_bp مع معالجة الخطأ
    try:
        from src.routes.settings import settings_bp
        settings_available = True
    except ImportError:
        try:
            from routes.settings import settings_bp
            settings_available = True
        except ImportError:
            print("Warning: Could not import settings_bp. Settings feature will be disabled.")
            settings_available = False
except ImportError:
    try:
        from routes.auth import auth_bp
        from routes.user import user_bp
        from routes.question import question_bp
        from routes.curriculum import curriculum_bp
        from routes.api import api_bp
        # استيراد settings_bp مع معالجة الخطأ
        try:
            from routes.settings import settings_bp
            settings_available = True
        except ImportError:
            print("Warning: Could not import settings_bp. Settings feature will be disabled.")
            settings_available = False
    except ImportError:
        print("Error: Could not import blueprints from src.routes or routes.")
        raise

# Import User model AFTER defining db
try:
    from src.models.user import User
    # استيراد Activity مع معالجة الخطأ
    try:
        from src.models.activity import Activity
        activity_available = True
    except ImportError:
        try:
            from models.activity import Activity
            activity_available = True
        except ImportError:
            print("Warning: Could not import Activity. Activity tracking will be disabled.")
            activity_available = False
except ImportError:
    try:
        from models.user import User
        # استيراد Activity مع معالجة الخطأ
        try:
            from models.activity import Activity
            activity_available = True
        except ImportError:
            print("Warning: Could not import Activity. Activity tracking will be disabled.")
            activity_available = False
    except ImportError:
        print("Error: Could not import User model from src.models or models.")
        raise

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key_for_development")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://question_manager_db_user:tmw3obihpI6UrR0IeyVep4DE6xrEMkTS@dpg-d09o15muk2gs73dnsoq0-a.oregon-postgres.render.com/question_manager_db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
    app.config["WTF_CSRF_ENABLED"] = True  # تفعيل حماية CSRF بشكل صريح
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf = CSRFProtect(app)  # تهيئة حماية CSRF
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
                
                # تسجيل نشاط إنشاء المستخدم الإداري إذا كان متاحاً
                if activity_available:
                    try:
                        Activity.log_system_activity("تم إنشاء حساب المستخدم الإداري")
                    except Exception as e:
                        print(f"Warning: Could not log activity: {e}")
        except Exception as e:
            print(f"Error during database initialization or admin creation: {e}")
            db.session.rollback()

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(question_bp, url_prefix="/questions")
    app.register_blueprint(curriculum_bp, url_prefix="/curriculum")
    app.register_blueprint(api_bp) # <<< Registered API blueprint (prefix is in api.py)
    
    # تسجيل blueprint الإعدادات إذا كان متاحاً
    if settings_available:
        try:
            app.register_blueprint(settings_bp, url_prefix="/settings")
            print("Settings blueprint registered successfully.")
        except Exception as e:
            print(f"Warning: Could not register settings blueprint: {e}")

    @app.route("/")
    @login_required
    def index():
        # جلب الإحصائيات من قاعدة البيانات
        try:
            from src.models.question import Question
            from src.models.curriculum import Course, Unit, Lesson
        except ImportError:
            try:
                from models.question import Question
                from models.curriculum import Course, Unit, Lesson
            except ImportError:
                print("Error: Could not import models for statistics.")
                return render_template("index.html", 
                                      questions_count=0,
                                      courses_count=0,
                                      units_count=0,
                                      lessons_count=0)
        
        # حساب عدد الأسئلة والدورات والوحدات والدروس
        questions_count = Question.query.count()
        courses_count = Course.query.count()
        units_count = Unit.query.count()
        lessons_count = Lesson.query.count()
        
        # جلب آخر الأنشطة إذا كان متاحاً
        recent_activities = None
        if activity_available:
            try:
                recent_activities = Activity.get_recent_activities(limit=4)
            except Exception as e:
                print(f"Warning: Could not get recent activities: {e}")
        
        # تمرير الإحصائيات والأنشطة إلى القالب
        context = {
            "questions_count": questions_count,
            "courses_count": courses_count,
            "units_count": units_count,
            "lessons_count": lessons_count
        }
        
        if recent_activities is not None:
            context["recent_activities"] = recent_activities
            
        return render_template("index.html", **context)

    # Error Handling
    @app.errorhandler(404)
    def page_not_found(e):
        # You might want to render a custom 404 template later
        # Check if the request path starts with /api/ for JSON response
        if request.path.startswith("/api/"):
            return jsonify(error="Not Found"), 404
        return render_template("404.html"), 404 # Or a simple string
        
    @app.errorhandler(500)
    def internal_server_error(e):
        print(f"Internal Server Error: {e}")
        db.session.rollback()
        # Check if the request path starts with /api/ for JSON response
        if request.path.startswith("/api/"):
             return jsonify(error="Internal Server Error"), 500
        # You might want to render a custom 500 template later
        return render_template("500.html"), 500 # Or a simple string

    return app

# Create the app instance for Gunicorn to find
app = create_app()

if __name__ == "__main__":
    # <<< Corrected indentation for the block below
    # Use 0.0.0.0 to be accessible externally if needed, port 5000 is common
    # Debug should be False in production
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True) # تفعيل وضع التصحيح مؤقتاً
