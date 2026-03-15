"""
إعدادات اختيار التصميم للطلاب (إعداد عام يحدده الأدمن)
"""
from src.extensions import db


class StudentDesignSettings(db.Model):
    __tablename__ = 'student_design_settings'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    # هل الميزة مفعّلة أصلاً (الأدمن يقدر يوقفها بالكامل)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    # التصاميم المسموحة للطلاب "1,2,5,16,17" — null = الكل
    allowed_designs = db.Column(db.String(200), nullable=True)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @classmethod
    def get(cls):
        """يجيب الإعداد الوحيد — ينشئه إذا ما كان موجوداً"""
        row = cls.query.first()
        if not row:
            row = cls(enabled=False, allowed_designs=None)
            db.session.add(row)
            db.session.commit()
        return row

    def allowed_list(self):
        """يرجع قائمة int أو None (= كل التصاميم)"""
        if not self.allowed_designs:
            return None
        try:
            return [int(x.strip()) for x in self.allowed_designs.split(',') if x.strip()]
        except ValueError:
            return None
