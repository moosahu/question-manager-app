"""
Blueprint جداول المذاكرة للاختبار التحصيلي
URL prefix: /scheduler
"""
import io
import json
import logging
from datetime import datetime, date, timedelta

from urllib.parse import quote
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, make_response, abort)
from flask_login import login_required, current_user

from src.extensions import db
from src.models.study_schedule import StudySchedule, StudySession

logger = logging.getLogger(__name__)


def _parse_pages_input(raw: str) -> tuple[int, int]:
    """
    يقبل:
    • عدد صحيح مثل "200"  → (1, 200)   — يبدأ من صفحة 1
    • نطاق مثل "6-110"    → (6, 110)   — يبدأ من صفحة 6 وينتهي عند 110
    يُرجع (0, 0) إذا كانت القيمة غير صحيحة.
    """
    raw = (raw or '').strip()
    if not raw:
        return (0, 0)
    if '-' in raw:
        parts = raw.split('-', 1)
        try:
            start = int(parts[0].strip())
            end   = int(parts[1].strip())
            if end > start:
                return (start, end)
        except (ValueError, TypeError):
            pass
        return (0, 0)
    try:
        val = int(raw)
        return (1, val) if val > 0 else (0, 0)
    except (ValueError, TypeError):
        return (0, 0)

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/scheduler')


def _get_mobile_student_id() -> int | None:
    """
    استخراج معرف الطالب — نفس نهج diagnostic_routes:
    1. Cookie: student_session_<username>  ← الطريقة الرئيسية للموبايل
    2. X-Student-ID header                ← بديل
    3. current_user (جلسة الويب)
    """
    # 1. Cookie student_session_<username>
    try:
        from src.models.student import Student
        for cookie_name in request.cookies:
            if cookie_name.startswith('student_session_'):
                username = cookie_name.replace('student_session_', '')
                student = Student.query.filter_by(username=username).first()
                if student:
                    return student.id
    except Exception:
        pass

    # 2. X-Student-ID header
    sid = request.headers.get('X-Student-ID', '').strip()
    if sid:
        try:
            return int(sid)
        except (ValueError, TypeError):
            pass

    # 3. جلسة الويب
    if current_user.is_authenticated and hasattr(current_user, 'id'):
        return current_user.id

    return None

# ─── Constants ────────────────────────────────────────────────────────────────
SUBJECTS      = ['رياضيات', 'فيزياء', 'كيمياء', 'أحياء']
BREAK_MINUTES = 15
START_HOUR    = 8   # يبدأ الجدول الساعة 8 صباحاً


# ─── Ensure tables exist when blueprint loads ─────────────────────────────────
@scheduler_bp.record_once
def _create_tables(state):
    """إنشاء الجداول تلقائياً إذا لم تكن موجودة"""
    try:
        with state.app.app_context():
            try:
                db.create_all()
                logger.info('✅ Study scheduler tables ready')
            except Exception as exc:
                logger.warning(f'⚠️  Could not create scheduler tables: {exc}')

            # Migrations for existing installations
            # كل migration يأخذ connection مستقل — ضروري في PostgreSQL
            # لأن فشل أي ALTER TABLE يُلغي الـ transaction الكامل
            from sqlalchemy import text
            for sql in [
                'ALTER TABLE study_schedules ADD COLUMN exam_date DATE',
                'ALTER TABLE study_schedules ADD COLUMN subject_pages TEXT',
                'ALTER TABLE study_sessions ADD COLUMN pages_from INTEGER',
                'ALTER TABLE study_sessions ADD COLUMN pages_to INTEGER',
                'ALTER TABLE study_schedules ADD COLUMN student_id INTEGER',
            ]:
                try:
                    with db.engine.connect() as _conn:
                        _conn.execute(text(sql))
                        _conn.commit()
                except Exception:
                    pass  # العمود موجود مسبقاً — آمن للتجاهل
    except Exception as exc:
        logger.warning(f'⚠️  _create_tables failed (non-fatal): {exc}')


