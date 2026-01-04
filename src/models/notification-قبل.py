"""
نموذج قاعدة البيانات للإشعارات
"""

from datetime import datetime
from src.extensions import db

class Notification(db.Model):
    """نموذج الإشعارات في قاعدة البيانات"""
    
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, success, warning, error
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقة مع المستخدم
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
    
    def to_dict(self):
        """تحويل الإشعار إلى قاموس"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'user_id': self.user_id,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def get_unread_count(user_id=None):
        """الحصول على عدد الإشعارات غير المقروءة"""
        query = Notification.query.filter_by(is_read=False)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.count()
    
    @staticmethod
    def get_recent_notifications(user_id=None, limit=10):
        """الحصول على الإشعارات الحديثة"""
        query = Notification.query.order_by(Notification.created_at.desc())
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.limit(limit).all()
    
    @staticmethod
    def mark_all_as_read(user_id=None):
        """تحديد جميع الإشعارات كمقروءة"""
        query = Notification.query.filter_by(is_read=False)
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        notifications = query.all()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
        
        db.session.commit()
        return len(notifications)

