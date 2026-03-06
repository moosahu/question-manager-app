"""
Unit tests for src/utils/notification_system.py
Coverage target: ~50 tests covering all main functions and branches.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Bootstrap: project root on path + heavy deps mocked before any import.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# External deps (not installed in test venv)
for _mod in [
    'firebase_admin',
    'firebase_admin.credentials',
    'firebase_admin.messaging',
    'firebase_admin.auth',
    'flask_socketio',
]:
    sys.modules.setdefault(_mod, MagicMock())

# google / genai stubs
sys.modules.setdefault('google', MagicMock())
sys.modules.setdefault('google.genai', MagicMock())
sys.modules.setdefault('google.genai.types', MagicMock())

# hashlib.scrypt stub (Python 3.9 doesn't have it on all platforms)
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

# SQLAlchemy dialect stubs
from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as _pg
_pg.ARRAY = lambda *args, **kwargs: Text()
_pg.JSONB = JSON

# Now import the module under test
import src.utils.notification_system as ns
from src.utils.notification_system import (
    NotificationSystem,
    UserNotifications,
    QuestionNotifications,
    SystemNotifications,
    create_notification,
    notify_user_action,
    safe_app_context_check,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _make_flask_mock(has_context=True):
    """Build a mock that replaces the flask module inside the tested functions."""
    flask_mock = MagicMock()
    flask_mock.has_app_context.return_value = has_context
    mock_logger = MagicMock()
    mock_app = MagicMock()
    mock_app.logger = mock_logger
    flask_mock.current_app = mock_app
    return flask_mock, mock_app, mock_logger


def _make_full_context_patches(student_id=1, user_id=None,
                                flush_raises=False, commit_raises=False):
    """
    Context manager: patches flask (has_app_context=True) + DB + models so
    that create_notification can run its full happy-path code.
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        flask_mock, mock_app, mock_logger = _make_flask_mock(has_context=True)

        mock_notif_inst = MagicMock()
        mock_notif_inst.id = 99
        mock_notif_cls = MagicMock(return_value=mock_notif_inst)
        mock_student_notif_cls = MagicMock()

        mock_db = MagicMock()
        if flush_raises:
            mock_db.session.flush.side_effect = Exception('flush error')
        if commit_raises:
            mock_db.session.commit.side_effect = Exception('commit error')

        notif_module = MagicMock()
        notif_module.Notification = mock_notif_cls
        notif_module.StudentNotification = mock_student_notif_cls
        ext_module = MagicMock()
        ext_module.db = mock_db

        with patch.dict('sys.modules', {
                'flask': flask_mock,
                'src.models.notification': notif_module,
                'src.extensions': ext_module,
        }):
            yield {
                'db': mock_db,
                'Notification': mock_notif_cls,
                'StudentNotification': mock_student_notif_cls,
                'app': mock_app,
                'logger': mock_logger,
            }

    return _ctx()


