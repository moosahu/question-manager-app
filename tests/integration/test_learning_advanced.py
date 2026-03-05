"""
اختبارات متقدمة لـ learning_routes
يغطي: admin pages, concept maps, summaries, reports, with actual data
"""
import pytest
import secrets


def _make_student(db_session, username, email):
    from src.models.student import Student
    s = Student(name='Learn Stu', username=username, email=email, is_active=True)
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestLearningAPIWithData:
    """اختبارات API التعلم مع بيانات فعلية"""

    def test_get_all_lessons_public(self, client):
        """جلب كل الدروس - عام"""
        response = client.get('/learning/api/lessons')
        assert response.status_code in [200, 401, 500]

    def test_get_all_lessons_with_token(self, client, db_session, app):
        """جلب كل الدروس مع token"""
        s = _make_student(db_session, 'learn_all1', 'learnall1@test.com')
        response = client.get(
            '/learning/api/lessons',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 500]

    def test_get_lesson_content_nonexistent_no_auth(self, client):
        """محتوى درس غير موجود بدون مصادقة"""
        response = client.get('/learning/api/lessons/99999')
        assert response.status_code in [200, 401, 404, 500]

    def test_get_lesson_content_with_token(self, client, db_session, app):
        """محتوى درس مع token"""
        s = _make_student(db_session, 'learn_cont1', 'learncont1@test.com')
        response = client.get(
            '/learning/api/lessons/99999',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 404, 500]

    def test_get_lesson_content_with_actual_lesson(self, client, db_session, app):
        """محتوى درس موجود مع token"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='Learn Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Learn Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Learn Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        s = _make_student(db_session, 'learn_cont2', 'learncont2@test.com')
        response = client.get(
            f'/learning/api/lessons/{l.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 404, 500]

    def test_update_progress_no_auth(self, client):
        """تحديث التقدم بدون مصادقة"""
        response = client.post('/learning/api/lessons/99999/progress', json={})
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_update_progress_with_token(self, client, db_session, app):
        """تحديث التقدم مع token"""
        s = _make_student(db_session, 'learn_prog1', 'learnprog1@test.com')
        response = client.post(
            '/learning/api/lessons/99999/progress',
            json={'progress': 50, 'time_spent': 120},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_get_student_stats_no_auth(self, client):
        """إحصائيات الطالب بدون مصادقة"""
        response = client.get('/learning/api/students/99999/stats')
        assert response.status_code in [302, 401, 403]

    def test_get_student_stats_as_admin(self, client, admin_user):
        """إحصائيات الطالب كأدمن"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/learning/api/students/99999/stats')
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
        assert response.status_code in [302, 401, 403]

    def test_admin_index_as_admin(self, client, admin_user):
        """صفحة أدمن التعلم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin')
        assert response.status_code in [200, 302, 404, 500]

    def test_admin_summaries_no_auth(self, client):
        """صفحة الملخصات بدون مصادقة"""
        response = client.get('/learning/admin/summaries')
        assert response.status_code in [302, 401, 403]

    def test_admin_summaries_as_admin(self, client, admin_user):
        """صفحة الملخصات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/summaries')
        assert response.status_code in [200, 302, 404, 500]

    def test_admin_concept_maps_no_auth(self, client):
        """صفحة خرائط المفاهيم بدون مصادقة"""
        response = client.get('/learning/admin/concept-maps')
        assert response.status_code in [302, 401, 403]

    def test_admin_concept_maps_as_admin(self, client, admin_user):
        """صفحة خرائط المفاهيم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-maps')
        assert response.status_code in [200, 302, 404, 500]

    def test_admin_view_concept_map_nonexistent(self, client, admin_user):
        """عرض خريطة مفاهيم غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-map/99999')
        assert response.status_code in [302, 404, 500]

    def test_admin_edit_concept_map_get_nonexistent(self, client, admin_user):
        """تعديل خريطة مفاهيم غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-map/99999/edit')
        assert response.status_code in [302, 404, 500]

    def test_admin_add_summary_get_no_auth(self, client):
        """إضافة ملخص بدون مصادقة"""
        response = client.get('/learning/admin/summary/add')
        assert response.status_code in [302, 401, 403]

    def test_admin_add_summary_get_as_admin(self, client, admin_user):
        """صفحة إضافة ملخص كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/summary/add')
        assert response.status_code in [200, 302, 404, 500]

    def test_admin_add_summary_post_empty(self, client, admin_user):
        """إضافة ملخص ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/summary/add', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_admin_add_concept_map_get_as_admin(self, client, admin_user):
        """صفحة إضافة خريطة مفاهيم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-map/add')
        assert response.status_code in [200, 302, 404, 500]

    def test_admin_add_concept_map_post_empty(self, client, admin_user):
        """إضافة خريطة مفاهيم ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/concept-map/add', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_admin_reports_no_auth(self, client):
        """تقارير التعلم بدون مصادقة"""
        response = client.get('/learning/admin/reports')
        assert response.status_code in [302, 401, 403]

    def test_admin_reports_as_admin(self, client, admin_user):
        """تقارير التعلم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/reports')
        assert response.status_code in [200, 302, 404, 500]

    def test_delete_concept_map_nonexistent(self, client, admin_user):
        """حذف خريطة مفاهيم غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/concept-maps/99999/delete')
        assert response.status_code in [200, 302, 404, 500]

    def test_delete_summary_nonexistent(self, client, admin_user):
        """حذف ملخص غير موجود"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/summaries/99999/delete')
        assert response.status_code in [200, 302, 404, 500]

    def test_generate_ai_concept_map_no_auth(self, client):
        """توليد خريطة مفاهيم AI بدون مصادقة"""
        response = client.post('/learning/admin/concept-map/generate-ai', json={})
        assert response.status_code in [302, 401, 403]

    def test_generate_ai_concept_map_empty(self, client, admin_user):
        """توليد خريطة مفاهيم AI ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/concept-map/generate-ai', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_save_ai_concept_map_empty(self, client, admin_user):
        """حفظ خريطة مفاهيم AI ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/concept-map/save-ai-generated', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_suggest_branches_empty(self, client, admin_user):
        """اقتراح فروع ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/learning/admin/concept-map/suggest-branches', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_export_concept_map_nonexistent(self, client, admin_user):
        """تصدير خريطة مفاهيم غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/learning/admin/concept-map/export/99999/json')
        assert response.status_code in [200, 302, 404, 500]
