"""
نظام موحد لتوليد ملفات PDF و Word من بيانات الاختبار
باستخدام python-docx و weasyprint
"""

from jinja2 import Template
from datetime import datetime
import io
from weasyprint import HTML
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


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
        
        /* جدول الإجابات */
        .answer-key {
            margin-top: 30px;
            border-top: 2px solid #000;
            padding-top: 20px;
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
        </div>
        
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
</body>
</html>
"""
    
    def generate_html(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """توليد HTML من البيانات"""
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
        
        # تنسيق الأسئلة
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
        """توليد PDF من البيانات"""
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        
        # تحويل HTML إلى PDF
        html_obj = HTML(string=html_content)
        pdf_bytes = html_obj.write_pdf()
        
        return pdf_bytes
    
    def generate_word(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """توليد Word من البيانات باستخدام python-docx"""
        try:
            # إنشاء مستند Word
            doc = Document()
            
            # تعيين اتجاه النص من اليمين إلى اليسار
            doc.paragraph_format.direction = 'RTL'
            
            # إضافة الرأس
            header_data = {
                'country': kwargs.get('country', self.header_settings.get('country', 'المملكة العربية السعودية')),
                'ministry': kwargs.get('ministry', self.header_settings.get('ministry', 'وزارة التعليم')),
                'education_department': kwargs.get('education_department', self.header_settings.get('education_department', '')),
                'school_name': kwargs.get('school_name', self.header_settings.get('school_name', '')),
                'subject': kwargs.get('subject', self.header_settings.get('subject', '')),
                'time': kwargs.get('time', self.header_settings.get('time', '')),
                'grade': kwargs.get('grade', self.header_settings.get('grade', '')),
                'total_score': kwargs.get('total_score', self.header_settings.get('total_score', 30)),
            }
            
            # جدول الرأس
            header_table = doc.add_table(rows=4, cols=2)
            header_table.style = 'Light Grid Accent 1'
            
            # ملء جدول الرأس
            header_cells = [
                ('المملكة:', header_data['country']),
                ('الوزارة:', header_data['ministry']),
                ('الإدارة:', header_data['education_department']),
                ('المدرسة:', header_data['school_name']),
            ]
            
            for i, (label, value) in enumerate(header_cells):
                row = header_table.rows[i]
                row.cells[0].text = label
                row.cells[1].text = value
                # تنسيق النص
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(11)
            
            # عنوان الاختبار
            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_run = title.add_run(exam_title)
            title_run.font.size = Pt(14)
            title_run.font.bold = True
            
            # معلومات إضافية
            info_table = doc.add_table(rows=4, cols=2)
            info_table.style = 'Light Grid Accent 1'
            
            info_cells = [
                ('المادة:', header_data['subject']),
                ('الزمن:', header_data['time']),
                ('المستوى:', header_data['grade']),
                ('الدرجة الكلية:', str(header_data['total_score'])),
            ]
            
            for i, (label, value) in enumerate(info_cells):
                row = info_table.rows[i]
                row.cells[0].text = label
                row.cells[1].text = value
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(11)
            
            # إضافة الأسئلة
            letters = ['أ', 'ب', 'ج', 'د']
            
            for idx, question in enumerate(questions, 1):
                # رقم السؤال
                q_num = doc.add_paragraph()
                q_num_run = q_num.add_run(f"السؤال {idx}: ({question.get('points', 1)} درجات)")
                q_num_run.font.bold = True
                q_num_run.font.size = Pt(12)
                
                # نص السؤال
                q_text = doc.add_paragraph(question.get('question_text', ''))
                q_text.paragraph_format.right_indent = Inches(0.2)
                
                # الخيارات
                options = question.get('options', [])
                for opt_idx, option in enumerate(options):
                    opt_text = doc.add_paragraph()
                    opt_text.paragraph_format.right_indent = Inches(0.4)
                    letter = letters[opt_idx] if opt_idx < len(letters) else str(opt_idx + 1)
                    opt_run = opt_text.add_run(f"{letter}) {option.get('option_text', '')}")
                    opt_run.font.size = Pt(11)
                
                # فاصل
                doc.add_paragraph()
            
            # جدول الإجابات
            if show_answers:
                doc.add_paragraph("مفتاح الإجابات").bold = True
                
                # إنشاء جدول الإجابات
                answer_table = doc.add_table(rows=2, cols=len(questions))
                answer_table.style = 'Light Grid Accent 1'
                
                # رؤوس الأعمدة (أرقام الأسئلة)
                for i in range(len(questions)):
                    answer_table.rows[0].cells[i].text = str(i + 1)
                
                # الإجابات الصحيحة
                letters = ['أ', 'ب', 'ج', 'د']
                for i, question in enumerate(questions):
                    options = question.get('options', [])
                    correct_answer = ''
                    for opt_idx, option in enumerate(options):
                        if option.get('is_correct') or option.get('option_id') == question.get('correct_option_id'):
                            correct_answer = letters[opt_idx] if opt_idx < len(letters) else str(opt_idx + 1)
                            break
                    answer_table.rows[1].cells[i].text = correct_answer
            
            # حفظ المستند في BytesIO
            doc_bytes = io.BytesIO()
            doc.save(doc_bytes)
            doc_bytes.seek(0)
            
            return doc_bytes.getvalue()
        
        except Exception as e:
            raise Exception(f"خطأ في توليد ملف Word: {str(e)}")


# دالة مساعدة
def generate_exam(questions, exam_title="نموذج الاختبار", 
                 output_format='word', show_answers=False, 
                 header_settings=None, **kwargs):
    """
    دالة موحدة لتوليد الاختبارات بصيغ مختلفة
    
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
    try:
        generator = ExamGenerator(header_settings or kwargs)
        
        if output_format.lower() == 'pdf':
            try:
                return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
            except ImportError:
                raise ImportError("weasyprint غير مثبت. الرجاء تثبيته: pip install weasyprint")
        elif output_format.lower() == 'word':
            return generator.generate_word(questions, exam_title, show_answers, **kwargs)
        else:
            raise ValueError(f"صيغة غير مدعومة: {output_format}")
    
    except Exception as e:
        raise Exception(f"خطأ في توليد الاختبار: {str(e)}")
