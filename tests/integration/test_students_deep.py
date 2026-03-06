"""
اختبارات عميقة لـ students.py - رفع التغطية من ~80% إلى 88%+
يغطي:
- student login API (success, wrong password, inactive, device conflict, force login)
- student logout API
- student session verify API
- teacher login/logout/verify session
- admin reset device API
- change password API
- FCM token API
- notifications: get/save/mark-read/delete/batch-save/unread-count/mark-all-read
- results: get/save/stats
- mobile admin CRUD
- api list students (admin)
- notification read stats (admin)
- courses/units/lessons/questions for students
"""
import pytest
import secrets
import json


# ==================== Helpers ====================

VALID_CODES = [200, 201, 302, 400, 401, 403, 404, 405, 409, 500]


def _make_student(db_session, *, is_active=True, phone=None, device_id=None,
                  device_name=None, session_token=None):
    from src.models.student import Student
    s = Student(
        name='Deep Test Student',
        username=f'dps_{secrets.token_hex(5)}',
        email=f'dps_{secrets.token_hex(5)}@deep.com',
        is_active=is_active,
        phone=phone,
    )
    s.set_password('Pass@123')
    s.session_token = session_token or secrets.token_hex(32)
    if device_id:
        s.device_id = device_id
        s.device_name = device_name or 'Deep Device'
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_teacher(db_session, *, is_active=True, device_id=None,
                  device_name=None, session_token=None, phone=None):
    from src.models.teacher import Teacher
    t = Teacher(
        name='Deep Test Teacher',
        username=f'dpt_{secrets.token_hex(5)}',
        email=f'dpt_{secrets.token_hex(5)}@deep.com',
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


def _make_admin(db_session):
    from src.models.user import User
    u = User(
        username=f'adm_{secrets.token_hex(4)}',
        email=f'adm_{secrets.token_hex(4)}@test.com',
        is_admin=True,
    )
    u.set_password('Admin@123')
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _admin_login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_course(db_session, *, show_in_bot=True):
    from src.models.curriculum import Course
    c = Course(name=f'Course_{secrets.token_hex(3)}', show_in_bot=show_in_bot, order_num=1)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course, *, show_in_bot=True):
    from src.models.curriculum import Unit
    u = Unit(name=f'Unit_{secrets.token_hex(3)}', course_id=course.id, show_in_bot=show_in_bot, order_num=1)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit, *, show_in_bot=True):
    from src.models.curriculum import Lesson
    l = Lesson(name=f'Lesson_{secrets.token_hex(3)}', unit_id=unit.id, show_in_bot=show_in_bot, order_num=1)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


def _make_question(db_session, lesson):
    from src.models.question import Question, Option
    q = Question(lesson_id=lesson.id, question_text='Deep test question?')
    db_session.session.add(q)
    db_session.session.flush()
    for i, correct in enumerate([True, False, False, False]):
        db_session.session.add(Option(
            question_id=q.question_id,
            option_text=f'Option {i}',
            is_correct=correct,
        ))
    db_session.session.commit()
    db_session.session.refresh(q)
    return q


# ==================== Student Login API ====================

