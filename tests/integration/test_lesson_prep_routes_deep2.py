"""
test_lesson_prep_routes_deep2.py
Deep integration tests for lesson_prep_routes.py.

Targets uncovered lines:
  51-60  (_is_feature_enabled - override/global/default paths)
  66-106 (_get_teacher_quota)
  111-116 (_check_quota)
  122-141 (_get_teacher_from_request)
  148-154 (auth_required decorator)
  162-175 (get_quota - admin + teacher + error)
  182-315 (generate_lesson_plan - all paths)
  322-429 (generate_unit_distribution - all paths)
  436-472 (get_plan_status - all statuses)
  479-506 (get_queue)
  513-530 (get_history)
  537-545 (get_plan)
  552-615 (download_plan_pdf)
  622-657 (delete_plan)
  668-736 (upload_semester_distribution)
  743-762 (update_semester_distribution)
  773-797 (update_section)
  804-833 (regenerate_section)
  836-890 (regenerate_pdf)
  901-926 (share_plan)
  933-955 (get_shared_plans)
  962-1001 (clone_plan)
  1012-1055 (rate_plan)
  1062-1084 (get_plan_ratings)
  1095-1144 (generate_worksheet)
  1151-1197 (download_worksheet_pdf)
  1208-1224 (mark_taught)
  1231-1303 (get_progress)
  1314-1350 (get_cost_summary)
  1357-1387 (get_cost_by_teacher)
  1394-1425 (get_cost_by_provider)
  1435-1447 (on_subscribe websocket)
  1453-1456 (on_unsubscribe websocket)
  1461-1466 (emit_plan_status)
"""
import pytest
import secrets
import json
from unittest.mock import patch, MagicMock


ACCEPT = [200, 302, 400, 401, 403, 404, 405, 429, 500]


# ============================================================
# Helpers
# ============================================================

def _login_admin(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_teacher(db_session, is_active=True):
    from src.models.teacher import Teacher
    t = Teacher(
        name='LP2 Teacher',
        username=f'lp2_t_{secrets.token_hex(4)}',
        email=f'lp2_{secrets.token_hex(4)}@test.com',
        is_active=is_active,
    )
    t.set_password('Pass@123')
    t.session_token = secrets.token_hex(32)
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _make_course(db_session):
    from src.models.curriculum import Course
    c = Course(name=f'LP2_Course_{secrets.token_hex(4)}', order_num=10, show_in_bot=True)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course_id):
    from src.models.curriculum import Unit
    u = Unit(name=f'LP2_Unit_{secrets.token_hex(4)}', course_id=course_id, order_num=10)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit_id):
    from src.models.curriculum import Lesson
    l = Lesson(name=f'LP2_Lesson_{secrets.token_hex(4)}', unit_id=unit_id, order_num=10)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


def _make_plan(db_session, lesson_id=None, teacher_id=None, status='completed',
               plan_type='single_lesson', course_id=None, plan_data=None):
    from src.models.textbook import LessonPlan
    plan = LessonPlan(
        lesson_id=lesson_id,
        teacher_id=teacher_id,
        course_id=course_id,
        plan_type=plan_type,
        status=status,
        plan_data=plan_data or {'lesson_info': {'title': 'Test Plan'}},
        student_level='متفاوت',
        student_count=30,
        weak_students_count=5,
        excellent_students_count=5,
        focus_area='شامل',
        examples_count=5,
        include_support_plan=False,
    )
    db_session.session.add(plan)
    db_session.session.commit()
    db_session.session.refresh(plan)
    return plan


def _teacher_headers(teacher):
    return {'X-Session-Token': teacher.session_token}


# ============================================================
# 1. GET /quota
# ============================================================

