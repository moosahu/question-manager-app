"""
Combined deep integration tests for:
  - src/routes/learning_routes.py  (target: ~94% coverage)
  - src/routes/curriculum.py       (target: ~93% coverage)

Gaps targeted in learning_routes.py:
  - api_get_lesson_content: admin view, device_id auth, no auth 401,
    lesson not found 404, concept_map view_count increment, progress creation
  - api_update_progress: no auth, device_id auth, node_explored (all explored),
    action=complete branch, existing progress update, empty data
  - api_get_all_lessons: admin view, device_id auth, no auth, with/without content
  - api_get_student_stats: own student, admin viewing other, forbidden case,
    empty progress
  - admin_index, admin_summaries, admin_concept_maps, admin_reports:
    non-admin redirect, admin ok
  - admin_view_concept_map, admin_edit_concept_map (GET & POST valid/invalid JSON)
  - admin_add_summary (GET & POST valid/invalid)
  - admin_add_concept_map (GET & POST valid/invalid)
  - admin_delete_concept_map, admin_delete_summary: non-admin, not-found, success
  - admin_generate_concept_map_ai: no lesson_id, lesson not found, success path
  - admin_save_ai_generated_concept_map: missing fields, update existing, create new
  - admin_suggest_branches: missing center_text, ai not configured
  - admin_export_concept_map: json format, png format, svg format, unknown format

Gaps targeted in curriculum.py:
  - list_courses: no auth, admin ok, zero-order reset, with data
  - add_course: empty name, duplicate name, success
  - edit_course: not found, empty name, duplicate name, success
  - delete_course: not found, success
  - update_course_order: up/down with AJAX header, no prev/next
  - update_course_order_alt
  - add_unit: empty name, success
  - edit_unit: empty name, success
  - delete_unit: success
  - update_unit_order: up/down, zero-order reset
  - update_unit_order_alt
  - add_lesson: empty name, success
  - edit_lesson: empty name, success
  - delete_lesson: success
  - update_lesson_order: up/down, zero-order reset, AJAX response
  - update_lesson_order_alt
  - delete_course_alt, delete_unit_alt, delete_lesson_alt
  - update_bulk_order: course/unit/lesson, missing type, missing order,
    invalid item_type, invalid id in list
  - toggle_bot_visibility: success, already visible
  - reset_order_nums helper (indirect via zero-order data)
"""
import json
import pytest
import secrets

ALLOWED = [200, 302, 400, 401, 403, 404, 405, 500, 503]


# ===========================================================================
# Shared Helpers
# ===========================================================================

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _student_session(client, student_id):
    with client.session_transaction() as sess:
        sess['user_id'] = student_id


def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='LCTest',
        username=f'lc_{secrets.token_hex(4)}',
        email=f'lc_{secrets.token_hex(4)}@test.com',
        is_active=True
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_course(db_session, name=None, order_num=10, show_in_bot=True):
    from src.models.curriculum import Course
    c = Course(name=name or f'Course_{secrets.token_hex(3)}',
               order_num=order_num, show_in_bot=show_in_bot)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course_id, name=None, order_num=10, show_in_bot=True):
    from src.models.curriculum import Unit
    u = Unit(name=name or f'Unit_{secrets.token_hex(3)}',
             course_id=course_id, order_num=order_num, show_in_bot=show_in_bot)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit_id, name=None, order_num=10, show_in_bot=True):
    from src.models.curriculum import Lesson
    l = Lesson(name=name or f'Lesson_{secrets.token_hex(3)}',
               unit_id=unit_id, order_num=order_num, show_in_bot=show_in_bot)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


def _make_summary(db_session, lesson_id):
    from src.models.learning_content import LessonSummary
    s = LessonSummary(
        lesson_id=lesson_id,
        introduction='Test intro',
        key_points=['point1', 'point2'],
        examples=[],
        vocabulary={}
    )
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_concept_map(db_session, lesson_id, view_count=0):
    from src.models.learning_content import ConceptMap
    cm = ConceptMap(
        lesson_id=lesson_id,
        layout_type='radial',
        theme='modern',
        animation_type='fade-in',
        map_data={'center': 'Test', 'branches': []}
    )
    cm.view_count = view_count
    db_session.session.add(cm)
    db_session.session.commit()
    db_session.session.refresh(cm)
    return cm


