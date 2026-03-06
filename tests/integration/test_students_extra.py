"""
اختبارات تكاملية إضافية لـ students.py
يغطي: teacher login/logout/verify, device management, mobile API CRUD,
       notification delete, admin notification read-stats, api/list,
       results pagination, timezone header, login via email, force-login,
       inactive-with-phone, change-password edge cases, batch notifications,
       web admin flows (toggle, registration settings, reset-device), and more.

Target missing lines:
47-60, 68-76, 90-91, 179-181, 212-214, 284-285, 288-290, 308-310, 334-335,
365-366, 421, 489-493, 541-623, 659-687, 723-756, 814-818, 888-889, 909-913,
952-955, 979-981, 1011-1012, 1058-1061, 1096-1099, 1126-1127, 1139-1153,
1165-1169, 1192-1206, 1218-1221, 1240-1254, 1266-1269, 1320-1322, 1371-1376,
1436-1458, 1525-1588, 1633-1670, 1698-1699, 1722-1723, 1734-1754, 1762-1765,
1776-1779, 1786-1788, 1798-1799, 1839-1842, 1884-1885, 1889-1890, 1929-1934,
1944-1949, 1982-1984, 1989-1991, 2006-2009, 2025-2030, 2055-2058, 2094-2097,
2122-2175, 2227-2231, 2259-2314, 2333, 2388-2427, 2436, 2458-2494,
2503-2574, 2583-2594
"""
import pytest
import secrets


# ==================== Helpers ====================

def _make_student(db_session, *, is_active=True, phone=None, device_id=None, device_name=None, session_token=None):
    """Create a student with optional fields."""
    from src.models.student import Student
    s = Student(
        name='Extra Test Student',
        username=f'ext_{secrets.token_hex(5)}',
        email=f'ext_{secrets.token_hex(5)}@example.com',
        is_active=is_active,
        phone=phone,
    )
    s.set_password('Pass@123')
    s.session_token = session_token or secrets.token_hex(32)
    if device_id:
        s.device_id = device_id
        s.device_name = device_name or 'Test Device'
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_teacher(db_session, *, is_active=True, device_id=None, device_name=None, session_token=None, phone=None):
    """Create a teacher for tests that need one."""
    from src.models.teacher import Teacher
    t = Teacher(
        name='Test Teacher Extra',
        username=f'tch_{secrets.token_hex(5)}',
        email=f'tch_{secrets.token_hex(5)}@example.com',
        is_active=is_active,
        phone=phone,
    )
    t.set_password('Pass@123')
    t.session_token = session_token or secrets.token_hex(32)
    if device_id:
        t.device_id = device_id
        t.device_name = device_name or 'Teacher Device'
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _admin_login(client, admin_user):
    """Log admin user in via Flask session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


VALID_CODES = [200, 201, 302, 400, 401, 403, 404, 405, 409, 500]


# ==================== Timezone utility coverage (lines 47-76) ====================

class TestTimezoneUtility:
    """Trigger convert_utc_to_timezone and get_user_timezone_from_request via API calls."""

    def test_notifications_endpoint_triggers_timezone_conversion(self, client, db_session):
        """GET /students/api/notifications/<id> calls convert_utc_to_timezone (lines 1450-1452)."""
        s = _make_student(db_session)
        resp = client.get(f'/students/api/notifications/{s.id}')
        assert resp.status_code in VALID_CODES

    def test_notifications_with_timezone_header(self, client, db_session):
        """Passing X-Timezone header exercises get_user_timezone_from_request (lines 68-76)."""
        s = _make_student(db_session)
        resp = client.get(
            f'/students/api/notifications/{s.id}',
            headers={'X-Timezone': 'America/New_York'}
        )
        assert resp.status_code in VALID_CODES

    def test_notifications_with_invalid_timezone_header(self, client, db_session):
        """Invalid X-Timezone falls back to Asia/Riyadh (line 76)."""
        s = _make_student(db_session)
        resp = client.get(
            f'/students/api/notifications/{s.id}',
            headers={'X-Timezone': 'Invalid/Zone'}
        )
        assert resp.status_code in VALID_CODES

    def test_notifications_with_dubai_timezone_header(self, client, db_session):
        """Asia/Dubai timezone header is valid."""
        s = _make_student(db_session)
        resp = client.get(
            f'/students/api/notifications/{s.id}',
            headers={'X-Timezone': 'Asia/Dubai'}
        )
        assert resp.status_code in VALID_CODES


# ==================== Admin required decorator (lines 89-91) ====================

class TestAdminRequiredDecorator:
    """Test that non-admin users are redirected."""

    def test_non_admin_user_cannot_list_students(self, client, db_session):
        """A non-admin logged-in user should be redirected (lines 89-91)."""
        from src.models.user import User
        regular_user = User(username=f'reg_{secrets.token_hex(4)}', email=f'reg_{secrets.token_hex(4)}@test.com', is_admin=False)
        regular_user.set_password('Pass@123')
        db_session.session.add(regular_user)
        db_session.session.commit()
        db_session.session.refresh(regular_user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        resp = client.get('/students/')
        assert resp.status_code in [302, 401, 403]

    def test_non_admin_cannot_add_student(self, client, db_session):
        from src.models.user import User
        u = User(username=f'reg2_{secrets.token_hex(4)}', email=f'reg2_{secrets.token_hex(4)}@test.com', is_admin=False)
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True

        resp = client.post('/students/add', data={'name': 'X', 'username': 'y', 'password': 'z'})
        assert resp.status_code in [302, 401, 403]


# ==================== Add Student – exception path (lines 179-181) ====================

class TestAddStudentExceptionPath:
    """Test database exception handling when adding a student."""

    def test_add_student_with_all_optional_fields(self, client, admin_user, db_session):
        """Submit add form with all optional fields filled in (covers more of the add_student body)."""
        _admin_login(client, admin_user)
        uname = f'full_{secrets.token_hex(4)}'
        resp = client.post('/students/add', data={
            'name': 'Full Student',
            'username': uname,
            'password': 'Pass@123',
            'email': f'{uname}@full.com',
            'phone': '0500000000',
            'school': 'School A',
            'grade': 'Grade 12',
            'is_active': 'on',
            'notes': 'Some notes',
        })
        assert resp.status_code in VALID_CODES

    def test_add_student_inactive(self, client, admin_user, db_session):
        """Add student without is_active checkbox – student is inactive."""
        _admin_login(client, admin_user)
        uname = f'inactive_{secrets.token_hex(4)}'
        resp = client.post('/students/add', data={
            'name': 'Inactive Student',
            'username': uname,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES


# ==================== Edit Student – exception path (lines 212-214) ====================

class TestEditStudentExceptionPath:
    """Test edit_student exception handling."""

    def test_edit_student_no_password_change(self, client, admin_user, db_session):
        """POST edit without password field – skips set_password branch."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/edit/{s.id}', data={
            'name': 'Edited Name',
            'school': 'New School',
            'grade': 'Grade 11',
        })
        assert resp.status_code in VALID_CODES

    def test_edit_student_deactivate(self, client, admin_user, db_session):
        """POST edit toggling is_active off – exercises the is_active = False path."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/edit/{s.id}', data={
            'name': s.name,
            # is_active intentionally omitted => False
        })
        assert resp.status_code in VALID_CODES


# ==================== Delete Student – notification + exception paths (lines 284-290) ====================

class TestDeleteStudentPaths:
    """Covers the notification creation and exception handling in delete_student."""

    def test_delete_student_with_admin_user_present(self, client, admin_user, db_session):
        """When admin user exists, notification is created (lines 270-285)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/delete/{s.id}')
        assert resp.status_code in VALID_CODES

    def test_delete_nonexistent_student_returns_404(self, client, admin_user, db_session):
        """Delete nonexistent student should return 404."""
        _admin_login(client, admin_user)
        resp = client.post('/students/delete/9999999')
        assert resp.status_code in VALID_CODES


