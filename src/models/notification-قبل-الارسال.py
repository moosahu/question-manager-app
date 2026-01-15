# src/models/notification.py

"""
نموذج الإشعارات - محدّث ليدعم AI والنظام القديم
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()


class Notification(db.Model):
    """نموذج الإشعارات العامة - محدّث"""

    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)

    # دعم الأعمدة القديمة والجديدة
    message = db.Column(db.Text, nullable=True)  # للتوافق مع الكود القديم
    body = db.Column(db.Text, nullable=True)     # العمود الجديد

    # النوع
    type = db.Column(db.String(50), default='info')               # للتوافق القديم
    notification_type = db.Column(db.String(50), default='info')  # الجديد

    # المستخدمين (القديم)
    student_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)

    # دعم AI (جديد)
    created_by_admin = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, nullable=True)

    created_by_ai = db.Column(db.Boolean, default=False)
    ai_analysis_id = db.Column(
        db.Integer,
        db.ForeignKey('ai_analysis.id'),
        nullable=True
    )

    # بيانات إضافية
    data = db.Column(JSONB, default={})

    # حالة القراءة (القديم - للتوافق)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # العلاقات
    student_notifications = db.relationship(
        'StudentNotification',
        backref='notification',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    def __repr__(self):
        return f"<Notification id={self.id} title={self.title!r}>"

    @property
    def content(self):
        """الحصول على المحتوى - يدعم القديم والجديد"""
        return self.body or self.message or ''

    @content.setter
    def content(self, value):
        """تعيين المحتوى - يحدث القديم والجديد"""
        self.body = value
        self.message = value

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'body': self.content,
            'message': self.content,  # للتوافق
            'notification_type': self.notification_type or self.type,
            'type': self.type,  # للتوافق
            'created_by_admin': self.created_by_admin,
            'created_by_ai': self.created_by_ai,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'data': self.data or {},
        }

    def mark_as_read(self):
        """تعليم الإشعار كمقروء - للتوافق مع الكود القديم"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()

    @staticmethod
    def create_notification(
        title,
        body,
        notification_type='info',
        created_by_admin=False,
        created_by_ai=False,
        data=None,
        admin_id=None,
        ai_analysis_id=None,
    ):
        """إنشاء إشعار جديد"""
        notification = Notification(
            title=title,
            body=body,
            message=body,  # للتوافق
            notification_type=notification_type,
            type=notification_type,  # للتوافق
            created_by_admin=created_by_admin,
            created_by_ai=created_by_ai,
            data=data or {},
            admin_id=admin_id,
            ai_analysis_id=ai_analysis_id,
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @staticmethod
    def get_unread_count(user_id=None, student_id=None):
        """الحصول على عدد الإشعارات غير المقروءة - للتوافق"""
        query = Notification.query.filter_by(is_read=False)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if student_id:
            query = query.filter_by(student_id=student_id)
        return query.count()

    @staticmethod
    def get_recent_notifications(user_id=None, student_id=None, limit=10):
        """الحصول على الإشعارات الحديثة - للتوافق"""
        query = Notification.query.order_by(Notification.created_at.desc())
        if user_id:
            query = query.filter_by(user_id=user_id)
        if student_id:
            query = query.filter_by(student_id=student_id)
        return query.limit(limit).all()

    @staticmethod
    def mark_all_as_read(user_id=None, student_id=None):
        """تحديد جميع الإشعارات كمقروءة - للتوافق"""
        query = Notification.query.filter_by(is_read=False)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if student_id:
            query = query.filter_by(student_id=student_id)

        notifications = query.all()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
        db.session.commit()
        return len(notifications)


class StudentNotification(db.Model):
    """نموذج ربط الإشعارات بالطلاب - جديد"""

    __tablename__ = 'student_notifications'

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(
        db.Integer,
        db.ForeignKey('notifications.id'),
        nullable=False,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id'),
        nullable=False,
    )

    # حالة القراءة
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    # حالة الإرسال عبر FCM
    fcm_sent = db.Column(db.Boolean, default=False)
    fcm_sent_at = db.Column(db.DateTime, nullable=True)
    fcm_success = db.Column(db.Boolean, nullable=True)

    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # العلاقات
    student = db.relationship(
        'Student',
        backref=db.backref('notifications', lazy='dynamic'),
    )

    # القيود
    __table_args__ = (
        db.UniqueConstraint(
            'notification_id',
            'student_id',
            name='unique_notification_student',
        ),
    )

    def __repr__(self):
        return f"<StudentNotification id={self.id} notif={self.notification_id} student={self.student_id}>"

    def mark_as_read(self):
        """تعليم الإشعار كمقروء"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()

    def mark_fcm_sent(self, success=True):
        """تعليم الإشعار كمرسل عبر FCM"""
        self.fcm_sent = True
        self.fcm_sent_at = datetime.utcnow()
        self.fcm_success = success
        db.session.commit()

    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'notification_id': self.notification_id,
            'student_id': self.student_id,
            'title': self.notification.title if self.notification else None,
            'body': self.notification.content if self.notification else None,
            'notification_type': (
                self.notification.notification_type
                if self.notification else None
            ),
            'data': self.notification.data if self.notification else {},
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create_for_student(notification_id, student_id):
        """إنشاء ربط إشعار بطالب مع منع التكرار لنفس الإشعار"""
        try:
            # لو فيه نفس الإشعار لنفس الطالب لا نكرره
            existing = StudentNotification.query.filter_by(
                notification_id=notification_id,
                student_id=student_id,
            ).first()
            if existing:
                return existing

            student_notif = StudentNotification(
                notification_id=notification_id,
                student_id=student_id,
            )
            db.session.add(student_notif)
            db.session.commit()
            return student_notif
        except Exception as e:
            db.session.rollback()
            print(f"❌ خطأ في إنشاء StudentNotification: {e}")
            return None

    @staticmethod
    def create_for_students(notification_id, student_ids):
        """إنشاء ربط إشعار لعدة طلاب"""
        created = []
        for student_id in student_ids:
            sn = StudentNotification.create_for_student(
                notification_id,
                student_id,
            )
            if sn:
                created.append(sn)
        return created

    @staticmethod
    def get_student_notifications(student_id, unread_only=False, limit=50):
        """جلب إشعارات طالب"""
        query = StudentNotification.query.filter_by(student_id=student_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(
            StudentNotification.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def get_unread_count(student_id):
        """عدد الإشعارات غير المقروءة لطالب"""
        return StudentNotification.query.filter_by(
            student_id=student_id,
            is_read=False,
        ).count()

    @staticmethod
    def mark_all_as_read(student_id):
        """تعليم جميع إشعارات الطالب كمقروءة"""
        StudentNotification.query.filter_by(
            student_id=student_id,
            is_read=False,
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow(),
        })
        db.session.commit()
