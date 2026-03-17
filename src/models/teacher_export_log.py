"""
TeacherExportLog - سجل استخراجات المعلم اليومية (اختبار + ورقة تظليل)
"""
from datetime import datetime
from src.extensions import db


class TeacherExportLog(db.Model):
    __tablename__ = 'teacher_export_logs'

    id          = db.Column(db.Integer, primary_key=True)
    teacher_id  = db.Column(db.Integer, nullable=False, index=True)
    export_type = db.Column(db.String(20), nullable=False)  # 'exam' أو 'remark'
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TeacherExportLog T{self.teacher_id} {self.export_type} {self.created_at}>'
