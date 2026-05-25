"""
Teacher Model - موديل المعلم
ضع هذا الملف في: src/models/teacher.py
"""
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from src.extensions import db
from src.utils.field_encryption import EncryptedString, make_email_hash
from datetime import datetime
import secrets
import string


class Teacher(db.Model, UserMixin):
    """جدول المعلمين"""
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    
    # البيانات الأساسية
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(EncryptedString(500), nullable=True)
    email_hash = db.Column(db.String(100), nullable=True, index=True)
    phone = db.Column(EncryptedString(500), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # معلومات إضافية
    school = db.Column(db.String(100), nullable=True)
    
    # حالة الحساب
    is_active = db.Column(db.Boolean, default=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # ملاحظات الأدمن
    notes = db.Column(db.Text, nullable=True)

    # كود الربط — الطالب يدخله للانضمام لهذا المعلم
    class_code = db.Column(db.String(10), unique=True, nullable=True)
    
    # Firebase Cloud Messaging Token
    fcm_token = db.Column(EncryptedString(1000), nullable=True)
    fcm_token_updated_at = db.Column(db.DateTime, nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)

    # بيانات الجهاز
    device_id = db.Column(EncryptedString(500), nullable=True)
    device_name = db.Column(db.String(255), nullable=True)
    last_device_login = db.Column(db.DateTime, nullable=True)
    session_token = db.Column(EncryptedString(1000), nullable=True)

    @staticmethod
    def generate_class_code():
        """توليد كود فريد من 6 أحرف/أرقام كبيرة"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(6))
            if not Teacher.query.filter_by(class_code=code).first():
                return code

    def ensure_class_code(self):
        """تأكد من وجود كود — أنشئه إذا لم يكن موجوداً"""
        if not self.class_code:
            self.class_code = Teacher.generate_class_code()
        return self.class_code

    def set_email(self, email):
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

    def update_device_info(self, device_id, device_name=None):
        """تحديث معلومات الجهاز عند تسجيل الدخول"""
        self.device_id = device_id
        self.device_name = device_name or 'جهاز غير معروف'
        self.last_device_login = datetime.utcnow()
        db.session.commit()

    def clear_device_info(self):
        """إزالة ربط الجهاز عند تسجيل الخروج"""
        self.device_id = None
        self.device_name = None
        self.last_device_login = None
        self.session_token = None
        db.session.commit()

    def is_same_device(self, device_id):
        """التحقق من أن الجهاز هو نفسه المسجل"""
        if not self.device_id:
            return True
        return self.device_id == device_id

    def has_registered_device(self):
        """التحقق من وجود جهاز مسجل"""
        return self.device_id is not None

    @staticmethod
    def get_active_teachers():
        """جلب المعلمين المفعلين"""
        return Teacher.query.filter_by(is_active=True).all()

    @staticmethod
    def get_all_teachers():
        """جلب جميع المعلمين"""
        return Teacher.query.order_by(Teacher.created_at.desc()).all()

    @staticmethod
    def search_teachers(query):
        """البحث عن معلمين"""
        search = f"%{query}%"
        return Teacher.query.filter(
            db.or_(
                Teacher.name.ilike(search),
                Teacher.username.ilike(search),
                Teacher.phone.ilike(search),
                Teacher.school.ilike(search)
            )
        ).all()

    def update_fcm_token(self, token):
        """تحديث FCM Token"""
        self.fcm_token = token
        self.fcm_token_updated_at = datetime.utcnow()
        db.session.commit()

    def clear_fcm_token(self):
        """حذف FCM Token"""
        self.fcm_token = None
        self.fcm_token_updated_at = None
        db.session.commit()

    @staticmethod
    def get_teachers_with_fcm_tokens():
        """جلب المعلمين الذين لديهم FCM Tokens"""
        return Teacher.query.filter(
            Teacher.is_active == True,
            Teacher.fcm_token.isnot(None)
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
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'fcm_token': self.fcm_token,
            'fcm_token_updated_at': self.fcm_token_updated_at.isoformat() if self.fcm_token_updated_at else None,
            'device_id': self.device_id,
            'device_name': self.device_name,
            'last_device_login': self.last_device_login.isoformat() if self.last_device_login else None,
        }

    def __repr__(self):
        return f"<Teacher {self.username}>"
