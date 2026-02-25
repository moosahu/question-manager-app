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
        self.progress = {'status': 'idle'}
        self.last_result = None

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

            # تحليل كل طالب
            for i, student in enumerate(students):
                try:
                    # تحديث التقدم
                    self.progress = {
                        'status': 'running',
                        'total': len(students),
                        'analyzed': results['analyzed'],
                        'failed': results['failed'],
                        'current_student': student.name,
                        'current_index': i + 1,
                    }

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

    # بدء الـ Scheduler
    scheduler.start()
    print("✅ تم تفعيل APScheduler")
    print(f"   - التحليل التلقائي: كل {analysis_interval} ساعات")
    print(f"   - التقرير اليومي: الساعة {daily_report_time}")
    print(f"   - تحدي اليوم: الساعة 8:00 صباحاً")
    print(f"   - تذكير التحدي: الساعة 20:00 مساءً")

    return scheduler


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