# ─── Firestore: مواعيد التحصيلي ───────────────────────────────────────────────
def _get_tahsili_periods() -> list[dict]:
    """
    جلب فترات الاختبار التحصيلي من Firestore (settings/exam_dates).
    يُرجع قائمة بالفترتين إن وُجدتا، أو قائمة فارغة عند أي خطأ.
    """
    try:
        from firebase_admin import firestore as fs
        db = fs.client()
        doc = db.collection('settings').document('exam_dates').get()
        if not doc.exists:
            return []
        data = doc.to_dict() or {}
        periods = []
        for key, label in [('exam_period1_start', 'الفترة الأولى'),
                            ('exam_period2_start', 'الفترة الثانية')]:
            raw = data.get(key)
            if raw:
                try:
                    d = datetime.fromisoformat(raw[:10])   # أخذ الجزء yyyy-mm-dd فقط
                    periods.append({
                        'label': f'{label} — {d.strftime("%Y/%m/%d")}',
                        'date':  d.strftime('%Y-%m-%d'),
                    })
                except ValueError:
                    pass
        return periods
    except Exception as exc:
        logger.warning(f'Could not fetch Tahsili dates from Firestore: {exc}')
        return []


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _mins_to_time(m: int) -> str:
    return f'{(m // 60) % 24:02d}:{m % 60:02d}'


def _subject_block_ranges(duration: int) -> list[dict]:
    """
    يُقسّم الأيام بالتساوي على المواد الأربعة في كتل متتالية.
    مثال (30 يوم): رياضيات 1-8، فيزياء 9-15، كيمياء 16-22، أحياء 23-30
    """
    n     = len(SUBJECTS)
    base  = duration // n
    extra = duration % n
    ranges, day = [], 1
    for i, subj in enumerate(SUBJECTS):
        cnt = base + (1 if i < extra else 0)
        ranges.append({'subject': subj, 'start': day, 'end': day + cnt - 1, 'days': cnt})
        day += cnt
    return ranges


def _generate_sessions(schedule: StudySchedule) -> list[StudySession]:
    """
    توليد جلسات الجدول.
    كل مادة تأخذ كتلة متتالية من الأيام (duration ÷ 4).
    كل يوم: جلسة واحدة — إذا أُدخلت صفحات تُوزَّع تلقائياً على أيام المادة.
    """
    duration_mins = int(schedule.daily_hours * 60)
    sessions      = []

    subject_pages: dict = {}
    if schedule.subject_pages:
        try:
            subject_pages = json.loads(schedule.subject_pages)
        except (ValueError, TypeError):
            pass

    for r in _subject_block_ranges(schedule.duration):
        subj = r['subject']
        days = r['days']

        # صيغة التخزين: [page_start, page_end] أو عدد صحيح قديم
        raw_val = subject_pages.get(subj)
        if isinstance(raw_val, list) and len(raw_val) == 2:
            p_start, p_end = int(raw_val[0]), int(raw_val[1])
            total_pages    = p_end - p_start + 1
        elif isinstance(raw_val, int) and raw_val > 0:
            p_start, p_end = 1, raw_val
            total_pages    = raw_val
        else:
            p_start = p_end = total_pages = 0

        for idx, day in enumerate(range(r['start'], r['end'] + 1)):
            if total_pages > 0:
                p_from = p_start + round(idx / days * total_pages)
                p_to   = p_start + round((idx + 1) / days * total_pages) - 1
                if idx == days - 1:
                    p_to = p_end          # اليوم الأخير يأخذ ما تبقى
                p_from = max(p_start, p_from)
                p_to   = min(p_end,   p_to)
            else:
                p_from = p_to = None

            sessions.append(StudySession(
                schedule_id      = schedule.id,
                day_number       = day,
                subject          = subj,
                start_time       = _mins_to_time(START_HOUR * 60),
                end_time         = _mins_to_time(START_HOUR * 60 + duration_mins),
                duration_minutes = duration_mins,
                is_completed     = False,
                order_index      = 0,
                pages_from       = p_from,
                pages_to         = p_to,
            ))

    return sessions


