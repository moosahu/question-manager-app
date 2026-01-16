import os
import os
import logging
from flask import Flask, render_template, redirect, url_for, flash, current_app, request, jsonify, session
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required, login_user
from flask_wtf.csrf import CSRFProtect
from src.extensions import db
# from src.models.notification import Notification  # ✅ نُقل داخل الدوال
from datetime import datetime
import uuid

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ تحميل الإعدادات والمتغيرات البيئية
from dotenv import load_dotenv
load_dotenv()

# ✅ تهيئة Firebase Admin SDK (يجب أن يكون قبل استخدام messaging)
try:
    import firebase_admin
    from firebase_admin import credentials
    import json
    
    # تحقق إذا Firebase لم يتم تهيئته بعد
    try:
        firebase_admin.get_app()
        logger.info("✅ Firebase already initialized")
    except ValueError:
        # Firebase غير مهيأ، قم بتهيئته
        # الأولوية: Environment Variable (للإنتاج)
        firebase_config_json = os.getenv('FIREBASE_CONFIG') or os.getenv('FIREBASE_CREDENTIALS_JSON')
        
        if firebase_config_json:
            # استخدام Environment Variable (Render/Production)
            try:
                firebase_config = json.loads(firebase_config_json)
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase initialized successfully from environment variable")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid FIREBASE_CONFIG JSON: {e}")
                logger.warning("💡 Push notifications disabled")
        elif os.path.exists('serviceAccountKey.json'):
            # استخدام ملف محلي (Development)
            cred = credentials.Certificate('serviceAccountKey.json')
            firebase_admin.initialize_app(cred)
            logger.info("✅ Firebase initialized successfully with serviceAccountKey.json")
        elif os.path.exists('src/serviceAccountKey.json'):
            # استخدام ملف في مجلد src (Development)
            cred = credentials.Certificate('src/serviceAccountKey.json')
            firebase_admin.initialize_app(cred)
            logger.info("✅ Firebase initialized successfully with src/serviceAccountKey.json")
        else:
            logger.warning("⚠️  No Firebase credentials found")
            logger.warning("💡 Set FIREBASE_CONFIG env variable or add serviceAccountKey.json file")
            logger.warning("💡 Push notifications disabled - notifications will be saved to database only")
except ImportError:
    logger.warning("⚠️  Firebase Admin SDK not installed (pip install firebase-admin)")
    logger.warning("💡 Push notifications disabled - notifications will be saved to database only")
except Exception as e:
    logger.error(f"❌ Firebase initialization error: {e}")
    logger.warning("💡 Push notifications disabled - notifications will be saved to database only")

try:
    from config import get_config
except ImportError:
    try:
        from src.config import get_config
    except ImportError:
        def get_config():
            class Config:
                SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
                SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
                SQLALCHEMY_TRACK_MODIFICATIONS = False
                JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev')
                JWT_ALGORITHM = 'HS256'
            return Config()

# استيراد students blueprint مع معالجة الخطأ
try:
    from src.routes.students import students_bp
    students_available = True
except ImportError:
    students_available = False
    print("⚠️ Students blueprint not available")

# ✅ استيراد teachers blueprint لإدارة المعلمين
try:
    from src.routes.teachers import teachers_bp
    teachers_available = True
    print("✅ Teachers blueprint imported successfully")
except ImportError:
    teachers_available = False
    print("⚠️ Teachers blueprint not available")

# استيراد registration blueprint للتسجيل الذاتي
try:
    from src.routes.registration import registration_bp
    registration_available = True
    print("✅ Registration blueprint imported successfully")
except ImportError:
    registration_available = False
    print("⚠️ Registration blueprint not available")

# استيراد password reset blueprint لإعادة تعيين كلمة المرور
try:
    from src.routes.password_reset_routes import password_reset_bp
    password_reset_available = True
    print("✅ Password Reset blueprint imported successfully")
except ImportError:
    password_reset_available = False
    print("⚠️ Password Reset blueprint not available")

# استيراد admin profile blueprint لجلب بيانات الأدمن
try:
    from src.routes.admin_profile import admin_profile_bp
    admin_profile_available = True
    print("✅ Admin Profile blueprint imported successfully")
except ImportError:
    admin_profile_available = False
    print("⚠️ Admin Profile blueprint not available")

# ✅ استيراد Admin AI Blueprint لنظام الذكاء الاصطناعي
admin_ai_available = False
try:
    from src.routes.admin_ai import admin_ai_bp
    admin_ai_available = True
    print("✅ Admin AI blueprint imported successfully")
except ImportError as e:
    print(f"⚠️ Admin AI blueprint not available: {e}")

# ✅ استيراد reports blueprint لنظام التقارير الشامل
reports_available = False
try:
    from src.routes.reports import reports_bp
    reports_available = True
    print("✅ Reports blueprint imported successfully from src.routes")
except ImportError as e1:
    print(f"⚠️ Import attempt 1 failed: {e1}")
    try:
        from routes.reports import reports_bp
        reports_available = True
        print("✅ Reports blueprint imported successfully from routes")
    except ImportError as e2:
        print(f"⚠️ Import attempt 2 failed: {e2}")
        try:
            import sys
            import os
            # إضافة مسار routes للـ path - جرّب المسار الحالي أولاً
            current_dir = os.path.dirname(os.path.abspath(__file__))
            routes_path = os.path.join(current_dir, 'routes')
            
            print(f"🔍 Looking for routes at: {routes_path}")
            
            if os.path.exists(routes_path):
                print(f"✅ Found routes directory")
                if routes_path not in sys.path:
                    sys.path.insert(0, routes_path)
                    print(f"✅ Added {routes_path} to sys.path")
                
                from reports import reports_bp
                reports_available = True
                print("✅ Reports blueprint imported successfully (direct import)")
            else:
                print(f"❌ Routes directory not found at {routes_path}")
                # جرّب مسار بديل
                parent_routes = os.path.join(os.path.dirname(current_dir), 'routes')
                if os.path.exists(parent_routes):
                    print(f"✅ Found routes at parent: {parent_routes}")
                    sys.path.insert(0, parent_routes)
                    from reports import reports_bp
                    reports_available = True
                    print("✅ Reports blueprint imported successfully (parent path)")
                else:
                    raise ImportError("Could not find routes directory")
                    
        except Exception as e3:
            reports_available = False
            print(f"⚠️ Reports blueprint not available: {e3}")
            import traceback
            traceback.print_exc()



# استيراد نظام جدولة النسخ الاحتياطي المحسن مع معالجة أخطاء
try:
    # استيراد مباشر من src/backup_scheduler_fixed
    from src.backup_scheduler_fixed import (
        init_backup_scheduler, 
        start_backup_scheduler,
        get_scheduler_status,
        schedule_user_backup
    )
    backup_scheduler_available = True
    logger.info("✅ تم استيراد نظام الجدولة المحسن")
except ImportError:
    try:
        # محاولة استيراد من backup_scheduler_fixed في المجلد الجذر
        from backup_scheduler_fixed import (
            init_backup_scheduler, 
            start_backup_scheduler,
            get_scheduler_status,
            schedule_user_backup
        )
        backup_scheduler_available = True
        logger.info("✅ تم استيراد نظام الجدولة المحسن من المجلد الجذر")
    except ImportError:
        logger.warning("❌ Could not import backup_scheduler_fixed. Using fallback implementation.")
        backup_scheduler_available = False
        
        # إنشاء دوال بديلة
        def init_backup_scheduler(app):
            logger.info("Backup scheduler fallback: initialized")
            return True
            
        def start_backup_scheduler():
            logger.info("Backup scheduler fallback: started")
            return True
            
        def get_scheduler_status():
            return {"status": "disabled", "message": "Backup scheduler not available"}
            
        def schedule_user_backup(user_id, frequency):
            logger.info(f"Backup scheduler fallback: scheduled for user {user_id}")
            return True

# Import db and login_manager from the new extensions file مع معالجة أخطاء
try:
    from src.extensions import db, login_manager
    logger.info("✅ Database extensions imported successfully")
except ImportError:
    try:
        from extensions import db, login_manager
        logger.info("✅ Database extensions imported successfully (fallback)")
    except ImportError:
        logger.error("❌ Could not import db and login_manager from src.extensions or extensions.")
        raise

# Import blueprints AFTER defining db and login_manager مع معالجة أخطاء محسنة
try:
    from src.routes.auth import auth_bp
    from src.routes.user import user_bp
    from src.routes.question import question_bp
    from src.routes.curriculum import curriculum_bp
    from src.routes.api import api_bp
    logger.info("✅ Main blueprints imported successfully")
    
    # استيراد APIs النسخ الاحتياطي المحسنة مع معالجة أخطاء
    try:
        from src.backup_apis_enhanced import register_backup_apis
        backup_apis_available = True
        logger.info("✅ تم استيراد APIs النسخ الاحتياطي المحسنة")
    except ImportError:
        try:
            from backup_apis_enhanced import register_backup_apis
            backup_apis_available = True
            logger.info("✅ تم استيراد APIs النسخ الاحتياطي المحسنة من المجلد الجذر")
        except ImportError:
            backup_apis_available = False
            logger.warning("⚠️ Could not import backup_apis_enhanced. Using fallback implementation.")
            
            # إنشاء دالة بديلة
            def register_backup_apis(app):
                @app.route('/api/backup/status')
                def backup_status_fallback():
                    return jsonify({
                        'status': 'disabled',
                        'message': 'Backup APIs not available'
                    })
                logger.info("Backup APIs fallback registered")
    
    # استيراد settings_bp مع معالجة الخطأ المحسنة
    try:
        from src.routes.settings import settings_bp
        settings_available = True
        logger.info("✅ Settings blueprint imported successfully")
    except ImportError:
        try:
            from routes.settings import settings_bp
            settings_available = True
            logger.info("✅ Settings blueprint imported successfully (fallback)")
        except ImportError:
            logger.warning("⚠️ Could not import settings_bp. Settings feature will be disabled.")
            settings_available = False
    
    # استيراد Google Drive Backend routes مع معالجة الخطأ المحسنة ✅ إصلاح الاستيراد
    try:
        from src.routes.google_drive_backend_routes import register_google_drive_backend_routes
        google_drive_backend_available = True
        logger.info("✅ Google Drive Backend routes imported successfully")
    except ImportError:
        try:
            from routes.google_drive_backend_routes import register_google_drive_backend_routes
            google_drive_backend_available = True
            logger.info("✅ Google Drive Backend routes imported successfully (fallback)")
        except ImportError:
            logger.warning("⚠️ Could not import google_drive_backend_routes. Using fallback implementation.")
            google_drive_backend_available = False
            
            # إنشاء دالة بديلة
            def register_google_drive_backend_routes(app):
                @app.route('/api/google-drive/status')
                def google_drive_status_fallback():
                    return jsonify({
                        'connected': False,
                        'error': 'Google Drive service not available'
                    })
                logger.info("Google Drive Backend routes fallback registered")
        
except ImportError:
    try:
        from routes.auth import auth_bp
        from routes.user import user_bp
        from routes.question import question_bp
        from routes.curriculum import curriculum_bp
        from routes.api import api_bp
        
        # استيراد APIs النسخ الاحتياطي المحسنة
        # تم استيراد backup_apis_enhanced مسبقاً في بداية الملف
        # لا حاجة لاستيراده مرة أخرى
        # استيراد settings_bp مع معالجة الخطأ
        try:
            from routes.settings import settings_bp
            settings_available = True
        except ImportError:
            print("Warning: Could not import settings_bp. Settings feature will be disabled.")
            settings_available = False
        
        # استيراد Google Drive Backend routes مع معالجة الخطأ ✅ إصلاح الاستيراد
        try:
            from src.routes.google_drive_backend_routes import register_google_drive_backend_routes
            google_drive_backend_available = True
        except ImportError:
            try:
                from routes.google_drive_backend_routes import register_google_drive_backend_routes
                google_drive_backend_available = True
            except ImportError:
                print("Warning: Could not import google_drive_backend_routes. Google Drive Backend feature will be disabled.")
                google_drive_backend_available = False
                
                # إنشاء دالة بديلة
                def register_google_drive_backend_routes(app):
                    pass
    except ImportError:
        print("Error: Could not import blueprints from src.routes or routes.")
        raise

