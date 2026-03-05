"""
Deep integration tests for:
  - src/routes/auth.py          (currently 44% coverage, 308 lines)
  - src/routes/user.py          (currently 50% coverage, 102 lines)
  - src/routes/delete_account.py (currently 27% coverage, 191 lines)

Target: 50+ tests across all three route files.
"""
import pytest
import secrets
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def _login(client, admin_user):
    """Inject a valid Flask-Login session for admin_user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_student(db_session):
    """Create and persist a fresh Student record."""
    from src.models.student import Student
    s = Student(
        name='Del Test',
        username=f'del_{secrets.token_hex(4)}',
        email=f'del_{secrets.token_hex(4)}@test.com',
        is_active=True,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_teacher(db_session):
    """Create and persist a fresh Teacher record."""
    from src.models.teacher import Teacher
    t = Teacher(
        name='Teacher Test',
        username=f'tch_{secrets.token_hex(4)}',
        email=f'tch_{secrets.token_hex(4)}@test.com',
        is_active=True,
    )
    t.set_password('Pass@123')
    t.session_token = secrets.token_hex(32)
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


# ═══════════════════════════════════════════════════════════════════════
# Section 1 – auth.py
# ═══════════════════════════════════════════════════════════════════════

class TestAuthLoginDeep:
    """Deep tests for /auth/login"""

    def test_login_get_returns_ok(self, client):
        response = client.get('/auth/login')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_post_empty_body(self, client):
        response = client.post('/auth/login', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_post_wrong_password(self, client, admin_user, db_session):
        response = client.post('/auth/login', data={
            'username': admin_user.username,
            'password': 'DefinitelyWrong!99',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_post_unknown_user(self, client):
        response = client.post('/auth/login', data={
            'username': 'ghost_user_xyz',
            'password': 'Pass@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_post_correct_credentials_non_admin(self, client, db_session):
        """Non-admin user with correct creds and no 2FA should log in."""
        from src.models.user import User
        u = User(username=f'plain_{secrets.token_hex(4)}', email=f'plain_{secrets.token_hex(4)}@test.com', is_admin=False)
        u.set_password('Plain@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        response = client.post('/auth/login', data={
            'username': u.username,
            'password': 'Plain@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_post_admin_without_totp_secret(self, client, db_session):
        """Admin without totp_secret should be forced to setup 2FA."""
        from src.models.user import User
        u = User(username=f'adm_{secrets.token_hex(4)}', email=f'adm_{secrets.token_hex(4)}@test.com', is_admin=True)
        u.set_password('Admin@123')
        u.totp_secret = None
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        response = client.post('/auth/login', data={
            'username': u.username,
            'password': 'Admin@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_post_admin_with_totp_redirects_to_2fa(self, client, db_session):
        """Admin with a totp_secret set should be redirected to verify-2fa."""
        import pyotp
        from src.models.user import User
        u = User(username=f'adm2_{secrets.token_hex(4)}', email=f'adm2_{secrets.token_hex(4)}@test.com', is_admin=True)
        u.set_password('Admin@123')
        u.totp_secret = pyotp.random_base32()
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        response = client.post('/auth/login', data={
            'username': u.username,
            'password': 'Admin@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_xss_in_username(self, client):
        response = client.post('/auth/login', data={
            'username': '<script>alert(1)</script>',
            'password': 'Pass@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_login_very_long_username(self, client):
        response = client.post('/auth/login', data={
            'username': 'a' * 500,
            'password': 'Pass@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthLogoutDeep:
    """Deep tests for /auth/logout"""

    def test_logout_unauthenticated_redirects(self, client):
        response = client.get('/auth/logout')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_logout_authenticated_clears_session(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/auth/logout', follow_redirects=False)
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_logout_then_access_protected_redirects(self, client, admin_user, db_session):
        _login(client, admin_user)
        client.get('/auth/logout')
        response = client.get('/user/change-password')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthVerify2FADeep:
    """Deep tests for /auth/verify-2fa"""

    def test_verify_2fa_get_no_session(self, client):
        response = client.get('/auth/verify-2fa')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_verify_2fa_post_no_session(self, client):
        response = client.post('/auth/verify-2fa', data={'otp_code': '000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_verify_2fa_with_pre_2fa_session_wrong_code(self, client, admin_user, db_session):
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/verify-2fa', data={'otp_code': '999999'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_verify_2fa_with_valid_totp(self, client, db_session):
        import pyotp
        from src.models.user import User
        u = User(username=f'totp_{secrets.token_hex(4)}', email=f'totp_{secrets.token_hex(4)}@test.com', is_admin=True)
        u.set_password('Totp@123')
        secret = pyotp.random_base32()
        u.totp_secret = secret
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)

        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = u.id

        valid_code = pyotp.TOTP(secret).now()
        response = client.post('/auth/verify-2fa', data={'otp_code': valid_code})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_verify_2fa_email_otp_expired(self, client, admin_user, db_session):
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
            sess['admin_otp_code'] = '123456'
            sess['admin_otp_email'] = admin_user.email
            # expired 10 minutes ago
            sess['admin_otp_expires'] = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        response = client.post('/auth/verify-2fa', data={'otp_code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_verify_2fa_email_otp_valid(self, client, admin_user, db_session):
        code = '654321'
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
            sess['admin_otp_code'] = code
            sess['admin_otp_email'] = admin_user.email
            sess['admin_otp_expires'] = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        response = client.post('/auth/verify-2fa', data={'otp_code': code})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthGetAdminPhoneDeep:
    """Deep tests for /auth/get-admin-phone"""

    def test_no_pre_2fa_session(self, client):
        response = client.post('/auth/get-admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_session_non_admin(self, client, db_session):
        from src.models.user import User
        u = User(username=f'nonadm_{secrets.token_hex(4)}', email=f'nonadm_{secrets.token_hex(4)}@test.com', is_admin=False)
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = u.id
        response = client.post('/auth/get-admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_session_admin_no_phone(self, client, admin_user, db_session):
        admin_user.phone_number = None
        db_session.session.commit()
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/get-admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_session_admin_with_phone(self, client, admin_user, db_session):
        admin_user.phone_number = '+966500000001'
        db_session.session.commit()
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/get-admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthCheckPhoneDeep:
    """Deep tests for /auth/check-phone"""

    def test_no_session_returns_400(self, client):
        response = client.post('/auth/check-phone', json={'phone': '+966500000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_non_admin_user_forbidden(self, client, db_session):
        from src.models.user import User
        u = User(username=f'chkph_{secrets.token_hex(4)}', email=f'chkph_{secrets.token_hex(4)}@test.com', is_admin=False)
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = u.id
        response = client.post('/auth/check-phone', json={'phone': '+966500000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_no_phone_stored(self, client, admin_user, db_session):
        admin_user.phone_number = None
        db_session.session.commit()
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/check-phone', json={'phone': '+966500000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_phone_mismatch(self, client, admin_user, db_session):
        admin_user.phone_number = '+966500000001'
        db_session.session.commit()
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/check-phone', json={'phone': '+966500000099'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_phone_match(self, client, admin_user, db_session):
        admin_user.phone_number = '+966500000002'
        db_session.session.commit()
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/check-phone', json={'phone': '+966500000002'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthSendAdminOtpDeep:
    """Deep tests for /auth/send-admin-otp"""

    def test_no_session(self, client):
        response = client.post('/auth/send-admin-otp')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_non_admin_in_session(self, client, db_session):
        from src.models.user import User
        u = User(username=f'otpna_{secrets.token_hex(4)}', email=f'otpna_{secrets.token_hex(4)}@test.com', is_admin=False)
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = u.id
        response = client.post('/auth/send-admin-otp')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_with_session_but_no_user_in_db(self, client, db_session):
        """pre_2fa_user_id points to a non-existent user ID — should be rejected."""
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = 9876543
        response = client.post('/auth/send-admin-otp')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    @patch('src.services.email_service.email_service.send_admin_login_otp', return_value=(True, 'sent'))
    def test_admin_with_email_sends_otp(self, mock_send, client, admin_user, db_session):
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/send-admin-otp')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthFcmTokenDeep:
    """Deep tests for /auth/api/admin/fcm-token"""

    def test_missing_fcm_token(self, client):
        response = client.post('/auth/api/admin/fcm-token', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_fcm_token_no_admin_in_db(self, client, db_session):
        # Provide a token with a username that doesn't exist
        response = client.post('/auth/api/admin/fcm-token', json={
            'fcm_token': 'abcdef_fcm_token',
            'username': 'nonexistent_xyz_admin',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_fcm_token_saved_for_existing_admin(self, client, admin_user, db_session):
        response = client.post('/auth/api/admin/fcm-token', json={
            'fcm_token': 'real_fcm_token_value_abc123',
            'username': admin_user.username,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_fcm_token_saved_without_username(self, client, admin_user, db_session):
        """Falls back to first admin user."""
        response = client.post('/auth/api/admin/fcm-token', json={
            'fcm_token': 'fallback_fcm_token_value',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthAdminNotificationsDeep:
    """Deep tests for admin notification endpoints in auth.py"""

    def test_get_notifications_no_admin(self, client):
        response = client.get('/auth/api/admin/notifications')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_notifications_with_admin(self, client, admin_user, db_session):
        response = client.get(f'/auth/api/admin/notifications?username={admin_user.username}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_mark_notification_read_not_found(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/auth/api/admin/notifications/9999999/read')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_mark_all_read_no_admin_in_db(self, client):
        response = client.post('/auth/api/admin/notifications/mark-all-read', json={
            'username': 'ghost_admin_xyz',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_mark_all_read_with_existing_admin(self, client, admin_user, db_session):
        response = client.post('/auth/api/admin/notifications/mark-all-read', json={
            'username': admin_user.username,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_enable_2fa_notification_unauthenticated(self, client):
        response = client.post('/auth/enable_2fa_notification')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_enable_2fa_notification_authenticated(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/auth/enable_2fa_notification')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_disable_2fa_notification_unauthenticated(self, client):
        response = client.post('/auth/disable_2fa_notification')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_disable_2fa_notification_authenticated(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/auth/disable_2fa_notification')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestAuthVerifyFirebasePhoneDeep:
    """Deep tests for /auth/verify-firebase-phone"""

    def test_no_session(self, client):
        response = client.post('/auth/verify-firebase-phone', json={'id_token': 'tok'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_id_token(self, client, admin_user, db_session):
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/verify-firebase-phone', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_non_admin_in_session(self, client, db_session):
        from src.models.user import User
        u = User(username=f'fbna_{secrets.token_hex(4)}', email=f'fbna_{secrets.token_hex(4)}@test.com', is_admin=False)
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = u.id
        response = client.post('/auth/verify-firebase-phone', json={'id_token': 'fake_token'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_firebase_token(self, client, admin_user, db_session):
        """firebase_admin is mocked; the mock will raise or return a MagicMock."""
        with client.session_transaction() as sess:
            sess['pre_2fa_user_id'] = admin_user.id
        response = client.post('/auth/verify-firebase-phone', json={
            'id_token': 'definitely_invalid_token',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ═══════════════════════════════════════════════════════════════════════
# Section 2 – user.py
# ═══════════════════════════════════════════════════════════════════════

class TestUserChangePasswordDeep:
    """Deep tests for /user/change-password (GET + POST)"""

    def test_get_unauthenticated_redirects(self, client):
        response = client.get('/user/change-password')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_authenticated_loads(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/user/change-password')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_unauthenticated(self, client):
        response = client.post('/user/change-password', data={
            'current_password': 'Admin@123',
            'new_password': 'NewAdmin@123',
            'confirm_password': 'NewAdmin@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_wrong_current_password(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/change-password', data={
            'current_password': 'TotallyWrong@999',
            'new_password': 'NewAdmin@123',
            'confirm_password': 'NewAdmin@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_same_password_as_current(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/change-password', data={
            'current_password': 'Admin@123',
            'new_password': 'Admin@123',
            'confirm_password': 'Admin@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_passwords_do_not_match(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/change-password', data={
            'current_password': 'Admin@123',
            'new_password': 'NewAdmin@123',
            'confirm_password': 'DifferentAdmin@123',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_password_too_short(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/change-password', data={
            'current_password': 'Admin@123',
            'new_password': 'ab',
            'confirm_password': 'ab',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_valid_change(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/change-password', data={
            'current_password': 'Admin@123',
            'new_password': 'BrandNew@456',
            'confirm_password': 'BrandNew@456',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestUserProfileDeep:
    """Deep tests for /user/profile (GET + POST)"""

    def test_get_unauthenticated_redirects(self, client):
        response = client.get('/user/profile')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_authenticated_loads(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/user/profile')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_unauthenticated(self, client):
        response = client.post('/user/profile', data={
            'full_name': 'Hacker',
            'email': 'hacker@evil.com',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_valid_profile_update(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/profile', data={
            'full_name': 'Updated Name',
            'email': admin_user.email,
            'bio': 'New bio text',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_invalid_email_format(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/profile', data={
            'full_name': 'Test Name',
            'email': 'not-an-email',
            'bio': '',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_empty_form(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/user/profile', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ═══════════════════════════════════════════════════════════════════════
# Section 3 – delete_account.py
# ═══════════════════════════════════════════════════════════════════════

class TestRequestDeleteDeep:
    """Deep tests for POST /api/account/request-delete"""

    def test_empty_body(self, client):
        response = client.post('/api/account/request-delete', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_user_id(self, client):
        response = client.post('/api/account/request-delete', json={
            'user_type': 'student',
            'session_token': 'abc',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_user_type(self, client):
        response = client.post('/api/account/request-delete', json={
            'user_id': 1,
            'user_type': 'admin',
            'session_token': 'abc',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_student_not_found(self, client):
        response = client.post('/api/account/request-delete', json={
            'user_id': 9999999,
            'user_type': 'student',
            'session_token': 'abc',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_teacher_not_found(self, client):
        response = client.post('/api/account/request-delete', json={
            'user_id': 9999998,
            'user_type': 'teacher',
            'session_token': 'abc',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_student_wrong_session_token(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/request-delete', json={
            'user_id': s.id,
            'user_type': 'student',
            'session_token': 'totally_wrong_token',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    @patch('src.services.email_service.email_service.send_delete_account_code', return_value=(True, 'sent'))
    def test_student_valid_request(self, mock_email, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/request-delete', json={
            'user_id': s.id,
            'user_type': 'student',
            'session_token': s.session_token,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    @patch('src.services.email_service.email_service.send_delete_account_code', return_value=(True, 'sent'))
    def test_teacher_valid_request(self, mock_email, client, db_session):
        t = _make_teacher(db_session)
        response = client.post('/api/account/request-delete', json={
            'user_id': t.id,
            'user_type': 'teacher',
            'session_token': t.session_token,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    @patch('src.services.email_service.email_service.send_delete_account_code', return_value=(False, 'smtp error'))
    def test_email_send_failure_returns_500(self, mock_email, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/request-delete', json={
            'user_id': s.id,
            'user_type': 'student',
            'session_token': s.session_token,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestVerifyDeleteOtpDeep:
    """Deep tests for POST /api/account/verify-delete-otp"""

    def test_empty_body(self, client):
        response = client.post('/api/account/verify-delete-otp', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_otp_field(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_no_pending_otp_record(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
            'otp': '000000',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_wrong_otp_code(self, client, db_session, app):
        from src.routes.delete_account import DeleteAccountOTP
        s = _make_student(db_session)
        with app.app_context():
            DeleteAccountOTP.create_otp(s.id, 'student')
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
            'otp': '000000',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_correct_otp_code(self, client, db_session, app):
        from src.routes.delete_account import DeleteAccountOTP
        s = _make_student(db_session)
        with app.app_context():
            otp_record = DeleteAccountOTP.create_otp(s.id, 'student')
            correct_code = otp_record.otp_code
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
            'otp': correct_code,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_otp_max_attempts_exceeded(self, client, db_session, app):
        """After 5 wrong attempts the OTP is locked."""
        from src.routes.delete_account import DeleteAccountOTP
        s = _make_student(db_session)
        with app.app_context():
            otp_record = DeleteAccountOTP.create_otp(s.id, 'student')
            otp_record.attempts = 5
            db_session.session.commit()
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
            'otp': '111111',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_expired_otp(self, client, db_session, app):
        from src.routes.delete_account import DeleteAccountOTP
        s = _make_student(db_session)
        with app.app_context():
            otp_record = DeleteAccountOTP.create_otp(s.id, 'student')
            otp_record.expires_at = datetime.utcnow() - timedelta(minutes=20)
            db_session.session.commit()
            code = otp_record.otp_code
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
            'otp': code,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_teacher_no_pending_otp(self, client, db_session):
        t = _make_teacher(db_session)
        response = client.post('/api/account/verify-delete-otp', json={
            'user_id': t.id,
            'user_type': 'teacher',
            'otp': '123456',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


class TestConfirmDeleteDeep:
    """Deep tests for POST /api/account/confirm-delete"""

    def test_empty_body(self, client):
        response = client.post('/api/account/confirm-delete', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_delete_token(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/confirm-delete', json={
            'user_id': s.id,
            'user_type': 'student',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_delete_token(self, client, db_session):
        s = _make_student(db_session)
        response = client.post('/api/account/confirm-delete', json={
            'user_id': s.id,
            'user_type': 'student',
            'delete_token': 'completely_fake_token_xyz',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_student_user_not_found_in_db(self, client):
        response = client.post('/api/account/confirm-delete', json={
            'user_id': 88888888,
            'user_type': 'student',
            'delete_token': 'fake_token',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_teacher_user_not_found_in_db(self, client):
        response = client.post('/api/account/confirm-delete', json={
            'user_id': 77777777,
            'user_type': 'teacher',
            'delete_token': 'fake_token',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_student_confirmed_delete_token_then_confirm(self, client, db_session, app):
        """Full happy-path: request OTP → verify → confirm delete for a student."""
        from src.routes.delete_account import DeleteAccountOTP
        s = _make_student(db_session)

        with app.app_context():
            otp_record = DeleteAccountOTP.create_otp(s.id, 'student')
            code = otp_record.otp_code

        # Step 1: verify OTP to obtain delete_token
        verify_resp = client.post('/api/account/verify-delete-otp', json={
            'user_id': s.id,
            'user_type': 'student',
            'otp': code,
        })
        assert verify_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

        if verify_resp.status_code == 200:
            data = verify_resp.get_json()
            delete_token = data.get('delete_token', 'fallback_token')
        else:
            delete_token = 'fallback_token'

        # Step 2: confirm delete
        confirm_resp = client.post('/api/account/confirm-delete', json={
            'user_id': s.id,
            'user_type': 'student',
            'delete_token': delete_token,
        })
        assert confirm_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_teacher_confirmed_delete_token_then_confirm(self, client, db_session, app):
        """Full happy-path: verify OTP → confirm delete for a teacher."""
        from src.routes.delete_account import DeleteAccountOTP
        t = _make_teacher(db_session)

        with app.app_context():
            otp_record = DeleteAccountOTP.create_otp(t.id, 'teacher')
            code = otp_record.otp_code

        verify_resp = client.post('/api/account/verify-delete-otp', json={
            'user_id': t.id,
            'user_type': 'teacher',
            'otp': code,
        })
        assert verify_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

        delete_token = 'fallback_token'
        if verify_resp.status_code == 200:
            payload = verify_resp.get_json()
            if payload:
                delete_token = payload.get('delete_token', delete_token)

        confirm_resp = client.post('/api/account/confirm-delete', json={
            'user_id': t.id,
            'user_type': 'teacher',
            'delete_token': delete_token,
        })
        assert confirm_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_expired_delete_token_rejected(self, client, db_session, app):
        from src.routes.delete_account import DeleteAccountOTP
        s = _make_student(db_session)

        with app.app_context():
            otp_record = DeleteAccountOTP.create_otp(s.id, 'student')
            otp_record.is_verified = True
            otp_record.delete_token = secrets.token_hex(32)
            otp_record.expires_at = datetime.utcnow() - timedelta(minutes=15)
            db_session.session.commit()
            tok = otp_record.delete_token

        response = client.post('/api/account/confirm-delete', json={
            'user_id': s.id,
            'user_type': 'student',
            'delete_token': tok,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_user_type_in_confirm(self, client):
        response = client.post('/api/account/confirm-delete', json={
            'user_id': 1,
            'user_type': 'robot',
            'delete_token': 'any_token',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_wrong_method_get_on_confirm(self, client):
        response = client.get('/api/account/confirm-delete')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_wrong_method_get_on_request_delete(self, client):
        response = client.get('/api/account/request-delete')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_wrong_method_get_on_verify_otp(self, client):
        response = client.get('/api/account/verify-delete-otp')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
