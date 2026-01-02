"""
نموذج إعادة تعيين كلمة المرور - Password Reset Model
يحفظ رموز التحقق لإعادة تعيين كلمة المرور
"""
from src.extensions import db
from datetime import datetime, timedelta
import random
import string


class PasswordReset(db.Model):
    """جدول رموز إعادة تعيين كلمة المرور"""
    __tablename__ = 'password_resets'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)  # رمز 6 أرقام
    
    # حالة التحقق
    is_used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)  # عدد المحاولات الخاطئة
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # صلاحية 10 دقائق
    used_at = db.Column(db.DateTime, nullable=True)

    # علاقة مع جدول الطلاب
    student = db.relationship('Student', backref='password_resets')

    @staticmethod
    def generate_code():
        """توليد رمز عشوائي من 6 أرقام"""
        return ''.join(random.choices(string.digits, k=6))

    @staticmethod
    def create_reset_request(student_id, email):
        """إنشاء طلب إعادة تعيين جديد"""
        # حذف الطلبات السابقة غير المستخدمة لنفس الطالب
        PasswordReset.query.filter_by(
            student_id=student_id, 
            is_used=False
        ).delete()
        
        code = PasswordReset.generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # صلاحية 10 دقائق
        
        reset_request = PasswordReset(
            student_id=student_id,
            email=email,
            code=code,
            expires_at=expires_at
        )
        
        db.session.add(reset_request)
        db.session.commit()
        
        return reset_request

    def is_expired(self):
        """التحقق من انتهاء صلاحية الرمز"""
        return datetime.utcnow() > self.expires_at

    def verify_code(self, code):
        """التحقق من صحة الرمز"""
        if self.is_used:
            return False, 'تم استخدام هذا الرمز مسبقاً'
        
        if self.is_expired():
            return False, 'انتهت صلاحية رمز التحقق'
        
        if self.attempts >= 5:
            return False, 'تجاوزت الحد الأقصى للمحاولات'
        
        if self.code != code:
            self.attempts += 1
            db.session.commit()
            remaining = 5 - self.attempts
            return False, f'رمز التحقق غير صحيح. متبقي {remaining} محاولات'
        
        return True, 'الرمز صحيح'

    def mark_as_used(self):
        """وضع علامة على الرمز كمستخدم"""
        self.is_used = True
        self.used_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def cleanup_expired():
        """حذف الرموز المنتهية الصلاحية"""
        expired = PasswordReset.query.filter(
            PasswordReset.expires_at < datetime.utcnow(),
            PasswordReset.is_used == False
        ).delete()
        db.session.commit()
        return expired

    def to_dict(self):
        """تحويل لـ dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'student_id': self.student_id,
            'is_used': self.is_used,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
