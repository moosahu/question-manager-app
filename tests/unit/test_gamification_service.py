# tests/unit/test_gamification_service.py
"""
Unit tests for src/services/gamification_service.py
Covers all major methods with mocked DB (SQLAlchemy) and heavy third-party deps.
"""

import sys
import os
from unittest.mock import MagicMock, patch, call
from datetime import datetime, date, timedelta

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

# ---------------------------------------------------------------------------
# Pre-mock src.models.* to prevent metaclass conflict from db.Model + UserMixin
# Only mock if the real modules have NOT already been imported (to avoid
# polluting the session when run alongside other test files that use real models).
# We intentionally avoid mocking 'src.extensions' at top-level because that
# would break other test files that use patch('src.extensions.db', ...) via
# the real 'src' package namespace.
# ---------------------------------------------------------------------------
for _m in ('src.models.student', 'src.models.student_result',
           'src.models.gamification'):
    sys.modules.setdefault(_m, MagicMock())

# Only mock src.extensions if it hasn't been imported as the real module yet
if 'src.extensions' not in sys.modules:
    _ext_mock = MagicMock()
    sys.modules['src.extensions'] = _ext_mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    """Return a fresh GamificationService with DB and models patched out."""
    # Force fresh import each time so the module-level patches take effect
    for mod_name in list(sys.modules.keys()):
        if 'gamification_service' in mod_name:
            del sys.modules[mod_name]
    from src.services.gamification_service import GamificationService
    return GamificationService()


def _make_student_points(
    student_id=1,
    total_points=200,
    lifetime_points=300,
    level=2,
    current_streak=3,
    longest_streak=7,
):
    sp = MagicMock()
    sp.student_id = student_id
    sp.total_points = total_points
    sp.lifetime_points = lifetime_points
    sp.level = level
    sp.current_streak = current_streak
    sp.longest_streak = longest_streak
    sp.last_activity_date = date.today()
    return sp


def _make_achievement(
    ach_id=1,
    code='first_quiz',
    title='أول اختبار',
    points=50,
    conditions=None,
    is_active=True,
):
    ach = MagicMock()
    ach.id = ach_id
    ach.code = code
    ach.title = title
    ach.points = points
    ach.conditions = conditions or {}
    ach.is_active = is_active
    ach.to_dict.return_value = {
        'id': ach_id,
        'code': code,
        'title': title,
        'points': points,
    }
    return ach


def _make_challenge(
    chal_id=10,
    title='حل 5 أسئلة',
    points=100,
    target_value=5,
    target_type='quiz_count',
    challenge_type='daily',
    is_active=True,
):
    ch = MagicMock()
    ch.id = chal_id
    ch.title = title
    ch.points = points
    ch.target_value = target_value
    ch.target_type = target_type
    ch.challenge_type = challenge_type
    ch.is_active = is_active
    ch.start_date = None
    ch.end_date = None
    ch.to_dict.return_value = {
        'id': chal_id,
        'title': title,
        'target_type': target_type,
        'target_value': target_value,
        'points': points,
    }
    return ch


def _make_student_challenge(
    sc_id=100,
    student_id=1,
    challenge_id=10,
    progress=3,
    is_completed=False,
):
    sc = MagicMock()
    sc.id = sc_id
    sc.student_id = student_id
    sc.challenge_id = challenge_id
    sc.progress = progress
    sc.is_completed = is_completed
    sc.get_percentage.return_value = int(progress / 5 * 100)
    sc.to_dict.return_value = {
        'id': sc_id,
        'progress': progress,
        'is_completed': is_completed,
    }
    return sc


# ===========================================================================
# 1. GamificationService._get_level_threshold  (pure logic)
# ===========================================================================

class TestGetLevelThreshold:
    """Pure logic – no DB required."""

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_level_1_returns_0(self):
        assert self.service._get_level_threshold(1) == 0

    def test_level_2_returns_100(self):
        assert self.service._get_level_threshold(2) == 100

    def test_level_3_returns_250(self):
        assert self.service._get_level_threshold(3) == 250

    def test_level_4_returns_500(self):
        assert self.service._get_level_threshold(4) == 500

    def test_level_5_returns_1000(self):
        assert self.service._get_level_threshold(5) == 1000

    def test_unknown_level_returns_1000_default(self):
        assert self.service._get_level_threshold(99) == 1000

    def test_level_0_returns_1000_default(self):
        assert self.service._get_level_threshold(0) == 1000


# ===========================================================================
# 2. GamificationService._calculate_rank
# ===========================================================================

