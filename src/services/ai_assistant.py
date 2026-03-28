# src/services/ai_assistant.py
"""
خدمة الذكاء الاصطناعي - المحرك الرئيسي
يدعم Google Gemini و Anthropic Claude لتحليل أداء الطلاب
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-genai غير مثبت!")

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

from src.models.ai_analysis import AIAnalysis, AILog, AISetting
from src.extensions import db


class AIAssistant:
    """مساعد AI الذكي - يدعم Gemini و Claude"""

    def __init__(self):
        self.gemini_client = None
        self.claude_client = None
        self.is_configured = False
        self.active_provider = 'gemini-flash'

    def _ensure_configured(self):
        """تهيئة الـ AI provider المختار — يقرأ من الإعداد الموحّد"""
        try:
            from src.services.lesson_prep_service import _EXPLANATION_TO_LESSON_KEY, AI_PROVIDERS as _LP
            exp_provider = AISetting.get_setting('explanation_ai_provider', 'gemini')
            exp_model    = AISetting.get_setting('explanation_ai_model', 'gemini-2.0-flash')
            mapped = _EXPLANATION_TO_LESSON_KEY.get((exp_provider, exp_model))
            new_provider = mapped if mapped and mapped in _LP else (AISetting.get_setting('ai_provider') or 'gemini-flash')
        except Exception:
            new_provider = 'gemini-flash'

        # إذا تغيّر الـ provider، نعيد التهيئة
        if new_provider != self.active_provider:
            print(f"🔄 تغيير AI provider: {self.active_provider} → {new_provider}")
            self.active_provider = new_provider
            self.is_configured = False

        if 'claude' in self.active_provider:
            return self._ensure_claude()
        else:
            return self._ensure_gemini()

    def _ensure_gemini(self):
        """تهيئة Gemini"""
        if self.gemini_client and self.is_configured:
            return True
        try:
            from src.services.gemini_client import gemini_key_manager
            self.gemini_client = gemini_key_manager.get_client()
            if self.gemini_client:
                self.is_configured = True
                print(f"✅ تم تهيئة Gemini بنجاح")
                return True
            if not GEMINI_AVAILABLE:
                print("⚠️ AI غير مفعّل - مكتبة google-genai غير مثبتة")
            else:
                print("⚠️ AI غير مفعّل - تحقق من GOOGLE_AI_API_KEY")
            return False
        except Exception as e:
            print(f"❌ خطأ في تهيئة Gemini: {e}")
            return False

    def _ensure_claude(self):
        """تهيئة Claude"""
        if self.claude_client and self.is_configured:
            return True
        try:
            from src.services.claude_client import claude_key_manager
            self.claude_client = claude_key_manager.get_client()
            if self.claude_client:
                self.is_configured = True
                print(f"✅ تم تهيئة Claude بنجاح")
                return True
            # fallback لـ Gemini
            if not CLAUDE_AVAILABLE:
                print("⚠️ Claude غير متاح (مكتبة غير مثبتة)، استخدام Gemini")
            else:
                print("⚠️ Claude غير متاح (تحقق من CLAUDE_AI_API_KEY)، استخدام Gemini")
            self.active_provider = 'gemini-flash'
            return self._ensure_gemini()
        except Exception as e:
            print(f"❌ خطأ في تهيئة Claude: {e}")
            self.active_provider = 'gemini-flash'
            return self._ensure_gemini()

    def _generate(self, prompt: str) -> Optional[str]:
        """استدعاء AI موحّد - Gemini أو Claude حسب الإعداد"""
        try:
            if 'claude' in self.active_provider and self.claude_client:
                from src.services.lesson_prep_service import AI_PROVIDERS
                model_id = AI_PROVIDERS.get(self.active_provider, {}).get('model', 'claude-haiku-4-5-20251001')
                response = self.claude_client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    messages=[{'role': 'user', 'content': prompt}],
                )
                return response.content[0].text
            elif self.gemini_client:
                from src.services.lesson_prep_service import AI_PROVIDERS as _LP
                model_id = _LP.get(self.active_provider, {}).get('model', 'gemini-2.0-flash')
                response = self.gemini_client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                )
                return response.text
            return None
        except Exception as e:
            print(f"❌ خطأ في _generate [{self.active_provider}]: {e}")
            return None
    
    def analyze_student(self, student_id: int, analysis_type: str = 'on_demand') -> Optional[Dict]:
        """تحليل شامل لأداء طالب"""
        
        if not self._ensure_configured():
             print(f"⚠️ لا يمكن تحليل الطالب {student_id}: AI غير مهيأ")
             return None

        start_time = datetime.utcnow()
        
        try:
            student_data = self._gather_student_data(student_id)
            
            if not student_data:
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
            
            analysis_result = self._process_ai_response(ai_response, student_data)
            analysis_result.update(self._calculate_status(student_data, analysis_result))
            
            analysis = AIAnalysis.create_analysis(
                student_id=student_id,
                analysis_type=analysis_type,
                data=analysis_result
            )
            
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
        """جمع بيانات الطالب"""
        from src.models.student import Student
        from src.models.student_result import StudentResult
        
        try:
            student = Student.query.get(student_id)
            if not student:
                return None
            
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
            
            total_quizzes = len(results)
            total_score = sum(r.score_percentage for r in results)
            average_score = total_score / total_quizzes if total_quizzes > 0 else 0
            
            last_quiz_date = results[0].created_at if results else None
            days_since_last_quiz = (datetime.utcnow() - last_quiz_date).days if last_quiz_date else 999
            
            recent_results = results[:5]
            older_results = results[5:10] if len(results) > 5 else []
            
            recent_avg = sum(r.score_percentage for r in recent_results) / len(recent_results) if recent_results else 0
            older_avg = sum(r.score_percentage for r in older_results) / len(older_results) if older_results else recent_avg
            
            trend_percentage = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            
            topics_performance = {}
            for r in results:
                topic = r.quiz_name
                if topic not in topics_performance:
                    topics_performance[topic] = []
                topics_performance[topic].append(r.score_percentage)
            
            topic_averages = {}
            for topic, scores in topics_performance.items():
                topic_averages[topic] = sum(scores) / len(scores)
            
            weak_topics = [t for t, avg in topic_averages.items() if avg < 60]
            improvement_topics = [t for t, avg in topic_averages.items() if 60 <= avg < 80]
            strong_topics = [t for t, avg in topic_averages.items() if avg >= 80]
            
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
                'topic_averages': topic_averages,
                'weak_topics': weak_topics,
                'improvement_topics': improvement_topics,
                'strong_topics': strong_topics,
                'is_new_student': False
            }
            
        except Exception as e:
            print(f"❌ خطأ في _gather_student_data: {e}")
            return None
    
    def _call_ai_for_analysis(self, data: Dict) -> Optional[str]:
        """استدعاء AI"""
        if not self.is_configured:
            return None

        try:
            prompt = self._build_analysis_prompt(data)
            return self._generate(prompt)
        except Exception as e:
            print(f"❌ خطأ في _call_ai_for_analysis: {e}")
            return None
    
    def _build_analysis_prompt(self, data: Dict) -> str:
        """بناء prompt التحليل"""
        weak_text = ', '.join([f"{t} ({data['topic_averages'].get(t, 0):.0f}%)" for t in data.get('weak_topics', [])])
        improvement_text = ', '.join([f"{t} ({data['topic_averages'].get(t, 0):.0f}%)" for t in data.get('improvement_topics', [])])
        strong_text = ', '.join([f"{t} ({data['topic_averages'].get(t, 0):.0f}%)" for t in data.get('strong_topics', [])])
        
        avg_score = data.get('average_score', 0)
        recent_avg = data.get('recent_average', 0)
        trend_pct = data.get('trend_percentage', 0)
        days_inactive = data.get('days_since_last_quiz', 999)
        is_new = data.get('is_new_student', False)

        return f"""
