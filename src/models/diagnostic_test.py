"""
نماذج الاختبارات التشخيصية (قبلي/بعدي)
Diagnostic Tests Models - Pre/Post Assessment
"""

from datetime import datetime
from src.extensions import db


class DiagnosticTest(db.Model):
    """نموذج الاختبار التشخيصي"""
    __tablename__ = 'diagnostic_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # نوع الاختبار: قبلي أو بعدي
    test_type = db.Column(db.String(20), nullable=False)  # 'pre_test' or 'post_test'
    
    # العنوان والوصف
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # الربط بالمنهج (بدون Foreign Key constraints)
    lesson_id = db.Column(db.Integer, nullable=True)
    unit_id = db.Column(db.Integer, nullable=True)
    course_id = db.Column(db.Integer, nullable=True)
    
    # أسماء للعرض (cached)
    lesson_name = db.Column(db.String(255))
    unit_name = db.Column(db.String(255))
    course_name = db.Column(db.String(255))
    
    # الأسئلة (JSON)
    questions = db.Column(db.JSON, default=list)
    questions_count = db.Column(db.Integer, default=0)
    
    # إعدادات الاختبار
    time_limit_minutes = db.Column(db.Integer, default=15)
    passing_score = db.Column(db.Float, default=60.0)
    
    # توزيع الصعوبة
    difficulty_distribution = db.Column(db.JSON, default=dict)
    
    # معلومات الإنشاء
    created_by = db.Column(db.Integer)  # Admin user ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # حالة الاختبار
    is_active = db.Column(db.Boolean, default=True)
    is_ai_generated = db.Column(db.Boolean, default=True)
    
    # ربط الاختبار القبلي بالبعدي
    paired_test_id = db.Column(db.Integer, nullable=True)
    
    # العلاقات - النتائج فقط (جدول محلي)
    results = db.relationship('DiagnosticResult', backref='test', lazy='dynamic',
                             foreign_keys='DiagnosticResult.test_id')
    
    def to_dict(self, include_questions=False):
        """تحويل لـ Dictionary"""
        data = {
            'id': self.id,
            'test_type': self.test_type,
            'test_type_display': 'قبلي' if self.test_type == 'pre_test' else 'بعدي',
            'title': self.title,
            'description': self.description,
            'lesson_id': self.lesson_id,
            'unit_id': self.unit_id,
            'course_id': self.course_id,
            'lesson_name': self.lesson_name,
            'unit_name': self.unit_name,
            'course_name': self.course_name,
            'questions_count': self.questions_count,
            'time_limit_minutes': self.time_limit_minutes,
            'passing_score': self.passing_score,
            'difficulty_distribution': self.difficulty_distribution,
            'is_active': self.is_active,
            'is_ai_generated': self.is_ai_generated,
            'paired_test_id': self.paired_test_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_questions:
            data['questions'] = self.questions or []
        
        return data
    
    def __repr__(self):
        return f'<DiagnosticTest {self.id}: {self.title}>'


class DiagnosticResult(db.Model):
    """نموذج نتيجة الاختبار التشخيصي"""
    __tablename__ = 'diagnostic_results'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # الربط بالاختبار والطالب
    test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    student_id = db.Column(db.Integer, nullable=False)  # بدون FK constraint
    
    # النتيجة
    score = db.Column(db.Float, nullable=False)  # النسبة المئوية
    correct_answers = db.Column(db.Integer, default=0)
    wrong_answers = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    
    # تفاصيل الإجابات (JSON)
    answers_detail = db.Column(db.JSON, default=list)
    
    # الوقت المستغرق
    time_spent_seconds = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # تحليل الذكاء الاصطناعي
    ai_analysis = db.Column(db.JSON, default=dict)
    weak_topics = db.Column(db.JSON, default=list)
    strong_topics = db.Column(db.JSON, default=list)
    recommendations = db.Column(db.JSON, default=list)
    
    # حالة النتيجة
    passed = db.Column(db.Boolean, default=False)
    
    # معلومات الإنشاء
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """تحويل لـ Dictionary"""
        return {
            'id': self.id,
            'test_id': self.test_id,
            'student_id': self.student_id,
            'score': self.score,
            'correct_answers': self.correct_answers,
            'wrong_answers': self.wrong_answers,
            'total_questions': self.total_questions,
            'answers_detail': self.answers_detail,
            'time_spent_seconds': self.time_spent_seconds,
            'time_spent_formatted': f"{self.time_spent_seconds // 60}:{self.time_spent_seconds % 60:02d}" if self.time_spent_seconds else "0:00",
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'ai_analysis': self.ai_analysis,
            'weak_topics': self.weak_topics,
            'strong_topics': self.strong_topics,
            'recommendations': self.recommendations,
            'passed': self.passed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<DiagnosticResult {self.id}: Test {self.test_id}, Student {self.student_id}, Score {self.score}%>'


class DiagnosticComparison(db.Model):
    """نموذج مقارنة الاختبار القبلي والبعدي"""
    __tablename__ = 'diagnostic_comparisons'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # الربط
    student_id = db.Column(db.Integer, nullable=False)
    pre_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    post_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    pre_result_id = db.Column(db.Integer, db.ForeignKey('diagnostic_results.id'), nullable=False)
    post_result_id = db.Column(db.Integer, db.ForeignKey('diagnostic_results.id'), nullable=False)
    
    # نتائج المقارنة
    pre_score = db.Column(db.Float, nullable=False)
    post_score = db.Column(db.Float, nullable=False)
    improvement = db.Column(db.Float, nullable=False)  # الفرق بين الدرجتين
    improvement_percentage = db.Column(db.Float)  # نسبة التحسن
    
    # تحليل التحسن
    improved_topics = db.Column(db.JSON, default=list)
    still_weak_topics = db.Column(db.JSON, default=list)
    new_weak_topics = db.Column(db.JSON, default=list)
    
    # تحليل AI
    ai_comparison_analysis = db.Column(db.JSON, default=dict)
    
    # معلومات الإنشاء
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """تحويل لـ Dictionary"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'pre_test_id': self.pre_test_id,
            'post_test_id': self.post_test_id,
            'pre_result_id': self.pre_result_id,
            'post_result_id': self.post_result_id,
            'pre_score': self.pre_score,
            'post_score': self.post_score,
            'improvement': self.improvement,
            'improvement_percentage': self.improvement_percentage,
            'improved_topics': self.improved_topics,
            'still_weak_topics': self.still_weak_topics,
            'new_weak_topics': self.new_weak_topics,
            'ai_comparison_analysis': self.ai_comparison_analysis,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<DiagnosticComparison {self.id}: Student {self.student_id}, Improvement {self.improvement}%>'
