# src/models/learning_content.py
"""
Models for Learning Content System:
- LessonSummary: Text summaries for lessons
- ConceptMap: Interactive concept maps
- StudentLessonProgress: Track student progress

✅ FIXED: Updated to work with 'students' table (plural)
"""

from src.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class LessonSummary(db.Model):
    """ملخصات الدروس النصية"""
    __tablename__ = 'lesson_summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id', ondelete='CASCADE'), 
                         nullable=False, unique=True)
    
    # المحتوى
    introduction = db.Column(db.Text, nullable=False)
    key_points = db.Column(JSONB, nullable=False, default=[])
    examples = db.Column(JSONB, default=[])
    vocabulary = db.Column(JSONB, default={})
    
    # الإعدادات
    estimated_reading_time = db.Column(db.Integer, default=5)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    lesson = db.relationship('Lesson', backref=db.backref('summary', uselist=False, 
                                                         cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<LessonSummary lesson_id={self.lesson_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'introduction': self.introduction,
            'key_points': self.key_points,
            'examples': self.examples,
            'vocabulary': self.vocabulary,
            'estimated_reading_time': self.estimated_reading_time
        }


class ConceptMap(db.Model):
    """خرائط المفاهيم التفاعلية"""
    __tablename__ = 'concept_maps'
    
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id', ondelete='CASCADE'),
                         nullable=False, unique=True)
    
    # التصميم
    layout_type = db.Column(db.String(50), default='radial')
    theme = db.Column(db.String(50), default='modern')
    animation_type = db.Column(db.String(50), default='fade-in')
    
    # البيانات
    map_data = db.Column(JSONB, nullable=False)
    settings = db.Column(JSONB, default={'enableAnimation': True})
    
    # الإحصائيات
    view_count = db.Column(db.Integer, default=0)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    lesson = db.relationship('Lesson', backref=db.backref('concept_map', uselist=False,
                                                         cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<ConceptMap lesson_id={self.lesson_id} layout={self.layout_type}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'layout_type': self.layout_type,
            'theme': self.theme,
            'animation_type': self.animation_type,
            'map_data': self.map_data,
            'settings': self.settings,
            'view_count': self.view_count
        }


class StudentLessonProgress(db.Model):
    """تقدم الطالب في الدروس"""
    __tablename__ = 'student_lesson_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ✅ FIX: Changed from 'student.id' to 'students.id' to match actual table name
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'),
                          nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id', ondelete='CASCADE'),
                         nullable=False)
    
    # الحالة العامة
    status = db.Column(db.String(50), default='not_started')
    
    # الملخص
    summary_read = db.Column(db.Boolean, default=False)
    summary_reading_time = db.Column(db.Integer, default=0)
    
    # خريطة المفاهيم
    concept_map_explored = db.Column(db.Boolean, default=False)
    explored_nodes = db.Column(JSONB, default=[])
    concept_map_time = db.Column(db.Integer, default=0)
    
    # الإحصائيات
    completion_percentage = db.Column(db.Integer, default=0)
    total_time_spent = db.Column(db.Integer, default=0)
    
    # التواريخ
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات - ✅ FIXED: Specify foreign_keys explicitly
    # Note: We're not defining the relationship here to avoid conflicts
    # The relationship will be accessed via queries directly
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('student_id', 'lesson_id', name='unique_student_lesson'),
    )
    
    def __repr__(self):
        return f'<StudentLessonProgress student_id={self.student_id} lesson_id={self.lesson_id} status={self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'lesson_id': self.lesson_id,
            'status': self.status,
            'summary_read': self.summary_read,
            'summary_reading_time': self.summary_reading_time,
            'concept_map_explored': self.concept_map_explored,
            'explored_nodes': self.explored_nodes,
            'concept_map_time': self.concept_map_time,
            'completion_percentage': self.completion_percentage,
            'total_time_spent': self.total_time_spent,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None
        }
    
    def calculate_completion(self):
        """حساب نسبة الإكمال"""
        completion = 0
        if self.summary_read:
            completion += 50
        if self.concept_map_explored:
            completion += 50
        return completion
    
    def update_completion(self):
        """تحديث نسبة الإكمال تلقائياً"""
        self.completion_percentage = self.calculate_completion()
        
        # تحديث الحالة
        if self.completion_percentage == 100 and self.status != 'completed':
            self.status = 'completed'
            if not self.completed_at:
                self.completed_at = datetime.utcnow()
        elif self.concept_map_explored and not self.summary_read:
            self.status = 'exploring_map'
        elif self.summary_read and not self.concept_map_explored:
            self.status = 'exploring_map'
        elif not self.summary_read:
            self.status = 'reading_summary'
