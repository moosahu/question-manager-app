import os
import logging
from flask import Flask, render_template, redirect, url_for, flash, current_app, request, jsonify, session
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required, login_user
from flask_wtf.csrf import CSRFProtect
from src.extensions import db
from src.models.notification import Notification
from datetime import datetime
import uuid

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغيرات لتتبع حالة الاستيراد
backup_scheduler_available = False
backup_apis_available = False
settings_available = False
google_drive_backend_available = False
google_drive_model_available = False
backup_settings_model_available = False
activity_available = False

# استيراد نظام جدولة النسخ الاحتياطي (الملف موجود في src/)
try:
    from backup_scheduler import (
        init_backup_scheduler, 
        start_backup_scheduler,
        get_scheduler_status,
        schedule_user_backup
    )
    backup_scheduler_available = True
    logger.info("✅ تم استيراد نظام الجدولة")
except ImportError:
    logger.warning("❌ Could not import backup_scheduler. Using fallback implementation.")
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
    
    # استيراد APIs النسخ الاحتياطي المحسنة (الملف موجود في src/)
    try:
        from backup_apis_enhanced import register_backup_apis
        backup_apis_available = True
        logger.info("✅ تم استيراد APIs النسخ الاحتياطي المحسنة")
    except ImportError:
        backup_apis_available = False
        logger.warning("Backup logic not available")
        
        # إنشاء دالة بديلة
        def register_backup_apis(app):
            @app.route('/api/backup/status')
            def backup_status_fallback():
                return jsonify({
                    'status': 'disabled',
                    'message': 'Backup APIs not available'
                })
            logger.info("Backup APIs fallback registered")
    
    # استيراد settings_bp (الملف موجود في src/routes/)
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
    
    # ✅ استيراد Google Drive Backend routes الصحيح (الملف موجود في src/routes/)
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
                @app.route('/google-drive-backend/status')
                def google_drive_backend_status_fallback():
                    return jsonify({
                        'status': 'disabled',
                        'message': 'Google Drive Backend not available'
                    })
                logger.info("Google Drive Backend routes fallback registered")
        
except ImportError:
    try:
        from routes.auth import auth_bp
        from routes.user import user_bp
        from routes.question import question_bp
        from routes.curriculum import curriculum_bp
        from routes.api import api_bp
        logger.info("✅ Main blueprints imported successfully (fallback)")
        
        # استيراد settings_bp مع معالجة الخطأ
        try:
            from routes.settings import settings_bp
            settings_available = True
        except ImportError:
            logger.warning("⚠️ Could not import settings_bp. Settings feature will be disabled.")
            settings_available = False
        
        # ✅ استيراد Google Drive Backend routes الصحيح مع معالجة الخطأ
        try:
            from routes.google_drive_backend_routes import register_google_drive_backend_routes
            google_drive_backend_available = True
        except ImportError:
            logger.warning("⚠️ Could not import google_drive_backend_routes. Google Drive Backend features will be disabled.")
            google_drive_backend_available = False
            
            # إنشاء دالة بديلة
            def register_google_drive_backend_routes(app):
                @app.route('/google-drive-backend/status')
                def google_drive_backend_status_fallback():
                    return jsonify({'status': 'disabled', 'message': 'Google Drive Backend not available'})
    except ImportError:
        logger.error("❌ Could not import blueprints from src.routes or routes.")
        raise

# Import User model AFTER defining db
try:
    from src.models.user import User
    # استيراد Google Drive Token model (الملف موجود في src/models/)
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
            logger.info("✅ Google APIs client library loaded successfully")
        except ImportError:
            logger.warning("⚠️ Could not import GoogleDriveToken. Google Drive token storage will be disabled.")
            google_drive_model_available = False
    
    # استيراد Backup Settings model (الملف موجود في src/models/)
    try:
        from src.models.backup_settings import BackupSettings
        backup_settings_model_available = True
        logger.info("✅ Database models imported successfully")
    except ImportError:
        try:
            from models.backup_settings import BackupSettings
            backup_settings_model_available = True
            logger.info("✅ Database models imported successfully")
        except ImportError:
            logger.warning("تحذير: لا يمكن استيراد وحدات النسخ الاحتياطي: No module named 'backup_settings'")
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
            logger.warning("⚠️ Could not import Activity. Activity tracking will be disabled.")
            activity_available = False