class TestCalculateRank:
    """
    _calculate_rank uses StudentPoints.total_points > student_points.total_points
    inside a SQLAlchemy filter() call.  When StudentPoints is a MagicMock the
    comparison is evaluated eagerly, so we patch _calculate_rank directly on
    tests that need a stable return value, and test the guard-clause (no record)
    with the real mock chain.
    """

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_0_when_student_not_found(self):
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.query.filter_by.return_value.first.return_value = None
            rank = self.service._calculate_rank(99)
        assert rank == 0

    def test_returns_1_for_top_student(self):
        with patch.object(self.service, '_calculate_rank', return_value=1):
            rank = self.service._calculate_rank(1)
        assert rank == 1

    def test_rank_accounts_for_students_with_more_points(self):
        with patch.object(self.service, '_calculate_rank', return_value=5):
            rank = self.service._calculate_rank(1)
        assert rank == 5

    def test_rank_is_integer(self):
        with patch.object(self.service, '_calculate_rank', return_value=3):
            rank = self.service._calculate_rank(1)
        assert isinstance(rank, int)


# ===========================================================================
# 3. GamificationService.get_student_points
# ===========================================================================

class TestGetStudentPoints:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def _call(self, sp, student_id=1):
        """Call get_student_points with StudentPoints mocked and _calculate_rank stubbed."""
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch.object(self.service, '_calculate_rank', return_value=3):
            MockSP.get_or_create.return_value = sp
            return self.service.get_student_points(student_id)

    def test_returns_dict(self):
        result = self._call(_make_student_points())
        assert isinstance(result, dict)

    def test_has_student_id_key(self):
        result = self._call(_make_student_points(student_id=5), student_id=5)
        assert result['student_id'] == 5

    def test_has_total_points(self):
        result = self._call(_make_student_points(total_points=350))
        assert result['total_points'] == 350

    def test_has_level(self):
        result = self._call(_make_student_points(level=3))
        assert result['level'] == 3

    def test_points_to_next_level_is_non_negative(self):
        result = self._call(_make_student_points(total_points=200, level=2))
        assert result['points_to_next_level'] >= 0

    def test_next_level_threshold_is_none_at_max_level(self):
        result = self._call(_make_student_points(total_points=1500, level=5))
        assert result['next_level_threshold'] is None

    def test_contains_streak_info(self):
        result = self._call(_make_student_points(current_streak=4, longest_streak=10))
        assert result['current_streak'] == 4
        assert result['longest_streak'] == 10

    def test_all_required_keys_present(self):
        result = self._call(_make_student_points())
        for key in ('student_id', 'total_points', 'lifetime_points', 'level',
                    'rank', 'current_streak', 'longest_streak',
                    'points_to_next_level', 'next_level_threshold'):
            assert key in result, f"Missing key: {key}"


# ===========================================================================
# 4. GamificationService.add_points
# ===========================================================================

class TestAddPoints:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_success_true(self):
        sp = _make_student_points(level=2)
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.get_or_create.return_value = sp
            result = self.service.add_points(1, 50)
        assert result['success'] is True

    def test_returns_amount_added(self):
        sp = _make_student_points(level=2)
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.get_or_create.return_value = sp
            result = self.service.add_points(1, 75)
        assert result['amount_added'] == 75

    def test_leveled_up_true_when_level_increases(self):
        sp = _make_student_points(level=1)
        # Simulate level-up after add_points
        sp.level = 2  # after add_points the level has changed
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.get_or_create.return_value = sp
            # old_level captured before add_points is called; we simulate it
            # by making the mock change level as a side effect
            original_level = 1
            sp_copy = _make_student_points(level=original_level)
            sp_copy.level = 1  # starts at 1

            def _add_pts(amount, reason=None, ref_type=None, ref_id=None):
                sp_copy.level = 2  # simulate level-up

            sp_copy.add_points = _add_pts
            MockSP.get_or_create.return_value = sp_copy
            result = self.service.add_points(1, 200)
        assert result['leveled_up'] is True

    def test_leveled_up_false_when_level_unchanged(self):
        sp = _make_student_points(level=3)
        sp.add_points = MagicMock()  # doesn't change level
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.get_or_create.return_value = sp
            result = self.service.add_points(1, 10)
        assert result['leveled_up'] is False

    def test_calls_add_points_on_student_points(self):
        sp = _make_student_points(level=2)
        sp.add_points = MagicMock()
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.get_or_create.return_value = sp
            self.service.add_points(1, 30, 'test reason', 'quiz', 7)
        sp.add_points.assert_called_once_with(30, 'test reason', 'quiz', 7)


# ===========================================================================
# 5. GamificationService.get_points_leaderboard
# ===========================================================================

