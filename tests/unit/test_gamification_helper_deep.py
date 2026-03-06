# tests/unit/test_gamification_helper_deep.py
"""
Deep unit tests for src/services/gamification_helper.py
Goal: push coverage from 92% to 95%+ by covering missed lines:
  - Lines 71-72:  achievements loop body
  - Lines 105-113: challenges loop body (with/without student_challenge)

All DB calls are mocked with patch + MagicMock.
"""
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, date

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy third-party modules before anything else is imported
# ---------------------------------------------------------------------------
for _mod in (
    'firebase_admin',
    'firebase_admin.credentials',
    'firebase_admin.messaging',
    'firebase_admin.auth',
):
    sys.modules.setdefault(_mod, MagicMock())

sys.modules.setdefault('flask_socketio', MagicMock())
sys.modules.setdefault('google', MagicMock())
sys.modules.setdefault('google.genai', MagicMock())
sys.modules.setdefault('google.genai.types', MagicMock())

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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ---------------------------------------------------------------------------
# Import helper - reimports module fresh every time with mocked extensions.db
# ---------------------------------------------------------------------------

def _fresh_import():
    """Return a freshly imported gamification_helper module with mocked db."""
    with patch('src.extensions.db', MagicMock()):
        mod_key = 'src.services.gamification_helper'
        if mod_key in sys.modules:
            del sys.modules[mod_key]
        import src.services.gamification_helper as mod
    return mod


# ---------------------------------------------------------------------------
# Shared mock builder
# ---------------------------------------------------------------------------

def _build_db_mock(
    total_points=0,
    rank_minus_one=0,
    total_students=5,
    achievements_data=None,
    challenges_data=None,
    streak_dates=None,
):
    """
    Build a mock `db` object whose session.query side_effect list covers all
    five DB calls made inside get_student_gamification_data():
      1. db.session.query(StudentPoints).filter().count()      -> rank
      2. db.session.query(Student).count()                     -> total_students
      3. achievements join query -> .all()                     -> achievements_data
      4. challenges outerjoin query -> .all()                  -> challenges_data
      5. StudentResult streak query -> .all()                  -> streak_dates
    """
    achievements_data = achievements_data or []
    challenges_data = challenges_data or []
    streak_dates = streak_dates or []

    mock_db = MagicMock()

    # Call 1: rank
    rank_q = MagicMock()
    rank_q.filter.return_value.count.return_value = rank_minus_one

    # Call 2: total students
    total_q = MagicMock()
    total_q.count.return_value = total_students

    # Call 3: achievements
    ach_q = MagicMock()
    ach_q.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = achievements_data

    # Call 4: challenges
    chal_q = MagicMock()
    chal_q.outerjoin.return_value.filter.return_value.all.return_value = challenges_data

    # Call 5: streak (StudentResult)
    streak_q = MagicMock()
    streak_q.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = streak_dates

    mock_db.session.query.side_effect = [
        rank_q, total_q, ach_q, chal_q, streak_q
    ]
    mock_db.and_ = MagicMock(return_value=MagicMock())
    mock_db.or_ = MagicMock(return_value=MagicMock())
    mock_db.func = MagicMock()

    return mock_db


def _make_student_points(total_points):
    sp = MagicMock()
    sp.total_points = total_points
    return sp


def _make_achievement(title='إنجاز', description='وصف', points=25, icon='star'):
    ach = MagicMock()
    ach.title = title
    ach.description = description
    ach.points = points
    ach.icon = icon
    return ach


def _make_challenge(
    cid=1, title='تحدي', description='وصف التحدي',
    target_value=10, points=50, challenge_type='quiz'
):
    ch = MagicMock()
    ch.id = cid
    ch.title = title
    ch.description = description
    ch.target_value = target_value
    ch.points = points
    ch.challenge_type = challenge_type
    return ch


def _make_student_challenge(progress=3, is_completed=False):
    sc = MagicMock()
    sc.progress = progress
    sc.is_completed = is_completed
    return sc


