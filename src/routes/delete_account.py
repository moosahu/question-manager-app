"""
حذف الحساب - Delete Account
متوافق مع Apple App Store (Guideline 5.1.1)

📁 المسار: src/routes/delete_account.py
"""

from flask import Blueprint, request, jsonify
from src.extensions import db
from datetime import datetime, timedelta
import random
import string
import secrets

# استيراد خدمة الإيميل
from email_service import email_service


delete_account_bp = Blueprint('delete_account', __name__)


# ============================================================
# Model: جدول رموز حذف الحساب
# ============================================================
class DeleteAccountOTP(db.Model):
    __tablename__ = 'delete_account_otps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    delete_token = db.Column(db.String(64), nullable=True)
    attempts = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def create_otp(user_id, user_type):
        DeleteAccountOTP.query.filter_by(user_id=user_id, user_type=user_type).delete()
        code = ''.join(random.choices(string.digits, k=6))
        otp = DeleteAccountOTP(
            user_id=user_id,
            user_type=user_type,
            otp_code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.session.add(otp)
        db.session.commit()
        return otp

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def verify_code(self, code):
        if self.is_expired():
            return False, 'انتهت صلاحية رمز التحقق'
        if self.attempts >= 5:
            return False, 'تجاوزت الحد الأقصى للمحاولات'
        if self.otp_code != code:
            self.attempts += 1
            db.session.commit()
            remaining = 5 - self.attempts
            return False, f'رمز التحقق غير صحيح. متبقي {remaining} محاولات'
        self.is_verified = True
        self.delete_token = secrets.token_hex(32)
        db.session.commit()
        return True, self.delete_token


# ============================================================
# Route 1: طلب حذف الحساب (إرسال OTP بالإيميل)
# ============================================================
@delete_account_bp.route('/api/account/request-delete', methods=['POST'])
def request_delete():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        session_token = data.get('session_token')

        if not user_id or user_type not in ('student', 'teacher'):
            return jsonify({'error': 'بيانات غير مكتملة'}), 400

        # جلب بيانات المستخدم
        if user_type == 'student':
            from src.models.student import Student
            user = Student.query.get(user_id)
        else:
            from src.models.teacher import Teacher
            user = Teacher.query.get(user_id)

        if not user:
            return jsonify({'error': 'المستخدم غير موجود'}), 404

        # التحقق من الجلسة
        if hasattr(user, 'session_token') and user.session_token:
            if user.session_token != session_token:
                return jsonify({'error': 'جلسة غير صالحة، أعد تسجيل الدخول'}), 401

        if not user.email:
            return jsonify({'error': 'لا يوجد إيميل مرتبط بالحساب'}), 400

        # إنشاء OTP وإرسال الإيميل
        otp = DeleteAccountOTP.create_otp(user_id, user_type)

        success, message = email_service.send_delete_account_code(
            to_email=user.email,
            code=otp.otp_code,
            user_name=user.name
        )

        if success:
            at_idx = user.email.index('@')
            masked = user.email[:2] + '***' + user.email[at_idx:]
            return jsonify({
                'success': True,
                'message': f'تم إرسال رمز التحقق إلى {masked}',
                'email': masked,
            })
        else:
            return jsonify({'error': f'فشل إرسال الإيميل: {message}'}), 500

    except Exception as e:
        print(f"❌ Error in request_delete: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'حدث خطأ، حاول مرة أخرى'}), 500


# ============================================================
# Route 2: التحقق من رمز الحذف
# ============================================================
@delete_account_bp.route('/api/account/verify-delete-otp', methods=['POST'])
def verify_delete_otp():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        otp_code = data.get('otp')

        if not user_id or not user_type or not otp_code:
            return jsonify({'error': 'بيانات غير مكتملة'}), 400

        otp = DeleteAccountOTP.query.filter_by(
            user_id=user_id,
            user_type=user_type,
            is_verified=False
        ).order_by(DeleteAccountOTP.created_at.desc()).first()

        if not otp:
            return jsonify({'error': 'لم يتم طلب حذف الحساب، أعد المحاولة'}), 404

        is_valid, result = otp.verify_code(otp_code)

        if is_valid:
            return jsonify({
                'success': True,
                'message': 'تم التحقق بنجاح',
                'delete_token': result,
            })
        else:
            return jsonify({'error': result}), 400

    except Exception as e:
        print(f"❌ Error in verify_delete_otp: {e}")
        return jsonify({'error': 'حدث خطأ، حاول مرة أخرى'}), 500


# ============================================================
# Route 3: تأكيد الحذف نهائياً
# ============================================================
@delete_account_bp.route('/api/account/confirm-delete', methods=['POST'])
def confirm_delete():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        delete_token = data.get('delete_token')

        if not user_id or not user_type or not delete_token:
            return jsonify({'error': 'بيانات غير مكتملة'}), 400

        otp = DeleteAccountOTP.query.filter_by(
            user_id=user_id,
            user_type=user_type,
            is_verified=True,
            delete_token=delete_token
        ).first()

        if not otp:
            return jsonify({'error': 'رمز الحذف غير صالح، أعد المحاولة من البداية'}), 400

        if otp.is_expired():
            return jsonify({'error': 'انتهت صلاحية رمز الحذف، أعد المحاولة'}), 400

        # ✅ حذف جميع البيانات
        try:
            if user_type == 'student':
                db.session.execute(db.text("DELETE FROM student_answers WHERE student_id = :id"), {'id': user_id})
                db.session.execute(db.text("DELETE FROM student_results WHERE student_id = :id"), {'id': user_id})
                db.session.execute(db.text("DELETE FROM fcm_tokens WHERE user_id = :id AND user_type = 'student'"), {'id': user_id})
                db.session.execute(db.text("DELETE FROM students WHERE id = :id"), {'id': user_id})
            elif user_type == 'teacher':
                db.session.execute(db.text("DELETE FROM fcm_tokens WHERE user_id = :id AND user_type = 'teacher'"), {'id': user_id})
                db.session.execute(db.text("DELETE FROM teachers WHERE id = :id"), {'id': user_id})

            # حذف OTP records
            DeleteAccountOTP.query.filter_by(user_id=user_id, user_type=user_type).delete()
            db.session.commit()

            print(f"✅ تم حذف حساب {user_type} ID={user_id}")
            return jsonify({
                'success': True,
                'message': 'تم حذف حسابك وجميع بياناتك بنجاح'
            })

        except Exception as e:
            db.session.rollback()
            print(f"❌ خطأ في حذف البيانات: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'فشل حذف الحساب، حاول مرة أخرى'}), 500

    except Exception as e:
        print(f"❌ Error in confirm_delete: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'حدث خطأ، حاول مرة أخرى'}), 500
