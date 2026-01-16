"""
🔄 Automation Scheduler - جدولة الرسائل التلقائية الذكية
يستخدم smart_notifications.py الموجود
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from flask import current_app
from src.extensions import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Scheduler عام
automation_scheduler = None


def is_within_working_hours(start_hour, end_hour):
    """تحقق: هل الوقت الحالي ضمن ساعات العمل؟"""
    current_hour = datetime.now().hour
    return start_hour <= current_hour < end_hour


def send_automatic_messages_job():
    """
    الوظيفة الأساسية: إرسال الرسائل التلقائية الذكية
    يقرأ الإعدادات من ai_settings (نفس الإعدادات في Flutter)
    """
    try:
        with current_app.app_context():
            # 1. قراءة الإعدادات من DB (نفس أسماء Flutter)
            result = db.session.execute(text("""
                SELECT setting_key, setting_value 
                FROM ai_settings 
                WHERE setting_key IN (
                    'enable_auto_messages',
                    'automation_start_hour',
                    'automation_end_hour'
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
            
            from src.services.smart_notifications import smart_notifications
            from src.models.student import Student
            from src.models.ai_analysis import AIAnalysis
            
            # جلب جميع الطلاب النشطين
            students = Student.query.filter_by(is_active=True).all()
            logger.info(f"📊 عدد الطلاب النشطين: {len(students)}")
            
            sent_count = 0
            skipped_count = 0
            errors = 0
            
            for student in students:
                try:
                    # جلب آخر تحليل للطالب
                    latest_analysis = AIAnalysis.query.filter_by(
                        student_id=student.id
                    ).order_by(
                        AIAnalysis.created_at.desc()
                    ).first()
                    
                    if not latest_analysis:
                        # لا يوجد تحليل، تخطي
                        skipped_count += 1
                        continue
                    
                    # تحديد إذا كان الطالب يحتاج رسالة
                    needs_message = (
                        latest_analysis.status_category in ['orange', 'red'] or
                        latest_analysis.suggested_action in ['send_message', 'send_message_and_alert']
                    )
                    
                    if needs_message:
                        # إرسال رسالة ذكية
                        success = smart_notifications._send_smart_message(latest_analysis)
                        
                        if success:
                            sent_count += 1
                            logger.info(f"✅ أُرسلت رسالة للطالب {student.id} ({student.name})")
                        else:
                            errors += 1
                    else:
                        skipped_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ خطأ في معالجة الطالب {student.id}: {e}")
                    errors += 1
                    continue
            
            logger.info(f"""✅ اكتمل الإرسال التلقائي:
            • أُرسل: {sent_count} رسالة
            • تُخطي: {skipped_count} طالب
            • أخطاء: {errors}""")
            
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الرسائل التلقائية: {e}")
        import traceback
        traceback.print_exc()


def start_automation_scheduler(app):
    """بدء جدولة الرسائل التلقائية"""
    global automation_scheduler
    
    if automation_scheduler is not None:
        logger.warning("⚠️ Scheduler يعمل بالفعل!")
        return
    
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
        
        # إضافة job
        automation_scheduler.add_job(
            func=send_automatic_messages_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='automation_messages',
            name='إرسال الرسائل التلقائية الذكية',
            replace_existing=True
        )
        
        # بدء التشغيل
        automation_scheduler.start()
        
        logger.info(f"✅ بدء جدولة الرسائل التلقائية: كل {interval_hours} ساعة ({interval_minutes} دقيقة)")
        
    except Exception as e:
        logger.error(f"❌ فشل بدء Scheduler: {e}")
        import traceback
        traceback.print_exc()


def stop_automation_scheduler():
    """إيقاف جدولة الرسائل التلقائية"""
    global automation_scheduler
    
    if automation_scheduler is not None:
        automation_scheduler.shutdown()
        automation_scheduler = None
        logger.info("⏹️ تم إيقاف جدولة الرسائل التلقائية")


def restart_automation_scheduler(app):
    """إعادة تشغيل Scheduler (بعد تغيير الإعدادات)"""
    logger.info("🔄 إعادة تشغيل Scheduler...")
    stop_automation_scheduler()
    start_automation_scheduler(app)
