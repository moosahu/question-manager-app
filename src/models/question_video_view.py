# src/models/question_video_view.py
# نموذج تتبع مشاهدات فيديو شرح الأسئلة

from datetime import datetime

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()


class QuestionVideoView(db.Model):
    """تتبع مشاهدة الطالب لفيديو شرح سؤال معين"""
    __tablename__ = 'question_video_views'

    id = db.Column(db.Integer, primary_key=True)

    # من شاهد وأي سؤال
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id',  ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.question_id', ondelete='CASCADE'), nullable=False, index=True)

    # متى ومقدار المشاهدة
    watched_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    watch_duration  = db.Column(db.Integer, default=0, nullable=False)   # ثواني شاهد فعلاً
    video_duration  = db.Column(db.Integer, default=0, nullable=False)   # طول الفيديو الكلي
    completed       = db.Column(db.Boolean,  default=False, nullable=False)  # شاهد 80%+
    view_count      = db.Column(db.Integer,  default=1, nullable=False)  # كم مرة فتح نفس الفيديو

    # علاقات
    student  = db.relationship('Student',  backref=db.backref('video_views', lazy='dynamic'))
    question = db.relationship('Question', backref=db.backref('video_views', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'question_id', name='uq_student_question_view'),
    )

    def __repr__(self):
        return f'<VideoView student={self.student_id} q={self.question_id} dur={self.watch_duration}s>'

    def to_dict(self):
        return {
            'id':             self.id,
            'student_id':     self.student_id,
            'question_id':    self.question_id,
            'watched_at':     self.watched_at.isoformat() if self.watched_at else None,
            'watch_duration': self.watch_duration,
            'video_duration': self.video_duration,
            'completed':      self.completed,
            'view_count':     self.view_count,
        }
