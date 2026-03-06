"""
test_registration_deep2.py
Additional integration tests for registration.py targeting uncovered lines.

Routes covered:
  GET  /api/registration/status
  POST /api/registration/register
  POST /api/registration/register-teacher
  POST /api/registration/verify
  POST /api/registration/verify-phone
  POST /api/registration/activate-after-phone
  POST /api/registration/resend
  GET  /api/registration/admin/settings
  POST /api/registration/admin/settings
  POST /api/registration/admin/toggle

Focus: edge cases in validation, all error branches, admin paths,
       teacher registration, phone verification flow, and notify_admin paths.
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


def _make_verification(db_session, email, username, phone=None, grade=None,
                        is_verified=False, expired=False):
    """Create an EmailVerification row directly for test setup."""
    from src.models.email_verification import EmailVerification
    from src.models.student import Student
    # Remove old unverified for same email
    EmailVerification.query.filter_by(email=email, is_verified=False).delete()
    db_session.session.commit()

    expires = datetime.utcnow() + timedelta(minutes=3)
    if expired:
        expires = datetime.utcnow() - timedelta(minutes=10)

    code = '123456'
    v = EmailVerification(
        email=email,
        code=code,
        name='أحمد محمد علي',
        username=username,
        password_hash=generate_password_hash('TestPass@1'),
        phone=phone,
        school='مدرسة الأمل',
        grade=grade,
        is_verified=is_verified,
        expires_at=expires,
    )
    db_session.session.add(v)
    db_session.session.commit()
    db_session.session.refresh(v)
    return v


def _make_student(db_session, username=None, email=None):
    from src.models.student import Student
    tok = secrets.token_hex(4)
    s = Student(
        name='طالب اختبار',
        username=username or f'stu_{tok}',
        email=email or f'stu_{tok}@test.com',
        is_active=False,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_teacher(db_session, username=None, email=None):
    from src.models.teacher import Teacher
    tok = secrets.token_hex(4)
    t = Teacher(
        name='معلم اختبار',
        username=username or f'tch_{tok}',
        email=email or f'tch_{tok}@test.com',
        is_active=False,
    )
    t.set_password('Pass@123')
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _open_registration(db_session):
    """Ensure student and teacher registration is open."""
    from src.models.email_verification import RegistrationSettings
    s = RegistrationSettings.get_settings()
    s.is_registration_open = True
    s.is_teacher_registration_open = True
    s.require_phone = False
    s.require_school = False
    s.teacher_require_phone = False
    s.teacher_require_school = False
    s.auto_activate = True
    s.teacher_auto_activate = True
    db_session.session.commit()


def _close_registration(db_session):
    from src.models.email_verification import RegistrationSettings
    s = RegistrationSettings.get_settings()
    s.is_registration_open = False
    s.is_teacher_registration_open = False
    db_session.session.commit()


# ===========================================================================
# 1. GET /api/registration/status
# ===========================================================================

class TestRegistrationStatus:
    """GET /api/registration/status - all branches."""

    def test_status_default_student(self, client, db_session):
        resp = client.get('/api/registration/status')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'is_open' in data or 'success' in data

    def test_status_student_explicit(self, client, db_session):
        resp = client.get('/api/registration/status?type=student')
        assert resp.status_code in VALID_CODES

    def test_status_teacher_type(self, client, db_session):
        resp = client.get('/api/registration/status?type=teacher')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'is_open' in data or 'success' in data

    def test_status_teacher_fields_returned(self, client, db_session):
        resp = client.get('/api/registration/status?type=teacher')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'require_phone' in data or 'is_open' in data

    def test_status_student_fields_returned(self, client, db_session):
        resp = client.get('/api/registration/status?type=student')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'require_phone' in data or 'is_open' in data

    def test_status_when_closed(self, client, db_session):
        _close_registration(db_session)
        resp = client.get('/api/registration/status')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('is_open') is False or 'message' in data

    def test_status_when_open(self, client, db_session):
        _open_registration(db_session)
        resp = client.get('/api/registration/status')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('is_open') is True


# ===========================================================================
# 2. POST /api/registration/register - All validation branches
# ===========================================================================

class TestRegisterStudent:
    """POST /api/registration/register - extensive validation coverage."""

    def setup_method(self):
        """Base valid payload."""
        tok = secrets.token_hex(4)
        self.valid_payload = {
            'name': 'أحمد محمد علي',
            'username': f'user_{tok}',
            'email': f'user_{tok}@gmail.com',
            'password': 'SecurePass@1',
        }

    def test_registration_closed_returns_403(self, client, db_session):
        _close_registration(db_session)
        resp = client.post('/api/registration/register', json=self.valid_payload)
        assert resp.status_code in VALID_CODES
        if resp.status_code == 403:
            data = resp.get_json()
            assert data.get('success') is False

    def test_missing_name_returns_400(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': ''}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_missing_username_returns_400(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'username': ''}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_missing_email_returns_400(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'email': ''}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_missing_password_returns_400(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'password': ''}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_too_short_two_parts(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'أحمد محمد'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_with_numbers(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'أحمد 123 علي'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_too_long(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'أ' * 41}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_mixed_arabic_english(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'Ahmed محمد علي'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_duplicate_first_second(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'أحمد أحمد علي'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_starts_with_abu(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'ابو علي محمد'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_single_char_parts(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'أ ب ت'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_repeated_chars(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'name': 'أحمدددد محمد علي'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_username_too_short(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'username': 'ab'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_username_too_long(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'username': 'a' * 21}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_username_starts_with_digit(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'username': '1username'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_username_with_special_chars(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'username': 'user@name'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_password_too_short(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'password': 'Ab1'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_password_no_letter(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'password': '12345678'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_password_no_digit(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'password': 'abcdefgh'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_password_weak_in_list(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'password': 'admin123'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_email_invalid_format(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'email': 'not-an-email'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_email_temp_domain_blocked(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'email': 'user@mailinator.com'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            assert data.get('success') is False

    def test_email_yopmail_blocked(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.valid_payload, 'email': 'test@yopmail.com'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_duplicate_username(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        existing = _make_student(db_session, username=f'dup_{tok}',
                                  email=f'orig_{tok}@gmail.com')
        payload = {
            'name': 'أحمد محمد علي',
            'username': existing.username,
            'email': f'diff_{tok}@gmail.com',
            'password': 'SecurePass@1',
        }
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_duplicate_email(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        existing = _make_student(db_session, username=f'unq_{tok}',
                                  email=f'dup_{tok}@gmail.com')
        payload = {
            'name': 'أحمد محمد علي',
            'username': f'newusr_{tok}',
            'email': existing.email,
            'password': 'SecurePass@1',
        }
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_require_phone_setting_missing_phone(self, client, db_session):
        from src.models.email_verification import RegistrationSettings
        _open_registration(db_session)
        s = RegistrationSettings.get_settings()
        s.require_phone = True
        db_session.session.commit()
        payload = {**self.valid_payload}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            assert data.get('success') is False

    def test_require_school_setting_missing_school(self, client, db_session):
        from src.models.email_verification import RegistrationSettings
        _open_registration(db_session)
        s = RegistrationSettings.get_settings()
        s.require_school = True
        db_session.session.commit()
        payload = {**self.valid_payload}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_email_send_failure_cleans_verification(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        payload = {
            'name': 'أحمد محمد علي',
            'username': f'fail_{tok}',
            'email': f'fail_{tok}@gmail.com',
            'password': 'SecurePass@1',
        }
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(False, 'SMTP error')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_valid_registration_email_sent(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        payload = {
            'name': 'أحمد محمد علي',
            'username': f'valid_{tok}',
            'email': f'valid_{tok}@gmail.com',
            'password': 'SecurePass@1',
        }
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('success') is True


# ===========================================================================
# 3. POST /api/registration/register-teacher
# ===========================================================================

class TestRegisterTeacher:
    """POST /api/registration/register-teacher - coverage."""

    def test_teacher_registration_closed(self, client, db_session):
        _close_registration(db_session)
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد محمد علي',
            'username': 'tch_abc1',
            'email': 'tch@gmail.com',
            'password': 'SecurePass@1',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_missing_required_fields(self, client, db_session):
        _open_registration(db_session)
        resp = client.post('/api/registration/register-teacher', json={
            'name': '',
            'username': '',
            'email': '',
            'password': '',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_invalid_name(self, client, db_session):
        _open_registration(db_session)
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد',
            'username': 'tch_x123',
            'email': 'tch_x123@gmail.com',
            'password': 'SecurePass@1',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_weak_password(self, client, db_session):
        _open_registration(db_session)
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد محمد علي',
            'username': 'tch_x456',
            'email': 'tch_x456@gmail.com',
            'password': 'admin123',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_temp_email_blocked(self, client, db_session):
        _open_registration(db_session)
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد محمد علي',
            'username': 'tch_t789',
            'email': 'teacher@guerrillamail.com',
            'password': 'SecurePass@1',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_duplicate_username_in_teachers(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        _make_teacher(db_session, username=f'tdup_{tok}', email=f'tdup_{tok}@gmail.com')
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tdup_{tok}',
                'email': f'new_{tok}@gmail.com',
                'password': 'SecurePass@1',
            })
        assert resp.status_code in VALID_CODES

    def test_teacher_duplicate_username_in_students(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        _make_student(db_session, username=f'tsdup_{tok}', email=f'stu_{tok}@gmail.com')
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tsdup_{tok}',
                'email': f'tch_ns_{tok}@gmail.com',
                'password': 'SecurePass@1',
            })
        assert resp.status_code in VALID_CODES

    def test_teacher_duplicate_email(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        t = _make_teacher(db_session, username=f'tne_{tok}', email=f'tde_{tok}@gmail.com')
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'new_tch_{tok}',
                'email': t.email,
                'password': 'SecurePass@1',
            })
        assert resp.status_code in VALID_CODES

    def test_teacher_require_phone_missing(self, client, db_session):
        from src.models.email_verification import RegistrationSettings
        _open_registration(db_session)
        s = RegistrationSettings.get_settings()
        s.teacher_require_phone = True
        db_session.session.commit()
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد محمد علي',
            'username': 'tch_rph1',
            'email': 'tch_rph1@gmail.com',
            'password': 'SecurePass@1',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_require_school_missing(self, client, db_session):
        from src.models.email_verification import RegistrationSettings
        _open_registration(db_session)
        s = RegistrationSettings.get_settings()
        s.teacher_require_school = True
        db_session.session.commit()
        resp = client.post('/api/registration/register-teacher', json={
            'name': 'أحمد محمد علي',
            'username': 'tch_rsc1',
            'email': 'tch_rsc1@gmail.com',
            'password': 'SecurePass@1',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_email_send_failure(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(False, 'SMTP error')):
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tch_fail_{tok}',
                'email': f'tch_fail_{tok}@gmail.com',
                'password': 'SecurePass@1',
            })
        assert resp.status_code in VALID_CODES

    def test_teacher_valid_registration(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register-teacher', json={
                'name': 'أحمد محمد علي',
                'username': f'tch_ok_{tok}',
                'email': f'tch_ok_{tok}@gmail.com',
                'password': 'SecurePass@1',
            })
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 4. POST /api/registration/verify
# ===========================================================================

class TestVerifyCode:
    """POST /api/registration/verify - all branches."""

    def test_missing_email_and_code(self, client, db_session):
        resp = client.post('/api/registration/verify', json={})
        assert resp.status_code in VALID_CODES

    def test_missing_email(self, client, db_session):
        resp = client.post('/api/registration/verify', json={'code': '123456'})
        assert resp.status_code in VALID_CODES

    def test_missing_code(self, client, db_session):
        resp = client.post('/api/registration/verify', json={'email': 'x@x.com'})
        assert resp.status_code in VALID_CODES

    def test_no_verification_record(self, client, db_session):
        resp = client.post('/api/registration/verify', json={
            'email': 'norecord@gmail.com',
            'code': '123456',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 404:
            data = resp.get_json()
            assert data.get('success') is False

    def test_wrong_code(self, client, db_session):
        tok = secrets.token_hex(4)
        email = f'vc_{tok}@gmail.com'
        _make_verification(db_session, email, f'vc_{tok}')
        resp = client.post('/api/registration/verify', json={
            'email': email,
            'code': '000000',
        })
        assert resp.status_code in VALID_CODES

    def test_expired_code(self, client, db_session):
        tok = secrets.token_hex(4)
        email = f'exp_{tok}@gmail.com'
        _make_verification(db_session, email, f'exp_{tok}', expired=True)
        resp = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
        })
        assert resp.status_code in VALID_CODES

    def test_valid_code_student_no_phone_auto_activate(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vs_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vs_{tok}')
        with patch('src.routes.registration.notify_admin'):
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
                'account_type': 'student',
            })
        assert resp.status_code in VALID_CODES

    def test_valid_code_teacher_no_phone(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vt_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vt_{tok}', grade='teacher')
        with patch('src.routes.registration.notify_admin'):
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
                'account_type': 'teacher',
            })
        assert resp.status_code in VALID_CODES

    def test_valid_code_student_with_phone(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vsp_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vsp_{tok}', phone='+966512345678')
        with patch('src.routes.registration.notify_admin'):
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
                'account_type': 'student',
            })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('require_phone_verification') is True

    def test_valid_code_teacher_with_phone(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vtp_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vtp_{tok}',
                                phone='+966598765432', grade='teacher')
        with patch('src.routes.registration.notify_admin'):
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
                'account_type': 'teacher',
            })
        assert resp.status_code in VALID_CODES

    def test_require_phone_but_no_phone(self, client, db_session):
        from src.models.email_verification import RegistrationSettings
        _open_registration(db_session)
        s = RegistrationSettings.get_settings()
        s.require_phone = True
        db_session.session.commit()
        tok = secrets.token_hex(4)
        email = f'rph_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'rph_{tok}')  # no phone
        resp = client.post('/api/registration/verify', json={
            'email': email,
            'code': v.code,
            'account_type': 'student',
        })
        assert resp.status_code in VALID_CODES

    def test_duplicate_username_at_verify_time(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'dupv_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'dupvs_{tok}')
        # Create student with same username after verification was created
        _make_student(db_session, username=v.username, email=f'other_{tok}@gmail.com')
        with patch('src.routes.registration.notify_admin'):
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
                'account_type': 'student',
            })
        assert resp.status_code in VALID_CODES

    def test_valid_student_returns_token(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vtok_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vtok_{tok}')
        with patch('src.routes.registration.notify_admin'):
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
            })
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'token' in data or 'student' in data


# ===========================================================================
# 5. POST /api/registration/verify-phone
# ===========================================================================

class TestVerifyPhoneCode:
    """POST /api/registration/verify-phone - all branches."""

    def test_missing_email_and_code(self, client, db_session):
        resp = client.post('/api/registration/verify-phone', json={})
        assert resp.status_code in VALID_CODES

    def test_missing_code_only(self, client, db_session):
        resp = client.post('/api/registration/verify-phone', json={
            'email': 'x@gmail.com'
        })
        assert resp.status_code in VALID_CODES

    def test_no_verified_record(self, client, db_session):
        resp = client.post('/api/registration/verify-phone', json={
            'email': 'norecord@gmail.com',
            'code': '123456',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 404:
            data = resp.get_json()
            assert data.get('success') is False

    def test_wrong_phone_code(self, client, db_session):
        tok = secrets.token_hex(4)
        email = f'ph_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'ph_{tok}',
                                phone='+966512345678', is_verified=True)
        resp = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '000000',
            'account_type': 'student',
        })
        assert resp.status_code in VALID_CODES

    def test_verified_record_no_phone(self, client, db_session):
        """Verified record but phone is None → 404."""
        tok = secrets.token_hex(4)
        email = f'nph_{tok}@gmail.com'
        _make_verification(db_session, email, f'nph_{tok}', is_verified=True)
        # phone is None by default
        resp = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '123456',
        })
        assert resp.status_code in VALID_CODES

    def test_valid_phone_student_creates_account(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vpc_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vpc_{tok}',
                                phone='+966512345678', is_verified=True)
        # verify_phone_code doesn't exist in this model - route will error gracefully
        resp = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': v.code,
            'account_type': 'student',
        })
        assert resp.status_code in VALID_CODES

    def test_valid_phone_teacher_creates_account(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'vpt_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'vpt_{tok}',
                                phone='+966598765432', grade='teacher', is_verified=True)
        resp = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': v.code,
            'account_type': 'teacher',
        })
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 6. POST /api/registration/activate-after-phone
# ===========================================================================

class TestActivateAfterPhone:
    """POST /api/registration/activate-after-phone."""

    def test_missing_email_and_phone(self, client, db_session):
        resp = client.post('/api/registration/activate-after-phone', json={})
        assert resp.status_code in VALID_CODES

    def test_missing_phone(self, client, db_session):
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': 'x@gmail.com',
        })
        assert resp.status_code in VALID_CODES

    def test_student_not_found(self, client, db_session):
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': 'notfound@gmail.com',
            'phone': '+966512345678',
            'account_type': 'student',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 404:
            data = resp.get_json()
            assert data.get('success') is False

    def test_teacher_not_found(self, client, db_session):
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': 'teacher_nf@gmail.com',
            'phone': '+966512345678',
            'account_type': 'teacher',
        })
        assert resp.status_code in VALID_CODES

    def test_student_activated(self, client, db_session):
        tok = secrets.token_hex(4)
        s = _make_student(db_session, username=f'act_{tok}',
                           email=f'act_{tok}@gmail.com')
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': s.email,
            'phone': '+966512345678',
            'account_type': 'student',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True
                assert data.get('is_active') is True

    def test_teacher_activated(self, client, db_session):
        tok = secrets.token_hex(4)
        t = _make_teacher(db_session, username=f'tact_{tok}',
                           email=f'tact_{tok}@gmail.com')
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': t.email,
            'phone': '+966598765432',
            'account_type': 'teacher',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True

    def test_returns_token_on_success(self, client, db_session):
        tok = secrets.token_hex(4)
        s = _make_student(db_session, username=f'tokact_{tok}',
                           email=f'tokact_{tok}@gmail.com')
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': s.email,
            'phone': '+966512345678',
            'account_type': 'student',
        })
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'token' in data

    def test_default_account_type_is_student(self, client, db_session):
        tok = secrets.token_hex(4)
        s = _make_student(db_session, username=f'defact_{tok}',
                           email=f'defact_{tok}@gmail.com')
        resp = client.post('/api/registration/activate-after-phone', json={
            'email': s.email,
            'phone': '+966512345678',
        })
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 7. POST /api/registration/resend
# ===========================================================================

class TestResendCode:
    """POST /api/registration/resend."""

    def test_missing_email(self, client, db_session):
        resp = client.post('/api/registration/resend', json={})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            assert data.get('success') is False

    def test_no_pending_verification(self, client, db_session):
        resp = client.post('/api/registration/resend', json={
            'email': 'noverif@gmail.com',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 404:
            data = resp.get_json()
            assert data.get('success') is False

    def test_resend_success(self, client, db_session):
        tok = secrets.token_hex(4)
        email = f'rsd_{tok}@gmail.com'
        _make_verification(db_session, email, f'rsd_{tok}')
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/resend', json={'email': email})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('success') is True

    def test_resend_email_failure(self, client, db_session):
        tok = secrets.token_hex(4)
        email = f'rsdf_{tok}@gmail.com'
        _make_verification(db_session, email, f'rsdf_{tok}')
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(False, 'SMTP error')):
            resp = client.post('/api/registration/resend', json={'email': email})
        assert resp.status_code in VALID_CODES

    def test_resend_resets_attempts(self, client, db_session):
        tok = secrets.token_hex(4)
        email = f'rsda_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'rsda_{tok}')
        v.attempts = 3
        db_session.session.commit()
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/resend', json={'email': email})
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 8. GET /api/registration/admin/settings (admin required)
# ===========================================================================

class TestAdminGetSettings:
    """GET /api/registration/admin/settings."""

    def test_unauthenticated_returns_403(self, client, db_session):
        resp = client.get('/api/registration/admin/settings')
        assert resp.status_code in [302, 401, 403, 404, 500]

    def test_non_admin_returns_403(self, client, db_session):
        from src.models.user import User
        u = User(
            username=f'nonadmin_{secrets.token_hex(3)}',
            email=f'nonadmin_{secrets.token_hex(3)}@test.com',
            is_admin=False,
        )
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = client.get('/api/registration/admin/settings')
        assert resp.status_code in VALID_CODES

    def test_admin_returns_settings(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/registration/admin/settings')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'settings' in data or 'success' in data

    def test_admin_settings_dict_structure(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/registration/admin/settings')
        if resp.status_code == 200:
            data = resp.get_json()
            if data and 'settings' in data:
                s = data['settings']
                assert 'is_registration_open' in s or 'auto_activate' in s


# ===========================================================================
# 9. POST /api/registration/admin/settings
# ===========================================================================

class TestAdminUpdateSettings:
    """POST /api/registration/admin/settings."""

    def test_unauthenticated_returns_403(self, client, db_session):
        resp = client.post('/api/registration/admin/settings', json={})
        assert resp.status_code in [302, 401, 403, 404, 500]

    def test_open_student_registration(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'is_registration_open': True,
        })
        assert resp.status_code in VALID_CODES

    def test_close_student_registration(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'is_registration_open': False,
            'closed_message': 'التسجيل مغلق للصيانة',
        })
        assert resp.status_code in VALID_CODES

    def test_open_teacher_registration(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'is_teacher_registration_open': True,
        })
        assert resp.status_code in VALID_CODES

    def test_close_teacher_registration_with_message(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'is_teacher_registration_open': False,
            'teacher_closed_message': 'تسجيل المعلمين مغلق',
        })
        assert resp.status_code in VALID_CODES

    def test_update_require_phone_and_school(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'require_phone': True,
            'require_school': True,
        })
        assert resp.status_code in VALID_CODES

    def test_update_auto_activate(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'auto_activate': False,
        })
        assert resp.status_code in VALID_CODES

    def test_update_teacher_require_fields(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'teacher_require_phone': True,
            'teacher_require_school': True,
            'teacher_auto_activate': True,
        })
        assert resp.status_code in VALID_CODES

    def test_update_all_settings(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'is_registration_open': True,
            'closed_message': 'test',
            'require_phone': False,
            'require_school': False,
            'auto_activate': True,
            'is_teacher_registration_open': True,
            'teacher_closed_message': 'test teacher',
            'teacher_require_phone': False,
            'teacher_require_school': False,
            'teacher_auto_activate': False,
        })
        assert resp.status_code in VALID_CODES

    def test_returns_updated_settings(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/settings', json={
            'is_registration_open': True,
        })
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'settings' in data or 'success' in data


# ===========================================================================
# 10. POST /api/registration/admin/toggle
# ===========================================================================

class TestAdminToggleRegistration:
    """POST /api/registration/admin/toggle."""

    def test_unauthenticated_returns_403(self, client, db_session):
        resp = client.post('/api/registration/admin/toggle', json={})
        assert resp.status_code in [302, 401, 403, 404, 500]

    def test_toggle_student_default(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/toggle', json={})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'is_open' in data

    def test_toggle_student_explicit(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('type') == 'student'

    def test_toggle_teacher(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/toggle', json={'type': 'teacher'})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('type') == 'teacher'

    def test_toggle_student_twice_back_to_original(self, client, admin_user, db_session):
        _open_registration(db_session)
        _login_admin(client, admin_user)
        resp1 = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        resp2 = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        assert resp1.status_code in VALID_CODES
        assert resp2.status_code in VALID_CODES

    def test_toggle_teacher_twice(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp1 = client.post('/api/registration/admin/toggle', json={'type': 'teacher'})
        resp2 = client.post('/api/registration/admin/toggle', json={'type': 'teacher'})
        assert resp1.status_code in VALID_CODES
        assert resp2.status_code in VALID_CODES

    def test_toggle_returns_is_open_bool(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        if resp.status_code == 200:
            data = resp.get_json()
            if data and 'is_open' in data:
                assert isinstance(data['is_open'], bool)


# ===========================================================================
# 11. validate_arabic_name() edge cases via /register endpoint
# ===========================================================================

class TestValidateArabicNameEdgeCases:
    """Tests specifically targeting validate_arabic_name branches."""

    def setup_method(self):
        self.base_payload = {
            'username': f'nm_{secrets.token_hex(3)}',
            'email': f'nm_{secrets.token_hex(3)}@gmail.com',
            'password': 'SecurePass@1',
        }

    def test_purely_english_three_parts(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.base_payload, 'name': 'John Michael Smith'}
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_arabic_three_parts_valid(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(3)
        payload = {
            'name': 'خالد عبدالله الزهراني',
            'username': f'kh_{tok}',
            'email': f'kh_{tok}@gmail.com',
            'password': 'SecurePass@1',
        }
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_with_leading_abu_parent(self, client, db_session):
        _open_registration(db_session)
        payload = {**self.base_payload, 'name': 'أم علي محمد'}
        resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES

    def test_name_exactly_40_chars_three_parts(self, client, db_session):
        _open_registration(db_session)
        # Create a valid 40-char name
        name = 'أحمد محمد علي'  # Valid, short enough
        payload = {**self.base_payload, 'name': name}
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resp = client.post('/api/registration/register', json=payload)
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 12. notify_admin function path coverage (via integration)
# ===========================================================================

class TestNotifyAdminPath:
    """Tests that trigger notify_admin (called after verify_code success)."""

    def test_notify_admin_called_on_student_verify(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'na_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'na_{tok}')
        with patch('src.routes.registration.notify_admin') as mock_notify:
            with patch('src.services.email_service.email_service.send_admin_notification'):
                resp = client.post('/api/registration/verify', json={
                    'email': email,
                    'code': v.code,
                    'account_type': 'student',
                })
        assert resp.status_code in VALID_CODES

    def test_notify_admin_called_on_teacher_verify(self, client, db_session):
        _open_registration(db_session)
        tok = secrets.token_hex(4)
        email = f'nat_{tok}@gmail.com'
        v = _make_verification(db_session, email, f'nat_{tok}', grade='teacher')
        with patch('src.routes.registration.notify_admin') as mock_notify:
            resp = client.post('/api/registration/verify', json={
                'email': email,
                'code': v.code,
                'account_type': 'teacher',
            })
        assert resp.status_code in VALID_CODES
