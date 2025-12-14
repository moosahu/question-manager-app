"""
نظام موحد لتوليد ملفات PDF و Word من ملف HTML واحد
"""

from jinja2 import Template
from datetime import datetime
import io
from weasyprint import HTML, CSS
from html2docx import html2docx


class ExamGenerator:
    """فئة موحدة لتوليد الاختبارات بصيغ مختلفة"""
    
    def __init__(self, header_settings=None):
        """
        تهيئة منشئ الاختبارات
        
        Args:
            header_settings: قاموس يحتوي على إعدادات الكليشة
        """
        self.header_settings = header_settings or {}
        self.html_template = self._get_html_template()
    
    def _get_html_template(self):
        """الحصول على قالب HTML"""
        return """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ exam_title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            direction: rtl;
            line-height: 1.6;
            background-color: #fff;
            color: #333;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* رأس الاختبار */
        .header {
            border: 2px solid #000;
            padding: 20px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .header-top {
            display: table;
            width: 100%;
            margin-bottom: 15px;
        }
        
        .header-cell {
            display: table-cell;
            width: 33.33%;
            text-align: center;
            padding: 10px;
            border: 1px solid #000;
        }
        
        .header-cell-right {
            text-align: right;
        }
        
        .header-cell-left {
            text-align: left;
        }
        
        .header-title {
            font-size: 18px;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .header-info {
            font-size: 12px;
            margin: 5px 0;
        }
        
        .exam-title {
            font-size: 16px;
            font-weight: bold;
            margin: 15px 0;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }
        
        .header-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        .header-table td {
            border: 1px solid #000;
            padding: 8px;
            text-align: right;
        }
        
        .header-table .label {
            font-weight: bold;
            background-color: #f5f5f5;
            width: 30%;
        }
        
        .header-table .value {
            width: 70%;
        }
        
        /* الأسئلة */
        .questions {
            margin-top: 20px;
        }
        
        .question {
            margin-bottom: 20px;
            page-break-inside: avoid;
        }
        
        .question-number {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .question-text {
            margin-bottom: 10px;
            line-height: 1.8;
        }
        
        .options {
            margin-right: 20px;
        }
        
        .option {
            margin-bottom: 8px;
            line-height: 1.6;
        }
        
        .option-letter {
            display: inline-block;
            width: 25px;
            text-align: center;
            font-weight: bold;
        }
        
        /* جدول الإجابات */
        .answer-key {
            margin-top: 30px;
            border-top: 2px solid #000;
            padding-top: 20px;
        }
        
        .answer-key-title {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .answer-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .answer-table th,
        .answer-table td {
            border: 1px solid #000;
            padding: 8px;
            text-align: center;
        }
        
        .answer-table th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        
        /* خط فاصل */
        hr {
            border: none;
            border-top: 1px solid #000;
            margin: 15px 0;
        }
        
        @media print {
            body {
                margin: 0;
                padding: 0;
            }
            .container {
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- رأس الاختبار -->
        <div class="header">
            <!-- الصف الأول: الإدارة - العنوان - المادة -->
            <table class="header-table" style="margin-bottom: 10px;">
                <tr>
                    <td class="header-cell header-cell-right">
                        <div class="header-info">{{ education_department }}</div>
                    </td>
                    <td class="header-cell">
                        <div class="header-title">{{ country }}</div>
                    </td>
                    <td class="header-cell header-cell-left">
                        <div class="header-info">{{ subject }}</div>
                    </td>
                </tr>
            </table>
            
            <!-- الصف الثاني: المدرسة - الوزارة - الزمن -->
            <table class="header-table" style="margin-bottom: 10px;">
                <tr>
                    <td class="header-cell header-cell-right">
                        <div class="header-info">{{ school_name }}</div>
                    </td>
                    <td class="header-cell">
                        <div class="header-info">{{ ministry }}</div>
                    </td>
                    <td class="header-cell header-cell-left">
                        <div class="header-info">الزمن: {{ time }}</div>
                    </td>
                </tr>
            </table>
            
            <!-- عنوان الاختبار -->
            <div class="exam-title">{{ exam_title }}</div>
            
            <!-- معلومات الاختبار -->
            <table class="header-table">
                <tr>
                    <td class="label">المستوى:</td>
                    <td class="value">{{ grade }}</td>
                </tr>
                <tr>
                    <td class="label">الدرجة الكلية:</td>
                    <td class="value">{{ total_score }}</td>
                </tr>
                <tr>
                    <td class="label">التاريخ:</td>
                    <td class="value">{{ exam_date }}</td>
                </tr>
                <tr>
                    <td class="label">المصحح:</td>
                    <td class="value">{{ checker_name }}</td>
                </tr>
            </table>
        </div>
        
        <!-- الأسئلة -->
        <div class="questions">
            {% for question in questions %}
            <div class="question">
                <div class="question-number">السؤال {{ loop.index }}: ({{ question.points }} درجات)</div>
                <div class="question-text">{{ question.question_text }}</div>
                <div class="options">
                    {% for option in question.options %}
                    <div class="option">
                        <span class="option-letter">{{ option.letter }}</span>
                        {{ option.option_text }}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        
        <!-- جدول الإجابات -->
        {% if show_answers %}
        <div class="answer-key">
            <div class="answer-key-title">مفتاح الإجابات</div>
            <table class="answer-table">
                <tr>
                    {% for i in range(1, questions|length + 1) %}
                    <th>{{ i }}</th>
                    {% endfor %}
                </tr>
                <tr>
                    {% for question in questions %}
                    <td>{{ question.correct_answer }}</td>
                    {% endfor %}
                </tr>
            </table>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""
    
    def generate_html(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """
        توليد HTML من البيانات
        
        Args:
            questions: قائمة الأسئلة
            exam_title: عنوان الاختبار
            show_answers: هل تتضمن الإجابات
            **kwargs: معاملات إضافية (country, ministry, إلخ)
        
        Returns:
            HTML string
        """
        # تحضير بيانات الكليشة
        context = {
            'exam_title': exam_title,
            'country': kwargs.get('country', self.header_settings.get('country', 'المملكة العربية السعودية')),
            'ministry': kwargs.get('ministry', self.header_settings.get('ministry', 'وزارة التعليم')),
            'education_department': kwargs.get('education_department', self.header_settings.get('education_department', '')),
            'school_name': kwargs.get('school_name', self.header_settings.get('school_name', '')),
            'subject': kwargs.get('subject', self.header_settings.get('subject', '')),
            'time': kwargs.get('time', self.header_settings.get('time', '')),
            'grade': kwargs.get('grade', self.header_settings.get('grade', '')),
            'total_score': kwargs.get('total_score', self.header_settings.get('total_score', 30)),
            'checker_name': kwargs.get('checker_name', self.header_settings.get('checker_name', '')),
            'reviewer_name': kwargs.get('reviewer_name', self.header_settings.get('reviewer_name', '')),
            'exam_date': kwargs.get('exam_date', self.header_settings.get('exam_date', datetime.now().strftime('%d/%m/%Y'))),
            'questions': questions,
            'show_answers': show_answers
        }
        
        # تحويل الأسئلة إلى صيغة صحيحة
        formatted_questions = []
        letters = ['أ', 'ب', 'ج', 'د']
        
        for question in questions:
            formatted_q = {
                'question_text': question.get('question_text', ''),
                'points': question.get('points', 1),
                'options': [],
                'correct_answer': ''
            }
            
            options = question.get('options', [])
            for idx, option in enumerate(options):
                formatted_q['options'].append({
                    'letter': letters[idx] if idx < len(letters) else str(idx + 1),
                    'option_text': option.get('option_text', '')
                })
                
                if option.get('is_correct') or option.get('option_id') == question.get('correct_option_id'):
                    formatted_q['correct_answer'] = letters[idx] if idx < len(letters) else str(idx + 1)
            
            formatted_questions.append(formatted_q)
        
        context['questions'] = formatted_questions
        
        # توليد HTML
        template = Template(self.html_template)
        return template.render(**context)
    
    def generate_pdf(self, questions, exam_title="نموذج الاختبار", 
                    show_answers=False, **kwargs):
        """
        توليد PDF من البيانات
        
        Args:
            questions: قائمة الأسئلة
            exam_title: عنوان الاختبار
            show_answers: هل تتضمن الإجابات
            **kwargs: معاملات إضافية
        
        Returns:
            PDF bytes
        """
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        
        # تحويل HTML إلى PDF
        html_obj = HTML(string=html_content)
        pdf_bytes = html_obj.write_pdf()
        
        return pdf_bytes
    
    def generate_word(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """
        توليد Word من البيانات
        
        Args:
            questions: قائمة الأسئلة
            exam_title: عنوان الاختبار
            show_answers: هل تتضمن الإجابات
            **kwargs: معاملات إضافية
        
        Returns:
            Word bytes
        """
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        
        # تحويل HTML إلى Word
        docx_bytes = html2docx(html_content, title=exam_title)
        
        return docx_bytes


# دالة مساعدة للاستخدام السريع
def generate_exam(questions, exam_title="نموذج الاختبار", 
                 output_format='pdf', show_answers=False, 
                 header_settings=None, **kwargs):
    """
    دالة مساعدة لتوليد الاختبارات
    
    Args:
        questions: قائمة الأسئلة
        exam_title: عنوان الاختبار
        output_format: صيغة الإخراج ('pdf' أو 'word')
        show_answers: هل تتضمن الإجابات
        header_settings: إعدادات الكليشة
        **kwargs: معاملات إضافية
    
    Returns:
        bytes (PDF أو Word)
    """
    generator = ExamGenerator(header_settings)
    
    if output_format.lower() == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    elif output_format.lower() == 'word':
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)
    else:
        raise ValueError(f"صيغة غير مدعومة: {output_format}")
