from flask import render_template
from weasyprint import HTML
import io
import base64
from docx import Document # للحفاظ على دعم الوورد

class ExamGenerator:
    def __init__(self, header_settings=None, logo_path=None):
        self.header_settings = header_settings or {}
        self.logo_path = logo_path or '/home/ubuntu/ministry_logo.png'
    
    def _get_logo_base64(self):
        try:
            with open(self.logo_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        except:
            return None
            
    def _prepare_context(self, questions, exam_title, show_answers, **kwargs):
        def get_val(key, default):
            return kwargs.get(key) or self.header_settings.get(key) or default

        context = {
            'exam_title': exam_title,
            'country': get_val('country', 'المملكة العربية السعودية'),
            'ministry': get_val('ministry', 'وزارة التعليم'),
            'education_department': get_val('education_department', ''),
            'school_name': get_val('school_name', ''),
            'subject': get_val('subject', ''),
            'time': get_val('time', ''),
            'grade': get_val('grade', ''),
            'total_score': get_val('total_score', 30),
            'checker_name': get_val('checker_name', ''),
            'reviewer_name': get_val('reviewer_name', ''),
            'exam_date': get_val('exam_date', ''),
            'teacher_name': get_val('teacher_name', ''),
            'academic_year': get_val('academic_year', ''),
            'exam_type': get_val('exam_type', ''),
            'semester': get_val('semester', ''),
            'questions': [],
            'show_answers': show_answers,
            'logo': self._get_logo_base64(),
            # إعدادات التنسيق
            'font_size': kwargs.get('font_size', 14),
            'image_size': kwargs.get('image_size', 100),
            'columns': kwargs.get('columns', 2),
            'spacing': kwargs.get('spacing', 'normal'),
            'options_layout': kwargs.get('options_layout', 'vertical'),
            'include_qr': kwargs.get('include_qr', True),
            # إعدادات الكليشه
            'header_size': get_val('header_size', 'medium'),
            'show_logo': get_val('show_logo', True),
            'logo_size': get_val('logo_size', 'medium'),
            'show_grades_table': get_val('show_grades_table', True),
            'show_extra_grade': get_val('show_extra_grade', False),
            'show_student_name': get_val('show_student_name', True),
            'show_student_class': get_val('show_student_class', True),
            'show_student_seat': get_val('show_student_seat', False),
            'show_student_signature': get_val('show_student_signature', False),
        }
        
        letters = ['a', 'b', 'c', 'd'] 
        for question in questions:
            formatted_q = {
                'question_text': question.get('question_text', ''),
                'points': question.get('points', 1),
                'options': [],
                'correct_answer': ''
            }
            options = question.get('options', [])
            for idx, option in enumerate(options):
                letter = letters[idx] if idx < len(letters) else str(idx + 1)
                formatted_q['options'].append({
                    'letter': letter,
                    'option_text': option.get('option_text', ''),
                })
                if option.get('is_correct') or option.get('option_id') == question.get('correct_option_id'):
                    formatted_q['correct_answer'] = letter
            context['questions'].append(formatted_q)
        return context

    def generate_html(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        context = self._prepare_context(questions, exam_title, show_answers, **kwargs)
        # هنا التغيير الجذري: استخدام القالب الموحد
        return render_template('question/exam_paper_layout_with_barcode.html', **context)
    
    def generate_pdf(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        html_obj = HTML(string=html_content)
        return html_obj.write_pdf()

    def generate_word(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        # اترك كود الوورد القديم هنا كما هو (يمكنك نسخه من الملف السابق إذا كنت تحتاجه)
        return b"" 

def generate_exam(questions, exam_title="نموذج الاختبار", output_format='word', show_answers=False, header_settings=None, logo_path=None, **kwargs):
    generator = ExamGenerator(header_settings, logo_path)
    if output_format == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    else:
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)