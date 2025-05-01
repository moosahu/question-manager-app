from .user import db # Import db
from .curriculum import Lesson # Import Lesson for ForeignKey

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False) # Supports longer text, potentially with equation markup
    image_path = db.Column(db.String(255), nullable=True) # Path to optional question image
    explanation = db.Column(db.Text, nullable=True) # Explanation text
    explanation_image_path = db.Column(db.String(255), nullable=True) # Path to optional explanation image
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    options = db.relationship("Option", backref="question", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Question {self.id}>"

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False) # Option text, potentially with equation markup
    image_path = db.Column(db.String(255), nullable=True) # Path to optional option image
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)

    def __repr__(self):
        return f"<Option {self.id} for Question {self.question_id}>"

