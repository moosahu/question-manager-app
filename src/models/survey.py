# src/models/survey.py
"""استبيانات عامة يبنيها الأدمن (أسئلة اختيار متعدد/نص حر/تقييم/نعم-لا) ويرسلها لطالب/معلم/الكل/طلابه"""
from datetime import datetime

try:
    from src.extensions import db
except ImportError:  # pragma: no cover
    from extensions import db

QUESTION_TYPES = ('choice', 'text', 'rating', 'yesno', 'likert5', 'yes_no', 'single_choice', 'multi_choice')
TARGET_TYPES = ('student', 'teacher', 'all', 'my_students', 'section')
SURVEY_TYPES = ('استطلاعي', 'كشفي', 'تقويمي', 'رضا')
GRADE_LEVELS = ('ابتدائي', 'متوسط', 'ثانوي')


class Survey(db.Model):
    """استبيان — عنوان + وصف + إعدادات السرية والاستهداف"""
    __tablename__ = 'surveys'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # الأدمن المُنشئ
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)

    target_type = db.Column(db.String(20), nullable=False, default='all')  # student/teacher/all/my_students/section
    target_ids = db.Column(db.JSON, nullable=True)  # قائمة معرّفات — لـ target_type: student أو teacher
    target_section = db.Column(db.String(100), nullable=True)  # اسم الشعبة — لـ target_type: section فقط

    status = db.Column(db.String(20), nullable=False, default='active')  # active/closed

    # ═══ حقول القياس النفسي/التربوي (مولّد الذكاء الاصطناعي المحسّن) ═══
    # كلها nullable — استبيانات قديمة اتبنت يدوياً قبل هذا التحديث تبقى تشتغل بدونها
    survey_type = db.Column(db.String(20), nullable=True)  # استطلاعي/كشفي/تقويمي/رضا
    purpose = db.Column(db.Text, nullable=True)  # الهدف أو القرار المبني على النتائج
    grade_level = db.Column(db.String(20), nullable=True)  # ابتدائي/متوسط/ثانوي
    estimated_minutes = db.Column(db.Integer, nullable=True)  # الزمن المتوقع للتعبئة — من توليد الذكاء الاصطناعي، يُستخدم بفحص سرعة الإكمال
    axes = db.Column(db.JSON, nullable=True)  # [{code, name, construct, high_score_means}]
    compare_by = db.Column(db.JSON, nullable=True)  # متغيرات ديموغرافية للمقارنة (مثل: الشعبة)
    is_pilot = db.Column(db.Boolean, nullable=False, default=False)  # تجريبي = لا تُدمج ردوده بالتحليل مع النهائي

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship(
        'SurveyQuestion', backref='survey', order_by='SurveyQuestion.order',
        cascade='all, delete-orphan',
    )
    responses = db.relationship('SurveyResponse', backref='survey', cascade='all, delete-orphan')

    def to_dict(self, with_questions=False, show_answers=True):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description or '',
            'is_anonymous': self.is_anonymous,
            'target_type': self.target_type,
            'target_ids': self.target_ids or [],
            'target_section': self.target_section or '',
            'status': self.status,
            'survey_type': self.survey_type or '',
            'purpose': self.purpose or '',
            'grade_level': self.grade_level or '',
            'estimated_minutes': self.estimated_minutes,
            'axes': self.axes or [],
            'compare_by': self.compare_by or [],
            'is_pilot': self.is_pilot,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'responses_count': len(self.responses) if self.responses is not None else 0,
        }
        if with_questions:
            data['questions'] = [q.to_dict(show_answers=show_answers) for q in self.questions]
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
    rating_min_label = db.Column(db.String(100), nullable=True)  # توضيح معنى أقل رقم (مثال: "غير موافق") — اختياري
    rating_max_label = db.Column(db.String(100), nullable=True)  # توضيح معنى أعلى رقم (مثال: "موافق تماماً") — اختياري

    # ═══ حقول القياس النفسي/التربوي (مولّد الذكاء الاصطناعي المحسّن) ═══
    axis_code = db.Column(db.String(5), nullable=True)  # رمز المحور اللي تنتمي له الفقرة (A/B/C...) — null للأسئلة خارج المحاور
    item_code = db.Column(db.String(10), nullable=True)  # رمز ثابت للفقرة (A1، KN1، DM1...) يُستخدم عمود بالتصدير
    reverse = db.Column(db.Boolean, nullable=False, default=False)  # فقرة عكسية — تُقلب درجتها عند التحليل، لا يُعرض للمستجيب إطلاقاً
    scored = db.Column(db.Boolean, nullable=False, default=True)  # تدخل بدرجة المحور وحساب الثبات (False لأسئلة ديموغرافية/معرفية)
    correct_option = db.Column(db.Text, nullable=True)  # الإجابة الصحيحة — للأسئلة المعرفية الموضوعية فقط — نص حر بلا حد أقصى (نفس طول الخيارات نفسها)
    # تفرّع شرطي: {"نص الخيار": "رمز السؤال التالي"} — كل خيار ممكن يوديك لسؤال مختلف، مو قفزة ثابتة
    skip_to = db.Column(db.JSON, nullable=True)

    def to_dict(self, show_answers=True):
        data = {
            'id': self.id,
            'order': self.order,
            'text': self.text,
            'type': self.type,
            'options': self.options or [],
            'rating_max': self.rating_max or 5,
            'rating_min_label': self.rating_min_label or '',
            'rating_max_label': self.rating_max_label or '',
            'axis_code': self.axis_code or '',
            'item_code': self.item_code or '',
            'reverse': self.reverse,
            'scored': self.scored,
            'skip_to': self.skip_to or {},
        }
        # ⚠️ correct_option مفتاح إجابة — يظهر للمعلم فقط (شاشة المراجعة/التحليل)، أبداً للمستجيب
        if show_answers:
            data['correct_option'] = self.correct_option or ''
        return data


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
    # ═══ لجودة الردود بالتحليل الإحصائي (المرحلة 4) — nullable، فاضية للردود القديمة قبل هذا التحديث ═══
    started_at = db.Column(db.DateTime, nullable=True)  # وقت فتح المستجيب لشاشة الأسئلة (يُرسل من التطبيق)
    device_id = db.Column(db.String(100), nullable=True)  # معرّف الجهاز الثابت (نفس ApiService.getDeviceId بالتطبيق)

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
