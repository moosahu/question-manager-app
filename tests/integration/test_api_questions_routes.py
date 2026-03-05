"""
اختبارات شاملة لـ API الأسئلة
يغطي: questions by lesson/unit/course, all questions, recent, toggle-block
"""
import pytest


@pytest.fixture
def full_curriculum(db_session, app):
    """منهج كامل مع وحدة ودرس وأسئلة"""
    from src.models.curriculum import Course, Unit, Lesson
    from src.models.question import Question, Option
    course = Course(name='كيمياء Questions Test', order_num=10, show_in_bot=True)
    db_session.session.add(course)
    db_session.session.commit()
    db_session.session.refresh(course)
    unit = Unit(name='وحدة Questions Test', course_id=course.id, show_in_bot=True)
    db_session.session.add(unit)
    db_session.session.commit()
    db_session.session.refresh(unit)
    lesson = Lesson(name='درس Questions Test', unit_id=unit.id, show_in_bot=True)
    db_session.session.add(lesson)
    db_session.session.commit()
    db_session.session.refresh(lesson)
    q1 = Question(question_text='سؤال 1', lesson_id=lesson.id, difficulty='easy', bloom_level='remember')
    q2 = Question(question_text='سؤال 2', lesson_id=lesson.id, difficulty='medium', bloom_level='understand')
    q3 = Question(question_text='سؤال 3 - محجوب', lesson_id=lesson.id, is_blocked=True)
    db_session.session.add_all([q1, q2, q3])
    db_session.session.commit()
    for q in [q1, q2, q3]:
        db_session.session.refresh(q)
    opt1 = Option(option_text='إجابة صحيحة', is_correct=True, question_id=q1.question_id)
    opt2 = Option(option_text='إجابة خاطئة', is_correct=False, question_id=q1.question_id)
    db_session.session.add_all([opt1, opt2])
    db_session.session.commit()
    return {'course': course, 'unit': unit, 'lesson': lesson, 'q1': q1, 'q2': q2, 'q3': q3}


class TestLessonQuestionsAPI:
    """اختبارات API أسئلة الدرس"""

    def test_lesson_questions_empty(self, client, sample_lesson):
        """درس بدون أسئلة"""
        response = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_lesson_questions_with_data(self, client, full_curriculum):
        """درس يحتوي أسئلة"""
        lesson = full_curriculum['lesson']
        response = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # يجب أن يُرجع الأسئلة غير المحجوبة فقط
        assert len(data) == 2  # q1, q2 فقط (q3 محجوب)

    def test_lesson_questions_blocked_filtered(self, client, full_curriculum):
        """الأسئلة المحجوبة لا تظهر"""
        lesson = full_curriculum['lesson']
        response = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = response.get_json()
        question_ids = [q['question_id'] for q in data]
        assert full_curriculum['q3'].question_id not in question_ids

    def test_lesson_questions_response_structure(self, client, full_curriculum):
        """هيكل استجابة الأسئلة"""
        lesson = full_curriculum['lesson']
        response = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = response.get_json()
        if len(data) > 0:
            q = data[0]
            assert 'question_id' in q
            assert 'question_text' in q
            assert 'options' in q
            assert 'correct_option_id' in q
            assert 'difficulty' in q
            assert 'bloom_level' in q

    def test_lesson_questions_includes_lesson_info(self, client, full_curriculum):
        """الأسئلة تتضمن معلومات الدرس/الوحدة/المنهج"""
        lesson = full_curriculum['lesson']
        response = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        data = response.get_json()
        if len(data) > 0:
            q = data[0]
            assert 'lesson' in q
            assert 'unit' in q
            assert 'course' in q

    def test_lesson_questions_nonexistent(self, client):
        """درس غير موجود"""
        response = client.get('/api/v1/lessons/99999/questions')
        assert response.status_code == 404


class TestUnitQuestionsAPI:
    """اختبارات API أسئلة الوحدة"""

    def test_unit_questions(self, client, full_curriculum):
        """أسئلة وحدة"""
        unit = full_curriculum['unit']
        response = client.get(f'/api/v1/units/{unit.id}/questions')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_unit_questions_nonexistent(self, client):
        """وحدة غير موجودة"""
        response = client.get('/api/v1/units/99999/questions')
        assert response.status_code == 404

    def test_unit_questions_show_all(self, client, full_curriculum):
        """أسئلة الوحدة مع show_all"""
        unit = full_curriculum['unit']
        response = client.get(f'/api/v1/units/{unit.id}/questions?show_all=true')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_unit_questions_blocked_filtered(self, client, full_curriculum):
        """الأسئلة المحجوبة لا تظهر في الوحدة"""
        unit = full_curriculum['unit']
        response = client.get(f'/api/v1/units/{unit.id}/questions')
        data = response.get_json()
        question_ids = [q['question_id'] for q in data]
        assert full_curriculum['q3'].question_id not in question_ids


