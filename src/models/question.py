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
    # Allow text to be nullable to support image-only options
    text = db.Column(db.Text, nullable=True) # Option text, potentially with equation markup
    image_path = db.Column(db.String(255), nullable=True) # Path to optional option image
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)

    # Add a check constraint to ensure either text or image_path is not null
    # This might require specific syntax depending on the DB (e.g., PostgreSQL)
    # For simplicity with Alembic, we might add this manually or in the migration script if needed.
    # __table_args__ = (db.CheckConstraint("text IS NOT NULL OR image_path IS NOT NULL", name="ck_option_content"),)

    def __repr__(self):
        return f"<Option {self.id} for Question {self.question_id}>"

