# src/models/learning_content.py
"""
Models for Learning Content System:
- LessonSummary: Text summaries for lessons
- ConceptMap: Interactive concept maps
- StudentLessonProgress: Track student progress
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
    introduction = db.Column(db.Text, nullable=False)  # المقدمة
    key_points = db.Column(JSONB, nullable=False, default=[])  # النقاط الرئيسية
    examples = db.Column(JSONB, default=[])  # الأمثلة التطبيقية
    vocabulary = db.Column(JSONB, default={})  # المصطلحات {"term": "definition"}
    
    # الإعدادات
    estimated_reading_time = db.Column(db.Integer, default=5)  # دقائق
    
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
    # Options: 'radial', 'hierarchical', 'mindmap', 'flowchart', 'timeline', 'network', 'spiral'
    
    theme = db.Column(db.String(50), default='modern')
    # Options: 'modern', 'neon', 'minimal', 'glassmorphism', 'gradient'
    
    animation_type = db.Column(db.String(50), default='fade-in')
    # Options: 'fade-in', 'slide-in', 'bounce-in', 'spiral-in'
    
    # البيانات
    map_data = db.Column(JSONB, nullable=False)
    """
    Structure:
    {
        "center_node": {
            "id": "chemistry",
            "text": "الكيمياء",
            "description": "...",
            "color": "#FFD54F"
        },
        "branches": [
            {
                "id": "organic",
                "text": "الكيمياء العضوية",
                "color": "#4CAF50",
                "description": "...",
                "specialty": "...",
                "examples": ["...", "..."]
            }
        ]
    }
    """
    
    # الإعدادات
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
    student_id = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'),
                          nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id', ondelete='CASCADE'),
                         nullable=False)
    
    # الحالة العامة
    status = db.Column(db.String(50), default='not_started')
    # Options: 'not_started', 'reading_summary', 'exploring_map', 'completed'
    
    # الملخص
    summary_read = db.Column(db.Boolean, default=False)
    summary_reading_time = db.Column(db.Integer, default=0)  # ثواني
    
    # خريطة المفاهيم
    concept_map_explored = db.Column(db.Boolean, default=False)
    explored_nodes = db.Column(JSONB, default=[])  # ["node1", "node2", ...]
    concept_map_time = db.Column(db.Integer, default=0)  # ثواني
    
    # الإحصائيات
    completion_percentage = db.Column(db.Integer, default=0)  # 0-100
    total_time_spent = db.Column(db.Integer, default=0)  # ثواني
    
    # التواريخ
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    student = db.relationship('Student', backref='lesson_progress')
    lesson = db.relationship('Lesson', backref='student_progress')
    
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
