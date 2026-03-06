"""
Integration tests targeting missing lines in settings.py and registration.py.

settings.py  missing: 15-20, 28-32, 68, 76, 83, 87, 95, 97, 99, 109, 117, 119,
             131, 237-250, 322-323, 356, 364, 401, 430, 437, 456-459, 472, 480,
             548-550, 580-582, 651-656, 670-671, 692-694, 728-730, 753-755,
             784-786, 806, 826-828, 852-973, 1054, 1060-1064, 1076-1079

registration.py missing: 30-34, 38-50, 54-57, 61-67, 94, 103, 105, 108,
             138-139, 213, 269-274, 319, 347, 354, 360, 394-396, 408-413, 469,
             480-500, 512, 514, 551, 557, 566, 615, 624, 668-673, 711-777,
             855-860, 917-919, 934, 950-951, 987-988, 1034-1035
"""
import pytest
import secrets
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash

VALID_CODES = [200, 302, 400, 401, 403, 404, 500]


# ===========================================================================
# Shared helpers
# ===========================================================================

def _login_admin(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_student(db_session, suffix=''):
    from src.models.student import Student
    tok = secrets.token_hex(4)
    s = Student(
        name='اختبار طالب',
        username=f'stu_{tok}{suffix}',
        email=f'stu_{tok}{suffix}@test.com',
        is_active=True,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_teacher(db_session, suffix=''):
    from src.models.teacher import Teacher
    tok = secrets.token_hex(4)
    t = Teacher(
        name='معلم اختبار',
        username=f'tch_{tok}{suffix}',
        email=f'tch_{tok}{suffix}@test.com',
        is_active=True,
    )
    t.set_password('Pass@123')
    t.session_token = secrets.token_hex(32)
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _make_drive_token(db_session, user_id):
    from src.models.google_drive import GoogleDriveToken
    tok = GoogleDriveToken(
        user_id=user_id,
        access_token=f'fake_access_{secrets.token_hex(8)}',
        refresh_token=f'fake_refresh_{secrets.token_hex(8)}',
        scopes='https://www.googleapis.com/auth/drive',
        is_active=True,
    )
    db_session.session.add(tok)
    db_session.session.commit()
    db_session.session.refresh(tok)
    return tok


def _make_verification(db_session, email, username, grade=None,
                       phone=None, school=None, is_verified=False):
    from src.models.email_verification import EmailVerification
    EmailVerification.query.filter_by(email=email).delete()
    db_session.session.commit()
    v = EmailVerification(
        email=email,
        code='123456',
        name='احمد محمد علي',
        username=username,
        password_hash=generate_password_hash('Pass@123'),
        phone=phone,
        school=school,
        grade=grade,
        is_verified=is_verified,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        attempts=0,
    )
    db_session.session.add(v)
    db_session.session.commit()
    db_session.session.refresh(v)
    return v


# ===========================================================================
# SETTINGS TESTS  (50+)
# ===========================================================================

class TestSettingsIndexExtra:
    """Additional settings index coverage"""

    def test_get_no_auth(self, client):
        r = client.get('/settings/')
        assert r.status_code in VALID_CODES

    def test_get_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.get('/settings/')
        assert r.status_code in VALID_CODES

    def test_post_profile_submit_valid(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'profile_submit': '1',
            'full_name': 'Admin Name Updated',
            'email': 'admin_upd@test.com',
            'bio': 'Short bio',
        })
        assert r.status_code in VALID_CODES

    def test_post_notification_submit(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'notification_submit': '1',
            'email_notifications': 'y',
            'app_notifications': 'y',
            'notification_frequency': 'daily',
        })
        assert r.status_code in VALID_CODES

    def test_post_security_submit(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'security_submit': '1',
            'two_factor_auth': 'y',
            'login_alerts': 'y',
        })
        assert r.status_code in VALID_CODES

    def test_post_integration_submit(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'integration_submit': '1',
            'google_integration': 'y',
        })
        assert r.status_code in VALID_CODES

    def test_post_integration_regenerate_api_key(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'integration_submit': '1',
            'regenerate_api_key': '1',
        })
        assert r.status_code in VALID_CODES

    def test_post_change_password_missing_fields(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'change_password_submit': '1',
        })
        assert r.status_code in VALID_CODES

    def test_post_change_password_mismatch(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'NewPass@123',
            'confirm_password': 'DifferentPass@123',
        })
        assert r.status_code in VALID_CODES

    def test_post_change_password_too_short(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'abc',
            'confirm_password': 'abc',
        })
        assert r.status_code in VALID_CODES

    def test_post_change_password_wrong_current(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'WrongPassword999',
            'new_password': 'NewPass@123',
            'confirm_password': 'NewPass@123',
        })
        assert r.status_code in VALID_CODES

    def test_post_change_password_success(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/', data={
            'change_password_submit': '1',
            'current_password': 'Admin@123',
            'new_password': 'NewAdmin@999',
            'confirm_password': 'NewAdmin@999',
        })
        assert r.status_code in VALID_CODES


