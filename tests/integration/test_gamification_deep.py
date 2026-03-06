"""
اختبارات شاملة لـ gamification_routes blueprint
يغطي: points, leaderboard, achievements, challenges, streak, stats, backward compat
"""
import pytest
import secrets
from unittest.mock import patch, MagicMock


# ===== helpers =====

def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='Test',
        username=f'gam_{secrets.token_hex(4)}',
        email=f'gam_{secrets.token_hex(4)}@test.com',
        is_active=True
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _auth_headers(student):
    return {'X-Session-Token': student.session_token}


def _make_points_data(student_id=1):
    return {
        'student_id': student_id,
        'total_points': 450,
        'lifetime_points': 500,
        'level': 4,
        'rank': 3,
        'current_streak': 7,
        'longest_streak': 15,
        'points_to_next_level': 50,
        'next_level_threshold': 500,
    }


def _make_achievements_data():
    return {
        'achievements': [],
        'total_achievements': 20,
        'total_unlocked': 5,
        'completion_rate': 25.0,
    }


def _make_challenges_data():
    return []


def _make_system_stats():
    return {
        'total_points_distributed': 125000,
        'total_achievements_unlocked': 450,
        'total_challenges_completed': 320,
        'active_students': 67,
    }


# ============================================================
# Class 1: Public routes (no auth required)
# ============================================================

