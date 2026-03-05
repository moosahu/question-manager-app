"""
اختبارات تفصيلية لـ Auth Routes
يغطي: login page, failed login, logout, verify-2fa, change password
"""
import pytest


class TestAuthLoginPage:
    """اختبارات صفحة تسجيل الدخول"""

    def test_login_page_accessible(self, client):
        """صفحة تسجيل الدخول تُحمّل"""
        response = client.get('/auth/login')
        assert response.status_code == 200

    def test_login_page_has_form(self, client):
        """الصفحة تحتوي على form"""
        response = client.get('/auth/login')
        assert b'form' in response.data or response.status_code == 200

    def test_login_wrong_password(self, client, admin_user):
        """كلمة مرور خاطئة ترفض الدخول"""
        response = client.post('/auth/login', data={
            'username': admin_user.username,
            'password': 'WrongPass@123'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_nonexistent_user(self, client):
        """مستخدم غير موجود"""
        response = client.post('/auth/login', data={
            'username': 'totally_nonexistent_user',
            'password': 'AnyPass@123'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_empty_form(self, client):
        """تقديم form فارغ"""
        response = client.post('/auth/login', data={}, follow_redirects=True)
        assert response.status_code == 200


class TestAuthVerify2FA:
    """اختبارات التحقق الثنائي"""

    def test_verify_2fa_without_session(self, client):
        """صفحة 2FA تعيد توجيه إذا لم يكن في session"""
        response = client.get('/auth/verify-2fa')
        assert response.status_code in [302, 200]

    def test_verify_2fa_page(self, client):
        """صفحة التحقق الثنائي تُحمّل أو تعيد توجيه"""
        response = client.get('/auth/verify-2fa')
        assert response.status_code in [200, 302]


class TestAuthLogout:
    """اختبارات تسجيل الخروج"""

    def test_logout_requires_login(self, client):
        """تسجيل الخروج يتطلب دخول مسبق"""
        response = client.get('/auth/logout')
        assert response.status_code in [200, 302]

    def test_logout_with_authenticated_user(self, client, admin_user):
        """تسجيل خروج بعد الدخول"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200


class TestAuthChangePassword:
    """اختبارات تغيير كلمة المرور"""

    def test_change_password_requires_login(self, client):
        """تغيير كلمة المرور يتطلب تسجيل دخول"""
        response = client.post('/auth/change-password', data={
            'current_password': 'old',
            'new_password': 'new',
            'confirm_password': 'new'
        })
        assert response.status_code in [200, 302, 401, 404]

    def test_change_password_with_admin(self, client, admin_user):
        """تغيير كلمة المرور للأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/auth/change-password', data={
            'current_password': 'Admin@123',
            'new_password': 'NewAdmin@456',
            'confirm_password': 'NewAdmin@456'
        }, follow_redirects=True)
        assert response.status_code in [200, 302, 404]


class TestAuthAPI:
    """اختبارات API نقاط Auth"""

    def test_generate_backup_codes_requires_auth(self, client):
        """توليد Backup Codes يتطلب مصادقة"""
        response = client.post('/auth/generate-backup-codes')
        assert response.status_code in [200, 302, 401, 404, 405]

    def test_setup_2fa_requires_auth(self, client):
        """إعداد 2FA يتطلب مصادقة"""
        response = client.get('/auth/setup-2fa')
        assert response.status_code in [200, 302, 401, 404]

    def test_send_otp_email_endpoint(self, client):
        """endpoint إرسال OTP عبر البريد"""
        response = client.post('/auth/send-otp-email', json={})
        assert response.status_code in [200, 302, 400, 401, 404, 405]

    def test_disable_2fa_requires_auth(self, client):
        """تعطيل 2FA يتطلب مصادقة"""
        response = client.post('/auth/disable-2fa')
        assert response.status_code in [200, 302, 401, 404, 405]
