"""
اختبارات نظام المصادقة (تسجيل الدخول والخروج)
"""
import pytest


class TestAdminLogin:
    """اختبارات تسجيل دخول الأدمن"""

    def test_login_page_loads(self, client):
        """صفحة تسجيل الدخول تُحمَّل بنجاح"""
        response = client.get('/auth/login')
        assert response.status_code == 200

    def test_login_correct_credentials(self, client, admin_user):
        """تسجيل دخول بكلمة مرور صحيحة"""
        response = client.post('/auth/login', data={
            'username': 'test_admin',
            'password': 'Admin@123'
        }, follow_redirects=False)
        # الأدمن يُوجَّه لـ verify_2fa (لأن 2FA مطلوب)
        # أو لـ setup_2fa (لو لم يُعدّه بعد)
        assert response.status_code in [200, 302]

    def test_login_wrong_password(self, client, admin_user):
        """تسجيل دخول بكلمة مرور خاطئة"""
        response = client.post('/auth/login', data={
            'username': 'test_admin',
            'password': 'WrongPassword'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'غير صحيحة' in response.get_data(as_text=True)

    def test_login_nonexistent_user(self, client):
        """تسجيل دخول بمستخدم غير موجود"""
        response = client.post('/auth/login', data={
            'username': 'ghost_user',
            'password': 'any_password'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'غير صحيحة' in response.get_data(as_text=True)

    def test_verify_2fa_without_session(self, client):
        """الوصول لـ verify_2fa بدون session سابقة → يُوجَّه لـ login"""
        response = client.get('/auth/verify-2fa', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestStudentApiLogin:
    """اختبارات تسجيل دخول الطالب عبر API"""

    def test_student_login_success(self, client, student_user):
        """تسجيل دخول طالب صحيح"""
        response = client.post('/students/api/login', json={
            'username': 'test_student',
            'password': 'Student@123',
            'device_id': 'test-device-001',
            'device_name': 'iPhone Test'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'session_token' in data or 'student' in data

    def test_student_login_wrong_password(self, client, student_user):
        """تسجيل دخول طالب بكلمة مرور خاطئة"""
        response = client.post('/students/api/login', json={
            'username': 'test_student',
            'password': 'WrongPass',
            'device_id': 'test-device-001'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False

    def test_student_login_missing_fields(self, client):
        """تسجيل دخول بدون بيانات"""
        response = client.post('/students/api/login', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_student_login_inactive_account(self, client, inactive_student):
        """طالب حسابه معطّل"""
        response = client.post('/students/api/login', json={
            'username': 'inactive_student',
            'password': 'Student@123',
            'device_id': 'test-device-001'
        })
        assert response.status_code in [401, 403]
        data = response.get_json()
        assert data['success'] is False

    def test_student_login_nonexistent(self, client):
        """طالب غير موجود"""
        response = client.post('/students/api/login', json={
            'username': 'ghost_student',
            'password': 'any_pass',
            'device_id': 'test-device-001'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
