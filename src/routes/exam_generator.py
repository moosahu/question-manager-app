from flask import render_template, current_app
from weasyprint import HTML
import io
import os
import base64
import threading
from docx import Document # للحفاظ على دعم الوورد

# ── Playwright browser singleton (per-process) ──────────────────────────────
_pw_instance = None
_pw_browser  = None
_pw_lock     = threading.Lock()

def _get_browser():
    global _pw_instance, _pw_browser
    with _pw_lock:
        try:
            if _pw_browser and _pw_browser.is_connected():
                return _pw_browser
        except Exception:
            pass
        try:
            if _pw_instance:
                _pw_instance.stop()
        except Exception:
            pass
        from playwright.sync_api import sync_playwright
        _pw_instance = sync_playwright().start()
        _pw_browser  = _pw_instance.chromium.launch(args=[
            '--no-sandbox', '--disable-setuid-sandbox',
            '--disable-dev-shm-usage', '--disable-gpu',
        ])
        return _pw_browser

_logo_cache = None   # cache في الذاكرة — يُحمَّل مرة واحدة فقط
_font_cache  = {}    # {filename: 'data:font/truetype;base64,...'}

def _font_base64(filename):
    """يقرأ ملف الخط ويحوّله base64 مع cache في الذاكرة"""
    if filename in _font_cache:
        return _font_cache[filename]
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts', filename)
    )
    try:
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
            _font_cache[filename] = f'data:font/truetype;base64,{data}'
    except Exception:
        _font_cache[filename] = ''
    return _font_cache[filename]

def _default_logo_base64():
    """يحاول تحميل شعار الوزارة من مسارات متعددة (مع cache)"""
    global _logo_cache
    if _logo_cache is not None:
        return _logo_cache
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'logo.png'),
        '/home/ubuntu/ministry_logo.png',
    ]
    for path in candidates:
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                    _logo_cache = f'data:image/png;base64,{data}'
                    return _logo_cache
        except Exception:
            pass
    _logo_cache = ''  # لا يوجد شعار — لا نعيد المحاولة
    return None

_FONT_FILES = {
    'traditional':   ('TraditionalArabic-Regular.ttf', None),
    'amiri':         ('Amiri-Regular.ttf',              'Amiri-Bold.ttf'),
    'cairo':         ('Cairo-Regular.ttf',              None),
    'tajawal':       ('Tajawal-Regular.ttf',            None),
    'tahoma':        ('Tahoma-Regular.ttf',             None),
    'scheherazade':  ('ScheherazadeNew-Regular.ttf',    None),
    'noto':          ('NotoNaskhArabic-Regular.ttf',    None),
}

def _get_font_data(family):
    regular, _ = _FONT_FILES.get(family, _FONT_FILES['traditional'])
    return _font_base64(regular)

def _get_font_data_bold(family):
    _, bold = _FONT_FILES.get(family, _FONT_FILES['traditional'])
    return _font_base64(bold) if bold else ''