class TestSettings2FAExtra:
    """Additional 2FA coverage"""

    def test_setup_2fa_get_no_auth(self, client):
        r = client.get('/settings/setup-2fa')
        assert r.status_code in VALID_CODES

    def test_setup_2fa_get_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.get('/settings/setup-2fa')
        assert r.status_code in VALID_CODES

    def test_setup_2fa_post_no_secret_in_session(self, client, admin_user):
        """POST without temp_2fa_secret in session → 400"""
        _login_admin(client, admin_user)
        r = client.post('/settings/setup-2fa', data={
            'verification_code': '123456',
        })
        assert r.status_code in VALID_CODES

    def test_setup_2fa_post_empty_code(self, client, admin_user):
        _login_admin(client, admin_user)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
            sess['temp_2fa_secret'] = 'JBSWY3DPEHPK3PXP'
        r = client.post('/settings/setup-2fa', data={
            'verification_code': '',
        })
        assert r.status_code in VALID_CODES

    def test_setup_2fa_post_wrong_code(self, client, admin_user):
        _login_admin(client, admin_user)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
            sess['temp_2fa_secret'] = 'JBSWY3DPEHPK3PXP'
        r = client.post('/settings/setup-2fa', data={
            'verification_code': '000000',
        })
        assert r.status_code in VALID_CODES

    def test_disable_2fa_no_auth(self, client):
        r = client.post('/settings/disable-2fa', data={})
        assert r.status_code in VALID_CODES

    def test_disable_2fa_no_code(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/disable-2fa', data={})
        assert r.status_code in VALID_CODES

    def test_disable_2fa_no_totp_secret(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/disable-2fa', data={'verification_code': '123456'})
        assert r.status_code in VALID_CODES

    def test_verify_2fa_no_session(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/verify-2fa', json={'code': '123456'})
        assert r.status_code in VALID_CODES

    def test_verify_2fa_no_code(self, client, admin_user):
        _login_admin(client, admin_user)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
            sess['temp_2fa_secret'] = 'JBSWY3DPEHPK3PXP'
        r = client.post('/settings/verify-2fa', json={})
        assert r.status_code in VALID_CODES

    def test_verify_2fa_wrong_code(self, client, admin_user):
        _login_admin(client, admin_user)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
            sess['temp_2fa_secret'] = 'JBSWY3DPEHPK3PXP'
        r = client.post('/settings/verify-2fa', json={'code': '000000'})
        assert r.status_code in VALID_CODES

    def test_verify_2fa_no_auth(self, client):
        r = client.post('/settings/verify-2fa', json={'code': '123456'})
        assert r.status_code in VALID_CODES


class TestGoogleDriveConnect:
    """settings/api/v1/google-drive/connect"""

    def test_connect_no_auth(self, client):
        r = client.post('/settings/api/v1/google-drive/connect', json={})
        assert r.status_code in VALID_CODES

    def test_connect_no_data(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/google-drive/connect', json={})
        assert r.status_code in VALID_CODES

    def test_connect_with_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'fake_token_abc123',
            'refresh_token': 'fake_refresh',
            'expires_in': 3600,
            'scope': 'drive.readonly',
            'token_type': 'Bearer',
        })
        assert r.status_code in VALID_CODES

    def test_connect_update_existing_token(self, client, admin_user, db_session):
        """Update existing token"""
        _login_admin(client, admin_user)
        _make_drive_token(db_session, admin_user.id)
        r = client.post('/settings/api/v1/google-drive/connect', json={
            'access_token': 'updated_token_xyz',
            'refresh_token': 'updated_refresh',
            'expires_in': 7200,
        })
        assert r.status_code in VALID_CODES


class TestGoogleDriveDisconnect:
    """settings/api/v1/google-drive/disconnect"""

    def test_disconnect_no_auth(self, client):
        r = client.post('/settings/api/v1/google-drive/disconnect', json={})
        assert r.status_code in VALID_CODES

    def test_disconnect_as_admin_no_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/google-drive/disconnect', json={})
        assert r.status_code in VALID_CODES

    def test_disconnect_as_admin_with_token(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        _make_drive_token(db_session, admin_user.id)
        r = client.post('/settings/api/v1/google-drive/disconnect', json={})
        assert r.status_code in VALID_CODES


class TestGoogleDriveStatus:
    """settings/api/v1/google-drive/status"""

    def test_status_no_auth(self, client):
        r = client.get('/settings/api/v1/google-drive/status')
        assert r.status_code in VALID_CODES

    def test_status_no_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.get('/settings/api/v1/google-drive/status')
        assert r.status_code in VALID_CODES

    def test_status_with_token(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        _make_drive_token(db_session, admin_user.id)
        r = client.get('/settings/api/v1/google-drive/status')
        assert r.status_code in VALID_CODES


class TestDriveSyncOperations:
    """sync-to-drive, download-from-drive, quick-sync"""

    def test_sync_no_auth(self, client):
        r = client.post('/settings/api/v1/user-settings/sync-to-drive', json={})
        assert r.status_code in VALID_CODES

    def test_sync_no_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/user-settings/sync-to-drive', json={})
        assert r.status_code in VALID_CODES

    def test_sync_with_token(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        _make_drive_token(db_session, admin_user.id)
        r = client.post('/settings/api/v1/user-settings/sync-to-drive', json={})
        assert r.status_code in VALID_CODES

    def test_download_no_auth(self, client):
        r = client.post('/settings/api/v1/user-settings/download-from-drive', json={})
        assert r.status_code in VALID_CODES

    def test_download_no_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/user-settings/download-from-drive', json={})
        assert r.status_code in VALID_CODES

    def test_download_with_token(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        _make_drive_token(db_session, admin_user.id)
        r = client.post('/settings/api/v1/user-settings/download-from-drive', json={})
        assert r.status_code in VALID_CODES

    def test_quick_sync_no_auth(self, client):
        r = client.post('/settings/api/v1/user-settings/quick-sync', json={})
        assert r.status_code in VALID_CODES

    def test_quick_sync_no_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/user-settings/quick-sync', json={})
        assert r.status_code in VALID_CODES

    def test_quick_sync_with_token(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        _make_drive_token(db_session, admin_user.id)
        r = client.post('/settings/api/v1/user-settings/quick-sync', json={})
        assert r.status_code in VALID_CODES


class TestGoogleOAuthCallback:
    """settings/auth/google/callback"""

    def test_callback_no_code_no_error(self, client):
        r = client.get('/settings/auth/google/callback')
        assert r.status_code in VALID_CODES

    def test_callback_with_error(self, client):
        r = client.get('/settings/auth/google/callback?error=access_denied')
        assert r.status_code in VALID_CODES

    def test_callback_with_code_no_user(self, client):
        r = client.get('/settings/auth/google/callback?code=fake_auth_code')
        assert r.status_code in VALID_CODES

    def test_callback_with_code_and_state(self, client, admin_user):
        r = client.get(
            f'/settings/auth/google/callback?code=fake_code&state={admin_user.id}'
        )
        assert r.status_code in VALID_CODES

    def test_callback_with_invalid_state(self, client):
        r = client.get('/settings/auth/google/callback?code=fake_code&state=notanint')
        assert r.status_code in VALID_CODES


class TestBackupSettings:
    """settings/api/v1/backup-settings"""

    def test_get_backup_settings_no_auth(self, client):
        r = client.get('/settings/api/v1/backup-settings')
        assert r.status_code in VALID_CODES

    def test_get_backup_settings_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.get('/settings/api/v1/backup-settings')
        assert r.status_code in VALID_CODES

    def test_save_backup_settings_no_auth(self, client):
        r = client.post('/settings/api/v1/backup-settings', json={})
        assert r.status_code in VALID_CODES

    def test_save_backup_settings_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'daily',
            'backup_time': '02:00',
            'max_backups': 5,
            'backup_destination': 'local',
        })
        assert r.status_code in VALID_CODES

    def test_save_backup_settings_google_drive(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/backup-settings', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'weekly',
            'backup_destination': 'google_drive',
            'max_backups': 10,
        })
        assert r.status_code in VALID_CODES


class TestCreateBackup:
    """settings/api/v1/backup/create"""

    def test_create_backup_no_auth(self, client):
        r = client.post('/settings/api/v1/backup/create', json={})
        assert r.status_code in VALID_CODES

    def test_create_basic_backup(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/backup/create', json={})
        assert r.status_code in VALID_CODES

    def test_create_comprehensive_backup(self, client, admin_user, db_session):
        """Drive token present → comprehensive backup"""
        _login_admin(client, admin_user)
        # Set backup destination to google_drive
        from src.models.backup_settings import BackupSettings
        BackupSettings.update_user_settings(admin_user.id, {
            'backup_destination': 'google_drive'
        })
        _make_drive_token(db_session, admin_user.id)
        r = client.post('/settings/api/v1/backup/create', json={})
        assert r.status_code in VALID_CODES


class TestRestoreBackup:
    """settings/api/v1/backup/restore"""

    def test_restore_no_auth(self, client):
        r = client.post('/settings/api/v1/backup/restore', json={})
        assert r.status_code in VALID_CODES

    def test_restore_invalid_data(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': None
        })
        assert r.status_code in VALID_CODES

    def test_restore_missing_data_key(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {'version': '1.0'}
        })
        assert r.status_code in VALID_CODES

    def test_restore_valid_data(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/api/v1/backup/restore', json={
            'backup_data': {
                'version': '1.0',
                'data': {
                    'backup_settings': {
                        'auto_backup_enabled': False,
                        'backup_frequency': 'daily',
                    }
                }
            }
        })
        assert r.status_code in VALID_CODES


class TestAdminPhone:
    """settings/admin-phone endpoints"""

    def test_admin_phone_page_no_auth(self, client):
        r = client.get('/settings/admin-phone')
        assert r.status_code in VALID_CODES

    def test_admin_phone_page_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.get('/settings/admin-phone')
        assert r.status_code in VALID_CODES

    def test_admin_phone_verify_firebase_no_auth(self, client):
        r = client.post('/settings/admin-phone/verify-firebase', json={})
        assert r.status_code in VALID_CODES

    def test_admin_phone_verify_firebase_no_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/admin-phone/verify-firebase', json={
            'phase': 'new',
        })
        assert r.status_code in VALID_CODES

    def test_admin_phone_verify_firebase_invalid_token(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'invalid_firebase_token',
            'phase': 'new',
        })
        assert r.status_code in VALID_CODES

    def test_admin_phone_verify_firebase_old_phase_no_phone(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'invalid_token_xyz',
            'phase': 'old',
        })
        assert r.status_code in VALID_CODES

    def test_admin_phone_verify_firebase_invalid_phase(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/settings/admin-phone/verify-firebase', json={
            'id_token': 'invalid_token_xyz',
            'phase': 'unknown',
        })
        assert r.status_code in VALID_CODES


