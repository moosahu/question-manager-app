# src/services/ai_assistant.py
"""
خدمة الذكاء الاصطناعي - المحرك الرئيسي
يستخدم Google Gemini لتحليل أداء الطلاب
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai غير مثبت!")

from src.models.ai_analysis import AIAnalysis, AILog, AISetting
from src.extensions import db


class AIAssistant:
    """مساعد AI الذكي - يحلل أداء الطلاب ويقدم توصيات"""
    
    def __init__(self):
        """
        تهيئة أولية فارغة لتجنب خطأ Application Context.
        لا تقم باستدعاء قاعدة البيانات هنا نهائياً.
        """
        self.model = None
        self.is_configured = False
        self.api_key = None
        self.model_name = 'gemini-1.5-flash' # قيمة افتراضية
        self.provider = 'gemini'

    def _ensure_configured(self):
        """
        دالة مساعدة لتهيئة الإعدادات عند الحاجة فقط
        (Lazy Loading)
        """
        # إذا تم التهيئة سابقاً، لا تعيد الكرة
        if self.is_configured and self.model:
            return True

        try:
            # محاولة جلب المفتاح من كونفيج التطبيق أو متغيرات البيئة
            self.api_key = current_app.config.get('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
            
            # جلب الإعدادات من قاعدة البيانات (الآن آمن لأننا داخل Context)
            try:
                # نضع هذا داخل try/except لأنه يتصل بقاعدة البيانات
                self.model_name = 'gemini-2.0-flash-exp'
                self.provider = AISetting.get_setting('ai_provider', 'gemini')
            except Exception as db_e:
                print(f"⚠️ تعذر جلب إعدادات AI من قاعدة البيانات، استخدام الافتراضي: {db_e}")
                self.model_name = 'gemini-1.5-flash'
                self.provider = 'gemini'

            if self.provider == 'gemini' and GEMINI_AVAILABLE and self.api_key:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.is_configured = True
                return True
            else:
                print("⚠️ AI غير مفعّل - تحقق من GOOGLE_AI_API_KEY")
                return False
        except Exception as e:
            print(f"❌ خطأ في تهيئة AI: {e}")
            return False
    
    def analyze_student(self, student_id: int, analysis_type: str = 'on_demand') -> Optional[Dict]:
        """تحليل شامل لأداء طالب"""
        
        # ✅ الخطوة الأهم: استدعاء التهيئة هنا بدلاً من __init__
        if not self._ensure_configured():
             print(f"⚠️ لا يمكن تحليل الطالب {student_id}: AI غير مهيأ")
             return None

        start_time = datetime.utcnow()
        
        try:
            # 1. جمع بيانات الطالب
            student_data = self._gather_student_data(student_id)
            
            if not student_data:
                # محاولة تسجيل الخطأ (قد تفشل إذا لم يكن هناك context، لذا نحميها)
                try:
                    AILog.log_operation(
                        'analyze_student',
                        description=f'لا توجد بيانات للطالب {student_id}',
                        student_id=student_id,
                        success=False,
                        error_message='No data found'
                    )
                except: pass
                return None
            
            # 2. تحليل البيانات بواسطة AI
            ai_response = self._call_ai_for_analysis(student_data)
            
            if not ai_response:
                try:
                    AILog.log_operation(
                        'analyze_student',
                        description=f'فشل تحليل AI للطالب {student_id}',
                        student_id=student_id,
                        success=False,
                        error_message='AI analysis failed'
                    )
                except: pass
                return None
            
            # 3. معالجة النتيجة
            analysis_result = self._process_ai_response(ai_response, student_data)
            
            # 4. حساب التصنيف والخطورة
            analysis_result.update(self._calculate_status(student_data, analysis_result))
            
            # 5. حفظ التحليل في قاعدة البيانات
            analysis = AIAnalysis.create_analysis(
                student_id=student_id,
                analysis_type=analysis_type,
                data=analysis_result
            )
            
            # 6. تسجيل النجاح
            duration = (datetime.utcnow() - start_time).total_seconds()
            AILog.log_operation(
                'analyze_student',
                description=f'تحليل ناجح للطالب {student_id}',
                student_id=student_id,
                success=True,
                duration_seconds=duration,
                data={'analysis_id': analysis.id}
            )
            
            return analysis.to_dict()
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            try:
                AILog.log_operation(
                    'analyze_student',
                    description=f'خطأ في تحليل الطالب {student_id}',
                    student_id=student_id,
                    success=False,
                    error_message=str(e),
                    duration_seconds=duration
                )
            except: pass
            print(f"❌ خطأ في analyze_student: {e}")
            return None
    
    def _gather_student_data(self, student_id: int) -> Optional[Dict]:
        """جمع جميع بيانات الطالب من قاعدة البيانات"""
        # ✅ استيراد النماذج داخل الدالة لتجنب Circular Import
        from src.models.student import Student
        from src.models.student_result import StudentResult
        
        try:
            # جلب الطالب
            student = Student.query.get(student_id)
            if not student:
                return None
            
            # جلب النتائج
            results = StudentResult.query.filter_by(student_id=student_id)\
                .order_by(StudentResult.created_at.desc()).all()
            
            if not results:
                return {
                    'student_id': student_id,
                    'student_name': student.name,
                    'grade': student.grade,
                    'total_quizzes': 0,
                    'results': [],
                    'is_new_student': True
                }
            
            # تحليل النتائج
            total_quizzes = len(results)
            total_score = sum(r.score_percentage for r in results)
            average_score = total_score / total_quizzes if total_quizzes > 0 else 0
            
            last_quiz_date = results[0].created_at if results else None
            days_since_last_quiz = (datetime.utcnow() - last_quiz_date).days if last_quiz_date else 999
            
            # حساب الاتجاه
            recent_results = results[:5]
            older_results = results[5:10] if len(results) > 5 else []
            
            recent_avg = sum(r.score_percentage for r in recent_results) / len(recent_results) if recent_results else 0
            older_avg = sum(r.score_percentage for r in older_results) / len(older_results) if older_results else recent_avg
            
            trend_percentage = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            
            return {
                'student_id': student_id,
                'student_name': student.name,
                'grade': student.grade,
                'total_quizzes': total_quizzes,
                'average_score': round(average_score, 2),
                'last_quiz_date': last_quiz_date.isoformat() if last_quiz_date else None,
                'days_since_last_quiz': days_since_last_quiz,
                'recent_average': round(recent_avg, 2),
                'older_average': round(older_avg, 2),
                'trend_percentage': round(trend_percentage, 2),
                'results': [
                    {
                        'score': r.score_percentage,
                        'date': r.created_at.isoformat(),
                        'quiz_type': r.quiz_type,
                        'time_spent': r.time_spent
                    } for r in results[:10]
                ],
                'is_new_student': False
            }
            
        except Exception as e:
            print(f"❌ خطأ في _gather_student_data: {e}")
            return None
    
    def _call_ai_for_analysis(self, student_data: Dict) -> Optional[str]:
        """استدعاء AI لتحليل البيانات"""
        
        # التأكد من التهيئة
        if not self._ensure_configured():
            return None
        
        prompt = self._create_analysis_prompt(student_data)
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ خطأ في استدعاء AI: {e}")
            return None
    
    def _create_analysis_prompt(self, data: Dict) -> str:
        """إنشاء prompt لـ AI"""
        if data.get('is_new_student'):
            return f"""