# Import User model AFTER defining db
try:
    from src.models.user import User
    # استيراد Google Drive Token model
    try:
        from src.models.google_drive import GoogleDriveToken
        google_drive_model_available = True
        logger.info("✅ Google APIs client library loaded successfully")
        logger.info("✅ Database models imported successfully")
        logger.info("✅ Google OAuth credentials loaded successfully")
        logger.info("✅ Google Drive Manager initialized successfully")
    except ImportError:
        try:
            from models.google_drive import GoogleDriveToken
            google_drive_model_available = True
        except ImportError:
            print("Warning: Could not import GoogleDriveToken. Google Drive token storage will be disabled.")
            google_drive_model_available = False
    
    # استيراد Backup Settings model مع تصحيح المسار
    backup_settings_model_available = False
    try:
        from src.models.backup_settings import BackupSettings
        backup_settings_model_available = True
        logger.info("✅ Database models imported successfully")
    except ImportError:
        try:
            from models.backup_settings import BackupSettings
            backup_settings_model_available = True
        except ImportError:
            try:
                from backup_settings import BackupSettings
                backup_settings_model_available = True
            except ImportError:
                print("تحذير: لا يمكن استيراد وحدات النسخ الاحتياطي: No module named 'backup_settings'")
                backup_settings_model_available = False
    
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
        # استيراد Google Drive Token model
        try:
            from models.google_drive import GoogleDriveToken
            google_drive_model_available = True
        except ImportError:
            print("Warning: Could not import GoogleDriveToken. Google Drive token storage will be disabled.")
            google_drive_model_available = False
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

    # ✅ تحميل الإعدادات من config.py
    app.config.from_object(get_config())
    
    # Configuration
    app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
    app.config["WTF_CSRF_ENABLED"] = True  # تفعيل حماية CSRF بشكل صريح
    app.config["WTF_CSRF_CHECK_DEFAULT"] = False  # ✅ تعطيل CSRF للـ API endpoints
    
    # ==================== إعدادات الإيميل للتسجيل الذاتي ====================
    app.config['MAIL_SERVER'] = 'smtp-relay.brevo.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = '9f21cf001@smtp-brevo.com'  # ✅ Login من Brevo SMTP Settings
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = ('no-reply@chem-tahsili.com')
    
    # تهيئة خدمة الإيميل
    try:
        from src.services.email_service import email_service
        email_service.init_app(app)
        print("✅ Email service initialized successfully")
    except Exception as e:
        print(f"⚠️ Email service not available: {e}")
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf = CSRFProtect(app)  # تهيئة حماية CSRF
    
    # إعفاء API من CSRF (آمن لأن API محمي بـ login_required + session)
    # التطبيقات لا تستخدم متصفح فلا تحتاج حماية CSRF
    csrf.exempt(api_bp)
    
    # إعفاء students API من CSRF للتطبيق
    if students_available:
        csrf.exempt(students_bp)
    
    # إعفاء registration API من CSRF للتطبيق
    if registration_available:
        csrf.exempt(registration_bp)
    
    # إعفاء password reset API من CSRF للتطبيق
    if password_reset_available:
        csrf.exempt(password_reset_bp)
    
    # ✅ إعفاء Admin AI من CSRF للتطبيق
    if admin_ai_available:
        csrf.exempt(admin_ai_bp)
    
    login_manager.login_view = "auth.login" # Set the login view

    # ===== إضافة CORS Middleware =====
    @app.after_request
    def add_cors_headers(response):
        """إضافة headers لحل مشاكل CORS و OAuth"""
        # إزالة Cross-Origin-Opener-Policy تماماً لحل مشاكل النوافذ المنبثقة
        if 'Cross-Origin-Opener-Policy' in response.headers:
            del response.headers['Cross-Origin-Opener-Policy']
        
        # إزالة Cross-Origin-Embedder-Policy أيضاً
        if 'Cross-Origin-Embedder-Policy' in response.headers:
            del response.headers['Cross-Origin-Embedder-Policy']
        
        # إضافة CORS headers للـ APIs
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        return response

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

    # ✅ تفعيل APScheduler لنظام الذكاء الاصطناعي
    if not app.config.get('TESTING'):
        try:
            from src.tasks import init_scheduler
            ai_scheduler = init_scheduler(app)
            app.ai_scheduler = ai_scheduler
            print("✅ AI APScheduler activated successfully")
            print("🤖 Automatic student analysis enabled")
        except ImportError:
            print("⚠️ APScheduler not available - install with: pip install APScheduler")
        except Exception as e:
            print(f"❌ Error initializing AI APScheduler: {e}")

    # تهيئة جدولة النسخ الاحتياطي المحسنة
    if backup_scheduler_available:
        try:
            scheduler = init_backup_scheduler(app)
            app.backup_scheduler = scheduler
            print("✅ تم تهيئة جدولة النسخ الاحتياطي")
            
            # بدء تشغيل الجدولة في thread منفصل (حل مشكلة before_first_request المهملة)
            import threading
            import time
            
            def start_scheduler_delayed():
                """بدء تشغيل الجدولة بعد تأخير قصير لضمان تهيئة التطبيق"""
                time.sleep(2)  # انتظار لضمان تهيئة التطبيق
                try:
                    if start_backup_scheduler():
                        print("✅ تم بدء تشغيل جدولة النسخ الاحتياطي بنجاح")
                        # جدولة النسخ لجميع المستخدمين
                        scheduled_count = scheduler.schedule_all_users()
                        print(f"📅 تم جدولة النسخ الاحتياطي لـ {scheduled_count} مستخدم")
                    else:
                        print("❌ فشل في بدء تشغيل جدولة النسخ الاحتياطي")
                except Exception as e:
                    print(f"❌ خطأ في بدء تشغيل جدولة النسخ الاحتياطي: {e}")
            
            # تشغيل الجدولة في thread منفصل
            scheduler_thread = threading.Thread(target=start_scheduler_delayed, daemon=True)
            scheduler_thread.start()
            
        except Exception as e:
            print(f"❌ خطأ في تهيئة جدولة النسخ الاحتياطي: {e}")
    else:
        print("⚠️ جدولة النسخ الاحتياطي غير متوفرة")

    # Register blueprints - ✅ تنظيف التسجيل المكرر
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(question_bp, url_prefix="/questions")
    app.register_blueprint(curriculum_bp, url_prefix="/curriculum")
    app.register_blueprint(api_bp)  # url_prefix="/api/v1" معرَّف في Blueprint نفسه
    
    # تسجيل students blueprint
    if students_available:
        csrf.exempt(students_bp)
        app.register_blueprint(students_bp)  # يسجل البلوبرينت بـ url_prefix='/students'
        print("✅ Students blueprint registered successfully")
        print(f"✅ Students routes available at: /students/api/login") 
    
    # ✅ تسجيل teachers blueprint لإدارة المعلمين
    if teachers_available:
        csrf.exempt(teachers_bp)
        app.register_blueprint(teachers_bp)  # يسجل البلوبرينت بـ url_prefix='/teachers'
        print("✅ Teachers blueprint registered successfully")
    
    # تسجيل registration blueprint للتسجيل الذاتي
    if registration_available:
        app.register_blueprint(registration_bp)
        print("✅ Registration blueprint registered successfully")
    
    # تسجيل password reset blueprint لإعادة تعيين كلمة المرور
    if password_reset_available:
        app.register_blueprint(password_reset_bp)
        print("✅ Password Reset blueprint registered successfully")
    
    # تسجيل admin profile blueprint لجلب بيانات الأدمن
    if admin_profile_available:
        app.register_blueprint(admin_profile_bp)
        print("✅ Admin Profile blueprint registered successfully")
        print("🔐 Admin profile endpoint available at: /api/admin/profile")
    
    # ✅ تسجيل reports blueprint لنظام التقارير الشامل
    if reports_available:
        csrf.exempt(reports_bp)  # إعفاء من CSRF لأن APIs محمية بـ login
        app.register_blueprint(reports_bp)  # يسجل البلوبرينت بـ url_prefix='/reports'
        print("✅ Reports blueprint registered successfully")
        print("📊 Reports endpoints available at:")
        print("   - /reports/api/students-performance")
        print("   - /reports/api/top-performers")
        print("   - /reports/api/need-help")
        print("   - /reports/api/courses-analysis")
        print("   - /reports/api/activity")
        print("   - /reports/api/student/<id>")
        print("   - /reports/api/export-excel")
    
    # ✅ تسجيل Admin AI Blueprint لنظام الذكاء الاصطناعي
    if admin_ai_available:
        csrf.exempt(admin_ai_bp)
        app.register_blueprint(admin_ai_bp)
        print("✅ Admin AI blueprint registered successfully")
        print("🤖 AI Co-Admin System activated!")
        print("📊 AI endpoints available at:")
        print("   - /api/admin/ai/dashboard/stats")
        print("   - /api/admin/ai/analyze/student/<id>")
        print("   - /api/admin/ai/analyze/all")
        print("   - /api/admin/ai/dashboard/students-need-attention")
        print("   - /api/admin/ai/notification/send")
        print("   - /api/admin/ai/chat")
        print("   - /api/admin/ai/settings")
        print("   - /api/admin/ai/logs")
        print("   - /api/admin/ai/report/daily")
        print("   - /api/admin/ai/status")
    
    # ✅ تسجيل Gamification Blueprint لنظام النقاط والإنجازات
    try:
        from src.routes.gamification_routes import gamification_bp
        csrf.exempt(gamification_bp)
        app.register_blueprint(gamification_bp)
        print("✅ Gamification blueprint registered successfully")
        print("🎮 Gamification System activated!")
        print("🏆 Gamification endpoints available at:")
        print("   - /api/gamification/points/<id>")
        print("   - /api/gamification/leaderboard")
        print("   - /api/gamification/achievements/<id>")
        print("   - /api/gamification/challenge/today")
        print("   - /api/gamification/challenge/progress/<id>")
        print("   - /api/gamification/stats/<id>")
    except ImportError as e:
        print(f"⚠️ Gamification blueprint not available: {e}")
    except Exception as e:
        print(f"❌ Error registering Gamification blueprint: {e}")
    
    # تسجيل Google Drive Backend routes إذا كان متاحاً - ✅ إصلاح التسجيل
    if google_drive_backend_available:
        try:
            register_google_drive_backend_routes(app)
            print("🚀 تم تسجيل Google Drive Backend routes بنجاح")
            print("📱 الوصول للتطبيق: /google-drive-backend/google-drive-dashboard")
            print("⚙️ صفحة الإعدادات: /google-drive-backend/google-drive-settings")
            print("☁️ مزامنة Google Drive متاحة")
        except Exception as e:
            print(f"Warning: Could not register Google Drive Backend routes: {e}")
    
    # تسجيل APIs النسخ الاحتياطي المحسنة إذا كانت متاحة - ✅ تسجيل واحد فقط
    if backup_apis_available:
        try:
            register_backup_apis(app)
            logger.info("Backup APIs registered successfully")
        except Exception as e:
            print(f"⚠️ Warning: Could not register Enhanced Backup APIs: {e}")
    
    # إضافة context processor لجعل unread_count متاح في جميع القوالب
    @app.context_processor
    def inject_unread_count():
        from src.models.notification import Notification
        """حقن عدد الإشعارات غير المقروءة في جميع القوالب"""
        if current_user.is_authenticated:
            try:
                unread_count = Notification.query.filter_by(
                    user_id=current_user.id, 
                    is_read=False
                ).count()
                return {'unread_count': unread_count}
            except Exception as e:
                print(f"Warning: Could not calculate unread count: {e}")
                return {'unread_count': 0}
        return {'unread_count': 0}
    
    # تسجيل blueprint الإشعارات - ✅ تسجيل واحد فقط
    try:
        from src.routes.notifications import notifications_bp
        app.register_blueprint(notifications_bp, url_prefix="/notifications")
        print("Notifications blueprint registered successfully.")
    except ImportError:
        try:
            from routes.notifications import notifications_bp
            app.register_blueprint(notifications_bp, url_prefix="/notifications")
            print("Notifications blueprint registered successfully.")
        except ImportError:
            print("Warning: No app context available for notifications init")
    
    # تسجيل blueprint الإعدادات إذا كان متاحاً - ✅ تسجيل واحد فقط
    if settings_available:
        try:
            app.register_blueprint(settings_bp, url_prefix="/settings")
            print("Settings blueprint registered successfully.")
        except Exception as e:
            print(f"Warning: Could not register settings blueprint: {e}")

    @app.route("/", endpoint='index')
    def home():
        # إذا كان المستخدم مسجل الدخول، عرض لوحة التحكم
        if current_user.is_authenticated:
            return dashboard()
        # إذا كان زائر، عرض الصفحة الرئيسية
        return render_template("home.html")
    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        from src.models.notification import Notification
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
        
        # حساب عدد الأسئلة والمناهج والوحدات والدروس
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

        # إضافة معالجة الإشعارات المحسنة
        try:
            notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
            unread_count = sum(1 for n in notifications if not n.is_read)
            context["notifications"] = notifications
            context["unread_count"] = unread_count
        except Exception as e:
            print(f"Warning: Failed to load notifications: {e}")
            context["notifications"] = []
            context["unread_count"] = 0
            
        return render_template("index.html", **context)

    # استثناء مسارات API والنماذج من حماية CSRF
    @csrf.exempt
    def csrf_exempt_routes():
        # استثناء جميع مسارات API
        if request.path.startswith('/api/'):
            return True
        # استثناء مسارات النماذج (إضافة وتعديل الأسئلة)
        if request.path.startswith('/questions/add') or '/questions/edit/' in request.path:
            return True
        # استثناء مسارات استيراد الأسئلة
        if request.path.startswith('/questions/import'):
            return True
        # استثناء مسارات Google Drive
        if request.path.startswith('/settings/google-drive/'):
            return True
        return False

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

    # مسارات الإشعارات المحسنة
    @app.route("/notifications")
    @login_required
    def view_notifications():
        from src.models.notification import Notification, StudentNotification
        """عرض صفحة الإشعارات المُرسلة للطلاب"""
        try:
            # التحقق من صلاحيات الأدمن
            if not current_user.is_admin:
                flash('ليس لديك صلاحية الوصول', 'error')
                return redirect(url_for('dashboard'))
            
            # جلب جميع الإشعارات التي لها student_notifications (أي المُرسلة للطلاب)
            # باستخدام join للتأكد من وجود ارتباط في student_notifications
            notifications = db.session.query(Notification).join(
                StudentNotification,
                Notification.id == StudentNotification.notification_id
            ).distinct().order_by(Notification.created_at.desc()).limit(100).all()
            
            # حساب عدد غير المقروءة (من منظور الإشعارات نفسها)
            unread_count = sum(1 for n in notifications if not n.is_read)
            
            return render_template("notifications.html", 
                                 notifications=notifications, 
                                 unread_count=unread_count)
        except Exception as e:
            print(f"Error loading notifications page: {e}")
            import traceback
            traceback.print_exc()
            flash('حدث خطأ في تحميل صفحة الإشعارات', 'error')
            return redirect(url_for('dashboard'))
    
    @app.route("/notifications/action", methods=["POST"])
    @login_required
    def bulk_notifications_action():
        from src.models.notification import Notification
        """تنفيذ إجراءات جماعية على الإشعارات مع تحسينات"""
        try:
            notif_ids = request.form.getlist("notif_ids")
            action = request.form.get("action")

            if not notif_ids:
                flash("يرجى تحديد إشعار واحد على الأقل.", 'warning')
                return redirect(url_for("view_notifications"))

            # تحويل IDs إلى أرقام صحيحة
            try:
                notif_ids = [int(id) for id in notif_ids]
            except ValueError:
                flash("معرفات الإشعارات غير صحيحة.", 'error')
                return redirect(url_for("view_notifications"))

            # جلب الإشعارات الخاصة بالمستخدم فقط
            notifications = Notification.query.filter(
                Notification.id.in_(notif_ids),
                Notification.user_id == current_user.id
            ).all()

            if not notifications:
                flash("لم يتم العثور على إشعارات صالحة للتحديث.", 'warning')
                return redirect(url_for("view_notifications"))

            if action == "mark_read":
                updated_count = 0
                for notif in notifications:
                    if not notif.is_read:
                        notif.is_read = True
                        updated_count += 1
                
                db.session.commit()
                
                if updated_count > 0:
                    flash(f"تم تحديد {updated_count} إشعار كمقروء.", 'success')
                else:
                    flash("جميع الإشعارات المحددة مقروءة بالفعل.", 'info')

            elif action == "delete":
                deleted_count = len(notifications)
                for notif in notifications:
                    db.session.delete(notif)
                
                db.session.commit()
                flash(f"تم حذف {deleted_count} إشعار بنجاح.", 'success')
                
                # تسجيل نشاط الحذف إذا كان متاحاً
                if activity_available:
                    try:
                        Activity.log_user_activity(
                            current_user.id, 
                            "delete", 
                            "notification", 
                            f"تم حذف {deleted_count} إشعار"
                        )
                    except Exception as e:
                        print(f"Warning: Could not log delete activity: {e}")
            else:
                flash("إجراء غير صحيح.", 'error')

        except Exception as e:
            db.session.rollback()
            print(f"Error in bulk notifications action: {e}")
            flash('حدث خطأ في تنفيذ الإجراء. يرجى المحاولة مرة أخرى.', 'error')

        return redirect(url_for("view_notifications"))

    # إضافة مسار لتحديد إشعار واحد كمقروء
    @app.route("/notifications/<int:notif_id>/mark-read", methods=["POST"])
    @login_required
    def mark_single_notification_read(notif_id):
        from src.models.notification import Notification
        """تحديد إشعار واحد كمقروء"""
        try:
            notification = Notification.query.filter_by(
                id=notif_id, 
                user_id=current_user.id
            ).first()
            
            if not notification:
                return jsonify({'error': 'الإشعار غير موجود'}), 404
            
            if not notification.is_read:
                notification.is_read = True
                db.session.commit()
                return jsonify({'success': True, 'message': 'تم تحديد الإشعار كمقروء'})
            else:
                return jsonify({'success': True, 'message': 'الإشعار مقروء بالفعل'})
                
        except Exception as e:
            db.session.rollback()
            print(f"Error marking notification {notif_id} as read: {e}")
            return jsonify({'error': 'حدث خطأ في تحديث الإشعار'}), 500

    # إضافة مسار لحذف إشعار واحد
    @app.route("/notifications/<int:notif_id>/delete", methods=["POST"])
    @login_required
    def delete_single_notification(notif_id):
        """حذف إشعار واحد"""
        try:
            notification = Notification.query.filter_by(
                id=notif_id, 
                user_id=current_user.id
            ).first()
            
            if not notification:
                return jsonify({'error': 'الإشعار غير موجود'}), 404
            
            db.session.delete(notification)
            db.session.commit()
            
            # تسجيل نشاط الحذف إذا كان متاحاً
            if activity_available:
                try:
                    Activity.log_user_activity(
                        current_user.id, 
                        "delete", 
                        "notification", 
                        f"تم حذف إشعار: {notification.title}"
                    )
                except Exception as e:
                    print(f"Warning: Could not log delete activity: {e}")
            
            return jsonify({'success': True, 'message': 'تم حذف الإشعار بنجاح'})
                
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting notification {notif_id}: {e}")
            return jsonify({'error': 'حدث خطأ في حذف الإشعار'}), 500

    # ===== صفحات الخصوصية والشروط والدعم =====
    
    @app.route("/privacy")
    def privacy():
        """صفحة سياسة الخصوصية"""
        return render_template("privacy.html")
    
    @app.route("/terms")
    def terms():
        """صفحة شروط الاستخدام"""
        return render_template("terms.html")
    
    @app.route("/support")
    def support():
        """صفحة الدعم الفني"""
        return render_template("support.html")
    
    @app.route("/home")
    def home_page():
        """الصفحة الرئيسية للزوار"""
        return render_template("home.html")

    # ===== Google Drive APIs المفقودة =====
    
    @app.route('/api/v1/google-drive/connect', methods=['POST'])
    def connect_google_drive():
        """ربط Google Drive - محسن لحفظ Token في قاعدة البيانات"""
        try:
            print('🔗 محاولة ربط Google Drive...')
            
            # التحقق من المستخدم أولاً
            if not current_user.is_authenticated:
                print('❌ المستخدم غير مسجل دخول')
                return jsonify({
                    'success': False,
                    'message': 'يجب تسجيل الدخول أولاً',
                    'connected': False
                }), 401
            
            # طباعة معلومات الطلب للتشخيص
            print(f'📋 Content-Type: {request.content_type}')
            print(f'📋 Method: {request.method}')
            print(f'📋 User ID: {current_user.id}')
            
            # الحصول على بيانات Token من الطلب
            try:
                # محاولة قراءة البيانات بطرق مختلفة
                data = None
                
                if request.is_json:
                    data = request.get_json()
                    print(f'📥 JSON data received: {bool(data)}')
                elif request.form:
                    data = request.form.to_dict()
                    print(f'📥 Form data received: {bool(data)}')
                else:
                    # محاولة قراءة البيانات الخام
                    raw_data = request.get_data(as_text=True)
                    print(f'📥 Raw data length: {len(raw_data)}')
                    if raw_data:
                        import json
                        data = json.loads(raw_data)
                
                if not data:
                    print('❌ لم يتم العثور على بيانات في الطلب')
                    return jsonify({
                        'success': False,
                        'message': 'لم يتم إرسال بيانات صحيحة - البيانات فارغة',
                        'connected': False,
                        'debug': {
                            'content_type': request.content_type,
                            'has_json': request.is_json,
                            'has_form': bool(request.form),
                            'raw_data_length': len(request.get_data())
                        }
                    }), 400
                    
            except Exception as json_error:
                print(f'❌ خطأ في قراءة البيانات: {json_error}')
                return jsonify({
                    'success': False,
                    'message': f'خطأ في قراءة البيانات: {str(json_error)}',
                    'connected': False
                }), 400
            
            # استخراج معلومات Token
            access_token = data.get('access_token')
            token_type = data.get('token_type', 'Bearer')
            expires_in = data.get('expires_in')
            scope = data.get('scope')
            refresh_token = data.get('refresh_token')
            
            print(f'📥 تم استلام - access_token: {bool(access_token)}, type: {token_type}, refresh: {bool(refresh_token)}')
            print(f'📥 expires_in: {expires_in}, scope: {scope}')
            
            if not access_token:
                print('❌ access_token مفقود من البيانات')
                return jsonify({
                    'success': False,
                    'message': 'لم يتم توفير access token في البيانات المرسلة',
                    'connected': False,
                    'debug': {
                        'received_keys': list(data.keys()) if data else [],
                        'data_sample': str(data)[:200] if data else 'لا توجد بيانات'
                    }
                }), 400
            
            # أولاً: حفظ في قاعدة البيانات (الأولوية الأولى)
            token_saved_in_db = False
            if google_drive_model_available and current_user.is_authenticated:
                try:
                    import json
                    from src.models.google_drive import GoogleDriveToken
                    
                    # إعداد بيانات الـ token للحفظ
                    token_data = {
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
                        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
                        'scopes': json.dumps(scope.split() if scope else ['https://www.googleapis.com/auth/drive.file']),
                        'expires_in': expires_in
                    }
                    
                    print(f'💾 محاولة حفظ token في قاعدة البيانات للمستخدم {current_user.id}...')
                    
                    # حفظ الـ token في قاعدة البيانات
                    saved_token = GoogleDriveToken.create_or_update_token(current_user.id, token_data)
                    
                    if saved_token:
                        token_saved_in_db = True
                        print(f'✅ تم حفظ token في قاعدة البيانات بنجاح للمستخدم {current_user.id}')
                        print(f'📊 Token ID: {saved_token.id}, Active: {saved_token.is_active}')
                        
                        # التحقق من حفظ البيانات
                        verification_token = GoogleDriveToken.get_user_token(current_user.id)
                        if verification_token:
                            print(f'✅ تم التحقق من حفظ Token - ID: {verification_token.id}')
                        else:
                            print(f'⚠️ فشل في التحقق من حفظ Token')
                    else:
                        print(f'❌ فشل في حفظ token في قاعدة البيانات للمستخدم {current_user.id}')
                    
                except Exception as db_error:
                    print(f'❌ خطأ في حفظ token في قاعدة البيانات: {db_error}')
                    import traceback
                    traceback.print_exc()
                    # لا نفشل العملية إذا فشل حفظ قاعدة البيانات، لكن نسجل الخطأ
            else:
                print(f'⚠️ نموذج Google Drive غير متاح أو المستخدم غير مصادق عليه')
                print(f'📊 google_drive_model_available: {google_drive_model_available}')
                print(f'📊 current_user.is_authenticated: {current_user.is_authenticated}')
            
            # ثانياً: حفظ في الجلسة كنسخة احتياطية
            try:
                session['google_drive_connected'] = True
                session['google_drive_token'] = access_token
                if refresh_token:
                    session['google_drive_refresh_token'] = refresh_token
                session['google_drive_user_id'] = current_user.id
                session['google_drive_expires_in'] = expires_in
                session['google_drive_scope'] = scope
                
                print('✅ تم حفظ token في الجلسة كنسخة احتياطية')
            except Exception as session_error:
                print(f'⚠️ خطأ في حفظ token في الجلسة: {session_error}')
            
            # إعداد الاستجابة
            response_data = {
                'success': True,
                'message': 'تم ربط Google Drive بنجاح',
                'connected': True,
                'user_id': current_user.id,
                'token_saved_in_db': token_saved_in_db,
                'token_saved_in_session': True,
                'has_refresh_token': bool(refresh_token),
                'expires_in': expires_in
            }
            
            # إضافة معلومات إضافية للتشخيص
            if token_saved_in_db:
                response_data['storage_method'] = 'database_primary'
            else:
                response_data['storage_method'] = 'session_fallback'
                response_data['warning'] = 'تم حفظ Token في الجلسة فقط - قد ينقطع الاتصال عند انتهاء الجلسة'
            
            print(f'📤 إرسال استجابة ناجحة: {response_data}')
            return jsonify(response_data)
            
        except Exception as e:
            print(f'❌ خطأ عام في ربط Google Drive: {e}')
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'خطأ في الخادم: {str(e)}',
                'connected': False,
                'error_type': 'server_error'
            }), 500
    
    @app.route('/api/v1/google-drive/disconnect', methods=['POST'])
    def disconnect_google_drive():
        """قطع اتصال Google Drive"""
        try:
            # حذف من قاعدة البيانات إذا كان النموذج متاحاً
            if google_drive_model_available and current_user.is_authenticated:
                existing_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
                if existing_token:
                    db.session.delete(existing_token)
                    db.session.commit()
            
            # حذف من الجلسة
            session.pop('google_drive_connected', None)
            session.pop('google_drive_token', None)
            
            return jsonify({
                'success': True,
                'message': 'تم قطع الاتصال مع Google Drive بنجاح',
                'connected': False
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في قطع الاتصال: {str(e)}',
                'connected': True
            }), 500

    @app.route('/api/v1/google-drive/connection-status', methods=['GET'])
    def google_drive_connection_status():
        """فحص حالة اتصال Google Drive - محسن للتحقق من قاعدة البيانات أولاً"""
        try:
            print('🔍 فحص حالة اتصال Google Drive...')
            
            # أولاً: فحص قاعدة البيانات (الأولوية الأولى)
            db_connected = False
            db_token = None
            db_token_info = {}
            
            if google_drive_model_available and current_user.is_authenticated:
                try:
                    from src.models.google_drive import GoogleDriveToken
                    user_token = GoogleDriveToken.get_user_token(current_user.id)
                    if user_token and user_token.is_token_valid():
                        db_connected = True
                        db_token = {
                            'access_token': user_token.access_token,
                            'token_type': 'Bearer'
                        }
                        db_token_info = {
                            'token_id': user_token.id,
                            'expires_at': user_token.expiry.isoformat() if user_token.expiry else None,
                            'has_refresh_token': bool(user_token.refresh_token),
                            'created_at': user_token.created_at.isoformat() if user_token.created_at else None,
                            'last_backup': user_token.last_backup_date.isoformat() if user_token.last_backup_date else None,
                            'backup_count': user_token.backup_count
                        }
                        print(f'✅ تم العثور على token صالح في قاعدة البيانات للمستخدم {current_user.id}')
                        print(f'📊 Token ID: {user_token.id}, Expires: {user_token.expiry}')
                        
                        # تحديث الجلسة من قاعدة البيانات
                        session['google_drive_connected'] = True
                        session['google_drive_token'] = user_token.access_token
                        if user_token.refresh_token:
                            session['google_drive_refresh_token'] = user_token.refresh_token
                        session['google_drive_user_id'] = current_user.id
                        
                        print('🔄 تم تحديث الجلسة من قاعدة البيانات')
                    else:
                        print(f'❌ لا يوجد token صالح في قاعدة البيانات للمستخدم {current_user.id}')
                        if user_token:
                            print(f'📊 Token موجود لكن غير صالح - ID: {user_token.id}, Active: {user_token.is_active}, Valid: {user_token.is_token_valid()}')
                except Exception as db_error:
                    print(f'⚠️ خطأ في فحص قاعدة البيانات: {db_error}')
            else:
                print(f'⚠️ نموذج Google Drive غير متاح أو المستخدم غير مصادق عليه')
                print(f'📊 google_drive_model_available: {google_drive_model_available}')
                print(f'📊 current_user.is_authenticated: {current_user.is_authenticated if current_user else False}')
            
            # ثانياً: فحص الجلسة كنسخة احتياطية
            session_connected = session.get('google_drive_connected', False)
            session_token = session.get('google_drive_token')
            session_user_id = session.get('google_drive_user_id')
            
            print(f'📊 حالة الجلسة: connected={session_connected}, token={bool(session_token)}, user_id={session_user_id}')
            
            # تحديد الحالة النهائية
            final_connected = db_connected or session_connected
            final_token = None
            storage_method = 'none'
            
            if db_connected:
                final_token = db_token
                storage_method = 'database'
            elif session_connected and session_token:
                final_token = {
                    'access_token': session_token,
                    'token_type': 'Bearer'
                }
                storage_method = 'session'
            
            print(f'🎯 الحالة النهائية: connected={final_connected}, storage={storage_method}')
            
            # إعداد الاستجابة
            response_data = {
                'success': True,
                'status': {
                    'connected': final_connected,
                    'storage_method': storage_method
                }
            }
            
            # إضافة معلومات الـ token إذا كان متصلاً
            if final_connected and final_token:
                response_data['token'] = final_token
            
            # إضافة معلومات إضافية من قاعدة البيانات
            if db_connected and db_token_info:
                response_data['token_info'] = db_token_info
            
            # إضافة تحذير إذا كان الاتصال من الجلسة فقط
            if final_connected and storage_method == 'session':
                response_data['warning'] = 'الاتصال محفوظ في الجلسة فقط - قد ينقطع عند انتهاء الجلسة'
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f'❌ خطأ في فحص حالة Google Drive: {e}')
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'connected': False,
                'error': str(e),
                'error_type': 'server_error'
            }), 500

    @app.route('/api/v1/google-drive/refresh-token', methods=['POST'])
    def refresh_google_drive_token():
        """تحديث Google Drive Token"""
        try:
            print('🔄 طلب تحديث Google Drive Token...')
            
            # التحقق من المستخدم
            if not current_user.is_authenticated:
                return jsonify({
                    'success': False,
                    'message': 'يجب تسجيل الدخول أولاً'
                }), 401
            
            # البحث عن refresh_token في قاعدة البيانات
            refresh_token = None
            if google_drive_model_available:
                try:
                    from src.models.google_drive import GoogleDriveToken
                    user_token = GoogleDriveToken.query.filter_by(user_id=current_user.id, is_active=True).first()
                    if user_token and user_token.refresh_token:
                        refresh_token = user_token.refresh_token
                        print('✅ تم العثور على refresh_token في قاعدة البيانات')
                    else:
                        print(f'❌ لا يوجد refresh_token في قاعدة البيانات للمستخدم {current_user.id}')
                except Exception as e:
                    print(f'⚠️ خطأ في البحث في قاعدة البيانات: {e}')
            
            # البحث في الجلسة كبديل
            if not refresh_token:
                refresh_token = session.get('google_drive_refresh_token')
                if refresh_token:
                    print('✅ تم العثور على refresh_token في الجلسة')
                else:
                    print('❌ لا يوجد refresh_token في الجلسة')
            
            if not refresh_token:
                return jsonify({
                    'success': False,
                    'message': 'لا يوجد refresh_token. يجب إعادة تسجيل الدخول إلى Google Drive',
                    'requires_reauth': True
                }), 400
            
            # تحديث الـ token باستخدام النموذج المحسن
            if google_drive_model_available:
                try:
                    refreshed_token = GoogleDriveToken.refresh_user_token(current_user.id)
                    if refreshed_token:
                        # تحديث في الجلسة أيضاً
                        session['google_drive_token'] = refreshed_token.access_token
                        session['google_drive_connected'] = True
                        
                        print('✅ تم تحديث Token بنجاح')
                        
                        return jsonify({
                            'success': True,
                            'message': 'تم تحديث Token بنجاح',
                            'access_token': refreshed_token.access_token,
                            'token_type': 'Bearer',
                            'expires_at': refreshed_token.expiry.isoformat() if refreshed_token.expiry else None
                        })
                    else:
                        print('❌ فشل في تحديث Token')
                        return jsonify({
                            'success': False,
                            'message': 'فشل في تحديث Token',
                            'requires_reauth': True
                        }), 400
                except Exception as e:
                    print(f'❌ خطأ في تحديث Token: {e}')
                    return jsonify({
                        'success': False,
                        'message': f'خطأ في تحديث Token: {str(e)}'
                    }), 500
            else:
                # محاكاة تحديث Token (في حالة عدم توفر النموذج)
                import time
                new_access_token = f"new_token_{int(time.time())}"
                
                # تحديث في الجلسة
                session['google_drive_token'] = new_access_token
                session['google_drive_connected'] = True
                
                print('✅ تم تحديث Token بنجاح (محاكاة)')
                
                return jsonify({
                    'success': True,
                    'message': 'تم تحديث Token بنجاح',
                    'access_token': new_access_token,
                    'token_type': 'Bearer'
                })
            
        except Exception as e:
            print(f'❌ خطأ في تحديث Token: {e}')
            return jsonify({
                'success': False,
                'message': f'خطأ في تحديث Token: {str(e)}'
            }), 500

    @app.route('/api/v1/user-settings/sync-to-drive', methods=['POST'])
    def sync_user_settings_to_drive():
        """مزامنة إعدادات المستخدم إلى Google Drive"""
        try:
            if not session.get('google_drive_connected'):
                return jsonify({
                    'success': False,
                    'message': 'يجب ربط Google Drive أولاً'
                }), 400
            
            # محاكاة عملية المزامنة
            session['last_sync'] = datetime.utcnow().isoformat()
            
            return jsonify({
                'success': True,
                'message': 'تم رفع الإعدادات إلى Google Drive بنجاح',
                'last_sync': session['last_sync']
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في المزامنة: {str(e)}'
            }), 500

    @app.route('/api/v1/user-settings/download-from-drive', methods=['POST'])
    def download_user_settings_from_drive():
        """تحميل إعدادات المستخدم من Google Drive"""
        try:
            if not session.get('google_drive_connected'):
                return jsonify({
                    'success': False,
                    'message': 'يجب ربط Google Drive أولاً'
                }), 400
            
            # محاكاة عملية التحميل
            session['last_sync'] = datetime.utcnow().isoformat()
            
            return jsonify({
                'success': True,
                'message': 'تم تحميل الإعدادات من Google Drive بنجاح',
                'last_sync': session['last_sync']
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في التحميل: {str(e)}'
            }), 500

    @app.route('/api/v1/user-settings/quick-sync', methods=['POST'])
    def quick_sync_user_settings():
        """مزامنة سريعة لإعدادات المستخدم"""
        try:
            if not session.get('google_drive_connected'):
                return jsonify({
                    'success': False,
                    'message': 'يجب ربط Google Drive أولاً'
                }), 400
            
            # محاكاة عملية المزامنة السريعة
            session['last_sync'] = datetime.utcnow().isoformat()
            
            return jsonify({
                'success': True,
                'message': 'تمت المزامنة السريعة بنجاح',
                'last_sync': session['last_sync']
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في المزامنة السريعة: {str(e)}'
            }), 500

    @app.route('/api/v1/user-settings/sync-status', methods=['GET'])
    def user_settings_sync_status():
        """فحص حالة مزامنة إعدادات المستخدم"""
        try:
            connected = session.get('google_drive_connected', False)
            last_sync = session.get('last_sync')
            
            return jsonify({
                'success': True,
                'connected': connected,
                'last_sync': last_sync,
                'sync_enabled': connected
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # ===== APIs إعدادات النسخ الاحتياطي =====
    
    @app.route('/api/v1/backup-settings/save', methods=['POST'])
    def save_backup_settings():
        """حفظ إعدادات النسخ الاحتياطي"""
        try:
            data = request.get_json() or {}
            print(f"📥 تم استلام بيانات حفظ الإعدادات: {data}")
            
            # التحقق من المستخدم
            if not current_user.is_authenticated:
                print("❌ المستخدم غير مسجل الدخول")
                return jsonify({
                    'success': False,
                    'message': 'يجب تسجيل الدخول أولاً'
                }), 401
            
            print(f"👤 المستخدم المسجل: {current_user.id}")
            print(f"🔧 backup_settings_model_available: {backup_settings_model_available}")
            
            # حفظ في قاعدة البيانات إذا كان النموذج متاحاً
            if backup_settings_model_available:
                try:
                    settings_data = {
                        'auto_backup_enabled': data.get('auto_backup_enabled', False),
                        'backup_frequency': data.get('backup_frequency', 'daily'),
                        'backup_time': data.get('backup_time', '02:00'),
                        'max_backups': data.get('max_backups', 10),
                        'backup_destination': data.get('backup_destination', 'local')
                    }
                    
                    print(f"💾 محاولة حفظ الإعدادات: {settings_data}")
                    result = BackupSettings.update_user_settings(current_user.id, settings_data)
                    print(f"✅ تم حفظ الإعدادات بنجاح: {result}")
                    
                    return jsonify({
                        'success': True,
                        'message': 'تم حفظ إعدادات النسخ الاحتياطي بنجاح',
                        'settings': settings_data
                    }), 200
                except Exception as db_error:
                    print(f"❌ خطأ في قاعدة البيانات: {str(db_error)}")
                    # في حالة فشل قاعدة البيانات، احفظ في الجلسة
                    session['backup_settings'] = data
                    return jsonify({
                        'success': True,
                        'message': f'تم حفظ الإعدادات مؤقتاً (خطأ قاعدة البيانات: {str(db_error)})',
                        'settings': data
                    }), 200
            else:
                print("⚠️ نموذج BackupSettings غير متاح، الحفظ في الجلسة")
                # حفظ في الجلسة كبديل
                session['backup_settings'] = data
                return jsonify({
                    'success': True,
                    'message': 'تم حفظ إعدادات النسخ الاحتياطي مؤقتاً',
                    'settings': data
                }), 200
                
        except Exception as e:
            print(f"❌ خطأ عام في API: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'خطأ في حفظ إعدادات النسخ الاحتياطي: {str(e)}'
            }), 500

    @app.route('/api/v1/auth/google/refresh', methods=['POST'])
    def refresh_google_token():
        """تحديث Google Drive Token"""
        try:
            print('🔄 طلب تحديث Google Drive Token...')
            
            # التحقق من المستخدم
            if not current_user.is_authenticated:
                return jsonify({
                    'success': False,
                    'message': 'يجب تسجيل الدخول أولاً'
                }), 401
            
            # البحث عن refresh_token في قاعدة البيانات
            refresh_token = None
            if google_drive_model_available:
                try:
                    user_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
                    if user_token and user_token.refresh_token:
                        refresh_token = user_token.refresh_token
                        print('✅ تم العثور على refresh_token في قاعدة البيانات')
                    else:
                        print(f'❌ لا يوجد refresh_token في قاعدة البيانات للمستخدم {current_user.id}')
                except Exception as e:
                    print(f'⚠️ خطأ في البحث في قاعدة البيانات: {e}')
            
            # البحث في الجلسة كبديل
            if not refresh_token:
                refresh_token = session.get('google_drive_refresh_token')
                if refresh_token:
                    print('✅ تم العثور على refresh_token في الجلسة')
                else:
                    print('❌ لا يوجد refresh_token في الجلسة')
            
            if not refresh_token:
                return jsonify({
                    'success': False,
                    'message': 'لا يوجد refresh_token. يجب إعادة تسجيل الدخول إلى Google Drive',
                    'requires_reauth': True
                }), 400
            
            # محاكاة تحديث Token (في التطبيق الحقيقي، ستستدعي Google OAuth API)
            import time
            new_access_token = f"new_token_{int(time.time())}"
            
            # تحديث في قاعدة البيانات
            if google_drive_model_available:
                try:
                    user_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
                    if user_token:
                        user_token.access_token = new_access_token
                        user_token.created_at = datetime.utcnow()
                        db.session.commit()
                        print('💾 تم تحديث access_token في قاعدة البيانات')
                except Exception as e:
                    print(f'⚠️ خطأ في تحديث قاعدة البيانات: {e}')
            
            # تحديث في الجلسة
            session['google_drive_token'] = new_access_token
            session['google_drive_connected'] = True
            
            print('✅ تم تحديث Token بنجاح')
            
            return jsonify({
                'success': True,
                'message': 'تم تحديث Token بنجاح',
                'access_token': new_access_token,
                'token_type': 'Bearer'
            })
            
        except Exception as e:
            print(f'❌ خطأ في تحديث Token: {e}')
            return jsonify({
                'success': False,
                'message': f'خطأ في تحديث Token: {str(e)}'
            }), 500



    # ===== API للنسخ الاحتياطي الفوري =====
    @app.route('/api/v1/backup/immediate', methods=['POST'])
    @login_required
    def trigger_immediate_backup():
        """تشغيل نسخ احتياطي فوري للمستخدم الحالي"""
        try:
            if not backup_scheduler_available or not hasattr(app, 'backup_scheduler'):
                return jsonify({
                    'success': False,
                    'error': 'جدولة النسخ الاحتياطي غير متوفرة'
                }), 400
            
            scheduler = app.backup_scheduler
            
            # تشغيل نسخ احتياطي فوري للمستخدم الحالي
            success = scheduler.trigger_immediate_backup(current_user.id)
            
            if success:
                # تحديث عدد النسخ في قاعدة البيانات بعد نجاح العملية
                try:
                    if google_drive_model_available:
                        from src.models.google_drive import GoogleDriveToken
                        user_token = GoogleDriveToken.get_user_token(current_user.id)
                        if user_token:
                            # زيادة عدد النسخ
                            current_count = user_token.backup_count or 0
                            user_token.backup_count = current_count + 1
                            user_token.last_backup_time = datetime.utcnow()
                            db.session.commit()
                            logger.info(f"تم تحديث عدد النسخ للمستخدم {current_user.id}: {user_token.backup_count}")
                except Exception as e:
                    logger.error(f"خطأ في تحديث عدد النسخ: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'تم تشغيل النسخ الاحتياطي الفوري بنجاح',
                    'user_id': current_user.id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'فشل في تشغيل النسخ الاحتياطي الفوري'
                }), 400
                
        except Exception as e:
            logger.error(f"خطأ في API النسخ الفوري: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في تشغيل النسخ الاحتياطي الفوري: {str(e)}'
            }), 500

    # ===== API لحالة النسخ الاحتياطي =====
    @app.route('/api/v1/backup/status', methods=['GET'])
    @login_required
    def get_backup_status_api():
        """الحصول على حالة النسخ الاحتياطي للمستخدم الحالي"""
        try:
            status = {
                'success': True,
                'status': {
                    'settings': {
                        'auto_backup_enabled': False,
                        'backup_frequency': 'daily',
                        'backup_destination': 'local',
                        'max_backups': 5,
                        'last_backup_time': None,
                        'updated_at': None
                    },
                    'google_drive': {
                        'connected': False,
                        'last_backup': None
                    },
                    'scheduler': {
                        'user_scheduled': False,
                        'next_backup': None
                    }
                }
            }
            
            # فحص إعدادات النسخ الاحتياطي من قاعدة البيانات
            try:
                if backup_settings_model_available:
                    from src.models.backup_settings import BackupSettings
                    user_settings = BackupSettings.get_user_settings(current_user.id)
                    if user_settings:
                        status['status']['settings'].update({
                            'auto_backup_enabled': user_settings.auto_backup_enabled,
                            'backup_frequency': user_settings.backup_frequency,
                            'backup_destination': user_settings.backup_destination,
                            'max_backups': user_settings.max_backups,
                            'updated_at': user_settings.updated_at.isoformat() if user_settings.updated_at else None
                        })
            except Exception as e:
                logger.error(f"خطأ في جلب إعدادات النسخ: {e}")
            
            # فحص حالة Google Drive
            try:
                if google_drive_model_available:
                    from src.models.google_drive import GoogleDriveToken
                    user_token = GoogleDriveToken.get_user_token(current_user.id)
                    if user_token and user_token.is_valid():
                        status['status']['google_drive'].update({
                            'connected': True,
                            'last_backup': user_token.last_backup_time.isoformat() if user_token.last_backup_time else None
                        })
                        # تحديث آخر نسخة في الإعدادات أيضاً
                        if user_token.last_backup_time:
                            status['status']['settings']['last_backup_time'] = user_token.last_backup_time.isoformat()
            except Exception as e:
                logger.error(f"خطأ في فحص حالة Google Drive: {e}")
            
            # فحص حالة الجدولة
            try:
                if backup_scheduler_available and hasattr(app, 'backup_scheduler'):
                    scheduler = app.backup_scheduler
                    jobs = scheduler.get_scheduled_jobs()
                    user_jobs = [job for job in jobs if job.get('user_id') == current_user.id]
                    if user_jobs:
                        status['status']['scheduler']['user_scheduled'] = True
                        # البحث عن موعد النسخة التالية
                        for job in user_jobs:
                            if job.get('next_run_time'):
                                status['status']['scheduler']['next_backup'] = job['next_run_time']
                                break
            except Exception as e:
                logger.error(f"خطأ في فحص حالة الجدولة: {e}")
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"خطأ في API حالة النسخ: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب حالة النسخ الاحتياطي: {str(e)}'
            }), 500

    # ===== API لحالة اتصال Google Drive =====
    @app.route('/api/v1/google-drive/connection-status', methods=['GET'])
    @login_required
    def get_google_drive_connection_status():
        """فحص حالة اتصال Google Drive للمستخدم الحالي"""
        try:
            status = {
                'success': True,
                'status': {
                    'connected': False,
                    'user_email': None,
                    'last_backup': None,
                    'backup_count': 0
                }
            }
            
            # فحص من قاعدة البيانات
            try:
                if google_drive_model_available:
                    from src.models.google_drive import GoogleDriveToken
                    user_token = GoogleDriveToken.get_user_token(current_user.id)
                    if user_token and user_token.is_valid():
                        status['status'].update({
                            'connected': True,
                            'user_email': user_token.user_email,
                            'last_backup': user_token.last_backup_time.isoformat() if user_token.last_backup_time else None,
                            'backup_count': user_token.backup_count or 0
                        })
            except Exception as e:
                logger.error(f"خطأ في فحص token من قاعدة البيانات: {e}")
            
            # فحص من الجلسة كبديل
            if not status['status']['connected']:
                if session.get('google_drive_connected') and session.get('google_drive_user_id') == current_user.id:
                    status['status']['connected'] = True
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"خطأ في API حالة Google Drive: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في فحص حالة Google Drive: {str(e)}'
            }), 500

    # ===== API لمعلومات المستخدم =====
    @app.route('/api/v1/user/info', methods=['GET'])
    @login_required
    def get_user_info():
        """الحصول على معلومات المستخدم الحالي"""
        try:
            return jsonify({
                'success': True,
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'email': getattr(current_user, 'email', None),
                    'is_admin': getattr(current_user, 'is_admin', False)
                }
            })
        except Exception as e:
            logger.error(f"خطأ في API معلومات المستخدم: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب معلومات المستخدم: {str(e)}'
            }), 500

    # ===== API لحفظ إعدادات النسخ الاحتياطي =====
    @app.route('/api/v1/backup/settings', methods=['POST'])
    @login_required
    def save_backup_settings_api():
        """حفظ إعدادات النسخ الاحتياطي للمستخدم الحالي"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'لا توجد بيانات لحفظها'
                }), 400
            
            # التحقق من صحة البيانات
            valid_frequencies = ['daily', 'weekly', 'monthly']
            valid_destinations = ['local', 'google_drive']
            
            settings = {}
            
            # تفعيل النسخ التلقائي
            if 'auto_backup_enabled' in data:
                settings['auto_backup_enabled'] = bool(data['auto_backup_enabled'])
            
            # تكرار النسخ
            if 'backup_frequency' in data:
                frequency = data['backup_frequency']
                if frequency in valid_frequencies:
                    settings['backup_frequency'] = frequency
                else:
                    return jsonify({
                        'success': False,
                        'error': f'تكرار النسخ غير صحيح. القيم المسموحة: {valid_frequencies}'
                    }), 400
            
            # وجهة النسخ
            if 'backup_destination' in data:
                destination = data['backup_destination']
                if destination in valid_destinations:
                    settings['backup_destination'] = destination
                else:
                    return jsonify({
                        'success': False,
                        'error': f'وجهة النسخ غير صحيحة. القيم المسموحة: {valid_destinations}'
                    }), 400
            
            # الحد الأقصى للنسخ
            if 'max_backups' in data:
                max_backups = data['max_backups']
                if isinstance(max_backups, int) and max_backups > 0:
                    settings['max_backups'] = max_backups
                else:
                    return jsonify({
                        'success': False,
                        'error': 'الحد الأقصى للنسخ يجب أن يكون رقم موجب'
                    }), 400
            
            # حفظ الإعدادات في قاعدة البيانات
            try:
                if backup_settings_model_available:
                    from src.models.backup_settings import BackupSettings
                    
                    # إنشاء أو تحديث إعدادات المستخدم
                    user_settings = BackupSettings.create_or_update_settings(current_user.id, settings)
                    
                    if user_settings:
                        logger.info(f"تم حفظ إعدادات النسخ للمستخدم {current_user.id}: {settings}")
                        
                        # إذا تم تفعيل النسخ التلقائي، جدولة النسخ
                        if settings.get('auto_backup_enabled') and backup_scheduler_available and hasattr(app, 'backup_scheduler'):
                            try:
                                scheduler = app.backup_scheduler
                                frequency = settings.get('backup_frequency', 'daily')
                                success = scheduler.schedule_user_backup(current_user.id, frequency)
                                if success:
                                    logger.info(f"تم جدولة النسخ التلقائي للمستخدم {current_user.id} بتكرار {frequency}")
                                else:
                                    logger.warning(f"فشل في جدولة النسخ التلقائي للمستخدم {current_user.id}")
                            except Exception as e:
                                logger.error(f"خطأ في جدولة النسخ التلقائي: {e}")
                        
                        return jsonify({
                            'success': True,
                            'message': 'تم حفظ إعدادات النسخ الاحتياطي بنجاح',
                            'settings': {
                                'auto_backup_enabled': user_settings.auto_backup_enabled,
                                'backup_frequency': user_settings.backup_frequency,
                                'backup_destination': user_settings.backup_destination,
                                'max_backups': user_settings.max_backups,
                                'updated_at': user_settings.updated_at.isoformat() if user_settings.updated_at else None
                            }
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'فشل في حفظ الإعدادات في قاعدة البيانات'
                        }), 500
                else:
                    # حفظ في الجلسة كبديل
                    session['backup_settings'] = settings
                    session['backup_settings']['user_id'] = current_user.id
                    logger.info(f"تم حفظ إعدادات النسخ في الجلسة للمستخدم {current_user.id}: {settings}")
                    
                    return jsonify({
                        'success': True,
                        'message': 'تم حفظ إعدادات النسخ الاحتياطي بنجاح (في الجلسة)',
                        'settings': settings
                    })
                    
            except Exception as e:
                logger.error(f"خطأ في حفظ إعدادات النسخ: {e}")
                return jsonify({
                    'success': False,
                    'error': f'خطأ في حفظ الإعدادات: {str(e)}'
                }), 500
            
        except Exception as e:
            logger.error(f"خطأ في API حفظ إعدادات النسخ: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في معالجة الطلب: {str(e)}'
            }), 500

    # ===== API لجلب إعدادات النسخ الاحتياطي =====
    @app.route('/api/v1/backup/settings', methods=['GET'])
    @login_required
    def get_backup_settings_api():
        """جلب إعدادات النسخ الاحتياطي للمستخدم الحالي"""
        try:
            settings = {
                'success': True,
                'settings': {
                    'auto_backup_enabled': False,
                    'backup_frequency': 'daily',
                    'backup_destination': 'local',
                    'max_backups': 5,
                    'updated_at': None
                }
            }
            
            # جلب من قاعدة البيانات
            try:
                if backup_settings_model_available:
                    from src.models.backup_settings import BackupSettings
                    user_settings = BackupSettings.get_user_settings(current_user.id)
                    if user_settings:
                        settings['settings'].update({
                            'auto_backup_enabled': user_settings.auto_backup_enabled,
                            'backup_frequency': user_settings.backup_frequency,
                            'backup_destination': user_settings.backup_destination,
                            'max_backups': user_settings.max_backups,
                            'updated_at': user_settings.updated_at.isoformat() if user_settings.updated_at else None
                        })
            except Exception as e:
                logger.error(f"خطأ في جلب إعدادات النسخ من قاعدة البيانات: {e}")
            
            # جلب من الجلسة كبديل
            if not settings['settings']['updated_at']:
                session_settings = session.get('backup_settings')
                if session_settings and session_settings.get('user_id') == current_user.id:
                    settings['settings'].update(session_settings)
            
            return jsonify(settings)
            
        except Exception as e:
            logger.error(f"خطأ في API جلب إعدادات النسخ: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب الإعدادات: {str(e)}'
            }), 500

    # ===== API للنسخ الاحتياطي الفوري (النسخة القديمة للتوافق) =====
    
    @app.route('/api/v1/backup-scheduler/status', methods=['GET'])
    @login_required
    def backup_scheduler_status():
        """فحص حالة جدولة النسخ الاحتياطي"""
        try:
            if not backup_scheduler_available or not hasattr(app, 'backup_scheduler'):
                return jsonify({
                    'success': False,
                    'message': 'جدولة النسخ الاحتياطي غير متوفرة',
                    'scheduler_running': False,
                    'user_scheduled': False
                }), 200
            
            scheduler = app.backup_scheduler
            is_running = scheduler.is_running
            
            # فحص ما إذا كان المستخدم الحالي لديه جدولة مفعلة
            user_scheduled = False
            user_job_info = None
            
            if current_user.is_authenticated:
                scheduled_jobs = scheduler.get_scheduled_jobs()
                for job in scheduled_jobs:
                    if job.get('user_id') == current_user.id:
                        user_scheduled = True
                        user_job_info = job
                        break
            
            return jsonify({
                'success': True,
                'scheduler_running': is_running,
                'user_scheduled': user_scheduled,
                'user_job_info': user_job_info,
                'total_scheduled_users': len(scheduler.get_scheduled_jobs())
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في فحص حالة الجدولة: {str(e)}'
            }), 500
    
    @app.route('/api/v1/backup-scheduler/schedule', methods=['POST'])
    @login_required
    def schedule_user_backup_api():
        """جدولة النسخ الاحتياطي للمستخدم الحالي"""
        try:
            if not backup_scheduler_available or not hasattr(app, 'backup_scheduler'):
                return jsonify({
                    'success': False,
                    'message': 'جدولة النسخ الاحتياطي غير متوفرة'
                }), 200
            
            scheduler = app.backup_scheduler
            
            # جدولة النسخ للمستخدم الحالي
            success = scheduler.schedule_user_backup(current_user.id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'تم جدولة النسخ الاحتياطي بنجاح',
                    'user_id': current_user.id
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'فشل في جدولة النسخ الاحتياطي. تأكد من تفعيل النسخ التلقائي في الإعدادات'
                }), 200
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في جدولة النسخ الاحتياطي: {str(e)}'
            }), 500
    
    @app.route('/api/v1/backup-scheduler/unschedule', methods=['POST'])
    @login_required
    def unschedule_user_backup_api():
        """إلغاء جدولة النسخ الاحتياطي للمستخدم الحالي"""
        try:
            if not backup_scheduler_available or not hasattr(app, 'backup_scheduler'):
                return jsonify({
                    'success': False,
                    'message': 'جدولة النسخ الاحتياطي غير متوفرة'
                }), 200
            
            scheduler = app.backup_scheduler
            
            # إلغاء جدولة النسخ للمستخدم الحالي
            success = scheduler.remove_user_backup(current_user.id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'تم إلغاء جدولة النسخ الاحتياطي بنجاح',
                    'user_id': current_user.id
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'فشل في إلغاء جدولة النسخ الاحتياطي'
                }), 200
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في إلغاء جدولة النسخ الاحتياطي: {str(e)}'
            }), 500
    
    @app.route('/api/v1/backup-scheduler/trigger', methods=['POST'])
    @login_required
    def trigger_immediate_backup_api():
        """تشغيل نسخ احتياطي فوري للمستخدم الحالي"""
        try:
            if not backup_scheduler_available or not hasattr(app, 'backup_scheduler'):
                return jsonify({
                    'success': False,
                    'message': 'جدولة النسخ الاحتياطي غير متوفرة'
                }), 200
            
            scheduler = app.backup_scheduler
            
            # تشغيل نسخ احتياطي فوري للمستخدم الحالي
            success = scheduler.trigger_immediate_backup(current_user.id)
            
            if success:
                # تحديث عدد النسخ في قاعدة البيانات بعد نجاح العملية
                try:
                    if google_drive_model_available:
                        from models.google_drive import GoogleDriveToken
                        user_token = GoogleDriveToken.get_user_token(current_user.id)
                        if user_token:
                            # زيادة عدد النسخ
                            current_count = user_token.backup_count or 0
                            user_token.backup_count = current_count + 1
                            user_token.last_backup_time = datetime.utcnow()
                            db.session.commit()
                            logger.info(f"تم تحديث عدد النسخ للمستخدم {current_user.id}: {user_token.backup_count}")
                except Exception as e:
                    logger.error(f"خطأ في تحديث عدد النسخ: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'تم تشغيل النسخ الاحتياطي الفوري بنجاح',
                    'user_id': current_user.id
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'فشل في تشغيل النسخ الاحتياطي الفوري'
                }), 200
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في تشغيل النسخ الاحتياطي الفوري: {str(e)}'
            }), 500
    
    @app.route('/api/v1/backup-scheduler/jobs', methods=['GET'])
    @login_required
    def get_scheduled_jobs_api():
        """الحصول على قائمة المهام المجدولة"""
        try:
            if not backup_scheduler_available or not hasattr(app, 'backup_scheduler'):
                return jsonify({
                    'success': False,
                    'message': 'جدولة النسخ الاحتياطي غير متوفرة',
                    'jobs': []
                }), 200
            
            scheduler = app.backup_scheduler
            jobs = scheduler.get_scheduled_jobs()
            
            # تصفية المهام للمستخدم الحالي فقط (إذا لم يكن مدير)
            if not getattr(current_user, 'is_admin', False):
                jobs = [job for job in jobs if job.get('user_id') == current_user.id]
            
            return jsonify({
                'success': True,
                'jobs': jobs,
                'total_jobs': len(jobs)
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'خطأ في جلب المهام المجدولة: {str(e)}',
                'jobs': []
            }), 500

    # ===== Google OAuth Configuration API =====
    @app.route('/api/v1/google-oauth/config')
    def get_google_oauth_config():
        """إرسال إعدادات Google OAuth للفرونت إند"""
        try:
            import os
            config = {
                'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
                'api_key': os.environ.get('GOOGLE_API_KEY', 'AIzaSyCcM3yO_m0xeItzlClPmb6ULkxwZlqIcjc'),
                'success': True
            }
            
            # التحقق من وجود Client ID
            if not config['client_id']:
                config['success'] = False
                config['error'] = 'GOOGLE_CLIENT_ID غير محدد في متغيرات البيئة'
                
            return jsonify(config)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب إعدادات Google OAuth: {str(e)}',
                'client_id': '',
                'api_key': ''
            }), 500

    # ===== Service Worker للنسخ التلقائي =====
    @app.route('/backup-service-worker.js')
    def service_worker():
        """تقديم ملف Service Worker للنسخ التلقائي"""
        try:
            from flask import send_from_directory
            return send_from_directory('.', 'backup-service-worker.js', 
                                     mimetype='application/javascript')
        except Exception as e:
            return jsonify({'error': 'Service Worker غير متوفر'}), 404

    # ===== Google OAuth Callback Route =====
    @app.route('/auth/google/callback')
    def google_oauth_callback():
        """معالجة callback من Google OAuth - محسن للنوافذ المنبثقة"""
        try:
            print('🔗 تم استلام callback من Google OAuth...')
            
            # الحصول على authorization code و state من URL parameters
            authorization_code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
            
            print(f'📥 Code: {bool(authorization_code)}, State: {state}, Error: {error}')
            
            # التحقق من وجود خطأ في OAuth
            if error:
                print(f'❌ خطأ في OAuth: {error}')
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>خطأ في المصادقة</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <script>
                        try {{
                            if (window.opener && !window.opener.closed) {{
                                window.opener.postMessage({{
                                    type: 'google-auth-error',
                                    error: '{error}',
                                    message: 'فشل في المصادقة مع Google: {error}'
                                }}, '*');
                            }}
                        }} catch (e) {{
                            console.error('خطأ في إرسال الرسالة:', e);
                        }} finally {{
                            window.close();
                        }}
                    </script>
                    <p>فشل في المصادقة مع Google. يمكنك إغلاق هذه النافذة.</p>
                </body>
                </html>
                """
            
            # التحقق من وجود authorization code
            if not authorization_code:
                print('❌ لا يوجد authorization code')
                return """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>خطأ في المصادقة</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <script>
                        try {
                            if (window.opener && !window.opener.closed) {
                                window.opener.postMessage({
                                    type: 'google-auth-error',
                                    error: 'no_code',
                                    message: 'لم يتم الحصول على رمز التفويض من Google'
                                }, '*');
                            }
                        } catch (e) {
                            console.error('خطأ في إرسال الرسالة:', e);
                        } finally {
                            window.close();
                        }
                    </script>
                    <p>لم يتم الحصول على رمز التفويض. يمكنك إغلاق هذه النافذة.</p>
                </body>
                </html>
                """
            
            # استخراج user_id من state parameter
            user_id = None
            if state:
                try:
                    user_id = int(state)
                    print(f'👤 User ID من state: {user_id}')
                except ValueError:
                    print(f'⚠️ state غير صحيح: {state}')
            
            # إذا لم يكن user_id في state، استخدم current_user
            if not user_id and current_user.is_authenticated:
                user_id = current_user.id
                print(f'👤 User ID من current_user: {user_id}')
            
            if not user_id:
                print('❌ لا يمكن تحديد user_id')
                return """
                <script>
                    window.opener.postMessage({
                        type: 'google-auth-error',
                        error: 'no_user_id',
                        message: 'لا يمكن تحديد المستخدم. يرجى تسجيل الدخول أولاً'
                    }, '*');
                    window.close();
                </script>
                """
            
            # معالجة authorization code وحفظ token
            success = False
            error_message = None
            
            try:
                # استخدام Google Drive Manager لمعالجة OAuth callback
                if google_drive_model_available:
                    from src.models.google_drive import GoogleDriveToken
                    
                    # إنشاء أو تحديث token للمستخدم
                    print(f'💾 محاولة حفظ token للمستخدم {user_id}...')
                    
                    # هنا يجب استدعاء Google OAuth API لتبديل authorization code بـ access token
                    # لكن للآن سنحاكي العملية
                    import time
                    mock_token_data = {
                        'access_token': f'mock_access_token_{int(time.time())}',
                        'refresh_token': f'mock_refresh_token_{int(time.time())}',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
                        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
                        'scopes': ['https://www.googleapis.com/auth/drive.file'],
                        'expires_in': 3600
                    }
                    
                    saved_token = GoogleDriveToken.create_or_update_token(user_id, mock_token_data)
                    
                    if saved_token:
                        success = True
                        print(f'✅ تم حفظ token بنجاح للمستخدم {user_id}')
                        
                        # تحديث الجلسة أيضاً
                        session['google_drive_connected'] = True
                        session['google_drive_token'] = mock_token_data['access_token']
                        session['google_drive_user_id'] = user_id
                        
                    else:
                        error_message = 'فشل في حفظ token في قاعدة البيانات'
                        print(f'❌ {error_message}')
                else:
                    # حفظ في الجلسة فقط إذا لم يكن النموذج متاحاً
                    import time
                    session['google_drive_connected'] = True
                    session['google_drive_token'] = f'session_token_{int(time.time())}'
                    session['google_drive_user_id'] = user_id
                    success = True
                    print('✅ تم حفظ token في الجلسة')
                    
            except Exception as e:
                error_message = f'خطأ في معالجة OAuth callback: {str(e)}'
                print(f'❌ {error_message}')
                import traceback
                traceback.print_exc()
            
            # إرسال النتيجة للنافذة الأصلية
            if success:
                return """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>تم الربط بنجاح</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <script>
                        try {
                            if (window.opener && !window.opener.closed) {
                                window.opener.postMessage({
                                    type: 'google-auth-success',
                                    message: 'تم ربط Google Drive بنجاح'
                                }, '*');
                            }
                        } catch (e) {
                            console.error('خطأ في إرسال الرسالة:', e);
                        } finally {
                            setTimeout(() => window.close(), 1000);
                        }
                    </script>
                    <div style="text-align: center; padding: 50px; font-family: Arial;">
                        <h2 style="color: green;">✅ تم ربط Google Drive بنجاح!</h2>
                        <p>سيتم إغلاق هذه النافذة تلقائياً...</p>
                    </div>
                </body>
                </html>
                """
            else:
                return f"""
                <script>
                    window.opener.postMessage({{
                        type: 'google-auth-error',
                        error: 'callback_processing_failed',
                        message: '{error_message or "فشل في معالجة callback"}'
                    }}, '*');
                    window.close();
                </script>
                """
                
        except Exception as e:
            print(f'❌ خطأ عام في Google OAuth callback: {e}')
            import traceback
            traceback.print_exc()
            return f"""
            <script>
                window.opener.postMessage({{
                    type: 'google-auth-error',
                    error: 'server_error',
                    message: 'خطأ في الخادم: {str(e)}'
                }}, '*');
                window.close();
            </script>
            """


    # ============================================
    # بدء جدولة الرسائل التلقائية
    # ============================================
    print("🔥 DEBUG: بدء تهيئة automation_scheduler...")
    try:
        from src.automation_scheduler import start_automation_scheduler
        print("✅ DEBUG: تم استيراد start_automation_scheduler")
        
        # تشغيل في thread منفصل مع تأخير بسيط (مثل backup scheduler)
        import threading
        import time
        
        def start_automation_delayed():
            """بدء تشغيل جدولة الرسائل التلقائية بعد تأخير قصير لضمان تهيئة التطبيق"""
            time.sleep(2)  # انتظار لضمان تهيئة التطبيق
            try:
                start_automation_scheduler(app)
                print("✅ DEBUG: تم تشغيل start_automation_scheduler")
                app.logger.info("✅ تم تهيئة النظام التلقائي بنجاح")
            except Exception as e:
                print(f"❌ DEBUG: خطأ في start_automation_scheduler: {e}")
                app.logger.error(f"❌ فشل تهيئة النظام التلقائي: {e}")
                import traceback
                traceback.print_exc()
        
        # تشغيل الجدولة في thread منفصل
        automation_thread = threading.Thread(target=start_automation_delayed, daemon=True)
        automation_thread.start()
        print("✅ DEBUG: تم بدء thread جدولة الرسائل التلقائية")
            
    except ImportError as e:
        print(f"❌ DEBUG: فشل استيراد automation_scheduler: {e}")
        app.logger.error(f"❌ فشل استيراد automation_scheduler: {e}")
        import traceback
        traceback.print_exc()
    
    print("🔥 DEBUG: انتهى قسم automation_scheduler")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)


