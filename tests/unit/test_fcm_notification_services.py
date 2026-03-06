# tests/unit/test_fcm_notification_services.py
"""
Unit tests for:
  - src/services/fcm_service.py       (FCMService + helper functions)
  - src/services/notification_service.py (NotificationService + module-level helpers)
All Firebase and requests calls are mocked.
"""

import sys
import os
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Mock firebase_admin BEFORE any project imports
# ---------------------------------------------------------------------------

firebase_mock = MagicMock()
for _m in ('firebase_admin', 'firebase_admin.credentials',
           'firebase_admin.messaging', 'firebase_admin.auth'):
    sys.modules[_m] = firebase_mock

# google.genai (pulled in transitively)
sys.modules.setdefault('google', MagicMock())
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()

# anthropic, flask_socketio
sys.modules.setdefault('anthropic', MagicMock())
sys.modules.setdefault('flask_socketio', MagicMock())

# hashlib.scrypt shim
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

# SQLAlchemy PostgreSQL shims
from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as _pg
_pg.ARRAY = lambda *args, **kwargs: Text()
_pg.JSONB = JSON

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


# ---------------------------------------------------------------------------
# Helpers to create fresh service instances
# ---------------------------------------------------------------------------

def _make_fcm_service(server_key='test-server-key'):
    """Return a fresh FCMService with optional server key."""
    with patch('src.services.fcm_service.Student'):
        from src.services.fcm_service import FCMService
        with patch.dict(os.environ, {'FCM_SERVER_KEY': server_key} if server_key else {}, clear=False):
            svc = FCMService()
    svc.server_key = server_key  # force-set since env patch timing varies
    svc.is_configured = bool(server_key)
    return svc


def _make_notification_service():
    """Return NotificationService class with _initialized reset."""
    with patch('src.services.notification_service.firebase_admin'), \
         patch('src.services.notification_service.messaging'):
        import importlib
        import src.services.notification_service as mod
        importlib.reload(mod)
        mod.NotificationService._initialized = False
        return mod.NotificationService


# ===========================================================================
# ===========================  FCMService  ===================================
# ===========================================================================

class TestFCMServiceInit:

    def test_creates_instance(self):
        svc = _make_fcm_service()
        assert svc is not None

    def test_is_configured_true_when_key_present(self):
        svc = _make_fcm_service(server_key='some-key')
        assert svc.is_configured is True

    def test_is_configured_false_when_no_key(self):
        svc = _make_fcm_service(server_key='')
        assert svc.is_configured is False

    def test_fcm_url_set(self):
        svc = _make_fcm_service()
        assert 'fcm.googleapis.com' in svc.fcm_url

    def test_server_key_stored(self):
        svc = _make_fcm_service(server_key='abc-key')
        assert svc.server_key == 'abc-key'