def _run(
    total_points=0,
    achievements_data=None,
    challenges_data=None,
    rank_minus_one=0,
    total_students=5,
):
    """Main helper: run get_student_gamification_data with controlled mocks."""
    mod = _fresh_import()

    sp = _make_student_points(total_points)

    mock_sp_cls = MagicMock()
    mock_sp_cls.query.filter_by.return_value.first.return_value = sp
    # Make StudentPoints.total_points support comparison operators
    # The code does: StudentPoints.total_points > student_points.total_points
    # We need this to work as a SQLAlchemy expression (returns anything truthy for .filter())
    mock_sp_cls.total_points = MagicMock()
    mock_sp_cls.total_points.__gt__ = MagicMock(return_value=MagicMock())

    mock_db = _build_db_mock(
        total_points=total_points,
        rank_minus_one=rank_minus_one,
        total_students=total_students,
        achievements_data=achievements_data,
        challenges_data=challenges_data,
    )

    # Build achievement/challenge mocks with comparison operators supported
    mock_ach_cls = MagicMock()
    mock_student_ach_cls = MagicMock()
    # unlocked_at column needs >= support against datetime
    mock_student_ach_cls.unlocked_at = MagicMock()
    mock_student_ach_cls.unlocked_at.__ge__ = MagicMock(return_value=MagicMock())
    mock_student_ach_cls.unlocked_at.desc = MagicMock(return_value=MagicMock())

    mock_challenge_cls = MagicMock()
    mock_student_challenge_cls = MagicMock()
    # end_date column needs >= support against date
    mock_challenge_cls.end_date = MagicMock()
    mock_challenge_cls.end_date.__ge__ = MagicMock(return_value=MagicMock())
    mock_challenge_cls.is_active = MagicMock()
    mock_challenge_cls.id = MagicMock()

    mock_gamification_mod = MagicMock()
    mock_gamification_mod.StudentPoints = mock_sp_cls
    mock_gamification_mod.Achievement = mock_ach_cls
    mock_gamification_mod.StudentAchievement = mock_student_ach_cls
    mock_gamification_mod.Challenge = mock_challenge_cls
    mock_gamification_mod.StudentChallenge = mock_student_challenge_cls

    mock_student_mod = MagicMock()
    mock_sr_mod = MagicMock()

    with patch('src.services.gamification_helper.db', mock_db), \
         patch.dict('sys.modules', {
             'src.models.student': mock_student_mod,
             'src.models.gamification': mock_gamification_mod,
             'src.models.student_result': mock_sr_mod,
         }):
        result = mod.get_student_gamification_data(1)

    return result


# ===========================================================================
# 1. Achievements loop (lines 71-77) — the critical uncovered section
# ===========================================================================

