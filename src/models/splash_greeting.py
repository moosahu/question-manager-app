from src.extensions import db
from datetime import datetime, timedelta


class SplashGreeting(db.Model):
    """
    مناسبة (صورة أو فيديو) تظهر ملء الشاشة فوق شاشة السبلاش عند فتح التطبيق —
    قبل التحقق من تسجيل الدخول، لكل مستخدم. تُدار بالكامل من لوحة التحكم
    بدون أي رفع جديد للمتجر: التطبيق ثابت، والمحتوى (media_url) يتغيّر من هنا فقط.
    """
    __tablename__ = 'splash_greetings'

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)  # وصف داخلي للأدمن فقط، ما يظهر للطالب
    media_type = db.Column(db.String(10), nullable=False, default='image')  # image / video
    media_url  = db.Column(db.Text, nullable=False)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'title':      self.title,
            'media_type': self.media_type,
            'media_url':  self.media_url,
            'is_active':  self.is_active,
            'created_at': (self.created_at + timedelta(hours=3)).isoformat() if self.created_at else None,
        }