# ─── Pages ────────────────────────────────────────────────────────────────────
@scheduler_bp.route('/')
@login_required
def index():
    """الصفحة الرئيسية — قائمة جميع الجداول"""
    schedules = StudySchedule.query.order_by(StudySchedule.created_at.desc()).all()
    return render_template('scheduler/index.html', schedules=schedules)


@scheduler_bp.route('/create', methods=['GET'])
@login_required
def create():
    """صفحة إنشاء جدول جديد"""
    today = date.today().strftime('%Y-%m-%d')
    # ⚠️ لا نستدعي Firebase هنا — مواعيد التحصيلي تُجلب عبر AJAX بعد تحميل الصفحة
    # (استدعاء Firebase في server-side render يُسبب gRPC SIGSEGV crash في الـ worker)
    duration_options = [
        {'val': 15, 'label': '15 يوم', 'desc': 'مراجعة مكثفة وسريعة',    'icon': '⚡'},
        {'val': 30, 'label': '30 يوم', 'desc': 'الخيار المتوازن والأنسب', 'icon': '✨'},
        {'val': 60, 'label': '60 يوم', 'desc': 'دراسة شاملة ومتعمقة',    'icon': '🎯'},
    ]
    subject_options = [
        {'name': 'رياضيات', 'key': 'math',    'cls': 'math'},
        {'name': 'فيزياء',  'key': 'physics', 'cls': 'physics'},
        {'name': 'كيمياء',  'key': 'chem',    'cls': 'chem'},
        {'name': 'أحياء',   'key': 'bio',     'cls': 'bio'},
    ]
    return render_template('scheduler/create.html', today=today, subjects=SUBJECTS,
                           break_minutes=BREAK_MINUTES, start_hour=START_HOUR,
                           duration_options=duration_options,
                           subject_options=subject_options)


@scheduler_bp.route('/create', methods=['POST'])
@login_required
def create_post():
    """معالجة إنشاء جدول جديد"""
    student_name = request.form.get('student_name', '').strip()
    duration     = request.form.get('duration', 30, type=int)
    daily_hours  = request.form.get('daily_hours', 4.0, type=float)
    start_date   = request.form.get('start_date', '')

    exam_date_str = request.form.get('exam_date', '').strip()
    exam_date     = None
    if exam_date_str:
        try:
            exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    # ── Validation ──
    if not student_name:
        flash('يرجى إدخال اسم الطالب', 'error')
        return redirect(url_for('scheduler.create'))
    if duration not in (15, 30, 60):
        flash('مدة الجدول يجب أن تكون 15 أو 30 أو 60 يوماً', 'error')
        return redirect(url_for('scheduler.create'))
    if not (1 <= daily_hours <= 16):
        flash('عدد الساعات اليومية يجب أن يكون بين 1 و 16', 'error')
        return redirect(url_for('scheduler.create'))
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('تاريخ البداية غير صحيح', 'error')
        return redirect(url_for('scheduler.create'))

    # ── Subject pages (اختياري) — يقبل "200" أو "6-110" ──
    subject_pages = {}
    for subj, key in [('رياضيات','math'),('فيزياء','physics'),('كيمياء','chem'),('أحياء','bio')]:
        ps, pe = _parse_pages_input(request.form.get(f'pages_{key}', ''))
        if pe > ps >= 1:
            subject_pages[subj] = [ps, pe]

    # ── Create ──
    schedule = StudySchedule(
        student_name  = student_name,
        duration      = duration,
        daily_hours   = daily_hours,
        start_date    = start,
        exam_date     = exam_date,
        subject_pages = json.dumps(subject_pages, ensure_ascii=False) if subject_pages else None,
    )
    db.session.add(schedule)
    db.session.flush()          # احصل على الـ ID قبل توليد الجلسات

    for sess in _generate_sessions(schedule):
        db.session.add(sess)

    db.session.commit()
    flash(f'تم إنشاء جدول "{student_name}" بنجاح 🎉', 'success')
    return redirect(url_for('scheduler.view_schedule', schedule_id=schedule.id))


