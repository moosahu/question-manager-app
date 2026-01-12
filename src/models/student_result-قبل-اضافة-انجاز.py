# src/models/student_result.py
# نموذج نتائج اختبارات الطلاب

from datetime import datetime

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()


class StudentResult(db.Model):
    """نموذج نتائج اختبارات الطلاب"""
    __tablename__ = 'student_results'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # نوع الاختبار: course, unit, lesson
    quiz_type = db.Column(db.String(20), nullable=False)
    
    # معرف المنهج/الوحدة/الدرس
    course_id = db.Column(db.Integer, nullable=True)
    unit_id = db.Column(db.Integer, nullable=True)
    lesson_id = db.Column(db.Integer, nullable=True)
    quiz_id = db.Column(db.Integer, nullable=True)
    
    # اسم الاختبار (للعرض)
    quiz_name = db.Column(db.String(200), nullable=False)
    
    # النتائج
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    correct_answers = db.Column(db.Integer, nullable=False, default=0)
    wrong_answers = db.Column(db.Integer, nullable=False, default=0)
    score_percentage = db.Column(db.Float, nullable=False, default=0.0)
    
    # الوقت المستغرق (بالثواني)
    time_spent = db.Column(db.Integer, nullable=True)
    
    # تاريخ الاختبار
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    student = db.relationship('Student', backref=db.backref('results', lazy='dynamic'))
    
    def __repr__(self):
        return f'<StudentResult {self.id} - {self.quiz_name}: {self.score_percentage}%>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'quiz_type': self.quiz_type,
            'quiz_name': self.quiz_name,
            'total_questions': self.total_questions,
            'correct_answers': self.correct_answers,
            'wrong_answers': self.wrong_answers,
            'score_percentage': self.score_percentage,
            'time_spent': self.time_spent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
