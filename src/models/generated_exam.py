"""
GeneratedExam — يحفظ إعدادات الاختبارات المولّدة (بدون الأسئلة) للتاريخ والإعادة
"""
from src.extensions import db
from datetime import datetime
import json


class GeneratedExam(db.Model):
    __tablename__ = 'generated_exams'

    id             = db.Column(db.Integer, primary_key=True)

    # من ولّد الاختبار
    teacher_id     = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id',     ondelete='CASCADE'), nullable=True)

    # إعدادات التوليد
    course_id      = db.Column(db.Integer, nullable=False)
    unit_id        = db.Column(db.Integer, nullable=True)
    lesson_id      = db.Column(db.Integer, nullable=True)
    question_count = db.Column(db.Integer, nullable=False, default=10)
    include_answers   = db.Column(db.Boolean, default=False)
    shuffle_questions = db.Column(db.Boolean, default=True)
    shuffle_options   = db.Column(db.Boolean, default=True)

    # بيانات الكليشه (JSON)
    header_json    = db.Column(db.Text, nullable=True)

    # رقم النموذج (نفس الرقم المطبوع بورقة الاختبار ومفتاح الريمارك)
    exam_number    = db.Column(db.String(20), nullable=True)

    # إعدادات إضافية للاستعادة الكاملة (توزيع الأنواع، الاختيار اليدوي،
    # منهج/وحدة/دروس متعددة، فلاتر، عدد نماذج، تنسيق) — JSON مرن واحد
    # بدل عمود منفصل لكل إعداد، بنفس نمط header_json
    extra_json     = db.Column(db.Text, nullable=True)

    # أسماء مخزّنة للعرض السريع (بدون join)
    course_name    = db.Column(db.String(200), nullable=True)
    unit_name      = db.Column(db.String(200), nullable=True)
    lesson_name    = db.Column(db.String(200), nullable=True)

    generated_at   = db.Column(db.DateTime, default=datetime.utcnow)

    # ───────────────────────────────────────────────
    @property
    def header(self):
        if self.header_json:
            try:
                return json.loads(self.header_json)
            except Exception:
                return {}
        return {}

    @header.setter
    def header(self, value):
        self.header_json = json.dumps(value, ensure_ascii=False) if value else None

    @property
    def extra(self):
        if self.extra_json:
            try:
                return json.loads(self.extra_json)
            except Exception:
                return {}
        return {}

    @extra.setter
    def extra(self, value):
        self.extra_json = json.dumps(value, ensure_ascii=False) if value else None

    def to_dict(self):
        return {
            'id':               self.id,
            'course_id':        self.course_id,
            'unit_id':          self.unit_id,
            'lesson_id':        self.lesson_id,
            'question_count':   self.question_count,
            'include_answers':  self.include_answers,
            'shuffle_questions': self.shuffle_questions,
            'shuffle_options':  self.shuffle_options,
            'header':           self.header,
            'exam_number':      self.exam_number or '',
            'extra':            self.extra,
            'course_name':      self.course_name or '',
            'unit_name':        self.unit_name or '',
            'lesson_name':      self.lesson_name or '',
            'generated_at':     self.generated_at.isoformat() if self.generated_at else None,
        }
