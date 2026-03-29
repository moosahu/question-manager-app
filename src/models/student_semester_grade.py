# src/models/student_semester_grade.py
"""
نموذج درجات الفترة الفصلية للطالب
يخزن درجة الفترة الأولى/الثانية مع الرسالة التحفيزية التي ولّدها AI
"""

from datetime import datetime
from src.extensions import db


class StudentSemesterGrade(db.Model):
    __tablename__ = 'student_semester_grades'

    id             = db.Column(db.Integer, primary_key=True)
    student_id     = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    period         = db.Column(db.Integer, nullable=False)          # 1 أو 2
    grade          = db.Column(db.Float,   nullable=False)          # الدرجة
    max_grade      = db.Column(db.Float,   nullable=False)          # الدرجة الكاملة
    ai_message     = db.Column(db.Text,    nullable=True)           # الرسالة التحفيزية
    notification_sent = db.Column(db.Boolean, default=False, nullable=False)
    notified_at    = db.Column(db.DateTime, nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow, nullable=False)

    # العلاقة مع الطالب
    student = db.relationship('Student', backref=db.backref('semester_grades', lazy='dynamic'))

    def percentage(self) -> float:
        """النسبة المئوية"""
        if self.max_grade and self.max_grade > 0:
            return round((self.grade / self.max_grade) * 100, 1)
        return 0.0

    def to_dict(self) -> dict:
        return {
            'id':                self.id,
            'student_id':        self.student_id,
            'period':            self.period,
            'grade':             self.grade,
            'max_grade':         self.max_grade,
            'percentage':        self.percentage(),
            'ai_message':        self.ai_message,
            'notification_sent': self.notification_sent,
            'notified_at':       self.notified_at.isoformat() if self.notified_at else None,
            'created_at':        self.created_at.isoformat(),
        }

    @classmethod
    def get_student_grades(cls, student_id: int) -> list:
        """جلب كل درجات الطالب"""
        return cls.query.filter_by(student_id=student_id)\
                        .order_by(cls.period.asc()).all()

    @classmethod
    def get_grade(cls, student_id: int, period: int):
        """جلب درجة فترة محددة"""
        return cls.query.filter_by(student_id=student_id, period=period).first()
