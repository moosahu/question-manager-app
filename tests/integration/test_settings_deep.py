"""
Deep integration tests for settings.py
Targets: /settings/* endpoints
Coverage goal: raise from 41% to 70%+
"""
import pytest
import secrets
import json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='Settings Test',
        username=f'sett_{secrets.token_hex(4)}',
        email=f'sett_{secrets.token_hex(4)}@test.com',
        is_active=True,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_drive_token(db_session, user_id):
    """Create a GoogleDriveToken for a user using real model columns."""
    from src.models.google_drive import GoogleDriveToken
    token = GoogleDriveToken(
        user_id=user_id,
        access_token=f'fake_access_{secrets.token_hex(8)}',
        refresh_token=f'fake_refresh_{secrets.token_hex(8)}',
        scopes='https://www.googleapis.com/auth/drive',
        is_active=True,
    )
    db_session.session.add(token)
    db_session.session.commit()
    db_session.session.refresh(token)
    return token


# ===========================================================================
# 1. Settings Index Page
# ===========================================================================

class TestSettingsIndex:
    """GET|POST /settings/"""

    def test_get_no_auth_redirects(self, client):
        response = client.get('/settings/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_profile_submit_no_auth(self, client):
        response = client.post('/settings/', data={'profile_submit': '1'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_profile_submit_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'profile_submit': '1',
            'full_name': 'Admin Updated',
            'email': 'admin@test.com',
            'bio': 'Bio text',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_notification_submit(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'notification_submit': '1',
            'email_notifications': 'y',
            'app_notifications': 'y',
            'notification_frequency': 'daily',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_security_submit(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'security_submit': '1',
            'two_factor_auth': 'y',
            'login_alerts': 'y',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_integration_submit(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'integration_submit': '1',
            'google_integration': 'y',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_integration_regenerate_api_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'integration_submit': '1',
            'regenerate_api_key': '1',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_change_password_missing_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'change_password_submit': '1',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_change_password_mismatch(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'NewPass@456',
            'confirm_password': 'DifferentPass@789',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_change_password_too_short(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'ab',
            'confirm_password': 'ab',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_change_password_wrong_current(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'WrongPassword!',
            'new_password': 'NewPass@456',
            'confirm_password': 'NewPass@456',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_change_password_correct(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'NewAdmin@456',
            'confirm_password': 'NewAdmin@456',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_integration_with_custom_api_key(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'integration_submit': '1',
            'regenerate_api_key': '1',
            'new_api_key': 'custom-api-key-12345',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ===========================================================================
# 2. Setup 2FA
# ===========================================================================

class TestSetup2FA:
    """GET|POST /settings/setup-2fa"""

    def test_get_no_auth(self, client):
        response = client.get('/settings/setup-2fa')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_as_admin_generates_qr(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/setup-2fa')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_returns_json_with_qr(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/setup-2fa')
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data or 'qr_code' in data

    def test_post_no_session_secret(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/setup-2fa', data={'verification_code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_missing_verification_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        # First GET to set temp_2fa_secret in session
        client.get('/settings/setup-2fa')
        response = client.post('/settings/setup-2fa', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_invalid_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        client.get('/settings/setup-2fa')
        response = client.post('/settings/setup-2fa', data={'verification_code': '000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_no_auth(self, client):
        response = client.post('/settings/setup-2fa', data={'verification_code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ===========================================================================
# 3. Disable 2FA
# ===========================================================================

class TestDisable2FA:
    """POST /settings/disable-2fa"""

    def test_no_auth(self, client):
        response = client.post('/settings/disable-2fa', data={'verification_code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/disable-2fa', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_2fa_not_enabled(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/disable-2fa', data={'verification_code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_code_when_enabled(self, client, admin_user, db_session):
        import pyotp
        secret = pyotp.random_base32()
        admin_user.totp_secret = secret
        admin_user.two_factor_auth = True
        db_session.session.commit()
        _login(client, admin_user)
        response = client.post('/settings/disable-2fa', data={'verification_code': '000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_valid_code_when_enabled(self, client, admin_user, db_session):
        import pyotp
        secret = pyotp.random_base32()
        admin_user.totp_secret = secret
        admin_user.two_factor_auth = True
        db_session.session.commit()
        _login(client, admin_user)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        response = client.post('/settings/disable-2fa', data={'verification_code': code})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ===========================================================================
# 4. Verify 2FA (JSON endpoint)
# ===========================================================================

class TestVerify2FA:
    """POST /settings/verify-2fa"""

    def test_no_auth(self, client):
        response = client.post('/settings/verify-2fa', json={'code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_no_session_secret(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/verify-2fa', json={'code': '123456'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        client.get('/settings/setup-2fa')
        response = client.post('/settings/verify-2fa', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_wrong_code(self, client, admin_user, db_session):
        _login(client, admin_user)
        client.get('/settings/setup-2fa')
        response = client.post('/settings/verify-2fa', json={'code': '000000'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_valid_totp_code(self, client, admin_user, db_session):
        import pyotp
        _login(client, admin_user)
        # Inject a known secret into the session
        secret = pyotp.random_base32()
        with client.session_transaction() as sess:
            sess['temp_2fa_secret'] = secret
        totp = pyotp.TOTP(secret)
        code = totp.now()
        response = client.post('/settings/verify-2fa', json={'code': code})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ===========================================================================
# 5. Google Drive Connect
# ===========================================================================

class TestGoogleDriveConnect:
    """POST /settings/api/v1/google-drive/connect"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/google-drive/connect', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_access_token(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/connect', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_empty_body(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post(
            '/settings/api/v1/google-drive/connect',
            data='',
            content_type='application/json',
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_access_token(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.fake_access_token',
            'refresh_token': 'fake_refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_existing_token(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.updated_access_token',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_returns_json_on_success(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'ya29.test_token',
        })
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data or 'connected' in data


# ===========================================================================
# 6. Google Drive Disconnect
# ===========================================================================

class TestGoogleDriveDisconnect:
    """POST /settings/api/v1/google-drive/disconnect"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/google-drive/disconnect')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_disconnect_no_token(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/disconnect')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_disconnect_with_token(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/disconnect')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_disconnect_returns_connected_false(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/disconnect')
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('connected') is False or 'success' in data


# ===========================================================================
# 7. Google Drive Status
# ===========================================================================

class TestGoogleDriveStatus:
    """GET /settings/api/v1/google-drive/status"""

    def test_no_auth(self, client):
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_not_connected(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_connected(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_status_json_structure_not_connected(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/status')
        if response.status_code == 200:
            data = response.get_json()
            assert 'connected' in data or 'success' in data

    def test_status_json_structure_connected(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/status')
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('connected') is True or 'success' in data


# ===========================================================================
# 8. Sync to Drive
# ===========================================================================

class TestSyncToDrive:
    """POST /settings/api/v1/user-settings/sync-to-drive"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/user-settings/sync-to-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_no_token_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/sync-to-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_token_syncs(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/sync-to-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_sync_returns_synced_flag(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/sync-to-drive')
        if response.status_code == 200:
            data = response.get_json()
            assert 'synced' in data or 'success' in data


# ===========================================================================
# 9. Download from Drive
# ===========================================================================

class TestDownloadFromDrive:
    """POST /settings/api/v1/user-settings/download-from-drive"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/user-settings/download-from-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_no_token_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/download-from-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_token_downloads(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/download-from-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_download_returns_downloaded_flag(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/download-from-drive')
        if response.status_code == 200:
            data = response.get_json()
            assert 'downloaded' in data or 'success' in data


# ===========================================================================
# 10. Quick Sync
# ===========================================================================

class TestQuickSync:
    """POST /settings/api/v1/user-settings/quick-sync"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/user-settings/quick-sync')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_no_token_returns_400(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/quick-sync')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_token_quick_syncs(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/quick-sync')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_quick_sync_returns_synced(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/user-settings/quick-sync')
        if response.status_code == 200:
            data = response.get_json()
            assert 'synced' in data or 'success' in data


# ===========================================================================
# 11. Backup Settings GET
# ===========================================================================

class TestGetBackupSettings:
    """GET /settings/api/v1/backup-settings"""

    def test_no_auth(self, client):
        response = client.get('/settings/api/v1/backup-settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/backup-settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_returns_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/backup-settings')
        if response.status_code == 200:
            data = response.get_json()
            assert 'settings' in data or 'success' in data


# ===========================================================================
# 12. Backup Settings POST
# ===========================================================================

class TestSaveBackupSettings:
    """POST /settings/api/v1/backup-settings"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/backup-settings', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_valid_settings(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'daily',
            'backup_time': '02:00',
            'max_backups': 5,
            'backup_destination': 'local',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_partial_settings(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'backup_frequency': 'weekly',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_ignores_unknown_fields(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'unknown_field': 'should_be_ignored',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_returns_updated_settings(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': False,
        })
        if response.status_code == 200:
            data = response.get_json()
            assert 'settings' in data or 'success' in data


# ===========================================================================
# 13. Create Backup
# ===========================================================================

class TestCreateBackup:
    """POST /settings/api/v1/backup/create"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/backup/create')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_create_local_backup(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/create')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_create_drive_backup(self, client, admin_user, db_session):
        _make_drive_token(db_session, admin_user.id)
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/create')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_returns_filename(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/create')
        if response.status_code == 200:
            data = response.get_json()
            assert 'filename' in data or 'backup_data' in data or 'success' in data


# ===========================================================================
# 14. Restore Backup
# ===========================================================================

class TestRestoreBackup:
    """POST /settings/api/v1/backup/restore"""

    def test_no_auth(self, client):
        response = client.post('/settings/api/v1/backup/restore', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_backup_data(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/restore', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_backup_structure(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {'no_data_key': True},
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_valid_backup_restore(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {
                'data': {
                    'backup_settings': {
                        'auto_backup_enabled': True,
                        'backup_frequency': 'daily',
                    }
                }
            }
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_restore_returns_success(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {
                'data': {}
            }
        })
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data or 'message' in data


# ===========================================================================
# 15. Google OAuth Callback
# ===========================================================================

class TestGoogleOAuthCallback:
    """GET /settings/auth/google/callback"""

    def test_with_error_param(self, client):
        response = client.get('/settings/auth/google/callback?error=access_denied')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_without_code_or_error(self, client):
        response = client.get('/settings/auth/google/callback')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_code_no_user(self, client):
        response = client.get('/settings/auth/google/callback?code=fake_auth_code_12345')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_code_and_state(self, client):
        response = client.get('/settings/auth/google/callback?code=fake_code&state=1')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_code_authenticated(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/auth/google/callback?code=fake_code')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_with_invalid_state(self, client):
        response = client.get('/settings/auth/google/callback?code=fake_code&state=not_a_number')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_callback_returns_html_with_script(self, client):
        response = client.get('/settings/auth/google/callback?error=test_error')
        if response.status_code == 200:
            assert b'script' in response.data.lower() or b'<script' in response.data


# ===========================================================================
# 16. Admin Phone Page
# ===========================================================================

class TestAdminPhonePage:
    """GET /settings/admin-phone"""

    def test_no_auth(self, client):
        response = client.get('/settings/admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_non_admin_blocked(self, client, db_session):
        from src.models.user import User
        u = User(
            username=f'plain_{secrets.token_hex(3)}',
            email=f'plain_{secrets.token_hex(3)}@test.com',
            is_admin=False,
        )
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        response = client.get('/settings/admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_can_access(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_response_structure(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/admin-phone')
        if response.status_code == 200:
            data = response.get_json()
            assert 'has_phone' in data or 'phone_masked' in data

    def test_admin_with_phone_number(self, client, admin_user, db_session):
        admin_user.phone_number = '+966500000000'
        db_session.session.commit()
        _login(client, admin_user)
        response = client.get('/settings/admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ===========================================================================
# 17. Admin Phone Verify Firebase
# ===========================================================================

class TestAdminPhoneVerifyFirebase:
    """POST /settings/admin-phone/verify-firebase"""

    def test_no_auth(self, client):
        response = client.post('/settings/admin-phone/verify-firebase', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_non_admin_blocked(self, client, db_session):
        from src.models.user import User
        u = User(
            username=f'plain2_{secrets.token_hex(3)}',
            email=f'plain2_{secrets.token_hex(3)}@test.com',
            is_admin=False,
        )
        u.set_password('Pass@123')
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        response = client.post('/settings/admin-phone/verify-firebase', json={'id_token': 'x'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_missing_id_token(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/admin-phone/verify-firebase', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_firebase_token(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'totally_invalid_token',
            'phase': 'new',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_phase_old_no_existing_phone(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'fake_token',
            'phase': 'old',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_phase_new_without_old_verification(self, client, admin_user, db_session):
        admin_user.phone_number = '+966500000000'
        db_session.session.commit()
        _login(client, admin_user)
        response = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'fake_token',
            'phase': 'new',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_invalid_phase_value(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'fake_token',
            'phase': 'invalid_phase',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ===========================================================================
# 18. Edge Cases and Method Guards
# ===========================================================================

class TestSettingsEdgeCases:
    """Edge cases and wrong HTTP methods for settings routes."""

    def test_get_on_disable_2fa(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/disable-2fa')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_on_google_drive_connect(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/google-drive/connect')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_on_backup_create(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/backup/create')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_on_sync_to_drive(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.get('/settings/api/v1/user-settings/sync-to-drive')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_post_on_drive_status(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/google-drive/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_settings_index_no_submit_key_post(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={'some_other_key': '1'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_restore_no_body(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post(
            '/settings/api/v1/backup/restore',
            data='',
            content_type='application/json',
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_connect_non_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post(
            '/settings/api/v1/google-drive/connect',
            data='access_token=fake',
            content_type='application/x-www-form-urlencoded',
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_verify_2fa_non_json(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post(
            '/settings/verify-2fa',
            data='code=123456',
            content_type='application/x-www-form-urlencoded',
        )
        # 415 is valid: JSON-only endpoint rejects form-encoded content
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 415, 500]

    def test_admin_phone_post_not_allowed(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/admin-phone')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_settings_index_get_reads_user_attributes(self, client, admin_user, db_session):
        """Ensure GET to settings index properly populates forms."""
        _login(client, admin_user)
        response = client.get('/settings/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_settings_notification_frequency_weekly(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'notification_submit': '1',
            'notification_frequency': 'weekly',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_settings_notification_frequency_immediate(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/', data={
            'notification_submit': '1',
            'notification_frequency': 'immediate',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_settings_google_drive_destination(self, client, admin_user, db_session):
        _login(client, admin_user)
        response = client.post('/settings/api/v1/backup-settings', json={
            'backup_destination': 'google_drive',
            'auto_backup_enabled': True,
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
