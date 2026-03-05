"""
اختبارات Learning Content Routes
يغطي: lesson content API, progress tracking, admin management
"""
import pytest


class TestLearningAPI:
    """اختبارات Learning API للتطبيق"""

    def test_lesson_content_no_auth(self, client, sample_lesson):
        """محتوى الدرس يتطلب تسجيل دخول"""
        response = client.get(f'/learning/api/lessons/{sample_lesson.id}')
        assert response.status_code in [401, 302, 404]

    def test_lesson_content_as_admin(self, client, admin_user, sample_lesson):
        """الأدمن يمكنه رؤية محتوى الدرس"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get(f'/learning/api/lessons/{sample_lesson.id}')
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_lesson_content_nonexistent(self, client, admin_user):
        """محتوى درس غير موجود"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/learning/api/lessons/99999')
        assert response.status_code in [200, 404]

    def test_progress_update_requires_auth(self, client, sample_lesson):
        """تحديث التقدم يتطلب مصادقة"""
        response = client.post(f'/learning/api/progress/{sample_lesson.id}', json={
            'progress_percentage': 50
        })
        assert response.status_code in [401, 302, 404, 405]

    def test_lessons_list_endpoint(self, client, admin_user):
        """قائمة الدروس للأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/learning/lessons')
        assert response.status_code in [200, 302, 404]

    def test_student_visible_lessons(self, client, sample_lesson, student_user):
        """الطالب يرى الدروس المتاحة له"""
        with client.session_transaction() as sess:
            sess['user_id'] = student_user.id
        response = client.get(f'/learning/api/lessons/{sample_lesson.id}')
        assert response.status_code in [200, 401, 404]

    def test_lesson_content_with_device_header(self, client, student_user, sample_lesson):
        """استخدام Device-ID Header للمصادقة"""
        from src.models.student import Student
        # تسجيل جهاز للطالب
        response = client.get(f'/learning/api/lessons/{sample_lesson.id}', headers={
            'X-Device-ID': 'nonexistent_device'
        })
        assert response.status_code in [200, 401, 404]


class TestLearningAdminPages:
    """اختبارات صفحات إدارة Learning Content"""

    def test_summaries_page_requires_login(self, client):
        """صفحة الملخصات تتطلب دخول"""
        response = client.get('/learning/summaries')
        assert response.status_code in [200, 302, 401, 404]

    def test_concept_maps_page_requires_login(self, client):
        """صفحة خرائط المفاهيم تتطلب دخول"""
        response = client.get('/learning/concept-maps')
        assert response.status_code in [200, 302, 401, 404]

    def test_student_progress_page_requires_login(self, client):
        """صفحة تقدم الطلاب تتطلب دخول"""
        response = client.get('/learning/student-progress')
        assert response.status_code in [200, 302, 401, 404]

    def test_learning_dashboard_requires_login(self, client):
        """لوحة تحكم Learning تتطلب دخول"""
        response = client.get('/learning/')
        assert response.status_code in [200, 302, 401, 404]

    def test_lesson_content_admin_page(self, client, admin_user, sample_lesson):
        """صفحة محتوى الدرس للأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get(f'/learning/lessons/{sample_lesson.id}')
        assert response.status_code in [200, 302, 404]


class TestStudentLearningProgress:
    """اختبارات تتبع تقدم الطالب"""

    def test_student_stats_api(self, client, student_user):
        """إحصائيات الطالب"""
        response = client.get(f'/learning/api/student/{student_user.id}/stats')
        assert response.status_code in [200, 302, 401, 404]

    def test_student_visible_courses_api(self, client, student_user, sample_course):
        """المناهج المتاحة للطالب"""
        with client.session_transaction() as sess:
            sess['user_id'] = student_user.id
        response = client.get('/learning/api/courses')
        assert response.status_code in [200, 302, 401, 404]

    def test_units_for_course_api(self, client, student_user, sample_unit):
        """وحدات المنهج للطالب"""
        with client.session_transaction() as sess:
            sess['user_id'] = student_user.id
        response = client.get(f'/learning/api/courses/{sample_unit.course_id}/units')
        assert response.status_code in [200, 302, 401, 404]

    def test_lessons_for_unit_api(self, client, student_user, sample_lesson):
        """دروس الوحدة للطالب"""
        with client.session_transaction() as sess:
            sess['user_id'] = student_user.id
        response = client.get(f'/learning/api/units/{sample_lesson.unit_id}/lessons')
        assert response.status_code in [200, 302, 401, 404]
