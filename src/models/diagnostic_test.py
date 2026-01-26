# src/models/diagnostic_test.py
"""
نموذج الاختبار التشخيصي (قبلي/بعدي)
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()


class DiagnosticTest(db.Model):
    """نموذج الاختبار التشخيصي"""
    __tablename__ = 'diagnostic_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # معلومات الاختبار
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # نوع الاختبار: pre_test (قبلي), post_test (بعدي)
    test_type = db.Column(db.String(20), nullable=False, default='pre_test')
    
    # ربط مع المنهج
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    
    # الأسئلة (IDs من جدول questions)
    question_ids = db.Column(JSONB, default=[])
    questions_count = db.Column(db.Integer, default=5)
    
    # الأسئلة الكاملة مع الخيارات (للطباعة والتطبيق)
    questions_data = db.Column(JSONB, default=[])
    
    # إعدادات
    difficulty_distribution = db.Column(JSONB, default={'easy': 2, 'medium': 2, 'hard': 1})
    time_limit_minutes = db.Column(db.Integer, default=15)
    passing_score = db.Column(db.Float, default=60.0)
    
    # AI
    ai_generated = db.Column(db.Boolean, default=False)
    ai_prompt = db.Column(db.Text, nullable=True)
    
    # ربط قبلي ↔ بعدي
    paired_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=True)
    
    # حالة
    is_active = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)
    
    # العلاقات
    lesson = db.relationship('Lesson', backref=db.backref('diagnostic_tests', lazy='dynamic'), foreign_keys=[lesson_id])
    unit = db.relationship('Unit', backref=db.backref('diagnostic_tests', lazy='dynamic'), foreign_keys=[unit_id])
    course = db.relationship('Course', backref=db.backref('diagnostic_tests', lazy='dynamic'), foreign_keys=[course_id])
    paired_test = db.relationship('DiagnosticTest', remote_side=[id], backref='paired_with', foreign_keys=[paired_test_id])
    
    def to_dict(self, include_questions=False):
        """تحويل إلى dictionary"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'test_type': self.test_type,
            'test_type_ar': 'قبلي' if self.test_type == 'pre_test' else 'بعدي',
            'lesson_id': self.lesson_id,
            'lesson_name': self.lesson.name if self.lesson else None,
            'unit_id': self.unit_id,
            'unit_name': self.unit.name if self.unit else None,
            'course_id': self.course_id,
            'course_name': self.course.name if self.course else None,
            'questions_count': self.questions_count,
            'question_ids': self.question_ids,
            'difficulty_distribution': self.difficulty_distribution,
            'time_limit_minutes': self.time_limit_minutes,
            'passing_score': self.passing_score,
            'ai_generated': self.ai_generated,
            'paired_test_id': self.paired_test_id,
            'is_active': self.is_active,
            'is_published': self.is_published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_questions:
            data['questions'] = self.questions_data
        
        return data
    
    def __repr__(self):
        return f'<DiagnosticTest {self.id}: {self.title}>'


class DiagnosticResult(db.Model):
    """نتائج الطالب في الاختبار التشخيصي"""
    __tablename__ = 'diagnostic_results'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ربط
    diagnostic_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # النتيجة
    score = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=5)
    score_percentage = db.Column(db.Float, default=0.0)
    passed = db.Column(db.Boolean, default=False)
    
    # الإجابات التفصيلية
    answers = db.Column(JSONB, default=[])
    
    # الوقت
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    time_spent_seconds = db.Column(db.Integer, default=0)
    
    # حالة
    status = db.Column(db.String(20), default='not_started')  # not_started, in_progress, completed
    
    # تحليل AI
    ai_analysis = db.Column(db.Text, nullable=True)
    weak_topics = db.Column(JSONB, default=[])
    strong_topics = db.Column(JSONB, default=[])
    recommendations = db.Column(db.Text, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    diagnostic_test = db.relationship('DiagnosticTest', backref=db.backref('results', lazy='dynamic'))
    student = db.relationship('Student', backref=db.backref('diagnostic_results', lazy='dynamic'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'diagnostic_test_id': self.diagnostic_test_id,
            'test_title': self.diagnostic_test.title if self.diagnostic_test else None,
            'test_type': self.diagnostic_test.test_type if self.diagnostic_test else None,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else None,
            'score': self.score,
            'total_questions': self.total_questions,
            'score_percentage': round(self.score_percentage, 1),
            'passed': self.passed,
            'answers': self.answers,
            'time_spent_seconds': self.time_spent_seconds,
            'status': self.status,
            'ai_analysis': self.ai_analysis,
            'weak_topics': self.weak_topics,
            'strong_topics': self.strong_topics,
            'recommendations': self.recommendations,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class DiagnosticComparison(db.Model):
    """مقارنة بين القبلي والبعدي"""
    __tablename__ = 'diagnostic_comparisons'
    
    id = db.Column(db.Integer, primary_key=True)
    
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    pre_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    post_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    pre_result_id = db.Column(db.Integer, db.ForeignKey('diagnostic_results.id'), nullable=False)
    post_result_id = db.Column(db.Integer, db.ForeignKey('diagnostic_results.id'), nullable=False)
    
    # النتائج
    pre_score = db.Column(db.Float, default=0.0)
    post_score = db.Column(db.Float, default=0.0)
    improvement = db.Column(db.Float, default=0.0)  # نسبة التحسن
    
    # التقييم
    effectiveness = db.Column(db.String(20), nullable=True)  # excellent, good, moderate, poor
    
    # تحليل AI
    ai_analysis = db.Column(db.Text, nullable=True)
    improved_topics = db.Column(JSONB, default=[])
    still_weak_topics = db.Column(JSONB, default=[])
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    student = db.relationship('Student', backref=db.backref('diagnostic_comparisons', lazy='dynamic'))
    pre_test = db.relationship('DiagnosticTest', foreign_keys=[pre_test_id])
    post_test = db.relationship('DiagnosticTest', foreign_keys=[post_test_id])
    pre_result = db.relationship('DiagnosticResult', foreign_keys=[pre_result_id])
    post_result = db.relationship('DiagnosticResult', foreign_keys=[post_result_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else None,
            'pre_test_id': self.pre_test_id,
            'post_test_id': self.post_test_id,
            'pre_score': round(self.pre_score, 1),
            'post_score': round(self.post_score, 1),
            'improvement': round(self.improvement, 1),
            'effectiveness': self.effectiveness,
            'effectiveness_ar': {
                'excellent': 'ممتاز',
                'good': 'جيد',
                'moderate': 'متوسط',
                'poor': 'ضعيف'
            }.get(self.effectiveness, 'غير محدد'),
            'ai_analysis': self.ai_analysis,
            'improved_topics': self.improved_topics,
            'still_weak_topics': self.still_weak_topics,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