@scheduler_bp.route('/<int:schedule_id>')
@login_required
def view_schedule(schedule_id):
    """عرض الجدول مع التنقل الأسبوعي وتتبع التقدم"""
    schedule = StudySchedule.query.get_or_404(schedule_id)
    # حوّل البيانات المخزنة إلى صيغة نطاق "start-end" لعرضها في modal
    stored_pages = {}
    if schedule.subject_pages:
        try:
            raw = json.loads(schedule.subject_pages)
            for subj, val in raw.items():
                if isinstance(val, list) and len(val) == 2:
                    stored_pages[subj] = f'{val[0]}-{val[1]}'
                elif isinstance(val, int) and val > 0:
                    stored_pages[subj] = str(val)
        except (ValueError, TypeError):
            pass
    return render_template('scheduler/view.html',
                           schedule=schedule,
                           schedule_json=schedule.to_dict(),
                           stored_pages=stored_pages)


@scheduler_bp.route('/<int:schedule_id>/update-pages', methods=['POST'])
@login_required
def update_pages(schedule_id):
    """تحديث عدد الصفحات لكل مادة وإعادة توليد أرقام الصفحات في الجلسات"""
    schedule = StudySchedule.query.get_or_404(schedule_id)

    subject_pages = {}
    for subj, key in [('رياضيات','math'),('فيزياء','physics'),('كيمياء','chem'),('أحياء','bio')]:
        ps, pe = _parse_pages_input(request.form.get(f'pages_{key}', ''))
        if pe > ps >= 1:
            subject_pages[subj] = [ps, pe]

    logger.info(f'update_pages for schedule {schedule_id}: {subject_pages}')
    schedule.subject_pages = json.dumps(subject_pages, ensure_ascii=False) if subject_pages else None
    db.session.flush()

    # أعد حساب pages_from و pages_to لكل جلسة موجودة بناءً على النطاق المدخل
    subject_block = {r['subject']: r for r in _subject_block_ranges(schedule.duration)}
    sessions = StudySession.query.filter_by(schedule_id=schedule_id).all()
    for sess in sessions:
        r       = subject_block.get(sess.subject, {})
        raw_val = subject_pages.get(sess.subject)
        if isinstance(raw_val, list) and len(raw_val) == 2 and r:
            p_start, p_end = raw_val[0], raw_val[1]
            total  = p_end - p_start + 1
            days   = r['days']
            idx    = sess.day_number - r['start']
            p_from = p_start + round(idx / days * total)
            p_to   = p_start + round((idx + 1) / days * total) - 1
            if idx == days - 1:
                p_to = p_end
            sess.pages_from = max(p_start, p_from)
            sess.pages_to   = min(p_end,   p_to)
        else:
            sess.pages_from = None
            sess.pages_to   = None

    db.session.commit()
    flash('تم تحديث عدد الصفحات وإعادة توزيعها على الجلسات ✅', 'success')
    return redirect(url_for('scheduler.view_schedule', schedule_id=schedule_id))


