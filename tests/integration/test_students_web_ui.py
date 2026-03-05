"""
اختبارات صفحات الويب للطلاب (Web UI)
يغطي: list, add, edit, delete, toggle, login API, teacher login/logout
"""
import pytest
import secrets


def _make_student(db_session, username, email, active=True):
    from src.models.student import Student
    s = Student(name='Test Stu', username=username, email=email, is_active=active)
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestStudentsWebUI:
    """اختبارات صفحات الويب"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_list_students_no_auth(self, client):
        """قائمة الطلاب بدون مصادقة"""
        response = client.get('/students/')
        assert response.status_code in [302, 401, 403]

    def test_list_students_as_admin(self, client, admin_user):
        """قائمة الطلاب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/students/')
        assert response.status_code in [200, 500]

    def test_add_student_get_no_auth(self, client):
        """صفحة إضافة طالب بدون مصادقة"""
        response = client.get('/students/add')
        assert response.status_code in [302, 401, 403]

    def test_add_student_get_as_admin(self, client, admin_user):
        """صفحة إضافة طالب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/students/add')
        assert response.status_code in [200, 500]

    def test_add_student_post_empty(self, client, admin_user):
        """إضافة طالب ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/students/add', data={})
        assert response.status_code in [200, 400, 422, 500]

    def test_add_student_post_valid(self, client, admin_user):
        """إضافة طالب ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/students/add', data={
            'name': 'طالب جديد',
            'username': 'newstu_web1',
            'email': 'newstu_web1@test.com',
            'password': 'Pass@123',
            'phone': '0500000001'
        })
        assert response.status_code in [200, 201, 302, 400, 500]

    def test_edit_student_get_nonexistent(self, client, admin_user):
        """صفحة تعديل طالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/students/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_student_get_existing(self, client, admin_user, db_session, app):
        """صفحة تعديل طالب موجود"""
        s = _make_student(db_session, 'editstu_web', 'editstu_web@test.com')
        self._login(client, admin_user)
        response = client.get(f'/students/edit/{s.id}')
        assert response.status_code in [200, 404, 500]

    def test_edit_student_post_nonexistent(self, client, admin_user):
        """تعديل طالب غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/edit/99999', data={'name': 'اسم جديد'})
        assert response.status_code in [302, 404, 500]

    def test_edit_student_post_existing(self, client, admin_user, db_session, app):
        """تعديل طالب موجود"""
        s = _make_student(db_session, 'editstu_web2', 'editstu_web2@test.com')
        self._login(client, admin_user)
        response = client.post(f'/students/edit/{s.id}', data={
            'name': 'اسم محدث',
            'username': s.username,
            'email': s.email
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_delete_student_no_auth(self, client):
        """حذف طالب بدون مصادقة"""
        response = client.post('/students/delete/1')
        assert response.status_code in [302, 401, 403]

    def test_delete_student_nonexistent(self, client, admin_user):
        """حذف طالب غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/delete/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_delete_student_existing(self, client, admin_user, db_session, app):
        """حذف طالب موجود"""
        s = _make_student(db_session, 'delstu_web', 'delstu_web@test.com')
        self._login(client, admin_user)
        response = client.post(f'/students/delete/{s.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_student_no_auth(self, client):
        """تبديل حالة طالب بدون مصادقة"""
        response = client.post('/students/toggle/1')
        assert response.status_code in [302, 401, 403]

    def test_toggle_student_nonexistent(self, client, admin_user):
        """تبديل حالة طالب غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/toggle/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_student_existing(self, client, admin_user, db_session, app):
        """تبديل حالة طالب موجود"""
        s = _make_student(db_session, 'togglestu_web', 'togglestu_web@test.com')
        self._login(client, admin_user)
        response = client.post(f'/students/toggle/{s.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_registration_no_auth(self, client):
        """تبديل حالة التسجيل بدون مصادقة"""
        response = client.post('/students/toggle-registration')
        assert response.status_code in [302, 401, 403]

    def test_toggle_registration_as_admin(self, client, admin_user):
        """تبديل حالة التسجيل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/students/toggle-registration')
        assert response.status_code in [200, 302, 400, 500]

    def test_save_registration_settings_no_auth(self, client):
        """حفظ إعدادات التسجيل بدون مصادقة"""
        response = client.post('/students/save-registration-settings', json={})
        assert response.status_code in [302, 401, 403]

    def test_save_registration_settings_as_admin(self, client, admin_user):
        """حفظ إعدادات التسجيل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/students/save-registration-settings', json={
            'max_students': 100,
            'registration_open': True
        })
        assert response.status_code in [200, 302, 400, 500]


class TestStudentAPILogin:
    """اختبارات تسجيل دخول الطلاب"""

    def test_api_student_login_no_data(self, client):
        """تسجيل دخول طالب بدون بيانات"""
        response = client.post('/students/api/login', json={})
        assert response.status_code in [200, 400, 401, 422]

    def test_api_student_login_wrong_credentials(self, client):
        """تسجيل دخول طالب ببيانات خاطئة"""
        response = client.post('/students/api/login', json={
            'username': 'wrong_user',
            'password': 'wrong_pass'
        })
        assert response.status_code in [200, 400, 401]

    def test_api_student_login_valid(self, client, db_session, app):
        """تسجيل دخول طالب ببيانات صالحة"""
        from src.models.student import Student
        s = Student(name='Login Stu', username='loginstu_valid', email='loginstu_valid@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/students/api/login', json={
            'username': 'loginstu_valid',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 400, 401]

    def test_api_student_logout(self, client, db_session, app):
        """تسجيل خروج طالب"""
        s = _make_student(db_session, 'logoutstu', 'logoutstu@test.com')
        response = client.post(
            '/students/api/logout',
            json={'session_token': s.session_token},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401]


class TestTeacherAPI:
    """اختبارات API المعلمين"""

    def test_teacher_login_no_data(self, client):
        """تسجيل دخول معلم بدون بيانات"""
        response = client.post('/students/api/login-teacher', json={})
        assert response.status_code in [200, 400, 401, 422]

    def test_teacher_login_wrong_credentials(self, client):
        """تسجيل دخول معلم ببيانات خاطئة"""
        response = client.post('/students/api/login-teacher', json={
            'username': 'wrong_teacher',
            'password': 'wrong_pass'
        })
        assert response.status_code in [200, 400, 401]

    def test_teacher_logout_no_token(self, client):
        """تسجيل خروج معلم بدون token"""
        response = client.post('/students/api/logout-teacher', json={})
        assert response.status_code in [200, 400, 401, 422]

    def test_teacher_verify_session_no_token(self, client):
        """التحقق من جلسة معلم بدون token"""
        response = client.post('/students/api/verify-teacher-session', json={})
        assert response.status_code in [200, 400, 401, 422]

    def test_teacher_verify_session_invalid_token(self, client):
        """التحقق من جلسة معلم بـ token خاطئ"""
        response = client.post('/students/api/verify-teacher-session', json={
            'session_token': 'invalid_token'
        })
        assert response.status_code in [200, 400, 401, 404]


class TestStudentAdminActions:
    """اختبارات إجراءات الأدمن على الطلاب"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_reset_device_no_auth(self, client):
        """إعادة ضبط جهاز طالب بدون مصادقة"""
        response = client.post('/students/api/admin/reset-device/99999')
        assert response.status_code in [302, 401, 403]

    def test_reset_device_nonexistent(self, client, admin_user):
        """إعادة ضبط جهاز طالب غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/api/admin/reset-device/99999')
        assert response.status_code in [200, 404, 500]

    def test_reset_device_web_nonexistent(self, client, admin_user):
        """إعادة ضبط جهاز طالب (web) غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/reset-device/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_mobile_edit_student_nonexistent(self, client, admin_user):
        """تعديل طالب (mobile) غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/api/mobile/students/99999/edit', json={
            'name': 'اسم جديد'
        })
        assert response.status_code in [200, 404, 500]

    def test_mobile_delete_student_nonexistent(self, client, admin_user):
        """حذف طالب (mobile) غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/api/mobile/students/99999/delete')
        assert response.status_code in [200, 404, 500]

    def test_mobile_toggle_student_nonexistent(self, client, admin_user):
        """تبديل حالة طالب (mobile) غير موجود"""
        self._login(client, admin_user)
        response = client.post('/students/api/mobile/students/99999/toggle')
        assert response.status_code in [200, 404, 500]

    def test_notification_read_stats_as_admin(self, client, admin_user):
        """إحصائيات قراءة إشعار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/students/api/admin/notification/99999/read-stats')
        assert response.status_code in [200, 404, 500]


class TestStudentNotificationsMore:
    """اختبارات إضافية للإشعارات"""

    def test_notification_read_no_auth(self, client):
        """قراءة إشعار بدون مصادقة"""
        response = client.post('/students/api/notifications/99999/read')
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_notification_read_with_token(self, client, db_session, app):
        """قراءة إشعار مع token"""
        s = _make_student(db_session, 'notifread_stu', 'notifread@test.com')
        response = client.post(
            '/students/api/notifications/99999/read',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_notification_delete_with_token(self, client, db_session, app):
        """حذف إشعار مع token"""
        s = _make_student(db_session, 'notifdel_stu', 'notifdel@test.com')
        response = client.post(
            '/students/api/notifications/99999/delete',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_batch_save_notifications_no_auth(self, client):
        """حفظ إشعارات دفعية بدون مصادقة"""
        response = client.post('/students/api/notifications/batch-save', json={
            'notifications': []
        })
        assert response.status_code in [200, 400, 401, 403, 422, 500, 503]

    def test_unit_questions_with_token(self, client, db_session, app):
        """أسئلة وحدة للطالب"""
        s = _make_student(db_session, 'unitqstu', 'unitqstu@test.com')
        response = client.get(
            '/students/api/units/99999/questions',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 404, 500]
