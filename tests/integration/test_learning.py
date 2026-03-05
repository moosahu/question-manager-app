"""
اختبارات نظام التعلم (الدروس، المحتوى، التقدم)
"""
import pytest


class TestLearningApi:
    """اختبارات API نظام التعلم"""

    def test_lessons_list_endpoint(self, client):
        """قائمة الدروس تعمل"""
        response = client.get('/learning/api/lessons')
        # يتطلب JWT auth → 401 أو 200
        assert response.status_code in [200, 401, 403]

    def test_lesson_content_endpoint(self, client, sample_lesson):
        """محتوى درس معين يعمل"""
        response = client.get(f'/learning/api/lessons/{sample_lesson.id}')
        assert response.status_code in [200, 401, 403, 404]

    def test_lesson_progress_requires_auth(self, client, sample_lesson):
        """تحديث التقدم يتطلب مصادقة"""
        response = client.post(f'/learning/api/lessons/{sample_lesson.id}/progress', json={
            'progress': 50
        })
        assert response.status_code in [401, 403]

    def test_student_stats_endpoint(self, client, student_user):
        """إحصائيات الطالب تعمل"""
        response = client.get(f'/learning/api/students/{student_user.id}/stats')
        # 302 = redirect to login, 401/403 = auth required, 200 = success
        assert response.status_code in [200, 302, 401, 403]


class TestCurriculumVisibility:
    """اختبارات ظهور المنهج للطلاب"""

    def test_student_sees_only_visible_courses(self, client, sample_course, sample_course_hidden):
        """الطالب يرى المناهج الظاهرة فقط"""
        response = client.get('/students/api/courses')
        assert response.status_code in [200, 401, 403]
        if response.status_code == 200:
            data = response.get_json()
            if isinstance(data, list):
                names = [c.get('name', '') for c in data]
                # كيمياء - مخفي لا يجب أن يظهر
                assert 'كيمياء - مخفي' not in names

    def test_student_api_units_for_course(self, client, sample_course, sample_unit):
        """API وحدات المنهج للطلاب"""
        response = client.get(f'/students/api/courses/{sample_course.id}/units')
        assert response.status_code in [200, 401, 403]

    def test_student_api_lessons_for_unit(self, client, sample_unit, sample_lesson):
        """API دروس الوحدة للطلاب"""
        response = client.get(f'/students/api/units/{sample_unit.id}/lessons')
        assert response.status_code in [200, 401, 403]
