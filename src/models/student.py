from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from src.extensions import db
from src.utils.field_encryption import EncryptedString, make_email_hash
from datetime import datetime


class Student(db.Model, UserMixin):
    """جدول الطلاب - يضيفهم الأدمن يدوياً"""
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    
    # البيانات الأساسية
    name = db.Column(db.String(100), nullable=False)  # اسم الطالب
    username = db.Column(db.String(80), unique=True, nullable=False)  # اسم المستخدم للدخول
    email = db.Column(EncryptedString(500), nullable=True)
    email_hash = db.Column(db.String(100), nullable=True, index=True)
    phone = db.Column(EncryptedString(500), nullable=True)
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
    
    # Firebase Cloud Messaging Token
    fcm_token = db.Column(EncryptedString(1000), nullable=True)
    fcm_token_updated_at = db.Column(db.DateTime, nullable=True)  # آخر تحديث للـ FCM Token

    # ✅ اختبار التصاميم — الأدمن يفعّل لطلاب محددين
    design_tester = db.Column(db.Boolean, default=False)       # هل مسموح له بزر التصاميم؟
    allowed_designs = db.Column(db.String(100), nullable=True) # "1,3,5" أو null=الكل

    # ✅ جديد: بيانات الجهاز للتسجيل من جهاز واحد
    device_id = db.Column(EncryptedString(500), nullable=True)
    device_name = db.Column(db.String(255), nullable=True)
    last_device_login = db.Column(db.DateTime, nullable=True)
    session_token = db.Column(EncryptedString(1000), nullable=True)

    def set_email(self, email):
        """يحفظ الإيميل مشفراً ويحدّث الـ hash للبحث"""
        self.email = email
        self.email_hash = make_email_hash(email)

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

    # ✅ جديد: تحديث معلومات الجهاز
    def update_device_info(self, device_id, device_name=None):
        """تحديث معلومات الجهاز عند تسجيل الدخول"""
        self.device_id = device_id
        self.device_name = device_name or 'جهاز غير معروف'
        self.last_device_login = datetime.utcnow()
        db.session.commit()

    # ✅ جديد: إزالة ربط الجهاز
    def clear_device_info(self):
        """إزالة ربط الجهاز عند تسجيل الخروج"""
        self.device_id = None
        self.device_name = None
        self.last_device_login = None
        self.session_token = None
        db.session.commit()

    # ✅ جديد: التحقق من الجهاز
    def is_same_device(self, device_id):
        """التحقق من أن الجهاز هو نفسه المسجل"""
        if not self.device_id:
            return True  # لا يوجد جهاز مسجل
        return self.device_id == device_id

    # ✅ جديد: هل الجهاز مسجل؟
    def has_registered_device(self):
        """التحقق من وجود جهاز مسجل"""
        return self.device_id is not None

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

    def update_fcm_token(self, token):
        """تحديث FCM Token"""
        self.fcm_token = token
        self.fcm_token_updated_at = datetime.utcnow()
        db.session.commit()

    def clear_fcm_token(self):
        """حذف FCM Token (عند تسجيل الخروج)"""
        self.fcm_token = None
        self.fcm_token_updated_at = None
        db.session.commit()

    @staticmethod
    def get_students_with_fcm_tokens():
        """جلب الطلاب الذين لديهم FCM Tokens"""
        return Student.query.filter(
            Student.is_active == True,
            Student.fcm_token.isnot(None)
        ).all()

    @staticmethod
    def get_students_by_grade(grade):
        """جلب الطلاب حسب الصف"""
        return Student.query.filter_by(grade=grade, is_active=True).all()

    # ✅ جديد: جلب الطلاب الذين لديهم أجهزة مسجلة
    @staticmethod
    def get_students_with_devices():
        """جلب الطلاب الذين لديهم أجهزة مسجلة"""
        return Student.query.filter(
            Student.device_id.isnot(None)
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
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'fcm_token': self.fcm_token,
            'fcm_token_updated_at': self.fcm_token_updated_at.isoformat() if self.fcm_token_updated_at else None,
            # ✅ جديد: معلومات الجهاز
            'device_id': self.device_id,
            'device_name': self.device_name,
            'last_device_login': self.last_device_login.isoformat() if self.last_device_login else None,
            # اختبار التصاميم
            'design_tester': self.design_tester or False,
            'allowed_designs': self.allowed_designs,
        }

    def __repr__(self):
        return f"<Student {self.username}>"
