"""
اختبارات إضافية لرفع تغطية api.py إلى 80%+
يستهدف:
- bulk_unblock_questions
- block_all_lesson_questions / unblock_all_lesson_questions
- block_all_unit_questions / unblock_all_unit_questions
- block_all_course_questions / unblock_all_course_questions
- get_question_block_status
- export_questions
- generate_exam
- get_unit_lessons_export (nested)
- get_unit_questions_count
- get_lesson_questions_count
- get_course_questions_count
- get_admin_profile_api
- trusted_device_auth
- register_trusted_device
- add_question_api (POST /questions)
- get_question_api
- update_question_api
- helper functions coverage
"""
import pytest
import json
import secrets
from unittest.mock import patch, MagicMock


# ==================== Helpers ====================

def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_admin(db_session):
    from src.models.user import User
    u = User(
        username=f'adm_extra_{secrets.token_hex(4)}',
        email=f'adm_extra_{secrets.token_hex(4)}@test.com',
        is_admin=True
    )
    u.set_password('Admin@123')
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_non_admin(db_session):
    from src.models.user import User
    u = User(
        username=f'usr_extra_{secrets.token_hex(4)}',
        email=f'usr_extra_{secrets.token_hex(4)}@test.com',
        is_admin=False
    )
    u.set_password('Pass@123')
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_course(db_session, *, show_in_bot=True, name=None):
    from src.models.curriculum import Course
    c = Course(
        name=name or f'ECourse_{secrets.token_hex(3)}',
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course, *, show_in_bot=True, name=None):
    from src.models.curriculum import Unit
    u = Unit(
        name=name or f'EUnit_{secrets.token_hex(3)}',
        course_id=course.id,
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit, *, show_in_bot=True, name=None):
    from src.models.curriculum import Lesson
    l = Lesson(
        name=name or f'ELesson_{secrets.token_hex(3)}',
        unit_id=unit.id,
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


def _make_question(db_session, lesson, *, blocked=False, text=None):
    from src.models.question import Question, Option
    q = Question(
        lesson_id=lesson.id,
        question_text=text or f'سؤال إضافي {secrets.token_hex(3)}؟',
        is_blocked=blocked
    )
    db_session.session.add(q)
    db_session.session.flush()
    for i, correct in enumerate([True, False, False, False]):
        opt = Option(
            question_id=q.question_id,
            option_text=f'خيار {i + 1}',
            is_correct=correct
        )
        db_session.session.add(opt)
    db_session.session.commit()
    db_session.session.refresh(q)
    return q


# ==================== Test: bulk_unblock_questions ====================

class TestBulkUnblockQuestions:
    """اختبارات /api/v1/questions/bulk-unblock"""

    def test_unblock_success(self, client, db_session):
        course = _make_course(db_session, name='BulkUnblock Course')
        unit = _make_unit(db_session, course, name='BulkUnblock Unit')
        lesson = _make_lesson(db_session, unit, name='BulkUnblock Lesson')
        q1 = _make_question(db_session, lesson, blocked=True, text='بلك أنبلوك 1')
        q2 = _make_question(db_session, lesson, blocked=True, text='بلك أنبلوك 2')
        r = client.post('/api/v1/questions/bulk-unblock', json={
            'question_ids': [q1.question_id, q2.question_id]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('unblocked_count') == 2

    def test_empty_list_returns_400(self, client):
        r = client.post('/api/v1/questions/bulk-unblock', json={
            'question_ids': []
        })
        assert r.status_code == 400

    def test_no_data_returns_400(self, client):
        r = client.post('/api/v1/questions/bulk-unblock', json={})
        assert r.status_code == 400

    def test_response_has_question_ids(self, client, db_session):
        course = _make_course(db_session, name='BulkUnblock IDs Course')
        unit = _make_unit(db_session, course, name='BulkUnblock IDs Unit')
        lesson = _make_lesson(db_session, unit, name='BulkUnblock IDs Lesson')
        q = _make_question(db_session, lesson, blocked=True)
        r = client.post('/api/v1/questions/bulk-unblock', json={
            'question_ids': [q.question_id]
        })
        data = r.get_json()
        assert 'question_ids' in data


# ==================== Test: block_all_lesson_questions ====================

class TestBlockAllLessonQuestions:
    """اختبارات /api/v1/lessons/<id>/questions/block-all"""

    def test_not_found_lesson(self, client):
        r = client.put('/api/v1/lessons/99999/questions/block-all')
        assert r.status_code == 404

    def test_block_all_success(self, client, db_session):
        course = _make_course(db_session, name='BlockAll Lesson Course')
        unit = _make_unit(db_session, course, name='BlockAll Lesson Unit')
        lesson = _make_lesson(db_session, unit, name='BlockAll Lesson')
        q1 = _make_question(db_session, lesson, blocked=False)
        q2 = _make_question(db_session, lesson, blocked=False)
        r = client.put(f'/api/v1/lessons/{lesson.id}/questions/block-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('blocked_count') == 2

    def test_response_has_lesson_id(self, client, db_session):
        course = _make_course(db_session, name='BlockAll2 Lesson Course')
        unit = _make_unit(db_session, course, name='BlockAll2 Lesson Unit')
        lesson = _make_lesson(db_session, unit, name='BlockAll2 Lesson')
        r = client.put(f'/api/v1/lessons/{lesson.id}/questions/block-all')
        data = r.get_json()
        assert data.get('lesson_id') == lesson.id


# ==================== Test: unblock_all_lesson_questions ====================

class TestUnblockAllLessonQuestions:
    """اختبارات /api/v1/lessons/<id>/questions/unblock-all"""

    def test_not_found_lesson(self, client):
        r = client.put('/api/v1/lessons/99999/questions/unblock-all')
        assert r.status_code == 404

    def test_unblock_all_success(self, client, db_session):
        course = _make_course(db_session, name='UnblockAll Lesson Course')
        unit = _make_unit(db_session, course, name='UnblockAll Lesson Unit')
        lesson = _make_lesson(db_session, unit, name='UnblockAll Lesson')
        q1 = _make_question(db_session, lesson, blocked=True)
        q2 = _make_question(db_session, lesson, blocked=True)
        r = client.put(f'/api/v1/lessons/{lesson.id}/questions/unblock-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('unblocked_count') == 2

    def test_empty_lesson_returns_zero(self, client, db_session):
        course = _make_course(db_session, name='UnblockAll Empty Course')
        unit = _make_unit(db_session, course, name='UnblockAll Empty Unit')
        lesson = _make_lesson(db_session, unit, name='UnblockAll Empty Lesson')
        r = client.put(f'/api/v1/lessons/{lesson.id}/questions/unblock-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('unblocked_count') == 0


# ==================== Test: block_all_unit_questions ====================

class TestBlockAllUnitQuestions:
    """اختبارات /api/v1/units/<id>/questions/block-all"""

    def test_not_found_unit(self, client):
        r = client.put('/api/v1/units/99999/questions/block-all')
        assert r.status_code == 404

    def test_block_all_success(self, client, db_session):
        course = _make_course(db_session, name='BlockAll Unit Course')
        unit = _make_unit(db_session, course, name='BlockAll Unit')
        lesson = _make_lesson(db_session, unit, name='BlockAll Unit Lesson')
        q1 = _make_question(db_session, lesson, blocked=False)
        q2 = _make_question(db_session, lesson, blocked=False)
        r = client.put(f'/api/v1/units/{unit.id}/questions/block-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('blocked_count') == 2

    def test_response_has_unit_id(self, client, db_session):
        course = _make_course(db_session, name='BlockAll2 Unit Course')
        unit = _make_unit(db_session, course, name='BlockAll2 Unit')
        r = client.put(f'/api/v1/units/{unit.id}/questions/block-all')
        data = r.get_json()
        assert data.get('unit_id') == unit.id


# ==================== Test: unblock_all_unit_questions ====================

class TestUnblockAllUnitQuestions:
    """اختبارات /api/v1/units/<id>/questions/unblock-all"""

    def test_not_found_unit(self, client):
        r = client.put('/api/v1/units/99999/questions/unblock-all')
        assert r.status_code == 404

    def test_unblock_all_success(self, client, db_session):
        course = _make_course(db_session, name='UnblockAll Unit Course')
        unit = _make_unit(db_session, course, name='UnblockAll Unit')
        lesson = _make_lesson(db_session, unit, name='UnblockAll Unit Lesson')
        q1 = _make_question(db_session, lesson, blocked=True)
        r = client.put(f'/api/v1/units/{unit.id}/questions/unblock-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True


# ==================== Test: block_all_course_questions ====================

class TestBlockAllCourseQuestions:
    """اختبارات /api/v1/courses/<id>/questions/block-all"""

    def test_not_found_course(self, client):
        r = client.put('/api/v1/courses/99999/questions/block-all')
        assert r.status_code == 404

    def test_block_all_success(self, client, db_session):
        course = _make_course(db_session, name='BlockAll Course')
        unit = _make_unit(db_session, course, name='BlockAll Course Unit')
        lesson = _make_lesson(db_session, unit, name='BlockAll Course Lesson')
        q1 = _make_question(db_session, lesson, blocked=False)
        q2 = _make_question(db_session, lesson, blocked=False)
        r = client.put(f'/api/v1/courses/{course.id}/questions/block-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('blocked_count') == 2

    def test_empty_course_returns_zero(self, client, db_session):
        course = _make_course(db_session, name='BlockAll Empty Course')
        r = client.put(f'/api/v1/courses/{course.id}/questions/block-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('blocked_count') == 0


# ==================== Test: unblock_all_course_questions ====================

class TestUnblockAllCourseQuestions:
    """اختبارات /api/v1/courses/<id>/questions/unblock-all"""

    def test_not_found_course(self, client):
        r = client.put('/api/v1/courses/99999/questions/unblock-all')
        assert r.status_code == 404

    def test_unblock_all_success(self, client, db_session):
        course = _make_course(db_session, name='UnblockAll Course')
        unit = _make_unit(db_session, course, name='UnblockAll Course Unit')
        lesson = _make_lesson(db_session, unit, name='UnblockAll Course Lesson')
        q = _make_question(db_session, lesson, blocked=True)
        r = client.put(f'/api/v1/courses/{course.id}/questions/unblock-all')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('unblocked_count') == 1

    def test_has_course_id_in_response(self, client, db_session):
        course = _make_course(db_session, name='UnblockAll Course2')
        r = client.put(f'/api/v1/courses/{course.id}/questions/unblock-all')
        data = r.get_json()
        assert data.get('course_id') == course.id


# ==================== Test: get_question_block_status ====================

class TestGetQuestionBlockStatus:
    """اختبارات /api/v1/questions/<id>/block-status"""

    def test_not_found(self, client):
        r = client.get('/api/v1/questions/99999/block-status')
        assert r.status_code == 404

    def test_blocked_question(self, client, db_session):
        course = _make_course(db_session, name='BlockStatus Course')
        unit = _make_unit(db_session, course, name='BlockStatus Unit')
        lesson = _make_lesson(db_session, unit, name='BlockStatus Lesson')
        q = _make_question(db_session, lesson, blocked=True)
        r = client.get(f'/api/v1/questions/{q.question_id}/block-status')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('is_blocked') == True

    def test_unblocked_question(self, client, db_session):
        course = _make_course(db_session, name='UnblockStatus Course')
        unit = _make_unit(db_session, course, name='UnblockStatus Unit')
        lesson = _make_lesson(db_session, unit, name='UnblockStatus Lesson')
        q = _make_question(db_session, lesson, blocked=False)
        r = client.get(f'/api/v1/questions/{q.question_id}/block-status')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('is_blocked') == False

    def test_has_question_id(self, client, db_session):
        course = _make_course(db_session, name='BlockStatus2 Course')
        unit = _make_unit(db_session, course, name='BlockStatus2 Unit')
        lesson = _make_lesson(db_session, unit, name='BlockStatus2 Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/questions/{q.question_id}/block-status')
        data = r.get_json()
        assert data.get('question_id') == q.question_id


# ==================== Test: export_questions ====================

class TestExportQuestions:
    """اختبارات /api/v1/questions/export"""

    def test_no_auth_redirects(self, client):
        r = client.post('/api/v1/questions/export', json={})
        assert r.status_code in [302, 401]

    def test_empty_ids_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/questions/export', json={
            'question_ids': []
        })
        assert r.status_code == 400

    def test_export_success_json(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Export Course')
        unit = _make_unit(db_session, course, name='Export Unit')
        lesson = _make_lesson(db_session, unit, name='Export Lesson')
        q = _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/export', json={
            'question_ids': [q.question_id],
            'include_answers': True,
            'format': 'json'
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'questions' in data
        assert data.get('count') == 1

    def test_export_without_answers(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Export NoAns Course')
        unit = _make_unit(db_session, course, name='Export NoAns Unit')
        lesson = _make_lesson(db_session, unit, name='Export NoAns Lesson')
        q = _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/export', json={
            'question_ids': [q.question_id],
            'include_answers': False,
            'format': 'json'
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        # correct_option_id يجب أن يكون مزالاً
        if data['questions']:
            assert 'correct_option_id' not in data['questions'][0]

    def test_export_unsupported_format_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Export Format Course')
        unit = _make_unit(db_session, course, name='Export Format Unit')
        lesson = _make_lesson(db_session, unit, name='Export Format Lesson')
        q = _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/export', json={
            'question_ids': [q.question_id],
            'format': 'pdf'
        })
        assert r.status_code == 400

    def test_export_nonexistent_ids_returns_404(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/questions/export', json={
            'question_ids': [99999, 99998]
        })
        assert r.status_code == 404


# ==================== Test: generate_exam ====================

class TestGenerateExam:
    """اختبارات /api/v1/questions/generate-exam"""

    def test_no_auth_redirects(self, client):
        r = client.post('/api/v1/questions/generate-exam', json={})
        assert r.status_code in [302, 401]

    def test_no_course_id_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/questions/generate-exam', json={
            'question_count': 5
        })
        assert r.status_code == 400

    def test_generate_by_course(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GenExam Course')
        unit = _make_unit(db_session, course, name='GenExam Unit')
        lesson = _make_lesson(db_session, unit, name='GenExam Lesson')
        for _ in range(5):
            _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/generate-exam', json={
            'course_id': course.id,
            'question_count': 3
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'exam' in data
        assert len(data['exam']['questions']) == 3

    def test_generate_by_unit(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GenExam Unit Course')
        unit = _make_unit(db_session, course, name='GenExam Unit')
        lesson = _make_lesson(db_session, unit, name='GenExam Unit Lesson')
        for _ in range(3):
            _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/generate-exam', json={
            'course_id': course.id,
            'unit_id': unit.id,
            'question_count': 2
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True

    def test_generate_by_lesson(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GenExam Lesson Course')
        unit = _make_unit(db_session, course, name='GenExam Lesson Unit')
        lesson = _make_lesson(db_session, unit, name='GenExam Lesson')
        for _ in range(3):
            _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/generate-exam', json={
            'course_id': course.id,
            'unit_id': unit.id,
            'lesson_id': lesson.id,
            'question_count': 2
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True

    def test_no_available_questions_returns_404(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GenExam Empty Course')
        r = client.post('/api/v1/questions/generate-exam', json={
            'course_id': course.id
        })
        assert r.status_code == 404

    def test_include_answers(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GenExam Ans Course')
        unit = _make_unit(db_session, course, name='GenExam Ans Unit')
        lesson = _make_lesson(db_session, unit, name='GenExam Ans Lesson')
        _make_question(db_session, lesson)
        r = client.post('/api/v1/questions/generate-exam', json={
            'course_id': course.id,
            'include_answers': True
        })
        assert r.status_code == 200
        data = r.get_json()
        if data.get('success') and data['exam']['questions']:
            assert 'correct_option_id' in data['exam']['questions'][0]

    def test_more_requested_than_available(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GenExam Few Course')
        unit = _make_unit(db_session, course, name='GenExam Few Unit')
        lesson = _make_lesson(db_session, unit, name='GenExam Few Lesson')
        _make_question(db_session, lesson)  # 1 سؤال فقط
        r = client.post('/api/v1/questions/generate-exam', json={
            'course_id': course.id,
            'question_count': 100
        })
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['exam']['questions']) == 1


# ==================== Test: get_unit_lessons_export (nested) ====================

class TestGetUnitLessonsExport:
    """اختبارات /api/v1/courses/<cid>/units/<uid>/lessons"""

    def test_no_auth_redirects(self, client, db_session):
        course = _make_course(db_session, name='ULE NoAuth Course')
        unit = _make_unit(db_session, course, name='ULE NoAuth Unit')
        r = client.get(f'/api/v1/courses/{course.id}/units/{unit.id}/lessons')
        assert r.status_code in [302, 401]

    def test_unit_not_found(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='ULE NotFound Course')
        r = client.get(f'/api/v1/courses/{course.id}/units/99999/lessons')
        assert r.status_code == 404

    def test_unit_wrong_course(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course1 = _make_course(db_session, name='ULE Course1')
        course2 = _make_course(db_session, name='ULE Course2')
        unit2 = _make_unit(db_session, course2, name='ULE Unit2')
        r = client.get(f'/api/v1/courses/{course1.id}/units/{unit2.id}/lessons')
        assert r.status_code == 404

    def test_success_returns_lessons(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='ULE Success Course')
        unit = _make_unit(db_session, course, name='ULE Success Unit')
        lesson = _make_lesson(db_session, unit, name='ULE Success Lesson')
        r = client.get(f'/api/v1/courses/{course.id}/units/{unit.id}/lessons')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'lessons' in data
        ids = [l['id'] for l in data['lessons']]
        assert lesson.id in ids


# ==================== Test: questions-count endpoints ====================

class TestQuestionsCount:
    """اختبارات questions-count endpoints"""

    def test_unit_questions_count_no_auth(self, client, db_session):
        course = _make_course(db_session, name='UQC NoAuth Course')
        unit = _make_unit(db_session, course, name='UQC NoAuth Unit')
        r = client.get(f'/api/v1/units/{unit.id}/questions-count')
        assert r.status_code in [302, 401]

    def test_unit_questions_count_not_found(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/units/99999/questions-count')
        assert r.status_code == 404

    def test_unit_questions_count_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='UQC Success Course')
        unit = _make_unit(db_session, course, name='UQC Success Unit')
        lesson = _make_lesson(db_session, unit, name='UQC Success Lesson')
        _make_question(db_session, lesson)
        _make_question(db_session, lesson)
        r = client.get(f'/api/v1/units/{unit.id}/questions-count')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('questions_count') == 2
        assert data.get('unit_id') == unit.id

    def test_lesson_questions_count_no_auth(self, client, db_session):
        course = _make_course(db_session, name='LQC NoAuth Course')
        unit = _make_unit(db_session, course, name='LQC NoAuth Unit')
        lesson = _make_lesson(db_session, unit, name='LQC NoAuth Lesson')
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions-count')
        assert r.status_code in [302, 401]

    def test_lesson_questions_count_not_found(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/lessons/99999/questions-count')
        assert r.status_code == 404

    def test_lesson_questions_count_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='LQC Success Course')
        unit = _make_unit(db_session, course, name='LQC Success Unit')
        lesson = _make_lesson(db_session, unit, name='LQC Success Lesson')
        _make_question(db_session, lesson)
        _make_question(db_session, lesson, blocked=True)  # مُحجوب - لا يُحسب
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions-count')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('questions_count') == 1

    def test_course_questions_count_no_auth(self, client, db_session):
        course = _make_course(db_session, name='CQC NoAuth Course')
        r = client.get(f'/api/v1/courses/{course.id}/questions-count')
        assert r.status_code in [302, 401]

    def test_course_questions_count_not_found(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/courses/99999/questions-count')
        assert r.status_code == 404

    def test_course_questions_count_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='CQC Success Course')
        unit = _make_unit(db_session, course, name='CQC Success Unit')
        lesson = _make_lesson(db_session, unit, name='CQC Success Lesson')
        _make_question(db_session, lesson)
        _make_question(db_session, lesson)
        r = client.get(f'/api/v1/courses/{course.id}/questions-count')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('questions_count') == 2
        assert data.get('course_name') is not None


# ==================== Test: get_admin_profile_api ====================

class TestGetAdminProfileApi:
    """اختبارات /api/v1/admin/profile"""

    def test_no_auth_redirects(self, client):
        r = client.get('/api/v1/admin/profile')
        assert r.status_code in [302, 401]

    def test_admin_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/admin/profile')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'admin' in data

    def test_admin_profile_has_required_fields(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/admin/profile')
        data = r.get_json()
        admin = data.get('admin', {})
        assert 'id' in admin
        assert 'username' in admin
        assert 'email' in admin

    def test_non_admin_returns_403(self, client, db_session):
        user = _make_non_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/admin/profile')
        assert r.status_code == 403


# ==================== Test: trusted_device_auth ====================

class TestTrustedDeviceAuth:
    """اختبارات /api/v1/auth/trusted-device"""

    def test_missing_data_returns_400(self, client):
        r = client.post('/api/v1/auth/trusted-device', json={})
        assert r.status_code == 400

    def test_missing_device_token_returns_400(self, client):
        r = client.post('/api/v1/auth/trusted-device', json={
            'username': 'test_user'
        })
        assert r.status_code == 400

    def test_missing_username_returns_400(self, client):
        r = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'some_token'
        })
        assert r.status_code == 400

    def test_nonexistent_user_returns_404(self, client):
        r = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'some_token',
            'username': 'nonexistent_user_xyz'
        })
        assert r.status_code == 404

    def test_non_admin_user_returns_404(self, client, db_session):
        user = _make_non_admin(db_session)
        r = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'some_token',
            'username': user.username
        })
        assert r.status_code == 404

    def test_invalid_device_token_returns_401(self, client, db_session):
        user = _make_admin(db_session)
        r = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'invalid_token_xyz',
            'username': user.username
        })
        assert r.status_code == 401

    def test_valid_device_token_success(self, client, db_session):
        from datetime import datetime, timedelta
        user = _make_admin(db_session)
        # تعيين device_token للمستخدم
        user.trusted_device_token = 'valid_token_123'
        user.trusted_device_expires = datetime.utcnow() + timedelta(days=30)
        db_session.session.commit()
        r = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'valid_token_123',
            'username': user.username
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'device_token' in data

    def test_expired_device_token_returns_401(self, client, db_session):
        from datetime import datetime, timedelta
        user = _make_admin(db_session)
        user.trusted_device_token = 'expired_token_456'
        user.trusted_device_expires = datetime.utcnow() - timedelta(days=1)  # منتهي
        db_session.session.commit()
        r = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'expired_token_456',
            'username': user.username
        })
        assert r.status_code == 401


# ==================== Test: register_trusted_device ====================

class TestRegisterTrustedDevice:
    """اختبارات /api/v1/auth/register-device"""

    def test_no_auth_redirects(self, client):
        r = client.post('/api/v1/auth/register-device')
        assert r.status_code in [302, 401]

    def test_admin_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/auth/register-device')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'device_token' in data

    def test_non_admin_returns_403(self, client, db_session):
        user = _make_non_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/auth/register-device')
        assert r.status_code == 403

    def test_token_is_string(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/auth/register-device')
        data = r.get_json()
        assert isinstance(data.get('device_token'), str)


# ==================== Test: add_question_api (POST /questions) ====================

class TestAddQuestionApi:
    """اختبارات POST /api/v1/questions"""

    def test_no_auth_redirects(self, client):
        r = client.post('/api/v1/questions', json={})
        assert r.status_code in [302, 401]

    def test_no_data_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/questions',
                        data='',
                        content_type='application/json')
        assert r.status_code in [400, 500]

    def test_missing_lesson_id_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/questions', json={
            'question_text': 'نص السؤال',
            'options': [
                {'option_text': 'أ', 'is_correct': True},
                {'option_text': 'ب', 'is_correct': False}
            ]
        })
        assert r.status_code == 400

    def test_nonexistent_lesson_returns_404(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/questions', json={
            'lesson_id': 99999,
            'question_text': 'نص السؤال',
            'options': [
                {'option_text': 'أ', 'is_correct': True},
                {'option_text': 'ب', 'is_correct': False}
            ]
        })
        assert r.status_code == 404

    def test_no_text_no_image_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='AddQ NoText Course')
        unit = _make_unit(db_session, course, name='AddQ NoText Unit')
        lesson = _make_lesson(db_session, unit, name='AddQ NoText Lesson')
        r = client.post('/api/v1/questions', json={
            'lesson_id': lesson.id,
            'options': [
                {'option_text': 'أ', 'is_correct': True},
                {'option_text': 'ب', 'is_correct': False}
            ]
        })
        assert r.status_code == 400

    def test_less_than_two_options_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='AddQ OneOpt Course')
        unit = _make_unit(db_session, course, name='AddQ OneOpt Unit')
        lesson = _make_lesson(db_session, unit, name='AddQ OneOpt Lesson')
        r = client.post('/api/v1/questions', json={
            'lesson_id': lesson.id,
            'question_text': 'سؤال',
            'options': [{'option_text': 'أ', 'is_correct': True}]
        })
        assert r.status_code == 400

    def test_no_correct_option_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='AddQ NoCorrect Course')
        unit = _make_unit(db_session, course, name='AddQ NoCorrect Unit')
        lesson = _make_lesson(db_session, unit, name='AddQ NoCorrect Lesson')
        r = client.post('/api/v1/questions', json={
            'lesson_id': lesson.id,
            'question_text': 'سؤال',
            'options': [
                {'option_text': 'أ', 'is_correct': False},
                {'option_text': 'ب', 'is_correct': False}
            ]
        })
        assert r.status_code == 400

    def test_add_question_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='AddQ Success Course')
        unit = _make_unit(db_session, course, name='AddQ Success Unit')
        lesson = _make_lesson(db_session, unit, name='AddQ Success Lesson')
        r = client.post('/api/v1/questions', json={
            'lesson_id': lesson.id,
            'question_text': 'ما هو أول عنصر في الجدول الدوري؟',
            'explanation': 'الهيدروجين هو أخف العناصر',
            'options': [
                {'option_text': 'الهيدروجين', 'is_correct': True},
                {'option_text': 'الأكسجين', 'is_correct': False},
                {'option_text': 'النيتروجين', 'is_correct': False},
                {'option_text': 'الكربون', 'is_correct': False}
            ]
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data.get('success') == True
        assert 'question_id' in data


# ==================== Test: get_question_api ====================

class TestGetQuestionApi:
    """اختبارات GET /api/v1/questions/<id>"""

    def test_no_auth_redirects(self, client, db_session):
        course = _make_course(db_session, name='GetQ NoAuth Course')
        unit = _make_unit(db_session, course, name='GetQ NoAuth Unit')
        lesson = _make_lesson(db_session, unit, name='GetQ NoAuth Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/questions/{q.question_id}')
        assert r.status_code in [302, 401]

    def test_not_found_returns_404(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.get('/api/v1/questions/99999')
        assert r.status_code == 404

    def test_success_returns_question(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='GetQ Success Course')
        unit = _make_unit(db_session, course, name='GetQ Success Unit')
        lesson = _make_lesson(db_session, unit, name='GetQ Success Lesson')
        q = _make_question(db_session, lesson, text='سؤال للعرض')
        r = client.get(f'/api/v1/questions/{q.question_id}')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert 'question' in data
        assert data['question']['question_id'] == q.question_id


# ==================== Test: update_question_api ====================

class TestUpdateQuestionApi:
    """اختبارات PUT /api/v1/questions/<id>"""

    def test_no_auth_redirects(self, client, db_session):
        course = _make_course(db_session, name='UpdQ NoAuth Course')
        unit = _make_unit(db_session, course, name='UpdQ NoAuth Unit')
        lesson = _make_lesson(db_session, unit, name='UpdQ NoAuth Lesson')
        q = _make_question(db_session, lesson)
        r = client.put(f'/api/v1/questions/{q.question_id}', json={})
        assert r.status_code in [302, 401]

    def test_not_found_returns_404(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.put('/api/v1/questions/99999', json={
            'question_text': 'نص جديد'
        })
        assert r.status_code == 404

    def test_update_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='UpdQ Success Course')
        unit = _make_unit(db_session, course, name='UpdQ Success Unit')
        lesson = _make_lesson(db_session, unit, name='UpdQ Success Lesson')
        q = _make_question(db_session, lesson, text='النص القديم')
        r = client.put(f'/api/v1/questions/{q.question_id}', json={
            'question_text': 'النص الجديد'
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
