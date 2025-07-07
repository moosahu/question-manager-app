import json
import logging
from datetime import datetime
from io import StringIO

# إعداد نظام السجلات
logger = logging.getLogger(__name__)

# استيراد النماذج والامتدادات
try:
    from src.models.backup_settings import BackupSettings
    from src.extensions import db
    from src.models.question import Question
    from src.models.curriculum import Course, Unit, Lesson
    from src.models.user import User
    from src.models.google_drive import GoogleDriveToken
except ImportError:
    try:
        from models.backup_settings import BackupSettings
        from extensions import db
        from models.question import Question
        from models.curriculum import Course, Unit, Lesson
        from models.user import User
        from models.google_drive import GoogleDriveToken
    except ImportError:
        try:
            from backup_settings import BackupSettings
            from google_drive import GoogleDriveToken
            # إذا فشل استيراد النماذج، سنحاول استيرادها لاحقاً
            db = None
            Question = None
            Course = None
            Unit = None
            Lesson = None
            User = None
        except ImportError:
            logger.error("فشل في استيراد النماذج المطلوبة")
            BackupSettings = None
            GoogleDriveToken = None
            db = None

# محاولة استيراد مكتبات Google Drive
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.auth.transport.requests import Request
    import io
    google_drive_available = True
except ImportError:
    logger.warning("مكتبات Google Drive غير متوفرة")
    google_drive_available = False