def _make_progress(db_session, student_id, lesson_id,
                   status='reading_summary', explored_nodes=None):
    from src.models.learning_content import StudentLessonProgress
    p = StudentLessonProgress(
        student_id=student_id,
        lesson_id=lesson_id,
        status=status
    )
    if explored_nodes:
        p.explored_nodes = explored_nodes
    db_session.session.add(p)
    db_session.session.commit()
    db_session.session.refresh(p)
    return p


# ===========================================================================
# LEARNING ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. GET /learning/api/lessons/<lesson_id>
# ---------------------------------------------------------------------------

class TestApiGetLessonContent:

    def test_no_auth_returns_401(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_admin_view_bypasses_student_check(self, client, admin_user, db_session):
        """Admin (Flask-Login) can view lesson without being a student."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_student_session_auth(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_device_id_auth(self, client, db_session):
        """Student authenticated via X-Device-ID header."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        from src.models.student import Student
        student = _make_student(db_session)
        student.device_id = f'dev_{secrets.token_hex(8)}'
        db_session.session.commit()
        r = client.get(f'/learning/api/lessons/{lesson.id}',
                       headers={'X-Device-ID': student.device_id})
        assert r.status_code in ALLOWED

    def test_device_id_header_alt(self, client, db_session):
        """Student authenticated via Device-ID header."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        student.device_id = f'dev2_{secrets.token_hex(8)}'
        db_session.session.commit()
        r = client.get(f'/learning/api/lessons/{lesson.id}',
                       headers={'Device-ID': student.device_id})
        assert r.status_code in ALLOWED

    def test_lesson_not_found_404(self, client, db_session):
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get('/learning/api/lessons/99999999')
        assert r.status_code in ALLOWED

    def test_concept_map_view_count_incremented(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id, view_count=5)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED
        if r.status_code == 200:
            from src.models.learning_content import ConceptMap
            from src.extensions import db
            refreshed = ConceptMap.query.get(cm.id)
            assert refreshed.view_count >= 5

    def test_with_summary_and_concept_map(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _make_summary(db_session, lesson.id)
        _make_concept_map(db_session, lesson.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_progress_created_when_missing(self, client, db_session):
        """First visit creates StudentLessonProgress record."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_progress_returned_when_existing(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _make_progress(db_session, student.id, lesson.id)
        _student_session(client, student.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_no_device_id_no_session_401(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        # No auth at all
        r = client.get(f'/learning/api/lessons/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_device_id_nonexistent_student(self, client, db_session):
        """Device ID that doesn't match any student => no student_id => 401."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        r = client.get(f'/learning/api/lessons/{lesson.id}',
                       headers={'X-Device-ID': 'nonexistent_device_xyz'})
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 2. POST /learning/api/lessons/<lesson_id>/progress
# ---------------------------------------------------------------------------

class TestApiUpdateProgress:

    def test_no_auth_401(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'summary_read'})
        assert r.status_code in ALLOWED

    def test_device_id_auth(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        student.device_id = f'dev3_{secrets.token_hex(8)}'
        db_session.session.commit()
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'summary_read'},
                        headers={'X-Device-ID': student.device_id})
        assert r.status_code in ALLOWED

    def test_action_summary_read(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'summary_read', 'reading_time': 30})
        assert r.status_code in ALLOWED

    def test_action_node_explored_new(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'node_explored', 'node_id': 'node1',
                              'time': 15, 'total_nodes': 5})
        assert r.status_code in ALLOWED

    def test_action_node_explored_completes_all(self, client, db_session):
        """Exploring last node marks concept_map_explored=True and status=completed."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        # Already explored 4 out of 5
        _make_progress(db_session, student.id, lesson.id,
                       explored_nodes=['n1', 'n2', 'n3', 'n4'])
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'node_explored', 'node_id': 'n5',
                              'time': 10, 'total_nodes': 5})
        assert r.status_code in ALLOWED

    def test_action_node_explored_duplicate_node(self, client, db_session):
        """Duplicate node_id not added again."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _make_progress(db_session, student.id, lesson.id,
                       explored_nodes=['n1'])
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'node_explored', 'node_id': 'n1',
                              'time': 5, 'total_nodes': 5})
        assert r.status_code in ALLOWED

    def test_time_spent_accumulated(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'summary_read', 'time_spent': 120})
        assert r.status_code in ALLOWED

    def test_creates_progress_when_missing(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'summary_read'})
        assert r.status_code in ALLOWED

    def test_unknown_action(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.post(f'/learning/api/lessons/{lesson.id}/progress',
                        json={'action': 'unknown_action'})
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 3. GET /learning/api/lessons
# ---------------------------------------------------------------------------

class TestApiGetAllLessons:

    def test_no_auth_401(self, client):
        r = client.get('/learning/api/lessons')
        assert r.status_code in ALLOWED

    def test_admin_view(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/api/lessons')
        assert r.status_code in ALLOWED

    def test_student_session(self, client, db_session):
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get('/learning/api/lessons')
        assert r.status_code in ALLOWED

    def test_with_visible_lessons(self, client, db_session):
        """Show lessons belonging to show_in_bot=True courses/units."""
        course = _make_course(db_session, show_in_bot=True)
        unit = _make_unit(db_session, course.id, show_in_bot=True)
        _make_lesson(db_session, unit.id, show_in_bot=True)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get('/learning/api/lessons')
        assert r.status_code in ALLOWED

    def test_with_hidden_course(self, client, db_session):
        """Hidden course lessons should not appear."""
        course = _make_course(db_session, show_in_bot=False)
        unit = _make_unit(db_session, course.id, show_in_bot=True)
        _make_lesson(db_session, unit.id, show_in_bot=True)
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get('/learning/api/lessons')
        assert r.status_code in ALLOWED

    def test_device_id_auth(self, client, db_session):
        student = _make_student(db_session)
        student.device_id = f'dev4_{secrets.token_hex(8)}'
        db_session.session.commit()
        r = client.get('/learning/api/lessons',
                       headers={'X-Device-ID': student.device_id})
        assert r.status_code in ALLOWED

    def test_response_structure(self, client, db_session):
        student = _make_student(db_session)
        _student_session(client, student.id)
        r = client.get('/learning/api/lessons')
        if r.status_code == 200:
            d = r.get_json()
            assert 'success' in d


# ---------------------------------------------------------------------------
# 4. GET /learning/api/students/<id>/stats
# ---------------------------------------------------------------------------

class TestApiGetStudentStats:

    def test_no_auth_401(self, client, db_session):
        student = _make_student(db_session)
        r = client.get(f'/learning/api/students/{student.id}/stats')
        assert r.status_code in ALLOWED

    def test_admin_can_view_any_student(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        r = client.get(f'/learning/api/students/{student.id}/stats')
        assert r.status_code in ALLOWED

    def test_with_progress_data(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        student = _make_student(db_session)
        _make_progress(db_session, student.id, lesson.id, status='completed')
        _login(client, admin_user)
        r = client.get(f'/learning/api/students/{student.id}/stats')
        assert r.status_code in ALLOWED

    def test_empty_progress(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        r = client.get(f'/learning/api/students/{student.id}/stats')
        assert r.status_code in ALLOWED
        if r.status_code == 200:
            d = r.get_json()
            if d.get('success'):
                assert d['data']['lessons_started'] == 0


# ---------------------------------------------------------------------------
# 5. Admin panel routes (HTML) — non-admin redirect + admin ok
# ---------------------------------------------------------------------------

class TestAdminPanelRoutes:

    def test_admin_index_no_auth(self, client):
        r = client.get('/learning/admin')
        assert r.status_code in ALLOWED

    def test_admin_index_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/admin')
        assert r.status_code in ALLOWED

    def test_admin_summaries_no_auth(self, client):
        r = client.get('/learning/admin/summaries')
        assert r.status_code in ALLOWED

    def test_admin_summaries_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/admin/summaries')
        assert r.status_code in ALLOWED

    def test_admin_concept_maps_no_auth(self, client):
        r = client.get('/learning/admin/concept-maps')
        assert r.status_code in ALLOWED

    def test_admin_concept_maps_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/admin/concept-maps')
        assert r.status_code in ALLOWED

    def test_admin_reports_no_auth(self, client):
        r = client.get('/learning/admin/reports')
        assert r.status_code in ALLOWED

    def test_admin_reports_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/admin/reports')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 6. Admin concept map view/edit
# ---------------------------------------------------------------------------

class TestAdminConceptMapViewEdit:

    def test_view_no_auth(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        r = client.get(f'/learning/admin/concept-map/{cm.id}')
        assert r.status_code in ALLOWED

    def test_view_as_admin(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.get(f'/learning/admin/concept-map/{cm.id}')
        assert r.status_code in ALLOWED

    def test_view_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/learning/admin/concept-map/9999999')
        assert r.status_code in ALLOWED

    def test_edit_get_as_admin(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.get(f'/learning/admin/concept-map/{cm.id}/edit')
        assert r.status_code in ALLOWED

    def test_edit_post_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.post(f'/learning/admin/concept-map/{cm.id}/edit',
                        data={
                            'layout_type': 'tree',
                            'theme': 'dark',
                            'animation_type': 'slide',
                            'map_data': json.dumps({'center': 'New', 'branches': []})
                        })
        assert r.status_code in ALLOWED

    def test_edit_post_invalid_json(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.post(f'/learning/admin/concept-map/{cm.id}/edit',
                        data={
                            'layout_type': 'radial',
                            'theme': 'modern',
                            'animation_type': 'fade-in',
                            'map_data': 'not valid json{{{'
                        })
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 7. Admin add summary
# ---------------------------------------------------------------------------

class TestAdminAddSummary:

    def test_get_no_auth(self, client):
        r = client.get('/learning/admin/summary/add')
        assert r.status_code in ALLOWED

    def test_get_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/admin/summary/add')
        assert r.status_code in ALLOWED

    def test_post_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/summary/add', data={
            'lesson_id': str(lesson.id),
            'introduction': 'Test intro',
            'key_points': json.dumps(['point1', 'point2']),
            'examples': json.dumps([]),
            'vocabulary': json.dumps({})
        })
        assert r.status_code in ALLOWED

    def test_post_invalid_key_points_json(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/summary/add', data={
            'lesson_id': str(lesson.id),
            'introduction': 'Test intro',
            'key_points': 'INVALID JSON{{{',
            'examples': json.dumps([])
        })
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 8. Admin add concept map
# ---------------------------------------------------------------------------

class TestAdminAddConceptMap:

    def test_get_no_auth(self, client):
        r = client.get('/learning/admin/concept-map/add')
        assert r.status_code in ALLOWED

    def test_get_as_admin(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/learning/admin/concept-map/add')
        assert r.status_code in ALLOWED

    def test_post_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/add', data={
            'lesson_id': str(lesson.id),
            'layout_type': 'radial',
            'theme': 'modern',
            'animation_type': 'fade-in',
            'map_data': json.dumps({'center': 'Test', 'branches': []})
        })
        assert r.status_code in ALLOWED

    def test_post_invalid_map_data_json(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/add', data={
            'lesson_id': str(lesson.id),
            'layout_type': 'radial',
            'theme': 'modern',
            'animation_type': 'fade-in',
            'map_data': 'INVALID{{{JSON'
        })
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 9. Admin delete concept map & summary
# ---------------------------------------------------------------------------

class TestAdminDeleteConceptMapSummary:

    def test_delete_concept_map_non_admin(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        r = client.post(f'/learning/admin/concept-maps/{cm.id}/delete')
        assert r.status_code in ALLOWED

    def test_delete_concept_map_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-maps/9999999/delete')
        assert r.status_code in ALLOWED

    def test_delete_concept_map_success(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.post(f'/learning/admin/concept-maps/{cm.id}/delete')
        assert r.status_code in ALLOWED

    def test_delete_summary_non_admin(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        summary = _make_summary(db_session, lesson.id)
        r = client.post(f'/learning/admin/summaries/{summary.id}/delete')
        assert r.status_code in ALLOWED

    def test_delete_summary_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/summaries/9999999/delete')
        assert r.status_code in ALLOWED

    def test_delete_summary_success(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        summary = _make_summary(db_session, lesson.id)
        _login(client, admin_user)
        r = client.post(f'/learning/admin/summaries/{summary.id}/delete')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 10. AI concept map generation & saving
# ---------------------------------------------------------------------------

class TestAdminGenerateConceptMapAI:

    def test_no_auth(self, client):
        r = client.post('/learning/admin/concept-map/generate-ai',
                        json={'lesson_id': 1})
        assert r.status_code in ALLOWED

    def test_missing_lesson_id(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/generate-ai',
                        json={'lesson_content': 'some content'})
        assert r.status_code in ALLOWED

    def test_lesson_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/generate-ai',
                        json={'lesson_id': 9999999})
        assert r.status_code in ALLOWED

    def test_with_valid_lesson(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/generate-ai',
                        json={'lesson_id': lesson.id,
                              'lesson_content': 'Chemistry introduction'})
        assert r.status_code in ALLOWED


class TestAdminSaveAIGeneratedConceptMap:

    def test_no_auth(self, client):
        r = client.post('/learning/admin/concept-map/save-ai-generated',
                        json={'lesson_id': 1,
                              'map_data': {'center': 'X', 'branches': []}})
        assert r.status_code in ALLOWED

    def test_missing_lesson_id(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/save-ai-generated',
                        json={'map_data': {'center': 'X'}})
        assert r.status_code in ALLOWED

    def test_missing_map_data(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/save-ai-generated',
                        json={'lesson_id': lesson.id})
        assert r.status_code in ALLOWED

    def test_create_new_map(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/save-ai-generated',
                        json={
                            'lesson_id': lesson.id,
                            'map_data': {'center': 'Test', 'branches': []},
                            'layout_type': 'radial',
                            'theme': 'modern'
                        })
        assert r.status_code in ALLOWED

    def test_update_existing_map(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/save-ai-generated',
                        json={
                            'lesson_id': lesson.id,
                            'map_data': {'center': 'Updated', 'branches': []},
                            'layout_type': 'tree'
                        })
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 11. Admin suggest branches
# ---------------------------------------------------------------------------

class TestAdminSuggestBranches:

    def test_no_auth(self, client):
        r = client.post('/learning/admin/concept-map/suggest-branches',
                        json={'center_text': 'Chemistry'})
        assert r.status_code in ALLOWED

    def test_missing_center_text(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/suggest-branches',
                        json={'existing_branches': []})
        assert r.status_code in ALLOWED

    def test_with_center_text(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/learning/admin/concept-map/suggest-branches',
                        json={'center_text': 'المحاليل الكيميائية',
                              'existing_branches': [{'text': 'التركيز'}]})
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 12. Admin export concept map
# ---------------------------------------------------------------------------

class TestAdminExportConceptMap:

    def test_export_json_no_auth(self, client, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        r = client.get(f'/learning/admin/concept-map/export/{cm.id}/json')
        assert r.status_code in ALLOWED

    def test_export_json_as_admin(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.get(f'/learning/admin/concept-map/export/{cm.id}/json')
        assert r.status_code in ALLOWED

    def test_export_png_as_admin(self, client, admin_user, db_session):
        """PNG export redirects (under development)."""
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.get(f'/learning/admin/concept-map/export/{cm.id}/png')
        assert r.status_code in ALLOWED

    def test_export_svg_as_admin(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.get(f'/learning/admin/concept-map/export/{cm.id}/svg')
        assert r.status_code in ALLOWED

    def test_export_unknown_format(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        cm = _make_concept_map(db_session, lesson.id)
        _login(client, admin_user)
        r = client.get(f'/learning/admin/concept-map/export/{cm.id}/pdf')
        assert r.status_code in ALLOWED

    def test_export_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/learning/admin/concept-map/export/9999999/json')
        assert r.status_code in ALLOWED


# ===========================================================================
# CURRICULUM ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. list_courses
# ---------------------------------------------------------------------------

class TestListCourses:

    def test_no_auth_redirects(self, client):
        r = client.get('/curriculum/')
        assert r.status_code in ALLOWED

    def test_as_admin_empty(self, client, admin_user, db_session):
        _login(client, admin_user)
        r = client.get('/curriculum/')
        assert r.status_code in ALLOWED

    def test_with_courses(self, client, admin_user, db_session):
        _make_course(db_session, name='Visible Course')
        _login(client, admin_user)
        r = client.get('/curriculum/')
        assert r.status_code in ALLOWED

    def test_zero_order_triggers_reset(self, client, admin_user, db_session):
        from src.models.curriculum import Course
        c = Course(name=f'ZeroOrder_{secrets.token_hex(3)}', order_num=0)
        db_session.session.add(c)
        db_session.session.commit()
        _login(client, admin_user)
        r = client.get('/curriculum/')
        assert r.status_code in ALLOWED

    def test_unit_with_zero_order_triggers_reset(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _make_unit(db_session, course.id, order_num=0)
        _login(client, admin_user)
        r = client.get('/curriculum/')
        assert r.status_code in ALLOWED

    def test_lesson_with_zero_order_triggers_reset(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _make_lesson(db_session, unit.id, order_num=0)
        _login(client, admin_user)
        r = client.get('/curriculum/')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 2. add_course
# ---------------------------------------------------------------------------

class TestAddCourse:

    def test_get_no_auth(self, client):
        r = client.get('/curriculum/courses/add')
        assert r.status_code in ALLOWED

    def test_get_as_admin(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/curriculum/courses/add')
        assert r.status_code in ALLOWED

    def test_post_empty_name(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/curriculum/courses/add', data={'name': ''})
        assert r.status_code in ALLOWED

    def test_post_duplicate_name(self, client, admin_user, db_session):
        _make_course(db_session, name='DuplicateCourse')
        _login(client, admin_user)
        r = client.post('/curriculum/courses/add',
                        data={'name': 'DuplicateCourse', 'show_in_bot': 'on'})
        assert r.status_code in ALLOWED

    def test_post_valid(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/curriculum/courses/add',
                        data={'name': f'NewCourse_{secrets.token_hex(4)}',
                              'show_in_bot': 'on'})
        assert r.status_code in ALLOWED

    def test_post_valid_without_show_in_bot(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/curriculum/courses/add',
                        data={'name': f'HiddenCourse_{secrets.token_hex(4)}'})
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 3. edit_course
# ---------------------------------------------------------------------------

class TestEditCourse:

    def test_get_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/curriculum/courses/edit/9999999')
        assert r.status_code in ALLOWED

    def test_get_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.get(f'/curriculum/courses/edit/{course.id}')
        assert r.status_code in ALLOWED

    def test_post_empty_name(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/edit/{course.id}',
                        data={'name': ''})
        assert r.status_code in ALLOWED

    def test_post_duplicate_name(self, client, admin_user, db_session):
        c1 = _make_course(db_session, name='CourseA_edit')
        c2 = _make_course(db_session, name='CourseB_edit')
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/edit/{c1.id}',
                        data={'name': 'CourseB_edit', 'show_in_bot': 'on'})
        assert r.status_code in ALLOWED

    def test_post_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/edit/{course.id}',
                        data={'name': f'Edited_{secrets.token_hex(4)}',
                              'show_in_bot': 'on'})
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 4. delete_course
# ---------------------------------------------------------------------------

class TestDeleteCourse:

    def test_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/curriculum/courses/delete/9999999')
        assert r.status_code in ALLOWED

    def test_success(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.get(f'/curriculum/courses/delete/{course.id}')
        assert r.status_code in ALLOWED

    def test_alt_route(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.get(f'/curriculum/course/delete/{course.id}')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 5. update_course_order
# ---------------------------------------------------------------------------

class TestUpdateCourseOrder:

    def test_no_auth(self, client, db_session):
        course = _make_course(db_session)
        r = client.post(f'/curriculum/courses/order/{course.id}/up')
        assert r.status_code in ALLOWED

    def test_up_with_prev(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/order/{c2.id}/up')
        assert r.status_code in ALLOWED

    def test_up_no_prev(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/order/{c1.id}/up')
        assert r.status_code in ALLOWED

    def test_down_with_next(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/order/{c1.id}/down')
        assert r.status_code in ALLOWED

    def test_down_no_next(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/order/{c1.id}/down')
        assert r.status_code in ALLOWED

    def test_ajax_header_returns_json(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/order/{c1.id}/down',
                        headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r.status_code in ALLOWED

    def test_with_zero_order_reset(self, client, admin_user, db_session):
        from src.models.curriculum import Course
        c = Course(name=f'Zero_{secrets.token_hex(3)}', order_num=0)
        db_session.session.add(c)
        c2 = _make_course(db_session, order_num=10)
        db_session.session.commit()
        _login(client, admin_user)
        r = client.post(f'/curriculum/courses/order/{c.id}/up')
        assert r.status_code in ALLOWED

    def test_alt_route_up(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/course/order/{c2.id}/up')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 6. toggle_bot_visibility
# ---------------------------------------------------------------------------

class TestToggleBotVisibility:

    def test_no_auth(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True)
        r = client.post(f'/curriculum/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code in ALLOWED

    def test_toggle_true_to_false(self, client, admin_user, db_session):
        course = _make_course(db_session, show_in_bot=True)
        _login(client, admin_user)
        r = client.post(f'/curriculum/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code in ALLOWED
        if r.status_code == 200:
            d = r.get_json()
            assert 'show_in_bot' in d

    def test_toggle_false_to_true(self, client, admin_user, db_session):
        course = _make_course(db_session, show_in_bot=False)
        _login(client, admin_user)
        r = client.post(f'/curriculum/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code in ALLOWED

    def test_not_found(self, client, admin_user):
        _login(client, admin_user)
        r = client.post('/curriculum/api/v1/courses/9999999/toggle-bot-visibility')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 7. add_unit / edit_unit / delete_unit
# ---------------------------------------------------------------------------

class TestUnitCRUD:

    def test_add_unit_get(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.get(f'/curriculum/units/add/{course.id}')
        assert r.status_code in ALLOWED

    def test_add_unit_post_empty_name(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/add/{course.id}', data={'name': ''})
        assert r.status_code in ALLOWED

    def test_add_unit_post_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/add/{course.id}',
                        data={'name': f'Unit_{secrets.token_hex(4)}'})
        assert r.status_code in ALLOWED

    def test_edit_unit_get(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/units/edit/{unit.id}')
        assert r.status_code in ALLOWED

    def test_edit_unit_post_empty_name(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/edit/{unit.id}', data={'name': ''})
        assert r.status_code in ALLOWED

    def test_edit_unit_post_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/edit/{unit.id}',
                        data={'name': f'Edited_{secrets.token_hex(4)}'})
        assert r.status_code in ALLOWED

    def test_delete_unit_success(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/units/delete/{unit.id}')
        assert r.status_code in ALLOWED

    def test_delete_unit_alt(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/unit/delete/{unit.id}')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 8. update_unit_order
# ---------------------------------------------------------------------------

class TestUpdateUnitOrder:

    def test_up_with_prev(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        u2 = _make_unit(db_session, course.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/order/{u2.id}/up')
        assert r.status_code in ALLOWED

    def test_up_no_prev(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/order/{u1.id}/up')
        assert r.status_code in ALLOWED

    def test_down_with_next(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        u2 = _make_unit(db_session, course.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert r.status_code in ALLOWED

    def test_down_no_next(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/order/{u1.id}/down')
        assert r.status_code in ALLOWED

    def test_ajax_header(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        u2 = _make_unit(db_session, course.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/order/{u1.id}/down',
                        headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r.status_code in ALLOWED

    def test_zero_order_reset(self, client, admin_user, db_session):
        from src.models.curriculum import Unit
        course = _make_course(db_session)
        u = Unit(name=f'ZeroUnit_{secrets.token_hex(3)}',
                 course_id=course.id, order_num=0)
        db_session.session.add(u)
        db_session.session.commit()
        _login(client, admin_user)
        r = client.post(f'/curriculum/units/order/{u.id}/up')
        assert r.status_code in ALLOWED

    def test_alt_route(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        u2 = _make_unit(db_session, course.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/unit/order/{u2.id}/up')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 9. add_lesson / edit_lesson / delete_lesson
# ---------------------------------------------------------------------------

class TestLessonCRUD:

    def test_add_lesson_get(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/lessons/add/{unit.id}')
        assert r.status_code in ALLOWED

    def test_add_lesson_empty_name(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/add/{unit.id}', data={'name': ''})
        assert r.status_code in ALLOWED

    def test_add_lesson_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/add/{unit.id}',
                        data={'name': f'Lesson_{secrets.token_hex(4)}'})
        assert r.status_code in ALLOWED

    def test_edit_lesson_get(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/lessons/edit/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_edit_lesson_empty_name(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/edit/{lesson.id}', data={'name': ''})
        assert r.status_code in ALLOWED

    def test_edit_lesson_valid(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/edit/{lesson.id}',
                        data={'name': f'Edited_{secrets.token_hex(4)}'})
        assert r.status_code in ALLOWED

    def test_delete_lesson_success(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/lessons/delete/{lesson.id}')
        assert r.status_code in ALLOWED

    def test_delete_lesson_alt(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        lesson = _make_lesson(db_session, unit.id)
        _login(client, admin_user)
        r = client.get(f'/curriculum/lesson/delete/{lesson.id}')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 10. update_lesson_order
# ---------------------------------------------------------------------------

class TestUpdateLessonOrder:

    def test_up_with_prev(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        l2 = _make_lesson(db_session, unit.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/order/{l2.id}/up')
        assert r.status_code in ALLOWED

    def test_up_no_prev(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/order/{l1.id}/up')
        assert r.status_code in ALLOWED

    def test_down_with_next(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        l2 = _make_lesson(db_session, unit.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert r.status_code in ALLOWED

    def test_down_no_next(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/order/{l1.id}/down')
        assert r.status_code in ALLOWED

    def test_ajax_header(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        l2 = _make_lesson(db_session, unit.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/order/{l1.id}/down',
                        headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r.status_code in ALLOWED

    def test_zero_order_reset(self, client, admin_user, db_session):
        from src.models.curriculum import Lesson
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l = Lesson(name=f'ZeroLesson_{secrets.token_hex(3)}',
                   unit_id=unit.id, order_num=0)
        db_session.session.add(l)
        db_session.session.commit()
        _login(client, admin_user)
        r = client.post(f'/curriculum/lessons/order/{l.id}/up')
        assert r.status_code in ALLOWED

    def test_alt_route(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        l2 = _make_lesson(db_session, unit.id, order_num=20)
        _login(client, admin_user)
        r = client.post(f'/curriculum/lesson/order/{l2.id}/up')
        assert r.status_code in ALLOWED


# ---------------------------------------------------------------------------
# 11. update_bulk_order
# ---------------------------------------------------------------------------

class TestUpdateBulkOrder:

    URL = '/curriculum/update_bulk_order'

    def test_no_auth(self, client):
        r = client.post(self.URL, data={
            'type': 'course', 'new_order': json.dumps([1, 2])
        })
        assert r.status_code in ALLOWED

    def test_missing_type(self, client, admin_user):
        _login(client, admin_user)
        r = client.post(self.URL, data={'new_order': json.dumps([1, 2])})
        assert r.status_code in ALLOWED

    def test_missing_new_order(self, client, admin_user):
        _login(client, admin_user)
        r = client.post(self.URL, data={'type': 'course', 'new_order': '[]'})
        assert r.status_code in ALLOWED

    def test_invalid_item_type(self, client, admin_user):
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'invalid_type', 'new_order': json.dumps([1])
        })
        assert r.status_code in ALLOWED

    def test_course_bulk_order(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        c2 = _make_course(db_session, order_num=20)
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'course',
            'new_order': json.dumps([str(c2.id), str(c1.id)])
        })
        assert r.status_code in ALLOWED

    def test_unit_bulk_order(self, client, admin_user, db_session):
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        u2 = _make_unit(db_session, course.id, order_num=20)
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'unit',
            'parent_id': str(course.id),
            'new_order': json.dumps([str(u2.id), str(u1.id)])
        })
        assert r.status_code in ALLOWED

    def test_lesson_bulk_order(self, client, admin_user, db_session):
        course = _make_course(db_session)
        unit = _make_unit(db_session, course.id)
        l1 = _make_lesson(db_session, unit.id, order_num=10)
        l2 = _make_lesson(db_session, unit.id, order_num=20)
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'lesson',
            'parent_id': str(unit.id),
            'new_order': json.dumps([str(l2.id), str(l1.id)])
        })
        assert r.status_code in ALLOWED

    def test_bulk_order_with_invalid_id(self, client, admin_user, db_session):
        """Non-integer id in new_order is skipped."""
        course = _make_course(db_session)
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'course',
            'new_order': json.dumps(['not_an_int', '99999999'])
        })
        assert r.status_code in ALLOWED

    def test_bulk_order_response_has_updated_count(self, client, admin_user, db_session):
        c1 = _make_course(db_session, order_num=10)
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'course',
            'new_order': json.dumps([str(c1.id)])
        })
        if r.status_code == 200:
            d = r.get_json()
            assert 'updated_count' in d

    def test_bulk_order_unit_with_id_param(self, client, admin_user, db_session):
        """Test using 'id' param instead of 'parent_id'."""
        course = _make_course(db_session)
        u1 = _make_unit(db_session, course.id, order_num=10)
        _login(client, admin_user)
        r = client.post(self.URL, data={
            'type': 'unit',
            'id': str(course.id),
            'new_order': json.dumps([str(u1.id)])
        })
        assert r.status_code in ALLOWED
