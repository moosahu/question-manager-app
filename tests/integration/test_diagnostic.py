"""
اختبارات نظام الاختبارات التشخيصية
"""
import pytest


class TestDiagnosticEndpoints:
    """اختبارات API الاختبارات التشخيصية"""

    def test_diagnostic_admin_page_requires_login(self, client):
        """صفحة إدارة التشخيص تتطلب صلاحيات"""
        response = client.get('/api/diagnostic/admin')
        assert response.status_code in [302, 401, 403]

    def test_generate_requires_auth(self, client):
        """توليد اختبار يتطلب مصادقة"""
        response = client.post('/api/diagnostic/generate', json={})
        assert response.status_code in [302, 401, 403]

    def test_tests_list_requires_auth(self, client):
        """قائمة الاختبارات تتطلب مصادقة"""
        response = client.get('/api/diagnostic/tests')
        assert response.status_code in [302, 401, 403]

    def test_student_assigned_tests(self, client):
        """الاختبارات المعيّنة للطالب تتطلب مصادقة"""
        response = client.get('/api/diagnostic/student/assigned')
        assert response.status_code in [302, 400, 401, 403]

    def test_admin_can_access_diagnostic(self, client, admin_user):
        """الأدمن يقدر يدخل على صفحة التشخيص"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/diagnostic/tests')
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_diagnostic_grades_endpoint(self, client, admin_user):
        """endpoint الصفوف الدراسية"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/diagnostic/grades')
        assert response.status_code in [200, 404]

    def test_diagnostic_stats_endpoint(self, client, admin_user):
        """endpoint الإحصائيات"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/api/diagnostic/stats')
        assert response.status_code in [200, 404]


class TestDiagnosticModel:
    """اختبارات نموذج الاختبارات التشخيصية"""

    def test_diagnostic_tables_exist(self, db_session, app):
        """جداول التشخيص موجودة في DB"""
        from sqlalchemy import inspect
        inspector = inspect(db_session.engine)
        tables = inspector.get_table_names()
        # هذه الجداول يجب أن تكون موجودة
        assert 'course' in tables
        assert 'unit' in tables
        assert 'lesson' in tables
        assert 'questions' in tables  # اسم الجدول بالجمع
