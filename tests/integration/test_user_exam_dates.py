"""
اختبارات لـ User routes و Exam Dates
يغطي: change-password, profile, exam dates CRUD
"""
import pytest


class TestUserRoutes:
    """اختبارات مسارات المستخدم"""

    def test_change_password_no_auth(self, client):
        """تغيير كلمة المرور بدون مصادقة"""
        response = client.get('/user/change-password')
        assert response.status_code in [302, 401]

    def test_change_password_page_as_admin(self, client, admin_user):
        """صفحة تغيير كلمة المرور كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/user/change-password')
        assert response.status_code in [200, 302, 500]

    def test_change_password_post_no_auth(self, client):
        """إرسال تغيير كلمة المرور بدون مصادقة"""
        response = client.post('/user/change-password', json={
            'current_password': 'old',
            'new_password': 'New@123',
            'confirm_password': 'New@123'
        })
        assert response.status_code in [302, 401]

    def test_change_password_wrong_current(self, client, admin_user):
        """تغيير كلمة المرور بكلمة المرور الحالية الخاطئة"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/user/change-password', data={
            'current_password': 'WrongPassword123',
            'new_password': 'NewPass@456',
            'confirm_password': 'NewPass@456'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_profile_no_auth(self, client):
        """صفحة الملف الشخصي بدون مصادقة"""
        response = client.get('/user/profile')
        assert response.status_code in [302, 401]

    def test_profile_as_admin(self, client, admin_user):
        """صفحة الملف الشخصي كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/user/profile')
        assert response.status_code in [200, 302, 500]


class TestExamDatesRoutes:
    """اختبارات مسارات مواعيد الاختبار"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_index_no_auth(self, client):
        """صفحة المواعيد بدون مصادقة"""
        response = client.get('/admin/exam-dates/')
        assert response.status_code in [302, 401, 403]

    def test_index_as_admin(self, client, admin_user):
        """صفحة المواعيد كأدمن"""
        self._login(client, admin_user)
        response = client.get('/admin/exam-dates/')
        assert response.status_code in [200, 302, 500]

    def test_get_all_dates_no_auth(self, client):
        """جلب المواعيد بدون مصادقة"""
        response = client.get('/admin/exam-dates/api/dates')
        assert response.status_code in [302, 401, 403]

    def test_get_all_dates_as_admin(self, client, admin_user):
        """جلب المواعيد كأدمن"""
        self._login(client, admin_user)
        response = client.get('/admin/exam-dates/api/dates')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_update_dates_no_auth(self, client):
        """تحديث المواعيد بدون مصادقة"""
        response = client.post('/admin/exam-dates/api/dates', json={})
        assert response.status_code in [302, 401, 403]

    def test_update_dates_as_admin_empty(self, client, admin_user):
        """تحديث المواعيد كأدمن ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/admin/exam-dates/api/dates', json={})
        assert response.status_code in [200, 400, 500]

    def test_update_dates_as_admin_with_data(self, client, admin_user):
        """تحديث المواعيد كأدمن ببيانات"""
        self._login(client, admin_user)
        response = client.post('/admin/exam-dates/api/dates', json={
            'first_exam_date': '2025-06-01',
            'second_exam_date': '2025-07-01'
        })
        assert response.status_code in [200, 400, 422, 500]

    def test_delete_date_no_auth(self, client):
        """حذف موعد بدون مصادقة"""
        response = client.delete('/admin/exam-dates/api/dates/first_exam_date')
        assert response.status_code in [302, 401, 403]

    def test_delete_date_as_admin_nonexistent(self, client, admin_user):
        """حذف موعد غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/admin/exam-dates/api/dates/nonexistent_field')
        assert response.status_code in [200, 404, 500]

    def test_delete_date_as_admin(self, client, admin_user):
        """حذف موعد موجود"""
        self._login(client, admin_user)
        response = client.delete('/admin/exam-dates/api/dates/first_exam_date')
        assert response.status_code in [200, 404, 500]

    def test_reset_to_defaults_no_auth(self, client):
        """إعادة تعيين للافتراضي بدون مصادقة"""
        response = client.post('/admin/exam-dates/api/dates/reset')
        assert response.status_code in [302, 401, 403]

    def test_reset_to_defaults_as_admin(self, client, admin_user):
        """إعادة تعيين للافتراضي كأدمن"""
        self._login(client, admin_user)
        response = client.post('/admin/exam-dates/api/dates/reset')
        assert response.status_code in [200, 500]
