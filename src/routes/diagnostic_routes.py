# src/routes/diagnostic_routes.py
"""
API للاختبارات التشخيصية
- متوافق مع Flutter
- توليد اختبارات قبلية/بعدية
- استخراج PDF
"""

from flask import Blueprint, request, jsonify, send_file, render_template, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from functools import wraps
import io
import os
import base64

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

# ✅ استيراد موديل الإشعارات لحفظها في قاعدة البيانات
try:
    from src.models.notification import Notification
except ImportError:
    try:
        from models.notification import Notification
    except:
        Notification = None
        print("⚠️ Notification model غير متوفر - الإشعارات لن تُحفظ في قاعدة البيانات")

# ✅ خدمة الإشعارات
try:
    from src.services.notification_service import NotificationService
except ImportError:
    try:
        from services.notification_service import NotificationService
    except:
        NotificationService = None
        print("⚠️ NotificationService غير متوفر")

diagnostic_bp = Blueprint('diagnostic', __name__, url_prefix='/api/diagnostic')


def _save_notification_to_db(student_id, title, message, notification_type='reminder', data=None):
    """حفظ الإشعار في قاعدة البيانات ليظهر في صفحة الإشعارات"""
    try:
        if Notification is None:
            print(f"⚠️ Notification model غير متوفر - لن يتم حفظ الإشعار في DB")
            return False
        
        notification = Notification(
            student_id=student_id,
            title=title,
            message=message,
            notification_type=notification_type,
            type=notification_type,  # الموديل فيه حقلين: type و notification_type
            is_read=False,
            status='delivered',
            sent_at=datetime.utcnow(),
        )
        
        # إضافة data إذا موجودة
        if data:
            notification.data = data
        
        db.session.add(notification)
        return True
    except Exception as e:
        print(f"❌ خطأ في حفظ الإشعار في DB: {e}")
        return False



