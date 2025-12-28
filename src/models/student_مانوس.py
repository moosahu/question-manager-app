from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from src.extensions import db
from datetime import datetime


class Student(db.Model, UserMixin):
    """جدول الطلاب - يضيفهم الأدمن يدوياً"""
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True)
    
    # البيانات الأساسية
    name = db.Column(db.String(100), nullable=False)  # اسم الطالب
    username = db.Column(db.String(80), unique=True, nullable=False)  # اسم المستخدم للدخول
    email = db.Column(db.String(120), unique=True, nullable=True)  # البريد (اختياري)
    phone = db.Column(db.String(20), nullable=True)  # رقم الجوال
    password_hash = db.Column(db.String(256), nullable=False)
    
    # معلومات إضافية
    school = db.Column(db.String(100), nullable=True)  # المدرسة
    grade = db.Column(db.String(50), nullable=True)  # الصف (أول/ثاني/ثالث ثانوي)
    
    # حالة الحساب
    is_active = db.Column(db.Boolean, default=True)  # الحساب مفعل؟
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # ملاحظات الأدمن
    notes = db.Column(db.Text, nullable=True)

    def set_password(self, password):
        """تشفير كلمة المرور"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """التحقق من كلمة المرور"""
        return check_password_hash(self.password_hash, password)

    def update_last_login(self):
        """تحديث وقت آخر تسجيل دخول"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def get_active_students():
        """جلب الطلاب المفعلين"""
        return Student.query.filter_by(is_active=True).all()

    @staticmethod
    def get_all_students():
        """جلب جميع الطلاب"""
        return Student.query.order_by(Student.created_at.desc()).all()

    @staticmethod
    def search_students(query):
        """البحث عن طلاب"""
        search = f"%{query}%"
        return Student.query.filter(
            db.or_(
                Student.name.ilike(search),
                Student.username.ilike(search),
                Student.phone.ilike(search),
                Student.school.ilike(search)
            )
        ).all()

    def to_dict(self):
        """تحويل لـ dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'school': self.school,
            'grade': self.grade,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

    def __repr__(self):
        return f"<Student {self.username}>"
