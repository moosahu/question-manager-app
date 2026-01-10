# src/services/smart_notifications.py
"""
خدمة الإشعارات الذكية
تقرر متى وكيف يتم إرسال الإشعارات بناءً على تحليلات AI
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict

from src.models.notification import Notification, StudentNotification
from src.models.ai_analysis import AIAnalysis, AIAction, AILog, AISetting
from src.models.student import Student
from src.services.notification_service import NotificationService
from src.extensions import db


class SmartNotificationService:
    """خدمة الإشعارات الذكية - تدير إرسال الإشعارات بناءً على AI"""
    
    def __init__(self):
        """تهيئة الخدمة"""
        self.fcm_service = NotificationService()
    
    def process_analysis_result(self, analysis: AIAnalysis) -> bool:
        """
        معالجة نتيجة تحليل ومعرفة الإجراء المطلوب
        
        Args:
            analysis: نتيجة التحليل من AI
        
        Returns:
            True إذا تم اتخاذ إجراء
        """
        try:
            # التحقق من الإعدادات
            auto_messages_enabled = AISetting.get_setting('enable_auto_messages', True)
            admin_alerts_enabled = AISetting.get_setting('enable_admin_alerts', True)
            
            # تحديد الإجراء المطلوب
            action_type = analysis.suggested_action or 'no_action'
            
            if action_type == 'no_action':
                # لا يحتاج إجراء
                return False
            
            elif action_type == 'send_message' and auto_messages_enabled:
                # إرسال رسالة ذكية للطالب
                return self._send_smart_message(analysis)
            
            elif action_type == 'admin_alert' and admin_alerts_enabled:
                # تنبيه للأدمن
                return self._send_admin_alert(analysis)
            
            return False
            
        except Exception as e:
            print(f"❌ خطأ في process_analysis_result: {e}")
            return False
    
    def _send_smart_message(self, analysis: AIAnalysis) -> bool:
        """إرسال رسالة ذكية للطالب"""
        
        try:
            # التحقق من عدم تجاوز الحد اليومي
            if not self._can_send_message(analysis.student_id):
                AILog.log_operation(
                    'smart_message_skipped',
                    description=f'تم تخطي الرسالة للطالب {analysis.student_id} - تجاوز الحد اليومي',
                    student_id=analysis.student_id,
                    success=True
                )
                return False
            
            # توليد الرسالة
            title, body = self._generate_message_content(analysis)
            
            # إنشاء الإشعار
            notification = Notification.create_notification(
                title=title,
                body=body,
                notification_type='ai_alert',
                created_by_ai=True,
                ai_analysis_id=analysis.id,
                data={
                    'severity': analysis.severity_level,
                    'student_status': analysis.student_status
                }
            )
            
            # ربطه بالطالب
            student_notif = StudentNotification.create_for_student(
                notification.id,
                analysis.student_id
            )
            
            if not student_notif:
                return False
            
            # إرسال عبر FCM
            student = Student.query.get(analysis.student_id)
            if student and student.fcm_token:
                fcm_success = self.fcm_service.send_fcm_notification(
                    token=student.fcm_token,
                    title=title,
                    body=body,
                    data={
                        'type': 'ai_alert',
                        'notification_id': str(notification.id),
                        'severity': analysis.severity_level
                    }
                )
                student_notif.mark_fcm_sent(fcm_success)
            
            # تسجيل الإجراء
            ai_action = AIAction(
                ai_analysis_id=analysis.id,
                student_id=analysis.student_id,
                action_type='smart_message',
                action_description=f'رسالة ذكية: {analysis.student_status}',
                message_title=title,
                message_body=body,
                message_sent=True,
                message_sent_at=datetime.utcnow(),
                success=True
            )
            db.session.add(ai_action)
            
            # تعليم التحليل كمنفذ
            analysis.mark_action_taken('smart_message')
            
            db.session.commit()
            
            AILog.log_operation(
                'smart_message_sent',
                description=f'تم إرسال رسالة ذكية للطالب {analysis.student_id}',
                student_id=analysis.student_id,
                success=True,
                data={'notification_id': notification.id}
            )
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ خطأ في _send_smart_message: {e}")
            
            AILog.log_operation(
                'smart_message_failed',
                description=f'فشل إرسال رسالة للطالب {analysis.student_id}',
                student_id=analysis.student_id,
                success=False,
                error_message=str(e)
            )
            
            return False
    
    def _send_admin_alert(self, analysis: AIAnalysis) -> bool:
        """إرسال تنبيه للأدمن"""
        
        try:
            student = Student.query.get(analysis.student_id)
            if not student:
                return False
            
            # إنشاء إشعار للأدمن
            title = f"⚠️ تنبيه: حالة حرجة - {student.name}"
            body = f"""
الطالب {student.name} (الصف {student.grade}) في حالة حرجة:
- المعدل: {analysis.average_score}%
- عدم نشاط: {analysis.days_since_last_quiz} يوم
- المشاكل: {', '.join(analysis.issues_detected) if analysis.issues_detected else 'متعددة'}