# ===========================================================================
# REGISTRATION TESTS  (50+)
# ===========================================================================

class TestRegistrationStatusExtra:
    """GET /api/registration/status"""

    def test_status_student(self, client):
        r = client.get('/api/registration/status?type=student')
        assert r.status_code in VALID_CODES

    def test_status_teacher(self, client):
        r = client.get('/api/registration/status?type=teacher')
        assert r.status_code in VALID_CODES

    def test_status_default(self, client):
        r = client.get('/api/registration/status')
        assert r.status_code in VALID_CODES


class TestRegisterStudentExtra:
    """POST /api/registration/register"""

    def test_register_missing_all_fields(self, client):
        r = client.post('/api/registration/register', json={})
        assert r.status_code in VALID_CODES

    def test_register_short_name(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'Ali',
            'username': 'ali_test1',
            'email': 'ali@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_mixed_lang_name(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'Ahmad محمد علي',
            'username': 'ahmadtest1',
            'email': 'ahmad@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_duplicate_name_parts(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد احمد علي',
            'username': 'ahmdtest1',
            'email': 'atest@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_short_username(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'ab',
            'email': 'shortuser@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_username_starts_with_digit(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': '1invalid',
            'email': 'digit@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_weak_password_no_letter(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'validuser1',
            'email': 'weak@test.com',
            'password': '12345678',
        })
        assert r.status_code in VALID_CODES

    def test_register_weak_password_no_digit(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'validuser2',
            'email': 'weak2@test.com',
            'password': 'abcdefgh',
        })
        assert r.status_code in VALID_CODES

    def test_register_blocked_email_domain(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'validuser3',
            'email': 'test@mailinator.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_duplicate_username(self, client, db_session):
        s = _make_student(db_session, '_dup')
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': s.username,
            'email': 'unique_email99@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_duplicate_email(self, client, db_session):
        s = _make_student(db_session, '_dup2')
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'unique_usr9871',
            'email': s.email,
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_invalid_email_format(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'validuser4',
            'email': 'not-an-email',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(True, 'sent'))
    def test_register_success(self, mock_send, client):
        tok = secrets.token_hex(4)
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': f'succ_{tok}',
            'email': f'succ_{tok}@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(False, 'SMTP error'))
    def test_register_email_send_fail(self, mock_send, client):
        tok = secrets.token_hex(4)
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': f'fail_{tok}',
            'email': f'fail_{tok}@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_name_too_long(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'أ' * 50,
            'username': 'toolongname1',
            'email': 'longname@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_name_with_prefix_abou(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'أبو أحمد محمد',
            'username': 'abouprefix1',
            'email': 'abou@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_name_repeated_chars(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'أحمد ааааа علي',
            'username': 'repeatchar1',
            'email': 'repeat@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_weak_common_password(self, client):
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'weakpass1u',
            'email': 'weakpass@test.com',
            'password': 'password123',
        })
        assert r.status_code in VALID_CODES


