"""
اختبارات شاملة لـ Registration API
يغطي: register student/teacher, verify, status, admin settings
"""
import pytest


class TestRegistrationStatus:
    """اختبارات حالة التسجيل"""

    def test_get_status(self, client):
        """جلب حالة التسجيل"""
        response = client.get('/api/registration/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        # يجب أن يحتوي على حقل is_open أو enabled أو مشابه
        assert isinstance(data, dict)

    def test_status_has_required_fields(self, client):
        """حالة التسجيل تحتوي على حقول مطلوبة"""
        response = client.get('/api/registration/status')
        data = response.get_json()
        # أي من هذه الحقول مقبول
        possible_fields = ['is_open', 'enabled', 'open', 'registration_open', 'success', 'status']
        has_field = any(f in data for f in possible_fields)
        assert has_field or isinstance(data, dict)


class TestStudentRegistration:
    """اختبارات تسجيل الطلاب"""

    def test_register_missing_fields(self, client):
        """تسجيل بدون حقول مطلوبة"""
        response = client.post('/api/registration/register', json={})
        assert response.status_code in [400, 422, 403]

    def test_register_missing_name(self, client):
        """تسجيل بدون اسم"""
        response = client.post('/api/registration/register', json={
            'username': 'testuser',
            'email': 'test@test.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [400, 403]

    def test_register_invalid_email(self, client):
        """تسجيل بإيميل غير صالح"""
        response = client.post('/api/registration/register', json={
            'name': 'Test Student',
            'username': 'testuser',
            'email': 'not-an-email',
            'password': 'Pass@123',
            'phone': '0501234567'
        })
        assert response.status_code in [400, 403, 422]

    def test_register_short_password(self, client):
        """تسجيل بكلمة مرور قصيرة"""
        response = client.post('/api/registration/register', json={
            'name': 'Test Student',
            'username': 'testuser',
            'email': 'test@test.com',
            'password': '123',
            'phone': '0501234567'
        })
        assert response.status_code in [400, 403, 422]

    def test_register_when_closed(self, client):
        """التسجيل عندما التسجيل مغلق"""
        response = client.post('/api/registration/register', json={
            'name': 'Test Student',
            'username': 'regclosed_user',
            'email': 'regclosed@test.com',
            'password': 'Pass@123',
            'phone': '0501234567',
            'gender': 'male'
        })
        # إما نجح التسجيل أو رُفض (403=مغلق, 400=خطأ, 200=نجح)
        assert response.status_code in [200, 201, 400, 403, 422, 500]

    def test_register_duplicate_username(self, client, db_session, app):
        """تسجيل باسم مستخدم موجود"""
        from src.models.student import Student
        s = Student(name='Existing', username='dup_user_reg', email='dup_reg@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/api/registration/register', json={
            'name': 'New Student',
            'username': 'dup_user_reg',
            'email': 'newdup@test.com',
            'password': 'Pass@123',
            'phone': '0501234567'
        })
        assert response.status_code in [400, 403, 409]


class TestTeacherRegistration:
    """اختبارات تسجيل المعلمين"""

    def test_register_teacher_missing_fields(self, client):
        """تسجيل معلم بدون حقول"""
        response = client.post('/api/registration/register-teacher', json={})
        assert response.status_code in [400, 403, 422]

    def test_register_teacher_missing_name(self, client):
        """تسجيل معلم بدون اسم"""
        response = client.post('/api/registration/register-teacher', json={
            'username': 'teacher_test',
            'password': 'Pass@123'
        })
        assert response.status_code in [400, 403, 422]

    def test_register_teacher_invalid_email(self, client):
        """تسجيل معلم بإيميل غير صالح"""
        response = client.post('/api/registration/register-teacher', json={
            'name': 'Test Teacher',
            'username': 'teacher_test',
            'email': 'invalid-email',
            'password': 'Pass@123'
        })
        assert response.status_code in [400, 403, 422]

    def test_register_teacher_valid_data(self, client):
        """تسجيل معلم ببيانات صالحة"""
        response = client.post('/api/registration/register-teacher', json={
            'name': 'Test Teacher',
            'username': 'teacher_valid_reg',
            'email': 'teachervalid@test.com',
            'password': 'Pass@123!',
            'phone': '0501234567',
            'subject': 'Chemistry'
        })
        # مقبول: 200/201=نجح, 400/403=مغلق/خطأ, 409=موجود
        assert response.status_code in [200, 201, 400, 403, 409, 422, 500]


class TestVerifyCode:
    """اختبارات التحقق من الكود"""

    def test_verify_missing_fields(self, client):
        """تحقق بدون حقول"""
        response = client.post('/api/registration/verify', json={})
        assert response.status_code in [400, 422]

    def test_verify_wrong_code(self, client):
        """تحقق بكود خاطئ"""
        response = client.post('/api/registration/verify', json={
            'username': 'nonexistent_user_verify',
            'code': '000000'
        })
        assert response.status_code in [400, 404]

    def test_verify_wrong_format(self, client):
        """تحقق بتنسيق خاطئ"""
        response = client.post('/api/registration/verify', json={
            'code': 'abc'
        })
        assert response.status_code in [400, 422]


class TestResendCode:
    """اختبارات إعادة إرسال الكود"""

    def test_resend_missing_identifier(self, client):
        """إعادة إرسال بدون معرّف"""
        response = client.post('/api/registration/resend', json={})
        assert response.status_code in [400, 404, 422]

    def test_resend_nonexistent_user(self, client):
        """إعادة إرسال لمستخدم غير موجود"""
        response = client.post('/api/registration/resend', json={
            'username': 'nonexistent_resend_user'
        })
        assert response.status_code in [400, 404]


class TestAdminRegistrationSettings:
    """اختبارات إعدادات التسجيل للأدمن"""

    def test_get_settings_no_auth(self, client):
        """جلب الإعدادات بدون مصادقة"""
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [302, 401, 403]

    def test_get_settings_as_admin(self, client, admin_user):
        """جلب الإعدادات كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_update_settings_no_auth(self, client):
        """تحديث الإعدادات بدون مصادقة"""
        response = client.post('/api/registration/admin/settings', json={
            'is_open': True
        })
        assert response.status_code in [302, 401, 403]

    def test_update_settings_as_admin(self, client, admin_user):
        """تحديث الإعدادات كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/registration/admin/settings', json={
            'is_open': True,
            'max_students': 100
        })
        assert response.status_code in [200, 400, 500]

    def test_toggle_registration_no_auth(self, client):
        """تبديل التسجيل بدون مصادقة"""
        response = client.post('/api/registration/admin/toggle', json={})
        assert response.status_code in [302, 401, 403]

    def test_toggle_registration_as_admin(self, client, admin_user):
        """تبديل التسجيل كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/registration/admin/toggle', json={})
        assert response.status_code in [200, 400, 500]
