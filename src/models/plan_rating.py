"""
PlanRating Model - تقييم جودة التحاضير
"""
from src.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB


class PlanRating(db.Model):
    """جدول تقييمات التحاضير"""
    __tablename__ = 'plan_ratings'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('lesson_plans.id', ondelete='CASCADE'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    overall_rating = db.Column(db.Integer, nullable=False)  # 1-5
    section_ratings = db.Column(JSONB, default={})  # {objectives: 1-5, evaluation: 1-5, ...}
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('plan_id', 'teacher_id', name='unique_plan_teacher_rating'),
    )

    plan = db.relationship('LessonPlan', backref=db.backref('ratings', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('plan_ratings', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.name if self.teacher else None,
            'overall_rating': self.overall_rating,
            'section_ratings': self.section_ratings,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
