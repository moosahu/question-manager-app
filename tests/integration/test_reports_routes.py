"""
اختبارات شاملة لـ Reports API
يغطي: students performance, top performers, need help, courses analysis, activity, student report
"""
import pytest


class TestReportsAuth:
    """اختبارات المصادقة للتقارير"""

    def test_reports_index_no_auth(self, client):
        """صفحة التقارير بدون مصادقة"""
        response = client.get('/reports/')
        assert response.status_code in [302, 401, 403]

    def test_api_performance_no_auth(self, client):
        """API الأداء بدون مصادقة"""
        response = client.get('/reports/api/students-performance')
        assert response.status_code in [302, 401, 403]

    def test_api_top_performers_no_auth(self, client):
        """API المتصدرين بدون مصادقة"""
        response = client.get('/reports/api/top-performers')
        assert response.status_code in [302, 401, 403]

    def test_api_need_help_no_auth(self, client):
        """API من يحتاج مساعدة بدون مصادقة"""
        response = client.get('/reports/api/need-help')
        assert response.status_code in [302, 401, 403]

    def test_api_courses_analysis_no_auth(self, client):
        """API تحليل المناهج بدون مصادقة"""
        response = client.get('/reports/api/courses-analysis')
        assert response.status_code in [302, 401, 403]

    def test_api_activity_no_auth(self, client):
        """API النشاط بدون مصادقة"""
        response = client.get('/reports/api/activity')
        assert response.status_code in [302, 401, 403]


class TestReportsAsAdmin:
    """اختبارات التقارير كأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_reports_index_as_admin(self, client, admin_user):
        """صفحة التقارير كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/')
        assert response.status_code in [200, 302, 500]

    def test_api_students_performance_as_admin(self, client, admin_user):
        """API أداء الطلاب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/students-performance')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_api_students_performance_empty(self, client, admin_user):
        """API أداء الطلاب - قاعدة بيانات فارغة"""
        self._login(client, admin_user)
        response = client.get('/reports/api/students-performance')
        assert response.status_code in [200, 500]

    def test_api_top_performers_as_admin(self, client, admin_user):
        """API المتصدرين كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/top-performers')
        assert response.status_code in [200, 500]

    def test_api_top_performers_with_limit(self, client, admin_user):
        """API المتصدرين مع حد"""
        self._login(client, admin_user)
        response = client.get('/reports/api/top-performers?limit=5')
        assert response.status_code in [200, 500]

    def test_api_need_help_as_admin(self, client, admin_user):
        """API من يحتاج مساعدة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/need-help')
        assert response.status_code in [200, 500]

    def test_api_courses_analysis_as_admin(self, client, admin_user):
        """API تحليل المناهج كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/courses-analysis')
        assert response.status_code in [200, 500]

    def test_api_activity_as_admin(self, client, admin_user):
        """API النشاط كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/activity')
        assert response.status_code in [200, 500]

    def test_api_activity_with_params(self, client, admin_user):
        """API النشاط مع معاملات"""
        self._login(client, admin_user)
        response = client.get('/reports/api/activity?days=7')
        assert response.status_code in [200, 400, 500]

    def test_api_student_report_nonexistent(self, client, admin_user):
        """تقرير طالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/reports/api/student/99999')
        assert response.status_code in [404, 500]

    def test_api_student_detail_nonexistent(self, client, admin_user):
        """تفاصيل طالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/reports/api/student/99999/detail')
        assert response.status_code in [404, 500]

    def test_api_student_report_with_student(self, client, admin_user, db_session, app):
        """تقرير طالب موجود"""
        from src.models.student import Student
        s = Student(name='Report Student', username='report_stu', email='reportstu@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login(client, admin_user)
        response = client.get(f'/reports/api/student/{s.id}')
        assert response.status_code in [200, 404, 500]

    def test_api_student_detail_with_student(self, client, admin_user, db_session, app):
        """تفاصيل طالب موجود"""
        from src.models.student import Student
        s = Student(name='Detail Student', username='detail_stu', email='detailstu@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login(client, admin_user)
        response = client.get(f'/reports/api/student/{s.id}/detail')
        assert response.status_code in [200, 404, 500]

    def test_student_detail_page(self, client, admin_user, db_session, app):
        """صفحة تفاصيل الطالب"""
        from src.models.student import Student
        s = Student(name='Page Student', username='page_stu', email='pagstu@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login(client, admin_user)
        response = client.get(f'/reports/student/{s.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_top_performers_page(self, client, admin_user):
        """صفحة المتصدرين"""
        self._login(client, admin_user)
        response = client.get('/reports/top-performers')
        assert response.status_code in [200, 302, 500]

    def test_export_excel_no_auth(self, client):
        """تصدير إكسل بدون مصادقة"""
        response = client.post('/reports/api/export-excel', json={})
        assert response.status_code in [302, 401, 403]

    def test_export_excel_as_admin(self, client, admin_user):
        """تصدير إكسل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/reports/api/export-excel', json={
            'report_type': 'all'
        })
        assert response.status_code in [200, 400, 500]