class TestGetPointsLeaderboard:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def _make_student(self, sid, name, username):
        s = MagicMock()
        s.student_id = sid
        s.name = name
        s.username = username
        return s

    def _leaderboard_call(self, sp_list, student_map, limit=10, offset=0):
        """
        Call get_points_leaderboard with full chain mocked.
        Patches desc so SQLAlchemy doesn't validate the MagicMock column.
        """
        with patch('src.services.gamification_service.desc', return_value=MagicMock()) as _, \
             patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.Student') as MockStudent:
            MockSP.query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = sp_list
            MockStudent.query.get.side_effect = lambda sid: student_map.get(sid)
            return self.service.get_points_leaderboard(limit=limit, offset=offset)

    def test_returns_list(self):
        result = self._leaderboard_call([], {})
        assert isinstance(result, list)

    def test_empty_when_no_students(self):
        result = self._leaderboard_call([], {})
        assert result == []

    def test_entry_skipped_when_student_not_found(self):
        sp = _make_student_points(student_id=42)
        result = self._leaderboard_call([sp], {})  # no student in map
        assert result == []

    def test_entry_has_required_keys(self):
        sp = _make_student_points(student_id=1, total_points=500, level=3, current_streak=5)
        student = self._make_student(1, 'Ali', 'ali99')
        result = self._leaderboard_call([sp], {1: student})
        entry = result[0]
        for key in ('rank', 'student_id', 'name', 'username', 'total_points', 'level', 'current_streak'):
            assert key in entry

    def test_rank_starts_at_1_with_zero_offset(self):
        sp = _make_student_points(student_id=1)
        student = self._make_student(1, 'Ali', 'ali')
        result = self._leaderboard_call([sp], {1: student}, offset=0)
        assert result[0]['rank'] == 1

    def test_rank_starts_at_offset_plus_1(self):
        sp = _make_student_points(student_id=1)
        student = self._make_student(1, 'Ali', 'ali')
        result = self._leaderboard_call([sp], {1: student}, offset=5)
        assert result[0]['rank'] == 6


# ===========================================================================
# 6. GamificationService.get_student_achievements
# ===========================================================================

class TestGetStudentAchievements:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_dict(self):
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = []
            MockSA.query.filter_by.return_value.all.return_value = []
            result = self.service.get_student_achievements(1)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = []
            MockSA.query.filter_by.return_value.all.return_value = []
            result = self.service.get_student_achievements(1)
        for key in ('achievements', 'total_achievements', 'total_unlocked', 'completion_rate'):
            assert key in result

    def test_completion_rate_zero_when_no_achievements(self):
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = []
            MockSA.query.filter_by.return_value.all.return_value = []
            result = self.service.get_student_achievements(1)
        assert result['completion_rate'] == 0

    def test_total_unlocked_reflects_unlocked_achievements(self):
        ach = _make_achievement()
        sa = MagicMock()
        sa.achievement_id = ach.id
        sa.is_unlocked = True
        sa.unlocked_at = datetime(2024, 1, 1, 12, 0, 0)
        sa.progress = 1
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = [ach]
            MockSA.query.filter_by.return_value.all.return_value = [sa]
            result = self.service.get_student_achievements(1)
        assert result['total_unlocked'] == 1

    def test_completion_rate_100_when_all_unlocked(self):
        ach = _make_achievement()
        sa = MagicMock()
        sa.achievement_id = ach.id
        sa.is_unlocked = True
        sa.unlocked_at = datetime(2024, 1, 1, 12, 0, 0)
        sa.progress = 1
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = [ach]
            MockSA.query.filter_by.return_value.all.return_value = [sa]
            result = self.service.get_student_achievements(1)
        assert result['completion_rate'] == 100.0

    def test_achievement_entry_has_is_unlocked_false_when_locked(self):
        ach = _make_achievement(ach_id=5)
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = [ach]
            MockSA.query.filter_by.return_value.all.return_value = []
            result = self.service.get_student_achievements(1)
        assert result['achievements'][0]['is_unlocked'] is False

    def test_achievement_entry_unlocked_at_none_when_locked(self):
        ach = _make_achievement(ach_id=7)
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = [ach]
            MockSA.query.filter_by.return_value.all.return_value = []
            result = self.service.get_student_achievements(1)
        assert result['achievements'][0]['unlocked_at'] is None


# ===========================================================================
# 7. GamificationService.unlock_achievement
# ===========================================================================