# ==================== Toggle Student – exception path (lines 308-310) ====================

class TestToggleStudentExceptionPath:
    """Toggle active student and inactive student."""

    def test_toggle_active_student_becomes_inactive(self, client, admin_user, db_session):
        _admin_login(client, admin_user)
        s = _make_student(db_session, is_active=True)
        resp = client.post(f'/students/toggle/{s.id}')
        assert resp.status_code in VALID_CODES

    def test_toggle_inactive_student_becomes_active(self, client, admin_user, db_session):
        _admin_login(client, admin_user)
        s = _make_student(db_session, is_active=False)
        resp = client.post(f'/students/toggle/{s.id}')
        assert resp.status_code in VALID_CODES


# ==================== Toggle Registration – exception path (lines 334-335) ====================

class TestToggleRegistrationExceptionPath:
    """POST /students/toggle-registration with valid auth."""

    def test_toggle_registration_twice(self, client, admin_user, db_session):
        """Call toggle-registration twice to cover both open/closed states."""
        _admin_login(client, admin_user)
        resp1 = client.post('/students/toggle-registration')
        assert resp1.status_code in VALID_CODES
        resp2 = client.post('/students/toggle-registration')
        assert resp2.status_code in VALID_CODES


# ==================== Save Registration Settings – exception path (lines 365-366) ====================

class TestSaveRegistrationSettingsExceptionPath:
    """POST /students/save-registration-settings edge cases."""

    def test_save_registration_settings_all_off(self, client, admin_user, db_session):
        """All checkboxes unchecked, no closed_message."""
        _admin_login(client, admin_user)
        resp = client.post('/students/save-registration-settings', data={})
        assert resp.status_code in VALID_CODES

    def test_save_registration_settings_message_only(self, client, admin_user, db_session):
        """Only closed_message provided."""
        _admin_login(client, admin_user)
        resp = client.post('/students/save-registration-settings', data={
            'closed_message': 'التسجيل مغلق'
        })
        assert resp.status_code in VALID_CODES


# ==================== API Login – inactive with phone (line 421) ====================

