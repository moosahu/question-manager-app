from flask import render_template, current_app
from weasyprint import HTML
import io
import os
import base64
from docx import Document # للحفاظ على دعم الوورد

_logo_cache = None  # cache في الذاكرة — يُحمَّل مرة واحدة فقط

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
            'image_size':          kwargs.get('image_size', 100),
            'columns':             kwargs.get('columns', 2),
            'spacing':             kwargs.get('spacing', 'normal'),
            'options_layout':      kwargs.get('options_layout', 'vertical'),
            'include_qr':          kwargs.get('include_qr', True),
            'font_family':         kwargs.get('font_family', 'amiri'),
        }

        arabic_letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
        for question in questions:
            formatted_q = {
                'question_text': question.get('question_text', ''),
                'points':        question.get('points', 1),
                'image_url':     question.get('image_url'),
                'options':       [],
                'correct_answer': ''
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
                    formatted_q['correct_answer'] = letter
            context['questions'].append(formatted_q)
        return context

    def generate_html(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        context = self._prepare_context(questions, exam_title, show_answers, **kwargs)
        return render_template('question/exam_paper_layout_with_barcode.html', **context)

    def generate_pdf(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        # base_url لحل مسارات الخطوط والصور النسبية
        try:
            from flask import request as _req
            base_url = _req.url_root
        except Exception:
            base_url = None
        html_obj = HTML(string=html_content, base_url=base_url)
        return html_obj.write_pdf()

    def generate_word(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        return b""

def generate_exam(questions, exam_title="نموذج الاختبار", output_format='word', show_answers=False, header_settings=None, logo_path=None, **kwargs):
    generator = ExamGenerator(header_settings, logo_path)
    if output_format == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    else:
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)


