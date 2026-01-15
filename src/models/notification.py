# src/models/notification.py
"""
Notification Model - الإصدار النهائي المتوافق 100%
✅ بدون content
✅ بدون relationships
✅ بدون updated_at (إذا لم يكن موجود)
"""

from datetime import datetime
from src.extensions import db


class Notification(db.Model):
    """نموذج الإشعارات - متوافق مع قاعدة البيانات الحالية"""
    __tablename__ = 'notifications'
    
    # ===== الحقول الأساسية =====
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)
    body = db.Column(db.Text, nullable=True)
    
    # ===== معلومات المستخدم =====
    user_id = db.Column(db.Integer, nullable=True)
    student_id = db.Column(db.Integer, nullable=True)
    
    # ===== نوع الإشعار =====
    type = db.Column(db.String(50), default='info', nullable=False)
    notification_type = db.Column(db.String(50), nullable=True)
    
    # ===== حالة القراءة =====
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # ===== حقول إضافية =====
    session_id = db.Column(db.String(255), nullable=True)
    icon = db.Column(db.String(50), default='bell', nullable=True)
    last_viewed_at = db.Column(db.DateTime, nullable=True)
    view_count = db.Column(db.Integer, default=0, nullable=True)
    data = db.Column(db.JSON, nullable=True)
    
    # ===== حقول الأدمن =====
    created_by_admin = db.Column(db.Boolean, default=False, nullable=True)
    admin_id = db.Column(db.Integer, nullable=True)
    
    # ===== حقول AI =====
    ai_analysis_id = db.Column(db.Integer, nullable=True)
    created_by_ai = db.Column(db.Boolean, default=False, nullable=True)
    
    # ===== 🆕 حقول النظام التلقائي (الجديدة) =====
    is_automatic = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    # ===== التواريخ =====
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # updated_at - فقط إذا كان موجود في قاعدة بياناتك
    # updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
    
    # ===== Property للحصول على المحتوى =====
    
    @property
    def content(self):
        """Property لقراءة المحتوى من message أو body"""
        return self.message or self.body
    
    @content.setter
    def content(self, value):
        """Property لتعيين المحتوى إلى message"""
        self.message = value
    
    # ===== Methods للقراءة =====
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء"""
        try:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error marking notification as read: {e}")
            return False
    
    def mark_as_unread(self):
        """تحديد الإشعار كغير مقروء"""
        try:
            self.is_read = False
            self.read_at = None
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error marking notification as unread: {e}")
            return False
    
    # ===== 🆕 Methods للنظام التلقائي =====
    
    def mark_as_sent(self):
        """تحديد الرسالة كمُرسلة"""
        try:
            self.status = 'delivered'
            self.sent_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error marking notification as sent: {e}")
            return False
    
    def mark_as_failed(self):
        """تحديد الرسالة كفاشلة"""
        try:
            self.status = 'failed'
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error marking notification as failed: {e}")
            return False
    
    # ===== Methods للحذف =====
    
    def delete(self):
        """حذف الإشعار"""
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting notification: {e}")
            return False
    
    # ===== Methods للتحويل =====
    
    def to_dict(self):
        """تحويل الإشعار إلى قاموس"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'content': self.content,  # Property
            'body': self.body,
            'type': self.type,
            'notification_type': self.notification_type,
            'user_id': self.user_id,
            'student_id': self.student_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'is_automatic': self.is_automatic,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'icon': self.icon,
            'view_count': self.view_count,
            'data': self.data,
        }
    
    # ===== Static Methods =====
    
    @staticmethod
    def get_all_notifications(limit=50):
        """جلب جميع الإشعارات"""
        try:
            return Notification.query.order_by(
                Notification.created_at.desc()
            ).limit(limit).all()
        except Exception as e:
            print(f"Error fetching notifications: {e}")
            return []
    
    @staticmethod
    def get_recent_notifications(student_id=None, limit=50):
        """جلب الإشعارات الحديثة"""
        try:
            query = Notification.query
            
            if student_id:
                query = query.filter(
                    (Notification.student_id == student_id) | 
                    (Notification.student_id == None)
                )
            
            return query.order_by(
                Notification.created_at.desc()
            ).limit(limit).all()
            
        except Exception as e:
            print(f"Error fetching recent notifications: {e}")
            return []
    
    @staticmethod
    def get_unread_count(user_id=None):
        """حساب عدد الإشعارات غير المقروءة"""
        try:
            query = Notification.query.filter_by(is_read=False)
            
            if user_id:
                query = query.filter(
                    (Notification.user_id == user_id) | 
                    (Notification.user_id == None)
                )
            
            return query.count()
        except Exception as e:
            print(f"Error counting unread notifications: {e}")
            return 0
    
    # ===== 🆕 Static Methods للنظام التلقائي =====
    
    @staticmethod
    def get_automatic_messages(period=None, limit=100):
        """جلب الرسائل التلقائية
        
        Args:
            period: 'today', 'week', 'month', أو None للكل
            limit: عدد الرسائل
        """
        try:
            query = Notification.query.filter_by(is_automatic=True)
            
            if period == 'today':
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(Notification.sent_at >= today_start)
            elif period == 'week':
                from datetime import timedelta
                week_start = datetime.utcnow() - timedelta(days=7)
                query = query.filter(Notification.sent_at >= week_start)
            elif period == 'month':
                from datetime import timedelta
                month_start = datetime.utcnow() - timedelta(days=30)
                query = query.filter(Notification.sent_at >= month_start)
            
            return query.order_by(
                Notification.sent_at.desc()
            ).limit(limit).all()
            
        except Exception as e:
            print(f"Error fetching automatic messages: {e}")
            return []
    
    @staticmethod
    def get_messaging_stats(period=None):
        """إحصائيات الإرسال
        
        Args:
            period: 'today', 'week', 'month', أو None للكل
            
        Returns:
            dict: {total_sent, delivered, failed, pending}
        """
        try:
            query = Notification.query
            
            if period == 'today':
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(Notification.sent_at >= today_start)
            elif period == 'week':
                from datetime import timedelta
                week_start = datetime.utcnow() - timedelta(days=7)
                query = query.filter(Notification.sent_at >= week_start)
            elif period == 'month':
                from datetime import timedelta
                month_start = datetime.utcnow() - timedelta(days=30)
                query = query.filter(Notification.sent_at >= month_start)
            
            total_sent = query.count()
            delivered = query.filter_by(status='delivered').count()
            failed = query.filter_by(status='failed').count()
            pending = query.filter_by(status='pending').count()
            
            return {
                'total_sent': total_sent,
                'delivered': delivered,
                'failed': failed,
                'pending': pending
            }
            
        except Exception as e:
            print(f"Error getting messaging stats: {e}")
            return {
                'total_sent': 0,
                'delivered': 0,
                'failed': 0,
                'pending': 0
            }


# ===== StudentNotification Model =====

class StudentNotification(db.Model):
    """جدول الربط بين الطلاب والإشعارات"""
    __tablename__ = 'student_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    notification_id = db.Column(db.Integer, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<StudentNotification student={self.student_id} notif={self.notification_id}>'
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء لهذا الطالب"""
        try:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error marking student notification as read: {e}")
            return False
    
    @staticmethod
    def get_student_notifications(student_id, unread_only=False, limit=50):
        """جلب إشعارات طالب معين"""
        try:
            query = StudentNotification.query.filter_by(student_id=student_id)
            
            if unread_only:
                query = query.filter_by(is_read=False)
            
            return query.order_by(
                StudentNotification.created_at.desc()
            ).limit(limit).all()
            
        except Exception as e:
            print(f"Error fetching student notifications: {e}")
            return []
