"""
🔄 Automation Scheduler - جدولة الرسائل التلقائية الذكية
يستخدم smart_notifications.py الموجود

⚠️ مهم: يستخدم قفل ملف لضمان تشغيل scheduler واحد فقط
حتى مع وجود عدة workers في Gunicorn
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from flask import current_app
from src.extensions import db
from sqlalchemy import text
import logging
import fcntl
import os
import atexit
try:
    import pytz
    _RIYADH_TZ = pytz.timezone('Asia/Riyadh')
except ImportError:
    _RIYADH_TZ = None

logger = logging.getLogger(__name__)

# Scheduler عام
automation_scheduler = None

# App reference للـ jobs (مهم!)
_flask_app = None

# قفل الملف لمنع تشغيل أكثر من scheduler
LOCK_FILE_PATH = '/tmp/automation_scheduler.lock'
_lock_file = None
_has_lock = False


def _acquire_scheduler_lock():
    """
    محاولة الحصول على قفل حصري للـ scheduler
    يضمن أن worker واحد فقط يشغّل الـ scheduler
    """
    global _lock_file, _has_lock
    
    try:
        # فتح/إنشاء ملف القفل
        _lock_file = open(LOCK_FILE_PATH, 'w')
        
        # محاولة الحصول على قفل حصري (non-blocking)
        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # نجحنا في الحصول على القفل
        _has_lock = True
        
        # كتابة معلومات الـ worker
        _lock_file.write(f"PID: {os.getpid()}\nTime: {datetime.now()}\n")
        _lock_file.flush()
        
        logger.info(f"🔒 Worker {os.getpid()} حصل على قفل الـ Scheduler")
        return True
        
    except (IOError, OSError) as e:
        # فشلنا - worker آخر يملك القفل
        _has_lock = False
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        logger.info(f"⏭️ Worker {os.getpid()} - الـ Scheduler يعمل في worker آخر")
        return False


def _release_scheduler_lock():
    """تحرير قفل الـ scheduler"""
    global _lock_file, _has_lock
    
    if _lock_file and _has_lock:
        try:
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()
            logger.info(f"🔓 Worker {os.getpid()} حرّر قفل الـ Scheduler")
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تحرير القفل: {e}")
        finally:
            _lock_file = None
            _has_lock = False


def is_within_working_hours(start_hour, end_hour):
    """تحقق: هل الوقت الحالي ضمن ساعات العمل؟ (توقيت الرياض)"""
    if _RIYADH_TZ:
        current_hour = datetime.now(_RIYADH_TZ).hour
    else:
        # fallback: إضافة 3 ساعات لتحويل UTC → Riyadh
        current_hour = (datetime.utcnow().hour + 3) % 24
    return start_hour <= current_hour < end_hour


def send_automatic_messages_job():
    """
    الوظيفة الأساسية: إرسال الرسائل التلقائية الذكية
    يقرأ الإعدادات من ai_settings (نفس الإعدادات في Flutter)
    """
    global _flask_app
    
    if _flask_app is None:
        logger.error("❌ Flask app not initialized!")
        return
    
    try:
        with _flask_app.app_context():
            # 1. قراءة الإعدادات من DB (نفس أسماء Flutter)
            result = db.session.execute(text("""
                SELECT setting_key, setting_value 
                FROM ai_settings 
                WHERE setting_key IN (
                    'enable_auto_messages',
                    'automation_start_hour',
                    'automation_end_hour',
                    'perform_fresh_analysis'
                )
            """)).fetchall()
            
            settings = {row[0]: row[1] for row in result}
            
            # 2. تحقق: هل الرسائل التلقائية مُفعّلة؟
            auto_messages_enabled = settings.get('enable_auto_messages', 'false') == 'true'
            if not auto_messages_enabled:
                logger.info("⏸️ الرسائل التلقائية معطّلة - تم تخطي الإرسال")
                return
            
            # 3. تحقق: هل نحن ضمن ساعات العمل؟
            start_hour = int(settings.get('automation_start_hour', 8))
            end_hour = int(settings.get('automation_end_hour', 22))
            
            if not is_within_working_hours(start_hour, end_hour):
                logger.info(f"⏰ خارج ساعات العمل ({start_hour}-{end_hour}) - تم تخطي الإرسال")
                return
            
            # 4. إرسال الرسائل الذكية!
            logger.info("📨 بدء إرسال الرسائل التلقائية الذكية...")
            
            # 4.1 قراءة إعداد التحليل
            perform_fresh_analysis = settings.get('perform_fresh_analysis', 'true') == 'true'
            logger.info(f"🔬 وضع التحليل: {'تحليل جديد' if perform_fresh_analysis else 'استخدام التحليل الأخير'}")
            
            from src.services.smart_notifications import smart_notifications
            from src.services.ai_assistant import ai_assistant
            from src.models.student import Student
            from src.models.ai_analysis import AIAnalysis
            
            # جلب جميع الطلاب النشطين
            students = Student.query.filter_by(is_active=True).all()
            logger.info(f"📊 عدد الطلاب النشطين: {len(students)}")
            
            analyzed_count = 0
            sent_count = 0
            skipped_count = 0
            errors = 0
            
            for student in students:
                try:
                    # الخطوة 1: الحصول على التحليل
                    if perform_fresh_analysis:
                        # 🔬 تحليل جديد للطالب (أدق)
                        logger.info(f"🔬 تحليل جديد للطالب {student.id} ({student.name})...")
                        
                        analysis_result = ai_assistant.analyze_student(
                            student_id=student.id,
                            analysis_type='automated'
                        )
                        
                        if not analysis_result:
                            logger.warning(f"⚠️ فشل تحليل الطالب {student.id}")
                            skipped_count += 1
                            continue
                        
                        analyzed_count += 1
                        
                        # جلب التحليل الجديد من Database
                        latest_analysis = AIAnalysis.query.filter_by(
                            student_id=student.id
                        ).order_by(
                            AIAnalysis.created_at.desc()
                        ).first()
                    else:
                        # 📚 استخدام آخر تحليل موجود (أسرع)
                        latest_analysis = AIAnalysis.query.filter_by(
                            student_id=student.id
                        ).order_by(
                            AIAnalysis.created_at.desc()
                        ).first()
                    
                    if not latest_analysis:
                        logger.warning(f"⚠️ لا يوجد تحليل للطالب {student.id}")
                        skipped_count += 1
                        continue
                    
                    # ✅ إرسال لجميع الطلاب بغض النظر عن مستوى الخطورة
                    try:
                        logger.info(f"📤 إرسال رسالة للطالب {student.id} ({latest_analysis.severity_level})...")
                        success = smart_notifications._send_smart_message(latest_analysis)

                        if success:
                            sent_count += 1
                            logger.info(f"✅ أُرسلت رسالة للطالب {student.id} ({student.name}) - {latest_analysis.severity_level}")
                        else:
                            logger.warning(f"⚠️ فشل إرسال رسالة للطالب {student.id}")
                            errors += 1
                    except Exception as send_error:
                        logger.error(f"❌ خطأ في إرسال رسالة للطالب {student.id}: {send_error}")
                        errors += 1
                    
                except Exception as e:
                    logger.error(f"❌ خطأ في معالجة الطالب {student.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    errors += 1
                    continue
            
            log_msg = f"""✅ اكتمل الإرسال التلقائي:
            • حُلّل: {analyzed_count} طالب (جديد)""" if perform_fresh_analysis else """✅ اكتمل الإرسال التلقائي:
            • استخدم التحليل السابق"""
            
            logger.info(log_msg + f"""
            • أُرسل: {sent_count} رسالة
            • تُخطي: {skipped_count} طالب
            • أخطاء: {errors}""")
            
            # ✅ تسجيل العملية في AILog (مهم للإحصائيات!)
            try:
                from src.models.ai_analysis import AILog
                AILog.log_operation(
                    operation_type='automation_send_messages',
                    description=f'إرسال تلقائي: {sent_count} رسالة، {analyzed_count if perform_fresh_analysis else 0} تحليل، {errors} أخطاء',
                    success=(errors == 0),
                    data={
                        'sent_count': sent_count,
                        'analyzed_count': analyzed_count if perform_fresh_analysis else 0,
                        'skipped_count': skipped_count,
                        'errors': errors,
                        'total_students': len(students),
                        'fresh_analysis': perform_fresh_analysis
                    }
                )
                logger.info("📊 تم تسجيل العملية في AILog")
            except Exception as log_error:
                logger.error(f"⚠️ فشل تسجيل AILog: {log_error}")
            
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الرسائل التلقائية: {e}")
        import traceback
        traceback.print_exc()


def check_manual_analysis_job():
    """
    فحص إذا فيه طلب تحليل يدوي من التطبيق
    يشتغل كل 10 ثواني
    """
    global _flask_app

    if _flask_app is None:
        return

    try:
        with _flask_app.app_context():
            import json as _json

            # قراءة حالة التحليل من DB
            result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'analysis_job_status'
            """)).fetchone()

            status = result[0] if result else 'idle'

            if status != 'running':
                return

            # تحقق من التقدم
            progress_result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'analysis_job_progress'
            """)).fetchone()

            progress = _json.loads(progress_result[0]) if progress_result else {}
            total = progress.get('total', 0)

            # إذا total=0 يعني لسا ما بدأ التحليل الفعلي
            if total == 0:
                logger.info("📋 [Scheduler] طلب تحليل يدوي - جاري التنفيذ...")

                try:
                    from src.tasks.student_analyzer import student_analyzer
                    student_analyzer.is_running = False
                    result = student_analyzer.analyze_all_students()

                    # حفظ النتيجة
                    from src.models.ai_analysis import AISetting
                    AISetting.set_setting('analysis_job_status', 'completed', 'string')
                    AISetting.set_setting('analysis_job_progress', _json.dumps(result), 'json')
                    logger.info(f"✅ [Scheduler] اكتمل التحليل اليدوي: {result.get('analyzed', 0)} طالب")
                except Exception as e:
                    logger.error(f"❌ [Scheduler] فشل التحليل اليدوي: {e}")
                    import traceback
                    traceback.print_exc()
                    from src.models.ai_analysis import AISetting
                    AISetting.set_setting('analysis_job_status', 'failed', 'string')
                    AISetting.set_setting('analysis_job_progress', _json.dumps({
                        'error': str(e)
                    }), 'json')

    except Exception as e:
        logger.error(f"❌ [Scheduler] خطأ في check_manual_analysis_job: {e}")


def check_single_student_analysis_job():
    """فحص إذا فيه طلب تحليل طالب واحد"""
    global _flask_app

    if _flask_app is None:
        return

    try:
        with _flask_app.app_context():
            import json as _json

            result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'single_analysis_job_status'
            """)).fetchone()

            status = result[0] if result else 'idle'

            if status != 'running':
                return

            # جلب بيانات الطلب
            data_result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'single_analysis_job_data'
            """)).fetchone()

            data = _json.loads(data_result[0]) if data_result else {}
            student_id = data.get('student_id')

            if not student_id:
                return

            logger.info(f"📋 [Scheduler] طلب تحليل طالب {student_id} - جاري التنفيذ...")

            try:
                from src.services.ai_assistant import ai_assistant
                from src.services.smart_notifications import smart_notifications
                from src.models.ai_analysis import AISetting, AIAnalysis

                analysis_result = ai_assistant.analyze_student(
                    student_id=student_id,
                    analysis_type='manual'
                )

                # إرسال إشعار بناءً على نتيجة التحليل
                latest_analysis = AIAnalysis.query.filter_by(
                    student_id=student_id
                ).order_by(AIAnalysis.created_at.desc()).first()

                if latest_analysis:
                    action_taken = smart_notifications.process_analysis_result(latest_analysis)
                    logger.info(f"📤 [Scheduler] إشعار للطالب {student_id}: action={action_taken}")

                AISetting.set_setting('single_analysis_job_status', 'completed', 'string')
                AISetting.set_setting('single_analysis_job_data', _json.dumps(
                    analysis_result if analysis_result else {'error': 'no result'}
                ), 'json')
                logger.info(f"✅ [Scheduler] اكتمل تحليل الطالب {student_id}")

            except Exception as e:
                logger.error(f"❌ [Scheduler] فشل تحليل الطالب {student_id}: {e}")
                from src.models.ai_analysis import AISetting
                AISetting.set_setting('single_analysis_job_status', 'failed', 'string')
                AISetting.set_setting('single_analysis_job_data', _json.dumps({
                    'error': str(e)
                }), 'json')

    except Exception as e:
        logger.error(f"❌ [Scheduler] خطأ في check_single_student_analysis_job: {e}")


def check_lesson_prep_job():
    """فحص إذا فيه طلب تحضير درس بالـ AI"""
    global _flask_app

    if _flask_app is None:
        return

    try:
        with _flask_app.app_context():
            import json as _json

            result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'lesson_prep_job_status'
            """)).fetchone()

            status = result[0] if result else 'idle'

            if status != 'running':
                return

            data_result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'lesson_prep_job_data'
            """)).fetchone()

            data = _json.loads(data_result[0]) if data_result else {}
            plan_id = data.get('plan_id')
            plan_type = data.get('type', 'single_lesson')

            if not plan_id:
                return

            logger.info(f"📝 [Scheduler] طلب تحضير درس #{plan_id} ({plan_type}) - جاري التنفيذ...")

            try:
                from src.services.lesson_prep_service import lesson_prep_service

                if plan_type == 'unit_distribution':
                    success = lesson_prep_service.generate_unit_distribution(plan_id)
                else:
                    success = lesson_prep_service.generate_lesson_plan(plan_id)

                from src.models.ai_analysis import AISetting
                AISetting.set_setting('lesson_prep_job_status', 'completed' if success else 'failed', 'string')
                logger.info(f"{'✅' if success else '❌'} [Scheduler] تحضير #{plan_id}: {'نجح' if success else 'فشل'}")

            except Exception as e:
                logger.error(f"❌ [Scheduler] فشل تحضير #{plan_id}: {e}")
                import traceback
                traceback.print_exc()
                from src.models.ai_analysis import AISetting
                AISetting.set_setting('lesson_prep_job_status', 'failed', 'string')

    except Exception as e:
        logger.error(f"❌ [Scheduler] خطأ في check_lesson_prep_job: {e}")


def check_notification_effectiveness_job():
    """فحص فعالية الإشعارات يومياً"""
    global _flask_app

    if _flask_app is None:
        return

    try:
        with _flask_app.app_context():
            from src.tasks.student_analyzer import student_analyzer
            logger.info("📊 [Scheduler] فحص فعالية الإشعارات...")
            result = student_analyzer.check_notification_effectiveness()
            logger.info(f"✅ [Scheduler] فعالية الإشعارات: {result.get('total_sent', 0)} إشعار")
    except Exception as e:
        logger.error(f"❌ [Scheduler] خطأ في فحص فعالية الإشعارات: {e}")


def start_automation_scheduler(app):
    """بدء جدولة الرسائل التلقائية"""
    global automation_scheduler, _flask_app, _has_lock

    # ⚠️ محاولة الحصول على القفل أولاً
    if not _acquire_scheduler_lock():
        logger.info(f"⏭️ Worker {os.getpid()} - تخطي تشغيل الـ Scheduler (يعمل في worker آخر)")
        return

    if automation_scheduler is not None:
        logger.warning("⚠️ Scheduler يعمل بالفعل!")
        return

    # حفظ reference للـ app (مهم جداً!)
    _flask_app = app

    try:
        with app.app_context():
            # قراءة interval من DB (بالساعات، نحوله لدقائق)
            result = db.session.execute(text("""
                SELECT setting_value
                FROM ai_settings
                WHERE setting_key = 'analysis_interval_hours'
            """)).fetchone()

            interval_hours = int(result[0]) if result else 24
            interval_minutes = interval_hours * 60  # تحويل من ساعات لدقائق

        # إنشاء scheduler
        automation_scheduler = BackgroundScheduler(daemon=True)

        # إضافة job الرسائل التلقائية
        automation_scheduler.add_job(
            func=send_automatic_messages_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='automation_messages',
            name='إرسال الرسائل التلقائية الذكية',
            replace_existing=True
        )

        # ✅ إضافة job فحص طلبات التحليل اليدوية (كل 10 ثواني)
        automation_scheduler.add_job(
            func=check_manual_analysis_job,
            trigger=IntervalTrigger(seconds=10),
            id='check_manual_analysis',
            name='فحص طلبات التحليل اليدوية',
            replace_existing=True
        )

        # ✅ إضافة job فحص تحليل طالب واحد (كل 5 ثواني)
        automation_scheduler.add_job(
            func=check_single_student_analysis_job,
            trigger=IntervalTrigger(seconds=5),
            id='check_single_analysis',
            name='فحص تحليل طالب واحد',
            replace_existing=True
        )

        # ✅ فحص طلبات تحضير الدروس (كل 5 ثواني)
        automation_scheduler.add_job(
            func=check_lesson_prep_job,
            trigger=IntervalTrigger(seconds=5),
            id='check_lesson_prep',
            name='فحص طلبات تحضير الدروس',
            replace_existing=True
        )

        # ✅ فحص فعالية الإشعارات يومياً (كل 24 ساعة)
        automation_scheduler.add_job(
            func=check_notification_effectiveness_job,
            trigger=IntervalTrigger(hours=24),
            id='check_notification_effectiveness',
            name='فحص فعالية الإشعارات',
            replace_existing=True
        )

        # بدء التشغيل
        automation_scheduler.start()

        # تسجيل تحرير القفل عند إغلاق التطبيق
        atexit.register(_release_scheduler_lock)
        atexit.register(stop_automation_scheduler)

        logger.info(f"✅ Worker {os.getpid()} - بدء جدولة الرسائل التلقائية: كل {interval_hours} ساعة ({interval_minutes} دقيقة)")
        logger.info(f"✅ فحص طلبات التحليل اليدوية: كل 10 ثواني")

    except Exception as e:
        logger.error(f"❌ فشل بدء Scheduler: {e}")
        _release_scheduler_lock()  # تحرير القفل في حالة الفشل
        import traceback
        traceback.print_exc()


def stop_automation_scheduler():
    """إيقاف جدولة الرسائل التلقائية"""
    global automation_scheduler, _has_lock
    
    if automation_scheduler is not None:
        automation_scheduler.shutdown()
        automation_scheduler = None
        logger.info("⏹️ تم إيقاف جدولة الرسائل التلقائية")
    
    # تحرير القفل
    if _has_lock:
        _release_scheduler_lock()
    
    # ملاحظة: نحتفظ بـ _flask_app للـ restart


def restart_automation_scheduler(app):
    """إعادة تشغيل Scheduler (بعد تغيير الإعدادات)"""
    logger.info("🔄 إعادة تشغيل Scheduler...")
    stop_automation_scheduler()
    start_automation_scheduler(app)


def reschedule_automation():
    """
    إعادة جدولة الـ Scheduler عند تغيير الإعدادات
    يُستدعى من admin_ai.py عند تحديث:
    - analysis_interval_hours
    - automation_start_hour
    - automation_end_hour
    """
    global automation_scheduler, _flask_app
    
    if automation_scheduler is None:
        logger.warning("⚠️ Scheduler غير مفعّل، لا يمكن إعادة الجدولة")
        return False
    
    if _flask_app is None:
        logger.error("❌ Flask app not initialized!")
        return False
    
    try:
        logger.info("🔄 بدء إعادة جدولة الـ Scheduler...")
        
        with _flask_app.app_context():
            # قراءة الإعدادات الجديدة من Database
            result = db.session.execute(text("""
                SELECT setting_value 
                FROM ai_settings 
                WHERE setting_key = 'analysis_interval_hours'
            """)).fetchone()
            
            interval_hours = int(result[0]) if result else 24
            interval_minutes = interval_hours * 60
            
            logger.info(f"📊 الإعدادات الجديدة:")
            logger.info(f"   • فترة التحليل: {interval_hours} ساعة ({interval_minutes} دقيقة)")
        
        # حذف Job القديم
        try:
            automation_scheduler.remove_job('automation_messages')
            logger.info("✅ تم حذف Job القديم")
        except Exception as e:
            logger.warning(f"⚠️ Job غير موجود (عادي): {e}")
        
        # إضافة Job جديد بالإعدادات المحدثة
        automation_scheduler.add_job(
            func=send_automatic_messages_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='automation_messages',
            name='إرسال الرسائل التلقائية الذكية',
            replace_existing=True
        )
        
        logger.info(f"✅ تم إعادة جدولة Scheduler بنجاح!")
        logger.info(f"   • التشغيل التالي: بعد {interval_hours} ساعة")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة الجدولة: {e}")
        import traceback
        traceback.print_exc()
        return False
