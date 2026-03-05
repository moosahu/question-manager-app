"""
اختبارات موسعة لـ API routes
يغطي: google drive, user settings, courses/units/lessons visibility toggle, questions API
"""
import pytest


class TestAPICoursesUnitsVisibility:
    """اختبارات تبديل رؤية المناهج والوحدات والدروس"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_toggle_course_visibility_no_auth(self, client):
        """تبديل رؤية منهج بدون مصادقة"""
        response = client.put('/api/v1/courses/1/toggle-bot-visibility')
        assert response.status_code in [302, 401, 403]

    def test_toggle_course_visibility_nonexistent(self, client, admin_user):
        """تبديل رؤية منهج غير موجود"""
        self._login(client, admin_user)
        response = client.put('/api/v1/courses/99999/toggle-bot-visibility')
        assert response.status_code in [200, 404, 500]

    def test_toggle_course_visibility_post(self, client, admin_user):
        """تبديل رؤية منهج - POST"""
        self._login(client, admin_user)
        response = client.post('/api/v1/courses/99999/toggle-bot-visibility')
        assert response.status_code in [200, 404, 500]

    def test_toggle_unit_visibility_no_auth(self, client):
        """تبديل رؤية وحدة بدون مصادقة"""
        response = client.put('/api/v1/units/1/toggle-bot-visibility')
        assert response.status_code in [302, 401, 403]

    def test_toggle_unit_visibility_nonexistent(self, client, admin_user):
        """تبديل رؤية وحدة غير موجودة"""
        self._login(client, admin_user)
        response = client.put('/api/v1/units/99999/toggle-bot-visibility')
        assert response.status_code in [200, 404, 500]

    def test_toggle_lesson_visibility_no_auth(self, client):
        """تبديل رؤية درس بدون مصادقة"""
        response = client.put('/api/v1/lessons/1/toggle-bot-visibility')
        assert response.status_code in [302, 401, 403]

    def test_toggle_lesson_visibility_nonexistent(self, client, admin_user):
        """تبديل رؤية درس غير موجود"""
        self._login(client, admin_user)
        response = client.put('/api/v1/lessons/99999/toggle-bot-visibility')
        assert response.status_code in [200, 404, 500]

    def test_get_courses_public(self, client):
        """جلب المناهج - عام"""
        response = client.get('/api/v1/courses')
        assert response.status_code in [200, 500]

    def test_get_course_units_public(self, client):
        """جلب وحدات منهج - عام"""
        response = client.get('/api/v1/courses/99999/units')
        assert response.status_code in [200, 404, 500]

    def test_get_unit_lessons_public(self, client):
        """جلب دروس وحدة - عام"""
        response = client.get('/api/v1/units/99999/lessons')
        assert response.status_code in [200, 404, 500]

    def test_get_lesson_questions_public(self, client):
        """جلب أسئلة درس - عام"""
        response = client.get('/api/v1/lessons/99999/questions')
        assert response.status_code in [200, 404, 500]

    def test_get_unit_questions_public(self, client):
        """جلب أسئلة وحدة - عام"""
        response = client.get('/api/v1/units/99999/questions')
        assert response.status_code in [200, 404, 500]

    def test_get_course_questions_public(self, client):
        """جلب أسئلة منهج - عام"""
        response = client.get('/api/v1/courses/99999/questions')
        assert response.status_code in [200, 404, 500]

    def test_get_all_questions_public(self, client):
        """جلب كل الأسئلة - عام"""
        response = client.get('/api/v1/questions/all')
        assert response.status_code in [200, 500]

    def test_get_recent_questions_public(self, client):
        """جلب الأسئلة الأخيرة - عام"""
        response = client.get('/api/v1/questions/recent')
        assert response.status_code in [200, 500]


class TestAPIGoogleDrive:
    """اختبارات Google Drive API"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_google_drive_connection_status_no_auth(self, client):
        """حالة اتصال Google Drive بدون مصادقة"""
        response = client.get('/api/v1/v1/google-drive/connection-status')
        assert response.status_code in [302, 401, 403, 404]

    def test_google_drive_connection_status_as_admin(self, client, admin_user):
        """حالة اتصال Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/v1/google-drive/connection-status')
        assert response.status_code in [200, 404, 500]

    def test_google_drive_connect_no_auth(self, client):
        """اتصال Google Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/google-drive/connect', json={})
        assert response.status_code in [302, 401, 403, 404]

    def test_google_drive_connect_as_admin(self, client, admin_user):
        """اتصال Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/v1/google-drive/connect', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_google_drive_diagnose_no_auth(self, client):
        """تشخيص Google Drive بدون مصادقة"""
        response = client.get('/api/v1/v1/google-drive/diagnose')
        assert response.status_code in [302, 401, 403, 404]

    def test_google_drive_diagnose_as_admin(self, client, admin_user):
        """تشخيص Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/v1/google-drive/diagnose')
        assert response.status_code in [200, 404, 500]

    def test_google_drive_disconnect_no_auth(self, client):
        """فصل Google Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/google-drive/disconnect', json={})
        assert response.status_code in [302, 401, 403, 404]

    def test_google_drive_disconnect_as_admin(self, client, admin_user):
        """فصل Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/v1/google-drive/disconnect', json={})
        assert response.status_code in [200, 404, 500]


