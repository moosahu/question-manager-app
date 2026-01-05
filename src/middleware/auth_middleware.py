"""Middleware للتحقق من JWT Token
يستخدم لحماية API endpoints للطالب والمعلم
"""
import jwt
from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime, timedelta


# ==================== التحقق من توكن الطالب ====================
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


# ==================== ✅ جديد: التحقق من توكن المعلم ====================
def verify_teacher_token(f):
    """
    Decorator للتحقق من JWT Token للمعلم
    يستخرج الرمز من Authorization header
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # البحث عن الرمز في Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
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
            
            # التأكد أن التوكن للمعلم
            if data.get('user_type') != 'teacher':
                return jsonify({
                    'success': False,
                    'error': 'هذا الإجراء مخصص للمعلمين فقط'
                }), 403
            
            # حفظ بيانات المعلم في request context
            request.teacher_id = data.get('teacher_id')
            request.username = data.get('username')
            request.user_type = 'teacher'
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


# ==================== ✅ جديد: التحقق من توكن أي مستخدم (طالب أو معلم) ====================
def verify_user_token(f):
    """
    Decorator للتحقق من JWT Token لأي مستخدم (طالب أو معلم)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
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
            data = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=[current_app.config['JWT_ALGORITHM']]
            )
            
            user_type = data.get('user_type', 'student')
            
            # حفظ البيانات حسب نوع المستخدم
            if user_type == 'teacher':
                request.teacher_id = data.get('teacher_id')
                request.user_id = data.get('teacher_id')
            else:
                request.student_id = data.get('student_id')
                request.user_id = data.get('student_id')
            
            request.username = data.get('username')
            request.user_type = user_type
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


# ==================== إنشاء توكن الطالب ====================
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
    payload = {
        'student_id': student_id,
        'username': username,
        'user_type': 'student',  # ✅ تحديد نوع المستخدم
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=expires_in_days)
    }
    
    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM']
    )
    
    return token


# ==================== ✅ جديد: إنشاء توكن المعلم ====================
def create_teacher_token(teacher_id, username, expires_in_days=30):
    """
    إنشاء JWT Token للمعلم
    
    Args:
        teacher_id: معرف المعلم
        username: اسم المستخدم
        expires_in_days: عدد أيام صلاحية الرمز
    
    Returns:
        str: الرمز المشفر
    """
    payload = {
        'teacher_id': teacher_id,
        'username': username,
        'user_type': 'teacher',  # ✅ تحديد نوع المستخدم كمعلم
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=expires_in_days)
    }
    
    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM']
    )
    
    return token


# ==================== استخراج بيانات المستخدم من التوكن ====================
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


# ==================== ✅ جديد: استخراج بيانات المعلم من التوكن ====================
def get_teacher_from_token(token):
    """
    استخراج بيانات المعلم من الرمز
    
    Args:
        token: الرمز المشفر
    
    Returns:
        dict: بيانات المعلم أو None إذا كان الرمز غير صحيح
    """
    try:
        data = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']]
        )
        if data.get('user_type') == 'teacher':
            return data
        return None
    except:
        return None


# ==================== ✅ جديد: استخراج بيانات أي مستخدم من التوكن ====================
def get_user_from_token(token):
    """
    استخراج بيانات المستخدم من الرمز (طالب أو معلم)
    
    Args:
        token: الرمز المشفر
    
    Returns:
        dict: بيانات المستخدم مع نوعه أو None
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
