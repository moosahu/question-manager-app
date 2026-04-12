from src.extensions import db
from datetime import datetime


class StudentGradeRelease(db.Model):
    __tablename__ = 'student_grade_releases'

    id             = db.Column(db.Integer, primary_key=True)
    student_id     = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id     = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    admin_id       = db.Column(db.Integer, db.ForeignKey('user.id'),     nullable=True)
    period_id      = db.Column(db.Integer, db.ForeignKey('grade_periods.id'), nullable=False)
    release_type   = db.Column(db.String(20), nullable=False, default='both')
    custom_message = db.Column(db.Text, nullable=True)
    released_at    = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student',     backref='grade_releases', lazy=True)
    teacher = db.relationship('Teacher',     backref='grade_releases', lazy=True)
    period  = db.relationship('GradePeriod', backref='grade_releases', lazy=True)

    def to_dict(self):
        from datetime import timedelta
        return {
            'id':             self.id,
            'student_id':     self.student_id,
            'teacher_id':     self.teacher_id,
            'period_id':      self.period_id,
            'period_name':    self.period.period_name if self.period else None,
            'release_type':   self.release_type,
            'custom_message': self.custom_message or '',
            'released_at':    (self.released_at + timedelta(hours=3)).isoformat() if self.released_at else None,
        }
