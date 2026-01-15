# src/services/smart_notifications.py

"""
خدمة الإشعارات الذكية
تقرر متى وكيف يتم إرسال الإشعارات بناءً على تحليلات AI
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import random

from src.models.notification import Notification, StudentNotification
from src.models.ai_analysis import AIAnalysis, AIAction, AILog, AISetting
from src.models.student import Student
from src.services.notification_service import NotificationService
from src.extensions import db

# ✅ دعم Gamification
try:
    from src.services.gamification_helper import (
        get_student_gamification_data,
        format_gamification_section,
        get_compact_gamification_text
    )
    GAMIFICATION_AVAILABLE = True
except ImportError:
    print("⚠️ Gamification helper غير متوفر - سيتم تجاهل معلومات اللعب")
    GAMIFICATION_AVAILABLE = False


# ============================================
# قوالب الرسائل المتنوعة (محسّنة!)
# ============================================

MESSAGE_TEMPLATES = {
    # للطلاب الممتازين (green)
    'excellent': {
        'morning': [
            "🎉 ماشاء الله {name}! نجم الصباح!",
            "⭐ صباح التميز يا {name}! أداء رائع!",
            "🌟 صباح الخير للطالب المتفوق {name}!",
        ],
        'afternoon': [
            "💎 {name}! أداؤك يلمع اليوم!",
            "🏆 ممتاز يا {name}! استمر في القمة!",
            "✨ {name}، أنت نجم المنصة!",
        ],
        'evening': [
            "🌟 مساء التميز {name}! أداء أسطوري اليوم!",
            "⭐ {name}، يوم ممتاز! حافظ على التألق!",
            "💫 ختام رائع ليومك يا {name}!",
        ],
        'weekend': [
            "🎊 نهاية أسبوع مميزة للطالب الممتاز {name}!",
            "🏅 {name}، أسبوع من التميز! أنت قدوة!",
        ]
    },
    
    # للطلاب الجيدين (yellow)
    'good': {
        'morning': [
            "💪 صباح الخير {name}! يلا نكمل التقدم!",
            "🚀 صباح جميل للطالب المجتهد {name}!",
            "☀️ يوم جديد، فرصة جديدة للتفوق!",
        ],
        'afternoon': [
            "📈 {name}! أداؤك يتحسن! استمر!",
            "💪 {name}، على الطريق الصح! واصل!",
            "🎯 {name}، تقدم ملحوظ! يلا نكمل!",
        ],
        'evening': [
            "🌙 مساء الخير {name}! يوم جيد، لنختمه بقوة!",
            "⭐ {name}، تحسن واضح اليوم! ممتاز!",
            "💫 {name}، أداء جيد! غداً أفضل!",
        ],
        'weekend': [
            "☀️ نهاية أسبوع رائعة {name}! استمر في التقدم!",
            "🎉 {name}، أسبوع جيد! الأفضل قادم!",
        ]
    },
    
    # للطلاب الذين يحتاجون انتباه (orange)
    'needs_attention': {
        'morning': [
            "☀️ صباح الخير {name}! دعنا نبدأ بقوة اليوم!",
            "🌅 يوم جديد، فرصة للتحسن يا {name}!",
            "☕ صباح الخير {name}! وقت مثالي للمراجعة",
        ],
        'afternoon': [
            "⏰ {name}! 5 دقائق اليوم أفضل من لا شيء!",
            "🌤️ وقت الظهيرة، {name}! اختبار واحد فقط",
            "📚 {name}، استراحة + مراجعة = تقدم!",
        ],
        'evening': [
            "🌙 {name}، ختام يومك باختبار؟",
            "⭐ {name}، 5 دقائق قبل النوم = فرق كبير!",
            "🌆 {name}، لا تنسَ مراجعتك اليومية!",
        ],
        'weekend': [
            "🎉 نهاية أسبوع رائعة {name}! وقت للتعويض!",
            "☀️ عطلة = فرصة للمراجعة يا {name}!",
        ]
    },
    
    # للطلاب في حالة حرجة (red)
    'critical': {
        'morning': [
            "⚠️ صباح الخير {name}، نفتقدك! عودتك مهمة!",
            "🚨 {name}، صباح الخير! نحن هنا لمساعدتك",
            "💚 {name}، بداية جديدة اليوم! نحن معك",
        ],
        'afternoon': [
            "⏰ {name}، ما زلنا ننتظرك! لا تستسلم",
            "🔔 {name}، نفتقد نشاطك! عودة بسيطة",
            "💪 {name}، خطوة واحدة اليوم = تقدم!",
        ],
        'evening': [
            "🌙 {name}، آخر فرصة اليوم! اختبار واحد فقط",
            "⏰ {name}، قبل نهاية اليوم! نحن هنا لك",
            "💚 {name}، لم يفت الأوان أبداً!",
        ],
        'weekend': [
            "📅 {name}، نهاية الأسبوع = بداية جديدة!",
            "💚 {name}، وقت العودة! نحن هنا لمساعدتك",
        ]
    }
}


# قوالب الرسائل القديمة (للتوافق)
OLD_MESSAGE_TEMPLATES = {
    'morning': {
        'orange': [
            "☀️ صباح الخير {name}! وقت مثالي لاختبار سريع",
            "🌅 يوم جديد، فرصة جديدة للتفوق يا {name}!",
            "☕ قهوتك الصباحية + اختبار = بداية رائعة",
        ],
        'red': [
            "⚠️ صباح الخير {name}، نحتاج انتباهك اليوم",
            "🚨 {name}، لنبدأ اليوم بقوة! وقت العودة",
        ]
    },
    'afternoon': {
        'orange': [
            "⏰ استراحة الغداء = وقت مراجعة!",
            "🌤️ وقت الظهيرة، {name}! 5 دقائق لاختبار واحد",
        ],
        'red': [
            "⏰ {name}، ما زلنا ننتظرك!",
            "🔔 تذكير: لم نرك اليوم يا {name}",
        ]
    },
    'evening': {
        'orange': [
            "🌙 ختام يومك باختبار يا {name}؟",
            "⭐ مسائك تفوق! حان وقت المراجعة",
            "🌆 {name}، ختام يومك الدراسي؟",
        ],
        'red': [
            "🌙 {name}، آخر فرصة اليوم!",
            "⏰ قبل نهاية اليوم، {name}! حل اختبار واحد",
        ]
    },
    'weekend': {
        'orange': [
            "🎉 نهاية أسبوع رائعة يا {name}!",
            "☀️ عطلة نهاية الأسبوع = وقت للمراجعة",
        ],
        'red': [
            "📅 نهاية الأسبوع، {name}! وقت التعويض",
        ]
    }
}


def get_time_of_day():
    """تحديد وقت اليوم"""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 17:
        return 'afternoon'
    elif 17 <= hour < 22:
        return 'evening'
    else:
        return 'night'


def is_weekend():
    """هل اليوم عطلة؟"""
    return datetime.now().weekday() >= 5  # السبت والأحد


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
                # تنبيه للأدمن فقط
                return self._send_admin_alert(analysis)

            # ==================== ✅ جديد: إرسال للطالب + الأدمن ====================
            elif action_type == 'send_message_and_alert':
                # 🔴 حالة حرجة: إرسال للاثنين
                message_sent = False
                alert_sent = False
                
                # 1. إرسال رسالة عاجلة للطالب
                if auto_messages_enabled:
                    print(f"   📤 إرسال رسالة عاجلة للطالب {analysis.student_id}")
                    message_sent = self._send_smart_message(analysis)
                
                # 2. إرسال تنبيه للأدمن
                if admin_alerts_enabled:
                    print(f"   🚨 إرسال تنبيه للأدمن عن الطالب {analysis.student_id}")
                    alert_sent = self._send_admin_alert(analysis)
                
                # نجح إذا نجح أحدهما على الأقل
                return message_sent or alert_sent
            # ==================== ✅ نهاية التعديل ====================

            return False

        except Exception as e:
            print(f"❌ خطأ في process_analysis_result: {e}")
            return False

    def _send_smart_message(self, analysis: AIAnalysis) -> bool:
        """إرسال رسالة ذكية للطالب"""
        print(f"🔵 _send_smart_message: بدء إرسال رسالة للطالب {analysis.student_id}")

        try:
            # التحقق من عدم تجاوز الحد اليومي
            can_send = self._can_send_message(analysis.student_id)
            print(f"   التحقق من الحد اليومي: can_send = {can_send}")

            if not can_send:
                print(f"   ⚠️ تم تخطي الرسالة - تجاوز الحد اليومي")
                AILog.log_operation(
                    'smart_message_skipped',
                    description=f'تم تخطي الرسالة للطالب {analysis.student_id} - تجاوز الحد اليومي',
                    student_id=analysis.student_id,
                    success=True
                )
                return False

            # توليد الرسالة
            print(f"   📝 توليد محتوى الرسالة...")
            title, body = self._generate_message_content(analysis)
            print(f"   ✅ العنوان: {title}")
            print(f"   📏 طول الرسالة: {len(body)} حرف")

            # ✅ تقصير الرسالة إذا كانت طويلة جداً (FCM limit)
            fcm_body = body
            full_body = body
            
            # FCM لديه حد 4000 حرف للـ notification body
            # لكن للأمان نستخدم 3000 حرف
            MAX_FCM_LENGTH = 3000
            
            if len(body) > MAX_FCM_LENGTH:
                print(f"   ⚠️ الرسالة طويلة ({len(body)} حرف) - سيتم اختصارها لـ FCM")
                fcm_body = body[:MAX_FCM_LENGTH] + "\n\n... [المزيد في التطبيق]"
                print(f"   ✅ الرسالة المختصرة: {len(fcm_body)} حرف")

            # إنشاء الإشعار (نحفظ النص الكامل في قاعدة البيانات)
            print(f"   💾 إنشاء Notification في قاعدة البيانات...")
            notification = Notification.create_notification(
                title=title,
                body=full_body,  # ✅ النص الكامل في قاعدة البيانات
                notification_type='ai_alert',
                created_by_ai=True,
                ai_analysis_id=analysis.id,
                data={
                    'severity': analysis.severity_level,
                    'student_status': analysis.student_status,
                    'full_message': full_body,  # ✅ نحفظ النص الكامل في data أيضاً
                }
            )
            print(f"   ✅ تم إنشاء Notification #{notification.id}")

            # ربطه بالطالب
            print(f"   🔗 إنشاء StudentNotification...")
            student_notif = StudentNotification.create_for_student(
                notification.id,
                analysis.student_id
            )

            if not student_notif:
                print(f"   ❌ فشل إنشاء StudentNotification")
                return False

            print(f"   ✅ تم إنشاء StudentNotification #{student_notif.id}")

            # إرسال عبر FCM (نستخدم النص المختصر)
            student = Student.query.get(analysis.student_id)
            if student and student.fcm_token:
                print(f"   📤 إرسال FCM للطالب (token موجود)...")
                
                # ✅ نرسل النص المختصر في notification body
                # والنص الكامل في data
                fcm_success = self.fcm_service.send_fcm_notification(
                    student.fcm_token,
                    title,
                    fcm_body,  # ✅ النص المختصر لـ FCM
                    {
                        'type': 'ai_alert',
                        'notification_id': str(notification.id),
                        'severity': analysis.severity_level,
                        'full_message': full_body,  # ✅ النص الكامل في data
                        'has_more': 'true' if len(body) > MAX_FCM_LENGTH else 'false'
                    }
                )
                print(f"   FCM Result: {fcm_success}")
                student_notif.mark_fcm_sent(fcm_success)
            else:
                print(f"   ⚠️ لا يوجد FCM token للطالب")

            # تسجيل الإجراء
            print(f"   📊 تسجيل AIAction...")
            ai_action = AIAction(
                ai_analysis_id=analysis.id,
                student_id=analysis.student_id,
                action_type='smart_message',
                action_description=f'رسالة ذكية: {analysis.student_status}',
                message_title=title,
                message_body=full_body,  # ✅ النص الكامل
                message_sent=True,
                message_sent_at=datetime.utcnow(),
                success=True
            )
            db.session.add(ai_action)

            # تعليم التحليل كمنفذ
            analysis.mark_action_taken('smart_message')
            db.session.commit()

            print(f"   ✅ تم إرسال الرسالة بنجاح!")

            AILog.log_operation(
                'smart_message_sent',
                description=f'تم إرسال رسالة ذكية للطالب {analysis.student_id}',
                student_id=analysis.student_id,
                success=True,
                data={
                    'notification_id': notification.id,
                    'message_length': len(full_body),
                    'fcm_length': len(fcm_body)
                }
            )

            return True

        except Exception as e:
            db.session.rollback()
            print(f"   ❌ خطأ في _send_smart_message: {e}")
            import traceback
            print(traceback.format_exc())

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
        try:
            max_messages = AISetting.get_setting('max_messages_per_student_day', 3)

            # عد الرسائل المرسلة اليوم
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            messages_today = AIAction.query.filter(
                AIAction.student_id == student_id,
                AIAction.action_type == 'smart_message',
                AIAction.message_sent == True,
                AIAction.message_sent_at >= today_start
            ).count()

            print(f"      📊 رسائل اليوم: {messages_today}/{max_messages}")

            return messages_today < max_messages
        except Exception as e:
            print(f"      ❌ خطأ في _can_send_message: {e}")
            return True  # في حالة الخطأ، نسمح بالإرسال

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
        
        # ✅ جلب بيانات Gamification
        gamification_data = None
        if GAMIFICATION_AVAILABLE:
            try:
                gamification_data = get_student_gamification_data(analysis.student_id)
            except Exception as e:
                print(f"⚠️ فشل جلب Gamification: {e}")
        
        # تحديد الوقت
        time_of_day = get_time_of_day()
        is_weekend_day = is_weekend()
        
        # ✅ استخدام القوالب الجديدة حسب حالة الطالب
        if is_weekend_day:
            templates = MESSAGE_TEMPLATES.get(status, {}).get('weekend', [])
        else:
            templates = MESSAGE_TEMPLATES.get(status, {}).get(time_of_day, [])
        
        # اختيار رسالة عشوائية
        if templates:
            title_template = random.choice(templates)
            title = title_template.format(name=student_name)
        else:
            # fallback حسب الحالة
            if status == 'excellent':
                title = f"🎉 ممتاز يا {student_name}! أداء رائع!"
            elif status == 'good':
                title = f"💪 {student_name}، تقدم ملحوظ! استمر!"
            elif status == 'needs_attention':
                title = f"📉 {student_name}، دعنا نعود للمسار الصحيح"
            else:  # critical
                title = f"⚠️ {student_name}، نحتاج انتباهك!"

        # ✅ محتوى الرسالة حسب الحالة مع Gamification
        if status == 'excellent':
            # للطلاب الممتازين - رسالة تهنئة
            body_parts = [f"معدلك: {analysis.average_score}% 🏆"]
            
            # إضافة معلومات gamification مختصرة
            if gamification_data:
                compact_text = get_compact_gamification_text(gamification_data)
                if compact_text:
                    body_parts.append(compact_text)
            
            body_parts.append("\nأداء استثنائي! أنت في القمة!")
            body_parts.append("استمر في هذا التميز... نحن فخورون بك! 🌟")
            
            body = "\n".join(body_parts)
        
        elif status == 'good':
            # للطلاب الجيدين - رسالة تشجيع
            body_parts = [f"معدلك: {analysis.average_score}% 📈"]
            
            if gamification_data:
                compact_text = get_compact_gamification_text(gamification_data)
                if compact_text:
                    body_parts.append(compact_text)
            
            body_parts.append("\nأداء جيد! أنت على الطريق الصحيح.")
            body_parts.append("خطوة بسيطة تفصلك عن الامتياز! 💪")
            
            body = "\n".join(body_parts)
        
        elif status == 'needs_attention':
            # للطلاب الذين يحتاجون انتباه
            if analysis.performance_trend == 'declining':
                body = f"""
