from src.extensions import db
from datetime import datetime


class GradeConfig(db.Model):
    __tablename__ = 'grade_config'

    id            = db.Column(db.Integer, primary_key=True)
    period_id     = db.Column(db.Integer, db.ForeignKey('grade_periods.id'), nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    max_score     = db.Column(db.Float, nullable=False, default=10)
    sort_order    = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    period = db.relationship('GradePeriod', backref='categories', lazy=True)

    def to_dict(self):
        return {
            'id':            self.id,
            'period_id':     self.period_id,
            'period_name':   self.period.period_name if self.period else None,
            'category_name': self.category_name,
            'max_score':     self.max_score,
            'sort_order':    self.sort_order,
            'is_active':     self.is_active,
        }