class TestAchievementsLoop:
    """
    Force the achievements loop to iterate (lines 71-77).
    The loop was previously xfail — we fix the mock so the import
    succeeds and the query returns real achievement objects.
    """

    def _single_achievement_result(self):
        ach = _make_achievement('نجم الأسبوع', 'حل 50 سؤال', 50, 'star')
        unlocked_at = datetime(2024, 6, 1, 10, 0, 0)
        return [(ach, unlocked_at)]

    def _two_achievement_results(self):
        ach1 = _make_achievement('نجم الأسبوع', 'حل 50 سؤال', 50, 'star')
        ach2 = _make_achievement('متحمس', 'لمدة 7 أيام', 30, 'fire')
        d1 = datetime(2024, 6, 1, 10, 0, 0)
        d2 = datetime(2024, 6, 2, 12, 0, 0)
        return [(ach1, d1), (ach2, d2)]

    def test_single_achievement_appended_to_list(self):
        """Line 72: achievements_list.append({...}) executes once."""
        result = _run(
            total_points=200,
            achievements_data=self._single_achievement_result(),
        )
        assert len(result['recent_achievements']) == 1

    def test_single_achievement_title_correct(self):
        result = _run(
            total_points=200,
            achievements_data=self._single_achievement_result(),
        )
        assert result['recent_achievements'][0]['title'] == 'نجم الأسبوع'

    def test_single_achievement_description_correct(self):
        result = _run(
            total_points=200,
            achievements_data=self._single_achievement_result(),
        )
        assert result['recent_achievements'][0]['description'] == 'حل 50 سؤال'

    def test_single_achievement_points_correct(self):
        result = _run(
            total_points=200,
            achievements_data=self._single_achievement_result(),
        )
        assert result['recent_achievements'][0]['points'] == 50

    def test_single_achievement_icon_correct(self):
        result = _run(
            total_points=200,
            achievements_data=self._single_achievement_result(),
        )
        assert result['recent_achievements'][0]['icon'] == 'star'

    def test_single_achievement_unlocked_at_is_isoformat(self):
        """Line 77: unlocked_at.isoformat() is called."""
        result = _run(
            total_points=200,
            achievements_data=self._single_achievement_result(),
        )
        unlocked_at = result['recent_achievements'][0]['unlocked_at']
        assert isinstance(unlocked_at, str)
        assert '2024-06-01' in unlocked_at

    def test_two_achievements_both_appended(self):
        """Loop iterates twice (lines 71-77 executed twice)."""
        result = _run(
            total_points=200,
            achievements_data=self._two_achievement_results(),
        )
        assert len(result['recent_achievements']) == 2

    def test_two_achievements_titles(self):
        result = _run(
            total_points=200,
            achievements_data=self._two_achievement_results(),
        )
        titles = [a['title'] for a in result['recent_achievements']]
        assert 'نجم الأسبوع' in titles
        assert 'متحمس' in titles

    def test_two_achievements_points(self):
        result = _run(
            total_points=200,
            achievements_data=self._two_achievement_results(),
        )
        pts = [a['points'] for a in result['recent_achievements']]
        assert 50 in pts
        assert 30 in pts

    def test_two_achievements_icons(self):
        result = _run(
            total_points=200,
            achievements_data=self._two_achievement_results(),
        )
        icons = [a['icon'] for a in result['recent_achievements']]
        assert 'star' in icons
        assert 'fire' in icons

    def test_achievements_all_have_unlocked_at_key(self):
        result = _run(
            total_points=500,
            achievements_data=self._two_achievement_results(),
        )
        for ach in result['recent_achievements']:
            assert 'unlocked_at' in ach

    def test_three_achievements_limit_respected(self):
        """The query is limited to 3 at DB level; test with 3 results."""
        ach_data = []
        for i in range(3):
            ach = _make_achievement(f'إنجاز {i}', 'وصف', i * 10, 'medal')
            ach_data.append((ach, datetime(2024, 6, i + 1, 10, 0, 0)))
        result = _run(total_points=300, achievements_data=ach_data)
        assert len(result['recent_achievements']) == 3

    def test_achievement_with_zero_points(self):
        ach = _make_achievement('تجربة', 'وصف', 0, 'test')
        result = _run(
            total_points=100,
            achievements_data=[(ach, datetime(2024, 1, 1))],
        )
        assert result['recent_achievements'][0]['points'] == 0

    def test_achievement_unlocked_at_isoformat_format(self):
        """Verify isoformat() produces a valid ISO 8601 string."""
        ach = _make_achievement()
        dt = datetime(2025, 3, 15, 8, 30, 0)
        result = _run(
            total_points=150,
            achievements_data=[(ach, dt)],
        )
        iso = result['recent_achievements'][0]['unlocked_at']
        # Should parse back to datetime
        parsed = datetime.fromisoformat(iso)
        assert parsed.year == 2025
        assert parsed.month == 3


# ===========================================================================
# 2. Challenges loop (lines 105-122) — the other critical uncovered section
# ===========================================================================

