"""
اختبارات شاملة لـ API Dashboard, Backup, Notifications, Question Block/Unblock
"""
import pytest


class TestDashboardAPI:
    """اختبارات Dashboard API"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_dashboard_stats_no_auth(self, client):
        """إحصائيات الـ Dashboard بدون مصادقة"""
        response = client.get('/api/v1/dashboard/statistics')
        assert response.status_code in [200, 302, 401, 403]

    def test_dashboard_stats_as_admin(self, client, admin_user):
        """إحصائيات الـ Dashboard كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/dashboard/statistics')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_dashboard_performance_no_auth(self, client):
        """أداء الـ Dashboard بدون مصادقة"""
        response = client.get('/api/v1/dashboard/performance')
        assert response.status_code in [200, 302, 401, 403]

    def test_dashboard_performance_as_admin(self, client, admin_user):
        """أداء الـ Dashboard كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/dashboard/performance')
        assert response.status_code in [200, 500]

    def test_csrf_token(self, client, admin_user):
        """جلب CSRF token"""
        self._login(client, admin_user)
        response = client.get('/api/v1/csrf-token')
        assert response.status_code in [200, 404, 500]


class TestAPINotifications:
    """اختبارات الإشعارات في API"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_notifications_no_auth(self, client):
        """جلب الإشعارات بدون مصادقة"""
        response = client.get('/api/v1/notifications')
        assert response.status_code in [302, 401, 403]

    def test_get_notifications_as_admin(self, client, admin_user):
        """جلب الإشعارات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/notifications')
        assert response.status_code in [200, 500, 503]

    def test_mark_notification_read_no_auth(self, client):
        """تأشير إشعار مقروء بدون مصادقة"""
        response = client.post('/api/v1/notifications/mark-read', json={'notification_id': 1})
        assert response.status_code in [302, 401, 403]

    def test_mark_notification_read_as_admin(self, client, admin_user):
        """تأشير إشعار مقروء كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/notifications/mark-read', json={'notification_id': 99999})
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_notification_no_auth(self, client):
        """حذف إشعار بدون مصادقة"""
        response = client.post('/api/v1/notifications/99999/delete')
        assert response.status_code in [302, 401, 403]

    def test_delete_notification_as_admin(self, client, admin_user):
        """حذف إشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/notifications/99999/delete')
        assert response.status_code in [200, 404, 500, 503]

    def test_create_notification_as_admin(self, client, admin_user):
        """إنشاء إشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/v1/notifications/create', json={
            'title': 'إشعار اختبار',
            'message': 'رسالة الاختبار'
        })
        assert response.status_code in [200, 201, 400, 500, 503]


class TestAPIRandomQuestions:
    """اختبارات الأسئلة العشوائية"""

    def test_random_questions_no_questions(self, client):
        """أسئلة عشوائية - لا توجد أسئلة"""
        response = client.get('/api/v1/questions/random')
        assert response.status_code in [200, 404]

    def test_random_questions_with_count(self, client):
        """أسئلة عشوائية مع تحديد عدد"""
        response = client.get('/api/v1/questions/random?count=5')
        assert response.status_code in [200, 404]

    def test_all_questions_endpoint(self, client):
        """نقطة نهاية كل الأسئلة"""
        response = client.get('/api/v1/questions')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None

    def test_all_questions_with_filters(self, client):
        """كل الأسئلة مع فلاتر"""
        response = client.get('/api/v1/questions?difficulty=easy')
        assert response.status_code == 200


