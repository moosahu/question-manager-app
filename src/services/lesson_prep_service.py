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
    'gemini-flash':   {'input': 0.075, 'output': 0.30},
    'gemini-1.5-pro': {'input': 1.25,  'output': 5.0},
    'gemini-2.5-pro': {'input': 1.25,  'output': 10.0},
    'claude-haiku':   {'input': 0.80,  'output': 4.0},
    'claude-sonnet':  {'input': 3.0,   'output': 15.0},
    'claude-opus':    {'input': 15.0,  'output': 75.0},
}

logger = logging.getLogger(__name__)

# النماذج المتاحة
AI_PROVIDERS = {
    'gemini-flash':   {'name': 'Gemini 2.0 Flash',  'provider': 'gemini', 'model': 'gemini-2.0-flash',       'cost': 'منخفض',  'output_limit': 24576},
    'gemini-1.5-pro': {'name': 'Gemini 1.5 Pro',    'provider': 'gemini', 'model': 'gemini-1.5-pro',         'cost': 'متوسط',  'output_limit': 24576},
    'gemini-2.5-pro': {'name': 'Gemini 2.5 Pro',    'provider': 'gemini', 'model': 'gemini-2.5-pro-preview-03-25', 'cost': 'متوسط',  'output_limit': 65536},
    'claude-haiku':   {'name': 'Claude Haiku 4.5',  'provider': 'claude', 'model': 'claude-haiku-4-5-20251001', 'cost': 'منخفض', 'output_limit': 8192},
    'claude-sonnet':  {'name': 'Claude Sonnet 4.6', 'provider': 'claude', 'model': 'claude-sonnet-4-6',       'cost': 'متوسط',  'output_limit': 16000},
    'claude-opus':    {'name': 'Claude Opus 4.6',   'provider': 'claude', 'model': 'claude-opus-4-6',         'cost': 'مرتفع',  'output_limit': 32000},
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
        self._current_gemini_model_id = None

    def _ensure_gemini(self, model_id='gemini-2.0-flash'):
        """تهيئة Gemini API - يدعم تغيير النموذج ديناميكياً"""
        if self.gemini_configured and self.gemini_model and self._current_gemini_model_id == model_id:
            return True
        api_key = current_app.config.get('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY غير موجود")
        genai.configure(api_key=api_key)
        # جلب الحد الأقصى للإخراج من AI_PROVIDERS
        provider_info = next((v for v in AI_PROVIDERS.values() if v['model'] == model_id), None)
        max_tokens = provider_info['output_limit'] if provider_info else 8192
        self.gemini_model = genai.GenerativeModel(
            model_id,
            generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens)
        )
        self.gemini_configured = True
        self._current_gemini_model_id = model_id
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
            self._ensure_gemini(info['model'])
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
                text, usage = self._call_gemini(content, images, label, info['model'])

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

    def _call_gemini(self, prompt, images=None, label="", model_id='gemini-2.0-flash'):
        """استدعاء Gemini - يُرجع (text, usage_info)"""
        self._ensure_gemini(model_id)
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
        # جلب الحد الأقصى للإخراج من AI_PROVIDERS
        provider_info = next((v for v in AI_PROVIDERS.values() if v['model'] == model), None)
        max_tokens = provider_info['output_limit'] if provider_info else 8192
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

        with self.claude_client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': messages_content}],
        ) as stream:
            response = stream.get_final_message()
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
                    scale=0.5,  # دقة مخفضة لتوفير الذاكرة على السيرفر (512MB RAM)
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
            # حقن الرسوم البيانية SVG
            if isinstance(plan_data, dict) and 'raw_text' not in plan_data:
                plan_data = LessonPrepService._inject_diagrams(plan_data)

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
                if 'drive.google.com' in pdf_url:
                    import re as _re
                    if '/file/d/' in pdf_url:
                        file_id = _re.search(r'/file/d/([a-zA-Z0-9_-]+)', pdf_url).group(1)
                    else:
                        file_id = _re.search(r'[?&]id=([a-zA-Z0-9_-]+)', pdf_url).group(1)
                    
                    # تحميل Google Drive مع معالجة صفحة تحذير الفيروسات
                    session = requests.Session()
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                    resp = session.get(download_url, timeout=120)
                    
                    # إذا رجع HTML (صفحة تحذير) — استخرج confirm token
                    if b'%PDF' not in resp.content[:10]:
                        confirm = _re.search(r'confirm=([0-9A-Za-z_]+)', resp.text)
                        uuid = _re.search(r'uuid=([0-9A-Za-z_-]+)', resp.text)
                        if confirm and uuid:
                            download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={confirm.group(1)}&uuid={uuid.group(1)}"
                        else:
                            download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
                        logger.info(f"✅ Drive confirm URL → {download_url}")
                        resp = session.get(download_url, timeout=120)
                    
                    resp.raise_for_status()
                    if b'%PDF' not in resp.content[:10]:
                        logger.error(f"❌ فشل تحميل PDF من Drive! (size={len(resp.content)})")
                        return []
                    pdf_bytes = resp.content
                    logger.info(f"✅ تم تحميل PDF من Drive ({len(pdf_bytes)//1024}KB)")
                else:
                    resp = requests.get(pdf_url, timeout=120)
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
    "duration": "45 دقيقة",
    "date": "",
    "prerequisites": ["المتطلبات السابقة"]
  }},
  "vocabulary": [
    {{
      "term": "المصطلح الجديد",
      "definition": "تعريف المصطلح بأسلوب واضح ومبسط"
    }}
  ],
  "objectives": {{
    "cognitive": ["أهداف معرفية - يتوقع من الطالب أن..."],
    "skill": ["أهداف مهارية"],
    "emotional": ["أهداف وجدانية"]
  }},
  "diagnostic_questions": [
    {{
      "question": "سؤال للتحقق من المتطلبات القبلية قبل بدء الدرس",
      "answer": "الإجابة النموذجية",
      "purpose": "الهدف من السؤال (مثل: التحقق من فهم مفهوم معين)"
    }}
  ],
  "preparation": {{
    "introduction": "التهيئة والتمهيد - سؤال أو موقف تحفيزي يشد انتباه الطلاب",
    "introduction_answer": "الإجابة المتوقعة أو المثالية من الطالب على سؤال التهيئة",
    "introduction_activity": "نشاط تفاعلي للتهيئة",
    "connection_to_previous": "ربط بالدرس السابق"
  }},
  "presentation": {{
    "main_concepts": [
      {{
        "concept": "المفهوم",
        "explanation": "الشرح التفصيلي",
        "teaching_method": "استراتيجية التدريس المستخدمة",
        "examples": [
          {{
            "problem": "نص المثال أو المسألة",
            "steps": ["الخطوة الأولى", "الخطوة الثانية", "الخطوة الثالثة"],
            "answer": "الإجابة النهائية مع التفسير"
          }}
        ],
        "student_activity": "نشاط الطلاب",
        "diagram": {{
          "type": "concentration_time أو energy_diagram أو rate_time أو none",
          "title": "عنوان الرسم البياني",
          "reactant_label": "اسم المتفاعل (للـ concentration_time و rate_time)",
          "product_label": "اسم الناتج (للـ concentration_time)",
          "is_exothermic": true,
          "note": "ملاحظة أسفل الرسم (اختيارية)"
        }}
      }}
    ],
    "equations": ["المعادلات إن وجدت"],
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
    "summative": [
      {{
        "question": "سؤال التقويم الختامي",
        "type": "نوع السؤال (اختياري/مقالي/صح وخطأ/إكمال)",
        "answer": "الإجابة النموذجية الكاملة",
        "explanation": "توضيح إضافي أو سبب صحة الإجابة"
      }}
    ],
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
    "optional": ["واجب اختياري إثرائي"],
    "solved_examples": [
      {{
        "question": "مسألة أو سؤال من محتوى الكتاب المرفق أو مشابه له",
        "solution": "الحل التفصيلي خطوة بخطوة",
        "answer": "الإجابة النهائية"
      }}
    ]
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
- ⚠️ مدة الحصة 45 دقيقة فقط - يجب أن يكون مجموع time_distribution يساوي 45 دقيقة بالضبط
- ⚠️ يجب أن يحتوي الرد على كل الأقسام المذكورة أعلاه بدون استثناء (lesson_info, vocabulary, diagnostic_questions, objectives, preparation, presentation, teaching_strategies, evaluation, individual_differences, homework, time_distribution, resources, safety_notes, reflection, values_connection, comparison_tables)
- ⚠️ استخدم نفس أسماء المفاتيح بالضبط كما هي مكتوبة - لا تغيرها (مثلاً: evaluation وليس assessment)
- ⚠️ الأمثلة في presentation يجب أن تكون كائنات بها (problem, steps, answer) وليس نصوصاً مجردة
- ⚠️ summative يجب أن يكون قائمة كائنات بها (question, type, answer, explanation) وليس نصوصاً
- التزم بتنسيق JSON بالضبط
- اكتب بالعربية الفصحى
- استخدم مصطلحات علمية دقيقة مناسبة للمادة
- اجعل الأمثلة من واقع الحياة السعودية قدر الإمكان
- عند وصف الرسومات، اذكر تفاصيل كافية لرسمها
- في diagram داخل كل concept: اختر type المناسب فقط (concentration_time إذا يعرض تغير التراكيز حتى الاتزان، energy_diagram إذا يعرض مخطط الطاقة، rate_time إذا يعرض تغير معدل التفاعل، none إذا لم يكن المفهوم بحاجة لرسم بياني)
- ركّز على "{focus}" حسب طلب المعلم
- قدّم {examples} أمثلة محلولة بخطوات واضحة لكل مفهوم رئيسي
- راعِ الفروق الفردية: {weak_count} ضعاف و {excellent_count} متفوقين
- استخدم صيغة المذكر دائماً (الطلاب، الطالب، المعلم) وليس المؤنث
- في vocabulary: استخرج المصطلحات الجديدة من محتوى الدرس نفسه
- في diagnostic_questions: اطرح أسئلة تتحقق من المتطلبات القبلية المذكورة في lesson_info
- في homework.solved_examples: قدّم أمثلة محلولة من محتوى الصفحات المرفقة أو مشابهة لها
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

    # ─────────────────────────────────────────────────────────────
    # مولّد الرسوم البيانية SVG
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _diagram_wrap(title, svg_body, legend_items, note=''):
        """غلاف HTML للرسم: عنوان + SVG + أسطورة - الكل بدون عربي داخل SVG"""
        legend_html = ''.join(
            f'<span style="display:inline-flex;align-items:center;margin-left:12px;">'
            f'<span style="display:inline-block;width:18px;height:3px;background:{color};margin-left:5px;border-radius:2px;"></span>'
            f'{label}</span>'
            for label, color in legend_items
        )
        note_html = f'<div style="font-size:8pt;color:#64748b;margin-top:3px;">{note}</div>' if note else ''
        return (
            f'<div style="border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;'
            f'background:#f8fafc;margin:8px auto;max-width:340px;text-align:center;">'
            f'<div style="font-size:9.5pt;font-weight:bold;color:#1e293b;margin-bottom:4px;">{title}</div>'
            f'{svg_body}'
            f'<div style="font-size:8.5pt;color:#374151;margin-top:5px;direction:rtl;">{legend_html}</div>'
            f'{note_html}'
            f'</div>'
        )

    @staticmethod
    def _svg_concentration_time(data):
        """رسم تغير التراكيز مع الزمن حتى الاتزان"""
        title    = data.get('title', 'تغير التراكيز مع الزمن حتى الاتزان')
        r_label  = data.get('reactant_label', 'مادة متفاعلة')
        p_label  = data.get('product_label', 'مادة ناتجة')
        note     = data.get('note', '')
        W, H     = 300, 160
        px0, px1 = 30, 280
        py0, py1 = 15, 140
        eq_x     = 180
        # تراكيز الاتزان مختلفة: المتفاعل يبقى أعلى، الناتج أقل
        r_eq_y   = py0 + int((py1 - py0) * 0.50)   # المتفاعل يستقر عند منتصف المحور
        p_eq_y   = py0 + int((py1 - py0) * 0.28)   # الناتج يستقر أقل منه

        r_path = (f"M {px0},{py0+10} C {eq_x-45},{py0+10} {eq_x-12},{r_eq_y} {px1},{r_eq_y}")
        p_path = (f"M {px0},{py1-10} C {eq_x-45},{py1-10} {eq_x-12},{p_eq_y} {px1},{p_eq_y}")

        svg_body = (
            f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:{W}px;">'
            f'<rect width="{W}" height="{H}" fill="#f8fafc" rx="4" stroke="#e2e8f0" stroke-width="1"/>'
            f'<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py1}" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<line x1="{px0}" y1="{py1}" x2="{px1}" y2="{py1}" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<text x="{px0-6}" y="{py0+4}" text-anchor="end" font-size="8" fill="#64748b">[C]</text>'
            f'<text x="{px1}" y="{py1+12}" text-anchor="middle" font-size="8" fill="#64748b">t</text>'
            f'<line x1="{eq_x}" y1="{py0}" x2="{eq_x}" y2="{py1}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,3"/>'
            f'<text x="{eq_x+3}" y="{py0+9}" font-size="7" fill="#94a3b8" font-style="italic">eq</text>'
            f'<path d="{r_path}" fill="none" stroke="#dc2626" stroke-width="2.2"/>'
            f'<path d="{p_path}" fill="none" stroke="#2563eb" stroke-width="2.2"/>'
            f'</svg>'
        )
        return LessonPrepService._diagram_wrap(
            title, svg_body,
            [(r_label, '#dc2626'), (p_label, '#2563eb')],
            note
        )

    @staticmethod
    def _svg_energy_diagram(data):
        """مخطط الطاقة - طاردة أو ماصة"""
        title    = data.get('title', 'مخطط الطاقة للتفاعل')
        r_label  = data.get('reactant_label', 'متفاعلات')
        p_label  = data.get('product_label', 'نواتج')
        is_exo   = data.get('is_exothermic', True)
        note     = data.get('note', '')
        W, H     = 300, 160
        px0, px1 = 30, 280
        py0, py1 = 15, 140
        peak_x   = (px0 + px1) // 2
        peak_y   = py0 + 10
        r_y      = py0 + 45 if is_exo else py0 + 65
        p_y      = (py0 + 65) if is_exo else (py0 + 45)
        dh_color = '#16a34a' if is_exo else '#dc2626'
        dh_text  = '\u0394H &lt; 0' if is_exo else '\u0394H &gt; 0'

        curve = (f"M {px0},{r_y} "
                 f"C {px0+50},{r_y} {peak_x-35},{peak_y} {peak_x},{peak_y} "
                 f"C {peak_x+35},{peak_y} {px1-50},{p_y} {px1},{p_y}")

        svg_body = (
            f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:{W}px;">'
            f'<rect width="{W}" height="{H}" fill="#f8fafc" rx="4" stroke="#e2e8f0" stroke-width="1"/>'
            f'<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py1}" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<line x1="{px0}" y1="{py1}" x2="{px1}" y2="{py1}" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<text x="{px0-6}" y="{py0+4}" text-anchor="end" font-size="8" fill="#64748b">E</text>'
            f'<text x="{px1}" y="{py1+12}" text-anchor="middle" font-size="8" fill="#64748b">rxn</text>'
            f'<line x1="{px0}" y1="{r_y}" x2="{px0+55}" y2="{r_y}" stroke="#dc2626" stroke-width="1" stroke-dasharray="3,2"/>'
            f'<line x1="{px1-55}" y1="{p_y}" x2="{px1}" y2="{p_y}" stroke="#2563eb" stroke-width="1" stroke-dasharray="3,2"/>'
            f'<line x1="{px1-4}" y1="{min(r_y,p_y)}" x2="{px1-4}" y2="{max(r_y,p_y)}" stroke="{dh_color}" stroke-width="1" stroke-dasharray="2,2"/>'
            f'<path d="{curve}" fill="none" stroke="#7c3aed" stroke-width="2.5"/>'
            f'<text x="{peak_x}" y="{peak_y-4}" text-anchor="middle" font-size="8" fill="#7c3aed" font-weight="bold">Ea</text>'
            f'<text x="{px1-8}" y="{(r_y+p_y)//2+4}" text-anchor="end" font-size="8" fill="{dh_color}" font-weight="bold">{dh_text}</text>'
            f'</svg>'
        )
        return LessonPrepService._diagram_wrap(
            title, svg_body,
            [(r_label, '#dc2626'), (p_label, '#2563eb')],
            note
        )

    @staticmethod
    def _svg_rate_time(data):
        """رسم تغير معدل التفاعل مع الزمن حتى الاتزان"""
        title    = data.get('title', 'تغير معدل التفاعل مع الزمن')
        r_label  = data.get('reactant_label', 'معدل التفاعل الأمامي')
        p_label  = data.get('product_label', 'معدل التفاعل العكسي')
        note     = data.get('note', '')
        W, H     = 300, 160
        px0, px1 = 30, 280
        py0, py1 = 15, 140
        eq_x     = 185
        eq_y     = (py0 + py1) // 2

        fwd_path = (f"M {px0},{py0+12} C {eq_x-55},{py0+12} {eq_x-12},{eq_y} {px1},{eq_y}")
        rev_path = (f"M {px0},{py1-12} C {eq_x-55},{py1-12} {eq_x-12},{eq_y} {px1},{eq_y}")

        svg_body = (
            f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:{W}px;">'
            f'<rect width="{W}" height="{H}" fill="#f8fafc" rx="4" stroke="#e2e8f0" stroke-width="1"/>'
            f'<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py1}" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<line x1="{px0}" y1="{py1}" x2="{px1}" y2="{py1}" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<text x="{px0-6}" y="{py0+4}" text-anchor="end" font-size="8" fill="#64748b">r</text>'
            f'<text x="{px1}" y="{py1+12}" text-anchor="middle" font-size="8" fill="#64748b">t</text>'
            f'<line x1="{eq_x}" y1="{py0}" x2="{eq_x}" y2="{py1}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,3"/>'
            f'<text x="{eq_x+3}" y="{py0+9}" font-size="7" fill="#94a3b8" font-style="italic">eq</text>'
            f'<path d="{fwd_path}" fill="none" stroke="#dc2626" stroke-width="2.2"/>'
            f'<text x="{px0+5}" y="{py0+26}" font-size="8" fill="#dc2626">r1</text>'
            f'<path d="{rev_path}" fill="none" stroke="#2563eb" stroke-width="2.2"/>'
            f'<text x="{px0+5}" y="{py1-14}" font-size="8" fill="#2563eb">r2</text>'
            f'</svg>'
        )
        return LessonPrepService._diagram_wrap(
            title, svg_body,
            [(r_label, '#dc2626'), (p_label, '#2563eb')],
            note
        )

    @staticmethod
    def _generate_diagram_svg(diagram):
        """توليد SVG للرسم البياني بحسب النوع"""
        if not diagram or not isinstance(diagram, dict):
            return None
        dtype = diagram.get('type', 'none')
        if dtype == 'concentration_time':
            return LessonPrepService._svg_concentration_time(diagram)
        elif dtype == 'energy_diagram':
            return LessonPrepService._svg_energy_diagram(diagram)
        elif dtype == 'rate_time':
            return LessonPrepService._svg_rate_time(diagram)
        return None

    @staticmethod
    def _inject_diagrams(plan_data):
        """معالجة plan_data وإضافة SVG لكل diagram موجود"""
        # درس واحد
        if 'diagram' in plan_data:
            svg = LessonPrepService._generate_diagram_svg(plan_data['diagram'])
            if svg:
                plan_data['diagram']['svg'] = svg

        # presentation → main_concepts (درس واحد)
        pres = plan_data.get('presentation', {})
        for c in pres.get('main_concepts', []):
            if isinstance(c, dict) and 'diagram' in c:
                svg = LessonPrepService._generate_diagram_svg(c['diagram'])
                if svg:
                    c['diagram']['svg'] = svg

        # توزيع الوحدة (per period)
        for p in plan_data.get('periods', []):
            if not isinstance(p, dict):
                continue
            if 'diagram' in p:
                svg = LessonPrepService._generate_diagram_svg(p['diagram'])
                if svg:
                    p['diagram']['svg'] = svg
            for c in p.get('main_concepts', []):
                if isinstance(c, dict) and 'diagram' in c:
                    svg = LessonPrepService._generate_diagram_svg(c['diagram'])
                    if svg:
                        c['diagram']['svg'] = svg
        return plan_data

    def _generate_pdf(self, plan_data, lesson_name, unit_name, course_name, show_answers=True):
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
                'show_answers': show_answers,
            }

            html_string = render_template('lesson_prep/lesson_plan.html', **context)
            base_url = os.path.join(os.getcwd(), 'src', 'static')
            pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf()

            logger.info(f"تم توليد PDF بـ WeasyPrint ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"خطأ في توليد PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_unit_pdf(self, plan_data, unit_name, course_name, show_answers=True):
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
                'show_answers': show_answers,
            }

            html_string = render_template('lesson_prep/unit_distribution.html', **context)
            base_url = os.path.join(os.getcwd(), 'src', 'static')
            pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf()

            logger.info(f"تم توليد PDF الوحدة بـ WeasyPrint ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"خطأ في توليد PDF الوحدة: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_single_period_prompt(self, period_num, total_periods, lesson_name, title,
                                     course_name, unit_name, all_lessons_text):
        """بناء برومت لحصة واحدة فقط"""
        return f"""أنت خبير تربوي متخصص في تحضير دروس الكيمياء للمرحلة الثانوية في السعودية.

## المقرر: {course_name}
## الوحدة: {unit_name}
## دروس الوحدة: {all_lessons_text}
## الحصة رقم: {period_num} من {total_periods}
## الدرس: {lesson_name}
## عنوان الحصة: {title}

## المطلوب
أعد تحضيراً تفصيلياً كاملاً لهذه الحصة الواحدة فقط.

أعد الرد بصيغة JSON لحصة واحدة فقط:
```json
{{
  "period_number": {period_num},
  "lesson_name": "{lesson_name}",
  "title": "{title}",
  "objectives": {{
    "cognitive": ["أهداف معرفية - أن يعرف الطالب..."],
    "skill": ["أهداف مهارية"],
    "emotional": ["أهداف وجدانية"]
  }},
  "vocabulary": [
    {{
      "term": "المصطلح الجديد",
      "definition": "تعريف المصطلح بأسلوب واضح ومبسط"
    }}
  ],
  "diagnostic_questions": [
    {{
      "question": "سؤال للتحقق من المتطلبات القبلية",
      "answer": "الإجابة النموذجية",
      "purpose": "الهدف من السؤال"
    }}
  ],
  "preparation": {{
    "introduction": "سؤال أو موقف تحفيزي للتهيئة",
    "introduction_answer": "الإجابة المتوقعة من الطالب على سؤال التهيئة",
    "introduction_activity": "نشاط تفاعلي للتهيئة",
    "connection_to_previous": "ربط بالحصة السابقة"
  }},
  "main_concepts": [
    {{
      "concept": "المفهوم الرئيسي",
      "explanation": "شرح مفصّل",
      "teaching_method": "استراتيجية التدريس المستخدمة",
      "examples": [
        {{
          "problem": "نص المثال أو المسألة",
          "steps": ["الخطوة الأولى", "الخطوة الثانية"],
          "answer": "الإجابة النهائية مع التفسير"
        }}
      ],
      "student_activity": "نشاط الطلاب",
      "diagram": {{
        "type": "concentration_time أو energy_diagram أو rate_time أو none",
        "title": "عنوان الرسم البياني",
        "reactant_label": "اسم المتفاعل",
        "product_label": "اسم الناتج",
        "is_exothermic": true,
        "note": "ملاحظة أسفل الرسم"
      }}
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
  "evaluation": {{
    "formative": [
      {{
        "question": "سؤال تقويمي",
        "answer": "الإجابة",
        "type": "نوع السؤال (اختياري/مقالي/صح وخطأ)",
        "bloom_level": "مستوى بلوم"
      }}
    ],
    "summative": [
      {{
        "question": "سؤال التقويم الختامي",
        "type": "نوع السؤال (اختياري/مقالي/صح وخطأ/إكمال)",
        "answer": "الإجابة النموذجية الكاملة",
        "explanation": "توضيح إضافي أو سبب صحة الإجابة"
      }}
    ],
    "enrichment": ["أسئلة إثرائية للمتفوقين"],
    "remedial": ["أنشطة علاجية للضعاف"]
  }},
  "individual_differences": {{
    "gifted_activities": ["نشاط للمتفوقين"],
    "weak_support": ["دعم الضعاف"],
    "average_activities": ["أنشطة للمستوى المتوسط"]
  }},
  "homework": {{
    "main": ["الواجب الأساسي"],
    "optional": ["واجب اختياري إثرائي"],
    "solved_examples": [
      {{
        "question": "مسألة من محتوى الحصة",
        "solution": "الحل التفصيلي خطوة بخطوة",
        "answer": "الإجابة النهائية"
      }}
    ]
  }},
  "time_distribution": [
    {{
      "activity": "النشاط",
      "duration_minutes": 5,
      "notes": "ملاحظات"
    }}
  ],
  "resources": ["الوسائل التعليمية"],
  "safety_notes": ["ملاحظات السلامة إن وجدت تجارب"],
  "values_connection": {{
    "religious": "ربط ديني بآية أو حديث",
    "national": "ربط وطني (رؤية 2030)",
    "life": "ربط بالحياة اليومية"
  }},
  "reflection": {{
    "strengths": "نقاط القوة المتوقعة",
    "improvements": "نقاط التحسين",
    "notes": "ملاحظات إضافية"
  }}
}}
```

## تنبيهات
- ⚠️ مدة الحصة 45 دقيقة فقط - يجب أن يكون مجموع time_distribution يساوي 45 دقيقة بالضبط
- ⚠️ الرد يجب أن يكون JSON لحصة واحدة فقط (ليس قائمة)
- ⚠️ الأمثلة في main_concepts يجب أن تكون كائنات بها (problem, steps, answer) وليس نصوصاً مجردة
- ⚠️ summative يجب أن يكون قائمة كائنات بها (question, type, answer, explanation)
- التزم بتنسيق JSON بالضبط
- اكتب بالعربية الفصحى والمذكر (الطالب، الطلاب)
- في vocabulary: استخرج المصطلحات الجديدة من محتوى هذه الحصة تحديداً
- في diagnostic_questions: اطرح أسئلة تتحقق من المتطلبات القبلية لهذه الحصة
- في diagram داخل كل concept: اختر type المناسب (concentration_time أو energy_diagram أو rate_time أو none)"""

    def generate_unit_distribution(self, plan_id):
        """توليد توزيع وحدة كاملة - حصة حصة لتجنب حد الـ tokens"""
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

            total_periods = plan.student_count or 12
            lessons = Lesson.query.filter_by(unit_id=unit.id).order_by(Lesson.order_num).all()
            lessons_text = "\n".join([f"- {l.name}" for l in lessons])
            course_name = course.name if course else ''

            # ── الخطوة 1: توليد خطة الحصص (عناوين وتوزيع فقط) ──
            plan_prompt = f"""أنت خبير تربوي. وزّع الوحدة التالية على {total_periods} حصة.

## المقرر: {course_name}
## الوحدة: {unit.name}
## الدروس:
{lessons_text}

أعد JSON بسيطاً فقط يحدد عنوان كل حصة والدرس المرتبط بها:
```json
{{
  "periods_plan": [
    {{"period_number": 1, "lesson_name": "اسم الدرس", "title": "عنوان الحصة"}},
    {{"period_number": 2, "lesson_name": "اسم الدرس", "title": "عنوان الحصة"}}
  ]
}}
```
- خصص حصة أخيرة للمراجعة والتقويم
- وزّع الدروس بالتساوي"""

            logger.info(f"الوحدة #{plan_id}: توليد خطة الحصص...")
            plan_text, _ = self._call_ai(plan_prompt, label=f"خطة وحدة #{plan_id}",
                                          plan_id=plan_id, teacher_id=plan.teacher_id, operation_type='unit_dist')
            periods_plan_data = self._extract_json(plan_text)
            if not periods_plan_data:
                periods_plan_data = self._aggressive_json_fix(plan_text)

            # بناء قائمة الحصص من الخطة أو توليد افتراضي
            if periods_plan_data and 'periods_plan' in periods_plan_data:
                periods_plan = periods_plan_data['periods_plan']
            else:
                # خطة افتراضية إذا فشل التوليد
                lessons_cycle = lessons if lessons else [type('L', (), {'name': unit.name})()]
                periods_plan = []
                for i in range(total_periods):
                    l = lessons_cycle[i % len(lessons_cycle)]
                    periods_plan.append({
                        'period_number': i + 1,
                        'lesson_name': l.name,
                        'title': f"الحصة {i + 1}: {l.name}",
                    })

            # ── الخطوة 2: توليد كل حصة بشكل منفصل ──
            generated_periods = []
            for p_info in periods_plan:
                period_num  = p_info.get('period_number', len(generated_periods) + 1)
                lesson_name = p_info.get('lesson_name', '')
                title       = p_info.get('title', f"الحصة {period_num}")

                logger.info(f"الوحدة #{plan_id}: توليد الحصة {period_num}/{total_periods} - {title}")

                period_prompt = self._build_single_period_prompt(
                    period_num, total_periods, lesson_name, title,
                    course_name, unit.name, lessons_text
                )

                try:
                    period_text, _ = self._call_ai(
                        period_prompt,
                        label=f"وحدة #{plan_id} حصة {period_num}",
                        plan_id=plan_id,
                        teacher_id=plan.teacher_id,
                        operation_type='unit_dist'
                    )
                    period_data = self._extract_json(period_text)
                    if not period_data:
                        period_data = self._aggressive_json_fix(period_text)
                    if period_data:
                        # تأكد من وجود period_number
                        period_data['period_number'] = period_num
                        if 'lesson_name' not in period_data:
                            period_data['lesson_name'] = lesson_name
                        generated_periods.append(period_data)
                    else:
                        # حفظ نص خام للحصة الفاشلة
                        generated_periods.append({
                            'period_number': period_num,
                            'lesson_name': lesson_name,
                            'title': title,
                            'raw_text': period_text[:1000],
                        })
                        logger.warning(f"الوحدة #{plan_id}: فشل تحليل الحصة {period_num}")
                except Exception as pe:
                    logger.warning(f"الوحدة #{plan_id}: خطأ في الحصة {period_num}: {pe}")
                    generated_periods.append({
                        'period_number': period_num,
                        'lesson_name': lesson_name,
                        'title': title,
                        'error': str(pe),
                    })

            plan_data = {
                'unit_name': unit.name,
                'course_name': course_name,
                'total_periods': total_periods,
                'periods': generated_periods,
            }

            # حقن الرسوم البيانية SVG
            plan_data = LessonPrepService._inject_diagrams(plan_data)

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
                    images = self._extract_pages_as_images(pdf_source, 1, 2, scale=0.5)
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
