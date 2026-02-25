"""
Textbook Models - نماذج الكتب الدراسية وتحضير الدروس
"""
from src.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB


class Textbook(db.Model):
    """جدول الكتب الدراسية"""
    __tablename__ = 'textbooks'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    edition_year = db.Column(db.String(10), nullable=True)
    pdf_url = db.Column(db.Text, nullable=False)
    total_pages = db.Column(db.Integer, default=0)
    uploaded_by = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship('Course', backref=db.backref('textbooks', lazy=True))
    lesson_pages = db.relationship('LessonPages', backref='textbook', lazy=True,
                                   cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_name': self.course.name if self.course else None,
            'title': self.title,
            'edition_year': self.edition_year,
            'pdf_url': self.pdf_url,
            'total_pages': self.total_pages,
            'uploaded_by': self.uploaded_by,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LessonPages(db.Model):
    """ربط الدروس بصفحات الكتاب"""
    __tablename__ = 'lesson_pages'

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id', ondelete='CASCADE'), nullable=False)
    textbook_id = db.Column(db.Integer, db.ForeignKey('textbooks.id', ondelete='CASCADE'), nullable=False)
    start_page = db.Column(db.Integer, nullable=False)
    end_page = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('lesson_id', 'textbook_id', name='unique_lesson_textbook'),
    )

    lesson = db.relationship('Lesson', backref=db.backref('page_mappings', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'lesson_name': self.lesson.name if self.lesson else None,
            'textbook_id': self.textbook_id,
            'start_page': self.start_page,
            'end_page': self.end_page,
        }


class LessonPlan(db.Model):
    """حفظ التحاضير المُولّدة"""
    __tablename__ = 'lesson_plans'

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    plan_type = db.Column(db.String(30), nullable=False, default='single_lesson')
    ai_provider = db.Column(db.String(20), default='gemini')
    plan_data = db.Column(JSONB, default={})
    pdf_file_url = db.Column(db.Text, nullable=True)
    student_level = db.Column(db.String(20), nullable=True)
    student_count = db.Column(db.Integer, nullable=True)
    weak_students_count = db.Column(db.Integer, nullable=True)
    excellent_students_count = db.Column(db.Integer, nullable=True)
    focus_area = db.Column(db.String(30), nullable=True)
    examples_count = db.Column(db.Integer, default=5)
    status = db.Column(db.String(20), default='pending')  # pending, generating, completed, failed
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lesson = db.relationship('Lesson', backref=db.backref('lesson_plans', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('lesson_plans', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'lesson_name': self.lesson.name if self.lesson else None,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.name if self.teacher else None,
            'plan_type': self.plan_type,
            'ai_provider': self.ai_provider,
            'plan_data': self.plan_data,
            'pdf_file_url': self.pdf_file_url,
            'student_level': self.student_level,
            'student_count': self.student_count,
            'weak_students_count': self.weak_students_count,
            'excellent_students_count': self.excellent_students_count,
            'focus_area': self.focus_area,
            'examples_count': self.examples_count,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
