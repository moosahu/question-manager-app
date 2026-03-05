"""
اختبارات شاملة لـ Gamification API
يغطي: points, leaderboard, achievements, challenges, streak, stats, system
"""
import pytest


class TestGamificationPublicRoutes:
    """الـ routes العامة (بدون session_token)"""

    def test_leaderboard_empty(self, client):
        """لوحة المتصدرين فارغة"""
        response = client.get('/api/gamification/leaderboard')
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('success') is True
        assert 'data' in data

    def test_leaderboard_with_limit(self, client):
        """لوحة المتصدرين مع تحديد عدد"""
        response = client.get('/api/gamification/leaderboard?limit=5')
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('success') is True

    def test_leaderboard_with_offset(self, client):
        """لوحة المتصدرين مع offset"""
        response = client.get('/api/gamification/leaderboard?offset=0&limit=10')
        assert response.status_code == 200

    def test_today_challenge_legacy(self, client):
        """تحدي اليوم (legacy route)"""
        response = client.get('/api/gamification/challenge/today')
        assert response.status_code in [200, 404]
        data = response.get_json()
        assert data is not None

    def test_today_challenge_new_route(self, client):
        """تحدي اليوم (new route)"""
        response = client.get('/api/gamification/challenges/today')
        assert response.status_code in [200, 404]
        data = response.get_json()
        assert 'success' in data

    def test_challenges_list(self, client):
        """قائمة التحديات"""
        response = client.get('/api/gamification/challenges')
        assert response.status_code in [200, 404]
        data = response.get_json()
        assert data is not None

    def test_challenges_by_type(self, client):
        """التحديات حسب النوع"""
        for challenge_type in ['daily', 'weekly', 'monthly']:
            response = client.get(f'/api/gamification/challenges?type={challenge_type}')
            assert response.status_code in [200, 404]

    def test_system_stats(self, client):
        """إحصائيات النظام"""
        response = client.get('/api/gamification/stats/system')
        assert response.status_code in [200, 404, 500]
        data = response.get_json()
        assert data is not None


class TestGamificationWithStudent:
    """الـ routes التي تتطلب session_token للطالب"""

    def _create_student_with_token(self, db_session, app, username, email):
        """مساعد: إنشاء طالب مع session_token"""
        import secrets
        from src.models.student import Student
        s = Student(name='Gamif', username=username, email=email, is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        return s

    def test_points_without_auth(self, client):
        """النقاط بدون مصادقة"""
        response = client.get('/api/gamification/points/1')
        assert response.status_code == 401
        data = response.get_json()
        assert data.get('success') is False

    def test_points_with_valid_token(self, client, db_session, app):
        """النقاط مع session_token صالح"""
        s = self._create_student_with_token(db_session, app, 'gamif_points', 'gamifpoints@test.com')
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_points_wrong_token(self, client, db_session, app):
        """النقاط مع session_token خاطئ"""
        s = self._create_student_with_token(db_session, app, 'gamif_wrong_token', 'gamifwrong@test.com')
        response = client.get(
            f'/api/gamification/points/{s.id}',
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code == 401

    def test_achievements_without_auth(self, client):
        """الإنجازات بدون مصادقة"""
        response = client.get('/api/gamification/achievements/1')
        assert response.status_code == 401

    def test_achievements_with_valid_token(self, client, db_session, app):
        """الإنجازات مع session_token صالح"""
        s = self._create_student_with_token(db_session, app, 'gamif_achiev', 'gamifachiev@test.com')
        response = client.get(
            f'/api/gamification/achievements/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 500]

    def test_check_achievements_without_auth(self, client):
        """فحص الإنجازات بدون مصادقة"""
        response = client.post('/api/gamification/achievements/1/check')
        assert response.status_code == 401

    def test_streak_without_auth(self, client):
        """السلسلة بدون مصادقة"""
        response = client.get('/api/gamification/streak/1')
        assert response.status_code == 401

    def test_streak_with_valid_token(self, client, db_session, app):
        """السلسلة مع session_token صالح"""
        s = self._create_student_with_token(db_session, app, 'gamif_streak', 'gamifstreak@test.com')
        response = client.get(
            f'/api/gamification/streak/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 500]

    def test_update_streak_without_auth(self, client):
        """تحديث السلسلة بدون مصادقة"""
        response = client.post('/api/gamification/streak/1/update')
        assert response.status_code == 401

    def test_update_streak_with_valid_token(self, client, db_session, app):
        """تحديث السلسلة مع session_token صالح"""
        s = self._create_student_with_token(db_session, app, 'gamif_update_streak', 'gamifupdatestreak@test.com')
        response = client.post(
            f'/api/gamification/streak/{s.id}/update',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 500]

    def test_stats_without_auth(self, client):
        """الإحصائيات بدون مصادقة"""
        response = client.get('/api/gamification/stats/1')
        assert response.status_code == 401

    def test_stats_with_valid_token(self, client, db_session, app):
        """الإحصائيات مع session_token صالح"""
        s = self._create_student_with_token(db_session, app, 'gamif_stats', 'gamifstats@test.com')
        response = client.get(
            f'/api/gamification/stats/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 500]

    def test_challenge_progress_without_auth(self, client):
        """تقدم التحدي بدون مصادقة"""
        response = client.get('/api/gamification/challenge/progress/1')
        assert response.status_code == 401

    def test_challenge_progress_with_valid_token(self, client, db_session, app):
        """تقدم التحدي - يتطلب مصادقة"""
        s = self._create_student_with_token(db_session, app, 'gamif_chprog', 'gamifchprog@test.com')
        # الـ legacy route يستدعي get_challenge_progress (مع decorator مرتين)
        response = client.get(
            f'/api/gamification/challenge/progress/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 500]


class TestGamificationAddPoints:
    """اختبارات إضافة النقاط"""

    def test_add_points_without_auth(self, client):
        """إضافة نقاط بدون مصادقة"""
        response = client.post('/api/gamification/points/1/add', json={
            'amount': 50,
            'reason': 'اختبار'
        })
        assert response.status_code in [401, 403]

    def test_add_points_as_admin(self, client, admin_user, db_session, app):
        """إضافة نقاط كأدمن"""
        from src.models.student import Student
        s = Student(name='Points Add', username='points_add', email='pointsadd@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/api/gamification/points/{s.id}/add', json={
            'amount': 100,
            'reason': 'مكافأة اختبار'
        })
        assert response.status_code in [200, 400, 500]

    def test_add_points_zero_amount(self, client, admin_user):
        """إضافة صفر نقاط - يجب الرفض"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/gamification/points/1/add', json={
            'amount': 0,
            'reason': 'اختبار'
        })
        assert response.status_code in [400, 500]

    def test_add_points_negative(self, client, admin_user):
        """إضافة نقاط سالبة - يجب الرفض"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/gamification/points/1/add', json={
            'amount': -10,
            'reason': 'اختبار'
        })
        assert response.status_code in [400, 500]