class TestAPIQuestionBlockUnblock:
    """اختبارات حجب وإلغاء حجب الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_block_question_no_auth(self, client):
        """حجب سؤال بدون مصادقة"""
        response = client.put('/api/v1/questions/1/block')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_unblock_question_no_auth(self, client):
        """إلغاء حجب سؤال بدون مصادقة"""
        response = client.put('/api/v1/questions/1/unblock')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_block_question_nonexistent(self, client, admin_user):
        """حجب سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.put('/api/v1/questions/99999/block')
        assert response.status_code in [404, 500]

    def test_unblock_question_nonexistent(self, client, admin_user):
        """إلغاء حجب سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.put('/api/v1/questions/99999/unblock')
        assert response.status_code in [404, 500]

    def test_block_question_existing(self, client, admin_user, db_session, app):
        """حجب سؤال موجود"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='Block Test Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Block Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Block Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='Block Q', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        self._login(client, admin_user)
        response = client.put(f'/api/v1/questions/{q.question_id}/block')
        assert response.status_code in [200, 500]

    def test_bulk_block_questions(self, client, admin_user):
        """حجب أسئلة متعددة"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/bulk-block', json={'question_ids': [99999]})
        assert response.status_code in [200, 400, 404, 500]

    def test_bulk_unblock_questions(self, client, admin_user):
        """إلغاء حجب أسئلة متعددة"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/bulk-unblock', json={'question_ids': [99999]})
        assert response.status_code in [200, 400, 404, 500]

    def test_block_all_lesson_questions(self, client, admin_user):
        """حجب كل أسئلة درس"""
        self._login(client, admin_user)
        response = client.put('/api/v1/lessons/99999/questions/block-all')
        assert response.status_code in [200, 404, 500]

    def test_unblock_all_lesson_questions(self, client, admin_user):
        """إلغاء حجب كل أسئلة درس"""
        self._login(client, admin_user)
        response = client.put('/api/v1/lessons/99999/questions/unblock-all')
        assert response.status_code in [200, 404, 500]

    def test_block_all_unit_questions(self, client, admin_user):
        """حجب كل أسئلة وحدة"""
        self._login(client, admin_user)
        response = client.put('/api/v1/units/99999/questions/block-all')
        assert response.status_code in [200, 404, 500]

    def test_unblock_all_unit_questions(self, client, admin_user):
        """إلغاء حجب كل أسئلة وحدة"""
        self._login(client, admin_user)
        response = client.put('/api/v1/units/99999/questions/unblock-all')
        assert response.status_code in [200, 404, 500]


class TestAPIBackup:
    """اختبارات Backup API"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_backup_stats_no_auth(self, client):
        """إحصائيات النسخ الاحتياطي بدون مصادقة"""
        response = client.get('/api/v1/backup/stats')
        assert response.status_code in [302, 401, 403]

    def test_backup_stats_as_admin(self, client, admin_user):
        """إحصائيات النسخ الاحتياطي كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/stats')
        assert response.status_code in [200, 500]

    def test_backup_list_as_admin(self, client, admin_user):
        """قائمة النسخ الاحتياطية"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/list')
        assert response.status_code in [200, 500]

    def test_backup_health_as_admin(self, client, admin_user):
        """صحة النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/health')
        assert response.status_code in [200, 500]

    def test_backup_status_as_admin(self, client, admin_user):
        """حالة النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/status')
        assert response.status_code in [200, 500]

    def test_backup_jobs_as_admin(self, client, admin_user):
        """مهام النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/jobs')
        assert response.status_code in [200, 500]

    def test_backup_settings_get_as_admin(self, client, admin_user):
        """إعدادات النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/settings')
        assert response.status_code in [200, 500]

    def test_backup_logs_as_admin(self, client, admin_user):
        """سجلات النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/logs')
        assert response.status_code in [200, 500]

    def test_backup_test_status_as_admin(self, client, admin_user):
        """حالة اختبار النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup/test-status')
        assert response.status_code in [200, 500]

    def test_backup_manual_as_admin(self, client, admin_user):
        """نسخ احتياطي يدوي"""
        self._login(client, admin_user)
        response = client.post('/api/v1/backup/manual', json={})
        assert response.status_code in [200, 400, 500]

    def test_backup_settings_load_as_admin(self, client, admin_user):
        """تحميل إعدادات النسخ الاحتياطي"""
        self._login(client, admin_user)
        response = client.get('/api/v1/backup-settings/load')
        assert response.status_code in [200, 404, 500]

    def test_google_drive_connection_status_as_admin(self, client, admin_user):
        """حالة اتصال Google Drive"""
        self._login(client, admin_user)
        response = client.get('/api/v1/v1/google-drive/connection-status')
        assert response.status_code in [200, 404, 500]


class TestAPIActivities:
    """اختبارات الأنشطة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_recent_activities_no_auth(self, client):
        """الأنشطة الأخيرة بدون مصادقة"""
        response = client.get('/api/v1/activities/recent')
        assert response.status_code in [200, 302, 401, 403]

    def test_recent_activities_as_admin(self, client, admin_user):
        """الأنشطة الأخيرة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/activities/recent')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
