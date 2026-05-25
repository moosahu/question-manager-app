"""
إعادة تعيين كلمة المرور - Password Reset Routes
APIs لإعادة تعيين كلمة المرور للطلاب
"""
import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash
from src.extensions import db
from src.models.student import Student
from src.models.password_reset import PasswordReset
from src.services.email_service import email_service
from src.utils.field_encryption import make_email_hash


def _make_reset_token(reset_id: int) -> str:
    """إنشاء token آمن موقَّع بـ HMAC لا يمكن تخمينه أو تتابعه"""
    secret = current_app.config['SECRET_KEY'].encode()
    sig = hmac.new(secret, str(reset_id).encode(), hashlib.sha256).hexdigest()
    return f"{reset_id}.{sig}"


def _parse_reset_token(token: str):
    """التحقق من صحة token وإرجاع reset_id، أو None إن كان مزوراً"""
    try:
        reset_id_str, sig = token.split('.', 1)
        reset_id = int(reset_id_str)
        expected = _make_reset_token(reset_id)
        if hmac.compare_digest(token, expected):
            return reset_id
    except Exception:
        pass
    return None

password_reset_bp = Blueprint('password_reset', __name__, url_prefix='/api/password-reset')


# ==================== الخطوة 1: طلب إعادة التعيين ====================
@password_reset_bp.route('/request', methods=['POST'])
def request_password_reset():
    """طلب إعادة تعيين كلمة المرور - إرسال رمز التحقق"""
    try:
        data = request.get_json() or request.form
        
        # طلب البريد الإلكتروني فقط
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'البريد الإلكتروني مطلوب'
            }), 400
        
        # البحث عن الطالب بالبريد الإلكتروني
        student = Student.query.filter_by(email_hash=make_email_hash(email)).first()

        if not student:
            # نُرجع نفس الرسالة لمنع اكتشاف الحسابات المسجلة
            return jsonify({
                'success': True,
                'message': 'إذا كان البريد مسجلاً، ستصلك رسالة تحقق قريباً',
                'expires_in': 600
            })
        
        # التحقق من وجود إيميل للطالب
        if not student.email:
            return jsonify({
                'success': False,
                'error': 'لا يوجد بريد إلكتروني مسجل لهذا الحساب. تواصل مع الإدارة'
            }), 400
        
        # التحقق من أن الحساب مفعل
        if not student.is_active:
            return jsonify({
                'success': False,
                'error': 'هذا الحساب غير مفعل. تواصل مع الإدارة'
            }), 403
        
        # إنشاء طلب إعادة تعيين
        reset_request = PasswordReset.create_reset_request(
            student_id=student.id,
            email=student.email
        )
        
        # إرسال رمز التحقق بالإيميل
        success, message = email_service.send_password_reset_code(
            to_email=student.email,
            code=reset_request.code,
            student_name=student.name
        )
        
        if not success:
            # حذف طلب التحقق إذا فشل الإرسال
            db.session.delete(reset_request)
            db.session.commit()
            return jsonify({
                'success': False,
                'error': f'فشل إرسال رمز التحقق: {message}'
            }), 500
        
        # إخفاء جزء من الإيميل لأسباب أمنية
        masked_email = student.email[:2] + '***@' + student.email.split('@')[1]
        
        return jsonify({
            'success': True,
            'message': 'تم إرسال رمز التحقق إلى بريدك الإلكتروني',
            'email': masked_email,
            'expires_in': 600  # 10 دقائق بالثواني
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في طلب إعادة التعيين: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في معالجة الطلب'
        }), 500


# ==================== الخطوة 2: التحقق من الرمز ====================
@password_reset_bp.route('/verify', methods=['POST'])
def verify_reset_code():
    """التحقق من رمز إعادة التعيين"""
    try:
        data = request.get_json() or request.form
        
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        
        if not email or not code:
            return jsonify({
                'success': False,
                'error': 'البريد الإلكتروني ورمز التحقق مطلوبان'
            }), 400
        
        # البحث عن الطالب
        student = Student.query.filter_by(email_hash=make_email_hash(email)).first()
        
        if not student:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على الحساب'
            }), 404
        
        # البحث عن طلب إعادة التعيين
        reset_request = PasswordReset.query.filter_by(
            student_id=student.id,
            is_used=False
        ).order_by(PasswordReset.created_at.desc()).first()
        
        if not reset_request:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على طلب إعادة تعيين. يرجى طلب رمز جديد'
            }), 404
        
        # التحقق من الرمز
        success, message = reset_request.verify_code(code)
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        return jsonify({
            'success': True,
            'message': 'الرمز صحيح. يمكنك الآن إدخال كلمة المرور الجديدة',
            'reset_token': _make_reset_token(reset_request.id)  # HMAC-signed token
        })
        
    except Exception as e:
        print(f"❌ خطأ في التحقق من الرمز: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في التحقق'
        }), 500


