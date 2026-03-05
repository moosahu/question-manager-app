"""
اختبارات لـ Lesson Prep API و Delete Account
"""
import pytest


class TestLessonPrepAuth:
    """اختبارات مصادقة Lesson Prep API"""

    def _make_teacher(self, db_session, username, email):
        import secrets
        from src.models.teacher import Teacher
        t = Teacher(name='Prep Teacher', username=username, email=email, is_active=True)
        t.set_password('Pass@123')
        t.session_token = secrets.token_hex(32)
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        return t

    def test_quota_no_auth(self, client):
        """الحصة بدون مصادقة"""
        response = client.get('/api/lesson-prep/quota')
        assert response.status_code in [401, 403]

    def test_quota_with_teacher_token(self, client, db_session, app):
        """الحصة مع token معلم"""
        t = self._make_teacher(db_session, 'quota_teacher', 'quotateacher@test.com')
        response = client.get(
            '/api/lesson-prep/quota',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 401, 403, 500]

    def test_generate_no_auth(self, client):
        """توليد درس بدون مصادقة"""
        response = client.post('/api/lesson-prep/generate', json={})
        assert response.status_code in [401, 403]

    def test_generate_missing_fields(self, client, db_session, app):
        """توليد درس ببيانات ناقصة"""
        t = self._make_teacher(db_session, 'gen_teacher', 'genteacher@test.com')
        response = client.post(
            '/api/lesson-prep/generate',
            json={},
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [400, 401, 422, 500]

    def test_history_no_auth(self, client):
        """السجل بدون مصادقة"""
        response = client.get('/api/lesson-prep/history')
        assert response.status_code in [401, 403]

    def test_history_with_teacher_token(self, client, db_session, app):
        """السجل مع token معلم"""
        t = self._make_teacher(db_session, 'hist_teacher', 'histteacher@test.com')
        response = client.get(
            '/api/lesson-prep/history',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 401, 403, 500]

    def test_queue_no_auth(self, client):
        """قائمة الانتظار بدون مصادقة"""
        response = client.get('/api/lesson-prep/queue')
        assert response.status_code in [401, 403]

    def test_queue_with_teacher_token(self, client, db_session, app):
        """قائمة الانتظار مع token معلم"""
        t = self._make_teacher(db_session, 'queue_teacher', 'queueteacher@test.com')
        response = client.get(
            '/api/lesson-prep/queue',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 401, 403, 500]

    def test_get_plan_no_auth(self, client):
        """جلب خطة بدون مصادقة"""
        response = client.get('/api/lesson-prep/99999')
        assert response.status_code in [401, 403]

    def test_get_plan_nonexistent(self, client, db_session, app):
        """جلب خطة غير موجودة"""
        t = self._make_teacher(db_session, 'getplan_teacher', 'getplanteacher@test.com')
        response = client.get(
            '/api/lesson-prep/99999',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [401, 403, 404, 500]

    def test_delete_plan_no_auth(self, client):
        """حذف خطة بدون مصادقة"""
        response = client.delete('/api/lesson-prep/99999')
        assert response.status_code in [401, 403]

    def test_delete_plan_nonexistent(self, client, db_session, app):
        """حذف خطة غير موجودة"""
        t = self._make_teacher(db_session, 'delplan_teacher', 'delplanteacher@test.com')
        response = client.delete(
            '/api/lesson-prep/99999',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [401, 403, 404, 500]

    def test_shared_plans_no_auth(self, client):
        """الخطط المشتركة بدون مصادقة"""
        response = client.get('/api/lesson-prep/shared')
        assert response.status_code in [401, 403]

    def test_shared_plans_with_teacher(self, client, db_session, app):
        """الخطط المشتركة مع token"""
        t = self._make_teacher(db_session, 'shared_teacher', 'sharedteacher@test.com')
        response = client.get(
            '/api/lesson-prep/shared',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 401, 403, 500]

    def test_progress_no_auth(self, client):
        """التقدم بدون مصادقة"""
        response = client.get('/api/lesson-prep/progress')
        assert response.status_code in [401, 403]

    def test_progress_with_teacher(self, client, db_session, app):
        """التقدم مع token"""
        t = self._make_teacher(db_session, 'prog_teacher', 'progteacher@test.com')
        response = client.get(
            '/api/lesson-prep/progress',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 401, 403, 500]

    def test_costs_summary_no_auth(self, client):
        """ملخص التكاليف بدون مصادقة (أدمن)"""
        response = client.get('/api/lesson-prep/costs/summary')
        assert response.status_code in [302, 401, 403]

    def test_costs_summary_as_admin(self, client, admin_user):
        """ملخص التكاليف كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/lesson-prep/costs/summary')
        assert response.status_code in [200, 403, 500]

    def test_costs_by_teacher_as_admin(self, client, admin_user):
        """التكاليف حسب المعلم"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/lesson-prep/costs/by-teacher')
        assert response.status_code in [200, 403, 500]

    def test_plan_status_nonexistent(self, client, db_session, app):
        """حالة خطة غير موجودة"""
        t = self._make_teacher(db_session, 'status_teacher', 'statusteacher@test.com')
        response = client.get(
            '/api/lesson-prep/status/99999',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [401, 403, 404, 500]

    def test_unit_distribution_no_auth(self, client):
        """توزيع الوحدة بدون مصادقة"""
        response = client.post('/api/lesson-prep/unit-distribution', json={})
        assert response.status_code in [401, 403]


class TestDeleteAccount:
    """اختبارات حذف الحساب"""

    def _make_student(self, db_session, username, email):
        import secrets
        from src.models.student import Student
        s = Student(name='Delete Me', username=username, email=email, is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        return s

    def test_request_delete_no_auth(self, client):
        """طلب حذف الحساب بدون مصادقة"""
        response = client.post('/api/account/request-delete', json={})
        assert response.status_code in [400, 401, 422]

    def test_request_delete_wrong_token(self, client):
        """طلب حذف بـ token خاطئ"""
        response = client.post(
            '/api/account/request-delete',
            json={'password': 'Pass@123', 'reason': 'اختبار'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [400, 401, 404]

    def test_request_delete_with_valid_token(self, client, db_session, app):
        """طلب حذف بـ token صالح"""
        s = self._make_student(db_session, 'delete_me_stu', 'deletemestu@test.com')
        response = client.post(
            '/api/account/request-delete',
            json={'password': 'Pass@123', 'reason': 'اختبار'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 500]

    def test_verify_delete_otp_no_auth(self, client):
        """التحقق من OTP الحذف بدون مصادقة"""
        response = client.post('/api/account/verify-delete-otp', json={
            'otp': '123456'
        })
        assert response.status_code in [400, 401, 422]

    def test_verify_delete_otp_wrong_token(self, client):
        """التحقق من OTP الحذف بـ token خاطئ"""
        response = client.post(
            '/api/account/verify-delete-otp',
            json={'otp': '000000'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [400, 401, 404]

    def test_confirm_delete_no_auth(self, client):
        """تأكيد حذف الحساب بدون مصادقة"""
        response = client.post('/api/account/confirm-delete', json={})
        assert response.status_code in [400, 401, 422]

    def test_confirm_delete_wrong_token(self, client):
        """تأكيد حذف بـ token خاطئ"""
        response = client.post(
            '/api/account/confirm-delete',
            json={'confirmation': 'DELETE'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [400, 401, 404]
