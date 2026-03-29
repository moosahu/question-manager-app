# src/routes/semester_grades.py
"""
API درجات الفترة الفصلية
POST /api/admin/semester-grades          → حفظ + توليد رسالة AI
GET  /api/admin/students/<id>/semester-grades → جلب الدرجات
POST /api/admin/semester-grades/<id>/notify   → إرسال الإشعار
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from src.extensions import db
from src.models.student import Student
from src.models.student_semester_grade import StudentSemesterGrade
from src.services.ai_assistant import ai_assistant
from src.services.fcm_service import send_notification_to_student

semester_grades_bp = Blueprint('semester_grades', __name__, url_prefix='/api/admin')


# ───────────────────────────────────────────
# مساعد: بناء prompt التحفيز
# ───────────────────────────────────────────
def _build_motivation_prompt(student_name: str, grade: float,
                              max_grade: float, period: int) -> str:
    pct = round((grade / max_grade) * 100, 1) if max_grade > 0 else 0
    period_label = 'الأولى' if period == 1 else 'الثانية'

    if pct >= 85:
        level_hint = 'الطالب حصل على درجة ممتازة، شجّعه على الاستمرار والتفوق.'
    elif pct >= 70:
        level_hint = 'الطالب حصل على درجة جيدة، حفّزه على رفع مستواه للوصول إلى التميز.'
    elif pct >= 50:
        level_hint = 'الطالب حصل على درجة مقبولة، شجّعه على المثابرة وتحسين أدائه.'
    else:
        level_hint = 'الطالب يحتاج دعماً، أرسل له رسالة تشجيعية تبثّ فيه الأمل وتحفّزه على المواصلة.'

    return f"""أنت مشجّع تعليمي متخصص في مادة الكيمياء.
اكتب رسالة تحفيزية قصيرة جداً (لا تتجاوز 3 جمل) باللغة العربية الفصيحة المبسّطة
لطالب يدرس الكيمياء اسمه "{student_name}".

معلومات:
- فترة الاختبار: الفترة {period_label}
- درجته: {grade} من {max_grade} ({pct}%)
- {level_hint}

اجعل الرسالة:
- شخصية (تذكر اسمه)
- مرتبطة بالكيمياء (استخدم مصطلح أو استعارة كيميائية لطيفة إن أمكن)
- تنتهي بجملة تحفيزية قوية

اكتب الرسالة فقط بدون مقدمة أو تعليق."""


# ───────────────────────────────────────────
# POST /api/admin/semester-grades
# ───────────────────────────────────────────
@semester_grades_bp.route('/semester-grades', methods=['POST'])
@login_required
def save_semester_grade():
    """حفظ الدرجة + توليد رسالة AI"""
    data = request.get_json(silent=True) or {}

    student_id = data.get('student_id')
    period     = data.get('period')      # 1 أو 2
    grade      = data.get('grade')
    max_grade  = data.get('max_grade')

    # تحقق من المدخلات
    if not all([student_id, period, grade is not None, max_grade]):
        return jsonify({'success': False, 'message': 'بيانات ناقصة'}), 400

    if period not in (1, 2):
        return jsonify({'success': False, 'message': 'الفترة يجب أن تكون 1 أو 2'}), 400

    if max_grade <= 0:
        return jsonify({'success': False, 'message': 'الدرجة الكاملة يجب أن تكون أكبر من صفر'}), 400

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'الطالب غير موجود'}), 404

    # توليد رسالة AI
    ai_message = None
    try:
        prompt = _build_motivation_prompt(student.name, grade, max_grade, period)
        ai_assistant._ensure_configured()
        ai_message = ai_assistant._generate(prompt)
        if ai_message:
            ai_message = ai_message.strip()
    except Exception as e:
        print(f'⚠️ خطأ في توليد رسالة AI: {e}')

    # حفظ أو تحديث الدرجة
    existing = StudentSemesterGrade.get_grade(student_id, period)
    if existing:
        existing.grade      = grade
        existing.max_grade  = max_grade
        existing.ai_message = ai_message
        existing.notification_sent = False   # إعادة تعيين ليرسل مجدداً
        existing.updated_at = datetime.utcnow()
        record = existing
    else:
        record = StudentSemesterGrade(
            student_id  = student_id,
            period      = period,
            grade       = grade,
            max_grade   = max_grade,
            ai_message  = ai_message,
        )
        db.session.add(record)

    db.session.commit()

    return jsonify({
        'success':    True,
        'message':    'تم حفظ الدرجة بنجاح',
        'grade_id':   record.id,
        'ai_message': ai_message or '',
        'percentage': record.percentage(),
    })


# ───────────────────────────────────────────
# GET /api/admin/students/<id>/semester-grades
# ───────────────────────────────────────────
@semester_grades_bp.route('/students/<int:student_id>/semester-grades', methods=['GET'])
@login_required
def get_semester_grades(student_id):
    """جلب درجات الطالب للفترتين"""
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'الطالب غير موجود'}), 404

    grades = StudentSemesterGrade.get_student_grades(student_id)
    return jsonify({
        'success': True,
        'student': {'id': student.id, 'name': student.name},
        'grades':  [g.to_dict() for g in grades],
    })


# ───────────────────────────────────────────
# POST /api/admin/semester-grades/<id>/notify
# ───────────────────────────────────────────
@semester_grades_bp.route('/semester-grades/<int:grade_id>/notify', methods=['POST'])
@login_required
def send_grade_notification(grade_id):
    """إرسال إشعار الدرجة للطالب"""
    data = request.get_json(silent=True) or {}

    record = StudentSemesterGrade.query.get(grade_id)
    if not record:
        return jsonify({'success': False, 'message': 'السجل غير موجود'}), 404

    student = Student.query.get(record.student_id)
    if not student:
        return jsonify({'success': False, 'message': 'الطالب غير موجود'}), 404

    if not student.fcm_token:
        return jsonify({'success': False, 'message': 'الطالب لا يملك FCM token'}), 400

    period_label = 'الأولى' if record.period == 1 else 'الثانية'
    pct          = record.percentage()

    # يقبل رسالة معدّلة من الأدمن، وإلا يستخدم رسالة AI
    custom_message = data.get('message', '').strip()
    body_text      = custom_message if custom_message else (record.ai_message or '')

    title = f'درجتك في اختبار الفترة {period_label} 📊'
    body  = f'{record.grade}/{record.max_grade} ({pct}%)\n{body_text}'

    success = send_notification_to_student(
        student=student,
        title=title,
        body=body,
        data={
            'type':      'semester_grade',
            'period':    str(record.period),
            'grade':     str(record.grade),
            'max_grade': str(record.max_grade),
            'grade_id':  str(record.id),
        }
    )

    if success:
        record.notification_sent = True
        record.notified_at       = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم إرسال الإشعار بنجاح'})
    else:
        return jsonify({'success': False, 'message': 'فشل إرسال الإشعار'}), 500
