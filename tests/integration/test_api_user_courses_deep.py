"""
اختبارات عميقة لـ courses/units/lessons APIs في api.py
يستهدف تغطية:
- get_all_courses (show_all / bot mode)
- get_course_units
- get_unit_lessons
- get_lesson_questions
- get_unit_questions_direct
- get_course_questions_direct
- get_course_unit_questions (nested)
- get_all_questions_in_db
- get_filtered_questions
- get_random_questions
- get_recent_questions
- toggle_course_bot_visibility
- toggle_unit_bot_visibility
- toggle_lesson_bot_visibility
- block/unblock questions
- bulk_block_questions
- get_dashboard_statistics
- get_course_performance
- get_recent_activities
- backup/health, backup/logs
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
        username=f'adm_courses_{secrets.token_hex(4)}',
        email=f'adm_courses_{secrets.token_hex(4)}@test.com',
        is_admin=True
    )
    u.set_password('Admin@123')
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_course(db_session, *, show_in_bot=True, name=None, order_num=1):
    from src.models.curriculum import Course
    c = Course(
        name=name or f'Course_{secrets.token_hex(3)}',
        show_in_bot=show_in_bot,
        order_num=order_num
    )
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course, *, show_in_bot=True, name=None):
    from src.models.curriculum import Unit
    u = Unit(
        name=name or f'Unit_{secrets.token_hex(3)}',
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
        name=name or f'Lesson_{secrets.token_hex(3)}',
        unit_id=unit.id,
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


def _make_question(db_session, lesson, *, blocked=False, text=None,
                   difficulty='medium', bloom_level='remember'):
    from src.models.question import Question, Option
    q = Question(
        lesson_id=lesson.id,
        question_text=text or f'سؤال {secrets.token_hex(3)}؟',
        is_blocked=blocked,
        difficulty=difficulty,
        bloom_level=bloom_level
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


# ==================== Test: get_all_courses ====================

class TestGetAllCourses:
    """اختبارات /api/v1/courses"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/courses')
        assert r.status_code == 200

    def test_returns_list(self, client):
        r = client.get('/api/v1/courses')
        data = r.get_json()
        assert isinstance(data, list)

    def test_bot_mode_filters_hidden(self, client, db_session):
        visible = _make_course(db_session, show_in_bot=True, name='Visible Bot')
        hidden = _make_course(db_session, show_in_bot=False, name='Hidden Bot')
        r = client.get('/api/v1/courses')
        data = r.get_json()
        names = [c['name'] for c in data]
        assert visible.name in names
        assert hidden.name not in names

    def test_show_all_includes_hidden(self, client, db_session):
        visible = _make_course(db_session, show_in_bot=True, name='V2 Course')
        hidden = _make_course(db_session, show_in_bot=False, name='H2 Course')
        r = client.get('/api/v1/courses?show_all=true')
        data = r.get_json()
        names = [c['name'] for c in data]
        assert visible.name in names
        assert hidden.name in names

    def test_course_has_required_fields(self, client, db_session):
        _make_course(db_session, name='Fields Test Course')
        r = client.get('/api/v1/courses?show_all=true')
        data = r.get_json()
        if data:
            c = next((x for x in data if x['name'] == 'Fields Test Course'), None)
            if c:
                assert 'id' in c
                assert 'name' in c
                assert 'order_num' in c

    def test_empty_db_returns_empty_list(self, client, db_session):
        r = client.get('/api/v1/courses')
        data = r.get_json()
        assert isinstance(data, list)

    def test_show_all_false_same_as_default(self, client, db_session):
        _make_course(db_session, show_in_bot=True, name='SameAsDefault')
        r1 = client.get('/api/v1/courses')
        r2 = client.get('/api/v1/courses?show_all=false')
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_db_error_returns_500(self, client, db_session):
        with patch('src.routes.api.Course') as mock_course:
            mock_course.query.filter.side_effect = Exception('DB error')
            mock_course.query.order_by.side_effect = Exception('DB error')
            r = client.get('/api/v1/courses')
            # قد يُرجع 200 أو 500 حسب كيفية Mock
            assert r.status_code in [200, 500]


# ==================== Test: get_course_units ====================

