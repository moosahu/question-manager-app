# tests/unit/test_gamification_helper.py
"""
Unit tests for src/services/gamification_helper.py
Covers pure-logic functions and mocked DB interactions.
"""

import sys
import os
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta, date

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy third-party modules before anything else is imported
# ---------------------------------------------------------------------------
for _mod in ('firebase_admin', 'firebase_admin.credentials', 'firebase_admin.messaging'):
    sys.modules.setdefault(_mod, MagicMock())

_google_mock = MagicMock()
sys.modules['google'] = _google_mock
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()

# flask_socketio shim
sys.modules.setdefault('flask_socketio', MagicMock())

# sqlalchemy shims for PostgreSQL types
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as _pg
_pg.ARRAY = lambda *args, **kwargs: Text()
_pg.JSONB = JSON

import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ===========================================================================
# Helpers
# ===========================================================================

def _import_module():
    """Import gamification_helper with DB mocked out."""
    with patch('src.extensions.db', MagicMock()):
        import src.services.gamification_helper as mod
    return mod


# ===========================================================================
# 1. calculate_level_from_points – PURE LOGIC
# ===========================================================================

class TestCalculateLevelFromPoints:
    """No mocking required – pure function."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        mod = _import_module()
        self.fn = mod.calculate_level_from_points

    def test_zero_points_returns_level_1(self):
        assert self.fn(0) == 1

    def test_one_point_returns_level_1(self):
        assert self.fn(1) == 1

    def test_99_points_returns_level_1(self):
        assert self.fn(99) == 1

    def test_100_points_returns_level_2(self):
        assert self.fn(100) == 2

    def test_101_points_returns_level_2(self):
        assert self.fn(101) == 2

    def test_249_points_returns_level_2(self):
        assert self.fn(249) == 2

    def test_250_points_returns_level_3(self):
        assert self.fn(250) == 3

    def test_251_points_returns_level_3(self):
        assert self.fn(251) == 3

    def test_499_points_returns_level_3(self):
        assert self.fn(499) == 3

    def test_500_points_returns_level_4(self):
        assert self.fn(500) == 4

    def test_501_points_returns_level_4(self):
        assert self.fn(501) == 4

    def test_999_points_returns_level_4(self):
        assert self.fn(999) == 4

    def test_1000_points_returns_level_5(self):
        assert self.fn(1000) == 5

    def test_1001_points_returns_level_5(self):
        assert self.fn(1001) == 5

    def test_large_points_returns_level_5(self):
        assert self.fn(99999) == 5

    def test_negative_points_returns_level_1(self):
        # Edge case: negative points should still give level 1
        assert self.fn(-10) == 1


# ===========================================================================
# 2. calculate_level_threshold – PURE LOGIC
# ===========================================================================

class TestCalculateLevelThreshold:
    """No mocking required – pure function."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        mod = _import_module()
        self.fn = mod.calculate_level_threshold

    def test_level_1_threshold_is_0(self):
        assert self.fn(1) == 0

    def test_level_2_threshold_is_100(self):
        assert self.fn(2) == 100

    def test_level_3_threshold_is_250(self):
        assert self.fn(3) == 250

    def test_level_4_threshold_is_500(self):
        assert self.fn(4) == 500

    def test_level_5_threshold_is_1000(self):
        assert self.fn(5) == 1000

    def test_level_6_returns_default_1000(self):
        # Key not in thresholds dict → returns 1000 (dict.get default)
        assert self.fn(6) == 1000

    def test_level_10_returns_default_1000(self):
        assert self.fn(10) == 1000

    def test_level_0_returns_default_1000(self):
        # Level 0 is not in dict → default
        assert self.fn(0) == 1000


# ===========================================================================
# 3. format_gamification_section – PURE LOGIC (dict manipulation)
# ===========================================================================

