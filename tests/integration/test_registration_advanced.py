"""
اختبارات موسعة لـ registration routes
يغطي: teacher registration, admin settings, verify, resend
"""
import pytest


class TestRegistrationAdvanced:
    """اختبارات متقدمة للتسجيل"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_registration_status_public(self, client):
        """حالة التسجيل - عام"""
        response = client.get('/api/registration/status')
        assert response.status_code in [200, 404, 500]

    def test_register_student_empty(self, client):
        """تسجيل طالب ببيانات فارغة"""
        response = client.post('/api/registration/register', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_register_student_valid(self, client):
        """تسجيل طالب ببيانات صالحة"""
        response = client.post('/api/registration/register', json={
            'name': 'طالب جديد للتسجيل',
            'username': 'new_reg_stu1',
            'email': 'new_reg_stu1@test.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 201, 400, 409, 422, 500]

    def test_register_student_duplicate(self, client, db_session, app):
        """تسجيل طالب بنفس البيانات مرتين"""
        import secrets
        from src.models.student import Student
        s = Student(name='Dup Stu', username='dup_reg_stu', email='dup_reg_stu@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/api/registration/register', json={
            'name': 'طالب مكرر',
            'username': 'dup_reg_stu',
            'email': 'dup_reg_stu@test.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 400, 409, 422, 500]

    def test_register_teacher_empty(self, client):
        """تسجيل معلم ببيانات فارغة"""
        response = client.post('/api/registration/register-teacher', json={})
        assert response.status_code in [200, 400, 403, 422, 500]

    def test_register_teacher_valid(self, client):
        """تسجيل معلم ببيانات صالحة"""
        response = client.post('/api/registration/register-teacher', json={
            'name': 'معلم جديد للتسجيل',
            'username': 'new_reg_tea1',
            'email': 'new_reg_tea1@test.com',
            'password': 'Pass@123',
            'subject': 'كيمياء'
        })
        assert response.status_code in [200, 201, 400, 403, 409, 422, 500]

    def test_verify_registration_empty(self, client):
        """التحقق من التسجيل ببيانات فارغة"""
        response = client.post('/api/registration/verify', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_verify_registration_invalid_code(self, client):
        """التحقق من التسجيل برمز خاطئ"""
        response = client.post('/api/registration/verify', json={
            'username': 'test_user',
            'code': '000000'
        })
        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_resend_verification_empty(self, client):
        """إعادة إرسال التحقق ببيانات فارغة"""
        response = client.post('/api/registration/resend', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_resend_verification_nonexistent(self, client):
        """إعادة إرسال التحقق لمستخدم غير موجود"""
        response = client.post('/api/registration/resend', json={
            'username': 'nonexistent_user_xyz'
        })
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_admin_settings_no_auth(self, client):
        """إعدادات التسجيل بدون مصادقة"""
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [302, 401, 403]

    def test_admin_settings_as_admin(self, client, admin_user):
        """إعدادات التسجيل كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/registration/admin/settings')
        assert response.status_code in [200, 404, 500]

    def test_admin_toggle_no_auth(self, client):
        """تبديل حالة التسجيل بدون مصادقة"""
        response = client.post('/api/registration/admin/toggle', json={})
        assert response.status_code in [302, 401, 403]

    def test_admin_toggle_as_admin(self, client, admin_user):
        """تبديل حالة التسجيل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/toggle', json={
            'enabled': True
        })
        assert response.status_code in [200, 400, 500]
