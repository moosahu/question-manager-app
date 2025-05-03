from .user import db # Import db
from .curriculum import Lesson # Import Lesson for ForeignKey

class Question(db.Model):
    # Make sure table name matches if it's different (usually inferred correctly)
    # __tablename__ = 'questions' 

    # Match column names from DBeaver
    question_id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False) # Renamed from 'text'
    image_url = db.Column(db.String(255), nullable=True) # Renamed from 'image_path'
    
    # Add column seen in DBeaver (assuming nullable integer)
    quiz_id = db.Column(db.Integer, nullable=True) 
    
    # Keep columns from original model that are used in code
    explanation = db.Column(db.Text, nullable=True) 
    explanation_image_path = db.Column(db.String(255), nullable=True)
    
    # Foreign Key to Lesson (assuming 'lesson' table has 'id' as PK)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    
    # Relationship to Option (adjust foreign_keys if needed due to PK rename)
    options = db.relationship("Option", foreign_keys="Option.question_id", backref="question", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Question {self.question_id}>"

class Option(db.Model):
    # __tablename__ = 'options' # Make sure table name matches if different

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=True) 
    image_path = db.Column(db.String(255), nullable=True) # Keep as image_path if Option table uses this
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    
    # Foreign Key to Question (referencing the renamed primary key)
    question_id = db.Column(db.Integer, db.ForeignKey("question.question_id"), nullable=False)

    def __repr__(self):
        return f"<Option {self.id} for Question {self.question_id}>"