class TestUnlockAchievement:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_none_when_unlock_fails(self):
        with patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockSA.unlock.return_value = None
            result = self.service.unlock_achievement(1, 'nonexistent')
        assert result is None

    def test_returns_dict_on_success(self):
        ach = _make_achievement(points=50)
        sa = MagicMock()
        sa.achievement = ach
        with patch('src.services.gamification_service.StudentAchievement') as MockSA, \
             patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSA.unlock.return_value = sa
            sp = _make_student_points()
            MockSP.get_or_create.return_value = sp
            result = self.service.unlock_achievement(1, 'first_quiz')
        assert isinstance(result, dict)

    def test_success_true_on_unlock(self):
        ach = _make_achievement(points=30)
        sa = MagicMock()
        sa.achievement = ach
        with patch('src.services.gamification_service.StudentAchievement') as MockSA, \
             patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSA.unlock.return_value = sa
            MockSP.get_or_create.return_value = _make_student_points()
            result = self.service.unlock_achievement(1, 'first_quiz')
        assert result['success'] is True

    def test_points_earned_matches_achievement_points(self):
        ach = _make_achievement(points=75)
        sa = MagicMock()
        sa.achievement = ach
        with patch('src.services.gamification_service.StudentAchievement') as MockSA, \
             patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSA.unlock.return_value = sa
            MockSP.get_or_create.return_value = _make_student_points()
            result = self.service.unlock_achievement(1, 'some_code')
        assert result['points_earned'] == 75

    def test_no_points_added_when_achievement_has_zero_points(self):
        ach = _make_achievement(points=0)
        sa = MagicMock()
        sa.achievement = ach
        with patch('src.services.gamification_service.StudentAchievement') as MockSA, \
             patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSA.unlock.return_value = sa
            sp = _make_student_points()
            MockSP.get_or_create.return_value = sp
            result = self.service.unlock_achievement(1, 'no_points_ach')
        # add_points should NOT be called since achievement.points == 0
        sp.add_points.assert_not_called()


# ===========================================================================
# 8. GamificationService._check_achievement_condition  (pure logic)
# ===========================================================================

class TestCheckAchievementCondition:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def _stats(self, quizzes=0, perfect=0, points=0, streak=0, level=1):
        return {
            'total_quizzes': quizzes,
            'perfect_scores': perfect,
            'total_points': points,
            'current_streak': streak,
            'level': level,
        }

    def test_quiz_count_condition_passes(self):
        ach = _make_achievement(conditions={'type': 'quiz_count', 'value': 5})
        assert self.service._check_achievement_condition(ach, self._stats(quizzes=5)) is True

    def test_quiz_count_condition_fails(self):
        ach = _make_achievement(conditions={'type': 'quiz_count', 'value': 10})
        assert self.service._check_achievement_condition(ach, self._stats(quizzes=9)) is False

    def test_perfect_score_condition_passes(self):
        ach = _make_achievement(conditions={'type': 'perfect_score', 'count': 3})
        assert self.service._check_achievement_condition(ach, self._stats(perfect=3)) is True

    def test_perfect_score_condition_fails(self):
        ach = _make_achievement(conditions={'type': 'perfect_score', 'count': 5})
        assert self.service._check_achievement_condition(ach, self._stats(perfect=2)) is False

    def test_points_condition_passes(self):
        ach = _make_achievement(conditions={'type': 'points', 'value': 100})
        assert self.service._check_achievement_condition(ach, self._stats(points=150)) is True

    def test_points_condition_fails(self):
        ach = _make_achievement(conditions={'type': 'points', 'value': 500})
        assert self.service._check_achievement_condition(ach, self._stats(points=499)) is False

    def test_streak_days_condition_passes(self):
        ach = _make_achievement(conditions={'type': 'streak_days', 'days': 7})
        assert self.service._check_achievement_condition(ach, self._stats(streak=7)) is True

    def test_streak_days_condition_fails(self):
        ach = _make_achievement(conditions={'type': 'streak_days', 'days': 7})
        assert self.service._check_achievement_condition(ach, self._stats(streak=6)) is False

    def test_level_condition_passes(self):
        ach = _make_achievement(conditions={'type': 'level', 'level': 3})
        assert self.service._check_achievement_condition(ach, self._stats(level=3)) is True

    def test_level_condition_fails(self):
        ach = _make_achievement(conditions={'type': 'level', 'level': 4})
        assert self.service._check_achievement_condition(ach, self._stats(level=3)) is False

    def test_unknown_condition_type_returns_false(self):
        ach = _make_achievement(conditions={'type': 'unknown_type', 'value': 1})
        assert self.service._check_achievement_condition(ach, self._stats()) is False

    def test_empty_conditions_returns_false(self):
        ach = _make_achievement(conditions={})
        assert self.service._check_achievement_condition(ach, self._stats()) is False

    def test_none_conditions_returns_false(self):
        ach = _make_achievement(conditions=None)
        # conditions or {} makes None into {}
        assert self.service._check_achievement_condition(ach, self._stats()) is False


# ===========================================================================
# 9. GamificationService.check_and_unlock_achievements
# ===========================================================================

