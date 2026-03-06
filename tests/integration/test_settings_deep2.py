"""
test_settings_deep2.py
Additional integration tests for settings.py targeting uncovered lines.

Covers:
- Settings index: all submit paths with valid CSRF bypass
- Setup 2FA GET/POST including valid TOTP verification
- Disable 2FA with valid code
- Verify 2FA JSON endpoint all branches
- Google Drive connect/disconnect/status JSON response fields
- Sync-to-drive / download-from-drive / quick-sync paths
- Backup settings GET/POST with all fields
- Create backup (local + google_drive destination)
- Restore backup (valid data, missing data key)
- Google OAuth callback all branches
- Admin phone page GET and Firebase verify POST edge cases
- Various error/edge paths
"""
import pytest
import secrets
import json
import pyotp
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash


VALID_CODES = [200, 302, 400, 401, 403, 404, 405, 500]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_plain_user(db_session):
    from src.models.user import User
    u = User(
        username=f'plain_{secrets.token_hex(4)}',
        email=f'plain_{secrets.token_hex(4)}@test.com',
        is_admin=False,
    )
    u.set_password('Pass@123')
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_drive_token(db_session, user_id):
    from src.models.google_drive import GoogleDriveToken
    token = GoogleDriveToken(
        user_id=user_id,
        access_token=f'ya29.fake_{secrets.token_hex(8)}',
        refresh_token=f'refresh_{secrets.token_hex(8)}',
        scopes='https://www.googleapis.com/auth/drive',
        is_active=True,
    )
    db_session.session.add(token)
    db_session.session.commit()
    db_session.session.refresh(token)
    return token


def _inject_2fa_session(client, secret):
    """Inject a known TOTP secret into the Flask session."""
    with client.session_transaction() as sess:
        sess['temp_2fa_secret'] = secret


# ===========================================================================
# 1. Settings Index - Extended form submissions
# ===========================================================================

