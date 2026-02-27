"""
Lesson Prep Service - خدمة تحضير الدروس بالذكاء الاصطناعي
يدعم Gemini (Google) و Claude (Anthropic)
- المعلمين: Gemini دائماً (أسرع وأرخص)
- الأدمن: يختار بين Gemini و Claude
"""
import os
import io
import json
import logging
import tempfile
import base64
import requests
from datetime import datetime

import gc
import google.generativeai as genai
from flask import current_app

import time as _time

from src.extensions import db
from src.models.textbook import Textbook, LessonPages, LessonPlan, AIUsageLog
from src.models.curriculum import Lesson, Unit, Course

# تسعيرة كل provider (بالدولار لكل مليون token)
AI_PRICING = {
    'gemini-flash': {'input': 0.075, 'output': 0.30},
    'claude-haiku': {'input': 0.80, 'output': 4.0},
    'claude-sonnet': {'input': 3.0, 'output': 15.0},
    'claude-opus': {'input': 15.0, 'output': 75.0},
}

logger = logging.getLogger(__name__)

# النماذج المتاحة
AI_PROVIDERS = {
    'gemini-flash': {'name': 'Gemini 2.0 Flash', 'provider': 'gemini', 'model': 'gemini-2.0-flash', 'cost': 'منخفض'},
    'claude-haiku': {'name': 'Claude Haiku 4.5', 'provider': 'claude', 'model': 'claude-haiku-4-5-20251001', 'cost': 'منخفض'},
    'claude-sonnet': {'name': 'Claude Sonnet 4.6', 'provider': 'claude', 'model': 'claude-sonnet-4-6', 'cost': 'متوسط'},
    'claude-opus': {'name': 'Claude Opus 4.6', 'provider': 'claude', 'model': 'claude-opus-4-6', 'cost': 'مرتفع'},
}

DEFAULT_PROVIDER = 'gemini-flash'


class RateLimitError(Exception):
    """خطأ تجاوز حد الطلبات - يُستخدم لإعادة المحاولة بدون حظر الـ scheduler"""
    pass