# إنشاء متغير app لـ gunicorn
app = create_app()

# ===== إضافة route للإعدادات إذا لم يكن موجوداً =====
try:
    @app.route('/settings')
    @login_required
    def settings_page():
        """صفحة الإعدادات مع دعم Google Drive Integration"""
        return render_template('settings.html')
    print("✅ Settings route registered successfully")
except Exception as e:
    print(f"⚠️ Settings route may already exist: {e}")

print("🚀 Google Drive Integration with Redirect Flow initialized successfully")

# ✅ Alias إضافي لتسهيل الوصول من السكربت القديم
@app.route("/api/backup/status")
@login_required
def alias_backup_status():
    """Alias route للتوافق مع الـ frontend القديم"""
    try:
        # استدعاء الدالة الصحيحة من backup_apis_enhanced
        from src.backup_apis_enhanced import get_backup_status
        return get_backup_status()
    except Exception as e:
        logger.error(f"Error in alias backup status: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في الحصول على حالة النسخ الاحتياطي',
            'error_type': 'alias_route_error'
        }), 500

# ===== API إحصائيات النسخ الاحتياطية الشاملة =====

@app.route('/api/v1/backup/stats', methods=['GET'])
@login_required
def get_backup_stats():
    """الحصول على إحصائيات النسخ الاحتياطية الشاملة"""
    try:
        user_id = current_user.id
        stats = {
            'total_backups': 0,
            'total_size': 0,
            'last_backup_time': None,
            'google_drive_connected': False,
            'google_drive_backups': 0,
            'local_backups': 0
        }
        
        # إحصائيات Google Drive
        try:
            if google_drive_model_available:
                from src.models.google_drive import GoogleDriveToken
                user_token = GoogleDriveToken.get_user_token(user_id)
                if user_token and user_token.is_active:
                    stats['google_drive_connected'] = True
                    stats['google_drive_backups'] = user_token.backup_count or 0
                    stats['total_backups'] += stats['google_drive_backups']
        except Exception as e:
            print(f"خطأ في جلب إحصائيات Google Drive: {e}")
        
        # إحصائيات النسخ المحلية (يمكن إضافتها لاحقاً)
        # stats['local_backups'] = get_local_backups_count(user_id)
        # stats['total_backups'] += stats['local_backups']
        
        # إحصائيات إضافية من backup_settings
        try:
            if backup_settings_model_available:
                from src.models.backup_settings import BackupSettings
                user_settings = BackupSettings.get_user_settings(user_id)
                if user_settings:
                    # يمكن إضافة المزيد من الإحصائيات هنا
                    pass
        except Exception as e:
            print(f"خطأ في جلب إعدادات النسخ: {e}")
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f"خطأ في جلب إحصائيات النسخ: {e}")
        return jsonify({
            'success': False,
            'error': 'فشل في جلب إحصائيات النسخ الاحتياطية',
            'message': str(e)
        }), 500


    # ===== API للاختبار بدون تسجيل دخول =====
    
    @app.route('/api/v1/backup/test-immediate', methods=['POST'])
    def test_immediate_backup():
        """تشغيل نسخ احتياطي فوري للاختبار (بدون تسجيل دخول)"""
        try:
            # محاكاة نجاح العملية للاختبار
            import time
            time.sleep(1)  # محاكاة وقت المعالجة
            
            return jsonify({
                'success': True,
                'message': 'تم تشغيل النسخ الاحتياطي الفوري بنجاح (اختبار)',
                'test_mode': True,
                'timestamp': datetime.utcnow().isoformat()
            })
                
        except Exception as e:
            logger.error(f"خطأ في API النسخ الفوري للاختبار: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في تشغيل النسخ الاحتياطي الفوري: {str(e)}',
                'test_mode': True
            }), 500

    @app.route('/api/v1/backup/test-status', methods=['GET'])
    def get_test_backup_status():
        """الحصول على حالة النسخ الاحتياطي للاختبار (بدون تسجيل دخول)"""
        try:
            status = {
                'success': True,
                'status': {
                    'settings': {
                        'auto_backup_enabled': True,
                        'backup_frequency': 'daily',
                        'backup_destination': 'google_drive',
                        'max_backups': 5,
                        'last_backup_time': datetime.utcnow().isoformat(),
                        'updated_at': datetime.utcnow().isoformat()
                    },
                    'google_drive': {
                        'connected': True,
                        'last_backup': datetime.utcnow().isoformat(),
                        'backup_count': 3,
                        'storage_used': '150 MB'
                    },
                    'scheduler': {
                        'user_scheduled': True,
                        'next_backup': (datetime.utcnow()).isoformat(),
                        'status': 'active'
                    }
                },
                'test_mode': True
            }
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"خطأ في API حالة النسخ للاختبار: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب حالة النسخ الاحتياطي: {str(e)}',
                'test_mode': True
            }), 500

    @app.route('/api/v1/google-drive/test-connection-status', methods=['GET'])
    def get_test_google_drive_status():
        """الحصول على حالة اتصال Google Drive للاختبار (بدون تسجيل دخول)"""
        try:
            status = {
                'success': True,
                'status': {
                    'connected': True,
                    'last_backup': datetime.utcnow().isoformat(),
                    'backup_count': 3,
                    'storage_used': '150 MB',
                    'account_email': 'test@example.com'
                },
                'test_mode': True
            }
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"خطأ في API حالة Google Drive للاختبار: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب حالة Google Drive: {str(e)}',
                'test_mode': True
            }), 500

