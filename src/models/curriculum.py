from .user import db # Import db from user.py or a central models init file

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    units = db.relationship('Unit', backref='course', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Course {self.name}>'

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    lessons = db.relationship('Lesson', backref='unit', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Unit {self.name}>'

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    questions = db.relationship('Question', backref='lesson', lazy=True) # Relationship to Question

    def __repr__(self):
        return f'<Lesson {self.name}>'

