"""
Lesson Prep Routes - واجهات API لتحضير الدروس بالذكاء الاصطناعي
"""
import threading
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import current_user
from functools import wraps
from datetime import datetime, timezone, timedelta
import json
import io
import os
import logging
import requests

from sqlalchemy import func

from src.extensions import db, socketio
from flask_socketio import join_room, leave_room
from src.models.textbook import LessonPlan, LessonPages, AIUsageLog
from src.models.curriculum import Lesson, Unit, Course
from src.models.teacher import Teacher
from src.models.ai_analysis import AISetting
from src.models.shared_plan import SharedPlan
from src.models.plan_rating import PlanRating
from src.models.teacher_feature import TeacherFeatureOverride, FEATURE_DEFAULTS

logger = logging.getLogger(__name__)

lesson_prep_bp = Blueprint('lesson_prep', __name__, url_prefix='/api/lesson-prep')


# ============================================================
# حدود الاستخدام للمعلمين
# ============================================================

# الحدود الافتراضية يومياً
DEFAULT_QUOTAS = {
    'single_lesson': 5,
    'unit_distribution': 2,
    'semester_distribution': 2,
    'worksheet': 3,
}

def _is_feature_enabled(teacher_id, feature_key):
    """
    هل الميزة مفعّلة لهذا المعلم؟
    1) تحقق من override خاص بالمعلم
    2) رجوع للإعداد العام (AISetting)
    3) رجوع للقيمة الافتراضية
    """
    override = TeacherFeatureOverride.query.filter_by(
        teacher_id=teacher_id, feature_key=feature_key
    ).first()
    if override:
        return override.value.lower() == 'true'
    global_val = AISetting.get_setting(feature_key)
    if global_val is not None:
        return str(global_val).lower() == 'true'
    default = FEATURE_DEFAULTS.get(feature_key, 'true')
    return default.lower() == 'true'


def _get_teacher_quota(teacher_id):
    """حساب الحصة المتبقية للمعلم اليوم"""
    # حساب بداية اليوم بتوقيت السعودية (UTC+3) ثم تحويل لـ UTC للمقارنة مع created_at
    sa_tz = timezone(timedelta(hours=3))
    sa_now = datetime.now(sa_tz)
    sa_today_start = sa_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = sa_today_start.astimezone(timezone.utc).replace(tzinfo=None)

    # قراءة الحدود — per-teacher override أولاً ثم global ثم default
    quotas = {}
    for plan_type, default_limit in DEFAULT_QUOTAS.items():
        feature_key = f'quota_{plan_type}'
        # 1. per-teacher override
        override = TeacherFeatureOverride.query.filter_by(
            teacher_id=teacher_id, feature_key=feature_key
        ).first()
        if override:
            quotas[plan_type] = int(override.value)
            continue
        # 2. global setting
        saved = AISetting.get_setting(feature_key)
        quotas[plan_type] = int(saved) if saved else default_limit

    # حساب الاستخدام اليوم
    usage = {}
    for plan_type in DEFAULT_QUOTAS:
        count = LessonPlan.query.filter(
            LessonPlan.teacher_id == teacher_id,
            LessonPlan.plan_type == plan_type,
            LessonPlan.created_at >= today_start,
            LessonPlan.status.notin_(['failed']),
        ).count()
        usage[plan_type] = count

    result = {}
    for plan_type in DEFAULT_QUOTAS:
        limit = quotas[plan_type]
        used = usage[plan_type]
        result[plan_type] = {
            'limit': limit,
            'used': used,
            'remaining': max(0, limit - used),
        }
    return result


def _check_quota(teacher_id, plan_type):
    """تحقق إذا المعلم عنده رصيد متبقي - يرجع (allowed, remaining, limit)"""
    if not teacher_id:
        return True, 999, 999  # أدمن بدون حدود

    quota = _get_teacher_quota(teacher_id)
    info = quota.get(plan_type, {'remaining': 0, 'limit': 0})
    return info['remaining'] > 0, info['remaining'], info['limit']


def _get_teacher_from_request():
    """استخراج المعلم من الطلب (JWT أو session)"""
    # 1. أدمن عبر جلسة الويب
    if current_user.is_authenticated:
        if getattr(current_user, 'is_admin', False):
            return None, current_user.id, True  # teacher=None, user_id, is_admin=True

    # 2. معلم عبر session_token
    session_token = (
        request.headers.get('X-Session-Token') or
        (request.get_json(silent=True) or {}).get('session_token') or
        request.args.get('session_token')
    )
    if session_token:
        teacher = Teacher.query.filter_by(session_token=session_token, is_active=True).first()
        if teacher:
            return teacher, teacher.id, False

    # 3. أدمن مع cookie
    if current_user.is_authenticated:
        return None, current_user.id, True

    return None, None, False