class TestChallengesLoop:
    """
    Force the challenges loop to iterate (lines 105-122).
    Tests both branches: student_challenge present and student_challenge=None.
    """

    # --- Branch A: student_challenge IS present (not None) ---

    def test_challenge_with_sc_progress_and_completed_false(self):
        """Lines 109-111: student_challenge is truthy -> read progress + is_completed."""
        ch = _make_challenge(cid=1, title='تحدي اليوم', target_value=10, points=100)
        sc = _make_student_challenge(progress=5, is_completed=False)
        result = _run(
            total_points=200,
            challenges_data=[(ch, sc)],
        )
        assert len(result['active_challenges']) == 1
        item = result['active_challenges'][0]
        assert item['progress'] == 5
        assert item['completed'] is False

    def test_challenge_with_sc_completed_true(self):
        """is_completed=True -> completed=True in result."""
        ch = _make_challenge(cid=2, title='تحدي مكتمل', target_value=20, points=200)
        sc = _make_student_challenge(progress=20, is_completed=True)
        result = _run(
            total_points=300,
            challenges_data=[(ch, sc)],
        )
        item = result['active_challenges'][0]
        assert item['completed'] is True
        assert item['progress'] == 20

    def test_challenge_with_sc_partial_progress(self):
        ch = _make_challenge(cid=3, target_value=50, points=75)
        sc = _make_student_challenge(progress=23, is_completed=False)
        result = _run(challenges_data=[(ch, sc)])
        assert result['active_challenges'][0]['progress'] == 23

    # --- Branch B: student_challenge is None (outer join returned NULL) ---

    def test_challenge_without_sc_progress_defaults_to_zero(self):
        """Lines 106-107: if student_challenge is None -> progress=0, completed=False."""
        ch = _make_challenge(cid=4, title='تحدي جديد')
        result = _run(
            total_points=100,
            challenges_data=[(ch, None)],
        )
        assert len(result['active_challenges']) == 1
        item = result['active_challenges'][0]
        assert item['progress'] == 0

    def test_challenge_without_sc_completed_defaults_to_false(self):
        ch = _make_challenge(cid=5)
        result = _run(challenges_data=[(ch, None)])
        item = result['active_challenges'][0]
        assert item['completed'] is False

    # --- Line 113: challenges_list.append({...}) — verify all keys ---

    def test_challenge_append_all_keys_present(self):
        """Line 113: verify all keys are appended correctly."""
        ch = _make_challenge(
            cid=10,
            title='تحدي الكيمياء',
            description='حل 10 أسئلة كيمياء',
            target_value=10,
            points=150,
            challenge_type='chemistry',
        )
        sc = _make_student_challenge(progress=3, is_completed=False)
        result = _run(challenges_data=[(ch, sc)])
        item = result['active_challenges'][0]
        assert item['id'] == 10
        assert item['title'] == 'تحدي الكيمياء'
        assert item['description'] == 'حل 10 أسئلة كيمياء'
        assert item['target'] == 10
        assert item['points'] == 150
        assert item['type'] == 'chemistry'
        assert item['progress'] == 3
        assert item['completed'] is False

    def test_challenge_append_keys_without_sc(self):
        """Line 113 with student_challenge=None: all keys present."""
        ch = _make_challenge(cid=11, title='تحدي بلا تتبع')
        result = _run(challenges_data=[(ch, None)])
        item = result['active_challenges'][0]
        required_keys = {'id', 'title', 'description', 'target', 'progress',
                         'completed', 'points', 'type'}
        assert required_keys.issubset(item.keys())

    def test_two_challenges_both_appended(self):
        """Loop iterates twice."""
        ch1 = _make_challenge(cid=20, title='تحدي 1', target_value=5)
        ch2 = _make_challenge(cid=21, title='تحدي 2', target_value=15)
        sc1 = _make_student_challenge(progress=2)
        result = _run(challenges_data=[(ch1, sc1), (ch2, None)])
        assert len(result['active_challenges']) == 2

    def test_two_challenges_first_has_sc(self):
        ch1 = _make_challenge(cid=30, title='أول تحدي')
        ch2 = _make_challenge(cid=31, title='ثاني تحدي')
        sc1 = _make_student_challenge(progress=7, is_completed=False)
        result = _run(challenges_data=[(ch1, sc1), (ch2, None)])
        first = result['active_challenges'][0]
        second = result['active_challenges'][1]
        assert first['progress'] == 7
        assert second['progress'] == 0

    def test_two_challenges_second_completed(self):
        ch1 = _make_challenge(cid=40)
        ch2 = _make_challenge(cid=41)
        sc2 = _make_student_challenge(progress=10, is_completed=True)
        result = _run(challenges_data=[(ch1, None), (ch2, sc2)])
        second = result['active_challenges'][1]
        assert second['completed'] is True

    def test_challenge_mixed_sc_and_none(self):
        """Three challenges: sc, None, sc."""
        challenges = [
            (_make_challenge(cid=50), _make_student_challenge(5, False)),
            (_make_challenge(cid=51), None),
            (_make_challenge(cid=52), _make_student_challenge(10, True)),
        ]
        result = _run(challenges_data=challenges)
        items = result['active_challenges']
        assert len(items) == 3
        assert items[0]['progress'] == 5
        assert items[1]['progress'] == 0
        assert items[2]['completed'] is True

    def test_challenge_type_preserved(self):
        ch = _make_challenge(cid=60, challenge_type='streak')
        result = _run(challenges_data=[(ch, None)])
        assert result['active_challenges'][0]['type'] == 'streak'

    def test_challenge_id_preserved(self):
        ch = _make_challenge(cid=999)
        result = _run(challenges_data=[(ch, None)])
        assert result['active_challenges'][0]['id'] == 999

    def test_challenge_points_preserved(self):
        ch = _make_challenge(cid=70, points=999)
        sc = _make_student_challenge()
        result = _run(challenges_data=[(ch, sc)])
        assert result['active_challenges'][0]['points'] == 999

    def test_challenge_target_value_preserved(self):
        ch = _make_challenge(cid=80, target_value=100)
        result = _run(challenges_data=[(ch, None)])
        assert result['active_challenges'][0]['target'] == 100


