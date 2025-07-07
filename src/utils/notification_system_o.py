# نظام الإشعارات المركزي الشامل
# الموقع: src/utils/notification_system.py

from datetime import datetime
from flask import current_app
from flask_login import current_user
import logging

# استيراد النماذج والامتدادات
try:
    from src.extensions import db
    from src.models.notification_model import Notification
    from src.models.user import User
except ImportError:
    try:
        from extensions import db
        from models.notification_model import Notification
        from models.user import User
    except ImportError:
        print("Error: Could not import required modules for notification system")
        raise

logger = logging.getLogger(__name__)

class NotificationTypes:
    """أنواع الإشعارات المختلفة"""
    # إشعارات الأسئلة
    QUESTION_ADDED = "question_added"
    QUESTION_UPDATED = "question_updated"
    QUESTION_DELETED = "question_deleted"
    QUESTIONS_IMPORTED = "questions_imported"
    QUESTIONS_EXPORTED = "questions_exported"
    
    # إشعارات المستخدمين
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTERED = "user_registered"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    
    # إشعارات النظام
    SYSTEM_UPDATE = "system_update"
    SETTINGS_UPDATED = "settings_updated"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    
    # إشعارات المناهج
    COURSE_ADDED = "course_added"
    COURSE_UPDATED = "course_updated"
    COURSE_DELETED = "course_deleted"
    UNIT_ADDED = "unit_added"
    UNIT_UPDATED = "unit_updated"
    UNIT_DELETED = "unit_deleted"
    LESSON_ADDED = "lesson_added"
    LESSON_UPDATED = "lesson_updated"
    LESSON_DELETED = "lesson_deleted"