يحتاج تدخل فوري!
            """.strip()
            
            notification = Notification.create_notification(
                title=title,
                body=body,
                notification_type='admin_alert',
                created_by_ai=True,
                ai_analysis_id=analysis.id,
                data={
                    'severity': 'critical',
                    'student_id': analysis.student_id,
                    'student_name': student.name
                }
            )
            
            # TODO: إرسال للأدمن عبر FCM أو Email
            # يمكن إضافة منطق إرسال للأدمن هنا
            
            # تسجيل الإجراء
            ai_action = AIAction(
                ai_analysis_id=analysis.id,
                student_id=analysis.student_id,
                action_type='admin_alert',
                action_description=f'تنبيه أدمن: حالة حرجة',
                admin_notified=True,
                admin_notified_at=datetime.utcnow(),
                success=True
            )
            db.session.add(ai_action)
            
            analysis.mark_action_taken('admin_alert')
            db.session.commit()
            
            AILog.log_operation(
                'admin_alert_sent',
                description=f'تم إرسال تنبيه أدمن للطالب {analysis.student_id}',
                student_id=analysis.student_id,
                success=True,
                data={'notification_id': notification.id}
            )
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ خطأ في _send_admin_alert: {e}")
            return False
    
    def _can_send_message(self, student_id: int) -> bool:
        """
        التحقق من إمكانية إرسال رسالة (الحد اليومي)
        
        Args:
            student_id: رقم الطالب
        
        Returns:
            True إذا يمكن إرسال رسالة
        """
        max_messages = AISetting.get_setting('max_messages_per_student_day', 3)
        
        # عد الرسائل المرسلة اليوم
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        messages_today = AIAction.query.filter(
            AIAction.student_id == student_id,
            AIAction.action_type == 'smart_message',
            AIAction.message_sent == True,
            AIAction.message_sent_at >= today_start
        ).count()
        
        return messages_today < max_messages
    
    def _generate_message_content(self, analysis: AIAnalysis) -> tuple:
        """
        توليد محتوى الرسالة بناءً على التحليل
        
        Args:
            analysis: نتيجة التحليل
        
        Returns:
            (title, body)
        """
        severity = analysis.severity_level
        status = analysis.student_status
        student = Student.query.get(analysis.student_id)
        student_name = student.name if student else 'الطالب'
        
        # اختيار الرسالة المناسبة
        if severity == 'red':
            title = f"⚠️ {student_name}، نحتاج انتباهك!"
            body = f"""
لاحظنا أنك لم تحل اختبارات منذ {analysis.days_since_last_quiz} يوم. 

نحن هنا لمساعدتك! 💪
ابدأ بحل اختبار قصير اليوم.
"""
        
        elif severity == 'orange':
            if analysis.performance_trend == 'declining':
                title = f"📉 {student_name}، دعنا نعود للمسار الصحيح"
                body = f"""
لاحظنا انخفاض في معدلك مؤخراً.

لا تقلق! راجع الدروس الأخيرة وحاول مرة أخرى. أنت قادر! 💪
"""
            else:
                title = f"💡 {student_name}، وقت الممارسة!"
                body = f"""
لم نرك منذ {analysis.days_since_last_quiz} يوم.

حل اختبار سريع اليوم لتحافظ على تقدمك! 🚀
"""
        
        else:  # yellow or green
            title = f"👍 {student_name}، أداء رائع!"
            body = f"""
معدلك الحالي: {analysis.average_score}%

استمر في المذاكرة المنتظمة! 🌟
"""
        
        # إضافة توصيات AI إذا وجدت
        if analysis.ai_recommendations:
            # استخراج أول 200 حرف من التوصيات
            recommendations = analysis.ai_recommendations[:200]
            if len(analysis.ai_recommendations) > 200:
                recommendations += "..."
            body += f"\n\n💡 نصيحة: {recommendations}"
        
        return title, body.strip()
    
    def send_bulk_notification(self, student_ids: List[int], title: str, 
                               body: str, notification_type: str = 'info') -> Dict:
        """
        إرسال إشعار جماعي لعدة طلاب
        
        Args:
            student_ids: قائمة أرقام الطلاب
            title: عنوان الإشعار
            body: محتوى الإشعار
            notification_type: نوع الإشعار
        
        Returns:
            تقرير بالنتائج
        """
        try:
            # إنشاء إشعار واحد
            notification = Notification.create_notification(
                title=title,
                body=body,
                notification_type=notification_type,
                created_by_admin=True
            )
            
            # ربطه بالطلاب
            StudentNotification.create_for_students(notification.id, student_ids)
            
            # إرسال عبر FCM
            students = Student.query.filter(Student.id.in_(student_ids)).all()
            tokens = [s.fcm_token for s in students if s.fcm_token]
            
            fcm_results = {'success': 0, 'failed': 0}
            
            if tokens:
                # إرسال جماعي
                success = self.fcm_service.send_multicast_notification(
                    tokens=tokens,
                    title=title,
                    body=body,
                    data={'notification_id': str(notification.id)}
                )
                
                if success:
                    fcm_results['success'] = len(tokens)
                else:
                    fcm_results['failed'] = len(tokens)
            
            AILog.log_operation(
                'bulk_notification_sent',
                description=f'إرسال جماعي لـ {len(student_ids)} طالب',
                success=True,
                data={
                    'notification_id': notification.id,
                    'student_count': len(student_ids),
                    'fcm_results': fcm_results
                }
            )
            
            return {
                'notification_id': notification.id,
                'students_count': len(student_ids),
                'fcm_sent': fcm_results['success'],
                'fcm_failed': fcm_results['failed']
            }
            
        except Exception as e:
            print(f"❌ خطأ في send_bulk_notification: {e}")
            
            AILog.log_operation(
                'bulk_notification_failed',
                description='فشل الإرسال الجماعي',
                success=False,
                error_message=str(e)
            )
            
            return {
                'error': str(e),
                'students_count': 0
            }


# إنشاء instance واحد
smart_notifications = SmartNotificationService()