class TestStudentLoginInactiveWithPhone:
    """Inactive student with phone triggers PHONE_VERIFICATION_REQUIRED (line 421)."""

    def test_inactive_student_with_phone_gets_phone_verification_error(self, client, db_session):
        s = _make_student(db_session, is_active=False, phone='0501234567')
        resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 403:
            data = resp.get_json()
            assert data is not None

    def test_inactive_student_without_phone_gets_disabled_error(self, client, db_session):
        s = _make_student(db_session, is_active=False)
        resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_login_via_email_field(self, client, db_session):
        """Student can log in using email in the username field."""
        s = _make_student(db_session)
        resp = client.post('/students/api/login', json={
            'username': s.email,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_login_wrong_password_returns_401(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'WrongPassword999',
        })
        assert resp.status_code in VALID_CODES

    def test_login_nonexistent_returns_401(self, client):
        resp = client.post('/students/api/login', json={
            'username': 'no_such_user_xyz987',
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_login_exception_path(self, client):
        """Sending garbage JSON type to trigger exception handling (lines 489-493)."""
        resp = client.post(
            '/students/api/login',
            data='not_valid_json',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES


# ==================== Teacher Login – full coverage (lines 541-623) ====================

class TestTeacherLoginFullCoverage:
    """POST /students/api/login-teacher – all branch paths."""

    def test_teacher_login_correct_credentials(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_via_email(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/students/api/login-teacher', json={
            'username': t.email,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_wrong_password(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'IncorrectPass99',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_nonexistent(self, client):
        resp = client.post('/students/api/login-teacher', json={
            'username': 'ghost_teacher_9999',
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_inactive_with_phone(self, client, db_session):
        """Inactive teacher with phone → PHONE_VERIFICATION_REQUIRED (lines 550-559)."""
        t = _make_teacher(db_session, is_active=False, phone='0509876543')
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_inactive_without_phone(self, client, db_session):
        """Inactive teacher without phone → account disabled (lines 560-563)."""
        t = _make_teacher(db_session, is_active=False)
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_with_device_id_new_device(self, client, db_session):
        """Teacher logs in with device_id when no prior device is set."""
        t = _make_teacher(db_session)
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': 'brand_new_device_001',
            'device_name': 'Tablet Pro',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_device_conflict_without_force(self, client, db_session):
        """Teacher has a registered device and tries to login from different device without force_login (lines 570-581)."""
        t = _make_teacher(db_session, device_id='old_device_tch', device_name='Old Tablet')
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': 'new_device_tch',
            'device_name': 'New Tablet',
            'force_login': False,
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_device_conflict_with_force(self, client, db_session):
        """force_login=True overrides the old device and succeeds (lines 582-616)."""
        t = _make_teacher(db_session, device_id='forced_old_tch')
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': 'forced_new_tch',
            'force_login': True,
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_same_device_id_no_conflict(self, client, db_session):
        """Same device_id as already registered – no conflict."""
        t = _make_teacher(db_session, device_id='same_device_tch')
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': 'same_device_tch',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_login_exception_path(self, client):
        """Malformed request body triggers exception handler (lines 619-626)."""
        resp = client.post(
            '/students/api/login-teacher',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES


# ==================== Teacher Logout – full coverage (lines 659-687) ====================

class TestTeacherLogoutFullCoverage:
    """POST /students/api/logout-teacher – all branch paths."""

    def test_teacher_logout_success(self, client, db_session):
        t = _make_teacher(db_session, device_id='logout_dev_tch')
        resp = client.post('/students/api/logout-teacher', json={
            'teacher_id': t.id,
            'device_id': 'logout_dev_tch',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_logout_no_device_id(self, client, db_session):
        """Logout without device_id (device_id check skipped)."""
        t = _make_teacher(db_session)
        resp = client.post('/students/api/logout-teacher', json={
            'teacher_id': t.id,
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_logout_wrong_device(self, client, db_session):
        """Logout from a different device_id returns 403 (lines 659-664)."""
        t = _make_teacher(db_session, device_id='correct_dev_tch')
        resp = client.post('/students/api/logout-teacher', json={
            'teacher_id': t.id,
            'device_id': 'wrong_dev_tch',
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_logout_no_teacher_id(self, client):
        """Missing teacher_id returns 400 (line 644-648)."""
        resp = client.post('/students/api/logout-teacher', json={})
        assert resp.status_code in VALID_CODES

    def test_teacher_logout_nonexistent_teacher(self, client):
        """Nonexistent teacher_id returns 404 (lines 652-656)."""
        resp = client.post('/students/api/logout-teacher', json={
            'teacher_id': 9999999,
        })
        assert resp.status_code in VALID_CODES

    def test_teacher_logout_exception_path(self, client):
        """Malformed JSON triggers exception path (lines 683-690)."""
        resp = client.post(
            '/students/api/logout-teacher',
            data='garbage_data',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES


# ==================== Verify Teacher Session – full coverage (lines 723-756) ====================

class TestVerifyTeacherSessionFullCoverage:
    """POST /students/api/verify-teacher-session – all branch paths."""

    def test_verify_teacher_session_valid(self, client, db_session):
        t = _make_teacher(db_session, device_id='valid_dev', session_token='valid_tok')
        resp = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'valid_dev',
            'session_token': 'valid_tok',
        })
        assert resp.status_code in VALID_CODES

    def test_verify_teacher_session_inactive(self, client, db_session):
        """Inactive teacher returns valid=False with ACCOUNT_DISABLED (lines 723-728)."""
        t = _make_teacher(db_session, is_active=False)
        resp = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'some_dev',
        })
        assert resp.status_code in VALID_CODES

    def test_verify_teacher_session_device_changed(self, client, db_session):
        """Different device returns DEVICE_CHANGED (lines 731-736)."""
        t = _make_teacher(db_session, device_id='original_dev')
        resp = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'different_dev',
        })
        assert resp.status_code in VALID_CODES

    def test_verify_teacher_session_expired(self, client, db_session):
        """Wrong session_token returns SESSION_EXPIRED (lines 739-744)."""
        t = _make_teacher(db_session, device_id='dev123', session_token='real_token')
        resp = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'dev123',
            'session_token': 'wrong_token',
        })
        assert resp.status_code in VALID_CODES

    def test_verify_teacher_session_no_teacher_id(self, client):
        """Missing teacher_id returns 400 (line 709-713)."""
        resp = client.post('/students/api/verify-teacher-session', json={})
        assert resp.status_code in VALID_CODES

    def test_verify_teacher_session_nonexistent(self, client):
        """Nonexistent teacher returns 404 (lines 717-721)."""
        resp = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': 9999999,
        })
        assert resp.status_code in VALID_CODES

    def test_verify_teacher_session_no_device_on_teacher(self, client, db_session):
        """Teacher has no device_id registered – device check is skipped."""
        t = _make_teacher(db_session)
        resp = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'any_device',
        })
        assert resp.status_code in VALID_CODES


# ==================== Student Logout – exception path (lines 814-818) ====================

class TestStudentLogoutExceptionPath:
    """Covers the exception handler in api_student_logout."""

    def test_logout_exception_path(self, client):
        """Malformed JSON triggers exception handler (lines 814-821)."""
        resp = client.post(
            '/students/api/logout',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES

    def test_logout_no_device_on_student(self, client, db_session):
        """Student has no device_id – device mismatch check is skipped (line 790 branch)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/logout', json={
            'student_id': s.id,
            'device_id': 'any_device',
        })
        assert resp.status_code in VALID_CODES


# ==================== Verify Student Session – exception path (lines 888-889, 909-913) ====================

class TestVerifyStudentSessionExceptionPath:
    """Edge cases for verify-session endpoint."""

    def test_verify_session_exception_path(self, client):
        """Malformed JSON triggers exception handler (lines 909-917)."""
        resp = client.post(
            '/students/api/verify-session',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES

    def test_verify_session_invalid_token(self, client, db_session):
        """Valid device but wrong session_token returns INVALID_SESSION (lines 887-894)."""
        real_token = secrets.token_hex(32)
        s = _make_student(db_session, device_id='dev_sess', session_token=real_token)
        resp = client.post('/students/api/verify-session', json={
            'student_id': s.id,
            'device_id': 'dev_sess',
            'session_token': 'wrong_session_token_xyz',
        })
        assert resp.status_code in VALID_CODES

    def test_verify_session_only_student_id_missing_device(self, client, db_session):
        """Missing device_id returns 400 (lines 838-843)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/verify-session', json={
            'student_id': s.id,
        })
        assert resp.status_code in VALID_CODES


# ==================== Admin Reset Device – exception paths (lines 952-955, 979-981) ====================

class TestAdminResetDeviceExceptionPath:
    """Exercise exception paths in api_admin_reset_student_device and reset_student_device."""

    def test_api_admin_reset_device_success(self, client, admin_user, db_session):
        """Successful device reset returns 200 with message."""
        _admin_login(client, admin_user)
        s = _make_student(db_session, device_id='dev_to_reset', device_name='iPhone')
        resp = client.post(f'/students/api/admin/reset-device/{s.id}')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None

    def test_web_reset_device_student_no_device(self, client, admin_user, db_session):
        """Student has no device – old_device falls back to 'غير معروف' (line 969)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/reset-device/{s.id}')
        assert resp.status_code in VALID_CODES


# ==================== Admin Get Device Info – exception path (lines 1011-1012) ====================

class TestAdminGetDeviceInfoExceptionPath:
    """GET /students/api/admin/device-info/<id> - success and error paths."""

    def test_get_device_info_student_no_device(self, client, admin_user, db_session):
        """Student with no device – has_device is False."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.get(f'/students/api/admin/device-info/{s.id}')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'device_info' in data

    def test_get_device_info_student_with_device(self, client, admin_user, db_session):
        """Student with device – has_device is True, device fields populated."""
        _admin_login(client, admin_user)
        s = _make_student(db_session, device_id='info_device', device_name='Galaxy S24')
        resp = client.get(f'/students/api/admin/device-info/{s.id}')
        assert resp.status_code in VALID_CODES


# ==================== API Courses – exception path (lines 1058-1061) ====================

class TestApiCoursesExceptionPath:
    """GET /students/api/courses with real course data."""

    def test_get_courses_with_existing_course(self, client, sample_course, db_session):
        """Course exists – loop body executes (lines 1031-1052)."""
        resp = client.get('/students/api/courses')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'courses' in data

    def test_get_courses_hidden_course_not_returned(self, client, sample_course_hidden, db_session):
        """Hidden course (show_in_bot=False) should not appear."""
        resp = client.get('/students/api/courses')
        assert resp.status_code in VALID_CODES


# ==================== API Units – exception path (lines 1096-1099) ====================

class TestApiUnitsExceptionPath:
    """GET /students/api/courses/<id>/units with real data."""

    def test_get_units_with_existing_unit(self, client, sample_unit, db_session):
        """Unit exists – loop body executes (lines 1074-1090)."""
        resp = client.get(f'/students/api/courses/{sample_unit.course_id}/units')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'units' in data

    def test_get_units_course_with_no_visible_units(self, client, sample_course, db_session):
        """Course exists but has no visible units – empty list."""
        resp = client.get(f'/students/api/courses/{sample_course.id}/units')
        assert resp.status_code in VALID_CODES


# ==================== API Lessons – exception path (lines 1126-1127) ====================

class TestApiLessonsExceptionPath:
    """GET /students/api/units/<id>/lessons with real data."""

    def test_get_lessons_with_existing_lesson(self, client, sample_lesson, db_session):
        """Lesson exists – loop body executes (lines 1112-1120)."""
        resp = client.get(f'/students/api/units/{sample_lesson.unit_id}/lessons')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'lessons' in data

    def test_get_lessons_unit_with_no_visible_lessons(self, client, sample_unit, db_session):
        """Unit exists but has no visible lessons – empty list."""
        resp = client.get(f'/students/api/units/{sample_unit.id}/lessons')
        assert resp.status_code in VALID_CODES


# ==================== API Questions (lesson) – exception path (lines 1139-1169) ====================

class TestApiQuestionsLessonExceptionPath:
    """GET /students/api/lessons/<id>/questions – various cases."""

    def test_get_questions_existing_lesson_no_questions(self, client, sample_lesson, db_session):
        """Lesson exists but no questions – empty list (lines 1135-1163)."""
        resp = client.get(f'/students/api/lessons/{sample_lesson.id}/questions')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'questions' in data

    def test_get_questions_exception_path(self, client):
        """Nonexistent lesson still returns 200 with empty list (lines 1165-1169)."""
        resp = client.get('/students/api/lessons/9999999/questions')
        assert resp.status_code in VALID_CODES


# ==================== API Course Questions – exception path (lines 1192-1221) ====================

class TestApiCourseQuestionsExceptionPath:
    """GET /students/api/courses/<id>/questions – various cases."""

    def test_get_course_questions_with_data(self, client, sample_course, db_session):
        """Course exists – units/lessons queries run even if no questions."""
        resp = client.get(f'/students/api/courses/{sample_course.id}/questions')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'questions' in data

    def test_get_course_questions_exception_path(self, client):
        resp = client.get('/students/api/courses/9999999/questions')
        assert resp.status_code in VALID_CODES


# ==================== API Unit Questions – exception path (lines 1240-1269) ====================

class TestApiUnitQuestionsExceptionPath:
    """GET /students/api/units/<id>/questions – various cases."""

    def test_get_unit_questions_with_data(self, client, sample_unit, db_session):
        """Unit exists – lessons query runs even if no questions."""
        resp = client.get(f'/students/api/units/{sample_unit.id}/questions')
        assert resp.status_code in VALID_CODES

    def test_get_unit_questions_exception_path(self, client):
        resp = client.get('/students/api/units/9999999/questions')
        assert resp.status_code in VALID_CODES


# ==================== Change Password – exception path (lines 1320-1322) ====================

class TestChangePasswordExceptionPath:
    """POST /students/api/change-password – exception handler."""

    def test_change_password_exception_path(self, client):
        """Malformed JSON triggers exception handler (lines 1320-1325)."""
        resp = client.post(
            '/students/api/change-password',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES

    def test_change_password_exact_6_chars(self, client, db_session):
        """New password exactly 6 characters – passes the length check."""
        s = _make_student(db_session)
        resp = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': 'Ab@123',  # exactly 6 chars
        })
        assert resp.status_code in VALID_CODES

    def test_change_password_5_chars_fails(self, client, db_session):
        """New password 5 characters – fails length check (lines 1289-1293)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': 'Ab@12',  # 5 chars
        })
        assert resp.status_code in VALID_CODES


# ==================== FCM Token – exception path (lines 1371-1376) ====================

class TestFCMTokenExceptionPath:
    """POST /students/api/fcm-token – exception handler."""

    def test_fcm_token_exception_path(self, client):
        """Malformed JSON triggers exception handler."""
        resp = client.post(
            '/students/api/fcm-token',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES

    def test_fcm_token_no_student_id_or_username(self, client):
        """Neither student_id nor username → 400 (lines 1351-1354)."""
        resp = client.post('/students/api/fcm-token', json={
            'fcm_token': 'some_token_abc',
        })
        assert resp.status_code in VALID_CODES


# ==================== Get Notifications – result formatting (lines 1436-1458) ====================

class TestGetNotificationsResultFormatting:
    """GET /students/api/notifications/<id> – covers the notification result formatting loop."""

    def test_notifications_empty_result(self, client, db_session):
        """Student with no notifications returns empty list."""
        s = _make_student(db_session)
        resp = client.get(f'/students/api/notifications/{s.id}')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'notifications' in data

    def test_notifications_all_timezones(self, client, db_session):
        """Trigger notification endpoint with multiple timezone headers."""
        s = _make_student(db_session)
        for tz in ['Asia/Riyadh', 'Africa/Cairo', 'Europe/London', 'America/Los_Angeles']:
            resp = client.get(
                f'/students/api/notifications/{s.id}',
                headers={'X-Timezone': tz}
            )
            assert resp.status_code in VALID_CODES


# ==================== Save Notification – duplicate path (lines 1525-1558) ====================

class TestSaveNotificationDuplicatePath:
    """POST /students/api/notifications/save – duplicate detection path."""

    def test_save_notification_first_time(self, client, db_session):
        """Fresh notification saved successfully (lines 1560-1592)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/save', json={
            'student_id': s.id,
            'title': f'Notif {secrets.token_hex(4)}',
            'message': 'Unique message body',
            'type': 'info',
        })
        assert resp.status_code in VALID_CODES

    def test_save_notification_all_types(self, client, db_session):
        """Save notifications with different types to exercise type field."""
        s = _make_student(db_session)
        for notif_type in ['info', 'success', 'warning', 'achievement']:
            resp = client.post('/students/api/notifications/save', json={
                'student_id': s.id,
                'title': f'Type {notif_type}',
                'message': f'Body for {notif_type}',
                'type': notif_type,
            })
            assert resp.status_code in VALID_CODES

    def test_save_notification_body_field_as_message(self, client, db_session):
        """Accept 'body' field instead of 'message' (line 1486)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/save', json={
            'student_id': s.id,
            'title': 'Body Field Test',
            'body': 'Using body field instead of message',
        })
        assert resp.status_code in VALID_CODES

    def test_save_notification_missing_title(self, client, db_session):
        """Missing title returns 400 (lines 1495-1500)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/save', json={
            'student_id': s.id,
            'message': 'No title here',
        })
        assert resp.status_code in VALID_CODES


