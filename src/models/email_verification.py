"""
نموذج التحقق من الإيميل - Email Verification Model
يحفظ رموز التحقق OTP للتسجيل الذاتي للطلاب والمعلمين
"""
from src.extensions import db
from datetime import datetime, timedelta
import random
import string


class EmailVerification(db.Model):
    """جدول رموز التحقق من الإيميل"""
    __tablename__ = 'email_verifications'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)  # رمز 6 أرقام
    
    # بيانات المستخدم المؤقتة
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    school = db.Column(db.String(100), nullable=True)
    grade = db.Column(db.String(50), nullable=True)
    
    # ✅ نوع الحساب (student أو teacher)
    account_type = db.Column(db.String(20), default='student')
    
    # حالة التحقق
    is_verified = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)  # عدد المحاولات الخاطئة
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # صلاحية 3 دقائق
    verified_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def generate_code():
        """توليد رمز عشوائي من 6 أرقام"""
        return ''.join(random.choices(string.digits, k=6))

    @staticmethod
    def create_verification(email, name, username, password_hash, 
                           phone=None, school=None, grade=None, account_type='student'):
        """إنشاء طلب تحقق جديد"""
        # حذف الطلبات السابقة لنفس الإيميل
        EmailVerification.query.filter_by(email=email, is_verified=False).delete()
        
        code = EmailVerification.generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=3)  # صلاحية 3 دقائق
        
        verification = EmailVerification(
            email=email,
            code=code,
            name=name,
            username=username,
            password_hash=password_hash,
            phone=phone,
            school=school,
            grade=grade,
            account_type=account_type,  # ✅ حفظ نوع الحساب
            expires_at=expires_at
        )
        
        db.session.add(verification)
        db.session.commit()
        
        return verification

    def is_expired(self):
        """التحقق من انتهاء صلاحية الرمز"""
        return datetime.utcnow() > self.expires_at

    def verify_code(self, code):
        """التحقق من صحة الرمز"""
        if self.is_expired():
            return False, 'انتهت صلاحية رمز التحقق'
        
        if self.attempts >= 5:
            return False, 'تجاوزت الحد الأقصى للمحاولات'
        
        if self.code != code:
            self.attempts += 1
            db.session.commit()
            remaining = 5 - self.attempts
            return False, f'رمز التحقق غير صحيح. متبقي {remaining} محاولات'
        
        self.is_verified = True
        self.verified_at = datetime.utcnow()
        db.session.commit()
        
        return True, 'تم التحقق بنجاح'

    @staticmethod
    def cleanup_expired():
        """حذف الرموز المنتهية الصلاحية"""
        expired = EmailVerification.query.filter(
            EmailVerification.expires_at < datetime.utcnow(),
            EmailVerification.is_verified == False
        ).delete()
        db.session.commit()
        return expired

    def to_dict(self):
        """تحويل لـ dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'username': self.username,
            'account_type': self.account_type,
            'is_verified': self.is_verified,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class RegistrationSettings(db.Model):
    """إعدادات التسجيل الذاتي"""
    __tablename__ = 'registration_settings'

    id = db.Column(db.Integer, primary_key=True)
    
    # ==================== إعدادات تسجيل الطلاب ====================
    is_registration_open = db.Column(db.Boolean, default=True)
    closed_message = db.Column(db.String(500), default='التسجيل مغلق حالياً، تواصل مع الإدارة')
    require_phone = db.Column(db.Boolean, default=False)
    require_school = db.Column(db.Boolean, default=False)
    auto_activate = db.Column(db.Boolean, default=True)
    
    # ==================== ✅ جديد: إعدادات تسجيل المعلمين ====================
    is_teacher_registration_open = db.Column(db.Boolean, default=False)
    teacher_closed_message = db.Column(db.String(500), default='تسجيل المعلمين مغلق حالياً، تواصل مع الإدارة')
    teacher_require_phone = db.Column(db.Boolean, default=True)
    teacher_require_school = db.Column(db.Boolean, default=True)
    teacher_auto_activate = db.Column(db.Boolean, default=False)
    
    # التواريخ
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, nullable=True)

    @staticmethod
    def get_settings():
        """جلب إعدادات التسجيل"""
        settings = RegistrationSettings.query.first()
        if not settings:
            # إنشاء إعدادات افتراضية
            settings = RegistrationSettings()
            db.session.add(settings)
            db.session.commit()
        return settings

    @staticmethod
    def update_settings(is_open=None, message=None, require_phone=None, 
                       require_school=None, auto_activate=None, admin_id=None,
                       # ✅ جديد: معاملات المعلمين
                       is_teacher_open=None, teacher_message=None,
                       teacher_require_phone=None, teacher_require_school=None,
                       teacher_auto_activate=None):
        """تحديث إعدادات التسجيل"""
        settings = RegistrationSettings.get_settings()
        
        # إعدادات الطلاب
        if is_open is not None:
            settings.is_registration_open = is_open
        if message is not None:
            settings.closed_message = message
        if require_phone is not None:
            settings.require_phone = require_phone
        if require_school is not None:
            settings.require_school = require_school
        if auto_activate is not None:
            settings.auto_activate = auto_activate
        
        # ✅ إعدادات المعلمين
        if is_teacher_open is not None:
            settings.is_teacher_registration_open = is_teacher_open
        if teacher_message is not None:
            settings.teacher_closed_message = teacher_message
        if teacher_require_phone is not None:
            settings.teacher_require_phone = teacher_require_phone
        if teacher_require_school is not None:
            settings.teacher_require_school = teacher_require_school
        if teacher_auto_activate is not None:
            settings.teacher_auto_activate = teacher_auto_activate
            
        if admin_id is not None:
            settings.updated_by = admin_id
        
        db.session.commit()
        return settings

    def to_dict(self):
        """تحويل لـ dictionary"""
        return {
            # إعدادات الطلاب
            'is_registration_open': self.is_registration_open,
            'closed_message': self.closed_message,
            'require_phone': self.require_phone,
            'require_school': self.require_school,
            'auto_activate': self.auto_activate,
            # ✅ إعدادات المعلمين
            'is_teacher_registration_open': self.is_teacher_registration_open,
            'teacher_closed_message': self.teacher_closed_message,
            'teacher_require_phone': self.teacher_require_phone,
            'teacher_require_school': self.teacher_require_school,
            'teacher_auto_activate': self.teacher_auto_activate,
            # عام
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
