from src.extensions import db
from datetime import datetime


class GradePeriod(db.Model):
    __tablename__ = 'grade_periods'

    id              = db.Column(db.Integer, primary_key=True)
    period_name     = db.Column(db.String(100), nullable=False)
    sort_order      = db.Column(db.Integer, default=0)
    is_active       = db.Column(db.Boolean, default=True, nullable=False)
    semester_number = db.Column(db.Integer, nullable=True)   # 1 أو 2 — ربط مع النظام القديم
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':              self.id,
            'period_name':     self.period_name,
            'sort_order':      self.sort_order,
            'is_active':       self.is_active,
            'semester_number': self.semester_number,
        }