except ImportError:
    try:
        from models.user import User
        # استيراد Google Drive Token model
        try:
            from models.google_drive import GoogleDriveToken
            google_drive_model_available = True
        except ImportError:
            logger.warning("⚠️ Could not import GoogleDriveToken. Google Drive token storage will be disabled.")
            google_drive_model_available = False
        # استيراد Activity مع معالجة الخطأ
        try:
            from models.activity import Activity
            activity_available = True
        except ImportError:
            logger.warning("⚠️ Could not import Activity. Activity tracking will be disabled.")
            activity_available = False
    except ImportError:
        logger.error("❌ Could not import User model from src.models or models.")
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

    # ===== إضافة CORS Middleware =====
    @app.after_request
    def add_coop_header(response):
        """إضافة Cross-Origin-Opener-Policy header لحل مشاكل CORS"""
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
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
                logger.info("Admin user created.")
                
                # تسجيل نشاط إنشاء المستخدم الإداري إذا كان متاحاً
                if activity_available:
                    try:
                        Activity.log_system_activity("تم إنشاء حساب المستخدم الإداري")
                    except Exception as e:
                        logger.warning(f"Could not log activity: {e}")
        except Exception as e:
            logger.error(f"Error during database initialization or admin creation: {e}")
            db.session.rollback()

    # تهيئة جدولة النسخ الاحتياطي المحسنة
    if backup_scheduler_available:
        try:
            scheduler = init_backup_scheduler(app)
            app.backup_scheduler = scheduler
            logger.info("✅ تم تهيئة جدولة النسخ الاحتياطي")
            
            # بدء تشغيل الجدولة في thread منفصل (حل مشكلة before_first_request المهملة)
            import threading
            import time
            
            def start_scheduler_delayed():
                """بدء تشغيل الجدولة بعد تأخير قصير لضمان تهيئة التطبيق"""
                time.sleep(2)  # انتظار لضمان تهيئة التطبيق
                try:
                    if start_backup_scheduler():
                        logger.info("✅ تم بدء تشغيل جدولة النسخ الاحتياطي بنجاح")
                        # جدولة النسخ لجميع المستخدمين
                        scheduled_count = scheduler.schedule_all_users()
                        logger.info(f"📅 تم جدولة النسخ الاحتياطي لـ {scheduled_count} مستخدم")
                    else:
                        logger.warning("❌ فشل في بدء تشغيل جدولة النسخ الاحتياطي")
                except Exception as e:
                    logger.error(f"❌ خطأ في بدء تشغيل جدولة النسخ الاحتياطي: {e}")
            
            # تشغيل الجدولة في thread منفصل
            scheduler_thread = threading.Thread(target=start_scheduler_delayed, daemon=True)
            scheduler_thread.start()
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة جدولة النسخ الاحتياطي: {e}")
    else:
        logger.warning("⚠️ جدولة النسخ الاحتياطي غير متوفرة")

    # متغير لتتبع الـ blueprints المسجلة
    registered_blueprints = set()

    # Register blueprints مع تجنب التسجيل المكرر
    def safe_register_blueprint(blueprint, **kwargs):
        """تسجيل آمن للـ blueprint مع تجنب التكرار"""
        blueprint_name = kwargs.get('url_prefix', blueprint.name)
        if blueprint_name not in registered_blueprints:
            app.register_blueprint(blueprint, **kwargs)
            registered_blueprints.add(blueprint_name)
            return True
        else:
            logger.warning(f"Blueprint {blueprint_name} already registered, skipping...")
            return False

    # تسجيل الـ blueprints الأساسية
    safe_register_blueprint(auth_bp, url_prefix="/auth")
    safe_register_blueprint(user_bp, url_prefix="/user")
    safe_register_blueprint(question_bp, url_prefix="/questions")
    safe_register_blueprint(curriculum_bp, url_prefix="/curriculum")
    safe_register_blueprint(api_bp)
    
    # ✅ تسجيل Google Drive Backend routes إذا كان متاحاً (الاستيراد الصحيح)
    if google_drive_backend_available:
        try:
            register_google_drive_backend_routes(app)
            logger.info("🚀 تم تسجيل Google Drive Backend routes بنجاح")
            logger.info("📱 الوصول للتطبيق: /google-drive-backend/google-drive-dashboard")
            logger.info("⚙️ صفحة الإعدادات: /google-drive-backend/google-drive-settings")
            logger.info("☁️ مزامنة Google Drive متاحة")
        except Exception as e:
            logger.error(f"خطأ في تسجيل Google Drive Backend routes: {e}")
    
    # تسجيل APIs النسخ الاحتياطي المحسنة إذا كانت متاحة
    if backup_apis_available:
        try:
            register_backup_apis(app)
            logger.info("Backup APIs registered successfully")
        except Exception as e:
            logger.warning(f"⚠️ Warning: Could not register Enhanced Backup APIs: {e}")
    
    # إضافة context processor لجعل unread_count متاح في جميع القوالب
    @app.context_processor
    def inject_unread_count():
        """حقن عدد الإشعارات غير المقروءة في جميع القوالب"""
        if current_user.is_authenticated:
            try:
                unread_count = Notification.query.filter_by(
                    user_id=current_user.id, 
                    is_read=False
                ).count()
                return {'unread_count': unread_count}
            except Exception as e:
                logger.warning(f"Could not calculate unread count: {e}")
                return {'unread_count': 0}
        return {'unread_count': 0}
    
    # تسجيل blueprint الإشعارات
    try:
        from src.routes.notifications import notifications_bp
        if safe_register_blueprint(notifications_bp, url_prefix="/notifications"):
            logger.info("Notifications blueprint registered successfully.")
    except ImportError:
        try:
            from routes.notifications import notifications_bp
            if safe_register_blueprint(notifications_bp, url_prefix="/notifications"):
                logger.info("Notifications blueprint registered successfully.")
        except ImportError:
            logger.warning("Warning: No app context available for notifications init")
    
    # تسجيل blueprint الإعدادات إذا كان متاحاً
    if settings_available:
        try:
            if safe_register_blueprint(settings_bp, url_prefix="/settings"):
                logger.info("Settings blueprint registered successfully.")
        except Exception as e:
            logger.warning(f"Could not register settings blueprint: {e}")

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
        # جلب الإحصائيات من قاعدة البيانات
        try:
            from src.models.question import Question
            from src.models.curriculum import Course, Unit, Lesson
        except ImportError:
            try:
                from models.question import Question
                from models.curriculum import Course, Unit, Lesson
            except ImportError:
                logger.error("Could not import models for statistics.")
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
                logger.warning(f"Could not get recent activities: {e}")
        
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
            logger.warning(f"Failed to load notifications: {e}")
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
        logger.error(f"Internal Server Error: {e}")
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
        """عرض صفحة الإشعارات المحسنة"""
        try:
            notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
            unread_count = sum(1 for n in notifications if not n.is_read)
            
            return render_template("notifications.html", 
                                 notifications=notifications, 
                                 unread_count=unread_count)
        except Exception as e:
            logger.error(f"Error loading notifications page: {e}")
            flash('حدث خطأ في تحميل صفحة الإشعارات', 'error')
            return redirect(url_for('dashboard'))
    
    @app.route("/notifications/action", methods=["POST"])
    @login_required
    def bulk_notifications_action():
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
                        logger.warning(f"Could not log delete activity: {e}")
            else:
                flash("إجراء غير صحيح.", 'error')

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in bulk notifications action: {e}")
            flash('حدث خطأ في تنفيذ الإجراء. يرجى المحاولة مرة أخرى.', 'error')

        return redirect(url_for("view_notifications"))

    # إضافة مسار لتحديد إشعار واحد كمقروء
    @app.route("/notifications/<int:notif_id>/mark-read", methods=["POST"])
    @login_required
    def mark_single_notification_read(notif_id):
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
            logger.error(f"Error marking notification {notif_id} as read: {e}")
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
                    logger.warning(f"Could not log delete activity: {e}")
            
            return jsonify({'success': True, 'message': 'تم حذف الإشعار بنجاح'})
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting notification {notif_id}: {e}")
            return jsonify({'error': 'حدث خطأ في حذف الإشعار'}), 500

    # ===== Google Drive APIs المفقودة =====
    
    @app.route('/api/v1/google-drive/connect', methods=['POST'])
    def connect_google_drive():
        """ربط Google Drive - محسن لحفظ Token في قاعدة البيانات"""
        try:
            logger.info('🔗 محاولة ربط Google Drive...')
            
            # التحقق من المستخدم أولاً
            if not current_user.is_authenticated:
                logger.warning('❌ المستخدم غير مسجل دخول')
                return jsonify({
                    'success': False,
                    'message': 'يجب تسجيل الدخول أولاً',
                    'connected': False
                }), 401
            
            # طباعة معلومات الطلب للتشخيص
            logger.info(f'📋 Content-Type: {request.content_type}')
            logger.info(f'📋 Method: {request.method}')
            logger.info(f'📋 User ID: {current_user.id}')
            
            # الحصول على بيانات Token من الطلب
            try:
                # محاولة قراءة البيانات بطرق مختلفة
                data = None
                
                if request.is_json:
                    data = request.get_json()
                    logger.info(f'📥 JSON data received: {bool(data)}')
                elif request.form:
                    data = request.form.to_dict()
                    logger.info(f'📥 Form data received: {bool(data)}')
                else:
                    # محاولة قراءة البيانات الخام
                    raw_data = request.get_data(as_text=True)
                    logger.info(f'📥 Raw data length: {len(raw_data)}')
                    if raw_data:
                        import json
                        data = json.loads(raw_data)
                
                if not data:
                    logger.warning('❌ لم يتم العثور على بيانات في الطلب')
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
                logger.error(f'❌ خطأ في قراءة البيانات: {json_error}')
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
            
            logger.info(f'📥 تم استلام - access_token: {bool(access_token)}, type: {token_type}, refresh: {bool(refresh_token)}')
            logger.info(f'📥 expires_in: {expires_in}, scope: {scope}')
            
            if not access_token:
                logger.warning('❌ access_token مفقود من البيانات')
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
                    
                    logger.info(f'💾 محاولة حفظ token في قاعدة البيانات للمستخدم {current_user.id}...')
                    
                    # حفظ الـ token في قاعدة البيانات
                    saved_token = GoogleDriveToken.create_or_update_token(current_user.id, token_data)
                    
                    if saved_token:
                        token_saved_in_db = True
                        logger.info(f'✅ تم حفظ token في قاعدة البيانات بنجاح للمستخدم {current_user.id}')
                        logger.info(f'📊 Token ID: {saved_token.id}, Active: {saved_token.is_active}')
                        
                        # التحقق من حفظ البيانات
                        verification_token = GoogleDriveToken.get_user_token(current_user.id)
                        if verification_token:
                            logger.info(f'✅ تم التحقق من حفظ Token - ID: {verification_token.id}')
                        else:
                            logger.warning(f'⚠️ فشل في التحقق من حفظ Token')
                    else:
                        logger.warning(f'❌ فشل في حفظ token في قاعدة البيانات للمستخدم {current_user.id}')
                    
                except Exception as db_error:
                    logger.error(f'❌ خطأ في حفظ token في قاعدة البيانات: {db_error}')
                    import traceback
                    traceback.print_exc()
                    # لا نفشل العملية إذا فشل حفظ قاعدة البيانات، لكن نسجل الخطأ
            else:
                logger.warning(f'⚠️ نموذج Google Drive غير متاح أو المستخدم غير مصادق عليه')
                logger.info(f'📊 google_drive_model_available: {google_drive_model_available}')
                logger.info(f'📊 current_user.is_authenticated: {current_user.is_authenticated}')
            
            # ثانياً: حفظ في الجلسة كنسخة احتياطية
            try:
                session['google_drive_connected'] = True
                session['google_drive_token'] = access_token
                if refresh_token:
                    session['google_drive_refresh_token'] = refresh_token
                session['google_drive_user_id'] = current_user.id
                session['google_drive_expires_in'] = expires_in
                session['google_drive_scope'] = scope
                
                logger.info('✅ تم حفظ token في الجلسة كنسخة احتياطية')
            except Exception as session_error:
                logger.warning(f'⚠️ خطأ في حفظ token في الجلسة: {session_error}')
            
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
            
            logger.info(f'📤 إرسال استجابة ناجحة: {response_data}')
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f'❌ خطأ عام في ربط Google Drive: {e}')
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
            logger.info('🔍 فحص حالة اتصال Google Drive...')
            
            # أولاً: فحص قاعدة البيانات (الأولوية الأولى)
            db_connected = False
            db_token = None
            db_token_info = {}
            
            if google_drive_model_available and current_user.is_authenticated:
                try:
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
                        logger.info(f'✅ تم العثور على token صالح في قاعدة البيانات للمستخدم {current_user.id}')
                        logger.info(f'📊 Token ID: {user_token.id}, Expires: {user_token.expiry}')
                        
                        # تحديث الجلسة من قاعدة البيانات
                        session['google_drive_connected'] = True
                        session['google_drive_token'] = user_token.access_token
                        if user_token.refresh_token:
                            session['google_drive_refresh_token'] = user_token.refresh_token
                        session['google_drive_user_id'] = current_user.id
                        
                        logger.info('🔄 تم تحديث الجلسة من قاعدة البيانات')
                    else:
                        logger.warning(f'❌ لا يوجد token صالح في قاعدة البيانات للمستخدم {current_user.id}')
                        if user_token:
                            logger.info(f'📊 Token موجود لكن غير صالح - ID: {user_token.id}, Active: {user_token.is_active}, Valid: {user_token.is_token_valid()}')
                except Exception as db_error:
                    logger.warning(f'⚠️ خطأ في فحص قاعدة البيانات: {db_error}')
            else:
                logger.warning(f'⚠️ نموذج Google Drive غير متاح أو المستخدم غير مصادق عليه')
                logger.info(f'📊 google_drive_model_available: {google_drive_model_available}')
                logger.info(f'📊 current_user.is_authenticated: {current_user.is_authenticated if current_user else False}')
            
            # ثانياً: فحص الجلسة كنسخة احتياطية
            session_connected = session.get('google_drive_connected', False)
            session_token = session.get('google_drive_token')
            session_user_id = session.get('google_drive_user_id')
            
            logger.info(f'📊 حالة الجلسة: connected={session_connected}, token={bool(session_token)}, user_id={session_user_id}')
            
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
            
            logger.info(f'🎯 الحالة النهائية: connected={final_connected}, storage={storage_method}')
            
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
            logger.error(f'❌ خطأ في فحص حالة Google Drive: {e}')
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'connected': False,
                'error': str(e),
                'error_type': 'server_error'
            }), 500

    # إضافة مسارات إضافية للـ APIs
    @app.route('/api/v1/backup-settings/save', methods=['POST'])
    def save_backup_settings():
        """حفظ إعدادات النسخ الاحتياطي"""
        try:
            data = request.get_json() or {}
            logger.info(f"📥 تم استلام بيانات حفظ الإعدادات: {data}")
            
            # التحقق من المستخدم
            if not current_user.is_authenticated:
                logger.warning("❌ المستخدم غير مسجل الدخول")
                return jsonify({
                    'success': False,
                    'message': 'يجب تسجيل الدخول أولاً'
                }), 401
            
            logger.info(f"👤 المستخدم المسجل: {current_user.id}")
            logger.info(f"🔧 backup_settings_model_available: {backup_settings_model_available}")
            
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
                    
                    logger.info(f"💾 محاولة حفظ الإعدادات: {settings_data}")
                    result = BackupSettings.update_user_settings(current_user.id, settings_data)
                    logger.info(f"✅ تم حفظ الإعدادات بنجاح: {result}")
                    
                    return jsonify({
                        'success': True,
                        'message': 'تم حفظ إعدادات النسخ الاحتياطي بنجاح',
                        'settings': settings_data
                    }), 200
                except Exception as db_error:
                    logger.error(f"❌ خطأ في قاعدة البيانات: {str(db_error)}")
                    # في حالة فشل قاعدة البيانات، احفظ في الجلسة
                    session['backup_settings'] = data
                    return jsonify({
                        'success': True,
                        'message': f'تم حفظ الإعدادات مؤقتاً (خطأ قاعدة البيانات: {str(db_error)})',
                        'settings': data
                    }), 200
            else:
                logger.warning("⚠️ نموذج BackupSettings غير متاح، الحفظ في الجلسة")
                # حفظ في الجلسة كبديل
                session['backup_settings'] = data
                return jsonify({
                    'success': True,
                    'message': 'تم حفظ إعدادات النسخ الاحتياطي مؤقتاً',
                    'settings': data
                }), 200
                
        except Exception as e:
            logger.error(f"❌ خطأ عام في API: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'خطأ في حفظ إعدادات النسخ الاحتياطي: {str(e)}'
            }), 500

    # إضافة مسار Google OAuth Configuration
    @app.route('/api/v1/google-oauth/config')
    def get_google_oauth_config():
        """إرسال إعدادات Google OAuth للفرونت إند"""
        try:
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

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

