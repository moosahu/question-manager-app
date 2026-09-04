# src/models/academic_calendar.py
"""مسرد إعداد الدروس — تقويم دراسي (تواريخ + إجازات) موزّع عليه دروس المنهج"""
from datetime import datetime

try:
    from src.extensions import db
except ImportError:  # pragma: no cover
    from extensions import db


class AcademicCalendar(db.Model):
    """تقويم فصل دراسي لمقرر معيّن — يحتوي الأسابيع/الأيام وتوزيع الدروس عليها"""
    __tablename__ = 'academic_calendars'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    semester_number = db.Column(db.Integer, nullable=False)  # 1 أو 2
    academic_year_label = db.Column(db.String(20), nullable=False)  # مثال: "1448هـ"
    section = db.Column(db.String(50), nullable=True)  # الشعبة — كل شعبة تقويمها المستقل (أيام حصص/توزيع مختلف)
    weeks_data = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ مدخلات الإنشاء الأصلية — تُخزَّن عشان نقدر نعيد بناء الأسابيع لاحقاً (مثلاً عند إضافة إجازة جديدة)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    class_weekdays = db.Column(db.JSON, nullable=True)  # [6,0,1,2,3] بترميز weekday() بايثون
    holidays = db.Column(db.JSON, nullable=True)  # [{start_date,end_date,type,label}, ...]

    course = db.relationship('Course', backref='academic_calendars')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_name': self.course.name if self.course else None,
            'semester_number': self.semester_number,
            'academic_year_label': self.academic_year_label,
            'section': self.section,
            'weeks_data': self.weeks_data or [],
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'class_weekdays': self.class_weekdays or [],
            'holidays': self.holidays or [],
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
        }
