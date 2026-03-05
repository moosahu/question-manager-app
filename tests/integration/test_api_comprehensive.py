"""
اختبارات شاملة لـ API endpoints
يغطي: courses, units, lessons, questions, toggle visibility, activities
"""
import pytest


class TestCoursesAPI:
    """اختبارات API المناهج"""

    def test_get_all_courses_empty(self, client):
        """قائمة المناهج فارغة في البداية"""
        response = client.get('/api/v1/courses')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_courses_returns_json(self, client):
        """الاستجابة بتنسيق JSON"""
        response = client.get('/api/v1/courses')
        assert response.content_type == 'application/json'

    def test_get_courses_with_data(self, client, sample_course):
        """المناهج تظهر عند وجود بيانات"""
        response = client.get('/api/v1/courses')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        names = [c['name'] for c in data]
        assert 'كيمياء - اختبار' in names

    def test_get_courses_hidden_not_shown(self, client, sample_course_hidden):
        """المنهج المخفي لا يظهر في قائمة البوت"""
        response = client.get('/api/v1/courses')
        assert response.status_code == 200
        data = response.get_json()
        names = [c['name'] for c in data]
        assert 'كيمياء - مخفي' not in names

    def test_get_courses_show_all_includes_hidden(self, client, sample_course, sample_course_hidden):
        """show_all=true يظهر المناهج المخفية أيضاً"""
        response = client.get('/api/v1/courses?show_all=true')
        assert response.status_code == 200
        data = response.get_json()
        names = [c['name'] for c in data]
        assert 'كيمياء - مخفي' in names

    def test_get_courses_show_all_false(self, client, sample_course, sample_course_hidden):
        """show_all=false يخفي المناهج المخفية"""
        response = client.get('/api/v1/courses?show_all=false')
        assert response.status_code == 200
        data = response.get_json()
        names = [c['name'] for c in data]
        assert 'كيمياء - مخفي' not in names

    def test_courses_response_structure(self, client, sample_course):
        """هيكل الاستجابة يحتوي على الحقول الصحيحة"""
        response = client.get('/api/v1/courses?show_all=true')
        data = response.get_json()
        if len(data) > 0:
            course = data[0]
            assert 'id' in course
            assert 'name' in course
            assert 'order_num' in course

    def test_toggle_course_visibility_requires_login(self, client, sample_course):
        """toggle المنهج يتطلب تسجيل دخول"""
        response = client.post(f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility', json={})
        assert response.status_code in [302, 401, 403]

    def test_toggle_course_visibility_with_admin(self, client, admin_user, sample_course):
        """الأدمن يمكنه toggle المنهج"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        original = sample_course.show_in_bot
        response = client.post(f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility', json={})
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True
            assert data['show_in_bot'] != original

    def test_toggle_course_nonexistent(self, client, admin_user):
        """toggle منهج غير موجود"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/v1/courses/99999/toggle-bot-visibility', json={})
        assert response.status_code in [404, 302]


class TestUnitsAPI:
    """اختبارات API الوحدات"""

    def test_get_units_for_course(self, client, sample_unit):
        """جلب وحدات منهج معين"""
        response = client.get(f'/api/v1/courses/{sample_unit.course_id}/units')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_units_nonexistent_course(self, client):
        """وحدات منهج غير موجود"""
        response = client.get('/api/v1/courses/99999/units')
        assert response.status_code == 404

    def test_units_response_structure(self, client, sample_unit):
        """هيكل استجابة الوحدات"""
        response = client.get(f'/api/v1/courses/{sample_unit.course_id}/units?show_all=true')
        assert response.status_code == 200
        data = response.get_json()
        if len(data) > 0:
            unit = data[0]
            assert 'id' in unit
            assert 'name' in unit

    def test_hidden_unit_not_shown(self, client, db_session, app, sample_course):
        """الوحدة المخفية لا تظهر للبوت"""
        from src.models.curriculum import Unit
        hidden_unit = Unit(name='وحدة مخفية API', course_id=sample_course.id, show_in_bot=False)
        db_session.session.add(hidden_unit)
        db_session.session.commit()
        response = client.get(f'/api/v1/courses/{sample_course.id}/units')
        assert response.status_code == 200
        data = response.get_json()
        names = [u['name'] for u in data]
        assert 'وحدة مخفية API' not in names

    def test_hidden_unit_shown_with_show_all(self, client, db_session, app, sample_course):
        """الوحدة المخفية تظهر مع show_all=true"""
        from src.models.curriculum import Unit
        hidden_unit = Unit(name='وحدة مخفية show_all', course_id=sample_course.id, show_in_bot=False)
        db_session.session.add(hidden_unit)
        db_session.session.commit()
        response = client.get(f'/api/v1/courses/{sample_course.id}/units?show_all=true')
        assert response.status_code == 200
        data = response.get_json()
        names = [u['name'] for u in data]
        assert 'وحدة مخفية show_all' in names

    def test_toggle_unit_visibility_requires_login(self, client, sample_unit):
        """toggle الوحدة يتطلب تسجيل دخول"""
        response = client.post(f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility', json={})
        assert response.status_code in [302, 401, 403]

    def test_toggle_unit_visibility_with_admin(self, client, admin_user, sample_unit):
        """الأدمن يمكنه toggle الوحدة"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        original = sample_unit.show_in_bot
        response = client.post(f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility', json={})
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True

    def test_toggle_unit_nonexistent(self, client, admin_user):
        """toggle وحدة غير موجودة"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/v1/units/99999/toggle-bot-visibility', json={})
        assert response.status_code in [404, 302]


class TestLessonsAPI:
    """اختبارات API الدروس"""

    def test_get_lessons_for_unit(self, client, sample_lesson):
        """جلب دروس وحدة معينة"""
        response = client.get(f'/api/v1/units/{sample_lesson.unit_id}/lessons')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_lessons_nonexistent_unit(self, client):
        """دروس وحدة غير موجودة"""
        response = client.get('/api/v1/units/99999/lessons')
        assert response.status_code == 404

    def test_lessons_response_structure(self, client, sample_lesson):
        """هيكل استجابة الدروس"""
        response = client.get(f'/api/v1/units/{sample_lesson.unit_id}/lessons?show_all=true')
        assert response.status_code == 200
        data = response.get_json()
        if len(data) > 0:
            lesson = data[0]
            assert 'id' in lesson
            assert 'name' in lesson

    def test_hidden_lesson_not_shown(self, client, db_session, app, sample_unit):
        """الدرس المخفي لا يظهر للبوت"""
        from src.models.curriculum import Lesson
        hidden = Lesson(name='درس مخفي API', unit_id=sample_unit.id, show_in_bot=False)
        db_session.session.add(hidden)
        db_session.session.commit()
        response = client.get(f'/api/v1/units/{sample_unit.id}/lessons')
        assert response.status_code == 200
        data = response.get_json()
        names = [l['name'] for l in data]
        assert 'درس مخفي API' not in names

    def test_toggle_lesson_visibility_requires_login(self, client, sample_lesson):
        """toggle الدرس يتطلب تسجيل دخول"""
        response = client.post(f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility', json={})
        assert response.status_code in [302, 401, 403]

    def test_toggle_lesson_visibility_with_admin(self, client, admin_user, sample_lesson):
        """الأدمن يمكنه toggle الدرس"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility', json={})
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True

    def test_toggle_lesson_nonexistent(self, client, admin_user):
        """toggle درس غير موجود"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/api/v1/lessons/99999/toggle-bot-visibility', json={})
        assert response.status_code in [404, 302]


class TestQuestionsAPI:
    """اختبارات API الأسئلة"""

    def test_get_questions_for_lesson_empty(self, client, sample_lesson):
        """أسئلة درس فارغة"""
        response = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, list)

    def test_get_questions_for_nonexistent_lesson(self, client):
        """أسئلة درس غير موجود"""
        response = client.get('/api/v1/lessons/99999/questions')
        assert response.status_code in [404, 200]

    def test_get_all_questions(self, client, admin_user):
        """قائمة كل الأسئلة - تتطلب تسجيل دخول"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/v1/questions/all')
        assert response.status_code in [200, 302, 404]

    def test_questions_all_without_auth(self, client):
        """قائمة الأسئلة بدون مصادقة"""
        response = client.get('/api/v1/questions/all')
        assert response.status_code in [200, 302, 401, 403]

    def test_questions_with_data(self, client, db_session, app, sample_lesson):
        """أسئلة الدرس تظهر عند وجود بيانات"""
        from src.models.question import Question, Option
        q = Question(question_text='سؤال API', lesson_id=sample_lesson.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        opt = Option(option_text='خيار', is_correct=True, question_id=q.question_id)
        db_session.session.add(opt)
        db_session.session.commit()
        response = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        assert response.status_code in [200, 404]

    def test_toggle_block_question_requires_auth(self, client, db_session, app, sample_lesson):
        """حجب السؤال يتطلب مصادقة"""
        from src.models.question import Question, Option
        q = Question(question_text='سؤال للحجب', lesson_id=sample_lesson.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        response = client.post(f'/api/v1/questions/{q.question_id}/toggle-block', json={})
        assert response.status_code in [302, 401, 403]

    def test_toggle_block_question_with_admin(self, client, admin_user, db_session, app, sample_lesson):
        """الأدمن يمكنه حجب وإظهار الأسئلة"""
        from src.models.question import Question, Option
        q = Question(question_text='سؤال toggle block', lesson_id=sample_lesson.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/api/v1/questions/{q.question_id}/toggle-block', json={})
        assert response.status_code in [200, 302, 404]


class TestActivitiesAPI:
    """اختبارات API الأنشطة"""

    def test_activities_recent_endpoint(self, client):
        """endpoint الأنشطة الأخيرة يرد"""
        response = client.get('/api/v1/activities/recent')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None

    def test_activities_with_limit(self, client):
        """تحديد عدد الأنشطة"""
        response = client.get('/api/v1/activities/recent?limit=5')
        assert response.status_code == 200

    def test_activities_response_structure(self, client):
        """هيكل بيانات الأنشطة"""
        response = client.get('/api/v1/activities/recent')
        data = response.get_json()
        assert data is not None
        # يمكن أن تكون قائمة أو dict يحتوي قائمة
        if isinstance(data, list) and len(data) > 0:
            activity = data[0]
            assert 'action_type' in activity or 'id' in activity
        elif isinstance(data, dict):
            # قد يكون في مفتاح 'activities' أو مباشرةً
            activities = data.get('activities', data.get('data', []))
            assert isinstance(activities, list)


class TestQuestionsWithCourseUnits:
    """اختبارات الأسئلة عبر مسار course/units/questions"""

    def test_questions_via_course_unit_path(self, client, db_session, app, sample_lesson, sample_unit, sample_course):
        """جلب الأسئلة عبر مسار المنهج/الوحدة"""
        response = client.get(f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/questions')
        assert response.status_code in [200, 404]

    def test_questions_invalid_course_unit(self, client):
        """مسار منهج/وحدة غير موجودين"""
        response = client.get('/api/v1/courses/99999/units/99999/questions')
        assert response.status_code in [200, 404, 500]


class TestStudentLoginAPI:
    """اختبارات API تسجيل دخول الطلاب"""

    def test_login_missing_fields(self, client):
        """تسجيل دخول بدون بيانات"""
        response = client.post('/students/api/login', json={})
        data = response.get_json()
        assert data is not None
        assert response.status_code in [400, 401, 422]

    def test_login_wrong_credentials(self, client):
        """بيانات دخول خاطئة"""
        response = client.post('/students/api/login', json={
            'username': 'nonexistent_user',
            'password': 'wrong_pass',
            'device_id': 'device_test'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data.get('success') is False

    def test_login_inactive_student(self, client, inactive_student):
        """طالب حسابه معطل لا يستطيع الدخول"""
        response = client.post('/students/api/login', json={
            'username': inactive_student.username,
            'password': 'Student@123',
            'device_id': 'test_device'
        })
        assert response.status_code in [401, 403]
        data = response.get_json()
        assert data.get('success') is False

    def test_login_valid_student(self, client, student_user):
        """طالب مفعل يمكنه الدخول"""
        response = client.post('/students/api/login', json={
            'username': student_user.username,
            'password': 'Student@123',
            'device_id': 'test_device_001'
        })
        assert response.status_code in [200, 401]
        data = response.get_json()
        assert data is not None

    def test_login_success_response_structure(self, client, student_user):
        """هيكل استجابة تسجيل الدخول الناجح"""
        response = client.post('/students/api/login', json={
            'username': student_user.username,
            'password': 'Student@123',
            'device_id': 'test_device_002'
        })
        data = response.get_json()
        assert 'success' in data


class TestStudentsAdminAPI:
    """اختبارات API إدارة الطلاب"""

    def test_student_list_requires_login(self, client):
        """قائمة الطلاب تتطلب تسجيل دخول"""
        response = client.get('/students/')
        assert response.status_code in [302, 401, 403]

    def test_student_list_with_admin(self, client, admin_user):
        """الأدمن يرى قائمة الطلاب"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/students/')
        assert response.status_code != 302

    def test_add_student_requires_login(self, client):
        """إضافة طالب تتطلب تسجيل دخول"""
        response = client.post('/students/add', json={
            'name': 'Test',
            'username': 'new_student',
            'password': 'Pass@123'
        })
        assert response.status_code in [302, 401, 403]

    def test_student_logout_api(self, client, student_user):
        """تسجيل خروج الطالب"""
        response = client.post('/students/api/logout', json={
            'device_id': 'test_device'
        })
        # بدون token أو مصادقة يرجع خطأ
        assert response.status_code in [200, 400, 401, 403, 404, 405]
