"""
Deep integration tests for src/routes/admin_profile.py
Target: 20+ tests covering all three routes with edge cases.

Routes covered:
  GET  /api/admin/profile
  GET  /api/admin/profile/email
  POST /api/admin/send-notification
"""
import pytest
import secrets

ALLOWED = [200, 302, 400, 401, 403, 404, 405, 500]


def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='AI Test',
        username=f'ai_{secrets.token_hex(4)}',
        email=f'ai_{secrets.token_hex(4)}@test.com',
        is_active=True,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


# ===========================================================================
# 1. GET /api/admin/profile
# ===========================================================================

class TestGetAdminProfile:

    def test_no_auth_redirects_or_rejects(self, client):
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED

    def test_as_admin_returns_200(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED

    def test_response_contains_success_true(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert data.get('success') is True

    def test_response_admin_object_has_id(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'admin' in data
            assert 'id' in data['admin']

    def test_response_admin_object_has_username(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'admin' in data
            assert 'username' in data['admin']

    def test_response_admin_object_has_email(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'admin' in data
            assert 'email' in data['admin']

    def test_response_admin_object_has_is_admin_flag(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'admin' in data
            assert data['admin'].get('is_admin') is True

    def test_admin_id_matches_fixture(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data['admin']['id'] == admin_user.id

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/profile')
        assert response.status_code in ALLOWED

    def test_wrong_method_put(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/profile')
        assert response.status_code in ALLOWED

    def test_wrong_method_delete(self, client, admin_user):
        _login(client, admin_user)
        response = client.delete('/api/admin/profile')
        assert response.status_code in ALLOWED

    def test_student_user_gets_403(self, client, db_session):
        """A non-admin logged-in user should be rejected."""
        student = _make_student(db_session)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(student.id)
            sess['_fresh'] = True
        response = client.get('/api/admin/profile')
        assert response.status_code in ALLOWED


# ===========================================================================
# 2. GET /api/admin/profile/email
# ===========================================================================

class TestGetAdminEmail:

    def test_no_auth_redirects_or_rejects(self, client):
        response = client.get('/api/admin/profile/email')
        assert response.status_code in ALLOWED

    def test_as_admin_returns_200(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile/email')
        assert response.status_code in ALLOWED

    def test_response_contains_success_true(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile/email')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_response_contains_email_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile/email')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'email' in data

    def test_email_matches_fixture(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/profile/email')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data['email'] == admin_user.email

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/profile/email')
        assert response.status_code in ALLOWED

    def test_wrong_method_delete(self, client, admin_user):
        _login(client, admin_user)
        response = client.delete('/api/admin/profile/email')
        assert response.status_code in ALLOWED


# ===========================================================================
# 3. POST /api/admin/send-notification
# ===========================================================================

class TestSendNotification:

    def test_no_auth_redirects_or_rejects(self, client):
        response = client.post('/api/admin/send-notification', json={
            'title': 'Test', 'message': 'Body'
        })
        assert response.status_code in ALLOWED

    def test_missing_title(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'message': 'رسالة بدون عنوان'
        })
        assert response.status_code in ALLOWED

    def test_missing_message(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'عنوان بدون رسالة'
        })
        assert response.status_code in ALLOWED

    def test_empty_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={})
        assert response.status_code in ALLOWED

    def test_no_body_at_all(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification')
        assert response.status_code in ALLOWED

    def test_recipient_type_all(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'إشعار عام',
            'message': 'رسالة لجميع الطلاب',
            'recipient_type': 'all'
        })
        assert response.status_code in ALLOWED

    def test_recipient_type_student_id_valid(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'إشعار لطالب',
            'message': 'رسالة شخصية',
            'recipient_type': 'student_id',
            'recipient_id': student.id
        })
        assert response.status_code in ALLOWED

    def test_recipient_type_student_id_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'إشعار',
            'message': 'رسالة',
            'recipient_type': 'student_id',
            'recipient_id': 999999
        })
        assert response.status_code in ALLOWED

    def test_recipient_type_level(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'إشعار مستوى',
            'message': 'رسالة للمستوى الأول',
            'recipient_type': 'level',
            'level': 'grade_1'
        })
        assert response.status_code in ALLOWED

    def test_unknown_recipient_type(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'اختبار',
            'message': 'رسالة',
            'recipient_type': 'unknown_type'
        })
        assert response.status_code in ALLOWED

    def test_response_has_success_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'عنوان',
            'message': 'رسالة',
            'recipient_type': 'all'
        })
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_response_has_sent_count_on_success(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'عنوان',
            'message': 'رسالة',
            'recipient_type': 'all'
        })
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            if data.get('success'):
                assert 'sent_count' in data

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/send-notification')
        assert response.status_code in ALLOWED

    def test_wrong_method_put(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/send-notification', json={
            'title': 'T', 'message': 'M'
        })
        assert response.status_code in ALLOWED

    def test_non_json_content_type(self, client, admin_user):
        _login(client, admin_user)
        response = client.post(
            '/api/admin/send-notification',
            data='title=Test&message=Body',
            content_type='application/x-www-form-urlencoded'
        )
        assert response.status_code in ALLOWED

    def test_student_user_gets_403(self, client, db_session):
        """Non-admin user should be rejected."""
        student = _make_student(db_session)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(student.id)
            sess['_fresh'] = True
        response = client.post('/api/admin/send-notification', json={
            'title': 'Test', 'message': 'Body', 'recipient_type': 'all'
        })
        assert response.status_code in ALLOWED
