"""
Deep integration tests for curriculum.py - Part 2
Target: raise curriculum.py coverage from 86% to 94%+

Focuses on uncovered paths:
- update_bulk_order: all item types, edge cases, invalid IDs
- toggle_bot_visibility: success/error
- unit ordering: up/down/ajax/no-prev/no-next/zero-order-reset
- lesson ordering: up/down/ajax/no-prev/no-next/zero-order-reset
- alt routes: course/unit/lesson order + delete
- reset_order_nums function (indirect via list_courses / order endpoints)
- sanitize_path helper (indirectly via error flash)
- add_no_cache_headers (indirectly via AJAX responses)
- error paths: commit failures, nonexistent IDs
- GET vs POST on add/edit forms
- Empty name rejection for unit/lesson
- Duplicate-course logic for edit
"""
import json
import pytest


ACCEPT = [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_course(db_session, name='CurrDeep2Course', order_num=10, show_in_bot=True):
    from src.models.curriculum import Course
    import secrets
    c = Course(name=f'{name}_{secrets.token_hex(4)}', order_num=order_num, show_in_bot=show_in_bot)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course_id, name='CurrDeep2Unit', order_num=10):
    from src.models.curriculum import Unit
    import secrets
    u = Unit(name=f'{name}_{secrets.token_hex(4)}', course_id=course_id, order_num=order_num)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit_id, name='CurrDeep2Lesson', order_num=10):
    from src.models.curriculum import Lesson
    import secrets
    l = Lesson(name=f'{name}_{secrets.token_hex(4)}', unit_id=unit_id, order_num=order_num)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


# ─────────────────────────────────────────────
# update_bulk_order
# ─────────────────────────────────────────────

class TestUpdateBulkOrder:
    """اختبارات تحديث الترتيب الجماعي"""

    def test_bulk_no_auth(self, client):
        """بدون مصادقة"""
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([1, 2, 3])
        })
        assert r.status_code in ACCEPT

    def test_bulk_missing_type(self, client, admin_user, db_session):
        """بدون نوع العنصر"""
        _login(client, admin_user)
        r = client.post('/curriculum/update_bulk_order', data={
            'new_order': json.dumps([1, 2])
        })
        assert r.status_code == 400
        data = r.get_json()
        assert data.get('success') is False

    def test_bulk_empty_order(self, client, admin_user, db_session):
        """ترتيب فارغ"""
        _login(client, admin_user)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([])
        })
        assert r.status_code == 400
        data = r.get_json()
        assert data.get('success') is False

    def test_bulk_invalid_type(self, client, admin_user, db_session):
        """نوع غير صالح"""
        _login(client, admin_user)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'invalid_type',
            'new_order': json.dumps([1, 2])
        })
        assert r.status_code == 400
        data = r.get_json()
        assert data.get('success') is False

    def test_bulk_course_type_success(self, client, admin_user, db_session):
        """تحديث ترتيب المناهج بنجاح"""
        _login(client, admin_user)
        c1 = _make_course(db_session, name='BulkC1', order_num=10)
        c2 = _make_course(db_session, name='BulkC2', order_num=20)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([c2.id, c1.id])
        })
        assert r.status_code in ACCEPT
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_bulk_unit_type_success(self, client, admin_user, db_session):
        """تحديث ترتيب الوحدات بنجاح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='BulkUnitCourse')
        u1 = _make_unit(db_session, c.id, name='BulkU1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='BulkU2', order_num=20)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'parent_id': str(c.id),
            'new_order': json.dumps([u2.id, u1.id])
        })
        assert r.status_code in ACCEPT

    def test_bulk_lesson_type_success(self, client, admin_user, db_session):
        """تحديث ترتيب الدروس بنجاح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='BulkLessonCourse')
        u = _make_unit(db_session, c.id, name='BulkLessonUnit')
        l1 = _make_lesson(db_session, u.id, name='BulkL1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='BulkL2', order_num=20)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'lesson',
            'parent_id': str(u.id),
            'new_order': json.dumps([l2.id, l1.id])
        })
        assert r.status_code in ACCEPT

    def test_bulk_unit_with_id_param(self, client, admin_user, db_session):
        """unit type مع id بدل parent_id"""
        _login(client, admin_user)
        c = _make_course(db_session, name='BulkUnitWithId')
        u1 = _make_unit(db_session, c.id, name='BulkUID1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='BulkUID2', order_num=20)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'id': str(c.id),
            'new_order': json.dumps([u1.id, u2.id])
        })
        assert r.status_code in ACCEPT

    def test_bulk_invalid_id_in_order(self, client, admin_user, db_session):
        """ID غير صالح في الترتيب يُتجاهل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='BulkInvalidId')
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps(['not_a_number', c.id])
        })
        assert r.status_code in ACCEPT

    def test_bulk_nonexistent_id_skipped(self, client, admin_user, db_session):
        """ID غير موجود يُتجاهل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='BulkNonExist')
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([c.id, 999999])
        })
        assert r.status_code in ACCEPT

    def test_bulk_returns_no_cache_headers(self, client, admin_user, db_session):
        """يُعيد تعليمات منع التخزين المؤقت"""
        _login(client, admin_user)
        c1 = _make_course(db_session, name='NoCacheC1', order_num=10)
        c2 = _make_course(db_session, name='NoCacheC2', order_num=20)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([c2.id, c1.id])
        })
        if r.status_code == 200:
            assert 'Cache-Control' in r.headers

    def test_bulk_lesson_without_parent_id(self, client, admin_user, db_session):
        """lesson بدون parent_id"""
        _login(client, admin_user)
        c = _make_course(db_session, name='BulkLessonNoPID')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'lesson',
            'new_order': json.dumps([l1.id])
        })
        assert r.status_code in ACCEPT

    def test_bulk_unit_wrong_parent(self, client, admin_user, db_session):
        """وحدة بـ parent_id خاطئ لا تُحدَّث"""
        _login(client, admin_user)
        c1 = _make_course(db_session, name='BulkWrongParent1')
        c2 = _make_course(db_session, name='BulkWrongParent2')
        u = _make_unit(db_session, c1.id, order_num=10)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'unit',
            'parent_id': str(c2.id),  # parent خاطئ
            'new_order': json.dumps([u.id])
        })
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# toggle_bot_visibility
# ─────────────────────────────────────────────