معدلك: {analysis.average_score}%

لاحظنا انخفاض بسيط مؤخراً.
لا تقلق! مراجعة سريعة وراح ترجع للمسار. 💪
"""
            else:
                body = f"""
لم نرك منذ {analysis.days_since_last_quiz} يوم.

وحشنا نشاطك! اختبار واحد اليوم = تقدم كبير! 🚀
"""
        
        else:  # critical
            # للطلاب في حالة حرجة - رسالة داعمة
            body = f"""
لاحظنا غيابك منذ {analysis.days_since_last_quiz} يوم.

نحن هنا لمساعدتك! 💚
ابدأ بخطوة بسيطة: اختبار واحد اليوم.
لا تستسلم... كل طالب متميز بدأ من هنا!
"""

        # ✅ إضافة قسم Gamification الكامل للممتازين والجيدين
        if gamification_data and status in ['excellent', 'good']:
            gamification_section = format_gamification_section(gamification_data)
            if gamification_section:
                body += f"\n\n{gamification_section}"

        # إضافة توصيات AI إذا وجدت
        if analysis.ai_recommendations:
            # تنظيف التوصيات من أي ترحيبات أو مقدمات زائدة
            recommendations = analysis.ai_recommendations.strip()
            
            # إزالة عبارات الترحيب الشائعة
            greetings_to_remove = [
                f"أهلاً بك يا {student_name}،",
                f"أهلاً بك يا {student_name}",
                f"مرحباً {student_name}،",
                f"مرحباً {student_name}",
                "أهلاً بك،",
                "أهلاً بك",
                "مرحباً،",
                "مرحباً",
            ]
            
            for greeting in greetings_to_remove:
                if recommendations.startswith(greeting):
                    recommendations = recommendations[len(greeting):].strip()
                    break
            
            # إضافة التوصيات المنظفة
            if recommendations:
                body += f"\n\n💡 نصيحة:\n{recommendations}"

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
            try:
                for student_id in student_ids:
                    student_notif = StudentNotification(
                        notification_id=notification.id,
                        student_id=student_id,
                        is_read=False,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(student_notif)
                db.session.commit()
            except Exception as e:
                print(f"❌ خطأ في إنشاء StudentNotifications: {e}")
                db.session.rollback()

            # ✅ تقصير الرسالة للـ FCM إذا كانت طويلة
            fcm_body = body
            MAX_FCM_LENGTH = 3000
            
            if len(body) > MAX_FCM_LENGTH:
                fcm_body = body[:MAX_FCM_LENGTH] + "\n\n... [المزيد في التطبيق]"

            # إرسال عبر FCM
            students = Student.query.filter(Student.id.in_(student_ids)).all()
            tokens = [s.fcm_token for s in students if s.fcm_token]

            fcm_results = {'success': 0, 'failed': 0}
            if tokens:
                # إرسال جماعي
                result = self.fcm_service.send_multicast_notification(
                    tokens,
                    title,
                    fcm_body,  # ✅ النص المختصر
                    {
                        'notification_id': str(notification.id),
                        'full_message': body,  # ✅ النص الكامل في data
                        'has_more': 'true' if len(body) > MAX_FCM_LENGTH else 'false'
                    }
                )

                if result:
                    fcm_results['success'] = result.get('success_count', 0)
                    fcm_results['failed'] = result.get('failure_count', 0)

            AILog.log_operation(
                'bulk_notification_sent',
                description=f'إرسال جماعي لـ {len(student_ids)} طالب',
                success=True,
                data={
                    'notification_id': notification.id,
                    'student_count': len(student_ids),
                    'fcm_results': fcm_results,
                    'message_length': len(body),
                    'fcm_length': len(fcm_body)
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
    
    # ============================================
    # Gamification Notifications
    # ============================================
    
    def send_achievement_notification(self, student_id: int, achievement: Dict) -> bool:
        """إرسال إشعار بإنجاز جديد"""
        try:
            from src.services.gamification_service import gamification_service
            
            student = Student.query.get(student_id)
            if not student:
                return False
            
            points_data = gamification_service.get_student_points(student_id)
            
            title = f"🎉 إنجاز جديد!"
            body = f"""{achievement['icon']} {achievement['title']}
{achievement['description']}
المكافأة: ⭐ +{achievement['points']} نقطة
💰 إجمالي نقاطك: {points_data['total_points']}"""
            
            # ✅ إنشاء الإشعار مع student_id
            notification = Notification(
                title=title,
                body=body,
                message=body,
                notification_type='achievement',
                type='achievement',
                student_id=student_id,  # ✅ إضافة student_id
                created_by_ai=True,
                data={
                    'type': 'achievement',
                    'achievement_type': achievement['achievement_type'],
                    'points': achievement['points']
                },
                created_at=datetime.utcnow()
            )
            db.session.add(notification)
            db.session.flush()  # ✅ للحصول على notification.id
            
            # ✅ ربطه بالطالب في student_notifications
            student_notif = StudentNotification(
                notification_id=notification.id,
                student_id=student_id,
                is_read=False,
                fcm_sent=False,
                created_at=datetime.utcnow()
            )
            db.session.add(student_notif)
            db.session.commit()
            
            # إرسال عبر FCM
            if student.fcm_token:
                self.fcm_service.send_fcm_notification(
                    student.fcm_token,
                    title,
                    body,
                    {
                        'type': 'achievement',
                        'notification_id': str(notification.id),
                        'achievement_type': achievement['achievement_type']
                    }
                )
                # تحديث حالة الإرسال
                student_notif.fcm_sent = True
                db.session.commit()
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في send_achievement_notification: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False
    
    def send_challenge_notification(self, student_id: int, challenge: Dict) -> bool:
        """إرسال إشعار بتحدي اليوم"""
        try:
            student = Student.query.get(student_id)
            if not student:
                return False
            
            title = f"⚡ تحدي اليوم!"
            body = f"""
{challenge['icon']} {challenge['title']}
{challenge['description']}