class LessonPrepService:
    def __init__(self):
        self.gemini_model = None
        self.claude_client = None
        self.gemini_configured = False
        self.claude_configured = False

    def _ensure_gemini(self):
        """تهيئة Gemini API"""
        if self.gemini_configured and self.gemini_model:
            return True
        api_key = current_app.config.get('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY غير موجود")
        genai.configure(api_key=api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        self.gemini_configured = True
        return True

    def _ensure_claude(self):
        """تهيئة Claude API"""
        if self.claude_configured and self.claude_client:
            return True
        api_key = current_app.config.get('CLAUDE_AI_API_KEY') or os.getenv('CLAUDE_AI_API_KEY')
        if not api_key:
            raise ValueError("CLAUDE_AI_API_KEY غير موجود")
        import anthropic
        self.claude_client = anthropic.Anthropic(api_key=api_key)
        self.claude_configured = True
        return True

    def _ensure_configured(self, provider=None):
        """تهيئة الـ AI provider المطلوب"""
        provider = provider or DEFAULT_PROVIDER
        info = AI_PROVIDERS.get(provider, AI_PROVIDERS[DEFAULT_PROVIDER])
        if info['provider'] == 'claude':
            self._ensure_claude()
        else:
            self._ensure_gemini()
        return info

    def _get_active_provider(self):
        """جلب الـ provider المختار من إعدادات الأدمن"""
        try:
            from src.models.ai_analysis import AISetting
            provider = AISetting.get_setting('ai_provider')
            if provider and provider in AI_PROVIDERS:
                return provider
        except Exception:
            pass
        return DEFAULT_PROVIDER

    def _call_ai(self, content, label="", images=None, provider=None, plan_id=None, teacher_id=None, operation_type='lesson_prep'):
        """
        استدعاء AI موحّد - يدعم Gemini و Claude
        يُرجع (text, usage_info)
        """
        if not provider:
            provider = self._get_active_provider()
        info = AI_PROVIDERS.get(provider, AI_PROVIDERS[DEFAULT_PROVIDER])

        start_time = _time.time()
        try:
            if info['provider'] == 'claude':
                text, usage = self._call_claude(content, images, info['model'], label)
            else:
                text, usage = self._call_gemini(content, images, label)

            duration = _time.time() - start_time
            usage['provider'] = provider
            usage['duration'] = duration

            # تسجيل التكلفة
            self._log_usage(provider, usage, plan_id, teacher_id, operation_type, duration)

            return text, usage
        except RateLimitError:
            raise
        except Exception as api_err:
            err_str = str(api_err)
            if '429' in err_str or 'resource exhausted' in err_str.lower() or 'quota' in err_str.lower() or 'rate' in err_str.lower():
                logger.warning(f"⚠️ Rate limit (429) {label} [{provider}]")
                raise RateLimitError(f"Rate limit 429 - {label}")
            raise

    def _log_usage(self, provider, usage, plan_id, teacher_id, operation_type, duration):
        """تسجيل استخدام AI في قاعدة البيانات"""
        try:
            pricing = AI_PRICING.get(provider, {'input': 0, 'output': 0})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            cost = (input_tokens * pricing['input'] + output_tokens * pricing['output']) / 1_000_000

            log_entry = AIUsageLog(
                teacher_id=teacher_id,
                ai_provider=provider,
                operation_type=operation_type,
                plan_id=plan_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                duration_seconds=duration,
            )
            db.session.add(log_entry)
            db.session.commit()
            logger.info(f"💰 تكلفة [{provider}] [{operation_type}]: ${cost:.6f} ({input_tokens}→{output_tokens} tokens)")
        except Exception as e:
            logger.warning(f"⚠️ فشل تسجيل التكلفة: {e}")

    def _call_gemini(self, prompt, images=None, label=""):
        """استدعاء Gemini - يُرجع (text, usage_info)"""
        self._ensure_gemini()
        content_parts = []
        if images:
            for img_bytes in images:
                content_parts.append({
                    'mime_type': 'image/jpeg',
                    'data': img_bytes,
                })
        content_parts.append(prompt)
        response = self.gemini_model.generate_content(content_parts)

        # استخراج tokens من usage_metadata
        usage = {'input_tokens': 0, 'output_tokens': 0}
        try:
            if hasattr(response, 'usage_metadata'):
                um = response.usage_metadata
                usage['input_tokens'] = getattr(um, 'prompt_token_count', 0) or 0
                usage['output_tokens'] = getattr(um, 'candidates_token_count', 0) or 0
        except Exception:
            pass

        logger.info(f"✅ Gemini [{label}] - {len(response.text)} حرف ({usage['input_tokens']}→{usage['output_tokens']} tokens)")
        return response.text, usage

    def _call_claude(self, prompt, images=None, model='claude-haiku-4-5-20251001', label=""):
        """استدعاء Claude - يُرجع (text, usage_info)"""
        self._ensure_claude()
        messages_content = []
        if images:
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                messages_content.append({
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': b64,
                    }
                })
        messages_content.append({'type': 'text', 'text': prompt})

        response = self.claude_client.messages.create(
            model=model,
            max_tokens=16384,
            messages=[{'role': 'user', 'content': messages_content}],
        )
        text = response.content[0].text

        # استخراج tokens من response.usage
        usage = {'input_tokens': 0, 'output_tokens': 0}
        try:
            if hasattr(response, 'usage'):
                usage['input_tokens'] = getattr(response.usage, 'input_tokens', 0) or 0
                usage['output_tokens'] = getattr(response.usage, 'output_tokens', 0) or 0
        except Exception:
            pass

        logger.info(f"✅ Claude [{model}] [{label}] - {len(text)} حرف ({usage['input_tokens']}→{usage['output_tokens']} tokens)")
        return text, usage

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
                    scale=0.8,  # دقة منخفضة لتوفير الذاكرة على السيرفر
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

            # 3. إرسال للـ AI
            num_images = len(images) if images else 0
            logger.info(f"إرسال {num_images} صورة للتحضير #{plan_id}")
            ai_text, _ = self._call_ai(prompt, label=f"تحضير #{plan_id}", images=images,
                                        plan_id=plan_id, teacher_id=plan.teacher_id, operation_type='lesson_prep')
            del images

            # 4. استخراج JSON من الرد
            plan_data = self._extract_json(ai_text)
            if not plan_data:
                logger.warning(f"فشل JSON parsing للتحضير #{plan_id}، محاولة إصلاح محلي...")
                plan_data = self._aggressive_json_fix(ai_text)
            if not plan_data:
                # محاولة أخيرة عبر Gemini
                logger.warning(f"فشل الإصلاح المحلي للتحضير #{plan_id}، محاولة Gemini...")
                try:
                    fix_prompt = f"النص التالي يحتوي على JSON لكنه غير صالح. أعد كتابته كـ JSON صالح فقط بدون أي نص إضافي:\n\n{ai_text[:8000]}"
                    fix_response_text, _ = self._call_ai(fix_prompt, label="إصلاح JSON")
                    plan_data = self._extract_json(fix_response_text)
                except Exception as fix_err:
                    logger.warning(f"فشل إصلاح JSON: {fix_err}")

            if not plan_data:
                plan_data = {'raw_text': ai_text}
                logger.error(f"التحضير #{plan_id}: حُفظ كـ raw_text (JSON غير صالح)")

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

            gc.collect()  # تحرير الذاكرة
            logger.info(f"اكتمل التحضير #{plan_id} بنجاح")
            return True

        except RateLimitError:
            # نرفع RateLimitError للـ scheduler بدون تغيير حالة الخطة
            logger.warning(f"⏳ Rate limit للتحضير #{plan_id} - سيُعاد تلقائياً")
            plan.status = 'generating'  # نخليها generating عشان الـ Flutter يستمر polling
            db.session.commit()
            raise
        except Exception as e:
            logger.error(f"فشل التحضير #{plan_id}: {e}")
            import traceback
            traceback.print_exc()
            plan.status = 'failed'
            plan.error_message = str(e)
            db.session.commit()
            return False

    def _extract_pages_as_images(self, pdf_url, start_page, end_page, scale=1.0):
        """استخراج صفحات PDF كصور JPEG بدقة منخفضة لتوفير الذاكرة"""
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
                if os.path.isabs(pdf_url):
                    filepath = pdf_url
                else:
                    filepath = os.path.join(os.getcwd(), pdf_url.lstrip('/'))
                with open(filepath, 'rb') as f:
                    pdf_bytes = f.read()

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            del pdf_bytes
            gc.collect()

            # تحويل من 1-based إلى 0-based
            actual_end = min(end_page, len(doc))
            for page_num in range(start_page - 1, actual_end):
                page = doc[page_num]
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat)
                # ضغط JPEG بجودة 60% لتقليل حجم الصورة والذاكرة
                img_bytes = pix.tobytes("jpeg")
                images.append(img_bytes)
                del pix
                gc.collect()  # تحرير بعد كل صفحة

            doc.close()
            gc.collect()
            total_size = sum(len(img) for img in images)
            logger.info(f"تم استخراج {len(images)} صفحة من PDF (scale={scale}, total={total_size//1024}KB)")

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
- ⚠️ يجب أن يحتوي الرد على كل الأقسام المذكورة أعلاه بدون استثناء (lesson_info, objectives, preparation, presentation, teaching_strategies, evaluation, individual_differences, homework, time_distribution, resources, safety_notes, reflection, values_connection, comparison_tables)
- ⚠️ استخدم نفس أسماء المفاتيح بالضبط كما هي مكتوبة - لا تغيرها (مثلاً: evaluation وليس assessment)
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
        """استخراج JSON من رد الـ AI مع إصلاح الأخطاء الشائعة"""
        import re

        def _try_parse(json_str):
            """محاولة تحليل JSON مع إصلاح أخطاء شائعة"""
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # إصلاح 1: trailing commas قبل } أو ]
            fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # إصلاح 2: حذف تعليقات // ...
            fixed = re.sub(r'//[^\n]*', '', fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # إصلاح 3: إصلاح quotes غير صحيحة
            fixed = fixed.replace("'", '"')
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # إصلاح 4: فاصلة مفقودة بين } و { أو } و " أو ] و { أو ] و "
            fixed = re.sub(r'(\})\s*(\{)', r'\1,\2', fixed)
            fixed = re.sub(r'(\})\s*(")', r'\1,\2', fixed)
            fixed = re.sub(r'(\])\s*(\{)', r'\1,\2', fixed)
            fixed = re.sub(r'(\])\s*(")', r'\1,\2', fixed)
            fixed = re.sub(r'(")\s*(")', r'\1,\2', fixed)  # "value" "key" -> "value","key"
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # إصلاح 5: محاولة إصلاح سطر بسطر - نحاول نحذف السطر المشكل
            try:
                return json.loads(fixed)
            except json.JSONDecodeError as e:
                # نحاول نحدد السطر المشكل ونصلحه
                lines = fixed.split('\n')
                if hasattr(e, 'lineno') and e.lineno and e.lineno <= len(lines):
                    problem_line = e.lineno - 1
                    line = lines[problem_line].rstrip()
                    prev_line = lines[problem_line - 1].rstrip() if problem_line > 0 else ''
                    # لو السطر السابق ما ينتهي بفاصلة وهذا سطر جديد
                    if prev_line and not prev_line.endswith(',') and not prev_line.endswith('{') and not prev_line.endswith('[') and not prev_line.endswith(':'):
                        lines[problem_line - 1] = prev_line + ','
                    try:
                        return json.loads('\n'.join(lines))
                    except json.JSONDecodeError:
                        pass

                logger.warning(f"فشل تحليل JSON: {e}")

            return None

        # محاولة 1: JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            result = _try_parse(json_match.group(1))
            if result:
                return result

        # محاولة 2: أول { إلى آخر }
        first = text.find('{')
        last = text.rfind('}')
        if first != -1 and last != -1:
            result = _try_parse(text[first:last + 1])
            if result:
                return result

        return None

    def _aggressive_json_fix(self, text):
        """إصلاح JSON بطريقة أقوى - سطر بسطر"""
        import re

        # استخراج النص JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            first = text.find('{')
            last = text.rfind('}')
            if first == -1 or last == -1:
                return None
            raw = text[first:last + 1]

        # تنظيف شامل
        # حذف تعليقات
        raw = re.sub(r'//[^\n]*', '', raw)
        # trailing commas
        raw = re.sub(r',\s*([}\]])', r'\1', raw)

        # إصلاح فاصلة مفقودة: "value"\n"key" أو }\n{ أو ]\n{ أو "value"\n{
        raw = re.sub(r'("\s*)\n(\s*")', r'\1,\n\2', raw)
        raw = re.sub(r'(\})\s*\n(\s*\{)', r'\1,\n\2', raw)
        raw = re.sub(r'(\])\s*\n(\s*\{)', r'\1,\n\2', raw)
        raw = re.sub(r'(\])\s*\n(\s*")', r'\1,\n\2', raw)
        raw = re.sub(r'(\})\s*\n(\s*")', r'\1,\n\2', raw)
        raw = re.sub(r'(true|false|null|\d)\s*\n(\s*")', r'\1,\n\2', raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"إصلاح JSON العنيف - خطأ عند حرف {e.pos}: {e.msg}")

            # محاولة إصلاح عند نقطة الخطأ
            if e.pos and e.pos < len(raw):
                # نبحث عن أقرب مكان ممكن نضيف فاصلة
                for delta in range(0, min(20, e.pos)):
                    pos = e.pos - delta
                    if pos > 0 and raw[pos-1] in '"]}0123456789':
                        fixed = raw[:pos] + ',' + raw[pos:]
                        try:
                            return json.loads(fixed)
                        except json.JSONDecodeError:
                            continue

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

    def _generate_unit_pdf(self, plan_data, unit_name, course_name):
        """توليد PDF لتوزيع الوحدة"""
        try:
            from weasyprint import HTML
            from flask import render_template
            from jinja2 import pass_eval_context
            from markupsafe import Markup

            app = current_app._get_current_object()
            @pass_eval_context
            def chem_filter(eval_ctx, value):
                result = LessonPrepService._chem_html(str(value))
                if eval_ctx.autoescape:
                    return Markup(result)
                return result
            app.jinja_env.filters['chem'] = chem_filter

            context = {
                'plan_data': plan_data,
                'unit_name': unit_name,
                'course_name': course_name,
            }

            html_string = render_template('lesson_prep/unit_distribution.html', **context)
            pdf_bytes = HTML(string=html_string).write_pdf()

            logger.info(f"تم توليد PDF الوحدة بـ WeasyPrint ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"خطأ في توليد PDF الوحدة: {e}")
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

            prompt = f"""أنت خبير تربوي متخصص في تحضير دروس الكيمياء للمرحلة الثانوية في السعودية.

## المقرر: {course.name if course else ''}
## الوحدة: {unit.name}
## الدروس:
{lessons_text}

## عدد الحصص المطلوب: {total_periods} حصة

## المطلوب
أعد تحضيراً تفصيلياً كاملاً للوحدة موزعاً على {total_periods} حصة.
كل حصة يجب أن تكون تحضيراً كاملاً كأنها درس مستقل يشمل كل الأقسام التالية.

أعد الرد بصيغة JSON:
```json
{{
  "unit_name": "اسم الوحدة",
  "course_name": "{course.name if course else ''}",
  "total_periods": {total_periods},
  "periods": [
    {{
      "period_number": 1,
      "lesson_name": "اسم الدرس",
      "title": "عنوان الحصة (مثلاً: مقدمة في سرعة التفاعل)",
      "objectives": {{
        "cognitive": ["أهداف معرفية - أن يعرف الطالب..."],
        "skill": ["أهداف مهارية"],
        "emotional": ["أهداف وجدانية"]
      }},
      "preparation": {{
        "introduction": "سؤال أو موقف تحفيزي للتهيئة",
        "connection_to_previous": "ربط بالحصة السابقة"
      }},
      "main_concepts": [
        {{
          "concept": "المفهوم الرئيسي",
          "explanation": "شرح مفصّل",
          "teaching_method": "استراتيجية التدريس المستخدمة",
          "examples": ["مثال 1", "مثال 2"],
          "student_activity": "نشاط الطلاب"
        }}
      ],
      "equations": ["المعادلات الكيميائية إن وجدت"],
      "teaching_strategies": [
        {{
          "strategy": "اسم الاستراتيجية",
          "application": "كيفية تطبيقها",
          "duration_minutes": 10
        }}
      ],
      "evaluation": [
        {{
          "question": "سؤال تقويمي",
          "answer": "الإجابة",
          "bloom_level": "مستوى بلوم"
        }}
      ],
      "individual_differences": {{
        "gifted_activities": ["نشاط للمتفوقين"],
        "weak_support": ["دعم الضعاف"]
      }},
      "homework": {{
        "main": ["الواجب الأساسي"],
        "optional": ["واجب اختياري"]
      }},
      "time_distribution": [
        {{
          "activity": "النشاط",
          "duration_minutes": 5
        }}
      ],
      "resources": ["الوسائل التعليمية"],
      "values_connection": {{
        "religious": "ربط ديني",
        "national": "ربط وطني",
        "life": "ربط بالحياة"
      }},
      "notes": "ملاحظات للمعلم"
    }}
  ],
  "assessment_plan": {{
    "formative": ["أساليب تقويم تكويني"],
    "summative": "وصف التقويم الختامي"
  }}
}}
```

## تنبيهات
- التزم بتنسيق JSON بالضبط
- اكتب بالعربية الفصحى والمذكر (الطالب، الطلاب)
- قدّم أمثلة من واقع الحياة السعودية
- اجعل كل حصة مستقلة وكاملة يمكن للمعلم تنفيذها مباشرة
- وزّع المحتوى بالتساوي على الحصص
- خصص حصة أو أكثر للمراجعة والتقويم
- كل حصة يجب أن تحتوي على كل الأقسام المذكورة أعلاه بدون استثناء"""

            ai_text, _ = self._call_ai(prompt, label=f"توزيع وحدة #{plan_id}",
                                        plan_id=plan_id, teacher_id=plan.teacher_id, operation_type='unit_dist')

            plan_data = self._extract_json(ai_text)
            if not plan_data:
                logger.warning(f"فشل JSON parsing للوحدة #{plan_id}، محاولة إصلاح محلي...")
                plan_data = self._aggressive_json_fix(ai_text)
            if not plan_data:
                # محاولة أخيرة عبر Gemini
                logger.warning(f"فشل الإصلاح المحلي للوحدة #{plan_id}، محاولة Gemini...")
                try:
                    fix_prompt = f"النص التالي يحتوي على JSON لكنه غير صالح. أعد كتابته كـ JSON صالح فقط بدون أي نص إضافي:\n\n{ai_text[:8000]}"
                    fix_response_text, _ = self._call_ai(fix_prompt, label="إصلاح JSON")
                    plan_data = self._extract_json(fix_response_text)
                except Exception as fix_err:
                    logger.warning(f"فشل إصلاح JSON الوحدة عبر Gemini: {fix_err}")
            if not plan_data:
                plan_data = {'raw_text': ai_text}
                logger.error(f"الوحدة #{plan_id}: حُفظ كـ raw_text")

            # توليد PDF للوحدة
            pdf_url = None
            try:
                pdf_bytes = self._generate_unit_pdf(
                    plan_data,
                    unit.name,
                    course.name if course else '',
                )
                if pdf_bytes:
                    try:
                        import cloudinary.uploader
                        result = cloudinary.uploader.upload(
                            io.BytesIO(pdf_bytes),
                            resource_type='raw',
                            folder='lesson_plans',
                            public_id=f"unit_{plan_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        )
                        pdf_url = result.get('secure_url') or result.get('url')
                    except Exception as e:
                        logger.warning(f"فشل Cloudinary للـ PDF: {e}")
                        upload_dir = os.path.join(os.getcwd(), 'uploads', 'lesson_plans')
                        os.makedirs(upload_dir, exist_ok=True)
                        filename = f"unit_{plan_id}.pdf"
                        filepath = os.path.join(upload_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(pdf_bytes)
                        pdf_url = f"/uploads/lesson_plans/{filename}"
            except Exception as e:
                logger.warning(f"فشل توليد PDF للوحدة: {e}")

            plan.plan_data = plan_data
            plan.pdf_file_url = pdf_url
            plan.status = 'completed'
            db.session.commit()

            gc.collect()  # تحرير الذاكرة
            logger.info(f"اكتمل توزيع الوحدة #{plan_id}")
            return True

        except RateLimitError:
            logger.warning(f"⏳ Rate limit لتوزيع الوحدة #{plan_id} - سيُعاد تلقائياً")
            plan.status = 'generating'
            db.session.commit()
            raise
        except Exception as e:
            logger.error(f"فشل توزيع الوحدة #{plan_id}: {e}")
            plan.status = 'failed'
            plan.error_message = str(e)
            db.session.commit()
            return False


    def parse_semester_distribution(self, plan_id, weekly_periods=5):
        """تحليل توزيع المنهج الفصلي من PDF مرفوع"""
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return False

        try:
            plan.status = 'generating'
            db.session.commit()

            self._ensure_configured()

            course = Course.query.get(plan.course_id) if plan.course_id else None
            if not course:
                raise ValueError("المقرر غير موجود")

            # جلب دروس المقرر
            units = Unit.query.filter_by(course_id=course.id).order_by(Unit.order_num).all()
            lessons_info = []
            for unit in units:
                unit_lessons = Lesson.query.filter_by(unit_id=unit.id).order_by(Lesson.order_num).all()
                for lesson in unit_lessons:
                    lessons_info.append({
                        'lesson_id': lesson.id,
                        'lesson_name': lesson.name,
                        'unit_name': unit.name,
                        'unit_id': unit.id,
                    })

            lessons_text = "\n".join([
                f"- lesson_id: {l['lesson_id']}, الدرس: {l['lesson_name']}, الوحدة: {l['unit_name']}"
                for l in lessons_info
            ])

            # استخراج صور PDF المرفوع
            images = []
            logger.info(f"original_pdf_url: {plan.original_pdf_url}")
            if plan.original_pdf_url:
                pdf_source = plan.original_pdf_url

                # تحديد مسار الملف الفعلي
                if pdf_source.startswith('/') and os.path.exists(pdf_source):
                    # مسار محلي كامل - نستخدمه مباشرة
                    logger.info(f"استخدام المسار المحلي: {pdf_source}")
                elif pdf_source.startswith('/uploads/'):
                    # مسار نسبي - نحوله لكامل
                    local_path = os.path.join(os.getcwd(), pdf_source.lstrip('/'))
                    if os.path.exists(local_path):
                        pdf_source = local_path
                        logger.info(f"استخدام المسار النسبي: {local_path}")
                elif pdf_source.startswith('http'):
                    # URL خارجي (Cloudinary) - نحاول نلقى الملف محلياً أولاً
                    import re
                    filename_match = re.search(r'semester_\d+_\d+_\d+', pdf_source)
                    if filename_match:
                        local_path = os.path.join(os.getcwd(), 'uploads', 'semester_pdfs', filename_match.group() + '.pdf')
                        if os.path.exists(local_path):
                            pdf_source = local_path
                            logger.info(f"استخدام الملف المحلي بدل Cloudinary: {local_path}")

                try:
                    # دقة منخفضة كافية لقراءة النص - يوفر ذاكرة كثير
                    images = self._extract_pages_as_images(pdf_source, 1, 2, scale=0.8)
                except Exception as e:
                    logger.warning(f"فشل استخراج صور PDF: {e}")

            has_images = bool(images)
            logger.info(f"عدد صور PDF المستخرجة: {len(images)}, has_images={has_images}, حصص أسبوعية={weekly_periods}")
            if has_images:
                task_description = f"حلّل توزيع المنهج الفصلي المرفق في الصور وأعد هيكلته بصيغة JSON. عدد الحصص الأسبوعية لهذا المقرر هو {weekly_periods} حصص."
                instructions = f"""1. طابق كل درس في التوزيع مع lesson_id من القائمة أعلاه
2. استخرج أسابيع الفصل مع التواريخ
3. حدد الإجازات والأسابيع بدون دراسة
4. إذا لم تجد تطابق دقيق، اختر أقرب lesson_id
5. كل أسبوع يجب أن يحتوي على دروس مجموع حصصها = {weekly_periods} حصص (إلا أسابيع الإجازات والمراجعة)
6. إذا كان الدرس يحتاج أكثر من حصة واحدة، ضع periods بالعدد المناسب"""
            else:
                task_description = f"أنشئ توزيعاً فصلياً مقترحاً للدروس التالية على 19 أسبوع دراسي (الفصل الثاني 1447هـ). عدد الحصص الأسبوعية = {weekly_periods} حصص."
                instructions = f"""1. وزّع جميع الدروس على الأسابيع بحيث يكون مجموع حصص كل أسبوع = {weekly_periods} حصص
2. أضف إجازة يوم التأسيس في الأسبوع المناسب
3. استخدم lesson_id الصحيح من القائمة
4. رتّب الدروس حسب ترتيب الوحدات
5. إذا كان الدرس يحتاج أكثر من حصة، ضع periods=2 أو أكثر
6. الأسبوع الأخير للاختبارات النهائية"""

            prompt = f"""أنت خبير تربوي متخصص في المناهج السعودية.

## المطلوب
{task_description}

## المقرر: {course.name}
## عدد الحصص الأسبوعية: {weekly_periods}

## دروس المقرر المسجلة في النظام:
{lessons_text}

## التعليمات
{instructions}

أعد الرد بصيغة JSON:
```json
{{
  "semester_name": "اسم الفصل (مثل: الفصل الثاني 1447هـ)",
  "course_name": "{course.name}",
  "weekly_periods": {weekly_periods},
  "total_weeks": 19,
  "weeks": [
    {{
      "week_number": 1,
      "start_date": "2026-02-08",
      "end_date": "2026-02-12",
      "is_holiday": false,
      "holiday_name": "",
      "lessons": [
        {{
          "lesson_id": 42,
          "lesson_name": "اسم الدرس",
          "unit_name": "اسم الوحدة",
          "periods": 2,
          "notes": ""
        }}
      ],
      "notes": ""
    }}
  ]
}}
```

## تنبيهات مهمة جداً
- التزم بتنسيق JSON بالضبط
- استخدم lesson_id الصحيح من القائمة
- حدد is_holiday=true للأسابيع التي فيها إجازة
- التواريخ بتنسيق YYYY-MM-DD
- مهم جداً: مجموع حصص كل أسبوع = {weekly_periods} حصص (لا أكثر ولا أقل، إلا في أسابيع الاختبارات والمراجعة)
- الحصة الواحدة = periods: 1، إذا الدرس يحتاج حصتين ضع periods: 2
"""

            ai_text, _ = self._call_ai(prompt, label=f"توزيع فصلي #{plan_id}", images=images,
                                        plan_id=plan_id, teacher_id=plan.teacher_id, operation_type='semester_dist')
            del images

            logger.info(f"رد AI للتوزيع (أول 500 حرف): {ai_text[:500]}")

            plan_data = self._extract_json(ai_text)
            logger.info(f"نتيجة _extract_json: {type(plan_data)}, keys={list(plan_data.keys()) if isinstance(plan_data, dict) else 'None'}")
            if not plan_data:
                plan_data = self._aggressive_json_fix(ai_text)
                logger.info(f"نتيجة _aggressive_json_fix: {type(plan_data)}")
            if not plan_data:
                try:
                    fix_prompt = f"النص التالي يحتوي على JSON لكنه غير صالح. أعد كتابته كـ JSON صالح فقط:\n\n{ai_text[:8000]}"
                    fix_response_text, _ = self._call_ai(fix_prompt, label="إصلاح JSON")
                    plan_data = self._extract_json(fix_response_text)
                except Exception:
                    pass
            if not plan_data:
                plan_data = {'raw_text': ai_text}
                logger.warning(f"فشل تحليل JSON - حفظ raw_text")

            weeks_count = len(plan_data.get('weeks', [])) if isinstance(plan_data, dict) else 0
            logger.info(f"التوزيع النهائي: {weeks_count} أسبوع, keys={list(plan_data.keys()) if isinstance(plan_data, dict) else 'N/A'}")

            # توليد PDF
            pdf_url = None
            try:
                pdf_bytes = self._generate_semester_pdf(plan_data, course.name)
                if pdf_bytes:
                    try:
                        import cloudinary.uploader
                        result = cloudinary.uploader.upload(
                            io.BytesIO(pdf_bytes),
                            resource_type='raw',
                            folder='lesson_plans',
                            public_id=f"semester_{plan_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        )
                        pdf_url = result.get('secure_url') or result.get('url')
                    except Exception as e:
                        logger.warning(f"فشل Cloudinary: {e}")
                        upload_dir = os.path.join(os.getcwd(), 'uploads', 'lesson_plans')
                        os.makedirs(upload_dir, exist_ok=True)
                        filename = f"semester_{plan_id}.pdf"
                        filepath = os.path.join(upload_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(pdf_bytes)
                        pdf_url = f"/uploads/lesson_plans/{filename}"
            except Exception as e:
                logger.warning(f"فشل توليد PDF الفصلي: {e}")

            plan.plan_data = plan_data
            plan.pdf_file_url = pdf_url
            plan.status = 'completed'
            db.session.commit()

            gc.collect()
            logger.info(f"اكتمل توزيع الفصل #{plan_id}")
            return True

        except RateLimitError:
            logger.warning(f"⏳ Rate limit لتوزيع الفصل #{plan_id} - سيُعاد تلقائياً")
            plan.status = 'generating'
            db.session.commit()
            raise
        except Exception as e:
            logger.error(f"فشل توزيع الفصل #{plan_id}: {e}")
            import traceback
            traceback.print_exc()
            plan.status = 'failed'
            plan.error_message = str(e)
            db.session.commit()
            return False

    def _generate_semester_pdf(self, plan_data, course_name):
        """توليد PDF لتوزيع المنهج الفصلي"""
        try:
            from weasyprint import HTML
            from flask import render_template
            from jinja2 import pass_eval_context
            from markupsafe import Markup

            app = current_app._get_current_object()
            @pass_eval_context
            def chem_filter(eval_ctx, value):
                result = LessonPrepService._chem_html(str(value))
                if eval_ctx.autoescape:
                    return Markup(result)
                return result
            app.jinja_env.filters['chem'] = chem_filter

            context = {
                'plan_data': plan_data,
                'course_name': course_name,
            }

            html_string = render_template('lesson_prep/semester_distribution.html', **context)
            pdf_bytes = HTML(string=html_string).write_pdf()

            logger.info(f"تم توليد PDF الفصلي ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"خطأ في توليد PDF الفصلي: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_worksheet(self, plan_id):
        """توليد ورقة عمل تلقائية من تحضير مكتمل"""
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return False

        try:
            plan_data = plan.plan_data or {}
            if not plan_data or 'raw_text' in plan_data:
                raise ValueError("التحضير غير مكتمل أو غير صالح")

            self._ensure_configured()

            lesson_name = plan_data.get('lesson_info', {}).get('title', '')
            if not lesson_name and plan.lesson:
                lesson_name = plan.lesson.name

            lesson = Lesson.query.get(plan.lesson_id) if plan.lesson_id else None
            unit = Unit.query.get(lesson.unit_id) if lesson else None
            course = Course.query.get(unit.course_id) if unit else None

            prompt = f"""أنت معلم كيمياء خبير. أنشئ ورقة عمل شاملة بناءً على التحضير التالي.

## معلومات الدرس
- المقرر: {course.name if course else ''}
- الوحدة: {unit.name if unit else ''}
- الدرس: {lesson_name}

## ملخص التحضير
{json.dumps(plan_data, ensure_ascii=False)[:4000]}

## المطلوب
أنشئ ورقة عمل تحتوي على:
1. أسئلة فراغات (5-8 أسئلة)
2. أسئلة اختيار من متعدد (5-8 أسئلة، كل سؤال 4 خيارات)
3. مسائل حسابية إن وجدت (3-5 مسائل)
4. سؤال تحدي للمتفوقين (1-2)

أعد الرد بصيغة JSON:
```json
{{
  "worksheet_title": "ورقة عمل: {lesson_name}",
  "course_name": "{course.name if course else ''}",
  "unit_name": "{unit.name if unit else ''}",
  "lesson_name": "{lesson_name}",
  "fill_blanks": [
    {{
      "question": "نص السؤال مع ______ للفراغ",
      "answer": "الإجابة"
    }}
  ],
  "multiple_choice": [
    {{
      "question": "نص السؤال",
      "options": ["أ) ...", "ب) ...", "ج) ...", "د) ..."],
      "correct_answer": "أ",
      "correct_index": 0
    }}
  ],
  "calculations": [
    {{
      "question": "نص المسألة",
      "steps": ["الخطوة 1", "الخطوة 2"],
      "answer": "الإجابة النهائية"
    }}
  ],
  "challenge": [
    {{
      "question": "سؤال التحدي",
      "answer": "الإجابة"
    }}
  ]
}}
```

## تنبيهات
- اجعل الأسئلة متدرجة من السهل للصعب
- استخدم مصطلحات كيميائية دقيقة
- المسائل الحسابية تشمل خطوات الحل
"""

            ai_text, _ = self._call_ai(prompt, label=f"ورقة عمل #{plan_id}",
                                        plan_id=plan_id, teacher_id=plan.teacher_id, operation_type='worksheet')

            worksheet_data = self._extract_json(ai_text)
            if not worksheet_data:
                worksheet_data = self._aggressive_json_fix(ai_text)
            if not worksheet_data:
                raise Exception("فشل تحليل JSON لورقة العمل")

            # توليد PDF (نسخة طالب + معلم)
            student_pdf = self._generate_worksheet_pdf(worksheet_data, show_answers=False)
            teacher_pdf = self._generate_worksheet_pdf(worksheet_data, show_answers=True)

            # حفظ
            student_url = None
            teacher_url = None

            upload_dir = os.path.join(os.getcwd(), 'uploads', 'worksheets')
            os.makedirs(upload_dir, exist_ok=True)

            if student_pdf:
                try:
                    import cloudinary.uploader
                    result = cloudinary.uploader.upload(
                        io.BytesIO(student_pdf), resource_type='raw',
                        folder='worksheets',
                        public_id=f"ws_student_{plan_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    )
                    student_url = result.get('secure_url') or result.get('url')
                except Exception:
                    filename = f"ws_student_{plan_id}.pdf"
                    filepath = os.path.join(upload_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(student_pdf)
                    student_url = f"/uploads/worksheets/{filename}"

            if teacher_pdf:
                try:
                    import cloudinary.uploader
                    result = cloudinary.uploader.upload(
                        io.BytesIO(teacher_pdf), resource_type='raw',
                        folder='worksheets',
                        public_id=f"ws_teacher_{plan_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    )
                    teacher_url = result.get('secure_url') or result.get('url')
                except Exception:
                    filename = f"ws_teacher_{plan_id}.pdf"
                    filepath = os.path.join(upload_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(teacher_pdf)
                    teacher_url = f"/uploads/worksheets/{filename}"

            # تخزين بيانات ورقة العمل في plan_data
            updated_data = dict(plan.plan_data or {})
            updated_data['worksheet'] = worksheet_data
            updated_data['worksheet_student_pdf'] = student_url
            updated_data['worksheet_teacher_pdf'] = teacher_url
            plan.plan_data = updated_data
            db.session.commit()

            gc.collect()
            logger.info(f"اكتملت ورقة العمل للتحضير #{plan_id}")
            return True

        except RateLimitError:
            logger.warning(f"⏳ Rate limit لورقة العمل #{plan_id} - سيُعاد تلقائياً")
            raise
        except Exception as e:
            logger.error(f"فشل توليد ورقة العمل #{plan_id}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _generate_worksheet_pdf(self, worksheet_data, show_answers=False):
        """توليد PDF لورقة العمل"""
        try:
            from weasyprint import HTML
            from flask import render_template
            from jinja2 import pass_eval_context
            from markupsafe import Markup

            app = current_app._get_current_object()
            @pass_eval_context
            def chem_filter(eval_ctx, value):
                result = LessonPrepService._chem_html(str(value))
                if eval_ctx.autoescape:
                    return Markup(result)
                return result
            app.jinja_env.filters['chem'] = chem_filter

            context = {
                'data': worksheet_data,
                'show_answers': show_answers,
            }

            html_string = render_template('lesson_prep/worksheet.html', **context)
            pdf_bytes = HTML(string=html_string).write_pdf()
            return pdf_bytes

        except Exception as e:
            logger.error(f"خطأ في توليد PDF ورقة العمل: {e}")
            return None

    def regenerate_section(self, plan_id, section_name):
        """إعادة توليد قسم واحد من التحضير بالذكاء الاصطناعي"""
        plan = LessonPlan.query.get(plan_id)
        if not plan or not plan.plan_data:
            return None

        try:
            self._ensure_configured()

            lesson = Lesson.query.get(plan.lesson_id) if plan.lesson_id else None
            unit = Unit.query.get(lesson.unit_id) if lesson else None
            course = Course.query.get(unit.course_id) if unit else None

            current_section = plan.plan_data.get(section_name, {})

            section_labels = {
                'objectives': 'الأهداف',
                'preparation': 'التهيئة والتمهيد',
                'presentation': 'عرض الدرس',
                'teaching_strategies': 'استراتيجيات التدريس',
                'evaluation': 'التقويم',
                'individual_differences': 'مراعاة الفروق الفردية',
                'homework': 'الواجبات',
                'time_distribution': 'توزيع الوقت',
                'resources': 'الوسائل التعليمية',
                'reflection': 'التأمل والانعكاس',
                'values_connection': 'ربط القيم',
            }

            label = section_labels.get(section_name, section_name)

            prompt = f"""أنت خبير تربوي متخصص في تحضير دروس الكيمياء.

## المطلوب
أعد كتابة قسم "{label}" فقط من تحضير الدرس التالي:
- المقرر: {course.name if course else ''}
- الوحدة: {unit.name if unit else ''}
- الدرس: {lesson.name if lesson else ''}

## القسم الحالي:
{json.dumps(current_section, ensure_ascii=False)[:2000]}

## التعليمات
- حسّن المحتوى واجعله أكثر تفصيلاً وعملية
- التزم بنفس هيكل JSON تماماً
- أعد فقط JSON القسم (ليس التحضير كامل)
"""

            response_text, _ = self._call_ai(prompt, label=f"إعادة توليد {section_name}",
                                            plan_id=plan_id, teacher_id=plan.teacher_id, operation_type='regenerate')
            new_section = self._extract_json(response_text)
            if not new_section:
                new_section = self._aggressive_json_fix(response_text)

            return new_section

        except Exception as e:
            logger.error(f"فشل إعادة توليد القسم {section_name}: {e}")
            return None


# Singleton
lesson_prep_service = LessonPrepService()
