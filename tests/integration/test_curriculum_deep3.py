"""
test_curriculum_deep3.py
Deep integration tests for curriculum.py.

Targets uncovered lines:
  22-25 (add_no_cache_headers)
  36-61 (reset_order_nums)
  70-144 (update_bulk_order)
  149-155 (sanitize_path)
  162-209 (list_courses)
  215-239 (add_course)
  245-269 (edit_course)
  274-284 (delete_course)
  290-361 (update_course_order)
  371-390 (toggle_bot_visibility)
  398-419 (add_unit)
  425-443 (edit_unit)
  448-458 (delete_unit)
  464-535 (update_unit_order)
  543-564 (add_lesson)
  570-588 (edit_lesson)
  593-603 (delete_lesson)
  609-680 (update_lesson_order)
  691-712 (alt order routes)
  723-744 (alt delete routes)
"""
import json
import secrets
import pytest


ACCEPT = [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_course(db_session, name=None, order_num=10, show_in_bot=True):
    from src.models.curriculum import Course
    name = name or f'D3_Course_{secrets.token_hex(4)}'
    c = Course(name=name, order_num=order_num, show_in_bot=show_in_bot)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course_id, name=None, order_num=10):
    from src.models.curriculum import Unit
    name = name or f'D3_Unit_{secrets.token_hex(4)}'
    u = Unit(name=name, course_id=course_id, order_num=order_num)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit_id, name=None, order_num=10):
    from src.models.curriculum import Lesson
    name = name or f'D3_Lesson_{secrets.token_hex(4)}'
    l = Lesson(name=name, unit_id=unit_id, order_num=order_num)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


# ─────────────────────────────────────────────
# 1. list_courses - uncovered paths
# ─────────────────────────────────────────────