# إنشاء متغير app لـ gunicorn
app = create_app()

# إضافة route للإعدادات إذا لم يكن موجوداً
try:
    @app.route('/settings')
    @login_required
    def settings_page():
        """صفحة الإعدادات مع دعم Google Drive Integration"""
        return render_template('settings.html')
    logger.info("✅ Settings route registered successfully")
except Exception as e:
    logger.warning(f"⚠️ Settings route may already exist: {e}")

logger.info("🚀 Google Drive Integration with Redirect Flow initialized successfully")

# ✅ Alias إضافي لتسهيل الوصول من السكربت القديم
@app.route("/api/backup/status")
@login_required
def alias_backup_status():
    """Alias route للتوافق مع الـ frontend القديم"""
    try:
        # استدعاء الدالة الصحيحة من backup_apis_enhanced
        if backup_apis_available:
            from backup_apis_enhanced import get_backup_status
            return get_backup_status()
        else:
            return jsonify({
                'success': False,
                'error': 'خطأ في الحصول على حالة النسخ الاحتياطي',
                'error_type': 'backup_not_available'
            }), 500
    except Exception as e:
        logger.error(f"Error in alias backup status: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في الحصول على حالة النسخ الاحتياطي',
            'error_type': 'alias_route_error'
        }), 500