class ExamGenerator:
    def __init__(self, header_settings=None, logo_path=None):
        self.header_settings = header_settings or {}
        self.logo_path = logo_path  # اختياري، يُفضّل _default_logo_base64

    def _get_logo_base64(self):
        # إذا مُرِّر مسار صريح، استخدمه
        if self.logo_path:
            try:
                with open(self.logo_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                    return f'data:image/png;base64,{data}'
            except Exception:
                pass
        return _default_logo_base64()

    def _prepare_context(self, questions, exam_title, show_answers, **kwargs):
        def get_val(key, default):
            return kwargs.get(key) or self.header_settings.get(key) or default

        logo_b64 = self._get_logo_base64()

        # header_format dict — بنفس البنية التي يتوقعها القالب
        header_format = {
            'exam_type':          get_val('exam_type', 'نهاية'),
            'semester':           get_val('semester', 'الأول'),
            'academic_year':      get_val('academic_year', '1447هـ'),
            'header_size':        get_val('header_size', 'medium'),
            'show_logo':          get_val('show_logo', True),
            'logo_size':          get_val('logo_size', 'medium'),
            'show_grades_table':  get_val('show_grades_table', True),
            'show_extra_grade':   get_val('show_extra_grade', False),
            'show_student_name':  get_val('show_student_name', True),
            'show_student_class': get_val('show_student_class', True),
            'show_student_seat':  get_val('show_student_seat', False),
            'show_student_signature': get_val('show_student_signature', False),
            'qr_size':            get_val('qr_size', 'medium'),
            'name_line_length':   get_val('name_line_length', 'medium'),
        }

        context = {
            'exam_title':          exam_title,
            'country':             get_val('country', 'المملكة العربية السعودية'),
            'ministry':            get_val('ministry', 'وزارة التعليم'),
            'education_department':get_val('education_department', ''),
            'school_name':         get_val('school_name', ''),
            'subject':             get_val('subject', ''),
            'time':                get_val('time', ''),
            'grade':               get_val('grade', ''),
            'total_score':         get_val('total_score', 30),
            'checker_name':        get_val('checker_name', '') or get_val('teacher_name', ''),
            'reviewer_name':       get_val('reviewer_name', ''),
            'exam_date':           get_val('exam_date', ''),
            'teacher_name':        get_val('teacher_name', ''),
            'academic_year':       get_val('academic_year', '1447هـ'),
            'questions':           [],
            'show_answers':        show_answers,
            'logo_base64':         logo_b64,   # اسم المتغير الصحيح للقالب
            'header_format':       header_format,
            'qr_code':             kwargs.get('qr_code'),
            'model_letter':        kwargs.get('model_letter', ''),
            # إعدادات التنسيق (تُقرأ مباشرة من القالب)
            'font_size':           kwargs.get('font_size', 14),
            'image_size':          kwargs.get('image_size', 70),
            'columns':             kwargs.get('columns', 2),
            'spacing':             kwargs.get('spacing', 'normal'),
            'options_layout':      kwargs.get('options_layout', 'vertical'),
            'include_qr':          kwargs.get('include_qr', True),
            'font_family':         kwargs.get('font_family', 'traditional'),
        }

        arabic_letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        for question in questions:
            formatted_q = {
                'question_text': question.get('question_text', ''),
                'points':        question.get('points', 1),
                'image_url':     question.get('image_url'),
                'options':       [],
                'correct_answer': '',
                'question_type': question.get('question_type', 'mcq'),
            }
            options = question.get('options', [])
            for idx, option in enumerate(options):
                letter = arabic_letters[idx] if idx < len(arabic_letters) else str(idx + 1)
                is_correct = (
                    option.get('is_correct') or
                    option.get('option_id') == question.get('correct_option_id')
                )
                formatted_q['options'].append({
                    'letter':      letter,
                    'option_text': option.get('option_text', ''),
                    'image_url':   option.get('image_url'),
                    'is_correct':  is_correct,
                })
                if is_correct and show_answers:
                    # لسؤال صح/خطأ نعرض النص نفسه ("صح"/"خطأ") بدل الحرف — أوضح بمفتاح الإجابة
                    formatted_q['correct_answer'] = (
                        option.get('option_text', letter)
                        if formatted_q['question_type'] == 'true_false'
                        else letter
                    )
            context['questions'].append(formatted_q)
        return context

    def generate_html(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        context = self._prepare_context(questions, exam_title, show_answers, **kwargs)
        return render_template('question/exam_paper_layout_with_barcode.html', **context)

    def generate_pdf(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        base_url = f"file://{src_dir}/"
        # Playwright أسرع بـ 5-8x — WeasyPrint احتياطي إذا فشل
        try:
            return self._pdf_playwright(html_content, base_url)
        except Exception as e:
            current_app.logger.warning(f"Playwright failed, fallback to WeasyPrint: {e}")
            return HTML(string=html_content, base_url=base_url).write_pdf()

    def _pdf_playwright(self, html_content, base_url):
        browser = _get_browser()
        ctx  = browser.new_context()
        page = ctx.new_page()
        page.set_content(html_content, base_url=base_url, wait_until='load')
        pdf  = page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '10mm', 'right': '8mm', 'bottom': '15mm', 'left': '8mm'},
        )
        ctx.close()
        return pdf

    def generate_word(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        return b""

def generate_exam(questions, exam_title="نموذج الاختبار", output_format='word', show_answers=False, header_settings=None, logo_path=None, **kwargs):
    generator = ExamGenerator(header_settings, logo_path)
    if output_format == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    else:
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)


