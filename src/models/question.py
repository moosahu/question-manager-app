from .user import db # Import db
from .curriculum import Lesson # Import Lesson for ForeignKey

class Question(db.Model):
    __tablename__ = 'questions'

    question_id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    quiz_id = db.Column(db.Integer, nullable=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    
    # --- Temporarily Commented Out --- #
    # explanation = db.Column(db.Text, nullable=True) 
    # explanation_image_path = db.Column(db.String(255), nullable=True)
    # --------------------------------- #
    
    options = db.relationship("Option", foreign_keys="Option.question_id", backref="question", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Question {self.question_id}>"

class Option(db.Model):
    __tablename__ = 'options'

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=True) 
    image_path = db.Column(db.String(255), nullable=True)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.question_id"), nullable=False)

    def __repr__(self):
        return f"<Option {self.id} for Question {self.question_id}>"

