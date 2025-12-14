"""
نموذج إعدادات رأس الاختبار
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class ExamHeaderSettings(db.Model):
    """نموذج لتخزين إعدادات رأس الاختبار"""
    
    __tablename__ = 'exam_header_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # معلومات الدولة والوزارة
    country = db.Column(db.String(255), default='المملكة العربية السعودية')
    ministry = db.Column(db.String(255), default='وزارة التعليم')
    education_department = db.Column(db.String(255), default='')
    school_name = db.Column(db.String(255), default='')
    
    # معلومات الاختبار
    subject = db.Column(db.String(255), default='')
    time = db.Column(db.String(100), default='')
    grade = db.Column(db.String(100), default='')
    total_score = db.Column(db.Integer, default=30)
    
    # معلومات التوقيع
    checker_name = db.Column(db.String(255), default='')
    reviewer_name = db.Column(db.String(255), default='')
    exam_date = db.Column(db.String(100), default='')
    
    # معلومات إضافية
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    def to_dict(self):
        """تحويل النموذج إلى قاموس"""
        return {
            'id': self.id,
            'country': self.country,
            'ministry': self.ministry,
            'education_department': self.education_department,
            'school_name': self.school_name,
            'subject': self.subject,
            'time': self.time,
            'grade': self.grade,
            'total_score': self.total_score,
            'checker_name': self.checker_name,
            'reviewer_name': self.reviewer_name,
            'exam_date': self.exam_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<ExamHeaderSettings {self.id}>'