المكافأة: ⭐ +{challenge['points']} نقطة

⏰ لديك 24 ساعة لإكماله!
"""
            
            # إنشاء الإشعار
            notification = Notification.create_notification(
                title=title,
                body=body,
                notification_type='challenge',
                created_by_ai=True,
                data={
                    'type': 'challenge',
                    'challenge_id': challenge['id'],
                    'points': challenge['points']
                }
            )
            
            # ربطه بالطالب
            student_notif = StudentNotification.create_for_student(
                notification.id,
                student_id
            )
            
            # إرسال عبر FCM
            if student.fcm_token:
                self.fcm_service.send_fcm_notification(
                    student.fcm_token,
                    title,
                    body,
                    {
                        'type': 'challenge',
                        'notification_id': str(notification.id),
                        'challenge_id': str(challenge['id'])
                    }
                )
                student_notif.mark_fcm_sent(True)
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في send_challenge_notification: {e}")
            return False
    
    def send_challenge_completion_notification(self, student_id: int, 
                                               completion_data: Dict) -> bool:
        """إرسال إشعار بإكمال تحدي"""
        try:
            from src.services.gamification_service import gamification_service
            
            student = Student.query.get(student_id)
            if not student:
                return False
            
            points_data = gamification_service.get_student_points(student_id)
            
            title = f"🎉 أكملت تحدي اليوم!"
            body = f"""✅ {completion_data['title']}
{completion_data['description']}
حصلت على:
⭐ +{completion_data['points_awarded']} نقطة
💰 إجمالي نقاطك: {points_data['total_points']}
🏆 ترتيبك: #{points_data['rank']}"""
            
            # ✅ إنشاء الإشعار مع student_id
            notification = Notification(
                title=title,
                body=body,
                message=body,
                notification_type='challenge_complete',
                type='challenge_complete',
                student_id=student_id,  # ✅ إضافة student_id
                created_by_ai=True,
                data={
                    'type': 'challenge_complete',
                    'points': completion_data['points_awarded']
                },
                created_at=datetime.utcnow()
            )
            db.session.add(notification)
            db.session.flush()
            
            # ✅ ربطه بالطالب في student_notifications
            student_notif = StudentNotification(
                notification_id=notification.id,
                student_id=student_id,
                is_read=False,
                fcm_sent=False,
                created_at=datetime.utcnow()
            )
            db.session.add(student_notif)
            db.session.commit()
            
            # إرسال عبر FCM
            if student.fcm_token:
                self.fcm_service.send_fcm_notification(
                    student.fcm_token,
                    title,
                    body,
                    {
                        'type': 'challenge_complete',
                        'notification_id': str(notification.id)
                    }
                )
                student_notif.fcm_sent = True
                db.session.commit()
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في send_challenge_completion_notification: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False
    
    def send_challenge_reminder(self, student_id: int) -> bool:
        """تذكير بتحدي اليوم"""
        try:
            from src.services.gamification_service import gamification_service
            
            student = Student.query.get(student_id)
            if not student:
                return False
            
            # الحصول على تقدم التحدي
            progress = gamification_service.get_student_challenge_progress(student_id)
            
            if progress.get('completed'):
                return False  # تم الإكمال
            
            if progress.get('no_challenge'):
                return False  # لا يوجد تحدي
            
            challenge = progress['challenge']
            current_progress = progress.get('progress', 0)
            target = progress.get('target', 0)
            
            title = f"⏰ تذكير: تحدي اليوم!"
            
            if target > 0:
                body = f"""
{challenge['icon']} {challenge['title']}
تقدمك: {current_progress} من {target}

باقي القليل! 💪
المكافأة: ⭐ {challenge['points']} نقطة

⏰ باقي حتى نهاية اليوم
"""
            else:
                body = f"""
{challenge['icon']} {challenge['title']}
{challenge['description']}

لم تبدأ بعد! 
المكافأة: ⭐ {challenge['points']} نقطة

⏰ باقي حتى نهاية اليوم
"""
            
            # إنشاء الإشعار
            notification = Notification.create_notification(
                title=title,
                body=body,
                notification_type='challenge_reminder',
                created_by_ai=True,
                data={'type': 'challenge_reminder'}
            )
            
            # ربطه بالطالب
            student_notif = StudentNotification.create_for_student(
                notification.id,
                student_id
            )
            
            # إرسال عبر FCM
            if student.fcm_token:
                self.fcm_service.send_fcm_notification(
                    student.fcm_token,
                    title,
                    body,
                    {
                        'type': 'challenge_reminder',
                        'notification_id': str(notification.id)
                    }
                )
                student_notif.mark_fcm_sent(True)
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في send_challenge_reminder: {e}")
            return False


# إنشاء instance واحد
smart_notifications = SmartNotificationService()