# ==================== الخطوة 3: تعيين كلمة المرور الجديدة ====================
@password_reset_bp.route('/reset', methods=['POST'])
def reset_password():
    """تعيين كلمة المرور الجديدة"""
    try:
        data = request.get_json() or request.form
        
        reset_token = data.get('reset_token', '').strip()
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        
        if not reset_token or not new_password or not confirm_password:
            return jsonify({
                'success': False,
                'error': 'جميع الحقول مطلوبة'
            }), 400
        
        # التحقق من تطابق كلمة المرور
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'error': 'كلمة المرور غير متطابقة'
            }), 400
        
        # التحقق من طول كلمة المرور
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'error': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'
            }), 400

        # التحقق من صحة reset_token (HMAC-signed)
        reset_id = _parse_reset_token(reset_token)
        if reset_id is None:
            return jsonify({
                'success': False,
                'error': 'رمز التحقق غير صالح'
            }), 400

        reset_request = PasswordReset.query.get(reset_id)
        
        if not reset_request:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على طلب إعادة التعيين'
            }), 404
        
        # التحقق من أن الرمز لم يستخدم
        if reset_request.is_used:
            return jsonify({
                'success': False,
                'error': 'تم استخدام هذا الرمز مسبقاً'
            }), 400
        
        # التحقق من أن الرمز لم تنتهي صلاحيته
        if reset_request.is_expired():
            return jsonify({
                'success': False,
                'error': 'انتهت صلاحية الرمز. يرجى طلب رمز جديد'
            }), 400
        
        # الحصول على الطالب
        student = Student.query.get(reset_request.student_id)
        
        if not student:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على الحساب'
            }), 404
        
        # تحديث كلمة المرور
        student.password_hash = generate_password_hash(new_password)
        
        # وضع علامة على الرمز كمستخدم
        reset_request.mark_as_used()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم تغيير كلمة المرور بنجاح. يمكنك الآن تسجيل الدخول'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إعادة التعيين: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في تغيير كلمة المرور'
        }), 500


# ==================== إعادة إرسال الرمز ====================
@password_reset_bp.route('/resend', methods=['POST'])
def resend_reset_code():
    """إعادة إرسال رمز إعادة التعيين"""
    try:
        data = request.get_json() or request.form
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'البريد الإلكتروني مطلوب'
            }), 400
        
        # البحث عن الطالب
        student = Student.query.filter_by(email_hash=make_email_hash(email)).first()
        
        if not student:
            # البريد غير موجود
            return jsonify({
                'success': False,
                'error': 'البريد الإلكتروني غير مسجل'
            }), 404
        
        # البحث عن طلب التحقق الأخير
        reset_request = PasswordReset.query.filter_by(
            student_id=student.id,
            is_used=False
        ).order_by(PasswordReset.created_at.desc()).first()
        
        if not reset_request:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على طلب سابق. يرجى البدء من جديد'
            }), 404
        
        # إنشاء رمز جديد
        from datetime import datetime, timedelta
        reset_request.code = PasswordReset.generate_code()
        reset_request.expires_at = datetime.utcnow() + timedelta(minutes=10)
        reset_request.attempts = 0
        db.session.commit()
        
        # إرسال الرمز الجديد
        success, message = email_service.send_password_reset_code(
            to_email=student.email,
            code=reset_request.code,
            student_name=student.name
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'فشل إرسال رمز التحقق: {message}'
            }), 500
        
        masked_email = student.email[:2] + '***@' + student.email.split('@')[1]
        
        return jsonify({
            'success': True,
            'message': 'تم إرسال رمز جديد إلى بريدك الإلكتروني',
            'email': masked_email,
            'expires_in': 600
        })
        
    except Exception as e:
        print(f"❌ خطأ في إعادة الإرسال: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في إعادة الإرسال'
        }), 500