# ===========================================================================
# TestNotificationSystemCreateNotification
# ===========================================================================
class TestNotificationSystemCreateNotification(unittest.TestCase):
    """Tests for NotificationSystem.create_notification()"""

    # -----------------------------------------------------------------------
    # Branch: no app context → returns True (just prints)
    # -----------------------------------------------------------------------
    def test_no_app_context_returns_true(self):
        flask_mock, _, _ = _make_flask_mock(has_context=False)
        with patch.dict('sys.modules', {'flask': flask_mock}):
            result = NotificationSystem.create_notification('Title', 'Message')
        self.assertTrue(result)

    def test_no_app_context_does_not_raise(self):
        flask_mock, _, _ = _make_flask_mock(has_context=False)
        with patch.dict('sys.modules', {'flask': flask_mock}):
            try:
                result = NotificationSystem.create_notification('T', 'M')
            except Exception as exc:
                self.fail(f"Unexpected exception: {exc}")

    def test_no_app_context_with_student_id_still_returns_true(self):
        flask_mock, _, _ = _make_flask_mock(has_context=False)
        with patch.dict('sys.modules', {'flask': flask_mock}):
            result = NotificationSystem.create_notification(
                'T', 'M', student_id=5)
        self.assertTrue(result)

    # -----------------------------------------------------------------------
    # Branch: app context present, models import succeeds
    # -----------------------------------------------------------------------
    def test_with_full_context_and_student_id_returns_true(self):
        with _make_full_context_patches(student_id=1) as ctx:
            result = NotificationSystem.create_notification(
                'Title', 'Message', 'info', student_id=1)
        self.assertTrue(result)

    def test_with_full_context_creates_notification_object(self):
        with _make_full_context_patches(student_id=1) as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', 'info', student_id=1)
        ctx['Notification'].assert_called_once()

    def test_with_full_context_creates_student_notification(self):
        with _make_full_context_patches(student_id=5) as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', student_id=5)
        ctx['StudentNotification'].assert_called_once()

    def test_with_user_id_only_no_student_notification(self):
        """When only user_id is set, no StudentNotification is created."""
        with _make_full_context_patches(student_id=None, user_id=7) as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', student_id=None, user_id=7)
        ctx['StudentNotification'].assert_not_called()

    def test_db_session_add_called_with_student(self):
        with _make_full_context_patches(student_id=1) as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', student_id=1)
        self.assertTrue(ctx['db'].session.add.called)

    def test_db_session_commit_called(self):
        with _make_full_context_patches(student_id=1) as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', student_id=1)
        ctx['db'].session.commit.assert_called()

    def test_db_session_flush_called(self):
        with _make_full_context_patches(student_id=1) as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', student_id=1)
        ctx['db'].session.flush.assert_called()

    # -----------------------------------------------------------------------
    # Branch: neither student_id nor user_id → returns False
    # -----------------------------------------------------------------------
    def test_no_student_or_user_id_returns_false(self):
        with _make_full_context_patches() as ctx:
            result = NotificationSystem.create_notification(
                'Title', 'Message', student_id=None, user_id=None)
        self.assertFalse(result)

    def test_no_student_or_user_id_does_not_create_notification(self):
        with _make_full_context_patches() as ctx:
            NotificationSystem.create_notification(
                'Title', 'Message', student_id=None, user_id=None)
        ctx['Notification'].assert_not_called()

    # -----------------------------------------------------------------------
    # Branch: exception during flush → rollback + returns False
    # -----------------------------------------------------------------------
    def test_exception_during_flush_returns_false(self):
        with _make_full_context_patches(student_id=1, flush_raises=True) as ctx:
            result = NotificationSystem.create_notification(
                'Title', 'Message', student_id=1)
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # Branch: exception during commit → returns False
    # -----------------------------------------------------------------------
    def test_exception_during_commit_returns_false(self):
        with _make_full_context_patches(student_id=1, commit_raises=True) as ctx:
            result = NotificationSystem.create_notification(
                'Title', 'Message', student_id=1)
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # Branch: both student_id and user_id provided
    # -----------------------------------------------------------------------
    def test_both_ids_provided_returns_true(self):
        with _make_full_context_patches(student_id=1, user_id=10) as ctx:
            result = NotificationSystem.create_notification(
                'Title', 'Message', student_id=1, user_id=10)
        self.assertTrue(result)