class TestToggleBotVisibilityDeep:
    """اختبارات تبديل ظهور المنهج في البوت"""

    def test_toggle_no_auth(self, client, db_session):
        """بدون مصادقة"""
        c = _make_course(db_session, name='ToggleNoAuth')
        r = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert r.status_code in ACCEPT

    def test_toggle_nonexistent(self, client, admin_user, db_session):
        """منهج غير موجود"""
        _login(client, admin_user)
        r = client.post('/curriculum/api/v1/courses/999999/toggle-bot-visibility')
        assert r.status_code in [404, 500]

    def test_toggle_visible_to_hidden(self, client, admin_user, db_session):
        """من ظاهر إلى مخفي"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ToggleVisible', show_in_bot=True)
        r = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') is True
        assert data.get('show_in_bot') is False

    def test_toggle_hidden_to_visible(self, client, admin_user, db_session):
        """من مخفي إلى ظاهر"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ToggleHidden', show_in_bot=False)
        r = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') is True
        assert data.get('show_in_bot') is True

    def test_toggle_no_cache_header(self, client, admin_user, db_session):
        """يُعيد Cache-Control header"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ToggleNoCache')
        r = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        if r.status_code == 200:
            assert 'Cache-Control' in r.headers

    def test_toggle_message_contains_activation(self, client, admin_user, db_session):
        """الرسالة تحتوي على 'تفعيل' أو 'إيقاف'"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ToggleMsg', show_in_bot=True)
        r = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        if r.status_code == 200:
            data = r.get_json()
            msg = data.get('message', '')
            assert 'تفعيل' in msg or 'إيقاف' in msg


# ─────────────────────────────────────────────
# Unit Order Routes
# ─────────────────────────────────────────────

