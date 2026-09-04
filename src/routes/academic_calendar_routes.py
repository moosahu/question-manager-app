# src/routes/academic_calendar_routes.py
"""مسرد إعداد الدروس — تقويم دراسي (تواريخ + إجازات + توزيع دروس تلقائي)"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timedelta
from hijridate import Gregorian

try:
    from src.extensions import db
    from src.models.academic_calendar import AcademicCalendar
    from src.models.curriculum import Lesson, Unit, Course
except ImportError:  # pragma: no cover
    from extensions import db
    from models.academic_calendar import AcademicCalendar
    from models.curriculum import Lesson, Unit, Course

academic_calendar_bp = Blueprint('academic_calendar', __name__, url_prefix='/api/academic-calendar')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'يجب تسجيل الدخول'}), 401
        if not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated


_ARABIC_WEEKDAY = {
    6: 'الأحد',      # Python weekday(): Monday=0 ... Sunday=6
    0: 'الاثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
}
_ARABIC_WEEK_ORDINALS = [
    'الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع', 'الثامن', 'التاسع', 'العاشر',
    'الحادي عشر', 'الثاني عشر', 'الثالث عشر', 'الرابع عشر', 'الخامس عشر', 'السادس عشر',
    'السابع عشر', 'الثامن عشر', 'التاسع عشر', 'العشرون', 'الحادي والعشرون', 'الثاني والعشرون',
]


def _week_label(n):
    """رقم -> اسم أسبوع عربي (١، ٢، ٣...)؛ يرجع الرقم نفسه لو تعدّى القائمة الجاهزة"""
    return _ARABIC_WEEK_ORDINALS[n - 1] if 1 <= n <= len(_ARABIC_WEEK_ORDINALS) else str(n)


def _generate_weeks_from_range(start_date_str, end_date_str, holidays, class_weekdays=None):
    """يبني هيكل الأسابيع/الأيام تلقائياً من تاريخ بداية/نهاية ميلادي، مستثنياً الجمعة/السبت،
    ومحوّلاً كل تاريخ للهجري للعرض، ومعلّماً أيام الإجازات المحددة.
    class_weekdays: مجموعة أرقام weekday() (الاثنين=0..الأحد=6) للأيام اللي فيها حصة لهذا المقرر —
    None يعني كل أيام الأسبوع الدراسي (الأحد-الخميس) فيها حصة (السلوك الافتراضي القديم)"""
    start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    if end < start:
        raise ValueError('تاريخ النهاية قبل تاريخ البداية')

    # حوّل نطاقات الإجازات/الاختبارات لتواريخ فعلية
    # type: 'holiday' (إجازة، برتقالي) أو 'exam' (اختبارات نهاية الفصل، وردي)
    holiday_ranges = []
    for h in (holidays or []):
        try:
            h_start = datetime.strptime(h['start_date'], '%Y-%m-%d').date()
            h_end = datetime.strptime(h.get('end_date') or h['start_date'], '%Y-%m-%d').date()
            h_type = h.get('type') or 'holiday'
            default_label = 'اختبارات نهاية الفصل الدراسي' if h_type == 'exam' else 'إجازة'
            holiday_ranges.append((h_start, h_end, h.get('label') or default_label, h_type))
        except Exception:
            continue

    def _holiday_label_for(d):
        for h_start, h_end, label, h_type in holiday_ranges:
            if h_start <= d <= h_end:
                return label, h_type
        return None, None

    weeks = []
    current_week_days = []
    week_num = 0
    d = start
    while d <= end:
        wd = d.weekday()
        if wd in _ARABIC_WEEKDAY:  # يستثني الجمعة (4) والسبت (5) تلقائياً
            hijri = Gregorian(d.year, d.month, d.day).to_hijri()
            holiday_label, day_type = _holiday_label_for(d)
            if day_type is None and class_weekdays is not None and wd not in class_weekdays:
                day_type = 'no_class'  # يوم دراسي عادي لكن ما فيه حصة لهذا المقرر
            current_week_days.append({
                'day_name': _ARABIC_WEEKDAY[wd],
                'hijri_date': f'{hijri.day}/{hijri.month}',
                'is_holiday': holiday_label is not None,
                'holiday_label': holiday_label,
                'day_type': day_type or 'study',  # study | holiday | exam | no_class
            })
            if len(current_week_days) == 5:
                week_num += 1
                weeks.append({'week_number': week_num, 'week_label': _week_label(week_num), 'days': current_week_days})
                current_week_days = []
        d += timedelta(days=1)

    if current_week_days:  # آخر أسبوع ناقص (أقل من 5 أيام)
        week_num += 1
        weeks.append({'week_number': week_num, 'week_label': _week_label(week_num), 'days': current_week_days})

    return weeks


def _auto_fill_lessons(course_id, weeks):
    """يوزّع دروس المقرر (بالترتيب: وحدة فوحدة، درس فدرس) على الأيام غير العطلة تسلسلياً"""
    units = Unit.query.filter_by(course_id=course_id).order_by(Unit.order_num).all()
    lesson_queue = []
    for u in units:
        lessons = Lesson.query.filter_by(unit_id=u.id).order_by(Lesson.order_num).all()
        for l in lessons:
            lesson_queue.append({
                'unit_id': u.id, 'unit_name': u.name,
                'lesson_id': l.id, 'lesson_name': l.name,
            })

    idx = 0
    for week in weeks:
        for day in week.get('days', []):
            if day.get('is_holiday') or day.get('day_type') == 'no_class':
                day['unit_id'] = None
                day['unit_name'] = None
                day['lesson_id'] = None
                day['lesson_name'] = None
            elif idx < len(lesson_queue):
                item = lesson_queue[idx]
                day['unit_id'] = item['unit_id']
                day['unit_name'] = item['unit_name']
                day['lesson_id'] = item['lesson_id']
                day['lesson_name'] = item['lesson_name']
                idx += 1
            else:
                day['unit_id'] = None
                day['unit_name'] = None
                day['lesson_id'] = None
                day['lesson_name'] = None
            day.setdefault('period_number', 1)
            day.setdefault('section', '')
            day.setdefault('solved_problems', '')
            day.setdefault('homework', '')
            day.setdefault('notes', '')
            day.setdefault('holiday_label', None)
            day.setdefault('day_type', 'exam' if day.get('is_holiday') and 'اختبار' in (day.get('holiday_label') or '') else ('holiday' if day.get('is_holiday') else 'study'))
    return weeks, len(lesson_queue), idx


@academic_calendar_bp.route('/page', methods=['GET'])
@login_required
@admin_required
def calendar_page():
    """صفحة مسرد إعداد الدروس"""
    return render_template('academic_calendar.html')


@academic_calendar_bp.route('/list', methods=['GET'])
@login_required
@admin_required
def list_calendars():
    """قائمة كل التقاويم المحفوظة (بدون weeks_data الكاملة لتخفيف الحمل)"""
    try:
        calendars = AcademicCalendar.query.order_by(AcademicCalendar.updated_at.desc()).all()
        return jsonify({
            'success': True,
            'calendars': [{
                'id': c.id,
                'course_id': c.course_id,
                'course_name': c.course.name if c.course else None,
                'semester_number': c.semester_number,
                'academic_year_label': c.academic_year_label,
                'weeks_count': len(c.weeks_data or []),
            } for c in calendars],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@academic_calendar_bp.route('/<int:calendar_id>', methods=['GET'])
@login_required
@admin_required
def get_calendar(calendar_id):
    try:
        cal = AcademicCalendar.query.get(calendar_id)
        if not cal:
            return jsonify({'success': False, 'error': 'التقويم غير موجود'}), 404
        return jsonify({'success': True, 'calendar': cal.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@academic_calendar_bp.route('/setup', methods=['POST'])
@login_required
@admin_required
def setup_calendar():
    """إنشاء تقويم جديد: يستقبل هيكل الأسابيع/الأيام (تواريخ + إجازات) ويوزّع دروس المنهج عليه تلقائياً"""
    try:
        data = request.get_json() or {}
        course_id = data.get('course_id')
        semester_number = data.get('semester_number')
        academic_year_label = (data.get('academic_year_label') or '').strip()

        if not course_id or not semester_number or not academic_year_label:
            return jsonify({'success': False, 'error': 'course_id و semester_number و academic_year_label مطلوبة'}), 400

        course = Course.query.get(course_id)
        if not course:
            return jsonify({'success': False, 'error': 'المقرر غير موجود'}), 404

        # ✅ طريقتان لبناء الأسابيع: (أ) تاريخ بداية/نهاية + إجازات (تلقائي، موصى به)
        #    (ب) هيكل weeks جاهز يدوياً (الطريقة القديمة، تبقى مدعومة)
        if data.get('start_date') and data.get('end_date'):
            # class_weekdays: أرقام weekday() (الاثنين=0..الأحد=6) للأيام اللي فيها حصة لهذا المقرر
            # ما تُرسل = كل أيام الأسبوع الدراسي فيها حصة (الافتراضي)
            raw_class_weekdays = data.get('class_weekdays')
            class_weekdays = set(raw_class_weekdays) if raw_class_weekdays else None
            try:
                weeks = _generate_weeks_from_range(
                    data['start_date'], data['end_date'], data.get('holidays') or [], class_weekdays)
            except ValueError as ve:
                return jsonify({'success': False, 'error': str(ve)}), 400
        else:
            weeks = data.get('weeks') or []

        if not weeks:
            return jsonify({'success': False, 'error': 'ما فيه أيام دراسية بالنطاق المحدد'}), 400

        existing = AcademicCalendar.query.filter_by(
            course_id=course_id, semester_number=semester_number,
            academic_year_label=academic_year_label,
        ).first()
        if existing:
            return jsonify({'success': False, 'error': 'يوجد تقويم محفوظ مسبقاً بنفس المقرر والفصل والعام — عدّله من شاشة التعديل بدل إنشاء واحد جديد'}), 400

        weeks, total_lessons, used_lessons = _auto_fill_lessons(course_id, weeks)

        cal = AcademicCalendar(
            course_id=course_id,
            semester_number=semester_number,
            academic_year_label=academic_year_label,
            weeks_data=weeks,
        )
        db.session.add(cal)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تم إنشاء التقويم وتوزيع الدروس تلقائياً',
            'calendar': cal.to_dict(),
            'total_lessons': total_lessons,
            'used_lessons': used_lessons,
        })
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error setting up academic calendar: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@academic_calendar_bp.route('/<int:calendar_id>/regenerate', methods=['POST'])
@login_required
@admin_required
def regenerate_calendar(calendar_id):
    """إعادة توزيع الدروس تلقائياً من جديد (لو تغيّر المنهج) — يمسح أي تعديل يدوي سابق"""
    try:
        cal = AcademicCalendar.query.get(calendar_id)
        if not cal:
            return jsonify({'success': False, 'error': 'التقويم غير موجود'}), 404

        weeks, total_lessons, used_lessons = _auto_fill_lessons(cal.course_id, cal.weeks_data or [])
        cal.weeks_data = weeks
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تم إعادة التوزيع',
            'calendar': cal.to_dict(),
            'total_lessons': total_lessons,
            'used_lessons': used_lessons,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@academic_calendar_bp.route('/<int:calendar_id>/day', methods=['PUT'])
@login_required
@admin_required
def update_day(calendar_id):
    """تعديل خانة يوم واحد يدوياً (موضوع الدرس/الواجب/الملاحظات)"""
    try:
        cal = AcademicCalendar.query.get(calendar_id)
        if not cal:
            return jsonify({'success': False, 'error': 'التقويم غير موجود'}), 404

        data = request.get_json() or {}
        week_number = data.get('week_number')
        day_name = data.get('day_name')
        if week_number is None or not day_name:
            return jsonify({'success': False, 'error': 'week_number و day_name مطلوبة'}), 400

        weeks = cal.weeks_data or []
        found = False
        for week in weeks:
            if week.get('week_number') != week_number:
                continue
            for day in week.get('days', []):
                if day.get('day_name') != day_name:
                    continue
                if 'lesson_id' in data:
                    day['lesson_id'] = data.get('lesson_id')
                if 'lesson_name' in data:
                    day['lesson_name'] = data.get('lesson_name')
                if 'unit_id' in data:
                    day['unit_id'] = data.get('unit_id')
                if 'unit_name' in data:
                    day['unit_name'] = data.get('unit_name')
                if 'period_number' in data:
                    day['period_number'] = data.get('period_number')
                if 'section' in data:
                    day['section'] = data.get('section')
                if 'solved_problems' in data:
                    day['solved_problems'] = data.get('solved_problems')
                if 'homework' in data:
                    day['homework'] = data.get('homework')
                if 'notes' in data:
                    day['notes'] = data.get('notes')
                if 'is_holiday' in data:
                    day['is_holiday'] = data.get('is_holiday')
                if 'holiday_label' in data:
                    day['holiday_label'] = data.get('holiday_label')
                if 'day_type' in data:
                    day['day_type'] = data.get('day_type')  # study | holiday | exam
                found = True
                break
            if found:
                break

        if not found:
            return jsonify({'success': False, 'error': 'اليوم غير موجود بهذا التقويم'}), 404

        cal.weeks_data = weeks
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم الحفظ'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@academic_calendar_bp.route('/<int:calendar_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_calendar(calendar_id):
    try:
        cal = AcademicCalendar.query.get(calendar_id)
        if not cal:
            return jsonify({'success': False, 'error': 'التقويم غير موجود'}), 404
        db.session.delete(cal)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم الحذف'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
