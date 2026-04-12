# src/routes/semester_grades.py
"""
API درجات الفترة الفصلية
POST /api/admin/semester-grades               → حفظ + توليد رسالة AI (فردي)
POST /api/admin/semester-grades/bulk          → حفظ + AI + إشعار لكل الطلاب دفعة
GET  /api/admin/students/<id>/semester-grades → جلب الدرجات
POST /api/admin/semester-grades/<id>/notify   → إرسال الإشعار (فردي)
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
import os

from src.extensions import db
from src.models.student import Student
from src.models.student_semester_grade import StudentSemesterGrade
from src.models.notification import Notification, StudentNotification
from src.services.ai_assistant import ai_assistant


def _sync_to_new_system(student_id, semester_number, grade, max_grade, admin_id=None):
    """مزامنة: لما يُحفظ StudentSemesterGrade → يُنشأ/يُحدَّث GradeEntry في فئة الاختبار"""
    try:
        from src.models.grade_period import GradePeriod
        from src.models.grade_config import GradeConfig
        from src.models.grade_entry import GradeEntry

        period = GradePeriod.query.filter_by(
            semester_number=semester_number, is_active=True
        ).first()
        if not period:
            return

        # فئة الاختبار = الفئة ذات أعلى درجة في الفترة
        exam_cat = GradeConfig.query.filter_by(
            period_id=period.id, is_active=True
        ).order_by(GradeConfig.max_score.desc()).first()
        if not exam_cat:
            return

        score_ratio = max(0.0, min(1.0, grade / max_grade)) if max_grade > 0 else 0.0
        label = f"اختبار الفترة {'الأولى' if semester_number == 1 else 'الثانية'}"

        existing = GradeEntry.query.filter_by(
            student_id=student_id,
            category_id=exam_cat.id,
            entry_label=label,
        ).first()

        if existing:
            existing.score = score_ratio
        else:
            db.session.add(GradeEntry(
                student_id=student_id,
                admin_id=admin_id,
                category_id=exam_cat.id,
                entry_label=label,
                score=score_ratio,
                entry_date=date.today(),
            ))
    except Exception as e:
        print(f"⚠️ _sync_to_new_system error: {e}")

# ── Firebase Admin SDK (نفس نمط notification_admin_routes.py) ──
FCM_ENABLED = False
try:
    import firebase_admin
    from firebase_admin import messaging
    try:
        firebase_admin.get_app()
        FCM_ENABLED = True
    except ValueError:
        import json
        from firebase_admin import credentials
        firebase_config = os.getenv('FIREBASE_CONFIG')
        if firebase_config:
            try:
                cred = credentials.Certificate(json.loads(firebase_config))
                firebase_admin.initialize_app(cred)
                FCM_ENABLED = True
            except Exception:
                pass
except ImportError:
    pass

semester_grades_bp = Blueprint('semester_grades', __name__, url_prefix='/api/admin')


# ─────────────────────────────────────────────
# مساعد: إرسال FCM عبر Firebase Admin SDK
# ─────────────────────────────────────────────
def _send_fcm(student, title: str, body: str, data: dict):
    """إرسال إشعار واحد عبر Firebase Admin SDK.
    Returns: 'sent' | 'no_fcm' | 'no_token' | 'expired_token' | 'error'
    """
    if not FCM_ENABLED:
        print("⚠️ FCM not enabled")
        return 'no_fcm'
    if not getattr(student, 'fcm_token', None):
        print(f"⚠️ الطالب {student.name} لا يملك FCM token")
        return 'no_token'
    try:
        # حساب badge (إشعارات غير مقروءة)
        try:
            from src.models.student_notification import StudentNotification
            badge = StudentNotification.query.filter_by(
                student_id=student.id, is_read=False
            ).count() + 1
        except Exception:
            badge = 1

        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=student.fcm_token,
            data={k: str(v) for k, v in data.items()},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='chem_tahsili_channel',
                    sound='default',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default', badge=badge),
                ),
            ),
        )
        messaging.send(msg)
        print(f"✅ FCM sent to {student.name}")
        return 'sent'
    except messaging.UnregisteredError:
        print(f"⚠️ Expired/invalid FCM token for {student.name} — clearing from DB")
        student.fcm_token = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return 'expired_token'
    except Exception as e:
        print(f"❌ FCM error for {student.name}: {e}")
        return 'error'


# ─────────────────────────────────────────────
# مساعد: حفظ الإشعار في قاعدة البيانات
# ─────────────────────────────────────────────
def _save_db_notification(student, title: str, body: str, notif_data: dict) -> int | None:
    """يحفظ Notification + StudentNotification ويرجع notification_id"""
    try:
        notif = Notification(
            title=title,
            message=body,
            body=body,
            student_id=student.id,
            type='semester_grade',
            notification_type='semester_grade',
            is_read=False,
            created_by_admin=True,
            data=notif_data,
        )
        db.session.add(notif)
        db.session.flush()  # نحتاج الـ ID

        sn = StudentNotification(
            student_id=student.id,
            notification_id=notif.id,
            is_read=False,
        )
        db.session.add(sn)
        return notif.id
    except Exception as e:
        print(f'⚠️ DB notification error for {student.name}: {e}')
        return None


# ─────────────────────────────────────────────
# مساعد: بناء prompt التحفيز
# ─────────────────────────────────────────────
def _build_motivation_prompt(student_name: str, grade: float,
                              max_grade: float, period: int,
                              prev_grade: float = None,
                              prev_max_grade: float = None) -> str:
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

    # بناء سياق المقارنة للفترة الثانية
    comparison_block = ''
    if period == 2 and prev_grade is not None and prev_max_grade and prev_max_grade > 0:
        prev_pct = round((prev_grade / prev_max_grade) * 100, 1)
        diff = pct - prev_pct
        if diff > 5:
            trend = f'تحسّن بمقدار {round(diff, 1)}% عن الفترة الأولى ({prev_grade}/{prev_max_grade}) — وهذا إنجاز يستحق الإشادة.'
        elif diff < -5:
            trend = f'انخفض بمقدار {round(abs(diff), 1)}% عن الفترة الأولى ({prev_grade}/{prev_max_grade}) — يحتاج تشجيعاً ودعماً لاستعادة مستواه.'
        else:
            trend = f'حافظ على نفس مستواه تقريباً مقارنةً بالفترة الأولى ({prev_grade}/{prev_max_grade}) — شجّعه على الارتقاء أكثر.'
        comparison_block = f'\n- مقارنة بالفترة الأولى: {trend}'

    return f"""أنت مشجّع تعليمي متخصص في مادة الكيمياء.