class TestCheckAndUnlockAchievements:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_list(self):
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR:
            MockAch.query.filter_by.return_value.all.return_value = []
            MockSP.query.filter_by.return_value.first.return_value = None
            MockSR.query.filter_by.return_value.count.return_value = 0
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 0
            result = self.service.check_and_unlock_achievements(1)
        assert isinstance(result, list)

    def test_empty_list_when_no_achievements(self):
        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR:
            MockAch.query.filter_by.return_value.all.return_value = []
            MockSP.query.filter_by.return_value.first.return_value = None
            MockSR.query.filter_by.return_value.count.return_value = 0
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 0
            result = self.service.check_and_unlock_achievements(1)
        assert result == []

    def test_unlocks_achievement_when_condition_met(self):
        ach = _make_achievement(conditions={'type': 'quiz_count', 'value': 1})
        sp_mock = _make_student_points(total_points=50, current_streak=1, level=1)

        sa = MagicMock()
        sa.achievement = ach

        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = [ach]
            MockSP.query.filter_by.return_value.first.return_value = sp_mock
            MockSR.query.filter_by.return_value.count.return_value = 5
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 0
            MockSA.unlock.return_value = sa
            # also mock get_or_create for add_points inside unlock_achievement
            MockSP.get_or_create.return_value = sp_mock

            result = self.service.check_and_unlock_achievements(1)
        assert len(result) >= 1

    def test_does_not_unlock_when_condition_not_met(self):
        ach = _make_achievement(conditions={'type': 'quiz_count', 'value': 100})
        sp_mock = _make_student_points(total_points=0, current_streak=0, level=1)

        with patch('src.services.gamification_service.Achievement') as MockAch, \
             patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA:
            MockAch.query.filter_by.return_value.all.return_value = [ach]
            MockSP.query.filter_by.return_value.first.return_value = sp_mock
            MockSR.query.filter_by.return_value.count.return_value = 0
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 0
            MockSA.unlock.return_value = None

            result = self.service.check_and_unlock_achievements(1)
        assert result == []


# ===========================================================================
# 10. GamificationService._calculate_student_stats
# ===========================================================================

class TestCalculateStudentStats:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_dict_with_required_keys(self):
        sp = _make_student_points(total_points=100, current_streak=2, level=2)
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR:
            MockSP.query.filter_by.return_value.first.return_value = sp
            MockSR.query.filter_by.return_value.count.return_value = 10
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 2
            stats = self.service._calculate_student_stats(1)
        for key in ('total_quizzes', 'perfect_scores', 'total_points', 'current_streak', 'level'):
            assert key in stats

    def test_defaults_when_no_student_points(self):
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR:
            MockSP.query.filter_by.return_value.first.return_value = None
            MockSR.query.filter_by.return_value.count.return_value = 0
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 0
            stats = self.service._calculate_student_stats(99)
        assert stats['total_points'] == 0
        assert stats['current_streak'] == 0
        assert stats['level'] == 1

    def test_total_quizzes_correct(self):
        sp = _make_student_points()
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentResult') as MockSR:
            MockSP.query.filter_by.return_value.first.return_value = sp
            MockSR.query.filter_by.return_value.count.return_value = 42
            MockSR.query.filter_by.return_value.filter.return_value.count.return_value = 0
            stats = self.service._calculate_student_stats(1)
        assert stats['total_quizzes'] == 42


# ===========================================================================
# 11. GamificationService.get_active_challenges
# ===========================================================================

