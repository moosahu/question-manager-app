"""
حذف الحساب - Delete Account Routes
متوافق مع متطلبات Apple App Store (Guideline 5.1.1)

الملفات المطلوبة:
1. هذا الملف → أضفه كـ Blueprint في app.py
2. Model: DeleteAccountOTP → موجود في نفس الملف
3. email_service.py → الدالة الجديدة send_delete_account_code

الاستخدام في app.py:
    from routes.delete_account import delete_account_bp
    app.register_blueprint(delete_account_bp)
"""

from flask import Blueprint, request, jsonify
from src.extensions import db
from datetime import datetime, timedelta
import random
import string
import secrets

# ✅ استيراد خدمة الإيميل الموجودة عندك
from email_service import email_service

# ✅ استيراد الموديلات حسب مشروعك
# عدّل المسارات حسب هيكل مشروعك
# from models.student import Student
# from models.teacher import Teacher


delete_account_bp = Blueprint('delete_account', __name__)


# ============================================================
# Model: جدول رموز حذف الحساب (نفس نمط EmailVerification)
# ============================================================
class DeleteAccountOTP(db.Model):
    """جدول رموز التحقق لحذف الحساب"""
    __tablename__ = 'delete_account_otps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'student' أو 'teacher'
    otp_code = db.Column(db.String(6), nullable=False)
    delete_token = db.Column(db.String(64), nullable=True)  # يُنشأ بعد التحقق من OTP
    attempts = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_code():
        """توليد رمز عشوائي من 6 أرقام"""
        return ''.join(random.choices(string.digits, k=6))

    @staticmethod
    def generate_delete_token():
        """توليد توكن حذف آمن"""
        return secrets.token_hex(32)

    @staticmethod
    def create_otp(user_id, user_type):
        """إنشاء OTP جديد (يحذف أي OTP سابق)"""
        # حذف الطلبات السابقة
        DeleteAccountOTP.query.filter_by(
            user_id=user_id,
            user_type=user_type
        ).delete()

        code = DeleteAccountOTP.generate_code()
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
        """التحقق من صحة الرمز"""
        if self.is_expired():
            return False, 'انتهت صلاحية رمز التحقق'

        if self.attempts >= 5:
            return False, 'تجاوزت الحد الأقصى للمحاولات'

        if self.otp_code != code:
            self.attempts += 1
            db.session.commit()
            remaining = 5 - self.attempts
            return False, f'رمز التحقق غير صحيح. متبقي {remaining} محاولات'

        # ✅ الرمز صحيح - إنشاء delete_token
        self.is_verified = True
        self.delete_token = DeleteAccountOTP.generate_delete_token()
        db.session.commit()
        return True, self.delete_token

    @staticmethod
    def cleanup_expired():
        """حذف الرموز المنتهية"""
        DeleteAccountOTP.query.filter(
            DeleteAccountOTP.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()


# ============================================================
# دالة مساعدة: جلب بيانات المستخدم
# ============================================================
def get_user_data(user_id, user_type):
    """
    جلب بيانات المستخدم من الداتابيس
    ⚠️ عدّل هذه الدالة حسب هيكل موديلاتك
    """
    if user_type == 'student':
        # عدّل حسب اسم الموديل عندك
        from models import Student  # أو from src.models.student import Student
        user = Student.query.get(user_id)
        if user:
            return {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': getattr(user, 'phone', None),
            }
    elif user_type == 'teacher':
        from models import Teacher  # أو from src.models.teacher import Teacher
        user = Teacher.query.get(user_id)
        if user:
            return {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': getattr(user, 'phone', None),
            }
    return None


def verify_session(user_id, user_type, session_token, device_id):
    """
    التحقق من صلاحية الجلسة
    ⚠️ عدّل حسب نظام الجلسات عندك
    """
    if user_type == 'student':
        from models import Student
        student = Student.query.get(user_id)
        if student and hasattr(student, 'session_token'):
            return student.session_token == session_token
        return True  # إذا ما عندك نظام session_token
    elif user_type == 'teacher':
        from models import Teacher
        teacher = Teacher.query.get(user_id)
        if teacher and hasattr(teacher, 'session_token'):
            return teacher.session_token == session_token
        return True
    return False


def _get_existing_tables():
    """جلب أسماء الجداول الموجودة"""
    result = db.session.execute(db.text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ))
    return {row[0] for row in result}


def delete_user_data(user_id, user_type):
    """
    حذف جميع بيانات المستخدم نهائياً
    يتحقق من وجود الجداول قبل الحذف
    """
    try:
        tables = _get_existing_tables()
        print(f"📋 الجداول الموجودة: {tables}")

        if user_type == 'student':
            # حذف بيانات الطالب (فقط من الجداول الموجودة)
            for table in ['student_answers', 'student_results', 'diagnostic_results', 'exam_results']:
                if table in tables:
                    db.session.execute(
                        db.text(f"DELETE FROM {table} WHERE student_id = :id"),
                        {'id': user_id}
                    )
                    print(f"  🗑️ حذف من {table}")

            if 'fcm_tokens' in tables:
                db.session.execute(
                    db.text("DELETE FROM fcm_tokens WHERE user_id = :id AND user_type = 'student'"),
                    {'id': user_id}
                )

            # حذف الطالب نفسه
            db.session.execute(
                db.text("DELETE FROM students WHERE id = :id"),
                {'id': user_id}
            )

        elif user_type == 'teacher':
            if 'fcm_tokens' in tables:
                db.session.execute(
                    db.text("DELETE FROM fcm_tokens WHERE user_id = :id AND user_type = 'teacher'"),
                    {'id': user_id}
                )

            # حذف المعلم نفسه
            db.session.execute(
                db.text("DELETE FROM teachers WHERE id = :id"),
                {'id': user_id}
            )

        # حذف OTP records
        if 'delete_account_otps' in tables:
            DeleteAccountOTP.query.filter_by(
                user_id=user_id,
                user_type=user_type
            ).delete()

        db.session.commit()
        print(f"✅ تم حذف جميع بيانات {user_type} ID={user_id}")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حذف البيانات: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# Route 1: طلب حذف الحساب (إرسال OTP)