class TestFormatGamificationSection:
    """Pure logic – no DB/AI mocking required."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        mod = _import_module()
        self.fn = mod.format_gamification_section

    def _full_data(self):
        return {
            'points': 350,
            'level': 3,
            'rank': 5,
            'total_students': 100,
            'recent_achievements': [
                {'title': 'نجم الأسبوع', 'description': 'desc', 'points': 50, 'icon': '⭐', 'unlocked_at': '2024-01-01T00:00:00'},
                {'title': 'متحمس', 'description': 'desc2', 'points': 20, 'icon': '🔥', 'unlocked_at': '2024-01-02T00:00:00'},
            ],
            'active_challenges': [
                {
                    'id': 1,
                    'title': 'حل 10 أسئلة',
                    'description': 'تحدي اليوم',
                    'target': 10,
                    'progress': 5,
                    'completed': False,
                    'points': 100,
                    'type': 'quiz'
                }
            ],
            'next_level_points': 500,
            'points_to_next_level': 150,
            'streak_days': 5,
        }

    def test_returns_string(self):
        result = self.fn(self._full_data())
        assert isinstance(result, str)

    def test_contains_points(self):
        result = self.fn(self._full_data())
        assert '350' in result

    def test_contains_level(self):
        result = self.fn(self._full_data())
        assert '3' in result

    def test_contains_rank(self):
        result = self.fn(self._full_data())
        assert '#5' in result

    def test_contains_total_students(self):
        result = self.fn(self._full_data())
        assert '100' in result

    def test_contains_achievement_title(self):
        result = self.fn(self._full_data())
        assert 'نجم الأسبوع' in result

    def test_contains_challenge_title(self):
        result = self.fn(self._full_data())
        assert 'حل 10 أسئلة' in result

    def test_streak_shown_when_gte_3(self):
        data = self._full_data()
        data['streak_days'] = 3
        result = self.fn(data)
        assert '3' in result

    def test_streak_not_shown_when_lt_3(self):
        data = self._full_data()
        data['streak_days'] = 2
        result = self.fn(data)
        # The streak section only appears when streak_days >= 3
        assert 'سلسلة' not in result

    def test_rank_zero_shows_jadeed(self):
        data = self._full_data()
        data['rank'] = 0
        result = self.fn(data)
        assert 'جديد' in result

    def test_level_5_shows_max_level_message(self):
        data = self._full_data()
        data['level'] = 5
        data['points_to_next_level'] = 0
        result = self.fn(data)
        assert 'المستوى الأقصى' in result or 'النخبة' in result

    def test_no_achievements_skips_achievements_section(self):
        data = self._full_data()
        data['recent_achievements'] = []
        result = self.fn(data)
        assert 'إنجازات جديدة' not in result

    def test_no_active_challenges_skips_challenge_section(self):
        data = self._full_data()
        data['active_challenges'] = []
        result = self.fn(data)
        assert 'تحدي اليوم' not in result

    def test_completed_challenge_not_shown(self):
        data = self._full_data()
        data['active_challenges'][0]['completed'] = True
        result = self.fn(data)
        # Completed challenges are filtered out
        assert 'حل 10 أسئلة' not in result

    def test_progress_bar_included_for_next_level(self):
        data = self._full_data()
        result = self.fn(data)
        assert '█' in result or '░' in result

    def test_sections_joined_by_double_newline(self):
        data = self._full_data()
        result = self.fn(data)
        assert '\n\n' in result

    def test_achievement_points_shown(self):
        data = self._full_data()
        result = self.fn(data)
        # +50 نقطة for first achievement
        assert '+50' in result

    def test_only_first_two_achievements_shown(self):
        data = self._full_data()
        data['recent_achievements'].append({
            'title': 'إنجاز ثالث', 'description': 'desc', 'points': 10,
            'icon': '🏅', 'unlocked_at': '2024-01-03T00:00:00'
        })
        result = self.fn(data)
        # Third achievement should NOT appear (limit is 2)
        assert 'إنجاز ثالث' not in result


# ===========================================================================
# 4. get_compact_gamification_text – PURE LOGIC
# ===========================================================================

class TestGetCompactGamificationText:
    """Pure logic – no DB/AI mocking required."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        mod = _import_module()
        self.fn = mod.get_compact_gamification_text

    def _full_data(self):
        return {
            'points': 500,
            'level': 4,
            'rank': 3,
            'total_students': 50,
            'streak_days': 7,
        }

    def test_returns_string(self):
        result = self.fn(self._full_data())
        assert isinstance(result, str)

    def test_points_shown_when_positive(self):
        result = self.fn(self._full_data())
        assert '500' in result

    def test_level_shown_when_gt_1(self):
        result = self.fn(self._full_data())
        assert '4' in result

    def test_rank_shown_when_in_top_10(self):
        result = self.fn(self._full_data())
        assert '#3' in result

    def test_streak_shown_when_gte_3(self):
        result = self.fn(self._full_data())
        assert '7' in result

    def test_empty_when_all_zeros(self):
        data = {'points': 0, 'level': 1, 'rank': 0, 'total_students': 0, 'streak_days': 0}
        result = self.fn(data)
        assert result == ''

    def test_points_zero_not_shown(self):
        data = self._full_data()
        data['points'] = 0
        result = self.fn(data)
        assert '💎' not in result

    def test_level_1_not_shown(self):
        data = self._full_data()
        data['level'] = 1
        result = self.fn(data)
        assert '⭐' not in result

    def test_rank_11_not_shown(self):
        data = self._full_data()
        data['rank'] = 11
        result = self.fn(data)
        assert '🏆' not in result

    def test_rank_10_is_shown(self):
        data = self._full_data()
        data['rank'] = 10
        result = self.fn(data)
        assert '🏆' in result

    def test_streak_2_not_shown(self):
        data = self._full_data()
        data['streak_days'] = 2
        result = self.fn(data)
        assert '🔥' not in result

    def test_parts_joined_by_bullet(self):
        result = self.fn(self._full_data())
        assert ' • ' in result

    def test_single_part_no_bullet(self):
        data = {'points': 0, 'level': 2, 'rank': 0, 'total_students': 0, 'streak_days': 0}
        result = self.fn(data)
        assert ' • ' not in result


