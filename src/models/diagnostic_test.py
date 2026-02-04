# src/models/diagnostic_test.py
"""
نموذج الاختبار التشخيصي (قبلي/بعدي) - النسخة المحدثة مع دعم الجدولة
"""

from datetime import datetime

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
    
    # ربط مع المنهج (IDs فقط - بدون ForeignKey لتجنب مشاكل العلاقات)
    lesson_id = db.Column(db.Integer, nullable=True)
    unit_id = db.Column(db.Integer, nullable=True)
    course_id = db.Column(db.Integer, nullable=True)
    
    # أسماء للعرض (cached)
    lesson_name = db.Column(db.String(255), nullable=True)
    unit_name = db.Column(db.String(255), nullable=True)
    course_name = db.Column(db.String(255), nullable=True)
    
    # عدد الأسئلة
    questions_count = db.Column(db.Integer, default=5)
    
    # الأسئلة الكاملة مع الخيارات (JSON)
    questions_data = db.Column(db.JSON, default=[])
    
    # إعدادات
    difficulty_distribution = db.Column(db.JSON, default={'easy': 2, 'medium': 2, 'hard': 1})
    time_limit_minutes = db.Column(db.Integer, default=15)
    passing_score = db.Column(db.Float, default=60.0)
    
    # AI
    ai_generated = db.Column(db.Boolean, default=False)
    
    # ربط قبلي ↔ بعدي
    paired_test_id = db.Column(db.Integer, nullable=True)
    
    # ===== الجدولة والإسناد (جديد) =====
    # وقت البداية والنهاية
    scheduled_start = db.Column(db.DateTime, nullable=True)
    scheduled_end = db.Column(db.DateTime, nullable=True)
    
    # الطلاب المخصص لهم الاختبار
    assigned_students = db.Column(db.JSON, default=[])
    
    # تخصيص حسب الصف (اختياري)
    assigned_grade = db.Column(db.String(50), nullable=True)
    
    # حالة الجدولة
    is_scheduled = db.Column(db.Boolean, default=False)
    schedule_status = db.Column(db.String(20), default='pending')
    
    # إشعارات
    notification_sent = db.Column(db.Boolean, default=False)
    notification_sent_at = db.Column(db.DateTime, nullable=True)
    
    # حالة
    is_active = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)
    
    def to_dict(self, include_questions=False):
        """تحويل إلى dictionary"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'test_type': self.test_type,
            'test_type_ar': 'قبلي' if self.test_type == 'pre_test' else 'بعدي',
            'lesson_id': self.lesson_id,
            'lesson_name': self.lesson_name,
            'unit_id': self.unit_id,
            'unit_name': self.unit_name,
            'course_id': self.course_id,
            'course_name': self.course_name,
            'questions_count': self.questions_count,
            'difficulty_distribution': self.difficulty_distribution,
            'time_limit_minutes': self.time_limit_minutes,
            'passing_score': self.passing_score,
            'ai_generated': self.ai_generated,
            'paired_test_id': self.paired_test_id,
            
            # الجدولة
            'is_scheduled': self.is_scheduled,
            'schedule_status': self.schedule_status,
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'scheduled_end': self.scheduled_end.isoformat() if self.scheduled_end else None,
            'assigned_students': self.assigned_students or [],
            'assigned_students_count': len(self.assigned_students or []),
            'assigned_grade': self.assigned_grade,
            'notification_sent': self.notification_sent,
            
            'is_active': self.is_active,
            'is_published': self.is_published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_questions:
            data['questions'] = self.questions_data or []
        
        return data
    
    def is_available_now(self):
        """هل الاختبار متاح الآن؟"""
        if not self.is_scheduled:
            return True
        
        now = datetime.utcnow()
        
        if self.scheduled_start and now < self.scheduled_start:
            return False
        
        if self.scheduled_end and now > self.scheduled_end:
            return False
        
        return True
    
    def is_student_assigned(self, student_id):
        """هل الطالب مخصص له هذا الاختبار؟"""
        if not self.is_scheduled:
            return True
        
        assigned = self.assigned_students or []
        return student_id in assigned
    
    def update_schedule_status(self):
        """تحديث حالة الجدولة تلقائياً"""
        if not self.is_scheduled:
            self.schedule_status = 'not_scheduled'
            return
        
        now = datetime.utcnow()
        
        if self.scheduled_start and now < self.scheduled_start:
            self.schedule_status = 'pending'
        elif self.scheduled_end and now > self.scheduled_end:
            self.schedule_status = 'expired'
        else:
            self.schedule_status = 'active'
    
    def __repr__(self):
        return f'<DiagnosticTest {self.id}: {self.title}>'


class DiagnosticResult(db.Model):
    """نتيجة اختبار تشخيصي"""
    __tablename__ = 'diagnostic_results'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # الاختبار
    diagnostic_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    
    # الطالب
    student_id = db.Column(db.String(100), nullable=True)
    student_name = db.Column(db.String(255), nullable=True)
    device_id = db.Column(db.String(255), nullable=True)
    
    # النتيجة
    score = db.Column(db.Float, default=0)
    total_questions = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0)
    
    # الإجابات التفصيلية
    answers = db.Column(db.JSON, default=[])
    
    # ✅ حالة الاختبار
    status = db.Column(db.String(20), default='in_progress')
    # القيم الممكنة: 'in_progress', 'completed'
    
    # الوقت
    time_spent_seconds = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقة
    test = db.relationship('DiagnosticTest', backref=db.backref('results', lazy='dynamic'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'test_id': self.diagnostic_test_id,
            'student_id': self.student_id,
            'student_name': self.student_name,
            'score': self.score,
            'total_questions': self.total_questions,
            'correct_answers': self.correct_answers,
            'percentage': self.percentage,
            'status': self.status,
            'time_spent_seconds': self.time_spent_seconds,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class DiagnosticComparison(db.Model):
    """مقارنة نتائج الاختبارات القبلية والبعدية"""
    __tablename__ = 'diagnostic_comparisons'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # الاختبارات
    pre_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    post_test_id = db.Column(db.Integer, db.ForeignKey('diagnostic_tests.id'), nullable=False)
    
    # النتائج
    pre_result_id = db.Column(db.Integer, db.ForeignKey('diagnostic_results.id'), nullable=True)
    post_result_id = db.Column(db.Integer, db.ForeignKey('diagnostic_results.id'), nullable=True)
    
    # الطالب
    student_id = db.Column(db.String(100), nullable=True)
    student_name = db.Column(db.String(255), nullable=True)
    device_id = db.Column(db.String(255), nullable=True)
    
    # النتائج
    pre_score = db.Column(db.Float, default=0)
    post_score = db.Column(db.Float, default=0)
    improvement = db.Column(db.Float, default=0)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    pre_test = db.relationship('DiagnosticTest', foreign_keys=[pre_test_id])
    post_test = db.relationship('DiagnosticTest', foreign_keys=[post_test_id])
    pre_result = db.relationship('DiagnosticResult', foreign_keys=[pre_result_id])
    post_result = db.relationship('DiagnosticResult', foreign_keys=[post_result_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'pre_test_id': self.pre_test_id,
            'post_test_id': self.post_test_id,
            'student_id': self.student_id,
            'student_name': self.student_name,
            'pre_score': self.pre_score,
            'post_score': self.post_score,
            'improvement': self.improvement,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
