"""
Endpoint لجلب بيانات الأدمن (البروفايل)
يُستخدم لجلب بيانات الأدمن بما فيها البريد الإلكتروني
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import csrf_exempt
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


@admin_profile_bp.route('/send-notification', methods=['POST'])
@login_required
@csrf_exempt
def send_notification():
    """
    إرسال إشعار للطلاب
    يتطلب تسجيل دخول كأدمن
    
    Request body:
        {
            'title': str,
            'message': str,
            'recipient_type': str ('all', 'student_id', 'level'),
            'recipient_id': int (اختياري),
            'level': str (اختياري)
        }
    """
    from flask import request
    from src.models.student import Student
    from src.services.notification_service import send_fcm_notification
    
    try:
        # التحقق من أن المستخدم الحالي هو أدمن
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية لإرسال الإشعارات'
            }), 403
        
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        if not data or 'title' not in data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'العنوان والرسالة مطلوبان'
            }), 400
        
        title = data.get('title')
        message = data.get('message')
        recipient_type = data.get('recipient_type', 'all')
        recipient_id = data.get('recipient_id')
        level = data.get('level')
        
        # جلب الطلاب المستهدفين
        students = []
        
        if recipient_type == 'all':
            # إرسال للجميع
            students = Student.query.all()
        elif recipient_type == 'student_id' and recipient_id:
            # إرسال لطالب معين
            student = Student.query.get(recipient_id)
            if student:
                students = [student]
        elif recipient_type == 'level' and level:
            # إرسال لمستوى معين
            students = Student.query.filter_by(level=level).all()
        
        # إرسال الإشعارات
        sent_count = 0
        failed_count = 0
        
        for student in students:
            try:
                # جلب FCM Token الطالب
                fcm_token = student.fcm_token if hasattr(student, 'fcm_token') else None
                
                if fcm_token:
                    # إرسال الإشعار
                    result = send_fcm_notification(
                        fcm_token=fcm_token,
                        title=title,
                        body=message
                    )
                    
                    if result:
                        sent_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                print(f"❌ خطأ في إرسال إشعار للطالب {student.id}: {e}")
                failed_count += 1
        
        return jsonify({
            'success': True,
            'message': f'تم إرسال {sent_count} إشعار بنجاح',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total': len(students)
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في إرسال الإشعارات: {e}")
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في إرسال الإشعارات'
        }), 500
