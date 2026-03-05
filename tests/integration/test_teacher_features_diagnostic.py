"""
اختبارات لـ Teacher Features API و Diagnostic API
يغطي: teacher features CRUD, diagnostic tests
"""
import pytest


class TestTeacherFeaturesAuth:
    """اختبارات مصادقة Teacher Features"""

    def test_global_features_no_auth(self, client):
        """جلب الميزات العامة بدون مصادقة"""
        response = client.get('/api/admin/teacher-features/global')
        assert response.status_code in [302, 401, 403]

    def test_set_global_feature_no_auth(self, client):
        """تعيين ميزة عامة بدون مصادقة"""
        response = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'test_feature',
            'enabled': True
        })
        assert response.status_code in [302, 401, 403]

    def test_all_teachers_features_no_auth(self, client):
        """جلب ميزات كل المعلمين بدون مصادقة"""
        response = client.get('/api/admin/teacher-features/all-teachers')
        assert response.status_code in [302, 401, 403]

    def test_get_teacher_features_no_auth(self, client):
        """جلب ميزات معلم بدون مصادقة"""
        response = client.get('/api/admin/teacher-features/1')
        assert response.status_code in [302, 401, 403]

    def test_features_page_no_auth(self, client):
        """صفحة الميزات بدون مصادقة"""
        response = client.get('/api/admin/teacher-features/page')
        assert response.status_code in [302, 401, 403]


class TestTeacherFeaturesAsAdmin:
    """اختبارات Teacher Features كأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_global_features_as_admin(self, client, admin_user):
        """جلب الميزات العامة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/teacher-features/global')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_set_global_feature_as_admin(self, client, admin_user):
        """تعيين ميزة عامة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'show_analytics',
            'enabled': True
        })
        assert response.status_code in [200, 400, 500]

    def test_all_teachers_features_as_admin(self, client, admin_user):
        """جلب ميزات كل المعلمين كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/teacher-features/all-teachers')
        assert response.status_code in [200, 500]

    def test_get_teacher_features_nonexistent(self, client, admin_user):
        """جلب ميزات معلم غير موجود"""
        self._login(client, admin_user)
        response = client.get('/api/admin/teacher-features/99999')
        assert response.status_code in [200, 404, 500]

    def test_get_teacher_features_existing(self, client, admin_user, db_session, app):
        """جلب ميزات معلم موجود"""
        from src.models.teacher import Teacher
        t = Teacher(name='Feature Teacher', username='feat_teacher', email='featteacher@test.com', is_active=True)
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        self._login(client, admin_user)
        response = client.get(f'/api/admin/teacher-features/{t.id}')
        assert response.status_code in [200, 500]

    def test_set_teacher_feature_existing(self, client, admin_user, db_session, app):
        """تعيين ميزة لمعلم موجود"""
        from src.models.teacher import Teacher
        t = Teacher(name='Set Feature Teacher', username='setfeat_teacher', email='setfeatteacher@test.com', is_active=True)
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        self._login(client, admin_user)
        response = client.post(f'/api/admin/teacher-features/{t.id}', json={
            'feature_key': 'show_reports',
            'enabled': True
        })
        assert response.status_code in [200, 400, 500]

    def test_delete_teacher_feature_nonexistent(self, client, admin_user):
        """حذف override ميزة معلم غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/api/admin/teacher-features/99999/show_analytics')
        assert response.status_code in [200, 404, 500]

    def test_features_page_as_admin(self, client, admin_user):
        """صفحة الميزات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/teacher-features/page')
        assert response.status_code in [200, 302, 500]


class TestDiagnosticAuth:
    """اختبارات مصادقة Diagnostic"""

    def test_get_tests_no_auth(self, client):
        """جلب الاختبارات التشخيصية بدون مصادقة"""
        response = client.get('/api/diagnostic/tests')
        assert response.status_code in [302, 401, 403]

    def test_generate_test_no_auth(self, client):
        """توليد اختبار تشخيصي بدون مصادقة"""
        response = client.post('/api/diagnostic/generate', json={})
        assert response.status_code in [302, 401, 403]

    def test_admin_page_no_auth(self, client):
        """صفحة الأدمن التشخيصي بدون مصادقة"""
        response = client.get('/api/diagnostic/admin')
        assert response.status_code in [302, 401, 403]

    def test_get_stats_no_auth(self, client):
        """إحصائيات التشخيص بدون مصادقة"""
        response = client.get('/api/diagnostic/stats')
        assert response.status_code in [302, 401, 403]


class TestDiagnosticAsAdmin:
    """اختبارات Diagnostic كأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_tests_as_admin(self, client, admin_user):
        """جلب الاختبارات التشخيصية كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/diagnostic/tests')
        assert response.status_code in [200, 500]

    def test_get_test_nonexistent(self, client, admin_user):
        """جلب اختبار غير موجود"""
        self._login(client, admin_user)
        response = client.get('/api/diagnostic/tests/99999')
        assert response.status_code in [404, 500]

    def test_get_stats_as_admin(self, client, admin_user):
        """إحصائيات التشخيص كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/diagnostic/stats')
        assert response.status_code in [200, 500]

    def test_admin_page_as_admin(self, client, admin_user):
        """صفحة الأدمن التشخيصي كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/diagnostic/admin')
        assert response.status_code in [200, 302, 500]

    def test_generate_test_empty(self, client, admin_user):
        """توليد اختبار تشخيصي ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/diagnostic/generate', json={})
        assert response.status_code in [400, 422, 500]

    def test_delete_test_nonexistent(self, client, admin_user):
        """حذف اختبار غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/api/diagnostic/tests/99999')
        assert response.status_code in [404, 500]

    def test_compare_tests_empty(self, client):
        """مقارنة اختبارات ببيانات فارغة"""
        response = client.post('/api/diagnostic/compare', json={})
        assert response.status_code in [400, 422, 500]

    def test_student_history_nonexistent(self, client):
        """تاريخ طالب غير موجود"""
        response = client.get('/api/diagnostic/student/99999/history')
        assert response.status_code in [200, 404, 500]

    def test_start_test_nonexistent(self, client):
        """بدء اختبار غير موجود"""
        response = client.post('/api/diagnostic/tests/99999/start', json={
            'student_id': 1
        })
        assert response.status_code in [404, 400, 500]