أنت مساعد تعليمي ذكي لمنصة كيم تحصيلي (كيمياء).
الطالب: {data['student_name']} (الصف {data['grade']})
الحالة: طالب جديد.

المطلوب: رسالة ترحيب، نصائح للبدء، وتوصيات عامة.

تعليمات مهمة:
- لا تكتب "أهلاً بك يا {data['student_name']}" أو أي ترحيب بالاسم
- ابدأ مباشرة بالمحتوى
- الرد بالعربية فقط، مختصر ومحفز
"""
        
        # تحليل المواضيع
        weak_topics = self.analyze_weak_topics(data['student_id'])
        
        # تصنيف المواضيع حسب الأداء
        actually_weak = []     # < 60%
        needs_work = []        # 60-79%
        good_topics = []       # 80-89%
        excellent_topics = []  # >= 90%
        
        for topic in weak_topics:
            avg = topic['average']
            if avg < 60:
                actually_weak.append(topic)
            elif avg < 80:
                needs_work.append(topic)
            elif avg < 90:
                good_topics.append(topic)
            else:
                excellent_topics.append(topic)
        
        # تنسيق المواضيع حسب التصنيف
        weak_text = ""
        if actually_weak:
            weak_text = "\n".join([
                f"- {t['topic']}: {t['average']}% (يحتاج تحسين)"
                for t in actually_weak[:3]
            ])
        
        improvement_text = ""
        if needs_work:
            improvement_text = "\n".join([
                f"- {t['topic']}: {t['average']}% (جيد، يمكن تحسينه)"
                for t in needs_work[:3]
            ])
        
        strong_text = ""
        if excellent_topics:
            strong_text = "\n".join([
                f"- {t['topic']}: {t['average']}%"
                for t in excellent_topics[:3]
            ])
        elif good_topics:
            strong_text = "\n".join([
                f"- {t['topic']}: {t['average']}%"
                for t in good_topics[:3]
            ])
        
        return f"""
