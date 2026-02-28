"""
Teacher Features Routes - API للأدمن للتحكم بمميزات المعلمين
"""
from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user
from functools import wraps
from datetime import datetime

from src.extensions import db
from src.models.teacher import Teacher
from src.models.teacher_feature import (
    TeacherFeatureOverride,
    FEATURE_DEFAULTS,
    FEATURE_LABELS,
)
from src.models.ai_analysis import AISetting

teacher_features_bp = Blueprint(
    'teacher_features',
    __name__,
    url_prefix='/api/admin/teacher-features'
)


# ── Decorator ──────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_global_features():
    """جلب كل المميزات العامة (من AISetting، مع fallback للـ defaults)"""
    features = {}
    for key, default in FEATURE_DEFAULTS.items():
        saved = AISetting.get_setting(key)
        features[key] = {
            'label': FEATURE_LABELS.get(key, key),
            'value': str(saved) if saved is not None else default,
            'default': default,
        }
    return features


def _get_teacher_features(teacher_id):
    """
    جلب مميزات معلم = القيم العامة + overrides الخاصة به.
    يُعيد dict: feature_key → {label, value, source ('override'|'global'), default}
    """
    global_features = _get_global_features()
    overrides = {
        o.feature_key: o.value
        for o in TeacherFeatureOverride.get_all_overrides_for_teacher(teacher_id)
    }

    result = {}
    for key, info in global_features.items():
        if key in overrides:
            result[key] = {**info, 'value': overrides[key], 'source': 'override'}
        else:
            result[key] = {**info, 'source': 'global'}
    return result


# ── Endpoints ───────────────────────────────────────────────────────────────

@teacher_features_bp.route('/global', methods=['GET'])
@admin_required
def get_global_features():
    """جلب كل المميزات العامة"""
    try:
        return jsonify({'success': True, 'features': _get_global_features()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_features_bp.route('/global', methods=['POST'])
@admin_required
def set_global_feature():
    """تعديل ميزة عامة لكل المعلمين"""
    try:
        data = request.get_json()
        feature_key = data.get('feature_key', '').strip()
        value = data.get('value')

        if not feature_key or feature_key not in FEATURE_DEFAULTS:
            return jsonify({'success': False, 'error': 'feature_key غير صحيح'}), 400
        if value is None:
            return jsonify({'success': False, 'error': 'القيمة مطلوبة'}), 400

        AISetting.set_setting(feature_key, str(value))
        return jsonify({
            'success': True,
            'message': f'تم تحديث {FEATURE_LABELS.get(feature_key, feature_key)} للجميع',
            'feature_key': feature_key,
            'value': str(value),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_features_bp.route('/all-teachers', methods=['GET'])
@admin_required
def get_all_teachers_features():
    """قائمة مختصرة بكل المعلمين وحالة مميزاتهم"""
    try:
        teachers = Teacher.query.order_by(Teacher.name).all()
        result = []
        for t in teachers:
            overrides = TeacherFeatureOverride.query.filter_by(teacher_id=t.id).all()
            result.append({
                'id': t.id,
                'name': t.name,
                'username': t.username,
                'is_active': t.is_active,
                'overrides_count': len(overrides),
                'overrides': [o.to_dict() for o in overrides],
            })
        return jsonify({'success': True, 'teachers': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_features_bp.route('/<int:teacher_id>', methods=['GET'])
@admin_required
def get_teacher_features(teacher_id):
    """مميزات معلم معين (global + overrides)"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        return jsonify({
            'success': True,
            'teacher': {'id': teacher.id, 'name': teacher.name, 'username': teacher.username},
            'features': _get_teacher_features(teacher_id),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_features_bp.route('/<int:teacher_id>', methods=['POST'])
@admin_required
def set_teacher_feature(teacher_id):
    """تعديل ميزة لمعلم واحد"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        data = request.get_json()
        feature_key = data.get('feature_key', '').strip()
        value = data.get('value')

        if not feature_key or feature_key not in FEATURE_DEFAULTS:
            return jsonify({'success': False, 'error': 'feature_key غير صحيح'}), 400
        if value is None:
            return jsonify({'success': False, 'error': 'القيمة مطلوبة'}), 400

        override = TeacherFeatureOverride.set_override(teacher_id, feature_key, str(value))
        return jsonify({
            'success': True,
            'message': f'تم تحديث {FEATURE_LABELS.get(feature_key, feature_key)} للمعلم {teacher.name}',
            'override': override.to_dict(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@teacher_features_bp.route('/<int:teacher_id>/<feature_key>', methods=['DELETE'])
@admin_required
def delete_teacher_feature_override(teacher_id, feature_key):
    """حذف override معين (يرجع للإعداد العام)"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        deleted = TeacherFeatureOverride.delete_override(teacher_id, feature_key)
        if deleted:
            return jsonify({
                'success': True,
                'message': f'تم إزالة التخصيص - {teacher.name} سيستخدم الإعداد العام',
            })
        return jsonify({'success': False, 'error': 'لا يوجد تخصيص لهذه الميزة'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── صفحة الويب ───────────────────────────────────────────────────────────────

@teacher_features_bp.route('/page', methods=['GET'])
@admin_required
def teacher_features_page():
    """صفحة الويب لإدارة مميزات المعلمين"""
    from flask_login import login_required
    teachers = Teacher.query.order_by(Teacher.name).all()
    global_features = _get_global_features()
    return render_template(
        'admin/teacher_features.html',
        teachers=teachers,
        global_features=global_features,
        feature_labels=FEATURE_LABELS,
        feature_defaults=FEATURE_DEFAULTS,
    )