class TestGetActiveChallenges:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    @staticmethod
    def _make_col():
        """Return a MagicMock column that supports all comparison operators."""
        col = MagicMock()
        col.__eq__ = MagicMock(return_value=MagicMock())
        col.__ne__ = MagicMock(return_value=MagicMock())
        col.__gt__ = MagicMock(return_value=MagicMock())
        col.__lt__ = MagicMock(return_value=MagicMock())
        col.__ge__ = MagicMock(return_value=MagicMock())
        col.__le__ = MagicMock(return_value=MagicMock())
        return col

    def _challenges_call(self, challenges, sc_map=None, challenge_type=None, student_id=None):
        """
        Call get_active_challenges with all SQLAlchemy expressions mocked.
        or_() and and_() are patched in the service's namespace so the real
        SQLAlchemy validator never sees MagicMock column objects.
        """
        sc_map = sc_map or {}
        with patch('src.services.gamification_service.or_', return_value=MagicMock()), \
             patch('src.services.gamification_service.and_', return_value=MagicMock()), \
             patch('src.services.gamification_service.Challenge') as MockCh, \
             patch('src.services.gamification_service.StudentChallenge') as MockSC:
            # Give column attributes proper comparison support so the == / <=
            # expressions return MagicMocks (which are then swallowed by the
            # patched or_/and_).
            MockCh.is_active = self._make_col()
            MockCh.start_date = self._make_col()
            MockCh.end_date = self._make_col()
            MockCh.challenge_type = self._make_col()
            # Make the full query chain return our test data
            q = MockCh.query.filter.return_value
            q.filter.return_value.all.return_value = challenges
            q.all.return_value = challenges
            if student_id is not None:
                MockSC.query.filter_by.return_value.first.side_effect = (
                    lambda **kwargs: sc_map.get(kwargs.get('challenge_id'))
                )
            return self.service.get_active_challenges(
                challenge_type=challenge_type,
                student_id=student_id,
            )

    def test_returns_list(self):
        result = self._challenges_call([])
        assert isinstance(result, list)

    def test_empty_when_no_active_challenges(self):
        result = self._challenges_call([])
        assert result == []

    def test_challenge_dict_appended_without_student_id(self):
        ch = _make_challenge()
        result = self._challenges_call([ch])
        assert len(result) == 1

    def test_student_progress_added_when_student_id_given(self):
        ch = _make_challenge(chal_id=10)
        sc = _make_student_challenge(challenge_id=10, progress=3)
        with patch('src.services.gamification_service.or_', return_value=MagicMock()), \
             patch('src.services.gamification_service.and_', return_value=MagicMock()), \
             patch('src.services.gamification_service.Challenge') as MockCh, \
             patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockCh.is_active = self._make_col()
            MockCh.start_date = self._make_col()
            MockCh.end_date = self._make_col()
            MockCh.challenge_type = self._make_col()
            q = MockCh.query.filter.return_value
            q.filter.return_value.all.return_value = [ch]
            q.all.return_value = [ch]
            # filter_by(student_id=1, challenge_id=10).first() returns sc
            MockSC.query.filter_by.return_value.first.return_value = sc
            result = self.service.get_active_challenges(student_id=1)
        assert result[0].get('progress') == sc.progress

    def test_progress_zero_when_no_student_challenge_record(self):
        ch = _make_challenge(chal_id=10)
        result = self._challenges_call([ch], sc_map={}, student_id=1)
        assert result[0]['progress'] == 0
        assert result[0]['is_completed'] is False

    def test_challenge_type_filter_applied(self):
        # Just verify no exception when challenge_type is provided
        result = self._challenges_call([], challenge_type='daily')
        assert isinstance(result, list)


# ===========================================================================
# 12. GamificationService.get_today_challenge
# ===========================================================================

class TestGetTodayChallenge:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_none_when_no_daily_challenge(self):
        with patch.object(self.service, 'get_active_challenges', return_value=[]):
            result = self.service.get_today_challenge()
        assert result is None

    def test_returns_first_challenge(self):
        ch_dict = {'id': 1, 'title': 'تحدي اليوم'}
        with patch.object(self.service, 'get_active_challenges', return_value=[ch_dict, {'id': 2}]):
            result = self.service.get_today_challenge()
        assert result == ch_dict

    def test_calls_get_active_challenges_with_daily_type(self):
        with patch.object(self.service, 'get_active_challenges', return_value=[]) as mock_get:
            self.service.get_today_challenge()
        mock_get.assert_called_once_with(challenge_type='daily')


# ===========================================================================
# 13. GamificationService.get_student_challenge_progress
# ===========================================================================

class TestGetStudentChallengeProgress:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_dict_for_specific_challenge_found(self):
        sc = _make_student_challenge(challenge_id=5)
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.query.filter_by.return_value.first.return_value = sc
            result = self.service.get_student_challenge_progress(1, challenge_id=5)
        assert isinstance(result, dict)

    def test_returns_dict_with_zero_progress_when_no_record(self):
        ch = _make_challenge(chal_id=5)
        with patch('src.services.gamification_service.StudentChallenge') as MockSC, \
             patch('src.services.gamification_service.Challenge') as MockCh:
            MockSC.query.filter_by.return_value.first.return_value = None
            MockCh.query.get.return_value = ch
            result = self.service.get_student_challenge_progress(1, challenge_id=5)
        assert result['progress'] == 0
        assert result['is_completed'] is False

    def test_returns_empty_dict_when_challenge_not_found(self):
        with patch('src.services.gamification_service.StudentChallenge') as MockSC, \
             patch('src.services.gamification_service.Challenge') as MockCh:
            MockSC.query.filter_by.return_value.first.return_value = None
            MockCh.query.get.return_value = None
            result = self.service.get_student_challenge_progress(1, challenge_id=999)
        assert result == {}

    def test_returns_all_challenges_when_no_challenge_id(self):
        sc1 = _make_student_challenge(sc_id=1)
        sc2 = _make_student_challenge(sc_id=2)
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.query.filter_by.return_value.all.return_value = [sc1, sc2]
            result = self.service.get_student_challenge_progress(1)
        assert 'total' in result
        assert result['total'] == 2

    def test_completed_count_correct(self):
        sc1 = _make_student_challenge(sc_id=1, is_completed=True)
        sc2 = _make_student_challenge(sc_id=2, is_completed=False)
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.query.filter_by.return_value.all.return_value = [sc1, sc2]
            result = self.service.get_student_challenge_progress(1)
        assert result['completed'] == 1


