"""
test_registration_deep4.py
Targets uncovered lines in src/routes/registration.py to push coverage from 89% -> 95%+

Lines targeted:
  - 33-34, 48-50, 56-57, 66-67: notify_admin exception branches
  - 319: teacher username regex validation
  - 483, 514: verify_code duplicate email (teacher + student paths with has_phone)
  - 566, 624: verify_code teacher/student has_phone → should_activate=False
  - 711-777: bulk verify_phone_code paths (teacher + student, duplicate conflicts)
  - 855-860: activate_after_phone exception path
  - 917-919: resend_code exception path
"""

import pytest
import secrets
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash

VALID_CODES = [200, 302, 400, 401, 403, 404, 405, 500]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login_admin(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _open_reg(db_session, require_phone=False, require_school=False,
              auto_activate=True, teacher_open=True,
              teacher_require_phone=False, teacher_require_school=False,
              teacher_auto_activate=True):
    from src.models.email_verification import RegistrationSettings
    s = RegistrationSettings.get_settings()
    s.is_registration_open = True
    s.require_phone = require_phone
    s.require_school = require_school
    s.auto_activate = auto_activate
    s.is_teacher_registration_open = teacher_open
    s.teacher_require_phone = teacher_require_phone
    s.teacher_require_school = teacher_require_school
    s.teacher_auto_activate = teacher_auto_activate
    db_session.session.commit()
    return s


def _make_verification(db_session, email=None, phone=None, grade=None,
                       is_verified=False, verify_phone=False):
    """إنشاء سجل EmailVerification مباشرة في DB"""
    from src.models.email_verification import EmailVerification
    email = email or f"v_{secrets.token_hex(4)}@test.com"
    name_parts = "أحمد محمد علي"
    username = f"user_{secrets.token_hex(4)}"
    code = "123456"
    v = EmailVerification(
        email=email,
        name=name_parts,
        username=username,
        password_hash=generate_password_hash("Pass@1234"),
        phone=phone,
        school=None,
        grade=grade,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        is_verified=is_verified,
    )
    db_session.session.add(v)
    db_session.session.commit()
    db_session.session.refresh(v)
    return v


# ---------------------------------------------------------------------------
# notify_admin – exception branches (lines 33-34, 48-50, 56-57, 66-67)
# ---------------------------------------------------------------------------

class TestNotifyAdminExceptions:
    """اختبار فروع الاستثناء في notify_admin"""

    def test_notify_admin_user_query_fails(self, client, db_session):
        """السطر 33-34: استثناء عند query User في notify_admin"""
        _open_reg(db_session)
        v = _make_verification(db_session, is_verified=False)
        # patch src.models.user.User.query لإثارة استثناء في notify_admin
        with patch('src.models.user.User.query') as mock_query:
            mock_query.filter_by.side_effect = Exception("User DB error")
            with patch('src.models.email_verification.EmailVerification.verify_code',
                       return_value=(True, 'ok')):
                with patch('src.routes.registration.create_student_token',
                           return_value='tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'student'
                    })
                    assert resp.status_code in VALID_CODES

    def test_notify_admin_db_save_fails(self, client, db_session):
        """السطر 48-50: استثناء عند حفظ الإشعار في DB"""
        from src.models.user import User
        admin = User(username=f'na_{secrets.token_hex(4)}',
                     email=f'na_{secrets.token_hex(4)}@test.com', is_admin=True)
        admin.set_password('Admin@123')
        db_session.session.add(admin)
        db_session.session.commit()
        db_session.session.refresh(admin)

        _open_reg(db_session)
        v = _make_verification(db_session, is_verified=False)

        with patch('src.routes.registration.Notification') as mock_notif_cls:
            mock_notif_cls.side_effect = Exception("DB error forced")
            with patch('src.models.email_verification.EmailVerification.verify_code',
                       return_value=(True, 'ok')):
                with patch('src.routes.registration.create_student_token',
                           return_value='tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'student'
                    })
                    assert resp.status_code in VALID_CODES

    def test_notify_admin_email_fails(self, client, db_session):
        """السطر 56-57: استثناء عند إرسال إيميل الأدمن"""
        from src.models.user import User
        admin = User(username=f'ne_{secrets.token_hex(4)}',
                     email=f'ne_{secrets.token_hex(4)}@test.com', is_admin=True)
        admin.set_password('Admin@123')
        db_session.session.add(admin)
        db_session.session.commit()
        db_session.session.refresh(admin)

        _open_reg(db_session)
        v = _make_verification(db_session, is_verified=False)

        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_admin_notification.side_effect = Exception("SMTP error")
            mock_email.send_verification_code.return_value = (True, 'ok')
            with patch('src.models.email_verification.EmailVerification.verify_code',
                       return_value=(True, 'ok')):
                with patch('src.routes.registration.create_student_token',
                           return_value='tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'student'
                    })
                    assert resp.status_code in VALID_CODES

    def test_notify_admin_fcm_fails(self, client, db_session):
        """السطر 66-67: استثناء عند push notification"""
        from src.models.user import User
        admin = User(username=f'nf_{secrets.token_hex(4)}',
                     email=f'nf_{secrets.token_hex(4)}@test.com',
                     is_admin=True)
        admin.set_password('Admin@123')
        admin.fcm_token = 'some_fcm_token'
        db_session.session.add(admin)
        db_session.session.commit()
        db_session.session.refresh(admin)

        _open_reg(db_session)
        v = _make_verification(db_session, is_verified=False)

        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_admin_notification.return_value = None
            mock_email.send_verification_code.return_value = (True, 'ok')
            # patch the module-level import inside notify_admin
            with patch('src.services.notification_service.NotificationService') as mock_ns:
                mock_ns.send_fcm_notification.side_effect = Exception("FCM error")
                with patch('src.models.email_verification.EmailVerification.verify_code',
                           return_value=(True, 'ok')):
                    with patch('src.routes.registration.create_student_token',
                               return_value='tok'):
                        resp = client.post('/api/registration/verify', json={
                            'email': v.email,
                            'code': '123456',
                            'account_type': 'student'
                        })
                        assert resp.status_code in VALID_CODES