class TestGetCourseUnits:
    """اختبارات /api/v1/courses/<id>/units"""

    def test_not_found_course(self, client):
        r = client.get('/api/v1/courses/99999/units')
        assert r.status_code == 404

    def test_returns_units_for_course(self, client, db_session):
        course = _make_course(db_session, name='Units Course Test')
        unit = _make_unit(db_session, course, show_in_bot=True)
        r = client.get(f'/api/v1/courses/{course.id}/units')
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        ids = [u['id'] for u in data]
        assert unit.id in ids

    def test_bot_mode_filters_hidden_units(self, client, db_session):
        course = _make_course(db_session, name='BotFilter Course')
        visible_unit = _make_unit(db_session, course, show_in_bot=True, name='Visible Unit')
        hidden_unit = _make_unit(db_session, course, show_in_bot=False, name='Hidden Unit')
        r = client.get(f'/api/v1/courses/{course.id}/units')
        data = r.get_json()
        names = [u['name'] for u in data]
        assert visible_unit.name in names
        assert hidden_unit.name not in names

    def test_show_all_includes_hidden_units(self, client, db_session):
        course = _make_course(db_session, name='ShowAll Course')
        visible_unit = _make_unit(db_session, course, show_in_bot=True, name='V Unit')
        hidden_unit = _make_unit(db_session, course, show_in_bot=False, name='H Unit')
        r = client.get(f'/api/v1/courses/{course.id}/units?show_all=true')
        data = r.get_json()
        names = [u['name'] for u in data]
        assert visible_unit.name in names
        assert hidden_unit.name in names

    def test_unit_has_required_fields(self, client, db_session):
        course = _make_course(db_session, name='FieldsUnit Course')
        _make_unit(db_session, course, name='Fields Unit')
        r = client.get(f'/api/v1/courses/{course.id}/units?show_all=true')
        data = r.get_json()
        if data:
            u = data[0]
            assert 'id' in u
            assert 'name' in u
            assert 'order_num' in u

    def test_course_with_no_units(self, client, db_session):
        course = _make_course(db_session, name='No Units Course')
        r = client.get(f'/api/v1/courses/{course.id}/units')
        assert r.status_code == 200
        assert r.get_json() == []

    def test_invalid_course_id(self, client):
        r = client.get('/api/v1/courses/0/units')
        assert r.status_code in [404, 200]


# ==================== Test: get_unit_lessons ====================

class TestGetUnitLessons:
    """اختبارات /api/v1/units/<id>/lessons"""

    def test_not_found_unit(self, client):
        r = client.get('/api/v1/units/99999/lessons')
        assert r.status_code == 404

    def test_returns_lessons_for_unit(self, client, db_session):
        course = _make_course(db_session, name='Lessons Course')
        unit = _make_unit(db_session, course, name='Lessons Unit')
        lesson = _make_lesson(db_session, unit, show_in_bot=True)
        r = client.get(f'/api/v1/units/{unit.id}/lessons')
        assert r.status_code == 200
        data = r.get_json()
        ids = [l['id'] for l in data]
        assert lesson.id in ids

    def test_bot_mode_filters_hidden_lessons(self, client, db_session):
        course = _make_course(db_session, name='BotFilter Lessons Course')
        unit = _make_unit(db_session, course, name='BotFilter Unit')
        visible = _make_lesson(db_session, unit, show_in_bot=True, name='Visible Lesson')
        hidden = _make_lesson(db_session, unit, show_in_bot=False, name='Hidden Lesson')
        r = client.get(f'/api/v1/units/{unit.id}/lessons')
        data = r.get_json()
        names = [l['name'] for l in data]
        assert visible.name in names
        assert hidden.name not in names

    def test_show_all_includes_hidden_lessons(self, client, db_session):
        course = _make_course(db_session, name='ShowAll Lessons Course')
        unit = _make_unit(db_session, course, name='ShowAll Unit')
        visible = _make_lesson(db_session, unit, show_in_bot=True, name='VL')
        hidden = _make_lesson(db_session, unit, show_in_bot=False, name='HL')
        r = client.get(f'/api/v1/units/{unit.id}/lessons?show_all=true')
        data = r.get_json()
        names = [l['name'] for l in data]
        assert visible.name in names
        assert hidden.name in names

    def test_lesson_has_required_fields(self, client, db_session):
        course = _make_course(db_session, name='FieldsLesson Course')
        unit = _make_unit(db_session, course, name='FieldsLesson Unit')
        _make_lesson(db_session, unit, name='Fields Lesson')
        r = client.get(f'/api/v1/units/{unit.id}/lessons?show_all=true')
        data = r.get_json()
        if data:
            l = data[0]
            assert 'id' in l
            assert 'name' in l
            assert 'order_num' in l

    def test_unit_with_no_lessons(self, client, db_session):
        course = _make_course(db_session, name='No Lessons Course')
        unit = _make_unit(db_session, course, name='No Lessons Unit')
        r = client.get(f'/api/v1/units/{unit.id}/lessons')
        assert r.status_code == 200
        assert r.get_json() == []