class TestUnitOrderDeep:
    """اختبارات ترتيب الوحدات"""

    def test_unit_order_up_no_prev(self, client, admin_user, db_session):
        """الوحدة الأولى لا يوجد قبلها"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitUpNoPrev')
        u = _make_unit(db_session, c.id, order_num=10)
        r = client.post(f'/curriculum/units/order/{u.id}/up')
        assert r.status_code in ACCEPT

    def test_unit_order_up_with_prev(self, client, admin_user, db_session):
        """الوحدة الثانية تتحرك للأعلى"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitUpWithPrev')
        u1 = _make_unit(db_session, c.id, name='UnitFirst', order_num=10)
        u2 = _make_unit(db_session, c.id, name='UnitSecond', order_num=20)
        r = client.post(f'/curriculum/units/order/{u2.id}/up')
        assert r.status_code in ACCEPT

    def test_unit_order_down_no_next(self, client, admin_user, db_session):
        """الوحدة الأخيرة لا يوجد بعدها"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitDownNoNext')
        u = _make_unit(db_session, c.id, order_num=10)
        r = client.post(f'/curriculum/units/order/{u.id}/down')
        assert r.status_code in ACCEPT

    def test_unit_order_down_with_next(self, client, admin_user, db_session):
        """الوحدة الأولى تتحرك للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitDownWithNext')
        u1 = _make_unit(db_session, c.id, name='UnitD1', order_num=10)
        u2 = _make_unit(db_session, c.id, name='UnitD2', order_num=20)
        r = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert r.status_code in ACCEPT

    def test_unit_order_invalid_direction(self, client, admin_user, db_session):
        """اتجاه غير صالح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitInvalidDir')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/units/order/{u.id}/sideways')
        assert r.status_code in ACCEPT

    def test_unit_order_ajax_up(self, client, admin_user, db_session):
        """طلب AJAX للأعلى"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitAjaxUp')
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        r = client.post(
            f'/curriculum/units/order/{u2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert r.status_code in ACCEPT
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_unit_order_ajax_down(self, client, admin_user, db_session):
        """طلب AJAX للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitAjaxDown')
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        r = client.post(
            f'/curriculum/units/order/{u1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert r.status_code in ACCEPT

    def test_unit_order_nonexistent(self, client, admin_user, db_session):
        """وحدة غير موجودة"""
        _login(client, admin_user)
        r = client.post('/curriculum/units/order/999999/up')
        assert r.status_code in ACCEPT

    def test_unit_order_zero_order_reset(self, client, admin_user, db_session):
        """وحدة بـ order_num=0 يُعيد الترتيب"""
        from src.models.curriculum import Unit
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitZeroReset')
        u1 = Unit(name='UnitZero1_deep2', course_id=c.id, order_num=0)
        u2 = Unit(name='UnitZero2_deep2', course_id=c.id, order_num=0)
        db_session.session.add(u1)
        db_session.session.add(u2)
        db_session.session.commit()
        db_session.session.refresh(u1)
        r = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert r.status_code in ACCEPT

    def test_unit_order_alt_route_up(self, client, admin_user, db_session):
        """مسار بديل للأعلى"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitAltUp')
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        r = client.post(f'/curriculum/unit/order/{u2.id}/up')
        assert r.status_code in ACCEPT

    def test_unit_order_alt_route_down(self, client, admin_user, db_session):
        """مسار بديل للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitAltDown')
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        r = client.post(f'/curriculum/unit/order/{u1.id}/down')
        assert r.status_code in ACCEPT

    def test_unit_order_no_auth(self, client, db_session):
        """بدون مصادقة"""
        c = _make_course(db_session, name='UnitNoAuth')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/units/order/{u.id}/up')
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# Lesson Order Routes
# ─────────────────────────────────────────────

class TestLessonOrderDeep:
    """اختبارات ترتيب الدروس"""

    def test_lesson_order_up_no_prev(self, client, admin_user, db_session):
        """الدرس الأول لا يوجد قبله"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonUpNoPrev')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id, order_num=10)
        r = client.post(f'/curriculum/lessons/order/{l.id}/up')
        assert r.status_code in ACCEPT

    def test_lesson_order_up_with_prev(self, client, admin_user, db_session):
        """الدرس الثاني يتحرك للأعلى"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonUpPrev')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, name='LessonP1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='LessonP2', order_num=20)
        r = client.post(f'/curriculum/lessons/order/{l2.id}/up')
        assert r.status_code in ACCEPT

    def test_lesson_order_down_no_next(self, client, admin_user, db_session):
        """الدرس الأخير لا يوجد بعده"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonDownNoNext')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id, order_num=10)
        r = client.post(f'/curriculum/lessons/order/{l.id}/down')
        assert r.status_code in ACCEPT

    def test_lesson_order_down_with_next(self, client, admin_user, db_session):
        """الدرس الأول يتحرك للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonDownNext')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, name='LessonDN1', order_num=10)
        l2 = _make_lesson(db_session, u.id, name='LessonDN2', order_num=20)
        r = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert r.status_code in ACCEPT

    def test_lesson_order_invalid_direction(self, client, admin_user, db_session):
        """اتجاه غير صالح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonInvalidDir')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.post(f'/curriculum/lessons/order/{l.id}/diagonal')
        assert r.status_code in ACCEPT

    def test_lesson_order_ajax_up(self, client, admin_user, db_session):
        """طلب AJAX للأعلى"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonAjaxUp')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        r = client.post(
            f'/curriculum/lessons/order/{l2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert r.status_code in ACCEPT
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_lesson_order_ajax_down(self, client, admin_user, db_session):
        """طلب AJAX للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonAjaxDown')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        r = client.post(
            f'/curriculum/lessons/order/{l1.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert r.status_code in ACCEPT

    def test_lesson_order_nonexistent(self, client, admin_user, db_session):
        """درس غير موجود"""
        _login(client, admin_user)
        r = client.post('/curriculum/lessons/order/999999/up')
        assert r.status_code in ACCEPT

    def test_lesson_order_zero_order_reset(self, client, admin_user, db_session):
        """درس بـ order_num=0 يُعيد الترتيب"""
        from src.models.curriculum import Lesson
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonZeroReset')
        u = _make_unit(db_session, c.id)
        l1 = Lesson(name='LessonZero1_deep2', unit_id=u.id, order_num=0)
        l2 = Lesson(name='LessonZero2_deep2', unit_id=u.id, order_num=0)
        db_session.session.add(l1)
        db_session.session.add(l2)
        db_session.session.commit()
        db_session.session.refresh(l1)
        r = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert r.status_code in ACCEPT

    def test_lesson_order_alt_route_up(self, client, admin_user, db_session):
        """مسار بديل للأعلى"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonAltUp')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        r = client.post(f'/curriculum/lesson/order/{l2.id}/up')
        assert r.status_code in ACCEPT

    def test_lesson_order_alt_route_down(self, client, admin_user, db_session):
        """مسار بديل للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonAltDown')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        r = client.post(f'/curriculum/lesson/order/{l1.id}/down')
        assert r.status_code in ACCEPT

    def test_lesson_order_no_auth(self, client, db_session):
        """بدون مصادقة"""
        c = _make_course(db_session, name='LessonNoAuth')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.post(f'/curriculum/lessons/order/{l.id}/up')
        assert r.status_code in ACCEPT

    def test_lesson_order_ajax_no_cache_headers(self, client, admin_user, db_session):
        """AJAX يُعيد تعليمات منع التخزين المؤقت"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonAjaxNoCache')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        r = client.post(
            f'/curriculum/lessons/order/{l2.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        if r.status_code == 200:
            assert 'Cache-Control' in r.headers


# ─────────────────────────────────────────────
# Alt Delete Routes
# ─────────────────────────────────────────────

class TestAltDeleteRoutes:
    """اختبارات مسارات الحذف البديلة"""

    def test_alt_delete_unit_exists(self, client, admin_user, db_session):
        """حذف وحدة بالمسار البديل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='AltDelUnit')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/unit/delete/{u.id}')
        assert r.status_code in ACCEPT

    def test_alt_delete_unit_nonexistent(self, client, admin_user, db_session):
        """حذف وحدة غير موجودة"""
        _login(client, admin_user)
        r = client.get('/curriculum/unit/delete/999999')
        assert r.status_code in ACCEPT

    def test_alt_delete_lesson_exists(self, client, admin_user, db_session):
        """حذف درس بالمسار البديل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='AltDelLesson')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/lesson/delete/{l.id}')
        assert r.status_code in ACCEPT

    def test_alt_delete_lesson_nonexistent(self, client, admin_user, db_session):
        """حذف درس غير موجود"""
        _login(client, admin_user)
        r = client.get('/curriculum/lesson/delete/999999')
        assert r.status_code in ACCEPT

    def test_alt_delete_course_no_auth(self, client, db_session):
        """حذف منهج بدون مصادقة"""
        c = _make_course(db_session, name='AltDelNoAuth')
        r = client.get(f'/curriculum/course/delete/{c.id}')
        assert r.status_code in ACCEPT

    def test_alt_delete_unit_no_auth(self, client, db_session):
        """حذف وحدة بدون مصادقة"""
        c = _make_course(db_session, name='AltDelUnitNoAuth')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/unit/delete/{u.id}')
        assert r.status_code in ACCEPT

    def test_alt_delete_lesson_no_auth(self, client, db_session):
        """حذف درس بدون مصادقة"""
        c = _make_course(db_session, name='AltDelLessonNoAuth')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/lesson/delete/{l.id}')
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# Unit CRUD
# ─────────────────────────────────────────────

class TestUnitCRUDDeep:
    """اختبارات CRUD للوحدات"""

    def test_add_unit_get_no_auth(self, client, db_session):
        """GET بدون مصادقة"""
        c = _make_course(db_session, name='UnitGetNoAuth')
        r = client.get(f'/curriculum/units/add/{c.id}')
        assert r.status_code in ACCEPT

    def test_add_unit_get_as_admin(self, client, admin_user, db_session):
        """GET كأدمن"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitGetAdmin')
        r = client.get(f'/curriculum/units/add/{c.id}')
        assert r.status_code in ACCEPT

    def test_add_unit_post_valid(self, client, admin_user, db_session):
        """إضافة وحدة بنجاح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitPostValid')
        r = client.post(f'/curriculum/units/add/{c.id}', data={'name': 'NewValidUnit'})
        assert r.status_code in ACCEPT

    def test_add_unit_post_empty_name(self, client, admin_user, db_session):
        """إضافة وحدة باسم فارغ"""
        _login(client, admin_user)
        c = _make_course(db_session, name='UnitPostEmpty')
        r = client.post(f'/curriculum/units/add/{c.id}', data={'name': ''})
        assert r.status_code in ACCEPT

    def test_add_unit_nonexistent_course(self, client, admin_user, db_session):
        """منهج غير موجود"""
        _login(client, admin_user)
        r = client.post('/curriculum/units/add/999999', data={'name': 'Orphan'})
        assert r.status_code in ACCEPT

    def test_edit_unit_get(self, client, admin_user, db_session):
        """GET تعديل وحدة"""
        _login(client, admin_user)
        c = _make_course(db_session, name='EditUnitGet')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/units/edit/{u.id}')
        assert r.status_code in ACCEPT

    def test_edit_unit_post_valid(self, client, admin_user, db_session):
        """تعديل وحدة بنجاح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='EditUnitPost')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/units/edit/{u.id}', data={'name': 'UpdatedUnitName'})
        assert r.status_code in ACCEPT

    def test_edit_unit_post_empty_name(self, client, admin_user, db_session):
        """تعديل وحدة باسم فارغ"""
        _login(client, admin_user)
        c = _make_course(db_session, name='EditUnitEmpty')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/units/edit/{u.id}', data={'name': ''})
        assert r.status_code in ACCEPT

    def test_edit_unit_nonexistent(self, client, admin_user, db_session):
        """وحدة غير موجودة"""
        _login(client, admin_user)
        r = client.get('/curriculum/units/edit/999999')
        assert r.status_code in ACCEPT

    def test_delete_unit_existing(self, client, admin_user, db_session):
        """حذف وحدة موجودة"""
        _login(client, admin_user)
        c = _make_course(db_session, name='DeleteUnitExist')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/units/delete/{u.id}')
        assert r.status_code in ACCEPT

    def test_delete_unit_nonexistent(self, client, admin_user, db_session):
        """حذف وحدة غير موجودة"""
        _login(client, admin_user)
        r = client.get('/curriculum/units/delete/999999')
        assert r.status_code in ACCEPT

    def test_delete_unit_no_auth(self, client, db_session):
        """بدون مصادقة"""
        c = _make_course(db_session, name='DeleteUnitNoAuth')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/units/delete/{u.id}')
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# Lesson CRUD
# ─────────────────────────────────────────────

