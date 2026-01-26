# src/routes/diagnostic_routes.py
"""
API للاختبارات التشخيصية
- متوافق مع Flutter
- توليد اختبارات قبلية/بعدية
- استخراج PDF
"""

from flask import Blueprint, request, jsonify, send_file, render_template
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps
import io

try:
    from src.extensions import db
    from src.models.diagnostic_test import DiagnosticTest, DiagnosticResult, DiagnosticComparison
    from src.services.diagnostic_service import diagnostic_service
    from src.models.curriculum import Lesson, Unit, Course
    from src.models.student import Student
except ImportError:
    from extensions import db
    from models.diagnostic_test import DiagnosticTest, DiagnosticResult, DiagnosticComparison
    from services.diagnostic_service import diagnostic_service
    from models.curriculum import Lesson, Unit, Course
    from models.student import Student

diagnostic_bp = Blueprint('diagnostic', __name__, url_prefix='/api/diagnostic')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'يجب تسجيل الدخول'}), 401
        if not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated


# ==========================================
# توليد الاختبارات
# ==========================================

@diagnostic_bp.route('/generate', methods=['POST'])
@login_required
def generate_test():
    """
    توليد اختبار تشخيصي جديد
    
    POST /api/diagnostic/generate
    {
        "lesson_id": 1,  // أو unit_id أو course_id
        "test_type": "pre_test",  // أو post_test
        "questions_count": 5,
        "difficulty_distribution": {"easy": 2, "medium": 2, "hard": 1}
    }
    """
    try:
        data = request.get_json() or {}
        
        lesson_id = data.get('lesson_id')
        unit_id = data.get('unit_id')
        course_id = data.get('course_id')
        test_type = data.get('test_type', 'pre_test')
        questions_count = data.get('questions_count', 5)
        difficulty_dist = data.get('difficulty_distribution', {'easy': 2, 'medium': 2, 'hard': 1})
        force_ai = data.get('force_ai', False)  # توليد كل الأسئلة بـ AI
        
        if not any([lesson_id, unit_id, course_id]):
            return jsonify({'success': False, 'error': 'يجب تحديد درس أو وحدة أو منهج'}), 400
        
        # توليد الاختبار
        result = diagnostic_service.generate_test(
            lesson_id=lesson_id,
            unit_id=unit_id,
            course_id=course_id,
            test_type=test_type,
            questions_count=questions_count,
            difficulty_dist=difficulty_dist,
            force_ai=force_ai
        )
        
        if not result.get('success'):
            return jsonify(result), 400
        
        # جلب الأسماء من السياق
        context = result.get('context', {})
        lesson_name = context.get('name') if context.get('type') == 'lesson' else None
        unit_name = context.get('name') if context.get('type') == 'unit' else context.get('unit_name')
        course_name = context.get('course_name') or (context.get('name') if context.get('type') == 'course' else None)
        
        # حفظ في قاعدة البيانات
        test = DiagnosticTest(
            title=result['title'],
            description=result['description'],
            test_type=test_type,
            lesson_id=lesson_id,
            unit_id=unit_id,
            course_id=course_id,
            lesson_name=lesson_name,
            unit_name=unit_name,
            course_name=course_name,
            questions_count=result['questions_count'],
            questions_data=result['questions'],
            difficulty_distribution=difficulty_dist,
            ai_generated=result.get('ai_generated', False),
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )
        
        db.session.add(test)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'تم إنشاء الاختبار {"القبلي" if test_type == "pre_test" else "البعدي"} بنجاح',
            'test': test.to_dict(include_questions=True)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostic_bp.route('/generate-pair', methods=['POST'])
