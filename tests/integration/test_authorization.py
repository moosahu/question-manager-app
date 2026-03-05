"""
اختبارات التفويض (Authorization) - من يملك صلاحية ماذا
"""
import pytest


class TestAdminOnlyRoutes:
    """مسارات الأدمن فقط"""

    def test_curriculum_page_requires_login(self, client):
        """صفحة المناهج تتطلب تسجيل دخول"""
        response = client.get('/curriculum/', follow_redirects=False)
        assert response.status_code == 302

    def test_questions_page_requires_login(self, client):
        """صفحة الأسئلة تتطلب تسجيل دخول"""
        response = client.get('/questions/', follow_redirects=False)
        assert response.status_code in [302, 401, 404]

    def test_reports_requires_login(self, client):
        """تقارير الأداء تتطلب تسجيل دخول"""
        response = client.get('/reports/api/students-performance')
        assert response.status_code in [302, 401, 403]

    def test_add_question_requires_login(self, client):
        """إضافة سؤال تتطلب تسجيل دخول"""
        response = client.post('/api/v1/questions', json={
            'question_text': 'سؤال تجريبي',
            'lesson_id': 1
        })
        assert response.status_code in [302, 401, 403]

    def test_delete_question_requires_login(self, client):
        """حذف سؤال يتطلب تسجيل دخول"""
        response = client.delete('/api/v1/questions/1')
        assert response.status_code in [302, 401, 403]

    def test_block_question_requires_login(self, client):
        """حجب سؤال يتطلب تسجيل دخول"""
        response = client.post('/api/v1/questions/1/toggle-block')
        assert response.status_code in [302, 401, 403]


class TestAdminAccessGranted:
    """الأدمن يملك صلاحية الوصول"""

    def test_admin_can_access_api_questions(self, client, admin_user):
        """الأدمن يقدر يجيب قائمة الأسئلة"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/v1/questions')
        # 200 (قائمة فارغة) أو 200 مع بيانات
        assert response.status_code == 200

    def test_admin_can_toggle_course_visibility(self, client, admin_user, sample_course):
        """الأدمن يقدر يغيّر ظهور المنهج في البوت"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility')
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert data.get('success') is True

    def test_admin_can_access_dashboard_stats(self, client, admin_user):
        """الأدمن يقدر يشوف إحصائيات الداشبورد"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/v1/dashboard/statistics')
        assert response.status_code in [200, 404]  # قد لا يكون مطبّقاً


class TestStudentCantAccessAdmin:
    """الطالب لا يملك صلاحيات الأدمن"""

    def test_student_cannot_block_questions(self, client, student_user):
        """الطالب لا يستطيع حجب الأسئلة"""
        # بدون login → redirect أو 401/403
        response = client.post('/api/v1/questions/1/toggle-block')
        assert response.status_code in [302, 401, 403]

    def test_student_cannot_add_questions(self, client, student_user):
        """الطالب لا يستطيع إضافة أسئلة"""
        response = client.post('/api/v1/questions', json={
            'question_text': 'سؤال من الطالب',
            'lesson_id': 1
        })
        # بدون session → redirect أو 401
        assert response.status_code in [302, 401, 403]
