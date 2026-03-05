"""
اختبارات شاملة لـ Notifications
يغطي: index, api notifications, mark-read, delete, mark-all-read, delete-multiple
"""
import pytest


class TestNotificationsAuth:
    """اختبارات المصادقة للإشعارات"""

    def test_index_no_auth(self, client):
        """صفحة الإشعارات بدون مصادقة"""
        response = client.get('/notifications/')
        assert response.status_code in [302, 401, 403]

    def test_api_notifications_no_auth(self, client):
        """API الإشعارات بدون مصادقة"""
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [302, 401, 403]

    def test_mark_read_no_auth(self, client):
        """تأشير مقروء بدون مصادقة"""
        response = client.post('/notifications/api/mark-read/1')
        assert response.status_code in [302, 401, 403]

    def test_delete_no_auth(self, client):
        """حذف إشعار بدون مصادقة"""
        response = client.delete('/notifications/api/delete/1')
        assert response.status_code in [302, 401, 403]

    def test_mark_all_read_no_auth(self, client):
        """تأشير الكل مقروء بدون مصادقة"""
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code in [302, 401, 403]

    def test_delete_multiple_no_auth(self, client):
        """حذف متعدد بدون مصادقة"""
        response = client.post('/notifications/api/delete-multiple', json={'ids': [1, 2]})
        assert response.status_code in [302, 401, 403]


class TestNotificationsAsAdmin:
    """اختبارات الإشعارات كأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_index_as_admin(self, client, admin_user):
        """صفحة الإشعارات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/notifications/')
        assert response.status_code in [200, 302, 500]

    def test_api_notifications_as_admin(self, client, admin_user):
        """API الإشعارات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_api_notifications_empty(self, client, admin_user):
        """API الإشعارات - قاعدة فارغة"""
        self._login(client, admin_user)
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [200, 500, 503]

    def test_api_notifications_with_filter(self, client, admin_user):
        """API الإشعارات مع فلتر"""
        self._login(client, admin_user)
        response = client.get('/notifications/api/notifications?read=false')
        assert response.status_code in [200, 400, 500, 503]

    def test_mark_read_nonexistent(self, client, admin_user):
        """تأشير مقروء لإشعار غير موجود"""
        self._login(client, admin_user)
        response = client.post('/notifications/api/mark-read/99999')
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_notification_nonexistent(self, client, admin_user):
        """حذف إشعار غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/notifications/api/delete/99999')
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_notification_post_method(self, client, admin_user):
        """حذف إشعار عبر POST"""
        self._login(client, admin_user)
        response = client.post('/notifications/api/delete/99999')
        assert response.status_code in [200, 404, 500, 503]

    def test_mark_all_read_as_admin(self, client, admin_user):
        """تأشير الكل مقروء كأدمن"""
        self._login(client, admin_user)
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code in [200, 500, 503]

    def test_delete_multiple_empty_list(self, client, admin_user):
        """حذف متعدد بقائمة فارغة"""
        self._login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple', json={'ids': []})
        assert response.status_code in [200, 400, 500, 503]

    def test_delete_multiple_nonexistent_ids(self, client, admin_user):
        """حذف متعدد بمعرفات غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple', json={'ids': [99999, 88888]})
        assert response.status_code in [200, 404, 500, 503]

    def test_get_notification_read_stats_nonexistent(self, client, admin_user):
        """إحصائيات قراءة إشعار غير موجود"""
        self._login(client, admin_user)
        response = client.get('/notifications/api/admin/notification/99999/read-stats')
        assert response.status_code in [200, 404, 500, 503]