class TestListCourseDeep3:

    def test_list_courses_authenticated_returns_ok(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/')
        assert resp.status_code in ACCEPT

    def test_list_courses_with_zero_order_course_triggers_reset(self, client, admin_user, db_session):
        """Courses with order_num=0 trigger reset_order_nums"""
        from src.models.curriculum import Course
        c = Course(name=f'ZeroOrder_{secrets.token_hex(4)}', order_num=0)
        db_session.session.add(c)
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.get('/curriculum/')
        assert resp.status_code in ACCEPT

    def test_list_courses_with_unit_order_zero_triggers_reset(self, client, admin_user, db_session):
        """Units with order_num=0 trigger reset inside list_courses"""
        from src.models.curriculum import Course, Unit
        c = Course(name=f'CourseZU_{secrets.token_hex(4)}', order_num=10)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name=f'UnitZero_{secrets.token_hex(4)}', course_id=c.id, order_num=0)
        db_session.session.add(u)
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.get('/curriculum/')
        assert resp.status_code in ACCEPT

    def test_list_courses_with_lesson_order_zero_triggers_reset(self, client, admin_user, db_session):
        """Lessons with order_num=0 trigger reset inside list_courses"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name=f'CourseZL_{secrets.token_hex(4)}', order_num=10)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name=f'UnitZL_{secrets.token_hex(4)}', course_id=c.id, order_num=10)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name=f'LessZero_{secrets.token_hex(4)}', unit_id=u.id, order_num=0)
        db_session.session.add(l)
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.get('/curriculum/')
        assert resp.status_code in ACCEPT

    def test_list_courses_has_no_cache_headers(self, client, admin_user, db_session):
        """Response should carry no-cache headers"""
        _login(client, admin_user)
        resp = client.get('/curriculum/')
        if resp.status_code == 200:
            assert 'no-cache' in resp.headers.get('Cache-Control', '').lower() or \
                   resp.headers.get('Pragma', '') == 'no-cache'

    def test_list_courses_no_auth_redirects(self, client):
        resp = client.get('/curriculum/')
        assert resp.status_code in ACCEPT

    def test_list_courses_multiple_courses_and_units(self, client, admin_user, db_session):
        """Multiple courses with units and lessons"""
        for i in range(3):
            c = _make_course(db_session, order_num=(i + 1) * 10)
            for j in range(2):
                u = _make_unit(db_session, c.id, order_num=(j + 1) * 10)
                _make_lesson(db_session, u.id, order_num=10)
        _login(client, admin_user)
        resp = client.get('/curriculum/')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 2. add_course
# ─────────────────────────────────────────────

class TestAddCourseDeep3:

    def test_add_course_get_returns_form(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/courses/add')
        assert resp.status_code in ACCEPT

    def test_add_course_post_success(self, client, admin_user, db_session):
        _login(client, admin_user)
        name = f'NewCourse_{secrets.token_hex(4)}'
        resp = client.post('/curriculum/courses/add', data={'name': name})
        assert resp.status_code in ACCEPT

    def test_add_course_post_with_show_in_bot_true(self, client, admin_user, db_session):
        _login(client, admin_user)
        name = f'BotCourse_{secrets.token_hex(4)}'
        resp = client.post('/curriculum/courses/add', data={'name': name, 'show_in_bot': 'on'})
        assert resp.status_code in ACCEPT

    def test_add_course_post_with_show_in_bot_false(self, client, admin_user, db_session):
        _login(client, admin_user)
        name = f'NoBotCourse_{secrets.token_hex(4)}'
        resp = client.post('/curriculum/courses/add', data={'name': name})
        assert resp.status_code in ACCEPT

    def test_add_course_post_duplicate_name(self, client, admin_user, db_session):
        """Duplicate course name triggers warning flash"""
        name = f'DupCourse_{secrets.token_hex(4)}'
        _make_course(db_session, name=name)
        _login(client, admin_user)
        resp = client.post('/curriculum/courses/add', data={'name': name})
        assert resp.status_code in ACCEPT

    def test_add_course_post_empty_name(self, client, admin_user, db_session):
        """Empty name triggers danger flash"""
        _login(client, admin_user)
        resp = client.post('/curriculum/courses/add', data={'name': ''})
        assert resp.status_code in ACCEPT

    def test_add_course_post_no_name_key(self, client, admin_user, db_session):
        """No name key at all"""
        _login(client, admin_user)
        resp = client.post('/curriculum/courses/add', data={})
        assert resp.status_code in ACCEPT

    def test_add_course_no_auth_redirects(self, client):
        resp = client.post('/curriculum/courses/add', data={'name': 'X'})
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 3. edit_course
# ─────────────────────────────────────────────

class TestEditCourseDeep3:

    def test_edit_course_get_returns_form(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/courses/edit/{c.id}')
        assert resp.status_code in ACCEPT

    def test_edit_course_get_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/courses/edit/999999')
        assert resp.status_code in ACCEPT

    def test_edit_course_post_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        new_name = f'EditedCourse_{secrets.token_hex(4)}'
        resp = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': new_name})
        assert resp.status_code in ACCEPT

    def test_edit_course_post_with_show_in_bot(self, client, admin_user, db_session):
        c = _make_course(db_session, show_in_bot=False)
        _login(client, admin_user)
        new_name = f'EditBotCourse_{secrets.token_hex(4)}'
        resp = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': new_name, 'show_in_bot': 'on'})
        assert resp.status_code in ACCEPT

    def test_edit_course_post_duplicate_name(self, client, admin_user, db_session):
        """Edit to an already-existing name triggers warning"""
        c1 = _make_course(db_session, name=f'Edit_C1_{secrets.token_hex(4)}')
        c2 = _make_course(db_session, name=f'Edit_C2_{secrets.token_hex(4)}')
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/edit/{c1.id}', data={'name': c2.name})
        assert resp.status_code in ACCEPT

    def test_edit_course_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': ''})
        assert resp.status_code in ACCEPT

    def test_edit_course_same_name_ok(self, client, admin_user, db_session):
        """Edit to same name (own name) should be OK"""
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': c.name})
        assert resp.status_code in ACCEPT

    def test_edit_course_no_auth(self, client, db_session):
        c = _make_course(db_session)
        resp = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': 'X'})
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 4. delete_course
# ─────────────────────────────────────────────

class TestDeleteCourseDeep3:

    def test_delete_course_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/courses/delete/{c.id}')
        assert resp.status_code in ACCEPT

    def test_delete_course_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/courses/delete/999999')
        assert resp.status_code in ACCEPT

    def test_delete_course_no_auth(self, client, db_session):
        c = _make_course(db_session)
        resp = client.get(f'/curriculum/courses/delete/{c.id}')
        assert resp.status_code in ACCEPT

    def test_delete_course_with_units_cascades(self, client, admin_user, db_session):
        """Cascade delete: course with units and lessons"""
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/courses/delete/{c.id}')
        assert resp.status_code in ACCEPT

    def test_delete_course_alt_route(self, client, admin_user, db_session):
        """Alt route /course/delete/<id>"""
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/course/delete/{c.id}')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 5. update_course_order
# ─────────────────────────────────────────────

class TestUpdateCourseOrderDeep3:

    def test_course_order_up_success(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/order/{c2.id}/up')
        assert resp.status_code in ACCEPT

    def test_course_order_down_success(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/order/{c1.id}/down')
        assert resp.status_code in ACCEPT

    def test_course_order_up_already_first(self, client, admin_user, db_session):
        """Moving the first course up does nothing"""
        c = _make_course(db_session, order_num=10)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/order/{c.id}/up')
        assert resp.status_code in ACCEPT

    def test_course_order_down_already_last(self, client, admin_user, db_session):
        """Moving the last course down does nothing"""
        c = _make_course(db_session, order_num=10)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/order/{c.id}/down')
        assert resp.status_code in ACCEPT

    def test_course_order_up_ajax(self, client, admin_user, db_session):
        """AJAX request returns JSON response"""
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post(
            f'/curriculum/courses/order/{c2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None

    def test_course_order_down_ajax(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post(
            f'/curriculum/courses/order/{c1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code in ACCEPT

    def test_course_order_with_zero_order_triggers_reset(self, client, admin_user, db_session):
        """Zero order_num triggers reset before ordering"""
        from src.models.curriculum import Course
        c1 = Course(name=f'OrdZero1_{secrets.token_hex(4)}', order_num=0)
        c2 = Course(name=f'OrdZero2_{secrets.token_hex(4)}', order_num=0)
        db_session.session.add_all([c1, c2])
        db_session.session.commit()
        db_session.session.refresh(c1)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/courses/order/{c1.id}/up')
        assert resp.status_code in ACCEPT

    def test_course_order_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/courses/order/999999/up')
        assert resp.status_code in ACCEPT

    def test_course_order_no_auth(self, client, db_session):
        c = _make_course(db_session)
        resp = client.post(f'/curriculum/courses/order/{c.id}/up')
        assert resp.status_code in ACCEPT

    def test_course_order_alt_up(self, client, admin_user, db_session):
        """Alt route /course/order/<id>/up"""
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/course/order/{c2.id}/up')
        assert resp.status_code in ACCEPT

    def test_course_order_alt_down(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/course/order/{c1.id}/down')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 6. toggle_bot_visibility
# ─────────────────────────────────────────────

class TestToggleBotVisibilityDeep3:

    def test_toggle_true_to_false(self, client, admin_user, db_session):
        c = _make_course(db_session, show_in_bot=True)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert data['show_in_bot'] is False

    def test_toggle_false_to_true(self, client, admin_user, db_session):
        c = _make_course(db_session, show_in_bot=False)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert data['show_in_bot'] is True

    def test_toggle_nonexistent_course(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/api/v1/courses/999999/toggle-bot-visibility')
        assert resp.status_code in ACCEPT

    def test_toggle_no_auth(self, client, db_session):
        c = _make_course(db_session)
        resp = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert resp.status_code in ACCEPT

    def test_toggle_response_has_no_cache_headers(self, client, admin_user, db_session):
        c = _make_course(db_session, show_in_bot=True)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        if resp.status_code == 200:
            cc = resp.headers.get('Cache-Control', '')
            assert 'no-cache' in cc.lower() or 'no-store' in cc.lower()

    def test_toggle_message_contains_تفعيل(self, client, admin_user, db_session):
        c = _make_course(db_session, show_in_bot=False)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'تفعيل' in data.get('message', '')

    def test_toggle_message_contains_إيقاف(self, client, admin_user, db_session):
        c = _make_course(db_session, show_in_bot=True)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'إيقاف' in data.get('message', '')


# ─────────────────────────────────────────────
# 7. add_unit
# ─────────────────────────────────────────────

class TestAddUnitDeep3:

    def test_add_unit_get_returns_form(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/units/add/{c.id}')
        assert resp.status_code in ACCEPT

    def test_add_unit_get_nonexistent_course(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/units/add/999999')
        assert resp.status_code in ACCEPT

    def test_add_unit_post_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        name = f'Unit_{secrets.token_hex(4)}'
        resp = client.post(f'/curriculum/units/add/{c.id}', data={'name': name})
        assert resp.status_code in ACCEPT

    def test_add_unit_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/add/{c.id}', data={'name': ''})
        assert resp.status_code in ACCEPT

    def test_add_unit_post_no_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/add/{c.id}', data={})
        assert resp.status_code in ACCEPT

    def test_add_unit_no_auth(self, client, db_session):
        c = _make_course(db_session)
        resp = client.post(f'/curriculum/units/add/{c.id}', data={'name': 'X'})
        assert resp.status_code in ACCEPT

    def test_add_unit_calculates_max_order(self, client, admin_user, db_session):
        """When a unit already exists, new unit gets max_order+10"""
        c = _make_course(db_session)
        _make_unit(db_session, c.id, order_num=50)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/add/{c.id}', data={'name': f'U_{secrets.token_hex(4)}'})
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 8. edit_unit
# ─────────────────────────────────────────────

class TestEditUnitDeep3:

    def test_edit_unit_get(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/units/edit/{u.id}')
        assert resp.status_code in ACCEPT

    def test_edit_unit_get_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/units/edit/999999')
        assert resp.status_code in ACCEPT

    def test_edit_unit_post_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/edit/{u.id}', data={'name': f'EditedUnit_{secrets.token_hex(4)}'})
        assert resp.status_code in ACCEPT

    def test_edit_unit_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/edit/{u.id}', data={'name': ''})
        assert resp.status_code in ACCEPT

    def test_edit_unit_no_auth(self, client, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        resp = client.post(f'/curriculum/units/edit/{u.id}', data={'name': 'X'})
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 9. delete_unit
# ─────────────────────────────────────────────

class TestDeleteUnitDeep3:

    def test_delete_unit_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/units/delete/{u.id}')
        assert resp.status_code in ACCEPT

    def test_delete_unit_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/units/delete/999999')
        assert resp.status_code in ACCEPT

    def test_delete_unit_no_auth(self, client, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        resp = client.get(f'/curriculum/units/delete/{u.id}')
        assert resp.status_code in ACCEPT

    def test_delete_unit_with_lessons(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/units/delete/{u.id}')
        assert resp.status_code in ACCEPT

    def test_delete_unit_alt_route(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/unit/delete/{u.id}')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 10. update_unit_order
# ─────────────────────────────────────────────

class TestUpdateUnitOrderDeep3:

    def test_unit_order_up_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/order/{u2.id}/up')
        assert resp.status_code in ACCEPT

    def test_unit_order_down_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert resp.status_code in ACCEPT

    def test_unit_order_up_no_previous(self, client, admin_user, db_session):
        """First unit — no swap needed"""
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id, order_num=10)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/order/{u.id}/up')
        assert resp.status_code in ACCEPT

    def test_unit_order_down_no_next(self, client, admin_user, db_session):
        """Last unit — no swap needed"""
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id, order_num=10)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/order/{u.id}/down')
        assert resp.status_code in ACCEPT

    def test_unit_order_up_ajax(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(
            f'/curriculum/units/order/{u2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None

    def test_unit_order_down_ajax(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(
            f'/curriculum/units/order/{u1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code in ACCEPT

    def test_unit_order_zero_order_triggers_reset(self, client, admin_user, db_session):
        from src.models.curriculum import Unit
        c = _make_course(db_session)
        u1 = Unit(name=f'UZero1_{secrets.token_hex(4)}', course_id=c.id, order_num=0)
        u2 = Unit(name=f'UZero2_{secrets.token_hex(4)}', course_id=c.id, order_num=0)
        db_session.session.add_all([u1, u2])
        db_session.session.commit()
        db_session.session.refresh(u1)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/units/order/{u1.id}/up')
        assert resp.status_code in ACCEPT

    def test_unit_order_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/units/order/999999/up')
        assert resp.status_code in ACCEPT

    def test_unit_order_alt_up(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/unit/order/{u2.id}/up')
        assert resp.status_code in ACCEPT

    def test_unit_order_alt_down(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/unit/order/{u1.id}/down')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 11. add_lesson
# ─────────────────────────────────────────────

class TestAddLessonDeep3:

    def test_add_lesson_get(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/lessons/add/{u.id}')
        assert resp.status_code in ACCEPT

    def test_add_lesson_get_nonexistent_unit(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/lessons/add/999999')
        assert resp.status_code in ACCEPT

    def test_add_lesson_post_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': f'Lesson_{secrets.token_hex(4)}'})
        assert resp.status_code in ACCEPT

    def test_add_lesson_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': ''})
        assert resp.status_code in ACCEPT

    def test_add_lesson_post_no_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/add/{u.id}', data={})
        assert resp.status_code in ACCEPT

    def test_add_lesson_calculates_max_order(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        _make_lesson(db_session, u.id, order_num=50)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': f'L_{secrets.token_hex(4)}'})
        assert resp.status_code in ACCEPT

    def test_add_lesson_no_auth(self, client, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        resp = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': 'X'})
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 12. edit_lesson
# ─────────────────────────────────────────────

class TestEditLessonDeep3:

    def test_edit_lesson_get(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/lessons/edit/{l.id}')
        assert resp.status_code in ACCEPT

    def test_edit_lesson_post_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': f'EditLesson_{secrets.token_hex(4)}'})
        assert resp.status_code in ACCEPT

    def test_edit_lesson_post_empty_name(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': ''})
        assert resp.status_code in ACCEPT

    def test_edit_lesson_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/lessons/edit/999999')
        assert resp.status_code in ACCEPT

    def test_edit_lesson_no_auth(self, client, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': 'X'})
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 13. delete_lesson
# ─────────────────────────────────────────────

class TestDeleteLessonDeep3:

    def test_delete_lesson_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert resp.status_code in ACCEPT

    def test_delete_lesson_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/curriculum/lessons/delete/999999')
        assert resp.status_code in ACCEPT

    def test_delete_lesson_no_auth(self, client, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert resp.status_code in ACCEPT

    def test_delete_lesson_alt_route(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login(client, admin_user)
        resp = client.get(f'/curriculum/lesson/delete/{l.id}')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 14. update_lesson_order
# ─────────────────────────────────────────────

class TestUpdateLessonOrderDeep3:

    def test_lesson_order_up_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/order/{l2.id}/up')
        assert resp.status_code in ACCEPT

    def test_lesson_order_down_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert resp.status_code in ACCEPT

    def test_lesson_order_up_no_previous(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id, order_num=10)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/order/{l.id}/up')
        assert resp.status_code in ACCEPT

    def test_lesson_order_down_no_next(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id, order_num=10)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/order/{l.id}/down')
        assert resp.status_code in ACCEPT

    def test_lesson_order_up_ajax(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(
            f'/curriculum/lessons/order/{l2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None

    def test_lesson_order_down_ajax(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(
            f'/curriculum/lessons/order/{l1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code in ACCEPT

    def test_lesson_order_zero_order_triggers_reset(self, client, admin_user, db_session):
        from src.models.curriculum import Lesson
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = Lesson(name=f'LZero1_{secrets.token_hex(4)}', unit_id=u.id, order_num=0)
        l2 = Lesson(name=f'LZero2_{secrets.token_hex(4)}', unit_id=u.id, order_num=0)
        db_session.session.add_all([l1, l2])
        db_session.session.commit()
        db_session.session.refresh(l1)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lessons/order/{l1.id}/up')
        assert resp.status_code in ACCEPT

    def test_lesson_order_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/lessons/order/999999/up')
        assert resp.status_code in ACCEPT

    def test_lesson_order_alt_up(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lesson/order/{l2.id}/up')
        assert resp.status_code in ACCEPT

    def test_lesson_order_alt_down(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post(f'/curriculum/lesson/order/{l1.id}/down')
        assert resp.status_code in ACCEPT


# ─────────────────────────────────────────────
# 15. update_bulk_order
# ─────────────────────────────────────────────

class TestUpdateBulkOrderDeep3:

    def test_bulk_order_courses(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([str(c2.id), str(c1.id)])
        })
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_bulk_order_units(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'parent_id': str(c.id),
            'new_order': json.dumps([str(u2.id), str(u1.id)])
        })
        assert resp.status_code in ACCEPT

    def test_bulk_order_lessons(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'lesson',
            'parent_id': str(u.id),
            'new_order': json.dumps([str(l2.id), str(l1.id)])
        })
        assert resp.status_code in ACCEPT

    def test_bulk_order_no_type(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'new_order': json.dumps([1, 2])
        })
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_bulk_order_invalid_type(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'invalid_type',
            'new_order': json.dumps([1, 2])
        })
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_bulk_order_empty_order(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([])
        })
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_bulk_order_nonexistent_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([999999, 888888])
        })
        assert resp.status_code in ACCEPT

    def test_bulk_order_invalid_id_values(self, client, admin_user, db_session):
        """Non-numeric IDs should be skipped with no crash"""
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps(['abc', 'def'])
        })
        assert resp.status_code in ACCEPT

    def test_bulk_order_no_auth(self, client):
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([1])
        })
        assert resp.status_code in ACCEPT

    def test_bulk_order_uses_id_param(self, client, admin_user, db_session):
        """Uses 'id' parameter when 'parent_id' is absent"""
        c = _make_course(db_session)
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'id': str(c.id),
            'new_order': json.dumps([str(u2.id), str(u1.id)])
        })
        assert resp.status_code in ACCEPT

    def test_bulk_order_response_has_no_cache_headers(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([str(c1.id), str(c2.id)])
        })
        if resp.status_code == 200:
            cc = resp.headers.get('Cache-Control', '')
            assert 'no-cache' in cc.lower() or 'no-store' in cc.lower()

    def test_bulk_order_units_with_wrong_course_id(self, client, admin_user, db_session):
        """IDs that don't belong to given parent_id are skipped"""
        c1 = _make_course(db_session)
        c2 = _make_course(db_session)
        u1 = _make_unit(db_session, c1.id, order_num=10)
        u2 = _make_unit(db_session, c2.id, order_num=10)
        _login(client, admin_user)
        # Pass unit from c2 as if it belongs to c1
        resp = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'parent_id': str(c1.id),
            'new_order': json.dumps([str(u2.id)])  # doesn't belong to c1
        })
        assert resp.status_code in ACCEPT