# ===========================================================================
# TestUserNotifications
# ===========================================================================
class TestUserNotifications(unittest.TestCase):
    """Tests for the UserNotifications static methods."""

    def _patch_create(self, return_value=True):
        return patch.object(NotificationSystem, 'create_notification',
                            return_value=return_value)

    # --- notify_user_login ---
    def test_notify_user_login_returns_true(self):
        with self._patch_create(True):
            result = UserNotifications.notify_user_login('ahmed', student_id=1)
        self.assertTrue(result)

    def test_notify_user_login_uses_success_type(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_login('ahmed', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    def test_notify_user_login_passes_student_id(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_login('ahmed', student_id=42)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['student_id'], 42)

    def test_notify_user_login_username_in_message(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_login('ibrahim', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('ibrahim', kwargs['message'])

    def test_notify_user_login_with_user_id(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_login('admin_user', user_id=5)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['user_id'], 5)

    # --- notify_user_login_2fa ---
    def test_notify_user_login_2fa_returns_true(self):
        with self._patch_create(True):
            result = UserNotifications.notify_user_login_2fa('sara', student_id=2)
        self.assertTrue(result)

    def test_notify_user_login_2fa_uses_success_type(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_login_2fa('sara', student_id=2)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    def test_notify_user_login_2fa_username_in_message(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_login_2fa('sara', student_id=2)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('sara', kwargs['message'])

    # --- notify_user_logout ---
    def test_notify_user_logout_returns_true(self):
        with self._patch_create(True):
            result = UserNotifications.notify_user_logout('khalid', student_id=3)
        self.assertTrue(result)

    def test_notify_user_logout_uses_info_type(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_logout('khalid', student_id=3)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'info')

    def test_notify_user_logout_username_in_message(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_user_logout('khalid', student_id=3)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('khalid', kwargs['message'])

    # --- notify_profile_updated ---
    def test_notify_profile_updated_returns_true(self):
        with self._patch_create(True):
            result = UserNotifications.notify_profile_updated('ali', user_id=10)
        self.assertTrue(result)

    def test_notify_profile_updated_uses_success_type(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_profile_updated('ali', user_id=10)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    def test_notify_profile_updated_username_in_message(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_profile_updated('ali', user_id=10)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('ali', kwargs['message'])

    # --- notify_password_changed ---
    def test_notify_password_changed_returns_true(self):
        with self._patch_create(True):
            result = UserNotifications.notify_password_changed('fatima', user_id=5)
        self.assertTrue(result)

    def test_notify_password_changed_uses_success_type(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_password_changed('fatima', user_id=5)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    def test_notify_password_changed_username_in_message(self):
        with self._patch_create() as mock_create:
            UserNotifications.notify_password_changed('fatima', user_id=5)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('fatima', kwargs['message'])


# ===========================================================================
# TestQuestionNotifications
# ===========================================================================
class TestQuestionNotifications(unittest.TestCase):
    """Tests for the QuestionNotifications static methods."""

    def _patch_create(self, return_value=True):
        return patch.object(NotificationSystem, 'create_notification',
                            return_value=return_value)

    # --- notify_question_added ---
    def test_notify_question_added_returns_true(self):
        with self._patch_create(True):
            result = QuestionNotifications.notify_question_added('الكيمياء', student_id=1)
        self.assertTrue(result)

    def test_notify_question_added_lesson_in_message(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_question_added('الكيمياء', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('الكيمياء', kwargs['message'])

    def test_notify_question_added_uses_success_type(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_question_added('درس', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    def test_notify_question_added_no_student_id(self):
        with self._patch_create(True):
            result = QuestionNotifications.notify_question_added('درس')
        self.assertTrue(result)

    # --- notify_question_updated ---
    def test_notify_question_updated_returns_true(self):
        with self._patch_create(True):
            result = QuestionNotifications.notify_question_updated('الفيزياء')
        self.assertTrue(result)

    def test_notify_question_updated_uses_info_type(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_question_updated('الفيزياء')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'info')

    def test_notify_question_updated_lesson_in_message(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_question_updated('الفيزياء')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('الفيزياء', kwargs['message'])

    # --- notify_question_deleted ---
    def test_notify_question_deleted_returns_true(self):
        with self._patch_create(True):
            result = QuestionNotifications.notify_question_deleted('الرياضيات')
        self.assertTrue(result)

    def test_notify_question_deleted_uses_warning_type(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_question_deleted('الرياضيات')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'warning')

    def test_notify_question_deleted_lesson_in_message(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_question_deleted('البيولوجيا')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('البيولوجيا', kwargs['message'])

    # --- notify_questions_imported ---
    def test_notify_questions_imported_returns_true(self):
        with self._patch_create(True):
            result = QuestionNotifications.notify_questions_imported(10)
        self.assertTrue(result)

    def test_notify_questions_imported_count_in_message(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_questions_imported(25)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('25', kwargs['message'])

    def test_notify_questions_imported_uses_success_type(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_questions_imported(5)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    # --- notify_file_uploaded ---
    def test_notify_file_uploaded_returns_true(self):
        with self._patch_create(True):
            result = QuestionNotifications.notify_file_uploaded('test.pdf', 'مجلد')
        self.assertTrue(result)

    def test_notify_file_uploaded_filename_in_message(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_file_uploaded('data.xlsx', 'uploads')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('data.xlsx', kwargs['message'])

    def test_notify_file_uploaded_folder_in_message(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_file_uploaded('file.csv', 'reports')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('reports', kwargs['message'])

    def test_notify_file_uploaded_uses_success_type(self):
        with self._patch_create() as mock_create:
            QuestionNotifications.notify_file_uploaded('x.pdf', 'folder')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')


# ===========================================================================
# TestSystemNotifications
# ===========================================================================
class TestSystemNotifications(unittest.TestCase):
    """Tests for the SystemNotifications static methods."""

    def _patch_create(self, return_value=True):
        return patch.object(NotificationSystem, 'create_notification',
                            return_value=return_value)

    def _patch_student_query(self, student_instance):
        """Patch src.models.student so Student.query works correctly."""
        mock_student_cls = MagicMock()
        mock_student_cls.query.filter_by.return_value.first.return_value = student_instance
        mock_student_module = MagicMock()
        mock_student_module.Student = mock_student_cls
        return patch.dict('sys.modules', {'src.models.student': mock_student_module})

    # --- notify_failed_login ---
    def test_notify_failed_login_returns_true(self):
        mock_student = MagicMock()
        mock_student.id = 7
        with self._patch_student_query(mock_student), self._patch_create(True):
            result = SystemNotifications.notify_failed_login('baduser', '1.2.3.4')
        self.assertTrue(result)

    def test_notify_failed_login_username_in_message(self):
        with self._patch_student_query(None), self._patch_create() as mock_create:
            SystemNotifications.notify_failed_login('baduser', '10.0.0.1')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('baduser', kwargs['message'])

    def test_notify_failed_login_ip_in_message(self):
        with self._patch_student_query(None), self._patch_create() as mock_create:
            SystemNotifications.notify_failed_login('user', '192.168.1.1')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('192.168.1.1', kwargs['message'])

    def test_notify_failed_login_uses_error_type(self):
        with self._patch_student_query(None), self._patch_create() as mock_create:
            SystemNotifications.notify_failed_login('user', '0.0.0.0')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'error')

    def test_notify_failed_login_student_not_found_passes_none_id(self):
        with self._patch_student_query(None), self._patch_create() as mock_create:
            SystemNotifications.notify_failed_login('ghost', '0.0.0.0')
        kwargs = mock_create.call_args.kwargs
        self.assertIsNone(kwargs['student_id'])

    def test_notify_failed_login_student_found_passes_id(self):
        mock_student = MagicMock()
        mock_student.id = 42
        with self._patch_student_query(mock_student), self._patch_create() as mock_create:
            SystemNotifications.notify_failed_login('known_user', '5.5.5.5')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['student_id'], 42)

    def test_notify_failed_login_import_error_uses_none_id(self):
        """If student query raises, student_id falls back to None."""
        mock_student_cls = MagicMock()
        mock_student_cls.query.filter_by.return_value.first.side_effect = Exception('db down')
        mock_student_module = MagicMock()
        mock_student_module.Student = mock_student_cls
        with patch.dict('sys.modules', {'src.models.student': mock_student_module}), \
             self._patch_create() as mock_create:
            result = SystemNotifications.notify_failed_login('x', '0.0.0.0')
        kwargs = mock_create.call_args.kwargs
        self.assertIsNone(kwargs['student_id'])

    # --- notify_security_alert ---
    def test_notify_security_alert_returns_true(self):
        with self._patch_create(True):
            result = SystemNotifications.notify_security_alert('تهديد أمني', student_id=2)
        self.assertTrue(result)

    def test_notify_security_alert_uses_error_type(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_security_alert('تهديد', student_id=2)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'error')

    def test_notify_security_alert_message_passed(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_security_alert('unauthorized access', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('unauthorized access', kwargs['message'])

    def test_notify_security_alert_without_student_id(self):
        with self._patch_create(True):
            result = SystemNotifications.notify_security_alert('alert')
        self.assertTrue(result)

    # --- notify_settings_updated ---
    def test_notify_settings_updated_returns_true(self):
        with self._patch_create(True):
            result = SystemNotifications.notify_settings_updated('theme')
        self.assertTrue(result)

    def test_notify_settings_updated_setting_name_in_message(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_settings_updated('language')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('language', kwargs['message'])

    def test_notify_settings_updated_uses_info_type(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_settings_updated('x')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'info')

    # --- notify_backup_completed ---
    def test_notify_backup_completed_returns_true(self):
        with self._patch_create(True):
            result = SystemNotifications.notify_backup_completed()
        self.assertTrue(result)

    def test_notify_backup_completed_uses_success_type(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_backup_completed()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'success')

    def test_notify_backup_completed_with_student_id(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_backup_completed(student_id=3)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['student_id'], 3)

    # --- notify_system_update ---
    def test_notify_system_update_returns_true(self):
        with self._patch_create(True):
            result = SystemNotifications.notify_system_update('2.0.0')
        self.assertTrue(result)

    def test_notify_system_update_version_in_message(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_system_update('3.1.4')
        kwargs = mock_create.call_args.kwargs
        self.assertIn('3.1.4', kwargs['message'])

    def test_notify_system_update_uses_info_type(self):
        with self._patch_create() as mock_create:
            SystemNotifications.notify_system_update('1.0')
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'info')


# ===========================================================================
# TestModuleLevelHelpers
# ===========================================================================
class TestModuleLevelHelpers(unittest.TestCase):
    """Tests for the module-level helper functions."""

    def _patch_create(self, return_value=True):
        return patch.object(NotificationSystem, 'create_notification',
                            return_value=return_value)

    # --- create_notification wrapper ---
    def test_create_notification_delegates_to_system(self):
        with self._patch_create(True) as mock_create:
            result = create_notification('T', 'M', 'info', student_id=1)
        mock_create.assert_called_once_with('T', 'M', 'info', 1, None)
        self.assertTrue(result)

    def test_create_notification_passes_user_id(self):
        with self._patch_create(True) as mock_create:
            create_notification('T', 'M', user_id=99)
        args = mock_create.call_args.args
        self.assertEqual(args[4], 99)

    def test_create_notification_default_type_is_info(self):
        with self._patch_create(True) as mock_create:
            create_notification('T', 'M')
        args = mock_create.call_args.args
        self.assertEqual(args[2], 'info')

    def test_create_notification_returns_value_from_system(self):
        with self._patch_create(False):
            result = create_notification('T', 'M')
        self.assertFalse(result)

    # --- notify_user_action ---
    def test_notify_user_action_login(self):
        with patch.object(UserNotifications, 'notify_user_login',
                          return_value=True) as mock_login:
            result = notify_user_action('login', 'ahmed', student_id=1)
        mock_login.assert_called_once_with('ahmed', 1, None)
        self.assertTrue(result)

    def test_notify_user_action_logout(self):
        with patch.object(UserNotifications, 'notify_user_logout',
                          return_value=True) as mock_logout:
            result = notify_user_action('logout', 'ahmed', student_id=1)
        mock_logout.assert_called_once_with('ahmed', 1, None)
        self.assertTrue(result)

    def test_notify_user_action_profile_update(self):
        with patch.object(UserNotifications, 'notify_profile_updated',
                          return_value=True) as mock_update:
            result = notify_user_action('profile_update', 'sara', user_id=5)
        mock_update.assert_called_once_with('sara', None, 5)
        self.assertTrue(result)

    def test_notify_user_action_password_change(self):
        with patch.object(UserNotifications, 'notify_password_changed',
                          return_value=True) as mock_pw:
            result = notify_user_action('password_change', 'ali', user_id=3)
        mock_pw.assert_called_once_with('ali', None, 3)
        self.assertTrue(result)

    def test_notify_user_action_unknown_action_returns_true(self):
        with self._patch_create(True):
            result = notify_user_action('custom_action', 'bob', student_id=2)
        self.assertTrue(result)

    def test_notify_user_action_unknown_calls_create_notification(self):
        with self._patch_create(True) as mock_create:
            notify_user_action('other', 'user', student_id=1)
        mock_create.assert_called_once()

    def test_notify_user_action_unknown_contains_action_in_message(self):
        with self._patch_create(True) as mock_create:
            notify_user_action('delete_account', 'user', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('delete_account', kwargs['message'])

    def test_notify_user_action_unknown_contains_username_in_message(self):
        with self._patch_create(True) as mock_create:
            notify_user_action('some_action', 'my_user', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertIn('my_user', kwargs['message'])

    def test_notify_user_action_unknown_uses_info_type(self):
        with self._patch_create(True) as mock_create:
            notify_user_action('other', 'user', student_id=1)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['notification_type'], 'info')

    # --- safe_app_context_check ---
    def test_safe_app_context_check_returns_true_when_context(self):
        flask_mock, _, _ = _make_flask_mock(has_context=True)
        with patch.dict('sys.modules', {'flask': flask_mock}):
            result = safe_app_context_check()
        self.assertTrue(result)

    def test_safe_app_context_check_returns_false_when_no_context(self):
        flask_mock, _, _ = _make_flask_mock(has_context=False)
        with patch.dict('sys.modules', {'flask': flask_mock}):
            result = safe_app_context_check()
        self.assertFalse(result)

    def test_safe_app_context_check_returns_false_on_exception(self):
        flask_mock = MagicMock()
        flask_mock.has_app_context.side_effect = RuntimeError('no flask')
        with patch.dict('sys.modules', {'flask': flask_mock}):
            result = safe_app_context_check()
        self.assertFalse(result)

    def test_safe_app_context_check_returns_bool(self):
        flask_mock, _, _ = _make_flask_mock(has_context=False)
        with patch.dict('sys.modules', {'flask': flask_mock}):
            result = safe_app_context_check()
        self.assertIsInstance(result, bool)


if __name__ == '__main__':
    unittest.main()
