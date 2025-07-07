"""
نموذج قاعدة البيانات لرموز Google Drive
"""

from datetime import datetime
from extensions import db

class GoogleDriveToken(db.Model):
    """نموذج رموز Google Drive في قاعدة البيانات"""
    
    __tablename__ = 'google_drive_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_type = db.Column(db.String(50), default='Bearer', nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    scope = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # العلاقة مع المستخدم
    user = db.relationship('User', backref=db.backref('google_drive_token', uselist=False, lazy=True))
    
    def __repr__(self):
        return f'<GoogleDriveToken user_id={self.user_id}>'
    
    def to_dict(self):
        """تحويل الرمز إلى قاموس"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token_type': self.token_type,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'scope': self.scope,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expired(self):
        """فحص إذا كان الرمز منتهي الصلاحية"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @staticmethod
    def get_by_user_id(user_id):
        """الحصول على رمز Google Drive للمستخدم"""
        return GoogleDriveToken.query.filter_by(user_id=user_id).first()
    
    @staticmethod
    def save_token(user_id, token_data):
        """حفظ أو تحديث رمز Google Drive"""
        existing_token = GoogleDriveToken.get_by_user_id(user_id)
        
        if existing_token:
            # تحديث الرمز الموجود
            existing_token.access_token = token_data.get('access_token')
            existing_token.refresh_token = token_data.get('refresh_token')
            existing_token.token_type = token_data.get('token_type', 'Bearer')
            existing_token.scope = token_data.get('scope')
            existing_token.updated_at = datetime.utcnow()
            
            # تحديث تاريخ انتهاء الصلاحية
            if 'expires_in' in token_data:
                expires_in = int(token_data['expires_in'])
                existing_token.expires_at = datetime.utcnow() + datetime.timedelta(seconds=expires_in)
            
            token = existing_token
        else:
            # إنشاء رمز جديد
            token = GoogleDriveToken(
                user_id=user_id,
                access_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_type=token_data.get('token_type', 'Bearer'),
                scope=token_data.get('scope')
            )
            
            # تحديد تاريخ انتهاء الصلاحية
            if 'expires_in' in token_data:
                expires_in = int(token_data['expires_in'])
                token.expires_at = datetime.utcnow() + datetime.timedelta(seconds=expires_in)
            
            db.session.add(token)
        
        db.session.commit()
        return token
    
    @staticmethod
    def delete_by_user_id(user_id):
        """حذف رمز Google Drive للمستخدم"""
        token = GoogleDriveToken.get_by_user_id(user_id)
        if token:
            db.session.delete(token)
            db.session.commit()
            return True
        return False