# ============================================================
@delete_account_bp.route('/api/account/request-delete', methods=['POST'])
def request_delete():
    """يرسل رمز تحقق من 6 أرقام إلى إيميل المستخدم"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        session_token = data.get('session_token')
        device_id = data.get('device_id')

        # التحقق من البيانات
        if not user_id or not user_type:
            return jsonify({'error': 'بيانات غير مكتملة'}), 400

        if user_type not in ('student', 'teacher'):
            return jsonify({'error': 'نوع مستخدم غير صالح'}), 400

        # ✅ التحقق من الجلسة
        if not verify_session(user_id, user_type, session_token, device_id):
            return jsonify({'error': 'جلسة غير صالحة، أعد تسجيل الدخول'}), 401

        # جلب بيانات المستخدم
        user = get_user_data(user_id, user_type)
        if not user:
            return jsonify({'error': 'المستخدم غير موجود'}), 404

        if not user.get('email'):
            return jsonify({'error': 'لا يوجد إيميل مرتبط بالحساب'}), 400

        # ✅ إنشاء OTP
        otp = DeleteAccountOTP.create_otp(user_id, user_type)

        # ✅ إرسال الإيميل
        success, message = email_service.send_delete_account_code(
            to_email=user['email'],
            code=otp.otp_code,
            user_name=user.get('name', '')
        )

        if success:
            # إخفاء جزء من الإيميل
            email = user['email']
            at_idx = email.index('@')
            masked = email[:2] + '***' + email[at_idx:]

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
    """يتحقق من صحة OTP ويرجع delete_token"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        otp_code = data.get('otp')

        if not user_id or not user_type or not otp_code:
            return jsonify({'error': 'بيانات غير مكتملة'}), 400

        # البحث عن OTP
        otp = DeleteAccountOTP.query.filter_by(
            user_id=user_id,
            user_type=user_type,
            is_verified=False
        ).order_by(DeleteAccountOTP.created_at.desc()).first()

        if not otp:
            return jsonify({'error': 'لم يتم طلب حذف الحساب، أعد المحاولة'}), 404

        # التحقق من الرمز
        is_valid, result = otp.verify_code(otp_code)

        if is_valid:
            # result = delete_token
            return jsonify({
                'success': True,
                'message': 'تم التحقق بنجاح',
                'delete_token': result,
            })
        else:
            # result = رسالة الخطأ
            return jsonify({'error': result}), 400

    except Exception as e:
        print(f"❌ Error in verify_delete_otp: {e}")
        return jsonify({'error': 'حدث خطأ، حاول مرة أخرى'}), 500


# ============================================================
# Route 3: تأكيد حذف الحساب نهائياً
# ============================================================
@delete_account_bp.route('/api/account/confirm-delete', methods=['POST'])
def confirm_delete():
    """يحذف الحساب نهائياً بعد التحقق من delete_token"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        delete_token = data.get('delete_token')

        if not user_id or not user_type or not delete_token:
            return jsonify({'error': 'بيانات غير مكتملة'}), 400

        # البحث عن OTP المُتحقق منه
        otp = DeleteAccountOTP.query.filter_by(
            user_id=user_id,
            user_type=user_type,
            is_verified=True,
            delete_token=delete_token
        ).first()

        if not otp:
            return jsonify({'error': 'رمز الحذف غير صالح، أعد المحاولة من البداية'}), 400

        # التحقق من انتهاء الصلاحية
        if otp.is_expired():
            return jsonify({'error': 'انتهت صلاحية رمز الحذف، أعد المحاولة'}), 400

        # ✅ حذف جميع بيانات المستخدم
        deleted = delete_user_data(user_id, user_type)

        if deleted:
            return jsonify({
                'success': True,
                'message': 'تم حذف حسابك وجميع بياناتك بنجاح'
            })
        else:
            return jsonify({'error': 'فشل حذف الحساب، حاول مرة أخرى'}), 500

    except Exception as e:
        print(f"❌ Error in confirm_delete: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'حدث خطأ، حاول مرة أخرى'}), 500


# ============================================================
# إنشاء الجدول (شغّلها مرة واحدة)
# ============================================================
"""
أضف هذا في app.py بعد db.create_all() أو شغّله يدوياً:

    with app.app_context():
        db.create_all()

أو عن طريق Flask shell:
    flask shell
    >>> from routes.delete_account import DeleteAccountOTP
    >>> db.create_all()
"""