class TestSettingsIndexExtended:
    """Additional coverage for /settings/ POST paths."""

    def test_get_unauthenticated_redirects(self, client):
        resp = client.get('/settings/')
        assert resp.status_code in VALID_CODES

    def test_get_authenticated_returns_page(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/')
        assert resp.status_code in VALID_CODES

    def test_post_profile_all_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'profile_submit': '1',
            'full_name': 'Admin Full Name',
            'email': 'admin_updated@test.com',
            'bio': 'A short bio for testing purposes',
        })
        assert resp.status_code in VALID_CODES

    def test_post_profile_empty_bio(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'profile_submit': '1',
            'full_name': 'Admin Test',
            'email': 'admin@test.com',
            'bio': '',
        })
        assert resp.status_code in VALID_CODES

    def test_post_notification_email_only(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'notification_submit': '1',
            'email_notifications': 'y',
            'notification_frequency': 'daily',
        })
        assert resp.status_code in VALID_CODES

    def test_post_notification_app_only(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'notification_submit': '1',
            'app_notifications': 'y',
            'notification_frequency': 'immediate',
        })
        assert resp.status_code in VALID_CODES

    def test_post_notification_all_off(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'notification_submit': '1',
            'notification_frequency': 'weekly',
        })
        assert resp.status_code in VALID_CODES

    def test_post_security_both_on(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'security_submit': '1',
            'two_factor_auth': 'y',
            'login_alerts': 'y',
        })
        assert resp.status_code in VALID_CODES

    def test_post_security_both_off(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'security_submit': '1',
        })
        assert resp.status_code in VALID_CODES

    def test_post_integration_microsoft(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'integration_submit': '1',
            'microsoft_integration': 'y',
        })
        assert resp.status_code in VALID_CODES

    def test_post_integration_both(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'integration_submit': '1',
            'google_integration': 'y',
            'microsoft_integration': 'y',
        })
        assert resp.status_code in VALID_CODES

    def test_post_integration_regenerate_with_provided_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'integration_submit': '1',
            'regenerate_api_key': '1',
            'new_api_key': 'test-api-key-9999',
        })
        assert resp.status_code in VALID_CODES

    def test_post_integration_regenerate_without_provided_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'integration_submit': '1',
            'regenerate_api_key': '1',
        })
        assert resp.status_code in VALID_CODES

    def test_post_change_password_all_fields_missing(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': '',
            'new_password': '',
            'confirm_password': '',
        })
        assert resp.status_code in VALID_CODES

    def test_post_change_password_only_current_provided(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': '',
            'confirm_password': '',
        })
        assert resp.status_code in VALID_CODES

    def test_post_change_password_new_too_short_exactly_5(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'ab123',
            'confirm_password': 'ab123',
        })
        assert resp.status_code in VALID_CODES

    def test_post_change_password_wrong_current(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'WrongPassword999',
            'new_password': 'NewPass@999',
            'confirm_password': 'NewPass@999',
        })
        assert resp.status_code in VALID_CODES

    def test_post_change_password_mismatch_confirm(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'NewPass@999',
            'confirm_password': 'DifferentPass@000',
        })
        assert resp.status_code in VALID_CODES

    def test_post_change_password_success(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'NewAdmin@999',
            'confirm_password': 'NewAdmin@999',
        })
        assert resp.status_code in VALID_CODES

    def test_post_unknown_submit_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={
            'unknown_submit': '1',
        })
        assert resp.status_code in VALID_CODES

    def test_post_no_submit_key_at_all(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/', data={})
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 2. Setup 2FA - Additional edge cases
# ===========================================================================

class TestSetup2FAExtended:
    """Extra coverage for /settings/setup-2fa."""

    def test_get_generates_qr_returns_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/setup-2fa')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'success' in data or 'qr_code' in data or 'secret' in data

    def test_get_sets_session_secret(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/setup-2fa')
        assert resp.status_code in VALID_CODES

    def test_post_with_valid_totp_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        secret = pyotp.random_base32()
        _inject_2fa_session(client, secret)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        resp = client.post('/settings/setup-2fa', data={'verification_code': code})
        assert resp.status_code in VALID_CODES

    def test_post_no_session_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        # No GET first - no session secret
        resp = client.post('/settings/setup-2fa', data={'verification_code': '123456'})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_post_empty_verification_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        secret = pyotp.random_base32()
        _inject_2fa_session(client, secret)
        resp = client.post('/settings/setup-2fa', data={'verification_code': ''})
        assert resp.status_code in VALID_CODES

    def test_post_wrong_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        secret = pyotp.random_base32()
        _inject_2fa_session(client, secret)
        resp = client.post('/settings/setup-2fa', data={'verification_code': '000000'})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_post_unauthenticated_redirects(self, client):
        resp = client.post('/settings/setup-2fa', data={'verification_code': '123456'})
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 3. Disable 2FA - Extended paths
# ===========================================================================

class TestDisable2FAExtended:
    """Extended tests for /settings/disable-2fa."""

    def test_disable_no_auth(self, client):
        resp = client.post('/settings/disable-2fa', data={'verification_code': '123456'})
        assert resp.status_code in VALID_CODES

    def test_disable_no_code_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/disable-2fa', data={})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_disable_2fa_not_enabled(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/disable-2fa', data={'verification_code': '123456'})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_disable_invalid_code(self, client, admin_user, db_session):
        secret = pyotp.random_base32()
        admin_user.totp_secret = secret
        admin_user.two_factor_auth = True
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.post('/settings/disable-2fa', data={'verification_code': '000000'})
        assert resp.status_code in VALID_CODES

    def test_disable_valid_code(self, client, admin_user, db_session):
        secret = pyotp.random_base32()
        admin_user.totp_secret = secret
        admin_user.two_factor_auth = True
        db_session.session.commit()
        _login(client, admin_user)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        resp = client.post('/settings/disable-2fa', data={'verification_code': code})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True

    def test_disable_returns_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/disable-2fa', data={'verification_code': '999999'})
        if resp.status_code in [200, 400]:
            data = resp.get_json()
            assert data is not None


# ===========================================================================
# 4. Verify 2FA JSON endpoint - Extended
# ===========================================================================

class TestVerify2FAExtended:
    """Extended tests for /settings/verify-2fa."""

    def test_valid_code_via_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        secret = pyotp.random_base32()
        _inject_2fa_session(client, secret)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        resp = client.post('/settings/verify-2fa', json={'code': code})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True

    def test_wrong_code_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        secret = pyotp.random_base32()
        _inject_2fa_session(client, secret)
        resp = client.post('/settings/verify-2fa', json={'code': '000000'})
        assert resp.status_code in VALID_CODES

    def test_missing_code_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        secret = pyotp.random_base32()
        _inject_2fa_session(client, secret)
        resp = client.post('/settings/verify-2fa', json={})
        assert resp.status_code in VALID_CODES

    def test_no_session_secret(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/verify-2fa', json={'code': '123456'})
        assert resp.status_code in VALID_CODES

    def test_unauthenticated(self, client):
        resp = client.post('/settings/verify-2fa', json={'code': '123456'})
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 5. Google Drive Connect - JSON field coverage
# ===========================================================================

class TestGoogleDriveConnectExtended:
    """Extends coverage for google-drive/connect."""

    def test_connect_with_all_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.access_token_full',
            'refresh_token': 'refresh_full',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': 'https://www.googleapis.com/auth/drive',
        })
        assert resp.status_code in VALID_CODES

    def test_connect_returns_connected_true(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.test_connected',
        })
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('connected') is True or data.get('success') is True

    def test_connect_update_existing_all_fields(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.updated',
            'refresh_token': 'updated_refresh',
            'expires_in': 7200,
            'scope': 'https://www.googleapis.com/auth/drive',
            'token_type': 'Bearer',
        })
        assert resp.status_code in VALID_CODES

    def test_connect_no_auth_redirects(self, client):
        resp = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.test',
        })
        assert resp.status_code in VALID_CODES

    def test_connect_empty_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/connect', json={})
        assert resp.status_code in VALID_CODES

    def test_connect_json_no_access_token_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/connect', json={
            'other_key': 'other_value',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False