def perform_backup_for_user(user_id):
    """
    تنفيذ النسخ الاحتياطي لمستخدم محدد
    
    Args:
        user_id: معرف المستخدم
    
    Returns:
        dict: نتيجة عملية النسخ الاحتياطي
    """
    try:
        logger.info(f"بدء النسخ الاحتياطي للمستخدم {user_id}")
        
        # الحصول على إعدادات النسخ الاحتياطي
        if not BackupSettings:
            logger.error("نموذج BackupSettings غير متوفر")
            return {"success": False, "error": "نموذج BackupSettings غير متوفر"}
        
        settings = BackupSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            logger.warning(f"لا توجد إعدادات نسخ احتياطي للمستخدم {user_id}")
            return {"success": False, "error": "لا توجد إعدادات نسخ احتياطي"}
        
        if not settings.auto_backup_enabled:
            logger.info(f"النسخ التلقائي غير مفعل للمستخدم {user_id}")
            return {"success": False, "error": "النسخ التلقائي غير مفعل"}
        
        # جمع البيانات للنسخ الاحتياطي
        backup_data = collect_backup_data(user_id, settings)
        
        # تحديد وجهة النسخ الاحتياطي
        if settings.backup_destination == 'google_drive':
            result = save_to_google_drive(user_id, backup_data, settings)
        else:
            result = save_to_local_storage(user_id, backup_data, settings)
        
        # تحديث إعدادات النسخ الاحتياطي
        if result.get("success"):
            update_backup_settings(settings, result)
        
        logger.info(f"انتهى النسخ الاحتياطي للمستخدم {user_id}: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"خطأ في النسخ الاحتياطي للمستخدم {user_id}: {e}")
        return {"success": False, "error": str(e)}

def collect_backup_data(user_id, settings):
    """
    جمع البيانات المطلوبة للنسخ الاحتياطي
    
    Args:
        user_id: معرف المستخدم
        settings: إعدادات النسخ الاحتياطي
    
    Returns:
        dict: البيانات المجمعة
    """
    backup_data = {
        "metadata": {
            "user_id": user_id,
            "backup_time": datetime.utcnow().isoformat(),
            "backup_type": "automatic",
            "version": "1.0"
        },
        "user_settings": {},
        "questions": [],
        "curriculum": {},
        "statistics": {}
    }
    
    try:
        # جمع إعدادات المستخدم
        if User:
            user = User.query.get(user_id)
            if user:
                backup_data["user_settings"] = {
                    "username": user.username,
                    "email": getattr(user, 'email', ''),
                    "is_admin": getattr(user, 'is_admin', False),
                    "created_at": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None
                }
        
        # جمع الأسئلة (إذا كانت متوفرة)
        if Question:
            questions = Question.query.all()
            for question in questions:
                question_data = {
                    "question_id": question.question_id,
                    "question_text": question.question_text,
                    "image_url": question.image_url,
                    "explanation": question.explanation,
                    "lesson_id": question.lesson_id,
                    "options": []
                }
                
                # جمع خيارات السؤال
                if hasattr(question, 'options') and question.options:
                    for option in question.options:
                        option_data = {
                            "option_id": option.option_id,
                            "option_text": option.option_text,
                            "is_correct": option.is_correct,
                            "image_url": getattr(option, 'image_url', None)
                        }
                        question_data["options"].append(option_data)
                
                backup_data["questions"].append(question_data)
        
        # جمع المناهج (إذا كانت متوفرة)
        if Course:
            courses = Course.query.all()
            backup_data["curriculum"]["courses"] = []
            
            for course in courses:
                course_data = {
                    "id": course.id,
                    "name": course.name,
                    "order_num": getattr(course, 'order_num', 0),
                    "units": []
                }
                
                # جمع الوحدات
                if Unit and hasattr(course, 'units'):
                    for unit in course.units:
                        unit_data = {
                            "id": unit.id,
                            "name": unit.name,
                            "order_num": getattr(unit, 'order_num', 0),
                            "lessons": []
                        }
                        
                        # جمع الدروس
                        if Lesson and hasattr(unit, 'lessons'):
                            for lesson in unit.lessons:
                                lesson_data = {
                                    "id": lesson.id,
                                    "name": lesson.name,
                                    "order_num": getattr(lesson, 'order_num', 0)
                                }
                                unit_data["lessons"].append(lesson_data)
                        
                        course_data["units"].append(unit_data)
                
                backup_data["curriculum"]["courses"].append(course_data)
        
        # جمع الإحصائيات
        backup_data["statistics"] = {
            "total_questions": len(backup_data["questions"]),
            "total_courses": len(backup_data["curriculum"].get("courses", [])),
            "backup_settings": {
                "auto_backup_enabled": settings.auto_backup_enabled,
                "backup_frequency": settings.backup_frequency,
                "backup_time": settings.backup_time,
                "max_backups": settings.max_backups,
                "backup_destination": settings.backup_destination
            }
        }
        
        logger.info(f"تم جمع البيانات للمستخدم {user_id}: {backup_data['statistics']['total_questions']} سؤال، {backup_data['statistics']['total_courses']} منهج")
        
    except Exception as e:
        logger.error(f"خطأ في جمع البيانات للمستخدم {user_id}: {e}")
    
    return backup_data

def save_to_google_drive(user_id, backup_data, settings):
    """
    حفظ النسخة الاحتياطية في Google Drive
    
    Args:
        user_id: معرف المستخدم
        backup_data: البيانات المراد نسخها
        settings: إعدادات النسخ الاحتياطي
    
    Returns:
        dict: نتيجة عملية الحفظ
    """
    try:
        if not google_drive_available:
            logger.warning("مكتبات Google Drive غير متوفرة، التحويل للحفظ المحلي")
            return save_to_local_storage(user_id, backup_data, settings)
        
        # محاولة الحصول على خدمة Google Drive
        service = get_google_drive_service(user_id)
        if not service:
            logger.warning(f"لا يمكن الوصول لخدمة Google Drive للمستخدم {user_id}, التحويل للحفظ المحلي")
            return save_to_local_storage(user_id, backup_data, settings)
        
        # تحويل البيانات إلى JSON
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        # إنشاء اسم الملف
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_user_{user_id}_{timestamp}.json"
        
        # رفع الملف إلى Google Drive
        file_stream = io.BytesIO(backup_json.encode('utf-8'))
        media = MediaIoBaseUpload(file_stream, mimetype='application/json')
        
        # البحث عن مجلد النسخ الاحتياطية أو إنشاؤه
        folder_id = get_or_create_backup_folder(service, f"نسخ احتياطية - المستخدم {user_id}")
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id] if folder_id else []
        }
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,size,createdTime'
        ).execute()
        
        # حذف النسخ القديمة إذا تجاوزت الحد الأقصى
        cleanup_old_backups(service, user_id, settings.max_backups)
        
        logger.info(f"تم حفظ النسخة الاحتياطية في Google Drive للمستخدم {user_id}: {file.get('id')}")
        
        return {
            "success": True,
            "destination": "google_drive",
            "file_id": file.get('id'),
            "filename": filename,
            "size": file.get('size'),
            "created_time": file.get('createdTime'),
            "backup_count": getattr(settings, 'backup_count', 0) + 1
        }
        
    except Exception as e:
        logger.error(f"خطأ في حفظ النسخة الاحتياطية في Google Drive للمستخدم {user_id}: {e}")
        # التحويل للحفظ المحلي في حالة الفشل
        return save_to_local_storage(user_id, backup_data, settings)

