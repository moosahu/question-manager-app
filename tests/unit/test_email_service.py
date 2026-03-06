# tests/unit/test_email_service.py
"""
Unit tests for src/services/email_service.py
Mocks smtplib.SMTP, ssl, and all heavy third-party deps.
Covers _send_email, send_verification_code, send_password_reset_code,
send_delete_account_code, send_admin_login_otp, send_admin_notification,
and init_app.
"""

import sys
import os
import smtplib
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy third-party modules before any project import
# ---------------------------------------------------------------------------
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()
for _mod in ('firebase_admin', 'firebase_admin.credentials',
             'firebase_admin.messaging', 'firebase_admin.auth'):
    sys.modules.setdefault(_mod, MagicMock())
sys.modules.setdefault('flask_socketio', MagicMock())

import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as _pg
_pg.ARRAY = lambda *args, **kwargs: Text()
_pg.JSONB = JSON

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from src.services.email_service import EmailService


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _configured_service(**overrides):
    """Return an EmailService with all SMTP settings pre-populated."""
    svc = EmailService()
    svc.mail_server = overrides.get('mail_server', 'smtp-relay.brevo.com')
    svc.mail_port = overrides.get('mail_port', 587)
    svc.mail_username = overrides.get('mail_username', 'test@example.com')
    svc.mail_password = overrides.get('mail_password', 'supersecret')
    svc.mail_sender_name = overrides.get('mail_sender_name', 'كيم تحصيلي')
    svc.mail_sender_email = overrides.get('mail_sender_email', 'noreply@example.com')
    return svc


def _make_smtp_mock():
    """Return a context-manager-compatible SMTP mock."""
    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)
    return smtp_instance


# ===========================================================================
# 1. EmailService.__init__
# ===========================================================================

class TestEmailServiceInit:

    def test_mail_server_is_none_on_bare_init(self):
        svc = EmailService()
        assert svc.mail_server is None

    def test_mail_port_is_none_on_bare_init(self):
        svc = EmailService()
        assert svc.mail_port is None

    def test_mail_username_is_none_on_bare_init(self):
        svc = EmailService()
        assert svc.mail_username is None

    def test_mail_password_is_none_on_bare_init(self):
        svc = EmailService()
        assert svc.mail_password is None

    def test_mail_sender_name_is_none_on_bare_init(self):
        svc = EmailService()
        assert svc.mail_sender_name is None

    def test_mail_sender_email_is_none_on_bare_init(self):
        svc = EmailService()
        assert svc.mail_sender_email is None

    def test_init_with_app_calls_init_app(self):
        app = MagicMock()
        app.config = {
            'MAIL_SERVER': 'smtp.test.com',
            'MAIL_PORT': 465,
            'MAIL_USERNAME': 'u@test.com',
            'MAIL_PASSWORD': 'pw',
            'MAIL_SENDER_NAME': 'Test',
            'MAIL_DEFAULT_SENDER': 'u@test.com',
        }
        svc = EmailService(app=app)
        assert svc.mail_server == 'smtp.test.com'

    def test_module_level_instance_exists(self):
        from src.services.email_service import email_service
        assert email_service is not None

    def test_module_level_instance_is_email_service(self):
        from src.services.email_service import email_service
        assert isinstance(email_service, EmailService)


# ===========================================================================
# 2. EmailService.init_app
# ===========================================================================

