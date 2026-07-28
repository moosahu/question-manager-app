# src/services/diagnostic_service.py
"""
خدمة الاختبارات التشخيصية
- توليد أسئلة من بنك الأسئلة
- توليد أسئلة بـ AI إذا لزم الأمر
- استخراج ورقة اختبار PDF
- تحليل النتائج
"""

import os
import io
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import current_app

# AI
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from src.extensions import db
    from src.models.question import Question, Option
    from src.models.curriculum import Lesson, Unit, Course
except ImportError:
    from extensions import db
    from models.question import Question, Option
    from models.curriculum import Lesson, Unit, Course


class DiagnosticService:
    """خدمة الاختبارات التشخيصية"""
    
    def __init__(self):
        self.client = None
        self.search_enabled = False
        self.is_configured = False

    def _get_model(self) -> str:
        """جلب اسم النموذج من إعدادات DB"""
        try:
            from src.models.ai_analysis import AISetting
            return AISetting.get_setting('explanation_ai_model', 'gemini-2.0-flash')
        except Exception:
            return 'gemini-2.0-flash'

    def _generate_with_rotation(self, prompt):
        """يستدعي Gemini، وعند 429/quota يدور للمفتاح التالي ويعيد المحاولة مرة وحدة."""
        from src.services.gemini_client import gemini_key_manager
        try:
            return self.client.models.generate_content(model=self._get_model(), contents=prompt)
        except Exception as e:
            if gemini_key_manager.is_quota_error(str(e)) and gemini_key_manager.rotate_key():
                self.client = gemini_key_manager.get_client()
                return self.client.models.generate_content(model=self._get_model(), contents=prompt)
            raise

    def _configure_ai(self):
        """تهيئة AI مع دعم البحث في الإنترنت"""
        if self.is_configured:
            return True

        try:
            from src.services.gemini_client import gemini_key_manager
            self.client = gemini_key_manager.get_client()
            if self.client:
                self.search_enabled = True
                self.is_configured = True
                print("✅ AI configured with Google Search enabled")
                return True
        except Exception as e:
            print(f"❌ AI Error: {e}")
        return False
    
    def generate_test(
        self,
        lesson_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        course_id: Optional[int] = None,
        test_type: str = 'pre_test',
        questions_count: int = 5,
        difficulty_dist: Optional[Dict] = None,
        force_ai: bool = True  # تغيير: AI دائماً للاختبارات التشخيصية
    ) -> Dict:
        """
        توليد اختبار تشخيصي
        
        الاختبارات التشخيصية تُولَّد دائماً بالذكاء الاصطناعي
        لضمان أسئلة جديدة ومختلفة عن بنك الأسئلة
        
        Args:
            lesson_id: معرف الدرس
            unit_id: معرف الوحدة
            course_id: معرف المنهج
            test_type: نوع الاختبار (pre_test أو post_test)
            questions_count: عدد الأسئلة
            difficulty_dist: توزيع الصعوبة
            force_ai: توليد جميع الأسئلة بـ AI (افتراضي: True)
        """
        try:
            if not difficulty_dist:
                difficulty_dist = {'easy': 2, 'medium': 2, 'hard': 1}
            
            # جلب معلومات الدرس/الوحدة
            context = self._get_context(lesson_id, unit_id, course_id)
            if not context:
                return {'success': False, 'error': 'لم يتم العثور على الدرس أو الوحدة'}
            
            # === الاختبارات التشخيصية: توليد AI دائماً ===
            questions = []
            
            # محاولة توليد الأسئلة بـ AI
            if self._configure_ai():
                print(f"🤖 توليد {questions_count} أسئلة بالذكاء الاصطناعي...")
                ai_questions = self._generate_ai_questions(
                    context,
                    questions_count,
                    difficulty_dist,
                    test_type
                )
                questions.extend(ai_questions)
                print(f"✅ تم توليد {len(ai_questions)} أسئلة بـ AI")
            else:
                print("⚠️ AI غير متوفر - محاولة استخدام بنك الأسئلة كبديل")
                # فقط كبديل إذا AI غير متوفر
                questions = self._fetch_questions(
                    lesson_id, unit_id, course_id,
                    questions_count, difficulty_dist
                )
            
            if not questions:
                return {
                    'success': False, 
                    'error': 'لم يتم توليد أي أسئلة. تأكد من إعداد مفتاح Gemini API'
                }
            
            # تنسيق الأسئلة
            formatted_questions = self._format_questions(questions)
            
            # إنشاء العنوان
            type_text = "قبلي" if test_type == 'pre_test' else "بعدي"
            title = f"اختبار تشخيصي {type_text} - {context['name']}"
            
            return {
                'success': True,
                'title': title,
                'description': f"اختبار تشخيصي {type_text} لقياس مستوى الفهم ({len(formatted_questions)} أسئلة)",
                'context': context,
                'questions': formatted_questions,
                'questions_count': len(formatted_questions),
                'ai_generated': True  # دائماً AI للتشخيصي
            }
            
        except Exception as e:
            print(f"❌ Error generating test: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def _get_context(self, lesson_id, unit_id, course_id) -> Optional[Dict]:
        """جلب سياق الدرس/الوحدة"""
        try:
            if lesson_id:
                lesson = Lesson.query.get(lesson_id)
                if lesson:
                    return {
                        'type': 'lesson',
                        'id': lesson.id,
                        'name': lesson.name,
                        'unit_name': lesson.unit.name if lesson.unit else None,
                        'course_name': lesson.unit.course.name if lesson.unit and lesson.unit.course else None
                    }
            
            if unit_id:
                unit = Unit.query.get(unit_id)
                if unit:
                    lessons = Lesson.query.filter_by(unit_id=unit_id).all()
                    return {
                        'type': 'unit',
                        'id': unit.id,
                        'name': unit.name,
                        'course_name': unit.course.name if unit.course else None,
                        'lessons': [l.name for l in lessons]
                    }
            
            if course_id:
                course = Course.query.get(course_id)
                if course:
                    return {
                        'type': 'course',
                        'id': course.id,
                        'name': course.name
                    }
            
            return None
        except Exception as e:
            print(f"❌ Error getting context: {e}")
            return None
    
    def _fetch_questions(
        self,
        lesson_id, unit_id, course_id,
        count: int,
        difficulty_dist: Dict
    ) -> List:
        """جلب الأسئلة من بنك الأسئلة"""
        try:
            query = Question.query.filter(
                Question.is_blocked == False
            )
            
            # تصفية حسب الدرس/الوحدة
            if lesson_id:
                query = query.filter(Question.lesson_id == lesson_id)
            elif unit_id:
                lesson_ids = [l.id for l in Lesson.query.filter_by(unit_id=unit_id).all()]
                query = query.filter(Question.lesson_id.in_(lesson_ids))
            elif course_id:
                unit_ids = [u.id for u in Unit.query.filter_by(course_id=course_id).all()]
                lesson_ids = [l.id for l in Lesson.query.filter(Lesson.unit_id.in_(unit_ids)).all()]
                query = query.filter(Question.lesson_id.in_(lesson_ids))
            
            all_questions = query.all()
            
            # تصنيف حسب الصعوبة
            by_diff = {'easy': [], 'medium': [], 'hard': []}
            for q in all_questions:
                diff = getattr(q, 'difficulty', 'medium') or 'medium'
                if diff in by_diff:
                    by_diff[diff].append(q)
            
            # اختيار حسب التوزيع
            selected = []
            for diff, needed in difficulty_dist.items():
                available = by_diff.get(diff, [])
                random.shuffle(available)
                selected.extend(available[:needed])
            
            # إكمال العدد إذا لم يكتمل
            if len(selected) < count:
                remaining = [q for q in all_questions if q not in selected]
                random.shuffle(remaining)
                selected.extend(remaining[:count - len(selected)])
            
            random.shuffle(selected)
            return selected[:count]
            
        except Exception as e:
            print(f"❌ Error fetching questions: {e}")
            return []
    
    def _format_questions(self, questions: List) -> List[Dict]:
        """تنسيق الأسئلة"""
        formatted = []
        letters = ['أ', 'ب', 'ج', 'د']
        
        for q in questions:
            # من قاعدة البيانات
            if hasattr(q, 'question_id'):
                options = []
                for i, opt in enumerate(q.options):
                    options.append({
                        'id': opt.option_id,
                        'text': opt.option_text or '',
                        'letter': letters[i] if i < 4 else str(i+1),
                        'image_url': getattr(opt, 'image_url', None),
                        'is_correct': opt.is_correct
                    })
                
                # خلط الخيارات
                random.shuffle(options)
                for i, opt in enumerate(options):
                    opt['letter'] = letters[i] if i < 4 else str(i+1)
                
                formatted.append({
                    'question_id': q.question_id,
                    'text': q.question_text,
                    'image_url': getattr(q, 'image_url', None),
                    'difficulty': getattr(q, 'difficulty', 'medium'),
                    'bloom_level': getattr(q, 'bloom_level', 'understand'),
                    'lesson_name': q.lesson.name if q.lesson else None,
                    'options': options,
                    'source': 'database'
                })
            
            # من AI
            elif isinstance(q, dict):
                options = q.get('options', [])
                for i, opt in enumerate(options):
                    opt['letter'] = letters[i] if i < 4 else str(i+1)
                
                formatted.append({
                    **q,
                    'source': 'ai'
                })
        
        return formatted
    
    def _generate_ai_questions(
        self, 
        context: Dict, 
        count: int, 
        difficulty_dist: Dict,
        test_type: str = 'pre_test'
    ) -> List[Dict]:
        """توليد أسئلة بـ AI بناءً على منهج الكيمياء السعودي (آخر طبعة)"""
        if not self.client:
            return []
        
        try:
            # تحديد نوع الأسئلة حسب نوع الاختبار
            if test_type == 'pre_test':
                focus_text = """الأسئلة تركز على المفاهيم القبلية والمعرفة السابقة اللازمة لفهم هذا الدرس.
   الهدف: قياس استعداد الطالب قبل دراسة الدرس"""
            else:  # post_test
                focus_text = """الأسئلة تركز على المفاهيم والمهارات الأساسية في هذا الدرس.
   الهدف: قياس مدى استيعاب الطالب بعد دراسة الدرس"""
            
            # توزيع الصعوبة
            diff_text = f"""
توزيع مستويات الصعوبة:
- سهل: {difficulty_dist.get('easy', 2)} أسئلة (تذكر واستيعاب)
- متوسط: {difficulty_dist.get('medium', 2)} أسئلة (تطبيق وتحليل)
- صعب: {difficulty_dist.get('hard', 1)} أسئلة (تركيب وتقويم)"""

            prompt = f"""أنت خبير في منهج الكيمياء السعودي (نظام المسارات - الثانوي).

🎯 المطلوب: إنشاء {count} أسئلة اختبار تشخيصي {"قبلي" if test_type == 'pre_test' else "بعدي"}

📚 معلومات الدرس من المنهج السعودي:
- المنهج: {context.get('course_name', 'كيمياء')}
- الوحدة/الفصل: {context.get('unit_name', context.get('name', ''))}
- الدرس: {context.get('name', '')}

⚠️ مهم جداً:
1. الأسئلة يجب أن تكون من **محتوى منهج الكيمياء السعودي الرسمي** (وزارة التعليم السعودية - أحدث طبعة)
2. استخدم المصطلحات والتعريفات الموجودة في الكتاب المدرسي السعودي الحالي
3. الأسئلة تكون على نمط أسئلة اختبارات التحصيلي والقدرات
4. تجنب أي معلومات ليست في المنهج السعودي الرسمي

{diff_text}

📋 {focus_text}

🔬 أنواع الأسئلة المطلوبة:
- أسئلة على المفاهيم الأساسية في الدرس
- أسئلة على القوانين والمعادلات الكيميائية
- أسئلة تطبيقية وحسابية
- أسئلة على التجارب والملاحظات العملية

📝 مواصفات الأسئلة:
1. لكل سؤال 4 خيارات فقط (أ، ب، ج، د)
2. خيار واحد صحيح فقط
3. الخيارات الخاطئة تمثل أخطاء شائعة يقع فيها الطلاب
4. الصياغة واضحة ومباشرة بالعربية الفصحى

⚠️ تجنب:
- "كل ما سبق" أو "لا شيء مما سبق"
- خيارات واضح أنها خطأ
- معلومات من خارج المنهج السعودي

📤 أرجع JSON فقط بهذا التنسيق:
[
  {{
    "text": "نص السؤال",
    "difficulty": "easy/medium/hard",
    "bloom_level": "remember/understand/apply/analyze",
    "options": [
      {{"text": "نص الخيار أ", "is_correct": false}},
      {{"text": "نص الخيار ب", "is_correct": true}},
      {{"text": "نص الخيار ج", "is_correct": false}},
      {{"text": "نص الخيار د", "is_correct": false}}
    ],
    "feedback": "الإجابة الصحيحة (ب) لأن..."
  }}
]
"""
            print(f"🤖 Generating questions for: {context.get('name', 'Unknown')}")
            response = self._generate_with_rotation(prompt)
            
            import re
            import json
            
            json_match = re.search(r'\[[\s\S]*\]', response.text)
            if json_match:
                questions = json.loads(json_match.group())
                print(f"✅ Generated {len(questions)} questions from AI")
                return questions
            
            print("⚠️ No valid JSON in AI response")
            return []
            
        except Exception as e:
            print(f"❌ AI Error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def generate_pdf(
        self,
        test_data: Dict,
        include_answers: bool = False,
        header_settings: Optional[Dict] = None
    ) -> Optional[bytes]:
        """
        توليد ورقة اختبار PDF
        """
        if not PDF_AVAILABLE:
            print("❌ ReportLab not installed")
            return None
        
        try:
            buffer = io.BytesIO()
            
            # إعداد المستند
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=50,
                leftMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            # تسجيل خط عربي (إذا متوفر)
            try:
                # محاولة استخدام خط عربي
                pdfmetrics.registerFont(TTFont('Arabic', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
                arabic_font = 'Arabic'
            except:
                arabic_font = 'Helvetica'
            
            # الأنماط
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'ArabicTitle',
                parent=styles['Title'],
                fontName=arabic_font,
                fontSize=18,
                alignment=TA_CENTER,
                spaceAfter=20
            )
            
            question_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontName=arabic_font,
                fontSize=12,
                alignment=TA_RIGHT,
                spaceAfter=10,
                rightIndent=20
            )
            
            option_style = ParagraphStyle(
                'Option',
                parent=styles['Normal'],
                fontName=arabic_font,
                fontSize=11,
                alignment=TA_RIGHT,
                rightIndent=40,
                spaceAfter=5
            )
            
            # بناء المحتوى
            story = []
            
            # === الترويسة ===
            if header_settings:
                header_text = f"""
                <para alignment="center">
                {header_settings.get('country', 'المملكة العربية السعودية')}<br/>
                {header_settings.get('ministry', 'وزارة التعليم')}<br/>
                {header_settings.get('school_name', 'المدرسة')}<br/>
                </para>
                """
                story.append(Paragraph(header_text, title_style))
                story.append(Spacer(1, 10))
            
            # العنوان
            story.append(Paragraph(test_data.get('title', 'اختبار تشخيصي'), title_style))
            
            # معلومات
            info_text = f"عدد الأسئلة: {test_data.get('questions_count', 5)} | الوقت: {test_data.get('time_limit', 15)} دقيقة"
            story.append(Paragraph(info_text, question_style))
            story.append(Spacer(1, 20))
            
            # خانة الاسم
            story.append(Paragraph("الاسم: ________________________    الصف: __________    التاريخ: __________", question_style))
            story.append(Spacer(1, 30))
            
            # === الأسئلة ===
            questions = test_data.get('questions', [])
            
            for i, q in enumerate(questions, 1):
                # نص السؤال
                q_text = f"<b>س{i}:</b> {q.get('text', '')}"
                story.append(Paragraph(q_text, question_style))
                
                # الخيارات
                options = q.get('options', [])
                for opt in options:
                    letter = opt.get('letter', '')
                    text = opt.get('text', '')
                    
                    if include_answers and opt.get('is_correct'):
                        opt_text = f"<b>({letter}) {text} ✓</b>"
                    else:
                        opt_text = f"({letter}) {text}"
                    
                    story.append(Paragraph(opt_text, option_style))
                
                story.append(Spacer(1, 15))
            
            # === نموذج الإجابة (إذا مطلوب) ===
            if include_answers:
                story.append(PageBreak())
                story.append(Paragraph("نموذج الإجابة", title_style))
                story.append(Spacer(1, 20))
                
                # جدول الإجابات
                answer_data = [['السؤال', 'الإجابة']]
                for i, q in enumerate(questions, 1):
                    correct = next((o for o in q.get('options', []) if o.get('is_correct')), None)
                    if correct:
                        answer_data.append([f"س{i}", correct.get('letter', '')])
                
                if len(answer_data) > 1:
                    answer_table = Table(answer_data, colWidths=[100, 100])
                    answer_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTSIZE', (0, 0), (-1, -1), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    story.append(answer_table)
            
            # بناء PDF
            doc.build(story)
            
            buffer.seek(0)
            return buffer.getvalue()
            
        except Exception as e:
            print(f"❌ PDF Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def analyze_result(self, result, context: Dict, test_type: str = 'pre_test') -> Dict:
        """تحليل نتيجة الاختبار بـ AI"""
        if not self._configure_ai():
            return self._basic_analysis(result)
        
        try:
            # تحليل الإجابات الخاطئة
            wrong_answers = [a for a in (result.answers or []) if not a.get('is_correct')]
            wrong_topics = list(set([a.get('topic', '') for a in wrong_answers if a.get('topic')]))
            
            type_text = "القبلي (التشخيصي)" if test_type == 'pre_test' else "البعدي (التحصيلي)"
            
            prompt = f"""أنت مستشار تربوي متخصص في تحليل نتائج الاختبارات التشخيصية في الكيمياء.

📊 بيانات الاختبار:
- نوع الاختبار: {type_text}
- الموضوع: {context.get('name', 'غير محدد')}
- النتيجة: {result.score_percentage:.1f}%
- الصحيح: {result.score} من {result.total_questions}
- الوقت المستغرق: {result.time_spent_seconds // 60} دقيقة و {result.time_spent_seconds % 60} ثانية

{"📍 المواضيع التي أخطأ فيها الطالب: " + ", ".join(wrong_topics) if wrong_topics else ""}

📋 المطلوب:
{"للاختبار القبلي: قيّم جاهزية الطالب لدراسة الدرس الجديد" if test_type == 'pre_test' else "للاختبار البعدي: قيّم مدى استيعاب الطالب للدرس"}

قدم تحليلاً يشمل:
1. 📈 تقييم المستوى العام (ممتاز/جيد/متوسط/ضعيف)
2. 💪 نقاط القوة (إن وجدت)
3. ⚠️ نقاط الضعف والمفاهيم التي تحتاج مراجعة
4. 📚 توصيات محددة للتحسين
5. {"🎯 هل الطالب جاهز لدراسة الدرس؟" if test_type == 'pre_test' else "🎯 هل يحتاج الطالب إعادة شرح؟"}

اكتب الرد بالعربية، مختصر ومفيد (أقل من 200 كلمة)، بأسلوب تشجيعي وإيجابي.
"""
            response = self._generate_with_rotation(prompt)
            
            return {
                'analysis': response.text,
                'level': self._determine_level(result.score_percentage),
                'weak_topics': wrong_topics,
                'ready_for_lesson': result.score_percentage >= 60 if test_type == 'pre_test' else None,
                'needs_review': result.score_percentage < 60 if test_type == 'post_test' else None
            }
            
        except Exception as e:
            print(f"❌ Analysis Error: {e}")
            return self._basic_analysis(result)
    
    def _basic_analysis(self, result) -> Dict:
        """تحليل أساسي بدون AI"""
        pct = result.score_percentage
        
        if pct >= 80:
            analysis = "ممتاز! مستواك جيد جداً في هذا الموضوع."
            level = 'excellent'
        elif pct >= 60:
            analysis = "جيد. لديك فهم أساسي ولكن تحتاج مراجعة بعض المفاهيم."
            level = 'good'
        elif pct >= 40:
            analysis = "متوسط. تحتاج مراجعة الدرس والتركيز على المفاهيم الأساسية."
            level = 'average'
        else:
            analysis = "تحتاج دراسة الموضوع من البداية والتركيز على الأساسيات."
            level = 'weak'
        
        return {
            'analysis': analysis,
            'level': level
        }
    
    def _determine_level(self, percentage: float) -> str:
        if percentage >= 80: return 'excellent'
        if percentage >= 60: return 'good'
        if percentage >= 40: return 'average'
        return 'weak'
    
    def compare_results(self, pre_result, post_result, context: Dict) -> Dict:
        """مقارنة القبلي والبعدي بتحليل AI"""
        improvement = post_result.score_percentage - pre_result.score_percentage
        
        # تحديد الفعالية
        if improvement >= 30:
            effectiveness = 'excellent'
        elif improvement >= 15:
            effectiveness = 'good'
        elif improvement >= 0:
            effectiveness = 'moderate'
        else:
            effectiveness = 'poor'
        
        # تحليل AI متقدم
        if self._configure_ai():
            try:
                # تحليل نقاط الضعف المستمرة
                pre_wrong = set([a.get('topic', '') for a in (pre_result.answers or []) if not a.get('is_correct') and a.get('topic')])
                post_wrong = set([a.get('topic', '') for a in (post_result.answers or []) if not a.get('is_correct') and a.get('topic')])
                still_weak = list(pre_wrong & post_wrong)  # مواضيع لا زالت ضعيفة
                improved = list(pre_wrong - post_wrong)    # مواضيع تحسنت
                
                prompt = f"""أنت مستشار تربوي متخصص في قياس فعالية التعلم.

📊 نتائج المقارنة:
- الدرس: {context.get('name', 'غير محدد')}
- الاختبار القبلي: {pre_result.score_percentage:.0f}%
- الاختبار البعدي: {post_result.score_percentage:.0f}%
- نسبة التحسن: {improvement:+.0f}%

{"📈 المواضيع التي تحسن فيها الطالب: " + ", ".join(improved) if improved else ""}
{"⚠️ المواضيع التي لا زالت تحتاج عمل: " + ", ".join(still_weak) if still_weak else ""}

قدم تقريراً مختصراً يشمل:
1. 🎯 تقييم فعالية التعلم
2. 📈 الإنجازات والتقدم
3. ⚠️ المجالات التي تحتاج متابعة
4. 📚 توصيات للمرحلة القادمة
5. 💬 رسالة تحفيزية للطالب

اكتب بأسلوب إيجابي ومشجع، أقل من 150 كلمة.
"""
                response = self._generate_with_rotation(prompt)
                analysis = response.text
                
            except Exception as e:
                print(f"❌ Comparison AI Error: {e}")
                analysis = self._basic_comparison_analysis(pre_result, post_result, improvement)
        else:
            analysis = self._basic_comparison_analysis(pre_result, post_result, improvement)
        
        return {
            'pre_score': pre_result.score_percentage,
            'post_score': post_result.score_percentage,
            'improvement': improvement,
            'effectiveness': effectiveness,
            'effectiveness_ar': {
                'excellent': 'ممتاز 🎉',
                'good': 'جيد 👍',
                'moderate': 'متوسط 📊',
                'poor': 'يحتاج متابعة ⚠️'
            }.get(effectiveness, 'غير محدد'),
            'analysis': analysis
        }
    
    def _basic_comparison_analysis(self, pre_result, post_result, improvement: float) -> str:
        """تحليل أساسي للمقارنة بدون AI"""
        if improvement >= 30:
            return f"""🎉 تحسن ممتاز!
ارتفع مستواك من {pre_result.score_percentage:.0f}% إلى {post_result.score_percentage:.0f}%
هذا يدل على فهم واستيعاب جيد جداً للدرس. استمر! 💪"""
        elif improvement >= 15:
            return f"""👍 تحسن جيد!
ارتفع مستواك من {pre_result.score_percentage:.0f}% إلى {post_result.score_percentage:.0f}%
تقدم ملحوظ، واصل المذاكرة لتحقيق نتائج أفضل."""
        elif improvement >= 0:
            return f"""📊 تحسن بسيط
من {pre_result.score_percentage:.0f}% إلى {post_result.score_percentage:.0f}%
راجع الدرس مرة أخرى وركز على النقاط الصعبة."""
        else:
            return f"""⚠️ يحتاج مراجعة
انخفض المستوى من {pre_result.score_percentage:.0f}% إلى {post_result.score_percentage:.0f}%
ننصح بإعادة دراسة الدرس والتركيز على الأساسيات."""


# Instance
diagnostic_service = DiagnosticService()