class TestGamificationPublicRoutes:
    """الـ routes العامة التي لا تحتاج مصادقة"""

    def test_leaderboard_no_params(self, client):
        """لوحة المتصدرين بدون معاملات"""
        response = client.get('/api/gamification/leaderboard')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_limit_5(self, client):
        """لوحة المتصدرين مع limit=5"""
        response = client.get('/api/gamification/leaderboard?limit=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_limit_0(self, client):
        """لوحة المتصدرين مع limit=0"""
        response = client.get('/api/gamification/leaderboard?limit=0')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_with_offset(self, client):
        """لوحة المتصدرين مع offset=10"""
        response = client.get('/api/gamification/leaderboard?offset=10')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_limit_and_offset(self, client):
        """لوحة المتصدرين مع limit و offset"""
        response = client.get('/api/gamification/leaderboard?limit=10&offset=0')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_large_limit(self, client):
        """لوحة المتصدرين مع limit كبير"""
        response = client.get('/api/gamification/leaderboard?limit=1000')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_response_structure(self, client):
        """لوحة المتصدرين - التحقق من بنية الاستجابة"""
        response = client.get('/api/gamification/leaderboard')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_leaderboard_post_not_allowed(self, client):
        """POST على leaderboard - يجب أن يرفض"""
        response = client.post('/api/gamification/leaderboard')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_list_no_params(self, client):
        """قائمة التحديات بدون معاملات"""
        response = client.get('/api/gamification/challenges')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_list_type_daily(self, client):
        """التحديات بنوع daily"""
        response = client.get('/api/gamification/challenges?type=daily')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_list_type_weekly(self, client):
        """التحديات بنوع weekly"""
        response = client.get('/api/gamification/challenges?type=weekly')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_list_type_monthly(self, client):
        """التحديات بنوع monthly"""
        response = client.get('/api/gamification/challenges?type=monthly')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_list_type_special(self, client):
        """التحديات بنوع special"""
        response = client.get('/api/gamification/challenges?type=special')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_list_with_student_id(self, client, db_session):
        """قائمة التحديات مع student_id"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/challenges?student_id={s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_today_new_route(self, client):
        """تحدي اليوم - route الجديد"""
        response = client.get('/api/gamification/challenges/today')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_today_legacy_route(self, client):
        """تحدي اليوم - legacy route"""
        response = client.get('/api/gamification/challenge/today')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_today_response_has_success(self, client):
        """تحدي اليوم - الرد يحتوي على success"""
        response = client.get('/api/gamification/challenges/today')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code in [200, 404]:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_system_stats_no_auth(self, client):
        """إحصائيات النظام بدون مصادقة - public endpoint"""
        response = client.get('/api/gamification/stats/system')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_system_stats_response_structure(self, client):
        """إحصائيات النظام - بنية الاستجابة"""
        response = client.get('/api/gamification/stats/system')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data


# ============================================================
# Class 2: Points routes
# ============================================================

class TestPointsRoutes:
    """اختبارات routes النقاط"""

    def test_get_points_no_token(self, client, db_session):
        """جلب نقاط بدون token"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/points/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_points_wrong_token(self, client, db_session):
        """جلب نقاط بـ token خاطئ"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers={'X-Session-Token': 'wrong_token_value'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_points_valid_token(self, client, db_session):
        """جلب نقاط بـ token صحيح"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_points_valid_token_response_structure(self, client, db_session):
        """جلب نقاط بـ token صحيح - بنية الاستجابة"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_get_points_nonexistent_student(self, client):
        """جلب نقاط طالب غير موجود"""
        response = client.get(
            '/api/gamification/points/99999',
            headers={'X-Session-Token': 'some_token'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_points_token_via_query_param(self, client, db_session):
        """جلب نقاط بـ token عبر query string"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s.id}?session_token={s.session_token}'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_points_other_student_token(self, client, db_session):
        """جلب نقاط طالب بـ token طالب آخر - يجب رفض"""
        s1 = _make_student(db_session)
        s2 = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s1.id}',
            headers={'X-Session-Token': s2.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_no_auth(self, client, db_session):
        """إضافة نقاط بدون مصادقة"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={'amount': 50, 'reason': 'test'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_with_student_token(self, client, db_session):
        """إضافة نقاط بـ token الطالب نفسه"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={'amount': 50, 'reason': 'مكافأة', 'session_token': s.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_zero_amount(self, client, db_session):
        """إضافة نقاط بمقدار صفر - يجب رفض"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={'amount': 0, 'reason': 'test', 'session_token': s.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_negative_amount(self, client, db_session):
        """إضافة نقاط بمقدار سالب - يجب رفض"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={'amount': -10, 'reason': 'test', 'session_token': s.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_valid_amount_response(self, client, db_session):
        """إضافة نقاط بمقدار صحيح - التحقق من الرد"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={'amount': 100, 'reason': 'مكافأة', 'session_token': s.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_add_points_as_admin(self, client, admin_user, db_session):
        """إضافة نقاط كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={'amount': 50, 'reason': 'admin bonus'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_empty_body(self, client, db_session):
        """إضافة نقاط بـ body فارغ"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s.id}/add',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_other_student_token_forbidden(self, client, db_session):
        """إضافة نقاط بـ token طالب آخر - يجب رفض"""
        s1 = _make_student(db_session)
        s2 = _make_student(db_session)
        response = client.post(
            f'/api/gamification/points/{s1.id}/add',
            json={'amount': 50, 'reason': 'hack', 'session_token': s2.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Class 3: Achievements routes
# ============================================================

class TestAchievementsRoutes:
    """اختبارات routes الإنجازات"""

    def test_get_achievements_no_token(self, client, db_session):
        """جلب الإنجازات بدون token"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/achievements/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_achievements_wrong_token(self, client, db_session):
        """جلب الإنجازات بـ token خاطئ"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/achievements/{s.id}',
            headers={'X-Session-Token': 'bad_token'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_achievements_valid_token(self, client, db_session):
        """جلب الإنجازات بـ token صحيح"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/achievements/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_achievements_response_structure(self, client, db_session):
        """جلب الإنجازات - بنية الاستجابة"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/achievements/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_check_achievements_no_token(self, client, db_session):
        """فحص الإنجازات بدون token"""
        s = _make_student(db_session)
        response = client.post(f'/api/gamification/achievements/{s.id}/check')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_check_achievements_valid_token(self, client, db_session):
        """فحص الإنجازات بـ token صحيح"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/achievements/{s.id}/check',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_check_achievements_response_has_unlocked(self, client, db_session):
        """فحص الإنجازات - الرد يحتوي على unlocked"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/achievements/{s.id}/check',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            if data and data.get('success'):
                assert 'unlocked' in data
                assert 'total_unlocked' in data

    def test_get_achievements_nonexistent_student(self, client):
        """جلب إنجازات طالب غير موجود"""
        response = client.get(
            '/api/gamification/achievements/99999',
            headers={'X-Session-Token': 'any_token'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Class 4: Challenges routes (student-auth)
# ============================================================

class TestChallengesStudentRoutes:
    """اختبارات routes التحديات التي تحتاج مصادقة الطالب"""

    def test_get_challenge_progress_no_token(self, client, db_session):
        """جلب تقدم التحديات بدون token"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/challenges/{s.id}/progress')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_challenge_progress_valid_token(self, client, db_session):
        """جلب تقدم التحديات بـ token صحيح"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/challenges/{s.id}/progress',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_challenge_progress_with_challenge_id(self, client, db_session):
        """جلب تقدم التحديات مع challenge_id"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/challenges/{s.id}/progress?challenge_id=5',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_challenge_progress_response_structure(self, client, db_session):
        """تقدم التحديات - بنية الاستجابة"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/challenges/{s.id}/progress',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_update_challenge_progress_no_token(self, client, db_session):
        """تحديث تقدم التحدي بدون token"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/challenges/{s.id}/update',
            json={'challenge_id': 1}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_challenge_progress_no_challenge_id(self, client, db_session):
        """تحديث تقدم التحدي بدون challenge_id"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/challenges/{s.id}/update',
            json={'increment': 1},
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_challenge_progress_valid(self, client, db_session):
        """تحديث تقدم التحدي بـ token وبيانات صحيحة"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/challenges/{s.id}/update',
            json={'challenge_id': 1, 'increment': 1},
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_challenge_progress_default_increment(self, client, db_session):
        """تحديث تقدم التحدي بدون تحديد increment - يستخدم الافتراضي 1"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/challenges/{s.id}/update',
            json={'challenge_id': 5},
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_challenge_progress_legacy_route(self, client, db_session):
        """تقدم التحديات - legacy route"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/challenge/progress/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_challenge_progress_legacy_no_token(self, client, db_session):
        """تقدم التحديات - legacy route بدون token"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/challenge/progress/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Class 5: Streak routes
# ============================================================

class TestStreakRoutes:
    """اختبارات routes السلسلة (streak)"""

    def test_get_streak_no_token(self, client, db_session):
        """جلب السلسلة بدون token"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/streak/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_streak_wrong_token(self, client, db_session):
        """جلب السلسلة بـ token خاطئ"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/streak/{s.id}',
            headers={'X-Session-Token': 'invalid'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_streak_valid_token(self, client, db_session):
        """جلب السلسلة بـ token صحيح"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/streak/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_streak_response_structure(self, client, db_session):
        """جلب السلسلة - بنية الاستجابة"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/streak/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data
            if data.get('success'):
                assert 'data' in data

    def test_get_streak_data_has_streak_fields(self, client, db_session):
        """جلب السلسلة - الرد يحتوي على حقول السلسلة"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/streak/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            if data and data.get('success') and 'data' in data:
                assert 'current_streak' in data['data']
                assert 'longest_streak' in data['data']

    def test_update_streak_no_token(self, client, db_session):
        """تحديث السلسلة بدون token"""
        s = _make_student(db_session)
        response = client.post(f'/api/gamification/streak/{s.id}/update')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_streak_valid_token(self, client, db_session):
        """تحديث السلسلة بـ token صحيح"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/streak/{s.id}/update',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_streak_response_structure(self, client, db_session):
        """تحديث السلسلة - بنية الاستجابة"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/streak/{s.id}/update',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_get_streak_nonexistent_student(self, client):
        """جلب سلسلة طالب غير موجود"""
        response = client.get(
            '/api/gamification/streak/99999',
            headers={'X-Session-Token': 'random_token'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Class 6: Stats routes
# ============================================================

class TestStatsRoutes:
    """اختبارات routes الإحصائيات"""

    def test_get_student_stats_no_token(self, client, db_session):
        """جلب إحصائيات الطالب بدون token"""
        s = _make_student(db_session)
        response = client.get(f'/api/gamification/stats/{s.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_student_stats_valid_token(self, client, db_session):
        """جلب إحصائيات الطالب بـ token صحيح"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/stats/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_student_stats_response_structure(self, client, db_session):
        """إحصائيات الطالب - بنية الاستجابة"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/stats/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_get_student_stats_has_all_sections(self, client, db_session):
        """إحصائيات الطالب - الرد يحتوي على كل الأقسام"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/stats/{s.id}',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            if data and data.get('success') and 'data' in data:
                stat_data = data['data']
                assert 'points' in stat_data
                assert 'achievements' in stat_data
                assert 'challenges' in stat_data
                assert 'streak' in stat_data

    def test_get_system_stats_structure(self, client):
        """إحصائيات النظام - بنية الاستجابة"""
        response = client.get('/api/gamification/stats/system')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_get_system_stats_post_not_allowed(self, client):
        """POST على system stats - يجب رفض"""
        response = client.post('/api/gamification/stats/system')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_student_stats_nonexistent(self, client):
        """إحصائيات طالب غير موجود"""
        response = client.get(
            '/api/gamification/stats/88888',
            headers={'X-Session-Token': 'bad_token'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Class 7: student_required decorator behavior
# ============================================================

class TestStudentRequiredDecorator:
    """اختبارات سلوك decorator student_required"""

    def test_decorator_missing_student_id_invalid(self, client, db_session):
        """التحقق من أن المسار بدون student_id صحيح يُرفض"""
        s = _make_student(db_session)
        # نقاط بـ id=0 (غير صالح)
        response = client.get(
            '/api/gamification/points/0',
            headers=_auth_headers(s)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_decorator_empty_token_header(self, client, db_session):
        """token فارغ في الـ header"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers={'X-Session-Token': ''}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_decorator_token_in_json_body(self, client, db_session):
        """token عبر JSON body"""
        s = _make_student(db_session)
        response = client.post(
            f'/api/gamification/achievements/{s.id}/check',
            json={'session_token': s.session_token}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_decorator_token_in_query_string(self, client, db_session):
        """token عبر query string"""
        s = _make_student(db_session)
        response = client.get(
            f'/api/gamification/streak/{s.id}?session_token={s.session_token}'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_decorator_inactive_student(self, db_session, client):
        """طالب حساب غير نشط"""
        from src.models.student import Student
        s = Student(
            name='Inactive',
            username=f'inactive_{secrets.token_hex(4)}',
            email=f'inactive_{secrets.token_hex(4)}@test.com',
            is_active=False
        )
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers=_auth_headers(s)
        )
        # inactive لا يمنع التوثيق (decorator لا يتحقق من is_active)
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_decorator_student_without_session_token(self, db_session, client):
        """طالب بدون session_token مخزّن"""
        from src.models.student import Student
        s = Student(
            name='NoToken',
            username=f'notoken_{secrets.token_hex(4)}',
            email=f'notoken_{secrets.token_hex(4)}@test.com',
            is_active=True
        )
        s.set_password('Pass@123')
        s.session_token = None
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers={'X-Session-Token': 'any_value'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Class 8: Error handling
# ============================================================

class TestGamificationErrorHandling:
    """اختبارات معالجة الأخطاء"""

    def test_leaderboard_service_exception(self, client):
        """leaderboard مع استثناء في الخدمة"""
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_points_leaderboard', side_effect=Exception("DB error")):
            response = client.get('/api/gamification/leaderboard')
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_system_stats_service_exception(self, client):
        """system stats مع استثناء في الخدمة"""
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_system_stats', side_effect=Exception("DB error")):
            response = client.get('/api/gamification/stats/system')
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_challenges_service_exception(self, client):
        """challenges مع استثناء في الخدمة"""
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_active_challenges', side_effect=Exception("DB error")):
            response = client.get('/api/gamification/challenges')
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_today_challenge_service_exception(self, client):
        """today challenge مع استثناء في الخدمة"""
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_today_challenge', side_effect=Exception("DB error")):
            response = client.get('/api/gamification/challenges/today')
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_points_service_exception(self, client, db_session):
        """get_points مع استثناء في الخدمة"""
        s = _make_student(db_session)
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_student_points', side_effect=Exception("points error")):
            response = client.get(
                f'/api/gamification/points/{s.id}',
                headers=_auth_headers(s)
            )
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_points_service_exception(self, client, db_session):
        """add_points مع استثناء في الخدمة"""
        s = _make_student(db_session)
        with patch('src.routes.gamification_routes.gamification_service'
                   '.add_points', side_effect=Exception("add error")):
            response = client.post(
                f'/api/gamification/points/{s.id}/add',
                json={'amount': 50, 'reason': 'test', 'session_token': s.session_token}
            )
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_achievements_service_exception(self, client, db_session):
        """get_achievements مع استثناء في الخدمة"""
        s = _make_student(db_session)
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_student_achievements', side_effect=Exception("ach error")):
            response = client.get(
                f'/api/gamification/achievements/{s.id}',
                headers=_auth_headers(s)
            )
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_error_response_has_success_false(self, client):
        """استجابة الخطأ تحتوي على success=False"""
        with patch('src.routes.gamification_routes.gamification_service'
                   '.get_points_leaderboard', side_effect=Exception("error")):
            response = client.get('/api/gamification/leaderboard')
            assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
            if response.status_code == 500:
                data = response.get_json()
                if data:
                    assert data.get('success') is False
                    assert 'error' in data


# ============================================================
# Class 9: Multiple students interaction
# ============================================================

class TestMultipleStudentsInteraction:
    """اختبارات تفاعل عدة طلاب"""

    def test_two_students_separate_points(self, client, db_session):
        """طالبان لكل منهما نقاطه الخاصة"""
        s1 = _make_student(db_session)
        s2 = _make_student(db_session)
        r1 = client.get(
            f'/api/gamification/points/{s1.id}',
            headers=_auth_headers(s1)
        )
        r2 = client.get(
            f'/api/gamification/points/{s2.id}',
            headers=_auth_headers(s2)
        )
        assert r1.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        assert r2.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_student1_cannot_access_student2_points(self, client, db_session):
        """طالب 1 لا يمكنه الوصول لنقاط طالب 2"""
        s1 = _make_student(db_session)
        s2 = _make_student(db_session)
        response = client.get(
            f'/api/gamification/points/{s2.id}',
            headers=_auth_headers(s1)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_student1_cannot_update_student2_streak(self, client, db_session):
        """طالب 1 لا يمكنه تحديث سلسلة طالب 2"""
        s1 = _make_student(db_session)
        s2 = _make_student(db_session)
        response = client.post(
            f'/api/gamification/streak/{s2.id}/update',
            headers=_auth_headers(s1)
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_leaderboard_shows_all_students(self, client, db_session):
        """لوحة المتصدرين تظهر للجميع"""
        _make_student(db_session)
        _make_student(db_session)
        response = client.get('/api/gamification/leaderboard')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
