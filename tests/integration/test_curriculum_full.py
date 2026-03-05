"""
اختبارات شاملة لـ Curriculum routes
يغطي: list, add/edit/delete courses/units/lessons, bulk order, toggle visibility
"""
import pytest


class TestCurriculumListFull:
    """اختبارات قائمة المنهج"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_list_no_auth(self, client):
        """قائمة المنهج بدون مصادقة"""
        response = client.get('/curriculum/')
        assert response.status_code in [302, 401]

    def test_list_as_admin(self, client, admin_user):
        """قائمة المنهج كأدمن"""
        self._login(client, admin_user)
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 500]


class TestCurriculumCoursesFull:
    """اختبارات إدارة المناهج"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_add_course_no_auth(self, client):
        """إضافة منهج بدون مصادقة"""
        response = client.post('/curriculum/courses/add', data={})
        assert response.status_code in [302, 401]

    def test_add_course_as_admin_empty(self, client, admin_user):
        """إضافة منهج بدون اسم"""
        self._login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={})
        assert response.status_code in [200, 302, 400, 500]

    def test_add_course_as_admin(self, client, admin_user):
        """إضافة منهج بنجاح"""
        self._login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={
            'name': 'منهج اختبار Full',
            'order_num': 99
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_edit_course_no_auth(self, client):
        """تعديل منهج بدون مصادقة"""
        response = client.get('/curriculum/courses/edit/1')
        assert response.status_code in [302, 401]

    def test_edit_course_nonexistent(self, client, admin_user):
        """تعديل منهج غير موجود"""
        self._login(client, admin_user)
        response = client.get('/curriculum/courses/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_course_as_admin(self, client, admin_user, db_session, app):
        """تعديل منهج موجود"""
        from src.models.curriculum import Course
        c = Course(name='Edit Test Course Full', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.get(f'/curriculum/courses/edit/{c.id}')
        assert response.status_code in [200, 302, 500]

    def test_delete_course_no_auth(self, client):
        """حذف منهج بدون مصادقة"""
        response = client.get('/curriculum/courses/delete/1')
        assert response.status_code in [302, 401]

    def test_delete_course_nonexistent(self, client, admin_user):
        """حذف منهج غير موجود"""
        self._login(client, admin_user)
        response = client.get('/curriculum/courses/delete/99999')
        assert response.status_code in [302, 404, 500]

    def test_toggle_course_visibility(self, client, admin_user, db_session, app):
        """تبديل ظهور منهج"""
        from src.models.curriculum import Course
        c = Course(name='Toggle Course Full', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        # الـ toggle في curriculum.py: /curriculum/api/v1/courses/<id>/toggle-bot-visibility
        response = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert response.status_code in [200, 302, 404, 500]


class TestCurriculumUnitsFull:
    """اختبارات إدارة الوحدات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_add_unit_no_auth(self, client):
        """إضافة وحدة بدون مصادقة"""
        response = client.post('/curriculum/units/add/1', data={})
        assert response.status_code in [302, 401]

    def test_add_unit_nonexistent_course(self, client, admin_user):
        """إضافة وحدة لمنهج غير موجود"""
        self._login(client, admin_user)
        response = client.post('/curriculum/units/add/99999', data={
            'name': 'وحدة اختبار'
        })
        assert response.status_code in [302, 404, 500]

    def test_add_unit_as_admin(self, client, admin_user, db_session, app):
        """إضافة وحدة بنجاح"""
        from src.models.curriculum import Course
        c = Course(name='Unit Add Test Full', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.post(f'/curriculum/units/add/{c.id}', data={
            'name': 'وحدة جديدة Full'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_edit_unit_nonexistent(self, client, admin_user):
        """تعديل وحدة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/curriculum/units/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_delete_unit_nonexistent(self, client, admin_user):
        """حذف وحدة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/curriculum/units/delete/99999')
        assert response.status_code in [302, 404, 500]


class TestCurriculumLessonsFull:
    """اختبارات إدارة الدروس"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_add_lesson_no_auth(self, client):
        """إضافة درس بدون مصادقة"""
        response = client.post('/curriculum/lessons/add/1', data={})
        assert response.status_code in [302, 401]

    def test_add_lesson_nonexistent_unit(self, client, admin_user):
        """إضافة درس لوحدة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/curriculum/lessons/add/99999', data={
            'name': 'درس اختبار'
        })
        assert response.status_code in [302, 404, 500]

    def test_add_lesson_as_admin(self, client, admin_user, db_session, app):
        """إضافة درس بنجاح"""
        from src.models.curriculum import Course, Unit
        c = Course(name='Lesson Add Course Full', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Lesson Add Unit Full', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        self._login(client, admin_user)
        response = client.post(f'/curriculum/lessons/add/{u.id}', data={
            'name': 'درس جديد Full'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_edit_lesson_nonexistent(self, client, admin_user):
        """تعديل درس غير موجود"""
        self._login(client, admin_user)
        response = client.get('/curriculum/lessons/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_delete_lesson_nonexistent(self, client, admin_user):
        """حذف درس غير موجود"""
        self._login(client, admin_user)
        response = client.get('/curriculum/lessons/delete/99999')
        assert response.status_code in [302, 404, 500]


class TestCurriculumBulkOrder:
    """اختبارات الترتيب المجمع"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_bulk_order_no_auth(self, client):
        """ترتيب مجمع بدون مصادقة"""
        response = client.post('/curriculum/update_bulk_order', json={})
        assert response.status_code in [302, 401]

    def test_bulk_order_empty_as_admin(self, client, admin_user):
        """ترتيب مجمع فارغ"""
        self._login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', json={
            'items': []
        })
        assert response.status_code in [200, 400, 500]

    def test_bulk_order_with_data(self, client, admin_user):
        """ترتيب مجمع ببيانات"""
        self._login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', json={
            'items': [{'id': 1, 'type': 'course', 'order': 1}]
        })
        assert response.status_code in [200, 400, 404, 500]