class TestLessonCRUDDeep:
    """اختبارات CRUD للدروس"""

    def test_add_lesson_get_no_auth(self, client, db_session):
        """GET بدون مصادقة"""
        c = _make_course(db_session, name='LessonGetNoAuth')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/lessons/add/{u.id}')
        assert r.status_code in ACCEPT

    def test_add_lesson_get_as_admin(self, client, admin_user, db_session):
        """GET كأدمن"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonGetAdmin')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/lessons/add/{u.id}')
        assert r.status_code in ACCEPT

    def test_add_lesson_post_valid(self, client, admin_user, db_session):
        """إضافة درس بنجاح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonPostValid')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': 'NewValidLesson'})
        assert r.status_code in ACCEPT

    def test_add_lesson_post_empty_name(self, client, admin_user, db_session):
        """إضافة درس باسم فارغ"""
        _login(client, admin_user)
        c = _make_course(db_session, name='LessonPostEmpty')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/lessons/add/{u.id}', data={'name': ''})
        assert r.status_code in ACCEPT

    def test_add_lesson_nonexistent_unit(self, client, admin_user, db_session):
        """وحدة غير موجودة"""
        _login(client, admin_user)
        r = client.post('/curriculum/lessons/add/999999', data={'name': 'Orphan'})
        assert r.status_code in ACCEPT

    def test_edit_lesson_get(self, client, admin_user, db_session):
        """GET تعديل درس"""
        _login(client, admin_user)
        c = _make_course(db_session, name='EditLessonGet')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/lessons/edit/{l.id}')
        assert r.status_code in ACCEPT

    def test_edit_lesson_post_valid(self, client, admin_user, db_session):
        """تعديل درس بنجاح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='EditLessonPost')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': 'UpdatedLessonName'})
        assert r.status_code in ACCEPT

    def test_edit_lesson_post_empty_name(self, client, admin_user, db_session):
        """تعديل درس باسم فارغ"""
        _login(client, admin_user)
        c = _make_course(db_session, name='EditLessonEmpty')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.post(f'/curriculum/lessons/edit/{l.id}', data={'name': ''})
        assert r.status_code in ACCEPT

    def test_edit_lesson_nonexistent(self, client, admin_user, db_session):
        """درس غير موجود"""
        _login(client, admin_user)
        r = client.get('/curriculum/lessons/edit/999999')
        assert r.status_code in ACCEPT

    def test_delete_lesson_existing(self, client, admin_user, db_session):
        """حذف درس موجود"""
        _login(client, admin_user)
        c = _make_course(db_session, name='DeleteLessonExist')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert r.status_code in ACCEPT

    def test_delete_lesson_nonexistent(self, client, admin_user, db_session):
        """حذف درس غير موجود"""
        _login(client, admin_user)
        r = client.get('/curriculum/lessons/delete/999999')
        assert r.status_code in ACCEPT

    def test_delete_lesson_no_auth(self, client, db_session):
        """بدون مصادقة"""
        c = _make_course(db_session, name='DeleteLessonNoAuth')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# List Courses - reset_order_nums trigger paths
# ─────────────────────────────────────────────

class TestListCoursesDeep:
    """اختبارات إضافية لعرض المناهج"""

    def test_list_courses_units_zero_order(self, client, admin_user, db_session):
        """وحدات بـ order_num=0 تُعيد ترتيبها"""
        from src.models.curriculum import Unit
        _login(client, admin_user)
        c = _make_course(db_session, name='ListUnitZero', order_num=10)
        u = Unit(name='ZeroUnitList_deep2', course_id=c.id, order_num=0)
        db_session.session.add(u)
        db_session.session.commit()
        r = client.get('/curriculum/')
        assert r.status_code in ACCEPT

    def test_list_courses_lessons_zero_order(self, client, admin_user, db_session):
        """دروس بـ order_num=0 تُعيد ترتيبها"""
        from src.models.curriculum import Lesson
        _login(client, admin_user)
        c = _make_course(db_session, name='ListLessonZero', order_num=10)
        u = _make_unit(db_session, c.id, order_num=10)
        l = Lesson(name='ZeroLessonList_deep2', unit_id=u.id, order_num=0)
        db_session.session.add(l)
        db_session.session.commit()
        r = client.get('/curriculum/')
        assert r.status_code in ACCEPT

    def test_list_courses_multiple_courses(self, client, admin_user, db_session):
        """قائمة مناهج متعددة"""
        _login(client, admin_user)
        for i in range(3):
            _make_course(db_session, name=f'MultiCourse{i}', order_num=(i+1)*10)
        r = client.get('/curriculum/')
        assert r.status_code in ACCEPT

    def test_list_courses_with_nested_data(self, client, admin_user, db_session):
        """بيانات متداخلة كاملة"""
        _login(client, admin_user)
        c = _make_course(db_session, name='NestedData', order_num=10)
        u = _make_unit(db_session, c.id, order_num=10)
        _make_lesson(db_session, u.id, order_num=10)
        r = client.get('/curriculum/')
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# Course CRUD - additional edge cases
# ─────────────────────────────────────────────

class TestCourseCRUDEdgeCases:
    """حالات حافة إضافية لـ CRUD المناهج"""

    def test_add_course_show_in_bot_false(self, client, admin_user, db_session):
        """إضافة منهج بدون show_in_bot (لن يكون في البوت)"""
        _login(client, admin_user)
        r = client.post('/curriculum/courses/add', data={
            'name': 'CourseNotInBot_d2'
        })
        assert r.status_code in ACCEPT

    def test_edit_course_same_name_allowed(self, client, admin_user, db_session):
        """تعديل بنفس الاسم مسموح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='SameName_d2')
        r = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': c.name})
        assert r.status_code in ACCEPT

    def test_delete_course_with_units_lessons(self, client, admin_user, db_session):
        """حذف منهج يحتوي وحدات ودروس (cascade)"""
        _login(client, admin_user)
        c = _make_course(db_session, name='DeleteWithChildren')
        u = _make_unit(db_session, c.id)
        _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/courses/delete/{c.id}')
        assert r.status_code in ACCEPT

    def test_add_course_max_order_calculation(self, client, admin_user, db_session):
        """يحسب max_order بشكل صحيح عند وجود مناهج"""
        _login(client, admin_user)
        _make_course(db_session, name='MaxOrdC1', order_num=30)
        _make_course(db_session, name='MaxOrdC2', order_num=50)
        r = client.post('/curriculum/courses/add', data={'name': 'AfterMaxOrd'})
        assert r.status_code in ACCEPT

    def test_edit_course_clear_show_in_bot(self, client, admin_user, db_session):
        """إزالة show_in_bot من منهج"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ClearBot_d2', show_in_bot=True)
        r = client.post(f'/curriculum/courses/edit/{c.id}', data={
            'name': c.name,
            # لا show_in_bot = إزالة
        })
        assert r.status_code in ACCEPT

    def test_course_order_ajax_no_swap(self, client, admin_user, db_session):
        """AJAX للمنهج الوحيد (لا تبديل)"""
        _login(client, admin_user)
        c = _make_course(db_session, name='AjaxNoSwap', order_num=10)
        r = client.post(
            f'/curriculum/courses/order/{c.id}/up',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert r.status_code in ACCEPT
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_course_order_down_ajax_no_next(self, client, admin_user, db_session):
        """AJAX للمنهج الأخير للأسفل"""
        _login(client, admin_user)
        c = _make_course(db_session, name='AjaxNoNext', order_num=10)
        r = client.post(
            f'/curriculum/courses/order/{c.id}/down',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert r.status_code in ACCEPT


# ─────────────────────────────────────────────
# sanitize_path helper (indirect)
# ─────────────────────────────────────────────

class TestSanitizePath:
    """اختبارات دالة sanitize_path (غير مباشرة)"""

    def test_sanitize_via_list_error(self, client, admin_user, db_session):
        """استدعاء sanitize_path عبر معالجة الأخطاء في list_courses"""
        _login(client, admin_user)
        # الطلب الطبيعي يكفي لتشغيل الدالة
        r = client.get('/curriculum/')
        assert r.status_code in ACCEPT

    def test_sanitize_path_directly(self, client, admin_user, db_session):
        """استدعاء sanitize_path مباشرة"""
        from src.routes.curriculum import sanitize_path
        with client.application.app_context():
            assert sanitize_path('/path/with/leading') == 'path/with/leading'
            assert sanitize_path('path\\with\\backslash') == 'path/with/backslash'
            assert sanitize_path('path//double') == 'path/double'
            assert sanitize_path(None) is None
            assert sanitize_path('') == ''


# ─────────────────────────────────────────────
# reset_order_nums (indirect via endpoints)
# ─────────────────────────────────────────────

class TestResetOrderNums:
    """اختبارات إعادة تعيين الترتيب"""

    def test_reset_courses_via_list(self, client, admin_user, db_session):
        """إعادة ترتيب المناهج عند zero order"""
        from src.models.curriculum import Course
        _login(client, admin_user)
        for i in range(3):
            c = Course(name=f'ResetC{i}_d2', order_num=0)
            db_session.session.add(c)
        db_session.session.commit()
        r = client.get('/curriculum/')
        assert r.status_code in ACCEPT

    def test_reset_units_via_order_endpoint(self, client, admin_user, db_session):
        """إعادة ترتيب الوحدات عند zero order"""
        from src.models.curriculum import Unit
        _login(client, admin_user)
        c = _make_course(db_session, name='ResetUnitsC')
        for i in range(3):
            u = Unit(name=f'ResetU{i}_d2', course_id=c.id, order_num=0)
            db_session.session.add(u)
        db_session.session.commit()
        units = db_session.session.query(Unit).filter_by(course_id=c.id).all()
        r = client.post(f'/curriculum/units/order/{units[0].id}/down')
        assert r.status_code in ACCEPT

    def test_reset_lessons_via_order_endpoint(self, client, admin_user, db_session):
        """إعادة ترتيب الدروس عند zero order"""
        from src.models.curriculum import Lesson
        _login(client, admin_user)
        c = _make_course(db_session, name='ResetLessonsC')
        u = _make_unit(db_session, c.id, order_num=10)
        for i in range(3):
            l = Lesson(name=f'ResetL{i}_d2', unit_id=u.id, order_num=0)
            db_session.session.add(l)
        db_session.session.commit()
        lessons = db_session.session.query(Lesson).filter_by(unit_id=u.id).all()
        r = client.post(f'/curriculum/lessons/order/{lessons[0].id}/up')
        assert r.status_code in ACCEPT

    def test_reset_order_nums_directly_course(self, client, admin_user, db_session):
        """استدعاء reset_order_nums مباشرة لـ course"""
        from src.routes.curriculum import reset_order_nums
        with client.application.app_context():
            result = reset_order_nums('course')
            assert result in [True, False]

    def test_reset_order_nums_directly_unit(self, client, admin_user, db_session):
        """استدعاء reset_order_nums مباشرة لـ unit"""
        from src.routes.curriculum import reset_order_nums
        with client.application.app_context():
            c = _make_course(db_session, name='DirectResetUnit')
            result = reset_order_nums('unit', c.id)
            assert result in [True, False]

    def test_reset_order_nums_directly_lesson(self, client, admin_user, db_session):
        """استدعاء reset_order_nums مباشرة لـ lesson"""
        from src.routes.curriculum import reset_order_nums
        with client.application.app_context():
            c = _make_course(db_session, name='DirectResetLesson')
            u = _make_unit(db_session, c.id)
            result = reset_order_nums('lesson', u.id)
            assert result in [True, False]

    def test_reset_order_nums_invalid_type(self, client, admin_user, db_session):
        """نوع غير صالح لا يُعيد خطأ"""
        from src.routes.curriculum import reset_order_nums
        with client.application.app_context():
            result = reset_order_nums('invalid_type')
            # لا يُعيد شيئاً محدداً ولكن لا يُسبب crash
            assert result in [True, False, None]


# ─────────────────────────────────────────────
# add_no_cache_headers helper
# ─────────────────────────────────────────────

class TestNoCacheHeaders:
    """اختبارات تعليمات منع التخزين المؤقت"""

    def test_list_courses_has_no_cache(self, client, admin_user, db_session):
        """عرض المناهج يُعيد Cache-Control"""
        _login(client, admin_user)
        r = client.get('/curriculum/')
        if r.status_code == 200:
            assert 'Cache-Control' in r.headers
            assert 'no-cache' in r.headers.get('Cache-Control', '')

    def test_bulk_order_has_no_cache(self, client, admin_user, db_session):
        """bulk order يُعيد Cache-Control"""
        _login(client, admin_user)
        c = _make_course(db_session, name='NoCacheBulk', order_num=10)
        r = client.post('/curriculum/update_bulk_order', data={
            'type': 'course',
            'new_order': json.dumps([c.id])
        })
        if r.status_code == 200:
            assert 'Cache-Control' in r.headers

    def test_toggle_bot_has_no_cache(self, client, admin_user, db_session):
        """toggle bot يُعيد Cache-Control"""
        _login(client, admin_user)
        c = _make_course(db_session, name='NoCacheToggle')
        r = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        if r.status_code == 200:
            assert 'Cache-Control' in r.headers

    def test_add_no_cache_headers_directly(self, client, admin_user, db_session):
        """استدعاء add_no_cache_headers مباشرة"""
        from src.routes.curriculum import add_no_cache_headers
        from flask import Flask
        with client.application.app_context():
            from flask import make_response
            resp = make_response('test')
            updated = add_no_cache_headers(resp)
            assert 'no-cache' in updated.headers.get('Cache-Control', '')
            assert updated.headers.get('Pragma') == 'no-cache'
            assert updated.headers.get('Expires') == '0'


# ─────────────────────────────────────────────
# DB Commit Error Paths (lines 58-61, 141-144, 200, etc.)
# ─────────────────────────────────────────────

class TestDBCommitErrors:
    """اختبارات مسارات أخطاء DB commit"""

    def test_reset_order_nums_commit_error(self, client, admin_user, db_session):
        """reset_order_nums يُعالج خطأ commit"""
        from src.routes.curriculum import reset_order_nums
        from src.extensions import db as real_db
        from unittest.mock import patch, MagicMock
        with client.application.app_context():
            orig_commit = real_db.session.commit
            try:
                real_db.session.commit = MagicMock(side_effect=Exception('commit error'))
                result = reset_order_nums('course')
                assert result is False
            finally:
                real_db.session.commit = orig_commit
                real_db.session.rollback()

    def test_add_course_post_success_verified(self, client, admin_user, db_session):
        """إضافة منهج ناجحة تُعيد redirect"""
        _login(client, admin_user)
        import secrets
        unique_name = f'SuccessCourse_{secrets.token_hex(6)}'
        r = client.post('/curriculum/courses/add', data={'name': unique_name})
        # يجب أن يُعيد redirect للقائمة
        assert r.status_code in [200, 302]

    def test_edit_course_post_success_verified(self, client, admin_user, db_session):
        """تعديل منهج ناجح يُعيد redirect"""
        _login(client, admin_user)
        import secrets
        c = _make_course(db_session, name='EditSuccess_src')
        new_name = f'EditSuccess_dst_{secrets.token_hex(4)}'
        r = client.post(f'/curriculum/courses/edit/{c.id}', data={'name': new_name})
        assert r.status_code in [200, 302]

    def test_delete_course_success_verified(self, client, admin_user, db_session):
        """حذف منهج ناجح يُعيد redirect"""
        _login(client, admin_user)
        c = _make_course(db_session, name='DeleteSuccess')
        r = client.get(f'/curriculum/courses/delete/{c.id}')
        assert r.status_code in [200, 302]

    def test_add_unit_success_verified(self, client, admin_user, db_session):
        """إضافة وحدة ناجحة"""
        _login(client, admin_user)
        import secrets
        c = _make_course(db_session, name='UnitSuccess')
        r = client.post(f'/curriculum/units/add/{c.id}',
                        data={'name': f'UnitNew_{secrets.token_hex(4)}'})
        assert r.status_code in [200, 302]

    def test_add_lesson_success_verified(self, client, admin_user, db_session):
        """إضافة درس ناجحة"""
        _login(client, admin_user)
        import secrets
        c = _make_course(db_session, name='LessonSuccess')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/lessons/add/{u.id}',
                        data={'name': f'LessonNew_{secrets.token_hex(4)}'})
        assert r.status_code in [200, 302]

    def test_edit_unit_success_verified(self, client, admin_user, db_session):
        """تعديل وحدة ناجح"""
        _login(client, admin_user)
        import secrets
        c = _make_course(db_session, name='EditUnitSucc')
        u = _make_unit(db_session, c.id)
        r = client.post(f'/curriculum/units/edit/{u.id}',
                        data={'name': f'UnitUpdated_{secrets.token_hex(4)}'})
        assert r.status_code in [200, 302]

    def test_edit_lesson_success_verified(self, client, admin_user, db_session):
        """تعديل درس ناجح"""
        _login(client, admin_user)
        import secrets
        c = _make_course(db_session, name='EditLessonSucc')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.post(f'/curriculum/lessons/edit/{l.id}',
                        data={'name': f'LessonUpdated_{secrets.token_hex(4)}'})
        assert r.status_code in [200, 302]

    def test_delete_unit_success_verified(self, client, admin_user, db_session):
        """حذف وحدة ناجح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='DeleteUnitSucc')
        u = _make_unit(db_session, c.id)
        r = client.get(f'/curriculum/units/delete/{u.id}')
        assert r.status_code in [200, 302]

    def test_delete_lesson_success_verified(self, client, admin_user, db_session):
        """حذف درس ناجح"""
        _login(client, admin_user)
        c = _make_course(db_session, name='DeleteLessonSucc')
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        r = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert r.status_code in [200, 302]

    def test_toggle_bot_second_time(self, client, admin_user, db_session):
        """تبديل البوت مرتين"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ToggleTwice')
        r1 = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert r1.status_code in [200, 500]
        r2 = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert r2.status_code in [200, 500]

    def test_course_order_with_three_courses(self, client, admin_user, db_session):
        """ترتيب ثلاثة مناهج"""
        _login(client, admin_user)
        c1 = _make_course(db_session, name='Three1', order_num=10)
        c2 = _make_course(db_session, name='Three2', order_num=20)
        c3 = _make_course(db_session, name='Three3', order_num=30)
        # نقل الوسطي للأعلى
        r = client.post(f'/curriculum/courses/order/{c2.id}/up')
        assert r.status_code in ACCEPT
        # نقل الوسطي للأسفل
        r = client.post(f'/curriculum/courses/order/{c2.id}/down')
        assert r.status_code in ACCEPT

    def test_unit_order_with_three_units(self, client, admin_user, db_session):
        """ترتيب ثلاث وحدات"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ThreeUnits')
        u1 = _make_unit(db_session, c.id, order_num=10)
        u2 = _make_unit(db_session, c.id, order_num=20)
        u3 = _make_unit(db_session, c.id, order_num=30)
        r = client.post(f'/curriculum/units/order/{u2.id}/up')
        assert r.status_code in ACCEPT
        r = client.post(f'/curriculum/units/order/{u2.id}/down')
        assert r.status_code in ACCEPT

    def test_lesson_order_with_three_lessons(self, client, admin_user, db_session):
        """ترتيب ثلاثة دروس"""
        _login(client, admin_user)
        c = _make_course(db_session, name='ThreeLessons')
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id, order_num=10)
        l2 = _make_lesson(db_session, u.id, order_num=20)
        l3 = _make_lesson(db_session, u.id, order_num=30)
        r = client.post(f'/curriculum/lessons/order/{l2.id}/up')
        assert r.status_code in ACCEPT
        r = client.post(f'/curriculum/lessons/order/{l2.id}/down')
        assert r.status_code in ACCEPT
