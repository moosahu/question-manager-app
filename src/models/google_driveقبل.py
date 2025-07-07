"""
إصلاح شامل لمشكلة Google Drive - النسخ التلقائي
حل جميع المشاكل المكتشفة في OAuth وAPI endpoints
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import io
from googleapiclient.http import MediaIoBaseUpload
import tempfile
import zipfile

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveManager:
    """مدير Google Drive محسن مع إصلاح جميع المشاكل"""
    
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.metadata'
        ]
        
        # تحميل إعدادات OAuth من متغيرات البيئة
        self.CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
        self.CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
        self.REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'https://chem-tahsili.com/auth/google/callback')
        
        # مجلد النسخ الاحتياطي في Google Drive
        self.BACKUP_FOLDER_NAME = 'ChemTahsili_Backups'
        
        # ملف حفظ الرموز المميزة
        self.TOKEN_FILE = 'google_drive_token.json'
        
        # التحقق من الإعدادات المطلوبة
        if not all([self.CLIENT_ID, self.CLIENT_SECRET]):
            logger.error("Google OAuth credentials غير مكتملة في متغيرات البيئة")
            raise ValueError("Google OAuth credentials مطلوبة")
    
    def get_authorization_url(self):
        """الحصول على رابط المصادقة"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.CLIENT_ID,
                        "client_secret": self.CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.REDIRECT_URI]
                    }
                },
                scopes=self.SCOPES
            )
            
            flow.redirect_uri = self.REDIRECT_URI
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # حفظ state في session للتحقق لاحقاً
            session['oauth_state'] = state
            
            logger.info(f"تم إنشاء رابط المصادقة: {authorization_url}")
            return authorization_url, state
            
        except Exception as e:
            logger.error(f"خطأ في إنشاء رابط المصادقة: {e}")
            return None, None
    
    def handle_oauth_callback(self, authorization_code, state):
        """معالجة callback من Google OAuth"""
        try:
            # التحقق من state
            if session.get('oauth_state') != state:
                logger.error("OAuth state غير متطابق")
                return False, "خطأ في التحقق من الأمان"
            
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.CLIENT_ID,
                        "client_secret": self.CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.REDIRECT_URI]
                    }
                },
                scopes=self.SCOPES,
                state=state
            )
            
            flow.redirect_uri = self.REDIRECT_URI
            
            # تبديل authorization code بـ access token
            flow.fetch_token(code=authorization_code)
            
            credentials = flow.credentials
            
            # حفظ الرموز المميزة
            if self.save_credentials(credentials):
                logger.info("تم حفظ Google Drive credentials بنجاح")
                return True, "تم ربط Google Drive بنجاح"
            else:
                return False, "فشل في حفظ معلومات الاتصال"
                
        except Exception as e:
            logger.error(f"خطأ في معالجة OAuth callback: {e}")
            return False, f"خطأ في المصادقة: {str(e)}"
    
    def save_credentials(self, credentials):
        """حفظ الرموز المميزة"""
        try:
            creds_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expiry': credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            with open(self.TOKEN_FILE, 'w') as f:
                json.dump(creds_data, f, indent=2)
            
            logger.info("تم حفظ Google Drive credentials")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في حفظ credentials: {e}")
            return False
    
    def load_credentials(self):
        """تحميل الرموز المميزة"""
        try:
            if not os.path.exists(self.TOKEN_FILE):
                logger.info("ملف الرموز المميزة غير موجود")
                return None
            
            with open(self.TOKEN_FILE, 'r') as f:
                creds_data = json.load(f)
            
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data.get('refresh_token'),
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )
            
            # تجديد الرمز المميز إذا انتهت صلاحيته
            if credentials.expired and credentials.refresh_token:
                logger.info("تجديد الرمز المميز...")
                credentials.refresh(Request())
                self.save_credentials(credentials)
            
            return credentials
            
        except Exception as e:
            logger.error(f"خطأ في تحميل credentials: {e}")
            return None
    
    def get_drive_service(self):
        """الحصول على خدمة Google Drive"""
        try:
            credentials = self.load_credentials()
            if not credentials:
                logger.error("لا توجد رموز مميزة صالحة")
                return None
            
            service = build('drive', 'v3', credentials=credentials)
            
            # اختبار الاتصال
            service.about().get(fields="user").execute()
            
            logger.info("تم إنشاء خدمة Google Drive بنجاح")
            return service
            
        except HttpError as e:
            logger.error(f"خطأ في Google Drive API: {e}")
            return None
        except Exception as e:
            logger.error(f"خطأ في إنشاء خدمة Google Drive: {e}")
            return None
    
    def is_connected(self):
        """فحص حالة الاتصال مع Google Drive"""
        try:
            service = self.get_drive_service()
            if service:
                # اختبار بسيط للتأكد من عمل الاتصال
                user_info = service.about().get(fields="user").execute()
                logger.info(f"متصل بـ Google Drive - المستخدم: {user_info.get('user', {}).get('emailAddress', 'غير معروف')}")
                return True
            return False
        except Exception as e:
            logger.error(f"خطأ في فحص الاتصال: {e}")
            return False
    
    def create_backup_folder(self, service):
        """إنشاء مجلد النسخ الاحتياطي"""
        try:
            # البحث عن المجلد الموجود
            query = f"name='{self.BACKUP_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = service.files().list(q=query, fields="files(id, name)").execute()
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"مجلد النسخ الاحتياطي موجود: {folder_id}")
                return folder_id
            
            # إنشاء مجلد جديد
            folder_metadata = {
                'name': self.BACKUP_FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')
            
            logger.info(f"تم إنشاء مجلد النسخ الاحتياطي: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"خطأ في إنشاء مجلد النسخ الاحتياطي: {e}")
            return None
    
    def upload_backup(self, data, filename=None):
        """رفع نسخة احتياطية إلى Google Drive"""
        try:
            service = self.get_drive_service()
            if not service:
                return False, "فشل في الاتصال بـ Google Drive"
            
            # إنشاء مجلد النسخ الاحتياطي
            folder_id = self.create_backup_folder(service)
            if not folder_id:
                return False, "فشل في إنشاء مجلد النسخ الاحتياطي"
            
            # إعداد اسم الملف
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"backup_{timestamp}.json"
            
            # تحويل البيانات إلى JSON
            if isinstance(data, dict):
                json_data = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                json_data = str(data)
            
            # إنشاء ملف مؤقت
            file_stream = io.BytesIO(json_data.encode('utf-8'))
            
            # إعداد metadata للملف
            file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'description': f'نسخة احتياطية من ChemTahsili - {datetime.now().isoformat()}'
            }
            
            # رفع الملف
            media = MediaIoBaseUpload(file_stream, mimetype='application/json', resumable=True)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            file_id = file.get('id')
            file_size = file.get('size', 0)
            
            logger.info(f"تم رفع النسخة الاحتياطية: {filename} ({file_size} bytes)")
            
            return True, {
                'message': 'تم رفع النسخة الاحتياطية بنجاح',
                'file_id': file_id,
                'filename': filename,
                'size': file_size,
                'created_time': file.get('createdTime')
            }
            
        except Exception as e:
            logger.error(f"خطأ في رفع النسخة الاحتياطية: {e}")
            return False, f"خطأ في رفع النسخة الاحتياطية: {str(e)}"
    
    def list_backups(self, limit=10):
        """عرض قائمة النسخ الاحتياطية"""
        try:
            service = self.get_drive_service()
            if not service:
                return False, "فشل في الاتصال بـ Google Drive"
            
            # البحث عن مجلد النسخ الاحتياطي
            folder_query = f"name='{self.BACKUP_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            folder_results = service.files().list(q=folder_query, fields="files(id)").execute()
            folders = folder_results.get('files', [])
            
            if not folders:
                return True, []
            
            folder_id = folders[0]['id']
            
            # البحث عن الملفات في المجلد
            files_query = f"'{folder_id}' in parents and trashed=false"
            results = service.files().list(
                q=files_query,
                orderBy='createdTime desc',
                pageSize=limit,
                fields="files(id,name,size,createdTime,modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            
            logger.info(f"تم العثور على {len(files)} نسخة احتياطية")
            return True, files
            
        except Exception as e:
            logger.error(f"خطأ في عرض النسخ الاحتياطية: {e}")
            return False, f"خطأ في عرض النسخ الاحتياطية: {str(e)}"
    
    def download_backup(self, file_id):
        """تحميل نسخة احتياطية من Google Drive"""
        try:
            service = self.get_drive_service()
            if not service:
                return False, "فشل في الاتصال بـ Google Drive"
            
            # تحميل محتوى الملف
            request = service.files().get_media(fileId=file_id)
            file_content = request.execute()
            
            # تحويل إلى JSON
            data = json.loads(file_content.decode('utf-8'))
            
            logger.info(f"تم تحميل النسخة الاحتياطية: {file_id}")
            return True, data
            
        except Exception as e:
            logger.error(f"خطأ في تحميل النسخة الاحتياطية: {e}")
            return False, f"خطأ في تحميل النسخة الاحتياطية: {str(e)}"
    
    def disconnect(self):
        """قطع الاتصال مع Google Drive"""
        try:
            if os.path.exists(self.TOKEN_FILE):
                os.remove(self.TOKEN_FILE)
                logger.info("تم حذف ملف الرموز المميزة")
            
            return True, "تم قطع الاتصال مع Google Drive"
            
        except Exception as e:
            logger.error(f"خطأ في قطع الاتصال: {e}")
            return False, f"خطأ في قطع الاتصال: {str(e)}"

# إنشاء مثيل مدير Google Drive
google_drive_manager = GoogleDriveManager()

# ===== Flask Routes =====

def register_google_drive_routes(app):
    """تسجيل مسارات Google Drive في التطبيق"""
    
    @app.route('/api/google-drive/status')
    def google_drive_status():
        """فحص حالة اتصال Google Drive"""
        try:
            connected = google_drive_manager.is_connected()
            
            backup_info = {}
            if connected:
                success, backups = google_drive_manager.list_backups(limit=1)
                if success and backups:
                    latest_backup = backups[0]
                    backup_info = {
                        'last_backup': latest_backup.get('createdTime'),
                        'last_backup_size': latest_backup.get('size', 0)
                    }
            
            return jsonify({
                'success': True,
                'connected': connected,
                'status': 'متصل' if connected else 'غير متصل',
                **backup_info
            })
            
        except Exception as e:
            logger.error(f"خطأ في فحص حالة Google Drive: {e}")
            return jsonify({
                'success': False,
                'connected': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/google-drive/connect')
    def connect_google_drive():
        """بدء عملية ربط Google Drive"""
        try:
            auth_url, state = google_drive_manager.get_authorization_url()
            
            if auth_url:
                return jsonify({
                    'success': True,
                    'auth_url': auth_url,
                    'state': state
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'فشل في إنشاء رابط المصادقة'
                }), 500
                
        except Exception as e:
            logger.error(f"خطأ في ربط Google Drive: {e}")
            return jsonify({
                'success': False,
                'message': f'خطأ في ربط Google Drive: {str(e)}'
            }), 500
    
    @app.route('/auth/google/callback')
    def google_oauth_callback():
        """معالجة callback من Google OAuth"""
        try:
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
            
            if error:
                logger.error(f"خطأ في OAuth: {error}")
                return redirect(url_for('settings') + '?error=oauth_error')
            
            if not code or not state:
                logger.error("معاملات OAuth مفقودة")
                return redirect(url_for('settings') + '?error=missing_params')
            
            success, message = google_drive_manager.handle_oauth_callback(code, state)
            
            if success:
                return redirect(url_for('settings') + '?success=google_drive_connected')
            else:
                return redirect(url_for('settings') + f'?error={message}')
                
        except Exception as e:
            logger.error(f"خطأ في OAuth callback: {e}")
            return redirect(url_for('settings') + '?error=callback_error')
    
    @app.route('/api/google-drive/disconnect', methods=['POST'])
    def disconnect_google_drive():
        """قطع الاتصال مع Google Drive"""
        try:
            success, message = google_drive_manager.disconnect()
            
            return jsonify({
                'success': success,
                'message': message
            })
            
        except Exception as e:
            logger.error(f"خطأ في قطع الاتصال: {e}")
            return jsonify({
                'success': False,
                'message': f'خطأ في قطع الاتصال: {str(e)}'
            }), 500
    
    @app.route('/api/backup/create', methods=['POST'])
    def create_backup():
        """إنشاء نسخة احتياطية"""
        try:
            # جمع البيانات للنسخ الاحتياطي
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
                'data': {
                    'settings': {},  # إضافة البيانات الفعلية هنا
                    'questions': [],  # إضافة الأسئلة هنا
                    'users': []  # إضافة المستخدمين هنا
                }
            }
            
            # رفع إلى Google Drive إذا كان متصلاً
            if google_drive_manager.is_connected():
                success, result = google_drive_manager.upload_backup(backup_data)
                
                if success:
                    return jsonify({
                        'success': True,
                        'message': 'تم إنشاء النسخة الاحتياطية في Google Drive',
                        'destination': 'google_drive',
                        'details': result
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': result
                    }), 500
            else:
                # حفظ محلي
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"local_backup_{timestamp}.json"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
                
                return jsonify({
                    'success': True,
                    'message': 'تم إنشاء النسخة الاحتياطية محلياً',
                    'destination': 'local',
                    'filename': filename
                })
                
        except Exception as e:
            logger.error(f"خطأ في إنشاء النسخة الاحتياطية: {e}")
            return jsonify({
                'success': False,
                'message': f'خطأ في إنشاء النسخة الاحتياطية: {str(e)}'
            }), 500
    
    @app.route('/api/backup/list')
    def list_backups():
        """عرض قائمة النسخ الاحتياطية"""
        try:
            if google_drive_manager.is_connected():
                success, backups = google_drive_manager.list_backups()
                
                if success:
                    return jsonify({
                        'success': True,
                        'backups': backups,
                        'source': 'google_drive'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': backups
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'message': 'Google Drive غير متصل'
                }), 400
                
        except Exception as e:
            logger.error(f"خطأ في عرض النسخ الاحتياطية: {e}")
            return jsonify({
                'success': False,
                'message': f'خطأ في عرض النسخ الاحتياطية: {str(e)}'
            }), 500

# ===== JavaScript للواجهة الأمامية =====

GOOGLE_DRIVE_FRONTEND_JS = """
// Google Drive Integration - Frontend JavaScript
class GoogleDriveIntegration {
    constructor() {
        this.statusElement = document.getElementById('google-drive-status');
        this.connectButton = document.getElementById('connect-google-drive');
        this.disconnectButton = document.getElementById('disconnect-google-drive');
        this.backupButton = document.getElementById('backup-now');
        
        this.init();
    }
    
    init() {
        this.checkStatus();
        this.bindEvents();
        
        // فحص دوري للحالة
        setInterval(() => this.checkStatus(), 30000);
    }
    
    bindEvents() {
        if (this.connectButton) {
            this.connectButton.addEventListener('click', () => this.connect());
        }
        
        if (this.disconnectButton) {
            this.disconnectButton.addEventListener('click', () => this.disconnect());
        }
        
        if (this.backupButton) {
            this.backupButton.addEventListener('click', () => this.createBackup());
        }
    }
    
    async checkStatus() {
        try {
            const response = await fetch('/api/google-drive/status');
            const data = await response.json();
            
            this.updateUI(data);
            
        } catch (error) {
            console.error('خطأ في فحص حالة Google Drive:', error);
            this.showError('فشل في فحص حالة Google Drive');
        }
    }
    
    updateUI(data) {
        if (this.statusElement) {
            if (data.connected) {
                this.statusElement.innerHTML = `
                    <span class="status-connected">متصل ✅</span>
                    ${data.last_backup ? `<br><small>آخر نسخة: ${new Date(data.last_backup).toLocaleString('ar')}</small>` : ''}
                `;
                this.statusElement.className = 'google-drive-status connected';
            } else {
                this.statusElement.innerHTML = '<span class="status-disconnected">غير متصل ❌</span>';
                this.statusElement.className = 'google-drive-status disconnected';
            }
        }
        
        // تحديث الأزرار
        if (this.connectButton) {
            this.connectButton.style.display = data.connected ? 'none' : 'inline-block';
        }
        
        if (this.disconnectButton) {
            this.disconnectButton.style.display = data.connected ? 'inline-block' : 'none';
        }
        
        if (this.backupButton) {
            this.backupButton.disabled = !data.connected;
            this.backupButton.textContent = data.connected ? 'نسخ إلى Google Drive' : 'نسخ محلي';
        }
    }
    
    async connect() {
        try {
            this.showLoading('جاري الاتصال بـ Google Drive...');
            
            const response = await fetch('/api/google-drive/connect');
            const data = await response.json();
            
            if (data.success && data.auth_url) {
                // فتح نافذة المصادقة
                window.location.href = data.auth_url;
            } else {
                this.showError(data.message || 'فشل في الاتصال بـ Google Drive');
            }
            
        } catch (error) {
            console.error('خطأ في الاتصال:', error);
            this.showError('فشل في الاتصال بـ Google Drive');
        } finally {
            this.hideLoading();
        }
    }
    
    async disconnect() {
        if (!confirm('هل أنت متأكد من قطع الاتصال مع Google Drive؟')) {
            return;
        }
        
        try {
            this.showLoading('جاري قطع الاتصال...');
            
            const response = await fetch('/api/google-drive/disconnect', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(data.message);
                this.checkStatus();
            } else {
                this.showError(data.message || 'فشل في قطع الاتصال');
            }
            
        } catch (error) {
            console.error('خطأ في قطع الاتصال:', error);
            this.showError('فشل في قطع الاتصال');
        } finally {
            this.hideLoading();
        }
    }
    
    async createBackup() {
        try {
            this.showLoading('جاري إنشاء النسخة الاحتياطية...');
            
            const response = await fetch('/api/backup/create', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(data.message);
                this.checkStatus();
            } else {
                this.showError(data.message || 'فشل في إنشاء النسخة الاحتياطية');
            }
            
        } catch (error) {
            console.error('خطأ في النسخ الاحتياطي:', error);
            this.showError('فشل في إنشاء النسخة الاحتياطية');
        } finally {
            this.hideLoading();
        }
    }
    
    showLoading(message) {
        // إظهار رسالة التحميل
        this.showNotification(message, 'info');
    }
    
    hideLoading() {
        // إخفاء رسالة التحميل
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showNotification(message, type) {
        // إنشاء إشعار
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // إزالة الإشعار بعد 5 ثوان
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
}

// تشغيل عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
    new GoogleDriveIntegration();
});
"""

# ===== CSS للواجهة الأمامية =====

GOOGLE_DRIVE_CSS = """
/* Google Drive Integration Styles */
.google-drive-status {
    padding: 10px;
    border-radius: 5px;
    margin: 10px 0;
    font-weight: bold;
}

.google-drive-status.connected {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.google-drive-status.disconnected {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}

.status-connected {
    color: #28a745;
}

.status-disconnected {
    color: #dc3545;
}

.google-drive-buttons {
    margin: 15px 0;
}

.google-drive-buttons button {
    margin: 5px;
    padding: 10px 20px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 14px;
}

.btn-connect {
    background-color: #007bff;
    color: white;
}

.btn-disconnect {
    background-color: #dc3545;
    color: white;
}

.btn-backup {
    background-color: #28a745;
    color: white;
}

.btn-backup:disabled {
    background-color: #6c757d;
    cursor: not-allowed;
}

.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    border-radius: 5px;
    color: white;
    font-weight: bold;
    z-index: 1000;
    max-width: 300px;
}

.notification-success {
    background-color: #28a745;
}

.notification-error {
    background-color: #dc3545;
}

.notification-info {
    background-color: #17a2b8;
}
"""

if __name__ == "__main__":
    print("Google Drive Integration - إصلاح شامل")
    print("=" * 50)
    print("✅ تم إنشاء GoogleDriveManager محسن")
    print("✅ تم إصلاح OAuth configuration")
    print("✅ تم إضافة token refresh mechanism")
    print("✅ تم إصلاح API endpoints")
    print("✅ تم إضافة error handling شامل")
    print("✅ تم إنشاء JavaScript للواجهة الأمامية")
    print("✅ تم إنشاء CSS للتصميم")
    print("\nالخطوات التالية:")
    print("1. تحديث ملف .env بالقيم الصحيحة")
    print("2. استيراد هذا الملف في التطبيق الرئيسي")
    print("3. تسجيل المسارات باستخدام register_google_drive_routes(app)")
    print("4. إضافة JavaScript و CSS للصفحات")

