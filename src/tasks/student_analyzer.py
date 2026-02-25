# src/tasks/student_analyzer.py

"""
مهمة تحليل الطلاب التلقائية
تعمل كل 6 ساعات (أو حسب الإعداد) لتحليل جميع الطلاب
"""

from datetime import datetime, timedelta
from typing import List, Dict

from src.models.student import Student
from src.models.ai_analysis import AIAnalysis, AILog, AISetting
from src.services.ai_assistant import ai_assistant
from src.services.smart_notifications import smart_notifications
from src.extensions import db


class StudentAnalyzer:
    """محلل الطلاب التلقائي"""

    def __init__(self):
        """تهيئة المحلل"""
        self.is_running = False

    def analyze_all_students(self) -> Dict:
        """
        تحليل جميع الطلاب النشطين

        Returns:
            تقرير بالنتائج
        """
        if self.is_running:
            print("⚠️ التحليل يعمل بالفعل...")
            return {'status': 'already_running'}

        self.is_running = True
        start_time = datetime.utcnow()

        try:
            print("🚀 بدء التحليل التلقائي للطلاب...")

            # جلب جميع الطلاب النشطين
            students = Student.query.filter_by(is_active=True).all()

            if not students:
                print("⚠️ لا يوجد طلاب نشطين")
                self.is_running = False
                return {
                    'status': 'no_students',
                    'total_students': 0
                }

            print(f"📊 عدد الطلاب: {len(students)}")

            results = {
                'total': len(students),
                'analyzed': 0,
                'failed': 0,
                'actions_taken': 0,
                'by_severity': {
                    'green': 0,
                    'yellow': 0,
                    'orange': 0,
                    'red': 0
                },
                'details': []
            }

            # تحليل كل طالب مع تحديث التقدم في DB
            for i, student in enumerate(students):
                try:
                    result = self._analyze_single_student(student)

                    if result:
                        results['analyzed'] += 1
                        results['by_severity'][result['severity']] += 1

                        if result['action_taken']:
                            results['actions_taken'] += 1

                        results['details'].append({
                            'student_id': student.id,
                            'name': student.name,
                            'severity': result['severity'],
                            'action': result['action_taken']
                        })
                    else:
                        results['failed'] += 1

                except Exception as e:
                    print(f"❌ خطأ في تحليل الطالب {student.id}: {e}")
                    results['failed'] += 1

                # تحديث التقدم في DB كل طالب
                try:
                    import json as _json
                    AISetting.set_setting('analysis_job_progress', _json.dumps({
                        'total': results['total'],
                        'analyzed': results['analyzed'],
                        'failed': results['failed'],
                        'actions_taken': results['actions_taken'],
                        'current': i + 1
                    }), 'json')
                except Exception:
                    pass

            # حساب المدة
            duration = (datetime.utcnow() - start_time).total_seconds()

            # تسجيل النتيجة
            AILog.log_operation(
                'scheduled_analysis',
                description=f'تحليل تلقائي لـ {results["analyzed"]} طالب',
                success=True,
                duration_seconds=duration,
                data=results
            )

            print(f"✅ اكتمل التحليل التلقائي في {duration:.2f} ثانية")
            print(f"📊 النتائج:")
            print(f"   - تم تحليل: {results['analyzed']}/{results['total']}")
            print(f"   - فشل: {results['failed']}")
            print(f"   - إجراءات: {results['actions_taken']}")
            print(f"   - 🟢 Green: {results['by_severity']['green']}")
            print(f"   - 🟡 Yellow: {results['by_severity']['yellow']}")
            print(f"   - 🟠 Orange: {results['by_severity']['orange']}")
            print(f"   - 🔴 Red: {results['by_severity']['red']}")

            self.is_running = False
            return results

        except Exception as e:
            print(f"❌ خطأ في analyze_all_students: {e}")
            AILog.log_operation(
                'scheduled_analysis_failed',
                description='فشل التحليل التلقائي',
                success=False,
                error_message=str(e)
            )
            self.is_running = False
            return {
                'status': 'error',
                'error': str(e)
            }

    def _analyze_single_student(self, student) -> Dict:
        """تحليل طالب واحد"""

        # تحليل بواسطة AI
        analysis_result = ai_assistant.analyze_student(
            student_id=student.id,
            analysis_type='scheduled'
        )

        if not analysis_result:
            return None

        # الحصول على آخر تحليل
        latest_analysis = AIAnalysis.get_latest_for_student(student.id)

        if not latest_analysis:
            return None

        # ✅ إضافة سطور التتبع
        print(f"📤 معالجة نتائج الطالب {student.id} ({student.name})")
        print(f"   suggested_action: {latest_analysis.suggested_action}")
        print(f"   severity: {latest_analysis.severity_level}")
        print(f"   student_status: {latest_analysis.student_status}")

        # معالجة النتيجة وإرسال إشعارات إذا لزم
        action_taken = smart_notifications.process_analysis_result(latest_analysis)

        print(f"   ✅ action_taken = {action_taken}")
        print("")

        return {
            'severity': latest_analysis.severity_level,
            'status': latest_analysis.student_status,
            'action_taken': action_taken
        }

    def _send_daily_report_fcm(self, report: Dict):
        """إرسال ملخص التقرير اليومي كإشعار FCM للأدمن"""
        try:
            admin_fcm_token = AISetting.get_setting('admin_fcm_token')
            if not admin_fcm_token:
                print("⚠️ لا يوجد FCM token للأدمن - تخطي إرسال التقرير")
                return

            from src.services.notification_service import NotificationService

            severity = report.get('severity_distribution', {})
            critical = report.get('critical_count', 0)
            analyzed = report.get('analyzed_today', 0)
            total = report.get('total_students', 0)

            title = f"📊 التقرير اليومي - {analyzed}/{total} طالب"

            body_parts = [f"تم تحليل {analyzed} طالب من أصل {total}"]
            if critical > 0:
                body_parts.append(f"🔴 {critical} حالة حرجة تحتاج متابعة!")
            attention = report.get('needs_attention_count', 0)
            if attention > 0:
                body_parts.append(f"🟠 {attention} يحتاج انتباه")
            body_parts.append(
                f"🟢{severity.get('green',0)} 🟡{severity.get('yellow',0)} "
                f"🟠{severity.get('orange',0)} 🔴{severity.get('red',0)}"
            )

            body = '\n'.join(body_parts)

            NotificationService.send_fcm_notification(
                admin_fcm_token, title, body,
                {'type': 'daily_report', 'date': report.get('date', '')}
            )
            print(f"✅ تم إرسال التقرير اليومي للأدمن عبر FCM")

        except Exception as e:
            print(f"⚠️ فشل إرسال التقرير اليومي للأدمن: {e}")

    def generate_daily_report(self) -> Dict:
        """
        توليد تقرير يومي عن أداء الطلاب

        Returns:
            التقرير
        """
        try:
            print("📊 توليد التقرير اليومي...")

            # إحصائيات عامة
            total_students = Student.query.filter_by(is_active=True).count()

            # آخر تحليل لكل طالب
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_analyses = db.session.query(AIAnalysis).filter(
                AIAnalysis.created_at >= yesterday
            ).all()

            # تجميع حسب الخطورة
            severity_counts = {
                'green': 0,
                'yellow': 0,
                'orange': 0,
                'red': 0
            }

            for analysis in recent_analyses:
                severity = analysis.severity_level
                if severity in severity_counts:
                    severity_counts[severity] += 1

            # الطلاب الذين يحتاجون انتباه
            needs_attention = AIAnalysis.get_students_by_severity('orange')
            critical = AIAnalysis.get_students_by_severity('red')

            report = {
                'date': datetime.utcnow().isoformat(),
                'total_students': total_students,
                'analyzed_today': len(recent_analyses),
                'severity_distribution': severity_counts,
                'needs_attention_count': len(needs_attention),
                'critical_count': len(critical),
                'critical_students': [
                    {
                        'student_id': a.student_id,
                        'student_name': a.student.name if a.student else 'Unknown',
                        'days_inactive': a.days_since_last_quiz,
                        'average_score': a.average_score
                    } for a in critical[:10]  # أول 10
                ]
            }

            AILog.log_operation(
                'daily_report',
                description='تقرير يومي',
                success=True,
                data=report
            )

            # إرسال التقرير كإشعار FCM للأدمن
            self._send_daily_report_fcm(report)

            print("✅ تم توليد التقرير اليومي")
            return report

        except Exception as e:
            print(f"❌ خطأ في generate_daily_report: {e}")
            AILog.log_operation(
                'daily_report_failed',
                description='فشل توليد التقرير اليومي',
                success=False,
                error_message=str(e)
            )
            return {
                'status': 'error',
                'error': str(e)
            }


    def check_notification_effectiveness(self) -> Dict:
        """
        تقييم فعالية الإشعارات المرسلة خلال آخر 7 أيام
        لكل إشعار: هل فتح الطالب التطبيق؟ هل حل أسئلة خلال 48 ساعة؟
        """
        try:
            from src.models.ai_analysis import AIAction
            from src.models.student_result import StudentResult

            print("📊 فحص فعالية الإشعارات...")

            week_ago = datetime.utcnow() - timedelta(days=7)

            # جلب الإشعارات المرسلة خلال 7 أيام
            sent_actions = AIAction.query.filter(
                AIAction.message_sent == True,
                AIAction.message_sent_at >= week_ago,
                AIAction.message_sent_at.isnot(None)
            ).all()

            if not sent_actions:
                print("⚠️ لا توجد إشعارات مرسلة خلال 7 أيام")
                return {'total_sent': 0, 'details': []}

            total_sent = len(sent_actions)
            opened_count = 0
            solved_count = 0
            total_response_hours = 0
            response_count = 0
            details = []

            for action in sent_actions:
                sent_at = action.message_sent_at
                check_until = sent_at + timedelta(hours=48)
                student = Student.query.get(action.student_id)

                if not student:
                    continue

                # هل فتح التطبيق بعد الإشعار؟
                opened_app = (
                    student.last_login is not None
                    and student.last_login > sent_at
                    and student.last_login <= check_until
                )

                # هل حل أسئلة بعد الإشعار؟
                results_after = StudentResult.query.filter(
                    StudentResult.student_id == action.student_id,
                    StudentResult.created_at > sent_at,
                    StudentResult.created_at <= check_until
                ).count()

                # حساب وقت الاستجابة
                response_hours = None
                if opened_app and student.last_login:
                    response_hours = (student.last_login - sent_at).total_seconds() / 3600

                if opened_app:
                    opened_count += 1
                if results_after > 0:
                    solved_count += 1
                if response_hours is not None:
                    total_response_hours += response_hours
                    response_count += 1

                # حفظ النتيجة في AIAction.result (حقل success/error_message)
                effectiveness = {
                    'opened_app': opened_app,
                    'solved_questions': results_after,
                    'response_time_hours': round(response_hours, 1) if response_hours else None
                }

                detail = {
                    'action_id': action.id,
                    'student_id': action.student_id,
                    'student_name': student.name,
                    'sent_at': sent_at.isoformat(),
                    'opened_app': opened_app,
                    'solved_questions': results_after,
                    'response_time_hours': round(response_hours, 1) if response_hours else None
                }
                details.append(detail)

            avg_response = round(total_response_hours / response_count, 1) if response_count > 0 else None

            summary = {
                'total_sent': total_sent,
                'opened_count': opened_count,
                'solved_count': solved_count,
                'open_rate': round(opened_count / total_sent * 100, 1) if total_sent > 0 else 0,
                'solve_rate': round(solved_count / total_sent * 100, 1) if total_sent > 0 else 0,
                'avg_response_hours': avg_response,
                'checked_at': datetime.utcnow().isoformat(),
                'details': details
            }

            # حفظ الملخص في AILog
            AILog.log_operation(
                'notification_effectiveness',
                description=f'فعالية الإشعارات: {opened_count}/{total_sent} فتح، {solved_count}/{total_sent} حل',
                success=True,
                data=summary
            )

            print(f"✅ فعالية الإشعارات: {opened_count}/{total_sent} فتح، {solved_count}/{total_sent} حل")
            return summary

        except Exception as e:
            print(f"❌ خطأ في check_notification_effectiveness: {e}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'error': str(e)}


# إنشاء instance واحد
student_analyzer = StudentAnalyzer()


# ============================================
# APScheduler Configuration
# ============================================

def init_scheduler(app):
    """
    تهيئة APScheduler في التطبيق

    Args:
        app: Flask application
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler()

    # قراءة الإعدادات
    with app.app_context():
        analysis_interval = AISetting.get_setting('analysis_interval_hours', 6)
        daily_report_time = AISetting.get_setting('daily_report_time', '08:00')

    # المهمة 1: التحليل التلقائي كل X ساعات
    scheduler.add_job(
        func=run_scheduled_analysis,
        trigger='interval',
        hours=analysis_interval,
        id='student_analysis',
        name='تحليل الطلاب التلقائي',
        replace_existing=True
    )

    # المهمة 2: التقرير اليومي
    hour, minute = map(int, daily_report_time.split(':'))
    scheduler.add_job(
        func=run_daily_report,
        trigger=CronTrigger(hour=hour, minute=minute),
        id='daily_report',
        name='التقرير اليومي',
        replace_existing=True
    )

    # ✅ المهمة 3: تحدي اليوم (8 صباحاً)
    scheduler.add_job(
        func=run_daily_challenge_notification,
        trigger=CronTrigger(hour=8, minute=0),
        id='daily_challenge',
        name='تحدي اليوم',
        replace_existing=True
    )

    # ✅ المهمة 4: تذكير بالتحدي (8 مساءً)
    scheduler.add_job(
        func=run_challenge_reminder,
        trigger=CronTrigger(hour=20, minute=0),
        id='challenge_reminder',
        name='تذكير بالتحدي',
        replace_existing=True
    )

    # ✅ المهمة 5: التحقق من طلبات التحليل اليدوية (كل 10 ثواني)
    scheduler.add_job(
        func=check_manual_analysis_request,
        trigger='interval',
        seconds=10,
        id='check_manual_analysis',
        name='فحص طلبات التحليل',
        replace_existing=True
    )

    # بدء الـ Scheduler
    scheduler.start()
    print("✅ تم تفعيل APScheduler")
    print(f"   - التحليل التلقائي: كل {analysis_interval} ساعات")
    print(f"   - التقرير اليومي: الساعة {daily_report_time}")
    print(f"   - تحدي اليوم: الساعة 8:00 صباحاً")
    print(f"   - تذكير التحدي: الساعة 20:00 مساءً")
    print(f"   - فحص طلبات التحليل: كل 10 ثواني")

    return scheduler


def check_manual_analysis_request():
    """فحص إذا فيه طلب تحليل يدوي من التطبيق"""
    from src import create_app
    import json as _json
    app = create_app()
    with app.app_context():
        try:
            status = AISetting.get_setting('analysis_job_status', 'idle')
            if status != 'running':
                return

            # تحقق من التقدم
            progress = AISetting.get_setting('analysis_job_progress', {})
            total = progress.get('total', 0) if isinstance(progress, dict) else 0

            # إذا total=0 يعني لسا ما بدأ التحليل الفعلي
            if total == 0:
                print("📋 [Scheduler] طلب تحليل يدوي - جاري التنفيذ...")

                try:
                    student_analyzer.is_running = False
                    result = student_analyzer.analyze_all_students()

                    AISetting.set_setting('analysis_job_status', 'completed', 'string')
                    AISetting.set_setting('analysis_job_progress', _json.dumps(result), 'json')
                    print(f"✅ [Scheduler] اكتمل التحليل اليدوي: {result.get('analyzed', 0)} طالب")
                except Exception as e:
                    print(f"❌ [Scheduler] فشل التحليل اليدوي: {e}")
                    AISetting.set_setting('analysis_job_status', 'failed', 'string')
                    AISetting.set_setting('analysis_job_progress', _json.dumps({
                        'error': str(e)
                    }), 'json')

        except Exception as e:
            print(f"❌ [Scheduler] خطأ في check_manual_analysis_request: {e}")


def run_scheduled_analysis():
    """تشغيل التحليل التلقائي (للـ Scheduler)"""
    from src import create_app
    app = create_app()
    with app.app_context():
        try:
            print("\n" + "="*50)
            print(f"🤖 بدء التحليل التلقائي - {datetime.utcnow()}")
            print("="*50)

            result = student_analyzer.analyze_all_students()

            print("="*50)
            print("✅ اكتمل التحليل التلقائي")
            print("="*50 + "\n")

            return result
        except Exception as e:
            print(f"❌ خطأ في run_scheduled_analysis: {e}")
            return None


def run_daily_report():
    """توليد التقرير اليومي (للـ Scheduler)"""
    from src import create_app
    app = create_app()
    with app.app_context():
        try:
            print("\n" + "="*50)
            print(f"📊 توليد التقرير اليومي - {datetime.utcnow()}")
            print("="*50)

            report = student_analyzer.generate_daily_report()

            # TODO: إرسال التقرير للأدمن عبر Email أو حفظه

            print("="*50)
            print("✅ اكتمل التقرير اليومي")
            print("="*50 + "\n")

            return report
        except Exception as e:
            print(f"❌ خطأ في run_daily_report: {e}")
            return None


# ============================================
# Gamification Tasks
# ============================================

def run_daily_challenge_notification():
    """إرسال تحدي اليوم لجميع الطلاب النشطين"""
    from src import create_app
    from src.services.gamification_service import gamification_service
    
    app = create_app()
    with app.app_context():
        try:
            print("\n" + "="*50)
            print(f"⚡ إرسال تحدي اليوم - {datetime.utcnow()}")
            print("="*50)
            
            # توليد تحدي اليوم
            challenge = gamification_service.generate_daily_challenge()
            
            if not challenge:
                print("❌ فشل توليد التحدي")
                return
            
            print(f"✅ التحدي: {challenge.title}")
            
            # الحصول على جميع الطلاب النشطين
            students = Student.query.filter_by(is_active=True).all()
            
            challenge_dict = {
                'id': challenge.id,
                'title': challenge.title,
                'description': challenge.description,
                'icon': challenge.icon,
                'points': challenge.points
            }
            
            # إرسال للجميع
            sent_count = 0
            for student in students:
                if student.fcm_token:
                    success = smart_notifications.send_challenge_notification(
                        student.id, challenge_dict
                    )
                    if success:
                        sent_count += 1
            
            print(f"✅ تم الإرسال لـ {sent_count} من {len(students)} طالب")
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"❌ خطأ في run_daily_challenge_notification: {e}")
            import traceback
            traceback.print_exc()


def run_challenge_reminder():
    """تذكير بتحدي اليوم (مساءً)"""
    from src import create_app
    from src.services.gamification_service import gamification_service
    
    app = create_app()
    with app.app_context():
        try:
            print("\n" + "="*50)
            print(f"⏰ تذكير بتحدي اليوم - {datetime.utcnow()}")
            print("="*50)
            
            # الطلاب النشطين
            students = Student.query.filter_by(is_active=True).all()
            
            reminded_count = 0
            for student in students:
                # التحقق من حالة التحدي
                progress = gamification_service.get_student_challenge_progress(student.id)
                
                # إرسال تذكير فقط لمن لم يكمل
                if not progress.get('completed') and not progress.get('no_challenge'):
                    success = smart_notifications.send_challenge_reminder(student.id)
                    if success:
                        reminded_count += 1
            
            print(f"✅ تم التذكير لـ {reminded_count} طالب")
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"❌ خطأ في run_challenge_reminder: {e}")
            import traceback
            traceback.print_exc()