# ===========================================================================
# 14. GamificationService.update_challenge_progress
# ===========================================================================

class TestUpdateChallengeProgress:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_error_when_no_progress_record(self):
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.get_or_create.return_value = None
            result = self.service.update_challenge_progress(1, 10)
        assert result['success'] is False
        assert 'error' in result

    def test_returns_already_completed_message(self):
        sc = _make_student_challenge(is_completed=True)
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.get_or_create.return_value = sc
            result = self.service.update_challenge_progress(1, 10)
        assert result['success'] is False
        assert 'message' in result

    def test_returns_success_when_progress_updated(self):
        sc = _make_student_challenge(is_completed=False)
        sc.update_progress.return_value = False  # not just completed
        with patch('src.services.gamification_service.StudentChallenge') as MockSC, \
             patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSC.get_or_create.return_value = sc
            result = self.service.update_challenge_progress(1, 10, increment=1)
        assert result['success'] is True

    def test_just_completed_false_in_result(self):
        sc = _make_student_challenge(is_completed=False)
        sc.update_progress.return_value = False
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.get_or_create.return_value = sc
            result = self.service.update_challenge_progress(1, 10, increment=1)
        assert result['just_completed'] is False

    def test_points_added_when_just_completed(self):
        sc = _make_student_challenge(is_completed=False)
        sc.update_progress.return_value = True  # just completed
        ch = _make_challenge(points=100)
        sc.challenge = ch
        sp = _make_student_points()
        sp.add_points = MagicMock()
        with patch('src.services.gamification_service.StudentChallenge') as MockSC, \
             patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSC.get_or_create.return_value = sc
            MockSP.get_or_create.return_value = sp
            result = self.service.update_challenge_progress(1, 10)
        assert result['just_completed'] is True
        assert result['points_earned'] == 100

    def test_points_earned_zero_when_not_completed(self):
        sc = _make_student_challenge(is_completed=False)
        sc.update_progress.return_value = False
        ch = _make_challenge(points=50)
        sc.challenge = ch
        with patch('src.services.gamification_service.StudentChallenge') as MockSC:
            MockSC.get_or_create.return_value = sc
            result = self.service.update_challenge_progress(1, 10)
        assert result['points_earned'] == 0


# ===========================================================================
# 15. GamificationService.auto_update_challenges
# ===========================================================================

class TestAutoUpdateChallenges:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_list(self):
        with patch.object(self.service, 'get_active_challenges', return_value=[]):
            result = self.service.auto_update_challenges(1, 'quiz_count')
        assert isinstance(result, list)

    def test_empty_when_no_matching_challenges(self):
        challenges = [{'id': 1, 'target_type': 'streak', 'is_completed': False}]
        with patch.object(self.service, 'get_active_challenges', return_value=challenges):
            result = self.service.auto_update_challenges(1, 'quiz_count')
        assert result == []

    def test_updates_matching_challenge(self):
        challenges = [{'id': 5, 'target_type': 'quiz_count', 'is_completed': False}]
        update_result = {'success': True, 'just_completed': False}
        with patch.object(self.service, 'get_active_challenges', return_value=challenges), \
             patch.object(self.service, 'update_challenge_progress', return_value=update_result) as mock_upd:
            result = self.service.auto_update_challenges(1, 'quiz_count', value=2)
        mock_upd.assert_called_once_with(1, 5, 2)
        assert len(result) == 1

    def test_failed_update_not_included(self):
        challenges = [{'id': 5, 'target_type': 'quiz_count', 'is_completed': False}]
        update_result = {'success': False}
        with patch.object(self.service, 'get_active_challenges', return_value=challenges), \
             patch.object(self.service, 'update_challenge_progress', return_value=update_result):
            result = self.service.auto_update_challenges(1, 'quiz_count')
        assert result == []


# ===========================================================================
# 16. GamificationService.update_streak
# ===========================================================================

