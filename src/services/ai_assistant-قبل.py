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
        """تهيئة أولية فارغة"""
        self.model = None
        self.is_configured = False
        self.api_key = None
        # ✅ تغيير الموديل إلى gemini-2.0-flash (مستقر)
        self.model_name = 'gemini-2.0-flash'
        self.provider = 'gemini'

    def _ensure_configured(self):
        """تهيئة Gemini عند الحاجة"""
        if self.is_configured and self.model:
            return True

        try:
            self.api_key = current_app.config.get('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
            
            try:
                self.model_name = 'gemini-2.0-flash'
                self.provider = AISetting.get_setting('ai_provider', 'gemini')
            except Exception as db_e:
                print(f"⚠️ استخدام الإعدادات الافتراضية: {db_e}")
                self.model_name = 'gemini-2.0-flash'
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
        if not self.model:
            return None
        
        try:
            prompt = self._build_analysis_prompt(data)
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ خطأ في _call_ai_for_analysis: {e}")
            return None
    
    def _build_analysis_prompt(self, data: Dict) -> str:
        """بناء prompt التحليل"""
        weak_text = ', '.join([f"{t} ({data['topic_averages'].get(t, 0):.0f}%)" for t in data.get('weak_topics', [])])
        improvement_text = ', '.join([f"{t} ({data['topic_averages'].get(t, 0):.0f}%)" for t in data.get('improvement_topics', [])])
        strong_text = ', '.join([f"{t} ({data['topic_averages'].get(t, 0):.0f}%)" for t in data.get('strong_topics', [])])
        
        return f"""
أنت مساعد تعليمي ذكي في منصة "كيم تحصيلي" لمادة الكيمياء.

بيانات الطالب: {data['student_name']}
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
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ خطأ في chat_with_ai: {e}")
            return f"حدث خطأ: {str(e)}"


ai_assistant = AIAssistant()
