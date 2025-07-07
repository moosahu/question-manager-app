"""
Google Drive Integration with SQLAlchemy Fix
حل جذري لمشكلة SQLAlchemy Backend
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import traceback

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# استيراد db
try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        db = None

class GoogleDriveToken(db.Model if db else object):
    """نموذج رموز Google Drive للمستخدمين"""
    __tablename__ = 'google_drive_tokens'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.String(255))
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    scopes = db.Column(db.Text)
    expiry = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    folder_id = db.Column(db.String(255))
    last_backup_date = db.Column(db.DateTime)
    backup_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    api_key = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<GoogleDriveToken {self.user_id}>'

def safe_db_operation(operation_func, *args, **kwargs):
    """
    تنفيذ آمن لعمليات قاعدة البيانات مع معالجة شاملة للأخطاء
    """
    try:
        # محاولة الحصول على Flask app و db
        app, db = get_flask_app_and_db()
        if not app or not db:
            logger.error("❌ لا يمكن الحصول على Flask app أو db instance")
            return None
        
        # تنفيذ العملية مع app context
        with app.app_context():
            try:
                result = operation_func(db, *args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"❌ خطأ في تنفيذ العملية: {str(e)}")
                logger.error(f"❌ تفاصيل الخطأ: {traceback.format_exc()}")
                # محاولة rollback
                try:
                    db.session.rollback()
                except:
                    pass
                return None
                
    except Exception as e:
        logger.error(f"❌ خطأ في safe_db_operation: {str(e)}")
        logger.error(f"❌ تفاصيل الخطأ: {traceback.format_exc()}")
        return None

def get_flask_app_and_db():
    """
    الحصول على Flask app و SQLAlchemy db instance بطريقة آمنة
    """
    app = None
    db = None
    
    try:
        # محاولة 1: استيراد من current_app
        from flask import current_app
        app = current_app._get_current_object()
        logger.info("✅ تم الحصول على app من current_app")
    except:
        pass
    
    if not app:
        try:
            # محاولة 2: استيراد من app module
            from app import app as flask_app
            app = flask_app
            logger.info("✅ تم الحصول على app من app module")
        except:
            pass
    
    if not app:
        try:
            # محاولة 3: استيراد من main module
            from main import app as flask_app
            app = flask_app
            logger.info("✅ تم الحصول على app من main module")
        except:
            pass
    
    # الحصول على db instance
    if app:
        try:
            # محاولة 1: من app extensions
            if hasattr(app, 'extensions') and 'sqlalchemy' in app.extensions:
                db = app.extensions['sqlalchemy'].db
                logger.info("✅ تم الحصول على db من app.extensions")
            else:
                # محاولة 2: استيراد مباشر
                try:
                    from app import db as db_instance
                    db = db_instance
                    logger.info("✅ تم الحصول على db من app module")
                except:
                    try:
                        from main import db as db_instance
                        db = db_instance
                        logger.info("✅ تم الحصول على db من main module")
                    except:
                        pass
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على db: {str(e)}")
    
    return app, db

def create_google_drive_token_table(db):
    """
    إنشاء جدول google_drive_tokens إذا لم يكن موجوداً
    """
    try:
        # تنفيذ SQL مباشر لإنشاء الجدول
        sql = """
        CREATE TABLE IF NOT EXISTS google_drive_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            access_token TEXT,
            refresh_token TEXT,
            token_uri VARCHAR(255),
            client_id VARCHAR(255),
            client_secret VARCHAR(255),
            scopes TEXT,
            expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            folder_id VARCHAR(255),
            last_backup_date TIMESTAMP,
            backup_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            api_key VARCHAR(255)
        );
        """
        
        db.session.execute(sql)
        db.session.commit()
        logger.info("✅ تم التأكد من وجود جدول google_drive_tokens")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء الجدول: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def get_user_token_safe(user_id: int) -> Optional[Dict[str, Any]]:
    """
    الحصول على token المستخدم بطريقة آمنة
    """
    def _get_token(db, user_id):
        # التأكد من وجود الجدول
        create_google_drive_token_table(db)
        
        # البحث عن Token
        sql = """
        SELECT * FROM google_drive_tokens 
        WHERE user_id = %s AND is_active = TRUE 
        ORDER BY created_at DESC LIMIT 1
        """
        
        result = db.session.execute(sql, (user_id,))
        row = result.fetchone()
        
        if row:
            # تحويل النتيجة إلى dictionary
            columns = result.keys()
            token_data = dict(zip(columns, row))
            logger.info(f"✅ تم العثور على token للمستخدم {user_id}")
            return token_data
        else:
            logger.info(f"❌ لم يتم العثور على token للمستخدم {user_id}")
            return None
    
    return safe_db_operation(_get_token, user_id)

def create_or_update_token_safe(user_id: int, token_data: Dict[str, Any], api_key: str = None) -> bool:
    """
    إنشاء أو تحديث token بطريقة آمنة
    """
    def _create_or_update_token(db, user_id, token_data, api_key):
        logger.info(f"🔄 محاولة حفظ token للمستخدم ID: {user_id}")
        
        # التأكد من وجود الجدول
        if not create_google_drive_token_table(db):
            logger.error("❌ فشل في إنشاء الجدول")
            return False
        
        try:
            # البحث عن token موجود
            existing_sql = """
            SELECT id FROM google_drive_tokens 
            WHERE user_id = %s AND is_active = TRUE
            """
            
            result = db.session.execute(existing_sql, (user_id,))
            existing_token = result.fetchone()
            
            # تحضير البيانات
            access_token = token_data.get('access_token', '')
            refresh_token = token_data.get('refresh_token', '')
            token_uri = token_data.get('token_uri', '')
            client_id = token_data.get('client_id', '')
            client_secret = token_data.get('client_secret', '')
            scopes = json.dumps(token_data.get('scopes', []))
            
            # معالجة expiry
            expiry = None
            if 'expiry' in token_data and token_data['expiry']:
                try:
                    if isinstance(token_data['expiry'], str):
                        expiry = datetime.fromisoformat(token_data['expiry'].replace('Z', '+00:00'))
                    elif isinstance(token_data['expiry'], datetime):
                        expiry = token_data['expiry']
                except:
                    expiry = None
            
            current_time = datetime.now(timezone.utc)
            
            if existing_token:
                # تحديث token موجود
                update_sql = """
                UPDATE google_drive_tokens SET
                    access_token = %s,
                    refresh_token = %s,
                    token_uri = %s,
                    client_id = %s,
                    client_secret = %s,
                    scopes = %s,
                    expiry = %s,
                    updated_at = %s,
                    api_key = %s
                WHERE user_id = %s AND is_active = TRUE
                """
                
                db.session.execute(update_sql, (
                    access_token, refresh_token, token_uri, client_id, 
                    client_secret, scopes, expiry, current_time, api_key, user_id
                ))
                
                logger.info(f"✅ تم تحديث token للمستخدم {user_id}")
                
            else:
                # إنشاء token جديد
                insert_sql = """
                INSERT INTO google_drive_tokens 
                (user_id, access_token, refresh_token, token_uri, client_id, 
                 client_secret, scopes, expiry, created_at, updated_at, 
                 backup_count, is_active, api_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                db.session.execute(insert_sql, (
                    user_id, access_token, refresh_token, token_uri, client_id,
                    client_secret, scopes, expiry, current_time, current_time,
                    0, True, api_key
                ))
                
                logger.info(f"✅ تم إنشاء token جديد للمستخدم {user_id}")
            
            # حفظ التغييرات
            db.session.commit()
            logger.info(f"✅ تم حفظ token بنجاح للمستخدم {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ token: {str(e)}")
            logger.error(f"❌ تفاصيل الخطأ: {traceback.format_exc()}")
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    return safe_db_operation(_create_or_update_token, user_id, token_data, api_key)

def get_user_connection_status_safe(user_id: int) -> Dict[str, Any]:
    """
    فحص حالة اتصال Google Drive للمستخدم بطريقة آمنة
    """
    def _get_connection_status(db, user_id):
        try:
            # التأكد من وجود الجدول
            create_google_drive_token_table(db)
            
            # فحص وجود token
            sql = """
            SELECT access_token, expiry, last_backup_date, backup_count, api_key
            FROM google_drive_tokens 
            WHERE user_id = %s AND is_active = TRUE 
            ORDER BY created_at DESC LIMIT 1
            """
            
            result = db.session.execute(sql, (user_id,))
            row = result.fetchone()
            
            if row:
                access_token, expiry, last_backup_date, backup_count, api_key = row
                
                # فحص انتهاء صلاحية Token
                is_expired = False
                if expiry:
                    try:
                        if isinstance(expiry, str):
                            expiry_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                        else:
                            expiry_dt = expiry
                        is_expired = expiry_dt < datetime.now(timezone.utc)
                    except:
                        is_expired = False
                
                return {
                    'connected': True,
                    'has_token': bool(access_token),
                    'is_expired': is_expired,
                    'last_backup_date': last_backup_date.isoformat() if last_backup_date else None,
                    'backup_count': backup_count or 0,
                    'api_key': api_key
                }
            else:
                return {
                    'connected': False,
                    'has_token': False,
                    'is_expired': False,
                    'last_backup_date': None,
                    'backup_count': 0,
                    'api_key': None
                }
                
        except Exception as e:
            logger.error(f"❌ خطأ في فحص حالة الاتصال: {str(e)}")
            return {
                'connected': False,
                'has_token': False,
                'is_expired': False,
                'last_backup_date': None,
                'backup_count': 0,
                'api_key': None,
                'error': str(e)
            }
    
    result = safe_db_operation(_get_connection_status, user_id)
    if result is None:
        return {
            'connected': False,
            'has_token': False,
            'is_expired': False,
            'last_backup_date': None,
            'backup_count': 0,
            'api_key': None,
            'error': 'Database operation failed'
        }
    return result

def disconnect_user_safe(user_id: int) -> bool:
    """
    قطع اتصال Google Drive للمستخدم بطريقة آمنة
    """
    def _disconnect_user(db, user_id):
        try:
            # تعطيل جميع tokens للمستخدم
            sql = """
            UPDATE google_drive_tokens 
            SET is_active = FALSE, updated_at = %s
            WHERE user_id = %s
            """
            
            current_time = datetime.now(timezone.utc)
            db.session.execute(sql, (current_time, user_id))
            db.session.commit()
            
            logger.info(f"✅ تم قطع اتصال Google Drive للمستخدم {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في قطع الاتصال: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    result = safe_db_operation(_disconnect_user, user_id)
    return result if result is not None else False

# الدوال الرئيسية للاستخدام الخارجي
def get_user_token(user_id: int) -> Optional[Dict[str, Any]]:
    """الحصول على token المستخدم"""
    return get_user_token_safe(user_id)

def create_or_update_token(user_id: int, token_data: Dict[str, Any], api_key: str = None) -> bool:
    """إنشاء أو تحديث token"""
    return create_or_update_token_safe(user_id, token_data, api_key)

def get_user_connection_status(user_id: int) -> Dict[str, Any]:
    """فحص حالة اتصال Google Drive"""
    return get_user_connection_status_safe(user_id)

def disconnect_user(user_id: int) -> bool:
    """قطع اتصال Google Drive"""
    return disconnect_user_safe(user_id)

# دالة اختبار
def test_database_connection():
    """اختبار الاتصال بقاعدة البيانات"""
    try:
        app, db = get_flask_app_and_db()
        if app and db:
            with app.app_context():
                # اختبار بسيط
                result = db.session.execute("SELECT 1")
                logger.info("✅ اختبار قاعدة البيانات نجح")
                return True
        else:
            logger.error("❌ فشل في الحصول على app أو db")
            return False
    except Exception as e:
        logger.error(f"❌ فشل اختبار قاعدة البيانات: {str(e)}")
        return False

if __name__ == "__main__":
    # اختبار الوحدة
    print("🧪 اختبار وحدة Google Drive...")
    if test_database_connection():
        print("✅ جميع الاختبارات نجحت!")
    else:
        print("❌ فشل في الاختبارات!")