class TestInitApp:

    def _make_app(self, **overrides):
        defaults = {
            'MAIL_SERVER': 'smtp.brevo.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'user@brevo.com',
            'MAIL_PASSWORD': 'brevo_key',
            'MAIL_SENDER_NAME': 'كيم تحصيلي',
            'MAIL_DEFAULT_SENDER': 'noreply@brevo.com',
        }
        defaults.update(overrides)
        app = MagicMock()
        app.config = defaults
        return app

    def test_sets_mail_server(self):
        svc = EmailService()
        svc.init_app(self._make_app())
        assert svc.mail_server == 'smtp.brevo.com'

    def test_sets_mail_port(self):
        svc = EmailService()
        svc.init_app(self._make_app(MAIL_PORT=465))
        assert svc.mail_port == 465

    def test_sets_mail_username(self):
        svc = EmailService()
        svc.init_app(self._make_app())
        assert svc.mail_username == 'user@brevo.com'

    def test_sets_mail_password(self):
        svc = EmailService()
        svc.init_app(self._make_app())
        assert svc.mail_password == 'brevo_key'

    def test_sets_sender_name(self):
        svc = EmailService()
        svc.init_app(self._make_app(MAIL_SENDER_NAME='MyApp'))
        assert svc.mail_sender_name == 'MyApp'

    def test_sets_sender_email_from_default_sender(self):
        svc = EmailService()
        svc.init_app(self._make_app(MAIL_DEFAULT_SENDER='info@myapp.com'))
        assert svc.mail_sender_email == 'info@myapp.com'

    def test_falls_back_to_username_when_no_default_sender(self):
        # Use a plain dict-backed config via _make_app without MAIL_DEFAULT_SENDER
        app = self._make_app()
        # Remove the MAIL_DEFAULT_SENDER key to trigger the fallback
        del app.config['MAIL_DEFAULT_SENDER']
        svc = EmailService()
        svc.init_app(app)
        # MAIL_DEFAULT_SENDER not set → falls back to mail_username
        assert svc.mail_sender_email == 'user@brevo.com'

    def test_default_server_when_not_configured(self):
        app = MagicMock()
        app.config.get = lambda k, d=None: d  # always return default
        svc = EmailService()
        svc.init_app(app)
        assert svc.mail_server == 'smtp-relay.brevo.com'

    def test_default_port_when_not_configured(self):
        app = MagicMock()
        app.config.get = lambda k, d=None: d
        svc = EmailService()
        svc.init_app(app)
        assert svc.mail_port == 587


# ===========================================================================
# 3. EmailService._send_email — configuration guard
# ===========================================================================

class TestSendEmailConfigGuard:

    def test_returns_false_when_username_missing(self):
        svc = _configured_service(mail_username=None)
        ok, msg = svc._send_email('to@test.com', 'subj', 'text')
        assert ok is False

    def test_error_message_mentions_username_when_username_missing(self):
        svc = _configured_service(mail_username=None)
        ok, msg = svc._send_email('to@test.com', 'subj', 'text')
        assert 'MAIL_USERNAME' in msg

    def test_returns_false_when_password_missing(self):
        svc = _configured_service(mail_password=None)
        ok, msg = svc._send_email('to@test.com', 'subj', 'text')
        assert ok is False

    def test_error_message_mentions_password_when_password_missing(self):
        svc = _configured_service(mail_password=None)
        ok, msg = svc._send_email('to@test.com', 'subj', 'text')
        assert 'MAIL_PASSWORD' in msg

    def test_returns_tuple_of_two(self):
        svc = _configured_service(mail_username=None)
        result = svc._send_email('to@test.com', 'subj', 'text')
        assert isinstance(result, tuple) and len(result) == 2


# ===========================================================================
# 4. EmailService._send_email — successful send
# ===========================================================================

