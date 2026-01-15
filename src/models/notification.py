# src/models/notification.py
"""
Notification Model - محدث بدعم النظام التلقائي ومراقبة الرسائل
✅ إضافة حقول: is_automatic, status, sent_at
"""

from datetime import datetime
from src.extensions import db

class Notification(db.Model):
    """نموذج الإشعارات"""
    __tablename__ = 'notifications'
    
    # ===== الحقول الأساسية =====
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    content = db.Column(db.Text)  # alias لـ message
    
    # ===== معلومات المستخدم =====
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    
    # ===== نوع الإشعار =====
    type = db.Column(
        db.String(50), 
        default='info',  # info, success, warning, error, admin_alert
        nullable=False
    )
    
    # ===== حالة القراءة =====
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # ===== 🆕 حقول جديدة للنظام التلقائي =====
    
    # هل الرسالة من النظام التلقائي؟
    is_automatic = db.Column(db.Boolean, default=False, nullable=False)
    
    # حالة الإرسال (pending, delivered, failed)
    status = db.Column(
        db.String(20), 
        default='pending',
        nullable=False
    )
    
    # تاريخ الإرسال الفعلي
    sent_at = db.Column(db.DateTime, nullable=True)
    
    # ===== التواريخ =====
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ===== العلاقات =====
    user = db.relationship('User', backref='notifications', foreign_keys=[user_id])
    student = db.relationship('Student', backref='student_notifications', foreign_keys=[student_id])
    
    # علاقة many-to-many مع الطلاب
    student_notifications = db.relationship(
        'StudentNotification', 
        backref='notification', 
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
    
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
            return False
        except Exception as e:
            db.session.rollback()
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
            'message': self.message or self.content,
            'content': self.content or self.message,
            'type': self.type,
            'user_id': self.user_id,
            'student_id': self.student_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            # 🆕 حقول جديدة
            'is_automatic': self.is_automatic,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            # التواريخ
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
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
            print(f"Error getting all notifications: {e}")
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
            print(f"Error getting recent notifications: {e}")
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
        """
        جلب الرسائل التلقائية
        
        Args:
            period: 'today', 'week', 'month', None (all)
            limit: عدد النتائج
        """
        try:
            query = Notification.query.filter_by(is_automatic=True)
            
            # تصفية حسب الفترة
            if period == 'today':
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
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
            print(f"Error getting automatic messages: {e}")
            return []
    
    @staticmethod
    def get_messaging_stats(period=None):
        """
        إحصائيات الإرسال
        
        Returns:
            dict: {total_sent, delivered, failed, pending}
        """
        try:
            query = Notification.query
            
            # تصفية حسب الفترة
            if period == 'today':
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
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
    """
    جدول الربط بين الطلاب والإشعارات (Many-to-Many)
    يسمح بإرسال إشعار واحد لعدة طلاب
    """
    __tablename__ = 'student_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # العلاقات
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id'), nullable=False)
    
    # حالة القراءة لكل طالب
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # العلاقات
    student = db.relationship('Student', backref='notifications_link')
    
    def __repr__(self):
        return f'<StudentNotification student_id={self.student_id} notification_id={self.notification_id}>'
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء لهذا الطالب"""
        try:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False
    
    @staticmethod
    def get_student_notifications(student_id, unread_only=False, limit=50):
        """جلب إشعارات طالب معين"""
        try:
            query = StudentNotification.query.filter_by(student_id=student_id)
            
            if unread_only:
                query = query.filter_by(is_read=False)
            
            # الترتيب حسب تاريخ الإنشاء
            query = query.join(Notification).order_by(
                Notification.created_at.desc()
            )
            
            return query.limit(limit).all()
            
        except Exception as e:
            print(f"Error getting student notifications: {e}")
            return []
