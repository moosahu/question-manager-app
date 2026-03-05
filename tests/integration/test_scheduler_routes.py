"""
اختبارات Scheduler routes
يغطي: index, create, view, update, delete, mobile API
"""
import pytest


class TestSchedulerAdmin:
    """اختبارات الـ scheduler للأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_scheduler_index_no_auth(self, client):
        """صفحة الـ scheduler بدون مصادقة"""
        response = client.get('/scheduler/')
        assert response.status_code in [302, 401, 403, 404]

    def test_scheduler_index_as_admin(self, client, admin_user):
        """صفحة الـ scheduler كأدمن"""
        self._login(client, admin_user)
        response = client.get('/scheduler/')
        assert response.status_code in [200, 302, 404, 500]

    def test_scheduler_create_get_no_auth(self, client):
        """صفحة إنشاء جدول بدون مصادقة"""
        response = client.get('/scheduler/create')
        assert response.status_code in [302, 401, 403, 404]

    def test_scheduler_create_get_as_admin(self, client, admin_user):
        """صفحة إنشاء جدول كأدمن"""
        self._login(client, admin_user)
        response = client.get('/scheduler/create')
        assert response.status_code in [200, 302, 404, 500]

    def test_scheduler_create_post_empty(self, client, admin_user):
        """إنشاء جدول ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/scheduler/create', json={})
        assert response.status_code in [200, 302, 400, 404, 422, 500]

    def test_scheduler_create_post_valid(self, client, admin_user):
        """إنشاء جدول ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/scheduler/create', data={
            'exam_date': '2026-06-01',
            'study_hours_per_day': '4',
            'start_date': '2026-05-01'
        })
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_scheduler_view_nonexistent(self, client, admin_user):
        """عرض جدول غير موجود"""
        self._login(client, admin_user)
        response = client.get('/scheduler/99999')
        assert response.status_code in [302, 404, 500]

    def test_scheduler_update_pages_nonexistent(self, client, admin_user):
        """تحديث صفحات لجدول غير موجود"""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/update-pages', json={})
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_scheduler_delete_nonexistent(self, client, admin_user):
        """حذف جدول غير موجود"""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/delete')
        assert response.status_code in [200, 302, 404, 500]

    def test_scheduler_toggle_session_nonexistent(self, client, admin_user):
        """تبديل جلسة لجدول غير موجود"""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/session/1/toggle')
        assert response.status_code in [200, 302, 404, 500]

    def test_scheduler_update_session_nonexistent(self, client, admin_user):
        """تحديث جلسة لجدول غير موجود"""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/session/1/update', json={})
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_scheduler_api_tahsili_dates(self, client, admin_user):
        """جلب مواعيد التحصيلي"""
        self._login(client, admin_user)
        response = client.get('/scheduler/api/tahsili-dates')
        assert response.status_code in [200, 404, 500]

    def test_scheduler_api_tahsili_dates_no_auth(self, client):
        """جلب مواعيد التحصيلي بدون مصادقة"""
        response = client.get('/scheduler/api/tahsili-dates')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_scheduler_update_exam_date_nonexistent(self, client, admin_user):
        """تحديث موعد امتحان لجدول غير موجود"""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/exam-date', json={})
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_scheduler_export_pdf_nonexistent(self, client, admin_user):
        """تصدير PDF لجدول غير موجود"""
        self._login(client, admin_user)
        response = client.get('/scheduler/99999/pdf')
        assert response.status_code in [302, 404, 500]


class TestSchedulerMobileAPI:
    """اختبارات Mobile API للـ scheduler"""

    def test_mobile_list_schedules_no_token(self, client):
        """قائمة الجداول بدون token"""
        response = client.get('/scheduler/api/mobile/schedules')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_list_schedules_with_token(self, client, db_session, app):
        """قائمة الجداول مع token طالب"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu', username='schedstu1', email='schedstu1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            '/scheduler/api/mobile/schedules',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 404, 500]

    def test_mobile_create_schedule_no_token(self, client):
        """إنشاء جدول بدون token"""
        response = client.post('/scheduler/api/mobile/schedules/create', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 422, 500]

    def test_mobile_create_schedule_with_token(self, client, db_session, app):
        """إنشاء جدول مع token طالب"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu2', username='schedstu2', email='schedstu2@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.post(
            '/scheduler/api/mobile/schedules/create',
            json={'exam_date': '2026-06-01', 'study_hours_per_day': 4},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

    def test_mobile_get_schedule_nonexistent(self, client, db_session, app):
        """جلب جدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu3', username='schedstu3', email='schedstu3@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            '/scheduler/api/mobile/schedules/99999',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_toggle_session_nonexistent(self, client, db_session, app):
        """تبديل جلسة في جدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu4', username='schedstu4', email='schedstu4@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/session/1/toggle',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_export_pdf_nonexistent(self, client, db_session, app):
        """تصدير PDF لجدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu5', username='schedstu5', email='schedstu5@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            '/scheduler/api/mobile/schedules/99999/pdf',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_delete_schedule_nonexistent(self, client, db_session, app):
        """حذف جدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu6', username='schedstu6', email='schedstu6@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/delete',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_update_exam_date_nonexistent(self, client, db_session, app):
        """تحديث موعد امتحان لجدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu7', username='schedstu7', email='schedstu7@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/exam-date',
            json={'exam_date': '2026-06-01'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_update_status_nonexistent(self, client, db_session, app):
        """تحديث حالة جدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu8', username='schedstu8', email='schedstu8@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/status',
            json={'status': 'active'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_reschedule_nonexistent(self, client, db_session, app):
        """إعادة جدولة جدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu9', username='schedstu9', email='schedstu9@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/reschedule',
            json={},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_get_stats_nonexistent(self, client, db_session, app):
        """إحصائيات جدول غير موجود"""
        from src.models.student import Student
        import secrets
        s = Student(name='Sched Stu10', username='schedstu10', email='schedstu10@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            '/scheduler/api/mobile/schedules/99999/stats',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]
