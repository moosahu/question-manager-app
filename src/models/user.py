from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import secrets
import string
# Import db from the central extensions file
# أضف هذا بعد استيراد flask_login
try:
    from src.utils.notification_system import UserNotifications, SystemNotifications
    notifications_available = True
except ImportError:
    try:
        from utils.notification_system import UserNotifications, SystemNotifications
        notifications_available = True
    except ImportError:
        print("Warning: Could not import notification system for users")
        UserNotifications = None
        SystemNotifications = None
        notifications_available = False
from src.extensions import db


class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(80), unique=True, nullable=False)
    full_name       = db.Column(db.String(100), nullable=True)
    email            = db.Column(db.String(120), unique=True, nullable=False)
    password_hash   = db.Column(db.String(256), nullable=False)  # Increased length for stronger hashes
    is_admin        = db.Column(db.Boolean, default=False)
    two_factor_auth = db.Column(db.Boolean, default=False, nullable=False)
    totp_secret     = db.Column(db.String(32), nullable=True)
    phone_number    = db.Column(db.String(20), nullable=True)  # للتحقق عبر SMS
    trusted_device_token = db.Column(db.String(128), nullable=True)  # توكن الجهاز الموثوق
    trusted_device_expires = db.Column(db.DateTime, nullable=True)   # تاريخ انتهاء التوكن
    fcm_token = db.Column(db.String(500), nullable=True)  # FCM token للإشعارات في التطبيق

    # كود ربط الطلاب بالأدمن — نفس منطق المعلمين
    class_code = db.Column(db.String(10), unique=True, nullable=True)

    @staticmethod
    def generate_class_code():
        """توليد كود فريد من 6 أحرف/أرقام"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(6))
            if not User.query.filter_by(class_code=code).first():
                return code

    def ensure_class_code(self):
        """تأكد من وجود كود — أنشئه إذا لم يكن موجوداً"""
        if not self.class_code:
            self.class_code = User.generate_class_code()
        return self.class_code

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"
