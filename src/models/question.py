# src/models/question.py (Updated)

try:
    from src.extensions import db
except ImportError:
    # Fallback if running in a different structure or directly
    try:
        from extensions import db
    except ImportError:
        try:
            from main import db # Adjust if your db instance is elsewhere
        except ImportError:
            print("Error: Database object 'db' could not be imported.")
            raise

class Question(db.Model):
    __tablename__ = 'questions'

    question_id = db.Column(db.Integer, primary_key=True)
    # Make question_text nullable to allow image-only questions
    question_text = db.Column(db.Text, nullable=True) 
    image_url = db.Column(db.String(255), nullable=True)
    # quiz_id = db.Column(db.Integer, nullable=True) # Assuming nullable, adjust if needed
    
    # إضافة حقل الشرح وصورة الشرح
    explanation = db.Column(db.Text, nullable=True)
    explanation_image_path = db.Column(db.String(255), nullable=True)
    
    # حقل منع السؤال من الظهور في المنهج/الوحدة/الدرس
    is_blocked = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # بنك الأسئلة — مخصص للأدمن فقط، لا يظهر في التفاعلي
    is_bank = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # شرح الفيديو — مفصّل للاستخدام في توليد الفيديو، لا يظهر للطالب
    video_explanation = db.Column(db.Text, nullable=True)

    # فيديو الشرح — يولَّد بالذكاء الاصطناعي ويُرفع على YouTube
    video_url    = db.Column(db.String(500), nullable=True)   # يوتيوب
    r2_video_url = db.Column(db.String(500), nullable=True)   # Cloudflare R2 (للتطبيق)
    video_status = db.Column(db.String(20), default='none', nullable=True)
    # video_status: none | generating | ready | failed

    # ==================== الحقول الجديدة ====================
    # مستوى الصعوبة: easy (سهل), medium (متوسط), hard (صعب)
    difficulty = db.Column(db.String(20), default='medium', nullable=False, index=True)

    # مستوى بلوم (أهداف التعلم):
    # remember (تذكر), understand (فهم), apply (تطبيق),
    # analyze (تحليل), evaluate (تقويم), create (إبداع)
    bloom_level = db.Column(db.String(30), default='remember', nullable=False, index=True)

    # مراجعة التصنيف من قِبل المعلم: True = تأكّد المعلم، False = لم يُراجَع بعد
    human_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # القانون الكيميائي المرتبط بالسؤال — يُعبأ بالذكاء الاصطناعي أو يدوياً
    formula_key = db.Column(db.String(120), nullable=True, index=True)
    # =========================================================

    # ================ نوع السؤال (أنواع جديدة غير MCQ) ================
    # mcq (افتراضي) | true_false | fill_blank | matching | essay
    # لا تظهر الأنواع غير mcq أبداً في تطبيق الطالب — للاستخدام في الويب/الامتحانات فقط
    question_type = db.Column(db.String(20), default='mcq', nullable=False, index=True)

    # إكمال الفراغ
    fill_blank_answer = db.Column(db.String(255), nullable=True)
    fill_blank_alt_answers = db.Column(db.JSON, nullable=True)  # ["إجابة بديلة 1", ...]

    # مقالية — إجابة نموذجية مرجعية للمعلم فقط (بدون تصحيح آلي)
    essay_model_answer = db.Column(db.Text, nullable=True)
    # =========================================================

    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id", ondelete="CASCADE"), nullable=False)

    # Cascade delete ensures options are deleted when a question is deleted
    options = db.relationship("Option", backref="question", lazy=True, cascade="all, delete-orphan")
    matching_pairs = db.relationship("MatchingPair", backref="question", lazy=True,
                                      cascade="all, delete-orphan",
                                      order_by="MatchingPair.order_num")
    lesson = db.relationship("Lesson", back_populates='questions', lazy=True) # Eager loading might be better if lesson is always accessed

    def __repr__(self):
        text_preview = self.question_text[:30] + '...' if self.question_text and len(self.question_text) > 30 else self.question_text
        return f"<Question {self.question_id}: {text_preview or '[Image Question]'}>"

class Option(db.Model):
    __tablename__ = 'options'

    option_id = db.Column(db.Integer, primary_key=True)
    # Allow nullable text for image-only options
    option_text = db.Column(db.Text, nullable=True) 
    # Add image_url field for option images
    image_url = db.Column(db.String(255), nullable=True) 
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    
    question_id = db.Column(db.Integer, db.ForeignKey("questions.question_id"), nullable=False)

    def __repr__(self):
        return f"<Option {self.option_id} for Question {self.question_id}>"


class MatchingPair(db.Model):
    __tablename__ = 'matching_pairs'

    pair_id = db.Column(db.Integer, primary_key=True)
    left_text = db.Column(db.Text, nullable=True)
    left_image_url = db.Column(db.String(255), nullable=True)
    right_text = db.Column(db.Text, nullable=True)
    right_image_url = db.Column(db.String(255), nullable=True)
    order_num = db.Column(db.Integer, default=0)

    question_id = db.Column(db.Integer, db.ForeignKey("questions.question_id"), nullable=False)

    def __repr__(self):
        return f"<MatchingPair {self.pair_id} for Question {self.question_id}>"

