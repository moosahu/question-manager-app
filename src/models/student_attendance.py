from src.extensions import db
from datetime import datetime


class StudentAttendance(db.Model):
    __tablename__ = 'student_attendance'

    id              = db.Column(db.Integer, primary_key=True)
    student_id      = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id      = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    admin_id        = db.Column(db.Integer, db.ForeignKey('user.id'),     nullable=True)
    attendance_date = db.Column(db.Date, nullable=False)
    period_number   = db.Column(db.Integer, nullable=False, default=1)
    status          = db.Column(db.String(20), nullable=False, default='present')
    notes           = db.Column(db.String(300), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'teacher_id', 'attendance_date', 'period_number',
                            name='uq_attendance'),
    )

    student = db.relationship('Student', backref='attendances', lazy=True)
    teacher = db.relationship('Teacher', backref='attendances', lazy=True)

    def to_dict(self):
        return {
            'id':              self.id,
            'student_id':      self.student_id,
            'teacher_id':      self.teacher_id,
            'attendance_date': self.attendance_date.isoformat() if self.attendance_date else None,
            'period_number':   self.period_number,
            'status':          self.status,
            'notes':           self.notes or '',
        }
