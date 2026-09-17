# src/models/survey.py
"""استبيانات عامة يبنيها الأدمن (أسئلة اختيار متعدد/نص حر/تقييم/نعم-لا) ويرسلها لطالب/معلم/الكل/طلابه"""
from datetime import datetime

try:
    from src.extensions import db
except ImportError:  # pragma: no cover
    from extensions import db

QUESTION_TYPES = ('choice', 'text', 'rating', 'yesno')
TARGET_TYPES = ('student', 'teacher', 'all', 'my_students')


class Survey(db.Model):
    """استبيان — عنوان + وصف + إعدادات السرية والاستهداف"""
    __tablename__ = 'surveys'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # الأدمن المُنشئ
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)

    target_type = db.Column(db.String(20), nullable=False, default='all')  # student/teacher/all/my_students
    target_ids = db.Column(db.JSON, nullable=True)  # قائمة معرّفات — لـ target_type: student أو teacher

    status = db.Column(db.String(20), nullable=False, default='active')  # active/closed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship(
        'SurveyQuestion', backref='survey', order_by='SurveyQuestion.order',
        cascade='all, delete-orphan',
    )
    responses = db.relationship('SurveyResponse', backref='survey', cascade='all, delete-orphan')

    def to_dict(self, with_questions=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description or '',
            'is_anonymous': self.is_anonymous,
            'target_type': self.target_type,
            'target_ids': self.target_ids or [],
            'status': self.status,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'responses_count': len(self.responses) if self.responses is not None else 0,
        }
        if with_questions:
            data['questions'] = [q.to_dict() for q in self.questions]
        return data


class SurveyQuestion(db.Model):
    """سؤال ضمن استبيان — نوعه أحد QUESTION_TYPES"""
    __tablename__ = 'survey_questions'

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    text = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False, default='choice')  # choice/text/rating/yesno
    options = db.Column(db.JSON, nullable=True)  # قائمة نصوص — لنوع choice فقط
    rating_max = db.Column(db.Integer, nullable=True, default=5)  # لنوع rating فقط

    def to_dict(self):
        return {
            'id': self.id,
            'order': self.order,
            'text': self.text,
            'type': self.type,
            'options': self.options or [],
            'rating_max': self.rating_max or 5,
        }


class SurveyResponse(db.Model):
    """رد شخص واحد على استبيان — يمنع الإجابة مرتين لنفس الشخص"""
    __tablename__ = 'survey_responses'
    __table_args__ = (
        db.UniqueConstraint('survey_id', 'respondent_type', 'respondent_id', name='uq_survey_respondent'),
    )

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False, index=True)
    respondent_type = db.Column(db.String(10), nullable=False)  # student/teacher
    respondent_id = db.Column(db.Integer, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    answers = db.relationship('SurveyAnswer', backref='response', cascade='all, delete-orphan')


class SurveyAnswer(db.Model):
    """إجابة سؤال واحد ضمن رد"""
    __tablename__ = 'survey_answers'

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('survey_responses.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('survey_questions.id', ondelete='CASCADE'), nullable=False, index=True)

    answer_text = db.Column(db.Text, nullable=True)  # لنوع text
    answer_choice = db.Column(db.String(200), nullable=True)  # لنوع choice/yesno
    answer_rating = db.Column(db.Integer, nullable=True)  # لنوع rating