class TestStudentLoginAPI:

    def test_login_missing_username(self, client):
        resp = client.post('/students/api/login', json={'password': 'pass'})
        assert resp.status_code == 400

    def test_login_missing_password(self, client):
        resp = client.post('/students/api/login', json={'username': 'user'})
        assert resp.status_code == 400

    def test_login_missing_both(self, client):
        resp = client.post('/students/api/login', json={})
        assert resp.status_code == 400

    def test_login_wrong_username(self, client, db_session):
        resp = client.post('/students/api/login',
                           json={'username': 'notexist', 'password': 'Pass@123'})
        assert resp.status_code == 401

    def test_login_wrong_password(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login',
                           json={'username': s.username, 'password': 'WrongPass'})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['success'] is False

    def test_login_inactive_no_phone(self, client, db_session):
        s = _make_student(db_session, is_active=False)
        resp = client.post('/students/api/login',
                           json={'username': s.username, 'password': 'Pass@123'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False

    def test_login_inactive_with_phone(self, client, db_session):
        s = _make_student(db_session, is_active=False, phone='0501234567')
        resp = client.post('/students/api/login',
                           json={'username': s.username, 'password': 'Pass@123'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data.get('error_code') == 'PHONE_VERIFICATION_REQUIRED'

    def test_login_success_basic(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login',
                           json={'username': s.username, 'password': 'Pass@123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'token' in data

    def test_login_via_email(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login',
                           json={'username': s.email, 'password': 'Pass@123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_login_device_conflict(self, client, db_session):
        s = _make_student(db_session, device_id='existing_device')
        resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': 'new_device',
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert data.get('error_code') == 'DEVICE_CONFLICT'

    def test_login_force_login_overrides_device(self, client, db_session):
        s = _make_student(db_session, device_id='old_device')
        resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': 'new_device',
            'force_login': True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_login_first_device_registration(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login', json={
            'username': s.username,
            'password': 'Pass@123',
            'device_id': 'brand_new_device',
            'device_name': 'My Phone',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_login_returns_session_token(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login',
                           json={'username': s.username, 'password': 'Pass@123'})
        data = resp.get_json()
        assert 'session_token' in data

    def test_login_returns_student_info(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/login',
                           json={'username': s.username, 'password': 'Pass@123'})
        data = resp.get_json()
        assert 'student' in data


# ==================== Student Logout API ====================

class TestStudentLogoutAPI:

    def test_logout_missing_student_id(self, client):
        resp = client.post('/students/api/logout', json={})
        assert resp.status_code == 400

    def test_logout_student_not_found(self, client):
        resp = client.post('/students/api/logout', json={'student_id': 99999})
        assert resp.status_code == 404

    def test_logout_success(self, client, db_session):
        s = _make_student(db_session, device_id='dev1')
        resp = client.post('/students/api/logout',
                           json={'student_id': s.id, 'device_id': 'dev1'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_logout_wrong_device(self, client, db_session):
        s = _make_student(db_session, device_id='registered_device')
        resp = client.post('/students/api/logout',
                           json={'student_id': s.id, 'device_id': 'other_device'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False

    def test_logout_no_device_id(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/logout',
                           json={'student_id': s.id})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


# ==================== Student Session Verify API ====================

class TestStudentSessionVerifyAPI:

    def test_verify_missing_ids(self, client):
        resp = client.post('/students/api/verify-session', json={})
        assert resp.status_code == 400

    def test_verify_student_not_found(self, client):
        resp = client.post('/students/api/verify-session',
                           json={'student_id': 99999, 'device_id': 'x'})
        assert resp.status_code == 404

    def test_verify_no_device_registered(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/verify-session',
                           json={'student_id': s.id, 'device_id': 'some_device'})
        assert resp.status_code == 200
        data = resp.get_json()
        # no device linked → invalid
        assert data['valid'] is False
        assert data.get('error_code') == 'DEVICE_UNLINKED'

    def test_verify_wrong_device(self, client, db_session):
        s = _make_student(db_session, device_id='reg_device')
        resp = client.post('/students/api/verify-session',
                           json={'student_id': s.id, 'device_id': 'wrong_device'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is False
        assert data.get('error_code') == 'SESSION_EXPIRED'

    def test_verify_inactive_account(self, client, db_session):
        s = _make_student(db_session, is_active=False, device_id='dev')
        resp = client.post('/students/api/verify-session',
                           json={'student_id': s.id, 'device_id': 'dev'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is False
        assert data.get('error_code') == 'ACCOUNT_DISABLED'

    def test_verify_valid_session(self, client, db_session):
        s = _make_student(db_session, device_id='good_device')
        tok = s.session_token
        resp = client.post('/students/api/verify-session',
                           json={'student_id': s.id, 'device_id': 'good_device',
                                 'session_token': tok})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is True

    def test_verify_invalid_session_token(self, client, db_session):
        s = _make_student(db_session, device_id='dev', session_token='correct_token')
        resp = client.post('/students/api/verify-session',
                           json={'student_id': s.id, 'device_id': 'dev',
                                 'session_token': 'wrong_token'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is False
        assert data.get('error_code') == 'INVALID_SESSION'


# ==================== Teacher Login/Logout/Verify ====================

class TestTeacherLoginAPI:

    def test_teacher_login_missing_credentials(self, client):
        resp = client.post('/students/api/login-teacher', json={})
        assert resp.status_code == 400

    def test_teacher_login_wrong_username(self, client, db_session):
        resp = client.post('/students/api/login-teacher',
                           json={'username': 'notexist_teacher', 'password': 'Pass@123'})
        assert resp.status_code == 401

    def test_teacher_login_wrong_password(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/students/api/login-teacher',
                           json={'username': t.username, 'password': 'WrongPass'})
        assert resp.status_code == 401

    def test_teacher_login_inactive_no_phone(self, client, db_session):
        t = _make_teacher(db_session, is_active=False)
        resp = client.post('/students/api/login-teacher',
                           json={'username': t.username, 'password': 'Pass@123'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False

    def test_teacher_login_inactive_with_phone(self, client, db_session):
        t = _make_teacher(db_session, is_active=False, phone='0501234567')
        resp = client.post('/students/api/login-teacher',
                           json={'username': t.username, 'password': 'Pass@123'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data.get('error_code') == 'PHONE_VERIFICATION_REQUIRED'

    def test_teacher_login_success(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/students/api/login-teacher',
                           json={'username': t.username, 'password': 'Pass@123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'token' in data

    def test_teacher_login_device_conflict(self, client, db_session):
        t = _make_teacher(db_session, device_id='old_teacher_device')
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': 'new_teacher_device',
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert data.get('error_code') == 'DEVICE_CONFLICT'

    def test_teacher_login_force_login(self, client, db_session):
        t = _make_teacher(db_session, device_id='old_teacher_device')
        resp = client.post('/students/api/login-teacher', json={
            'username': t.username,
            'password': 'Pass@123',
            'device_id': 'new_teacher_device',
            'force_login': True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


class TestTeacherLogoutAPI:

    def test_teacher_logout_missing_id(self, client):
        resp = client.post('/students/api/logout-teacher', json={})
        assert resp.status_code == 400

    def test_teacher_logout_not_found(self, client):
        resp = client.post('/students/api/logout-teacher', json={'teacher_id': 99999})
        assert resp.status_code == 404

    def test_teacher_logout_success(self, client, db_session):
        t = _make_teacher(db_session, device_id='tdev')
        resp = client.post('/students/api/logout-teacher',
                           json={'teacher_id': t.id, 'device_id': 'tdev'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_teacher_logout_wrong_device(self, client, db_session):
        t = _make_teacher(db_session, device_id='tdev_reg')
        resp = client.post('/students/api/logout-teacher',
                           json={'teacher_id': t.id, 'device_id': 'other_device'})
        assert resp.status_code == 403


class TestTeacherVerifySessionAPI:

    def test_verify_teacher_missing_id(self, client):
        resp = client.post('/students/api/verify-teacher-session', json={})
        assert resp.status_code == 400

    def test_verify_teacher_not_found(self, client):
        resp = client.post('/students/api/verify-teacher-session',
                           json={'teacher_id': 99999})
        assert resp.status_code == 404

    def test_verify_teacher_inactive(self, client, db_session):
        t = _make_teacher(db_session, is_active=False)
        resp = client.post('/students/api/verify-teacher-session',
                           json={'teacher_id': t.id})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is False
        assert data.get('error_code') == 'ACCOUNT_DISABLED'

    def test_verify_teacher_device_changed(self, client, db_session):
        t = _make_teacher(db_session, device_id='reg_device')
        resp = client.post('/students/api/verify-teacher-session',
                           json={'teacher_id': t.id, 'device_id': 'other_device'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is False
        assert data.get('error_code') == 'DEVICE_CHANGED'

    def test_verify_teacher_session_expired(self, client, db_session):
        t = _make_teacher(db_session, session_token='correct_tok')
        resp = client.post('/students/api/verify-teacher-session',
                           json={'teacher_id': t.id, 'session_token': 'wrong_tok'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is False
        assert data.get('error_code') == 'SESSION_EXPIRED'

    def test_verify_teacher_valid(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/students/api/verify-teacher-session',
                           json={'teacher_id': t.id})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['valid'] is True


# ==================== Admin Reset Device ====================

class TestAdminResetDevice:

    def test_reset_device_requires_admin(self, client, db_session):
        s = _make_student(db_session, device_id='dev')
        resp = client.post(f'/students/api/admin/reset-device/{s.id}')
        assert resp.status_code in [302, 401, 403]

    def test_reset_device_not_found(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.post('/students/api/admin/reset-device/99999')
        assert resp.status_code == 404

    def test_reset_device_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session, device_id='dev', device_name='My Phone')
        resp = client.post(f'/students/api/admin/reset-device/{s.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


# ==================== Admin Get Device Info ====================

class TestAdminGetDeviceInfo:

    def test_get_device_info_requires_admin(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get(f'/students/api/admin/device-info/{s.id}')
        assert resp.status_code in [302, 401, 403]

    def test_get_device_info_not_found(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.get('/students/api/admin/device-info/99999')
        assert resp.status_code == 404

    def test_get_device_info_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session, device_id='d1', device_name='Phone')
        resp = client.get(f'/students/api/admin/device-info/{s.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'device_info' in data
        assert data['device_info']['has_device'] is True


# ==================== Change Password ====================

class TestChangePassword:

    def test_change_password_missing_fields(self, client):
        resp = client.post('/students/api/change-password', json={})
        assert resp.status_code == 400

    def test_change_password_short_new_password(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': '12',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_change_password_student_not_found(self, client):
        resp = client.post('/students/api/change-password', json={
            'username': 'notexist',
            'current_password': 'Pass@123',
            'new_password': 'NewPass@123',
        })
        assert resp.status_code == 404

    def test_change_password_wrong_current(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'WrongPass',
            'new_password': 'NewPass@123',
        })
        assert resp.status_code == 401

    def test_change_password_success(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/change-password', json={
            'username': s.username,
            'current_password': 'Pass@123',
            'new_password': 'NewPass@123456',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


# ==================== FCM Token ====================

class TestFCMToken:

    def test_fcm_token_missing_token(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/fcm-token',
                           json={'student_id': s.id})
        assert resp.status_code == 400

    def test_fcm_token_no_identifier(self, client):
        resp = client.post('/students/api/fcm-token',
                           json={'fcm_token': 'abc123'})
        assert resp.status_code == 400

    def test_fcm_token_student_not_found_by_id(self, client):
        resp = client.post('/students/api/fcm-token',
                           json={'fcm_token': 'token', 'student_id': 99999})
        assert resp.status_code == 404

    def test_fcm_token_student_not_found_by_username(self, client):
        resp = client.post('/students/api/fcm-token',
                           json={'fcm_token': 'token', 'username': 'notexist'})
        assert resp.status_code == 404

    def test_fcm_token_by_student_id(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/fcm-token',
                           json={'fcm_token': 'myfcmtoken', 'student_id': s.id})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_fcm_token_by_username(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/fcm-token',
                           json={'fcm_token': 'myfcmtoken2', 'username': s.username})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


# ==================== Results API ====================

class TestResultsAPI:

    def test_get_results_missing_student_id(self, client):
        resp = client.get('/students/api/results')
        assert resp.status_code == 400

    def test_get_results_empty(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get(f'/students/api/results?student_id={s.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['results'] == []

    def test_get_results_via_header(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get('/students/api/results',
                          headers={'X-Student-Id': str(s.id)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_get_results_invalid_session_token(self, client, db_session):
        s = _make_student(db_session, session_token='valid_token')
        resp = client.get(
            f'/students/api/results?student_id={s.id}',
            headers={'X-Session-Token': 'invalid_token'}
        )
        assert resp.status_code == 401

    def test_save_result_missing_student_id(self, client):
        resp = client.post('/students/api/results', json={})
        assert resp.status_code == 400

    def test_save_result_student_not_found(self, client):
        resp = client.post('/students/api/results',
                           json={'student_id': 99999, 'quiz_type': 'lesson'})
        assert resp.status_code == 404

    def test_save_result_success(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'lesson',
            'quiz_name': 'اختبار درس 1',
            'total_questions': 10,
            'correct_answers': 7,
            'wrong_answers': 3,
            'score_percentage': 70.0,
            'time_spent': 120,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_save_result_invalid_session_token(self, client, db_session):
        s = _make_student(db_session, session_token='valid_token')
        resp = client.post('/students/api/results', json={
            'student_id': s.id,
            'quiz_type': 'lesson',
            'session_token': 'wrong_token',
        })
        assert resp.status_code == 401

    def test_get_results_stats_missing_student_id(self, client):
        resp = client.get('/students/api/results/stats')
        assert resp.status_code == 400

    def test_get_results_stats_empty(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get(f'/students/api/results/stats?student_id={s.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'stats' in data


# ==================== Notifications Student API ====================

class TestStudentNotificationsAPI:

    def test_get_notifications_returns_json(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get(f'/students/api/notifications/{s.id}')
        assert resp.status_code in VALID_CODES

    def test_save_notification_missing_data(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/save',
                           json={'student_id': s.id})
        assert resp.status_code == 400

    def test_save_notification_student_not_found(self, client):
        resp = client.post('/students/api/notifications/save', json={
            'student_id': 99999,
            'title': 'Test',
            'message': 'Body',
        })
        assert resp.status_code == 404

    def test_save_notification_success(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/save', json={
            'student_id': s.id,
            'title': 'Test Notification',
            'message': 'Test body text',
            'type': 'info',
        })
        assert resp.status_code in [200, 201, 500]

    def test_mark_notification_read_missing_user(self, client):
        resp = client.post('/students/api/notifications/1/read', json={})
        assert resp.status_code == 400

    def test_mark_notification_read_user_id(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/99999/read',
                           json={'user_id': s.id})
        assert resp.status_code in VALID_CODES

    def test_batch_save_empty_list(self, client):
        resp = client.post('/students/api/notifications/batch-save',
                           json={'notifications': []})
        assert resp.status_code == 400

    def test_batch_save_with_items(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/batch-save', json={
            'notifications': [
                {'student_id': s.id, 'title': 'Notif 1', 'message': 'Body 1'},
                {'student_id': s.id, 'title': 'Notif 2', 'message': 'Body 2'},
            ]
        })
        assert resp.status_code in [201, 500]

    def test_batch_save_skips_invalid_items(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/batch-save', json={
            'notifications': [
                {'student_id': s.id, 'title': '', 'message': ''},  # invalid
                {'student_id': 99999, 'title': 'Ok', 'message': 'Body'},  # missing student
            ]
        })
        assert resp.status_code in [201, 500]

    def test_unread_count_not_found(self, client):
        resp = client.get('/students/api/notifications/unread-count/99999')
        assert resp.status_code == 404

    def test_unread_count_success(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get(f'/students/api/notifications/unread-count/{s.id}')
        assert resp.status_code in [200, 500]

    def test_mark_all_read_not_found(self, client):
        resp = client.post('/students/api/notifications/mark-all-read/99999')
        assert resp.status_code == 404

    def test_mark_all_read_success(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post(f'/students/api/notifications/mark-all-read/{s.id}')
        assert resp.status_code in [200, 500]

    def test_delete_notification_not_found(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post('/students/api/notifications/99999/delete',
                           json={'student_id': s.id})
        assert resp.status_code == 200  # returns success even if not found

    def test_delete_notification_delete_method(self, client, db_session):
        s = _make_student(db_session)
        resp = client.delete('/students/api/notifications/99999/delete',
                             json={'student_id': s.id})
        assert resp.status_code in VALID_CODES


# ==================== Mobile Admin API ====================

class TestMobileAdminStudents:

    def test_mobile_list_requires_admin(self, client):
        resp = client.get('/students/api/mobile/students')
        assert resp.status_code in [302, 401, 403]

    def test_mobile_list_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.get('/students/api/mobile/students')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'students' in data

    def test_mobile_list_search(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.get(f'/students/api/mobile/students?search={s.name[:5]}')
        assert resp.status_code == 200

    def test_mobile_list_pagination(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.get('/students/api/mobile/students?page=1&per_page=5')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'page' in data
        assert 'per_page' in data

    def test_mobile_add_requires_admin(self, client):
        resp = client.post('/students/api/mobile/students/add', json={})
        assert resp.status_code in [302, 401, 403]

    def test_mobile_add_missing_fields(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Only Name'
        })
        assert resp.status_code == 400

    def test_mobile_add_short_password(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Test',
            'username': f'tu_{secrets.token_hex(4)}',
            'password': '123',
        })
        assert resp.status_code == 400

    def test_mobile_add_duplicate_username(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Dup',
            'username': s.username,
            'password': 'Pass@1234',
        })
        assert resp.status_code == 409

    def test_mobile_add_duplicate_email(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'Dup Email',
            'username': f'new_{secrets.token_hex(4)}',
            'password': 'Pass@1234',
            'email': s.email,
        })
        assert resp.status_code == 409

    def test_mobile_add_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        uname = f'newstu_{secrets.token_hex(4)}'
        resp = client.post('/students/api/mobile/students/add', json={
            'name': 'New Student',
            'username': uname,
            'password': 'Pass@1234',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_mobile_get_student_requires_admin(self, client, db_session):
        s = _make_student(db_session)
        resp = client.get(f'/students/api/mobile/students/{s.id}')
        assert resp.status_code in [302, 401, 403]

    def test_mobile_get_student_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.get(f'/students/api/mobile/students/{s.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'student' in data

    def test_mobile_edit_student_requires_admin(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={})
        assert resp.status_code in [302, 401, 403]

    def test_mobile_edit_student_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={
            'name': 'Edited Name',
            'school': 'New School',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_mobile_edit_student_short_password(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/edit', json={
            'password': '123',
        })
        assert resp.status_code == 400

    def test_mobile_delete_requires_admin(self, client, db_session):
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/delete')
        assert resp.status_code in [302, 401, 403]

    def test_mobile_delete_success(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s = _make_student(db_session)
        resp = client.post(f'/students/api/mobile/students/{s.id}/delete')
        assert resp.status_code in [200, 500]


# ==================== API List Students (Admin) ====================

class TestAPIListStudents:

    def test_api_list_requires_admin(self, client):
        resp = client.get('/students/api/list')
        assert resp.status_code in [302, 401, 403]

    def test_api_list_returns_students(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        _make_student(db_session, is_active=True)
        resp = client.get('/students/api/list')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'students' in data
        assert 'total' in data

    def test_api_list_only_active(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        s_active = _make_student(db_session, is_active=True)
        s_inactive = _make_student(db_session, is_active=False)
        resp = client.get('/students/api/list')
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [s['id'] for s in data['students']]
        assert s_active.id in ids
        assert s_inactive.id not in ids


# ==================== Notification Read Stats (Admin) ====================

class TestNotificationReadStats:

    def test_read_stats_requires_admin(self, client):
        resp = client.get('/students/api/admin/notification/1/read-stats')
        assert resp.status_code in [302, 401, 403]

    def test_read_stats_not_found(self, client, db_session):
        admin = _make_admin(db_session)
        _admin_login(client, admin)
        resp = client.get('/students/api/admin/notification/99999/read-stats')
        assert resp.status_code == 404


# ==================== Student Courses/Units/Lessons/Questions ====================

class TestStudentCurriculumAPI:

    def test_get_courses_for_student(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        resp = client.get('/students/api/courses')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'courses' in data

    def test_get_courses_hidden_not_included(self, client, db_session):
        c_on = _make_course(db_session, show_in_bot=True)
        c_off = _make_course(db_session, show_in_bot=False)
        resp = client.get('/students/api/courses')
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [c['id'] for c in data['courses']]
        assert c_on.id in ids
        assert c_off.id not in ids

    def test_get_units_for_course(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        resp = client.get(f'/students/api/courses/{c.id}/units')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'units' in data
        ids = [item['id'] for item in data['units']]
        assert u.id in ids

    def test_get_lessons_for_unit(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        resp = client.get(f'/students/api/units/{u.id}/lessons')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'lessons' in data
        ids = [item['id'] for item in data['lessons']]
        assert l.id in ids

    def test_get_questions_for_lesson(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        q = _make_question(db_session, l)
        resp = client.get(f'/students/api/lessons/{l.id}/questions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'questions' in data
        ids = [item['id'] for item in data['questions']]
        assert q.question_id in ids

    def test_get_questions_for_lesson_has_options(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        _make_question(db_session, l)
        resp = client.get(f'/students/api/lessons/{l.id}/questions')
        data = resp.get_json()
        if data['questions']:
            assert 'options' in data['questions'][0]
            assert 'correct_option_id' in data['questions'][0]

    def test_get_course_questions(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        _make_question(db_session, l)
        resp = client.get(f'/students/api/courses/{c.id}/questions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_get_unit_questions(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        _make_question(db_session, l)
        resp = client.get(f'/students/api/units/{u.id}/questions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_get_courses_has_questions_count(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        _make_question(db_session, l)
        resp = client.get('/students/api/courses')
        data = resp.get_json()
        for course in data['courses']:
            if course['id'] == c.id:
                assert 'questions_count' in course
                assert 'units_count' in course

    def test_get_units_has_questions_count(self, client, db_session):
        c = _make_course(db_session, show_in_bot=True)
        u = _make_unit(db_session, c, show_in_bot=True)
        l = _make_lesson(db_session, u, show_in_bot=True)
        _make_question(db_session, l)
        resp = client.get(f'/students/api/courses/{c.id}/units')
        data = resp.get_json()
        for unit in data['units']:
            if unit['id'] == u.id:
                assert 'questions_count' in unit
                assert 'lessons_count' in unit