أنت مساعد تعليمي ذكي في منصة "كيم تحصيلي" لمادة الكيمياء.

بيانات الطالب: {data.get('student_name', 'طالب')}
- الاختبارات: {data.get('total_quizzes', 0)}
- المعدل: {avg_score}%
- المعدل الأخير: {recent_avg}%
- الاتجاه: {trend_pct:+.1f}%
- آخر نشاط: منذ {days_inactive} يوم
- {'طالب جديد لم يحل أي اختبار بعد' if is_new else ''}

المواضيع التي تحتاج تحسين (< 60%):
{weak_text if weak_text else "لا يوجد"}

المواضيع الجيدة (60-79%):
{improvement_text if improvement_text else "لا يوجد"}

المواضيع الممتازة (80%+):
{strong_text if strong_text else "لا توجد بيانات كافية"}

المطلوب: اكتب رسالة محفزة مخصصة بهذا التنسيق:

1. تقييم الأداء:
[تقييم مختصر حسب المعدل]

2. نقاط القوة:
[المواضيع الممتازة]

3. خطة عمل:
[خطة واضحة ومحددة]

4. رسالة تحفيزية:
[رسالة شخصية قصيرة]

تعليمات:
- لا تكتب ترحيب
- ابدأ مباشرة بـ "1. تقييم الأداء:"
- استخدم الرموز بحكمة
- أقصى طول: 500 حرف
- الرد بالعربية
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
        """حساب التصنيف"""
        avg_score = student_data.get('average_score', 0)
        days_inactive = student_data.get('days_since_last_quiz', 0)
        trend = analysis.get('performance_trend', 'unknown')
        total_quizzes = student_data.get('total_quizzes', 0)
        
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
        
        if days_inactive >= critical_inactive or (avg_score < 40 and total_quizzes >= 3):
            status = 'critical'
            severity = 'red'
            suggested_action = 'send_message_and_alert'
        elif days_inactive >= inactive_threshold or avg_score < 60 or (trend == 'declining' and avg_score < 75):
            status = 'needs_attention'
            severity = 'orange'
            suggested_action = 'send_message'
        elif avg_score >= 80:
            status = 'excellent'
            severity = 'green'
            suggested_action = 'send_message'
        elif avg_score >= 60:
            status = 'good'
            severity = 'yellow'
            suggested_action = 'send_message'
        else:
            status = 'needs_attention'
            severity = 'orange'
            suggested_action = 'send_message'
        
        return {
            'student_status': status,
            'severity_level': severity,
            'suggested_action': suggested_action,
            'issues_detected': issues,
            'strengths': strengths
        }
    
    def analyze_weak_topics(self, student_id: int) -> List[Dict]:
        """تحليل المواضيع الضعيفة"""
        from src.models.student_result import StudentResult
        
        try:
            results = StudentResult.query.filter_by(student_id=student_id).all()
            
            if not results:
                return []
            
            topics = {}
            for r in results:
                topic = r.quiz_name
                if topic not in topics:
                    topics[topic] = []
                topics[topic].append(r.score_percentage)
            
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
            
            return sorted(analyzed_topics, key=lambda x: x['average'])
        
        except Exception as e:
            print(f"❌ خطأ في analyze_weak_topics: {e}")
            return []
    
    def chat_with_ai(self, message: str, context: Optional[Dict] = None) -> str:
        """محادثة مع AI"""
        if not self._ensure_configured():
            return "⚠️ AI غير مفعّل - يرجى التحقق من مفتاح API"
        
        try:
            prompt = f"""
أنت مساعد إداري لمنصة كيم تحصيلي التعليمية.
{f"السياق: {json.dumps(context, ensure_ascii=False)}" if context else ""}
السؤال: {message}
الرد بالعربية، مختصر ومهني.
"""
            result = self._generate(prompt)
            return result or "لم أتمكن من الرد"
        except Exception as e:
            print(f"❌ خطأ في chat_with_ai: {e}")
            return f"حدث خطأ: {str(e)}"


    # ============================================
    # Concept Map Generation - جديد
    # ============================================
    
    def generate_concept_map(self, lesson_name: str, lesson_content: str = None, 
                            course_name: str = None, unit_name: str = None) -> Optional[Dict]:
        """
        توليد خريطة مفاهيم تلقائياً من اسم الدرس والمحتوى
        
        Args:
            lesson_name: اسم الدرس
            lesson_content: محتوى الدرس (اختياري)
            course_name: اسم المنهج (اختياري)
            unit_name: اسم الوحدة (اختياري)
            
        Returns:
            Dict: خريطة المفاهيم بصيغة JSON أو None في حالة الفشل
        """
        if not self._ensure_configured():
            print("⚠️ لا يمكن توليد خريطة المفاهيم: AI غير مهيأ")
            return None
        
        start_time = datetime.utcnow()
        
        try:
            # بناء prompt لتوليد الخريطة
            prompt = self._build_concept_map_prompt(
                lesson_name=lesson_name,
                lesson_content=lesson_content,
                course_name=course_name,
                unit_name=unit_name
            )
            
            # استدعاء AI
            ai_text = self._generate(prompt)
            if not ai_text:
                raise Exception("لم يتم الحصول على رد من AI")
            
            # استخراج JSON من الرد
            concept_map_data = self._extract_json_from_response(ai_text)
            
            if not concept_map_data:
                print(f"❌ فشل استخراج JSON من رد AI")
                AILog.log_operation(
                    'generate_concept_map',
                    description=f'فشل توليد خريطة للدرس: {lesson_name}',
                    success=False,
                    error_message='Failed to extract JSON'
                )
                return None
            
            # التحقق من صحة البنية
            if not self._validate_concept_map_structure(concept_map_data):
                print(f"❌ بنية خريطة المفاهيم غير صحيحة")
                AILog.log_operation(
                    'generate_concept_map',
                    description=f'بنية غير صحيحة للدرس: {lesson_name}',
                    success=False,
                    error_message='Invalid structure'
                )
                return None
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            AILog.log_operation(
                'generate_concept_map',
                description=f'توليد ناجح لخريطة الدرس: {lesson_name}',
                success=True,
                duration_seconds=duration,
                data={'lesson_name': lesson_name}
            )
            
            return concept_map_data
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            AILog.log_operation(
                'generate_concept_map',
                description=f'خطأ في توليد خريطة للدرس: {lesson_name}',
                success=False,
                error_message=str(e),
                duration_seconds=duration
            )
            print(f"❌ خطأ في generate_concept_map: {e}")
            return None
    
    def generate_lesson_summary(self, lesson_name: str, lesson_content: str = None,
                               course_name: str = None, unit_name: str = None) -> Optional[Dict]:
        """توليد ملخص الدرس تلقائياً بالذكاء الاصطناعي"""
        if not self._ensure_configured():
            return None

        start_time = datetime.utcnow()
        try:
            prompt = self._build_summary_prompt(lesson_name, lesson_content, course_name, unit_name)
            ai_text = self._generate(prompt)
            if not ai_text:
                raise Exception("لم يتم الحصول على رد من AI")

            data = self._extract_json_from_response(ai_text)
            if not data or 'introduction' not in data:
                raise Exception("بنية الملخص غير صحيحة")

            duration = (datetime.utcnow() - start_time).total_seconds()
            AILog.log_operation('generate_summary', description=f'ملخص: {lesson_name}',
                                success=True, duration_seconds=duration)
            return data

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            AILog.log_operation('generate_summary', description=f'فشل ملخص: {lesson_name}',
                                success=False, error_message=str(e), duration_seconds=duration)
            print(f"❌ خطأ في generate_lesson_summary: {e}")
            return None

    def _build_summary_prompt(self, lesson_name: str, lesson_content: str = None,
                              course_name: str = None, unit_name: str = None) -> str:
        """بناء prompt لتوليد ملخص الدرس"""
        context = f"الدرس: {lesson_name}"
        if course_name:
            context += f"\nالمنهج: {course_name}"
        if unit_name:
            context += f"\nالوحدة: {unit_name}"
        if lesson_content:
            context += f"\n\nمحتوى الدرس (مستخرج من الكتاب المدرسي):\n{lesson_content[:6000]}"

        return f"""
أنت خبير تربوي متخصص في مادة الكيمياء للمرحلة الثانوية.

{context}

المطلوب: قم بإنشاء ملخص شامل للدرس بصيغة JSON بالتنسيق التالي:

{{
  "introduction": "مقدمة تعريفية بالدرس في فقرة واحدة (3-5 جمل)",
  "key_points": [
    "النقطة الرئيسية الأولى مع تفاصيلها",
    "النقطة الرئيسية الثانية (تضمّن المعادلات مثل: 2H₂ + O₂ → 2H₂O)",
    "النقطة الثالثة..."
  ],
  "examples": [
    "مثال عملي أول",
    "مثال عملي ثانٍ"
  ],
  "vocabulary": {{
    "المصطلح الأول": "تعريف المصطلح الأول",
    "المصطلح الثاني": "تعريف المصطلح الثاني"
  }}
}}

تعليمات مهمة:
1. المقدمة: فقرة واحدة واضحة تشرح موضوع الدرس
2. النقاط الرئيسية: 5-8 نقاط تغطي أهم المفاهيم والقوانين
3. المعادلات الكيميائية: استخدم Unicode دائماً: H₂O، CO₂، →، ⇌، Δ، Na⁺، Cl⁻
4. الأمثلة: 2-4 أمثلة عملية أو تطبيقية
5. المصطلحات: 4-8 مصطلحات علمية مهمة مع تعريفاتها
6. إذا كان المحتوى من الكتاب متاحاً، التزم بما ورد فيه تماماً
7. الرد: JSON فقط بدون أي نص إضافي
8. اللغة: العربية الفصحى

أرسل JSON فقط بدون أي نص قبله أو بعده:
"""

    def _build_concept_map_prompt(self, lesson_name: str, lesson_content: str = None,
                                 course_name: str = None, unit_name: str = None) -> str:
        """بناء prompt لتوليد خريطة المفاهيم"""
        
        context = f"الدرس: {lesson_name}"
        if course_name:
            context += f"\nالمنهج: {course_name}"
        if unit_name:
            context += f"\nالوحدة: {unit_name}"
        if lesson_content:
            context += f"\n\nمحتوى الدرس (مستخرج من الكتاب المدرسي):\n{lesson_content[:6000]}"
        
        return f"""
أنت خبير في تصميم خرائط المفاهيم التعليمية لمادة الكيمياء.

{context}

المطلوب: قم بإنشاء خريطة مفاهيم شجرية متداخلة بصيغة JSON. كل فرع يمكن أن يحتوي على "children" (فروع فرعية)، وكل فرع فرعي يمكن أن يحتوي بدوره على "children" أيضاً (بلا حد ثابت للتداخل).

التنسيق المطلوب:

{{
  "center_node": {{
    "text": "المفهوم المركزي (3 كلمات كحد أقصى)",
    "color": "#FFD54F",
    "description": "وصف مختصر"
  }},
  "branches": [
    {{
      "text": "فرع رئيسي 1",
      "color": "#4A90E2",
      "description": "وصف أو معادلة",
      "children": [
        {{
          "text": "فرع فرعي 1.1",
          "color": "#4A90E2",
          "description": "تفصيل أو قانون",
          "children": [
            {{
              "text": "تفصيل أعمق",
              "color": "#4A90E2",
              "description": "شرح أو مثال",
              "children": []
            }}
          ]
        }},
        {{
          "text": "فرع فرعي 1.2",
          "color": "#4A90E2",
          "description": "تفصيل",
          "children": []
        }}
      ]
    }},
    {{
      "text": "فرع رئيسي 2",
      "color": "#50C878",
      "description": "وصف",
      "children": []
    }}
  ]
}}

تعليمات مهمة:
1. العقدة المركزية: 3 كلمات كحد أقصى
2. الفروع الرئيسية: من 3 إلى 6 فروع
3. كل فرع: 4 كلمات كحد أقصى في "text"
4. كل فرع رئيسي يجب أن يحتوي على 2 إلى 4 فروع فرعية في "children"
5. الفروع الفرعية يمكنها هي الأخرى أن تحتوي على "children" حسب الحاجة (عمق 2-3 مستويات كافٍ عادةً)
6. ألوان كل مجموعة (الفرع الرئيسي وأبناؤه) تكون نفس اللون للتمييز البصري:
   - #4A90E2 (أزرق) | #50C878 (أخضر) | #FF6B6B (أحمر) | #FFB347 (برتقالي) | #9B59B6 (بنفسجي) | #F39C12 (ذهبي) | #1ABC9C (فيروزي)
7. الوصف: جملة واحدة، تتضمن المعادلات والقوانين إذا وُجدت
8. المعادلات الكيميائية (مهم جداً): استخدم Unicode: H₂O، CO₂، →، ⇌، Δ، Na⁺، Cl⁻
   - مثال: "2H₂ + O₂ → 2H₂O" | "P₁V₁ = P₂V₂" | "HCl → H⁺ + Cl⁻"
   - لا تتجاهل أي معادلة أو قانون ورد في محتوى الدرس
9. يجب أن يكون المحتوى شاملاً للدرس كله لا مختصراً
10. الرد: JSON فقط بدون أي نص إضافي
11. اللغة: العربية الفصحى

أرسل JSON فقط بدون أي نص قبله أو بعده:
"""
    
    def _extract_json_from_response(self, ai_text: str) -> Optional[Dict]:
        """استخراج JSON من رد AI"""
        try:
            # محاولة 1: البحث عن JSON بين ```json و ```
            if '```json' in ai_text:
                start = ai_text.find('```json') + 7
                end = ai_text.find('```', start)
                json_text = ai_text[start:end].strip()
            elif '```' in ai_text:
                start = ai_text.find('```') + 3
                end = ai_text.find('```', start)
                json_text = ai_text[start:end].strip()
            else:
                # محاولة 2: البحث عن أول { وآخر }
                start = ai_text.find('{')
                end = ai_text.rfind('}') + 1
                if start != -1 and end > start:
                    json_text = ai_text[start:end]
                else:
                    json_text = ai_text.strip()
            
            # تحويل إلى JSON
            data = json.loads(json_text)
            return data
            
        except json.JSONDecodeError as e:
            print(f"❌ خطأ في تحويل JSON: {e}")
            print(f"النص المستلم: {ai_text[:500]}")
            return None
        except Exception as e:
            print(f"❌ خطأ في استخراج JSON: {e}")
            return None
    
    def _validate_concept_map_structure(self, data: Dict) -> bool:
        """التحقق من صحة بنية خريطة المفاهيم"""
        try:
            # التحقق من وجود المفاتيح الأساسية
            if 'center_node' not in data or 'branches' not in data:
                return False
            
            center = data['center_node']
            if not isinstance(center, dict):
                return False
            
            # التحقق من العقدة المركزية
            if 'text' not in center or 'color' not in center:
                return False
            
            # التحقق من الفروع
            branches = data['branches']
            if not isinstance(branches, list) or len(branches) < 2:
                return False
            
            for branch in branches:
                if not isinstance(branch, dict):
                    return False
                if 'text' not in branch or 'color' not in branch:
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في التحقق من البنية: {e}")
            return False


# إنشاء instance عام
ai_assistant = AIAssistant()
