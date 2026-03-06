"""
Unit tests for src/services/smart_notifications.py
Coverage target: ≥ 70 tests
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock, call

# ---------------------------------------------------------------------------
# Bootstrap: make sure the project root is on the path and all heavy deps
# are replaced with mocks BEFORE importing the module under test.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---- external deps that are not installed in the test virtualenv ----------
for _mod in [
    'firebase_admin',
    'firebase_admin.credentials',
    'firebase_admin.messaging',
    'firebase_admin.auth',
    'flask_socketio',
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---- patch every internal import that the module needs --------------------
# We patch at the sys.modules level so that when smart_notifications.py does
#   "from src.models.notification import Notification, StudentNotification"
# it gets our MagicMock objects instead of real SQLAlchemy models.

_mock_notification_module    = MagicMock()
_mock_ai_analysis_module     = MagicMock()
_mock_student_module         = MagicMock()
_mock_notification_service_m = MagicMock()
_mock_extensions             = MagicMock()
_mock_gamification_helper    = MagicMock()

# Expose named symbols that the module imports
_mock_notification_module.Notification      = MagicMock()
_mock_notification_module.StudentNotification = MagicMock()

_mock_ai_analysis_module.AIAnalysis = MagicMock()
_mock_ai_analysis_module.AIAction   = MagicMock()
_mock_ai_analysis_module.AILog      = MagicMock()
_mock_ai_analysis_module.AISetting  = MagicMock()

_mock_student_module.Student = MagicMock()

_mock_notification_service_m.NotificationService = MagicMock()

_mock_extensions.db = MagicMock()

_mock_gamification_helper.get_student_gamification_data = MagicMock(return_value=None)
_mock_gamification_helper.format_gamification_section   = MagicMock(return_value='')
_mock_gamification_helper.get_compact_gamification_text = MagicMock(return_value='')

sys.modules['src.models.notification']       = _mock_notification_module
sys.modules['src.models.ai_analysis']        = _mock_ai_analysis_module
sys.modules['src.models.student']            = _mock_student_module
sys.modules['src.services.notification_service'] = _mock_notification_service_m
sys.modules['src.extensions']               = _mock_extensions
sys.modules['src.services.gamification_helper'] = _mock_gamification_helper

# Now it is safe to import the module under test
import src.services.smart_notifications as sn
from src.services.smart_notifications import (
    get_time_of_day,
    is_weekend,
    MESSAGE_TEMPLATES,
    SmartNotificationService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analysis(**kwargs):
    """Build a MagicMock that resembles an AIAnalysis object."""
    defaults = dict(
        id=42,
        student_id=1,
        suggested_action='send_message',
        student_status='needs_attention',
        severity_level='orange',
        average_score=65.0,
        days_since_last_quiz=5,
        issues_detected=['low_score'],
        performance_trend='stable',
        ai_recommendations=None,
    )
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ===========================================================================
# TestGetTimeOfDay
# ===========================================================================
class TestGetTimeOfDay(unittest.TestCase):
    """Tests for the module-level get_time_of_day() function."""

    def _patch_hour(self, hour):
        mock_dt = MagicMock()
        mock_dt.now.return_value.hour = hour
        return patch('src.services.smart_notifications.datetime', mock_dt)

    # --- morning: 6 ≤ hour < 12 ---
    def test_morning_at_6(self):
        with self._patch_hour(6):
            self.assertEqual(get_time_of_day(), 'morning')

    def test_morning_at_9(self):
        with self._patch_hour(9):
            self.assertEqual(get_time_of_day(), 'morning')

    def test_morning_at_11(self):
        with self._patch_hour(11):
            self.assertEqual(get_time_of_day(), 'morning')

    # --- afternoon: 12 ≤ hour < 17 ---
    def test_afternoon_at_12(self):
        with self._patch_hour(12):
            self.assertEqual(get_time_of_day(), 'afternoon')

    def test_afternoon_at_14(self):
        with self._patch_hour(14):
            self.assertEqual(get_time_of_day(), 'afternoon')

    def test_afternoon_at_16(self):
        with self._patch_hour(16):
            self.assertEqual(get_time_of_day(), 'afternoon')

    # --- evening: 17 ≤ hour < 22 ---
    def test_evening_at_17(self):
        with self._patch_hour(17):
            self.assertEqual(get_time_of_day(), 'evening')

    def test_evening_at_19(self):
        with self._patch_hour(19):
            self.assertEqual(get_time_of_day(), 'evening')

    def test_evening_at_21(self):
        with self._patch_hour(21):
            self.assertEqual(get_time_of_day(), 'evening')

    # --- night: hour < 6 OR hour >= 22 ---
    def test_night_at_22(self):
        with self._patch_hour(22):
            self.assertEqual(get_time_of_day(), 'night')

    def test_night_at_0(self):
        with self._patch_hour(0):
            self.assertEqual(get_time_of_day(), 'night')

    def test_night_at_5(self):
        with self._patch_hour(5):
            self.assertEqual(get_time_of_day(), 'night')

    def test_night_at_23(self):
        with self._patch_hour(23):
            self.assertEqual(get_time_of_day(), 'night')

    def test_returns_string(self):
        with self._patch_hour(8):
            result = get_time_of_day()
        self.assertIsInstance(result, str)

    def test_boundary_afternoon_starts_at_12(self):
        # hour 11 → morning, hour 12 → afternoon
        with self._patch_hour(11):
            r1 = get_time_of_day()
        with self._patch_hour(12):
            r2 = get_time_of_day()
        self.assertEqual(r1, 'morning')
        self.assertEqual(r2, 'afternoon')


# ===========================================================================
# TestIsWeekend
# ===========================================================================
class TestIsWeekend(unittest.TestCase):
    """Tests for the module-level is_weekend() function."""

    def _patch_weekday(self, day):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = day
        return patch('src.services.smart_notifications.datetime', mock_dt)

    def test_saturday_is_weekend(self):
        with self._patch_weekday(5):
            self.assertTrue(is_weekend())

    def test_sunday_is_weekend(self):
        with self._patch_weekday(6):
            self.assertTrue(is_weekend())

    def test_monday_is_not_weekend(self):
        with self._patch_weekday(0):
            self.assertFalse(is_weekend())

    def test_tuesday_is_not_weekend(self):
        with self._patch_weekday(1):
            self.assertFalse(is_weekend())

    def test_wednesday_is_not_weekend(self):
        with self._patch_weekday(2):
            self.assertFalse(is_weekend())

    def test_thursday_is_not_weekend(self):
        with self._patch_weekday(3):
            self.assertFalse(is_weekend())

    def test_friday_is_not_weekend(self):
        with self._patch_weekday(4):
            self.assertFalse(is_weekend())

    def test_returns_bool(self):
        with self._patch_weekday(0):
            result = is_weekend()
        self.assertIsInstance(result, bool)


# ===========================================================================
# TestMessageTemplates
# ===========================================================================
class TestMessageTemplates(unittest.TestCase):
    """Tests for the MESSAGE_TEMPLATES dict."""

    def test_templates_is_dict(self):
        self.assertIsInstance(MESSAGE_TEMPLATES, dict)

    def test_statuses_present(self):
        for status in ('excellent', 'good', 'needs_attention', 'critical'):
            with self.subTest(status=status):
                self.assertIn(status, MESSAGE_TEMPLATES)

    def test_each_status_has_time_keys(self):
        for status, times in MESSAGE_TEMPLATES.items():
            with self.subTest(status=status):
                self.assertIn('morning',   times)
                self.assertIn('afternoon', times)
                self.assertIn('evening',   times)
                self.assertIn('weekend',   times)

    def test_each_list_non_empty(self):
        for status, times in MESSAGE_TEMPLATES.items():
            for period, msgs in times.items():
                with self.subTest(status=status, period=period):
                    self.assertIsInstance(msgs, list)
                    self.assertGreater(len(msgs), 0)

    def test_templates_most_contain_name_placeholder(self):
        """Most (>50%) template strings contain {name} for formatting."""
        total, with_name = 0, 0
        for status, times in MESSAGE_TEMPLATES.items():
            for period, msgs in times.items():
                for msg in msgs:
                    total += 1
                    if '{name}' in msg:
                        with_name += 1
        self.assertGreater(with_name, total // 2)

    def test_excellent_morning_list_type(self):
        self.assertIsInstance(MESSAGE_TEMPLATES['excellent']['morning'], list)

    def test_critical_weekend_list_type(self):
        self.assertIsInstance(MESSAGE_TEMPLATES['critical']['weekend'], list)


# ===========================================================================
# TestSmartNotificationServiceInit
# ===========================================================================
class TestSmartNotificationServiceInit(unittest.TestCase):
    """Tests for SmartNotificationService.__init__()"""

    def test_init_creates_instance(self):
        with patch('src.services.smart_notifications.NotificationService') as MockNS:
            svc = SmartNotificationService()
        self.assertIsNotNone(svc)

    def test_init_calls_notification_service(self):
        with patch('src.services.smart_notifications.NotificationService') as MockNS:
            svc = SmartNotificationService()
        MockNS.assert_called_once()

    def test_init_sets_fcm_service(self):
        mock_ns_instance = MagicMock()
        with patch('src.services.smart_notifications.NotificationService',
                   return_value=mock_ns_instance):
            svc = SmartNotificationService()
        self.assertIs(svc.fcm_service, mock_ns_instance)


# ===========================================================================
# TestProcessAnalysisResult
# ===========================================================================
class TestProcessAnalysisResult(unittest.TestCase):
    """Tests for SmartNotificationService.process_analysis_result()"""

    def _make_service(self):
        with patch('src.services.smart_notifications.NotificationService'):
            return SmartNotificationService()

    # --- no_action ---
    def test_no_action_returns_false(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='no_action')

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = True
            result = svc.process_analysis_result(analysis)

        self.assertFalse(result)

    def test_no_action_does_not_call_send_smart_message(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='no_action')
        svc._send_smart_message = MagicMock()

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = True
            svc.process_analysis_result(analysis)

        svc._send_smart_message.assert_not_called()

    # --- send_message ---
    def test_send_message_calls_send_smart_message_when_enabled(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='send_message')
        svc._send_smart_message = MagicMock(return_value=True)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = lambda key, default=None: True
            result = svc.process_analysis_result(analysis)

        svc._send_smart_message.assert_called_once_with(analysis)
        self.assertTrue(result)

    def test_send_message_returns_false_when_disabled(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='send_message')
        svc._send_smart_message = MagicMock(return_value=True)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            # auto_messages disabled, alerts enabled
            MockAS.get_setting.side_effect = lambda key, default=None: (
                False if key == 'enable_auto_messages' else True
            )
            result = svc.process_analysis_result(analysis)

        svc._send_smart_message.assert_not_called()
        self.assertFalse(result)

    # --- admin_alert ---
    def test_admin_alert_calls_send_admin_alert_when_enabled(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='admin_alert')
        svc._send_admin_alert = MagicMock(return_value=True)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = lambda key, default=None: True
            result = svc.process_analysis_result(analysis)

        svc._send_admin_alert.assert_called_once_with(analysis)
        self.assertTrue(result)

    def test_admin_alert_skipped_when_disabled(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='admin_alert')
        svc._send_admin_alert = MagicMock(return_value=True)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = lambda key, default=None: (
                False if key == 'enable_admin_alerts' else True
            )
            result = svc.process_analysis_result(analysis)

        svc._send_admin_alert.assert_not_called()
        self.assertFalse(result)

    # --- send_message_and_alert ---
    def test_send_message_and_alert_calls_both(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='send_message_and_alert')
        svc._send_smart_message = MagicMock(return_value=True)
        svc._send_admin_alert   = MagicMock(return_value=True)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = lambda key, default=None: True
            result = svc.process_analysis_result(analysis)

        svc._send_smart_message.assert_called_once_with(analysis)
        svc._send_admin_alert.assert_called_once_with(analysis)
        self.assertTrue(result)

    def test_send_message_and_alert_only_alert_when_messages_disabled(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='send_message_and_alert')
        svc._send_smart_message = MagicMock(return_value=False)
        svc._send_admin_alert   = MagicMock(return_value=True)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = lambda key, default=None: (
                False if key == 'enable_auto_messages' else True
            )
            result = svc.process_analysis_result(analysis)

        svc._send_smart_message.assert_not_called()
        svc._send_admin_alert.assert_called_once()
        self.assertTrue(result)

    def test_send_message_and_alert_both_disabled_returns_false(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='send_message_and_alert')
        svc._send_smart_message = MagicMock(return_value=False)
        svc._send_admin_alert   = MagicMock(return_value=False)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = False
            result = svc.process_analysis_result(analysis)

        svc._send_smart_message.assert_not_called()
        svc._send_admin_alert.assert_not_called()
        self.assertFalse(result)

    def test_exception_returns_false(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action='send_message')

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = RuntimeError('db gone')
            result = svc.process_analysis_result(analysis)

        self.assertFalse(result)

    def test_suggested_action_none_treated_as_no_action(self):
        svc = self._make_service()
        analysis = _make_analysis(suggested_action=None)

        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = True
            result = svc.process_analysis_result(analysis)

        self.assertFalse(result)


# ===========================================================================
# TestCanSendMessage
# ===========================================================================
class TestCanSendMessage(unittest.TestCase):
    """Tests for SmartNotificationService._can_send_message()"""

    def _make_service(self):
        with patch('src.services.smart_notifications.NotificationService'):
            return SmartNotificationService()

    class _FakeCol:
        """SQLAlchemy-like column stub that supports comparison operators."""
        def __eq__(self, other): return True
        def __ge__(self, other): return True
        def __le__(self, other): return True
        def __gt__(self, other): return True
        def __lt__(self, other): return True
        def __ne__(self, other): return True

    def _patch_aiaction(self, count_value):
        """Patch AIAction with a fake that avoids MagicMock comparison issues."""
        mock_aa = MagicMock()
        mock_aa.student_id = self._FakeCol()
        mock_aa.action_type = self._FakeCol()
        mock_aa.message_sent = self._FakeCol()
        mock_aa.message_sent_at = self._FakeCol()
        mock_aa.query.filter.return_value.count.return_value = count_value
        return patch.object(sn, 'AIAction', mock_aa)

    def test_can_send_when_below_limit(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = 3
            with self._patch_aiaction(0):
                result = svc._can_send_message(1)
        self.assertTrue(result)

    def test_cannot_send_when_at_limit(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = 3
            with self._patch_aiaction(3):
                result = svc._can_send_message(1)
        self.assertFalse(result)

    def test_cannot_send_when_above_limit(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = 3
            with self._patch_aiaction(5):
                result = svc._can_send_message(1)
        self.assertFalse(result)

    def test_allows_send_on_exception(self):
        """If any error occurs, default to allowing the message."""
        svc = self._make_service()
        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.side_effect = Exception('db error')
            result = svc._can_send_message(99)
        self.assertTrue(result)

    def test_limit_of_1_allows_first_message(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = 1
            with self._patch_aiaction(0):
                result = svc._can_send_message(1)
        self.assertTrue(result)

    def test_limit_of_1_blocks_second_message(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.AISetting') as MockAS:
            MockAS.get_setting.return_value = 1
            with self._patch_aiaction(1):
                result = svc._can_send_message(1)
        self.assertFalse(result)


# ===========================================================================
# TestGenerateMessageContent
# ===========================================================================
class TestGenerateMessageContent(unittest.TestCase):
    """Tests for SmartNotificationService._generate_message_content()"""

    def _make_service(self):
        with patch('src.services.smart_notifications.NotificationService'):
            return SmartNotificationService()

    def _mock_student(self, name='أحمد'):
        mock = MagicMock()
        mock.name = name
        return mock

    def _patch_env(self, hour=9, weekday=0, student=None):
        """Return a context manager stack for common patches."""
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            mock_dt = MagicMock()
            mock_dt.now.return_value.hour = hour
            mock_dt.now.return_value.weekday.return_value = weekday
            mock_dt.utcnow.return_value = MagicMock()

            stu = student or self._mock_student()

            with patch('src.services.smart_notifications.datetime', mock_dt), \
                 patch('src.services.smart_notifications.Student') as MockStu, \
                 patch('src.services.smart_notifications.GAMIFICATION_AVAILABLE', False):
                MockStu.query.get.return_value = stu
                yield MockStu, stu

        return _ctx()

    # --- excellent ---
    def test_excellent_returns_tuple(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='excellent', average_score=95.0)
        with self._patch_env(hour=9):
            title, body = svc._generate_message_content(analysis)
        self.assertIsInstance(title, str)
        self.assertIsInstance(body, str)

    def test_excellent_body_contains_score(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='excellent', average_score=95.0)
        with self._patch_env(hour=9):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('95.0', body)

    def test_excellent_title_contains_student_name(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='excellent', average_score=95.0)
        stu = self._mock_student('محمد')
        with self._patch_env(hour=9, student=stu):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('محمد', title)

    # --- good ---
    def test_good_returns_tuple(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='good', average_score=75.0)
        with self._patch_env(hour=14):
            title, body = svc._generate_message_content(analysis)
        self.assertIsInstance(title, str)
        self.assertIsInstance(body, str)

    def test_good_body_contains_score(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='good', average_score=75.0)
        with self._patch_env(hour=14):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('75.0', body)

    # --- needs_attention (declining) ---
    def test_needs_attention_declining_body(self):
        svc = self._make_service()
        analysis = _make_analysis(
            student_status='needs_attention',
            performance_trend='declining',
            average_score=55.0,
        )
        with self._patch_env(hour=19):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('55.0', body)

    # --- needs_attention (stable / inactive) ---
    def test_needs_attention_stable_body_contains_days(self):
        svc = self._make_service()
        analysis = _make_analysis(
            student_status='needs_attention',
            performance_trend='stable',
            days_since_last_quiz=7,
        )
        with self._patch_env(hour=19):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('7', body)

    # --- critical ---
    def test_critical_body_contains_days(self):
        svc = self._make_service()
        analysis = _make_analysis(
            student_status='critical',
            days_since_last_quiz=14,
        )
        with self._patch_env(hour=9):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('14', body)

    def test_critical_returns_tuple(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='critical')
        with self._patch_env(hour=9):
            result = svc._generate_message_content(analysis)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    # --- student not found (None) ---
    def test_student_not_found_uses_fallback_name(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='needs_attention')

        mock_dt = MagicMock()
        mock_dt.now.return_value.hour = 9
        mock_dt.now.return_value.weekday.return_value = 0
        mock_dt.utcnow.return_value = MagicMock()

        with patch('src.services.smart_notifications.datetime', mock_dt), \
             patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.GAMIFICATION_AVAILABLE', False):
            MockStu.query.get.return_value = None
            title, body = svc._generate_message_content(analysis)

        # fallback name is 'الطالب'
        self.assertIsNotNone(title)

    # --- weekend template used on Saturday ---
    def test_weekend_template_used_on_saturday(self):
        svc = self._make_service()
        analysis = _make_analysis(student_status='excellent', average_score=90.0)

        mock_dt = MagicMock()
        mock_dt.now.return_value.hour = 9
        mock_dt.now.return_value.weekday.return_value = 5  # Saturday
        mock_dt.utcnow.return_value = MagicMock()

        stu = self._mock_student('خالد')
        with patch('src.services.smart_notifications.datetime', mock_dt), \
             patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.GAMIFICATION_AVAILABLE', False):
            MockStu.query.get.return_value = stu
            title, body = svc._generate_message_content(analysis)

        # title must contain the student name
        self.assertIn('خالد', title)

    # --- ai_recommendations appended ---
    def test_ai_recommendations_appended_to_body(self):
        svc = self._make_service()
        analysis = _make_analysis(
            student_status='needs_attention',
            performance_trend='stable',
            days_since_last_quiz=3,
            ai_recommendations='راجع الفصل الأول',
        )
        with self._patch_env(hour=10):
            title, body = svc._generate_message_content(analysis)
        self.assertIn('راجع الفصل الأول', body)

    # --- greeting stripped from ai_recommendations ---
    def test_greeting_stripped_from_ai_recommendations(self):
        svc = self._make_service()
        stu = self._mock_student('سعيد')
        analysis = _make_analysis(
            student_status='critical',
            days_since_last_quiz=10,
            ai_recommendations='مرحباً سعيد، استمر في المراجعة',
        )
        mock_dt = MagicMock()
        mock_dt.now.return_value.hour = 9
        mock_dt.now.return_value.weekday.return_value = 0
        mock_dt.utcnow.return_value = MagicMock()

        with patch('src.services.smart_notifications.datetime', mock_dt), \
             patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.GAMIFICATION_AVAILABLE', False):
            MockStu.query.get.return_value = stu
            title, body = svc._generate_message_content(analysis)

        # The greeting prefix should have been stripped
        self.assertNotIn('مرحباً سعيد،', body)
        self.assertIn('استمر في المراجعة', body)


# ===========================================================================
# TestSendBulkNotification
# ===========================================================================
class TestSendBulkNotification(unittest.TestCase):
    """Tests for SmartNotificationService.send_bulk_notification()"""

    def _make_service(self):
        with patch('src.services.smart_notifications.NotificationService'):
            svc = SmartNotificationService()
        svc.fcm_service = MagicMock()
        return svc

    def _build_patches(self, students=None, fcm_result=None):
        """Returns a context manager that patches db, Student, Notification, etc."""
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            mock_notif = MagicMock()
            mock_notif.id = 100

            mock_student_notif = MagicMock()

            _students = students or []

            mock_db = MagicMock()

            with patch('src.services.smart_notifications.db', mock_db), \
                 patch('src.services.smart_notifications.Notification',
                       return_value=mock_notif) as MockN, \
                 patch('src.services.smart_notifications.StudentNotification',
                       return_value=mock_student_notif), \
                 patch('src.services.smart_notifications.Student') as MockStu, \
                 patch('src.services.smart_notifications.AILog'):
                MockStu.query.filter.return_value.all.return_value = _students
                yield mock_db, MockN, MockStu

        return _ctx()

    def test_returns_dict(self):
        svc = self._make_service()
        svc.fcm_service.send_multicast_notification = MagicMock(return_value=None)
        with self._build_patches():
            result = svc.send_bulk_notification([1, 2], 'Title', 'Body')
        self.assertIsInstance(result, dict)

    def test_returns_notification_id(self):
        svc = self._make_service()
        svc.fcm_service.send_multicast_notification = MagicMock(return_value=None)
        with self._build_patches():
            result = svc.send_bulk_notification([1, 2], 'Title', 'Body')
        self.assertIn('notification_id', result)

    def test_returns_students_count(self):
        svc = self._make_service()
        svc.fcm_service.send_multicast_notification = MagicMock(return_value=None)
        with self._build_patches():
            result = svc.send_bulk_notification([1, 2, 3], 'T', 'B')
        self.assertEqual(result['students_count'], 3)

    def test_fcm_sent_when_tokens_present(self):
        svc = self._make_service()
        stu1 = MagicMock()
        stu1.fcm_token = 'token_abc'
        svc.fcm_service.send_multicast_notification = MagicMock(
            return_value={'success_count': 1, 'failure_count': 0}
        )
        with self._build_patches(students=[stu1]):
            result = svc.send_bulk_notification([1], 'T', 'B')
        svc.fcm_service.send_multicast_notification.assert_called_once()
        self.assertEqual(result['fcm_sent'], 1)

    def test_fcm_not_called_when_no_tokens(self):
        svc = self._make_service()
        stu1 = MagicMock()
        stu1.fcm_token = None
        svc.fcm_service.send_multicast_notification = MagicMock()
        with self._build_patches(students=[stu1]):
            svc.send_bulk_notification([1], 'T', 'B')
        svc.fcm_service.send_multicast_notification.assert_not_called()

    def test_long_body_truncated_for_fcm(self):
        """A body > 3000 chars should be truncated in the FCM call."""
        svc = self._make_service()
        stu1 = MagicMock()
        stu1.fcm_token = 'tok'
        long_body = 'أ' * 3500
        svc.fcm_service.send_multicast_notification = MagicMock(
            return_value={'success_count': 1, 'failure_count': 0}
        )
        with self._build_patches(students=[stu1]):
            svc.send_bulk_notification([1], 'T', long_body)

        called_body = svc.fcm_service.send_multicast_notification.call_args[0][2]
        self.assertLessEqual(len(called_body), 3100)  # truncated + suffix
        self.assertIn('[المزيد', called_body)

    def test_exception_returns_error_dict(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.db') as mock_db, \
             patch('src.services.smart_notifications.Notification',
                   side_effect=Exception('boom')), \
             patch('src.services.smart_notifications.AILog'):
            result = svc.send_bulk_notification([1], 'T', 'B')
        self.assertIn('error', result)
        self.assertEqual(result['students_count'], 0)


# ===========================================================================
# TestSendAchievementNotification
# ===========================================================================
class TestSendAchievementNotification(unittest.TestCase):
    """Tests for SmartNotificationService.send_achievement_notification()"""

    def _make_service(self):
        with patch('src.services.smart_notifications.NotificationService'):
            svc = SmartNotificationService()
        svc.fcm_service = MagicMock()
        return svc

    def _sample_achievement(self):
        return {
            'icon': '🏆',
            'title': 'إنجاز رائع',
            'description': 'أكملت 10 اختبارات',
            'points': 50,
            'achievement_type': 'quiz_master',
        }

    def _patch_env(self, student=None):
        import contextlib
        @contextlib.contextmanager
        def _ctx():
            mock_notif = MagicMock()
            mock_notif.id = 200
            mock_stu_notif = MagicMock()
            stu = student or MagicMock(fcm_token='tok', name='علي')

            mock_gam_svc = MagicMock()
            mock_gam_svc.get_student_points.return_value = {'total_points': 300}

            with patch('src.services.smart_notifications.Student') as MockStu, \
                 patch('src.services.smart_notifications.db'), \
                 patch('src.services.smart_notifications.Notification', return_value=mock_notif), \
                 patch('src.services.smart_notifications.StudentNotification', return_value=mock_stu_notif), \
                 patch('src.services.gamification_service.gamification_service', mock_gam_svc, create=True), \
                 patch.dict('sys.modules', {'src.services.gamification_service': MagicMock(gamification_service=mock_gam_svc)}):
                MockStu.query.get.return_value = stu
                yield MockStu, stu

        return _ctx()

    def test_returns_true_on_success(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock(return_value=True)
        with self._patch_env():
            result = svc.send_achievement_notification(1, self._sample_achievement())
        self.assertTrue(result)

    def test_returns_false_when_student_not_found(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.db'), \
             patch.dict('sys.modules', {'src.services.gamification_service': MagicMock()}):
            MockStu.query.get.return_value = None
            result = svc.send_achievement_notification(999, self._sample_achievement())
        self.assertFalse(result)

    def test_fcm_called_when_token_present(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock(return_value=True)
        with self._patch_env():
            svc.send_achievement_notification(1, self._sample_achievement())
        svc.fcm_service.send_fcm_notification.assert_called_once()

    def test_fcm_not_called_when_no_token(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock()
        stu = MagicMock(fcm_token=None, name='بلا توكن')
        with self._patch_env(student=stu):
            svc.send_achievement_notification(1, self._sample_achievement())
        svc.fcm_service.send_fcm_notification.assert_not_called()

    def test_exception_returns_false(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.db'), \
             patch.dict('sys.modules', {'src.services.gamification_service': MagicMock()}):
            MockStu.query.get.side_effect = Exception('db crash')
            result = svc.send_achievement_notification(1, self._sample_achievement())
        self.assertFalse(result)


# ===========================================================================
# TestSendChallengeNotification
# ===========================================================================
class TestSendChallengeNotification(unittest.TestCase):
    """Tests for SmartNotificationService.send_challenge_notification()"""

    def _make_service(self):
        with patch('src.services.smart_notifications.NotificationService'):
            svc = SmartNotificationService()
        svc.fcm_service = MagicMock()
        return svc

    def _sample_challenge(self):
        return {
            'id': 7,
            'icon': '⚡',
            'title': 'تحدي اليوم',
            'description': 'أكمل 3 اختبارات',
            'points': 30,
        }

    def _patch_env(self, student=None):
        import contextlib
        @contextlib.contextmanager
        def _ctx():
            mock_notif = MagicMock()
            mock_notif.id = 300
            mock_stu_notif = MagicMock()
            stu = student or MagicMock(fcm_token='tok_ch', name='زيد')

            with patch('src.services.smart_notifications.Student') as MockStu, \
                 patch('src.services.smart_notifications.db'), \
                 patch('src.services.smart_notifications.Notification', return_value=mock_notif), \
                 patch('src.services.smart_notifications.StudentNotification', return_value=mock_stu_notif):
                MockStu.query.get.return_value = stu
                yield MockStu, stu

        return _ctx()

    def test_returns_true_on_success(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock(return_value=True)
        with self._patch_env():
            result = svc.send_challenge_notification(1, self._sample_challenge())
        self.assertTrue(result)

    def test_returns_false_when_student_not_found(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.db'):
            MockStu.query.get.return_value = None
            result = svc.send_challenge_notification(999, self._sample_challenge())
        self.assertFalse(result)

    def test_fcm_called_when_token_present(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock(return_value=True)
        with self._patch_env():
            svc.send_challenge_notification(1, self._sample_challenge())
        svc.fcm_service.send_fcm_notification.assert_called_once()

    def test_fcm_not_called_when_no_token(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock()
        stu = MagicMock(fcm_token=None, name='بلا توكن')
        with self._patch_env(student=stu):
            svc.send_challenge_notification(1, self._sample_challenge())
        svc.fcm_service.send_fcm_notification.assert_not_called()

    def test_exception_returns_false(self):
        svc = self._make_service()
        with patch('src.services.smart_notifications.Student') as MockStu, \
             patch('src.services.smart_notifications.db'):
            MockStu.query.get.side_effect = Exception('crash')
            result = svc.send_challenge_notification(1, self._sample_challenge())
        self.assertFalse(result)

    def test_body_contains_challenge_title(self):
        """The notification body should embed the challenge title."""
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock(return_value=True)
        challenge = self._sample_challenge()

        with self._patch_env():
            svc.send_challenge_notification(1, challenge)

        # Inspect what body was passed to FCM
        call_args = svc.fcm_service.send_fcm_notification.call_args[0]
        body_arg = call_args[2]
        self.assertIn('تحدي اليوم', body_arg)

    def test_challenge_points_appear_in_fcm_body(self):
        svc = self._make_service()
        svc.fcm_service.send_fcm_notification = MagicMock(return_value=True)
        challenge = self._sample_challenge()  # points = 30

        with self._patch_env():
            svc.send_challenge_notification(1, challenge)

        call_args = svc.fcm_service.send_fcm_notification.call_args[0]
        body_arg = call_args[2]
        self.assertIn('30', body_arg)


# ===========================================================================
# TestModuleLevelInstance
# ===========================================================================
class TestModuleLevelInstance(unittest.TestCase):
    """Verify that the module exposes a singleton smart_notifications instance."""

    def test_smart_notifications_instance_exists(self):
        self.assertIsNotNone(sn.smart_notifications)

    def test_smart_notifications_is_service(self):
        self.assertIsInstance(sn.smart_notifications, SmartNotificationService)

    def test_smart_notifications_has_fcm_service(self):
        self.assertTrue(hasattr(sn.smart_notifications, 'fcm_service'))


# ===========================================================================
# TestOldMessageTemplates
# ===========================================================================
class TestOldMessageTemplates(unittest.TestCase):
    """Sanity checks on the legacy OLD_MESSAGE_TEMPLATES dict."""

    def test_old_templates_exist(self):
        self.assertTrue(hasattr(sn, 'OLD_MESSAGE_TEMPLATES'))

    def test_old_templates_has_morning_key(self):
        self.assertIn('morning', sn.OLD_MESSAGE_TEMPLATES)

    def test_old_templates_orange_in_morning(self):
        self.assertIn('orange', sn.OLD_MESSAGE_TEMPLATES['morning'])

    def test_old_templates_red_in_evening(self):
        self.assertIn('red', sn.OLD_MESSAGE_TEMPLATES['evening'])


if __name__ == '__main__':
    unittest.main()