class TestSendEmailSuccess:

    def test_returns_true_on_success(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert ok is True

    def test_success_message_returned(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert isinstance(msg, str) and len(msg) > 0

    def test_starttls_called(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            svc._send_email('to@test.com', 'Subject', 'Hello')
        smtp_mock.starttls.assert_called_once()

    def test_login_called_with_credentials(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            svc._send_email('to@test.com', 'Subject', 'Hello')
        smtp_mock.login.assert_called_once_with(svc.mail_username, svc.mail_password)

    def test_sendmail_called_with_correct_recipient(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            svc._send_email('recipient@test.com', 'Subject', 'Hello')
        args = smtp_mock.sendmail.call_args[0]
        assert args[1] == 'recipient@test.com'

    def test_html_content_attached_when_provided(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, _ = svc._send_email('to@test.com', 'Subject', 'plain text', html_content='<b>HTML</b>')
        assert ok is True

    def test_smtp_connected_with_correct_server(self):
        svc = _configured_service(mail_server='smtp.custom.com', mail_port=465)
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock) as MockSMTP:
            svc._send_email('to@test.com', 'Subject', 'Hello')
        MockSMTP.assert_called_once_with('smtp.custom.com', 465, timeout=30)


# ===========================================================================
# 5. EmailService._send_email — SMTP error handling
# ===========================================================================

class TestSendEmailErrorHandling:

    def test_returns_false_on_smtp_auth_error(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Auth failed')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert ok is False

    def test_auth_error_message_mentions_brevo(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Auth failed')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert 'Brevo' in msg or 'بيانات' in msg

    def test_returns_false_on_smtp_recipients_refused(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.sendmail.side_effect = smtplib.SMTPRecipientsRefused({'to@test.com': (550, b'Refused')})
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert ok is False

    def test_returns_false_on_smtp_sender_refused(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.sendmail.side_effect = smtplib.SMTPSenderRefused(553, b'Sender refused', 'from@test.com')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert ok is False

    def test_returns_false_on_generic_smtp_exception(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.starttls.side_effect = smtplib.SMTPException('Generic SMTP error')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert ok is False

    def test_generic_smtp_message_contains_error_text(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.starttls.side_effect = smtplib.SMTPException('connection lost')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert 'connection lost' in msg

    def test_returns_false_on_unexpected_exception(self):
        svc = _configured_service()
        with patch('smtplib.SMTP', side_effect=ConnectionRefusedError('Connection refused')):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert ok is False

    def test_unexpected_exception_message_is_string(self):
        svc = _configured_service()
        with patch('smtplib.SMTP', side_effect=Exception('boom')):
            ok, msg = svc._send_email('to@test.com', 'Subject', 'Hello')
        assert isinstance(msg, str)


# ===========================================================================
# 6. EmailService.send_verification_code
# ===========================================================================

class TestSendVerificationCode:

    def test_returns_tuple(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            result = svc.send_verification_code('stu@test.com', '123456', 'Ahmed')
        assert isinstance(result, tuple) and len(result) == 2

    def test_returns_true_on_success(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, _ = svc.send_verification_code('stu@test.com', '123456', 'Ahmed')
        assert ok is True

    def test_code_in_email_body(self):
        # Intercept _send_email to check the plain text content passed to it
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_verification_code('stu@test.com', '999888', 'Khaled')
        # _send_email(to, subject, text_content, html_content)
        text_content = mock_send.call_args[0][2]
        assert '999888' in text_content

    def test_student_name_in_email_body(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_verification_code('stu@test.com', '111222', 'Fatima')
        text_content = mock_send.call_args[0][2]
        assert 'Fatima' in text_content

    def test_returns_false_tuple_on_missing_credentials(self):
        svc = _configured_service(mail_username=None)
        ok, msg = svc.send_verification_code('stu@test.com', '123456', 'Ali')
        assert ok is False

    def test_returns_false_tuple_on_smtp_error(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Fail')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc.send_verification_code('stu@test.com', '123456', 'Ali')
        assert ok is False

    def test_subject_contains_verification_keyword(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_verification_code('stu@test.com', '123456', 'Nora')
        subject = mock_send.call_args[0][1]
        assert 'تحقق' in subject or 'رمز' in subject or 'Verification' in subject

    def test_calls_send_email_internally(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_verification_code('stu@test.com', '123456', 'Omar')
        mock_send.assert_called_once()

    def test_exception_in_send_returns_false(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', side_effect=Exception('unexpected')):
            ok, msg = svc.send_verification_code('stu@test.com', '123456', 'Zaid')
        assert ok is False


# ===========================================================================
# 7. EmailService.send_password_reset_code
# ===========================================================================

class TestSendPasswordResetCode:

    def test_returns_tuple(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            result = svc.send_password_reset_code('stu@test.com', '654321', 'Hassan')
        assert isinstance(result, tuple) and len(result) == 2

    def test_returns_true_on_success(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, _ = svc.send_password_reset_code('stu@test.com', '654321', 'Hassan')
        assert ok is True

    def test_code_in_email_body(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_password_reset_code('stu@test.com', '112233', 'Layla')
        text_content = mock_send.call_args[0][2]
        assert '112233' in text_content

    def test_student_name_in_email_body(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_password_reset_code('stu@test.com', '000111', 'Mariam')
        text_content = mock_send.call_args[0][2]
        assert 'Mariam' in text_content

    def test_subject_mentions_reset(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_password_reset_code('stu@test.com', '654321', 'Saad')
        subject = mock_send.call_args[0][1]
        assert 'إعادة' in subject or 'reset' in subject.lower()

    def test_returns_false_on_missing_credentials(self):
        svc = _configured_service(mail_password=None)
        ok, msg = svc.send_password_reset_code('stu@test.com', '654321', 'Tariq')
        assert ok is False

    def test_calls_send_email_internally(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_password_reset_code('stu@test.com', '654321', 'Nadia')
        mock_send.assert_called_once()

    def test_exception_returns_false(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', side_effect=Exception('fail')):
            ok, msg = svc.send_password_reset_code('stu@test.com', '654321', 'Rana')
        assert ok is False

    def test_exception_returns_error_string(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', side_effect=Exception('fail')):
            ok, msg = svc.send_password_reset_code('stu@test.com', '654321', 'Rana')
        assert isinstance(msg, str)


# ===========================================================================
# 8. EmailService.send_delete_account_code
# ===========================================================================

class TestSendDeleteAccountCode:

    def test_returns_tuple(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            result = svc.send_delete_account_code('user@test.com', '777888', 'Khalid')
        assert isinstance(result, tuple) and len(result) == 2

    def test_returns_true_on_success(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, _ = svc.send_delete_account_code('user@test.com', '777888', 'Khalid')
        assert ok is True

    def test_code_in_email_body(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_delete_account_code('user@test.com', '998877', 'Sara')
        text_content = mock_send.call_args[0][2]
        assert '998877' in text_content

    def test_user_name_in_email_body(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_delete_account_code('user@test.com', '998877', 'Ahmad')
        text_content = mock_send.call_args[0][2]
        assert 'Ahmad' in text_content

    def test_subject_mentions_delete(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_delete_account_code('user@test.com', '123', 'Walid')
        subject = mock_send.call_args[0][1]
        assert 'حذف' in subject

    def test_returns_false_on_auth_error(self):
        svc = _configured_service()
        smtp_mock = _make_smtp_mock()
        smtp_mock.login.side_effect = smtplib.SMTPAuthenticationError(535, b'fail')
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, msg = svc.send_delete_account_code('user@test.com', '123456', 'Rami')
        assert ok is False

    def test_calls_send_email_internally(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', return_value=(True, 'ok')) as mock_send:
            svc.send_delete_account_code('user@test.com', '654321', 'Hana')
        mock_send.assert_called_once()

    def test_exception_returns_false(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', side_effect=Exception('kaboom')):
            ok, msg = svc.send_delete_account_code('user@test.com', '654321', 'Dina')
        assert ok is False

    def test_exception_error_message_is_string(self):
        svc = _configured_service()
        with patch.object(svc, '_send_email', side_effect=Exception('err123')):
            ok, msg = svc.send_delete_account_code('user@test.com', '654321', 'Dina')
        assert isinstance(msg, str)


# ===========================================================================
# 9. EmailService.send_admin_login_otp
# ===========================================================================

class TestSendAdminLoginOtp:

    def _svc_with_smtp_attrs(self, **overrides):
        """
        send_admin_login_otp uses self.sender_email / self.smtp_host / self.smtp_port /
        self.smtp_user / self.smtp_password (legacy attribute names).
        We set them directly so the method can run.
        """
        svc = EmailService()
        svc.sender_email = overrides.get('sender_email', 'admin@app.com')
        svc.smtp_host = overrides.get('smtp_host', 'smtp.app.com')
        svc.smtp_port = overrides.get('smtp_port', 587)
        svc.smtp_user = overrides.get('smtp_user', 'smtp_user@app.com')
        svc.smtp_password = overrides.get('smtp_password', 'pw')
        return svc

    def test_returns_tuple(self):
        svc = self._svc_with_smtp_attrs()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            result = svc.send_admin_login_otp('admin@test.com', '112233', 'Admin')
        assert isinstance(result, tuple) and len(result) == 2

    def test_returns_true_on_success(self):
        svc = self._svc_with_smtp_attrs()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, _ = svc.send_admin_login_otp('admin@test.com', '112233', 'Admin')
        assert ok is True

    def test_code_in_email_body(self):
        # Intercept MIMEText to capture the html_content before MIME encoding
        svc = self._svc_with_smtp_attrs()
        captured = []

        real_mime_text = __import__('email.mime.text', fromlist=['MIMEText']).MIMEText

        def _capturing_mime_text(content, *args, **kwargs):
            captured.append(content)
            return real_mime_text(content, *args, **kwargs)

        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock), \
             patch('src.services.email_service.MIMEText', side_effect=_capturing_mime_text):
            svc.send_admin_login_otp('admin@test.com', '445566', 'Boss')
        assert any('445566' in c for c in captured)

    def test_admin_name_in_email_body(self):
        svc = self._svc_with_smtp_attrs()
        captured = []

        real_mime_text = __import__('email.mime.text', fromlist=['MIMEText']).MIMEText

        def _capturing_mime_text(content, *args, **kwargs):
            captured.append(content)
            return real_mime_text(content, *args, **kwargs)

        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock), \
             patch('src.services.email_service.MIMEText', side_effect=_capturing_mime_text):
            svc.send_admin_login_otp('admin@test.com', '112233', 'SuperAdmin')
        assert any('SuperAdmin' in c for c in captured)

    def test_starttls_called(self):
        svc = self._svc_with_smtp_attrs()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            svc.send_admin_login_otp('admin@test.com', '112233', 'Admin')
        smtp_mock.starttls.assert_called_once()

    def test_returns_false_on_exception(self):
        svc = self._svc_with_smtp_attrs()
        with patch('smtplib.SMTP', side_effect=Exception('connection refused')):
            ok, msg = svc.send_admin_login_otp('admin@test.com', '112233', 'Admin')
        assert ok is False

    def test_error_message_is_string_on_exception(self):
        svc = self._svc_with_smtp_attrs()
        with patch('smtplib.SMTP', side_effect=Exception('timeout')):
            ok, msg = svc.send_admin_login_otp('admin@test.com', '112233', 'Admin')
        assert isinstance(msg, str)


# ===========================================================================
# 10. EmailService.send_admin_notification
# ===========================================================================

class TestSendAdminNotification:

    def _svc_with_smtp_attrs(self, **overrides):
        svc = EmailService()
        svc.sender_email = overrides.get('sender_email', 'admin@app.com')
        svc.smtp_host = overrides.get('smtp_host', 'smtp.app.com')
        svc.smtp_port = overrides.get('smtp_port', 587)
        svc.smtp_user = overrides.get('smtp_user', 'smtp_user@app.com')
        svc.smtp_password = overrides.get('smtp_password', 'pw')
        return svc

    def test_returns_tuple(self):
        svc = self._svc_with_smtp_attrs()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            result = svc.send_admin_notification('admin@test.com', 'تسجيل جديد', 'طالب جديد: Ali')
        assert isinstance(result, tuple) and len(result) == 2

    def test_returns_true_on_success(self):
        svc = self._svc_with_smtp_attrs()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            ok, _ = svc.send_admin_notification('admin@test.com', 'Title', 'Body')
        assert ok is True

    def _notification_with_captured_mime(self, to_email, title, message):
        """Call send_admin_notification and return captured MIMEText contents."""
        svc = self._svc_with_smtp_attrs()
        captured = []

        real_mime_text = __import__('email.mime.text', fromlist=['MIMEText']).MIMEText

        def _capturing_mime_text(content, *args, **kwargs):
            captured.append(content)
            return real_mime_text(content, *args, **kwargs)

        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock), \
             patch('src.services.email_service.MIMEText', side_effect=_capturing_mime_text):
            result = svc.send_admin_notification(to_email, title, message)
        return result, captured

    def test_title_in_email_body(self):
        _, captured = self._notification_with_captured_mime('admin@test.com', 'NewStudent', 'details')
        assert any('NewStudent' in c for c in captured)

    def test_message_in_email_body(self):
        _, captured = self._notification_with_captured_mime('admin@test.com', 'Title', 'UniqueBodyContent')
        assert any('UniqueBodyContent' in c for c in captured)

    def test_newlines_in_message_converted_to_html_br(self):
        _, captured = self._notification_with_captured_mime('admin@test.com', 'T', 'Line1\nLine2')
        # The html_content contains <br> where \n was
        assert any('<br>' in c for c in captured)

    def test_starttls_called(self):
        svc = self._svc_with_smtp_attrs()
        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock):
            svc.send_admin_notification('admin@test.com', 'T', 'M')
        smtp_mock.starttls.assert_called_once()

    def test_returns_false_on_exception(self):
        svc = self._svc_with_smtp_attrs()
        with patch('smtplib.SMTP', side_effect=Exception('network error')):
            ok, msg = svc.send_admin_notification('admin@test.com', 'T', 'M')
        assert ok is False

    def test_error_message_on_exception_is_string(self):
        svc = self._svc_with_smtp_attrs()
        with patch('smtplib.SMTP', side_effect=Exception('net fail')):
            ok, msg = svc.send_admin_notification('admin@test.com', 'T', 'M')
        assert isinstance(msg, str)

    def test_subject_includes_title(self):
        # send_admin_notification sets msg['Subject'] = f'{title} - كيم تحصيلي'
        # Capture via MIMEMultipart
        svc = self._svc_with_smtp_attrs()
        captured_subjects = []

        from email.mime.multipart import MIMEMultipart as RealMIMEMultipart

        class CapturingMIMEMultipart(RealMIMEMultipart):
            def __setitem__(self, key, value):
                if key == 'Subject':
                    captured_subjects.append(value)
                super().__setitem__(key, value)

        smtp_mock = _make_smtp_mock()
        with patch('smtplib.SMTP', return_value=smtp_mock), \
             patch('src.services.email_service.MIMEMultipart', CapturingMIMEMultipart):
            svc.send_admin_notification('admin@test.com', 'MyTitle', 'body')
        assert any('MyTitle' in s for s in captured_subjects)
