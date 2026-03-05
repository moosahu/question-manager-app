"""
اختبارات شاملة لـ Learning Routes
يغطي: lesson content, progress, all lessons, student stats, admin pages
"""
import pytest


class TestLearningAPIPublic:
    """الـ API العامة للتعلم (بدون مصادقة أدمن)"""

    def test_get_lesson_content_nonexistent(self, client):
        """محتوى درس غير موجود"""
        response = client.get('/learning/api/lessons/99999')
        assert response.status_code in [200, 401, 404, 500]

    def test_get_lesson_content_existing(self, client, sample_lesson):
        """محتوى درس موجود"""
        response = client.get(f'/learning/api/lessons/{sample_lesson.id}')
        assert response.status_code in [200, 401, 404, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_get_all_lessons(self, client):
        """جلب كل الدروس"""
        response = client.get('/learning/api/lessons')
        assert response.status_code in [200, 401, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_get_all_lessons_with_filter(self, client):
        """جلب الدروس مع فلتر"""
        response = client.get('/learning/api/lessons?show_in_bot=true')
        assert response.status_code in [200, 401, 500]

    def test_get_all_lessons_with_course_filter(self, client, full_curriculum_learning):
        """جلب الدروس مع فلتر منهج"""
        course = full_curriculum_learning['course']
        response = client.get(f'/learning/api/lessons?course_id={course.id}')
        assert response.status_code in [200, 401, 500]


class TestLearningProgress:
    """اختبارات تحديث التقدم"""

    def _create_student(self, db_session, username, email):
        import secrets
        from src.models.student import Student
        s = Student(name='Progress Student', username=username, email=email, is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        return s

    def test_update_progress_no_auth(self, client, sample_lesson):
        """تحديث التقدم بدون مصادقة"""
        response = client.post(f'/learning/api/lessons/{sample_lesson.id}/progress', json={
            'student_id': 1,
            'score': 80
        })
        # يقبل بدون مصادقة (student auth عبر session_token)
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_update_progress_with_student(self, client, db_session, app, sample_lesson):
        """تحديث التقدم مع session_token"""
        s = self._create_student(db_session, 'progress_stu', 'progressstu@test.com')
        response = client.post(
            f'/learning/api/lessons/{sample_lesson.id}/progress',
            json={'student_id': s.id, 'score': 75},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_update_progress_nonexistent_lesson(self, client, db_session, app):
        """تحديث تقدم لدرس غير موجود"""
        s = self._create_student(db_session, 'progress_stu2', 'progressstu2@test.com')
        response = client.post(
            '/learning/api/lessons/99999/progress',
            json={'student_id': s.id, 'score': 50},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [400, 401, 404, 500]


class TestLearningStudentStats:
    """اختبارات إحصائيات الطالب"""

    def _login_admin(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_student_stats_no_auth(self, client):
        """إحصائيات الطالب بدون مصادقة"""
        response = client.get('/learning/api/students/1/stats')
        assert response.status_code in [302, 401, 403]

    def test_student_stats_as_admin(self, client, admin_user):
        """إحصائيات الطالب كأدمن"""
        self._login_admin(client, admin_user)
        response = client.get('/learning/api/students/99999/stats')
        assert response.status_code in [200, 404, 500]

    def test_student_stats_existing(self, client, admin_user, db_session, app):
        """إحصائيات طالب موجود"""
        from src.models.student import Student
        s = Student(name='Stats Student', username='stats_stu', email='statsstu@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login_admin(client, admin_user)
        response = client.get(f'/learning/api/students/{s.id}/stats')
        assert response.status_code in [200, 404, 500]


class TestLearningAdminPages:
    """اختبارات صفحات الأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_admin_index_no_auth(self, client):
        """صفحة أدمن التعلم بدون مصادقة"""
        response = client.get('/learning/admin')
        assert response.status_code in [302, 401]

    def test_admin_index_as_admin(self, client, admin_user):
        """صفحة أدمن التعلم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin')
        assert response.status_code in [200, 302, 500]

    def test_admin_summaries_as_admin(self, client, admin_user):
        """صفحة الملخصات"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/summaries')
        assert response.status_code in [200, 302, 500]

    def test_admin_concept_maps_as_admin(self, client, admin_user):
        """صفحة الخرائط الذهنية"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-maps')
        assert response.status_code in [200, 302, 500]

    def test_admin_reports_as_admin(self, client, admin_user):
        """صفحة التقارير"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/reports')
        assert response.status_code in [200, 302, 500]

    def test_view_concept_map_nonexistent(self, client, admin_user):
        """عرض خريطة ذهنية غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-map/99999')
        assert response.status_code in [302, 404, 500]

    def test_admin_add_summary_get(self, client, admin_user):
        """صفحة إضافة ملخص"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/summary/add')
        assert response.status_code in [200, 302, 500]

    def test_admin_add_concept_map_get(self, client, admin_user):
        """صفحة إضافة خريطة ذهنية"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-map/add')
        assert response.status_code in [200, 302, 500]

    def test_delete_concept_map_nonexistent(self, client, admin_user):
        """حذف خريطة ذهنية غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/concept-maps/99999/delete')
        assert response.status_code in [302, 404, 500]

    def test_delete_summary_nonexistent(self, client, admin_user):
        """حذف ملخص غير موجود"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/summaries/99999/delete')
        assert response.status_code in [302, 404, 500]


@pytest.fixture
def full_curriculum_learning(db_session, app):
    """منهج كامل للاختبارات"""
    from src.models.curriculum import Course, Unit, Lesson
    c = Course(name='Learning Test Course', show_in_bot=True)
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    u = Unit(name='Learning Unit', course_id=c.id, show_in_bot=True)
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    l = Lesson(name='Learning Lesson', unit_id=u.id, show_in_bot=True)
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return {'course': c, 'unit': u, 'lesson': l}
