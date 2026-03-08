"""
نظام جدولة النسخ الاحتياطي باستخدام APScheduler - نسخة محدثة
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import atexit
import json
import os
import threading

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# استيراد النماذج والوظائف المطلوبة
try:
    from src.extensions import db
    from src.models.backup_settings import BackupSettings
    from src.models.user import User
    from backup_logic import perform_backup_for_user
except ImportError:
    try:
        from extensions import db
        from models.backup_settings import BackupSettings
        from models.user import User
        from backup_logic import perform_backup_for_user
    except ImportError:
        try:
            from backup_settings import BackupSettings
            from backup_logic import perform_backup_for_user
            # إذا فشل استيراد db، سنحاول استيراده لاحقاً
            db = None
        except ImportError:
            logger.error("فشل في استيراد النماذج المطلوبة")
            BackupSettings = None
            perform_backup_for_user = None
            db = None

class BackupScheduler:
    """
    فئة إدارة جدولة النسخ الاحتياطي - نسخة محدثة
    """
    
    def __init__(self, app=None):
        """
        تهيئة جدولة النسخ الاحتياطي
        
        Args:
            app: تطبيق Flask (اختياري)
        """
        self.app = app
        self.is_running = False
        self.backup_jobs = {}  # تتبع المهام المجدولة
        self._lock = threading.Lock()  # حماية من التداخل

        # تهيئة APScheduler دائماً (بغض النظر عن وجود app)
        self.init_app(app)
    
    def init_app(self, app):
        """
        تهيئة الجدولة مع تطبيق Flask
        
        Args:
            app: تطبيق Flask
        """
        self.app = app
        
        # إعداد الجدولة
        self.scheduler = BackgroundScheduler(
            timezone='UTC',
            job_defaults={
                'coalesce': True,  # دمج المهام المتأخرة
                'max_instances': 1,  # مهمة واحدة فقط في كل مرة
                'misfire_grace_time': 300  # 5 دقائق تسامح للمهام المتأخرة
            }
        )
        
        # إضافة مستمعي الأحداث
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        
        # تسجيل إيقاف الجدولة عند إغلاق التطبيق
        atexit.register(self.shutdown)
        
        logger.info("تم تهيئة جدولة النسخ الاحتياطي بنجاح")
    
    def start(self):
        """
        بدء تشغيل الجدولة
        """
        with self._lock:
            if not self.scheduler:
                logger.error("لم يتم تهيئة الجدولة بعد")
                return False
            
            try:
                if not self.is_running:
                    self.scheduler.start()
                    self.is_running = True
                    logger.info("تم بدء تشغيل جدولة النسخ الاحتياطي")
                    
                    # تحميل المهام المحفوظة
                    self._load_scheduled_jobs()
                    
                    return True
                else:
                    logger.warning("الجدولة تعمل بالفعل")
                    return True
            except Exception as e:
                logger.error(f"خطأ في بدء تشغيل الجدولة: {e}")
                return False
    
    def stop(self):
        """
        إيقاف الجدولة مؤقتاً
        """
        with self._lock:
            if self.scheduler and self.is_running:
                try:
                    self.scheduler.pause()
                    self.is_running = False
                    logger.info("تم إيقاف جدولة النسخ الاحتياطي مؤقتاً")
                    return True
                except Exception as e:
                    logger.error(f"خطأ في إيقاف الجدولة: {e}")
                    return False
            return True
    
    def shutdown(self):
        """
        إيقاف الجدولة نهائياً
        """
        with self._lock:
            if self.scheduler and self.is_running:
                try:
                    # حفظ المهام المجدولة
                    self._save_scheduled_jobs()
                    
                    self.scheduler.shutdown(wait=False)
                    self.is_running = False
                    logger.info("تم إيقاف جدولة النسخ الاحتياطي نهائياً")
                except Exception as e:
                    logger.error(f"خطأ في إيقاف الجدولة: {e}")
    
    def schedule_user_backup(self, user_id, backup_settings=None):
        """
        جدولة النسخ الاحتياطي لمستخدم محدد
        
        Args:
            user_id: معرف المستخدم
            backup_settings: إعدادات النسخ الاحتياطي (اختياري)
        
        Returns:
            bool: True إذا تم الجدولة بنجاح
        """
        try:
            # التحقق من تشغيل الجدولة
            if not self.is_running:
                logger.warning("الجدولة غير مشغلة، سيتم بدء تشغيلها")
                if not self.start():
                    return False
            
            # الحصول على إعدادات النسخ الاحتياطي
            if not backup_settings:
                # محاكاة إعدادات افتراضية إذا لم تكن متوفرة
                backup_settings = {
                    'auto_backup_enabled': True,
                    'backup_frequency': 'daily',
                    'backup_time': '02:00',
                    'backup_destination': 'local'
                }
                
                # محاولة الحصول على الإعدادات الفعلية
                if BackupSettings:
                    try:
                        real_settings = BackupSettings.get_user_settings(user_id)
                        if real_settings and real_settings.auto_backup_enabled:
                            backup_settings = {
                                'auto_backup_enabled': real_settings.auto_backup_enabled,
                                'backup_frequency': real_settings.backup_frequency,
                                'backup_time': real_settings.backup_time,
                                'backup_destination': real_settings.backup_destination
                            }
                    except Exception as e:
                        logger.warning(f"فشل في الحصول على إعدادات المستخدم {user_id}: {e}")
            
            if not backup_settings.get('auto_backup_enabled', False):
                logger.info(f"النسخ التلقائي غير مفعل للمستخدم {user_id}")
                return False
            
            # إزالة المهمة السابقة إن وجدت
            job_id = f"backup_user_{user_id}"
            self.remove_user_backup(user_id)
            
            # تحديد نوع الجدولة
            backup_frequency = backup_settings.get('backup_frequency', 'daily')
            backup_time = backup_settings.get('backup_time', '02:00')
            
            if backup_frequency == 'daily':
                trigger = self._create_daily_trigger(backup_time)
            elif backup_frequency == 'weekly':
                trigger = self._create_weekly_trigger(backup_time)
            elif backup_frequency == 'monthly':
                trigger = self._create_monthly_trigger(backup_time)
            else:
                logger.error(f"تكرار النسخ غير مدعوم: {backup_frequency}")
                return False
            
            # إضافة المهمة للجدولة
            self.scheduler.add_job(
                func=self._execute_backup,
                trigger=trigger,
                id=job_id,
                args=[user_id],
                name=f"نسخ احتياطي للمستخدم {user_id}",
                replace_existing=True
            )
            
            # حفظ معلومات المهمة
            self.backup_jobs[user_id] = {
                'job_id': job_id,
                'frequency': backup_frequency,
                'time': backup_time,
                'destination': backup_settings.get('backup_destination', 'local'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"تم جدولة النسخ الاحتياطي للمستخدم {user_id} - {backup_frequency} في {backup_time}")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في جدولة النسخ الاحتياطي للمستخدم {user_id}: {e}")
            return False
    
    def remove_user_backup(self, user_id):
        """
        إزالة جدولة النسخ الاحتياطي لمستخدم محدد
        
        Args:
            user_id: معرف المستخدم
        
        Returns:
            bool: True إذا تم الحذف بنجاح
        """
        try:
            job_id = f"backup_user_{user_id}"
            
            # إزالة المهمة من الجدولة
            if self.scheduler and self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"تم إزالة جدولة النسخ الاحتياطي للمستخدم {user_id}")
            
            # إزالة معلومات المهمة
            if user_id in self.backup_jobs:
                del self.backup_jobs[user_id]
            
            return True
            
        except Exception as e:
            logger.error(f"خطأ في إزالة جدولة النسخ الاحتياطي للمستخدم {user_id}: {e}")
            return False
    
    def schedule_all_users(self):
        """
        جدولة النسخ الاحتياطي لجميع المستخدمين الذين فعلوا النسخ التلقائي
        
        Returns:
            int: عدد المستخدمين الذين تم جدولة النسخ لهم
        """
        scheduled_count = 0
        
        try:
            if not BackupSettings:
                logger.warning("نموذج BackupSettings غير متوفر، سيتم استخدام إعدادات افتراضية")
                # جدولة افتراضية للمستخدم الإداري
                if self.schedule_user_backup(1):  # افتراض أن المستخدم الإداري له ID = 1
                    scheduled_count = 1
                return scheduled_count
            
            # الحصول على جميع المستخدمين الذين فعلوا النسخ التلقائي
            with self.app.app_context() if self.app else self._dummy_context():
                enabled_settings = BackupSettings.query.filter_by(auto_backup_enabled=True).all()
                
                for settings in enabled_settings:
                    settings_dict = {
                        'auto_backup_enabled': settings.auto_backup_enabled,
                        'backup_frequency': settings.backup_frequency,
                        'backup_time': settings.backup_time,
                        'backup_destination': settings.backup_destination
                    }
                    
                    if self.schedule_user_backup(settings.user_id, settings_dict):
                        scheduled_count += 1
            
            logger.info(f"تم جدولة النسخ الاحتياطي لـ {scheduled_count} مستخدم")
            
        except Exception as e:
            logger.error(f"خطأ في جدولة النسخ لجميع المستخدمين: {e}")
        
        return scheduled_count
    
    def get_scheduled_jobs(self):
        """
        الحصول على قائمة المهام المجدولة
        
        Returns:
            list: قائمة المهام المجدولة
        """
        jobs = []
        
        try:
            if not self.scheduler:
                return jobs
                
            for job in self.scheduler.get_jobs():
                if job.id.startswith('backup_user_'):
                    user_id = int(job.id.replace('backup_user_', ''))
                    next_run = job.next_run_time.isoformat() if job.next_run_time else None
                    
                    job_info = {
                        'user_id': user_id,
                        'job_id': job.id,
                        'name': job.name,
                        'next_run': next_run,
                        'trigger': str(job.trigger)
                    }
                    
                    # إضافة معلومات إضافية من backup_jobs
                    if user_id in self.backup_jobs:
                        job_info.update(self.backup_jobs[user_id])
                    
                    jobs.append(job_info)
        
        except Exception as e:
            logger.error(f"خطأ في الحصول على المهام المجدولة: {e}")
        
        return jobs
    
    def trigger_immediate_backup(self, user_id):
        """
        تشغيل نسخ احتياطي فوري لمستخدم محدد
        
        Args:
            user_id: معرف المستخدم
        
        Returns:
            bool: True إذا تم التشغيل بنجاح
        """
        try:
            # التحقق من تشغيل الجدولة
            if not self.is_running:
                if not self.start():
                    return False
            
            # تشغيل النسخ الاحتياطي في مهمة منفصلة
            job_id = f"immediate_backup_user_{user_id}_{int(datetime.utcnow().timestamp())}"
            
            self.scheduler.add_job(
                func=self._execute_backup,
                trigger='date',  # تشغيل فوري
                id=job_id,
                args=[user_id],
                name=f"نسخ احتياطي فوري للمستخدم {user_id}"
            )
            
            logger.info(f"تم تشغيل نسخ احتياطي فوري للمستخدم {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في تشغيل النسخ الاحتياطي الفوري للمستخدم {user_id}: {e}")
            return False
    
    def _execute_backup(self, user_id):
        """
        تنفيذ النسخ الاحتياطي لمستخدم محدد
        
        Args:
            user_id: معرف المستخدم
        """
        try:
            logger.info(f"بدء تنفيذ النسخ الاحتياطي للمستخدم {user_id}")
            
            # التحقق من وجود وظيفة النسخ الاحتياطي
            if perform_backup_for_user:
                # تنفيذ النسخ الاحتياطي
                with self.app.app_context() if self.app else self._dummy_context():
                    perform_backup_for_user(user_id)
                
                logger.info(f"تم إكمال النسخ الاحتياطي للمستخدم {user_id} بنجاح")
            else:
                # محاكاة النسخ الاحتياطي
                logger.info(f"محاكاة النسخ الاحتياطي للمستخدم {user_id} (الوظيفة غير متوفرة)")
                
        except Exception as e:
            logger.error(f"خطأ في تنفيذ النسخ الاحتياطي للمستخدم {user_id}: {e}")
            raise
    
    def _create_daily_trigger(self, backup_time):
        """
        إنشاء trigger للنسخ اليومي
        
        Args:
            backup_time: وقت النسخ (HH:MM)
        
        Returns:
            CronTrigger: trigger للنسخ اليومي
        """
        try:
            hour, minute = map(int, backup_time.split(':'))
            return CronTrigger(hour=hour, minute=minute)
        except:
            # إعدادات افتراضية
            return CronTrigger(hour=2, minute=0)
    
    def _create_weekly_trigger(self, backup_time):
        """
        إنشاء trigger للنسخ الأسبوعي
        
        Args:
            backup_time: وقت النسخ (HH:MM)
        
        Returns:
            CronTrigger: trigger للنسخ الأسبوعي
        """
        try:
            hour, minute = map(int, backup_time.split(':'))
            return CronTrigger(day_of_week=0, hour=hour, minute=minute)  # الأحد
        except:
            # إعدادات افتراضية
            return CronTrigger(day_of_week=0, hour=2, minute=0)
    
    def _create_monthly_trigger(self, backup_time):
        """
        إنشاء trigger للنسخ الشهري
        
        Args:
            backup_time: وقت النسخ (HH:MM)
        
        Returns:
            CronTrigger: trigger للنسخ الشهري
        """
        try:
            hour, minute = map(int, backup_time.split(':'))
            return CronTrigger(day=1, hour=hour, minute=minute)  # أول يوم في الشهر
        except:
            # إعدادات افتراضية
            return CronTrigger(day=1, hour=2, minute=0)
    
    def _job_executed_listener(self, event):
        """
        مستمع تنفيذ المهام
        
        Args:
            event: حدث تنفيذ المهمة
        """
        logger.info(f"تم تنفيذ المهمة بنجاح: {event.job_id}")
    
    def _job_error_listener(self, event):
        """
        مستمع أخطاء المهام
        
        Args:
            event: حدث خطأ المهمة
        """
        logger.error(f"خطأ في تنفيذ المهمة {event.job_id}: {event.exception}")
    
    def _save_scheduled_jobs(self):
        """
        حفظ معلومات المهام المجدولة في ملف
        """
        try:
            jobs_file = 'scheduled_backup_jobs.json'
            with open(jobs_file, 'w', encoding='utf-8') as f:
                json.dump(self.backup_jobs, f, ensure_ascii=False, indent=2)
            logger.info(f"تم حفظ معلومات المهام المجدولة في {jobs_file}")
        except Exception as e:
            logger.error(f"خطأ في حفظ معلومات المهام: {e}")
    
    def _load_scheduled_jobs(self):
        """
        تحميل معلومات المهام المجدولة من ملف
        """
        try:
            jobs_file = 'scheduled_backup_jobs.json'
            if os.path.exists(jobs_file):
                with open(jobs_file, 'r', encoding='utf-8') as f:
                    self.backup_jobs = json.load(f)
                logger.info(f"تم تحميل معلومات المهام المجدولة من {jobs_file}")
                
                # إعادة جدولة المهام
                self.schedule_all_users()
        except Exception as e:
            logger.error(f"خطأ في تحميل معلومات المهام: {e}")
    
    def _dummy_context(self):
        """
        سياق وهمي في حالة عدم توفر تطبيق Flask
        """
        class DummyContext:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        
        return DummyContext()

# إنشاء مثيل عام للجدولة
backup_scheduler = BackupScheduler()

def init_backup_scheduler(app):
    """
    تهيئة جدولة النسخ الاحتياطي مع تطبيق Flask
    
    Args:
        app: تطبيق Flask
    
    Returns:
        BackupScheduler: مثيل الجدولة
    """
    backup_scheduler.init_app(app)
    return backup_scheduler

def start_backup_scheduler():
    """
    بدء تشغيل جدولة النسخ الاحتياطي
    
    Returns:
        bool: True إذا تم البدء بنجاح
    """
    return backup_scheduler.start()

def stop_backup_scheduler():
    """
    إيقاف جدولة النسخ الاحتياطي
    
    Returns:
        bool: True إذا تم الإيقاف بنجاح
    """
    return backup_scheduler.stop()

def schedule_user_backup(user_id, backup_settings=None):
    """
    جدولة النسخ الاحتياطي لمستخدم محدد
    
    Args:
        user_id: معرف المستخدم
        backup_settings: إعدادات النسخ الاحتياطي (اختياري)
    
    Returns:
        bool: True إذا تم الجدولة بنجاح
    """
    return backup_scheduler.schedule_user_backup(user_id, backup_settings)

def remove_user_backup_schedule(user_id):
    """
    إزالة جدولة النسخ الاحتياطي لمستخدم محدد
    
    Args:
        user_id: معرف المستخدم
    
    Returns:
        bool: True إذا تم الحذف بنجاح
    """
    return backup_scheduler.remove_user_backup(user_id)

def trigger_immediate_backup(user_id):
    """
    تشغيل نسخ احتياطي فوري لمستخدم محدد
    
    Args:
        user_id: معرف المستخدم
    
    Returns:
        bool: True إذا تم التشغيل بنجاح
    """
    return backup_scheduler.trigger_immediate_backup(user_id)

def get_scheduled_backup_jobs():
    """
    الحصول على قائمة المهام المجدولة
    
    Returns:
        list: قائمة المهام المجدولة
    """
    return backup_scheduler.get_scheduled_jobs()

def get_scheduler_status():
    """
    الحصول على حالة الجدولة
    
    Returns:
        dict: معلومات حالة الجدولة
    """
    return {
        'is_running': backup_scheduler.is_running,
        'jobs_count': len(backup_scheduler.get_scheduled_jobs()),
        'scheduler_available': backup_scheduler.scheduler is not None
    }

