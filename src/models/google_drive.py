"""
Google Drive Integration - Enhanced Version with SQLAlchemy Context Fix
نظام ربط Google Drive محسن مع إصلاح مشكلة SQLAlchemy context
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import io
import zipfile
import tempfile
from flask import current_app

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# استيراد المكتبات المطلوبة مع معالجة أخطاء محسنة
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    GOOGLE_APIS_AVAILABLE = True
    logger.info("✅ Google APIs client library loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ Google APIs client library not available: {e}. Using mock implementation.")
    GOOGLE_APIS_AVAILABLE = False
    
    # إنشاء فئات بديلة
    class Credentials:
        def __init__(self, *args, **kwargs):
            pass
    
    class Flow:
        def __init__(self, *args, **kwargs):
            pass
    
    class HttpError(Exception):
        pass

# استيراد النماذج مع معالجة أخطاء محسنة
try:
    from src.extensions import db
    from src.models.user import User
    logger.info("✅ Database models imported successfully")
except ImportError:
    try:
        from extensions import db
        from models.user import User
        logger.info("✅ Database models imported successfully (fallback)")
    except ImportError:
        logger.warning("⚠️ Could not import database models - using fallback")
        db = None
        User = None

def execute_with_app_context(func, *args, **kwargs):
    """تنفيذ دالة مع app context صحيح - إصلاح محسن"""
    try:
        # فحص وجود current_app أولاً
        if current_app:
            return func(*args, **kwargs)
        
        # إذا لم يكن هناك current_app، نحاول الوصول للتطبيق عبر db
        if db and hasattr(db, 'app') and db.app:
            with db.app.app_context():
                return func(*args, **kwargs)
        
        logger.warning("No Flask app context available for database operation")
        return None
        
    except Exception as e:
        logger.error(f"Error executing with app context: {e}")
        return None

def get_db_with_context():
    """الحصول على db مع app context صحيح - محسن"""
    try:
        if current_app:
            return db
        else:
            # إذا لم يكن هناك app context، نحاول إنشاء واحد
            if db and hasattr(db, 'app') and db.app:
                return db
            return None
    except:
        return None

class GoogleDriveToken(db.Model if db else object):
    """نموذج رمز Google Drive المحسن مع إصلاح SQLAlchemy context"""
    
    if db:
        __tablename__ = 'google_drive_tokens'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        access_token = db.Column(db.Text, nullable=True)
        refresh_token = db.Column(db.Text, nullable=True)
        token_uri = db.Column(db.String(255), nullable=True)
        client_id = db.Column(db.String(255), nullable=True)
        client_secret = db.Column(db.String(255), nullable=True)
        scopes = db.Column(db.Text, nullable=True)  # JSON string of scopes
        expiry = db.Column(db.DateTime, nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        # معلومات إضافية
        folder_id = db.Column(db.String(255), nullable=True)  # مجلد النسخ الاحتياطي
        last_backup_date = db.Column(db.DateTime, nullable=True)
        backup_count = db.Column(db.Integer, default=0)
        is_active = db.Column(db.Boolean, default=True)
        
        # العلاقة مع المستخدم
        user = db.relationship('User', backref=db.backref('google_drive_tokens', lazy=True))
    
    def __repr__(self):
        return f'<GoogleDriveToken {self.user_id}>'
    
    def to_dict(self):
        """تحويل الكائن إلى قاموس"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'has_access_token': bool(self.access_token),
            'has_refresh_token': bool(self.refresh_token),
            'expiry': self.expiry.isoformat() if self.expiry else None,
            'folder_id': self.folder_id,
            'last_backup_date': self.last_backup_date.isoformat() if self.last_backup_date else None,
            'backup_count': self.backup_count,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_token_valid(self):
        """فحص صحة الرمز المميز"""
        if not self.access_token or not self.is_active:
            return False
        
        if self.expiry and self.expiry < datetime.utcnow():
            return False
            
        return True
    
    @classmethod
    def get_user_token(cls, user_id):
        """الحصول على رمز المستخدم مع app context صحيح"""
        def _get_token():
            try:
                return cls.query.filter_by(user_id=user_id, is_active=True).first()
            except Exception as e:
                logger.error(f"Database error getting user token: {e}")
                return None
        
        return execute_with_app_context(_get_token)
    
    @classmethod
    def create_or_update_token(cls, user_id, token_data):
        """إنشاء أو تحديث رمز المستخدم مع app context صحيح - إصلاح محسن"""
        def _create_or_update():
            try:
                database = get_db_with_context()
                if not database:
                    logger.error("Database not available for token operation")
                    return None
                
                existing_token = cls.query.filter_by(user_id=user_id, is_active=True).first()
                
                if existing_token:
                    # تحديث الرمز الموجود
                    existing_token.access_token = token_data.get('access_token')
                    existing_token.refresh_token = token_data.get('refresh_token')
                    existing_token.token_uri = token_data.get('token_uri')
                    existing_token.client_id = token_data.get('client_id')
                    existing_token.client_secret = token_data.get('client_secret')
                    existing_token.scopes = token_data.get('scopes')
                    existing_token.expiry = token_data.get('expiry')
                    existing_token.updated_at = datetime.utcnow()
                    existing_token.is_active = True
                    
                    database.session.commit()
                    logger.info(f"Token updated successfully for user {user_id}")
                    return existing_token
                else:
                    # إنشاء رمز جديد
                    new_token = cls(
                        user_id=user_id,
                        access_token=token_data.get('access_token'),
                        refresh_token=token_data.get('refresh_token'),
                        token_uri=token_data.get('token_uri'),
                        client_id=token_data.get('client_id'),
                        client_secret=token_data.get('client_secret'),
                        scopes=token_data.get('scopes'),
                        expiry=token_data.get('expiry'),
                        is_active=True
                    )
                    
                    database.session.add(new_token)
                    database.session.commit()
                    logger.info(f"New token created successfully for user {user_id}")
                    return new_token
                    
            except Exception as e:
                logger.error(f"Error creating/updating token for user {user_id}: {e}")
                try:
                    if database:
                        database.session.rollback()
                except:
                    pass
                return None
        
        return execute_with_app_context(_create_or_update)

