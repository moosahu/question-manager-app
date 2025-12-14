"""
نظام موحد لتوليد ملفات PDF و Word من نفس قالب HTML
- نفس HTML لكلا الملفين
- PDF من HTML باستخدام weasyprint
- Word من HTML باستخدام html2docx
- نتيجة: ملفان متطابقان تماماً
"""

from jinja2 import Template
from datetime import datetime
import io
from weasyprint import HTML
from html2docx import HTML2Docx


class UnifiedExamGenerator:
    """فئة موحدة لتوليد الاختبارات من نفس قالب HTML"""
    
    def __init__(self, header_settings=None):
        """
        تهيئة منشئ الاختبارات
        
        Args:
            header_settings: قاموس يحتوي على إعدادات الكليشة
        """
        self.header_settings = header_settings or {}
        self.html_template = self._get_html_template()
    
    def _get_html_template(self):
        """الحصول على قالب HTML الموحد"""
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
        
        .header-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
        }
        
        .header-table td {
            border: 1px solid #000;
            padding: 8px;
            text-align: right;
            font-size: 12px;
        }
        
        .header-table .label {
            font-weight: bold;
            background-color: #f5f5f5;
            width: 30%;
        }
        
        .header-table .value {
            width: 70%;
        }
        
        .exam-title {
            font-size: 16px;
            font-weight: bold;
            margin: 15px 0;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }
        
        /* الأسئلة */
        .questions {
            margin-top: 20px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .question {
            margin-bottom: 20px;
            page-break-inside: avoid;
            border: 1px solid #ccc;
            padding: 15px;
            border-radius: 5px;
            background-color: #f9f9f9;
        }
        
        .question-number {
            font-weight: bold;
            margin-bottom: 5px;
            color: #0066cc;
        }
        
        .question-text {
            margin-bottom: 10px;
            line-height: 1.8;
            font-weight: 500;
        }
        
        .options {
            margin-right: 20px;
        }
        
        .option {
            margin-bottom: 8px;
            line-height: 1.6;
        }
        
        /* جدول الإجابات */
        .answer-key {
            margin-top: 30px;
            border-top: 2px solid #000;
            padding-top: 20px;
            grid-column: 1 / -1;
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
            font-size: 12px;
        }
        
        .answer-table th {
            background-color: #f5f5f5;
            font-weight: bold;
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
            <!-- معلومات الاختبار -->
            <table class="header-table">
                <tr>
                    <td class="label">المملكة:</td>
                    <td class="value">{{ country }}</td>
                </tr>
                <tr>
                    <td class="label">الوزارة:</td>
                    <td class="value">{{ ministry }}</td>
                </tr>
                <tr>
                    <td class="label">الإدارة:</td>
                    <td class="value">{{ education_department }}</td>
                </tr>
                <tr>
                    <td class="label">المدرسة:</td>
                    <td class="value">{{ school_name }}</td>
                </tr>
            </table>
            
            <!-- عنوان الاختبار -->
            <div class="exam-title">{{ exam_title }}</div>
            
            <!-- معلومات إضافية -->
            <table class="header-table">
                <tr>
                    <td class="label">المادة:</td>
                    <td class="value">{{ subject }}</td>
                </tr>
                <tr>
                    <td class="label">الزمن:</td>
                    <td class="value">{{ time }}</td>
                </tr>
                <tr>
                    <td class="label">المستوى:</td>
                    <td class="value">{{ grade }}</td>
                </tr>
                <tr>
                    <td class="label">الدرجة الكلية:</td>
                    <td class="value">{{ total_score }}</td>
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
                    {% set letters = ['أ', 'ب', 'ج', 'د'] %}
                    {% for option in question.options %}
                    <div class="option">
                        <span>{{ letters[loop.index0] if loop.index0 < 4 else loop.index0 + 1 }})</span>
                        {{ option.option_text }}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
            
            <!-- جدول الإجابات -->
            {% if show_answers %}
            <div class="answer-key">
                <div style="font-weight: bold; margin-bottom: 10px;">مفتاح الإجابات</div>
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
    </div>
</body>
</html>
"""
    
    def _prepare_context(self, questions, exam_title, show_answers, **kwargs):
        """تحضير السياق للقالب"""
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
            'questions': [],
            'show_answers': show_answers
        }
        
        # تنسيق الأسئلة
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
            
            context['questions'].append(formatted_q)
        
        return context
    
    def generate_html(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """توليد HTML من البيانات"""
        context = self._prepare_context(questions, exam_title, show_answers, **kwargs)
        
        # توليد HTML
        template = Template(self.html_template)
        return template.render(**context)
    
    def generate_pdf(self, questions, exam_title="نموذج الاختبار", 
                    show_answers=False, **kwargs):
        """توليد PDF من HTML"""
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        
        # تحويل HTML إلى PDF
        html_obj = HTML(string=html_content)
        pdf_bytes = html_obj.write_pdf()
        
        return pdf_bytes
    
    def generate_word(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """توليد Word من HTML"""
        try:
            html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
            
            # تحويل HTML إلى Word
            converter = HTML2Docx(title='الاختبار')
            converter.feed(html_content)
            doc = converter.doc
            
            # حفظ في BytesIO
            doc_bytes = io.BytesIO()
            doc.save(doc_bytes)
            doc_bytes.seek(0)
            
            return doc_bytes.getvalue()
            return docx_bytes
        
        except Exception as e:
            raise Exception(f"خطأ في توليد ملف Word: {str(e)}")


# دالة موحدة
def generate_exam(questions, exam_title="نموذج الاختبار", 
                 output_format='word', show_answers=False, 
                 header_settings=None, **kwargs):
    """
    دالة موحدة لتوليد الاختبارات من نفس قالب HTML
    
    Args:
        questions: قائمة الأسئلة
        exam_title: عنوان الاختبار
        output_format: صيغة الإخراج ('word' أو 'pdf')
        show_answers: هل يتم عرض الإجابات
        header_settings: إعدادات الرأس
        **kwargs: معاملات إضافية
    
    Returns:
        bytes: محتوى الملف
    """
    generator = UnifiedExamGenerator(header_settings)
    
    if output_format == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    else:  # word
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)
