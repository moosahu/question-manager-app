from datetime import datetime
try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from main import db


class AuditLog(db.Model):
    """سجل نشاط الادمن - يتتبع العمليات المهمة"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    description = db.Column(db.String(512), nullable=False)
    admin_name = db.Column(db.String(128), default='الادمن')
    target_type = db.Column(db.String(64))      # student / teacher / question
    target_id = db.Column(db.Integer)
    extra_data = db.Column(db.Text)             # JSON إضافي
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @classmethod
    def log(cls, action: str, description: str, admin_name: str = 'الادمن',
            target_type: str = None, target_id: int = None):
        """دالة مساعدة لإضافة سجل"""
        try:
            entry = cls(
                action=action,
                description=description,
                admin_name=admin_name,
                target_type=target_type,
                target_id=target_id,
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def __repr__(self):
        return f'<AuditLog {self.action}: {self.description[:40]}>'
