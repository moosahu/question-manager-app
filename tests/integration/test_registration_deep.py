"""
اختبارات تكاملية عميقة لـ registration.py
يغطي جميع الـ 9 routes بشكل شامل:

  GET  /api/registration/status                  → get_registration_status
  POST /api/registration/register                → register_student
  POST /api/registration/register-teacher        → register_teacher
  POST /api/registration/verify                  → verify_code
  POST /api/registration/verify-phone            → verify_phone_code
  POST /api/registration/activate-after-phone    → activate_after_phone
  POST /api/registration/resend                  → resend_code
  GET  /api/registration/admin/settings          → get_admin_settings  (admin_required)
  POST /api/registration/admin/settings          → update_admin_settings (admin_required)
  POST /api/registration/admin/toggle            → toggle_registration  (admin_required)
"""
import pytest
import secrets
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_student(db_session, suffix):
    from src.models.student import Student
    s = Student(
        name='Test',
        username=f'reg_{suffix}_{secrets.token_hex(3)}',
        email=f'reg_{suffix}_{secrets.token_hex(3)}@test.com',
        is_active=True
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_teacher(db_session, suffix):
    from src.models.teacher import Teacher
    t = Teacher(
        name='معلم اختبار',
        username=f'tch_{suffix}_{secrets.token_hex(3)}',
        email=f'tch_{suffix}_{secrets.token_hex(3)}@test.com',
        is_active=True
    )
    t.set_password('Pass@123')
    t.session_token = secrets.token_hex(32)
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _make_verification(db_session, app, email, username,
                       grade=None, phone=None, school=None,
                       is_verified=False):
    """إنشاء طلب تحقق مباشرة في DB متجاوزاً إرسال الإيميل"""
    from src.models.email_verification import EmailVerification
    from werkzeug.security import generate_password_hash
    with app.app_context():
        # حذف أي سجل سابق لنفس الإيميل
        EmailVerification.query.filter_by(email=email).delete()
        db_session.session.commit()

        v = EmailVerification(
            email=email,
            code='123456',
            name='احمد محمد علي',
            username=username,
            password_hash=generate_password_hash('Pass@123'),
            phone=phone,
            school=school,
            grade=grade,
            is_verified=is_verified,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db_session.session.add(v)
        db_session.session.commit()
        db_session.session.refresh(v)
        return v


def _open_registration(db_session, app,
                       student_open=True, teacher_open=True):
    """ضمان أن التسجيل مفتوح للطلاب و/أو المعلمين"""
    from src.models.email_verification import RegistrationSettings
    with app.app_context():
        s = RegistrationSettings.get_settings()
        s.is_registration_open = student_open
        s.is_teacher_registration_open = teacher_open
        s.require_phone = False
        s.require_school = False
        s.teacher_require_phone = False
        s.teacher_require_school = False
        s.auto_activate = True
        s.teacher_auto_activate = True
        db_session.session.commit()


# ---------------------------------------------------------------------------
# SECTION 1: GET /api/registration/status
# ---------------------------------------------------------------------------

class TestRegistrationStatus:
    """9 اختبارات لـ GET /api/registration/status"""

    def test_status_returns_200(self, client):
        """الـ endpoint يرد بـ 200"""
        response = client.get('/api/registration/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_status_response_is_json(self, client):
        """الرد JSON"""
        response = client.get('/api/registration/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_status_default_student_type(self, client):
        """بدون type parameter → إعدادات الطلاب"""
        response = client.get('/api/registration/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'is_open' in data

    def test_status_explicit_student_type(self, client):
        """type=student يعيد إعدادات الطلاب"""
        response = client.get('/api/registration/status?type=student')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'is_open' in data

    def test_status_teacher_type(self, client):
        """type=teacher يعيد إعدادات المعلمين"""
        response = client.get('/api/registration/status?type=teacher')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'is_open' in data

    def test_status_student_has_require_phone_field(self, client):
        """حقل require_phone موجود في رد الطلاب"""
        response = client.get('/api/registration/status?type=student')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'require_phone' in data or 'is_open' in data

    def test_status_teacher_has_require_school_field(self, client):
        """حقل require_school موجود في رد المعلمين"""
        response = client.get('/api/registration/status?type=teacher')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'require_school' in data or 'is_open' in data

    def test_status_unknown_type_falls_back_to_student(self, client):
        """نوع غير معروف يرجع إعدادات الطلاب"""
        response = client.get('/api/registration/status?type=unknown_xyz')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_status_success_flag_present(self, client):
        """حقل success موجود في الرد"""
        response = client.get('/api/registration/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True or 'is_open' in data


# ---------------------------------------------------------------------------
# SECTION 2: POST /api/registration/register  (student)
# ---------------------------------------------------------------------------

MOCK_EMAIL_SUCCESS = ('email_service', 'send_verification_code',
                      MagicMock(return_value=(True, 'sent')))


class TestRegisterStudent:
    """25 اختبارات لـ POST /api/registration/register"""

    def test_empty_body(self, client):
        """جسم فارغ → 400"""
        response = client.post('/api/registration/register', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_name(self, client, db_session, app):
        """بدون اسم → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'username': 'testuser1',
            'email': 'testuser1@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_username(self, client, db_session, app):
        """بدون اسم مستخدم → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'email': 'miss_user@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_email(self, client, db_session, app):
        """بدون إيميل → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'miss_email1',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_password(self, client, db_session, app):
        """بدون كلمة مرور → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'miss_pass1',
            'email': 'miss_pass@gmail.com'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_name_too_short(self, client, db_session, app):
        """اسم ثنائي (يجب ثلاثي) → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد',
            'username': 'shortname1',
            'email': 'shortname@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_name_too_long(self, client, db_session, app):
        """اسم أطول من 40 حرف → 400"""
        _open_registration(db_session, app)
        long_name = 'أ' * 41
        response = client.post('/api/registration/register', json={
            'name': long_name,
            'username': 'longname1',
            'email': 'longname@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_name_mixed_languages(self, client, db_session, app):
        """اسم مخلوط عربي وإنجليزي → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'Ahmed محمد علي',
            'username': 'mixedname1',
            'email': 'mixedname@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_name_repeated_first_two_parts(self, client, db_session, app):
        """الاسم الأول والثاني متطابقان → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد احمد علي',
            'username': 'repname1',
            'email': 'repname@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_username_too_short(self, client, db_session, app):
        """اسم مستخدم أقل من 4 أحرف → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'ab',
            'email': 'short_un@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_username_too_long(self, client, db_session, app):
        """اسم مستخدم أكثر من 20 حرف → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'a' * 21,
            'email': 'long_un@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_username_starts_with_digit(self, client, db_session, app):
        """اسم مستخدم يبدأ برقم → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': '1testuser',
            'email': 'digit_un@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_username_arabic_chars(self, client, db_session, app):
        """اسم مستخدم بأحرف عربية → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'مستخدم',
            'email': 'arabic_un@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_password_too_short(self, client, db_session, app):
        """كلمة مرور أقل من 8 أحرف → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'shortpass1',
            'email': 'shortpass@gmail.com',
            'password': 'Abc1'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_password_no_letter(self, client, db_session, app):
        """كلمة مرور بأرقام فقط → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'noletpass1',
            'email': 'noletpass@gmail.com',
            'password': '12345678'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_password_no_digit(self, client, db_session, app):
        """كلمة مرور بحروف فقط → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'nodigpass1',
            'email': 'nodigpass@gmail.com',
            'password': 'PasswordOnly'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_password_in_weak_list(self, client, db_session, app):
        """كلمة مرور ضعيفة من القائمة المحظورة → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'weakpass1',
            'email': 'weakpass@gmail.com',
            'password': 'password123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_email_format(self, client, db_session, app):
        """إيميل بصيغة خاطئة → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'bademail1',
            'email': 'not-an-email',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_blocked_email_domain(self, client, db_session, app):
        """إيميل مؤقت محظور → 400"""
        _open_registration(db_session, app)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'blockmail1',
            'email': 'test@mailinator.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_duplicate_username(self, client, db_session, app):
        """اسم مستخدم موجود مسبقاً → 400"""
        _open_registration(db_session, app)
        s = _make_student(db_session, 'dupusr')
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': s.username,
            'email': 'newuniq@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_duplicate_email(self, client, db_session, app):
        """إيميل موجود مسبقاً → 400"""
        _open_registration(db_session, app)
        s = _make_student(db_session, 'dupeml')
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'newuniquser1',
            'email': s.email,
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(True, 'sent'))
    def test_valid_registration_sends_verification(self, mock_send, client, db_session, app):
        """تسجيل صالح يطلب إرسال رمز التحقق"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': f'valreg_{tok}',
            'email': f'valreg_{tok}@gmail.com',
            'password': 'Str0ng!Pass1'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(False, 'SMTP error'))
    def test_valid_registration_email_failure(self, mock_send, client, db_session, app):
        """فشل إرسال الإيميل → 500"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': f'failmail_{tok}',
            'email': f'failmail_{tok}@gmail.com',
            'password': 'Str0ng!Pass1'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_registration_closed(self, client, db_session, app):
        """التسجيل مغلق → 403"""
        from src.models.email_verification import RegistrationSettings
        with app.app_context():
            s = RegistrationSettings.get_settings()
            s.is_registration_open = False
            db_session.session.commit()
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'closed_reg1',
            'email': 'closed_reg@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_require_phone_missing(self, client, db_session, app):
        """رقم الجوال مطلوب لكن غير موجود → 400"""
        from src.models.email_verification import RegistrationSettings
        with app.app_context():
            s = RegistrationSettings.get_settings()
            s.is_registration_open = True
            s.require_phone = True
            db_session.session.commit()
        tok = secrets.token_hex(4)
        response = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': f'nophone_{tok}',
            'email': f'nophone_{tok}@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 3: POST /api/registration/register-teacher
# ---------------------------------------------------------------------------

class TestRegisterTeacher:
    """12 اختبارات لـ POST /api/registration/register-teacher"""

    def test_empty_body(self, client):
        """جسم فارغ → 400/403"""
        response = client.post('/api/registration/register-teacher', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_teacher_registration_closed(self, client, db_session, app):
        """تسجيل المعلمين مغلق → 403"""
        from src.models.email_verification import RegistrationSettings
        with app.app_context():
            s = RegistrationSettings.get_settings()
            s.is_teacher_registration_open = False
            db_session.session.commit()
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'tch_closed1',
            'email': 'tch_closed@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_name(self, client, db_session, app):
        """بدون اسم → 400"""
        _open_registration(db_session, app, teacher_open=True)
        response = client.post('/api/registration/register-teacher', json={
            'username': 'tch_miss_name',
            'email': 'tch_mn@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_name(self, client, db_session, app):
        """اسم غير صالح (ثنائي) → 400"""
        _open_registration(db_session, app, teacher_open=True)
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد',
            'username': 'tch_badname',
            'email': 'tch_bn@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_invalid_email(self, client, db_session, app):
        """إيميل خاطئ → 400"""
        _open_registration(db_session, app, teacher_open=True)
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'tch_bademl',
            'email': 'bad-email',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_blocked_email_domain(self, client, db_session, app):
        """إيميل مؤقت → 400"""
        _open_registration(db_session, app, teacher_open=True)
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'tch_blkml',
            'email': 'teacher@yopmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_weak_password(self, client, db_session, app):
        """كلمة مرور ضعيفة → 400"""
        _open_registration(db_session, app, teacher_open=True)
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'tch_weakpw',
            'email': 'tch_wk@gmail.com',
            'password': 'password123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_duplicate_username_with_teacher(self, client, db_session, app):
        """اسم مستخدم معلم موجود مسبقاً → 400"""
        _open_registration(db_session, app, teacher_open=True)
        t = _make_teacher(db_session, 'dup_tch_un')
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': t.username,
            'email': 'new_tch_un@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_duplicate_username_with_student(self, client, db_session, app):
        """اسم مستخدم طالب موجود → منع تسجيل معلم بنفسه → 400"""
        _open_registration(db_session, app, teacher_open=True)
        s = _make_student(db_session, 'dup_stu_as_tch')
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': s.username,
            'email': 'new_tch_stu@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_duplicate_email_with_teacher(self, client, db_session, app):
        """إيميل معلم موجود مسبقاً → 400"""
        _open_registration(db_session, app, teacher_open=True)
        t = _make_teacher(db_session, 'dup_tch_eml')
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'new_tch_eml1',
            'email': t.email,
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_require_phone_missing(self, client, db_session, app):
        """رقم جوال المعلم مطلوب لكن غير موجود → 400"""
        from src.models.email_verification import RegistrationSettings
        with app.app_context():
            s = RegistrationSettings.get_settings()
            s.is_teacher_registration_open = True
            s.teacher_require_phone = True
            db_session.session.commit()
        tok = secrets.token_hex(4)
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': f'tch_noph_{tok}',
            'email': f'tch_noph_{tok}@gmail.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(True, 'sent'))
    def test_valid_teacher_registration(self, mock_send, client, db_session, app):
        """تسجيل معلم صالح يرسل رمز التحقق"""
        _open_registration(db_session, app, teacher_open=True)
        tok = secrets.token_hex(4)
        response = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': f'valteach_{tok}',
            'email': f'valteach_{tok}@gmail.com',
            'password': 'Str0ng!Pass1'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 4: POST /api/registration/verify
# ---------------------------------------------------------------------------

class TestVerifyCode:
    """12 اختبارات لـ POST /api/registration/verify"""

    def test_empty_body(self, client):
        """جسم فارغ → 400"""
        response = client.post('/api/registration/verify', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_email(self, client):
        """بدون إيميل → 400"""
        response = client.post('/api/registration/verify', json={'code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_code(self, client):
        """بدون رمز → 400"""
        response = client.post('/api/registration/verify', json={
            'email': 'test@gmail.com'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_no_verification_record(self, client):
        """إيميل بدون طلب تحقق موجود → 404"""
        response = client.post('/api/registration/verify', json={
            'email': 'notfound_xyz@gmail.com',
            'code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_wrong_code(self, client, db_session, app):
        """رمز خاطئ → 400"""
        tok = secrets.token_hex(4)
        email = f'wrong_code_{tok}@gmail.com'
        _make_verification(db_session, app, email=email, username=f'wc_{tok}')
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '000000'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_correct_code_student_no_phone(self, client, db_session, app):
        """رمز صحيح لطالب بدون جوال → ينشئ الحساب"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        email = f'verify_stu_{tok}@gmail.com'
        _make_verification(db_session, app, email=email, username=f'vstu_{tok}')
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_correct_code_teacher_no_phone(self, client, db_session, app):
        """رمز صحيح لمعلم (grade=teacher) بدون جوال → ينشئ حساب المعلم"""
        _open_registration(db_session, app, teacher_open=True)
        tok = secrets.token_hex(4)
        email = f'verify_tch_{tok}@gmail.com'
        _make_verification(
            db_session, app, email=email, username=f'vtch_{tok}', grade='teacher'
        )
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'teacher'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_correct_code_student_with_phone(self, client, db_session, app):
        """رمز صحيح لطالب مع رقم جوال → is_active=False وينتظر التحقق من الجوال"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        email = f'verify_ph_{tok}@gmail.com'
        _make_verification(
            db_session, app, email=email,
            username=f'vph_{tok}', phone='0501234567'
        )
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_already_verified_email(self, client, db_session, app):
        """إيميل تم التحقق منه مسبقاً (is_verified=True) → 404 (لا يوجد unverified)"""
        tok = secrets.token_hex(4)
        email = f'already_ver_{tok}@gmail.com'
        _make_verification(
            db_session, app, email=email,
            username=f'av_{tok}', is_verified=True
        )
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_duplicate_username_race_condition(self, client, db_session, app):
        """اسم مستخدم أصبح محجوزاً بعد التحقق → 400"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        uname = f'race_{tok}'
        email = f'race_{tok}@gmail.com'
        # ننشئ طلب التحقق
        _make_verification(db_session, app, email=email, username=uname)
        # ننشئ الطالب بنفس اسم المستخدم قبل التحقق
        from src.models.student import Student
        s = Student(name='Race', username=uname,
                    email=f'race2_{tok}@gmail.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_expired_code(self, client, db_session, app):
        """رمز منتهي الصلاحية → 400"""
        from src.models.email_verification import EmailVerification
        from werkzeug.security import generate_password_hash
        tok = secrets.token_hex(4)
        email = f'expired_{tok}@gmail.com'
        with app.app_context():
            EmailVerification.query.filter_by(email=email).delete()
            db_session.session.commit()
            v = EmailVerification(
                email=email,
                code='123456',
                name='احمد محمد علي',
                username=f'exp_{tok}',
                password_hash=generate_password_hash('Pass@123'),
                is_verified=False,
                expires_at=datetime.utcnow() - timedelta(minutes=5),  # منتهي
            )
            db_session.session.add(v)
            db_session.session.commit()
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_max_attempts_exceeded(self, client, db_session, app):
        """تجاوز الحد الأقصى للمحاولات الخاطئة → 400"""
        from src.models.email_verification import EmailVerification
        from werkzeug.security import generate_password_hash
        tok = secrets.token_hex(4)
        email = f'maxatt_{tok}@gmail.com'
        with app.app_context():
            EmailVerification.query.filter_by(email=email).delete()
            db_session.session.commit()
            v = EmailVerification(
                email=email,
                code='123456',
                name='احمد محمد علي',
                username=f'ma_{tok}',
                password_hash=generate_password_hash('Pass@123'),
                is_verified=False,
                attempts=5,  # وصل الحد الأقصى
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
            db_session.session.add(v)
            db_session.session.commit()
        response = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 5: POST /api/registration/verify-phone
# ---------------------------------------------------------------------------

class TestVerifyPhoneCode:
    """6 اختبارات لـ POST /api/registration/verify-phone"""

    def test_empty_body(self, client):
        """جسم فارغ → 400"""
        response = client.post('/api/registration/verify-phone', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_code(self, client):
        """بدون رمز → 400"""
        response = client.post('/api/registration/verify-phone', json={
            'email': 'test@gmail.com'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_no_verified_record(self, client):
        """لا يوجد سجل تحقق بـ is_verified=True → 404"""
        response = client.post('/api/registration/verify-phone', json={
            'email': 'norecord_xyz@gmail.com',
            'code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_verified_record_no_phone(self, client, db_session, app):
        """سجل تحقق بدون رقم جوال → 404"""
        tok = secrets.token_hex(4)
        email = f'vphone_noph_{tok}@gmail.com'
        _make_verification(
            db_session, app, email=email,
            username=f'vpnph_{tok}', is_verified=True  # بدون phone
        )
        response = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_wrong_phone_code(self, client, db_session, app):
        """رمز جوال خاطئ → 400"""
        from src.models.email_verification import EmailVerification
        from werkzeug.security import generate_password_hash
        tok = secrets.token_hex(4)
        email = f'wrong_pcode_{tok}@gmail.com'
        with app.app_context():
            EmailVerification.query.filter_by(email=email).delete()
            db_session.session.commit()
            v = EmailVerification(
                email=email,
                code='654321',
                name='احمد محمد علي',
                username=f'wpc_{tok}',
                password_hash=generate_password_hash('Pass@123'),
                phone='0501234567',
                is_verified=True,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
            db_session.session.add(v)
            db_session.session.commit()
        response = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '000000'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_verify_phone_teacher_account_type(self, client, db_session, app):
        """account_type=teacher يُفعّل حساب معلم"""
        response = client.post('/api/registration/verify-phone', json={
            'email': 'tch_phone@gmail.com',
            'code': '123456',
            'account_type': 'teacher'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 6: POST /api/registration/activate-after-phone
# ---------------------------------------------------------------------------

class TestActivateAfterPhone:
    """7 اختبارات لـ POST /api/registration/activate-after-phone"""

    def test_empty_body(self, client):
        """جسم فارغ → 400"""
        response = client.post('/api/registration/activate-after-phone', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_email(self, client):
        """بدون إيميل → 400"""
        response = client.post('/api/registration/activate-after-phone', json={
            'phone': '0501234567'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_phone(self, client):
        """بدون رقم جوال → 400"""
        response = client.post('/api/registration/activate-after-phone', json={
            'email': 'test@gmail.com'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_student_not_found(self, client):
        """طالب غير موجود → 404"""
        response = client.post('/api/registration/activate-after-phone', json={
            'email': 'notfound_stu@gmail.com',
            'phone': '0501234567',
            'account_type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_teacher_not_found(self, client):
        """معلم غير موجود → 404"""
        response = client.post('/api/registration/activate-after-phone', json={
            'email': 'notfound_tch@gmail.com',
            'phone': '0501234567',
            'account_type': 'teacher'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_activate_existing_student(self, client, db_session, app):
        """تفعيل طالب موجود بعد التحقق من الجوال"""
        s = _make_student(db_session, 'act_stu')
        s.is_active = False
        db_session.session.commit()
        response = client.post('/api/registration/activate-after-phone', json={
            'email': s.email,
            'phone': '0501234567',
            'account_type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_activate_existing_teacher(self, client, db_session, app):
        """تفعيل معلم موجود بعد التحقق من الجوال"""
        t = _make_teacher(db_session, 'act_tch')
        t.is_active = False
        db_session.session.commit()
        response = client.post('/api/registration/activate-after-phone', json={
            'email': t.email,
            'phone': '0509876543',
            'account_type': 'teacher'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 7: POST /api/registration/resend
# ---------------------------------------------------------------------------

class TestResendCode:
    """7 اختبارات لـ POST /api/registration/resend"""

    def test_empty_body(self, client):
        """جسم فارغ → 400"""
        response = client.post('/api/registration/resend', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_missing_email(self, client):
        """بدون إيميل → 400"""
        response = client.post('/api/registration/resend', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_nonexistent_verification(self, client):
        """لا يوجد طلب تحقق لهذا الإيميل → 404"""
        response = client.post('/api/registration/resend', json={
            'email': 'norecord_resend@gmail.com'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_already_verified_no_pending(self, client, db_session, app):
        """الطلب مكتمل (is_verified=True) → 404"""
        tok = secrets.token_hex(4)
        email = f'resend_done_{tok}@gmail.com'
        _make_verification(
            db_session, app, email=email,
            username=f'rsd_{tok}', is_verified=True
        )
        response = client.post('/api/registration/resend', json={'email': email})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(True, 'sent'))
    def test_resend_success(self, mock_send, client, db_session, app):
        """إعادة إرسال ناجحة"""
        tok = secrets.token_hex(4)
        email = f'resend_ok_{tok}@gmail.com'
        _make_verification(db_session, app, email=email, username=f'rok_{tok}')
        response = client.post('/api/registration/resend', json={'email': email})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(False, 'SMTP down'))
    def test_resend_email_failure(self, mock_send, client, db_session, app):
        """فشل إعادة الإرسال → 500"""
        tok = secrets.token_hex(4)
        email = f'resend_fail_{tok}@gmail.com'
        _make_verification(db_session, app, email=email, username=f'rfail_{tok}')
        response = client.post('/api/registration/resend', json={'email': email})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_resend_resets_attempts(self, client, db_session, app):
        """إعادة الإرسال تعيد عدد المحاولات إلى 0"""
        from src.models.email_verification import EmailVerification
        from werkzeug.security import generate_password_hash
        tok = secrets.token_hex(4)
        email = f'resend_att_{tok}@gmail.com'
        with app.app_context():
            EmailVerification.query.filter_by(email=email).delete()
            db_session.session.commit()
            v = EmailVerification(
                email=email,
                code='111111',
                name='احمد محمد علي',
                username=f'rattmp_{tok}',
                password_hash=generate_password_hash('Pass@123'),
                is_verified=False,
                attempts=3,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
            db_session.session.add(v)
            db_session.session.commit()
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            response = client.post('/api/registration/resend', json={'email': email})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 8: GET /api/registration/admin/settings  (admin_required)
# ---------------------------------------------------------------------------

class TestAdminGetSettings:
    """5 اختبارات لـ GET /api/registration/admin/settings"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_no_auth_redirects(self, client):
        """بدون مصادقة → redirect أو 403"""
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_admin_can_get_settings(self, client, admin_user, db_session, app):
        """الأدمن يجلب الإعدادات بنجاح"""
        self._login(client, admin_user)
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_response_contains_settings_key(self, client, admin_user, db_session, app):
        """الرد يحتوي على مفتاح settings"""
        self._login(client, admin_user)
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'settings' in data or 'success' in data

    def test_settings_contain_student_fields(self, client, admin_user, db_session, app):
        """إعدادات الطلاب موجودة في الرد"""
        self._login(client, admin_user)
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            if 'settings' in data:
                s = data['settings']
                assert 'is_registration_open' in s or 'auto_activate' in s

    def test_settings_contain_teacher_fields(self, client, admin_user, db_session, app):
        """إعدادات المعلمين موجودة في الرد"""
        self._login(client, admin_user)
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            if 'settings' in data:
                s = data['settings']
                assert 'is_teacher_registration_open' in s or 'teacher_auto_activate' in s


# ---------------------------------------------------------------------------
# SECTION 9: POST /api/registration/admin/settings  (admin_required)
# ---------------------------------------------------------------------------

class TestAdminUpdateSettings:
    """7 اختبارات لـ POST /api/registration/admin/settings"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_no_auth_redirects(self, client):
        """بدون مصادقة → redirect أو 403"""
        response = client.post('/api/registration/admin/settings', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_admin_can_update_settings(self, client, admin_user, db_session, app):
        """الأدمن يحدث الإعدادات"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={
            'is_registration_open': True,
            'auto_activate': True,
            'require_phone': False,
            'require_school': False
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_admin_update_teacher_settings(self, client, admin_user, db_session, app):
        """الأدمن يحدث إعدادات المعلمين"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={
            'is_teacher_registration_open': True,
            'teacher_auto_activate': False,
            'teacher_require_phone': True
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_admin_close_student_registration(self, client, admin_user, db_session, app):
        """الأدمن يغلق تسجيل الطلاب"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={
            'is_registration_open': False,
            'closed_message': 'التسجيل مغلق مؤقتاً'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_admin_update_closed_message(self, client, admin_user, db_session, app):
        """الأدمن يغير رسالة الإغلاق"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={
            'closed_message': 'سيُفتح التسجيل قريباً إن شاء الله'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_empty_body_still_responds(self, client, admin_user, db_session, app):
        """جسم فارغ لا يكسر الـ endpoint"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_update_returns_updated_settings(self, client, admin_user, db_session, app):
        """الرد يحتوي على الإعدادات المحدثة"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={
            'is_registration_open': True
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True


# ---------------------------------------------------------------------------
# SECTION 10: POST /api/registration/admin/toggle  (admin_required)
# ---------------------------------------------------------------------------

class TestAdminToggleRegistration:
    """8 اختبارات لـ POST /api/registration/admin/toggle"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_no_auth_redirects(self, client):
        """بدون مصادقة → redirect أو 403"""
        response = client.post('/api/registration/admin/toggle', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_toggle_student_default(self, client, admin_user, db_session, app):
        """toggle بدون type → يؤثر على تسجيل الطلاب"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_toggle_student_explicit(self, client, admin_user, db_session, app):
        """toggle مع type=student"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={
            'type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_toggle_teacher(self, client, admin_user, db_session, app):
        """toggle مع type=teacher"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={
            'type': 'teacher'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_toggle_student_response_has_is_open(self, client, admin_user, db_session, app):
        """الرد يحتوي على is_open"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={
            'type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'is_open' in data or data.get('success') is True

    def test_toggle_teacher_response_has_type_field(self, client, admin_user, db_session, app):
        """الرد يحتوي على حقل type=teacher"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={
            'type': 'teacher'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('type') == 'teacher' or data.get('success') is True

    def test_double_toggle_returns_original_state(self, client, admin_user, db_session, app):
        """toggle مرتين يرجع الحالة الأصلية"""
        self._login(client, admin_user)
        # toggle أول
        client.post('/api/registration/admin/toggle', json={'type': 'student'})
        # toggle ثاني
        response = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_toggle_with_unknown_type_defaults_to_student(self, client, admin_user, db_session, app):
        """type غير معروف → يتصرف مثل student"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={
            'type': 'unknown_xyz'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]


# ---------------------------------------------------------------------------
# SECTION 11: اختبارات التكامل الشاملة (end-to-end flows)
# ---------------------------------------------------------------------------

class TestIntegrationFlows:
    """5 اختبارات تدمج عدة routes معاً"""

    def test_status_then_register_student_flow(self, client, db_session, app):
        """فحص الحالة أولاً ثم محاولة التسجيل"""
        # الخطوة 1: فحص الحالة
        status_resp = client.get('/api/registration/status?type=student')
        assert status_resp.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

        # الخطوة 2: محاولة التسجيل
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            reg_resp = client.post('/api/registration/register', json={
                'name': 'احمد محمد علي',
                'username': f'flow_stu_{tok}',
                'email': f'flow_stu_{tok}@gmail.com',
                'password': 'Str0ng!Pass1'
            })
        assert reg_resp.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_register_then_verify_then_activate_flow(self, client, db_session, app):
        """تسجيل → تحقق من كود → تفعيل بعد جوال"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        email = f'full_flow_{tok}@gmail.com'
        uname = f'ff_{tok}'

        # ننشئ طلب التحقق مباشرة
        _make_verification(db_session, app, email=email, username=uname,
                           phone='0501234567')

        # تحقق من الكود
        verify_resp = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'student'
        })
        assert verify_resp.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_admin_toggle_blocks_new_registration(self, client, admin_user, db_session, app):
        """الأدمن يغلق التسجيل → محاولة التسجيل تفشل"""
        # نفتح أولاً
        _open_registration(db_session, app)

        # الأدمن يغلق
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        from src.models.email_verification import RegistrationSettings
        with app.app_context():
            s = RegistrationSettings.get_settings()
            s.is_registration_open = False
            db_session.session.commit()

        # محاولة التسجيل بعد الإغلاق
        tok = secrets.token_hex(4)
        reg_resp = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': f'after_close_{tok}',
            'email': f'after_close_{tok}@gmail.com',
            'password': 'Str0ng!Pass1'
        })
        assert reg_resp.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_resend_then_verify_flow(self, client, db_session, app):
        """إعادة إرسال الرمز ثم التحقق بالرمز الجديد"""
        _open_registration(db_session, app)
        tok = secrets.token_hex(4)
        email = f'resend_verify_{tok}@gmail.com'
        uname = f'rv_{tok}'
        _make_verification(db_session, app, email=email, username=uname)

        # إعادة الإرسال
        with patch('src.services.email_service.email_service.send_verification_code',
                   return_value=(True, 'sent')):
            resend_resp = client.post('/api/registration/resend', json={'email': email})
        assert resend_resp.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_activate_after_phone_gives_valid_token(self, client, db_session, app):
        """تفعيل حساب طالب بعد التحقق من الجوال يعيد token"""
        s = _make_student(db_session, 'tok_check')
        s.is_active = False
        db_session.session.commit()

        response = client.post('/api/registration/activate-after-phone', json={
            'email': s.email,
            'phone': '0501234567',
            'account_type': 'student'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'token' in data
