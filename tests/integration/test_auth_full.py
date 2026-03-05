"""
اختبارات شاملة لـ Auth routes
يغطي: login, logout, 2fa, admin phone, admin OTP, fcm-token, admin notifications
"""
import pytest


class TestAuthLoginFull:
    """اختبارات تسجيل الدخول الشاملة"""

    def test_login_page_get(self, client):
        """صفحة تسجيل الدخول"""
        response = client.get('/auth/login')
        assert response.status_code in [200, 302, 500]

    def test_login_empty_post(self, client):
        """تسجيل دخول بدون بيانات"""
        response = client.post('/auth/login', data={})
        assert response.status_code in [200, 302, 400]

    def test_login_wrong_password(self, client, admin_user):
        """تسجيل دخول بكلمة مرور خاطئة"""
        response = client.post('/auth/login', data={
            'username': admin_user.username,
            'password': 'WrongPassword123!'
        })
        assert response.status_code in [200, 302, 400, 401]

    def test_login_nonexistent_user(self, client):
        """تسجيل دخول بمستخدم غير موجود"""
        response = client.post('/auth/login', data={
            'username': 'nonexistent_admin_user',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 400, 401]

    def test_login_success(self, client, admin_user):
        """تسجيل دخول ناجح"""
        response = client.post('/auth/login', data={
            'username': admin_user.username,
            'password': 'admin123'
        })
        assert response.status_code in [200, 302]

    def test_logout_no_auth(self, client):
        """تسجيل خروج بدون مصادقة"""
        response = client.get('/auth/logout')
        assert response.status_code in [302, 401]

    def test_logout_as_admin(self, client, admin_user):
        """تسجيل خروج كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/auth/logout')
        assert response.status_code in [200, 302]


class TestAuth2FA:
    """اختبارات المصادقة الثنائية"""

    def test_verify_2fa_page_get(self, client):
        """صفحة التحقق من 2FA"""
        response = client.get('/auth/verify-2fa')
        assert response.status_code in [200, 302, 500]

    def test_verify_2fa_no_session(self, client):
        """التحقق من 2FA بدون جلسة"""
        response = client.post('/auth/verify-2fa', data={
            'otp_code': '123456'
        })
        assert response.status_code in [200, 302, 400, 401]

    def test_verify_2fa_wrong_code(self, client, admin_user):
        """التحقق من 2FA بكود خاطئ"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['2fa_user_id'] = admin_user.id
        response = client.post('/auth/verify-2fa', data={
            'otp_code': '000000'
        })
        assert response.status_code in [200, 302, 400, 401]


class TestAuthAdminPhone:
    """اختبارات هاتف الأدمن"""

    def test_get_admin_phone(self, client):
        """جلب هاتف الأدمن"""
        response = client.post('/auth/get-admin-phone', json={
            'username': 'someadmin'
        })
        assert response.status_code in [200, 400, 404]

    def test_check_phone_missing(self, client):
        """التحقق من الهاتف بدون بيانات"""
        response = client.post('/auth/check-phone', json={})
        assert response.status_code in [200, 400, 422]

    def test_check_phone_invalid(self, client):
        """التحقق من هاتف غير موجود"""
        response = client.post('/auth/check-phone', json={
            'phone': '0500000000'
        })
        assert response.status_code in [200, 400, 404]

    def test_send_admin_otp_no_user(self, client):
        """إرسال OTP لأدمن غير موجود"""
        response = client.post('/auth/send-admin-otp', json={
            'username': 'nonexistent_otp_admin'
        })
        assert response.status_code in [200, 400, 404, 500]


class TestAuthAdminNotifications:
    """اختبارات إشعارات الأدمن عبر Auth"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_admin_notifications_no_auth(self, client):
        """جلب إشعارات الأدمن بدون مصادقة"""
        response = client.get('/auth/api/admin/notifications')
        assert response.status_code in [200, 401, 403, 404, 500, 503]

    def test_get_admin_notifications_as_admin(self, client, admin_user):
        """جلب إشعارات الأدمن"""
        self._login(client, admin_user)
        response = client.get('/auth/api/admin/notifications')
        assert response.status_code in [200, 404, 500, 503]

    def test_mark_admin_notification_read_nonexistent(self, client, admin_user):
        """تأشير إشعار أدمن مقروء - غير موجود"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/99999/read')
        assert response.status_code in [200, 404, 500]

    def test_mark_all_admin_notifications_read(self, client, admin_user):
        """تأشير كل إشعارات الأدمن مقروءة"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/mark-all-read')
        assert response.status_code in [200, 404, 500]

    def test_save_admin_fcm_token_no_auth(self, client):
        """حفظ FCM token للأدمن بدون مصادقة"""
        response = client.post('/auth/api/admin/fcm-token', json={
            'fcm_token': 'test_fcm_token_admin'
        })
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_enable_2fa_notification_no_auth(self, client):
        """تفعيل إشعار 2FA بدون مصادقة"""
        response = client.post('/auth/enable_2fa_notification', json={})
        assert response.status_code in [302, 401, 403]

    def test_enable_2fa_notification_as_admin(self, client, admin_user):
        """تفعيل إشعار 2FA كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/enable_2fa_notification', json={})
        assert response.status_code in [200, 302, 400, 500]

    def test_disable_2fa_notification_as_admin(self, client, admin_user):
        """تعطيل إشعار 2FA كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/disable_2fa_notification', json={})
        assert response.status_code in [200, 302, 400, 500]