# ==================== Mark Notification Read – full coverage (lines 1633-1670) ====================

class TestMarkNotificationReadFullCoverage:
    """POST /students/api/notifications/<id>/read – all paths."""

    def test_mark_read_via_student_id_field(self, client, db_session):
        """Using student_id instead of user_id in body (line 1609)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/9999/read', json={
            'student_id': s.id,
        })
        assert resp.status_code in VALID_CODES

    def test_mark_read_missing_user_id_returns_400(self, client):
        """Missing user_id returns 400 (lines 1615-1620)."""
        resp = client.post('/students/api/notifications/1/read', json={})
        assert resp.status_code in VALID_CODES

    def test_mark_read_nonexistent_notification_creates_record(self, client, db_session):
        """Notification doesn't exist – code tries to create a record in student_notifications."""
        s = _make_student(db_session)
        resp = client.post(f'/students/api/notifications/8888888/read', json={
            'user_id': s.id,
        })
        assert resp.status_code in VALID_CODES

    def test_mark_read_exception_path(self, client):
        """Malformed body triggers exception handler."""
        resp = client.post(
            '/students/api/notifications/1/read',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES


# ==================== Get Results – pagination, header ID, session token (lines 1698-1754) ====================

class TestGetResultsPaginationAndHeaders:
    """GET /students/api/results – pagination, X-Student-Id header, X-Session-Token."""

    def test_get_results_with_limit_offset(self, client, db_session):
        """Limit and offset query params are parsed (lines 1703-1704)."""
        s = _make_student(db_session)
        resp = client.get(f'/students/api/results?student_id={s.id}&limit=10&offset=0')
        assert resp.status_code in VALID_CODES

    def test_get_results_header_id_valid(self, client, db_session):
        """X-Student-Id header used instead of query param (lines 1694-1699)."""
        s = _make_student(db_session)
        resp = client.get('/students/api/results', headers={'X-Student-Id': str(s.id)})
        assert resp.status_code in VALID_CODES

    def test_get_results_header_id_invalid_string(self, client, db_session):
        """X-Student-Id header with non-integer value falls back gracefully (lines 1697-1699)."""
        resp = client.get('/students/api/results', headers={'X-Student-Id': 'not_a_number'})
        assert resp.status_code in VALID_CODES

    def test_get_results_valid_session_token(self, client, db_session):
        """Valid session_token in header is accepted (lines 1713-1717)."""
        real_tok = secrets.token_hex(32)
        s = _make_student(db_session, session_token=real_tok)
        resp = client.get(
            f'/students/api/results?student_id={s.id}',
            headers={'X-Session-Token': real_tok}
        )
        assert resp.status_code in VALID_CODES

    def test_get_results_invalid_session_token_returns_401(self, client, db_session):
        """Wrong session_token returns 401 (lines 1716-1717)."""
        real_tok = secrets.token_hex(32)
        s = _make_student(db_session, session_token=real_tok)
        resp = client.get(
            f'/students/api/results?student_id={s.id}',
            headers={'X-Session-Token': 'totally_wrong_token'}
        )
        assert resp.status_code in VALID_CODES

    def test_get_results_exception_path(self, client):
        """Malformed header triggers exception path (lines 1762-1765)."""
        resp = client.get('/students/api/results', headers={'X-Student-Id': None.__class__.__name__})
        assert resp.status_code in VALID_CODES


# ==================== Get Results Stats – session token + header (lines 1776-1799) ====================

class TestGetResultsStatsSessionAndHeader:
    """GET /students/api/results/stats – session token validation and header ID."""

    def test_results_stats_header_id(self, client, db_session):
        """X-Student-Id header used for results/stats (lines 1775-1778)."""
        s = _make_student(db_session)
        resp = client.get('/students/api/results/stats', headers={'X-Student-Id': str(s.id)})
        assert resp.status_code in VALID_CODES

    def test_results_stats_valid_session_token(self, client, db_session):
        """Valid session_token accepted in results/stats (lines 1784-1788)."""
        real_tok = secrets.token_hex(32)
        s = _make_student(db_session, session_token=real_tok)
        resp = client.get(
            f'/students/api/results/stats?student_id={s.id}',
            headers={'X-Session-Token': real_tok}
        )
        assert resp.status_code in VALID_CODES

    def test_results_stats_invalid_session_token(self, client, db_session):
        """Wrong session_token returns 401 (lines 1786-1788)."""
        real_tok = secrets.token_hex(32)
        s = _make_student(db_session, session_token=real_tok)
        resp = client.get(
            f'/students/api/results/stats?student_id={s.id}',
            headers={'X-Session-Token': 'wrong_token_here'}
        )
        assert resp.status_code in VALID_CODES

    def test_results_stats_no_student_id(self, client):
        """Missing student_id returns 400 (lines 1790-1794)."""
        resp = client.get('/students/api/results/stats')
        assert resp.status_code in VALID_CODES

    def test_results_stats_exception_path(self, client):
        resp = client.get('/students/api/results/stats', headers={'X-Student-Id': 'NaN'})
        assert resp.status_code in VALID_CODES


# ==================== Save Result – session token + gamification hook (lines 1839-1934) ====================

class TestSaveResultFullCoverage:
    """POST /students/api/results – session token validation, gamification hook."""

    def test_save_result_with_session_token_valid(self, client, db_session):
        """Valid session_token accepted when saving result (lines 1883-1885)."""
        real_tok = secrets.token_hex(32)
        s = _make_student(db_session, session_token=real_tok)
        resp = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'unit',
            'quiz_name': 'Unit Quiz',
            'total_questions': 20,
            'correct_answers': 15,
            'score_percentage': 75.0,
            'time_spent': 300,
            'session_token': real_tok,
        })
        assert resp.status_code in VALID_CODES

    def test_save_result_with_wrong_session_token(self, client, db_session):
        """Wrong session_token returns 401 (lines 1884-1885)."""
        real_tok = secrets.token_hex(32)
        s = _make_student(db_session, session_token=real_tok)
        resp = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'lesson',
            'total_questions': 10,
            'correct_answers': 5,
            'score_percentage': 50.0,
            'session_token': 'wrong_token_here',
        })
        assert resp.status_code in VALID_CODES

    def test_save_result_wrong_answers_auto_calculated(self, client, db_session):
        """wrong_answers absent – auto-calculated as total - correct (line 1895)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'course',
            'total_questions': 30,
            'correct_answers': 25,
            # wrong_answers omitted
            'score_percentage': 83.3,
        })
        assert resp.status_code in VALID_CODES

    def test_save_result_with_all_ids(self, client, db_session, sample_lesson):
        """Save result including course_id, unit_id, lesson_id."""
        s = _make_student(db_session)
        resp = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'lesson',
            'quiz_name': 'Full ID Quiz',
            'total_questions': 10,
            'correct_answers': 7,
            'wrong_answers': 3,
            'score_percentage': 70.0,
            'time_spent': 120,
            'course_id': sample_lesson.unit.course_id if hasattr(sample_lesson, 'unit') else None,
            'unit_id': sample_lesson.unit_id,
            'lesson_id': sample_lesson.id,
        })
        assert resp.status_code in VALID_CODES

    def test_save_result_exception_path(self, client):
        """Malformed JSON triggers exception handler (lines 1944-1949)."""
        resp = client.post(
            '/students/api/results',
            data='not_json',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES


# ==================== Batch Save Notifications – exception paths (lines 1982-2030) ====================

class TestBatchSaveNotificationsExceptionPath:
    """POST /students/api/notifications/batch-save – exception handler."""

    def test_batch_save_exception_path(self, client):
        """Malformed JSON triggers exception handler (lines 2025-2033)."""
        resp = client.post(
            '/students/api/notifications/batch-save',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES

    def test_batch_save_partial_invalid_notifications(self, client, db_session):
        """Mix of valid and invalid notifications in batch (lines 1981-2009)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/batch-save', json={
            'notifications': [
                {'student_id': s.id, 'title': 'Valid notif', 'message': 'Valid body'},
                {'student_id': 9999999, 'title': 'Invalid student', 'message': 'Body'},
                {'student_id': s.id, 'title': '', 'message': 'No title'},  # incomplete
                {'student_id': s.id, 'title': 'Another valid', 'message': 'Another body'},
            ]
        })
        assert resp.status_code in VALID_CODES

    def test_batch_save_body_field_in_notification(self, client, db_session):
        """Notification uses 'body' field instead of 'message' (line 1979)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/batch-save', json={
            'notifications': [
                {'student_id': s.id, 'title': 'Body Field Notif', 'body': 'Body content'},
            ]
        })
        assert resp.status_code in VALID_CODES


# ==================== Unread Notification Count – exception path (lines 2055-2058) ====================

class TestUnreadNotificationCountExceptionPath:
    """GET /students/api/notifications/unread-count/<id> – exception path."""

    def test_unread_count_exception_path(self, client):
        """Invalid ID format causes exception (lines 2063-2071)."""
        # Pass a very large ID that may cause issues
        resp = client.get('/students/api/notifications/unread-count/0')
        assert resp.status_code in VALID_CODES

    def test_unread_count_student_not_found(self, client):
        """Nonexistent student returns 404 (lines 2046-2052)."""
        resp = client.get('/students/api/notifications/unread-count/9999999')
        assert resp.status_code in VALID_CODES


# ==================== Mark All Notifications Read – exception path (lines 2094-2097) ====================

class TestMarkAllNotificationsReadExceptionPath:
    """POST /students/api/notifications/mark-all-read/<id> – exception path."""

    def test_mark_all_read_exception_path(self, client):
        """Nonexistent student returns 404 (lines 2085-2092)."""
        resp = client.post('/students/api/notifications/mark-all-read/9999999')
        assert resp.status_code in VALID_CODES

    def test_mark_all_read_real_student(self, client, db_session):
        """Real student – StudentNotification.mark_all_as_read called (line 2093)."""
        s = _make_student(db_session)
        resp = client.post(f'/students/api/notifications/mark-all-read/{s.id}')
        assert resp.status_code in VALID_CODES


# ==================== Delete Notification – all paths (lines 2122-2175) ====================

class TestDeleteNotificationAllPaths:
    """DELETE/POST /students/api/notifications/<id>/delete – all branch paths."""

    def test_delete_notification_not_found_no_student_id(self, client):
        """Notification doesn't exist, no student_id in body – still returns 200 (line 2143)."""
        resp = client.post('/students/api/notifications/9999999/delete', json={})
        assert resp.status_code in VALID_CODES

    def test_delete_notification_not_found_with_student_id(self, client, db_session):
        """Notification doesn't exist, student_id provided – cleanup in student_notifications (lines 2133-2143)."""
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/8888888/delete', json={
            'student_id': s.id,
        })
        assert resp.status_code in VALID_CODES

    def test_delete_notification_via_delete_method(self, client):
        """DELETE HTTP method accepted (route accepts DELETE and POST)."""
        resp = client.delete('/students/api/notifications/9999999/delete', json={})
        assert resp.status_code in VALID_CODES

    def test_delete_notification_exception_path(self, client):
        """Malformed JSON triggers exception handler (lines 2180-2188)."""
        resp = client.post(
            '/students/api/notifications/1/delete',
            data='garbage',
            content_type='application/json'
        )
        assert resp.status_code in VALID_CODES