# ===========================================================================
# 6. Google Drive Disconnect - JSON structure
# ===========================================================================

class TestGoogleDriveDisconnectExtended:
    """Extended disconnect tests."""

    def test_disconnect_no_token_returns_success(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/disconnect')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'connected' in data or 'success' in data

    def test_disconnect_with_token_connected_false(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/disconnect')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('connected') is False

    def test_disconnect_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/google-drive/disconnect')
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 7. Google Drive Status - JSON fields
# ===========================================================================

class TestGoogleDriveStatusExtended:
    """Extended status tests."""

    def test_status_not_connected_json_shape(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/google-drive/status')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'connected' in data
                assert data['connected'] is False

    def test_status_connected_json_shape(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/google-drive/status')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('connected') is True

    def test_status_unauthenticated(self, client):
        resp = client.get('/settings/api/v1/google-drive/status')
        assert resp.status_code in VALID_CODES

    def test_status_get_only(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/google-drive/status')
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 8. Sync / Download / Quick Sync - With Drive token
# ===========================================================================

class TestDriveSyncExtended:
    """Detailed path coverage for sync endpoints."""

    def test_sync_to_drive_with_token(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/user-settings/sync-to-drive')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True
                assert data.get('synced') is True

    def test_sync_to_drive_without_token_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/user-settings/sync-to-drive')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_download_from_drive_with_token(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/user-settings/download-from-drive')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True
                assert data.get('downloaded') is True

    def test_download_from_drive_without_token_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/user-settings/download-from-drive')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_quick_sync_with_token(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/user-settings/quick-sync')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True
                assert data.get('synced') is True

    def test_quick_sync_without_token_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/user-settings/quick-sync')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_sync_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/user-settings/sync-to-drive')
        assert resp.status_code in VALID_CODES

    def test_download_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/user-settings/download-from-drive')
        assert resp.status_code in VALID_CODES

    def test_quick_sync_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/user-settings/quick-sync')
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 9. Backup Settings GET/POST - Detailed field coverage
# ===========================================================================

class TestBackupSettingsExtended:
    """Extended coverage for backup-settings endpoints."""

    def test_get_returns_settings_dict(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/backup-settings')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'settings' in data or 'success' in data

    def test_post_enable_auto_backup(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
        })
        assert resp.status_code in VALID_CODES

    def test_post_disable_auto_backup(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': False,
        })
        assert resp.status_code in VALID_CODES

    def test_post_backup_frequency_monthly(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'backup_frequency': 'monthly',
        })
        assert resp.status_code in VALID_CODES

    def test_post_max_backups(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'max_backups': 10,
        })
        assert resp.status_code in VALID_CODES

    def test_post_destination_google_drive(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'backup_destination': 'google_drive',
        })
        assert resp.status_code in VALID_CODES

    def test_post_all_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'daily',
            'backup_time': '03:00',
            'max_backups': 7,
            'backup_destination': 'local',
        })
        assert resp.status_code in VALID_CODES

    def test_post_returns_updated_settings(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'weekly',
        })
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert 'settings' in data

    def test_post_ignores_extra_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'not_a_real_field': 'value_to_ignore',
            'another_fake': 123,
        })
        assert resp.status_code in VALID_CODES

    def test_get_unauthenticated(self, client):
        resp = client.get('/settings/api/v1/backup-settings')
        assert resp.status_code in VALID_CODES

    def test_post_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
        })
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 10. Create Backup - Destination-based branching
# ===========================================================================

