"""
Lesson Prep Service - خدمة تحضير الدروس بالذكاء الاصطناعي
يستخرج صفحات PDF كصور ويرسلها لـ Gemini Vision لتوليد تحضير احترافي
"""
import os
import io
import json
import logging
import tempfile
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
            response = self.model.generate_content(content_parts)
            ai_text = response.text

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
- **عدد الطالبات**: {student_count}
- **مستوى الطالبات**: {student_level}
- **عدد الطالبات الضعيفات**: {weak_count}
- **عدد الطالبات المتفوقات**: {excellent_count}
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
    "cognitive": ["أهداف معرفية - يتوقع من الطالبة أن..."],
    "skill": ["أهداف مهارية"],
    "emotional": ["أهداف وجدانية"]
  }},
  "preparation": {{
    "introduction": "التهيئة والتمهيد - سؤال أو موقف تحفيزي يشد انتباه الطالبات",
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
        "student_activity": "نشاط الطالبات"
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
    "enrichment": ["أسئلة إثرائية للمتفوقات"],
    "remedial": ["أنشطة علاجية للضعيفات"]
  }},
  "individual_differences": {{
    "gifted_activities": ["أنشطة للمتفوقات"],
    "weak_support": ["دعم الطالبات الضعيفات"],
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
- ركّز على "{focus}" حسب طلب المعلمة
- قدّم {examples} أمثلة على الأقل لكل مفهوم رئيسي
- راعِ الفروق الفردية: {weak_count} ضعيفات و {excellent_count} متفوقات
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

    def _generate_pdf(self, plan_data, lesson_name, unit_name, course_name):
        """توليد ملف PDF احترافي من بيانات التحضير"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.enums import TA_RIGHT, TA_CENTER
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                has_arabic = True
            except ImportError:
                has_arabic = False

            def reshape(text):
                if not has_arabic or not text:
                    return text
                reshaped = arabic_reshaper.reshape(text)
                return get_display(reshaped)

            # تسجيل الخط العربي
            font_name = 'Helvetica'
            for font_path in [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
                '/System/Library/Fonts/Supplemental/Arial.ttf',
            ]:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('ArabicFont', font_path))
                        font_name = 'ArabicFont'
                        break
                    except Exception:
                        pass

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=A4,
                rightMargin=1.5 * cm, leftMargin=1.5 * cm,
                topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            )

            # الأنماط
            title_style = ParagraphStyle(
                'Title', fontName=font_name, fontSize=18,
                alignment=TA_CENTER, spaceAfter=12,
                textColor=HexColor('#1a365d'),
            )
            heading_style = ParagraphStyle(
                'Heading', fontName=font_name, fontSize=14,
                alignment=TA_RIGHT, spaceAfter=8, spaceBefore=12,
                textColor=HexColor('#2563eb'),
            )
            body_style = ParagraphStyle(
                'Body', fontName=font_name, fontSize=11,
                alignment=TA_RIGHT, spaceAfter=4,
                leading=16,
            )
            bullet_style = ParagraphStyle(
                'Bullet', fontName=font_name, fontSize=11,
                alignment=TA_RIGHT, spaceAfter=3,
                leftIndent=20, leading=15,
            )

            elements = []

            # العنوان
            lesson_info = plan_data.get('lesson_info', {})
            title_text = lesson_info.get('title', lesson_name)
            elements.append(Paragraph(reshape(f"تحضير درس: {title_text}"), title_style))
            elements.append(Paragraph(reshape(f"{course_name} - {unit_name}"), body_style))
            elements.append(Spacer(1, 12))

            # الأهداف
            objectives = plan_data.get('objectives', {})
            if objectives:
                elements.append(Paragraph(reshape("الأهداف"), heading_style))
                for obj_type, label in [('cognitive', 'معرفية'), ('skill', 'مهارية'), ('emotional', 'وجدانية')]:
                    items = objectives.get(obj_type, [])
                    if items:
                        elements.append(Paragraph(reshape(f"أهداف {label}:"), body_style))
                        for item in items:
                            elements.append(Paragraph(reshape(f"• {item}"), bullet_style))

            # التهيئة
            prep = plan_data.get('preparation', {})
            if prep:
                elements.append(Paragraph(reshape("التهيئة والتمهيد"), heading_style))
                if prep.get('introduction'):
                    elements.append(Paragraph(reshape(prep['introduction']), body_style))
                if prep.get('introduction_activity'):
                    elements.append(Paragraph(reshape(f"النشاط: {prep['introduction_activity']}"), bullet_style))

            # العرض
            presentation = plan_data.get('presentation', {})
            if presentation:
                elements.append(Paragraph(reshape("عرض الدرس"), heading_style))
                for concept in presentation.get('main_concepts', []):
                    if isinstance(concept, dict):
                        elements.append(Paragraph(reshape(f"▸ {concept.get('concept', '')}"), body_style))
                        elements.append(Paragraph(reshape(concept.get('explanation', '')), bullet_style))
                        for ex in concept.get('examples', []):
                            elements.append(Paragraph(reshape(f"  مثال: {ex}"), bullet_style))

                # المعادلات
                for eq in presentation.get('equations', []):
                    elements.append(Paragraph(reshape(f"⚗ {eq}"), bullet_style))

            # استراتيجيات التدريس
            strategies = plan_data.get('teaching_strategies', [])
            if strategies:
                elements.append(Paragraph(reshape("استراتيجيات التدريس"), heading_style))
                for s in strategies:
                    if isinstance(s, dict):
                        elements.append(Paragraph(
                            reshape(f"• {s.get('strategy', '')} ({s.get('duration_minutes', '')} د): {s.get('application', '')}"),
                            bullet_style
                        ))

            # التقويم
            evaluation = plan_data.get('evaluation', {})
            if evaluation:
                elements.append(Paragraph(reshape("التقويم"), heading_style))
                for q in evaluation.get('formative', []):
                    if isinstance(q, dict):
                        elements.append(Paragraph(reshape(f"س: {q.get('question', '')}"), body_style))
                        elements.append(Paragraph(reshape(f"ج: {q.get('answer', '')}"), bullet_style))

                enrichment = evaluation.get('enrichment', [])
                if enrichment:
                    elements.append(Paragraph(reshape("إثرائي:"), body_style))
                    for item in enrichment:
                        elements.append(Paragraph(reshape(f"• {item}"), bullet_style))

                remedial = evaluation.get('remedial', [])
                if remedial:
                    elements.append(Paragraph(reshape("علاجي:"), body_style))
                    for item in remedial:
                        elements.append(Paragraph(reshape(f"• {item}"), bullet_style))

            # الفروق الفردية
            ind_diff = plan_data.get('individual_differences', {})
            if ind_diff:
                elements.append(Paragraph(reshape("مراعاة الفروق الفردية"), heading_style))
                for key, label in [('gifted_activities', 'للمتفوقات'), ('weak_support', 'للضعيفات')]:
                    items = ind_diff.get(key, [])
                    if items:
                        elements.append(Paragraph(reshape(f"{label}:"), body_style))
                        for item in items:
                            elements.append(Paragraph(reshape(f"• {item}"), bullet_style))

            # الواجب
            homework = plan_data.get('homework', {})
            if homework:
                elements.append(Paragraph(reshape("الواجب"), heading_style))
                for item in homework.get('main', []):
                    elements.append(Paragraph(reshape(f"• {item}"), bullet_style))

            # التوزيع الزمني
            time_dist = plan_data.get('time_distribution', [])
            if time_dist:
                elements.append(Paragraph(reshape("التوزيع الزمني"), heading_style))
                table_data = [[reshape('النشاط'), reshape('المدة'), reshape('ملاحظات')]]
                for t in time_dist:
                    if isinstance(t, dict):
                        table_data.append([
                            reshape(t.get('activity', '')),
                            reshape(f"{t.get('duration_minutes', '')} د"),
                            reshape(t.get('notes', '')),
                        ])
                if len(table_data) > 1:
                    table = Table(table_data, colWidths=[8 * cm, 3 * cm, 7 * cm])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2563eb')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#d1d5db')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f9fafb'), HexColor('#ffffff')]),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    elements.append(table)

            # جداول المقارنة
            comparison_tables = plan_data.get('comparison_tables', [])
            for ct in comparison_tables:
                if isinstance(ct, dict):
                    elements.append(Paragraph(reshape(ct.get('title', 'جدول مقارنة')), heading_style))
                    headers = ct.get('headers', [])
                    rows = ct.get('rows', [])
                    if headers and rows:
                        table_data = [[reshape(h) for h in headers]]
                        for row in rows:
                            table_data.append([reshape(str(c)) for c in row])
                        table = Table(table_data)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#10b981')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
                            ('FONTNAME', (0, 0), (-1, -1), font_name),
                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#d1d5db')),
                            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f0fdf4'), HexColor('#ffffff')]),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        elements.append(table)

            # الوسائل التعليمية
            resources = plan_data.get('resources', [])
            if resources:
                elements.append(Paragraph(reshape("الوسائل التعليمية"), heading_style))
                for r in resources:
                    elements.append(Paragraph(reshape(f"• {r}"), bullet_style))

            # التأمل
            reflection = plan_data.get('reflection', {})
            if reflection and isinstance(reflection, dict):
                elements.append(Paragraph(reshape("التأمل الذاتي"), heading_style))
                if reflection.get('strengths'):
                    elements.append(Paragraph(reshape(f"نقاط القوة: {reflection['strengths']}"), body_style))
                if reflection.get('improvements'):
                    elements.append(Paragraph(reshape(f"نقاط التحسين: {reflection['improvements']}"), body_style))

            doc.build(elements)
            buffer.seek(0)
            return buffer.read()

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

            lessons = Lesson.query.filter_by(unit_id=unit.id).order_by(Lesson.order_num).all()
            lessons_text = "\n".join([f"- {l.name}" for l in lessons])

            prompt = f"""أنت خبير تربوي. أعد توزيع منهج وحدة كيمياء كاملة.

## المقرر: {course.name if course else ''}
## الوحدة: {unit.name}
## الدروس:
{lessons_text}

## المطلوب
أعد توزيع الوحدة على الحصص مع مراعاة:
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

            response = self.model.generate_content(prompt)
            plan_data = self._extract_json(response.text) or {'raw_text': response.text}

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