أنت مساعد تعليمي ذكي لمنصة كيم تحصيلي (كيمياء).

الطالب: {data['student_name']}
الصف: {data['grade']}
الإحصائيات العامة:
- الاختبارات: {data['total_quizzes']}
- المعدل: {data['average_score']}%
- المعدل الأخير: {data['recent_average']}%
- الاتجاه: {data['trend_percentage']:+.1f}%
- آخر نشاط: منذ {data['days_since_last_quiz']} يوم

المواضيع التي تحتاج تحسين (< 60%):
{weak_text if weak_text else "لا يوجد"}

المواضيع الجيدة (60-79%):
{improvement_text if improvement_text else "لا يوجد"}

المواضيع الممتازة (80%+):
{strong_text if strong_text else "لا توجد بيانات كافية"}

المطلوب: اكتب تحليلاً مخصصاً بهذا التنسيق:

1. تقييم الأداء:
[فقط المواضيع < 60% (إن وجدت). إذا لم توجد، اكتب "أداؤك جيد في معظم المواضيع!"]

2. نقاط القوة:
[فقط المواضيع >= 80%]

3. خطة عمل:
[توصيات محددة للمواضيع < 60% فقط. اذكر عدد الاختبارات المطلوبة]

4. رسالة تحفيزية:
[رسالة شخصية قصيرة ومحفزة]