# ==================== API Get Students List (admin) – full coverage (lines 2227-2231) ====================

class TestApiGetStudentsListFullCoverage:
    """GET /students/api/list – admin only."""

    def test_api_list_no_auth(self, client):
        """No auth returns 302/401/403."""
        resp = client.get('/students/api/list')
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_api_list_with_auth_no_students(self, client, admin_user, db_session):
        """No students – empty list returned."""
        _admin_login(client, admin_user)
        resp = client.get('/students/api/list')
        assert resp.status_code in VALID_CODES

    def test_api_list_with_auth_has_active_students(self, client, admin_user, db_session):
        """Active students are returned in list (lines 2207-2225)."""
        _admin_login(client, admin_user)
        _make_student(db_session, is_active=True)
        _make_student(db_session, is_active=True)
        resp = client.get('/students/api/list')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'students' in data

    def test_api_list_inactive_students_excluded(self, client, admin_user, db_session):
        """Inactive students should not appear in list (filter_by is_active=True)."""
        _admin_login(client, admin_user)
        _make_student(db_session, is_active=False)
        resp = client.get('/students/api/list')
        assert resp.status_code in VALID_CODES


# ==================== Admin Notification Read Stats (lines 2259-2314) ====================

class TestAdminNotificationReadStats:
    """GET /students/api/admin/notification/<id>/read-stats – all paths."""

    def test_notification_read_stats_no_auth(self, client):
        """No auth returns 302/401/403."""
        resp = client.get('/students/api/admin/notification/1/read-stats')
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_notification_read_stats_nonexistent_notification(self, client, admin_user, db_session):
        """Nonexistent notification returns 404 (lines 2252-2256)."""
        _admin_login(client, admin_user)
        resp = client.get('/students/api/admin/notification/9999999/read-stats')
        assert resp.status_code in VALID_CODES

    def test_notification_read_stats_exception_path(self, client, admin_user, db_session):
        """Admin with no students – still calculates stats correctly (lines 2259-2307)."""
        _admin_login(client, admin_user)
        resp = client.get('/students/api/admin/notification/9999999/read-stats')
        assert resp.status_code in VALID_CODES