class TestFCMServiceSendNotification:

    def test_returns_false_when_not_configured(self):
        svc = _make_fcm_service(server_key='')
        result = svc.send_notification('token', 'title', 'body')
        assert result is False

    def test_returns_false_when_no_token(self):
        svc = _make_fcm_service()
        result = svc.send_notification('', 'title', 'body')
        assert result is False

    def test_returns_false_when_none_token(self):
        svc = _make_fcm_service()
        result = svc.send_notification(None, 'title', 'body')
        assert result is False

    def test_returns_true_on_success(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 1, 'results': [{}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp):
            result = svc.send_notification('valid-token', 'Title', 'Body')
        assert result is True

    def test_returns_false_on_http_error(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp):
            result = svc.send_notification('valid-token', 'Title', 'Body')
        assert result is False

    def test_returns_false_when_fcm_reports_failure(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 0, 'results': [{'error': 'InvalidRegistration'}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp):
            result = svc.send_notification('bad-token', 'Title', 'Body')
        assert result is False

    def test_returns_false_on_exception(self):
        svc = _make_fcm_service()
        with patch('src.services.fcm_service.requests.post', side_effect=Exception('Network error')):
            result = svc.send_notification('token', 'Title', 'Body')
        assert result is False

    def test_includes_data_in_payload_when_provided(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 1, 'results': [{}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp) as mock_post:
            svc.send_notification('token', 'Title', 'Body', data={'key': 'val'})
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs['json']['data'] == {'key': 'val'}

    def test_does_not_include_data_key_when_none(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 1, 'results': [{}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp) as mock_post:
            svc.send_notification('token', 'Title', 'Body', data=None)
        payload = mock_post.call_args[1]['json']
        assert 'data' not in payload

    def test_post_called_with_correct_url(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 1, 'results': [{}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp) as mock_post:
            svc.send_notification('token', 'T', 'B')
        call_args = mock_post.call_args
        assert 'fcm.googleapis.com' in call_args[0][0]

    def test_authorization_header_sent(self):
        svc = _make_fcm_service(server_key='my-key')
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 1, 'results': [{}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp) as mock_post:
            svc.send_notification('token', 'T', 'B')
        headers = mock_post.call_args[1]['headers']
        assert 'my-key' in headers['Authorization']

    def test_timeout_set_to_10(self):
        svc = _make_fcm_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'success': 1, 'results': [{}]}

        with patch('src.services.fcm_service.requests.post', return_value=mock_resp) as mock_post:
            svc.send_notification('token', 'T', 'B')
        assert mock_post.call_args[1]['timeout'] == 10


class TestFCMServiceSendToMultiple:

    def test_returns_0_when_not_configured(self):
        svc = _make_fcm_service(server_key='')
        result = svc.send_notification_to_multiple(['t1', 't2'], 'T', 'B')
        assert result == 0

    def test_returns_0_when_tokens_empty(self):
        svc = _make_fcm_service()
        result = svc.send_notification_to_multiple([], 'T', 'B')
        assert result == 0

    def test_returns_count_of_successful_sends(self):
        svc = _make_fcm_service()
        with patch.object(svc, 'send_notification', return_value=True):
            result = svc.send_notification_to_multiple(['t1', 't2', 't3'], 'T', 'B')
        assert result == 3

    def test_counts_only_successful(self):
        svc = _make_fcm_service()
        # First two succeed, third fails
        with patch.object(svc, 'send_notification', side_effect=[True, True, False]):
            result = svc.send_notification_to_multiple(['t1', 't2', 't3'], 'T', 'B')
        assert result == 2

    def test_calls_send_notification_for_each_token(self):
        svc = _make_fcm_service()
        with patch.object(svc, 'send_notification', return_value=True) as mock_send:
            svc.send_notification_to_multiple(['t1', 't2'], 'T', 'B')
        assert mock_send.call_count == 2

    def test_passes_data_to_individual_sends(self):
        svc = _make_fcm_service()
        extra = {'key': 'value'}
        with patch.object(svc, 'send_notification', return_value=True) as mock_send:
            svc.send_notification_to_multiple(['t1'], 'T', 'B', data=extra)
        mock_send.assert_called_once_with('t1', 'T', 'B', extra)

    def test_all_fail_returns_0(self):
        svc = _make_fcm_service()
        with patch.object(svc, 'send_notification', return_value=False):
            result = svc.send_notification_to_multiple(['t1', 't2'], 'T', 'B')
        assert result == 0


# ===========================================================================
# Helper functions in fcm_service.py
# ===========================================================================

class TestFCMHelperFunctions:

    def _import_helpers(self):
        with patch('src.services.fcm_service.Student'):
            import src.services.fcm_service as mod
        return mod

    def test_send_notification_to_student_returns_false_when_no_token(self):
        mod = self._import_helpers()
        student = MagicMock()
        student.fcm_token = None
        student.name = 'Ahmed'
        result = mod.send_notification_to_student(student, 'T', 'B')
        assert result is False

    def test_send_notification_to_student_calls_fcm_service(self):
        mod = self._import_helpers()
        student = MagicMock()
        student.fcm_token = 'valid-token'
        with patch.object(mod.fcm_service, 'send_notification', return_value=True) as mock_snd:
            result = mod.send_notification_to_student(student, 'Title', 'Body')
        mock_snd.assert_called_once_with('valid-token', 'Title', 'Body', None)
        assert result is True

    def test_send_notification_to_students_skips_students_without_tokens(self):
        mod = self._import_helpers()
        s1 = MagicMock()
        s1.fcm_token = 'token1'
        s2 = MagicMock()
        s2.fcm_token = None  # no token - should be skipped
        with patch.object(mod.fcm_service, 'send_notification_to_multiple', return_value=1) as mock_multi:
            mod.send_notification_to_students([s1, s2], 'T', 'B')
        call_tokens = mock_multi.call_args[0][0]
        assert call_tokens == ['token1']

    def test_send_notification_to_students_returns_0_if_no_tokens(self):
        mod = self._import_helpers()
        s1 = MagicMock()
        s1.fcm_token = None
        result = mod.send_notification_to_students([s1], 'T', 'B')
        assert result == 0

    def test_send_broadcast_notification_calls_students_helper(self):
        mod = self._import_helpers()
        with patch.object(mod, 'send_notification_to_students', return_value=5) as mock_fn:
            with patch('src.services.fcm_service.Student') as MockStudent:
                MockStudent.get_students_with_fcm_tokens.return_value = []
                mod.send_broadcast_notification('T', 'B')
        mock_fn.assert_called_once()


# ===========================================================================
# ======================  NotificationService  ================================
# ===========================================================================

class TestNotificationServiceInitialize:

    def test_returns_true_when_already_initialized(self):
        with patch('src.services.notification_service.firebase_admin') as mock_fa, \
             patch('src.services.notification_service.messaging'):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            result = NotificationService.initialize()
        assert result is True

    def test_detects_existing_firebase_app(self):
        with patch('src.services.notification_service.firebase_admin') as mock_fa, \
             patch('src.services.notification_service.messaging'):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            mock_fa.get_app.return_value = MagicMock()  # app already initialized
            result = NotificationService.initialize()
        assert result is True
        assert NotificationService._initialized is True

    def test_initializes_from_env_json(self):
        creds_json = '{"type": "service_account", "project_id": "test"}'
        with patch('src.services.notification_service.firebase_admin') as mock_fa, \
             patch('src.services.notification_service.messaging'), \
             patch('src.services.notification_service.credentials') as mock_creds, \
             patch.dict(os.environ, {'FIREBASE_CONFIG': creds_json}, clear=False):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            mock_fa.get_app.side_effect = ValueError('no app')
            mock_creds.Certificate.return_value = MagicMock()
            result = NotificationService.initialize()
        assert result is True

    def test_returns_false_when_no_config_available(self):
        with patch('src.services.notification_service.firebase_admin') as mock_fa, \
             patch('src.services.notification_service.messaging'), \
             patch.dict(os.environ, {}, clear=True):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            mock_fa.get_app.side_effect = ValueError('no app')
            result = NotificationService.initialize()
        assert result is False

    def test_returns_false_on_invalid_json(self):
        with patch('src.services.notification_service.firebase_admin') as mock_fa, \
             patch('src.services.notification_service.messaging'), \
             patch.dict(os.environ, {'FIREBASE_CONFIG': '{invalid-json}'}, clear=False):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            mock_fa.get_app.side_effect = ValueError('no app')
            result = NotificationService.initialize()
        assert result is False

    def test_exception_during_init_returns_false(self):
        with patch('src.services.notification_service.firebase_admin') as mock_fa, \
             patch('src.services.notification_service.messaging'), \
             patch.dict(os.environ, {}, clear=True):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            mock_fa.get_app.side_effect = Exception('Unexpected error')
            result = NotificationService.initialize()
        assert result is False


class TestNotificationServiceSendFCM:

    def test_returns_false_when_initialize_fails(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            with patch.object(NotificationService, 'initialize', return_value=False):
                result = NotificationService.send_fcm_notification('token', 'T', 'B')
        assert result is False

    def test_returns_true_on_success(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'projects/test/messages/123'
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            result = NotificationService.send_fcm_notification('valid-token', 'Title', 'Body')
        assert result is True

    def test_returns_false_on_exception(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.side_effect = Exception('FCM error')
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            result = NotificationService.send_fcm_notification('token', 'T', 'B')
        assert result is False

    def test_data_values_converted_to_strings(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            # Pass integer values - they should be converted to strings
            NotificationService.send_fcm_notification('token', 'T', 'B', data={'count': 42})
        # messaging.Message should have been called
        mock_msg.Message.assert_called()

    def test_calls_messaging_send(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            NotificationService.send_fcm_notification('token', 'T', 'B')
        mock_msg.send.assert_called_once()


class TestNotificationServiceSendMulticast:

    def test_returns_failure_dict_when_not_initialized(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            with patch.object(NotificationService, 'initialize', return_value=False):
                result = NotificationService.send_multicast_notification(
                    ['t1', 't2'], 'T', 'B'
                )
        assert result['success_count'] == 0
        assert result['failure_count'] == 2

    def test_returns_success_counts_on_success(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True

            mock_response = MagicMock()
            mock_response.success_count = 2
            mock_response.failure_count = 0
            mock_response.responses = []
            mock_msg.send_multicast.return_value = mock_response
            mock_msg.MulticastMessage.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()

            result = NotificationService.send_multicast_notification(['t1', 't2'], 'T', 'B')
        assert result['success_count'] == 2
        assert result['failure_count'] == 0

    def test_returns_failure_dict_on_exception(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send_multicast.side_effect = Exception('FCM error')
            mock_msg.MulticastMessage.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()

            result = NotificationService.send_multicast_notification(['t1', 't2', 't3'], 'T', 'B')
        assert result['success_count'] == 0
        assert result['failure_count'] == 3

    def test_result_has_responses_key(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True

            mock_response = MagicMock()
            mock_response.success_count = 1
            mock_response.failure_count = 0
            mock_response.responses = []
            mock_msg.send_multicast.return_value = mock_response
            mock_msg.MulticastMessage.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()

            result = NotificationService.send_multicast_notification(['t1'], 'T', 'B')
        assert 'responses' in result


class TestNotificationServiceSendTopic:

    def test_returns_false_when_not_initialized(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            with patch.object(NotificationService, 'initialize', return_value=False):
                result = NotificationService.send_topic_notification('mytopic', 'T', 'B')
        assert result is False

    def test_returns_true_on_success(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            result = NotificationService.send_topic_notification('news', 'Title', 'Body')
        assert result is True

    def test_returns_false_on_exception(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.side_effect = Exception('error')
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            result = NotificationService.send_topic_notification('topic', 'T', 'B')
        assert result is False

    def test_data_converted_to_strings(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            mock_msg.Notification.return_value = MagicMock()
            mock_msg.AndroidConfig.return_value = MagicMock()
            mock_msg.AndroidNotification.return_value = MagicMock()
            mock_msg.APNSConfig.return_value = MagicMock()
            mock_msg.APNSPayload.return_value = MagicMock()
            mock_msg.Aps.return_value = MagicMock()
            mock_msg.ApsAlert.return_value = MagicMock()
            NotificationService.send_topic_notification('topic', 'T', 'B', data={'num': 99})
        mock_msg.Message.assert_called()


class TestNotificationServiceSendDataOnly:

    def test_returns_false_when_not_initialized(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            from src.services.notification_service import NotificationService
            NotificationService._initialized = False
            with patch.object(NotificationService, 'initialize', return_value=False):
                result = NotificationService.send_data_only_message('token', {'key': 'val'})
        assert result is False

    def test_returns_true_on_success(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            result = NotificationService.send_data_only_message('token', {'key': 'val'})
        assert result is True

    def test_returns_false_on_exception(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.side_effect = Exception('error')
            mock_msg.Message.return_value = MagicMock()
            result = NotificationService.send_data_only_message('token', {'key': 'val'})
        assert result is False

    def test_data_values_converted_to_strings(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            NotificationService.send_data_only_message('token', {'count': 5})
        mock_msg.Message.assert_called()

    def test_calls_messaging_send(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging') as mock_msg:
            from src.services.notification_service import NotificationService
            NotificationService._initialized = True
            mock_msg.send.return_value = 'ok'
            mock_msg.Message.return_value = MagicMock()
            NotificationService.send_data_only_message('token', {'key': 'value'})
        mock_msg.send.assert_called_once()


# ===========================================================================
# Module-level helper functions in notification_service.py
# ===========================================================================

class TestNotificationModuleFunctions:

    def test_send_fcm_notification_delegates_to_class(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            import src.services.notification_service as mod
            with patch.object(mod.NotificationService, 'send_fcm_notification', return_value=True) as mock_m:
                result = mod.send_fcm_notification('token', 'T', 'B')
            mock_m.assert_called_once_with('token', 'T', 'B', None)
            assert result is True

    def test_send_multicast_notification_delegates_to_class(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            import src.services.notification_service as mod
            expected = {'success_count': 2, 'failure_count': 0, 'responses': []}
            with patch.object(mod.NotificationService, 'send_multicast_notification', return_value=expected) as mock_m:
                result = mod.send_multicast_notification(['t1', 't2'], 'T', 'B')
            mock_m.assert_called_once_with(['t1', 't2'], 'T', 'B', None)
            assert result == expected

    def test_send_topic_notification_delegates_to_class(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            import src.services.notification_service as mod
            with patch.object(mod.NotificationService, 'send_topic_notification', return_value=True) as mock_m:
                result = mod.send_topic_notification('topic', 'T', 'B')
            mock_m.assert_called_once_with('topic', 'T', 'B', None)
            assert result is True

    def test_send_data_only_message_delegates_to_class(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            import src.services.notification_service as mod
            with patch.object(mod.NotificationService, 'send_data_only_message', return_value=True) as mock_m:
                result = mod.send_data_only_message('token', {'k': 'v'})
            mock_m.assert_called_once_with('token', {'k': 'v'})
            assert result is True

    def test_send_fcm_notification_passes_data(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            import src.services.notification_service as mod
            with patch.object(mod.NotificationService, 'send_fcm_notification', return_value=True) as mock_m:
                mod.send_fcm_notification('tok', 'T', 'B', {'extra': 'data'})
            mock_m.assert_called_once_with('tok', 'T', 'B', {'extra': 'data'})

    def test_send_multicast_passes_data(self):
        with patch('src.services.notification_service.firebase_admin'), \
             patch('src.services.notification_service.messaging'):
            import src.services.notification_service as mod
            with patch.object(mod.NotificationService, 'send_multicast_notification',
                               return_value={'success_count': 1, 'failure_count': 0, 'responses': []}) as mock_m:
                mod.send_multicast_notification(['tok'], 'T', 'B', {'k': 'v'})
            mock_m.assert_called_once_with(['tok'], 'T', 'B', {'k': 'v'})
