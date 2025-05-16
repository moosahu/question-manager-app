import os
import sys
import logging
import traceback
from flask import Flask, render_template, redirect, url_for, flash, current_app, request, jsonify
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required

# إعداد التسجيل (logging)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# طباعة معلومات النظام للتشخيص
logger.info(f"المسار الحالي: {os.getcwd()}")
logger.info(f"قائمة المجلدات والملفات في المسار الحالي: {os.listdir('.')}")
if os.path.exists('src'):
    logger.info(f"قائمة المجلدات والملفات في مجلد src: {os.listdir('src')}")
    if os.path.exists('src/routes'):
        logger.info(f"قائمة الملفات في مجلد src/routes: {os.listdir('src/routes')}")
    if os.path.exists('src/templates'):
        logger.info(f"قائمة الملفات في مجلد src/templates: {os.listdir('src/templates')}")

# طباعة مسارات البحث في Python
logger.info(f"مسارات البحث في Python: {sys.path}")

try:
    # Import db and login_manager from the new extensions file
    logger.info("محاولة استيراد db و login_manager من src.extensions")
    from src.extensions import db, login_manager
    logger.info("تم استيراد db و login_manager بنجاح")
except Exception as e:
    logger.error(f"خطأ في استيراد db و login_manager: {e}")
    logger.error(traceback.format_exc())
    raise

# Import blueprints AFTER defining db and login_manager
try:
    logger.info("محاولة استيراد البلوبرنت")
    from src.routes.auth import auth_bp
    from src.routes.user import user_bp
    from src.routes.question import question_bp
    from src.routes.curriculum import curriculum_bp
    from src.routes.api import api_bp
    logger.info("تم استيراد البلوبرنت الأساسية بنجاح")
except Exception as e:
    logger.error(f"خطأ في استيراد البلوبرنت الأساسية: {e}")
    logger.error(traceback.format_exc())
    raise

# استيراد شرطي لبلوبرنت لوحة التحكم مع محاولة مسارات مختلفة
has_dashboard = False
dashboard_bp = None

# محاولة استيراد dashboard_blueprint من مسارات مختلفة
try:
    # المسار الأول: routes.dashboard_blueprint (بدون src)
    logger.info("محاولة استيراد dashboard_blueprint من routes.dashboard_blueprint")
    from routes.dashboard_blueprint import dashboard_bp
    has_dashboard = True
    logger.info("تم استيراد dashboard_blueprint بنجاح من routes.dashboard_blueprint")
except ImportError as e:
    logger.warning(f"فشل استيراد dashboard_blueprint من routes.dashboard_blueprint: {e}")
    try:
        # المسار الثاني: src.routes.dashboard_blueprint
        logger.info("محاولة استيراد dashboard_blueprint من src.routes.dashboard_blueprint")
        from src.routes.dashboard_blueprint import dashboard_bp
        has_dashboard = True
        logger.info("تم استيراد dashboard_blueprint بنجاح من src.routes.dashboard_blueprint")
    except ImportError as e:
        logger.warning(f"فشل استيراد dashboard_blueprint من src.routes.dashboard_blueprint: {e}")
        try:
            # المسار الثالث: محاولة استيراد نسبي
            logger.info("محاولة استيراد dashboard_blueprint باستخدام المسار النسبي")
            import sys
            sys.path.append(os.getcwd())
            from src.routes.dashboard_blueprint import dashboard_bp
            has_dashboard = True
            logger.info("تم استيراد dashboard_blueprint بنجاح باستخدام المسار النسبي")
        except ImportError as e:
            logger.error(f"فشل استيراد dashboard_blueprint من جميع المسارات: {e}")
            has_dashboard = False

# Import User model AFTER defining db
try:
    logger.info("محاولة استيراد User من src.models.user")
    from src.models.user import User
    logger.info("تم استيراد User بنجاح")
except Exception as e:
    logger.error(f"خطأ في استيراد User: {e}")
    logger.error(traceback.format_exc())
    raise

