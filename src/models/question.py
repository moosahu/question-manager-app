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

    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)

    # Cascade delete ensures options are deleted when a question is deleted
    options = db.relationship("Option", backref="question", lazy=True, cascade="all, delete-orphan")
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

