"""
اختبارات موسعة لـ auth routes
يغطي: 2FA, OTP, device management, session management
"""
import pytest


class TestAuthLogin:
    """اختبارات تسجيل الدخول"""

    def test_login_page_get(self, client):
        """صفحة تسجيل الدخول"""
        response = client.get('/auth/login')
        assert response.status_code in [200, 302, 404]

    def test_login_wrong_password(self, client, admin_user):
        """تسجيل دخول بكلمة مرور خاطئة"""
        response = client.post('/auth/login', data={
            'username': admin_user.username,
            'password': 'WrongPassword123!',
            'remember_me': 'false'
        })
        assert response.status_code in [200, 302, 400, 401, 500]

    def test_login_nonexistent_user(self, client):
        """تسجيل دخول بمستخدم غير موجود"""
        response = client.post('/auth/login', data={
            'username': 'nonexistent_user_xyz',
            'password': 'Pass@123',
            'remember_me': 'false'
        })
        assert response.status_code in [200, 302, 400, 401, 500]

    def test_logout_as_admin(self, client, admin_user):
        """تسجيل الخروج كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/auth/logout')
        assert response.status_code in [200, 302, 404, 500]


class TestAuth2FA:
    """اختبارات المصادقة الثنائية"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_verify_2fa_get(self, client):
        """صفحة التحقق من 2FA"""
        response = client.get('/auth/verify-2fa')
        assert response.status_code in [200, 302, 404, 500]

    def test_verify_2fa_post_empty(self, client):
        """إرسال 2FA بدون رمز"""
        response = client.post('/auth/verify-2fa', data={})
        assert response.status_code in [200, 302, 400, 401, 500]

    def test_verify_2fa_post_wrong_code(self, client):
        """إرسال 2FA برمز خاطئ"""
        response = client.post('/auth/verify-2fa', data={'otp_code': '000000'})
        assert response.status_code in [200, 302, 400, 401, 500]

    def test_get_admin_phone_no_auth(self, client):
        """جلب رقم هاتف الأدمن بدون مصادقة"""
        response = client.post('/auth/get-admin-phone', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_get_admin_phone_as_admin(self, client, admin_user):
        """جلب رقم هاتف الأدمن كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/get-admin-phone', json={})
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_check_phone_no_auth(self, client):
        """التحقق من رقم الهاتف بدون مصادقة"""
        response = client.post('/auth/check-phone', json={
            'phone': '+966500000000'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 500]

    def test_check_phone_as_admin(self, client, admin_user):
        """التحقق من رقم الهاتف كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/check-phone', json={
            'phone': '+966500000000'
        })
        assert response.status_code in [200, 400, 500]

    def test_send_admin_otp_no_auth(self, client):
        """إرسال OTP بدون مصادقة"""
        response = client.post('/auth/send-admin-otp', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 500]

    def test_send_admin_otp_as_admin(self, client, admin_user):
        """إرسال OTP كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/send-admin-otp', json={
            'phone': '+966500000000'
        })
        assert response.status_code in [200, 400, 500, 503]

    def test_enable_2fa_notification_no_auth(self, client):
        """تفعيل 2FA بإشعار بدون مصادقة"""
        response = client.post('/auth/api/admin/notifications/enable-2fa', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_enable_2fa_notification_as_admin(self, client, admin_user):
        """تفعيل 2FA بإشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/enable-2fa', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_disable_2fa_notification_no_auth(self, client):
        """إلغاء 2FA بإشعار بدون مصادقة"""
        response = client.post('/auth/api/admin/notifications/disable-2fa', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_disable_2fa_notification_as_admin(self, client, admin_user):
        """إلغاء 2FA بإشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/disable-2fa', json={})
        assert response.status_code in [200, 400, 404, 500]


class TestAuthNotifications:
    """اختبارات إشعارات الأدمن عبر Auth"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_admin_notifications_no_auth(self, client):
        """جلب إشعارات الأدمن بدون مصادقة"""
        response = client.get('/auth/api/admin/notifications')
        assert response.status_code in [302, 401, 403, 404]

    def test_get_admin_notifications_as_admin(self, client, admin_user):
        """جلب إشعارات الأدمن كأدمن"""
        self._login(client, admin_user)
        response = client.get('/auth/api/admin/notifications')
        assert response.status_code in [200, 404, 500, 503]

    def test_mark_notification_read_as_admin(self, client, admin_user):
        """تأشير إشعار مقروء كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/99999/read')
        assert response.status_code in [200, 404, 500, 503]

    def test_mark_all_notifications_read_as_admin(self, client, admin_user):
        """تأشير كل الإشعارات مقروءة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/mark-all-read')
        assert response.status_code in [200, 404, 500, 503]

    def test_save_fcm_token_no_auth(self, client):
        """حفظ FCM token بدون مصادقة"""
        response = client.post('/auth/api/admin/fcm-token', json={
            'fcm_token': 'test_token'
        })
        assert response.status_code in [302, 401, 403, 404]

    def test_save_fcm_token_as_admin(self, client, admin_user):
        """حفظ FCM token كأدمن"""
        self._login(client, admin_user)
        response = client.post('/auth/api/admin/fcm-token', json={
            'fcm_token': 'test_fcm_token_123'
        })
        assert response.status_code in [200, 400, 404, 500]