# ===========================================================================
# 5. get_student_gamification_data – mocked DB queries
# ===========================================================================

class TestGetStudentGamificationData:
    """DB calls are mocked; tests verify default values and structure."""

    def _import_and_patch(self):
        """Returns (module, mock_db) with all DB models mocked."""
        mock_db = MagicMock()
        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=mock_db),
        }):
            # Re-import with fresh patches
            if 'src.services.gamification_helper' in sys.modules:
                del sys.modules['src.services.gamification_helper']
            with patch('src.extensions.db', mock_db):
                import src.services.gamification_helper as mod
        return mod, mock_db

    def _make_mock_student_points(self, total_points=0):
        sp = MagicMock()
        sp.total_points = total_points
        return sp

    def test_returns_dict_on_db_error(self):
        """When DB raises, returns safe defaults."""
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.models.gamification.StudentPoints', create=True) as mock_sp_cls:
            mock_sp_cls.query.filter_by.return_value.first.side_effect = Exception('DB error')
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(1)
        assert isinstance(result, dict)

    def test_default_points_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['points'] == 0

    def test_default_level_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['level'] == 1

    def test_default_rank_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['rank'] == 0

    def test_default_streak_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['streak_days'] == 0

    def test_default_next_level_points_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['next_level_points'] == 100

    def test_default_achievements_empty_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['recent_achievements'] == []

    def test_default_challenges_empty_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(99)
        assert result['active_challenges'] == []

    def test_all_required_keys_present_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(1)
        required = {'points', 'level', 'rank', 'total_students', 'recent_achievements',
                    'active_challenges', 'next_level_points', 'streak_days'}
        assert required.issubset(result.keys())

    def test_points_to_next_level_key_present_on_error(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.get_student_gamification_data(1)
        assert 'points_to_next_level' in result


# ===========================================================================
# 6. calculate_streak – mocked DB
# ===========================================================================

class TestCalculateStreak:
    """Mock StudentResult DB queries to verify streak logic."""

    def setup_method(self):
        """Ensure src.models.student_result is mocked to prevent import failures
        when src.extensions is replaced by another test file's module-level mock."""
        self._prev_sr = sys.modules.get('src.models.student_result')
        mock_sr_mod = MagicMock()
        mock_sr_mod.StudentResult = MagicMock()
        sys.modules['src.models.student_result'] = mock_sr_mod

    def teardown_method(self):
        if self._prev_sr is None:
            sys.modules.pop('src.models.student_result', None)
        else:
            sys.modules['src.models.student_result'] = self._prev_sr

    def _make_date_result(self, d):
        """Create a mock query result row with a .date attribute."""
        r = MagicMock()
        r.date = d
        return r

    def test_returns_zero_when_no_results(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []
            result = mod.calculate_streak(1)
        assert result == 0

    def test_returns_zero_on_exception(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = Exception('DB error')
            result = mod.calculate_streak(1)
        assert result == 0

    def test_streak_one_when_quiz_today(self):
        mod = _import_module()
        today = datetime.utcnow().date()
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 12, 0, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_result(today)
            ]
            result = mod.calculate_streak(1)
        assert result == 1

    def test_streak_one_when_quiz_yesterday(self):
        mod = _import_module()
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 12, 0, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_result(yesterday)
            ]
            result = mod.calculate_streak(1)
        assert result == 1

    def test_streak_two_consecutive_days(self):
        mod = _import_module()
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 12, 0, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_result(today),
                self._make_date_result(yesterday),
            ]
            result = mod.calculate_streak(1)
        assert result == 2

    def test_streak_breaks_on_gap(self):
        mod = _import_module()
        today = datetime.utcnow().date()
        three_days_ago = today - timedelta(days=3)
        # Gap of 2+ days between today and 3 days ago; yesterday and two_days_ago are missing.
        # First result (today): matches current_date → streak=1, current_date becomes today-1
        # Second result (3 days ago): checks vs (today-1) or (today-2). Neither matches → break.
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 12, 0, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_result(today),
                self._make_date_result(three_days_ago),
            ]
            result = mod.calculate_streak(1)
        assert result == 1

    def test_streak_three_consecutive_days(self):
        mod = _import_module()
        today = datetime.utcnow().date()
        days = [today - timedelta(days=i) for i in range(3)]
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 12, 0, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_result(d) for d in days
            ]
            result = mod.calculate_streak(1)
        assert result == 3

    def test_returns_integer(self):
        mod = _import_module()
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []
            result = mod.calculate_streak(42)
        assert isinstance(result, int)
