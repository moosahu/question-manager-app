# src/models/curriculum.py

try:
    from src.extensions import db
except ImportError:
    # Fallback for direct execution or different structure
    # Ensure this import points to your actual db instance
    # Maybe from .user import db or from ..extensions import db
    # Adjust the import based on your project structure
    # Assuming db is accessible via src.extensions
    from src.extensions import db 

class Course(db.Model):
    __tablename__ = 'course' # Explicit table name is good practice
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    units = db.relationship('Unit', backref='course', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Course {self.name}>'

class Unit(db.Model):
    __tablename__ = 'unit' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    lessons = db.relationship('Lesson', backref='unit', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Unit {self.name}>'

class Lesson(db.Model):
    __tablename__ = 'lesson' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    # --- FIX: Removed conflicting backref --- #
    questions = db.relationship("Question", back_populates="lesson", lazy=True) # Relationship to Question
    # ---------------------------------------- #

    def __repr__(self):
        return f'<Lesson {self.name}>'