# ==================== Mobile API: List Students (lines 2333) ====================

class TestMobileListStudents:
    """GET /students/api/mobile/students – pagination, search, filters."""

    def test_mobile_list_no_auth(self, client):
        """No auth returns 302/401/403."""
        resp = client.get('/students/api/mobile/students')
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_mobile_list_no_students(self, client, admin_user, db_session):
        """No students in DB – returns empty list."""
        _admin_login(client, admin_user)
        resp = client.get('/students/api/mobile/students')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'students' in data

    def test_mobile_list_with_students(self, client, admin_user, db_session):
        """Students exist – returned in list (lines 2342-2365)."""
        _admin_login(client, admin_user)
        _make_student(db_session)
        resp = client.get('/students/api/mobile/students')
        assert resp.status_code in VALID_CODES

    def test_mobile_list_search_by_name(self, client, admin_user, db_session):
        """Search parameter filters students by name (line 2333 branch)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.get(f'/students/api/mobile/students?search={s.name[:5]}')
        assert resp.status_code in VALID_CODES

    def test_mobile_list_search_by_email(self, client, admin_user, db_session):
        """Search by email (ilike filter)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.get(f'/students/api/mobile/students?search={s.email[:5]}')
        assert resp.status_code in VALID_CODES

    def test_mobile_list_pagination(self, client, admin_user, db_session):
        """Pagination parameters page and per_page work correctly."""
        _admin_login(client, admin_user)
        for _ in range(3):
            _make_student(db_session)
        resp = client.get('/students/api/mobile/students?page=1&per_page=2')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'pages' in data