def save_to_local_storage(user_id, backup_data, settings):
    """
    حفظ النسخة الاحتياطية محلياً
    
    Args:
        user_id: معرف المستخدم
        backup_data: البيانات المراد نسخها
        settings: إعدادات النسخ الاحتياطي
    
    Returns:
        dict: نتيجة عملية الحفظ
    """
    try:
        import os
        
        # إنشاء مجلد النسخ الاحتياطية
        backup_dir = f"backups/user_{user_id}"
        os.makedirs(backup_dir, exist_ok=True)
        
        # إنشاء اسم الملف
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_user_{user_id}_{timestamp}.json"
        filepath = os.path.join(backup_dir, filename)
        
        # حفظ البيانات في ملف JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        # حذف النسخ القديمة إذا تجاوزت الحد الأقصى
        cleanup_old_local_backups(backup_dir, settings.max_backups)
        
        # حساب حجم الملف
        file_size = os.path.getsize(filepath)
        
        logger.info(f"تم حفظ النسخة الاحتياطية محلياً للمستخدم {user_id}: {filepath}")
        
        return {
            "success": True,
            "destination": "local",
            "filepath": filepath,
            "filename": filename,
            "size": file_size,
            "created_time": datetime.utcnow().isoformat(),
            "backup_count": getattr(settings, 'backup_count', 0) + 1
        }
        
    except Exception as e:
        logger.error(f"خطأ في حفظ النسخة الاحتياطية محلياً للمستخدم {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "destination": "local"
        }

def update_backup_settings(settings, backup_result):
    """
    تحديث إعدادات النسخ الاحتياطي بعد النسخ الناجح
    
    Args:
        settings: إعدادات النسخ الاحتياطي
        backup_result: نتيجة عملية النسخ
    """
    try:
        if not db:
            logger.warning("قاعدة البيانات غير متوفرة لتحديث الإعدادات")
            return
        
        # تحديث العداد وتاريخ آخر نسخة
        if settings.backup_count is None:
            settings.backup_count = 1
        else:
            settings.backup_count += 1
        
        settings.last_backup_time = datetime.utcnow()
        
        # حفظ التغييرات
        db.session.commit()
        
        logger.info(f"تم تحديث إعدادات النسخ الاحتياطي للمستخدم {settings.user_id}")
        
    except Exception as e:
        logger.error(f"خطأ في تحديث إعدادات النسخ الاحتياطي: {e}")
        if db:
            db.session.rollback()

def get_google_drive_service(user_id):
    """
    الحصول على خدمة Google Drive للمستخدم - نسخة محدثة
    
    Args:
        user_id: معرف المستخدم
    
    Returns:
        service: خدمة Google Drive أو None
    """
    try:
        if not GoogleDriveToken:
            logger.error("نموذج GoogleDriveToken غير متوفر")
            return None
        
        # الحصول على رمز المستخدم من قاعدة البيانات
        token_record = GoogleDriveToken.get_user_token(user_id)
        if not token_record:
            logger.warning(f"لا يوجد رمز Google Drive للمستخدم {user_id}")
            return None
        
        if not token_record.is_token_valid():
            logger.warning(f"رمز Google Drive غير صالح للمستخدم {user_id}")
            # محاولة تجديد الرمز
            if not refresh_token_if_needed(user_id):
                return None
            # إعادة جلب الرمز المحدث
            token_record = GoogleDriveToken.get_user_token(user_id)
            if not token_record or not token_record.is_token_valid():
                return None
        
        # إنشاء credentials من البيانات المحفوظة
        creds = Credentials(
            token=token_record.access_token,
            refresh_token=token_record.refresh_token,
            token_uri=token_record.token_uri,
            client_id=token_record.client_id,
            client_secret=token_record.client_secret,
            scopes=json.loads(token_record.scopes) if token_record.scopes else []
        )
        
        # تجديد الرمز إذا كان منتهي الصلاحية
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # حفظ الرمز المحدث
            token_record.access_token = creds.token
            token_record.expiry = creds.expiry
            if db:
                db.session.commit()
        
        # إنشاء خدمة Google Drive
        service = build('drive', 'v3', credentials=creds)
        logger.info(f"تم إنشاء خدمة Google Drive بنجاح للمستخدم {user_id}")
        return service
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على خدمة Google Drive للمستخدم {user_id}: {e}")
        return None

