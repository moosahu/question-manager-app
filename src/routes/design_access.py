# src/routes/design_access.py
"""
Design Access Routes — إدارة صلاحيات اختبار التصاميم
الأدمن يفعّل زر التصاميم لطلاب محددين
"""

from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from functools import wraps

from src.models.student import Student
from src.extensions import db
from src.middleware.auth_middleware import verify_student_token

design_access_bp = Blueprint('design_access', __name__, url_prefix='/api/design-access')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'غير مسجل الدخول'}), 401
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# Admin: قائمة الطلاب مع حالة اختبار التصاميم
# GET /api/design-access/admin/testers
# ─────────────────────────────────────────────────────────────────────────────
@design_access_bp.route('/admin/testers', methods=['GET'])
@login_required
@admin_required
def get_testers():
    students = Student.query.order_by(Student.name).all()
    return jsonify({
        'success': True,
        'students': [
            {
                'id': s.id,
                'name': s.name,
                'username': s.username,
                'grade': s.grade,
                'design_tester': s.design_tester or False,
                'allowed_designs': s.allowed_designs,  # "1,3,5" أو null=الكل
            }
            for s in students
        ]
    })


# ─────────────────────────────────────────────────────────────────────────────
# Admin: تعديل إعداد طالب محدد
# PUT /api/design-access/admin/testers/<student_id>
# Body: { "design_tester": true, "allowed_designs": "1,3,5" }
# ─────────────────────────────────────────────────────────────────────────────
@design_access_bp.route('/admin/testers/<int:student_id>', methods=['PUT'])
@login_required
@admin_required
def update_tester(student_id):
    student = Student.query.get_or_404(student_id)
    data = request.get_json() or {}

    if 'design_tester' in data:
        student.design_tester = bool(data['design_tester'])

    if 'allowed_designs' in data:
        val = data['allowed_designs']
        # null أو string فارغ = الكل مسموح
        student.allowed_designs = val if val else None

    db.session.commit()
    return jsonify({
        'success': True,
        'student': {
            'id': student.id,
            'name': student.name,
            'design_tester': student.design_tester or False,
            'allowed_designs': student.allowed_designs,
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# Student: جلب صلاحية التصاميم الخاصة بالطالب الحالي
# GET /api/design-access/my-access
# يقبل JWT Token (Authorization: Bearer) من التطبيق
# ─────────────────────────────────────────────────────────────────────────────
@design_access_bp.route('/my-access', methods=['GET'])
@verify_student_token
def get_my_access():
    student = Student.query.get(request.student_id)
    if not student:
        return jsonify({'success': False, 'error': 'الطالب غير موجود'}), 404

    enabled = student.design_tester or False
    allowed_raw = student.allowed_designs

    # تحويل "1,3,5" لقائمة أرقام
    allowed_list = None
    if allowed_raw:
        try:
            allowed_list = [int(x.strip()) for x in allowed_raw.split(',') if x.strip()]
        except ValueError:
            allowed_list = None

    return jsonify({
        'success': True,
        'design_tester': enabled,
        'allowed_designs': allowed_list,  # null = الكل، أو قائمة أرقام
    })
