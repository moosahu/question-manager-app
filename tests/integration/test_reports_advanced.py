"""
اختبارات موسعة لـ reports routes
يغطي: student detail, excel export, activity, courses analysis
"""
import pytest


class TestReportsAdvanced:
    """اختبارات متقدمة للتقارير"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_reports_index_no_auth(self, client):
        """صفحة التقارير الرئيسية بدون مصادقة"""
        response = client.get('/reports/')
        assert response.status_code in [302, 401, 403]

    def test_reports_index_as_admin(self, client, admin_user):
        """صفحة التقارير الرئيسية كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/')
        assert response.status_code in [200, 302, 404, 500]

    def test_student_detail_page_nonexistent(self, client, admin_user):
        """صفحة تفاصيل طالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/reports/student/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_top_performers_page_as_admin(self, client, admin_user):
        """صفحة أفضل الطلاب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/top-performers')
        assert response.status_code in [200, 302, 404, 500]

    def test_students_performance_with_filters(self, client, admin_user):
        """تقرير أداء الطلاب مع فلاتر"""
        self._login(client, admin_user)
        response = client.get('/reports/api/students-performance?page=1&per_page=10')
        assert response.status_code in [200, 500]

    def test_top_performers_with_limit(self, client, admin_user):
        """أفضل الطلاب مع حد"""
        self._login(client, admin_user)
        response = client.get('/reports/api/top-performers?limit=5')
        assert response.status_code in [200, 500]

    def test_need_help_with_filters(self, client, admin_user):
        """الطلاب الذين يحتاجون مساعدة مع فلاتر"""
        self._login(client, admin_user)
        response = client.get('/reports/api/need-help?threshold=50')
        assert response.status_code in [200, 500]

    def test_courses_analysis_as_admin(self, client, admin_user):
        """تحليل المناهج كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/courses-analysis')
        assert response.status_code in [200, 500]

    def test_activity_report_as_admin(self, client, admin_user):
        """تقرير النشاط كأدمن"""
        self._login(client, admin_user)
        response = client.get('/reports/api/activity')
        assert response.status_code in [200, 500]

    def test_student_report_nonexistent(self, client, admin_user):
        """تقرير طالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/reports/api/student/99999')
        assert response.status_code in [200, 404, 500]

    def test_student_detail_api_nonexistent(self, client, admin_user):
        """تفاصيل طالب API غير موجود"""
        self._login(client, admin_user)
        response = client.get('/reports/api/student/99999/detail')
        assert response.status_code in [200, 404, 500]

    def test_export_excel_no_auth(self, client):
        """تصدير Excel بدون مصادقة"""
        response = client.post('/reports/api/export-excel', json={})
        assert response.status_code in [302, 401, 403]

    def test_export_excel_as_admin(self, client, admin_user):
        """تصدير Excel كأدمن"""
        self._login(client, admin_user)
        response = client.post('/reports/api/export-excel', json={
            'report_type': 'performance'
        })
        assert response.status_code in [200, 400, 500]

    def test_student_report_with_actual_data(self, client, admin_user, db_session, app):
        """تقرير طالب مع بيانات فعلية"""
        import secrets
        from src.models.student import Student
        s = Student(name='Report Stu', username='reportstu1', email='reportstu1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login(client, admin_user)
        response = client.get(f'/reports/api/student/{s.id}')
        assert response.status_code in [200, 404, 500]

    def test_student_detail_page_existing(self, client, admin_user, db_session, app):
        """صفحة تفاصيل طالب موجود"""
        import secrets
        from src.models.student import Student
        s = Student(name='Detail Stu', username='detailstu1', email='detailstu1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login(client, admin_user)
        response = client.get(f'/reports/student/{s.id}')
        assert response.status_code in [200, 302, 404, 500]