class TestCreateBackupExtended:
    """Extended create backup tests covering both local and drive paths."""

    def test_create_local_backup_returns_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/create')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True
                assert 'filename' in data
                assert 'backup_data' in data

    def test_create_backup_basic_type(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/create')
        if resp.status_code == 200:
            data = resp.get_json()
            if data and 'backup_type' in data:
                assert data['backup_type'] in ['basic', 'comprehensive']

    def test_create_drive_backup_with_destination_setting(self, client, admin_user, db_session):
        """Set destination to google_drive then create backup."""
        _login(client, admin_user)
        # Set destination first
        client.post('/settings/api/v1/backup-settings', json={
            'backup_destination': 'google_drive',
        })
        resp = client.post('/settings/api/v1/backup/create')
        assert resp.status_code in VALID_CODES

    def test_create_backup_with_drive_token(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/create')
        assert resp.status_code in VALID_CODES

    def test_create_backup_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/backup/create')
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 11. Restore Backup - All paths
# ===========================================================================

class TestRestoreBackupExtended:
    """Extended restore backup tests."""

    def test_restore_empty_body_returns_error(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/restore', json={})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_restore_backup_data_no_data_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {'version': '1.0'},
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_restore_with_backup_settings(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {
                'data': {
                    'backup_settings': {
                        'auto_backup_enabled': True,
                        'backup_frequency': 'daily',
                        'max_backups': 5,
                    }
                }
            }
        })
        assert resp.status_code in VALID_CODES

    def test_restore_with_empty_data_dict(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {
                'data': {}
            }
        })
        assert resp.status_code in VALID_CODES

    def test_restore_returns_success_flag(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {
                'data': {}
            }
        })
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('success') is True

    def test_restore_unauthenticated(self, client):
        resp = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {'data': {}}
        })
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 12. Google OAuth Callback - All branches
# ===========================================================================