def convert_saudi_to_utc(dt_string):
    """تحويل وقت من السعودية (UTC+3) إلى UTC"""
    try:
        # إزالة Z أو timezone info
        dt_string = dt_string.replace('Z', '').replace('+00:00', '')
        
        # parse التاريخ
        dt = datetime.fromisoformat(dt_string)
        
        # السعودية = UTC + 3، نطرح 3 ساعات
        dt_utc = dt - timedelta(hours=3)
        
        print(f"⏰ Converted {dt_string} (Saudi) → {dt_utc} (UTC)")
        return dt_utc
    except Exception as e:
        print(f"⚠️ Error converting timezone: {e}")
        # fallback - استخدم الوقت كما هو
        return datetime.fromisoformat(dt_string.replace('Z', ''))


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
                    'grade': header.grade or ""
                }
            
            # جلب الشعار من الملف
            import os
            import base64
            logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_base64 = base64.b64encode(f.read()).decode('utf-8')
                    header_settings['logo_base64'] = f"data:image/png;base64,{logo_base64}"
        except Exception as e:
            print(f"⚠️ Error loading header settings: {e}")
        
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
            gap: 6px 20px;
        }}
        /* ترتيب الخيارات: أ يمين، ب يسار */
        .options-grid .option:nth-child(1) {{ order: 1; }}
        .options-grid .option:nth-child(2) {{ order: 2; }}
        .options-grid .option:nth-child(3) {{ order: 3; }}
        .options-grid .option:nth-child(4) {{ order: 4; }}
        
        /* === الخيارات - أفقي === */
        .options-horizontal {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
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
            padding: 5px 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 12px;
            background: white;
            text-align: right;
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
        logo_base64 = header_settings.get('logo_base64', '')
        if logo_base64:
            logo_html = f'<img src="{logo_base64}" style="max-width: 60px; max-height: 60px;">'
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
    # === الأحرف العربية للخيارات ===
    arabic_letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
    
    def build_question_html(q, num):
        q_text = q.get('text', '')
        options_list = q.get('options', [])
        
        # بناء الخيارات بترتيب صحيح للشبكة RTL
        # الترتيب المطلوب في HTML: [ب، أ، د، ج] ليظهر [أ، ب] في الصف الأول و[ج، د] في الثاني
        if options_layout == 'grid' and len(options_list) >= 4:
            # إعادة ترتيب: نضع ب قبل أ، د قبل ج
            reordered = [
                options_list[1] if len(options_list) > 1 else None,  # ب
                options_list[0] if len(options_list) > 0 else None,  # أ
                options_list[3] if len(options_list) > 3 else None,  # د
                options_list[2] if len(options_list) > 2 else None,  # ج
            ]
            reordered = [o for o in reordered if o]  # إزالة None
            letter_order = ['ب', 'أ', 'د', 'ج']
        else:
            reordered = options_list
            letter_order = arabic_letters
        
        options_html = ""
        for idx, opt in enumerate(reordered):
            if options_layout == 'grid' and len(options_list) >= 4:
                letter = letter_order[idx] if idx < len(letter_order) else str(idx + 1)
            else:
                letter = arabic_letters[idx] if idx < len(arabic_letters) else str(idx + 1)
            
            text = opt.get('text', '')
            is_correct = opt.get('is_correct', False)
            
            correct_class = ' correct' if include_answers and is_correct else ''
            check_mark = ' ✓' if include_answers and is_correct else ''
            
            options_html += f'''
            <div class="option{correct_class}">{letter}- {text}{check_mark}</div>
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
        
        # ✅ استخرج student_id من session cookie (كما في assigned tests)
        student_id = None
        
        # 1. جرّب من session cookie
        for cookie_name, cookie_value in request.cookies.items():
            if cookie_name.startswith('student_session_'):
                username = cookie_name.replace('student_session_', '')
                student = Student.query.filter_by(username=username).first()
                if student:
                    student_id = student.id
                    print(f"✅ Got student_id from session cookie: {student_id} (username: {username})")
                    break
        
        # 2. جرّب من body
        if not student_id:
            student_id = data.get('student_id')
        
        # 3. جرّب من current_user
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
        
        # جلب الأسئلة
        questions = []
        questions = test.questions_data or []
        
        return jsonify({
            'success': True,
            'message': 'تم بدء الاختبار',
            'result_id': result.id,
            'questions': questions,
            'time_limit_minutes': test.time_limit_minutes
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
        print(f"📝 Submit - result_id: {result_id}, answers: {len(answers)}")
        
        result = DiagnosticResult.query.get(result_id)
        if not result:
            return jsonify({'success': False, 'error': 'النتيجة غير موجودة'}), 404
        
        if result.status == 'completed':
            return jsonify({'success': False, 'error': 'تم تسليم الاختبار مسبقاً'}), 400
        
        test = result.test
        questions = test.questions_data or []
        
        # تصحيح الإجابات
        corrected = []
        correct_count = 0
        
        # ✅ استخدم index-based correction
        for i, ans in enumerate(answers):
            selected_answer = ans.get('selected_answer')  # index من Flutter
            
            # استخدام index للوصول للسؤال
            if i >= len(questions):
                continue
            
            question = questions[i]
            options = question.get('options', [])
            
            # البحث عن الإجابة الصحيحة بالـ index
            correct_index = None
            for opt_idx, opt in enumerate(options):
                if opt.get('is_correct'):
                    correct_index = opt_idx
                    break
            
            is_correct = (selected_answer == correct_index) if selected_answer is not None else False
            
            if is_correct:
                correct_count += 1
            
            corrected.append({
                'question_id': i,
                'question_text': question.get('text', question.get('question_text', '')),
                'selected_answer': selected_answer,
                'correct_answer': correct_index,
                'is_correct': is_correct,
                'time_spent': ans.get('time_spent', 0),
                'topic': question.get('lesson_name', '')
            })
        
        # تحديث النتيجة
        result.answers = corrected
        result.score = correct_count
        result.total_questions = len(corrected)
        result.correct_answers = correct_count
        result.percentage = (correct_count / len(corrected) * 100) if corrected else 0
        result.score_percentage = result.percentage
        result.passed = result.score_percentage >= test.passing_score
        result.completed_at = datetime.utcnow()
        result.time_spent_seconds = sum(a.get('time_spent', 0) for a in corrected)
        result.status = 'completed'
        
        # تحليل النتيجة
        context = {'name': test.lesson_name or test.unit_name or 'عام'}
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
            test_id=pre_test_id,
            student_id=student_id,
            status='completed'
        ).first()
        
        post_result = DiagnosticResult.query.filter_by(
            test_id=post_test_id,
            student_id=student_id,
            status='completed'
        ).first()
        
        if not pre_result:
            return jsonify({'success': False, 'error': 'لم تكمل الاختبار القبلي'}), 404
        
        if not post_result:
            return jsonify({'success': False, 'error': 'لم تكمل الاختبار البعدي'}), 404
        
        # المقارنة
        pre_test = DiagnosticTest.query.get(pre_test_id)
        context = {'name': pre_test.lesson_name or 'عام'}
        
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


# =====================================================
# ✅ Routes الجدولة والإسناد (مضافة - جديدة)
# =====================================================

@diagnostic_bp.route('/scheduled', methods=['GET'])
@login_required
@admin_required
def get_scheduled_tests():
    """جلب الاختبارات المجدولة"""
    try:
        tests = DiagnosticTest.query.filter_by(
            is_scheduled=True,
            is_active=True
        ).order_by(DiagnosticTest.scheduled_start.desc()).all()
        
        # تحديث حالة كل اختبار
        for test in tests:
            if hasattr(test, 'update_schedule_status'):
                test.update_schedule_status()
        db.session.commit()
        
        return jsonify({
            'scheduled_tests': [test.to_dict() for test in tests]
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting scheduled tests: {e}")
        return jsonify({'error': str(e)}), 500


@diagnostic_bp.route('/assign', methods=['POST'])
@login_required
@admin_required
def assign_test():
    """إسناد اختبار لطلاب مع جدولة - محدث لدعم الإرسال المتعدد والصفوف الدراسية"""
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        student_ids = data.get('student_ids')
        grade = data.get('grade')  # ✅ جديد: الصف الدراسي
        scheduled_start = data.get('scheduled_start')
        scheduled_end = data.get('scheduled_end')
        time_limit = data.get('time_limit_minutes', 30)
        send_notification = data.get('send_notification', True)
        append_students = data.get('append_students', False)  # ✅ جديد: إضافة بدلاً من الاستبدال
        
        test = DiagnosticTest.query.get(test_id)
        if not test:
            return jsonify({'error': 'Test not found'}), 404
        
        # تحضير قائمة الطلاب
        student_ids_list = []
        
        if grade:
            # ✅ طلاب صف دراسي محدد (أولوية عليا)
            students = Student.query.filter_by(is_active=True, grade=grade).all()
            student_ids_list = [s.id for s in students]
            print(f"✅ تم اختيار {len(student_ids_list)} طالب من الصف {grade}")
        elif student_ids == 'all':
            # جميع الطلاب النشطين
            students = Student.query.filter_by(is_active=True).all()
            student_ids_list = [s.id for s in students]
            print(f"✅ تم اختيار جميع الطلاب: {len(student_ids_list)} طالب")
        else:
            # طلاب محددين
            student_ids_list = student_ids if isinstance(student_ids, list) else [student_ids]
            print(f"✅ تم اختيار {len(student_ids_list)} طالب محدد")
        
        # ✅ جديد: دعم الإضافة بدلاً من الاستبدال
        if append_students and test.assigned_students:
            # إضافة الطلاب الجدد للقائمة الحالية
            existing_ids = set(test.assigned_students)
            new_ids = set(student_ids_list)
            student_ids_list = list(existing_ids.union(new_ids))
            print(f"✅ تم إضافة طلاب جدد. الإجمالي: {len(student_ids_list)}")
        else:
            # استبدال القائمة بالكامل
            print(f"✅ تم استبدال قائمة الطلاب. العدد: {len(student_ids_list)}")
        
        # تحديث الاختبار
        test.is_scheduled = True
        test.scheduled_start = convert_saudi_to_utc(scheduled_start)
        test.scheduled_end = convert_saudi_to_utc(scheduled_end)
        test.assigned_students = student_ids_list
        test.time_limit_minutes = time_limit
        test.schedule_status = 'pending'
        
        if hasattr(test, 'update_schedule_status'):
            test.update_schedule_status()
        
        db.session.commit()
        
        # إرسال إشعارات
        if send_notification and NotificationService:
            try:
                students = Student.query.filter(
                    Student.id.in_(student_ids_list),
                    Student.fcm_token.isnot(None)
                ).all()
                
                # ✅ استخدام NotificationService
                success_count = 0
                
                # ✅ تنسيق رسالة FCM بشكل مقروء
                try:
                    from datetime import datetime as dt_parse
                    start_dt = dt_parse.fromisoformat(scheduled_start.replace('Z', ''))
                    end_dt = dt_parse.fromisoformat(scheduled_end.replace('Z', ''))
                    start_hour = start_dt.strftime('%I:%M')
                    start_period = 'م' if start_dt.hour >= 12 else 'ص'
                    end_hour = end_dt.strftime('%I:%M')
                    end_period = 'م' if end_dt.hour >= 12 else 'ص'
                    fcm_body = f'{test.title}\n⏰ من {start_hour} {start_period} إلى {end_hour} {end_period}'
                except:
                    fcm_body = f'{test.title}'
                
                for student in students:
                    if student.fcm_token:
                        result = NotificationService.send_fcm_notification(
                            student.fcm_token,
                            '📝 اختبار تشخيصي جديد',
                            fcm_body,
                            {
                                'type': 'diagnostic_test',
                                'test_id': str(test.id),
                                'scheduled_start': scheduled_start,
                                'scheduled_end': scheduled_end,
                                'time_limit_minutes': str(test.time_limit_minutes)
                            }
                        )
                        if result:
                            success_count += 1
                
                # ✅ حفظ الإشعار في قاعدة البيانات لكل الطلاب المعينين (ليظهر في صفحة الإشعارات)
                db_save_count = 0
                notification_title = '📝 اختبار تشخيصي جديد'
                
                # ✅ تنسيق الوقت بشكل مقروء
                try:
                    from datetime import datetime as dt_parse
                    start_dt = dt_parse.fromisoformat(scheduled_start.replace('Z', ''))
                    end_dt = dt_parse.fromisoformat(scheduled_end.replace('Z', ''))
                    
                    # تنسيق عربي مقروء
                    start_hour = start_dt.strftime('%I:%M')
                    start_period = 'مساءً' if start_dt.hour >= 12 else 'صباحاً'
                    end_hour = end_dt.strftime('%I:%M')
                    end_period = 'مساءً' if end_dt.hour >= 12 else 'صباحاً'
                    date_str = f"{start_dt.day}/{start_dt.month}/{start_dt.year}"
                    
                    notification_message = (
                        f'تم تعيين اختبار: {test.title}\n\n'
                        f'📅 التاريخ: {date_str}\n'
                        f'⏰ من {start_hour} {start_period} إلى {end_hour} {end_period}\n'
                        f'⏱ المدة: {test.time_limit_minutes} دقيقة'
                    )
                except:
                    notification_message = f'تم تعيين اختبار: {test.title}'
                
                notification_data = {
                    'type': 'diagnostic_test',
                    'test_id': str(test.id),
                }
                
                for sid in student_ids_list:
                    if _save_notification_to_db(
                        student_id=sid,
                        title=notification_title,
                        message=notification_message,
                        notification_type='reminder',
                        data=notification_data
                    ):
                        db_save_count += 1
                
                db.session.commit()
                print(f"✅ تم إرسال {success_count}/{len(students)} إشعار FCM")
                print(f"✅ تم حفظ {db_save_count}/{len(student_ids_list)} إشعار في قاعدة البيانات")
                
                if success_count > 0:
                    test.notification_sent = True
                    test.notification_sent_at = datetime.utcnow()
                    db.session.commit()
                
            except Exception as e:
                print(f"⚠️ Error sending notifications: {e}")
        
        return jsonify({
            'message': 'Test assigned successfully',
            'test': test.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error assigning test: {e}")
        return jsonify({'error': str(e)}), 500


@diagnostic_bp.route('/student/assigned', methods=['GET', 'POST'])
def get_student_assigned_tests():
    """اختبارات الطالب المخصصة (للتطبيق والويب)"""
    try:
        # جرب جميع الطرق للحصول على student_id
        student_id = None
        
        # 1. من query parameter (GET)
        student_id = request.args.get('student_id', type=int)
        
        # 2. من body (POST)
        if not student_id and request.method == 'POST':
            data = request.get_json() or {}
            student_id = data.get('student_id')
            if student_id:
                student_id = int(student_id)
        
        # 3. من headers
        if not student_id:
            header_id = request.headers.get('X-Student-ID') or request.headers.get('Student-ID')
            if header_id:
                try:
                    student_id = int(header_id)
                except:
                    pass
        
        # 4. من cookies (للتطبيق Flutter)
        if not student_id:
            # جرب cookie مباشر
            cookie_id = request.cookies.get('student_id')
            if cookie_id:
                try:
                    student_id = int(cookie_id)
                    print(f"📱 Got student_id from cookie: {student_id}")
                except:
                    pass
            
            # جرب استخراج من session cookie
            if not student_id:
                for cookie_name, cookie_value in request.cookies.items():
                    # ابحث عن pattern: student_session_{username}
                    if cookie_name.startswith('student_session_'):
                        print(f"🔍 Found session cookie: {cookie_name}")
                        # جرب query الـ database
                        try:
                            username = cookie_name.replace('student_session_', '')
                            student = Student.query.filter_by(username=username).first()
                            if student:
                                student_id = student.id
                                print(f"✅ Got student_id from session cookie: {student_id} (username: {username})")
                                break
                        except Exception as e:
                            print(f"⚠️ Error extracting from session cookie: {e}")
                            pass
        
        # 5. من session (Flask session)
        if not student_id:
            from flask import session
            session_id = session.get('student_id') or session.get('user_id')
            if session_id:
                try:
                    student_id = int(session_id)
                    print(f"📱 Got student_id from session: {student_id}")
                except:
                    pass
        
        # 6. من current_user (للويب)
        if not student_id:
            try:
                if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                    student_id = current_user.id
                    print(f"📱 Got student_id from current_user: {student_id}")
            except:
                pass
        
        print(f"📱 Getting assigned tests - Methods tried:")
        print(f"  - Query param: {request.args.get('student_id')}")
        print(f"  - Body: {request.get_json() if request.method == 'POST' else 'N/A'}")
        print(f"  - Header X-Student-ID: {request.headers.get('X-Student-ID')}")
        print(f"  - Header Student-ID: {request.headers.get('Student-ID')}")
        print(f"  - Cookie student_id: {request.cookies.get('student_id')}")
        print(f"  - All cookies: {list(request.cookies.keys())}")
        print(f"  - Final student_id: {student_id}")
        
        if not student_id:
            return jsonify({
                'success': False,
                'error': 'student_id required',
                'message_ar': 'يرجى تحديث التطبيق أو إرسال student_id',
                'hint': 'Send student_id as: ?student_id=7 (query parameter)',
                'fix_flutter': 'في diagnostic_service.dart أضف: ?student_id=$studentId في الـ URL',
                'example_url': '/api/diagnostic/student/assigned?student_id=7',
                'debug': {
                    'cookies_received': list(request.cookies.keys()),
                    'all_headers': {k: v for k, v in request.headers.items() if k.lower() not in ['cookie', 'authorization']}
                }
            }), 400
        
        print(f"✅ Getting assigned tests for student {student_id}")
        
        tests = DiagnosticTest.query.filter(
            DiagnosticTest.is_scheduled == True,
            DiagnosticTest.is_active == True
        ).all()
        
        print(f"📋 Found {len(tests)} scheduled tests")
        
        # فلتر الاختبارات حسب الطالب
        assigned_tests = []
        for test in tests:
            print(f"🔍 Test {test.id}: assigned_students={test.assigned_students}")
            
            # تحقق من الإسناد
            is_assigned = False
            
            if not test.assigned_students or test.assigned_students == 'all':
                is_assigned = True
            elif test.assigned_students:
                if isinstance(test.assigned_students, list):
                    is_assigned = student_id in test.assigned_students
                elif isinstance(test.assigned_students, str):
                    import json
                    try:
                        students_list = json.loads(test.assigned_students)
                        is_assigned = student_id in students_list
                    except:
                        is_assigned = str(student_id) in test.assigned_students or (student_id == int(test.assigned_students) if test.assigned_students.isdigit() else False)
            
            print(f"  → Assigned: {is_assigned}")
            
            if is_assigned:
                is_available = True
                if test.scheduled_start and test.scheduled_end:
                    now = datetime.utcnow()
                    
                    # إزالة timezone للمقارنة الصحيحة
                    start = test.scheduled_start.replace(tzinfo=None) if test.scheduled_start.tzinfo else test.scheduled_start
                    end = test.scheduled_end.replace(tzinfo=None) if test.scheduled_end.tzinfo else test.scheduled_end
                    
                    is_available = start <= now <= end
                    
                    print(f"  → Available (time): {is_available}")
                    print(f"     Now (UTC): {now}")
                    print(f"     Start: {start}")
                    print(f"     End: {end}")
                
                if is_available:
                    assigned_tests.append(test)
        
        print(f"✅ Returning {len(assigned_tests)} assigned tests")
        
        return jsonify({
            'success': True,
            'assigned_tests': [test.to_dict() for test in assigned_tests]
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting student tests: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostic_bp.route('/tests/<int:test_id>/cancel-schedule', methods=['POST'])
@login_required
@admin_required
def cancel_schedule(test_id):
    """إلغاء جدولة اختبار"""
    try:
        test = DiagnosticTest.query.get(test_id)
        if not test:
            return jsonify({'error': 'Test not found'}), 404
        
        test.is_scheduled = False
        test.schedule_status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'message': 'Schedule cancelled successfully',
            'test': test.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error cancelling schedule: {e}")
        return jsonify({'error': str(e)}), 500


@diagnostic_bp.route('/tests/<int:test_id>/send-notification', methods=['POST'])
@login_required
@admin_required
def resend_notification(test_id):
    """إعادة إرسال إشعار"""
    try:
        test = DiagnosticTest.query.get(test_id)
        if not test:
            return jsonify({'error': 'Test not found'}), 404
        
        if not test.is_scheduled or not test.assigned_students:
            return jsonify({'error': 'Test not scheduled or no students assigned'}), 400
        
        try:
            if not NotificationService:
                return jsonify({'error': 'Notification service not available'}), 500
            
            students = Student.query.filter(
                Student.id.in_(test.assigned_students),
                Student.fcm_token.isnot(None)
            ).all()
            
            # ✅ استخدام NotificationService
            success_count = 0
            for student in students:
                if student.fcm_token:
                    result = NotificationService.send_fcm_notification(
                        student.fcm_token,
                        '📝 اختبار تشخيصي',
                        f'{test.title}',
                        {
                            'type': 'diagnostic_test',
                            'test_id': str(test.id)
                        }
                    )
                    if result:
                        success_count += 1
            
            # ✅ حفظ الإشعار في قاعدة البيانات لكل الطلاب المعينين
            db_save_count = 0
            for sid in test.assigned_students:
                if _save_notification_to_db(
                    student_id=sid,
                    title='📝 تذكير: اختبار تشخيصي',
                    message=f'{test.title}',
                    notification_type='reminder',
                    data={'type': 'diagnostic_test', 'test_id': str(test.id)}
                ):
                    db_save_count += 1
            
            test.notification_sent = True
            test.notification_sent_at = datetime.utcnow()
            db.session.commit()
            print(f"✅ تم حفظ {db_save_count} إشعار في قاعدة البيانات (إعادة إرسال)")
            
            return jsonify({
                'message': f'Notifications sent to {success_count} students',
                'success_count': success_count
            }), 200
            
        except Exception as e:
            print(f"❌ Error sending notifications: {e}")
            return jsonify({'error': str(e)}), 500
        
    except Exception as e:
        print(f"❌ Error in resend_notification: {e}")
        return jsonify({'error': str(e)}), 500


# =====================================================
# ✅ Routes مساعدة للصفحة (مضافة - جديدة)
# =====================================================

@diagnostic_bp.route('/lessons', methods=['GET'])
def get_lessons():
    """جلب قائمة الدروس"""
    try:
        lessons = Lesson.query.filter_by(is_active=True).all()
        return jsonify({
            'lessons': [{'id': l.id, 'name': l.name, 'unit_id': l.unit_id} for l in lessons]
        }), 200
    except Exception as e:
        print(f"❌ Error getting lessons: {e}")
        return jsonify({'error': str(e)}), 500


@diagnostic_bp.route('/students', methods=['GET'])
def get_students():
    """جلب قائمة الطلاب"""
    try:
        students = Student.query.filter_by(is_active=True).all()
        return jsonify({
            'students': [{'id': s.id, 'name': s.name, 'grade': getattr(s, 'grade', None)} for s in students]
        }), 200
    except Exception as e:
        print(f"❌ Error getting students: {e}")
        return jsonify({'error': str(e)}), 500


@diagnostic_bp.route('/grades', methods=['GET'])
def get_grades():
    """جلب قائمة الصفوف الدراسية المتوفرة"""
    try:
        # جلب جميع الصفوف الفريدة من جدول الطلاب
        grades_query = db.session.query(Student.grade).filter(
            Student.is_active == True,
            Student.grade.isnot(None),
            Student.grade != ''
        ).distinct().all()
        
        grades = [g[0] for g in grades_query if g[0]]
        
        # حساب عدد الطلاب لكل صف
        grades_with_count = []
        for grade in grades:
            count = Student.query.filter_by(is_active=True, grade=grade).count()
            grades_with_count.append({
                'grade': grade,
                'count': count
            })
        
        return jsonify({
            'success': True,
            'grades': grades_with_count
        }), 200
    except Exception as e:
        print(f"❌ Error getting grades: {e}")
        return jsonify({'error': str(e)}), 500


# ✅ تحسين route الإحصائيات (معدل)
@diagnostic_bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def get_diagnostic_stats():
    """إحصائيات الاختبارات التشخيصية"""
    try:
        total_tests = DiagnosticTest.query.filter_by(is_active=True).count()
        
        stats = {
            'total_tests': total_tests,
            'pre_tests': DiagnosticTest.query.filter_by(
                test_type='pre_test', 
                is_active=True
            ).count(),
            'post_tests': DiagnosticTest.query.filter_by(
                test_type='post_test',
                is_active=True
            ).count(),
            'scheduled_tests': 0  # قيمة افتراضية
        }
        
        # إحصائيات الجدولة (إذا كانت متوفرة)
        try:
            stats['scheduled_tests'] = DiagnosticTest.query.filter_by(
                is_scheduled=True,
                is_active=True
            ).count()
        except:
            pass
        
        return jsonify(stats), 200
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return jsonify({
            'total_tests': 0,
            'pre_tests': 0,
            'post_tests': 0,
            'scheduled_tests': 0
        }), 200


print("🧪 Diagnostic Tests System with Scheduling - Loaded successfully!")


@diagnostic_bp.route('/results', methods=['GET'])
def get_all_results():
    """جلب جميع النتائج"""
    try:
        # جلب آخر 50 نتيجة
        results = DiagnosticResult.query\
            .order_by(DiagnosticResult.completed_at.desc())\
            .limit(50)\
            .all()
        
        results_data = []
        for r in results:
            try:
                result_dict = r.to_dict()
                # إضافة معلومات الاختبار
                if r.test:
                    result_dict['test_title'] = r.test.title
                    result_dict['test_type'] = r.test.test_type
                
                # جلب اسم الطالب
                if r.student_id:
                    student = Student.query.get(r.student_id)
                    if student:
                        result_dict['student_name'] = student.name
                
                results_data.append(result_dict)
            except Exception as e:
                print(f"⚠️ Error processing result {r.id}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'results': results_data,
            'count': len(results_data)
        })
    except Exception as e:
        print(f"❌ Error getting results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