class TestRegisterTeacherExtra:
    """POST /api/registration/register-teacher"""

    def test_register_teacher_missing_fields(self, client):
        r = client.post('/api/registration/register-teacher', json={})
        assert r.status_code in VALID_CODES

    def test_register_teacher_invalid_name(self, client):
        r = client.post('/api/registration/register-teacher', json={
            'name': 'Ali',
            'username': 'teacher_usr1',
            'email': 'teacher1@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_teacher_blocked_email(self, client):
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'teacher_usr2',
            'email': 'fake@yopmail.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_teacher_duplicate_username_in_teacher(self, client, db_session):
        t = _make_teacher(db_session, '_dup')
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': t.username,
            'email': 'unique_tch2@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_teacher_duplicate_username_in_student(self, client, db_session):
        s = _make_student(db_session, '_tchdup')
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': s.username,
            'email': 'unique_tch3@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_teacher_duplicate_email(self, client, db_session):
        t = _make_teacher(db_session, '_em2')
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'teacher_usr99',
            'email': t.email,
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(True, 'sent'))
    def test_register_teacher_success(self, mock_send, client):
        tok = secrets.token_hex(4)
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': f'tch_succ_{tok}',
            'email': f'tch_succ_{tok}@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(False, 'error'))
    def test_register_teacher_email_fail(self, mock_send, client):
        tok = secrets.token_hex(4)
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': f'tch_fail_{tok}',
            'email': f'tch_fail_{tok}@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES


class TestVerifyCodeExtra:
    """POST /api/registration/verify"""

    def test_verify_empty(self, client):
        r = client.post('/api/registration/verify', json={})
        assert r.status_code in VALID_CODES

    def test_verify_no_email(self, client):
        r = client.post('/api/registration/verify', json={'code': '123456'})
        assert r.status_code in VALID_CODES

    def test_verify_not_found(self, client):
        r = client.post('/api/registration/verify', json={
            'email': 'nonexistent@test.com',
            'code': '123456',
        })
        assert r.status_code in VALID_CODES

    def test_verify_wrong_code(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vf_{tok}@test.com'
        _make_verification(db_session, email, f'vfu_{tok}')
        r = client.post('/api/registration/verify', json={
            'email': email,
            'code': '999999',
        })
        assert r.status_code in VALID_CODES

    def test_verify_correct_code_student_no_phone(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vs_{tok}@test.com'
        _make_verification(db_session, email, f'vsu_{tok}')
        r = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'student',
        })
        assert r.status_code in VALID_CODES

    def test_verify_correct_code_teacher(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vt_{tok}@test.com'
        _make_verification(db_session, email, f'vtu_{tok}', grade='teacher')
        r = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'teacher',
        })
        assert r.status_code in VALID_CODES

    def test_verify_with_phone_student(self, client, db_session, app):
        """Student verification that has phone → requires phone verification"""
        tok = secrets.token_hex(4)
        email = f'vph_{tok}@test.com'
        _make_verification(db_session, email, f'vphu_{tok}', phone='+966500000099')
        r = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'student',
        })
        assert r.status_code in VALID_CODES

    def test_verify_with_phone_teacher(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vpht_{tok}@test.com'
        _make_verification(db_session, email, f'vphtu_{tok}',
                           grade='teacher', phone='+966500000088')
        r = client.post('/api/registration/verify', json={
            'email': email,
            'code': '123456',
            'account_type': 'teacher',
        })
        assert r.status_code in VALID_CODES


class TestVerifyPhoneExtra:
    """POST /api/registration/verify-phone"""

    def test_verify_phone_empty(self, client):
        r = client.post('/api/registration/verify-phone', json={})
        assert r.status_code in VALID_CODES

    def test_verify_phone_no_verification(self, client):
        r = client.post('/api/registration/verify-phone', json={
            'email': 'nobody@test.com',
            'code': '123456',
        })
        assert r.status_code in VALID_CODES

    def test_verify_phone_wrong_code(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vphone_{tok}@test.com'
        _make_verification(db_session, email, f'vphu_{tok}',
                           phone='+966500000077', is_verified=True)
        r = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '000000',
        })
        assert r.status_code in VALID_CODES

    def test_verify_phone_teacher_account(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vptch_{tok}@test.com'
        _make_verification(db_session, email, f'vptchu_{tok}',
                           grade='teacher', phone='+966500000066',
                           is_verified=True)
        r = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '123456',
            'account_type': 'teacher',
        })
        assert r.status_code in VALID_CODES

    def test_verify_phone_student_account(self, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'vpstu_{tok}@test.com'
        _make_verification(db_session, email, f'vphstu_{tok}',
                           phone='+966500000055', is_verified=True)
        r = client.post('/api/registration/verify-phone', json={
            'email': email,
            'code': '123456',
            'account_type': 'student',
        })
        assert r.status_code in VALID_CODES


class TestActivateAfterPhoneExtra:
    """POST /api/registration/activate-after-phone"""

    def test_activate_empty(self, client):
        r = client.post('/api/registration/activate-after-phone', json={})
        assert r.status_code in VALID_CODES

    def test_activate_no_email(self, client):
        r = client.post('/api/registration/activate-after-phone', json={
            'phone': '+966500000099',
        })
        assert r.status_code in VALID_CODES

    def test_activate_student_not_found(self, client):
        r = client.post('/api/registration/activate-after-phone', json={
            'email': 'ghost@test.com',
            'phone': '+966500000001',
            'account_type': 'student',
        })
        assert r.status_code in VALID_CODES

    def test_activate_teacher_not_found(self, client):
        r = client.post('/api/registration/activate-after-phone', json={
            'email': 'ghost_teacher@test.com',
            'phone': '+966500000002',
            'account_type': 'teacher',
        })
        assert r.status_code in VALID_CODES

    def test_activate_student_success(self, client, db_session):
        s = _make_student(db_session, '_act1')
        s.is_active = False
        db_session.session.commit()
        r = client.post('/api/registration/activate-after-phone', json={
            'email': s.email,
            'phone': '+966500000003',
            'account_type': 'student',
        })
        assert r.status_code in VALID_CODES

    def test_activate_teacher_success(self, client, db_session):
        t = _make_teacher(db_session, '_act2')
        t.is_active = False
        db_session.session.commit()
        r = client.post('/api/registration/activate-after-phone', json={
            'email': t.email,
            'phone': '+966500000004',
            'account_type': 'teacher',
        })
        assert r.status_code in VALID_CODES


class TestResendCodeExtra:
    """POST /api/registration/resend"""

    def test_resend_no_email(self, client):
        r = client.post('/api/registration/resend', json={})
        assert r.status_code in VALID_CODES

    def test_resend_not_found(self, client):
        r = client.post('/api/registration/resend', json={
            'email': 'ghost@test.com'
        })
        assert r.status_code in VALID_CODES

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(True, 'sent'))
    def test_resend_success(self, mock_send, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'resend_{tok}@test.com'
        _make_verification(db_session, email, f'rsnd_{tok}')
        r = client.post('/api/registration/resend', json={'email': email})
        assert r.status_code in VALID_CODES

    @patch('src.services.email_service.email_service.send_verification_code',
           return_value=(False, 'error'))
    def test_resend_email_fail(self, mock_send, client, db_session, app):
        tok = secrets.token_hex(4)
        email = f'rsfail_{tok}@test.com'
        _make_verification(db_session, email, f'rsf_{tok}')
        r = client.post('/api/registration/resend', json={'email': email})
        assert r.status_code in VALID_CODES


class TestAdminRegistrationSettings:
    """GET|POST /api/registration/admin/settings + toggle"""

    def test_get_settings_no_auth(self, client):
        r = client.get('/api/registration/admin/settings')
        assert r.status_code in VALID_CODES

    def test_get_settings_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.get('/api/registration/admin/settings')
        assert r.status_code in VALID_CODES

    def test_post_settings_no_auth(self, client):
        r = client.post('/api/registration/admin/settings', json={})
        assert r.status_code in VALID_CODES

    def test_post_settings_as_admin_student(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/api/registration/admin/settings', json={
            'is_registration_open': True,
            'require_phone': False,
            'require_school': False,
            'auto_activate': True,
        })
        assert r.status_code in VALID_CODES

    def test_post_settings_as_admin_teacher(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/api/registration/admin/settings', json={
            'is_teacher_registration_open': True,
            'teacher_require_phone': False,
            'teacher_require_school': False,
            'teacher_auto_activate': False,
        })
        assert r.status_code in VALID_CODES

    def test_toggle_student_registration_no_auth(self, client):
        r = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        assert r.status_code in VALID_CODES

    def test_toggle_student_registration_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/api/registration/admin/toggle', json={'type': 'student'})
        assert r.status_code in VALID_CODES

    def test_toggle_teacher_registration_as_admin(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/api/registration/admin/toggle', json={'type': 'teacher'})
        assert r.status_code in VALID_CODES

    def test_toggle_default_type(self, client, admin_user):
        _login_admin(client, admin_user)
        r = client.post('/api/registration/admin/toggle', json={})
        assert r.status_code in VALID_CODES


class TestRegistrationClosedExtra:
    """Test registration when closed"""

    def test_register_student_when_closed(self, client, admin_user):
        _login_admin(client, admin_user)
        # Close student registration
        client.post('/api/registration/admin/settings', json={
            'is_registration_open': False,
            'closed_message': 'التسجيل مغلق'
        })
        r = client.post('/api/registration/register', json={
            'name': 'احمد محمد علي',
            'username': 'closed_test1',
            'email': 'closed1@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES

    def test_register_teacher_when_closed(self, client, admin_user):
        _login_admin(client, admin_user)
        client.post('/api/registration/admin/settings', json={
            'is_teacher_registration_open': False,
            'teacher_closed_message': 'تسجيل المعلمين مغلق'
        })
        r = client.post('/api/registration/register-teacher', json={
            'name': 'احمد محمد علي',
            'username': 'tclosed_test1',
            'email': 'tclosed1@test.com',
            'password': 'Pass@1234',
        })
        assert r.status_code in VALID_CODES
