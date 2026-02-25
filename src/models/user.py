from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
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
    email            = db.Column(db.String(120), unique=True, nullable=False)
    password_hash   = db.Column(db.String(256), nullable=False)  # Increased length for stronger hashes
    is_admin        = db.Column(db.Boolean, default=False)
    two_factor_auth = db.Column(db.Boolean, default=False, nullable=False)
    totp_secret     = db.Column(db.String(32), nullable=True)
    phone_number    = db.Column(db.String(20), nullable=True)  # للتحقق عبر SMS
    trusted_device_token = db.Column(db.String(128), nullable=True)  # توكن الجهاز الموثوق
    trusted_device_expires = db.Column(db.DateTime, nullable=True)   # تاريخ انتهاء التوكن

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"