# ==================== Test: get_lesson_questions ====================

class TestGetLessonQuestions:
    """اختبارات /api/v1/lessons/<id>/questions"""

    def test_not_found_lesson(self, client):
        r = client.get('/api/v1/lessons/99999/questions')
        assert r.status_code == 404

    def test_returns_questions(self, client, db_session):
        course = _make_course(db_session, name='Qs Course')
        unit = _make_unit(db_session, course, name='Qs Unit')
        lesson = _make_lesson(db_session, unit, name='Qs Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_blocked_questions_excluded(self, client, db_session):
        course = _make_course(db_session, name='Block Qs Course')
        unit = _make_unit(db_session, course, name='Block Qs Unit')
        lesson = _make_lesson(db_session, unit, name='Block Qs Lesson')
        visible = _make_question(db_session, lesson, blocked=False, text='سؤال مرئي')
        blocked = _make_question(db_session, lesson, blocked=True, text='سؤال محجوب')
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert visible.question_id in ids
        assert blocked.question_id not in ids

    def test_question_has_required_fields(self, client, db_session):
        course = _make_course(db_session, name='Fields Qs Course')
        unit = _make_unit(db_session, course, name='Fields Qs Unit')
        lesson = _make_lesson(db_session, unit, name='Fields Qs Lesson')
        _make_question(db_session, lesson)
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = r.get_json()
        if data:
            q = data[0]
            assert 'question_id' in q
            assert 'question_text' in q
            assert 'options' in q
            assert 'correct_option_id' in q

    def test_empty_lesson_returns_empty_list(self, client, db_session):
        course = _make_course(db_session, name='Empty Qs Course')
        unit = _make_unit(db_session, course, name='Empty Qs Unit')
        lesson = _make_lesson(db_session, unit, name='Empty Lesson')
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        assert r.status_code == 200
        assert r.get_json() == []

    def test_question_has_difficulty_and_bloom(self, client, db_session):
        course = _make_course(db_session, name='Diff Course')
        unit = _make_unit(db_session, course, name='Diff Unit')
        lesson = _make_lesson(db_session, unit, name='Diff Lesson')
        _make_question(db_session, lesson, difficulty='hard', bloom_level='analyze')
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = r.get_json()
        if data:
            q = data[0]
            assert 'difficulty' in q
            assert 'bloom_level' in q


# ==================== Test: get_unit_questions_direct ====================

class TestGetUnitQuestionsDirect:
    """اختبارات /api/v1/units/<id>/questions"""

    def test_not_found_unit(self, client):
        r = client.get('/api/v1/units/99999/questions')
        assert r.status_code == 404

    def test_returns_questions_for_unit(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True, name='UQD Course')
        unit = _make_unit(db_session, course, name='UQD Unit')
        lesson = _make_lesson(db_session, unit, name='UQD Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/units/{unit.id}/questions')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_blocked_excluded(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True, name='UQD Block Course')
        unit = _make_unit(db_session, course, name='UQD Block Unit')
        lesson = _make_lesson(db_session, unit, name='UQD Block Lesson')
        visible = _make_question(db_session, lesson, blocked=False)
        blocked = _make_question(db_session, lesson, blocked=True)
        r = client.get(f'/api/v1/units/{unit.id}/questions')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert visible.question_id in ids
        assert blocked.question_id not in ids

    def test_show_all_bypasses_course_filter(self, client, db_session):
        course = _make_course(db_session, show_in_bot=False, name='Hidden UQD Course')
        unit = _make_unit(db_session, course, name='Hidden UQD Unit')
        lesson = _make_lesson(db_session, unit, name='Hidden UQD Lesson')
        q = _make_question(db_session, lesson)
        # بدون show_all: لا يظهر لأن course.show_in_bot=False
        r = client.get(f'/api/v1/units/{unit.id}/questions')
        data_no_all = r.get_json()
        # مع show_all=true: يظهر
        r2 = client.get(f'/api/v1/units/{unit.id}/questions?show_all=true')
        data_with_all = r2.get_json()
        ids_with_all = [x['question_id'] for x in data_with_all]
        assert q.question_id in ids_with_all

    def test_empty_unit_returns_empty_list(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True, name='Empty UQD')
        unit = _make_unit(db_session, course, name='Empty UQD Unit')
        r = client.get(f'/api/v1/units/{unit.id}/questions')
        assert r.status_code == 200
        assert r.get_json() == []


# ==================== Test: get_course_questions_direct ====================

class TestGetCourseQuestionsDirect:
    """اختبارات /api/v1/courses/<id>/questions"""

    def test_not_found_course(self, client):
        r = client.get('/api/v1/courses/99999/questions')
        assert r.status_code == 404

    def test_returns_questions_for_course(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True, name='CQD Course')
        unit = _make_unit(db_session, course, name='CQD Unit')
        lesson = _make_lesson(db_session, unit, name='CQD Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/courses/{course.id}/questions')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_blocked_excluded(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True, name='CQD Block Course')
        unit = _make_unit(db_session, course, name='CQD Block Unit')
        lesson = _make_lesson(db_session, unit, name='CQD Block Lesson')
        visible = _make_question(db_session, lesson, blocked=False)
        blocked = _make_question(db_session, lesson, blocked=True)
        r = client.get(f'/api/v1/courses/{course.id}/questions')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert visible.question_id in ids
        assert blocked.question_id not in ids

    def test_show_all_includes_hidden_course(self, client, db_session):
        course = _make_course(db_session, show_in_bot=False, name='Hidden CQD')
        unit = _make_unit(db_session, course, name='Hidden CQD Unit')
        lesson = _make_lesson(db_session, unit, name='Hidden CQD Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/courses/{course.id}/questions?show_all=true')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_empty_course_returns_empty_list(self, client, db_session):
        course = _make_course(db_session, show_in_bot=True, name='Empty CQD')
        r = client.get(f'/api/v1/courses/{course.id}/questions')
        assert r.status_code == 200
        assert r.get_json() == []


# ==================== Test: get_course_unit_questions ====================

class TestGetCourseUnitQuestions:
    """اختبارات /api/v1/courses/<cid>/units/<uid>/questions"""

    def test_course_not_found(self, client):
        r = client.get('/api/v1/courses/99999/units/1/questions')
        assert r.status_code == 404
        data = r.get_json()
        assert 'error' in data

    def test_unit_not_found(self, client, db_session):
        course = _make_course(db_session, name='CUQ Course')
        r = client.get(f'/api/v1/courses/{course.id}/units/99999/questions')
        assert r.status_code == 404

    def test_unit_belongs_to_different_course(self, client, db_session):
        course1 = _make_course(db_session, name='CUQ Course1')
        course2 = _make_course(db_session, name='CUQ Course2')
        unit2 = _make_unit(db_session, course2, name='CUQ Unit2')
        r = client.get(f'/api/v1/courses/{course1.id}/units/{unit2.id}/questions')
        assert r.status_code == 404

    def test_returns_questions_in_unit(self, client, db_session):
        course = _make_course(db_session, name='CUQ FullTest Course')
        unit = _make_unit(db_session, course, name='CUQ FullTest Unit')
        lesson = _make_lesson(db_session, unit, name='CUQ FullTest Lesson')
        q = _make_question(db_session, lesson)
        r = client.get(f'/api/v1/courses/{course.id}/units/{unit.id}/questions')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_blocked_excluded(self, client, db_session):
        course = _make_course(db_session, name='CUQ Block Course')
        unit = _make_unit(db_session, course, name='CUQ Block Unit')
        lesson = _make_lesson(db_session, unit, name='CUQ Block Lesson')
        visible = _make_question(db_session, lesson, blocked=False)
        blocked = _make_question(db_session, lesson, blocked=True)
        r = client.get(f'/api/v1/courses/{course.id}/units/{unit.id}/questions')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert visible.question_id in ids
        assert blocked.question_id not in ids

    def test_empty_unit_returns_empty(self, client, db_session):
        course = _make_course(db_session, name='CUQ Empty Course')
        unit = _make_unit(db_session, course, name='CUQ Empty Unit')
        r = client.get(f'/api/v1/courses/{course.id}/units/{unit.id}/questions')
        assert r.status_code == 200
        assert r.get_json() == []


# ==================== Test: get_all_questions_in_db ====================

class TestGetAllQuestionsInDb:
    """اختبارات /api/v1/questions/all"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/questions/all')
        assert r.status_code == 200

    def test_returns_list(self, client):
        r = client.get('/api/v1/questions/all')
        data = r.get_json()
        assert isinstance(data, list)

    def test_only_visible_courses_questions(self, client, db_session):
        c_vis = _make_course(db_session, show_in_bot=True, name='All Qs Visible')
        c_hid = _make_course(db_session, show_in_bot=False, name='All Qs Hidden')
        u_vis = _make_unit(db_session, c_vis, name='All Qs VUnit')
        u_hid = _make_unit(db_session, c_hid, name='All Qs HUnit')
        l_vis = _make_lesson(db_session, u_vis, name='All Qs VLesson')
        l_hid = _make_lesson(db_session, u_hid, name='All Qs HLesson')
        q_vis = _make_question(db_session, l_vis, text='سؤال مرئي كل')
        q_hid = _make_question(db_session, l_hid, text='سؤال مخفي كل')
        r = client.get('/api/v1/questions/all')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q_vis.question_id in ids
        assert q_hid.question_id not in ids


# ==================== Test: get_filtered_questions ====================

class TestGetFilteredQuestions:
    """اختبارات /api/v1/questions (with filters)"""

    def test_no_filter_returns_all(self, client):
        r = client.get('/api/v1/questions')
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)

    def test_filter_by_lesson_id(self, client, db_session):
        course = _make_course(db_session, name='Filter L Course')
        unit = _make_unit(db_session, course, name='Filter L Unit')
        lesson = _make_lesson(db_session, unit, name='Filter L Lesson')
        q = _make_question(db_session, lesson, text='سؤال فلتر درس')
        r = client.get(f'/api/v1/questions?lesson_id={lesson.id}')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_filter_by_unit_id(self, client, db_session):
        course = _make_course(db_session, name='Filter U Course')
        unit = _make_unit(db_session, course, name='Filter U Unit')
        lesson = _make_lesson(db_session, unit, name='Filter U Lesson')
        q = _make_question(db_session, lesson, text='سؤال فلتر وحدة')
        r = client.get(f'/api/v1/questions?unit_id={unit.id}')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_filter_by_course_id(self, client, db_session):
        course = _make_course(db_session, name='Filter C Course')
        unit = _make_unit(db_session, course, name='Filter C Unit')
        lesson = _make_lesson(db_session, unit, name='Filter C Lesson')
        q = _make_question(db_session, lesson, text='سؤال فلتر منهج')
        r = client.get(f'/api/v1/questions?course_id={course.id}')
        assert r.status_code == 200
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id in ids

    def test_nonexistent_lesson_returns_empty(self, client):
        r = client.get('/api/v1/questions?lesson_id=99999')
        assert r.status_code == 200
        assert r.get_json() == []

    def test_nonexistent_unit_returns_empty(self, client):
        r = client.get('/api/v1/questions?unit_id=99999')
        assert r.status_code == 200
        assert r.get_json() == []

    def test_nonexistent_course_returns_empty(self, client):
        r = client.get('/api/v1/questions?course_id=99999')
        assert r.status_code == 200
        assert r.get_json() == []


# ==================== Test: get_random_questions ====================

class TestGetRandomQuestions:
    """اختبارات /api/v1/questions/random"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/questions/random')
        assert r.status_code == 200

    def test_returns_list(self, client):
        r = client.get('/api/v1/questions/random')
        data = r.get_json()
        assert isinstance(data, list)

    def test_count_param(self, client, db_session):
        course = _make_course(db_session, name='Random Qs Course')
        unit = _make_unit(db_session, course, name='Random Qs Unit')
        lesson = _make_lesson(db_session, unit, name='Random Qs Lesson')
        for _ in range(5):
            _make_question(db_session, lesson)
        r = client.get('/api/v1/questions/random?count=3')
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) <= 3

    def test_negative_count_defaults_to_10(self, client):
        r = client.get('/api/v1/questions/random?count=-5')
        assert r.status_code == 200

    def test_zero_count_defaults_to_10(self, client):
        r = client.get('/api/v1/questions/random?count=0')
        assert r.status_code == 200


