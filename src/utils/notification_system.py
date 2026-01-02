"""
نظام الإشعارات المحسن - بدون أخطاء سياق التطبيق
يوفر إشعارات للمستخدمين والنظام مع حماية من أخطاء السياق
"""

from datetime import datetime
import traceback

class NotificationSystem:
    """النظام الأساسي للإشعارات مع حماية من أخطاء السياق"""
    
    @staticmethod
    def create_notification(title, message, notification_type="info", user_id=None):
        """
        إنشاء إشعار جديد مع حماية من أخطاء السياق
        
        Args:
            title (str): عنوان الإشعار
            message (str): محتوى الإشعار
            notification_type (str): نوع الإشعار (info, success, warning, error)
            user_id (int): معرف المستخدم (اختياري)
        """
        try:
            # التحقق من وجود سياق التطبيق
            from flask import has_app_context, current_app
            
            if not has_app_context():
                # إذا لم يكن هناك سياق تطبيق، نسجل فقط
                print(f"Notification (no app context): {title} - {message}")
                return True
            
            # محاولة استيراد نموذج الإشعارات
            try:
                from src.models.notification import Notification
                from src.extensions import db
            except ImportError:
                try:
                    from models.notification import Notification
                    from extensions import db
                except ImportError:
                    # إذا لم يتم العثور على النموذج، نسجل فقط
                    current_app.logger.info(f"Notification: {title} - {message}")
                    return True
            
            # إنشاء الإشعار
            notification = Notification(
                title=title,
                message=message,
                type=notification_type,
                user_id=user_id,
                created_at=datetime.utcnow(),
                is_read=False
            )
            
            db.session.add(notification)
            db.session.commit()
            
            current_app.logger.info(f"Notification created: {title}")
            return True
            
        except Exception as e:
            # معالجة الأخطاء بدون استخدام current_app إذا لم يكن متاحاً
            try:
                from flask import has_app_context, current_app
                if has_app_context():
                    current_app.logger.error(f"Error creating notification: {e}")
                    current_app.logger.error(traceback.format_exc())
                else:
                    print(f"Error creating notification (no app context): {e}")
            except:
                print(f"Error creating notification: {e}")
            return False

class UserNotifications:
    """إشعارات خاصة بالمستخدمين مع حماية السياق"""
    
    @staticmethod
    def notify_user_login(username, user_id=None):
        """إشعار تسجيل دخول المستخدم"""
        title = "تسجيل دخول"
        message = f"تم تسجيل دخول المستخدم: {username}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )
    
    @staticmethod
    def notify_user_login_2fa(username, user_id=None):
        """إشعار تسجيل دخول بالتحقق الثنائي"""
        title = "تسجيل دخول بالتحقق الثنائي"
        message = f"تم تسجيل دخول المستخدم بالتحقق الثنائي: {username}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )
    
    @staticmethod
    def notify_user_logout(username, user_id=None):
        """إشعار تسجيل خروج المستخدم"""
        title = "تسجيل خروج"
        message = f"تم تسجيل خروج المستخدم: {username}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="info",
            user_id=user_id
        )
    
    @staticmethod
    def notify_profile_updated(username, user_id=None):
        """إشعار تحديث الملف الشخصي"""
        title = "تحديث الملف الشخصي"
        message = f"تم تحديث الملف الشخصي للمستخدم: {username}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )
    
    @staticmethod
    def notify_password_changed(username, user_id=None):
        """إشعار تغيير كلمة المرور"""
        title = "تحديث كلمة المرور"
        message = f"تم تحديث كلمة المرور للمستخدم: {username}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )

class QuestionNotifications:
    """إشعارات خاصة بالأسئلة مع حماية السياق"""
    
    @staticmethod
    def notify_question_added(lesson_name, user_id=None):
        """إشعار إضافة سؤال جديد"""
        title = "إضافة سؤال جديد"
        message = f"تم إضافة سؤال جديد في درس: {lesson_name}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )
    
    @staticmethod
    def notify_question_updated(lesson_name, user_id=None):
        """إشعار تحديث سؤال"""
        title = "تحديث سؤال"
        message = f"تم تحديث سؤال في درس: {lesson_name}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="info",
            user_id=user_id
        )
    
    @staticmethod
    def notify_question_deleted(lesson_name, user_id=None):
        """إشعار حذف سؤال"""
        title = "حذف سؤال"
        message = f"تم حذف سؤال من درس: {lesson_name}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="warning",
            user_id=user_id
        )
    
    @staticmethod
    def notify_questions_imported(count, user_id=None):
        """إشعار استيراد أسئلة"""
        title = "استيراد أسئلة"
        message = f"تم استيراد {count} سؤال بنجاح"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )
    
    @staticmethod
    def notify_file_uploaded(filename, folder, user_id=None):
        """إشعار رفع ملف"""
        title = "رفع ملف"
        message = f"تم رفع ملف: {filename} في مجلد: {folder}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )

class SystemNotifications:
    """إشعارات النظام والأمان مع حماية السياق"""
    
    @staticmethod
    def notify_security_alert(message, user_id=None):
        """إشعار أمني"""
        title = "تنبيه أمني"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="error",
            user_id=user_id
        )
    
    @staticmethod
    def notify_settings_updated(setting_name, user_id=None):
        """إشعار تحديث الإعدادات"""
        title = "تحديث الإعدادات"
        message = f"تم تحديث: {setting_name}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="info",
            user_id=user_id
        )
    
    @staticmethod
    def notify_backup_completed(user_id=None):
        """إشعار اكتمال النسخ الاحتياطي"""
        title = "النسخ الاحتياطي"
        message = "تم إنشاء نسخة احتياطية بنجاح"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="success",
            user_id=user_id
        )
    
    @staticmethod
    def notify_system_update(version, user_id=None):
        """إشعار تحديث النظام"""
        title = "تحديث النظام"
        message = f"تم تحديث النظام إلى الإصدار: {version}"
        return NotificationSystem.create_notification(
            title=title,
            message=message,
            notification_type="info",
            user_id=user_id
        )

# دوال مساعدة للتوافق مع الإصدارات القديمة
def create_notification(title, message, notification_type="info", user_id=None):
    """دالة مساعدة لإنشاء إشعار مع حماية السياق"""
    return NotificationSystem.create_notification(title, message, notification_type, user_id)

def notify_user_action(action, username, user_id=None):
    """دالة مساعدة لإشعارات المستخدمين مع حماية السياق"""
    if action == "login":
        return UserNotifications.notify_user_login(username, user_id)
    elif action == "logout":
        return UserNotifications.notify_user_logout(username, user_id)
    elif action == "profile_update":
        return UserNotifications.notify_profile_updated(username, user_id)
    elif action == "password_change":
        return UserNotifications.notify_password_changed(username, user_id)
    else:
        return NotificationSystem.create_notification(
            title="إجراء مستخدم",
            message=f"تم تنفيذ إجراء: {action} للمستخدم: {username}",
            notification_type="info",
            user_id=user_id
        )

# دالة آمنة للتحقق من سياق التطبيق
def safe_app_context_check():
    """التحقق الآمن من وجود سياق التطبيق"""
    try:
        from flask import has_app_context
        return has_app_context()
    except:
        return False

