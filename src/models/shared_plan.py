"""
SharedPlan Model - مشاركة التحاضير بين المعلمين
"""
from src.extensions import db
from datetime import datetime


class SharedPlan(db.Model):
    """جدول التحاضير المشتركة"""
    __tablename__ = 'shared_plans'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('lesson_plans.id', ondelete='CASCADE'), nullable=False)
    shared_by = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    visibility = db.Column(db.String(20), default='school')  # 'school' | 'public'
    avg_rating = db.Column(db.Float, default=0)
    use_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship('LessonPlan', backref=db.backref('shared', uselist=False, lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('shared_plans', lazy=True))

    def to_dict(self):
        plan_dict = self.plan.to_dict() if self.plan else {}
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'shared_by': self.shared_by,
            'teacher_name': self.teacher.name if self.teacher else None,
            'visibility': self.visibility,
            'avg_rating': self.avg_rating,
            'use_count': self.use_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'plan': plan_dict,
        }