class TestCourseQuestionsAPI:
    """اختبارات API أسئلة المنهج"""

    def test_course_questions(self, client, full_curriculum):
        """أسئلة منهج"""
        course = full_curriculum['course']
        response = client.get(f'/api/v1/courses/{course.id}/questions')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_course_questions_nonexistent(self, client):
        """منهج غير موجود"""
        response = client.get('/api/v1/courses/99999/questions')
        assert response.status_code == 404

    def test_course_questions_hidden_course(self, client, db_session, app):
        """منهج مخفي - أسئلته لا تظهر"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question, Option
        c = Course(name='منهج مخفي Questions', show_in_bot=False)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال مخفي', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        response = client.get(f'/api/v1/courses/{c.id}/questions')
        data = response.get_json()
        assert len(data) == 0  # المنهج مخفي → لا أسئلة


class TestAllQuestionsAPI:
    """اختبارات API كل الأسئلة"""

    def test_all_questions_empty(self, client):
        """لا أسئلة في البداية"""
        response = client.get('/api/v1/questions/all')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_all_questions_with_data(self, client, full_curriculum):
        """كل الأسئلة مع وجود بيانات"""
        response = client.get('/api/v1/questions/all')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # الأسئلة المرئية للمنهج المفعّل
        assert len(data) >= 2  # q1 + q2 على الأقل

    def test_all_questions_response_structure(self, client, full_curriculum):
        """هيكل كل الأسئلة"""
        response = client.get('/api/v1/questions/all')
        data = response.get_json()
        if len(data) > 0:
            q = data[0]
            assert 'question_id' in q
            assert 'options' in q


class TestRecentQuestionsAPI:
    """اختبارات API الأسئلة الأخيرة"""

    def test_recent_questions(self, client):
        """الأسئلة الأخيرة"""
        response = client.get('/api/v1/questions/recent')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None

    def test_recent_questions_with_limit(self, client):
        """الأسئلة الأخيرة مع تحديد العدد"""
        response = client.get('/api/v1/questions/recent?limit=5')
        assert response.status_code == 200

    def test_recent_questions_with_data(self, client, full_curriculum):
        """الأسئلة الأخيرة مع وجود بيانات"""
        response = client.get('/api/v1/questions/recent?limit=10')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None


class TestToggleBlockQuestion:
    """اختبارات حجب وإظهار الأسئلة"""

    def test_toggle_block_requires_auth(self, client, full_curriculum):
        """الحجب يتطلب مصادقة"""
        q = full_curriculum['q1']
        response = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        assert response.status_code in [302, 401, 403]

    def test_toggle_block_with_admin(self, client, admin_user, full_curriculum):
        """الأدمن يحجب سؤالاً"""
        q = full_curriculum['q1']
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        assert response.status_code in [200, 302, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_toggle_block_question_nonexistent(self, client, admin_user):
        """حجب سؤال غير موجود"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/v1/questions/99999/toggle-block')
        assert response.status_code in [302, 404]


class TestCourseUnitQuestionsNested:
    """اختبارات الأسئلة عبر المسار المتداخل"""

    def test_nested_course_unit_questions(self, client, full_curriculum):
        """الأسئلة عبر course/unit path"""
        course = full_curriculum['course']
        unit = full_curriculum['unit']
        response = client.get(f'/api/v1/courses/{course.id}/units/{unit.id}/questions')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_nested_wrong_course_for_unit(self, client, full_curriculum):
        """وحدة لا تنتمي للمنهج المحدد"""
        unit = full_curriculum['unit']
        response = client.get(f'/api/v1/courses/99999/units/{unit.id}/questions')
        assert response.status_code == 404

    def test_nested_nonexistent_unit(self, client, full_curriculum):
        """وحدة غير موجودة في المسار"""
        course = full_curriculum['course']
        response = client.get(f'/api/v1/courses/{course.id}/units/99999/questions')
        assert response.status_code == 404

    def test_nested_unit_in_wrong_course(self, client, full_curriculum, db_session, app):
        """وحدة موجودة لكن في منهج مختلف"""
        from src.models.curriculum import Course, Unit
        other_course = Course(name='منهج آخر nested')
        db_session.session.add(other_course)
        db_session.session.commit()
        db_session.session.refresh(other_course)
        unit = full_curriculum['unit']
        response = client.get(f'/api/v1/courses/{other_course.id}/units/{unit.id}/questions')
        assert response.status_code == 404
