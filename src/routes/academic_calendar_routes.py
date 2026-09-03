# src/routes/academic_calendar_routes.py
"""مسرد إعداد الدروس — تقويم دراسي (تواريخ + إجازات + توزيع دروس تلقائي)"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from functools import wraps

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
            if day.get('is_holiday'):
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
            day.setdefault('homework', '')
            day.setdefault('notes', '')
            day.setdefault('holiday_label', None)
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
        weeks = data.get('weeks') or []

        if not course_id or not semester_number or not academic_year_label:
            return jsonify({'success': False, 'error': 'course_id و semester_number و academic_year_label مطلوبة'}), 400

        course = Course.query.get(course_id)
        if not course:
            return jsonify({'success': False, 'error': 'المقرر غير موجود'}), 404

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
                if 'homework' in data:
                    day['homework'] = data.get('homework')
                if 'notes' in data:
                    day['notes'] = data.get('notes')
                if 'is_holiday' in data:
                    day['is_holiday'] = data.get('is_holiday')
                if 'holiday_label' in data:
                    day['holiday_label'] = data.get('holiday_label')
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