تعليمات مهمة:
- لا تكتب "أهلاً بك" أو "مرحباً" أو أي ترحيب
- ابدأ مباشرة بـ "1. تقييم الأداء:"
- لا تذكر المواضيع الممتازة (>= 80%) في قسم "تقييم الأداء"
- ضع المواضيع الممتازة فقط في قسم "نقاط القوة"
- ضع سطر جديد بعد كل عنوان رئيسي
- اذكر المواضيع بالاسم الكامل
- كن محدداً في الأرقام
- استخدم نقاط (•) للقوائم الفرعية
- الرد بالعربية، مختصر ومهني
"""
    
    def _process_ai_response(self, ai_text: str, student_data: Dict) -> Dict:
        """معالجة رد AI"""
        return {
            'total_quizzes': student_data.get('total_quizzes', 0),
            'average_score': student_data.get('average_score', 0),
            'last_quiz_date': student_data.get('last_quiz_date'),
            'days_since_last_quiz': student_data.get('days_since_last_quiz', 0),
            'performance_trend': self._extract_trend(student_data),
            'trend_percentage': student_data.get('trend_percentage', 0),
            'ai_recommendations': ai_text,
            'full_analysis': {
                'raw_response': ai_text,
                'student_data': student_data
            }
        }
    
    def _extract_trend(self, data: Dict) -> str:
        """استخراج اتجاه الأداء"""
        trend_pct = data.get('trend_percentage', 0)
        if trend_pct > 10: return 'improving'
        elif trend_pct < -10: return 'declining'
        elif abs(trend_pct) <= 10: return 'stable'
        return 'unknown'
    
    def _calculate_status(self, student_data: Dict, analysis: Dict) -> Dict:
        """حساب التصنيف ومستوى الخطورة"""
        avg_score = student_data.get('average_score', 0)
        days_inactive = student_data.get('days_since_last_quiz', 0)
        trend = analysis.get('performance_trend', 'unknown')
        total_quizzes = student_data.get('total_quizzes', 0)
        
        # استخدام try-except هنا أيضاً للسلامة
        try:
            inactive_threshold = AISetting.get_setting('inactive_days_threshold', 7)
            critical_inactive = AISetting.get_setting('critical_inactive_days', 14)
        except:
            inactive_threshold = 7
            critical_inactive = 14
        
        issues = []
        strengths = []
        
        if days_inactive >= critical_inactive:
            issues.append(f'غير نشط منذ {days_inactive} يوم')
        elif days_inactive >= inactive_threshold:
            issues.append(f'نشاط منخفض ({days_inactive} يوم)')
        
        if trend == 'declining': issues.append('انخفاض في الأداء')
        if avg_score < 50: issues.append('معدل منخفض جداً')
        elif avg_score < 70: issues.append('معدل أقل من المطلوب')
        
        if avg_score >= 85: strengths.append('أداء ممتاز')
        elif avg_score >= 75: strengths.append('أداء جيد')
        if trend == 'improving': strengths.append('تحسن مستمر')
        if days_inactive <= 1: strengths.append('نشط ومواظب')
        
        # ==================== ✅ تعديل التصنيفات والإرسال ====================
        if days_inactive >= critical_inactive or (avg_score < 40 and total_quizzes >= 3):
            # 🔴 حرج: إرسال للطالب + تنبيه للأدمن
            status = 'critical'
            severity = 'red'
            suggested_action = 'send_message_and_alert'  # ✅ جديد: إرسال للاثنين
        elif days_inactive >= inactive_threshold or avg_score < 60 or (trend == 'declining' and avg_score < 75):
            # 🟠 يحتاج انتباه: إرسال للطالب فقط
            # ملاحظة: declining فقط إذا المعدل أقل من 75% (لتجنب تصنيف الممتازين كـ needs_attention)
            status = 'needs_attention'
            severity = 'orange'
            suggested_action = 'send_message'
        elif avg_score >= 80:
            # 🟢 ممتاز: إرسال رسالة تهنئة
            status = 'excellent'
            severity = 'green'
            suggested_action = 'send_message'  # ✅ تعديل: كان no_action
        elif avg_score >= 60:
            # 🟡 جيد: إرسال رسالة تشجيع
            status = 'good'
            severity = 'yellow'
            suggested_action = 'send_message'  # ✅ تعديل: الآن يرسل
        else:
            # 🟠 يحتاج انتباه (احتياطي)
            status = 'needs_attention'
            severity = 'orange'
            suggested_action = 'send_message'
        # ==================== ✅ نهاية التعديل ====================
        
        return {
            'student_status': status,
            'severity_level': severity,
            'suggested_action': suggested_action,
            'issues_detected': issues,
            'strengths': strengths
        }
    
    def analyze_weak_topics(self, student_id: int) -> List[Dict]:
        """تحليل المواضيع التي يضعف فيها الطالب"""
        from src.models.student_result import StudentResult
        
        try:
            # جلب النتائج
            results = StudentResult.query.filter_by(student_id=student_id).all()
            
            if not results:
                return []
            
            # تجميع حسب المواضيع
            topics = {}
            for r in results:
                topic = r.quiz_name
                if topic not in topics:
                    topics[topic] = []
                topics[topic].append(r.score_percentage)
            
            # حساب المتوسط لكل موضوع
            analyzed_topics = []
            for topic, scores in topics.items():
                avg = sum(scores) / len(scores)
                analyzed_topics.append({
                    'topic': topic,
                    'average': round(avg, 1),
                    'attempts': len(scores),
                    'last_score': scores[0] if scores else 0,
                    'trend': 'improving' if len(scores) >= 2 and scores[0] > scores[-1] else 'declining'
                })
            
            # ترتيب من الأضعف للأقوى
            return sorted(analyzed_topics, key=lambda x: x['average'])
        
        except Exception as e:
            print(f"❌ خطأ في analyze_weak_topics: {e}")
            return []
    
    def chat_with_ai(self, message: str, context: Optional[Dict] = None) -> str:
        """محادثة حرة مع AI (للأدمن)"""
        if not self._ensure_configured():
            return "⚠️ AI غير مفعّل حالياً - يرجى التحقق من مفتاح API"
        
        try:
            prompt = f"""
أنت مساعد إداري لمنصة كيم تحصيلي التعليمية.
{f"السياق: {json.dumps(context, ensure_ascii=False)}" if context else ""}
السؤال: {message}
الرد بالعربية، مختصر ومهني.
"""
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ خطأ في chat_with_ai: {e}")
            return f"حدث خطأ: {str(e)}"

# إنشاء instance واحد
ai_assistant = AIAssistant()