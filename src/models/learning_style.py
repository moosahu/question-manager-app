# src/models/learning_style.py
"""أنماط التعلم (VARK) — استبيان يحدد نمط تعلم الطالب: بصري/سمعي/قرائي-كتابي/حركي"""
from datetime import datetime

try:
    from src.extensions import db
except ImportError:  # pragma: no cover
    from extensions import db


class LearningStyleResult(db.Model):
    """نتيجة استبيان أنماط التعلم لطالب — سجل واحد لكل طالب (يُحدَّث عند إعادة الاستبيان)"""
    __tablename__ = 'learning_styles'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, unique=True)

    visual_score = db.Column(db.Integer, nullable=False, default=0)
    auditory_score = db.Column(db.Integer, nullable=False, default=0)
    reading_score = db.Column(db.Integer, nullable=False, default=0)
    kinesthetic_score = db.Column(db.Integer, nullable=False, default=0)
    dominant_style = db.Column(db.String(100), nullable=False, default='')  # مثال: "بصري" أو "بصري/حركي" (تعادل)

    answers = db.Column(db.JSON, nullable=True)  # [{question_id, option}] — للمراجعة لاحقاً
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('learning_style', uselist=False))

    def to_dict(self):
        total = (self.visual_score or 0) + (self.auditory_score or 0) + (self.reading_score or 0) + (self.kinesthetic_score or 0)
        def pct(n):
            return round((n or 0) / total * 100) if total else 0
        return {
            'id': self.id,
            'student_id': self.student_id,
            'visual_score': self.visual_score,
            'auditory_score': self.auditory_score,
            'reading_score': self.reading_score,
            'kinesthetic_score': self.kinesthetic_score,
            'visual_percent': pct(self.visual_score),
            'auditory_percent': pct(self.auditory_score),
            'reading_percent': pct(self.reading_score),
            'kinesthetic_percent': pct(self.kinesthetic_score),
            'dominant_style': self.dominant_style,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
        }
