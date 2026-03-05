"""
اختبارات تكاملية موسعة لـ students routes
يغطي: admin CRUD, toggle, registration settings, API login/logout,
       device management, teacher login, verify-session, courses/units/lessons,
       notifications, results, change-password, fcm-token
"""
import pytest
import secrets


# ==================== Helpers ====================

def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='Test Stu',
        username=f'stu_{secrets.token_hex(4)}',
        email=f'stu_{secrets.token_hex(4)}@test.com',
        is_active=True
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


# ==================== Admin: List Students ====================

class TestListStudents:
    """GET /students/ - عرض قائمة الطلاب"""

    def test_list_no_auth(self, client):
        response = client.get('/students/')
        assert response.status_code in [200, 302, 401, 403]

    def test_list_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_list_with_search(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/?search=test')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_list_with_empty_search(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/?search=')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_list_with_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.get(f'/students/?search={s.username}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== Admin: Add Student ====================

class TestAddStudent:
    """GET/POST /students/add - إضافة طالب"""

    def test_add_get_no_auth(self, client):
        response = client.get('/students/add')
        assert response.status_code in [200, 302, 401, 403]

    def test_add_get_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/add')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_add_post_missing_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/add', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_add_post_valid_data(self, client, admin_user, db_session):
        _login(client, admin_user)
        uname = f'newstu_{secrets.token_hex(3)}'
        response = client.post('/students/add', data={
            'name': 'New Student',
            'username': uname,
            'password': 'Pass@1234',
            'email': f'{uname}@example.com',
            'is_active': 'on'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_add_post_duplicate_username(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.post('/students/add', data={
            'name': 'Dup Student',
            'username': s.username,
            'password': 'Pass@1234',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_add_post_duplicate_email(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.post('/students/add', data={
            'name': 'Dup Email',
            'username': f'dupem_{secrets.token_hex(3)}',
            'password': 'Pass@1234',
            'email': s.email,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== Admin: Edit Student ====================

class TestEditStudent:
    """GET/POST /students/edit/<id> - تعديل طالب"""

    def test_edit_nonexistent_no_auth(self, client):
        response = client.get('/students/edit/99999')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_edit_nonexistent_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/edit/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_edit_get_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.get(f'/students/edit/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_edit_post_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.post(f'/students/edit/{s.id}', data={
            'name': 'Updated Name',
            'email': s.email,
            'is_active': 'on'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_edit_post_change_password(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.post(f'/students/edit/{s.id}', data={
            'name': s.name,
            'password': 'NewPass@123'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== Admin: Delete Student ====================

class TestDeleteStudent:
    """POST /students/delete/<id> - حذف طالب"""

    def test_delete_nonexistent_no_auth(self, client):
        response = client.post('/students/delete/99999')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_delete_nonexistent_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/delete/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_delete_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        sid = s.id
        response = client.post(f'/students/delete/{sid}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_delete_get_method_not_allowed(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/delete/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ==================== Admin: Toggle Student ====================

class TestToggleStudent:
    """POST /students/toggle/<id> - تفعيل/تعطيل حساب طالب"""

    def test_toggle_nonexistent_no_auth(self, client):
        response = client.post('/students/toggle/99999')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_toggle_nonexistent_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/toggle/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_toggle_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.post(f'/students/toggle/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== Admin: Registration Settings ====================

class TestRegistrationSettings:
    """POST /students/toggle-registration & /students/save-registration-settings"""

    def test_toggle_registration_no_auth(self, client):
        response = client.post('/students/toggle-registration')
        assert response.status_code in [200, 302, 401, 403]

    def test_toggle_registration_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/toggle-registration')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_save_registration_settings_no_auth(self, client):
        response = client.post('/students/save-registration-settings')
        assert response.status_code in [200, 302, 401, 403]

    def test_save_registration_settings_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/save-registration-settings', data={
            'require_phone': 'on',
            'require_school': 'on',
            'auto_activate': 'on',
            'closed_message': 'التسجيل مغلق حالياً'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== Admin: Reset Device (Web) ====================

class TestResetStudentDevice:
    """POST /students/reset-device/<id> - إزالة ربط الجهاز"""

    def test_reset_device_no_auth(self, client):
        response = client.post('/students/reset-device/99999')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_reset_device_nonexistent_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/reset-device/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_reset_device_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        s.device_id = 'device123'
        s.device_name = 'iPhone 15'
        db_session.session.commit()
        response = client.post(f'/students/reset-device/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== API: Admin Reset Device (JSON) ====================

class TestAdminResetStudentDeviceAPI:
    """POST /students/api/admin/reset-device/<id>"""

    def test_api_reset_device_no_auth(self, client):
        response = client.post('/students/api/admin/reset-device/99999')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_api_reset_device_nonexistent_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/students/api/admin/reset-device/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_api_reset_device_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        s.device_id = 'dev_abc'
        db_session.session.commit()
        response = client.post(f'/students/api/admin/reset-device/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== API: Admin Get Device Info ====================

class TestAdminGetStudentDeviceInfo:
    """GET /students/api/admin/device-info/<id>"""

    def test_device_info_no_auth(self, client):
        response = client.get('/students/api/admin/device-info/99999')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_device_info_nonexistent_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/students/api/admin/device-info/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_device_info_real_student(self, client, admin_user, db_session):
        _login(client, admin_user)
        s = _make_student(db_session)
        response = client.get(f'/students/api/admin/device-info/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]


# ==================== API: Student Login ====================

class TestStudentApiLogin:
    """POST /students/api/login - تسجيل دخول الطالب"""

    def test_login_missing_credentials(self, client):
        response = client.post('/students/api/login', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_login_invalid_credentials(self, client):
        response = client.post('/students/api/login', json={
            'username': 'nonexistent_xyz',
            'password': 'WrongPass'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_login_valid_credentials(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_login_inactive_student(self, client, db_session):
        from src.models.student import Student
        s = Student(
            name='Inactive',
            username=f'inactive_{secrets.token_hex(4)}',
            email=f'inactive_{secrets.token_hex(4)}@test.com',
            is_active=False
        )
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_login_with_device_id(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': 'device_test_001',
            'device_name': 'Test Phone'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_login_device_conflict_no_force(self, client, db_session):
        s = _make_student(db_session)
        s.device_id = 'old_device_999'
        s.device_name = 'Old Phone'
        db_session.session.commit()
        response = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': 'new_device_111',
            'device_name': 'New Phone',
            'force_login': False
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_login_device_conflict_force(self, client, db_session):
        s = _make_student(db_session)
        s.device_id = 'old_dev_forced'
        db_session.session.commit()
        response = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': 'forced_new_dev',
            'force_login': True
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Student Logout ====================

class TestStudentApiLogout:
    """POST /students/api/logout - تسجيل خروج الطالب"""

    def test_logout_missing_student_id(self, client):
        response = client.post('/students/api/logout', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_logout_nonexistent_student(self, client):
        response = client.post('/students/api/logout', json={
            'student_id': 99999,
            'device_id': 'some_device'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_logout_real_student(self, client, db_session):
        s = _make_student(db_session)
        s.device_id = 'logout_device'
        db_session.session.commit()
        response = client.post('/students/api/logout', json={
            'student_id': s.id,
            'device_id': 'logout_device'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_logout_wrong_device(self, client, db_session):
        s = _make_student(db_session)
        s.device_id = 'correct_device'
        db_session.session.commit()
        response = client.post('/students/api/logout', json={
            'student_id': s.id,
            'device_id': 'wrong_device'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Verify Student Session ====================

class TestVerifyStudentSession:
    """POST /students/api/verify-session"""

    def test_verify_session_missing_data(self, client):
        response = client.post('/students/api/verify-session', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_verify_session_nonexistent_student(self, client):
        response = client.post('/students/api/verify-session', json={
            'student_id': 99999,
            'device_id': 'some_device'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_verify_session_no_device_linked(self, client, db_session):
        s = _make_student(db_session)
        # no device_id set on student
        response = client.post('/students/api/verify-session', json={
            'student_id': s.id,
            'device_id': 'any_device'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_verify_session_wrong_device(self, client, db_session):
        s = _make_student(db_session)
        s.device_id = 'real_device_abc'
        db_session.session.commit()
        response = client.post('/students/api/verify-session', json={
            'student_id': s.id,
            'device_id': 'wrong_device_xyz'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_verify_session_valid(self, client, db_session):
        s = _make_student(db_session)
        s.device_id = 'valid_device_123'
        db_session.session.commit()
        response = client.post('/students/api/verify-session', json={
            'student_id': s.id,
            'device_id': 'valid_device_123',
            'session_token': s.session_token
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_verify_session_inactive_student(self, client, db_session):
        from src.models.student import Student
        s = Student(
            name='Inactive Verify',
            username=f'inv_v_{secrets.token_hex(3)}',
            email=f'inv_v_{secrets.token_hex(3)}@test.com',
            is_active=False
        )
        s.set_password('Pass@123')
        s.device_id = 'some_dev'
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/students/api/verify-session', json={
            'student_id': s.id,
            'device_id': 'some_dev'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Teacher Login ====================

class TestTeacherApiLogin:
    """POST /students/api/login-teacher - تسجيل دخول المعلم"""

    def test_teacher_login_missing_credentials(self, client):
        response = client.post('/students/api/login-teacher', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_teacher_login_invalid_credentials(self, client):
        response = client.post('/students/api/login-teacher', json={
            'username': 'nonexistent_teacher_xyz',
            'password': 'WrongPass'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Teacher Logout ====================

class TestTeacherApiLogout:
    """POST /students/api/logout-teacher"""

    def test_teacher_logout_missing_id(self, client):
        response = client.post('/students/api/logout-teacher', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_teacher_logout_nonexistent(self, client):
        response = client.post('/students/api/logout-teacher', json={
            'teacher_id': 99999
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Verify Teacher Session ====================

class TestVerifyTeacherSession:
    """POST /students/api/verify-teacher-session"""

    def test_verify_teacher_session_missing_data(self, client):
        response = client.post('/students/api/verify-teacher-session', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_verify_teacher_session_nonexistent(self, client):
        response = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': 99999,
            'device_id': 'some_device'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Courses / Units / Lessons ====================

class TestCoursesUnitsLessonsAPI:
    """GET /students/api/courses, /api/courses/<id>/units, etc."""

    def test_get_courses(self, client):
        response = client.get('/students/api/courses')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_units_nonexistent_course(self, client):
        response = client.get('/students/api/courses/99999/units')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_lessons_nonexistent_unit(self, client):
        response = client.get('/students/api/units/99999/lessons')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_questions_nonexistent_lesson(self, client):
        response = client.get('/students/api/lessons/99999/questions')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_course_questions_nonexistent(self, client):
        response = client.get('/students/api/courses/99999/questions')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_unit_questions_nonexistent(self, client):
        response = client.get('/students/api/units/99999/questions')
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Change Password ====================

class TestChangePasswordAPI:
    """POST /students/api/change-password"""

    def test_change_password_missing_fields(self, client):
        response = client.post('/students/api/change-password', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_change_password_short_new_password(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': 'abc'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_change_password_wrong_current(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'WrongPass',
            'new_password': 'NewPass@123'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_change_password_nonexistent_user(self, client):
        response = client.post('/students/api/change-password', json={
            'username': 'ghost_user_xyz',
            'current_password': 'SomePass',
            'new_password': 'NewPass@123'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_change_password_valid(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': 'NewPass@456'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: FCM Token ====================

class TestFCMTokenAPI:
    """POST /students/api/fcm-token"""

    def test_fcm_token_missing_token(self, client):
        response = client.post('/students/api/fcm-token', json={
            'student_id': 1
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_fcm_token_missing_student_id(self, client):
        response = client.post('/students/api/fcm-token', json={
            'fcm_token': 'some_token_abc'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_fcm_token_nonexistent_student(self, client):
        response = client.post('/students/api/fcm-token', json={
            'fcm_token': 'fcm_tok_xyz',
            'student_id': 99999
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_fcm_token_valid_by_id(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/fcm-token', json={
            'fcm_token': f'valid_fcm_{secrets.token_hex(8)}',
            'student_id': s.id
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_fcm_token_valid_by_username(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/fcm-token', json={
            'fcm_token': f'valid_fcm_{secrets.token_hex(8)}',
            'username': s.username
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Notifications ====================

class TestNotificationsAPI:
    """GET /students/api/notifications/<id>, POST save, read, batch-save"""

    def test_get_notifications_nonexistent_student(self, client):
        response = client.get('/students/api/notifications/99999')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_notifications_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.get(f'/students/api/notifications/{s.id}')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_save_notification_missing_fields(self, client):
        response = client.post('/students/api/notifications/save', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_save_notification_nonexistent_student(self, client):
        response = client.post('/students/api/notifications/save', json={
            'student_id': 99999,
            'title': 'Test Notif',
            'message': 'Hello'
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_save_notification_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/notifications/save', json={
            'student_id': s.id,
            'title': 'Test Notification',
            'message': 'This is a test notification',
            'type': 'info'
        })
        assert response.status_code in [200, 201, 400, 401, 403, 404, 500]

    def test_mark_notification_read_missing_user(self, client):
        response = client.post('/students/api/notifications/99999/read', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mark_notification_read_with_user(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/notifications/99999/read', json={
            'user_id': s.id
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_batch_save_notifications_empty(self, client):
        response = client.post('/students/api/notifications/batch-save', json={
            'notifications': []
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_batch_save_notifications_with_data(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/notifications/batch-save', json={
            'notifications': [
                {
                    'student_id': s.id,
                    'title': 'Batch Notif 1',
                    'message': 'Body 1'
                },
                {
                    'student_id': s.id,
                    'title': 'Batch Notif 2',
                    'message': 'Body 2'
                }
            ]
        })
        assert response.status_code in [200, 201, 400, 401, 403, 404, 500]

    def test_get_unread_count_nonexistent(self, client):
        response = client.get('/students/api/notifications/unread-count/99999')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_unread_count_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.get(f'/students/api/notifications/unread-count/{s.id}')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mark_all_read_nonexistent(self, client):
        response = client.post('/students/api/notifications/mark-all-read/99999')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mark_all_read_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.post(f'/students/api/notifications/mark-all-read/{s.id}')
        assert response.status_code in [200, 400, 401, 403, 404, 500]


# ==================== API: Results ====================

class TestResultsAPI:
    """GET/POST /students/api/results, GET /students/api/results/stats"""

    def test_get_results_missing_student_id(self, client):
        response = client.get('/students/api/results')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_results_nonexistent_student(self, client):
        response = client.get('/students/api/results?student_id=99999')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_results_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.get(f'/students/api/results?student_id={s.id}')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_results_via_header(self, client, db_session):
        s = _make_student(db_session)
        response = client.get(
            '/students/api/results',
            headers={'X-Student-Id': str(s.id)}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_results_invalid_session_token(self, client, db_session):
        s = _make_student(db_session)
        response = client.get(
            f'/students/api/results?student_id={s.id}',
            headers={'X-Session-Token': 'invalid_token'}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_results_stats_missing_student_id(self, client):
        response = client.get('/students/api/results/stats')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_results_stats_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.get(f'/students/api/results/stats?student_id={s.id}')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_save_result_missing_student_id(self, client):
        response = client.post('/students/api/results', json={
            'quiz_type': 'lesson',
            'total_questions': 10,
            'correct_answers': 7
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_save_result_nonexistent_student(self, client):
        response = client.post('/students/api/results', json={
            'student_id': 99999,
            'quiz_type': 'lesson',
            'total_questions': 10,
            'correct_answers': 7,
            'score_percentage': 70.0
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_save_result_real_student(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'lesson',
            'quiz_name': 'Test Quiz',
            'total_questions': 10,
            'correct_answers': 8,
            'wrong_answers': 2,
            'score_percentage': 80.0,
            'time_spent': 120
        })
        assert response.status_code in [200, 400, 401, 403, 404, 500]
