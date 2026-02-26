"""
Lesson Prep Service - خدمة تحضير الدروس بالذكاء الاصطناعي
يستخرج صفحات PDF كصور ويرسلها لـ Gemini Vision لتوليد تحضير احترافي
"""
import os
import io
import json
import logging
import tempfile
import time
import requests
from datetime import datetime

import google.generativeai as genai
from flask import current_app

from src.extensions import db
from src.models.textbook import Textbook, LessonPages, LessonPlan
from src.models.curriculum import Lesson, Unit, Course

logger = logging.getLogger(__name__)


class LessonPrepService:
    def __init__(self):
        self.model = None
        self.is_configured = False

    def _ensure_configured(self):
        """تهيئة Gemini API"""
        if self.is_configured and self.model:
            return True
        api_key = current_app.config.get('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY غير موجود")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.is_configured = True
        return True

    def generate_lesson_plan(self, plan_id):
        """توليد تحضير درس كامل"""
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            logger.error(f"التحضير {plan_id} غير موجود")
            return False

        try:
            plan.status = 'generating'
            db.session.commit()

            self._ensure_configured()

            lesson = Lesson.query.get(plan.lesson_id)
            if not lesson:
                raise ValueError("الدرس غير موجود")

            unit = Unit.query.get(lesson.unit_id)
            course = Course.query.get(unit.course_id) if unit else None

            # 1. جلب صفحات الدرس
            page_mapping = LessonPages.query.filter_by(lesson_id=lesson.id).first()

            images = []
            if page_mapping:
                images = self._extract_pages_as_images(
                    page_mapping.textbook.pdf_url,
                    page_mapping.start_page,
                    page_mapping.end_page,
                )

            # 2. بناء البرومبت
            prompt = self._build_prompt(
                lesson_name=lesson.name,
                unit_name=unit.name if unit else '',
                course_name=course.name if course else '',
                teacher_options={
                    'student_level': plan.student_level or 'متفاوت',
                    'student_count': plan.student_count or 30,
                    'weak_students_count': plan.weak_students_count or 5,
                    'excellent_students_count': plan.excellent_students_count or 5,
                    'focus_area': plan.focus_area or 'شامل',
                    'examples_count': plan.examples_count or 5,
                },
            )

            # 3. إرسال لـ Gemini
            content_parts = []
            if images:
                for img_bytes in images:
                    content_parts.append({
                        'mime_type': 'image/png',
                        'data': img_bytes,
                    })
            content_parts.append(prompt)

            logger.info(f"إرسال {len(images)} صورة لـ Gemini للتحضير #{plan_id}")
            ai_text = None
            for attempt in range(3):
                try:
                    response = self.model.generate_content(content_parts)
                    ai_text = response.text
                    break
                except Exception as api_err:
                    err_str = str(api_err)
                    if '429' in err_str or 'Resource exhausted' in err_str.lower():
                        wait = 30 * (attempt + 1)
                        logger.warning(f"Rate limit (429) - محاولة {attempt+1}/3، انتظار {wait} ثانية...")
                        time.sleep(wait)
                    else:
                        raise
            if ai_text is None:
                raise Exception("فشل الاتصال بـ Gemini بعد 3 محاولات (429 Rate Limit). جرب بعد دقائق.")

            # 4. استخراج JSON من الرد
            plan_data = self._extract_json(ai_text)
            if not plan_data:
                # إذا فشل الـ JSON، نحفظ النص كاملاً
                plan_data = {'raw_text': ai_text}

            # 5. توليد PDF
            pdf_url = None
            try:
                pdf_bytes = self._generate_pdf(plan_data, lesson.name, unit.name if unit else '', course.name if course else '')
                if pdf_bytes:
                    # رفع على Cloudinary
                    try:
                        import cloudinary.uploader
                        result = cloudinary.uploader.upload(
                            io.BytesIO(pdf_bytes),
                            resource_type='raw',
                            folder='lesson_plans',
                            public_id=f"plan_{plan_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        )
                        pdf_url = result.get('secure_url') or result.get('url')
                    except Exception as e:
                        logger.warning(f"فشل Cloudinary للـ PDF: {e}")
                        # حفظ محلي
                        upload_dir = os.path.join(os.getcwd(), 'uploads', 'lesson_plans')
                        os.makedirs(upload_dir, exist_ok=True)
                        filename = f"plan_{plan_id}.pdf"
                        filepath = os.path.join(upload_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(pdf_bytes)
                        pdf_url = f"/uploads/lesson_plans/{filename}"
            except Exception as e:
                logger.warning(f"فشل توليد PDF: {e}")

            # 6. حفظ النتيجة
            plan.plan_data = plan_data
            plan.pdf_file_url = pdf_url
            plan.status = 'completed'
            db.session.commit()

            logger.info(f"اكتمل التحضير #{plan_id} بنجاح")
            return True

        except Exception as e:
            logger.error(f"فشل التحضير #{plan_id}: {e}")
            import traceback
            traceback.print_exc()
            plan.status = 'failed'
            plan.error_message = str(e)
            db.session.commit()
            return False

    def _extract_pages_as_images(self, pdf_url, start_page, end_page):
        """استخراج صفحات PDF كصور PNG"""
        images = []
        try:
            import fitz  # PyMuPDF

            # تحميل PDF
            if pdf_url.startswith('http'):
                resp = requests.get(pdf_url, timeout=60)
                resp.raise_for_status()
                pdf_bytes = resp.content
            else:
                # ملف محلي
                filepath = os.path.join(os.getcwd(), pdf_url.lstrip('/'))
                with open(filepath, 'rb') as f:
                    pdf_bytes = f.read()

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # تحويل من 1-based إلى 0-based
            for page_num in range(start_page - 1, min(end_page, len(doc))):
                page = doc[page_num]
                # رندر بـ 2x للوضوح
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)

            doc.close()
            logger.info(f"تم استخراج {len(images)} صفحة من PDF")

        except Exception as e:
            logger.error(f"خطأ في استخراج صفحات PDF: {e}")

        return images

    def _build_prompt(self, lesson_name, unit_name, course_name, teacher_options):
        """بناء البرومبت الاحترافي للتحضير"""
        student_level = teacher_options.get('student_level', 'متفاوت')
        student_count = teacher_options.get('student_count', 30)
        weak_count = teacher_options.get('weak_students_count', 5)
        excellent_count = teacher_options.get('excellent_students_count', 5)
        focus = teacher_options.get('focus_area', 'شامل')
        examples = teacher_options.get('examples_count', 5)

        prompt = f"""أنت خبير تربوي متخصص في تحضير دروس الكيمياء للمرحلة الثانوية في المملكة العربية السعودية.

## المطلوب
حضّر درساً احترافياً كاملاً بناءً على صفحات الكتاب المرفقة.

## معلومات الدرس
- **المقرر**: {course_name}
- **الوحدة**: {unit_name}
- **الدرس**: {lesson_name}

## معلومات الفصل
- **عدد الطلاب**: {student_count}
- **مستوى الطلاب**: {student_level}
- **عدد الطلاب الضعاف**: {weak_count}
- **عدد الطلاب المتفوقين**: {excellent_count}
- **التركيز المطلوب**: {focus}
- **عدد الأمثلة**: {examples}

## التعليمات
أعد الرد بصيغة JSON تتضمن الأقسام التالية:

```json
{{
  "lesson_info": {{
    "title": "عنوان الدرس",
    "course": "اسم المقرر",
    "unit": "اسم الوحدة",
    "duration": "مدة الحصة",
    "date": "",
    "prerequisites": ["المتطلبات السابقة"]
  }},
  "objectives": {{
    "cognitive": ["أهداف معرفية - يتوقع من الطالب أن..."],
    "skill": ["أهداف مهارية"],
    "emotional": ["أهداف وجدانية"]
  }},
  "preparation": {{
    "introduction": "التهيئة والتمهيد - سؤال أو موقف تحفيزي يشد انتباه الطلاب",
    "introduction_activity": "نشاط تفاعلي للتهيئة",
    "connection_to_previous": "ربط بالدرس السابق"
  }},
  "presentation": {{
    "main_concepts": [
      {{
        "concept": "المفهوم",
        "explanation": "الشرح التفصيلي",
        "teaching_method": "استراتيجية التدريس المستخدمة",
        "examples": ["أمثلة توضيحية"],
        "student_activity": "نشاط الطلاب"
      }}
    ],
    "equations": ["المعادلات الكيميائية إن وجدت"],
    "diagrams_description": ["وصف الرسومات والمخططات التوضيحية المطلوبة"]
  }},
  "teaching_strategies": [
    {{
      "strategy": "اسم الاستراتيجية",
      "application": "كيفية تطبيقها في الدرس",
      "duration_minutes": 10
    }}
  ],
  "evaluation": {{
    "formative": [
      {{
        "question": "السؤال",
        "answer": "الإجابة",
        "type": "نوع السؤال (اختياري/مقالي/صح وخطأ)",
        "bloom_level": "مستوى بلوم"
      }}
    ],
    "summative": ["أسئلة التقويم الختامي"],
    "enrichment": ["أسئلة إثرائية للمتفوقين"],
    "remedial": ["أنشطة علاجية للضعاف"]
  }},
  "individual_differences": {{
    "gifted_activities": ["أنشطة للمتفوقين"],
    "weak_support": ["دعم الطلاب الضعاف"],
    "average_activities": ["أنشطة للمستوى المتوسط"]
  }},
  "homework": {{
    "main": ["الواجب الأساسي"],
    "optional": ["واجب اختياري إثرائي"]
  }},
  "time_distribution": [
    {{
      "activity": "النشاط",
      "duration_minutes": 5,
      "notes": "ملاحظات"
    }}
  ],
  "resources": ["الوسائل التعليمية المستخدمة"],
  "safety_notes": ["ملاحظات السلامة (إن وجدت تجارب)"],
  "reflection": {{
    "strengths": "نقاط القوة المتوقعة",
    "improvements": "نقاط التحسين",
    "notes": "ملاحظات إضافية"
  }},
  "values_connection": {{
    "religious": "ربط ديني بآية أو حديث",
    "national": "ربط وطني (رؤية 2030 أو إنجازات سعودية)",
    "life": "ربط بالحياة اليومية"
  }},
  "comparison_tables": [
    {{
      "title": "عنوان جدول المقارنة",
      "headers": ["العنصر 1", "العنصر 2"],
      "rows": [["بيانات", "بيانات"]]
    }}
  ]
}}
```

## تنبيهات مهمة
- التزم بتنسيق JSON بالضبط
- اكتب بالعربية الفصحى
- استخدم مصطلحات كيميائية دقيقة
- اجعل الأمثلة من واقع الحياة السعودية قدر الإمكان
- عند وصف الرسومات، اذكر تفاصيل كافية لرسمها
- ركّز على "{focus}" حسب طلب المعلم
- قدّم {examples} أمثلة على الأقل لكل مفهوم رئيسي
- راعِ الفروق الفردية: {weak_count} ضعاف و {excellent_count} متفوقين
- استخدم صيغة المذكر دائماً (الطلاب، الطالب، المعلم) وليس المؤنث
"""
        return prompt

    def _extract_json(self, text):
        """استخراج JSON من رد الـ AI"""
        try:
            # محاولة 1: JSON block
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # محاولة 2: أول { إلى آخر }
            first = text.find('{')
            last = text.rfind('}')
            if first != -1 and last != -1:
                return json.loads(text[first:last + 1])

        except json.JSONDecodeError as e:
            logger.warning(f"فشل تحليل JSON: {e}")

        return None

    @staticmethod
    def _chem_html(text):
        """تحويل النص الكيميائي إلى HTML مع superscript/subscript"""
        import re
        if not text or not isinstance(text, str):
            return text or ''
        # السهم
        text = text.replace('->', '→')
        # Superscript: ^n, ^2, ^m, ^2+, ^1-
        text = re.sub(r'\^([\w\+\-]+)', r'<sup>\1</sup>', text)
        # Subscript: رقم بعد حرف لاتيني أو ) أو ]
        text = re.sub(r'(?<=[A-Za-z\)\]])([\d]+)', r'<sub>\1</sub>', text)
        return text

    def _generate_pdf(self, plan_data, lesson_name, unit_name, course_name):
        """توليد ملف PDF احترافي من بيانات التحضير باستخدام WeasyPrint"""
        try:
            from weasyprint import HTML
            from flask import render_template
            from jinja2 import pass_eval_context
            from markupsafe import Markup

            # إضافة فلتر chem للقالب
            app = current_app._get_current_object()
            @pass_eval_context
            def chem_filter(eval_ctx, value):
                result = LessonPrepService._chem_html(str(value))
                if eval_ctx.autoescape:
                    return Markup(result)
                return result
            app.jinja_env.filters['chem'] = chem_filter

            lesson_info = plan_data.get('lesson_info', {})
            context = {
                'plan_data': plan_data,
                'lesson_info': lesson_info,
                'lesson_name': lesson_name,
                'unit_name': unit_name,
                'course_name': course_name,
            }

            html_string = render_template('lesson_prep/lesson_plan.html', **context)
            pdf_bytes = HTML(string=html_string).write_pdf()

            logger.info(f"تم توليد PDF بـ WeasyPrint ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"خطأ في توليد PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_unit_distribution(self, plan_id):
        """توليد توزيع وحدة كاملة"""
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return False

        try:
            plan.status = 'generating'
            db.session.commit()

            self._ensure_configured()

            lesson = Lesson.query.get(plan.lesson_id)
            unit = Unit.query.get(lesson.unit_id) if lesson else None
            course = Course.query.get(unit.course_id) if unit else None

            if not unit:
                raise ValueError("الوحدة غير موجودة")

            total_periods = plan.student_count or 12  # عدد الحصص المطلوب

            lessons = Lesson.query.filter_by(unit_id=unit.id).order_by(Lesson.order_num).all()
            lessons_text = "\n".join([f"- {l.name}" for l in lessons])

            prompt = f"""أنت خبير تربوي. أعد توزيع منهج وحدة كيمياء كاملة.

## المقرر: {course.name if course else ''}
## الوحدة: {unit.name}
## الدروس:
{lessons_text}

## عدد الحصص المطلوب: {total_periods} حصة

## المطلوب
أعد توزيع الوحدة على {total_periods} حصة مع مراعاة:
- عدد الحصص المناسب لكل درس
- حصص المراجعة والتقويم
- التدرج في الصعوبة

أعد الرد بصيغة JSON:
```json
{{
  "unit_name": "اسم الوحدة",
  "total_periods": 0,
  "distribution": [
    {{
      "week": 1,
      "period": 1,
      "lesson": "اسم الدرس",
      "topics": ["المواضيع"],
      "activities": ["الأنشطة"],
      "homework": "الواجب"
    }}
  ],
  "assessment_plan": {{
    "formative": ["تقويم تكويني"],
    "summative": "تقويم ختامي"
  }}
}}
```"""

            ai_text = None
            for attempt in range(3):
                try:
                    response = self.model.generate_content(prompt)
                    ai_text = response.text
                    break
                except Exception as api_err:
                    err_str = str(api_err)
                    if '429' in err_str or 'Resource exhausted' in err_str.lower():
                        wait = 30 * (attempt + 1)
                        logger.warning(f"Rate limit (429) توزيع وحدة - محاولة {attempt+1}/3، انتظار {wait} ثانية...")
                        time.sleep(wait)
                    else:
                        raise
            if ai_text is None:
                raise Exception("فشل الاتصال بـ Gemini بعد 3 محاولات (429 Rate Limit)")

            plan_data = self._extract_json(ai_text) or {'raw_text': ai_text}

            plan.plan_data = plan_data
            plan.status = 'completed'
            db.session.commit()

            logger.info(f"اكتمل توزيع الوحدة #{plan_id}")
            return True

        except Exception as e:
            logger.error(f"فشل توزيع الوحدة #{plan_id}: {e}")
            plan.status = 'failed'
            plan.error_message = str(e)
            db.session.commit()
            return False


# Singleton
lesson_prep_service = LessonPrepService()