def refresh_token_if_needed(user_id):
    """
    تجديد الرمز المميز إذا كان منتهي الصلاحية
    
    Args:
        user_id: معرف المستخدم
    
    Returns:
        bool: True إذا تم التجديد بنجاح أو الرمز صالح
    """
    try:
        if not GoogleDriveToken:
            return False
        
        token_record = GoogleDriveToken.get_user_token(user_id)
        if not token_record:
            return False
        
        if token_record.expiry and token_record.expiry < datetime.utcnow():
            # الرمز منتهي الصلاحية، محاولة التجديد
            if token_record.refresh_token:
                creds = Credentials(
                    token=token_record.access_token,
                    refresh_token=token_record.refresh_token,
                    token_uri=token_record.token_uri,
                    client_id=token_record.client_id,
                    client_secret=token_record.client_secret
                )
                
                creds.refresh(Request())
                
                # تحديث قاعدة البيانات
                token_record.access_token = creds.token
                token_record.expiry = creds.expiry
                if db:
                    db.session.commit()
                
                logger.info(f"تم تجديد رمز Google Drive للمستخدم {user_id}")
                return True
            else:
                # لا يوجد refresh token، يحتاج إعادة تفويض
                token_record.is_active = False
                if db:
                    db.session.commit()
                logger.warning(f"لا يوجد refresh token للمستخدم {user_id}, يحتاج إعادة تفويض")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"خطأ في تجديد الرمز للمستخدم {user_id}: {e}")
        return False

def get_or_create_backup_folder(service, folder_name):
    """
    الحصول على مجلد النسخ الاحتياطية أو إنشاؤه
    
    Args:
        service: خدمة Google Drive
        folder_name: اسم المجلد
    
    Returns:
        str: معرف المجلد أو None
    """
    try:
        # البحث عن المجلد الموجود
        results = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
            fields="files(id, name)"
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            # المجلد موجود
            return folders[0]['id']
        else:
            # إنشاء مجلد جديد
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"تم إنشاء مجلد جديد: {folder_name}")
            return folder.get('id')
            
    except Exception as e:
        logger.error(f"خطأ في إنشاء/الحصول على المجلد {folder_name}: {e}")
        return None

def cleanup_old_backups(service, user_id, max_backups):
    """
    حذف النسخ الاحتياطية القديمة من Google Drive
    
    Args:
        service: خدمة Google Drive
        user_id: معرف المستخدم
        max_backups: الحد الأقصى للنسخ
    """
    try:
        if max_backups <= 0:
            return
        
        # البحث عن ملفات النسخ الاحتياطي
        query = f"name contains 'backup_user_{user_id}_' and mimeType='application/json'"
        results = service.files().list(
            q=query,
            orderBy='createdTime desc',
            fields="files(id, name, createdTime)"
        ).execute()
        
        files = results.get('files', [])
        
        # حذف الملفات الزائدة
        if len(files) > max_backups:
            files_to_delete = files[max_backups:]
            for file in files_to_delete:
                service.files().delete(fileId=file['id']).execute()
                logger.info(f"تم حذف النسخة الاحتياطية القديمة: {file['name']}")
                
    except Exception as e:
        logger.error(f"خطأ في تنظيف النسخ القديمة للمستخدم {user_id}: {e}")

def cleanup_old_local_backups(backup_dir, max_backups):
    """
    حذف النسخ الاحتياطية المحلية القديمة
    
    Args:
        backup_dir: مجلد النسخ الاحتياطية
        max_backups: الحد الأقصى للنسخ
    """
    try:
        import os
        import glob
        
        if max_backups <= 0:
            return
        
        # الحصول على قائمة ملفات النسخ الاحتياطي
        pattern = os.path.join(backup_dir, "backup_user_*.json")
        backup_files = glob.glob(pattern)
        
        # ترتيب الملفات حسب تاريخ التعديل (الأحدث أولاً)
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # حذف الملفات الزائدة
        if len(backup_files) > max_backups:
            files_to_delete = backup_files[max_backups:]
            for file_path in files_to_delete:
                os.remove(file_path)
                logger.info(f"تم حذف النسخة الاحتياطية المحلية القديمة: {file_path}")
                
    except Exception as e:
        logger.error(f"خطأ في تنظيف النسخ المحلية القديمة: {e}")

