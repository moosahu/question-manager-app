"""
نموذج طلبات الربط المعلّقة — لما الأدمن يفعّل "ربط يدوي" لكوده الخاص
(عمود User.require_manual_link_approval)، دخول الطالب للكود ما يرتبط فوراً —
ينشئ طلب هنا بانتظار موافقة/رفض الأدمن. أكواد المعلمين ما تمر من هنا إطلاقاً،
تبقى تلقائية دايماً.
"""
from src.extensions import db
from datetime import datetime


class PendingLinkRequest(db.Model):
    """طلب ربط طالب بأدمن معلّق بانتظار الموافقة اليدوية"""
    __tablename__ = 'pending_link_requests'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending/approved/rejected
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', backref=db.backref('pending_link_requests', lazy='dynamic'))
    admin = db.relationship('User', backref=db.backref('pending_link_requests', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else None,
            'admin_id': self.admin_id,
            'status': self.status,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }
