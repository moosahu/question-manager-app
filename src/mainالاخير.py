import os
from flask import Flask, render_template, redirect, url_for, flash, current_app, request, jsonify
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required, login_user
from flask_wtf.csrf import CSRFProtect
from src.extensions import db
from src.models.notification import Notification


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
                print(f"Warning: Could not calculate unread count: {e}")
                return {'unread_count': 0}
        return {'unread_count': 0}
    
    # تسجيل blueprint الإشعارات
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
            print("Warning: Could not import notifications blueprint. Notifications feature will be disabled.")
    
    # تسجيل blueprint الإعدادات إذا كان متاحاً
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
        """عرض صفحة الإشعارات المحسنة"""
        try:
            notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
            unread_count = sum(1 for n in notifications if not n.is_read)
            
            return render_template("notifications.html", 
                                 notifications=notifications, 
                                 unread_count=unread_count)
        except Exception as e:
            print(f"Error loading notifications page: {e}")
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
            
            return jsonify({'success': True, 'message': 'تم حذف الإشعار بنجاح'})
            
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting notification {notif_id}: {e}")
            return jsonify({'error': 'حدث خطأ في حذف الإشعار'}), 500

    # إضافة دالة مساعدة لإنشاء الإشعارات
    def create_notification(user_id, content):
        """إنشاء إشعار جديد للمستخدم"""
        try:
            notification = Notification(
                user_id=user_id,
                content=content,
                is_read=False
            )
            db.session.add(notification)
            db.session.commit()
            print(f"Created notification for user {user_id}: {content}")
            return notification
        except Exception as e:
            db.session.rollback()
            print(f"Error creating notification: {e}")
            return None

    # إضافة الدالة للتطبيق لاستخدامها في أماكن أخرى
    app.create_notification = create_notification

    return app

# Create the app instance for Gunicorn to find
app = create_app()

if __name__ == "__main__":
    # <<< Corrected indentation for the block below
    # Use 0.0.0.0 to be accessible externally if needed, port 5000 is common
    # Debug should be False in production
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True) # تفعيل وضع التصحيح مؤقتاً

