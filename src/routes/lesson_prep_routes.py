"""
Lesson Prep Routes - واجهات API لتحضير الدروس بالذكاء الاصطناعي
"""
from flask import Blueprint, request, jsonify, send_file
from flask_login import current_user
from functools import wraps
from datetime import datetime
import json
import io
import logging
import requests

from src.extensions import db
from src.models.textbook import LessonPlan, LessonPages
from src.models.curriculum import Lesson, Unit, Course
from src.models.teacher import Teacher
from src.models.ai_analysis import AISetting

logger = logging.getLogger(__name__)

lesson_prep_bp = Blueprint('lesson_prep', __name__, url_prefix='/api/lesson-prep')


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


@lesson_prep_bp.route('/generate', methods=['POST'])
@auth_required
def generate_lesson_plan(teacher=None, user_id=None, is_admin=False):
    """بدء توليد تحضير درس (async)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'لا توجد بيانات'}), 400

        lesson_id = data.get('lesson_id')
        if not lesson_id:
            return jsonify({'success': False, 'error': 'معرف الدرس مطلوب'}), 400

        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({'success': False, 'error': 'الدرس غير موجود'}), 404

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
            status='pending',
        )
        db.session.add(plan)
        db.session.commit()

        # حفظ طلب التوليد في ai_settings للـ scheduler
        AISetting.set_setting('lesson_prep_job_status', 'running', 'string')
        AISetting.set_setting('lesson_prep_job_data', json.dumps({
            'plan_id': plan.id,
            'type': 'single_lesson',
        }), 'json')

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
        data = request.get_json()
        lesson_id = data.get('lesson_id')  # أي درس من الوحدة

        if not lesson_id:
            return jsonify({'success': False, 'error': 'معرف الدرس مطلوب'}), 400

        plan = LessonPlan(
            lesson_id=lesson_id,
            teacher_id=teacher.id if teacher else None,
            plan_type='unit_distribution',
            status='pending',
        )
        db.session.add(plan)
        db.session.commit()

        AISetting.set_setting('lesson_prep_job_status', 'running', 'string')
        AISetting.set_setting('lesson_prep_job_data', json.dumps({
            'plan_id': plan.id,
            'type': 'unit_distribution',
        }), 'json')

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
def get_plan_status(plan_id):
    """حالة التوليد (polling)"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        result = {
            'plan_id': plan.id,
            'status': plan.status,
        }

        if plan.status == 'completed':
            result['data'] = plan.to_dict()
        elif plan.status == 'failed':
            result['error'] = plan.error_message

        return jsonify({'success': True, 'data': result})

    except Exception as e:
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
def get_plan(plan_id):
    """عرض التحضير كـ JSON"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        return jsonify({'success': True, 'data': plan.to_dict()})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@lesson_prep_bp.route('/<int:plan_id>/pdf', methods=['GET'])
def download_plan_pdf(plan_id):
    """تحميل ملف PDF"""
    try:
        plan = LessonPlan.query.get(plan_id)
        if not plan:
            return jsonify({'success': False, 'error': 'التحضير غير موجود'}), 404

        if not plan.pdf_file_url:
            # توليد PDF on-the-fly
            from src.services.lesson_prep_service import lesson_prep_service
            from src.models.curriculum import Lesson, Unit, Course

            lesson = Lesson.query.get(plan.lesson_id)
            unit = Unit.query.get(lesson.unit_id) if lesson else None
            course = Course.query.get(unit.course_id) if unit else None

            pdf_bytes = lesson_prep_service._generate_pdf(
                plan.plan_data or {},
                lesson.name if lesson else 'تحضير',
                unit.name if unit else '',
                course.name if course else '',
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

        db.session.delete(plan)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم حذف التحضير'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