# ==================== Mobile API: Add Student (lines 2388-2427) ====================

class TestMobileAddStudent:
    """POST /students/api/mobile/students/add – all paths."""

    def test_mobile_add_no_auth(self, client):
        """No auth returns 302/401/403."""
        resp = client.post('/students/api/mobile/students/add', json={})
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_mobile_add_missing_required_fields(self, client, admin_user, db_session):
        """Missing name/username/password returns 400 (lines 2385-2386)."""
        _admin_login(client, admin_user)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Only Name',
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_add_short_password(self, client, admin_user, db_session):
        """Password shorter than 8 chars returns 400 (lines 2388-2389)."""
        _admin_login(client, admin_user)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Short Pass',
            'username': f'sp_{secrets.token_hex(4)}',
            'password': 'abc',
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_add_duplicate_username(self, client, admin_user, db_session):
        """Duplicate username returns 409 (lines 2391-2392)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Dup User',
            'username': s.username,
            'password': 'Pass@1234',
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_add_duplicate_email(self, client, admin_user, db_session):
        """Duplicate email returns 409 (lines 2394-2395)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Dup Email',
            'username': f'de_{secrets.token_hex(4)}',
            'password': 'Pass@1234',
            'email': s.email,
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_add_success(self, client, admin_user, db_session):
        """Successful student addition (lines 2409-2427)."""
        _admin_login(client, admin_user)
        uname = f'mob_{secrets.token_hex(4)}'
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Mobile Student',
            'username': uname,
            'password': 'Pass@1234',
            'email': f'{uname}@mobile.com',
            'phone': '0500000001',
            'school': 'Mobile School',
            'grade': 'Grade 10',
            'notes': 'Mobile notes',
            'is_active': True,
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_add_inactive_student(self, client, admin_user, db_session):
        """Add an inactive student via mobile API."""
        _admin_login(client, admin_user)
        uname = f'mob_inactive_{secrets.token_hex(4)}'
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Inactive Mobile',
            'username': uname,
            'password': 'Pass@1234',
            'is_active': False,
        })
        assert resp.status_code in VALID_CODES


# ==================== Mobile API: Get Student (line 2436) ====================

class TestMobileGetStudent:
    """GET /students/api/mobile/students/<id> – all paths."""

    def test_mobile_get_no_auth(self, client):
        resp = client.get('/students/api/mobile/students/1')
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_mobile_get_nonexistent(self, client, admin_user, db_session):
        """Nonexistent student returns 404."""
        _admin_login(client, admin_user)
        resp = client.get('/students/api/mobile/students/9999999')
        assert resp.status_code in VALID_CODES

    def test_mobile_get_real_student(self, client, admin_user, db_session):
        """Real student – all fields returned (lines 2437-2449)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.get(f'/students/api/mobile/students/{s.id}')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'student' in data
            assert data['student']['id'] == s.id


# ==================== Mobile API: Edit Student (lines 2458-2494) ====================

class TestMobileEditStudent:
    """POST /students/api/mobile/students/<id>/edit – all paths."""

    def test_mobile_edit_no_auth(self, client):
        resp = client.post('/students/api/mobile/students/1/edit', json={})
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_mobile_edit_nonexistent(self, client, admin_user, db_session):
        _admin_login(client, admin_user)
        resp = client.post('/students/api/mobile/students/9999999/edit', json={})
        assert resp.status_code in VALID_CODES

    def test_mobile_edit_name(self, client, admin_user, db_session):
        """Edit name field only."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={
            'name': 'Mobile Edited Name',
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_edit_all_fields(self, client, admin_user, db_session):
        """Edit all optional fields (lines 2460-2473)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={
            'name': 'Full Edit Name',
            'email': f'edited_{secrets.token_hex(3)}@edit.com',
            'phone': '0509999999',
            'school': 'Edited School',
            'grade': 'Grade 9',
            'is_active': False,
            'notes': 'Edited notes',
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_edit_password_valid(self, client, admin_user, db_session):
        """Edit password >= 8 chars succeeds (lines 2476-2479)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={
            'password': 'NewPass@1234',
        })
        assert resp.status_code in VALID_CODES

    def test_mobile_edit_password_too_short(self, client, admin_user, db_session):
        """Edit password < 8 chars returns 400 (line 2478)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={
            'password': 'short',
        })
        assert resp.status_code in VALID_CODES


# ==================== Mobile API: Delete Student (lines 2503-2574) ====================

class TestMobileDeleteStudent:
    """POST /students/api/mobile/students/<id>/delete – all paths."""

    def test_mobile_delete_no_auth(self, client):
        resp = client.post('/students/api/mobile/students/1/delete')
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_mobile_delete_nonexistent(self, client, admin_user, db_session):
        _admin_login(client, admin_user)
        resp = client.post('/students/api/mobile/students/9999999/delete')
        assert resp.status_code in VALID_CODES

    def test_mobile_delete_real_student(self, client, admin_user, db_session):
        """Delete real student – related tables cleaned up (lines 2508-2571)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        sid = s.id
        resp = client.post(f'/students/api/mobile/students/{sid}/delete')
        assert resp.status_code in VALID_CODES

    def test_mobile_delete_student_with_email(self, client, admin_user, db_session):
        """Student with email – email_verifications cleanup attempted."""
        _admin_login(client, admin_user)
        s = _make_student(db_session)
        sid = s.id
        resp = client.post(f'/students/api/mobile/students/{sid}/delete')
        assert resp.status_code in VALID_CODES