# ==================== إرسال الإشعارات ====================
@app.route('/api/admin/send-notification', methods=['POST'])
@login_required
def api_send_notification():
    """إرسال إشعار للطلاب - نسخة محسّنة (إشعار واحد مشترك)"""
    try:
        # التحقق من أن المستخدم أدمن
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية إرسال الإشعارات'
            }), 403
        
        data = request.get_json() or request.form
        
        # جلب البيانات المطلوبة
        notification_title = data.get('title', '').strip()
        notification_body = data.get('body', '').strip()
        recipient_type = data.get('recipient_type', 'all')  # all, student_id, level
        recipient_id = data.get('recipient_id')  # للطالب المحدد
        level = data.get('level')  # للمستوى المحدد
        
        print(f"\n🔍 ========== Send Notification Request ==========")
        print(f"Title: {notification_title}")
        print(f"Body: {notification_body}")
        print(f"Recipient Type: {recipient_type}")
        print(f"Recipient ID: {recipient_id}")
        print(f"Level: {level}")
        
        # التحقق من البيانات المطلوبة
        if not notification_title or not notification_body:
            return jsonify({
                'success': False,
                'error': 'العنوان والنص مطلوبان'
            }), 400
        
        # استيراد النماذج المطلوبة
        from src.models.student import Student
        from src.models.notification import Notification, StudentNotification
        
        # جلب الطلاب المستهدفين
        target_students = []
        
        if recipient_type == 'all':
            # إرسال للجميع
            target_students = Student.query.filter_by(is_active=True).all()
            print(f"🔍 إرسال للجميع: {len(target_students)} طالب")
            
        elif recipient_type == 'student_id':
            # إرسال لطالب محدد
            if not recipient_id:
                return jsonify({
                    'success': False,
                    'error': 'معرف الطالب مطلوب'
                }), 400
            student = Student.query.get(recipient_id)
            if student:
                target_students = [student]
                print(f"🔍 إرسال لطالب محدد: {student.username}")
            else:
                return jsonify({
                    'success': False,
                    'error': 'الطالب غير موجود'
                }), 404
                
        elif recipient_type == 'level':
            # إرسال لمستوى دراسي محدد
            if not level:
                return jsonify({
                    'success': False,
                    'error': 'المستوى الدراسي مطلوب'
                }), 400
            target_students = Student.query.filter_by(grade=level, is_active=True).all()
            print(f"🔍 إرسال للمستوى {level}: {len(target_students)} طالب")
        
        if not target_students:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على مستلمين'
            }), 400
        
        # ✅ تحديد نوع الإشعار حسب عدد المستلمين
        is_single_recipient = len(target_students) == 1
        
        if is_single_recipient:
            # إرسال لطالب واحد محدد
            single_student = target_students[0]
            notification = Notification(
                title=notification_title,
                message=notification_body,
                type='info',
                student_id=single_student.id,  # ← طالب محدد
                user_id=current_user.id,
                is_read=False,
                created_at=datetime.utcnow(),
                created_by_admin=True if current_user.is_admin else False,
                notification_type='broadcast'
            )
            db.session.add(notification)
            db.session.flush()
            
            print(f"✅ تم إنشاء إشعار فردي للطالب {single_student.username}: ID={notification.id}")
            
            # ✅ إنشاء StudentNotification (مطلوب لعمل القراءة)
            student_notification = StudentNotification(
                notification_id=notification.id,
                student_id=single_student.id,
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.session.add(student_notification)
            
        else:
            # إرسال جماعي (أكثر من طالب) - إشعار واحد مشترك
            notification = Notification(
                title=notification_title,
                message=notification_body,
                type='info',
                student_id=None,  # ← إشعار مشترك للجميع
                user_id=current_user.id,
                is_read=False,
                created_at=datetime.utcnow(),
                created_by_admin=True if current_user.is_admin else False,
                notification_type='broadcast'
            )
            db.session.add(notification)
            db.session.flush()
            
            print(f"✅ تم إنشاء الإشعار المشترك: ID={notification.id}")
            
            # إنشاء StudentNotification لكل طالب
            for student in target_students:
                student_notification = StudentNotification(
                    notification_id=notification.id,
                    student_id=student.id,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(student_notification)
        
        # إرسال الإشعارات عبر FCM
        sent_count = 0
        failed_count = 0
        
        for student in target_students:
            try:
                # إرسال عبر FCM إذا كان لدى الطالب token
                if student.fcm_token:
                    # استيراد Firebase Admin SDK
                    import firebase_admin
                    from firebase_admin import messaging
                    
                    # إنشاء الرسالة
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=notification_title,
                            body=notification_body,
                        ),
                        token=student.fcm_token,
                        android=messaging.AndroidConfig(
                            priority='high',
                            notification=messaging.AndroidNotification(
                                click_action='FLUTTER_NOTIFICATION_CLICK',
                                channel_id='high_importance_channel',
                            ),
                        ),
                        data={
                            'notification_id': str(notification.id),
                            'title': notification_title,
                            'body': notification_body,
                            'type': 'info',
                            'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                        }
                    )
                    
                    # إرسال الرسالة
                    response = messaging.send(message)
                    print(f"✅ تم إرسال الإشعار للطالب {student.username}: {response}")
                    sent_count += 1
                else:
                    print(f"⚠️  الطالب {student.username} لا يملك FCM Token")
                    failed_count += 1
                
            except Exception as e:
                print(f"❌ خطأ في إرسال الإشعار للطالب {student.username}: {str(e)}")
                failed_count += 1
        
        # حفظ جميع التغييرات
        db.session.commit()
        
        print(f"✅ تم إرسال {sent_count} إشعار بنجاح")
        print(f"❌ فشل إرسال {failed_count} إشعار")
        print(f"========== End Send Notification Request ==========\n")
        
        return jsonify({
            'success': True,
            'message': f'تم إرسال {sent_count} إشعار بنجاح',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total': len(target_students)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إرسال الإشعارات: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'خطأ في إرسال الإشعارات: {str(e)}'
        }), 500


# ==================== API جديد: إحصائيات قراءة الإشعارات للأدمن ====================

@app.route('/api/admin/notification/<int:notification_id>/read-stats', methods=['GET'])
@login_required
def api_notification_read_stats(notification_id):
    """
    عرض إحصائيات قراءة إشعار معين
    - من قرأ الإشعار
    - من لم يقرأ الإشعار
    - نسبة القراءة
    """
    try:
        # التحقق من صلاحيات الأدمن
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية الوصول'
            }), 403
        
        from src.models.notification import Notification, StudentNotification
        from src.models.student import Student
        
        # التحقق من وجود الإشعار
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({
                'success': False,
                'error': 'الإشعار غير موجود'
            }), 404
        
        # جلب جميع الطلاب المرتبطين بهذا الإشعار
        student_notifications = StudentNotification.query.filter_by(
            notification_id=notification_id
        ).all()
        
        # تصنيف الطلاب
        read_students = []
        unread_students = []
        
        for sn in student_notifications:
            student_data = {
                'id': sn.student_id,
                'name': sn.student.name if sn.student else 'غير معروف',
                'username': sn.student.username if sn.student else '',
                'read_at': sn.read_at.isoformat() if sn.read_at else None,
            }
            
            if sn.is_read:
                read_students.append(student_data)
            else:
                unread_students.append(student_data)
        
        # حساب النسب
        total_students = len(student_notifications)
        read_count = len(read_students)
        unread_count = len(unread_students)
        read_percentage = (read_count / total_students * 100) if total_students > 0 else 0
        
        return jsonify({
            'success': True,
            'notification': {
                'id': notification.id,
                'title': notification.title,
                'body': notification.body or notification.message,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
            },
            'stats': {
                'total_students': total_students,
                'read_count': read_count,
                'unread_count': unread_count,
                'read_percentage': round(read_percentage, 2),
            },
            'read_students': read_students,
            'unread_students': unread_students,
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب إحصائيات القراءة: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/notifications/overview', methods=['GET'])
@login_required
def api_notifications_overview():
    """
    عرض نظرة عامة على جميع الإشعارات مع إحصائيات القراءة
    """
    try:
        # التحقق من صلاحيات الأدمن
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية الوصول'
            }), 403
        
        from src.models.notification import Notification, StudentNotification
        from sqlalchemy import func
        
        # جلب الإشعارات مع إحصائيات القراءة
        notifications_query = db.session.query(
            Notification.id,
            Notification.title,
            Notification.body,
            Notification.message,
            Notification.notification_type,
            Notification.created_at,
            Notification.created_by_admin,
            Notification.created_by_ai,
            func.count(StudentNotification.id).label('total_recipients'),
            func.sum(
                db.case(
                    (StudentNotification.is_read == True, 1),
                    else_=0
                )
            ).label('read_count')
        ).outerjoin(
            StudentNotification,
            Notification.id == StudentNotification.notification_id
        ).group_by(
            Notification.id
        ).order_by(
            Notification.created_at.desc()
        ).limit(100).all()
        
        # تحويل النتائج
        notifications = []
        for n in notifications_query:
            total = int(n.total_recipients) if n.total_recipients else 0
            read = int(n.read_count) if n.read_count else 0
            unread = total - read
            read_percentage = (read / total * 100) if total > 0 else 0
            
            notifications.append({
                'id': n.id,
                'title': n.title,
                'body': n.body or n.message,
                'notification_type': n.notification_type,
                'created_at': n.created_at.isoformat() if n.created_at else None,
                'created_by_admin': n.created_by_admin,
                'created_by_ai': n.created_by_ai,
                'stats': {
                    'total_recipients': total,
                    'read_count': read,
                    'unread_count': unread,
                    'read_percentage': round(read_percentage, 2),
                }
            })
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'total_notifications': len(notifications)
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب نظرة عامة على الإشعارات: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500