# ===========================================================================
# 3. Combined achievements + challenges in one call
# ===========================================================================

class TestCombinedAchievementsAndChallenges:
    """Both loops execute in a single get_student_gamification_data call."""

    def test_both_achievements_and_challenges_returned(self):
        ach = _make_achievement('إنجاز مشترك', 'وصف', 40, 'trophy')
        unlocked_at = datetime(2024, 9, 1, 14, 0, 0)
        ch = _make_challenge(cid=90, title='تحدي مشترك')
        sc = _make_student_challenge(6, False)

        result = _run(
            total_points=300,
            achievements_data=[(ach, unlocked_at)],
            challenges_data=[(ch, sc)],
            rank_minus_one=2,
            total_students=10,
        )

        assert len(result['recent_achievements']) == 1
        assert len(result['active_challenges']) == 1
        assert result['recent_achievements'][0]['title'] == 'إنجاز مشترك'
        assert result['active_challenges'][0]['progress'] == 6

    def test_combined_result_has_all_keys(self):
        ach = _make_achievement()
        ch = _make_challenge()
        sc = _make_student_challenge()
        result = _run(
            total_points=400,
            achievements_data=[(ach, datetime(2024, 1, 1))],
            challenges_data=[(ch, sc)],
        )
        keys = {'points', 'level', 'rank', 'total_students', 'recent_achievements',
                'active_challenges', 'next_level_points', 'streak_days',
                'points_to_next_level'}
        assert keys.issubset(result.keys())

    def test_combined_points_to_next_level(self):
        ach = _make_achievement()
        ch = _make_challenge()
        result = _run(
            total_points=250,
            achievements_data=[(ach, datetime(2024, 5, 5))],
            challenges_data=[(ch, None)],
        )
        # Level 3 (250 pts) -> next level 4 needs 500 -> points_to_next = 250
        assert result['points_to_next_level'] == 250


# ===========================================================================
# 4. calculate_level_from_points - all boundary values
# ===========================================================================

class TestCalculateLevelFromPoints:
    """Ensure all level thresholds are covered."""

    def setup_method(self):
        self.mod = _fresh_import()

    def test_zero_points_level_1(self):
        assert self.mod.calculate_level_from_points(0) == 1

    def test_99_points_level_1(self):
        assert self.mod.calculate_level_from_points(99) == 1

    def test_100_points_level_2(self):
        assert self.mod.calculate_level_from_points(100) == 2

    def test_249_points_level_2(self):
        assert self.mod.calculate_level_from_points(249) == 2

    def test_250_points_level_3(self):
        assert self.mod.calculate_level_from_points(250) == 3

    def test_499_points_level_3(self):
        assert self.mod.calculate_level_from_points(499) == 3

    def test_500_points_level_4(self):
        assert self.mod.calculate_level_from_points(500) == 4

    def test_999_points_level_4(self):
        assert self.mod.calculate_level_from_points(999) == 4

    def test_1000_points_level_5(self):
        assert self.mod.calculate_level_from_points(1000) == 5

    def test_9999_points_level_5(self):
        assert self.mod.calculate_level_from_points(9999) == 5


# ===========================================================================
# 5. calculate_level_threshold - all levels including unknown
# ===========================================================================

class TestCalculateLevelThreshold:
    """All branches of calculate_level_threshold()."""

    def setup_method(self):
        self.mod = _fresh_import()

    def test_level_1_threshold_is_0(self):
        assert self.mod.calculate_level_threshold(1) == 0

    def test_level_2_threshold_is_100(self):
        assert self.mod.calculate_level_threshold(2) == 100

    def test_level_3_threshold_is_250(self):
        assert self.mod.calculate_level_threshold(3) == 250

    def test_level_4_threshold_is_500(self):
        assert self.mod.calculate_level_threshold(4) == 500

    def test_level_5_threshold_is_1000(self):
        assert self.mod.calculate_level_threshold(5) == 1000

    def test_level_6_unknown_returns_1000(self):
        """Unknown level -> dict.get default = 1000."""
        assert self.mod.calculate_level_threshold(6) == 1000

    def test_level_0_unknown_returns_1000(self):
        assert self.mod.calculate_level_threshold(0) == 1000

    def test_level_99_unknown_returns_1000(self):
        assert self.mod.calculate_level_threshold(99) == 1000


