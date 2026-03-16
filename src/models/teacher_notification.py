# src/models/teacher_notification.py
"""
TeacherNotification Model
إشعارات المعلمين — انضمام/مغادرة طالب، رسائل النظام، رسائل الأدمن
"""

from datetime import datetime
from src.extensions import db


class TeacherNotification(db.Model):
    """جدول إشعارات المعلم"""
    __tablename__ = 'teacher_notifications'

    id         = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey('teachers.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    title      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    type       = db.Column(db.String(50), default='system', nullable=False)
    # القيم المتوقعة: student_joined | student_left | system
    is_read    = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship (اختياري — للقراءة فقط، لا يُستخدم في الكتابة)
    teacher = db.relationship('Teacher', backref=db.backref('notifications', lazy='dynamic'))

    def __repr__(self):
        return f'<TeacherNotification id={self.id} teacher={self.teacher_id} type={self.type}>'

    # ------------------------------------------------------------------ #
    # to_dict
    # ------------------------------------------------------------------ #

    def to_dict(self):
        """تحويل الإشعار إلى قاموس للـ API"""
        return {
            'id':         self.id,
            'teacher_id': self.teacher_id,
            'title':      self.title,
            'message':    self.message,
            'type':       self.type,
            'is_read':    self.is_read,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
        }

    # ------------------------------------------------------------------ #
    # create helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def create(teacher_id, title, message, type='system'):
        """
        دالة مساعدة لإنشاء إشعار وحفظه في قاعدة البيانات.
        تُعيد الكائن المُنشأ، أو None عند الفشل.
        """
        try:
            notif = TeacherNotification(
                teacher_id=teacher_id,
                title=title,
                message=message,
                type=type,
            )
            db.session.add(notif)
            db.session.commit()
            return notif
        except Exception as e:
            db.session.rollback()
            print(f'[TeacherNotification.create] Error: {e}')
            return None