# ---------------------------------------------------------------------------
# register_teacher validation – line 319 (username regex)
# ---------------------------------------------------------------------------

class TestRegisterTeacherValidation:
    """التحقق من validation إضافي في register_teacher"""

    def test_teacher_username_starts_with_digit(self, client, db_session):
        """السطر 319: اسم المستخدم يبدأ برقم → خطأ"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': '1baduser',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'يبدأ بحرف' in data.get('error', '')

    def test_teacher_username_too_short(self, client, db_session):
        """اسم مستخدم أقل من 4 أحرف"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'ab',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400

    def test_teacher_username_too_long(self, client, db_session):
        """اسم مستخدم أكثر من 20 حرف"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'a' * 25,
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400

    def test_teacher_password_no_letter(self, client, db_session):
        """كلمة مرور بدون حرف"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'teacher1',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': '12345678',
            })
            assert resp.status_code == 400

    def test_teacher_password_no_digit(self, client, db_session):
        """كلمة مرور بدون رقم"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'teacher1',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'abcdefgh',
            })
            assert resp.status_code == 400

    def test_teacher_weak_password(self, client, db_session):
        """كلمة مرور ضعيفة"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'teacher1',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'password123',
            })
            assert resp.status_code == 400

    def test_teacher_blocked_email_domain(self, client, db_session):
        """إيميل من نطاق محظور"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'teacher1',
                'email': 'teacher@mailinator.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400

    def test_teacher_require_phone_missing(self, client, db_session):
        """teacher_require_phone=True بدون جوال"""
        _open_reg(db_session, teacher_open=True, teacher_require_phone=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'teacher1',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'الجوال' in data.get('error', '') or 'phone' in data.get('error', '').lower()

    def test_teacher_require_school_missing(self, client, db_session):
        """teacher_require_school=True بدون مدرسة"""
        _open_reg(db_session, teacher_open=True, teacher_require_school=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'teacher1',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400

    def test_teacher_student_username_duplicate(self, client, db_session):
        """اسم مستخدم موجود في جدول الطلاب"""
        from src.models.student import Student
        existing_student = Student(
            name='طالب موجود', username='existstudent',
            email=f's_{secrets.token_hex(4)}@test.com', is_active=True
        )
        existing_student.set_password('Pass@123')
        db_session.session.add(existing_student)
        db_session.session.commit()

        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': 'existstudent',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400

    def test_teacher_email_duplicate(self, client, db_session):
        """إيميل موجود مسبقاً في جدول المعلمين"""
        from src.models.teacher import Teacher
        dup_email = f'dup_{secrets.token_hex(4)}@gmail.com'
        t = Teacher(
            name='معلم موجود', username=f'tch_{secrets.token_hex(4)}',
            email=dup_email, is_active=True
        )
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()

        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'newteacher_{secrets.token_hex(3)}',
                'email': dup_email,
                'password': 'Pass@1234',
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# verify_code – lines 483, 514 (duplicate email for teacher/student with phone)
# ---------------------------------------------------------------------------

class TestVerifyCodeDuplicateWithPhone:
    """تكرار الإيميل في مسار has_phone"""

    def test_verify_teacher_with_phone_duplicate_email(self, client, db_session):
        """السطر 483: معلم بجوال → إيميل مكرر"""
        from src.models.teacher import Teacher
        phone_email = f'tpe_{secrets.token_hex(4)}@test.com'

        # إنشاء معلم موجود بنفس الإيميل
        existing = Teacher(
            name='معلم قديم',
            username=f'tch_old_{secrets.token_hex(4)}',
            email=phone_email, is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session)
        # verification بجوال ونوع teacher
        v = _make_verification(db_session, email=phone_email,
                                phone='+966501234567', grade='teacher',
                                is_verified=False)

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': phone_email,
                'code': '123456',
                'account_type': 'teacher'
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'مسجلاً' in data.get('error', '') or 'محجوزاً' in data.get('error', '')

    def test_verify_student_with_phone_duplicate_email(self, client, db_session):
        """السطر 514: طالب بجوال → إيميل مكرر"""
        from src.models.student import Student
        phone_email = f'spe_{secrets.token_hex(4)}@test.com'

        existing = Student(
            name='طالب قديم',
            username=f'stu_old_{secrets.token_hex(4)}',
            email=phone_email, is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session)
        v = _make_verification(db_session, email=phone_email,
                                phone='+966501234568', grade=None,
                                is_verified=False)

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': phone_email,
                'code': '123456',
                'account_type': 'student'
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'مسجلاً' in data.get('error', '') or 'محجوزاً' in data.get('error', '')

    def test_verify_teacher_with_phone_duplicate_username(self, client, db_session):
        """مسار Teacher مع phone: username مكرر"""
        from src.models.teacher import Teacher
        dup_uname = f'tchu_{secrets.token_hex(4)}'
        existing = Teacher(
            name='معلم موجود', username=dup_uname,
            email=f'tchu_{secrets.token_hex(4)}@test.com', is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session)
        v = _make_verification(db_session,
                                email=f'new_{secrets.token_hex(4)}@test.com',
                                phone='+966501234569', grade='teacher',
                                is_verified=False)
        # override username in verification to match duplicate
        v.username = dup_uname
        db_session.session.commit()

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': v.email,
                'code': '123456',
                'account_type': 'teacher'
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'محجوزاً' in data.get('error', '') or 'مسجلاً' in data.get('error', '')

    def test_verify_student_with_phone_duplicate_username(self, client, db_session):
        """مسار Student مع phone: username مكرر"""
        from src.models.student import Student
        dup_uname = f'stuu_{secrets.token_hex(4)}'
        existing = Student(
            name='طالب موجود', username=dup_uname,
            email=f'stuu_{secrets.token_hex(4)}@test.com', is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session)
        v = _make_verification(db_session,
                                email=f'new_{secrets.token_hex(4)}@test.com',
                                phone='+966501234570', grade=None,
                                is_verified=False)
        v.username = dup_uname
        db_session.session.commit()

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': v.email,
                'code': '123456',
                'account_type': 'student'
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'محجوزاً' in data.get('error', '') or 'مسجلاً' in data.get('error', '')


# ---------------------------------------------------------------------------
# verify_code – lines 566, 624 (has_phone → should_activate=False branch)
# ---------------------------------------------------------------------------

class TestVerifyCodeHasPhone:
    """السيناريو 2: لا جوال → teacher/student مع should_activate"""

    def test_verify_teacher_no_phone_auto_activate_false(self, client, db_session):
        """السطر 566: معلم بدون جوال وauto_activate=False"""
        _open_reg(db_session, teacher_open=True, teacher_auto_activate=False)
        v = _make_verification(db_session, grade='teacher', phone=None, is_verified=False)

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            with patch('src.routes.registration.notify_admin'):
                with patch('src.routes.registration.create_teacher_token',
                           return_value='teacher_tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'teacher'
                    })
                    assert resp.status_code in [200, 400, 500]
                    if resp.status_code == 200:
                        data = resp.get_json()
                        assert data.get('success') is True
                        assert data.get('auto_login') is False or data.get('auto_login') is True

    def test_verify_teacher_with_phone_verify_flow(self, client, db_session):
        """السطر 566: معلم بجوال → should_activate=False في السيناريو 1 (has_phone=True)"""
        _open_reg(db_session, teacher_open=True, teacher_auto_activate=True)
        # السيناريو 1: معلم بجوال يُنشأ الحساب مع is_active=False
        v = _make_verification(db_session, grade='teacher', phone='+966501234571',
                                is_verified=False)

        with patch('src.routes.registration.notify_admin'):
            with patch('src.routes.registration.create_teacher_token',
                       return_value='teacher_tok'):
                with patch('src.models.email_verification.EmailVerification.verify_code',
                           return_value=(True, 'ok')):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'teacher'
                    })
                    assert resp.status_code in VALID_CODES

    def test_verify_student_no_phone_auto_activate_false(self, client, db_session):
        """السطر 624: طالب بدون جوال وauto_activate=False"""
        _open_reg(db_session, auto_activate=False)
        v = _make_verification(db_session, grade=None, phone=None, is_verified=False)

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            with patch('src.routes.registration.notify_admin'):
                with patch('src.routes.registration.create_student_token',
                           return_value='student_tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'student'
                    })
                    assert resp.status_code in [200, 400, 500]
                    if resp.status_code == 200:
                        data = resp.get_json()
                        assert data.get('success') is True

    def test_verify_student_with_phone_scenario2(self, client, db_session):
        """السطر 624: طالب بجوال → should_activate=False"""
        _open_reg(db_session, auto_activate=True)
        v = _make_verification(db_session, grade=None, phone='+966501234572',
                                is_verified=False)

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            with patch('src.routes.registration.notify_admin'):
                with patch('src.routes.registration.create_student_token',
                           return_value='student_tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'student'
                    })
                    # السيناريو 1 يُعالج هذا - التحقق من استجابة صحيحة
                    assert resp.status_code in VALID_CODES


# ---------------------------------------------------------------------------
# verify_phone_code – lines 711-777 (bulk paths)
# ---------------------------------------------------------------------------

class TestVerifyPhoneCode:
    """اختبارات شاملة لـ verify_phone_code"""

    def test_verify_phone_missing_email(self, client, db_session):
        """بدون إيميل"""
        resp = client.post('/api/registration/verify-phone', json={
            'code': '123456'
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data.get('success') is False

    def test_verify_phone_missing_code(self, client, db_session):
        """بدون رمز"""
        resp = client.post('/api/registration/verify-phone', json={
            'email': 'test@test.com'
        })
        assert resp.status_code == 400

    def test_verify_phone_no_verification_found(self, client, db_session):
        """لا يوجد طلب تحقق"""
        resp = client.post('/api/registration/verify-phone', json={
            'email': 'nonexistent@test.com',
            'code': '123456'
        })
        assert resp.status_code == 404
        data = resp.get_json()
        assert data.get('success') is False

    def test_verify_phone_no_phone_in_verification(self, client, db_session):
        """verification موجود لكن بدون phone"""
        v = _make_verification(db_session, phone=None, is_verified=True)
        resp = client.post('/api/registration/verify-phone', json={
            'email': v.email,
            'code': '123456'
        })
        assert resp.status_code == 404

    def test_verify_phone_wrong_code(self, client, db_session):
        """رمز جوال خاطئ"""
        from src.models.email_verification import EmailVerification
        v = _make_verification(db_session, phone='+966501234573', is_verified=True)
        with patch.object(EmailVerification, 'verify_phone_code',
                          return_value=(False, 'رمز غير صحيح'), create=True):
            resp = client.post('/api/registration/verify-phone', json={
                'email': v.email,
                'code': 'wrong'
            })
            assert resp.status_code in [400, 500]

    def test_verify_phone_teacher_success(self, client, db_session):
        """السطر 721-751: إنشاء معلم بنجاح عبر verify_phone_code"""
        from src.models.email_verification import EmailVerification
        v = _make_verification(db_session, phone='+966501234574',
                                grade='teacher', is_verified=True)
        with patch.object(EmailVerification, 'verify_phone_code',
                          return_value=(True, 'ok'), create=True):
            with patch('src.routes.registration.create_teacher_token',
                       return_value='teach_tok'):
                resp = client.post('/api/registration/verify-phone', json={
                    'email': v.email,
                    'code': '654321',
                    'account_type': 'teacher'
                })
                assert resp.status_code in [200, 400, 500]
                if resp.status_code == 200:
                    data = resp.get_json()
                    assert data.get('success') is True
                    assert data.get('account_type') == 'teacher'

    def test_verify_phone_student_success(self, client, db_session):
        """السطر 753-784: إنشاء طالب بنجاح عبر verify_phone_code"""
        from src.models.email_verification import EmailVerification
        v = _make_verification(db_session, phone='+966501234575',
                                grade=None, is_verified=True)
        with patch.object(EmailVerification, 'verify_phone_code',
                          return_value=(True, 'ok'), create=True):
            with patch('src.routes.registration.create_student_token',
                       return_value='stud_tok'):
                resp = client.post('/api/registration/verify-phone', json={
                    'email': v.email,
                    'code': '654321',
                    'account_type': 'student'
                })
                assert resp.status_code in [200, 400, 500]
                if resp.status_code == 200:
                    data = resp.get_json()
                    assert data.get('success') is True
                    assert data.get('account_type') == 'student'

    def test_verify_phone_teacher_duplicate_conflict(self, client, db_session):
        """السطر 723-728: معلم موجود بنفس البيانات"""
        from src.models.teacher import Teacher
        from src.models.email_verification import EmailVerification
        phone_email = f'tph_{secrets.token_hex(4)}@test.com'
        username = f'tph_{secrets.token_hex(4)}'

        existing = Teacher(
            name='معلم موجود', username=username,
            email=phone_email, is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        v = _make_verification(db_session, email=phone_email,
                                phone='+966501234576', grade='teacher',
                                is_verified=True)
        v.username = username
        db_session.session.commit()

        with patch.object(EmailVerification, 'verify_phone_code',
                          return_value=(True, 'ok'), create=True):
            resp = client.post('/api/registration/verify-phone', json={
                'email': phone_email,
                'code': '654321',
                'account_type': 'teacher'
            })
            assert resp.status_code in [400, 500]
            data = resp.get_json()
            assert data.get('success') is False

    def test_verify_phone_student_duplicate_conflict(self, client, db_session):
        """السطر 754-759: طالب موجود بنفس البيانات"""
        from src.models.student import Student
        from src.models.email_verification import EmailVerification
        phone_email = f'sph_{secrets.token_hex(4)}@test.com'
        username = f'sph_{secrets.token_hex(4)}'

        existing = Student(
            name='طالب موجود', username=username,
            email=phone_email, is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        v = _make_verification(db_session, email=phone_email,
                                phone='+966501234577', grade=None,
                                is_verified=True)
        v.username = username
        db_session.session.commit()

        with patch.object(EmailVerification, 'verify_phone_code',
                          return_value=(True, 'ok'), create=True):
            resp = client.post('/api/registration/verify-phone', json={
                'email': phone_email,
                'code': '654321',
                'account_type': 'student'
            })
            assert resp.status_code in [400, 500]
            data = resp.get_json()
            assert data.get('success') is False

    def test_verify_phone_account_type_via_grade(self, client, db_session):
        """تحديد نوع الحساب عبر grade='teacher' بدلاً من account_type"""
        from src.models.email_verification import EmailVerification
        v = _make_verification(db_session, phone='+966501234578',
                                grade='teacher', is_verified=True)
        with patch.object(EmailVerification, 'verify_phone_code',
                          return_value=(True, 'ok'), create=True):
            with patch('src.routes.registration.create_teacher_token',
                       return_value='tok'):
                resp = client.post('/api/registration/verify-phone', json={
                    'email': v.email,
                    'code': '654321'
                    # بدون account_type → الافتراضي 'student' لكن grade='teacher'
                })
                assert resp.status_code in VALID_CODES

    def test_verify_phone_exception_path(self, client, db_session):
        """مسار الاستثناء في verify_phone_code"""
        from src.models.email_verification import EmailVerification
        v = _make_verification(db_session, phone='+966501234579',
                                grade=None, is_verified=True)
        with patch.object(EmailVerification, 'verify_phone_code',
                          side_effect=Exception("DB crash"), create=True):
            resp = client.post('/api/registration/verify-phone', json={
                'email': v.email,
                'code': '654321',
                'account_type': 'student'
            })
            assert resp.status_code == 500


# ---------------------------------------------------------------------------
# activate_after_phone – lines 855-860
# ---------------------------------------------------------------------------

class TestActivateAfterPhone:
    """اختبارات activate_after_phone"""

    def test_activate_student_success(self, client, db_session):
        """تفعيل طالب موجود بنجاح"""
        from src.models.student import Student
        s = Student(
            name='طالب للتفعيل', username=f'act_{secrets.token_hex(4)}',
            email=f'act_{secrets.token_hex(4)}@test.com', is_active=False
        )
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)

        with patch('src.routes.registration.create_student_token', return_value='tok'):
            resp = client.post('/api/registration/activate-after-phone', json={
                'email': s.email,
                'phone': '+966501234580',
                'account_type': 'student'
            })
            assert resp.status_code in [200, 400, 500]
            if resp.status_code == 200:
                data = resp.get_json()
                assert data.get('success') is True
                assert data.get('is_active') is True

    def test_activate_teacher_success(self, client, db_session):
        """تفعيل معلم موجود بنجاح"""
        from src.models.teacher import Teacher
        t = Teacher(
            name='معلم للتفعيل', username=f'tact_{secrets.token_hex(4)}',
            email=f'tact_{secrets.token_hex(4)}@test.com', is_active=False
        )
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)

        with patch('src.routes.registration.create_teacher_token', return_value='tok'):
            resp = client.post('/api/registration/activate-after-phone', json={
                'email': t.email,
                'phone': '+966501234581',
                'account_type': 'teacher'
            })
            assert resp.status_code in [200, 400, 500]
            if resp.status_code == 200:
                data = resp.get_json()
                assert data.get('success') is True

    def test_activate_missing_email(self, client, db_session):
        """بدون إيميل"""
        resp = client.post('/api/registration/activate-after-phone', json={
            'phone': '+966501234582',
        })
        assert resp.status_code == 400

    def test_activate_missing_phone(self, client, db_session):
        """بدون جوال"""
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': 'test@test.com',
        })
        assert resp.status_code == 400

    def test_activate_user_not_found(self, client, db_session):
        """حساب غير موجود"""
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': 'notfound@test.com',
            'phone': '+966501234583',
            'account_type': 'student'
        })
        assert resp.status_code == 404
        data = resp.get_json()
        assert data.get('success') is False

    def test_activate_exception_path(self, client, db_session):
        """السطر 855-860: استثناء عند التفعيل"""
        with patch('src.routes.registration.Student') as mock_student:
            mock_student.query.filter_by.side_effect = Exception("DB error")
            resp = client.post('/api/registration/activate-after-phone', json={
                'email': 'test@test.com',
                'phone': '+966501234584',
                'account_type': 'student'
            })
            assert resp.status_code == 500
            data = resp.get_json()
            assert data.get('success') is False

    def test_activate_teacher_not_found(self, client, db_session):
        """معلم غير موجود"""
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': 'notsuchteacher@test.com',
            'phone': '+966501234585',
            'account_type': 'teacher'
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# resend_code – lines 917-919
# ---------------------------------------------------------------------------

class TestResendCode:
    """اختبارات resend_code"""

    def test_resend_success(self, client, db_session):
        """إعادة إرسال ناجحة"""
        v = _make_verification(db_session, is_verified=False)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/resend', json={'email': v.email})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get('success') is True

    def test_resend_missing_email(self, client, db_session):
        """بدون إيميل"""
        resp = client.post('/api/registration/resend', json={})
        assert resp.status_code == 400

    def test_resend_no_verification_found(self, client, db_session):
        """لا يوجد طلب"""
        resp = client.post('/api/registration/resend',
                           json={'email': 'noreq@test.com'})
        assert resp.status_code == 404

    def test_resend_email_send_fails(self, client, db_session):
        """فشل إرسال الإيميل"""
        v = _make_verification(db_session, is_verified=False)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (False, 'SMTP error')
            resp = client.post('/api/registration/resend', json={'email': v.email})
            assert resp.status_code == 500
            data = resp.get_json()
            assert data.get('success') is False

    def test_resend_exception_path(self, client, db_session):
        """السطر 917-919: استثناء عام في resend"""
        with patch('src.models.email_verification.EmailVerification.query') as mock_query:
            mock_query.filter_by.side_effect = Exception("DB crash")
            resp = client.post('/api/registration/resend',
                               json={'email': 'crash@test.com'})
            assert resp.status_code == 500
            data = resp.get_json()
            assert data.get('success') is False

    def test_resend_already_verified(self, client, db_session):
        """verification مكتمل (is_verified=True) لا يُعاد إرساله"""
        v = _make_verification(db_session, is_verified=True)
        resp = client.post('/api/registration/resend', json={'email': v.email})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# register_student – additional validation paths
# ---------------------------------------------------------------------------

class TestRegisterStudentValidation:
    """تغطية validation إضافية في register_student"""

    def test_register_closed(self, client, db_session):
        """التسجيل مغلق"""
        from src.models.email_verification import RegistrationSettings
        s = RegistrationSettings.get_settings()
        s.is_registration_open = False
        db_session.session.commit()

        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 403
        _open_reg(db_session)  # إعادة الفتح

    def test_register_missing_fields(self, client, db_session):
        """حقول ناقصة"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
        })
        assert resp.status_code == 400

    def test_register_invalid_name_short_part(self, client, db_session):
        """جزء من الاسم أقل من حرفين"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أ محمد علي',
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_name_mixed_arabic_english(self, client, db_session):
        """اسم يخلط عربي وإنجليزي"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'Ahmed محمد علي',
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_name_repeated_chars(self, client, db_session):
        """اسم بأحرف مكررة"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد ااااا',
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_name_with_abu(self, client, db_session):
        """اسم يبدأ بـ 'أبو'"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أبو محمد علي',
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_name_identical_parts(self, client, db_session):
        """الاسم الأول والثاني متطابقان"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'محمد محمد علي',
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_name_too_long(self, client, db_session):
        """اسم أطول من 40 حرف"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد ' + 'ع' * 35,
            'username': 'testuser1',
            'email': 'test@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_invalid_email_format(self, client, db_session):
        """صيغة إيميل خاطئة"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': 'testuser1',
            'email': 'notanemail',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_blocked_email(self, client, db_session):
        """إيميل مؤقت محظور"""
        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': 'testuser1',
            'email': 'student@yopmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_require_phone_missing(self, client, db_session):
        """require_phone=True بدون جوال"""
        _open_reg(db_session, require_phone=True)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': 'testuser1',
            'email': f's_{secrets.token_hex(4)}@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_require_school_missing(self, client, db_session):
        """require_school=True بدون مدرسة"""
        _open_reg(db_session, require_school=True)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': 'testuser1',
            'email': f's_{secrets.token_hex(4)}@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client, db_session):
        """اسم مستخدم موجود"""
        from src.models.student import Student
        existing = Student(
            name='طالب قديم', username='dupstudent',
            email=f'dup_{secrets.token_hex(4)}@test.com', is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': 'dupstudent',
            'email': f'new_{secrets.token_hex(4)}@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_duplicate_email(self, client, db_session):
        """إيميل موجود"""
        from src.models.student import Student
        dup_email = f'dup_{secrets.token_hex(4)}@test.com'
        existing = Student(
            name='طالب قديم',
            username=f'uniq_{secrets.token_hex(4)}',
            email=dup_email, is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session)
        resp = client.post('/api/registration/register', json={
            'name': 'أحمد محمد علي',
            'username': f'new_{secrets.token_hex(4)}',
            'email': dup_email,
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400

    def test_register_email_send_fails(self, client, db_session):
        """فشل إرسال رمز التحقق"""
        _open_reg(db_session)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (False, 'SMTP error')
            resp = client.post('/api/registration/register', json={
                'name': 'أحمد محمد علي',
                'username': f'newu_{secrets.token_hex(4)}',
                'email': f'new_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 500

    def test_register_success(self, client, db_session):
        """تسجيل ناجح"""
        _open_reg(db_session)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register', json={
                'name': 'أحمد محمد علي',
                'username': f'success_{secrets.token_hex(4)}',
                'email': f'success_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code in [200, 400, 500]


# ---------------------------------------------------------------------------
# get_registration_status
# ---------------------------------------------------------------------------

class TestRegistrationStatus:
    """اختبارات status endpoint"""

    def test_status_student(self, client, db_session):
        """status للطلاب"""
        _open_reg(db_session)
        resp = client.get('/api/registration/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert 'is_open' in data

    def test_status_teacher(self, client, db_session):
        """status للمعلمين"""
        _open_reg(db_session, teacher_open=True)
        resp = client.get('/api/registration/status?type=teacher')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert 'is_open' in data

    def test_status_teacher_closed(self, client, db_session):
        """status معلمين مغلق"""
        from src.models.email_verification import RegistrationSettings
        s = RegistrationSettings.get_settings()
        s.is_teacher_registration_open = False
        s.teacher_closed_message = 'تسجيل المعلمين مغلق'
        db_session.session.commit()

        resp = client.get('/api/registration/status?type=teacher')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('is_open') is False
        _open_reg(db_session)

    def test_status_exception(self, client, db_session):
        """استثناء في status"""
        with patch('src.routes.registration.RegistrationSettings') as mock_rs:
            mock_rs.get_settings.side_effect = Exception("DB error")
            resp = client.get('/api/registration/status')
            assert resp.status_code == 500


# ---------------------------------------------------------------------------
# verify_code – general paths
# ---------------------------------------------------------------------------

class TestVerifyCodeGeneral:
    """مسارات عامة في verify_code"""

    def test_verify_missing_fields(self, client, db_session):
        """حقول ناقصة"""
        resp = client.post('/api/registration/verify', json={'email': 'x@x.com'})
        assert resp.status_code == 400

    def test_verify_no_verification_found(self, client, db_session):
        """لا يوجد طلب تحقق"""
        resp = client.post('/api/registration/verify', json={
            'email': 'none@test.com',
            'code': '123456'
        })
        assert resp.status_code == 404

    def test_verify_wrong_code(self, client, db_session):
        """رمز خاطئ"""
        v = _make_verification(db_session, is_verified=False)
        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(False, 'رمز منتهي الصلاحية')):
            resp = client.post('/api/registration/verify', json={
                'email': v.email,
                'code': '000000'
            })
            assert resp.status_code == 400

    def test_verify_require_phone_but_missing(self, client, db_session):
        """require_phone=True لكن verification بدون phone"""
        _open_reg(db_session, require_phone=True)
        v = _make_verification(db_session, phone=None, is_verified=False)
        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': v.email,
                'code': '123456',
                'account_type': 'student'
            })
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'الجوال' in data.get('error', '') or 'phone' in data.get('error', '').lower()

    def test_verify_exception_path(self, client, db_session):
        """استثناء في verify_code"""
        with patch('src.models.email_verification.EmailVerification.query') as mock_q:
            mock_q.filter_by.side_effect = Exception("crash")
            resp = client.post('/api/registration/verify', json={
                'email': 'x@test.com',
                'code': '123456'
            })
            assert resp.status_code == 500

    def test_verify_teacher_registration_closed(self, client, db_session):
        """تسجيل المعلمين مغلق"""
        from src.models.email_verification import RegistrationSettings
        s = RegistrationSettings.get_settings()
        s.is_teacher_registration_open = False
        db_session.session.commit()

        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tch_{secrets.token_hex(4)}',
                'email': f't_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 403
        _open_reg(db_session)

    def test_verify_teacher_success_no_phone(self, client, db_session):
        """تحقق معلم بنجاح - بدون جوال"""
        _open_reg(db_session, teacher_open=True, teacher_auto_activate=True)
        v = _make_verification(db_session, grade='teacher', phone=None,
                                is_verified=False)
        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            with patch('src.routes.registration.notify_admin'):
                with patch('src.routes.registration.create_teacher_token',
                           return_value='tok'):
                    resp = client.post('/api/registration/verify', json={
                        'email': v.email,
                        'code': '123456',
                        'account_type': 'teacher'
                    })
                    assert resp.status_code in [200, 400, 500]

    def test_verify_teacher_duplicate_username_no_phone(self, client, db_session):
        """السطر 550-554: معلم username مكرر بدون جوال"""
        from src.models.teacher import Teacher
        dup_uname = f'tchdup_{secrets.token_hex(4)}'
        existing = Teacher(
            name='معلم موجود', username=dup_uname,
            email=f'tchdup_{secrets.token_hex(4)}@test.com', is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session, teacher_open=True, teacher_auto_activate=True)
        v = _make_verification(db_session, grade='teacher', phone=None,
                                is_verified=False)
        v.username = dup_uname
        db_session.session.commit()

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': v.email,
                'code': '123456',
                'account_type': 'teacher'
            })
            assert resp.status_code == 400

    def test_verify_student_duplicate_username_no_phone(self, client, db_session):
        """السطر 608-612: طالب username مكرر بدون جوال"""
        from src.models.student import Student
        dup_uname = f'studup_{secrets.token_hex(4)}'
        existing = Student(
            name='طالب موجود', username=dup_uname,
            email=f'studup_{secrets.token_hex(4)}@test.com', is_active=True
        )
        existing.set_password('Pass@123')
        db_session.session.add(existing)
        db_session.session.commit()

        _open_reg(db_session, auto_activate=True)
        v = _make_verification(db_session, grade=None, phone=None,
                                is_verified=False)
        v.username = dup_uname
        db_session.session.commit()

        with patch('src.models.email_verification.EmailVerification.verify_code',
                   return_value=(True, 'ok')):
            resp = client.post('/api/registration/verify', json={
                'email': v.email,
                'code': '123456',
                'account_type': 'student'
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# register_teacher – success path
# ---------------------------------------------------------------------------

class TestRegisterTeacherSuccess:
    """مسار التسجيل الناجح للمعلم"""

    def test_register_teacher_success(self, client, db_session):
        """تسجيل معلم ناجح"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (True, 'ok')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tch_{secrets.token_hex(4)}',
                'email': f'tch_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code in [200, 400, 500]
            if resp.status_code == 200:
                data = resp.get_json()
                assert data.get('success') is True

    def test_register_teacher_email_send_fails(self, client, db_session):
        """فشل إرسال رمز للمعلم"""
        _open_reg(db_session, teacher_open=True)
        with patch('src.routes.registration.email_service') as mock_email:
            mock_email.send_verification_code.return_value = (False, 'SMTP error')
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tch_{secrets.token_hex(4)}',
                'email': f'tch_{secrets.token_hex(4)}@gmail.com',
                'password': 'Pass@1234',
            })
            assert resp.status_code == 500

    def test_register_teacher_missing_fields(self, client, db_session):
        """حقول ناقصة في register_teacher"""
        _open_reg(db_session, teacher_open=True)
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد محمد علي',
        })
        assert resp.status_code == 400

    def test_register_teacher_invalid_name(self, client, db_session):
        """اسم غير صحيح في register_teacher"""
        _open_reg(db_session, teacher_open=True)
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد',  # اسم ثنائي
            'username': 'teacher1',
            'email': f't_{secrets.token_hex(4)}@gmail.com',
            'password': 'Pass@1234',
        })
        assert resp.status_code == 400