class NotificationPriority:
    """أولويات الإشعارات"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationSystem:
    """نظام الإشعارات المركزي"""
    
    @staticmethod
    def create_notification(user_id, content, notification_type=NotificationTypes.SYSTEM_UPDATE, 
                          priority=NotificationPriority.NORMAL, data=None):
        """إنشاء إشعار جديد"""
        try:
            notification = Notification(
                user_id=user_id,
                content=content,
                notification_type=notification_type,
                priority=priority,
                data=data,
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.session.add(notification)
            db.session.commit()
            
            logger.info(f"Created notification for user {user_id}: {content}")
            return notification
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating notification: {e}")
            return None
    
    @staticmethod
    def create_notification_for_all_users(content, notification_type=NotificationTypes.SYSTEM_UPDATE,
                                        priority=NotificationPriority.NORMAL, exclude_user_id=None):
        """إنشاء إشعار لجميع المستخدمين"""
        try:
            users_query = User.query
            if exclude_user_id:
                users_query = users_query.filter(User.id != exclude_user_id)
            
            users = users_query.all()
            notifications_created = 0
            
            for user in users:
                notification = Notification(
                    user_id=user.id,
                    content=content,
                    notification_type=notification_type,
                    priority=priority,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(notification)
                notifications_created += 1
            
            db.session.commit()
            logger.info(f"Created {notifications_created} notifications for all users: {content}")
            return notifications_created
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating notifications for all users: {e}")
            return 0
    
    @staticmethod
    def create_notification_for_admins(content, notification_type=NotificationTypes.SYSTEM_UPDATE,
                                     priority=NotificationPriority.HIGH):
        """إنشاء إشعار للمديرين فقط"""
        try:
            admin_users = User.query.filter_by(is_admin=True).all()
            notifications_created = 0
            
            for admin in admin_users:
                notification = Notification(
                    user_id=admin.id,
                    content=content,
                    notification_type=notification_type,
                    priority=priority,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(notification)
                notifications_created += 1
            
            db.session.commit()
            logger.info(f"Created {notifications_created} notifications for admins: {content}")
            return notifications_created
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating notifications for admins: {e}")
            return 0

# دوال مخصصة لكل نوع من العمليات

class QuestionNotifications:
    """إشعارات خاصة بالأسئلة"""
    
    @staticmethod
    def notify_question_added(lesson_name, question_text=None, user_id=None):
        """إشعار بإضافة سؤال جديد"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم إضافة سؤال جديد في درس '{lesson_name}'"
        if question_text:
            content += f": {question_text[:50]}..."
        
        # إشعار للمستخدم الحالي
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.QUESTION_ADDED,
                priority=NotificationPriority.NORMAL
            )
        
        # إشعار للمديرين
        admin_content = f"قام المستخدم بإضافة سؤال جديد في درس '{lesson_name}'"
        NotificationSystem.create_notification_for_admins(
            content=admin_content,
            notification_type=NotificationTypes.QUESTION_ADDED,
            priority=NotificationPriority.LOW
        )
    
    @staticmethod
    def notify_question_updated(lesson_name, question_text=None, user_id=None):
        """إشعار بتحديث سؤال"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم تحديث سؤال في درس '{lesson_name}'"
        if question_text:
            content += f": {question_text[:50]}..."
        
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.QUESTION_UPDATED,
                priority=NotificationPriority.NORMAL
            )
    
    @staticmethod
    def notify_question_deleted(lesson_name, user_id=None):
        """إشعار بحذف سؤال"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم حذف سؤال من درس '{lesson_name}'"
        
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.QUESTION_DELETED,
                priority=NotificationPriority.NORMAL
            )
    
    @staticmethod
    def notify_questions_imported(count, lesson_name, user_id=None):
        """إشعار باستيراد أسئلة"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم استيراد {count} سؤال جديد في درس '{lesson_name}'"
        
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.QUESTIONS_IMPORTED,
                priority=NotificationPriority.HIGH
            )

class UserNotifications:
    """إشعارات خاصة بالمستخدمين"""
    
    @staticmethod
    def notify_user_login(username, user_id=None):
        """إشعار بتسجيل دخول مستخدم"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم تسجيل دخولك بنجاح - مرحباً {username}"
        
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.USER_LOGIN,
                priority=NotificationPriority.LOW
            )
    
    @staticmethod
    def notify_user_logout(username, user_id=None):
        """إشعار بتسجيل خروج مستخدم"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم تسجيل خروجك بنجاح - إلى اللقاء {username}"
        
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.USER_LOGOUT,
                priority=NotificationPriority.LOW
            )
    
    @staticmethod
    def notify_user_registered(username):
        """إشعار بتسجيل مستخدم جديد"""
        content = f"مرحباً بك في النظام {username}! تم إنشاء حسابك بنجاح"
        
        # إشعار للمستخدم الجديد
        new_user = User.query.filter_by(username=username).first()
        if new_user:
            NotificationSystem.create_notification(
                user_id=new_user.id,
                content=content,
                notification_type=NotificationTypes.USER_REGISTERED,
                priority=NotificationPriority.HIGH
            )
        
        # إشعار للمديرين
        admin_content = f"تم تسجيل مستخدم جديد: {username}"
        NotificationSystem.create_notification_for_admins(
            content=admin_content,
            notification_type=NotificationTypes.USER_REGISTERED,
            priority=NotificationPriority.NORMAL
        )

class SystemNotifications:
    """إشعارات خاصة بالنظام"""
    
    @staticmethod
    def notify_system_update(update_description):
        """إشعار بتحديث النظام"""
        content = f"تم تحديث النظام: {update_description}"
        
        NotificationSystem.create_notification_for_all_users(
            content=content,
            notification_type=NotificationTypes.SYSTEM_UPDATE,
            priority=NotificationPriority.HIGH
        )
    
    @staticmethod
    def notify_settings_updated(setting_name, user_id=None):
        """إشعار بتحديث الإعدادات"""
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        content = f"تم تحديث إعداد '{setting_name}' بنجاح"
        
        if user_id:
            NotificationSystem.create_notification(
                user_id=user_id,
                content=content,
                notification_type=NotificationTypes.SETTINGS_UPDATED,
                priority=NotificationPriority.NORMAL
            )
    
    @staticmethod
    def notify_backup_created():
        """إشعار بإنشاء نسخة احتياطية"""
        content = "تم إنشاء نسخة احتياطية من البيانات بنجاح"
        
        NotificationSystem.create_notification_for_admins(
            content=content,
            notification_type=NotificationTypes.BACKUP_CREATED,
            priority=NotificationPriority.NORMAL
        )

# دالة مساعدة للتكامل مع Flask
def init_notification_system(app):
    """تهيئة نظام الإشعارات مع التطبيق"""
    
    # إضافة دوال الإشعارات للتطبيق
    app.notify_question_added = QuestionNotifications.notify_question_added
    app.notify_question_updated = QuestionNotifications.notify_question_updated
    app.notify_question_deleted = QuestionNotifications.notify_question_deleted
    app.notify_questions_imported = QuestionNotifications.notify_questions_imported
    
    app.notify_user_login = UserNotifications.notify_user_login
    app.notify_user_logout = UserNotifications.notify_user_logout
    app.notify_user_registered = UserNotifications.notify_user_registered
    
    app.notify_system_update = SystemNotifications.notify_system_update
    app.notify_settings_updated = SystemNotifications.notify_settings_updated
    app.notify_backup_created = SystemNotifications.notify_backup_created
    
    # إضافة النظام المركزي
    app.notification_system = NotificationSystem
    
    logger.info("Notification system initialized successfully")

# دالة للاستخدام المباشر
def send_notification(user_id, content, notification_type=NotificationTypes.SYSTEM_UPDATE):
    """دالة مبسطة لإرسال إشعار"""
    return NotificationSystem.create_notification(user_id, content, notification_type)

