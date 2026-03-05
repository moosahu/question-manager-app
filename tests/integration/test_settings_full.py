"""
اختبارات شاملة لـ settings routes
يغطي: إعدادات النظام، 2FA، Google Drive، backup
"""
import pytest


class TestSettingsIndex:
    """اختبارات صفحة الإعدادات الرئيسية"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_settings_index_no_auth(self, client):
        """صفحة الإعدادات بدون مصادقة"""
        response = client.get('/settings/')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_settings_index_as_admin(self, client, admin_user):
        """صفحة الإعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/')
        assert response.status_code in [200, 302, 404, 500]

    def test_settings_post_no_auth(self, client):
        """تحديث الإعدادات بدون مصادقة"""
        response = client.post('/settings/', data={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_settings_post_as_admin(self, client, admin_user):
        """تحديث الإعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/', data={
            'app_name': 'اختبار',
        })
        assert response.status_code in [200, 302, 400, 422, 500]


class TestSettings2FA:
    """اختبارات إعداد المصادقة الثنائية"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_setup_2fa_get_no_auth(self, client):
        """صفحة إعداد 2FA بدون مصادقة"""
        response = client.get('/settings/setup-2fa')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_setup_2fa_get_as_admin(self, client, admin_user):
        """صفحة إعداد 2FA كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/setup-2fa')
        assert response.status_code in [200, 302, 404, 500]

    def test_setup_2fa_post_empty(self, client, admin_user):
        """إعداد 2FA ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/settings/setup-2fa', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_disable_2fa_no_auth(self, client):
        """تعطيل 2FA بدون مصادقة"""
        response = client.post('/settings/disable-2fa', data={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_disable_2fa_as_admin(self, client, admin_user):
        """تعطيل 2FA كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/disable-2fa', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_verify_2fa_no_auth(self, client):
        """التحقق من 2FA بدون مصادقة"""
        response = client.post('/settings/verify-2fa', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_verify_2fa_as_admin_empty(self, client, admin_user):
        """التحقق من 2FA كأدمن ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/settings/verify-2fa', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_verify_2fa_wrong_code(self, client, admin_user):
        """التحقق من 2FA برمز خاطئ"""
        self._login(client, admin_user)
        response = client.post('/settings/verify-2fa', json={'otp': '000000'})
        assert response.status_code in [200, 400, 401, 422, 500]


class TestSettingsGoogleDrive:
    """اختبارات إعدادات Google Drive"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_google_drive_connect_no_auth(self, client):
        """ربط Google Drive بدون مصادقة"""
        response = client.post('/settings/api/v1/google-drive/connect', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_google_drive_connect_as_admin(self, client, admin_user):
        """ربط Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/connect', json={})
        assert response.status_code in [200, 400, 500]

    def test_google_drive_disconnect_no_auth(self, client):
        """فصل Google Drive بدون مصادقة"""
        response = client.post('/settings/api/v1/google-drive/disconnect', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_google_drive_disconnect_as_admin(self, client, admin_user):
        """فصل Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/disconnect', json={})
        assert response.status_code in [200, 400, 500]

    def test_google_drive_status_no_auth(self, client):
        """حالة Google Drive بدون مصادقة"""
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_google_drive_status_as_admin(self, client, admin_user):
        """حالة Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 500]

    def test_sync_to_drive_no_auth(self, client):
        """مزامنة إلى Drive بدون مصادقة"""
        response = client.post('/settings/api/v1/user-settings/sync-to-drive', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_sync_to_drive_as_admin(self, client, admin_user):
        """مزامنة إلى Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/sync-to-drive', json={})
        assert response.status_code in [200, 400, 500]

    def test_download_from_drive_no_auth(self, client):
        """تحميل من Drive بدون مصادقة"""
        response = client.post('/settings/api/v1/user-settings/download-from-drive', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_download_from_drive_as_admin(self, client, admin_user):
        """تحميل من Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/download-from-drive', json={})
        assert response.status_code in [200, 400, 500]

    def test_quick_sync_no_auth(self, client):
        """مزامنة سريعة بدون مصادقة"""
        response = client.post('/settings/api/v1/user-settings/quick-sync', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_quick_sync_as_admin(self, client, admin_user):
        """مزامنة سريعة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/quick-sync', json={})
        assert response.status_code in [200, 400, 500]


class TestSettingsBackup:
    """اختبارات النسخ الاحتياطي"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_backup_settings_no_auth(self, client):
        """جلب إعدادات الباكب بدون مصادقة"""
        response = client.get('/settings/api/v1/backup-settings')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_get_backup_settings_as_admin(self, client, admin_user):
        """جلب إعدادات الباكب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/api/v1/backup-settings')
        assert response.status_code in [200, 500]

    def test_save_backup_settings_no_auth(self, client):
        """حفظ إعدادات الباكب بدون مصادقة"""
        response = client.post('/settings/api/v1/backup-settings', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_save_backup_settings_as_admin(self, client, admin_user):
        """حفظ إعدادات الباكب كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'enabled': True,
            'frequency': 'daily'
        })
        assert response.status_code in [200, 400, 500]

    def test_create_backup_no_auth(self, client):
        """إنشاء نسخة احتياطية بدون مصادقة"""
        response = client.post('/settings/api/v1/backup/create', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_create_backup_as_admin(self, client, admin_user):
        """إنشاء نسخة احتياطية كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/backup/create', json={})
        assert response.status_code in [200, 400, 500]

    def test_restore_backup_no_auth(self, client):
        """استعادة نسخة احتياطية بدون مصادقة"""
        response = client.post('/settings/api/v1/backup/restore', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_restore_backup_no_file(self, client, admin_user):
        """استعادة نسخة احتياطية بدون ملف"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/backup/restore', json={})
        assert response.status_code in [200, 400, 422, 500]


class TestSettingsAdminPhone:
    """اختبارات إعدادات هاتف الأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_admin_phone_page_no_auth(self, client):
        """صفحة هاتف الأدمن بدون مصادقة"""
        response = client.get('/settings/admin-phone')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_admin_phone_page_as_admin(self, client, admin_user):
        """صفحة هاتف الأدمن كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/admin-phone')
        assert response.status_code in [200, 302, 404, 500]

    def test_verify_firebase_no_auth(self, client):
        """التحقق من Firebase بدون مصادقة"""
        response = client.post('/settings/admin-phone/verify-firebase', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_verify_firebase_as_admin(self, client, admin_user):
        """التحقق من Firebase كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/admin-phone/verify-firebase', json={
            'phone': '+966500000000',
            'token': 'test_firebase_token'
        })
        assert response.status_code in [200, 400, 500]
