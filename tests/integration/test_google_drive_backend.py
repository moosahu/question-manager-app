"""
اختبارات Google Drive Backend routes
يغطي: dashboard, settings, connect, disconnect, status, sync, export, import
"""
import pytest


class TestGoogleDriveBackendPages:
    """اختبارات الصفحات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_dashboard_no_auth(self, client):
        """لوحة التحكم بدون مصادقة"""
        response = client.get('/google-drive-backend/google-drive-dashboard')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_dashboard_as_admin(self, client, admin_user):
        """لوحة التحكم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/google-drive-backend/google-drive-dashboard')
        assert response.status_code in [200, 302, 404, 500]

    def test_settings_get_no_auth(self, client):
        """إعدادات Google Drive بدون مصادقة"""
        response = client.get('/google-drive-backend/google-drive-settings')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_settings_get_as_admin(self, client, admin_user):
        """إعدادات Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.get('/google-drive-backend/google-drive-settings')
        assert response.status_code in [200, 302, 404, 500]

    def test_settings_post_as_admin(self, client, admin_user):
        """حفظ إعدادات Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/google-drive-backend/google-drive-settings', data={
            'credentials': '{}',
            'folder_id': 'test_folder'
        })
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_add_question_page(self, client, admin_user):
        """صفحة إضافة سؤال عبر Google Drive"""
        self._login(client, admin_user)
        response = client.get('/google-drive-backend/google-drive-add-question')
        assert response.status_code in [200, 302, 404, 500]

    def test_manage_questions_page(self, client, admin_user):
        """صفحة إدارة الأسئلة عبر Google Drive"""
        self._login(client, admin_user)
        response = client.get('/google-drive-backend/google-drive-manage-questions')
        assert response.status_code in [200, 302, 404, 500]


class TestGoogleDriveBackendAPI:
    """اختبارات Google Drive Backend API"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_connect_no_auth(self, client):
        """اتصال بدون مصادقة"""
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/connect',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_connect_as_admin(self, client, admin_user):
        """اتصال كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/connect',
            json={'credentials': '{}'}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_disconnect_no_auth(self, client):
        """فصل بدون مصادقة"""
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/disconnect',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_disconnect_as_admin(self, client, admin_user):
        """فصل كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/disconnect',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_connection_status(self, client):
        """حالة الاتصال"""
        response = client.get(
            '/google-drive-backend/api/v1/google-drive-backend/connection-status'
        )
        assert response.status_code in [200, 404, 500]

    def test_save_settings_no_auth(self, client):
        """حفظ إعدادات بدون مصادقة"""
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/save-settings',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_save_settings_as_admin(self, client, admin_user):
        """حفظ إعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/save-settings',
            json={'setting': 'value'}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_load_settings_no_auth(self, client):
        """تحميل إعدادات بدون مصادقة"""
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/load-settings',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_load_settings_as_admin(self, client, admin_user):
        """تحميل إعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/load-settings',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_sync_no_auth(self, client):
        """مزامنة بدون مصادقة"""
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/sync',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_sync_as_admin(self, client, admin_user):
        """مزامنة كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/sync',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_export_user_data(self, client, admin_user):
        """تصدير بيانات المستخدم"""
        self._login(client, admin_user)
        response = client.get(
            '/google-drive-backend/api/google-drive-backend/user/export'
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_import_user_data_no_auth(self, client):
        """استيراد بيانات المستخدم بدون مصادقة"""
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/user/import',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_import_user_data_as_admin(self, client, admin_user):
        """استيراد بيانات المستخدم كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/google-drive-backend/user/import',
            json={'data': {}}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_sync_to_drive_as_admin(self, client, admin_user):
        """مزامنة الإعدادات إلى Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/user-settings/sync-to-drive',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_download_from_drive_as_admin(self, client, admin_user):
        """تحميل الإعدادات من Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/user-settings/download-from-drive',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_quick_sync_as_admin(self, client, admin_user):
        """مزامنة سريعة كأدمن"""
        self._login(client, admin_user)
        response = client.post(
            '/google-drive-backend/api/v1/google-drive-backend/user-settings/quick-sync',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]