@scheduler_bp.route('/<int:schedule_id>/delete', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    """حذف الجدول"""
    schedule = StudySchedule.query.get_or_404(schedule_id)
    name = schedule.student_name
    db.session.delete(schedule)
    db.session.commit()
    flash(f'تم حذف جدول "{name}"', 'info')
    return redirect(url_for('scheduler.index'))


# ─── AJAX APIs ────────────────────────────────────────────────────────────────
@scheduler_bp.route('/<int:schedule_id>/session/<int:session_id>/toggle', methods=['POST'])
@login_required
def toggle_session(schedule_id, session_id):
    """تبديل حالة إتمام الجلسة (مكتملة / غير مكتملة)"""
    session = StudySession.query.filter_by(
        id=session_id, schedule_id=schedule_id
    ).first_or_404()

    session.is_completed = not session.is_completed
    db.session.commit()

    schedule = StudySchedule.query.get(schedule_id)
    return jsonify({
        'ok':              True,
        'isCompleted':     session.is_completed,
        'completionPct':   schedule.completion_percent,
        'completedCount':  schedule.completed_sessions,
        'totalCount':      schedule.total_sessions,
    })


@scheduler_bp.route('/<int:schedule_id>/session/<int:session_id>/update', methods=['POST'])
@login_required
def update_session(schedule_id, session_id):
    """تحديث بيانات جلسة (المادة، الوقت)"""
    session = StudySession.query.filter_by(
        id=session_id, schedule_id=schedule_id
    ).first_or_404()

    data = request.get_json(silent=True) or {}

    if 'subject' in data and data['subject'] in SUBJECTS:
        session.subject = data['subject']
    if 'startTime' in data:
        session.start_time = data['startTime']
    if 'endTime' in data:
        session.end_time = data['endTime']

    # إعادة حساب المدة
    try:
        sh, sm = map(int, session.start_time.split(':'))
        eh, em = map(int, session.end_time.split(':'))
        dur = (eh * 60 + em) - (sh * 60 + sm)
        if dur > 0:
            session.duration_minutes = dur
    except Exception:
        pass

    db.session.commit()
    return jsonify({'ok': True, 'session': session.to_dict()})


# ─── API: مواعيد التحصيلي للـ AJAX ───────────────────────────────────────────
@scheduler_bp.route('/api/tahsili-dates')
@login_required
def api_tahsili_dates():
    """إرجاع مواعيد التحصيلي من Firestore للاستخدام في AJAX"""
    periods = _get_tahsili_periods()
    return jsonify({'ok': True, 'periods': periods})


# ─── Exam date ────────────────────────────────────────────────────────────────
@scheduler_bp.route('/<int:schedule_id>/exam-date', methods=['POST'])
@login_required
def update_exam_date(schedule_id):
    """تحديث / مسح تاريخ الاختبار التحصيلي"""
    schedule = StudySchedule.query.get_or_404(schedule_id)
    exam_date_str = (request.get_json(silent=True) or {}).get('examDate') \
                    or request.form.get('exam_date', '').strip()
    if exam_date_str:
        try:
            schedule.exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'تاريخ غير صحيح'}), 400
    else:
        schedule.exam_date = None

    db.session.commit()
    return jsonify({
        'ok':            True,
        'examDate':      schedule.exam_date.strftime('%Y-%m-%d') if schedule.exam_date else None,
        'daysUntilExam': schedule.days_until_exam,
    })


# ─── PDF Export ───────────────────────────────────────────────────────────────
@scheduler_bp.route('/<int:schedule_id>/pdf')
@login_required
def export_pdf(schedule_id):
    """تصدير الجدول كملف PDF باستخدام WeasyPrint"""
    schedule = StudySchedule.query.get_or_404(schedule_id)

    sessions_by_day: dict[int, list[StudySession]] = {}
    for s in schedule.sessions:
        sessions_by_day.setdefault(s.day_number, []).append(s)
    for day_sessions in sessions_by_day.values():
        day_sessions.sort(key=lambda x: x.order_index)

    days_dates = {
        day: schedule.start_date + timedelta(days=day - 1)
        for day in range(1, schedule.duration + 1)
    }

    html_content = render_template(
        'scheduler/pdf.html',
        schedule=schedule,
        sessions_by_day=sessions_by_day,
        days_dates=days_dates,
        today_date=date.today(),
        subject_ranges=_subject_block_ranges(schedule.duration),
    )

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(
            string=html_content,
            base_url=request.url_root
        ).write_pdf()

        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        encoded = quote(f'جدول-{schedule.student_name}.pdf', safe='')
        response.headers['Content-Disposition'] = (
            f"attachment; filename*=UTF-8''{encoded}"
        )
        return response

    except ImportError:
        # WeasyPrint غير متاح — أرسل HTML بدلاً منه
        logger.warning('WeasyPrint not available, serving HTML fallback')
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as exc:
        logger.error(f'PDF generation error: {exc}')
        flash('حدث خطأ أثناء توليد PDF', 'error')
        return redirect(url_for('scheduler.view_schedule', schedule_id=schedule_id))


