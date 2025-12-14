"""
نظام محسّن لتوليد ملفات PDF و Word من بيانات الاختبار
يضمن تطابق كامل بين الملفين
"""

from jinja2 import Template
from datetime import datetime
import io
from weasyprint import HTML
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


class ExamGenerator:
    """فئة محسّنة لتوليد الاختبارات بصيغ مختلفة"""
    
    def __init__(self, header_settings=None):
        """تهيئة منشئ الاختبارات"""
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
    </style>
</head>
<body>
    <div class="container">
        <!-- رأس الاختبار -->
        <div class="header">
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
            
            <div class="exam-title">{{ exam_title }}</div>
            
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
        template = Template(self.html_template)
        return template.render(**context)
    
    def generate_pdf(self, questions, exam_title="نموذج الاختبار", 
                    show_answers=False, **kwargs):
        """توليد PDF من HTML"""
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        html_obj = HTML(string=html_content)
        pdf_bytes = html_obj.write_pdf()
        return pdf_bytes
    
    def generate_word(self, questions, exam_title="نموذج الاختبار", 
                     show_answers=False, **kwargs):
        """توليد Word بنفس تصميم PDF"""
        try:
            # إنشاء مستند Word
            doc = Document()
            
            # تعيين هوامش الصفحة
            sections = doc.sections
            for section in sections:
                section.top_margin = Inches(0.75)
                section.bottom_margin = Inches(0.75)
                section.left_margin = Inches(0.75)
                section.right_margin = Inches(0.75)
            
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
            
            # جدول الرأس الأول
            header_table = doc.add_table(rows=4, cols=2)
            header_table.style = 'Table Grid'
            
            for row in header_table.rows:
                row.cells[0].width = Inches(1.5)
                row.cells[1].width = Inches(3.5)
            
            header_cells = [
                ('المملكة:', header_data['country']),
                ('الوزارة:', header_data['ministry']),
                ('الإدارة:', header_data['education_department']),
                ('المدرسة:', header_data['school_name']),
            ]
            
            for i, (label, value) in enumerate(header_cells):
                row = header_table.rows[i]
                
                label_cell = row.cells[0]
                label_cell.text = label
                for paragraph in label_cell.paragraphs:
                    paragraph.paragraph_format.direction = 1
                    for run in paragraph.runs:
                        run.font.size = Pt(11)
                        run.font.bold = True
                    self._add_shading(paragraph, 'f5f5f5')
                
                value_cell = row.cells[1]
                value_cell.text = value
                for paragraph in value_cell.paragraphs:
                    paragraph.paragraph_format.direction = 1
                    for run in paragraph.runs:
                        run.font.size = Pt(11)
            
            # عنوان الاختبار
            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title.paragraph_format.direction = 1
            title.paragraph_format.space_before = Pt(12)
            title.paragraph_format.space_after = Pt(12)
            title_run = title.add_run(exam_title)
            title_run.font.size = Pt(14)
            title_run.font.bold = True
            
            # إضافة خط تحت العنوان
            pPr = title._element.get_or_add_pPr()
            pBdr = OxmlElement('w:pBdr')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '24')
            bottom.set(qn('w:space'), '1')
            bottom.set(qn('w:color'), '000000')
            pBdr.append(bottom)
            pPr.append(pBdr)
            
            # جدول المعلومات الإضافية
            info_table = doc.add_table(rows=4, cols=2)
            info_table.style = 'Table Grid'
            
            for row in info_table.rows:
                row.cells[0].width = Inches(1.5)
                row.cells[1].width = Inches(3.5)
            
            info_cells = [
                ('المادة:', header_data['subject']),
                ('الزمن:', header_data['time']),
                ('المستوى:', header_data['grade']),
                ('الدرجة الكلية:', str(header_data['total_score'])),
            ]
            
            for i, (label, value) in enumerate(info_cells):
                row = info_table.rows[i]
                
                label_cell = row.cells[0]
                label_cell.text = label
                for paragraph in label_cell.paragraphs:
                    paragraph.paragraph_format.direction = 1
                    for run in paragraph.runs:
                        run.font.size = Pt(11)
                        run.font.bold = True
                    self._add_shading(paragraph, 'f5f5f5')
                
                value_cell = row.cells[1]
                value_cell.text = value
                for paragraph in value_cell.paragraphs:
                    paragraph.paragraph_format.direction = 1
                    for run in paragraph.runs:
                        run.font.size = Pt(11)
            
            # إضافة فاصل
            doc.add_paragraph()
            
            # إضافة الأسئلة في تخطيط عمودين
            letters = ['أ', 'ب', 'ج', 'د']
            num_rows = (len(questions) + 1) // 2
            
            questions_table = doc.add_table(rows=num_rows, cols=2)
            questions_table.style = 'Table Grid'
            
            for row in questions_table.rows:
                row.cells[0].width = Inches(3.5)
                row.cells[1].width = Inches(3.5)
            
            for row_idx in range(num_rows):
                row = questions_table.rows[row_idx]
                
                right_cell = row.cells[1]
                right_q_idx = row_idx
                
                left_cell = row.cells[0]
                left_q_idx = row_idx + num_rows
                
                if right_q_idx < len(questions):
                    self._fill_question_cell(right_cell, questions[right_q_idx], right_q_idx + 1, letters)
                
                if left_q_idx < len(questions):
                    self._fill_question_cell(left_cell, questions[left_q_idx], left_q_idx + 1, letters)
            
            # جدول الإجابات
            if show_answers:
                doc.add_paragraph()
                answer_key_para = doc.add_paragraph("مفتاح الإجابات")
                answer_key_para.paragraph_format.direction = 1
                answer_key_para.runs[0].bold = True
                answer_key_para.runs[0].font.size = Pt(12)
                
                answer_table = doc.add_table(rows=2, cols=len(questions))
                answer_table.style = 'Table Grid'
                
                for i in range(len(questions)):
                    cell = answer_table.rows[0].cells[i]
                    cell.text = str(i + 1)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.direction = 1
                        for run in paragraph.runs:
                            run.font.bold = True
                            run.font.size = Pt(10)
                        self._add_shading(paragraph, 'f5f5f5')
                
                letters = ['أ', 'ب', 'ج', 'د']
                for i, question in enumerate(questions):
                    options = question.get('options', [])
                    correct_answer = ''
                    for opt_idx, option in enumerate(options):
                        if option.get('is_correct') or option.get('option_id') == question.get('correct_option_id'):
                            correct_answer = letters[opt_idx] if opt_idx < len(letters) else str(opt_idx + 1)
                            break
                    cell = answer_table.rows[1].cells[i]
                    cell.text = correct_answer
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.direction = 1
                        for run in paragraph.runs:
                            run.font.size = Pt(10)
            
            # حفظ في BytesIO
            doc_bytes = io.BytesIO()
            doc.save(doc_bytes)
            doc_bytes.seek(0)
            
            return doc_bytes.getvalue()
        
        except Exception as e:
            raise Exception(f"خطأ في توليد ملف Word: {str(e)}")
    
    def _add_shading(self, paragraph, color):
        """إضافة خلفية للفقرة"""
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), color)
        paragraph._element.get_or_add_pPr().append(shading_elm)
    
    def _fill_question_cell(self, cell, question, question_num, letters):
        """ملء خلية السؤال"""
        for paragraph in cell.paragraphs:
            p = paragraph._element
            p.getparent().remove(p)
        
        q_num = cell.add_paragraph()
        q_num.paragraph_format.direction = 1
        q_num.paragraph_format.space_after = Pt(6)
        q_num_run = q_num.add_run(f"السؤال {question_num}: ({question.get('points', 1)} درجات)")
        q_num_run.font.bold = True
        q_num_run.font.size = Pt(11)
        q_num_run.font.color.rgb = RGBColor(0, 102, 204)
        
        q_text = cell.add_paragraph(question.get('question_text', ''))
        q_text.paragraph_format.direction = 1
        q_text.paragraph_format.right_indent = Inches(0.1)
        q_text.paragraph_format.space_after = Pt(6)
        for run in q_text.runs:
            run.font.size = Pt(10)
        
        options = question.get('options', [])
        for opt_idx, option in enumerate(options):
            opt_text = cell.add_paragraph()
            opt_text.paragraph_format.direction = 1
            opt_text.paragraph_format.right_indent = Inches(0.2)
            opt_text.paragraph_format.space_after = Pt(3)
            letter = letters[opt_idx] if opt_idx < len(letters) else str(opt_idx + 1)
            opt_run = opt_text.add_run(f"{letter}) {option.get('option_text', '')}")
            opt_run.font.size = Pt(10)


# دالة موحدة
def generate_exam(questions, exam_title="نموذج الاختبار", 
                 output_format='word', show_answers=False, 
                 header_settings=None, **kwargs):
    """دالة موحدة لتوليد الاختبارات"""
    generator = ExamGenerator(header_settings)
    
    if output_format == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    else:
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)