def create_app():
    # طباعة المسار الحالي وقائمة الملفات للتشخيص
    logger.info(f"المسار الحالي في create_app: {os.getcwd()}")
    
    # تعديل مسارات القوالب والملفات الثابتة لتكون نسبية
    try:
        logger.info("إنشاء تطبيق Flask مع مسارات القوالب والملفات الثابتة النسبية")
        app = Flask(__name__, template_folder="templates", static_folder="static")
        logger.info("تم إنشاء تطبيق Flask بنجاح")
    except Exception as e:
        logger.error(f"خطأ في إنشاء تطبيق Flask: {e}")
        logger.error(traceback.format_exc())
        raise

    # Configuration
    try:
        logger.info("تكوين إعدادات التطبيق")
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key_for_development")
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///instance/mydatabase.db")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
        logger.info("تم تكوين إعدادات التطبيق بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تكوين إعدادات التطبيق: {e}")
        logger.error(traceback.format_exc())
        raise

    # طباعة مسار القوالب الفعلي الذي يستخدمه Flask
    logger.info(f"مسار القوالب الفعلي في Flask: {app.template_folder}")
    logger.info(f"مسار الملفات الثابتة الفعلي في Flask: {app.static_folder}")

    # Initialize extensions
    try:
        logger.info("تهيئة الإضافات (db و login_manager)")
        db.init_app(app)
        login_manager.init_app(app)
        login_manager.login_view = "auth.login" # Set the login view
        logger.info("تم تهيئة الإضافات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تهيئة الإضافات: {e}")
        logger.error(traceback.format_exc())
        raise

    # User loader function for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        try:
            logger.debug(f"محاولة تحميل المستخدم بالمعرف: {user_id}")
            user = User.query.get(int(user_id))
            if user:
                logger.debug(f"تم تحميل المستخدم: {user.username}")
            else:
                logger.warning(f"لم يتم العثور على المستخدم بالمعرف: {user_id}")
            return user
        except Exception as e:
            logger.error(f"خطأ في تحميل المستخدم: {e}")
            logger.error(traceback.format_exc())
            return None

    # Create database tables and default admin if needed
    with app.app_context():
        try:
            logger.info("محاولة إنشاء جداول قاعدة البيانات")
            db.create_all()
            logger.info("تم إنشاء جداول قاعدة البيانات بنجاح")
            
            # Check if admin user exists
            logger.info("التحقق من وجود مستخدم admin")
            admin_user = User.query.filter_by(username="admin").first()
            if not admin_user:
                logger.info("إنشاء مستخدم admin جديد")
                admin_password = os.environ.get("ADMIN_PASSWORD", "password")
                hashed_password = generate_password_hash(admin_password)
                new_admin = User(username="admin", password_hash=hashed_password, is_admin=True)
                db.session.add(new_admin)
                db.session.commit()
                logger.info("تم إنشاء مستخدم admin بنجاح")
            else:
                logger.info("مستخدم admin موجود بالفعل")
        except Exception as e:
            logger.error(f"خطأ أثناء تهيئة قاعدة البيانات أو إنشاء مستخدم admin: {e}")
            logger.error(traceback.format_exc())
            db.session.rollback()

    # Register blueprints
    try:
        logger.info("تسجيل البلوبرنت")
        app.register_blueprint(auth_bp, url_prefix="/auth")
        app.register_blueprint(user_bp, url_prefix="/user")
        app.register_blueprint(question_bp, url_prefix="/questions")
        app.register_blueprint(curriculum_bp, url_prefix="/curriculum")
        app.register_blueprint(api_bp)
        logger.info("تم تسجيل البلوبرنت الأساسية بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تسجيل البلوبرنت الأساسية: {e}")
        logger.error(traceback.format_exc())
        raise
    
    # تسجيل بلوبرنت لوحة التحكم بشكل شرطي
    if has_dashboard:
        try:
            logger.info("محاولة تسجيل بلوبرنت لوحة التحكم")
            app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
            logger.info("تم تسجيل بلوبرنت لوحة التحكم بنجاح")
        except Exception as e:
            logger.error(f"خطأ في تسجيل بلوبرنت لوحة التحكم: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.warning("تم تخطي تسجيل بلوبرنت لوحة التحكم لأنه غير متوفر")

    @app.route("/")
    @login_required
    def index():
        try:
            logger.info("تم استدعاء المسار الرئيسي '/'")
            # إعادة توجيه مباشرة إلى لوحة التحكم بغض النظر عن وجود البلوبرنت
            logger.info("إعادة توجيه إلى /dashboard")
            return redirect("/dashboard")
        except Exception as e:
            logger.error(f"خطأ في المسار الرئيسي: {e}")
            logger.error(traceback.format_exc())
            return render_template("500.html"), 500

    # إضافة مسار مباشر للوحة التحكم في حالة عدم تسجيل البلوبرنت
    @app.route("/dashboard")
    @login_required
    def dashboard_direct():
        try:
            logger.info("تم استدعاء المسار المباشر '/dashboard'")
            # عرض قالب لوحة التحكم مباشرة
            dashboard_data = {
                'courses_count': 10,
                'units_count': 50,
                'lessons_count': 200,
                'questions_count': 1000,
                'title': 'لوحة التحكم'
            }
            logger.info("عرض قالب dashboard.html مباشرة")
            return render_template("dashboard.html", **dashboard_data)
        except Exception as e:
            logger.error(f"خطأ في المسار المباشر للوحة التحكم: {e}")
            logger.error(traceback.format_exc())
            return render_template("500.html"), 500

    # Error Handling
    @app.errorhandler(404)
    def page_not_found(e):
        logger.warning(f"خطأ 404: {request.path}")
        if request.path.startswith("/api/"):
            return jsonify(error="Not Found"), 404
        try:
            return render_template("404.html"), 404
        except Exception as ex:
            logger.error(f"خطأ في عرض 404.html: {ex}")
            logger.error(traceback.format_exc())
            return "<h1>404 - الصفحة غير موجودة</h1>", 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"خطأ 500: {e}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        if request.path.startswith("/api/"):
             return jsonify(error="Internal Server Error"), 500
        try:
            return render_template("500.html"), 500
        except Exception as ex:
            logger.error(f"خطأ في عرض 500.html: {ex}")
            logger.error(traceback.format_exc())
            return "<h1>500 - خطأ في الخادم</h1>", 500
    
    # إضافة معالج خطأ عام لالتقاط جميع الاستثناءات غير المعالجة
    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"استثناء غير معالج: {e}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify(error="Internal Server Error"), 500
        try:
            return render_template("500.html"), 500
        except Exception as ex:
            logger.error(f"خطأ في عرض 500.html: {ex}")
            logger.error(traceback.format_exc())
            return "<h1>500 - خطأ في الخادم</h1>", 500

    return app

# Create the app instance for Gunicorn to find
try:
    logger.info("إنشاء تطبيق Flask الرئيسي")
    app = create_app()
    logger.info("تم إنشاء تطبيق Flask الرئيسي بنجاح")
except Exception as e:
    logger.critical(f"خطأ حرج في إنشاء تطبيق Flask الرئيسي: {e}")
    logger.critical(traceback.format_exc())
    raise

if __name__ == "__main__":
    try:
        logger.info("بدء تشغيل تطبيق Flask")
        app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
    except Exception as e:
        logger.critical(f"خطأ حرج في تشغيل تطبيق Flask: {e}")
        logger.critical(traceback.format_exc())
        raise
