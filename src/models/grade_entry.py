from src.extensions import db
from datetime import datetime


class GradeEntry(db.Model):
    __tablename__ = 'grade_entries'

    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id  = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('grade_config.id'), nullable=False)
    entry_label = db.Column(db.String(100), nullable=False)   # واجب 1، واجب 2، ...
    score       = db.Column(db.Float, nullable=False)         # 0.0 – 1.0 نسبة
    entry_date  = db.Column(db.Date, default=datetime.utcnow)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    student  = db.relationship('Student',     backref='grade_entries', lazy=True)
    teacher  = db.relationship('Teacher',     backref='grade_entries', lazy=True)
    category = db.relationship('GradeConfig', backref='entries',       lazy=True)

    def to_dict(self):
        return {
            'id':          self.id,
            'student_id':  self.student_id,
            'teacher_id':  self.teacher_id,
            'category_id': self.category_id,
            'entry_label': self.entry_label,
            'score':       self.score,
            'entry_date':  self.entry_date.isoformat() if self.entry_date else None,
        }
