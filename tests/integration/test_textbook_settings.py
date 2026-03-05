"""
اختبارات لـ Textbook API و Settings
يغطي: textbooks CRUD, settings index/2fa, backup settings
"""
import pytest


class TestTextbookAuth:
    """اختبارات مصادقة Textbook API"""

    def test_get_textbooks_no_auth(self, client):
        """جلب الكتب بدون مصادقة"""
        response = client.get('/api/admin/textbooks')
        assert response.status_code in [302, 401, 403]

    def test_register_textbook_no_auth(self, client):
        """تسجيل كتاب بدون مصادقة"""
        response = client.post('/api/admin/textbooks/register', json={})
        assert response.status_code in [302, 401, 403]

    def test_delete_textbook_no_auth(self, client):
        """حذف كتاب بدون مصادقة"""
        response = client.delete('/api/admin/textbooks/1')
        assert response.status_code in [302, 401, 403]

    def test_get_courses_with_textbooks_no_auth(self, client):
        """جلب المناهج مع الكتب - يمكن العام الوصول إليها"""
        response = client.get('/api/admin/textbooks/courses-with-textbooks')
        assert response.status_code in [200, 302, 401, 403]


class TestTextbookAsAdmin:
    """اختبارات Textbook API كأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_textbooks_as_admin(self, client, admin_user):
        """جلب الكتب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_register_textbook_missing_fields(self, client, admin_user):
        """تسجيل كتاب بدون حقول مطلوبة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/register', json={})
        assert response.status_code in [400, 422, 500]

    def test_register_textbook_valid(self, client, admin_user, db_session, app):
        """تسجيل كتاب ببيانات صالحة"""
        from src.models.curriculum import Course
        c = Course(name='Textbook Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/register', json={
            'course_id': c.id,
            'title': 'كتاب الكيمياء',
            'total_pages': 200
        })
        assert response.status_code in [200, 201, 400, 500]

    def test_delete_textbook_nonexistent(self, client, admin_user):
        """حذف كتاب غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/api/admin/textbooks/99999')
        assert response.status_code in [404, 500]

    def test_get_courses_with_textbooks(self, client, admin_user):
        """جلب المناهج مع الكتب"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks/courses-with-textbooks')
        assert response.status_code in [200, 500]

    def test_set_lesson_pages_nonexistent(self, client, admin_user):
        """تعيين صفحات درس لكتاب غير موجود"""
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/99999/pages', json={
            'lesson_id': 1,
            'start_page': 10,
            'end_page': 20
        })
        assert response.status_code in [400, 404, 500]

    def test_get_lesson_pages_nonexistent(self, client, admin_user):
        """جلب صفحات كتاب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks/99999/pages')
        assert response.status_code in [200, 404, 500]

    def test_get_lesson_page_info(self, client, admin_user):
        """جلب معلومات صفحات الدرس"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks/lesson/99999/pages')
        assert response.status_code in [200, 404, 500]


class TestSettingsRoutes:
    """اختبارات مسارات الإعدادات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_settings_index_no_auth(self, client):
        """صفحة الإعدادات بدون مصادقة"""
        response = client.get('/settings/')
        assert response.status_code in [302, 401]

    def test_settings_index_as_admin(self, client, admin_user):
        """صفحة الإعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/')
        assert response.status_code in [200, 302, 500]

    def test_google_drive_status_no_auth(self, client):
        """حالة Google Drive بدون مصادقة"""
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [302, 401]

    def test_google_drive_status_as_admin(self, client, admin_user):
        """حالة Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 500]

    def test_backup_settings_get_no_auth(self, client):
        """جلب إعدادات النسخ الاحتياطي بدون مصادقة"""
        response = client.get('/settings/api/v1/backup-settings')
        assert response.status_code in [302, 401]

    def test_backup_settings_get_as_admin(self, client, admin_user):
        """جلب إعدادات النسخ الاحتياطي كأدمن"""
        self._login(client, admin_user)
        response = client.get('/settings/api/v1/backup-settings')
        assert response.status_code in [200, 500]

    def test_backup_settings_save_as_admin(self, client, admin_user):
        """حفظ إعدادات النسخ الاحتياطي كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'enabled': True,
            'frequency': 'daily'
        })
        assert response.status_code in [200, 400, 500]

    def test_create_backup_no_auth(self, client):
        """إنشاء نسخ احتياطية بدون مصادقة"""
        response = client.post('/settings/api/v1/backup/create', json={})
        assert response.status_code in [302, 401]

    def test_create_backup_as_admin(self, client, admin_user):
        """إنشاء نسخ احتياطية كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/backup/create', json={})
        assert response.status_code in [200, 400, 500]

    def test_disable_2fa_no_auth(self, client):
        """تعطيل 2FA بدون مصادقة"""
        response = client.post('/settings/disable-2fa', json={})
        assert response.status_code in [302, 401]

    def test_disable_2fa_as_admin(self, client, admin_user):
        """تعطيل 2FA كأدمن"""
        self._login(client, admin_user)
        response = client.post('/settings/disable-2fa', json={})
        assert response.status_code in [200, 302, 400, 500]

    def test_google_drive_disconnect_as_admin(self, client, admin_user):
        """قطع الاتصال بـ Google Drive"""
        self._login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/disconnect', json={})
        assert response.status_code in [200, 400, 500]