def auth_required(f):
    """Decorator للتحقق من تسجيل الدخول (معلم أو أدمن)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        teacher, user_id, is_admin = _get_teacher_from_request()
        if not user_id:
            return jsonify({'success': False, 'error': 'يرجى تسجيل الدخول'}), 401
        kwargs['teacher'] = teacher
        kwargs['user_id'] = user_id
        kwargs['is_admin'] = is_admin
        return f(*args, **kwargs)
    return decorated_function


@lesson_prep_bp.route('/quota', methods=['GET'])
@auth_required
def get_quota(teacher=None, user_id=None, is_admin=False):
    """الحصة المتبقية للمعلم اليوم"""
    try:
        if not teacher:
            # أدمن - بدون حدود
            return jsonify({
                'success': True,
                'data': {t: {'limit': 999, 'used': 0, 'remaining': 999} for t in DEFAULT_QUOTAS},
                'is_admin': True,
            })

        quota = _get_teacher_quota(teacher.id)
        return jsonify({'success': True, 'data': quota, 'is_admin': False})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/generate', methods=['POST'])
@auth_required
def generate_lesson_plan(teacher=None, user_id=None, is_admin=False):
    """بدء توليد تحضير درس (async)"""
    try:
        # فحص تفعيل الميزة + الحصة
        if teacher and not is_admin:
            if not _is_feature_enabled(teacher.id, 'lesson_prep_enabled'):
                return jsonify({
                    'success': False,
                    'error': 'ميزة تحضير الدروس غير مفعّلة لحسابك. تواصل مع المشرف.',
                    'feature_disabled': True,
                }), 403

            allowed, remaining, limit = _check_quota(teacher.id, 'single_lesson')
            if not allowed:
                return jsonify({
                    'success': False,
                    'error': f'تجاوزت الحد اليومي ({limit} تحضيرات). حاول غداً.',
                    'quota_exceeded': True,
                }), 429

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'لا توجد بيانات'}), 400

        lesson_id = data.get('lesson_id')
        if not lesson_id:
            return jsonify({'success': False, 'error': 'معرف الدرس مطلوب'}), 400

        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({'success': False, 'error': 'الدرس غير موجود'}), 404

        # منع التكرار: إذا في طلب نشط لنفس الدرس ونفس المعلم، أرجع الموجود
        teacher_id_val = teacher.id if teacher else None
        existing_active = LessonPlan.query.filter(
            LessonPlan.lesson_id == lesson_id,
            LessonPlan.teacher_id == teacher_id_val,
            LessonPlan.plan_type == 'single_lesson',
            LessonPlan.status.in_(['pending', 'generating', 'rate_limited']),
        ).order_by(LessonPlan.id.desc()).first()
        if existing_active:
            logger.info(f"⚠️ طلب مكرر - إرجاع plan #{existing_active.id} النشط للمعلم {teacher_id_val}")
            return jsonify({
                'success': True,
                'data': {
                    'plan_id': existing_active.id,
                    'status': existing_active.status,
                    'duplicate': True,
                }
            })

        # Cache: بحث عن تحضير مكتمل بنفس المعايير (للمعلمين فقط)
        if teacher and not is_admin:
            student_level = data.get('student_level', 'متفاوت')
            student_count = data.get('student_count', 30)
            weak_count = data.get('weak_students_count', 5)
            excellent_count = data.get('excellent_students_count', 5)
            focus_area = data.get('focus_area', 'شامل')
            examples_count = data.get('examples_count', 5)

            cached = LessonPlan.query.filter_by(
                lesson_id=lesson_id,
                plan_type='single_lesson',
                student_level=student_level,
                student_count=student_count,
                weak_students_count=weak_count,
                excellent_students_count=excellent_count,
                focus_area=focus_area,
                examples_count=examples_count,
                include_support_plan=bool(data.get('include_support_plan', False)),
                status='completed',
            ).filter(
                LessonPlan.plan_data.isnot(None),
            ).first()

            if cached and cached.plan_data:
                new_plan = LessonPlan(
                    lesson_id=lesson_id,
                    teacher_id=teacher.id,
                    plan_type='single_lesson',
                    ai_provider=cached.ai_provider,
                    plan_data=dict(cached.plan_data),
                    pdf_file_url=cached.pdf_file_url,
                    student_level=student_level,
                    student_count=student_count,
                    weak_students_count=weak_count,
                    excellent_students_count=excellent_count,
                    focus_area=focus_area,
                    examples_count=examples_count,
                    status='completed',
                )
                db.session.add(new_plan)
                db.session.commit()
                logger.info(f"📦 Cache hit! تحضير #{cached.id} → نسخة #{new_plan.id} للمعلم {teacher.id}")
                return jsonify({
                    'success': True,
                    'data': {
                        'plan_id': new_plan.id,
                        'status': 'completed',
                        'cached': True,
                        'data': new_plan.to_dict(),
                    }
                })

        # إنشاء طلب تحضير
        plan = LessonPlan(
            lesson_id=lesson_id,
            teacher_id=teacher.id if teacher else None,
            plan_type='single_lesson',
            student_level=data.get('student_level', 'متفاوت'),
            student_count=data.get('student_count', 30),
            weak_students_count=data.get('weak_students_count', 5),
            excellent_students_count=data.get('excellent_students_count', 5),
            focus_area=data.get('focus_area', 'شامل'),
            examples_count=data.get('examples_count', 5),
            include_support_plan=bool(data.get('include_support_plan', False)),
            status='pending',
        )
        db.session.add(plan)
        db.session.commit()

        logger.info(f"طلب تحضير جديد #{plan.id} للدرس {lesson_id} من المستخدم {user_id}")

        return jsonify({
            'success': True,
            'data': {
                'plan_id': plan.id,
                'status': 'pending',
                'message': 'جاري توليد التحضير...',
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"خطأ في طلب التحضير: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/unit-distribution', methods=['POST'])
@auth_required
def generate_unit_distribution(teacher=None, user_id=None, is_admin=False):
    """توليد توزيع وحدة كاملة"""
    try:
        # فحص تفعيل الميزة + الحصة
        if teacher and not is_admin:
            if not _is_feature_enabled(teacher.id, 'unit_distribution_enabled'):
                return jsonify({
                    'success': False,
                    'error': 'ميزة توزيع الوحدة غير مفعّلة لحسابك. تواصل مع المشرف.',
                    'feature_disabled': True,
                }), 403

            allowed, remaining, limit = _check_quota(teacher.id, 'unit_distribution')
            if not allowed:
                return jsonify({
                    'success': False,
                    'error': f'تجاوزت الحد اليومي ({limit} توزيعات). حاول غداً.',
                    'quota_exceeded': True,
                }), 429

        data = request.get_json()
        lesson_id = data.get('lesson_id')  # أي درس من الوحدة
        total_periods = data.get('total_periods', 12)
        include_support_plan = data.get('include_support_plan', False)

        if not lesson_id:
            return jsonify({'success': False, 'error': 'معرف الدرس مطلوب'}), 400

        # منع التكرار: إذا في طلب نشط لنفس الوحدة ونفس المعلم
        teacher_id_val = teacher.id if teacher else None
        existing_active_unit = LessonPlan.query.filter(
            LessonPlan.lesson_id == lesson_id,
            LessonPlan.teacher_id == teacher_id_val,
            LessonPlan.plan_type == 'unit_distribution',
            LessonPlan.status.in_(['pending', 'generating', 'rate_limited']),
        ).order_by(LessonPlan.id.desc()).first()
        if existing_active_unit:
            logger.info(f"⚠️ طلب وحدة مكرر - إرجاع plan #{existing_active_unit.id} النشط")
            return jsonify({
                'success': True,
                'data': {
                    'plan_id': existing_active_unit.id,
                    'status': existing_active_unit.status,
                    'duplicate': True,
                }
            })

        # Cache: بحث عن توزيع وحدة مكتمل بنفس الدرس وعدد الحصص (للمعلمين فقط)
        if teacher and not is_admin:
            # نبحث عن أي درس من نفس الوحدة
            lesson_obj = Lesson.query.get(lesson_id)
            if lesson_obj:
                unit_lesson_ids = [l.id for l in Lesson.query.filter_by(unit_id=lesson_obj.unit_id).all()]
                cached = LessonPlan.query.filter(
                    LessonPlan.lesson_id.in_(unit_lesson_ids),
                    LessonPlan.plan_type == 'unit_distribution',
                    LessonPlan.student_count == total_periods,
                    LessonPlan.include_support_plan == bool(include_support_plan),
                    LessonPlan.status == 'completed',
                    LessonPlan.plan_data.isnot(None),
                ).first()

                if cached and cached.plan_data:
                    new_plan = LessonPlan(
                        lesson_id=lesson_id,
                        teacher_id=teacher.id,
                        plan_type='unit_distribution',
                        ai_provider=cached.ai_provider,
                        plan_data=dict(cached.plan_data),
                        pdf_file_url=cached.pdf_file_url,
                        student_count=total_periods,
                        status='completed',
                    )
                    db.session.add(new_plan)
                    db.session.commit()
                    logger.info(f"📦 Cache hit (unit)! #{cached.id} → #{new_plan.id} للمعلم {teacher.id}")
                    return jsonify({
                        'success': True,
                        'data': {
                            'plan_id': new_plan.id,
                            'status': 'completed',
                            'cached': True,
                            'data': new_plan.to_dict(),
                        }
                    })

        plan = LessonPlan(
            lesson_id=lesson_id,
            teacher_id=teacher.id if teacher else None,
            plan_type='unit_distribution',
            status='pending',
            student_count=total_periods,  # نستخدم هذا الحقل مؤقتاً لتخزين عدد الحصص
            include_support_plan=include_support_plan,
        )
        db.session.add(plan)
        db.session.commit()


        return jsonify({
            'success': True,
            'data': {
                'plan_id': plan.id,
                'status': 'pending',
                'message': 'جاري توليد توزيع الوحدة...',
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/status/<int:plan_id>', methods=['GET'])
@auth_required
def get_plan_status(plan_id, teacher=None, user_id=None, is_admin=False):
    """حالة التوليد (polling)"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        # rate_limited تُعرض كـ generating للتطبيق (الـ scheduler سيعيد المحاولة تلقائياً)
        display_status = 'generating' if plan.status == 'rate_limited' else plan.status

        result = {
            'plan_id': plan.id,
            'status': display_status,
            'progress_message': plan.progress_message,
            'needs_review': plan.needs_review,
        }

        if plan.status == 'pending':
            ahead = LessonPlan.query.filter(
                LessonPlan.status == 'pending',
                LessonPlan.id < plan.id
            ).count()
            generating = LessonPlan.query.filter_by(status='generating').count()
            result['queue_position'] = ahead + generating + 1
            result['queue_total'] = LessonPlan.query.filter(
                LessonPlan.status.in_(['pending', 'generating'])
            ).count()
        elif plan.status == 'generating' or plan.status == 'rate_limited':
            result['queue_position'] = 0

        if plan.status == 'completed':
            result['data'] = plan.to_dict()
        elif plan.status == 'failed':
            result['error'] = plan.error_message

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/queue', methods=['GET'])
@auth_required
def get_queue(teacher=None, user_id=None, is_admin=False):
    """الطابور الحالي - generating + pending"""
    try:
        generating = LessonPlan.query.filter(
            LessonPlan.status.in_(['generating', 'rate_limited'])
        ).order_by(LessonPlan.id).all()
        pending = LessonPlan.query.filter_by(status='pending').order_by(LessonPlan.id).all()
        all_active = generating + pending

        result = []
        for i, plan in enumerate(all_active):
            if not is_admin and teacher and plan.teacher_id != teacher.id:
                continue
            lesson_name = (plan.lesson.name if plan.lesson
                           else (plan.course.name if plan.course else 'تحضير'))
            result.append({
                'id': plan.id,
                'plan_type': plan.plan_type,
                'status': 'generating' if plan.status in ('generating', 'rate_limited') else 'pending',
                'queue_position': i + 1,
                'queue_total': len(all_active),
                'lesson_name': lesson_name,
                'ai_provider': plan.ai_provider,
                'created_at': plan.created_at.isoformat() if plan.created_at else None,
                'teacher_name': plan.teacher.name if plan.teacher else None,
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f'خطأ في جلب الطابور: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/history', methods=['GET'])
@auth_required
def get_history(teacher=None, user_id=None, is_admin=False):
    """تحاضير سابقة"""
    try:
        query = LessonPlan.query.filter_by(status='completed')

        if teacher and not is_admin:
            query = query.filter_by(teacher_id=teacher.id)

        course_id = request.args.get('course_id', type=int)
        if course_id:
            query = query.join(Lesson).join(Unit).filter(Unit.course_id == course_id)

        plans = query.order_by(LessonPlan.created_at.desc()).limit(50).all()
        return jsonify({
            'success': True,
            'data': [p.to_dict() for p in plans]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>', methods=['GET'])
@auth_required
def get_plan(plan_id, teacher=None, user_id=None, is_admin=False):
    """عرض التحضير كـ JSON"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        return jsonify({'success': True, 'data': plan.to_dict()})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/pdf', methods=['GET'])
@auth_required
def download_plan_pdf(plan_id, teacher=None, user_id=None, is_admin=False):
    """تحميل ملف PDF"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        show_answers = request.args.get('show_answers', '1') != '0'
        period_idx = request.args.get('period', type=int)  # حصة واحدة للوحدة
        font_family = request.args.get('font_family', 'cairo')

        # لما يطلب حصة معينة أو خط مخصص، نولّد دائماً on-the-fly
        if not plan.pdf_file_url or period_idx is not None or font_family != 'cairo':
            # توليد PDF on-the-fly
            from src.services.lesson_prep_service import lesson_prep_service
            from src.models.curriculum import Lesson, Unit, Course

            lesson = Lesson.query.get(plan.lesson_id)
            unit = Unit.query.get(lesson.unit_id) if lesson else None
            course = Course.query.get(unit.course_id) if unit else None

            if plan.plan_type == 'semester_distribution':
                course = Course.query.get(plan.course_id) if plan.course_id else None
                pdf_bytes = lesson_prep_service._generate_semester_pdf(
                    plan.plan_data or {},
                    course.name if course else '',
                )
            elif plan.plan_type == 'unit_distribution':
                plan_data = plan.plan_data or {}
                # فلترة حصة واحدة إذا طُلب
                if period_idx is not None:
                    all_periods = plan_data.get('periods', [])
                    single = [p for p in all_periods if p.get('period_number') == period_idx + 1]
                    plan_data = {**plan_data, 'periods': single}
                pdf_bytes = lesson_prep_service._generate_unit_pdf(
                    plan_data,
                    unit.name if unit else '',
                    course.name if course else '',
                    show_answers=show_answers,
                    font_family=font_family,
                )
            else:
                pdf_bytes = lesson_prep_service._generate_pdf(
                    plan.plan_data or {},
                    lesson.name if lesson else 'تحضير',
                    unit.name if unit else '',
                    course.name if course else '',
                    show_answers=show_answers,
                    font_family=font_family,
                )
            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"تحضير_{plan.id}.pdf",
                )
            return jsonify({'success': False, 'error': 'فشل توليد PDF'}), 500

        # إذا URL خارجي
        if plan.pdf_file_url.startswith('http'):
            resp = requests.get(plan.pdf_file_url, timeout=30)
            return send_file(
                io.BytesIO(resp.content),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"تحضير_{plan.id}.pdf",
            )

        # ملف محلي
        import os
        filepath = os.path.join(os.getcwd(), plan.pdf_file_url.lstrip('/'))
        return send_file(filepath, as_attachment=True, download_name=f"تحضير_{plan.id}.pdf")

    except Exception as e:
        logger.error(f"خطأ في تحميل PDF: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>', methods=['DELETE'])
@auth_required
def delete_plan(plan_id, teacher=None, user_id=None, is_admin=False):
    """حذف تحضير"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if not is_admin and teacher and plan.teacher_id != teacher.id:
            return jsonify({'success': False, 'error': 'لا يمكنك حذف تحضير معلم آخر'}), 403

        # حذف ناعم - يختفي من العرض لكن يبقى محسوب في العداد (التكلفة راحت)
        plan.status = 'deleted'
        db.session.commit()

        # لو هذه الخطة كانت في rate_limited → أعد الـ scheduler لـ idle فوراً
        # بدل ما ينتظر 5 دقائق قبل ما يلتقط طلبات جديدة
        try:
            import json as _j
            from sqlalchemy import text as _text
            rate_data_row = db.session.execute(_text(
                "SELECT setting_value FROM ai_settings WHERE setting_key='lesson_prep_job_data'"
            )).fetchone()
            if rate_data_row:
                rate_data = _j.loads(rate_data_row[0])
                if rate_data.get('plan_id') == plan_id:
                    db.session.execute(_text(
                        "UPDATE ai_settings SET setting_value='idle' WHERE setting_key='lesson_prep_job_status'"
                    ))
                    db.session.commit()
                    logger.info(f"🧹 [Delete] أعدنا الـ scheduler لـ idle بعد حذف الخطة #{plan_id} المعلّقة")
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'تم حذف التحضير'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 1: توزيع المنهج الفصلي
# ============================================================

@lesson_prep_bp.route('/semester-distribution/upload', methods=['POST'])
@auth_required
def upload_semester_distribution(teacher=None, user_id=None, is_admin=False):
    """رفع PDF توزيع فصلي + تحليل AI"""
    try:
        # فحص تفعيل الميزة + الحصة
        if teacher and not is_admin:
            if not _is_feature_enabled(teacher.id, 'semester_distribution_enabled'):
                return jsonify({
                    'success': False,
                    'error': 'ميزة التوزيع الفصلي غير مفعّلة لحسابك. تواصل مع المشرف.',
                    'feature_disabled': True,
                }), 403

            allowed, remaining, limit = _check_quota(teacher.id, 'semester_distribution')
            if not allowed:
                return jsonify({
                    'success': False,
                    'error': f'تجاوزت الحد اليومي ({limit} توزيعات فصلية). حاول غداً.',
                    'quota_exceeded': True,
                }), 429

        course_id = request.form.get('course_id', type=int)
        weekly_periods = request.form.get('weekly_periods', type=int) or 5
        if not course_id:
            data = request.get_json(silent=True) or {}
            course_id = data.get('course_id')
            weekly_periods = data.get('weekly_periods', 5)

        if not course_id:
            return jsonify({'success': False, 'error': 'معرف المقرر مطلوب'}), 400

        course = Course.query.get(course_id)
        if not course:
            return jsonify({'success': False, 'error': 'المقرر غير موجود'}), 404

        # حفظ PDF المرفوع - نحفظ المسار المحلي دائماً لأن Cloudinary يرجع 401
        pdf_url = None
        if 'pdf' in request.files:
            pdf_file = request.files['pdf']
            if pdf_file.filename:
                upload_dir = os.path.join(os.getcwd(), 'uploads', 'semester_pdfs')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"semester_{course_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                filepath = os.path.join(upload_dir, filename)
                pdf_file.save(filepath)
                # نستخدم المسار المحلي الكامل مباشرة - أضمن وأسرع من Cloudinary
                pdf_url = filepath

        plan = LessonPlan(
            course_id=course_id,
            teacher_id=teacher.id if teacher else None,
            plan_type='semester_distribution',
            original_pdf_url=pdf_url,
            status='pending',
            student_count=weekly_periods,
        )
        db.session.add(plan)
        db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'plan_id': plan.id,
                'status': 'pending',
                'message': 'جاري تحليل التوزيع الفصلي...',
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"خطأ في رفع التوزيع الفصلي: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/semester-distribution/<int:plan_id>', methods=['PUT'])
@auth_required
def update_semester_distribution(plan_id, teacher=None, user_id=None, is_admin=False):
    """حفظ تعديلات المعلم على التوزيع الفصلي"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التوزيع غير موجود'}), 404

        if not is_admin and teacher and plan.teacher_id != teacher.id:
            return jsonify({'success': False, 'error': 'غير مسموح'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'لا توجد بيانات'}), 400

        plan.plan_data = data.get('plan_data', plan.plan_data)
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم حفظ التعديلات'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 3: تعديل التحضير بعد التوليد
# ============================================================

@lesson_prep_bp.route('/<int:plan_id>/section', methods=['PUT'])
@auth_required
def update_section(plan_id, teacher=None, user_id=None, is_admin=False):
    """تعديل قسم واحد من التحضير"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if not is_admin and teacher and plan.teacher_id != teacher.id:
            return jsonify({'success': False, 'error': 'غير مسموح'}), 403

        data = request.get_json()
        section_name = data.get('section_name')
        section_data = data.get('section_data')

        if not section_name or section_data is None:
            return jsonify({'success': False, 'error': 'اسم القسم والبيانات مطلوبة'}), 400

        updated = dict(plan.plan_data or {})
        updated[section_name] = section_data
        plan.plan_data = updated
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم تحديث القسم'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/regenerate-section', methods=['POST'])
@auth_required
def regenerate_section(plan_id, teacher=None, user_id=None, is_admin=False):
    """إعادة توليد قسم واحد بالذكاء الاصطناعي"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        data = request.get_json()
        section_name = data.get('section_name')
        if not section_name:
            return jsonify({'success': False, 'error': 'اسم القسم مطلوب'}), 400

        from src.services.lesson_prep_service import lesson_prep_service
        new_section = lesson_prep_service.regenerate_section(plan_id, section_name)

        if new_section:
            updated = dict(plan.plan_data or {})
            updated[section_name] = new_section
            plan.plan_data = updated
            db.session.commit()

            return jsonify({
                'success': True,
                'data': {section_name: new_section},
                'message': 'تم إعادة توليد القسم',
            })
        else:
            return jsonify({'success': False, 'error': 'فشل إعادة التوليد'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/regenerate-pdf', methods=['POST'])
@auth_required
def regenerate_pdf(plan_id, teacher=None, user_id=None, is_admin=False):
    """إعادة توليد PDF بعد التعديلات"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        from src.services.lesson_prep_service import lesson_prep_service

        lesson = Lesson.query.get(plan.lesson_id) if plan.lesson_id else None
        unit = Unit.query.get(lesson.unit_id) if lesson else None
        course = Course.query.get(unit.course_id) if unit else None

        pdf_bytes = None
        if plan.plan_type == 'unit_distribution':
            pdf_bytes = lesson_prep_service._generate_unit_pdf(
                plan.plan_data or {}, unit.name if unit else '', course.name if course else '')
        elif plan.plan_type == 'semester_distribution':
            pdf_bytes = lesson_prep_service._generate_semester_pdf(
                plan.plan_data or {}, course.name if course else '')
        else:
            pdf_bytes = lesson_prep_service._generate_pdf(
                plan.plan_data or {}, lesson.name if lesson else '',
                unit.name if unit else '', course.name if course else '')

        if pdf_bytes:
            pdf_url = None
            try:
                import cloudinary.uploader
                result = cloudinary.uploader.upload(
                    io.BytesIO(pdf_bytes), resource_type='raw',
                    folder='lesson_plans',
                    public_id=f"plan_{plan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                )
                pdf_url = result.get('secure_url') or result.get('url')
            except Exception:
                upload_dir = os.path.join(os.getcwd(), 'uploads', 'lesson_plans')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"plan_{plan_id}.pdf"
                with open(os.path.join(upload_dir, filename), 'wb') as f:
                    f.write(pdf_bytes)
                pdf_url = f"/uploads/lesson_plans/{filename}"

            plan.pdf_file_url = pdf_url
            db.session.commit()

            return jsonify({'success': True, 'data': {'pdf_url': pdf_url}, 'message': 'تم تحديث PDF'})

        return jsonify({'success': False, 'error': 'فشل توليد PDF'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 7: مشاركة بين المعلمين
# ============================================================

@lesson_prep_bp.route('/<int:plan_id>/share', methods=['POST'])
@auth_required
def share_plan(plan_id, teacher=None, user_id=None, is_admin=False):
    """مشاركة تحضير"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if not teacher:
            return jsonify({'success': False, 'error': 'يجب تسجيل الدخول كمعلم'}), 403

        existing = SharedPlan.query.filter_by(plan_id=plan_id).first()
        if existing:
            return jsonify({'success': False, 'error': 'التحضير مشارك بالفعل'}), 400

        data = request.get_json() or {}
        shared = SharedPlan(
            plan_id=plan_id,
            shared_by=teacher.id,
            visibility=data.get('visibility', 'school'),
        )
        db.session.add(shared)
        db.session.commit()

        return jsonify({'success': True, 'message': 'تمت المشاركة بنجاح'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/shared', methods=['GET'])
@auth_required
def get_shared_plans(teacher=None, user_id=None, is_admin=False):
    """المكتبة المشتركة"""
    try:
        query = SharedPlan.query

        # فلتر بالمقرر
        course_id = request.args.get('course_id', type=int)
        if course_id:
            query = query.join(LessonPlan).join(Lesson).join(Unit).filter(Unit.course_id == course_id)

        # بحث نصي
        search = request.args.get('q', '')
        if search:
            query = query.join(LessonPlan).filter(
                LessonPlan.plan_data['lesson_info']['title'].astext.ilike(f'%{search}%')
            )

        shared = query.order_by(SharedPlan.created_at.desc()).limit(50).all()
        return jsonify({
            'success': True,
            'data': [s.to_dict() for s in shared]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/clone', methods=['POST'])
@auth_required
def clone_plan(plan_id, teacher=None, user_id=None, is_admin=False):
    """نسخ تحضير مشترك"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if not teacher:
            return jsonify({'success': False, 'error': 'يجب تسجيل الدخول كمعلم'}), 403

        new_plan = LessonPlan(
            lesson_id=plan.lesson_id,
            teacher_id=teacher.id,
            course_id=plan.course_id,
            plan_type=plan.plan_type,
            plan_data=dict(plan.plan_data or {}),
            student_level=plan.student_level,
            student_count=plan.student_count,
            weak_students_count=plan.weak_students_count,
            excellent_students_count=plan.excellent_students_count,
            focus_area=plan.focus_area,
            examples_count=plan.examples_count,
            status='completed',
        )
        db.session.add(new_plan)

        # تحديث عداد الاستخدام
        shared = SharedPlan.query.filter_by(plan_id=plan_id).first()
        if shared:
            shared.use_count = (shared.use_count or 0) + 1

        db.session.commit()

        return jsonify({
            'success': True,
            'data': new_plan.to_dict(),
            'message': 'تم نسخ التحضير بنجاح',
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 8: تقييم جودة التحضير
# ============================================================

@lesson_prep_bp.route('/<int:plan_id>/rate', methods=['POST'])
@auth_required
def rate_plan(plan_id, teacher=None, user_id=None, is_admin=False):
    """تقييم تحضير"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if not teacher:
            return jsonify({'success': False, 'error': 'يجب تسجيل الدخول كمعلم'}), 403

        data = request.get_json()
        overall = data.get('overall_rating')
        if not overall or not (1 <= overall <= 5):
            return jsonify({'success': False, 'error': 'التقييم يجب أن يكون بين 1 و 5'}), 400

        # تحديث أو إنشاء
        rating = PlanRating.query.filter_by(plan_id=plan_id, teacher_id=teacher.id).first()
        if rating:
            rating.overall_rating = overall
            rating.section_ratings = data.get('section_ratings', rating.section_ratings)
            rating.notes = data.get('notes', rating.notes)
        else:
            rating = PlanRating(
                plan_id=plan_id,
                teacher_id=teacher.id,
                overall_rating=overall,
                section_ratings=data.get('section_ratings', {}),
                notes=data.get('notes', ''),
            )
            db.session.add(rating)

        db.session.commit()

        # تحديث متوسط التقييم في SharedPlan
        shared = SharedPlan.query.filter_by(plan_id=plan_id).first()
        if shared:
            from sqlalchemy import func
            avg = db.session.query(func.avg(PlanRating.overall_rating)).filter_by(plan_id=plan_id).scalar()
            shared.avg_rating = float(avg) if avg else 0
            db.session.commit()

        return jsonify({'success': True, 'message': 'تم حفظ التقييم'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/ratings', methods=['GET'])
@auth_required
def get_plan_ratings(plan_id, teacher=None, user_id=None, is_admin=False):
    """عرض تقييمات تحضير"""
    try:
        ratings = PlanRating.query.filter_by(plan_id=plan_id).order_by(PlanRating.created_at.desc()).all()
        from sqlalchemy import func
        avg = db.session.query(func.avg(PlanRating.overall_rating)).filter_by(plan_id=plan_id).scalar()

        my_teacher_id = teacher.id if teacher else None
        ratings_list = []
        for r in ratings:
            d = r.to_dict()
            d['is_mine'] = (my_teacher_id is not None and r.teacher_id == my_teacher_id)
            ratings_list.append(d)

        return jsonify({
            'success': True,
            'data': {
                'ratings': ratings_list,
                'avg_rating': float(avg) if avg else 0,
                'count': len(ratings),
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 9: توليد أوراق عمل
# ============================================================

@lesson_prep_bp.route('/<int:plan_id>/worksheet', methods=['POST'])
@auth_required
def generate_worksheet(plan_id, teacher=None, user_id=None, is_admin=False):
    """توليد ورقة عمل (async)"""
    try:
        # فحص تفعيل الميزة + الحصة
        if teacher and not is_admin:
            if not _is_feature_enabled(teacher.id, 'worksheet_enabled'):
                return jsonify({
                    'success': False,
                    'error': 'ميزة أوراق العمل غير مفعّلة لحسابك. تواصل مع المشرف.',
                    'feature_disabled': True,
                }), 403

            allowed, remaining, limit = _check_quota(teacher.id, 'worksheet')
            if not allowed:
                return jsonify({
                    'success': False,
                    'error': f'تجاوزت الحد اليومي ({limit} أوراق عمل). حاول غداً.',
                    'quota_exceeded': True,
                }), 429

        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if plan.status != 'completed':
            return jsonify({'success': False, 'error': 'التحضير غير مكتمل'}), 400

        # تشغيل ورقة العمل في thread مستقل (لا يحجب الـscheduler)
        from src.services.lesson_prep_service import lesson_prep_service
        app = current_app._get_current_object()

        def _run_worksheet(app_ctx, pid):
            with app_ctx.app_context():
                try:
                    lesson_prep_service.generate_worksheet(pid)
                except Exception as ex:
                    logger.error(f"❌ خطأ في worksheet thread #{pid}: {ex}")

        t = threading.Thread(target=_run_worksheet, args=(app, plan.id), daemon=True)
        t.start()

        return jsonify({
            'success': True,
            'data': {
                'plan_id': plan.id,
                'status': 'generating',
                'message': 'جاري توليد ورقة العمل...',
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/worksheet/pdf', methods=['GET'])
@auth_required
def download_worksheet_pdf(plan_id, teacher=None, user_id=None, is_admin=False):
    """تحميل PDF ورقة العمل - يدعم ?period=N للوحدات"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        plan_data = plan.plan_data or {}
        ws_type = request.args.get('type', 'student')  # student | teacher
        period_str = request.args.get('period')  # اختياري - للوحدات
        font_family = request.args.get('font_family', 'cairo')  # خط مخصص → يولّد on-the-fly

        show_answers = ws_type == 'teacher'

        # إذا طُلب خط مخصص (غير cairo الافتراضي) → ولّد PDF on-the-fly من البيانات المخزّنة
        if font_family and font_family != 'cairo':
            from src.services.lesson_prep_service import lesson_prep_service
            if period_str is not None:
                # وحدة: ابحث عن بيانات الحصة المخزّنة
                try:
                    period_idx = int(period_str)
                except ValueError:
                    return jsonify({'success': False, 'error': 'رقم الحصة غير صالح'}), 400
                period_worksheets = plan_data.get('period_worksheets', [])
                entry = next((p for p in period_worksheets if p.get('period_index') == period_idx), None)
                ws_data = entry.get('data') if entry else None
                filename = f"worksheet_{ws_type}_p{period_idx}_{plan_id}.pdf"
            else:
                ws_data = plan_data.get('worksheet')
                filename = f"worksheet_{ws_type}_{plan_id}.pdf"

            if ws_data:
                pdf_bytes = lesson_prep_service._generate_worksheet_pdf(
                    ws_data, show_answers=show_answers, font_family=font_family
                )
                if pdf_bytes:
                    return send_file(
                        io.BytesIO(pdf_bytes),
                        mimetype='application/pdf',
                        as_attachment=True,
                        download_name=filename,
                    )
            # fallback: البيانات مفقودة أو فشل التوليد → استخدم الـ URL المخزّن
            # (الخط سيكون الأصلي بدل المطلوب)

        # المسار الافتراضي: استخدم الـ URL المخزّن
        if period_str is not None:
            try:
                period_idx = int(period_str)
            except ValueError:
                return jsonify({'success': False, 'error': 'رقم الحصة غير صالح'}), 400

            period_worksheets = plan_data.get('period_worksheets', [])
            entry = next((p for p in period_worksheets if p.get('period_index') == period_idx), None)
            if not entry:
                return jsonify({'success': False, 'error': f'ورقة عمل الحصة {period_idx} غير موجودة'}), 404

            url = entry.get(f'{ws_type}_pdf_url')
            filename = f"worksheet_{ws_type}_p{period_idx}_{plan_id}.pdf"
        else:
            # درس واحد: المسار القديم
            key = f'worksheet_{ws_type}_pdf'
            url = plan_data.get(key)
            filename = f"worksheet_{ws_type}_{plan_id}.pdf"

        if not url:
            return jsonify({'success': False, 'error': 'ورقة العمل غير موجودة'}), 404

        if url.startswith('http'):
            resp = requests.get(url, timeout=30)
            return send_file(
                io.BytesIO(resp.content),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename,
            )

        import os
        filepath = os.path.join(os.getcwd(), url.lstrip('/'))
        return send_file(filepath, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 12: تتبع تنفيذ المنهج
# ============================================================

@lesson_prep_bp.route('/<int:plan_id>/mark-taught', methods=['PUT'])
@auth_required
def mark_taught(plan_id, teacher=None, user_id=None, is_admin=False):
    """تأشير "تم التدريس" """
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        data = request.get_json() or {}
        is_taught = data.get('is_taught', True)

        plan.is_taught = is_taught
        plan.taught_at = datetime.utcnow() if is_taught else None
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم التحديث'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/progress', methods=['GET'])
@auth_required
def get_progress(teacher=None, user_id=None, is_admin=False):
    """نسبة إنجاز المنهج"""
    try:
        course_id = request.args.get('course_id', type=int)
        if not course_id:
            return jsonify({'success': False, 'error': 'معرف المقرر مطلوب'}), 400

        units = Unit.query.filter_by(course_id=course_id).order_by(Unit.order_num).all()

        total_lessons = 0
        taught_lessons = 0
        prepared_lessons = 0
        unit_progress = []

        for unit in units:
            lessons = Lesson.query.filter_by(unit_id=unit.id).order_by(Lesson.order_num).all()
            unit_total = len(lessons)
            unit_taught = 0
            unit_prepared = 0
            lesson_details = []

            for lesson in lessons:
                total_lessons += 1
                # أحدث تحضير مكتمل للمعلم
                plan_query = LessonPlan.query.filter_by(
                    lesson_id=lesson.id, status='completed'
                )
                if teacher and not is_admin:
                    plan_query = plan_query.filter_by(teacher_id=teacher.id)

                plan = plan_query.order_by(LessonPlan.created_at.desc()).first()

                status = 'not_prepared'
                if plan:
                    unit_prepared += 1
                    prepared_lessons += 1
                    if plan.is_taught:
                        unit_taught += 1
                        taught_lessons += 1
                        status = 'taught'
                    else:
                        status = 'prepared'

                lesson_details.append({
                    'lesson_id': lesson.id,
                    'lesson_name': lesson.name,
                    'status': status,
                    'plan_id': plan.id if plan else None,
                    'taught_at': plan.taught_at.isoformat() if plan and plan.taught_at else None,
                })

            unit_progress.append({
                'unit_id': unit.id,
                'unit_name': unit.name,
                'total': unit_total,
                'prepared': unit_prepared,
                'taught': unit_taught,
                'progress_percent': round(unit_taught / unit_total * 100) if unit_total > 0 else 0,
                'lessons': lesson_details,
            })

        return jsonify({
            'success': True,
            'data': {
                'course_id': course_id,
                'total_lessons': total_lessons,
                'prepared_lessons': prepared_lessons,
                'taught_lessons': taught_lessons,
                'overall_progress': round(taught_lessons / total_lessons * 100) if total_lessons > 0 else 0,
                'units': unit_progress,
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 9: مراقبة تكلفة الذكاء الاصطناعي
# ============================================================

@lesson_prep_bp.route('/costs/summary', methods=['GET'])
@auth_required
def get_cost_summary(teacher=None, user_id=None, is_admin=False):
    """ملخص التكلفة (اليوم/الأسبوع/الشهر)"""
    try:
        sa_tz = timezone(timedelta(hours=3))
        sa_now = datetime.now(sa_tz)

        today_start = sa_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
        week_start = (sa_now - timedelta(days=sa_now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
        month_start = sa_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)

        def _calc_period(start):
            q = db.session.query(
                func.coalesce(func.sum(AIUsageLog.cost_usd), 0),
                func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.output_tokens), 0),
                func.count(AIUsageLog.id),
            ).filter(AIUsageLog.created_at >= start)
            if teacher and not is_admin:
                q = q.filter(AIUsageLog.teacher_id == teacher.id)
            row = q.first()
            return {
                'cost_usd': round(float(row[0]), 6),
                'input_tokens': int(row[1]),
                'output_tokens': int(row[2]),
                'requests': int(row[3]),
            }

        return jsonify({
            'success': True,
            'data': {
                'today': _calc_period(today_start),
                'week': _calc_period(week_start),
                'month': _calc_period(month_start),
            }
        })

    except Exception as e:
        logger.error(f"خطأ في ملخص التكلفة: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/costs/by-teacher', methods=['GET'])
@auth_required
def get_cost_by_teacher(teacher=None, user_id=None, is_admin=False):
    """تكلفة كل معلم (للأدمن فقط)"""
    try:
        if not is_admin:
            return jsonify({'success': False, 'error': 'للأدمن فقط'}), 403

        sa_tz = timezone(timedelta(hours=3))
        sa_now = datetime.now(sa_tz)
        month_start = sa_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)

        from src.models.teacher import Teacher as T
        rows = db.session.query(
            AIUsageLog.teacher_id,
            T.name,
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0),
            func.count(AIUsageLog.id),
        ).outerjoin(T, AIUsageLog.teacher_id == T.id).filter(
            AIUsageLog.created_at >= month_start,
        ).group_by(AIUsageLog.teacher_id, T.name).order_by(
            func.sum(AIUsageLog.cost_usd).desc()
        ).all()

        teachers_data = [{
            'teacher_id': row[0],
            'teacher_name': row[1] or 'أدمن',
            'cost_usd': round(float(row[2]), 6),
            'requests': int(row[3]),
        } for row in rows]

        return jsonify({'success': True, 'data': teachers_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/costs/by-provider', methods=['GET'])
@auth_required
def get_cost_by_provider(teacher=None, user_id=None, is_admin=False):
    """تكلفة كل provider"""
    try:
        sa_tz = timezone(timedelta(hours=3))
        sa_now = datetime.now(sa_tz)
        month_start = sa_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)

        q = db.session.query(
            AIUsageLog.ai_provider,
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0),
            func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.output_tokens), 0),
            func.count(AIUsageLog.id),
        ).filter(AIUsageLog.created_at >= month_start)

        if teacher and not is_admin:
            q = q.filter(AIUsageLog.teacher_id == teacher.id)

        rows = q.group_by(AIUsageLog.ai_provider).order_by(
            func.sum(AIUsageLog.cost_usd).desc()
        ).all()

        providers_data = [{
            'provider': row[0],
            'cost_usd': round(float(row[1]), 6),
            'input_tokens': int(row[2]),
            'output_tokens': int(row[3]),
            'requests': int(row[4]),
        } for row in rows]

        return jsonify({'success': True, 'data': providers_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ميزة 11: WebSocket للتحديثات الفورية
# ============================================================

@socketio.on('subscribe')
def on_subscribe(data):
    """اشتراك في تحديثات تحضير معين"""
    plan_id = data.get('plan_id')
    if plan_id:
        join_room(f'plan_{plan_id}')
        logger.info(f"🔌 WebSocket: اشتراك في plan_{plan_id}")
        plan = LessonPlan.query.get(plan_id)
        if plan:
            display_status = 'generating' if plan.status == 'rate_limited' else plan.status
            result = {'plan_id': plan.id, 'status': display_status}
            if plan.status == 'completed':
                result['data'] = plan.to_dict()
            elif plan.status == 'failed':
                result['error'] = plan.error_message
            socketio.emit('plan_status', result, room=f'plan_{plan_id}')


@socketio.on('unsubscribe')
def on_unsubscribe(data):
    """إلغاء اشتراك"""
    plan_id = data.get('plan_id')
    if plan_id:
        leave_room(f'plan_{plan_id}')
        logger.info(f"🔌 WebSocket: إلغاء اشتراك plan_{plan_id}")


def emit_plan_status(plan_id, status, data=None, error=None):
    """إرسال تحديث حالة التحضير عبر WebSocket"""
    result = {'plan_id': plan_id, 'status': status}
    if data:
        result['data'] = data
    if error:
        result['error'] = error
    socketio.emit('plan_status', result, room=f'plan_{plan_id}')