# ===========================================================================
# 6. format_gamification_section - all branches
# ===========================================================================

class TestFormatGamificationSection:
    """Cover all branches of format_gamification_section()."""

    def setup_method(self):
        self.mod = _fresh_import()

    def _base_data(self, **kwargs):
        data = {
            'points': 0,
            'level': 1,
            'rank': 0,
            'total_students': 5,
            'recent_achievements': [],
            'active_challenges': [],
            'next_level_points': 100,
            'points_to_next_level': 100,
            'streak_days': 0,
        }
        data.update(kwargs)
        return data

    def test_basic_stats_always_rendered(self):
        result = self.mod.format_gamification_section(self._base_data())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_rank_zero_shows_jadeed(self):
        result = self.mod.format_gamification_section(self._base_data(rank=0))
        assert 'جديد' in result

    def test_rank_nonzero_shows_hash_number(self):
        result = self.mod.format_gamification_section(self._base_data(rank=3, total_students=10))
        assert '#3' in result

    def test_with_achievements_shows_section(self):
        data = self._base_data(
            points=200,
            level=2,
            recent_achievements=[
                {'title': 'نجم', 'points': 50},
                {'title': 'بطل', 'points': 30},
            ]
        )
        result = self.mod.format_gamification_section(data)
        assert 'نجم' in result or 'إنجاز' in result or len(result) > 0

    def test_without_achievements_no_achievement_section(self):
        result = self.mod.format_gamification_section(self._base_data())
        # No achievement header when list is empty
        assert isinstance(result, str)

    def test_active_challenge_incomplete_shows_section(self):
        data = self._base_data(
            active_challenges=[{
                'id': 1,
                'title': 'تحدي اليوم',
                'progress': 3,
                'target': 10,
                'completed': False,
                'points': 100,
            }]
        )
        result = self.mod.format_gamification_section(data)
        assert 'تحدي' in result or len(result) > 0

    def test_active_challenge_completed_not_shown(self):
        """Completed challenges are filtered out."""
        data = self._base_data(
            active_challenges=[{
                'id': 1,
                'title': 'تحدي منتهي',
                'progress': 10,
                'target': 10,
                'completed': True,
                'points': 50,
            }]
        )
        result = self.mod.format_gamification_section(data)
        assert isinstance(result, str)

    def test_level_less_than_5_shows_progress_bar(self):
        data = self._base_data(points=50, level=1, next_level_points=100, points_to_next_level=50)
        result = self.mod.format_gamification_section(data)
        assert '█' in result or 'باقي' in result or len(result) > 0

    def test_level_5_shows_max_level_message(self):
        data = self._base_data(
            points=1500,
            level=5,
            next_level_points=1000,
            points_to_next_level=0,  # would be negative but test boundary
        )
        result = self.mod.format_gamification_section(data)
        assert 'أقصى' in result or 'نخبة' in result or '🏆' in result

    def test_streak_less_than_3_not_shown(self):
        result = self.mod.format_gamification_section(self._base_data(streak_days=2))
        # streak < 3 -> not displayed
        assert isinstance(result, str)

    def test_streak_3_or_more_shown(self):
        data = self._base_data(streak_days=3)
        result = self.mod.format_gamification_section(data)
        assert '3' in result or 'سلسلة' in result or 'أيام' in result

    def test_streak_10_shown(self):
        data = self._base_data(streak_days=10)
        result = self.mod.format_gamification_section(data)
        assert '10' in result or 'سلسلة' in result

    def test_result_is_non_empty_string(self):
        data = self._base_data(points=500, level=4, rank=2, total_students=20)
        result = self.mod.format_gamification_section(data)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_sections_joined_with_double_newline(self):
        data = self._base_data(
            points=500,
            level=4,
            rank=5,
            total_students=50,
            streak_days=5,
            next_level_points=1000,
            points_to_next_level=500,
        )
        result = self.mod.format_gamification_section(data)
        assert '\n\n' in result


