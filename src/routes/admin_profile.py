"""
Endpoint لجلب بيانات الأدمن (البروفايل)
يُستخدم لجلب بيانات الأدمن بما فيها البريد الإلكتروني
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from src.models.user import User

admin_profile_bp = Blueprint('admin_profile', __name__, url_prefix='/api/admin')


@admin_profile_bp.route('/profile', methods=['GET'])
@login_required
def get_admin_profile():
    """
    جلب بيانات الأدمن الحالي
    يتطلب تسجيل دخول
    
    Returns:
        {
            'success': True,
            'admin': {
                'id': int,
                'username': str,
                'email': str,
                'is_admin': bool
            }
        }
    """
    try:
        # التحقق من أن المستخدم الحالي هو أدمن
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية للوصول إلى هذا الـ endpoint'
            }), 403
        
        # جلب بيانات الأدمن
        admin_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'is_admin': current_user.is_admin
        }
        
        return jsonify({
            'success': True,
            'admin': admin_data
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب بيانات الأدمن: {e}")
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في جلب البيانات'
        }), 500


@admin_profile_bp.route('/profile/email', methods=['GET'])
@login_required
def get_admin_email():
    """
    جلب البريد الإلكتروني للأدمن فقط
    
    Returns:
        {
            'success': True,
            'email': str
        }
    """
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية'
            }), 403
        
        return jsonify({
            'success': True,
            'email': current_user.email
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب البريد: {e}")
        return jsonify({
            'success': False,
            'error': 'حدث خطأ'
        }), 500
