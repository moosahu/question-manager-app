"""
نماذج جداول المذاكرة للاختبار التحصيلي
Study Schedule models — added to question_manager project
"""
from datetime import datetime, date
from src.extensions import db


class StudySchedule(db.Model):
    """جدول مذاكرة"""
    __tablename__ = 'study_schedules'

    id           = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    duration     = db.Column(db.Integer, nullable=False)        # 15 | 30 | 60 يوم
    daily_hours  = db.Column(db.Float,   nullable=False)        # ساعات الدراسة يومياً
    start_date   = db.Column(db.Date,    nullable=False)
    exam_date    = db.Column(db.Date,    nullable=True)         # تاريخ الاختبار التحصيلي (اختياري)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship(
        'StudySession',
        backref='schedule',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='StudySession.day_number, StudySession.order_index'
    )

    # ── helpers ──────────────────────────────────────────────────────────────
    @property
    def days_until_exam(self):
        if not self.exam_date:
            return None
        return (self.exam_date - date.today()).days

    @property
    def total_sessions(self):
        return len(self.sessions)

    @property
    def completed_sessions(self):
        return sum(1 for s in self.sessions if s.is_completed)

    @property
    def completion_percent(self):
        if not self.total_sessions:
            return 0
        return round(self.completed_sessions / self.total_sessions * 100)

    def to_dict(self):
        return {
            'id':               self.id,
            'studentName':      self.student_name,
            'duration':         self.duration,
            'dailyHours':       float(self.daily_hours),
            'startDate':        self.start_date.strftime('%Y-%m-%d'),
            'examDate':         self.exam_date.strftime('%Y-%m-%d') if self.exam_date else None,
            'daysUntilExam':    self.days_until_exam,
            'createdAt':        self.created_at.isoformat(),
            'totalSessions':    self.total_sessions,
            'completedSessions': self.completed_sessions,
            'completionPercent': self.completion_percent,
            'sessions':         [s.to_dict() for s in self.sessions],
        }

    def __repr__(self):
        return f'<StudySchedule id={self.id} name={self.student_name}>'


class StudySession(db.Model):
    """جلسة دراسية ضمن الجدول"""
    __tablename__ = 'study_sessions'

    id               = db.Column(db.Integer, primary_key=True)
    schedule_id      = db.Column(db.Integer, db.ForeignKey('study_schedules.id'), nullable=False)
    day_number       = db.Column(db.Integer, nullable=False)
    subject          = db.Column(db.String(50), nullable=False)
    start_time       = db.Column(db.String(5),  nullable=False)   # HH:MM
    end_time         = db.Column(db.String(5),  nullable=False)   # HH:MM
    duration_minutes = db.Column(db.Integer, nullable=False)
    is_completed     = db.Column(db.Boolean, default=False, nullable=False)
    order_index      = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'id':              self.id,
            'scheduleId':      self.schedule_id,
            'dayNumber':       self.day_number,
            'subject':         self.subject,
            'startTime':       self.start_time,
            'endTime':         self.end_time,
            'durationMinutes': self.duration_minutes,
            'isCompleted':     self.is_completed,
            'orderIndex':      self.order_index,
        }

    def __repr__(self):
        return f'<StudySession day={self.day_number} {self.subject}>'
