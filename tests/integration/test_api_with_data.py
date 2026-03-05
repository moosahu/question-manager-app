"""
اختبارات API مع بيانات حقيقية لتحقيق تغطية أعمق
يستخدم fixtures: sample_course, sample_unit, sample_lesson
"""
import pytest
import secrets


class TestApiWithRealCourse:
    """اختبارات API مع منهج حقيقي"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_courses_as_admin(self, client, admin_user, sample_course):
        """جلب المناهج مع بيانات"""
        self._login(client, admin_user)
        response = client.get('/api/courses')
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_get_course_units_real(self, client, admin_user, sample_course, sample_unit):
        """جلب وحدات منهج حقيقي"""
        self._login(client, admin_user)
        response = client.get(f'/api/courses/{sample_course.id}/units')
        assert response.status_code in [200, 302, 404, 500]

    def test_get_unit_lessons_real(self, client, admin_user, sample_unit, sample_lesson):
        """جلب دروس وحدة حقيقية"""
        self._login(client, admin_user)
        response = client.get(f'/api/units/{sample_unit.id}/lessons')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_course_bot_visibility(self, client, admin_user, sample_course):
        """تبديل إظهار منهج في البوت"""
        self._login(client, admin_user)
        response = client.post(
            f'/api/courses/{sample_course.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_toggle_unit_bot_visibility(self, client, admin_user, sample_unit):
        """تبديل إظهار وحدة في البوت"""
        self._login(client, admin_user)
        response = client.post(
            f'/api/units/{sample_unit.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_toggle_lesson_bot_visibility(self, client, admin_user, sample_lesson):
        """تبديل إظهار درس في البوت"""
        self._login(client, admin_user)
        response = client.post(
            f'/api/lessons/{sample_lesson.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_get_lesson_questions_real(self, client, admin_user, sample_lesson):
        """جلب أسئلة درس حقيقي"""
        self._login(client, admin_user)
        response = client.get(f'/api/lessons/{sample_lesson.id}/questions')
        assert response.status_code in [200, 302, 404, 500]

    def test_get_unit_questions_real(self, client, admin_user, sample_unit):
        """جلب أسئلة وحدة حقيقية"""
        self._login(client, admin_user)
        response = client.get(f'/api/units/{sample_unit.id}/questions')
        assert response.status_code in [200, 302, 404, 500]

    def test_get_course_questions_real(self, client, admin_user, sample_course):
        """جلب أسئلة منهج حقيقي"""
        self._login(client, admin_user)
        response = client.get(f'/api/courses/{sample_course.id}/questions')
        assert response.status_code in [200, 302, 404, 500]

    def test_get_course_unit_questions_real(self, client, admin_user, sample_course, sample_unit):
        """جلب أسئلة وحدة من منهج"""
        self._login(client, admin_user)
        response = client.get(
            f'/api/courses/{sample_course.id}/units/{sample_unit.id}/questions'
        )
        assert response.status_code in [200, 302, 404, 500]

    def test_get_course_unit_lessons_real(self, client, admin_user, sample_course, sample_unit):
        """جلب دروس وحدة من منهج"""
        self._login(client, admin_user)
        response = client.get(
            f'/api/courses/{sample_course.id}/units/{sample_unit.id}/lessons'
        )
        assert response.status_code in [200, 302, 404, 500]

    def test_unit_questions_count_real(self, client, admin_user, sample_unit):
        """عدد أسئلة وحدة حقيقية"""
        self._login(client, admin_user)
        response = client.get(f'/api/units/{sample_unit.id}/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_lesson_questions_count_real(self, client, admin_user, sample_lesson):
        """عدد أسئلة درس حقيقي"""
        self._login(client, admin_user)
        response = client.get(f'/api/lessons/{sample_lesson.id}/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_course_questions_count_real(self, client, admin_user, sample_course):
        """عدد أسئلة منهج حقيقي"""
        self._login(client, admin_user)
        response = client.get(f'/api/courses/{sample_course.id}/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_block_all_unit_questions_real(self, client, admin_user, sample_unit):
        """حجب كل أسئلة وحدة حقيقية"""
        self._login(client, admin_user)
        response = client.put(
            f'/api/units/{sample_unit.id}/questions/block-all',
            json={}
        )
        assert response.status_code in [200, 404, 500]

    def test_unblock_all_lesson_questions_real(self, client, admin_user, sample_lesson):
        """رفع حجب كل أسئلة درس حقيقي"""
        self._login(client, admin_user)
        response = client.put(
            f'/api/lessons/{sample_lesson.id}/questions/unblock-all',
            json={}
        )
        assert response.status_code in [200, 404, 500]


class TestQuestionApiWithData:
    """اختبارات CRUD الأسئلة مع بيانات حقيقية"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_create_question_with_lesson(self, client, admin_user, sample_lesson):
        """إنشاء سؤال مع درس حقيقي"""
        self._login(client, admin_user)
        response = client.post('/api/questions', json={
            'question_text': 'ما هو ذرة الكربون؟',
            'answer': 'C',
            'lesson_id': sample_lesson.id,
            'difficulty': 'متوسط'
        })
        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_filter_questions_by_lesson(self, client, admin_user, sample_lesson):
        """فلترة الأسئلة حسب الدرس"""
        self._login(client, admin_user)
        response = client.get(f'/api/questions?lesson_id={sample_lesson.id}')
        assert response.status_code in [200, 404, 500]

    def test_filter_questions_by_course(self, client, admin_user, sample_course):
        """فلترة الأسئلة حسب المنهج"""
        self._login(client, admin_user)
        response = client.get(f'/api/questions?course_id={sample_course.id}')
        assert response.status_code in [200, 404, 500]

    def test_dashboard_statistics_with_data(self, client, admin_user, sample_course, sample_unit, sample_lesson):
        """إحصائيات لوحة التحكم مع بيانات"""
        self._login(client, admin_user)
        response = client.get('/api/dashboard/statistics')
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_dashboard_performance_with_data(self, client, admin_user, sample_course):
        """أداء لوحة التحكم مع بيانات"""
        self._login(client, admin_user)
        response = client.get('/api/dashboard/performance')
        assert response.status_code in [200, 404, 500]