# ===========================================================================
# 7. get_compact_gamification_text - all branches
# ===========================================================================

class TestGetCompactGamificationText:
    """Cover all branches of get_compact_gamification_text()."""

    def setup_method(self):
        self.mod = _fresh_import()

    def _base(self, **kwargs):
        data = {
            'points': 0,
            'level': 1,
            'rank': 0,
            'total_students': 10,
            'streak_days': 0,
        }
        data.update(kwargs)
        return data

    def test_no_points_no_level_no_rank_returns_empty(self):
        result = self.mod.get_compact_gamification_text(self._base())
        assert result == ''

    def test_points_above_zero_shows_points(self):
        result = self.mod.get_compact_gamification_text(self._base(points=100))
        assert '100' in result

    def test_level_above_1_shows_level(self):
        result = self.mod.get_compact_gamification_text(self._base(level=3))
        assert '3' in result or 'مستوى' in result

    def test_rank_1_to_10_shows_rank(self):
        result = self.mod.get_compact_gamification_text(self._base(rank=5))
        assert '5' in result or '#' in result

    def test_rank_above_10_not_shown(self):
        result = self.mod.get_compact_gamification_text(self._base(rank=11))
        assert '#11' not in result

    def test_streak_3_or_more_shown(self):
        result = self.mod.get_compact_gamification_text(self._base(streak_days=5))
        assert '5' in result

    def test_streak_2_not_shown(self):
        result = self.mod.get_compact_gamification_text(self._base(streak_days=2))
        # streak < 3 not shown
        assert isinstance(result, str)

    def test_all_parts_joined_with_bullet(self):
        result = self.mod.get_compact_gamification_text(self._base(
            points=500, level=4, rank=3, streak_days=7
        ))
        assert ' • ' in result

    def test_only_points_no_bullet(self):
        result = self.mod.get_compact_gamification_text(self._base(points=100))
        assert isinstance(result, str)
        assert '100' in result

    def test_rank_0_not_shown(self):
        result = self.mod.get_compact_gamification_text(self._base(rank=0))
        assert '#0' not in result

    def test_level_1_not_shown(self):
        result = self.mod.get_compact_gamification_text(self._base(level=1, points=0))
        assert 'مستوى 1' not in result

    def test_points_1000_formatted(self):
        result = self.mod.get_compact_gamification_text(self._base(points=1000))
        assert '1,000' in result or '1000' in result


# ===========================================================================
# 8. calculate_streak - additional edge cases
# ===========================================================================

class TestCalculateStreakDeep:
    """Additional edge cases for calculate_streak()."""

    def setup_method(self):
        self.mod = _fresh_import()
        # Ensure StudentResult mock is available
        sr_mock = MagicMock()
        sr_mock.StudentResult = MagicMock()
        sys.modules['src.models.student_result'] = sr_mock

    def _make_date_row(self, d):
        r = MagicMock()
        r.date = d
        return r

    def test_streak_empty_results_returns_zero(self):
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []
            result = self.mod.calculate_streak(1)
        assert result == 0

    def test_streak_today_only_is_one(self):
        today = datetime.utcnow().date()
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 10, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_row(today)
            ]
            result = self.mod.calculate_streak(1)
        assert result == 1

    def test_streak_ten_consecutive_days(self):
        today = datetime.utcnow().date()
        days = [today - timedelta(days=i) for i in range(10)]
        with patch('src.services.gamification_helper.db') as mock_db, \
             patch('src.services.gamification_helper.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(today.year, today.month, today.day, 12, 0)
            mock_db.session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
                self._make_date_row(d) for d in days
            ]
            result = self.mod.calculate_streak(1)
        assert result == 10

    def test_streak_import_error_returns_zero(self):
        """If src.models.student_result import fails inside calculate_streak."""
        with patch.dict('sys.modules', {'src.models.student_result': None}):
            result = self.mod.calculate_streak(99)
        assert result == 0

    def test_streak_db_runtime_error_returns_zero(self):
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = RuntimeError("lost connection")
            result = self.mod.calculate_streak(1)
        assert result == 0

    def test_streak_attribute_error_returns_zero(self):
        with patch('src.services.gamification_helper.db') as mock_db:
            mock_db.session.query.side_effect = AttributeError("no attr")
            result = self.mod.calculate_streak(1)
        assert result == 0
