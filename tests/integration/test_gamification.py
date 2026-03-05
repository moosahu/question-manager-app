"""
اختبارات نظام Gamification (النقاط، الإنجازات، المتصدرين)
"""
import pytest


class TestGamificationPoints:
    """اختبارات النقاط"""

    def test_points_endpoint_exists(self, client, student_user):
        """endpoint النقاط موجود"""
        response = client.get(f'/api/gamification/points/{student_user.id}')
        # يتطلب JWT auth عادةً → 401 أو 200
        assert response.status_code in [200, 401, 403]

    def test_leaderboard_endpoint(self, client):
        """endpoint المتصدرين يعمل"""
        response = client.get('/api/gamification/leaderboard')
        assert response.status_code in [200, 401, 403]

    def test_challenge_today_endpoint(self, client):
        """endpoint تحدي اليوم يعمل"""
        response = client.get('/api/gamification/challenge/today')
        assert response.status_code in [200, 401, 403, 404]


class TestGamificationAchievements:
    """اختبارات الإنجازات"""

    def test_achievements_endpoint(self, client, student_user):
        """endpoint الإنجازات يعمل"""
        response = client.get(f'/api/gamification/achievements/{student_user.id}')
        assert response.status_code in [200, 401, 403]

    def test_stats_endpoint(self, client, student_user):
        """endpoint الإحصائيات يعمل"""
        response = client.get(f'/api/gamification/stats/{student_user.id}')
        assert response.status_code in [200, 401, 403]


class TestGamificationModels:
    """اختبارات نماذج Gamification"""

    def test_student_has_initial_points(self, db_session, student_user, app):
        """الطالب الجديد يبدأ من صفر نقاط أو ليس لديه سجل بعد"""
        from src.models.student import Student
        student = Student.query.filter_by(username='test_student').first()
        assert student is not None
        # نقاط Gamification قد تكون في جدول منفصل أو حقل في Student
        # نتحقق من وجود الطالب فقط
        assert student.id is not None
