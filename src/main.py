import os
from flask import Flask, render_template, redirect, url_for, flash, current_app, request, jsonify
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required

# Import db and login_manager from the new extensions file
from src.extensions import db, login_manager

# Import blueprints AFTER defining db and login_manager
from src.routes.auth import auth_bp
from src.routes.user import user_bp
from src.routes.question import question_bp
from src.routes.curriculum import curriculum_bp
from src.routes.api import api_bp

# استيراد شرطي لبلوبرنت لوحة التحكم مع محاولة مسارات مختلفة
has_dashboard = False
dashboard_bp = None

# محاولة استيراد dashboard_blueprint من مسارات مختلفة
try:
    # المسار الأول: src.routes.dashboard_blueprint (المسار الأصلي)
    from src.routes.dashboard_blueprint import dashboard_bp
    has_dashboard = True
    print("تم استيراد dashboard_blueprint بنجاح من src.routes.dashboard_blueprint")
except ImportError:
    try:
        # المسار الثاني: routes.dashboard_blueprint (بدون src)
        from routes.dashboard_blueprint import dashboard_bp
        has_dashboard = True
        print("تم استيراد dashboard_blueprint بنجاح من routes.dashboard_blueprint")
    except ImportError:
        try:
            # المسار الثالث: محاولة استيراد نسبي
            import sys
            sys.path.append(os.getcwd())
            from src.routes.dashboard_blueprint import dashboard_bp
            has_dashboard = True
            print("تم استيراد dashboard_blueprint بنجاح باستخدام المسار النسبي")
        except ImportError:
            has_dashboard = False
            print("تحذير: لم يتم العثور على ملف dashboard_blueprint.py، سيتم تخطي تسجيل بلوبرنت لوحة التحكم")

# Import User model AFTER defining db
from src.models.user import User

def create_app():
    # طباعة المسار الحالي وقائمة الملفات للتشخيص
    print("المسار الحالي:", os.getcwd())
    
    # تعديل مسارات القوالب والملفات الثابتة لتتناسب مع هيكل المشروع الفعلي
    app = Flask(__name__, template_folder="src/templates", static_folder="src/static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key_for_development")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///instance/mydatabase.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")

    # طباعة مسار القوالب الفعلي الذي يستخدمه Flask
    print("مسار القوالب الفعلي في Flask:", app.template_folder)
    print("مسار الملفات الثابتة الفعلي في Flask:", app.static_folder)

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
    app.register_blueprint(api_bp)
    
    # تسجيل بلوبرنت لوحة التحكم بشكل شرطي
    if has_dashboard:
        app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
        print("تم تسجيل بلوبرنت لوحة التحكم بنجاح")

    @app.route("/")
    @login_required
    def index():
        # إعادة توجيه مباشرة إلى لوحة التحكم بغض النظر عن وجود البلوبرنت
        return redirect("/dashboard")

    # Error Handling
    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not Found"), 404
        try:
            return render_template("404.html"), 404
        except Exception as ex:
            print(f"خطأ في عرض 404.html: {ex}")
            return "<h1>404 - الصفحة غير موجودة</h1>", 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        print(f"Internal Server Error: {e}")
        db.session.rollback()
        if request.path.startswith("/api/"):
             return jsonify(error="Internal Server Error"), 500
        try:
            return render_template("500.html"), 500
        except Exception as ex:
            print(f"خطأ في عرض 500.html: {ex}")
            return "<h1>500 - خطأ في الخادم</h1>", 500

    return app

# Create the app instance for Gunicorn to find
app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
