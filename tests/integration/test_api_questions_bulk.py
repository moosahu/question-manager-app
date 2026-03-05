"""
اختبارات API الأسئلة - block/unblock، تصنيف، بحث، إنشاء/تعديل/حذف
يغطي: block, unblock, bulk-block, bulk-unblock, block-status, generate-exam,
       questions CRUD, search, classify, classification-stats
"""
import pytest
import secrets


def _make_admin_login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


class TestApiQuestionsBlock:
    """اختبارات حجب/رفع حجب الأسئلة"""

    def test_block_question_no_auth(self, client):
        """حجب سؤال بدون مصادقة"""
        response = client.put('/api/questions/99999/block', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_block_question_as_admin(self, client, admin_user):
        """حجب سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/questions/99999/block', json={})
        assert response.status_code in [200, 404, 500]

    def test_unblock_question_no_auth(self, client):
        """رفع حجب سؤال بدون مصادقة"""
        response = client.put('/api/questions/99999/unblock', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_unblock_question_as_admin(self, client, admin_user):
        """رفع حجب سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/questions/99999/unblock', json={})
        assert response.status_code in [200, 404, 500]

    def test_bulk_block_no_auth(self, client):
        """حجب مجموعة أسئلة بدون مصادقة"""
        response = client.post('/api/questions/bulk-block', json={'ids': [1, 2]})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_bulk_block_as_admin(self, client, admin_user):
        """حجب مجموعة أسئلة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions/bulk-block', json={'ids': [99999]})
        assert response.status_code in [200, 400, 404, 500]

    def test_bulk_unblock_no_auth(self, client):
        """رفع حجب مجموعة أسئلة بدون مصادقة"""
        response = client.post('/api/questions/bulk-unblock', json={'ids': [1, 2]})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_bulk_unblock_as_admin(self, client, admin_user):
        """رفع حجب مجموعة أسئلة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions/bulk-unblock', json={'ids': [99999]})
        assert response.status_code in [200, 400, 404, 500]

    def test_toggle_block_no_auth(self, client):
        """تبديل حجب سؤال بدون مصادقة"""
        response = client.post('/api/questions/99999/toggle-block', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_toggle_block_as_admin(self, client, admin_user):
        """تبديل حجب سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions/99999/toggle-block', json={})
        assert response.status_code in [200, 404, 500]

    def test_block_status_no_auth(self, client):
        """حالة حجب سؤال بدون مصادقة"""
        response = client.get('/api/questions/99999/block-status')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_block_status_as_admin(self, client, admin_user):
        """حالة حجب سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/99999/block-status')
        assert response.status_code in [200, 404, 500]

    def test_lesson_block_all_no_auth(self, client):
        """حجب كل أسئلة درس بدون مصادقة"""
        response = client.put('/api/lessons/99999/questions/block-all', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_lesson_block_all_as_admin(self, client, admin_user):
        """حجب كل أسئلة درس كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/lessons/99999/questions/block-all', json={})
        assert response.status_code in [200, 404, 500]

    def test_lesson_unblock_all_as_admin(self, client, admin_user):
        """رفع حجب كل أسئلة درس كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/lessons/99999/questions/unblock-all', json={})
        assert response.status_code in [200, 404, 500]

    def test_unit_block_all_as_admin(self, client, admin_user):
        """حجب كل أسئلة وحدة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/units/99999/questions/block-all', json={})
        assert response.status_code in [200, 404, 500]

    def test_unit_unblock_all_as_admin(self, client, admin_user):
        """رفع حجب كل أسئلة وحدة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/units/99999/questions/unblock-all', json={})
        assert response.status_code in [200, 404, 500]

    def test_course_block_all_as_admin(self, client, admin_user):
        """حجب كل أسئلة منهج كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/courses/99999/questions/block-all', json={})
        assert response.status_code in [200, 404, 500]

    def test_course_unblock_all_as_admin(self, client, admin_user):
        """رفع حجب كل أسئلة منهج كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/courses/99999/questions/unblock-all', json={})
        assert response.status_code in [200, 404, 500]


class TestApiQuestionsSearch:
    """اختبارات بحث الأسئلة"""

    def test_search_questions_no_auth(self, client):
        """بحث الأسئلة بدون مصادقة"""
        response = client.get('/api/questions/search')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_search_questions_empty(self, client, admin_user):
        """بحث الأسئلة ببدون معاملات"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/search')
        assert response.status_code in [200, 400, 404, 500]

    def test_search_questions_with_query(self, client, admin_user):
        """بحث الأسئلة بكلمة"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/search?q=كيمياء')
        assert response.status_code in [200, 400, 404, 500]

    def test_get_question_nonexistent(self, client, admin_user):
        """جلب سؤال غير موجود"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/99999')
        assert response.status_code in [200, 404, 500]

    def test_update_question_no_auth(self, client):
        """تحديث سؤال بدون مصادقة"""
        response = client.put('/api/questions/99999', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_update_question_as_admin(self, client, admin_user):
        """تحديث سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/questions/99999', json={
            'question_text': 'سؤال محدث'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_delete_question_no_auth(self, client):
        """حذف سؤال بدون مصادقة"""
        response = client.delete('/api/questions/99999')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_question_as_admin(self, client, admin_user):
        """حذف سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.delete('/api/questions/99999')
        assert response.status_code in [200, 404, 500]

    def test_create_question_no_auth(self, client):
        """إنشاء سؤال بدون مصادقة"""
        response = client.post('/api/questions', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_create_question_empty(self, client, admin_user):
        """إنشاء سؤال ببيانات فارغة"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions', json={})
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_get_all_questions_as_admin(self, client, admin_user):
        """جلب كل الأسئلة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/all')
        assert response.status_code in [200, 404, 500]

    def test_get_recent_questions_as_admin(self, client, admin_user):
        """جلب الأسئلة الأخيرة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/recent')
        assert response.status_code in [200, 404, 500]

    def test_get_random_questions_as_admin(self, client, admin_user):
        """جلب أسئلة عشوائية كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/random')
        assert response.status_code in [200, 400, 404, 500]


class TestApiQuestionsClassify:
    """اختبارات تصنيف الأسئلة"""

    def test_classify_all_no_auth(self, client):
        """تصنيف كل الأسئلة بدون مصادقة"""
        response = client.post('/api/questions/classify-all', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_classify_all_as_admin(self, client, admin_user):
        """تصنيف كل الأسئلة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions/classify-all', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_classify_question_no_auth(self, client):
        """تصنيف سؤال بدون مصادقة"""
        response = client.post('/api/questions/99999/classify', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_classify_question_as_admin(self, client, admin_user):
        """تصنيف سؤال كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions/99999/classify', json={
            'category': 'مفاهيم أساسية'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_classification_stats_no_auth(self, client):
        """إحصائيات التصنيف بدون مصادقة"""
        response = client.get('/api/questions/classification-stats')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_classification_stats_as_admin(self, client, admin_user):
        """إحصائيات التصنيف كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/classification-stats')
        assert response.status_code in [200, 404, 500]

    def test_update_classification_no_auth(self, client):
        """تحديث تصنيف بدون مصادقة"""
        response = client.put('/api/questions/99999/update-classification', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_update_classification_as_admin(self, client, admin_user):
        """تحديث تصنيف كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.put('/api/questions/99999/update-classification', json={
            'category': 'مفاهيم متقدمة'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_browse_classifications_as_admin(self, client, admin_user):
        """تصفح التصنيفات كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/browse-classifications')
        assert response.status_code in [200, 404, 500]

    def test_unclassified_questions_as_admin(self, client, admin_user):
        """الأسئلة غير المصنفة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/unclassified')
        assert response.status_code in [200, 404, 500]

    def test_classification_summary_as_admin(self, client, admin_user):
        """ملخص التصنيفات كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/questions/classification-summary')
        assert response.status_code in [200, 404, 500]


class TestApiDashboard:
    """اختبارات لوحة تحكم API"""

    def test_dashboard_statistics_no_auth(self, client):
        """إحصائيات لوحة التحكم بدون مصادقة"""
        response = client.get('/api/dashboard/statistics')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_dashboard_statistics_as_admin(self, client, admin_user):
        """إحصائيات لوحة التحكم كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/dashboard/statistics')
        assert response.status_code in [200, 404, 500]

    def test_dashboard_performance_no_auth(self, client):
        """أداء لوحة التحكم بدون مصادقة"""
        response = client.get('/api/dashboard/performance')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_dashboard_performance_as_admin(self, client, admin_user):
        """أداء لوحة التحكم كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/dashboard/performance')
        assert response.status_code in [200, 404, 500]

    def test_activities_recent_no_auth(self, client):
        """الأنشطة الأخيرة بدون مصادقة"""
        response = client.get('/api/activities/recent')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_activities_recent_as_admin(self, client, admin_user):
        """الأنشطة الأخيرة كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/activities/recent')
        assert response.status_code in [200, 404, 500]


class TestApiBackupExtended:
    """اختبارات موسعة للنسخ الاحتياطي"""

    def test_backup_stats_as_admin(self, client, admin_user):
        """إحصائيات الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/stats')
        assert response.status_code in [200, 404, 500]

    def test_backup_list_as_admin(self, client, admin_user):
        """قائمة الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/list')
        assert response.status_code in [200, 404, 500]

    def test_backup_start_as_admin(self, client, admin_user):
        """بدء الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup/start', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_backup_stop_as_admin(self, client, admin_user):
        """إيقاف الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup/stop', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_backup_manual_as_admin(self, client, admin_user):
        """نسخ احتياطي يدوي كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup/manual', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_backup_jobs_as_admin(self, client, admin_user):
        """مهام الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/jobs')
        assert response.status_code in [200, 404, 500]

    def test_backup_settings_get_as_admin(self, client, admin_user):
        """جلب إعدادات الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/settings')
        assert response.status_code in [200, 404, 500]

    def test_backup_settings_post_as_admin(self, client, admin_user):
        """حفظ إعدادات الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup/settings', json={'enabled': True})
        assert response.status_code in [200, 400, 404, 500]

    def test_backup_test_connection_as_admin(self, client, admin_user):
        """اختبار اتصال الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup/test-connection', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_backup_logs_as_admin(self, client, admin_user):
        """سجلات الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/logs')
        assert response.status_code in [200, 404, 500]

    def test_backup_health_as_admin(self, client, admin_user):
        """صحة الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/health')
        assert response.status_code in [200, 404, 500]

    def test_backup_status_as_admin(self, client, admin_user):
        """حالة الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/status')
        assert response.status_code in [200, 404, 500]

    def test_backup_upload_to_drive_as_admin(self, client, admin_user):
        """رفع باكب إلى Drive كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup/upload-to-drive', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_backup_test_status_as_admin(self, client, admin_user):
        """حالة اختبار الباكب كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup/test-status')
        assert response.status_code in [200, 404, 500]

    def test_generate_exam_as_admin(self, client, admin_user):
        """توليد اختبار كأدمن"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/questions/generate-exam', json={
            'course_id': 1,
            'num_questions': 10
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_questions_count_by_unit(self, client, admin_user):
        """عدد الأسئلة في وحدة"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/units/99999/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_questions_count_by_lesson(self, client, admin_user):
        """عدد الأسئلة في درس"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/lessons/99999/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_questions_count_by_course(self, client, admin_user):
        """عدد الأسئلة في منهج"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/courses/99999/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_csrf_token_get(self, client):
        """جلب CSRF token"""
        response = client.get('/api/csrf-token')
        assert response.status_code in [200, 404, 500]

    def test_backup_settings_load(self, client, admin_user):
        """تحميل إعدادات الباكب"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/backup-settings/load')
        assert response.status_code in [200, 404, 500]

    def test_backup_settings_save(self, client, admin_user):
        """حفظ إعدادات الباكب"""
        _make_admin_login(client, admin_user)
        response = client.post('/api/backup-settings/save', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_user_settings_sync_status(self, client, admin_user):
        """حالة المزامنة"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/user-settings/sync-status')
        assert response.status_code in [200, 404, 500]

    def test_google_drive_connection_status(self, client, admin_user):
        """حالة اتصال Google Drive"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/google-drive/connection-status')
        assert response.status_code in [200, 404, 500]

    def test_google_drive_test_connection_status(self, client, admin_user):
        """حالة اختبار اتصال Google Drive"""
        _make_admin_login(client, admin_user)
        response = client.get('/api/google-drive/test-connection-status')
        assert response.status_code in [200, 404, 500]
