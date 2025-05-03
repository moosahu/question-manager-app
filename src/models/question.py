# src/models/question.py

try:
    from src.extensions import db
except ImportError:
    # Fallback for direct execution or different structure
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

    # Foreign Key to Lesson
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)

    # Relationships
    options = db.relationship("Option", backref="question", lazy=True, cascade="all, delete-orphan")
    lesson = db.relationship("Lesson", lazy=True)

    def __repr__(self):
        return f"<Question {self.question_id}: {self.question_text[:30]}...>"

class Option(db.Model):
    __tablename__ = 'options'

    option_id = db.Column(db.Integer, primary_key=True)
    # --- FIX: Changed column name from 'text' to 'option_text' --- #
    option_text = db.Column(db.Text, nullable=True) 
    # ----------------------------------------------------------- #
    image_path = db.Column(db.String(255), nullable=True) 
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    
    # Foreign Key to Question (referencing the correct table and column name)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.question_id"), nullable=False)

    def __repr__(self):
        # --- FIX: Use option_text in repr if needed --- #
        return f"<Option {self.option_id} for Question {self.question_id}>"
        # Or: return f"<Option {self.option_id}: {self.option_text[:20]}...>"

