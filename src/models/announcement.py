from src.extensions import db
from datetime import datetime


class Announcement(db.Model):
    __tablename__ = 'announcements'

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text, nullable=True)
    images     = db.Column(db.JSON, default=list)   # قائمة روابط Cloudinary
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'title':      self.title,
            'body':       self.body or '',
            'images':     self.images or [],
            'is_active':  self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