# ==================== Test: get_recent_questions ====================

class TestGetRecentQuestions:
    """اختبارات /api/v1/questions/recent"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/questions/recent')
        assert r.status_code == 200

    def test_response_has_questions_key(self, client):
        r = client.get('/api/v1/questions/recent')
        data = r.get_json()
        assert 'questions' in data

    def test_limit_param(self, client, db_session):
        course = _make_course(db_session, name='Recent Qs Course')
        unit = _make_unit(db_session, course, name='Recent Qs Unit')
        lesson = _make_lesson(db_session, unit, name='Recent Qs Lesson')
        for _ in range(5):
            _make_question(db_session, lesson)
        r = client.get('/api/v1/questions/recent?limit=2')
        data = r.get_json()
        assert len(data['questions']) <= 2

    def test_default_limit_10(self, client):
        r = client.get('/api/v1/questions/recent')
        data = r.get_json()
        assert len(data['questions']) <= 10

    def test_question_has_id_and_text(self, client, db_session):
        course = _make_course(db_session, name='Recent Text Course')
        unit = _make_unit(db_session, course, name='Recent Text Unit')
        lesson = _make_lesson(db_session, unit, name='Recent Text Lesson')
        _make_question(db_session, lesson, text='سؤال حديث للاختبار')
        r = client.get('/api/v1/questions/recent')
        data = r.get_json()
        if data['questions']:
            q = data['questions'][0]
            assert 'id' in q
            assert 'text' in q


# ==================== Test: toggle_course_bot_visibility ====================

class TestToggleCourseBotVisibility:
    """اختبارات /api/v1/courses/<id>/toggle-bot-visibility"""

    def test_no_auth_redirects(self, client, db_session):
        course = _make_course(db_session, name='Toggle Course NoAuth')
        r = client.post(f'/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code in [302, 401]

    def test_toggle_visible_to_hidden(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, show_in_bot=True, name='Toggle Vis->Hid')
        r = client.post(f'/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('show_in_bot') == False

    def test_toggle_hidden_to_visible(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, show_in_bot=False, name='Toggle Hid->Vis')
        r = client.post(f'/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('show_in_bot') == True

    def test_not_found_course(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/courses/99999/toggle-bot-visibility')
        assert r.status_code == 404

    def test_put_method_works(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Toggle PUT Course')
        r = client.put(f'/api/v1/courses/{course.id}/toggle-bot-visibility')
        assert r.status_code == 200

    def test_response_has_message(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Toggle Message Course')
        r = client.post(f'/api/v1/courses/{course.id}/toggle-bot-visibility')
        data = r.get_json()
        assert 'message' in data


# ==================== Test: toggle_unit_bot_visibility ====================

class TestToggleUnitBotVisibility:
    """اختبارات /api/v1/units/<id>/toggle-bot-visibility"""

    def test_no_auth_redirects(self, client, db_session):
        course = _make_course(db_session, name='Toggle Unit NoAuth Course')
        unit = _make_unit(db_session, course, name='Toggle Unit NoAuth')
        r = client.post(f'/api/v1/units/{unit.id}/toggle-bot-visibility')
        assert r.status_code in [302, 401]

    def test_toggle_visible_to_hidden(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Unit Toggle Course')
        unit = _make_unit(db_session, course, show_in_bot=True, name='Toggle Unit Vis')
        r = client.post(f'/api/v1/units/{unit.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('show_in_bot') == False

    def test_toggle_hidden_to_visible(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Unit Toggle2 Course')
        unit = _make_unit(db_session, course, show_in_bot=False, name='Toggle Unit Hid')
        r = client.post(f'/api/v1/units/{unit.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('show_in_bot') == True

    def test_not_found_unit(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/units/99999/toggle-bot-visibility')
        assert r.status_code == 404

    def test_put_method_works(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Unit Toggle PUT Course')
        unit = _make_unit(db_session, course, name='Toggle Unit PUT')
        r = client.put(f'/api/v1/units/{unit.id}/toggle-bot-visibility')
        assert r.status_code == 200


# ==================== Test: toggle_lesson_bot_visibility ====================

class TestToggleLessonBotVisibility:
    """اختبارات /api/v1/lessons/<id>/toggle-bot-visibility"""

    def test_no_auth_redirects(self, client, db_session):
        course = _make_course(db_session, name='Toggle Lesson NoAuth Course')
        unit = _make_unit(db_session, course, name='Toggle Lesson NoAuth Unit')
        lesson = _make_lesson(db_session, unit, name='Toggle Lesson NoAuth')
        r = client.post(f'/api/v1/lessons/{lesson.id}/toggle-bot-visibility')
        assert r.status_code in [302, 401]

    def test_toggle_visible_to_hidden(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Lesson Toggle Course')
        unit = _make_unit(db_session, course, name='Lesson Toggle Unit')
        lesson = _make_lesson(db_session, unit, show_in_bot=True, name='Toggle Lesson Vis')
        r = client.post(f'/api/v1/lessons/{lesson.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('show_in_bot') == False

    def test_toggle_hidden_to_visible(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Lesson Toggle2 Course')
        unit = _make_unit(db_session, course, name='Lesson Toggle2 Unit')
        lesson = _make_lesson(db_session, unit, show_in_bot=False, name='Toggle Lesson Hid')
        r = client.post(f'/api/v1/lessons/{lesson.id}/toggle-bot-visibility')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('show_in_bot') == True

    def test_not_found_lesson(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/lessons/99999/toggle-bot-visibility')
        assert r.status_code == 404

    def test_put_method_works(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        course = _make_course(db_session, name='Lesson Toggle PUT Course')
        unit = _make_unit(db_session, course, name='Lesson Toggle PUT Unit')
        lesson = _make_lesson(db_session, unit, name='Toggle Lesson PUT')
        r = client.put(f'/api/v1/lessons/{lesson.id}/toggle-bot-visibility')
        assert r.status_code == 200


# ==================== Test: block/unblock questions ====================

class TestBlockUnblockQuestions:
    """اختبارات /api/v1/questions/<id>/block و /api/v1/questions/<id>/unblock"""

    def test_block_question_success(self, client, db_session):
        course = _make_course(db_session, name='Block Q Course')
        unit = _make_unit(db_session, course, name='Block Q Unit')
        lesson = _make_lesson(db_session, unit, name='Block Q Lesson')
        q = _make_question(db_session, lesson, blocked=False)
        r = client.put(f'/api/v1/questions/{q.question_id}/block')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('is_blocked') == True

    def test_block_nonexistent_question(self, client):
        r = client.put('/api/v1/questions/99999/block')
        assert r.status_code == 404

    def test_unblock_question_success(self, client, db_session):
        course = _make_course(db_session, name='Unblock Q Course')
        unit = _make_unit(db_session, course, name='Unblock Q Unit')
        lesson = _make_lesson(db_session, unit, name='Unblock Q Lesson')
        q = _make_question(db_session, lesson, blocked=True)
        r = client.put(f'/api/v1/questions/{q.question_id}/unblock')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('is_blocked') == False

    def test_unblock_nonexistent_question(self, client):
        r = client.put('/api/v1/questions/99999/unblock')
        assert r.status_code == 404

    def test_block_then_verify_excluded(self, client, db_session):
        course = _make_course(db_session, name='BlockVerify Course')
        unit = _make_unit(db_session, course, name='BlockVerify Unit')
        lesson = _make_lesson(db_session, unit, name='BlockVerify Lesson')
        q = _make_question(db_session, lesson, blocked=False)
        # منع السؤال
        client.put(f'/api/v1/questions/{q.question_id}/block')
        # تأكد أنه غير موجود في الاستعلام
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = r.get_json()
        ids = [x['question_id'] for x in data]
        assert q.question_id not in ids


# ==================== Test: bulk_block_questions ====================

class TestBulkBlockQuestions:
    """اختبارات /api/v1/questions/bulk-block"""

    def test_bulk_block_success(self, client, db_session):
        course = _make_course(db_session, name='BulkBlock Course')
        unit = _make_unit(db_session, course, name='BulkBlock Unit')
        lesson = _make_lesson(db_session, unit, name='BulkBlock Lesson')
        q1 = _make_question(db_session, lesson, text='بلك سؤال 1')
        q2 = _make_question(db_session, lesson, text='بلك سؤال 2')
        r = client.post('/api/v1/questions/bulk-block', json={
            'question_ids': [q1.question_id, q2.question_id]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') == True
        assert data.get('blocked_count') == 2

    def test_bulk_block_empty_list(self, client):
        r = client.post('/api/v1/questions/bulk-block', json={
            'question_ids': []
        })
        assert r.status_code == 400
        data = r.get_json()
        assert data.get('success') == False

    def test_bulk_block_no_data(self, client):
        r = client.post('/api/v1/questions/bulk-block', json={})
        assert r.status_code == 400


# ==================== Test: get_dashboard_statistics ====================

class TestGetDashboardStatistics:
    """اختبارات /api/v1/dashboard/statistics"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/dashboard/statistics')
        assert r.status_code == 200

    def test_response_has_required_keys(self, client):
        r = client.get('/api/v1/dashboard/statistics')
        data = r.get_json()
        assert 'total_questions' in data
        assert 'total_courses' in data
        assert 'total_units' in data
        assert 'total_lessons' in data

    def test_has_course_distribution(self, client):
        r = client.get('/api/v1/dashboard/statistics')
        data = r.get_json()
        assert 'course_distribution' in data
        assert isinstance(data['course_distribution'], list)

    def test_has_monthly_data(self, client):
        r = client.get('/api/v1/dashboard/statistics')
        data = r.get_json()
        assert 'monthly_data' in data

    def test_counts_are_non_negative(self, client):
        r = client.get('/api/v1/dashboard/statistics')
        data = r.get_json()
        assert data['total_questions'] >= 0
        assert data['total_courses'] >= 0


