"""
نموذج سجل النسخ الاحتياطي
"""
from datetime import datetime

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from extensions import db


class BackupLog(db.Model):
    """سجل عمليات النسخ الاحتياطي"""
    __tablename__ = 'backup_logs'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status          = db.Column(db.String(10), nullable=False)   # 'success' | 'failed'
    destination     = db.Column(db.String(20))                   # 'google_drive' | 'local'
    file_size       = db.Column(db.Integer)                      # بالبايت
    error_msg       = db.Column(db.Text)                         # سبب الفشل
    questions_count = db.Column(db.Integer)                      # عدد الأسئلة المنسوخة
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id':              self.id,
            'status':          self.status,
            'destination':     self.destination,
            'file_size':       self.file_size,
            'error_msg':       self.error_msg,
            'questions_count': self.questions_count,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def log(cls, user_id, result_dict):
        """يُستدعى مباشرة بعد perform_backup_for_user لحفظ نتيجة النسخ"""
        try:
            success = result_dict.get('success', False)
            entry = cls(
                user_id         = user_id,
                status          = 'success' if success else 'failed',
                destination     = result_dict.get('destination'),
                file_size       = int(result_dict['size']) if result_dict.get('size') else None,
                error_msg       = result_dict.get('error') if not success else None,
                questions_count = result_dict.get('questions_count'),
            )
            db.session.add(entry)
            db.session.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"فشل في حفظ سجل النسخ: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    @classmethod
    def get_user_logs(cls, user_id, limit=50):
        """جلب آخر سجلات المستخدم"""
        return (cls.query
                .filter_by(user_id=user_id)
                .order_by(cls.created_at.desc())
                .limit(limit)
                .all())
