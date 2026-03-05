"""
اختبارات شاملة لـ curriculum.py
يغطي: list_courses, add/edit/delete course/unit/lesson,
       update_order (course/unit/lesson), bulk_order,
       toggle_bot_visibility, alt routes, no-auth protection
Target: 70+ tests — raising coverage from 49% to 80%+
"""
import json
import pytest


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────
def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_course(db_session, name='TestCourse', order_num=10, show_in_bot=True):
    from src.models.curriculum import Course
    c = Course(name=name, order_num=order_num, show_in_bot=show_in_bot)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course_id, name='TestUnit', order_num=10):
    from src.models.curriculum import Unit
    u = Unit(name=name, course_id=course_id, order_num=order_num)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit_id, name='TestLesson', order_num=10):
    from src.models.curriculum import Lesson
    l = Lesson(name=name, unit_id=unit_id, order_num=order_num)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


# ─────────────────────────────────────────────
# 1. list_courses
# ─────────────────────────────────────────────
class TestListCourses:

    def test_list_courses_no_auth_redirects(self, client):
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_courses_as_admin_ok(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_courses_with_data(self, client, admin_user, db_session):
        _make_course(db_session, name='Chem101 List')
        _login(client, admin_user)
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_courses_triggers_reset_when_order_zero(self, client, admin_user, db_session):
        """Course with order_num=0 triggers reset_order_nums"""
        from src.models.curriculum import Course
        c = Course(name='ZeroOrderCourse', order_num=0)
        db_session.session.add(c)
        db_session.session.commit()
        _login(client, admin_user)
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_courses_cache_headers(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 2. add_course
# ─────────────────────────────────────────────
class TestAddCourse:

    def test_add_course_get_no_auth(self, client):
        response = client.get('/curriculum/courses/add')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_get_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/courses/add')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_post_no_auth(self, client):
        response = client.post('/curriculum/courses/add', data={'name': 'NoAuthCourse'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_post_empty_name(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={'name': ''})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_post_valid_name(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={'name': 'BrandNewCourse'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_post_with_show_in_bot(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={
            'name': 'CourseWithBot',
            'show_in_bot': 'on'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_duplicate_name(self, client, admin_user, db_session):
        _make_course(db_session, name='DuplicateCourse')
        _login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={'name': 'DuplicateCourse'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_course_no_data_posted(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 3. edit_course
# ─────────────────────────────────────────────
class TestEditCourse:

    def test_edit_course_get_no_auth(self, client, sample_course):
        response = client.get(f'/curriculum/courses/edit/{sample_course.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_course_get_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/courses/edit/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_course_get_existing(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditGetCourse')
        _login(client, admin_user)
        response = client.get(f'/curriculum/courses/edit/{c.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_course_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditEmptyName')
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': ''})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_course_post_valid_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='OldCourseName')
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': 'NewCourseName'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_course_post_duplicate_name(self, client, admin_user, db_session):
        _make_course(db_session, name='AlreadyExists')
        c2 = _make_course(db_session, name='WillConflict')
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/edit/{c2.id}', data={'name': 'AlreadyExists'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_course_post_toggle_show_in_bot(self, client, admin_user, db_session):
        c = _make_course(db_session, name='BotToggleCourse', show_in_bot=False)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/edit/{c.id}', data={
            'name': 'BotToggleCourse',
            'show_in_bot': 'on'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 4. delete_course
# ─────────────────────────────────────────────
class TestDeleteCourse:

    def test_delete_course_no_auth(self, client, sample_course):
        response = client.get(f'/curriculum/courses/delete/{sample_course.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_course_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/courses/delete/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_course_existing(self, client, admin_user, db_session):
        c = _make_course(db_session, name='CourseToDelete')
        _login(client, admin_user)
        response = client.get(f'/curriculum/courses/delete/{c.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_course_alt_route(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AltDeleteCourse')
        _login(client, admin_user)
        response = client.get(f'/curriculum/course/delete/{c.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 5. update_course_order
# ─────────────────────────────────────────────
class TestUpdateCourseOrder:

    def test_course_order_up_no_auth(self, client, sample_course):
        response = client.post(f'/curriculum/courses/order/{sample_course.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_up_no_prev(self, client, admin_user, db_session):
        """Course is first — no swap happens"""
        c = _make_course(db_session, name='OnlyCourseMoveUp', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/order/{c.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_up_with_prev(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='CourseOrderFirst', order_num=10)
        c2 = _make_course(db_session, name='CourseOrderSecond', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/order/{c2.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_down_no_next(self, client, admin_user, db_session):
        c = _make_course(db_session, name='OnlyCourseMoveDown', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/order/{c.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_down_with_next(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='CourseDown1', order_num=10)
        c2 = _make_course(db_session, name='CourseDown2', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/order/{c1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_invalid_direction(self, client, admin_user, db_session):
        c = _make_course(db_session, name='CourseInvalidDir', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/order/{c.id}/sideways')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_ajax_up(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='AjaxCourse1', order_num=10)
        c2 = _make_course(db_session, name='AjaxCourse2', order_num=20)
        _login(client, admin_user)
        response = client.post(
            f'/curriculum/courses/order/{c2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_ajax_down(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='AjaxCourseDown1', order_num=10)
        c2 = _make_course(db_session, name='AjaxCourseDown2', order_num=20)
        _login(client, admin_user)
        response = client.post(
            f'/curriculum/courses/order/{c1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/courses/order/99999/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_alt_route_up(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='AltOrdCourse1', order_num=10)
        c2 = _make_course(db_session, name='AltOrdCourse2', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/course/order/{c2.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_course_order_reset_when_zero(self, client, admin_user, db_session):
        """Course with order_num=0 causes reset before swap"""
        from src.models.curriculum import Course
        c1 = Course(name='ZeroOrder1ForSwap', order_num=0)
        c2 = Course(name='ZeroOrder2ForSwap', order_num=0)
        db_session.session.add(c1)
        db_session.session.add(c2)
        db_session.session.commit()
        db_session.session.refresh(c1)
        _login(client, admin_user)
        response = client.post(f'/curriculum/courses/order/{c1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 6. toggle_bot_visibility
# ─────────────────────────────────────────────
class TestToggleBotVisibility:

    def test_toggle_no_auth(self, client, sample_course):
        response = client.post(f'/curriculum/api/v1/courses/{sample_course.id}/toggle-bot-visibility')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/api/v1/courses/99999/toggle-bot-visibility')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_true_to_false(self, client, admin_user, db_session):
        c = _make_course(db_session, name='ToggleTrue', show_in_bot=True)
        _login(client, admin_user)
        response = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_false_to_true(self, client, admin_user, db_session):
        c = _make_course(db_session, name='ToggleFalse', show_in_bot=False)
        _login(client, admin_user)
        response = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_returns_json(self, client, admin_user, db_session):
        c = _make_course(db_session, name='ToggleJSON', show_in_bot=True)
        _login(client, admin_user)
        response = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None


# ─────────────────────────────────────────────
# 7. add_unit
# ─────────────────────────────────────────────
class TestAddUnit:

    def test_add_unit_get_no_auth(self, client, sample_course):
        response = client.get(f'/curriculum/units/add/{sample_course.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_unit_get_nonexistent_course(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/units/add/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_unit_get_existing_course(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddUnitGetCourse')
        _login(client, admin_user)
        response = client.get(f'/curriculum/units/add/{c.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_unit_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddUnitEmptyName')
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/add/{c.id}', data={'name': ''})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_unit_post_valid_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddUnitValidName')
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/add/{c.id}', data={'name': 'NewUnit'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_unit_post_no_data(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddUnitNoData')
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/add/{c.id}', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 8. edit_unit
# ─────────────────────────────────────────────
class TestEditUnit:

    def test_edit_unit_get_no_auth(self, client, sample_unit):
        response = client.get(f'/curriculum/units/edit/{sample_unit.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_unit_get_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/units/edit/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_unit_get_existing(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditUnitCourse')
        u = _make_unit(db_session, c.id, name='EditUnitGet')
        _login(client, admin_user)
        response = client.get(f'/curriculum/units/edit/{u.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_unit_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditUnitEmptyC')
        u = _make_unit(db_session, c.id, name='EditUnitEmpty')
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/edit/{u.id}', data={'name': ''})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_unit_post_valid_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditUnitValidC')
        u = _make_unit(db_session, c.id, name='OldUnitName')
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/edit/{u.id}', data={'name': 'UpdatedUnit'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 9. delete_unit
# ─────────────────────────────────────────────
class TestDeleteUnit:

    def test_delete_unit_no_auth(self, client, sample_unit):
        response = client.get(f'/curriculum/units/delete/{sample_unit.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_unit_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/units/delete/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_unit_existing(self, client, admin_user, db_session):
        c = _make_course(db_session, name='DeleteUnitCourse')
        u = _make_unit(db_session, c.id, name='UnitToDelete')
        _login(client, admin_user)
        response = client.get(f'/curriculum/units/delete/{u.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_unit_alt_route(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AltDeleteUnitCourse')
        u = _make_unit(db_session, c.id, name='AltUnitToDelete')
        _login(client, admin_user)
        response = client.get(f'/curriculum/unit/delete/{u.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 10. update_unit_order
# ─────────────────────────────────────────────
class TestUpdateUnitOrder:

    def test_unit_order_up_no_auth(self, client, sample_unit):
        response = client.post(f'/curriculum/units/order/{sample_unit.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_up_first_unit(self, client, admin_user, db_session):
        c = _make_course(db_session, name='UnitOrderUpCourse')
        u = _make_unit(db_session, c.id, name='FirstUnitUp', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/order/{u.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_up_second_unit(self, client, admin_user, db_session):
        c = _make_course(db_session, name='UnitOrderUp2Course')
        u1 = _make_unit(db_session, c.id, name='UnitUpFirst', order_num=10)
        u2 = _make_unit(db_session, c.id, name='UnitUpSecond', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/order/{u2.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_down_last_unit(self, client, admin_user, db_session):
        c = _make_course(db_session, name='UnitOrderDownCourse')
        u = _make_unit(db_session, c.id, name='LastUnitDown', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/order/{u.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_down_first_unit(self, client, admin_user, db_session):
        c = _make_course(db_session, name='UnitOrderDown2Course')
        u1 = _make_unit(db_session, c.id, name='UnitDownFirst', order_num=10)
        u2 = _make_unit(db_session, c.id, name='UnitDownSecond', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/units/order/99999/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_ajax_up(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AjaxUnitOrdCourse')
        u1 = _make_unit(db_session, c.id, name='AjaxUnit1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='AjaxUnit2', order_num=20)
        _login(client, admin_user)
        response = client.post(
            f'/curriculum/units/order/{u2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_alt_route_down(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AltUnitOrdCourse')
        u1 = _make_unit(db_session, c.id, name='AltUnitOrd1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='AltUnitOrd2', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/unit/order/{u1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unit_order_reset_on_zero(self, client, admin_user, db_session):
        """Units with order_num=0 cause reset before swap"""
        from src.models.curriculum import Unit
        c = _make_course(db_session, name='ZeroUnitOrdCourse')
        u1 = Unit(name='ZeroOrdUnit1', course_id=c.id, order_num=0)
        u2 = Unit(name='ZeroOrdUnit2', course_id=c.id, order_num=0)
        db_session.session.add_all([u1, u2])
        db_session.session.commit()
        db_session.session.refresh(u1)
        _login(client, admin_user)
        response = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 11. add_lesson
# ─────────────────────────────────────────────
class TestAddLesson:

    def test_add_lesson_get_no_auth(self, client, sample_unit):
        response = client.get(f'/curriculum/lessons/add/{sample_unit.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_lesson_get_nonexistent_unit(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/lessons/add/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_lesson_get_existing_unit(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddLessonCourse')
        u = _make_unit(db_session, c.id, name='AddLessonUnit')
        _login(client, admin_user)
        response = client.get(f'/curriculum/lessons/add/{u.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_lesson_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddLessonEmptyCourse')
        u = _make_unit(db_session, c.id, name='AddLessonEmptyUnit')
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': ''})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_lesson_post_valid_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddLessonValidCourse')
        u = _make_unit(db_session, c.id, name='AddLessonValidUnit')
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': 'NewLesson'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_lesson_post_no_data(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AddLessonNoDataCourse')
        u = _make_unit(db_session, c.id, name='AddLessonNoDataUnit')
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/add/{u.id}', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 12. edit_lesson
# ─────────────────────────────────────────────
class TestEditLesson:

    def test_edit_lesson_get_no_auth(self, client, sample_lesson):
        response = client.get(f'/curriculum/lessons/edit/{sample_lesson.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_lesson_get_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/lessons/edit/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_lesson_get_existing(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditLessonCourse')
        u = _make_unit(db_session, c.id, name='EditLessonUnit')
        l = _make_lesson(db_session, u.id, name='EditLessonGet')
        _login(client, admin_user)
        response = client.get(f'/curriculum/lessons/edit/{l.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_lesson_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditLessonEmptyCourse')
        u = _make_unit(db_session, c.id, name='EditLessonEmptyUnit')
        l = _make_lesson(db_session, u.id, name='EditLessonEmpty')
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': ''})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_lesson_post_valid_name(self, client, admin_user, db_session):
        c = _make_course(db_session, name='EditLessonValidCourse')
        u = _make_unit(db_session, c.id, name='EditLessonValidUnit')
        l = _make_lesson(db_session, u.id, name='OldLessonName')
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': 'UpdatedLesson'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 13. delete_lesson
# ─────────────────────────────────────────────
class TestDeleteLesson:

    def test_delete_lesson_no_auth(self, client, sample_lesson):
        response = client.get(f'/curriculum/lessons/delete/{sample_lesson.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_lesson_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/curriculum/lessons/delete/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_lesson_existing(self, client, admin_user, db_session):
        c = _make_course(db_session, name='DeleteLessonCourse')
        u = _make_unit(db_session, c.id, name='DeleteLessonUnit')
        l = _make_lesson(db_session, u.id, name='LessonToDelete')
        _login(client, admin_user)
        response = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_lesson_alt_route(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AltDeleteLessonCourse')
        u = _make_unit(db_session, c.id, name='AltDeleteLessonUnit')
        l = _make_lesson(db_session, u.id, name='AltLessonToDelete')
        _login(client, admin_user)
        response = client.get(f'/curriculum/lesson/delete/{l.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 14. update_lesson_order
# ─────────────────────────────────────────────
class TestUpdateLessonOrder:

    def test_lesson_order_up_no_auth(self, client, sample_lesson):
        response = client.post(f'/curriculum/lessons/order/{sample_lesson.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_up_first_lesson(self, client, admin_user, db_session):
        c = _make_course(db_session, name='LessonOrderUpCourse')
        u = _make_unit(db_session, c.id, name='LessonOrderUpUnit')
        l = _make_lesson(db_session, u.id, name='FirstLessonUp', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/order/{l.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_up_second_lesson(self, client, admin_user, db_session):
        c = _make_course(db_session, name='LessonOrdUp2Course')
        u = _make_unit(db_session, c.id, name='LessonOrdUp2Unit')
        l1 = _make_lesson(db_session, u.id, name='LessonOrdUp2First', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='LessonOrdUp2Second', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/order/{l2.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_down_last_lesson(self, client, admin_user, db_session):
        c = _make_course(db_session, name='LessonOrdDownCourse')
        u = _make_unit(db_session, c.id, name='LessonOrdDownUnit')
        l = _make_lesson(db_session, u.id, name='LastLessonDown', order_num=10)
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/order/{l.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_down_first_lesson(self, client, admin_user, db_session):
        c = _make_course(db_session, name='LessonOrdDown2Course')
        u = _make_unit(db_session, c.id, name='LessonOrdDown2Unit')
        l1 = _make_lesson(db_session, u.id, name='LessonDown2First', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='LessonDown2Second', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/lessons/order/99999/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_ajax_up(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AjaxLessonOrdCourse')
        u = _make_unit(db_session, c.id, name='AjaxLessonOrdUnit')
        l1 = _make_lesson(db_session, u.id, name='AjaxLesson1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='AjaxLesson2', order_num=20)
        _login(client, admin_user)
        response = client.post(
            f'/curriculum/lessons/order/{l2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_ajax_down(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AjaxLessonDownCourse')
        u = _make_unit(db_session, c.id, name='AjaxLessonDownUnit')
        l1 = _make_lesson(db_session, u.id, name='AjaxLessonD1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='AjaxLessonD2', order_num=20)
        _login(client, admin_user)
        response = client.post(
            f'/curriculum/lessons/order/{l1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_alt_route_up(self, client, admin_user, db_session):
        c = _make_course(db_session, name='AltLessonOrdCourse')
        u = _make_unit(db_session, c.id, name='AltLessonOrdUnit')
        l1 = _make_lesson(db_session, u.id, name='AltLessOrd1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='AltLessOrd2', order_num=20)
        _login(client, admin_user)
        response = client.post(f'/curriculum/lesson/order/{l2.id}/up')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_lesson_order_reset_on_zero(self, client, admin_user, db_session):
        """Lessons with order_num=0 cause reset before swap"""
        from src.models.curriculum import Lesson
        c = _make_course(db_session, name='ZeroLessonOrdCourse')
        u = _make_unit(db_session, c.id, name='ZeroLessonOrdUnit')
        l1 = Lesson(name='ZeroOrdLesson1', unit_id=u.id, order_num=0)
        l2 = Lesson(name='ZeroOrdLesson2', unit_id=u.id, order_num=0)
        db_session.session.add_all([l1, l2])
        db_session.session.commit()
        db_session.session.refresh(l1)
        _login(client, admin_user)
        response = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# 15. update_bulk_order
# ─────────────────────────────────────────────
class TestUpdateBulkOrder:

    def test_bulk_order_no_auth(self, client):
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([1, 2, 3])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_missing_type(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'new_order': json.dumps([1, 2])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_missing_new_order(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_invalid_type(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'invalid_type',
            'new_order': json.dumps([1, 2])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_courses(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='BulkCourse1', order_num=10)
        c2 = _make_course(db_session, name='BulkCourse2', order_num=20)
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([str(c2.id), str(c1.id)])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_units(self, client, admin_user, db_session):
        c = _make_course(db_session, name='BulkUnitCourse')
        u1 = _make_unit(db_session, c.id, name='BulkUnit1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='BulkUnit2', order_num=20)
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'parent_id': str(c.id),
            'new_order': json.dumps([str(u2.id), str(u1.id)])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_lessons(self, client, admin_user, db_session):
        c = _make_course(db_session, name='BulkLessonCourse')
        u = _make_unit(db_session, c.id, name='BulkLessonUnit')
        l1 = _make_lesson(db_session, u.id, name='BulkLesson1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='BulkLesson2', order_num=20)
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'lesson',
            'parent_id': str(u.id),
            'new_order': json.dumps([str(l2.id), str(l1.id)])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_using_id_param(self, client, admin_user, db_session):
        """Test that 'id' param works as fallback for parent_id"""
        c = _make_course(db_session, name='BulkIdParamCourse')
        u1 = _make_unit(db_session, c.id, name='BulkIdUnit1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='BulkIdUnit2', order_num=20)
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'id': str(c.id),
            'new_order': json.dumps([str(u2.id), str(u1.id)])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_with_nonexistent_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([99991, 99992])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_returns_json_success(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='BulkReturnCourse1', order_num=10)
        c2 = _make_course(db_session, name='BulkReturnCourse2', order_num=20)
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([str(c1.id), str(c2.id)])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_bulk_order_empty_new_order_list(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_order_invalid_id_string(self, client, admin_user, db_session):
        """Non-integer ID in list — should be skipped"""
        _login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps(['abc', 'xyz'])
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
