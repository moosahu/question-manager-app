"""
نموذج سجل التحديثات (ما الجديد)
"""
import json
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


class Changelog(db.Model):
    """سجل التحديثات — يُعرض للمستخدمين كـ 'ما الجديد؟'"""
    __tablename__ = 'changelogs'
    __table_args__ = {'extend_existing': True}

    id           = db.Column(db.Integer, primary_key=True)
    version      = db.Column(db.String(20), nullable=False)   # '1.0.9'
    entries      = db.Column(db.Text, nullable=False)          # JSON array of strings
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active    = db.Column(db.Boolean, default=True)

    def get_entries(self):
        try:
            return json.loads(self.entries)
        except Exception:
            return []

    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'entries': self.get_entries(),
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'is_active': self.is_active,
        }