@login_required
def generate_test_pair():
    """
    توليد زوج اختبارات (قبلي + بعدي) معاً
    
    POST /api/diagnostic/generate-pair
    {
        "lesson_id": 1,
        "questions_count": 5
    }
    """
    try:
        data = request.get_json() or {}
        
        lesson_id = data.get('lesson_id')
        unit_id = data.get('unit_id')
        questions_count = data.get('questions_count', 5)
        
        if not any([lesson_id, unit_id]):
            return jsonify({'success': False, 'error': 'يجب تحديد درس أو وحدة'}), 400
        
        # توليد القبلي
        pre_result = diagnostic_service.generate_test(
            lesson_id=lesson_id,
            unit_id=unit_id,
            test_type='pre_test',
            questions_count=questions_count
        )
        
        if not pre_result.get('success'):
            return jsonify(pre_result), 400
        
        # جلب الأسماء
        context = pre_result.get('context', {})
        lesson_name = context.get('name') if context.get('type') == 'lesson' else None
        unit_name = context.get('name') if context.get('type') == 'unit' else context.get('unit_name')
        course_name = context.get('course_name')
        
        # حفظ القبلي
        pre_test = DiagnosticTest(
            title=pre_result['title'],
            description=pre_result['description'],
            test_type='pre_test',
            lesson_id=lesson_id,
            unit_id=unit_id,
            lesson_name=lesson_name,
            unit_name=unit_name,
            course_name=course_name,
            questions_count=pre_result['questions_count'],
            questions_data=pre_result['questions'],
            ai_generated=pre_result.get('ai_generated', False),
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )
        db.session.add(pre_test)
        db.session.flush()  # للحصول على ID
        
        # توليد البعدي (نفس الأسئلة أو مختلفة)
        post_result = diagnostic_service.generate_test(
            lesson_id=lesson_id,
            unit_id=unit_id,
            test_type='post_test',
            questions_count=questions_count
        )
        
        # حفظ البعدي
        post_test = DiagnosticTest(
            title=post_result['title'],
            description=post_result['description'],
            test_type='post_test',
            lesson_id=lesson_id,
            unit_id=unit_id,
            lesson_name=lesson_name,
            unit_name=unit_name,
            course_name=course_name,
            questions_count=post_result.get('questions_count', questions_count),
            questions_data=post_result.get('questions', pre_result['questions']),
            ai_generated=post_result.get('ai_generated', False),
            paired_test_id=pre_test.id,
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )
        db.session.add(post_test)
        
        # ربط القبلي بالبعدي
        pre_test.paired_test_id = post_test.id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم إنشاء الاختبارين القبلي والبعدي بنجاح',
            'pre_test': pre_test.to_dict(),
            'post_test': post_test.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# جلب الاختبارات
# ==========================================