اكتب رسالة تحفيزية قصيرة جداً (لا تتجاوز 3 جمل) باللغة العربية الفصيحة المبسّطة
لطالب يدرس الكيمياء اسمه "{student_name}".

معلومات:
- فترة الاختبار: الفترة {period_label}
- درجته: {grade} من {max_grade} ({pct}%){comparison_block}
- {level_hint}

اجعل الرسالة:
- شخصية (تذكر اسمه)
- {'تذكر التحسن أو التراجع مقارنةً بالفترة الأولى بشكل طبيعي ومحفّز' if comparison_block else 'مرتبطة بالكيمياء (استخدم مصطلح أو استعارة كيميائية لطيفة إن أمكن)'}
- تنتهي بجملة تحفيزية قوية

اكتب الرسالة فقط بدون مقدمة أو تعليق."""


# ─────────────────────────────────────────────
# POST /api/admin/semester-grades (فردي)
# ─────────────────────────────────────────────
@semester_grades_bp.route('/semester-grades', methods=['POST'])
@login_required
def save_semester_grade():
    """حفظ الدرجة + توليد رسالة AI"""
    data = request.get_json(silent=True) or {}

    student_id = data.get('student_id')
    period     = data.get('period')
    grade      = data.get('grade')
    max_grade  = data.get('max_grade')

    if not all([student_id, period, grade is not None, max_grade]):
        return jsonify({'success': False, 'message': 'بيانات ناقصة'}), 400
    if period not in (1, 2):
        return jsonify({'success': False, 'message': 'الفترة يجب أن تكون 1 أو 2'}), 400
    if max_grade <= 0:
        return jsonify({'success': False, 'message': 'الدرجة الكاملة يجب أن تكون أكبر من صفر'}), 400

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'الطالب غير موجود'}), 404

    # جلب درجة الفترة الأولى للمقارنة (إن كانت الفترة الثانية)
    prev_grade = prev_max_grade = None
    if period == 2:
        prev_record = StudentSemesterGrade.query.filter_by(
            student_id=student_id, period=1
        ).first()
        if prev_record:
            prev_grade     = prev_record.grade
            prev_max_grade = prev_record.max_grade

    ai_message = None
    try:
        ai_assistant._ensure_configured()
        ai_message = ai_assistant._generate(
            _build_motivation_prompt(student.name, grade, max_grade, period,
                                     prev_grade, prev_max_grade)
        )
        if ai_message:
            ai_message = ai_message.strip()
    except Exception as e:
        print(f'⚠️ AI error: {e}')

    existing = StudentSemesterGrade.get_grade(student_id, period)
    if existing:
        existing.grade             = grade
        existing.max_grade         = max_grade
        existing.ai_message        = ai_message
        existing.notification_sent = False
        existing.updated_at        = datetime.utcnow()
        record = existing
    else:
        record = StudentSemesterGrade(
            student_id=student_id, period=period,
            grade=grade, max_grade=max_grade, ai_message=ai_message,
        )
        db.session.add(record)

    _sync_to_new_system(student_id, period, grade, max_grade, admin_id=current_user.id)
    db.session.commit()

    return jsonify({
        'success':    True,
        'message':    'تم حفظ الدرجة بنجاح',
        'grade_id':   record.id,
        'ai_message': ai_message or '',
        'percentage': record.percentage(),
    })


# ─────────────────────────────────────────────
# POST /api/admin/semester-grades/bulk (جماعي)
# ─────────────────────────────────────────────
@semester_grades_bp.route('/semester-grades/bulk', methods=['POST'])
@login_required
def save_semester_grades_bulk():
    """حفظ درجات عدة طلاب + AI + FCM دفعة واحدة"""
    data      = request.get_json(silent=True) or {}
    period    = data.get('period')
    max_grade = data.get('max_grade')
    entries   = data.get('grades', [])

    if period not in (1, 2):
        return jsonify({'success': False, 'message': 'الفترة يجب أن تكون 1 أو 2'}), 400
    if not max_grade or max_grade <= 0:
        return jsonify({'success': False, 'message': 'الدرجة الكاملة غير صحيحة'}), 400
    if not entries:
        return jsonify({'success': False, 'message': 'لا توجد درجات'}), 400

    ai_assistant._ensure_configured()
    period_label = 'الأولى' if period == 1 else 'الثانية'

    results = []
    for entry in entries:
        student_id = entry.get('student_id')
        grade      = entry.get('grade')
        if student_id is None or grade is None:
            continue

        student = Student.query.get(student_id)
        if not student:
            results.append({'student_id': student_id, 'success': False, 'message': 'طالب غير موجود'})
            continue

        # جلب درجة الفترة الأولى للمقارنة (إن كانت الفترة الثانية)
        prev_grade = prev_max_grade = None
        if period == 2:
            prev_record = StudentSemesterGrade.query.filter_by(
                student_id=student_id, period=1
            ).first()
            if prev_record:
                prev_grade     = prev_record.grade
                prev_max_grade = prev_record.max_grade

        # توليد رسالة AI
        ai_message = None
        try:
            ai_message = ai_assistant._generate(
                _build_motivation_prompt(student.name, grade, max_grade, period,
                                         prev_grade, prev_max_grade)
            )
            if ai_message:
                ai_message = ai_message.strip()
        except Exception as e:
            print(f'⚠️ AI error for {student.name}: {e}')

        # حفظ أو تحديث
        existing = StudentSemesterGrade.get_grade(student_id, period)
        if existing:
            existing.grade             = grade
            existing.max_grade         = max_grade
            existing.ai_message        = ai_message
            existing.notification_sent = False
            existing.updated_at        = datetime.utcnow()
            record = existing
        else:
            record = StudentSemesterGrade(
                student_id=student_id, period=period,
                grade=grade, max_grade=max_grade, ai_message=ai_message,
            )
            db.session.add(record)

        db.session.flush()

        pct   = round((grade / max_grade) * 100, 1)
        title = f'درجتك في اختبار الفترة {period_label} 📊'
        body  = f'{grade}/{max_grade} ({pct}%)\n{ai_message or ""}'
        notif_data = {
            'type': 'semester_grade', 'period': str(period),
            'grade': str(grade), 'max_grade': str(max_grade),
        }

        # ① حفظ في DB دائماً
        _save_db_notification(student, title, body, notif_data)

        # ② FCM push (بونص)
        fcm_result = _send_fcm(student, title, body, notif_data)

        record.notification_sent = True
        record.notified_at       = datetime.utcnow()

        _sync_to_new_system(student_id, period, grade, max_grade, admin_id=current_user.id)

        results.append({
            'student_id':   student_id,
            'student_name': student.name,
            'success':      True,
            'grade_id':     record.id,
            'percentage':   pct,
            'ai_message':   ai_message or '',
            'notif_sent':   True,
            'fcm_push':     (fcm_result == 'sent'),
        })

    db.session.commit()

    saved   = sum(1 for r in results if r.get('success'))
    notified = sum(1 for r in results if r.get('notif_sent'))

    return jsonify({
        'success':  True,
        'total':    len(entries),
        'saved':    saved,
        'notified': notified,
        'results':  results,
    })


# ─────────────────────────────────────────────
# GET /api/admin/semester-grades/bulk?period=1
# ─────────────────────────────────────────────
@semester_grades_bp.route('/semester-grades/bulk', methods=['GET'])
@login_required
def get_semester_grades_bulk():
    """جلب درجات كل الطلاب لفترة معينة دفعة واحدة"""
    period = request.args.get('period', type=int)
    if period not in (1, 2):
        return jsonify({'success': False, 'message': 'period يجب أن يكون 1 أو 2'}), 400

    records = StudentSemesterGrade.query.filter_by(period=period).all()
    return jsonify({
        'success': True,
        'period':  period,
        'grades':  {r.student_id: r.to_dict() for r in records},
    })


# ─────────────────────────────────────────────
# GET /api/admin/students/<id>/semester-grades
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# POST /api/admin/semester-grades/<id>/notify
# ─────────────────────────────────────────────
@semester_grades_bp.route('/semester-grades/<int:grade_id>/notify', methods=['POST'])
@login_required
def send_grade_notification(grade_id):
    """إرسال إشعار الدرجة للطالب (فردي)"""
    data = request.get_json(silent=True) or {}

    record = StudentSemesterGrade.query.get(grade_id)
    if not record:
        return jsonify({'success': False, 'message': 'السجل غير موجود'}), 404

    student = Student.query.get(record.student_id)
    if not student:
        return jsonify({'success': False, 'message': 'الطالب غير موجود'}), 404

    period_label   = 'الأولى' if record.period == 1 else 'الثانية'
    pct            = record.percentage()
    custom_message = data.get('message', '').strip()
    body_text      = custom_message if custom_message else (record.ai_message or '')

    title = f'درجتك في اختبار الفترة {period_label} 📊'
    body  = f'{record.grade}/{record.max_grade} ({pct}%)\n{body_text}'

    notif_data = {
        'type':      'semester_grade',
        'period':    str(record.period),
        'grade':     str(record.grade),
        'max_grade': str(record.max_grade),
        'grade_id':  str(record.id),
    }

    # ① حفظ في قاعدة البيانات (الطالب يشوفه لما يفتح التطبيق)
    _save_db_notification(student, title, body, notif_data)

    # ② محاولة FCM push (بونص — لو فشل ما يأثر)
    fcm_result = _send_fcm(student, title, body, notif_data)

    record.notification_sent = True
    record.notified_at       = datetime.utcnow()
    db.session.commit()

    push_note = '' if fcm_result == 'sent' else ' (بدون push — سيراه عند فتح التطبيق)'
    return jsonify({'success': True, 'message': f'تم إرسال الإشعار بنجاح{push_note}'})
