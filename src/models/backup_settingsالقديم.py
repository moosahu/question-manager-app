"""
نموذج إعدادات النسخ الاحتياطي
"""
from datetime import datetime

# استيراد db من extensions
try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        # إذا فشل الاستيراد، سنحاول استيراد من المسار المحلي
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from extensions import db

class BackupSettings(db.Model):
    """نموذج إعدادات النسخ الاحتياطي للمستخدمين"""
    __tablename__ = 'backup_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # إعدادات النسخ الاحتياطي
    auto_backup_enabled = db.Column(db.Boolean, default=False, nullable=False)
    backup_frequency = db.Column(db.String(20), default='daily', nullable=False)  # daily, weekly, monthly
    backup_time = db.Column(db.String(5), default='02:00', nullable=False)  # HH:MM format
    max_backups = db.Column(db.Integer, default=10, nullable=False)
    backup_destination = db.Column(db.String(20), default='local', nullable=False)  # local, google_drive
    
    # معلومات إضافية
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # علاقة مع المستخدم
    user = db.relationship('User', backref=db.backref('backup_settings', uselist=False))
    
    def __repr__(self):
        return f'<BackupSettings {self.user_id}: {self.backup_destination}>'
    
    def to_dict(self):
        """تحويل الإعدادات إلى قاموس"""
        return {
            'auto_backup_enabled': self.auto_backup_enabled,
            'backup_frequency': self.backup_frequency,
            'backup_time': self.backup_time,
            'max_backups': self.max_backups,
            'backup_destination': self.backup_destination,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_user_settings(cls, user_id):
        """جلب إعدادات المستخدم أو إنشاء إعدادات افتراضية"""
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            # إنشاء إعدادات افتراضية
            settings = cls(
                user_id=user_id,
                auto_backup_enabled=False,
                backup_frequency='daily',
                backup_time='02:00',
                max_backups=10,
                backup_destination='local'
            )
            db.session.add(settings)
            db.session.commit()
        return settings
    
    @classmethod
    def update_user_settings(cls, user_id, settings_data):
        """تحديث إعدادات المستخدم"""
        settings = cls.get_user_settings(user_id)
        
        # تحديث الحقول المرسلة فقط
        for key, value in settings_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        return settings