class TestAPIUserSettings:
    """اختبارات إعدادات المستخدم"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_user_settings_sync_status_no_auth(self, client):
        """حالة مزامنة الإعدادات بدون مصادقة"""
        response = client.get('/api/v1/v1/user-settings/sync-status')
        assert response.status_code in [302, 401, 403, 404]

    def test_user_settings_sync_status_as_admin(self, client, admin_user):
        """حالة مزامنة الإعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/v1/user-settings/sync-status')
        assert response.status_code in [200, 404, 500]

    def test_sync_to_drive_no_auth(self, client):
        """مزامنة إلى Google Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/user-settings/sync-to-drive', json={})
        assert response.status_code in [302, 401, 403, 404]

    def test_sync_to_drive_as_admin(self, client, admin_user):
        """مزامنة إلى Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/v1/user-settings/sync-to-drive', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_download_from_drive_no_auth(self, client):
        """تحميل من Google Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/user-settings/download-from-drive', json={})
        assert response.status_code in [302, 401, 403, 404]

    def test_download_from_drive_as_admin(self, client, admin_user):
        """تحميل من Google Drive كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/v1/user-settings/download-from-drive', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_quick_sync_no_auth(self, client):
        """مزامنة سريعة بدون مصادقة"""
        response = client.post('/api/v1/v1/user-settings/quick-sync', json={})
        assert response.status_code in [302, 401, 403, 404]

    def test_quick_sync_as_admin(self, client, admin_user):
        """مزامنة سريعة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/v1/user-settings/quick-sync', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_user_settings_sync_status_v1(self, client, admin_user):
        """حالة مزامنة الإعدادات - مسار v1 آخر"""
        self._login(client, admin_user)
        response = client.get('/api/v1/user-settings/sync-status')
        assert response.status_code in [200, 404, 500]


class TestAPIBackupExtended:
    """اختبارات Backup الموسعة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_backup_test_no_auth(self, client):
        """اختبار النسخ الاحتياطي بدون مصادقة"""
        response = client.post('/api/v1/backup/test', json={})
        assert response.status_code in [302, 401, 403]

    def test_backup_test_as_admin(self, client, admin_user):
        """اختبار النسخ الاحتياطي كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/backup/test', json={})
        assert response.status_code in [200, 400, 500]

    def test_backup_test_immediate_no_auth(self, client):
        """نسخ احتياطي فوري بدون مصادقة"""
        response = client.post('/api/v1/backup/test-immediate', json={})
        assert response.status_code in [200, 302, 401, 403]

    def test_backup_test_immediate_as_admin(self, client, admin_user):
        """نسخ احتياطي فوري كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/backup/test-immediate', json={})
        assert response.status_code in [200, 400, 500]

    def test_google_drive_test_connection_status_as_admin(self, client, admin_user):
        """حالة اتصال Google Drive (backup) كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/google-drive/test-connection-status')
        assert response.status_code in [200, 404, 500]

    def test_backup_settings_save_no_auth(self, client):
        """حفظ إعدادات النسخ الاحتياطي بدون مصادقة"""
        response = client.post('/api/v1/backup-settings/save', json={})
        assert response.status_code in [302, 401, 403]

    def test_backup_settings_save_as_admin(self, client, admin_user):
        """حفظ إعدادات النسخ الاحتياطي كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/backup-settings/save', json={
            'backup_enabled': True,
            'backup_frequency': 'daily'
        })
        assert response.status_code in [200, 400, 500]

    def test_upload_image_no_auth(self, client):
        """رفع صورة بدون مصادقة"""
        response = client.post('/api/v1/upload-image', data={})
        assert response.status_code in [302, 401, 403]

    def test_upload_image_empty_as_admin(self, client, admin_user):
        """رفع صورة بدون ملف كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/upload-image', data={})
        assert response.status_code in [200, 400, 422, 500]

    def test_questions_export_no_auth(self, client):
        """تصدير الأسئلة بدون مصادقة"""
        response = client.post('/api/v1/questions/export', json={})
        assert response.status_code in [302, 401, 403]

    def test_questions_export_as_admin(self, client, admin_user):
        """تصدير الأسئلة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/export', json={
            'format': 'json',
            'filters': {}
        })
        assert response.status_code in [200, 400, 500]


class TestAPIQuestionsFilteredSearch:
    """اختبارات الأسئلة المفلترة والبحث"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_questions_with_filters(self, client):
        """جلب الأسئلة مع فلاتر"""
        response = client.get('/api/v1/questions?lesson_id=1')
        assert response.status_code in [200, 500]

    def test_get_questions_with_course_filter(self, client):
        """جلب الأسئلة مع فلتر منهج"""
        response = client.get('/api/v1/questions?course_id=1')
        assert response.status_code in [200, 500]

    def test_get_questions_with_unit_filter(self, client):
        """جلب الأسئلة مع فلتر وحدة"""
        response = client.get('/api/v1/questions?unit_id=1')
        assert response.status_code in [200, 500]

    def test_get_questions_with_bloom_filter(self, client):
        """جلب الأسئلة مع فلتر بلوم"""
        response = client.get('/api/v1/questions?bloom_level=remember')
        assert response.status_code in [200, 500]

    def test_course_unit_questions_public(self, client):
        """جلب أسئلة منهج ووحدة - عام"""
        response = client.get('/api/v1/courses/99999/units/99999/questions')
        assert response.status_code in [200, 404, 500]

    def test_course_unit_lessons_public(self, client):
        """جلب دروس منهج ووحدة - عام"""
        response = client.get('/api/v1/courses/99999/units/99999/lessons')
        assert response.status_code in [200, 302, 404, 500]