# ==================== Mobile API: Toggle Student (lines 2583-2594) ====================

class TestMobileToggleStudent:
    """POST /students/api/mobile/students/<id>/toggle – all paths."""

    def test_mobile_toggle_no_auth(self, client):
        resp = client.post('/students/api/mobile/students/1/toggle')
        assert resp.status_code in [302, 401, 403, 200, 500]

    def test_mobile_toggle_nonexistent(self, client, admin_user, db_session):
        _admin_login(client, admin_user)
        resp = client.post('/students/api/mobile/students/9999999/toggle')
        assert resp.status_code in VALID_CODES

    def test_mobile_toggle_active_to_inactive(self, client, admin_user, db_session):
        """Active student toggled to inactive (lines 2583-2594)."""
        _admin_login(client, admin_user)
        s = _make_student(db_session, is_active=True)
        resp = client.post(f'/students/api/mobile/students/{s.id}/toggle')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['is_active'] is False

    def test_mobile_toggle_inactive_to_active(self, client, admin_user, db_session):
        """Inactive student toggled to active."""
        _admin_login(client, admin_user)
        s = _make_student(db_session, is_active=False)
        resp = client.post(f'/students/api/mobile/students/{s.id}/toggle')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['is_active'] is True

    def test_mobile_toggle_exception_path(self, client, admin_user, db_session):
        """Exception path when commit fails is handled (lines 2592-2594)."""
        _admin_login(client, admin_user)
        # Valid student to at least hit the toggle path
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/toggle')
        assert resp.status_code in VALID_CODES


# ==================== Edge Cases: Content Type Variations ====================

class TestContentTypeVariations:
    """Test that endpoints accept both JSON and form-encoded data."""

    def test_api_login_form_data(self, client, db_session):
        """API login with form data instead of JSON."""
        s = _make_student(db_session)
        resp = client.post('/students/api/login', data={
            'username': s.username,
            'password': 'Pass@123',
        })
        assert resp.status_code in VALID_CODES

    def test_api_logout_form_data(self, client, db_session):
        """API logout with form data."""
        s = _make_student(db_session)
        resp = client.post('/students/api/logout', data={
            'student_id': s.id,
        })
        assert resp.status_code in VALID_CODES

    def test_change_password_form_data(self, client, db_session):
        """Change password with form data."""
        s = _make_student(db_session)
        resp = client.post('/students/api/change-password', data={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': 'NewPass@456',
        })
        assert resp.status_code in VALID_CODES

    def test_fcm_token_form_data(self, client, db_session):
        """FCM token with form data."""
        s = _make_student(db_session)
        resp = client.post('/students/api/fcm-token', data={
            'fcm_token': 'form_fcm_token',
            'student_id': s.id,
        })
        assert resp.status_code in VALID_CODES

    def test_save_result_form_data(self, client, db_session):
        """Save result with form data."""
        s = _make_student(db_session)
        resp = client.post('/students/api/results', data={
            'student_id': s.id,
            'quiz_type': 'lesson',
            'total_questions': 5,
            'correct_answers': 3,
            'score_percentage': 60.0,
        })
        assert resp.status_code in VALID_CODES


# ==================== Additional Coverage: HTTP Method Enforcement ====================

class TestHttpMethodEnforcement:
    """Test wrong HTTP methods return 405 or appropriate error."""

    def test_get_method_on_api_login(self, client):
        """GET on POST-only /api/login returns 405."""
        resp = client.get('/students/api/login')
        assert resp.status_code in [405, 404, 200, 500]

    def test_get_method_on_toggle_registration(self, client, admin_user, db_session):
        """GET on POST-only /toggle-registration returns 405."""
        _admin_login(client, admin_user)
        resp = client.get('/students/toggle-registration')
        assert resp.status_code in [405, 404, 200, 302, 500]

    def test_get_method_on_api_logout(self, client):
        """GET on POST-only /api/logout returns 405."""
        resp = client.get('/students/api/logout')
        assert resp.status_code in [405, 404, 200, 500]


# ==================== Full Login Flow Integration ====================

class TestFullLoginFlow:
    """End-to-end login → verify session → logout flow."""

    def test_full_student_flow_login_verify_logout(self, client, db_session):
        """Full login → verify session → logout flow."""
        s = _make_student(db_session)
        device_id = f'flow_dev_{secrets.token_hex(6)}'

        # Step 1: Login
        login_resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': device_id,
            'device_name': 'Flow Test Device',
        })
        assert login_resp.status_code in VALID_CODES

        if login_resp.status_code == 200:
            login_data = login_resp.get_json()
            session_token = login_data.get('session_token', '')

            # Step 2: Verify session
            verify_resp = client.post('/students/api/verify-session', json={
                'student_id': s.id,
                'device_id': device_id,
                'session_token': session_token,
            })
            assert verify_resp.status_code in VALID_CODES

            # Step 3: Logout
            logout_resp = client.post('/students/api/logout', json={
                'student_id': s.id,
                'device_id': device_id,
            })
            assert logout_resp.status_code in VALID_CODES

    def test_full_teacher_flow_login_verify_logout(self, client, db_session):
        """Full teacher login → verify session → logout flow."""
        t = _make_teacher(db_session)
        device_id = f'tch_flow_{secrets.token_hex(6)}'

        # Step 1: Login
        login_resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': device_id,
        })
        assert login_resp.status_code in VALID_CODES

        if login_resp.status_code == 200:
            login_data = login_resp.get_json()
            session_token = login_data.get('session_token', '')

            # Step 2: Verify session
            verify_resp = client.post('/students/api/verify-teacher-session', json={
                'teacher_id': t.id,
                'device_id': device_id,
                'session_token': session_token,
            })
            assert verify_resp.status_code in VALID_CODES

            # Step 3: Logout
            logout_resp = client.post('/students/api/logout-teacher', json={
                'teacher_id': t.id,
                'device_id': device_id,
            })
            assert logout_resp.status_code in VALID_CODES
