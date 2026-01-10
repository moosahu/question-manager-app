# src/models/quiz.py
# نموذج الاختبارات المتكامل

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()

from datetime import datetime


class Quiz(db.Model):
    """جدول الاختبارات"""
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # معلومات الاختبار
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # الارتباط بالمنهج
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=True)
    
    # إعدادات الاختبار
    total_questions = db.Column(db.Integer, default=0)
    time_limit = db.Column(db.Integer, nullable=True)  # بالدقائق
    passing_score = db.Column(db.Float, default=60.0)  # النسبة المئوية للنجاح
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    course = db.relationship('Course', backref='quizzes', lazy=True)
    unit = db.relationship('Unit', backref='quizzes', lazy=True)
    lesson = db.relationship('Lesson', backref='quizzes', lazy=True)
    
    @staticmethod
    def get_active_quizzes():
        """جلب الاختبارات المفعلة والمنشورة"""
        return Quiz.query.filter_by(is_active=True, is_published=True).all()
    
    @staticmethod
    def get_quizzes_by_course(course_id):
        """جلب الاختبارات حسب المنهج"""
        return Quiz.query.filter_by(course_id=course_id, is_active=True).all()
    
    @staticmethod
    def get_quizzes_by_unit(unit_id):
        """جلب الاختبارات حسب الوحدة"""
        return Quiz.query.filter_by(unit_id=unit_id, is_active=True).all()
    
    @staticmethod
    def get_quizzes_by_lesson(lesson_id):
        """جلب الاختبارات حسب الدرس"""
        return Quiz.query.filter_by(lesson_id=lesson_id, is_active=True).all()
    
    def to_dict(self):
        """تحويل لـ dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'course_id': self.course_id,
            'unit_id': self.unit_id,
            'lesson_id': self.lesson_id,
            'total_questions': self.total_questions,
            'time_limit': self.time_limit,
            'passing_score': self.passing_score,
            'is_active': self.is_active,
            'is_published': self.is_published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f"<Quiz {self.name}>"