# ─── Mobile API ────────────────────────────────────────────────────────────────
@scheduler_bp.route('/api/mobile/schedules')
def mobile_list_schedules():
    """قائمة جداول الطالب — للموبايل"""
    student_id = _get_mobile_student_id()
    if student_id is None:
        return jsonify({'ok': False, 'error': 'يجب تسجيل الدخول'}), 401
    schedules = (StudySchedule.query
                 .filter_by(student_id=student_id)
                 .order_by(StudySchedule.created_at.desc())
                 .all())
    return jsonify({'ok': True, 'schedules': [s.to_summary_dict() for s in schedules]})


@scheduler_bp.route('/api/mobile/schedules/create', methods=['POST'])
def mobile_create_schedule():
    """إنشاء جدول جديد من الموبايل — JSON body"""
    student_id = _get_mobile_student_id()
    if student_id is None:
        return jsonify({'ok': False, 'error': 'يجب تسجيل الدخول'}), 401

    data         = request.get_json(silent=True) or {}
    student_name = (data.get('studentName') or '').strip()
    duration     = data.get('duration', 30)
    daily_hours  = data.get('dailyHours', 4.0)
    start_date_s = (data.get('startDate') or '').strip()
    exam_date_s  = (data.get('examDate') or '').strip()
    pages        = data.get('pages') or {}

    # ── Auto-fill student_name from DB if not provided ──
    if not student_name:
        try:
            from src.models.student import Student
            student = Student.query.get(student_id)
            if student:
                student_name = getattr(student, 'name', None) or getattr(student, 'username', '') or ''
        except Exception:
            pass
    if not student_name:
        student_name = 'طالب'
    try:
        duration = int(duration)
        if duration not in (15, 30, 60):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'المدة يجب أن تكون 15 أو 30 أو 60 يوماً'}), 400
    try:
        daily_hours = float(daily_hours)
        if not (1 <= daily_hours <= 16):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'عدد الساعات يجب أن يكون بين 1 و 16'}), 400
    try:
        start = datetime.strptime(start_date_s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'تاريخ البداية غير صحيح'}), 400

    exam_date = None
    if exam_date_s:
        try:
            exam_date = datetime.strptime(exam_date_s, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    # ── Subject pages ──
    subject_pages = {}
    key_map = {'math': 'رياضيات', 'physics': 'فيزياء', 'chem': 'كيمياء', 'bio': 'أحياء'}
    for key, subj in key_map.items():
        raw = (pages.get(key) or '').strip()
        if raw:
            ps, pe = _parse_pages_input(raw)
            if pe > ps >= 1:
                subject_pages[subj] = [ps, pe]

    schedule = StudySchedule(
        student_id    = student_id,
        student_name  = student_name,
        duration      = duration,
        daily_hours   = daily_hours,
        start_date    = start,
        exam_date     = exam_date,
        subject_pages = json.dumps(subject_pages, ensure_ascii=False) if subject_pages else None,
    )
    db.session.add(schedule)
    db.session.flush()

    for sess in _generate_sessions(schedule):
        db.session.add(sess)
    db.session.commit()

    return jsonify({'ok': True, 'schedule': schedule.to_dict()}), 201


@scheduler_bp.route('/api/mobile/schedules/<int:schedule_id>')
def mobile_get_schedule(schedule_id):
    """تفاصيل جدول + جلساته — للموبايل"""
    student_id = _get_mobile_student_id()
    if student_id is None:
        return jsonify({'ok': False, 'error': 'يجب تسجيل الدخول'}), 401

    schedule = StudySchedule.query.filter_by(id=schedule_id, student_id=student_id).first()
    if not schedule:
        return jsonify({'ok': False, 'error': 'الجدول غير موجود أو لا تملك صلاحية الوصول إليه'}), 404

    return jsonify({'ok': True, 'schedule': schedule.to_dict()})


@scheduler_bp.route('/api/mobile/schedules/<int:schedule_id>/session/<int:session_id>/toggle', methods=['POST'])
def mobile_toggle_session(schedule_id, session_id):
    """تبديل حالة إتمام الجلسة — للموبايل (بدون @login_required)"""
    student_id = _get_mobile_student_id()
    if student_id is None:
        return jsonify({'ok': False, 'error': 'يجب تسجيل الدخول'}), 401

    schedule = StudySchedule.query.filter_by(id=schedule_id, student_id=student_id).first()
    if not schedule:
        return jsonify({'ok': False, 'error': 'الجدول غير موجود'}), 404

    sess = StudySession.query.filter_by(id=session_id, schedule_id=schedule_id).first()
    if not sess:
        return jsonify({'ok': False, 'error': 'الجلسة غير موجودة'}), 404

    sess.is_completed = not sess.is_completed
    db.session.commit()

    return jsonify({
        'ok':           True,
        'isCompleted':  sess.is_completed,
        'completionPct': schedule.completion_percent,
        'completedCount': schedule.completed_sessions,
        'totalCount':   schedule.total_sessions,
    })


@scheduler_bp.route('/api/mobile/schedules/<int:schedule_id>/pdf')
def mobile_export_pdf(schedule_id):
    """تصدير الجدول كـ PDF — للموبايل (بدون @login_required)"""
    student_id = _get_mobile_student_id()
    if student_id is None:
        return jsonify({'ok': False, 'error': 'يجب تسجيل الدخول'}), 401

    schedule = StudySchedule.query.filter_by(id=schedule_id, student_id=student_id).first()
    if not schedule:
        return jsonify({'ok': False, 'error': 'الجدول غير موجود'}), 404

    sessions_by_day: dict[int, list[StudySession]] = {}
    for s in schedule.sessions:
        sessions_by_day.setdefault(s.day_number, []).append(s)
    for day_sessions in sessions_by_day.values():
        day_sessions.sort(key=lambda x: x.order_index)

    days_dates = {
        day: schedule.start_date + timedelta(days=day - 1)
        for day in range(1, schedule.duration + 1)
    }

    html_content = render_template(
        'scheduler/pdf.html',
        schedule=schedule,
        sessions_by_day=sessions_by_day,
        days_dates=days_dates,
        today_date=date.today(),
        subject_ranges=_subject_block_ranges(schedule.duration),
    )

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(
            string=html_content,
            base_url=request.url_root
        ).write_pdf()

        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        encoded = quote(f'جدول-{schedule.student_name}.pdf', safe='')
        response.headers['Content-Disposition'] = (
            f"attachment; filename*=UTF-8''{encoded}"
        )
        return response

    except ImportError:
        return jsonify({'ok': False, 'error': 'خدمة PDF غير متاحة حالياً'}), 503
    except Exception as exc:
        logger.error(f'Mobile PDF generation error: {exc}')
        return jsonify({'ok': False, 'error': 'خطأ في توليد PDF'}), 500


@scheduler_bp.route('/api/mobile/schedules/<int:schedule_id>/exam-date', methods=['POST'])
def mobile_update_exam_date(schedule_id):
    """تحديث / مسح تاريخ الاختبار — للموبايل (بدون @login_required)"""
    student_id = _get_mobile_student_id()
    if student_id is None:
        return jsonify({'ok': False, 'error': 'يجب تسجيل الدخول'}), 401

    schedule = StudySchedule.query.filter_by(id=schedule_id, student_id=student_id).first()
    if not schedule:
        return jsonify({'ok': False, 'error': 'الجدول غير موجود'}), 404

    exam_date_str = ((request.get_json(silent=True) or {}).get('examDate') or '').strip()
    if exam_date_str:
        try:
            schedule.exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'تاريخ غير صحيح'}), 400
    else:
        schedule.exam_date = None

    db.session.commit()
    return jsonify({
        'ok':            True,
        'examDate':      schedule.exam_date.strftime('%Y-%m-%d') if schedule.exam_date else None,
        'daysUntilExam': schedule.days_until_exam,
    })
