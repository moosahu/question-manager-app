"""
اختبارات API الرئيسي (المناهج، الوحدات، الدروس)
"""
import pytest


class TestCoursesApi:
    """اختبارات API المناهج"""

    def test_get_courses_returns_list(self, client):
        """API المناهج يرجع قائمة"""
        response = client.get('/api/v1/courses')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_courses_bot_hides_hidden(self, client, sample_course, sample_course_hidden):
        """المناهج المخفية (show_in_bot=False) لا تظهر في API البوت"""
        response = client.get('/api/v1/courses')
        data = response.get_json()
        names = [c['name'] for c in data]
        assert 'كيمياء - اختبار' in names
        assert 'كيمياء - مخفي' not in names

    def test_get_courses_show_all(self, client, sample_course, sample_course_hidden):
        """show_all=true يعرض جميع المناهج"""
        response = client.get('/api/v1/courses?show_all=true')
        data = response.get_json()
        names = [c['name'] for c in data]
        assert 'كيمياء - اختبار' in names
        assert 'كيمياء - مخفي' in names

    def test_get_courses_response_format(self, client, sample_course):
        """التحقق من بنية الـ response"""
        response = client.get('/api/v1/courses')
        data = response.get_json()
        if len(data) > 0:
            course = data[0]
            assert 'id' in course
            assert 'name' in course
            assert 'order_num' in course


class TestUnitsApi:
    """اختبارات API الوحدات"""

    def test_get_units_for_course(self, client, sample_course, sample_unit):
        """جلب وحدات منهج معين"""
        response = client.get(f'/api/v1/courses/{sample_course.id}/units')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_units_course_not_found(self, client):
        """منهج غير موجود → 404"""
        response = client.get('/api/v1/courses/99999/units')
        assert response.status_code == 404

    def test_hidden_unit_not_in_bot_api(self, client, sample_course, db_session, app):
        """وحدة مخفية (show_in_bot=False) لا تظهر"""
        from src.models.curriculum import Unit
        hidden_unit = Unit(
            name='وحدة مخفية',
            course_id=sample_course.id,
            order_num=99,
            show_in_bot=False
        )
        db_session.session.add(hidden_unit)
        db_session.session.commit()

        response = client.get(f'/api/v1/courses/{sample_course.id}/units')
        data = response.get_json()
        names = [u.get('name', '') for u in data]
        assert 'وحدة مخفية' not in names


class TestToggleBotVisibility:
    """اختبارات toggle show_in_bot"""

    def test_toggle_course_requires_login(self, client, sample_course):
        """toggle المنهج يتطلب تسجيل دخول"""
        response = client.post(f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility')
        # بدون login → redirect لصفحة login أو 401
        assert response.status_code in [302, 401, 403]

    def test_toggle_unit_not_found(self, client, admin_user):
        """toggle وحدة غير موجودة → 404"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/v1/units/99999/toggle-bot-visibility')
        assert response.status_code == 404

    def test_toggle_lesson_not_found(self, client, admin_user):
        """toggle درس غير موجود → 404"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/v1/lessons/99999/toggle-bot-visibility')
        assert response.status_code == 404
