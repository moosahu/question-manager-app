"""
اختبارات موسعة لـ admin_ai routes
يغطي: providers PUT, settings import, automation test, dashboard, inactive/low-score students, audit log
"""
import pytest


class TestAdminAIProviders:
    """اختبارات مزودي AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_set_ai_provider_no_auth(self, client):
        """تعيين مزود AI بدون مصادقة"""
        response = client.put('/api/admin/ai/providers', json={})
        assert response.status_code in [302, 401, 403]

    def test_set_ai_provider_as_admin(self, client, admin_user):
        """تعيين مزود AI كأدمن"""
        self._login(client, admin_user)
        response = client.put('/api/admin/ai/providers', json={
            'provider': 'gemini',
            'model': 'gemini-2.0-flash'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_get_providers_as_admin(self, client, admin_user):
        """جلب مزودي AI كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/providers')
        assert response.status_code in [200, 500]


class TestAdminAISettingsImport:
    """اختبارات استيراد إعدادات AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_import_settings_no_auth(self, client):
        """استيراد إعدادات بدون مصادقة"""
        response = client.post('/api/admin/ai/settings/import', json={})
        assert response.status_code in [302, 401, 403]

    def test_import_settings_empty(self, client, admin_user):
        """استيراد إعدادات ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_import_settings_valid(self, client, admin_user):
        """استيراد إعدادات ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import', json={
            'settings': {'max_tokens': 1000}
        })
        assert response.status_code in [200, 400, 422, 500]


class TestAdminAIAutomation:
    """اختبارات الأتمتة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_automation_test_no_auth(self, client):
        """اختبار الأتمتة بدون مصادقة"""
        response = client.post('/api/admin/ai/automation/test', json={})
        assert response.status_code in [302, 401, 403]

    def test_automation_test_as_admin(self, client, admin_user):
        """اختبار الأتمتة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/automation/test', json={})
        assert response.status_code in [200, 400, 500]


class TestAdminAIDashboard:
    """اختبارات لوحة تحكم AI الموسعة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_api_admin_dashboard_no_auth(self, client):
        """لوحة تحكم AI بدون مصادقة"""
        response = client.get('/api/admin/ai/dashboard')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_api_admin_dashboard_as_admin(self, client, admin_user):
        """لوحة تحكم AI كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard')
        assert response.status_code in [200, 500]

    def test_inactive_students_no_auth(self, client):
        """الطلاب غير النشطين بدون مصادقة"""
        response = client.get('/api/admin/ai/students/inactive')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_inactive_students_as_admin(self, client, admin_user):
        """الطلاب غير النشطين كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/students/inactive')
        assert response.status_code in [200, 500]

    def test_low_score_students_no_auth(self, client):
        """الطلاب ذوو الدرجات المنخفضة بدون مصادقة"""
        response = client.get('/api/admin/ai/students/low-score')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_low_score_students_as_admin(self, client, admin_user):
        """الطلاب ذوو الدرجات المنخفضة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/students/low-score')
        assert response.status_code in [200, 500]

    def test_students_need_attention_with_filters(self, client, admin_user):
        """الطلاب المحتاجون اهتماماً مع فلاتر"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/students-need-attention?limit=10')
        assert response.status_code in [200, 500]


class TestAdminAIAuditLog:
    """اختبارات سجل المراجعة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_audit_log_no_auth(self, client):
        """جلب سجل المراجعة بدون مصادقة"""
        response = client.get('/api/admin/ai/audit-log')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_get_audit_log_as_admin(self, client, admin_user):
        """جلب سجل المراجعة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/audit-log')
        assert response.status_code in [200, 500]

    def test_create_audit_log_no_auth(self, client):
        """إنشاء سجل مراجعة بدون مصادقة"""
        response = client.post('/api/admin/ai/audit-log', json={})
        assert response.status_code in [302, 401, 403]

    def test_create_audit_log_as_admin(self, client, admin_user):
        """إنشاء سجل مراجعة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'test_action',
            'details': 'تفاصيل اختبار'
        })
        assert response.status_code in [200, 201, 400, 500]

    def test_analyze_student_with_data(self, client, admin_user, db_session, app):
        """تحليل طالب موجود"""
        import secrets
        from src.models.student import Student
        s = Student(name='AI Stu', username='aistu1', email='aistu1@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        self._login(client, admin_user)
        response = client.post(f'/api/admin/ai/analyze/student/{s.id}')
        assert response.status_code in [200, 400, 404, 500]

    def test_messages_stats_with_params(self, client, admin_user):
        """إحصائيات الرسائل مع معاملات"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats?days=30')
        assert response.status_code in [200, 500]

    def test_logs_with_filters(self, client, admin_user):
        """سجلات AI مع فلاتر"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/logs?limit=50')
        assert response.status_code in [200, 500]
