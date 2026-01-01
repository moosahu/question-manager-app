"""Middleware للتحقق من JWT Token
يستخدم لحماية API endpoints للطالب
"""
import jwt
from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime'


def verify_student_token(f):
    """
    Decorator للتحقق من JWT Token للطالب
    يستخرج الرمز من Authorization header
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # البحث عن الرمز في Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                # الصيغة: "Bearer <token>"
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({
                    'success': False,
                    'error': 'صيغة Authorization header غير صحيحة'
                }), 401
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'رمز المصادقة مطلوب'
            }), 401
        
        try:
            # فك تشفير والتحقق من الرمز
            data = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=[current_app.config['JWT_ALGORITHM']]
            )
            
            # حفظ بيانات الطالب في request context
            request.student_id = data.get('student_id')
            request.username = data.get('username')
            request.token_data = data
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'انتهت صلاحية رمز المصادقة'
            }), 401
            
        except jwt.InvalidTokenError as e:
            return jsonify({
                'success': False,
                'error': f'رمز المصادقة غير صحيح: {str(e)}'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def create_student_token(student_id, username, expires_in_days=30):
    """
    إنشاء JWT Token للطالب
    
    Args:
        student_id: معرف الطالب
        username: اسم المستخدم
        expires_in_days: عدد أيام صلاحية الرمز
    
    Returns:
        str: الرمز المشفر
    """
    from datetime import timedelta
    
    payload = {
        'student_id': student_id,
        'username': username,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=expires_in_days)
    }
    
    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM']
    )
    
    return token


def get_student_from_token(token):
    """
    استخراج بيانات الطالب من الرمز
    
    Args:
        token: الرمز المشفر
    
    Returns:
        dict: بيانات الطالب أو None إذا كان الرمز غير صحيح
    """
    try:
        data = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']]
        )
        return data
    except:
        return None
