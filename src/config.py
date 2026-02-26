"""
إعدادات التطبيق الرئيسية
Configuration for Question Manager Application
"""
import os
from datetime import timedelta

# استخراج متغيرات البيئة
class Config:
    """الإعدادات الأساسية للتطبيق"""
    
    # ==================== Flask Core ====================
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
    DEBUG = False
    TESTING = False
    
    # ==================== Database ====================
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'mysql+pymysql://root:password@localhost/question_manager'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # ==================== Session ====================
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # ==================== JWT Token - جديد ✅ ====================
    JWT_SECRET_KEY = os.getenv(
        'JWT_SECRET_KEY',
        'your-jwt-secret-key-change-this-in-production'
    )
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_DAYS = 30
    JWT_REFRESH_DAYS = 60
    
    # ==================== Email ====================
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'your-email@gmail.com')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'your-app-password')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@chem-tahsili.com')
    
    # ==================== Google Drive ====================
    GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '')
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    
    # ==================== File Upload ====================
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'jpeg', 'png'}
    
    # ==================== Backup ====================
    BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', 24))
    BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', 30))
    
    # ==================== AI Providers ====================
    GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY', '')
    CLAUDE_AI_API_KEY = os.getenv('CLAUDE_AI_API_KEY', '')

    # ==================== API ====================
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True


class DevelopmentConfig(Config):
    """إعدادات التطوير"""
    DEBUG = True
    TESTING = False
    # في التطوير: يمكن استخدام HTTP
    SESSION_COOKIE_SECURE = False
    # في التطوير: مفاتيح اختبار
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-not-for-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key-not-for-production')


class ProductionConfig(Config):
    """إعدادات الإنتاج"""
    DEBUG = False
    TESTING = False
    # في الإنتاج: استخدم HTTPS فقط
    SESSION_COOKIE_SECURE = True
    # لا قيم افتراضية في الإنتاج — يُقرأ من متغيرات البيئة فقط
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')


class TestingConfig(Config):
    """إعدادات الاختبار"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret-key'


# اختر الإعدادات حسب البيئة
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# احصل على الإعدادات الحالية
def get_config():
    """احصل على إعدادات التطبيق الحالية"""
    env = os.getenv('FLASK_ENV', 'development')
    cfg = config.get(env, config['default'])
    # التحقق من المتغيرات الحرجة في بيئة الإنتاج
    if env == 'production':
        for var in ('SECRET_KEY', 'JWT_SECRET_KEY'):
            if not os.getenv(var):
                raise ValueError(
                    f"متغير البيئة '{var}' مطلوب في بيئة الإنتاج. "
                    "يرجى تعيينه قبل تشغيل التطبيق."
                )
    return cfg