@diagnostic_bp.route('/tests', methods=['GET'])
@login_required
def get_tests():
    """جلب قائمة الاختبارات"""
    try:
        lesson_id = request.args.get('lesson_id', type=int)
        unit_id = request.args.get('unit_id', type=int)
        test_type = request.args.get('test_type')
        
        query = DiagnosticTest.query.filter_by(is_active=True)
        
        if lesson_id:
            query = query.filter_by(lesson_id=lesson_id)
        if unit_id:
            query = query.filter_by(unit_id=unit_id)
        if test_type:
            query = query.filter_by(test_type=test_type)
        
        tests = query.order_by(DiagnosticTest.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'tests': [t.to_dict() for t in tests],
            'count': len(tests)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostic_bp.route('/tests/<int:test_id>', methods=['GET'])
@login_required
def get_test(test_id):
    """جلب تفاصيل اختبار مع الأسئلة"""
    try:
        test = DiagnosticTest.query.filter_by(id=test_id, is_active=True).first()
        
        if not test:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        return jsonify({
            'success': True,
            'test': test.to_dict(include_questions=True)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# استخراج PDF
# ==========================================

@diagnostic_bp.route('/tests/<int:test_id>/pdf', methods=['GET'])
@login_required
def export_pdf(test_id):
    """
    استخراج ورقة اختبار PDF بتنسيق احترافي
    
    GET /api/diagnostic/tests/1/pdf?include_answers=true&columns=2&layout=grid
    
    Parameters:
        include_answers: إظهار الإجابات (true/false)
        columns: عدد الأعمدة (1, 2, 3) - افتراضي: 2
        layout: تنسيق الخيارات (vertical, horizontal, grid) - افتراضي: grid
    """
    try:
        test = DiagnosticTest.query.filter_by(id=test_id, is_active=True).first()
        
        if not test:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        # قراءة المعاملات
        include_answers = request.args.get('include_answers', 'false').lower() == 'true'
        columns = int(request.args.get('columns', 2))
        options_layout = request.args.get('layout', 'grid')
        
        # التحقق من القيم
        if columns not in [1, 2, 3]:
            columns = 2
        if options_layout not in ['vertical', 'horizontal', 'grid']:
            options_layout = 'grid'
        
        # جلب إعدادات الكليشة
        header_settings = {}
        try:
            from src.models.exam_header_settings import ExamHeaderSettings
            header = ExamHeaderSettings.query.first()
            if header:
                header_settings = {
                    'country': header.country or "المملكة العربية السعودية",
                    'ministry': header.ministry or "وزارة التعليم",
                    'school_name': header.school_name or "",
                    'subject': header.subject or "كيمياء",
                    'grade': header.grade or "",
                    'logo_url': getattr(header, 'logo_url', '') or getattr(header, 'logo', '') or ""
                }
        except:
            pass
        
        # بناء HTML بالتنسيق المطلوب
        html_content = generate_diagnostic_html(
            test, 
            include_answers, 
            header_settings,
            columns=columns,
            options_layout=options_layout
        )
        
        # تحويل إلى PDF باستخدام WeasyPrint
        try:
            from weasyprint import HTML, CSS
            pdf_bytes = HTML(string=html_content).write_pdf()
        except Exception as e:
            print(f"❌ WeasyPrint Error: {e}")
            return jsonify({'success': False, 'error': f'خطأ في توليد PDF: {str(e)}'}), 500
        
        if not pdf_bytes:
            return jsonify({'success': False, 'error': 'فشل توليد PDF'}), 500
        
        # إرسال الملف
        filename = f"diagnostic_test_{test_id}{'_answers' if include_answers else ''}.pdf"
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ PDF Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def generate_diagnostic_html(test, include_answers=False, header_settings=None, columns=2, options_layout='grid'):
    """
    توليد HTML للاختبار التشخيصي بتنسيق احترافي
    
    Args:
        test: كائن الاختبار
        include_answers: إظهار الإجابات
        header_settings: إعدادات الكليشة
        columns: عدد الأعمدة (1، 2، 3)
        options_layout: تنسيق الخيارات (vertical، horizontal، grid)
    """
    
    questions = test.questions_data or []
    
    # تحديد عرض الأعمدة
    if columns == 1:
        column_width = "100%"
        questions_per_column = len(questions)
    elif columns == 2:
        column_width = "48%"
        questions_per_column = (len(questions) + 1) // 2
    else:  # 3 columns
        column_width = "31%"
        questions_per_column = (len(questions) + 2) // 3
    
    # CSS للتنسيق الاحترافي
    css = f"""
    <style>
        @page {{
            size: A4;
            margin: 1cm;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Traditional Arabic', 'Arial', 'Tahoma', sans-serif;
            direction: rtl;
            text-align: right;
            font-size: 12px;
            line-height: 1.4;
            margin: 0;
            padding: 10px;
        }}
        
        /* === الكليشة === */
        .header-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
        }}
        .header-table td {{
            padding: 3px 8px;
            vertical-align: top;
        }}
        .header-right, .header-left {{
            width: 35%;
            font-size: 11px;
        }}
        .header-center {{
            width: 30%;
            text-align: center;
        }}
        .header-center img {{
            max-width: 60px;
            max-height: 60px;
        }}
        
        /* === عنوان الاختبار === */
        .exam-title {{
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
            font-size: 16px;
            font-weight: bold;
        }}
        
        /* === معلومات الطالب === */
        .student-info {{
            display: flex;
            justify-content: space-between;
            border: 1px solid #333;
            padding: 8px 15px;
            margin: 10px 0;
            background: #f9f9f9;
            border-radius: 5px;
        }}
        .student-info span {{
            font-size: 12px;
        }}
        
        /* === الأعمدة === */
        .questions-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 2%;
            justify-content: space-between;
        }}
        .questions-column {{
            width: {column_width};
            display: flex;
            flex-direction: column;
        }}
        
        /* === السؤال === */
        .question {{
            margin-bottom: 12px;
            padding: 8px;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            background: #fafafa;
            page-break-inside: avoid;
        }}
        .question-text {{
            font-weight: bold;
            font-size: 12px;
            margin-bottom: 8px;
            color: #333;
            line-height: 1.5;
        }}
        
        /* === الخيارات - شبكة === */
        .options-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            direction: rtl;
        }}
        
        /* === الخيارات - أفقي === */
        .options-horizontal {{
            display: flex;
            flex-wrap: wrap;
            flex-direction: row-reverse;
            gap: 10px;
            direction: rtl;
        }}
        .options-horizontal .option {{
            flex: 1;
            min-width: 45%;
        }}
        
        /* === الخيارات - عمودي === */
        .options-vertical {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        /* === الخيار === */
        .option {{
            padding: 4px 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 11px;
            background: white;
            text-align: right;
            direction: rtl;
        }}
        .option.correct {{
            background: #d4edda;
            border-color: #28a745;
            font-weight: bold;
        }}
        .option-letter {{
            display: inline-block;
            width: 22px;
            height: 22px;
            line-height: 22px;
            text-align: center;
            background: #667eea;
            color: white;
            border-radius: 50%;
            font-size: 11px;
            margin-left: 8px;
            font-weight: bold;
        }}
        
        /* === نموذج الإجابة === */
        .answer-key {{
            page-break-before: always;
            margin-top: 20px;
        }}
        .answer-key h2 {{
            text-align: center;
            background: #28a745;
            color: white;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        .answer-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
            max-width: 500px;
            margin: 0 auto;
        }}
        .answer-box {{
            border: 2px solid #333;
            padding: 8px;
            text-align: center;
            border-radius: 5px;
            background: #f5f5f5;
        }}
        .answer-box .q-num {{
            font-weight: bold;
            color: #667eea;
        }}
        .answer-box .q-ans {{
            font-size: 14px;
            font-weight: bold;
            color: #28a745;
        }}
        
        @media print {{
            body {{
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
    """
    
    # === الكليشة ===
    header_html = ""
    if header_settings:
        # الشعار
        logo_url = header_settings.get('logo_url', '')
        if logo_url:
            logo_html = f'<img src="{logo_url}" style="max-width: 60px; max-height: 60px;">'
        else:
            logo_html = ''
        
        header_html = f"""
        <table class="header-table">
            <tr>
                <td class="header-right">
                    <div style="font-weight: bold;">{header_settings.get('country', 'المملكة العربية السعودية')}</div>
                    <div>{header_settings.get('ministry', 'وزارة التعليم')}</div>
                    <div>{header_settings.get('school_name', '')}</div>
                </td>
                <td class="header-center">
                    {logo_html}
                </td>
                <td class="header-left" style="text-align: left;">
                    <div>المادة: {header_settings.get('subject', 'كيمياء')}</div>
                    <div>الصف: {header_settings.get('grade', '')}</div>
                    <div>الزمن: {test.time_limit_minutes} دقيقة</div>
                </td>
            </tr>
        </table>
        """
    
    # === عنوان الاختبار ===
    test_type_ar = 'قبلي' if test.test_type == 'pre_test' else 'بعدي'
    title_html = f"""
    <div class="exam-title">
        {test.title or f'اختبار تشخيصي {test_type_ar}'}
        <br>
        <span style="font-size: 12px; font-weight: normal;">عدد الأسئلة: {len(questions)}</span>
    </div>
    """
    
    # === معلومات الطالب ===
    student_html = """
    <div class="student-info">
        <span>الاسم: ________________________________</span>
        <span>الصف: ____________</span>
        <span>التاريخ: ____/____/______</span>
    </div>
    """
    
    # === تحديد class الخيارات ===
    options_class = f"options-{options_layout}"
    
    # === بناء الأسئلة ===
    def build_question_html(q, num):
        q_text = q.get('text', '')
        options_html = ""
        
        for opt in q.get('options', []):
            letter = opt.get('letter', '')
            text = opt.get('text', '')
            is_correct = opt.get('is_correct', False)
            
            correct_class = ' correct' if include_answers and is_correct else ''
            check_mark = ' ✓' if include_answers and is_correct else ''
            
            options_html += f'''
            <div class="option{correct_class}">
                <span class="option-letter">{letter}</span>
                {text}{check_mark}
            </div>
            '''
        
        return f'''
        <div class="question">
            <div class="question-text">س{num}: {q_text}</div>
            <div class="{options_class}">{options_html}</div>
        </div>
        '''
    
    # === توزيع الأسئلة على الأعمدة ===
    questions_html = '<div class="questions-container">'
    
    if columns == 1:
        questions_html += '<div class="questions-column">'
        for i, q in enumerate(questions, 1):
            questions_html += build_question_html(q, i)
        questions_html += '</div>'
    else:
        # توزيع على أعمدة متعددة
        for col in range(columns):
            questions_html += '<div class="questions-column">'
            start_idx = col * questions_per_column
            end_idx = min(start_idx + questions_per_column, len(questions))
            
            for i in range(start_idx, end_idx):
                questions_html += build_question_html(questions[i], i + 1)
            
            questions_html += '</div>'
    
    questions_html += '</div>'
    
    # === نموذج الإجابة ===
    answer_key_html = ""
    if include_answers:
        answers_grid = ""
        for i, q in enumerate(questions, 1):
            correct = next((o for o in q.get('options', []) if o.get('is_correct')), None)
            if correct:
                answers_grid += f'''
                <div class="answer-box">
                    <div class="q-num">س{i}</div>
                    <div class="q-ans">{correct.get('letter', '')}</div>
                </div>
                '''
        
        answer_key_html = f"""
        <div class="answer-key">
            <h2>🔑 نموذج الإجابة</h2>
            <div class="answer-grid">
                {answers_grid}
            </div>
        </div>
        """
    
    # === HTML النهائي ===
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        {css}
    </head>
    <body>
        {header_html}
        {title_html}
        {student_html}
        {questions_html}
        {answer_key_html}
    </body>
    </html>
    """
    
    return html
    
    # Answer Key (if needed)
    answer_key_html = ""
    if include_answers:
        rows = ""
        for i, q in enumerate(questions, 1):
            correct = next((o for o in q.get('options', []) if o.get('is_correct')), None)
            if correct:
                rows += f"<tr><td>س{i}</td><td>{correct.get('letter', '')}</td></tr>"
        
        answer_key_html = f"""
        <div class="answer-key">
            <h2>نموذج الإجابة</h2>
            <table class="answer-table">
                <tr><th>السؤال</th><th>الإجابة</th></tr>
                {rows}
            </table>
        </div>
        """
    
    # Final HTML
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        {css}
    </head>
    <body>
        {header_html}
        {title_html}
        {student_html}
        {questions_html}
        {answer_key_html}
    </body>
    </html>
    """
    
    return html


# ==========================================
# حل الاختبار (للطالب)
# ==========================================

@diagnostic_bp.route('/tests/<int:test_id>/start', methods=['POST'])
def start_test(test_id):
    """
    بدء اختبار (للطالب من التطبيق)
    
    POST /api/diagnostic/tests/1/start
    Headers: Authorization: Bearer <token>
    Body: {"student_id": 5}  // أو من التوكن
    """
    try:
        data = request.get_json() or {}
        
        # جلب student_id من التوكن أو الـ body
        student_id = data.get('student_id')
        if not student_id and current_user.is_authenticated:
            student_id = current_user.id
        
        if not student_id:
            return jsonify({'success': False, 'error': 'يجب تحديد الطالب'}), 400
        
        test = DiagnosticTest.query.filter_by(id=test_id, is_active=True).first()
        if not test:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        # التحقق من عدم وجود نتيجة سابقة مكتملة
        existing = DiagnosticResult.query.filter_by(
            diagnostic_test_id=test_id,
            student_id=student_id,
            status='completed'
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': 'لقد أكملت هذا الاختبار مسبقاً',
                'result': existing.to_dict()
            }), 400
        
        # إنشاء أو تحديث نتيجة
        result = DiagnosticResult.query.filter_by(
            diagnostic_test_id=test_id,
            student_id=student_id
        ).first()
        
        if not result:
            result = DiagnosticResult(
                diagnostic_test_id=test_id,
                student_id=student_id,
                total_questions=test.questions_count
            )
            db.session.add(result)
        
        result.started_at = datetime.utcnow()
        result.status = 'in_progress'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم بدء الاختبار',
            'result_id': result.id,
            'test': test.to_dict(include_questions=True)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostic_bp.route('/results/<int:result_id>/submit', methods=['POST'])
def submit_test(result_id):
    """
    تسليم إجابات الاختبار
    
    POST /api/diagnostic/results/1/submit
    {
        "answers": [
            {"question_id": 1, "selected_option_id": 3, "time_spent": 30},
            ...
        ]
    }
    """
    try:
        data = request.get_json() or {}
        answers = data.get('answers', [])
        
        result = DiagnosticResult.query.get(result_id)
        if not result:
            return jsonify({'success': False, 'error': 'النتيجة غير موجودة'}), 404
        
        if result.status == 'completed':
            return jsonify({'success': False, 'error': 'تم تسليم الاختبار مسبقاً'}), 400
        
        test = result.diagnostic_test
        questions = test.questions_data or []
        
        # تصحيح الإجابات
        corrected = []
        correct_count = 0
        
        for ans in answers:
            q_id = ans.get('question_id')
            selected_id = ans.get('selected_option_id')
            
            # البحث عن السؤال
            question = next((q for q in questions if q.get('question_id') == q_id), None)
            
            if question:
                # البحث عن الإجابة الصحيحة
                correct_opt = next((o for o in question.get('options', []) if o.get('is_correct')), None)
                is_correct = str(selected_id) == str(correct_opt.get('id')) if correct_opt else False
                
                if is_correct:
                    correct_count += 1
                
                corrected.append({
                    'question_id': q_id,
                    'question_text': question.get('text', ''),
                    'selected_option_id': selected_id,
                    'correct_option_id': correct_opt.get('id') if correct_opt else None,
                    'is_correct': is_correct,
                    'time_spent': ans.get('time_spent', 0),
                    'topic': question.get('lesson_name', '')
                })
        
        # تحديث النتيجة
        result.answers = corrected
        result.score = correct_count
        result.total_questions = len(corrected)
        result.score_percentage = (correct_count / len(corrected) * 100) if corrected else 0
        result.passed = result.score_percentage >= test.passing_score
        result.completed_at = datetime.utcnow()
        result.time_spent_seconds = sum(a.get('time_spent', 0) for a in corrected)
        result.status = 'completed'
        
        # تحليل النتيجة
        context = {'name': test.lesson.name if test.lesson else (test.unit.name if test.unit else 'عام')}
        analysis = diagnostic_service.analyze_result(result, context, test.test_type)
        
        result.ai_analysis = analysis.get('analysis', '')
        
        # تحديد نقاط القوة والضعف
        weak = [a['topic'] for a in corrected if not a['is_correct'] and a.get('topic')]
        strong = [a['topic'] for a in corrected if a['is_correct'] and a.get('topic')]
        result.weak_topics = list(set(weak))
        result.strong_topics = list(set(strong))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم تسليم الاختبار بنجاح',
            'result': result.to_dict(),
            'analysis': analysis
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Submit Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# المقارنة بين القبلي والبعدي
# ==========================================

@diagnostic_bp.route('/compare', methods=['POST'])
def compare_tests():
    """
    مقارنة نتائج القبلي والبعدي
    
    POST /api/diagnostic/compare
    {
        "pre_test_id": 1,
        "post_test_id": 2,
        "student_id": 5
    }
    """
    try:
        data = request.get_json() or {}
        
        pre_test_id = data.get('pre_test_id')
        post_test_id = data.get('post_test_id')
        student_id = data.get('student_id')
        
        if not all([pre_test_id, post_test_id, student_id]):
            return jsonify({'success': False, 'error': 'بيانات ناقصة'}), 400
        
        # جلب النتائج
        pre_result = DiagnosticResult.query.filter_by(
            diagnostic_test_id=pre_test_id,
            student_id=student_id,
            status='completed'
        ).first()
        
        post_result = DiagnosticResult.query.filter_by(
            diagnostic_test_id=post_test_id,
            student_id=student_id,
            status='completed'
        ).first()
        
        if not pre_result:
            return jsonify({'success': False, 'error': 'لم تكمل الاختبار القبلي'}), 404
        
        if not post_result:
            return jsonify({'success': False, 'error': 'لم تكمل الاختبار البعدي'}), 404
        
        # المقارنة
        pre_test = DiagnosticTest.query.get(pre_test_id)
        context = {'name': pre_test.lesson.name if pre_test.lesson else 'عام'}
        
        comparison_data = diagnostic_service.compare_results(pre_result, post_result, context)
        
        # حفظ المقارنة
        comparison = DiagnosticComparison(
            student_id=student_id,
            pre_test_id=pre_test_id,
            post_test_id=post_test_id,
            pre_result_id=pre_result.id,
            post_result_id=post_result.id,
            pre_score=comparison_data['pre_score'],
            post_score=comparison_data['post_score'],
            improvement=comparison_data['improvement'],
            effectiveness=comparison_data['effectiveness'],
            ai_analysis=comparison_data['analysis']
        )
        db.session.add(comparison)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'comparison': comparison.to_dict(),
            'pre_result': pre_result.to_dict(),
            'post_result': post_result.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# إحصائيات
# ==========================================

@diagnostic_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """إحصائيات الاختبارات التشخيصية"""
    try:
        from sqlalchemy import func
        
        total = DiagnosticTest.query.filter_by(is_active=True).count()
        pre_count = DiagnosticTest.query.filter_by(is_active=True, test_type='pre_test').count()
        post_count = DiagnosticTest.query.filter_by(is_active=True, test_type='post_test').count()
        results_count = DiagnosticResult.query.filter_by(status='completed').count()
        
        avg_improvement = db.session.query(
            func.avg(DiagnosticComparison.improvement)
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_tests': total,
                'pre_tests': pre_count,
                'post_tests': post_count,
                'total_results': results_count,
                'avg_improvement': round(avg_improvement, 1)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostic_bp.route('/student/<int:student_id>/history', methods=['GET'])
def get_student_history(student_id):
    """سجل اختبارات الطالب"""
    try:
        results = DiagnosticResult.query.filter_by(
            student_id=student_id,
            status='completed'
        ).order_by(DiagnosticResult.completed_at.desc()).all()
        
        comparisons = DiagnosticComparison.query.filter_by(
            student_id=student_id
        ).order_by(DiagnosticComparison.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'results': [r.to_dict() for r in results],
            'comparisons': [c.to_dict() for c in comparisons]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# حذف
# ==========================================

@diagnostic_bp.route('/tests/<int:test_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_test(test_id):
    """حذف اختبار"""
    try:
        test = DiagnosticTest.query.filter_by(id=test_id, is_active=True).first()
        
        if not test:
            return jsonify({'success': False, 'error': 'الاختبار غير موجود'}), 404
        
        test.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم حذف الاختبار'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# صفحة الأدمن
# ==========================================

@diagnostic_bp.route('/admin', methods=['GET'])
@login_required
@admin_required
def admin_page():
    """صفحة إدارة الاختبارات التشخيصية"""
    return render_template('diagnostic/admin.html')