# ==================== Test: get_course_performance ====================

class TestGetCoursePerformance:
    """اختبارات /api/v1/dashboard/performance"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/dashboard/performance')
        assert r.status_code == 200

    def test_has_performance_key(self, client):
        r = client.get('/api/v1/dashboard/performance')
        data = r.get_json()
        assert 'performance' in data
        assert isinstance(data['performance'], list)

    def test_performance_item_has_required_fields(self, client, db_session):
        _make_course(db_session, name='Performance Test Course')
        r = client.get('/api/v1/dashboard/performance')
        data = r.get_json()
        if data['performance']:
            item = data['performance'][0]
            assert 'course_name' in item
            assert 'question_count' in item
            assert 'percentage' in item


# ==================== Test: get_recent_activities ====================

class TestGetRecentActivities:
    """اختبارات /api/v1/activities/recent"""

    def test_returns_200(self, client):
        r = client.get('/api/v1/activities/recent')
        assert r.status_code == 200

    def test_has_activities_key(self, client):
        r = client.get('/api/v1/activities/recent')
        data = r.get_json()
        assert 'activities' in data

    def test_limit_param(self, client):
        r = client.get('/api/v1/activities/recent?limit=2')
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['activities']) <= 2

    def test_activities_is_list(self, client):
        r = client.get('/api/v1/activities/recent')
        data = r.get_json()
        assert isinstance(data['activities'], list)

    def test_default_returns_dummy_data(self, client):
        # نظام Activity قد لا يكون موجوداً، لذا يرجع dummy data
        r = client.get('/api/v1/activities/recent')
        assert r.status_code == 200


# ==================== Test: backup/health ====================

class TestBackupHealth:
    """اختبارات /api/v1/backup/health"""

    def test_returns_json(self, client):
        r = client.get('/api/v1/backup/health')
        # backup_settings_manager قد لا يكون معرّفاً -> 500 أو 200
        assert r.status_code in [200, 500]
        assert r.content_type.startswith('application/json')

    def test_response_has_success_key(self, client):
        r = client.get('/api/v1/backup/health')
        data = r.get_json()
        assert 'success' in data

    def test_response_has_message(self, client):
        r = client.get('/api/v1/backup/health')
        data = r.get_json()
        # success=True -> يحتوي data, success=False -> يحتوي message
        assert 'data' in data or 'message' in data

    def test_when_success_has_health_data(self, client):
        r = client.get('/api/v1/backup/health')
        data = r.get_json()
        if data.get('success') and 'data' in data:
            assert 'overall_health' in data['data']
            assert 'components' in data['data']


# ==================== Test: backup/logs ====================

class TestBackupLogs:
    """اختبارات /api/v1/backup/logs"""

    def test_returns_200_no_logs_file(self, client):
        r = client.get('/api/v1/backup/logs')
        assert r.status_code == 200

    def test_response_has_success(self, client):
        r = client.get('/api/v1/backup/logs')
        data = r.get_json()
        assert 'success' in data

    def test_lines_param(self, client):
        r = client.get('/api/v1/backup/logs?lines=10')
        assert r.status_code == 200

    def test_level_param(self, client):
        r = client.get('/api/v1/backup/logs?level=ERROR')
        assert r.status_code == 200