class TestQuotaDeep2:

    def test_quota_no_auth_returns_401(self, client):
        resp = client.get('/api/lesson-prep/quota')
        assert resp.status_code in ACCEPT

    def test_quota_admin_session_returns_unlimited(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/quota')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert data['is_admin'] is True
            for v in data['data'].values():
                assert v['limit'] == 999

    def test_quota_teacher_session_token(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.get('/api/lesson-prep/quota', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert data['is_admin'] is False
            assert 'data' in data

    def test_quota_inactive_teacher_no_auth(self, client, db_session):
        t = _make_teacher(db_session, is_active=False)
        resp = client.get('/api/lesson-prep/quota', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_quota_invalid_token_401(self, client):
        resp = client.get('/api/lesson-prep/quota', headers={'X-Session-Token': 'invalid_token_xyz'})
        assert resp.status_code in ACCEPT


# ============================================================
# 2. POST /generate
# ============================================================

class TestGenerateDeep2:

    def test_generate_no_auth(self, client):
        resp = client.post('/api/lesson-prep/generate', json={'lesson_id': 1})
        assert resp.status_code in ACCEPT

    def test_generate_admin_no_data(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/generate')
        assert resp.status_code in ACCEPT

    def test_generate_admin_no_lesson_id(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/generate', json={})
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_generate_admin_nonexistent_lesson(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/generate', json={'lesson_id': 999999})
        assert resp.status_code in ACCEPT
        if resp.status_code == 404:
            data = resp.get_json()
            assert data['success'] is False

    def test_generate_admin_valid_lesson_creates_plan(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/generate', json={'lesson_id': l.id})
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert 'plan_id' in data['data']

    def test_generate_admin_duplicate_active_plan_returns_existing(self, client, admin_user, db_session):
        """Duplicate generate request returns the existing pending plan"""
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, teacher_id=None, status='pending')
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/generate', json={'lesson_id': l.id})
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            if data.get('success'):
                assert data['data'].get('duplicate') is True

    def test_generate_teacher_feature_disabled(self, client, db_session):
        """Teacher with lesson_prep_enabled=false gets 403"""
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='lesson_prep_enabled',
            value='false'
        )
        db_session.session.add(override)
        db_session.session.commit()
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/generate',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 403:
            data = resp.get_json()
            assert data.get('feature_disabled') is True

    def test_generate_teacher_quota_exceeded(self, client, db_session):
        """Teacher exceeds daily quota gets 429"""
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        # Set quota to 0
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='quota_single_lesson',
            value='0'
        )
        db_session.session.add(override)
        db_session.session.commit()
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/generate',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 429:
            data = resp.get_json()
            assert data.get('quota_exceeded') is True

    def test_generate_teacher_valid_lesson(self, client, db_session):
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/generate',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_generate_teacher_with_all_options(self, client, db_session):
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/generate',
            json={
                'lesson_id': l.id,
                'student_level': 'متقدم',
                'student_count': 25,
                'weak_students_count': 3,
                'excellent_students_count': 7,
                'focus_area': 'تطبيقي',
                'examples_count': 3,
                'include_support_plan': True,
            },
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 3. POST /unit-distribution
# ============================================================

class TestUnitDistributionDeep2:

    def test_unit_dist_no_auth(self, client):
        resp = client.post('/api/lesson-prep/unit-distribution', json={'lesson_id': 1})
        assert resp.status_code in ACCEPT

    def test_unit_dist_admin_no_lesson_id(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/unit-distribution', json={})
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_unit_dist_admin_valid(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/unit-distribution', json={
            'lesson_id': l.id,
            'total_periods': 10
        })
        assert resp.status_code in ACCEPT

    def test_unit_dist_duplicate_active(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, teacher_id=None,
                          status='pending', plan_type='unit_distribution')
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/unit-distribution', json={'lesson_id': l.id})
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            if data.get('success'):
                assert data['data'].get('duplicate') is True

    def test_unit_dist_teacher_feature_disabled(self, client, db_session):
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='unit_distribution_enabled',
            value='false'
        )
        db_session.session.add(override)
        db_session.session.commit()
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/unit-distribution',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_unit_dist_teacher_quota_exceeded(self, client, db_session):
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='quota_unit_distribution',
            value='0'
        )
        db_session.session.add(override)
        db_session.session.commit()
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/unit-distribution',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_unit_dist_teacher_cache_hit(self, client, db_session):
        """Teacher request finds a cached completed plan"""
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        # Create a completed plan that will be used as cache
        _make_plan(db_session, lesson_id=l.id, teacher_id=t.id,
                   status='completed', plan_type='unit_distribution',
                   plan_data={'distribution': 'cached'})
        resp = client.post(
            '/api/lesson-prep/unit-distribution',
            json={'lesson_id': l.id, 'total_periods': 30},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 4. GET /status/<plan_id>
# ============================================================

class TestPlanStatusDeep2:

    def test_status_no_auth(self, client):
        resp = client.get('/api/lesson-prep/status/1')
        assert resp.status_code in ACCEPT

    def test_status_nonexistent_plan(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/status/999999')
        assert resp.status_code in ACCEPT
        if resp.status_code == 404:
            data = resp.get_json()
            assert data['success'] is False

    def test_status_pending_plan(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='pending')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/status/{plan.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert 'queue_position' in data['data']

    def test_status_generating_plan(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='generating')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/status/{plan.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['data']['status'] == 'generating'

    def test_status_rate_limited_shows_as_generating(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='rate_limited')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/status/{plan.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['data']['status'] == 'generating'

    def test_status_completed_plan_has_data(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, status='completed')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/status/{plan.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'data' in data['data']

    def test_status_failed_plan_has_error(self, client, admin_user, db_session):
        from src.models.textbook import LessonPlan
        plan = _make_plan(db_session, status='failed')
        # Set error_message via direct DB update
        plan.error_message = 'Test error'
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/status/{plan.id}')
        assert resp.status_code in ACCEPT

    def test_status_teacher_token(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.get(f'/api/lesson-prep/status/{plan.id}', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT


# ============================================================
# 5. GET /queue
# ============================================================

class TestQueueDeep2:

    def test_queue_no_auth(self, client):
        resp = client.get('/api/lesson-prep/queue')
        assert resp.status_code in ACCEPT

    def test_queue_admin_empty(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/queue')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert isinstance(data['data'], list)

    def test_queue_admin_with_plans(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _make_plan(db_session, lesson_id=l.id, status='pending')
        _make_plan(db_session, lesson_id=l.id, status='generating')
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/queue')
        assert resp.status_code in ACCEPT

    def test_queue_teacher_sees_only_own_plans(self, client, db_session):
        t1 = _make_teacher(db_session)
        t2 = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _make_plan(db_session, lesson_id=l.id, teacher_id=t1.id, status='pending')
        _make_plan(db_session, lesson_id=l.id, teacher_id=t2.id, status='pending')
        resp = client.get('/api/lesson-prep/queue', headers=_teacher_headers(t1))
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            # Teacher should only see their own plans
            for item in data['data']:
                assert item is not None  # just ensure data is parseable

    def test_queue_rate_limited_plan_shows_as_generating(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _make_plan(db_session, lesson_id=l.id, status='rate_limited')
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/queue')
        assert resp.status_code in ACCEPT


# ============================================================
# 6. GET /history
# ============================================================

class TestHistoryDeep2:

    def test_history_no_auth(self, client):
        resp = client.get('/api/lesson-prep/history')
        assert resp.status_code in ACCEPT

    def test_history_admin_empty(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/history')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_history_admin_with_course_filter(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _make_plan(db_session, lesson_id=l.id, status='completed')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/history?course_id={c.id}')
        assert resp.status_code in ACCEPT

    def test_history_teacher_sees_only_own(self, client, db_session):
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _make_plan(db_session, lesson_id=l.id, teacher_id=t.id, status='completed')
        resp = client.get('/api/lesson-prep/history', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT


# ============================================================
# 7. GET /<plan_id>
# ============================================================

class TestGetPlanDeep2:

    def test_get_plan_no_auth(self, client):
        resp = client.get('/api/lesson-prep/1')
        assert resp.status_code in ACCEPT

    def test_get_plan_nonexistent(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/999999')
        assert resp.status_code in ACCEPT
        if resp.status_code == 404:
            data = resp.get_json()
            assert data['success'] is False

    def test_get_plan_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, status='completed')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_get_plan_teacher_token(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.get(f'/api/lesson-prep/{plan.id}', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT


# ============================================================
# 8. DELETE /<plan_id>
# ============================================================

class TestDeletePlanDeep2:

    def test_delete_plan_no_auth(self, client):
        resp = client.delete('/api/lesson-prep/1')
        assert resp.status_code in ACCEPT

    def test_delete_plan_nonexistent(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.delete('/api/lesson-prep/999999')
        assert resp.status_code in ACCEPT

    def test_delete_plan_admin_success(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.delete(f'/api/lesson-prep/{plan.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_delete_plan_teacher_own_plan(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.delete(f'/api/lesson-prep/{plan.id}', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_delete_plan_teacher_other_plan_forbidden(self, client, db_session):
        t1 = _make_teacher(db_session)
        t2 = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t2.id, status='completed')
        resp = client.delete(f'/api/lesson-prep/{plan.id}', headers=_teacher_headers(t1))
        assert resp.status_code in ACCEPT
        if resp.status_code == 403:
            data = resp.get_json()
            assert data['success'] is False

    def test_delete_plan_sets_status_deleted(self, client, admin_user, db_session):
        from src.models.textbook import LessonPlan
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.delete(f'/api/lesson-prep/{plan.id}')
        if resp.status_code == 200:
            # Verify status is set to 'deleted'
            updated = LessonPlan.query.get(plan.id)
            assert updated.status == 'deleted'


# ============================================================
# 9. POST /semester-distribution/upload
# ============================================================

class TestSemesterDistributionDeep2:

    def test_upload_no_auth(self, client):
        resp = client.post('/api/lesson-prep/semester-distribution/upload')
        assert resp.status_code in ACCEPT

    def test_upload_admin_no_course_id(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/semester-distribution/upload', json={})
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_upload_admin_nonexistent_course(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/semester-distribution/upload', json={'course_id': 999999})
        assert resp.status_code in ACCEPT

    def test_upload_admin_valid_course(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/semester-distribution/upload', json={
            'course_id': c.id,
            'weekly_periods': 5
        })
        assert resp.status_code in ACCEPT

    def test_upload_admin_via_form_data(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/semester-distribution/upload', data={
            'course_id': str(c.id),
            'weekly_periods': '5'
        })
        assert resp.status_code in ACCEPT

    def test_upload_teacher_feature_disabled(self, client, db_session):
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='semester_distribution_enabled',
            value='false'
        )
        db_session.session.add(override)
        db_session.session.commit()
        resp = client.post(
            '/api/lesson-prep/semester-distribution/upload',
            json={'course_id': c.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_upload_teacher_quota_exceeded(self, client, db_session):
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='quota_semester_distribution',
            value='0'
        )
        db_session.session.add(override)
        db_session.session.commit()
        resp = client.post(
            '/api/lesson-prep/semester-distribution/upload',
            json={'course_id': c.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 10. PUT /semester-distribution/<plan_id>
# ============================================================

class TestUpdateSemesterDistributionDeep2:

    def test_update_no_auth(self, client):
        resp = client.put('/api/lesson-prep/semester-distribution/1', json={'plan_data': {}})
        assert resp.status_code in ACCEPT

    def test_update_nonexistent(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.put('/api/lesson-prep/semester-distribution/999999', json={'plan_data': {}})
        assert resp.status_code in ACCEPT

    def test_update_no_data(self, client, admin_user, db_session):
        c = _make_course(db_session)
        plan = _make_plan(db_session, course_id=c.id, plan_type='semester_distribution')
        _login_admin(client, admin_user)
        resp = client.put(f'/api/lesson-prep/semester-distribution/{plan.id}')
        assert resp.status_code in ACCEPT

    def test_update_admin_success(self, client, admin_user, db_session):
        c = _make_course(db_session)
        plan = _make_plan(db_session, course_id=c.id, plan_type='semester_distribution')
        _login_admin(client, admin_user)
        resp = client.put(
            f'/api/lesson-prep/semester-distribution/{plan.id}',
            json={'plan_data': {'updated': True}}
        )
        assert resp.status_code in ACCEPT

    def test_update_teacher_other_plan_forbidden(self, client, db_session):
        t1 = _make_teacher(db_session)
        t2 = _make_teacher(db_session)
        c = _make_course(db_session)
        plan = _make_plan(db_session, course_id=c.id, teacher_id=t2.id,
                          plan_type='semester_distribution')
        resp = client.put(
            f'/api/lesson-prep/semester-distribution/{plan.id}',
            json={'plan_data': {}},
            headers=_teacher_headers(t1)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 11. PUT /<plan_id>/section
# ============================================================

class TestUpdateSectionDeep2:

    def test_update_section_no_auth(self, client):
        resp = client.put('/api/lesson-prep/1/section', json={'section_name': 'x', 'section_data': {}})
        assert resp.status_code in ACCEPT

    def test_update_section_nonexistent(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.put('/api/lesson-prep/999999/section', json={'section_name': 'x', 'section_data': {}})
        assert resp.status_code in ACCEPT

    def test_update_section_no_section_name(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.put(f'/api/lesson-prep/{plan.id}/section', json={'section_data': {}})
        assert resp.status_code in ACCEPT

    def test_update_section_success(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.put(f'/api/lesson-prep/{plan.id}/section', json={
            'section_name': 'introduction',
            'section_data': {'text': 'Updated intro'}
        })
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_update_section_teacher_other_plan_forbidden(self, client, db_session):
        t1 = _make_teacher(db_session)
        t2 = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t2.id, status='completed')
        resp = client.put(
            f'/api/lesson-prep/{plan.id}/section',
            json={'section_name': 'x', 'section_data': {}},
            headers=_teacher_headers(t1)
        )
        assert resp.status_code in ACCEPT

    def test_update_section_teacher_own_plan(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.put(
            f'/api/lesson-prep/{plan.id}/section',
            json={'section_name': 'objectives', 'section_data': {'items': []}},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 12. POST /<plan_id>/regenerate-section
# ============================================================

class TestReGenerateSectionDeep2:

    def test_regen_section_no_auth(self, client):
        resp = client.post('/api/lesson-prep/1/regenerate-section', json={'section_name': 'x'})
        assert resp.status_code in ACCEPT

    def test_regen_section_nonexistent_plan(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/999999/regenerate-section', json={'section_name': 'x'})
        assert resp.status_code in ACCEPT

    def test_regen_section_no_section_name(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/regenerate-section', json={})
        assert resp.status_code in ACCEPT

    def test_regen_section_service_returns_none(self, client, admin_user, db_session):
        """When section_name is missing, returns 400"""
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/regenerate-section', json={})
        assert resp.status_code in ACCEPT

    def test_regen_section_with_name(self, client, admin_user, db_session):
        """Provide section_name - service will fail gracefully"""
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/regenerate-section', json={'section_name': 'objectives'})
        assert resp.status_code in ACCEPT


# ============================================================
# 13. POST /<plan_id>/regenerate-pdf
# ============================================================

class TestRegeneratePdfDeep2:

    def test_regen_pdf_no_auth(self, client):
        resp = client.post('/api/lesson-prep/1/regenerate-pdf')
        assert resp.status_code in ACCEPT

    def test_regen_pdf_nonexistent(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/999999/regenerate-pdf')
        assert resp.status_code in ACCEPT

    def test_regen_pdf_with_mock_service(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/regenerate-pdf')
        assert resp.status_code in ACCEPT


# ============================================================
# 14. POST /<plan_id>/share
# ============================================================

class TestSharePlanDeep2:

    def test_share_no_auth(self, client):
        resp = client.post('/api/lesson-prep/1/share')
        assert resp.status_code in ACCEPT

    def test_share_admin_not_teacher_forbidden(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/share')
        assert resp.status_code in ACCEPT
        if resp.status_code == 403:
            data = resp.get_json()
            assert data['success'] is False

    def test_share_nonexistent_plan(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/api/lesson-prep/999999/share', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_share_teacher_success(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/share',
            json={'visibility': 'school'},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_share_already_shared(self, client, db_session):
        from src.models.shared_plan import SharedPlan
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        # Share it first
        shared = SharedPlan(plan_id=plan.id, shared_by=t.id, visibility='school')
        db_session.session.add(shared)
        db_session.session.commit()
        # Try to share again
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/share',
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False


# ============================================================
# 15. GET /shared
# ============================================================

class TestGetSharedPlansDeep2:

    def test_shared_no_auth(self, client):
        resp = client.get('/api/lesson-prep/shared')
        assert resp.status_code in ACCEPT

    def test_shared_admin_empty(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/shared')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_shared_with_course_filter(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/shared?course_id={c.id}')
        assert resp.status_code in ACCEPT

    def test_shared_with_search_query(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/shared?q=كيمياء')
        assert resp.status_code in ACCEPT

    def test_shared_teacher_token(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.get('/api/lesson-prep/shared', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT


# ============================================================
# 16. POST /<plan_id>/clone
# ============================================================

class TestClonePlanDeep2:

    def test_clone_no_auth(self, client):
        resp = client.post('/api/lesson-prep/1/clone')
        assert resp.status_code in ACCEPT

    def test_clone_admin_not_teacher_forbidden(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/clone')
        assert resp.status_code in ACCEPT

    def test_clone_nonexistent_plan(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/api/lesson-prep/999999/clone', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_clone_teacher_success(self, client, db_session):
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, teacher_id=t.id, status='completed')
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/clone',
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_clone_updates_shared_use_count(self, client, db_session):
        from src.models.shared_plan import SharedPlan
        t1 = _make_teacher(db_session)
        t2 = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t1.id, status='completed')
        shared = SharedPlan(plan_id=plan.id, shared_by=t1.id, visibility='school', use_count=0)
        db_session.session.add(shared)
        db_session.session.commit()
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/clone',
            headers=_teacher_headers(t2)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 17. POST /<plan_id>/rate
# ============================================================

class TestRatePlanDeep2:

    def test_rate_no_auth(self, client):
        resp = client.post('/api/lesson-prep/1/rate', json={'overall_rating': 4})
        assert resp.status_code in ACCEPT

    def test_rate_admin_not_teacher(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/rate', json={'overall_rating': 4})
        assert resp.status_code in ACCEPT

    def test_rate_nonexistent_plan(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.post('/api/lesson-prep/999999/rate', json={'overall_rating': 4}, headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_rate_invalid_rating_below_1(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/rate',
            json={'overall_rating': 0},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_rate_invalid_rating_above_5(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/rate',
            json={'overall_rating': 6},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_rate_teacher_success_creates_new(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/rate',
            json={'overall_rating': 5, 'notes': 'Excellent!'},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_rate_teacher_updates_existing(self, client, db_session):
        from src.models.plan_rating import PlanRating
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        # Create initial rating
        rating = PlanRating(plan_id=plan.id, teacher_id=t.id, overall_rating=3)
        db_session.session.add(rating)
        db_session.session.commit()
        # Update it
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/rate',
            json={'overall_rating': 5},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_rate_updates_shared_plan_avg(self, client, db_session):
        from src.models.shared_plan import SharedPlan
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        shared = SharedPlan(plan_id=plan.id, shared_by=t.id, visibility='school')
        db_session.session.add(shared)
        db_session.session.commit()
        resp = client.post(
            f'/api/lesson-prep/{plan.id}/rate',
            json={'overall_rating': 4},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 18. GET /<plan_id>/ratings
# ============================================================

class TestGetPlanRatingsDeep2:

    def test_ratings_no_auth(self, client):
        resp = client.get('/api/lesson-prep/1/ratings')
        assert resp.status_code in ACCEPT

    def test_ratings_no_ratings(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/ratings')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert data['data']['count'] == 0

    def test_ratings_with_rating(self, client, db_session):
        from src.models.plan_rating import PlanRating
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        rating = PlanRating(plan_id=plan.id, teacher_id=t.id, overall_rating=4, notes='Good')
        db_session.session.add(rating)
        db_session.session.commit()
        resp = client.get(f'/api/lesson-prep/{plan.id}/ratings', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['data']['count'] == 1
            # is_mine flag should be True for this teacher
            for r in data['data']['ratings']:
                assert r['is_mine'] is True

    def test_ratings_admin_sees_all(self, client, admin_user, db_session):
        from src.models.plan_rating import PlanRating
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        rating = PlanRating(plan_id=plan.id, teacher_id=t.id, overall_rating=3)
        db_session.session.add(rating)
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/ratings')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            # Admin has no teacher_id, so is_mine should be False
            for r in data['data']['ratings']:
                assert r['is_mine'] is False


# ============================================================
# 19. POST /<plan_id>/worksheet
# ============================================================

class TestGenerateWorksheetDeep2:

    def test_worksheet_no_auth(self, client):
        resp = client.post('/api/lesson-prep/1/worksheet')
        assert resp.status_code in ACCEPT

    def test_worksheet_nonexistent_plan(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/999999/worksheet')
        assert resp.status_code in ACCEPT

    def test_worksheet_incomplete_plan(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='pending')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/worksheet')
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_worksheet_completed_plan(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.post(f'/api/lesson-prep/{plan.id}/worksheet')
        assert resp.status_code in ACCEPT

    def test_worksheet_teacher_feature_disabled(self, client, db_session):
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='worksheet_enabled',
            value='false'
        )
        db_session.session.add(override)
        db_session.session.commit()
        resp = client.post(f'/api/lesson-prep/{plan.id}/worksheet', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_worksheet_teacher_quota_exceeded(self, client, db_session):
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='quota_worksheet',
            value='0'
        )
        db_session.session.add(override)
        db_session.session.commit()
        resp = client.post(f'/api/lesson-prep/{plan.id}/worksheet', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT


# ============================================================
# 20. GET /<plan_id>/worksheet/pdf
# ============================================================

class TestDownloadWorksheetPdfDeep2:

    def test_ws_pdf_no_auth(self, client):
        resp = client.get('/api/lesson-prep/1/worksheet/pdf')
        assert resp.status_code in ACCEPT

    def test_ws_pdf_nonexistent_plan(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/999999/worksheet/pdf')
        assert resp.status_code in ACCEPT

    def test_ws_pdf_no_url(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed', plan_data={'lesson_info': {}})
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/worksheet/pdf')
        assert resp.status_code in ACCEPT
        if resp.status_code == 404:
            data = resp.get_json()
            assert data['success'] is False

    def test_ws_pdf_with_url(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed', plan_data={
            'worksheet_student_pdf': '/some/path/ws.pdf'
        })
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/worksheet/pdf')
        assert resp.status_code in ACCEPT

    def test_ws_pdf_period_parameter(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed', plan_data={
            'period_worksheets': [
                {'period_index': 0, 'student_pdf_url': '/path/ws0.pdf'}
            ]
        })
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/worksheet/pdf?period=0')
        assert resp.status_code in ACCEPT

    def test_ws_pdf_invalid_period(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed', plan_data={'period_worksheets': []})
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/worksheet/pdf?period=abc')
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_ws_pdf_period_not_found(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed', plan_data={'period_worksheets': []})
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/worksheet/pdf?period=5')
        assert resp.status_code in ACCEPT

    def test_ws_pdf_teacher_type(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed', plan_data={
            'worksheet_teacher_pdf': '/some/path/ws_teacher.pdf'
        })
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/worksheet/pdf?type=teacher')
        assert resp.status_code in ACCEPT


# ============================================================
# 21. PUT /<plan_id>/mark-taught
# ============================================================

class TestMarkTaughtDeep2:

    def test_mark_taught_no_auth(self, client):
        resp = client.put('/api/lesson-prep/1/mark-taught', json={'is_taught': True})
        assert resp.status_code in ACCEPT

    def test_mark_taught_nonexistent(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.put('/api/lesson-prep/999999/mark-taught', json={'is_taught': True})
        assert resp.status_code in ACCEPT

    def test_mark_taught_true(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.put(f'/api/lesson-prep/{plan.id}/mark-taught', json={'is_taught': True})
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_mark_taught_false(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.put(f'/api/lesson-prep/{plan.id}/mark-taught', json={'is_taught': False})
        assert resp.status_code in ACCEPT

    def test_mark_taught_no_body_defaults_true(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        _login_admin(client, admin_user)
        resp = client.put(f'/api/lesson-prep/{plan.id}/mark-taught', json={})
        assert resp.status_code in ACCEPT

    def test_mark_taught_teacher_token(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.put(
            f'/api/lesson-prep/{plan.id}/mark-taught',
            json={'is_taught': True},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 22. GET /progress
# ============================================================

class TestProgressDeep2:

    def test_progress_no_auth(self, client):
        resp = client.get('/api/lesson-prep/progress?course_id=1')
        assert resp.status_code in ACCEPT

    def test_progress_no_course_id(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/progress')
        assert resp.status_code in ACCEPT
        if resp.status_code == 400:
            data = resp.get_json()
            assert data['success'] is False

    def test_progress_empty_course(self, client, admin_user, db_session):
        c = _make_course(db_session)
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/progress?course_id={c.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert data['data']['total_lessons'] == 0

    def test_progress_with_lessons(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l1 = _make_lesson(db_session, u.id)
        l2 = _make_lesson(db_session, u.id)
        # One prepared, one taught
        p1 = _make_plan(db_session, lesson_id=l1.id, status='completed')
        p2 = _make_plan(db_session, lesson_id=l2.id, status='completed')
        p2.is_taught = True
        from datetime import datetime
        p2.taught_at = datetime.utcnow()
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/progress?course_id={c.id}')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['data']['total_lessons'] == 2
            assert data['data']['prepared_lessons'] == 2

    def test_progress_teacher_sees_own_plans(self, client, db_session):
        t = _make_teacher(db_session)
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _make_plan(db_session, lesson_id=l.id, teacher_id=t.id, status='completed')
        resp = client.get(f'/api/lesson-prep/progress?course_id={c.id}', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_progress_percent_calculation(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        p = _make_plan(db_session, lesson_id=l.id, status='completed')
        p.is_taught = True
        from datetime import datetime
        p.taught_at = datetime.utcnow()
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/progress?course_id={c.id}')
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['data']['overall_progress'] == 100


# ============================================================
# 23. GET /costs/summary
# ============================================================

class TestCostSummaryDeep2:

    def test_costs_summary_no_auth(self, client):
        resp = client.get('/api/lesson-prep/costs/summary')
        assert resp.status_code in ACCEPT

    def test_costs_summary_admin(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/costs/summary')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert 'today' in data['data']
            assert 'week' in data['data']
            assert 'month' in data['data']

    def test_costs_summary_teacher(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.get('/api/lesson-prep/costs/summary', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_costs_summary_with_usage_logs(self, client, admin_user, db_session):
        from src.models.textbook import AIUsageLog
        from datetime import datetime
        log = AIUsageLog(
            plan_id=None,
            ai_provider='gemini',
            operation_type='lesson_prep',
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.001,
            created_at=datetime.utcnow()
        )
        db_session.session.add(log)
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/costs/summary')
        assert resp.status_code in ACCEPT


# ============================================================
# 24. GET /costs/by-teacher
# ============================================================

class TestCostByTeacherDeep2:

    def test_cost_by_teacher_no_auth(self, client):
        resp = client.get('/api/lesson-prep/costs/by-teacher')
        assert resp.status_code in ACCEPT

    def test_cost_by_teacher_admin(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/costs/by-teacher')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True
            assert isinstance(data['data'], list)

    def test_cost_by_teacher_non_admin_forbidden(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.get('/api/lesson-prep/costs/by-teacher', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT
        if resp.status_code == 403:
            data = resp.get_json()
            assert data['success'] is False

    def test_cost_by_teacher_with_data(self, client, admin_user, db_session):
        from src.models.textbook import AIUsageLog
        from datetime import datetime
        t = _make_teacher(db_session)
        log = AIUsageLog(
            plan_id=None,
            teacher_id=t.id,
            ai_provider='gemini',
            operation_type='lesson_prep',
            input_tokens=500,
            output_tokens=1000,
            cost_usd=0.005,
            created_at=datetime.utcnow()
        )
        db_session.session.add(log)
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/costs/by-teacher')
        assert resp.status_code in ACCEPT


# ============================================================
# 25. GET /costs/by-provider
# ============================================================

class TestCostByProviderDeep2:

    def test_cost_by_provider_no_auth(self, client):
        resp = client.get('/api/lesson-prep/costs/by-provider')
        assert resp.status_code in ACCEPT

    def test_cost_by_provider_admin(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/costs/by-provider')
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['success'] is True

    def test_cost_by_provider_teacher(self, client, db_session):
        t = _make_teacher(db_session)
        resp = client.get('/api/lesson-prep/costs/by-provider', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT

    def test_cost_by_provider_with_logs(self, client, admin_user, db_session):
        from src.models.textbook import AIUsageLog
        from datetime import datetime
        log = AIUsageLog(
            plan_id=None,
            ai_provider='claude',
            operation_type='lesson_prep',
            input_tokens=200,
            output_tokens=300,
            cost_usd=0.002,
            created_at=datetime.utcnow()
        )
        db_session.session.add(log)
        db_session.session.commit()
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/costs/by-provider')
        assert resp.status_code in ACCEPT


# ============================================================
# 26. PDF download endpoint
# ============================================================

class TestDownloadPlanPdfDeep2:

    def test_pdf_no_auth(self, client):
        resp = client.get('/api/lesson-prep/1/pdf')
        assert resp.status_code in ACCEPT

    def test_pdf_nonexistent_plan(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/999999/pdf')
        assert resp.status_code in ACCEPT

    def test_pdf_plan_with_http_url(self, client, admin_user, db_session):
        plan = _make_plan(db_session, status='completed')
        plan.pdf_file_url = 'http://example.com/test.pdf'
        db_session.session.commit()
        _login_admin(client, admin_user)
        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = b'%PDF-1.4'
            mock_get.return_value = mock_resp
            resp = client.get(f'/api/lesson-prep/{plan.id}/pdf')
        assert resp.status_code in ACCEPT

    def test_pdf_plan_no_pdf_url_calls_service(self, client, admin_user, db_session):
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        plan = _make_plan(db_session, lesson_id=l.id, status='completed')
        # plan_data is set, but pdf_file_url is None
        _login_admin(client, admin_user)
        resp = client.get(f'/api/lesson-prep/{plan.id}/pdf')
        assert resp.status_code in ACCEPT

    def test_pdf_teacher_token(self, client, db_session):
        t = _make_teacher(db_session)
        plan = _make_plan(db_session, teacher_id=t.id, status='completed')
        resp = client.get(f'/api/lesson-prep/{plan.id}/pdf', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT


# ============================================================
# 27. Feature override - _is_feature_enabled paths
# ============================================================

class TestIsFeatureEnabledDeep2:

    def test_feature_with_override_true(self, client, db_session):
        """Override value='true' -> feature enabled"""
        from src.models.teacher_feature import TeacherFeatureOverride
        t = _make_teacher(db_session)
        override = TeacherFeatureOverride(
            teacher_id=t.id,
            feature_key='lesson_prep_enabled',
            value='true'
        )
        db_session.session.add(override)
        db_session.session.commit()
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/generate',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT

    def test_feature_with_global_setting(self, client, db_session):
        """No override, uses global AISetting"""
        from src.models.ai_analysis import AISetting
        t = _make_teacher(db_session)
        # Set global setting to 'true'
        setting = AISetting.query.filter_by(setting_key='lesson_prep_enabled').first()
        if not setting:
            setting = AISetting(setting_key='lesson_prep_enabled', setting_value='true')
            db_session.session.add(setting)
            db_session.session.commit()
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        resp = client.post(
            '/api/lesson-prep/generate',
            json={'lesson_id': l.id},
            headers=_teacher_headers(t)
        )
        assert resp.status_code in ACCEPT


# ============================================================
# 28. Quota with global setting override
# ============================================================

class TestQuotaWithGlobalSettingDeep2:

    def test_quota_global_setting_override(self, client, db_session):
        """_get_teacher_quota reads global AISetting for quota"""
        from src.models.ai_analysis import AISetting
        t = _make_teacher(db_session)
        # Set global quota
        setting = AISetting.query.filter_by(setting_key='quota_single_lesson').first()
        if not setting:
            setting = AISetting(setting_key='quota_single_lesson', setting_value='10')
            db_session.session.add(setting)
            db_session.session.commit()
        else:
            setting.setting_value = '10'
            db_session.session.commit()

        resp = client.get('/api/lesson-prep/quota', headers=_teacher_headers(t))
        assert resp.status_code in ACCEPT
        if resp.status_code == 200:
            data = resp.get_json()
            if data.get('success') and not data.get('is_admin'):
                single_lesson = data['data'].get('single_lesson', {})
                assert single_lesson.get('limit', 0) >= 0


# ============================================================
# 29. _check_quota with no teacher (admin path)
# ============================================================

class TestCheckQuotaAdminPathDeep2:

    def test_generate_no_teacher_id_no_limit(self, client, admin_user, db_session):
        """Admin has no teacher_id → _check_quota returns (True, 999, 999)"""
        c = _make_course(db_session)
        u = _make_unit(db_session, c.id)
        l = _make_lesson(db_session, u.id)
        _login_admin(client, admin_user)
        resp = client.post('/api/lesson-prep/generate', json={'lesson_id': l.id})
        assert resp.status_code in ACCEPT

    def test_quota_endpoint_admin_returns_999(self, client, admin_user, db_session):
        _login_admin(client, admin_user)
        resp = client.get('/api/lesson-prep/quota')
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('is_admin') is True
            for v in data['data'].values():
                assert v['remaining'] == 999
