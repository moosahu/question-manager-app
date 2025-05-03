# src/models/question.py

try:
    from src.extensions import db
except ImportError:
    from src.main import db

class Question(db.Model):
    __tablename__ = 'questions'

    question_id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    # --- Temporarily Commented Out --- #
    # explanation = db.Column(db.Text, nullable=True)
    # explanation_image_path = db.Column(db.String(255), nullable=True)
    # --------------------------------- #
    quiz_id = db.Column(db.Integer, nullable=True) # Assuming nullable, adjust if needed

    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)

    options = db.relationship("Option", backref="question", lazy=True, cascade="all, delete-orphan")
    lesson = db.relationship("Lesson", lazy=True)

    def __repr__(self):
        return f"<Question {self.question_id}: {self.question_text[:30]}...>"

class Option(db.Model):
    __tablename__ = 'options'

    option_id = db.Column(db.Integer, primary_key=True)
    option_text = db.Column(db.Text, nullable=True) 
    # --- FIX: Commented out image_path as it doesn't exist in DB --- #
    # image_path = db.Column(db.String(255), nullable=True) 
    # -------------------------------------------------------------- #
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    
    question_id = db.Column(db.Integer, db.ForeignKey("questions.question_id"), nullable=False)

    def __repr__(self):
        return f"<Option {self.option_id} for Question {self.question_id}>"

