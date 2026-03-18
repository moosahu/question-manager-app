# src/models/curriculum.py
# ✅ Updated with Learning Content relationships

try:
    from src.extensions import db
except ImportError:
    from src.extensions import db 

class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    order_num = db.Column(db.Integer, default=0)
    show_in_bot = db.Column(db.Boolean, default=True, nullable=False)
    is_bank = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # العلاقات
    units = db.relationship('Unit', backref='course', lazy=True,
                           cascade="all, delete-orphan",
                           order_by="Unit.order_num")

    def __repr__(self):
        return f'<Course {self.name}>'

class Unit(db.Model):
    __tablename__ = 'unit'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order_num = db.Column(db.Integer, default=0)
    show_in_bot = db.Column(db.Boolean, default=True, nullable=False)
    
    # العلاقات
    lessons = db.relationship('Lesson', backref='unit', lazy=True,
                             cascade="all, delete-orphan",
                             order_by="Lesson.order_num")

    def __repr__(self):
        return f'<Unit {self.name}>'

class Lesson(db.Model):
    __tablename__ = 'lesson'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    order_num = db.Column(db.Integer, default=0)
    show_in_bot = db.Column(db.Boolean, default=True, nullable=False)
    
    # العلاقات
    questions = db.relationship("Question", back_populates="lesson", lazy=True)
    
    # ✅ جديد: العلاقات مع Learning Content
    # لا نحتاج تعريفها هنا لأنها معرفة في learning_content.py
    # لكن يمكننا الوصول إليها:
    # lesson.summary - الملخص
    # lesson.concept_map - خريطة المفاهيم
    # lesson.student_progress - تقدم الطلاب
    
    def has_content(self):
        """تحقق إذا الدرس له محتوى تعليمي"""
        return self.summary is not None or self.concept_map is not None
    
    def content_completion_percentage(self):
        """نسبة اكتمال المحتوى (ملخص + خريطة)"""
        count = 0
        if self.summary:
            count += 1
        if self.concept_map:
            count += 1
        return (count / 2) * 100 if count > 0 else 0

    def __repr__(self):
        return f'<Lesson {self.name}>'
