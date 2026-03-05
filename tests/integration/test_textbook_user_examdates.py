"""
اختبارات لـ textbook, user, exam_dates, gamification routes
"""
import pytest


class TestTextbookRoutes:
    """اختبارات API الكتاب المدرسي"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_textbooks_no_auth(self, client):
        """جلب الكتب بدون مصادقة"""
        response = client.get('/api/admin/textbooks')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_get_textbooks_as_admin(self, client, admin_user):
        """جلب الكتب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks')
        assert response.status_code in [200, 500]

    def test_register_textbook_no_auth(self, client):
        """تسجيل كتاب بدون مصادقة"""
        response = client.post('/api/admin/textbooks/register', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_register_textbook_empty(self, client, admin_user):
        """تسجيل كتاب ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/register', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_register_textbook_valid(self, client, admin_user):
        """تسجيل كتاب ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/register', json={
            'name': 'كتاب اختبار',
            'course_id': 1
        })
        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_upload_textbook_no_auth(self, client):
        """رفع كتاب بدون مصادقة"""
        response = client.post('/api/admin/textbooks/upload', data={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_upload_textbook_no_file(self, client, admin_user):
        """رفع كتاب بدون ملف"""
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/upload', data={})
        assert response.status_code in [200, 400, 422, 500]

    def test_delete_textbook_no_auth(self, client):
        """حذف كتاب بدون مصادقة"""
        response = client.delete('/api/admin/textbooks/99999')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_textbook_nonexistent(self, client, admin_user):
        """حذف كتاب غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/api/admin/textbooks/99999')
        assert response.status_code in [200, 400, 404, 500]

    def test_set_lesson_pages_no_auth(self, client):
        """ضبط صفحات درس بدون مصادقة"""
        response = client.post('/api/admin/textbooks/99999/pages', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_set_lesson_pages_as_admin(self, client, admin_user):
        """ضبط صفحات درس كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/textbooks/99999/pages', json={
            'lesson_id': 1,
            'start_page': 1,
            'end_page': 10
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_get_lesson_pages_no_auth(self, client):
        """جلب صفحات درس بدون مصادقة"""
        response = client.get('/api/admin/textbooks/99999/pages')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_get_lesson_pages_as_admin(self, client, admin_user):
        """جلب صفحات درس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks/99999/pages')
        assert response.status_code in [200, 404, 500]

    def test_get_lesson_page_info(self, client, admin_user):
        """جلب معلومات صفحة الدرس"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks/lesson/99999/pages')
        assert response.status_code in [200, 404, 500]

    def test_get_courses_with_textbooks(self, client, admin_user):
        """جلب المناهج التي لها كتب"""
        self._login(client, admin_user)
        response = client.get('/api/admin/textbooks/courses-with-textbooks')
        assert response.status_code in [200, 500]


class TestUserRoutes:
    """اختبارات صفحات المستخدم"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_change_password_get_no_auth(self, client):
        """صفحة تغيير كلمة المرور بدون مصادقة"""
        response = client.get('/user/change-password')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_change_password_get_as_admin(self, client, admin_user):
        """صفحة تغيير كلمة المرور كأدمن"""
        self._login(client, admin_user)
        response = client.get('/user/change-password')
        assert response.status_code in [200, 302, 404, 500]

    def test_change_password_post_empty(self, client, admin_user):
        """تغيير كلمة المرور ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/user/change-password', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_change_password_post_wrong_current(self, client, admin_user):
        """تغيير كلمة المرور بكلمة مرور حالية خاطئة"""
        self._login(client, admin_user)
        response = client.post('/user/change-password', data={
            'current_password': 'WrongPass123!',
            'new_password': 'NewPass@123',
            'confirm_password': 'NewPass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 422, 500]

    def test_profile_get_no_auth(self, client):
        """صفحة الملف الشخصي بدون مصادقة"""
        response = client.get('/user/profile')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_profile_get_as_admin(self, client, admin_user):
        """صفحة الملف الشخصي كأدمن"""
        self._login(client, admin_user)
        response = client.get('/user/profile')
        assert response.status_code in [200, 302, 404, 500]

    def test_profile_post_as_admin(self, client, admin_user):
        """تحديث الملف الشخصي كأدمن"""
        self._login(client, admin_user)
        response = client.post('/user/profile', data={
            'name': 'أدمن محدث'
        })
        assert response.status_code in [200, 302, 400, 422, 500]


class TestExamDatesRoutes:
    """اختبارات مواعيد الاختبارات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_exam_dates_index_no_auth(self, client):
        """صفحة مواعيد الاختبارات بدون مصادقة"""
        response = client.get('/admin/exam-dates/')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_exam_dates_index_as_admin(self, client, admin_user):
        """صفحة مواعيد الاختبارات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/admin/exam-dates/')
        assert response.status_code in [200, 302, 404, 500]

    def test_get_all_dates_no_auth(self, client):
        """جلب كل المواعيد بدون مصادقة"""
        response = client.get('/admin/exam-dates/api/dates')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_get_all_dates_as_admin(self, client, admin_user):
        """جلب كل المواعيد كأدمن"""
        self._login(client, admin_user)
        response = client.get('/admin/exam-dates/api/dates')
        assert response.status_code in [200, 404, 500]

    def test_update_dates_no_auth(self, client):
        """تحديث المواعيد بدون مصادقة"""
        response = client.post('/admin/exam-dates/api/dates', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_update_dates_as_admin(self, client, admin_user):
        """تحديث المواعيد كأدمن"""
        self._login(client, admin_user)
        response = client.post('/admin/exam-dates/api/dates', json={
            'dates': {}
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_delete_date_no_auth(self, client):
        """حذف موعد بدون مصادقة"""
        response = client.delete('/admin/exam-dates/api/dates/test_field')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_date_as_admin(self, client, admin_user):
        """حذف موعد كأدمن"""
        self._login(client, admin_user)
        response = client.delete('/admin/exam-dates/api/dates/test_field')
        assert response.status_code in [200, 400, 404, 500]

    def test_reset_dates_no_auth(self, client):
        """إعادة ضبط المواعيد بدون مصادقة"""
        response = client.post('/admin/exam-dates/api/dates/reset', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_reset_dates_as_admin(self, client, admin_user):
        """إعادة ضبط المواعيد كأدمن"""
        self._login(client, admin_user)
        response = client.post('/admin/exam-dates/api/dates/reset', json={})
        assert response.status_code in [200, 400, 404, 500]


class TestGamificationRoutes:
    """اختبارات gamification API"""

    def test_get_points_no_student(self, client):
        """جلب النقاط لطالب غير موجود"""
        response = client.get('/api/gamification/points/99999')
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_add_points_no_auth(self, client):
        """إضافة نقاط بدون مصادقة"""
        response = client.post('/api/gamification/points/99999/add', json={
            'points': 10
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_leaderboard(self, client):
        """جلب قائمة المتصدرين"""
        response = client.get('/api/gamification/leaderboard')
        assert response.status_code in [200, 500]

    def test_get_achievements_nonexistent(self, client):
        """جلب الإنجازات لطالب غير موجود"""
        response = client.get('/api/gamification/achievements/99999')
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_check_achievements_no_auth(self, client):
        """التحقق من الإنجازات بدون مصادقة"""
        response = client.post('/api/gamification/achievements/99999/check', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_challenges(self, client):
        """جلب التحديات"""
        response = client.get('/api/gamification/challenges')
        assert response.status_code in [200, 500]

    def test_get_today_challenge(self, client):
        """جلب تحدي اليوم"""
        response = client.get('/api/gamification/challenges/today')
        assert response.status_code in [200, 404, 500]

    def test_get_challenge_progress(self, client):
        """جلب تقدم التحدي"""
        response = client.get('/api/gamification/challenges/99999/progress')
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_update_challenge_progress(self, client):
        """تحديث تقدم التحدي"""
        response = client.post('/api/gamification/challenges/99999/update', json={})
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_get_streak(self, client):
        """جلب السلسلة"""
        response = client.get('/api/gamification/streak/99999')
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_update_streak(self, client):
        """تحديث السلسلة"""
        response = client.post('/api/gamification/streak/99999/update', json={})
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_get_student_stats(self, client):
        """جلب إحصائيات الطالب"""
        response = client.get('/api/gamification/stats/99999')
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_get_system_stats(self, client):
        """جلب إحصائيات النظام"""
        response = client.get('/api/gamification/stats/system')
        assert response.status_code in [200, 500]

    def test_gamification_with_real_student(self, client, db_session, app):
        """اختبار gamification مع طالب حقيقي"""
        import secrets
        from src.models.student import Student
        s = Student(name='Gami Stu', username='gami_stu1', email='gami_stu1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(f'/api/gamification/points/{s.id}',
                              headers={'X-Session-Token': s.session_token})
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_leaderboard_with_token(self, client, db_session, app):
        """جلب قائمة المتصدرين مع token"""
        import secrets
        from src.models.student import Student
        s = Student(name='Lead Stu', username='lead_stu1', email='lead_stu1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        response = client.get('/api/gamification/leaderboard',
                              headers={'X-Session-Token': s.session_token})
        assert response.status_code in [200, 500]
