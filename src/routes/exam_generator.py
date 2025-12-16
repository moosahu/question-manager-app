"""
نظام محسّن لتوليد ملفات PDF و Word من بيانات الاختبار
(النسخة الكاملة: تشمل تصميم PDF الجديد + كود Word الأصلي)
"""

from jinja2 import Template
from datetime import datetime
import io
import base64
from weasyprint import HTML
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image


class ExamGenerator:
    """فئة محسّنة لتوليد الاختبارات بصيغ مختلفة"""
    
    def __init__(self, header_settings=None, logo_path=None):
        """تهيئة منشئ الاختبارات"""
        self.header_settings = header_settings or {}
        self.logo_path = logo_path or '/home/ubuntu/ministry_logo.png'
        self.html_template = self._get_html_template()
    
    def _get_logo_base64(self):
        """تحويل الشعار إلى base64"""
        try:
            with open(self.logo_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        except:
            return None
    
    def _get_html_template(self):
        """الحصول على قالب HTML - بالتصميم الجديد (إطار وجداول)"""
        return """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>{{ exam_title }}</title>
    <style>
        @page {
            size: A4;
            margin: 0;
        }
        
        body {
            font-family: 'Traditional Arabic', 'Times New Roman', Arial, serif;
            margin: 0;
            padding: 0;
            background: #fff;
            color: #000;
        }

        /* حاوية الصفحة */
        .page-container {
            width: 210mm;
            min-height: 296mm;
            padding: 15mm;
            margin: 0 auto;
            box-sizing: border-box;
        }

        /* الإطار المزدوج */
        .exam-frame {
            border: 3px double #000;
            padding: 20px;
            min-height: 265mm;
            position: relative;
        }

        /* الرأس */
        .header-table {
            width: 100%;
            border: none;
            margin-bottom: 10px;
        }
        .header-table td {
            border: none;
            vertical-align: top;
            padding: 2px;
        }
        
        .header-right { text-align: right; width: 35%; font-size: 16px; font-weight: bold; line-height: 1.6; }
        .header-center { text-align: center; width: 30%; }
        .header-left { text-align: left; width: 35%; direction: ltr; }
        
        .left-info {
            direction: rtl;
            text-align: right;
            display: inline-block;
            width: 100%;
            font-size: 16px;
            font-weight: bold;
            line-height: 1.8;
        }
        
        .underlined {
            border-bottom: 1px solid #000;
            display: inline-block;
            min-width: 100px;
            text-align: center;
        }

        /* جدول الدرجات */
        .grades-table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            border: 2px solid #000;
        }
        .grades-table th, .grades-table td {
            border: 1px solid #000;
            text-align: center;
            padding: 5px;
            font-weight: bold;
            font-size: 15px;
        }
        .grades-table th {
            background-color: #e6e6e6;
            height: 35px;
        }
        .grades-table td {
            height: 40px;
            font-size: 18px;
        }

        /* معلومات الطالب */
        .student-info {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
            font-family: 'Traditional Arabic', serif;
        }
        .info-box {
            display: flex;
            align-items: baseline;
        }
        .dashed-line {
            border-bottom: 1px solid #000;
            flex-grow: 1;
            margin-right: 5px;
            min-width: 50px;
        }

        /* الأسئلة */
        .questions-wrapper {
            margin-top: 20px;
            column-count: 2;
            column-gap: 40px;
            column-rule: 1px solid #ccc;
        }
        .question-box {
            break-inside: avoid;
            margin-bottom: 15px;
            font-size: 15px;
        }
        .q-num { color: #000; font-weight: bold; margin-left: 5px; }
        .q-text { font-weight: bold; }
        .q-options { margin-top: 5px; margin-right: 15px; }
        .q-option { display: block; margin-bottom: 3px; }

        /* نموذج الإجابة */
        .answer-key {
            margin-top: 30px;
            border-top: 2px solid #000;
            padding-top: 20px;
            break-before: page;
        }
        .answer-table-key { width: 100%; border-collapse: collapse; direction: rtl; }
        .answer-table-key th, .answer-table-key td { border: 1px solid #000; padding: 5px; text-align: center; }
        .answer-table-key th { background-color: #f5f5f5; }

    </style>
</head>
<body>
    <div class="page-container">
        <div class="exam-frame">
            
            <table class="header-table">
                <tr>
                    <td class="header-right">
                        <div>{{ country }}</div>
                        <div>{{ ministry }}</div>
                        <div>{{ education_department }}</div>
                        <div>مدرسة {{ school_name }}</div>
                    </td>
                    <td class="header-center">
                        <div style="font-size: 22px; font-weight: bold; color: #0b8c78; line-height: 1.2;">
                            .::.::.::.<br>
                            <span style="font-size:12px; letter-spacing:1px; color:#000;">MINISTRY OF EDUCATION</span><br>
                            وزارة التعليم
                        </div>
                    </td>
                    <td class="header-left">
                        <div class="left-info">
                            <div>المادة : <span class="underlined">{{ subject }}</span></div>
                            <div>الزمن : <span class="underlined">{{ time }}</span></div>
                            <div>الصف : <span class="underlined">{{ grade }}</span></div>
                        </div>
                    </td>
                </tr>
            </table>

            <div style="text-align:center; font-weight:bold; font-size:18px; margin: 15px 0;">
                {{ exam_title }}
            </div>

            <table class="grades-table">
                <thead>
                    <tr>
                        <th>الدرجة الأساسية</th>
                        <th>درجة الطالب رقماً</th>
                        <th>الدرجة كتابةً</th>
                        <th>المصحح</th>
                        <th>المراجع</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{{ total_score }}</td>
                        <td></td>
                        <td></td>
                        <td>{{ checker_name }}</td>
                        <td>{{ reviewer_name }}</td>
                    </tr>
                </tbody>
            </table>

            <div class="student-info">
                <div class="info-box" style="width: 45%;">
                    <span>اسم الطالب /</span><div class="dashed-line"></div>
                </div>
                <div class="info-box" style="width: 25%;">
                    <span>الشعبة /</span><div class="dashed-line"></div>
                </div>
                <div class="info-box" style="width: 25%;">
                    <span>رقم الجلوس /</span><div class="dashed-line"></div>
                </div>
            </div>

            <hr style="border: 0; border-top: 2px solid #000; margin: 20px 0;">

            <div class="questions-wrapper">
                {% for question in questions %}
                <div class="question-box">
                    <div>
                        <span class="q-num">س{{ loop.index }}:</span>
                        <span class="q-text">{{ question.question_text }}</span>
                    </div>
                    <div class="q-options">
                        {% for option in question.options %}
                        <div class="q-option">
                            {{ option.letter }}) {{ option.option_text }}
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if show_answers %}
            <div class="answer-key">
                <div style="font-weight: bold; margin-bottom: 10px;">مفتاح الإجابات</div>
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; direction: rtl;">
                    {% for question in questions %}
                    <div style="border:1px solid #000; padding:5px; text-align:center;">
                        س{{ loop.index }}: <strong>{{ question.correct_answer }}</strong>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

        </div>
    </div>
</body>
</html>
"""
    
    def _prepare_context(self, questions, exam_title, show_answers, **kwargs):
        """تحضير السياق للقالب"""
        def get_val(key, default):
            val = kwargs.get(key)
            if val: return val
            val = self.header_settings.get(key)
            if val: return val
            return default

        context = {
            'exam_title': exam_title,
            'country': get_val('country', 'المملكة العربية السعودية'),
            'ministry': get_val('ministry', 'وزارة التعليم'),
            'education_department': get_val('education_department', 'الإدارة العامة للتعليم بالمنطقة الشرقية'),
            'school_name': get_val('school_name', 'مدرسة عبدالرحمن بن القاسم الثانوية'),
            'subject': get_val('subject', 'كيمياء 4'),
            'time': get_val('time', 'ثلاث ساعات'),
            'grade': get_val('grade', 'ثالث ثانوي'),
            'total_score': get_val('total_score', 30),
            'checker_name': get_val('checker_name', ''),
            'reviewer_name': get_val('reviewer_name', ''),
            'exam_date': get_val('exam_date', ''),
            'questions': [],
            'show_answers': show_answers,
            'logo': self._get_logo_base64()
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
                    'option_text': option.get('option_text', '')
                })
                if option.get('is_correct') or option.get('option_id') == question.get('correct_option_id'):
                    formatted_q['correct_answer'] = letter
            context['questions'].append(formatted_q)
        return context
    
    def generate_html(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        context = self._prepare_context(questions, exam_title, show_answers, **kwargs)
        template = Template(self.html_template)
        return template.render(**context)
    
    def generate_pdf(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        html_content = self.generate_html(questions, exam_title, show_answers, **kwargs)
        html_obj = HTML(string=html_content)
        pdf_bytes = html_obj.write_pdf()
        return pdf_bytes
    
    def generate_word(self, questions, exam_title="نموذج الاختبار", show_answers=False, **kwargs):
        """توليد ملف Word كامل"""
        try:
            # دالة مساعدة لجلب القيم
            def get_val(key, default):
                return kwargs.get(key) or self.header_settings.get(key) or default

            doc = Document()
            
            # تعيين هوامش الصفحة
            sections = doc.sections
            for section in sections:
                section.top_margin = Inches(0.75)
                section.bottom_margin = Inches(0.75)
                section.left_margin = Inches(0.75)
                section.right_margin = Inches(0.75)
            
            # إضافة الشعار
            try:
                logo_para = doc.add_paragraph()
                logo_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = logo_para.add_run()
                run.add_picture(self.logo_path, width=Inches(1.2))
            except:
                pass
            
            # إضافة معلومات الرأس
            header_data = {
                'country': get_val('country', 'المملكة العربية السعودية'),
                'ministry': get_val('ministry', 'وزارة التعليم'),
                'education_department': get_val('education_department', 'الإدارة العامة للتعليم بالمنطقة الشرقية'),
                'school_name': get_val('school_name', 'مدرسة عبدالرحمن بن القاسم الثانوية'),
                'subject': get_val('subject', 'كيمياء 4'),
                'time': get_val('time', 'ثلاث ساعات'),
                'grade': get_val('grade', 'ثالث ثانوي'),
                'total_score': get_val('total_score', 30),
            }
            
            # جدول معلومات الرأس
            header_info = doc.add_table(rows=1, cols=3)
            header_info.style = 'Table Grid'
            
            cells = header_info.rows[0].cells
            
            # العمود الأيمن
            right_cell = cells[2]
            right_cell.text = f"{header_data['country']}\n{header_data['ministry']}"
            for paragraph in right_cell.paragraphs:
                paragraph.paragraph_format.direction = 1
                for run in paragraph.runs:
                    run.font.size = Pt(11)
                    run.font.bold = True
            
            # العمود الأوسط (فارغ)
            middle_cell = cells[1]
            middle_cell.text = ""
            
            # العمود الأيسر
            left_cell = cells[0]
            left_cell.text = f"{header_data['education_department']}\n{header_data['school_name']}"
            for paragraph in left_cell.paragraphs:
                paragraph.paragraph_format.direction = 1
                for run in paragraph.runs:
                    run.font.size = Pt(11)
                    run.font.bold = True
            
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
            
            # جدول المعلومات
            info_table = doc.add_table(rows=2, cols=4)
            info_table.style = 'Table Grid'
            
            info_cells = [
                ('المادة:', header_data['subject'], 'الزمن:', header_data['time']),
                ('الصف:', header_data['grade'], 'الدرجة الكلية:', str(header_data['total_score'])),
            ]
            
            for row_idx, row_data in enumerate(info_cells):
                row = info_table.rows[row_idx]
                for col_idx, (label, value) in enumerate([(row_data[0], row_data[1]), (row_data[2], row_data[3])]):
                    label_cell = row.cells[col_idx * 2]
                    label_cell.text = label
                    for paragraph in label_cell.paragraphs:
                        paragraph.paragraph_format.direction = 1
                        for run in paragraph.runs:
                            run.font.size = Pt(11)
                            run.font.bold = True
                        self._add_shading(paragraph, 'f5f5f5')
                    
                    value_cell = row.cells[col_idx * 2 + 1]
                    value_cell.text = value
                    for paragraph in value_cell.paragraphs:
                        paragraph.paragraph_format.direction = 1
                        for run in paragraph.runs:
                            run.font.size = Pt(11)
            
            # جدول الدرجات
            grades_table = doc.add_table(rows=2, cols=5)
            grades_table.style = 'Table Grid'
            
            grade_headers = ['الدرجة الأساسية', 'درجة الطالب رقماً', 'درجة كتابية', 'المصحح', 'المراجع']
            for col_idx, header in enumerate(grade_headers):
                cell = grades_table.rows[0].cells[col_idx]
                cell.text = header
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.direction = 1
                    for run in paragraph.runs:
                        run.font.bold = True
                        run.font.size = Pt(10)
                    self._add_shading(paragraph, 'f5f5f5')
            
            # ملء الصف الثاني من جدول الدرجات
            grades_table.rows[1].cells[0].text = str(header_data['total_score'])
            
            # معلومات الطالب
            doc.add_paragraph()
            student_info = doc.add_table(rows=1, cols=3)
            student_info.style = 'Table Grid'
            
            student_fields = [
                'اسم الطالب: __________',
                'الشعبة: __________',
                'رقم الجلوس: __________'
            ]
            
            for col_idx, field in enumerate(student_fields):
                cell = student_info.rows[0].cells[col_idx]
                cell.text = field
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.direction = 1
                    for run in paragraph.runs:
                        run.font.size = Pt(10)
            
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
        if len(options) > 0:
            for row_idx in range(0, len(options), 2):
                opt_para = cell.add_paragraph()
                opt_para.paragraph_format.direction = 1
                opt_para.paragraph_format.space_after = Pt(4)
                
                if row_idx < len(options):
                    letter = letters[row_idx] if row_idx < len(letters) else str(row_idx + 1)
                    letter_run = opt_para.add_run(f"{letter}) ")
                    letter_run.font.bold = True
                    letter_run.font.size = Pt(10)
                    opt_run = opt_para.add_run(options[row_idx].get('option_text', ''))
                    opt_run.font.size = Pt(10)
                    
                    space_run = opt_para.add_run("                    ")
                    space_run.font.size = Pt(10)
                
                if row_idx + 1 < len(options):
                    letter = letters[row_idx + 1] if row_idx + 1 < len(letters) else str(row_idx + 2)
                    letter_run = opt_para.add_run(f"{letter}) ")
                    letter_run.font.bold = True
                    letter_run.font.size = Pt(10)
                    opt_run = opt_para.add_run(options[row_idx + 1].get('option_text', ''))
                    opt_run.font.size = Pt(10)


# دالة موحدة
def generate_exam(questions, exam_title="نموذج الاختبار", 
                 output_format='word', show_answers=False, 
                 header_settings=None, logo_path=None, **kwargs):
    """دالة موحدة لتوليد الاختبارات"""
    generator = ExamGenerator(header_settings, logo_path)
    
    if output_format == 'pdf':
        return generator.generate_pdf(questions, exam_title, show_answers, **kwargs)
    else:
        return generator.generate_word(questions, exam_title, show_answers, **kwargs)