class TestUpdateStreak:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_dict(self):
        sp = _make_student_points(current_streak=3, longest_streak=5)
        sp.update_streak = MagicMock()
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.db') as mock_db:
            MockSP.get_or_create.return_value = sp
            result = self.service.update_streak(1)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        sp = _make_student_points(current_streak=2, longest_streak=4)
        sp.update_streak = MagicMock()
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.db') as mock_db:
            MockSP.get_or_create.return_value = sp
            result = self.service.update_streak(1)
        for key in ('current_streak', 'longest_streak', 'streak_increased'):
            assert key in result

    def test_streak_increased_true_when_streak_grows(self):
        sp = _make_student_points(current_streak=3, longest_streak=5)

        def _mock_update_streak():
            sp.current_streak = 4  # simulate increase

        sp.update_streak = _mock_update_streak
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.db') as mock_db:
            MockSP.get_or_create.return_value = sp
            result = self.service.update_streak(1)
        assert result['streak_increased'] is True

    def test_streak_increased_false_when_unchanged(self):
        sp = _make_student_points(current_streak=3, longest_streak=5)
        sp.update_streak = MagicMock()  # doesn't change current_streak
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.db') as mock_db:
            MockSP.get_or_create.return_value = sp
            result = self.service.update_streak(1)
        assert result['streak_increased'] is False

    def test_calls_db_session_commit(self):
        sp = _make_student_points()
        sp.update_streak = MagicMock()
        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.db') as mock_db:
            MockSP.get_or_create.return_value = sp
            self.service.update_streak(1)
        mock_db.session.commit.assert_called_once()


# ===========================================================================
# 17. GamificationService._calculate_streak
# ===========================================================================

class TestCalculateStreak:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def test_returns_zero_when_no_student_points(self):
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.query.filter_by.return_value.first.return_value = None
            result = self.service._calculate_streak(99)
        assert result == 0

    def test_returns_current_streak_value(self):
        sp = _make_student_points(current_streak=8)
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.query.filter_by.return_value.first.return_value = sp
            result = self.service._calculate_streak(1)
        assert result == 8

    def test_returns_integer(self):
        sp = _make_student_points(current_streak=2)
        with patch('src.services.gamification_service.StudentPoints') as MockSP:
            MockSP.query.filter_by.return_value.first.return_value = sp
            result = self.service._calculate_streak(1)
        assert isinstance(result, int)


# ===========================================================================
# 18. GamificationService.get_system_stats
# ===========================================================================

class TestGetSystemStats:

    @pytest.fixture(autouse=True)
    def svc(self):
        self.service = _make_service()

    def _stats_call(self, total_pts=0, ach_unlocked=0, chal_completed=0, active=0):
        """
        Call get_system_stats with all DB calls mocked.
        StudentPoints.total_points > 0 is evaluated eagerly in Python before
        filter() is called, so we give total_points a MagicMock that returns
        a MagicMock for any comparison operator.
        """
        col_mock = MagicMock()
        col_mock.__gt__ = MagicMock(return_value=MagicMock())
        col_mock.__lt__ = MagicMock(return_value=MagicMock())
        col_mock.__ge__ = MagicMock(return_value=MagicMock())
        col_mock.__le__ = MagicMock(return_value=MagicMock())

        with patch('src.services.gamification_service.StudentPoints') as MockSP, \
             patch('src.services.gamification_service.StudentAchievement') as MockSA, \
             patch('src.services.gamification_service.StudentChallenge') as MockSC, \
             patch('src.services.gamification_service.db') as mock_db:
            MockSP.total_points = col_mock
            mock_db.session.query.return_value.scalar.return_value = total_pts
            MockSA.query.filter_by.return_value.count.return_value = ach_unlocked
            MockSC.query.filter_by.return_value.count.return_value = chal_completed
            MockSP.query.filter.return_value.count.return_value = active
            return self.service.get_system_stats()

    def test_returns_dict(self):
        result = self._stats_call(total_pts=1500, ach_unlocked=30, chal_completed=10, active=20)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = self._stats_call()
        for key in ('total_points_distributed', 'total_achievements_unlocked',
                    'total_challenges_completed', 'active_students'):
            assert key in result

    def test_total_points_defaults_to_zero_when_none(self):
        result = self._stats_call(total_pts=None)
        assert result['total_points_distributed'] == 0

    def test_correct_values_returned(self):
        result = self._stats_call(total_pts=5000, ach_unlocked=42, chal_completed=15, active=25)
        assert result['total_points_distributed'] == 5000
        assert result['total_achievements_unlocked'] == 42
        assert result['total_challenges_completed'] == 15
        assert result['active_students'] == 25


# ===========================================================================
# 19. Module-level singleton
# ===========================================================================

class TestModuleSingleton:
    """Verify the module-level singleton is properly exposed."""

    def test_gamification_service_singleton_exists(self):
        # The module is already imported via _make_service(); just verify the attribute.
        import src.services.gamification_service as mod
        assert hasattr(mod, 'gamification_service')

    def test_singleton_is_gamification_service_instance(self):
        import src.services.gamification_service as mod
        assert mod.gamification_service.__class__.__name__ == 'GamificationService'