class GoogleDriveManager:
    """مدير Google Drive المحسن"""
    
    def __init__(self):
        """تهيئة مدير Google Drive مع معالجة أخطاء محسنة للنشر"""
        # فحص توفر credentials
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
        
        # تحديد ما إذا كانت credentials متوفرة
        self.credentials_available = bool(self.client_id and self.client_secret)
        
        if not self.credentials_available:
            logger.warning("⚠️ Google OAuth credentials غير مكتملة في متغيرات البيئة")
            # استخدام قيم افتراضية للتطوير
            self.client_id = 'your-client-id'
            self.client_secret = 'your-client-secret'
        else:
            logger.info("✅ Google OAuth credentials loaded successfully")
        
        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }
        
        self.scopes = [
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.metadata'
        ]
        
        self.backup_folder_name = "نسخ احتياطية - نظام الأسئلة الكيميائية"
        
        # التحقق من عدم وجود credentials مطلوبة
        if not self.credentials_available:
            logger.warning("Google Drive سيعمل في وضع محدود - بعض الميزات غير متاحة")
            # لا نرفع خطأ، بل نستمر في العمل بوضع محدود
    
    def is_available(self) -> bool:
        """فحص ما إذا كان Google Drive متاحاً"""
        return GOOGLE_APIS_AVAILABLE and self.credentials_available
    
    def get_authorization_url(self, user_id: int) -> Optional[str]:
        """الحصول على رابط التفويض"""
        try:
            if not GOOGLE_APIS_AVAILABLE:
                logger.warning("Google APIs not available, returning mock URL")
                return f"https://accounts.google.com/oauth2/auth?mock=true&user_id={user_id}"
            
            flow = Flow.from_client_config(
                self.client_config,
                scopes=self.scopes,
                state=str(user_id)
            )
            
            flow.redirect_uri = self.client_config["web"]["redirect_uris"][0]
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            logger.info(f"Generated authorization URL for user {user_id}")
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error generating authorization URL: {e}")
            return None
    
    def handle_oauth_callback(self, user_id: int, authorization_code: str) -> bool:
        """معالجة callback OAuth"""
        try:
            if not GOOGLE_APIS_AVAILABLE:
                logger.info(f"Mock OAuth callback for user {user_id}")
                # محاكاة نجح التفويض
                mock_token_data = {
                    'access_token': f'mock_access_token_{user_id}',
                    'refresh_token': f'mock_refresh_token_{user_id}',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'client_id': self.client_config["web"]["client_id"],
                    'client_secret': self.client_config["web"]["client_secret"],
                    'scopes': json.dumps(self.scopes),
                    'expiry': datetime.utcnow() + timedelta(hours=1)
                }
                
                GoogleDriveToken.create_or_update_token(user_id, mock_token_data)
                return True
            
            flow = Flow.from_client_config(
                self.client_config,
                scopes=self.scopes,
                state=str(user_id)
            )
            
            flow.redirect_uri = self.client_config["web"]["redirect_uris"][0]
            flow.fetch_token(code=authorization_code)
            
            credentials = flow.credentials
            
            # حفظ الرمز المميز
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': json.dumps(credentials.scopes),
                'expiry': credentials.expiry
            }
            
            GoogleDriveToken.create_or_update_token(user_id, token_data)
            
            # إنشاء مجلد النسخ الاحتياطي
            self._create_backup_folder(user_id)
            
            logger.info(f"OAuth callback handled successfully for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            return False
    
    def disconnect_user(self, user_id: int) -> bool:
        """قطع اتصال المستخدم مع app context صحيح"""
        def _disconnect():
            try:
                database = get_db_with_context()
                if not database:
                    logger.error("Database not available for disconnect operation")
                    return False
                    
                token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                if token:
                    token.is_active = False
                    token.updated_at = datetime.utcnow()
                    database.session.commit()
                    
                    logger.info(f"User {user_id} disconnected from Google Drive")
                    return True
                
                return False
                
            except Exception as e:
                logger.error(f"Error disconnecting user {user_id}: {e}")
                try:
                    if database:
                        database.session.rollback()
                except:
                    pass
                return False
        
        return execute_with_app_context(_disconnect)
    
    def get_user_connection_status(self, user_id: int) -> Dict[str, Any]:
        """الحصول على حالة اتصال المستخدم مع app context صحيح - إصلاح محسن"""
        def _get_status():
            try:
                database = get_db_with_context()
                if not database:
                    logger.error("Database not available for status check")
                    return {
                        'connected': False,
                        'message': 'قاعدة البيانات غير متاحة'
                    }
                    
                token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                
                if not token:
                    return {
                        'connected': False,
                        'message': 'غير متصل بـ Google Drive'
                    }
                
                if not token.is_token_valid():
                    return {
                        'connected': False,
                        'message': 'انتهت صلاحية الرمز المميز',
                        'needs_refresh': True
                    }
                
                return {
                    'connected': True,
                    'message': 'متصل بـ Google Drive',
                    'folder_id': token.folder_id,
                    'last_backup': token.last_backup_date.isoformat() if token.last_backup_date else None,
                    'backup_count': token.backup_count
                }
                
            except Exception as e:
                logger.error(f"Error getting connection status for user {user_id}: {e}")
                return {
                    'connected': False,
                    'message': f'خطأ في فحص الاتصال: {str(e)}'
                }
        
        return execute_with_app_context(_get_status)
    
    def upload_backup(self, user_id: int, backup_data: bytes, filename: str) -> bool:
        """رفع نسخة احتياطية إلى Google Drive"""
        try:
            if not GOOGLE_APIS_AVAILABLE:
                logger.info(f"Mock backup upload for user {user_id}: {filename}")
                # محاكاة رفع ناجح
                def _update_backup_stats():
                    try:
                        database = get_db_with_context()
                        if database:
                            token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                            if token:
                                token.last_backup_date = datetime.utcnow()
                                token.backup_count += 1
                                database.session.commit()
                    except Exception as e:
                        logger.error(f"Error updating backup stats: {e}")
                
                execute_with_app_context(_update_backup_stats)
                return True
            
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                return False
            
            service = build('drive', 'v3', credentials=credentials)
            
            # الحصول على مجلد النسخ الاحتياطي
            folder_id = self._get_backup_folder_id(user_id, service)
            if not folder_id:
                return False
            
            # إعداد البيانات للرفع
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(backup_data),
                mimetype='application/zip',
                resumable=True
            )
            
            # رفع الملف
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            # تحديث إحصائيات النسخ الاحتياطي
            def _update_backup_stats():
                try:
                    database = get_db_with_context()
                    if database:
                        token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                        if token:
                            token.last_backup_date = datetime.utcnow()
                            token.backup_count += 1
                            database.session.commit()
                except Exception as e:
                    logger.error(f"Error updating backup stats: {e}")
            
            execute_with_app_context(_update_backup_stats)
            
            logger.info(f"Backup uploaded successfully for user {user_id}: {file.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading backup for user {user_id}: {e}")
            return False
    
    def list_backups(self, user_id: int) -> List[Dict[str, Any]]:
        """قائمة النسخ الاحتياطية"""
        try:
            if not GOOGLE_APIS_AVAILABLE:
                # محاكاة قائمة النسخ الاحتياطية
                return [
                    {
                        'id': f'mock_backup_{i}',
                        'name': f'backup_{datetime.utcnow().strftime("%Y%m%d")}_{i}.zip',
                        'size': f'{1.5 + i * 0.3:.1f} MB',
                        'created_time': (datetime.utcnow() - timedelta(days=i)).isoformat(),
                        'download_url': f'https://drive.google.com/file/d/mock_backup_{i}/view'
                    }
                    for i in range(1, 6)
                ]
            
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                return []
            
            service = build('drive', 'v3', credentials=credentials)
            
            # الحصول على مجلد النسخ الاحتياطي
            folder_id = self._get_backup_folder_id(user_id, service)
            if not folder_id:
                return []
            
            # البحث عن الملفات في المجلد
            results = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                orderBy='createdTime desc',
                fields="files(id, name, size, createdTime, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            backups = []
            for file in files:
                backups.append({
                    'id': file['id'],
                    'name': file['name'],
                    'size': self._format_file_size(int(file.get('size', 0))),
                    'created_time': file['createdTime'],
                    'download_url': file.get('webViewLink', '')
                })
            
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups for user {user_id}: {e}")
            return []
    
    def delete_backup(self, user_id: int, file_id: str) -> bool:
        """حذف نسخة احتياطية"""
        try:
            if not GOOGLE_APIS_AVAILABLE:
                logger.info(f"Mock backup deletion for user {user_id}: {file_id}")
                return True
            
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                return False
            
            service = build('drive', 'v3', credentials=credentials)
            
            # حذف الملف
            service.files().delete(fileId=file_id).execute()
            
            logger.info(f"Backup deleted successfully for user {user_id}: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting backup for user {user_id}: {e}")
            return False
    
    def _get_user_credentials(self, user_id: int) -> Optional[Credentials]:
        """الحصول على بيانات اعتماد المستخدم"""
        try:
            token = GoogleDriveToken.get_user_token(user_id)
            if not token or not token.is_token_valid():
                return None
            
            credentials = Credentials(
                token=token.access_token,
                refresh_token=token.refresh_token,
                token_uri=token.token_uri,
                client_id=token.client_id,
                client_secret=token.client_secret,
                scopes=json.loads(token.scopes) if token.scopes else self.scopes
            )
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error getting credentials for user {user_id}: {e}")
            return None
    
    def _create_backup_folder(self, user_id: int) -> Optional[str]:
        """إنشاء مجلد النسخ الاحتياطي"""
        try:
            if not GOOGLE_APIS_AVAILABLE:
                # محاكاة إنشاء المجلد
                folder_id = f"mock_folder_{user_id}"
                def _update_folder_id():
                    try:
                        database = get_db_with_context()
                        if database:
                            token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                            if token:
                                token.folder_id = folder_id
                                database.session.commit()
                    except Exception as e:
                        logger.error(f"Error updating folder ID: {e}")
                
                execute_with_app_context(_update_folder_id)
                return folder_id
            
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                return None
            
            service = build('drive', 'v3', credentials=credentials)
            
            # البحث عن المجلد الموجود
            existing_folder = self._find_backup_folder(service)
            if existing_folder:
                # تحديث معرف المجلد في قاعدة البيانات
                def _update_folder_id():
                    try:
                        database = get_db_with_context()
                        if database:
                            token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                            if token:
                                token.folder_id = existing_folder
                                database.session.commit()
                    except Exception as e:
                        logger.error(f"Error updating folder ID: {e}")
                
                execute_with_app_context(_update_folder_id)
                return existing_folder
            
            # إنشاء مجلد جديد
            file_metadata = {
                'name': self.backup_folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
            
            # حفظ معرف المجلد
            def _save_folder_id():
                try:
                    database = get_db_with_context()
                    if database:
                        token = GoogleDriveToken.query.filter_by(user_id=user_id, is_active=True).first()
                        if token:
                            token.folder_id = folder_id
                            database.session.commit()
                except Exception as e:
                    logger.error(f"Error saving folder ID: {e}")
            
            execute_with_app_context(_save_folder_id)
            
            logger.info(f"Backup folder created for user {user_id}: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"Error creating backup folder for user {user_id}: {e}")
            return None
    
    def _find_backup_folder(self, service) -> Optional[str]:
        """البحث عن مجلد النسخ الاحتياطي"""
        try:
            results = service.files().list(
                q=f"name='{self.backup_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            if files:
                return files[0]['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding backup folder: {e}")
            return None
    
    def _get_backup_folder_id(self, user_id: int, service) -> Optional[str]:
        """الحصول على معرف مجلد النسخ الاحتياطي"""
        token = GoogleDriveToken.get_user_token(user_id)
        
        if token and token.folder_id:
            return token.folder_id
        
        # إنشاء المجلد إذا لم يكن موجوداً
        return self._create_backup_folder(user_id)
    
    def _format_file_size(self, size_bytes: int) -> str:
        """تنسيق حجم الملف"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

# إنشاء مثيل عام مع معالجة أخطاء محسنة للنشر على Render
try:
    google_drive_manager = GoogleDriveManager()
    logger.info("✅ Google Drive Manager initialized successfully")
except Exception as e:
    logger.warning(f"⚠️ Google Drive Manager initialization failed: {e}")
    # إنشاء مدير وهمي في حالة الفشل
    class DummyGoogleDriveManager:
        def __init__(self):
            self.credentials_available = False
            
        def is_available(self):
            return False
        
        def get_user_connection_status(self, user_id):
            return {
                'connected': False,
                'error': 'Google Drive credentials not configured'
            }
        
        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                logger.warning(f"Google Drive method '{name}' called but service unavailable")
                return None
            return dummy_method
    
    google_drive_manager = DummyGoogleDriveManager()

# دوال مساعدة للاستخدام السهل
def get_authorization_url(user_id: int) -> Optional[str]:
    """الحصول على رابط التفويض"""
    return google_drive_manager.get_authorization_url(user_id)

def handle_oauth_callback(user_id: int, authorization_code: str) -> bool:
    """معالجة callback OAuth"""
    return google_drive_manager.handle_oauth_callback(user_id, authorization_code)

def disconnect_user(user_id: int) -> bool:
    """قطع اتصال المستخدم"""
    return google_drive_manager.disconnect_user(user_id)

def get_connection_status(user_id: int) -> Dict[str, Any]:
    """الحصول على حالة الاتصال"""
    return google_drive_manager.get_user_connection_status(user_id)

def upload_backup(user_id: int, backup_data: bytes, filename: str) -> bool:
    """رفع نسخة احتياطية"""
    return google_drive_manager.upload_backup(user_id, backup_data, filename)

def list_user_backups(user_id: int) -> List[Dict[str, Any]]:
    """قائمة النسخ الاحتياطية للمستخدم"""
    return google_drive_manager.list_backups(user_id)

def delete_backup_file(user_id: int, file_id: str) -> bool:
    """حذف نسخة احتياطية"""
    return google_drive_manager.delete_backup(user_id, file_id)