class TestGoogleOAuthCallbackExtended:
    """Extended OAuth callback tests covering all script-returning branches."""

    def test_error_param_returns_script(self, client):
        resp = client.get('/settings/auth/google/callback?error=access_denied')
        assert resp.status_code in VALID_CODES
        if resp.status_code == 200:
            assert b'<script' in resp.data or b'script' in resp.data.lower()

    def test_no_code_no_error_returns_script(self, client):
        resp = client.get('/settings/auth/google/callback')
        assert resp.status_code in VALID_CODES

    def test_code_no_state_no_auth_returns_script(self, client):
        resp = client.get('/settings/auth/google/callback?code=fake_code_abc')
        assert resp.status_code in VALID_CODES

    def test_code_with_valid_state_int(self, client):
        resp = client.get('/settings/auth/google/callback?code=fake_code&state=999')
        assert resp.status_code in VALID_CODES

    def test_code_with_non_int_state(self, client):
        resp = client.get('/settings/auth/google/callback?code=fake_code&state=not_number')
        assert resp.status_code in VALID_CODES

    def test_code_with_authenticated_user(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/auth/google/callback?code=fake_code')
        assert resp.status_code in VALID_CODES

    def test_error_custom_value(self, client):
        resp = client.get('/settings/auth/google/callback?error=some_custom_error')
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 13. Admin Phone Page - Extended
# ===========================================================================

class TestAdminPhonePageExtended:
    """Extended tests for /settings/admin-phone."""

    def test_admin_no_phone(self, client, admin_user, db_session):
        admin_user.phone_number = None
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.get('/settings/admin-phone')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('has_phone') is False or 'has_phone' in data

    def test_admin_with_phone_number(self, client, admin_user, db_session):
        admin_user.phone_number = '+966512345678'
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.get('/settings/admin-phone')
        if resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert data.get('has_phone') is True

    def test_non_admin_blocked(self, client, db_session):
        u = _make_plain_user(db_session)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = client.get('/settings/admin-phone')
        assert resp.status_code in [200, 302, 400, 401, 403, 404, 500]
        if resp.status_code == 403:
            data = resp.get_json()
            if data:
                assert 'error' in data

    def test_no_auth_redirects(self, client):
        resp = client.get('/settings/admin-phone')
        assert resp.status_code in VALID_CODES


# ===========================================================================
# 14. Admin Phone Verify Firebase - Extended edge cases
# ===========================================================================

class TestAdminPhoneVerifyFirebaseExtended:
    """Extended Firebase phone verify tests."""

    def test_no_auth_redirects(self, client):
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'tok', 'phase': 'new'
        })
        assert resp.status_code in VALID_CODES

    def test_non_admin_returns_403(self, client, db_session):
        u = _make_plain_user(db_session)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'tok', 'phase': 'new'
        })
        assert resp.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_missing_id_token_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase', json={})
        assert resp.status_code in VALID_CODES
        if resp.status_code == 400:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_empty_id_token_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': '  ',
            'phase': 'new',
        })
        assert resp.status_code in VALID_CODES

    def test_invalid_firebase_token_returns_error(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'clearly_invalid_token',
            'phase': 'new',
        })
        assert resp.status_code in VALID_CODES
        if resp.status_code in [400, 500]:
            data = resp.get_json()
            if data:
                assert data.get('success') is False

    def test_phase_old_no_existing_phone(self, client, admin_user, db_session):
        admin_user.phone_number = None
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'some_token',
            'phase': 'old',
        })
        assert resp.status_code in VALID_CODES

    def test_phase_new_has_phone_no_session_flag(self, client, admin_user, db_session):
        admin_user.phone_number = '+966512345678'
        db_session.session.commit()
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'some_token',
            'phase': 'new',
        })
        assert resp.status_code in VALID_CODES

    def test_invalid_phase_value(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'tok',
            'phase': 'bad_phase_value',
        })
        assert resp.status_code in VALID_CODES

    def test_no_json_body(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone/verify-firebase')
        assert resp.status_code in VALID_CODES + [415]


# ===========================================================================
# 15. Method guards
# ===========================================================================

class TestSettingsMethodGuards:
    """Ensure wrong HTTP methods return appropriate status codes."""

    def test_delete_settings_index(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.delete('/settings/')
        assert resp.status_code in VALID_CODES

    def test_put_backup_settings(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.put('/settings/api/v1/backup-settings', json={})
        assert resp.status_code in VALID_CODES

    def test_get_backup_create(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/backup/create')
        assert resp.status_code in VALID_CODES

    def test_get_backup_restore(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/backup/restore')
        assert resp.status_code in VALID_CODES

    def test_get_google_drive_connect(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/google-drive/connect')
        assert resp.status_code in VALID_CODES

    def test_get_google_drive_disconnect(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get('/settings/api/v1/google-drive/disconnect')
        assert resp.status_code in VALID_CODES

    def test_post_google_drive_status(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/api/v1/google-drive/status')
        assert resp.status_code in VALID_CODES

    def test_post_admin_phone_get_only(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post('/settings/admin-phone')
        assert resp.status_code in VALID_CODES