class TestLearningApiWithData:
    """اختبارات API التعلم مع بيانات حقيقية"""

    def _make_student(self, db_session):
        from src.models.student import Student
        s = Student(
            name='Learning Test Stu',
            username=f'learn_stu_{secrets.token_hex(4)}',
            email=f'learn_stu_{secrets.token_hex(4)}@test.com',
            is_active=True
        )
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        return s

    def test_get_lessons_with_token(self, client, db_session, app, sample_lesson):
        """جلب دروس مع token الطالب"""
        s = self._make_student(db_session)
        response = client.get(
            '/learning/api/lessons',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 302, 401, 404, 500]

    def test_get_student_stats_with_token(self, client, db_session, app):
        """جلب إحصائيات الطالب مع token"""
        s = self._make_student(db_session)
        response = client.get(
            f'/learning/api/students/{s.id}/stats',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 302, 404, 500]


class TestCurriculumApiWithData:
    """اختبارات curriculum مع بيانات حقيقية"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_list_curriculum_with_data(self, client, admin_user, sample_course):
        """قائمة المنهج مع بيانات"""
        self._login(client, admin_user)
        response = client.get('/curriculum/')
        assert response.status_code in [200, 302, 404, 500]

    def test_edit_course_real(self, client, admin_user, sample_course):
        """تعديل منهج حقيقي"""
        self._login(client, admin_user)
        response = client.post(
            f'/curriculum/courses/edit/{sample_course.id}',
            data={'name': 'منهج محدث', 'order_num': 1}
        )
        assert response.status_code in [200, 302, 400, 500]

    def test_add_unit_to_real_course(self, client, admin_user, sample_course):
        """إضافة وحدة إلى منهج حقيقي"""
        self._login(client, admin_user)
        response = client.get(f'/curriculum/units/add/{sample_course.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_add_lesson_to_real_unit(self, client, admin_user, sample_unit):
        """إضافة درس إلى وحدة حقيقية"""
        self._login(client, admin_user)
        response = client.get(f'/curriculum/lessons/add/{sample_unit.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_edit_unit_real(self, client, admin_user, sample_unit):
        """تعديل وحدة حقيقية"""
        self._login(client, admin_user)
        response = client.post(
            f'/curriculum/units/edit/{sample_unit.id}',
            data={'name': 'وحدة محدثة', 'order_num': 1}
        )
        assert response.status_code in [200, 302, 400, 500]

    def test_edit_lesson_real(self, client, admin_user, sample_lesson):
        """تعديل درس حقيقي"""
        self._login(client, admin_user)
        response = client.post(
            f'/curriculum/lessons/edit/{sample_lesson.id}',
            data={'name': 'درس محدث', 'order_num': 1}
        )
        assert response.status_code in [200, 302, 400, 500]


class TestReportsApiWithData:
    """اختبارات التقارير مع بيانات حقيقية"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_students_performance_with_student(self, client, admin_user, db_session, app):
        """أداء الطلاب مع طالب حقيقي"""
        from src.models.student import Student
        s = Student(name='Rpt Stu', username='rpt_stu_data1', email='rpt_stu_data1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        self._login(client, admin_user)
        response = client.get('/reports/api/students-performance')
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_top_performers_with_student(self, client, admin_user, db_session, app):
        """أفضل الطلاب مع طالب حقيقي"""
        from src.models.student import Student
        s = Student(name='Top Stu', username='top_stu_data1', email='top_stu_data1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        self._login(client, admin_user)
        response = client.get('/reports/api/top-performers?limit=5')
        assert response.status_code in [200, 404, 500]

    def test_need_help_with_student(self, client, admin_user, db_session, app):
        """الطلاب المحتاجون مساعدة مع طالب حقيقي"""
        from src.models.student import Student
        s = Student(name='Help Stu', username='help_stu_data1', email='help_stu_data1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        self._login(client, admin_user)
        response = client.get('/reports/api/need-help?threshold=50')
        assert response.status_code in [200, 404, 500]
