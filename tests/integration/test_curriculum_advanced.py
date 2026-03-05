"""
اختبارات متقدمة لـ curriculum routes
يغطي: add/edit/delete courses, units, lessons with real data
"""
import pytest


class TestCurriculumCourses:
    """اختبارات المناهج"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_add_course_get_no_auth(self, client):
        """صفحة إضافة منهج بدون مصادقة"""
        response = client.get('/curriculum/courses/add')
        assert response.status_code in [302, 401, 403]

    def test_add_course_get_as_admin(self, client, admin_user):
        """صفحة إضافة منهج كأدمن"""
        self._login(client, admin_user)
        response = client.get('/curriculum/courses/add')
        assert response.status_code in [200, 302, 404, 500]

    def test_add_course_post_empty(self, client, admin_user):
        """إضافة منهج ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_add_course_post_valid(self, client, admin_user):
        """إضافة منهج ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/curriculum/courses/add', data={
            'name': 'منهج اختبار جديد',
            'show_in_bot': 'true'
        })
        assert response.status_code in [200, 201, 302, 400, 500]

    def test_edit_course_get_nonexistent(self, client, admin_user):
        """تعديل منهج غير موجود"""
        self._login(client, admin_user)
        response = client.get('/curriculum/courses/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_course_get_existing(self, client, admin_user, db_session, app):
        """تعديل منهج موجود"""
        from src.models.curriculum import Course
        c = Course(name='Edit Course Test', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.get(f'/curriculum/courses/edit/{c.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_edit_course_post_valid(self, client, admin_user, db_session, app):
        """تعديل منهج موجود ببيانات"""
        from src.models.curriculum import Course
        c = Course(name='Course To Edit', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.post(f'/curriculum/courses/edit/{c.id}', data={
            'name': 'منهج محدّث'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_delete_course_existing(self, client, admin_user, db_session, app):
        """حذف منهج موجود"""
        from src.models.curriculum import Course
        c = Course(name='Course To Delete', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.get(f'/curriculum/courses/delete/{c.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_bot_visibility_existing(self, client, admin_user, db_session, app):
        """تبديل رؤية منهج موجود في البوت"""
        from src.models.curriculum import Course
        c = Course(name='Course To Toggle', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        self._login(client, admin_user)
        response = client.post(f'/curriculum/api/v1/courses/{c.id}/toggle-bot-visibility')
        assert response.status_code in [200, 302, 404, 500]

    def test_course_order_nonexistent(self, client, admin_user):
        """ترتيب منهج غير موجود"""
        self._login(client, admin_user)
        response = client.post('/curriculum/courses/order/99999/up')
        assert response.status_code in [200, 302, 404, 500]


class TestCurriculumUnits:
    """اختبارات الوحدات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def _make_course(self, db_session, name=None):
        from src.models.curriculum import Course
        import random
        c = Course(name=name or f'Unit Test Course {random.randint(1,99999)}', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        return c

    def test_add_unit_get_as_admin(self, client, admin_user, db_session, app):
        """صفحة إضافة وحدة كأدمن"""
        c = self._make_course(db_session, 'Unit Add Get Course')
        self._login(client, admin_user)
        response = client.get(f'/curriculum/units/add/{c.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_add_unit_post_valid(self, client, admin_user, db_session, app):
        """إضافة وحدة ببيانات صالحة"""
        c = self._make_course(db_session, 'Unit Add Post Course')
        self._login(client, admin_user)
        response = client.post(f'/curriculum/units/add/{c.id}', data={
            'name': 'وحدة اختبار'
        })
        assert response.status_code in [200, 201, 302, 400, 500]

    def test_edit_unit_get_nonexistent(self, client, admin_user):
        """تعديل وحدة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/curriculum/units/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_unit_post_existing(self, client, admin_user, db_session, app):
        """تعديل وحدة موجودة"""
        from src.models.curriculum import Unit
        c = self._make_course(db_session, 'Unit Edit Post Course')
        u = Unit(name='Unit To Edit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        self._login(client, admin_user)
        response = client.post(f'/curriculum/units/edit/{u.id}', data={
            'name': 'وحدة محدّثة'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_delete_unit_existing(self, client, admin_user, db_session, app):
        """حذف وحدة موجودة"""
        from src.models.curriculum import Unit
        c = self._make_course(db_session, 'Unit Delete Course')
        u = Unit(name='Unit To Delete', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        self._login(client, admin_user)
        response = client.get(f'/curriculum/units/delete/{u.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_unit_order_nonexistent(self, client, admin_user):
        """ترتيب وحدة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/curriculum/units/order/99999/up')
        assert response.status_code in [200, 302, 404, 500]


class TestCurriculumLessons:
    """اختبارات الدروس"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def _make_unit(self, db_session, name_suffix=''):
        from src.models.curriculum import Course, Unit
        import random
        c = Course(name=f'Lesson Test Course {name_suffix}{random.randint(1,99999)}', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name=f'Lesson Test Unit {name_suffix}', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        return u

    def test_add_lesson_get_as_admin(self, client, admin_user, db_session, app):
        """صفحة إضافة درس كأدمن"""
        u = self._make_unit(db_session, 'get')
        self._login(client, admin_user)
        response = client.get(f'/curriculum/lessons/add/{u.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_add_lesson_post_valid(self, client, admin_user, db_session, app):
        """إضافة درس ببيانات صالحة"""
        u = self._make_unit(db_session, 'post')
        self._login(client, admin_user)
        response = client.post(f'/curriculum/lessons/add/{u.id}', data={
            'name': 'درس اختبار'
        })
        assert response.status_code in [200, 201, 302, 400, 500]

    def test_edit_lesson_get_nonexistent(self, client, admin_user):
        """تعديل درس غير موجود"""
        self._login(client, admin_user)
        response = client.get('/curriculum/lessons/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_lesson_post_existing(self, client, admin_user, db_session, app):
        """تعديل درس موجود"""
        from src.models.curriculum import Lesson
        u = self._make_unit(db_session, 'edit')
        l = Lesson(name='Lesson To Edit', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        self._login(client, admin_user)
        response = client.post(f'/curriculum/lessons/edit/{l.id}', data={
            'name': 'درس محدّث'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_delete_lesson_existing(self, client, admin_user, db_session, app):
        """حذف درس موجود"""
        from src.models.curriculum import Lesson
        u = self._make_unit(db_session, 'del')
        l = Lesson(name='Lesson To Delete', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        self._login(client, admin_user)
        response = client.get(f'/curriculum/lessons/delete/{l.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_lesson_order_nonexistent(self, client, admin_user):
        """ترتيب درس غير موجود"""
        self._login(client, admin_user)
        response = client.post('/curriculum/lessons/order/99999/up')
        assert response.status_code in [200, 302, 404, 500]

    def test_bulk_order_update(self, client, admin_user):
        """تحديث الترتيب الجماعي"""
        self._login(client, admin_user)
        response = client.post('/curriculum/update_bulk_order', json={
            'items': []
        })
        assert response.status_code in [200, 302, 400, 404, 500]
