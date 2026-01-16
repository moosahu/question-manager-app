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

# App reference للـ jobs (مهم!)
_flask_app = None


def is_within_working_hours(start_hour, end_hour):
    """تحقق: هل الوقت الحالي ضمن ساعات العمل؟"""
    current_hour = datetime.now().hour
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
                    
                    # ✅ تحديد إذا كان الطالب يحتاج رسالة (باستخدام التحليل الجديد)
                    needs_message = (
                        # فحص مستوى الخطورة (orange أو red)
                        latest_analysis.severity_level in ['orange', 'red'] or
                        # أو حالة الطالب (needs_attention أو critical)
                        latest_analysis.student_status in ['needs_attention', 'critical'] or
                        # أو الإجراء المقترح هو إرسال رسالة
                        latest_analysis.suggested_action == 'send_message'
                    )
                    
                    if needs_message:
                        # إرسال رسالة ذكية
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
                    else:
                        skipped_count += 1
                        logger.debug(f"⏭️ تخطي الطالب {student.id} - {latest_analysis.severity_level} (لا يحتاج رسالة)")
                    
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


def start_automation_scheduler(app):
    """بدء جدولة الرسائل التلقائية"""
    global automation_scheduler, _flask_app
    
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
    
    # ملاحظة: نحتفظ بـ _flask_app للـ restart


def restart_automation_scheduler(app):
    """إعادة تشغيل Scheduler (بعد تغيير الإعدادات)"""
    logger.info("🔄 إعادة تشغيل Scheduler...")
    stop_automation_scheduler()
    start_automation_scheduler(app)
