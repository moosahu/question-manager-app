"""
نظام الدرجات والحضور اليومي
- admin web: إدارة grade_config (الفترات والفئات)
- teacher API: إدخال درجات، حضور، إرسال درجات
- student API: عرض ما أُرسل من درجات
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, date

from src.extensions import db
from src.middleware.auth_middleware import verify_teacher_token, verify_student_token
from src.models.grade_period import GradePeriod
from src.models.grade_config import GradeConfig
from src.models.grade_entry import GradeEntry
from src.models.student_attendance import StudentAttendance
from src.models.student_grade_release import StudentGradeRelease
from src.models.teacher_student import TeacherStudent
from src.models.student import Student

grades_bp = Blueprint('grades', __name__)


# ──────────────────────────────────────────────────────
#  دوال مساعدة
# ──────────────────────────────────────────────────────

def _calc_category_score(entries):
    """متوسط الإدخالات (score بين 0-1) × max_score"""
    if not entries:
        return None
    avg = sum(e.score for e in entries) / len(entries)
    return round(avg * entries[0].category.max_score, 2)


def _build_student_grades(student_id, teacher_id=None, admin_id=None):
    """يبني هيكل درجات الطالب — يدعم teacher_id أو admin_id"""
    periods = GradePeriod.query.filter_by(is_active=True).order_by(GradePeriod.sort_order).all()
    result = {}
    for period in periods:
        cats = GradeConfig.query.filter_by(period_id=period.id, is_active=True)\
                                .order_by(GradeConfig.sort_order).all()
        period_data = {'period_name': period.period_name, 'categories': {}}
        for cat in cats:
            q = GradeEntry.query.filter_by(student_id=student_id, category_id=cat.id)
            if teacher_id:
                q = q.filter_by(teacher_id=teacher_id)
            elif admin_id:
                q = q.filter_by(admin_id=admin_id)
            entries = q.order_by(GradeEntry.entry_date).all()
            avg = _calc_category_score(entries) if entries else None
            period_data['categories'][cat.id] = {
                'category_name': cat.category_name,
                'max_score':     cat.max_score,
                'entries':       [e.to_dict() for e in entries],
                'avg_score':     avg,
            }
        result[period.id] = period_data
    return result


# ══════════════════════════════════════════════════════
#  ADMIN WEB: إدارة grade_config
# ══════════════════════════════════════════════════════

@grades_bp.route('/admin/grade-config', methods=['GET'])
@login_required
def admin_grade_config():
    """صفحة إدارة التقسيمة"""
    periods = GradePeriod.query.order_by(GradePeriod.sort_order).all()
    configs = GradeConfig.query.order_by(GradeConfig.period_id, GradeConfig.sort_order).all()
    return render_template('grades/grade_config.html', periods=periods, configs=configs)


@grades_bp.route('/admin/grade-config/add-category', methods=['POST'])
@login_required
def admin_add_category():
    period_id     = request.form.get('period_id', type=int)
    category_name = request.form.get('category_name', '').strip()
    max_score     = request.form.get('max_score', type=float, default=10)
    sort_order    = request.form.get('sort_order', type=int, default=0)

    if not period_id or not category_name:
        flash('الفترة واسم الفئة مطلوبان', 'danger')
        return redirect(url_for('grades.admin_grade_config'))

    cat = GradeConfig(
        period_id=period_id,
        category_name=category_name,
        max_score=max_score,
        sort_order=sort_order,
        is_active=True,
    )
    db.session.add(cat)
    db.session.commit()
    flash(f'تمت إضافة الفئة "{category_name}"', 'success')
    return redirect(url_for('grades.admin_grade_config'))


@grades_bp.route('/admin/grade-config/<int:cat_id>/edit', methods=['POST'])
@login_required
def admin_edit_category(cat_id):
    cat = GradeConfig.query.get_or_404(cat_id)
    cat.category_name = request.form.get('category_name', cat.category_name).strip()
    cat.max_score     = request.form.get('max_score', type=float, default=cat.max_score)
    cat.sort_order    = request.form.get('sort_order', type=int, default=cat.sort_order)
    db.session.commit()
    flash('تم تحديث الفئة', 'success')
    return redirect(url_for('grades.admin_grade_config'))


@grades_bp.route('/admin/grade-config/<int:cat_id>/toggle', methods=['POST'])
@login_required
def admin_toggle_category(cat_id):
    cat = GradeConfig.query.get_or_404(cat_id)
    cat.is_active = not cat.is_active
    db.session.commit()
    return redirect(url_for('grades.admin_grade_config'))


@grades_bp.route('/admin/grade-config/<int:cat_id>/delete', methods=['POST'])
@login_required
def admin_delete_category(cat_id):
    cat = GradeConfig.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    flash('تم حذف الفئة', 'success')
    return redirect(url_for('grades.admin_grade_config'))


@grades_bp.route('/admin/grade-config/add-period', methods=['POST'])
@login_required
def admin_add_period():
    period_name = request.form.get('period_name', '').strip()
    sort_order  = request.form.get('sort_order', type=int, default=0)
    if not period_name:
        flash('اسم الفترة مطلوب', 'danger')
        return redirect(url_for('grades.admin_grade_config'))
    p = GradePeriod(period_name=period_name, sort_order=sort_order, is_active=True)
    db.session.add(p)
    db.session.commit()
    flash(f'تمت إضافة الفترة "{period_name}"', 'success')
    return redirect(url_for('grades.admin_grade_config'))


# ══════════════════════════════════════════════════════
#  TEACHER API: التقسيمة
# ══════════════════════════════════════════════════════

@grades_bp.route('/api/teacher/grade-config', methods=['GET'])
@verify_teacher_token
def api_teacher_grade_config():
    """المعلم يجلب التقسيمة الكاملة"""
    periods = GradePeriod.query.filter_by(is_active=True).order_by(GradePeriod.sort_order).all()
    data = []
    for p in periods:
        cats = GradeConfig.query.filter_by(period_id=p.id, is_active=True)\
                                .order_by(GradeConfig.sort_order).all()
        data.append({
            'period_id':   p.id,
            'period_name': p.period_name,
            'categories':  [c.to_dict() for c in cats],
        })
    return jsonify({'success': True, 'periods': data})


# ══════════════════════════════════════════════════════
#  TEACHER API: إدخال درجات
# ══════════════════════════════════════════════════════

@grades_bp.route('/api/teacher/grade-entries', methods=['POST'])
@verify_teacher_token
def api_add_grade_entry():
    """إضافة إدخال درجة لطالب في فئة معينة"""
    teacher_id = request.teacher_id
    data = request.get_json() or {}

    student_id  = data.get('student_id')
    category_id = data.get('category_id')
    entry_label = data.get('entry_label', '').strip()
    score       = data.get('score')          # 0 – max_score

    if not all([student_id, category_id, entry_label, score is not None]):
        return jsonify({'success': False, 'error': 'البيانات ناقصة'}), 400

    cat = GradeConfig.query.get(category_id)
    if not cat:
        return jsonify({'success': False, 'error': 'الفئة غير موجودة'}), 404

    # التحقق أن الطالب تابع لهذا المعلم
    link = TeacherStudent.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    if not link:
        return jsonify({'success': False, 'error': 'الطالب غير مرتبط بحسابك'}), 403

    # score يُخزّن كنسبة 0-1
    score_ratio = float(score) / cat.max_score
    score_ratio = max(0.0, min(1.0, score_ratio))

    entry = GradeEntry(
        student_id=student_id,
        teacher_id=teacher_id,
        category_id=category_id,
        entry_label=entry_label,
        score=score_ratio,
        entry_date=date.today(),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'success': True, 'entry': entry.to_dict()})


@grades_bp.route('/api/teacher/grade-entries/<int:entry_id>', methods=['DELETE'])
@verify_teacher_token
def api_delete_grade_entry(entry_id):
    teacher_id = request.teacher_id
    entry = GradeEntry.query.get_or_404(entry_id)
    if entry.teacher_id != teacher_id:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'success': True})


@grades_bp.route('/api/teacher/students/<int:student_id>/grades', methods=['GET'])
@verify_teacher_token
def api_teacher_student_grades(student_id):
    """المعلم يجلب درجات طالب بالتفصيل"""
    teacher_id = request.teacher_id
    link = TeacherStudent.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    if not link:
        return jsonify({'success': False, 'error': 'الطالب غير مرتبط بحسابك'}), 403

    grades = _build_student_grades(student_id, teacher_id)
    return jsonify({'success': True, 'grades': grades})


# ══════════════════════════════════════════════════════
#  TEACHER API: الحضور
# ══════════════════════════════════════════════════════

@grades_bp.route('/api/teacher/attendance', methods=['POST'])
@verify_teacher_token
def api_record_attendance():
    """تسجيل / تحديث حضور طالب"""
    teacher_id = request.teacher_id
    data = request.get_json() or {}

    student_id      = data.get('student_id')
    attendance_date = data.get('attendance_date')  # YYYY-MM-DD
    period_number   = data.get('period_number', 1)
    status          = data.get('status', 'present')  # present/absent/late/sleeping
    notes           = data.get('notes', '')

    if not all([student_id, attendance_date]):
        return jsonify({'success': False, 'error': 'student_id و attendance_date مطلوبان'}), 400

    if status not in ('present', 'absent', 'late', 'sleeping'):
        return jsonify({'success': False, 'error': 'status غير صحيح'}), 400

    try:
        att_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'تنسيق التاريخ غير صحيح (YYYY-MM-DD)'}), 400

    link = TeacherStudent.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    if not link:
        return jsonify({'success': False, 'error': 'الطالب غير مرتبط بحسابك'}), 403

    existing = StudentAttendance.query.filter_by(
        student_id=student_id,
        teacher_id=teacher_id,
        attendance_date=att_date,
        period_number=period_number,
    ).first()

    if existing:
        existing.status = status
        existing.notes  = notes
        att = existing
    else:
        att = StudentAttendance(
            student_id=student_id,
            teacher_id=teacher_id,
            attendance_date=att_date,
            period_number=period_number,
            status=status,
            notes=notes,
        )
        db.session.add(att)

    db.session.commit()
    return jsonify({'success': True, 'attendance': att.to_dict()})


@grades_bp.route('/api/teacher/attendance', methods=['GET'])
@verify_teacher_token
def api_get_attendance():
    """سجل الحضور للمعلم — فلترة بالتاريخ أو الطالب"""
    teacher_id = request.teacher_id
    student_id = request.args.get('student_id', type=int)
    date_str   = request.args.get('date')  # YYYY-MM-DD

    q = StudentAttendance.query.filter_by(teacher_id=teacher_id)
    if student_id:
        q = q.filter_by(student_id=student_id)
    if date_str:
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            q = q.filter_by(attendance_date=d)
        except ValueError:
            pass

    records = q.order_by(StudentAttendance.attendance_date.desc(),
                         StudentAttendance.period_number).all()
    return jsonify({'success': True, 'attendance': [r.to_dict() for r in records]})


# ══════════════════════════════════════════════════════
#  TEACHER API: إرسال درجات للطالب
# ══════════════════════════════════════════════════════

@grades_bp.route('/api/teacher/send-grades', methods=['POST'])
@verify_teacher_token
def api_send_grades():
    """المعلم يرسل درجات فترة معينة لطالب"""
    teacher_id = request.teacher_id
    data = request.get_json() or {}

    student_id     = data.get('student_id')
    period_id      = data.get('period_id')
    release_type   = data.get('release_type', 'both')   # test/yearly/both
    custom_message = data.get('custom_message', '')

    if not all([student_id, period_id]):
        return jsonify({'success': False, 'error': 'student_id و period_id مطلوبان'}), 400

    if release_type not in ('test', 'yearly', 'both'):
        return jsonify({'success': False, 'error': 'release_type غير صحيح'}), 400

    link = TeacherStudent.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    if not link:
        return jsonify({'success': False, 'error': 'الطالب غير مرتبط بحسابك'}), 403

    # إنشاء أو تحديث سجل الإرسال
    existing = StudentGradeRelease.query.filter_by(
        student_id=student_id,
        teacher_id=teacher_id,
        period_id=period_id,
    ).first()

    if existing:
        existing.release_type   = release_type
        existing.custom_message = custom_message
        existing.released_at    = datetime.utcnow()
        rel = existing
    else:
        rel = StudentGradeRelease(
            student_id=student_id,
            teacher_id=teacher_id,
            period_id=period_id,
            release_type=release_type,
            custom_message=custom_message,
        )
        db.session.add(rel)

    db.session.commit()

    # ── إشعار FCM للطالب ──────────────────────────────
    try:
        from src.services.notification_service import NotificationService
        student = Student.query.get(student_id)
        period  = GradePeriod.query.get(period_id)
        if student and student.fcm_token:
            type_label = {'test': 'الاختبار', 'yearly': 'أعمال السنة', 'both': 'الدرجات'}.get(release_type, 'الدرجات')
            period_name = period.period_name if period else ''
            notif_body  = f'أرسل معلمك {type_label} - {period_name}'
            if custom_message:
                notif_body += f'\n{custom_message}'
            NotificationService.send_fcm_notification(
                student.fcm_token,
                '📊 درجاتك الجديدة',
                notif_body,
                {'type': 'grades_released', 'period_id': str(period_id)},
            )
    except Exception as e:
        print(f"⚠️ grades FCM error: {e}")

    return jsonify({'success': True, 'release': rel.to_dict()})


# ══════════════════════════════════════════════════════
#  STUDENT API: عرض الدرجات المُرسلة
# ══════════════════════════════════════════════════════

@grades_bp.route('/api/student/my-grades', methods=['GET'])
@verify_student_token
def api_student_my_grades():
    """الطالب يجلب الدرجات التي أرسلها المعلم له"""
    student_id = request.student_id

    # جلب كل سجلات الإرسال لهذا الطالب
    releases = StudentGradeRelease.query.filter_by(student_id=student_id).all()
    if not releases:
        return jsonify({'success': True, 'data': []})

    output = []
    for rel in releases:
        teacher_id    = rel.teacher_id
        period_id     = rel.period_id
        release_type  = rel.release_type

        # جلب الفئات المطلوبة فقط حسب release_type
        period = GradePeriod.query.get(period_id)
        cats   = GradeConfig.query.filter_by(period_id=period_id, is_active=True)\
                                  .order_by(GradeConfig.sort_order).all()

        categories_data = []
        for cat in cats:
            # فلترة حسب نوع الإرسال (بسيط: test = يحتوي "اختبار"، yearly = غيره)
            is_test_cat = 'اختبار' in cat.category_name
            if release_type == 'test' and not is_test_cat:
                continue
            if release_type == 'yearly' and is_test_cat:
                continue

            entries = GradeEntry.query.filter_by(
                student_id=student_id,
                teacher_id=teacher_id,
                category_id=cat.id,
            ).order_by(GradeEntry.entry_date).all()

            avg = _calc_category_score(entries) if entries else None
            categories_data.append({
                'category_name': cat.category_name,
                'max_score':     cat.max_score,
                'avg_score':     avg,
                'entries':       [{'label': e.entry_label, 'score': round(e.score * cat.max_score, 2)} for e in entries],
            })

        output.append({
            'period_id':      period_id,
            'period_name':    period.period_name if period else '',
            'release_type':   release_type,
            'custom_message': rel.custom_message or '',
            'released_at':    rel.to_dict()['released_at'],
            'categories':     categories_data,
        })

    return jsonify({'success': True, 'data': output})


# ══════════════════════════════════════════════════════
#  ADMIN API: إدارة درجات وحضور (session cookie)
#  نفس منطق المعلم لكن teacher_id يأتي من الـ body/params
# ══════════════════════════════════════════════════════

@grades_bp.route('/api/admin/students/<int:student_id>/grades', methods=['GET'])
@login_required
def api_admin_student_grades(student_id):
    """الأدمن يجلب درجات طالبه — يستخدم admin_id من الجلسة"""
    from flask_login import current_user
    grades = _build_student_grades(student_id, admin_id=current_user.id)
    return jsonify({'success': True, 'grades': grades})


@grades_bp.route('/api/admin/grade-entries', methods=['POST'])
@login_required
def api_admin_add_grade_entry():
    from flask_login import current_user
    data        = request.get_json() or {}
    student_id  = data.get('student_id')
    category_id = data.get('category_id')
    entry_label = data.get('entry_label', '').strip()
    score       = data.get('score')

    if not all([student_id, category_id, entry_label, score is not None]):
        return jsonify({'success': False, 'error': 'البيانات ناقصة'}), 400

    cat = GradeConfig.query.get(category_id)
    if not cat:
        return jsonify({'success': False, 'error': 'الفئة غير موجودة'}), 404

    score_ratio = max(0.0, min(1.0, float(score) / cat.max_score))
    entry = GradeEntry(
        student_id=student_id, admin_id=current_user.id,
        category_id=category_id, entry_label=entry_label,
        score=score_ratio, entry_date=date.today(),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'success': True, 'entry': entry.to_dict()})


@grades_bp.route('/api/admin/grade-entries/<int:entry_id>', methods=['DELETE'])
@login_required
def api_admin_delete_grade_entry(entry_id):
    entry = GradeEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'success': True})


@grades_bp.route('/api/admin/attendance', methods=['POST'])
@login_required
def api_admin_record_attendance():
    from flask_login import current_user
    data            = request.get_json() or {}
    student_id      = data.get('student_id')
    attendance_date = data.get('attendance_date')
    period_number   = data.get('period_number', 1)
    status          = data.get('status', 'present')
    notes           = data.get('notes', '')

    if not all([student_id, attendance_date]):
        return jsonify({'success': False, 'error': 'بيانات ناقصة'}), 400
    if status not in ('present', 'absent', 'late', 'sleeping'):
        return jsonify({'success': False, 'error': 'status غير صحيح'}), 400
    try:
        att_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'تنسيق التاريخ غير صحيح'}), 400

    existing = StudentAttendance.query.filter_by(
        student_id=student_id, admin_id=current_user.id,
        attendance_date=att_date, period_number=period_number,
    ).first()
    if existing:
        existing.status = status
        existing.notes  = notes
        att = existing
    else:
        att = StudentAttendance(
            student_id=student_id, admin_id=current_user.id,
            attendance_date=att_date, period_number=period_number,
            status=status, notes=notes,
        )
        db.session.add(att)
    db.session.commit()
    return jsonify({'success': True, 'attendance': att.to_dict()})


@grades_bp.route('/api/admin/attendance', methods=['GET'])
@login_required
def api_admin_get_attendance():
    from flask_login import current_user
    student_id = request.args.get('student_id', type=int)
    date_str   = request.args.get('date')
    q = StudentAttendance.query.filter_by(admin_id=current_user.id)
    if student_id:
        q = q.filter_by(student_id=student_id)
    if date_str:
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            q = q.filter_by(attendance_date=d)
        except ValueError:
            pass
    records = q.order_by(StudentAttendance.attendance_date.desc(),
                         StudentAttendance.period_number).all()
    return jsonify({'success': True, 'attendance': [r.to_dict() for r in records]})


@grades_bp.route('/api/admin/send-grades', methods=['POST'])
@login_required
def api_admin_send_grades():
    from flask_login import current_user
    data           = request.get_json() or {}
    student_id     = data.get('student_id')
    period_id      = data.get('period_id')
    release_type   = data.get('release_type', 'both')
    custom_message = data.get('custom_message', '')

    if not all([student_id, period_id]):
        return jsonify({'success': False, 'error': 'بيانات ناقصة'}), 400
    if release_type not in ('test', 'yearly', 'both'):
        return jsonify({'success': False, 'error': 'release_type غير صحيح'}), 400

    existing = StudentGradeRelease.query.filter_by(
        student_id=student_id, admin_id=current_user.id, period_id=period_id,
    ).first()
    if existing:
        existing.release_type   = release_type
        existing.custom_message = custom_message
        existing.released_at    = datetime.utcnow()
        rel = existing
    else:
        rel = StudentGradeRelease(
            student_id=student_id, admin_id=current_user.id,
            period_id=period_id, release_type=release_type,
            custom_message=custom_message,
        )
        db.session.add(rel)
    db.session.commit()

    # إشعار FCM
    try:
        from src.services.notification_service import NotificationService
        student = Student.query.get(student_id)
        period  = GradePeriod.query.get(period_id)
        if student and student.fcm_token:
            type_label  = {'test': 'الاختبار', 'yearly': 'أعمال السنة', 'both': 'الدرجات'}.get(release_type, 'الدرجات')
            period_name = period.period_name if period else ''
            notif_body  = f'أُرسلت لك {type_label} - {period_name}'
            if custom_message:
                notif_body += f'\n{custom_message}'
            NotificationService.send_fcm_notification(
                student.fcm_token, '📊 درجاتك الجديدة', notif_body,
                {'type': 'grades_released', 'period_id': str(period_id)},
            )
    except Exception as e:
        print(f"⚠️ grades FCM error: {e}")

    return jsonify({'success': True, 'release': rel.to_dict()})
