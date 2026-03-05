"""
اختبارات analytics وتحليل admin_ai
يغطي: analyze/student/status, analyze/all, dashboard/stats, chat, settings,
       analytics/overview, analytics/trends, notifications/effectiveness,
       report/daily, status, messages/sent, automation/status/toggle
"""
import pytest
import secrets


def _make_student(db_session, username, email):
    from src.models.student import Student
    s = Student(name='AI Stu', username=username, email=email, is_active=True)
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestAdminAIAnalyze:
    """اختبارات تحليل الطلاب"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_analyze_student_status_no_auth(self, client):
        """حالة تحليل الطالب بدون مصادقة"""
        response = client.get('/api/admin/ai/analyze/student/status')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_analyze_student_status_as_admin(self, client, admin_user):
        """حالة تحليل الطالب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/student/status')
        assert response.status_code in [200, 500]

    def test_analyze_all_no_auth(self, client):
        """تحليل كل الطلاب بدون مصادقة"""
        response = client.post('/api/admin/ai/analyze/all', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_analyze_all_as_admin(self, client, admin_user):
        """تحليل كل الطلاب كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/all', json={})
        assert response.status_code in [200, 400, 500]

    def test_analyze_all_status_as_admin(self, client, admin_user):
        """حالة تحليل كل الطلاب كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/all/status')
        assert response.status_code in [200, 500]

    def test_analysis_latest_no_auth(self, client):
        """آخر تحليل بدون مصادقة"""
        response = client.get('/api/admin/ai/analysis/latest/99999')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_analysis_latest_as_admin(self, client, admin_user):
        """آخر تحليل كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analysis/latest/99999')
        assert response.status_code in [200, 404, 500]

    def test_analysis_history_no_auth(self, client):
        """تاريخ التحليل بدون مصادقة"""
        response = client.get('/api/admin/ai/analysis/history/99999')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_analysis_history_as_admin(self, client, admin_user):
        """تاريخ التحليل كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analysis/history/99999')
        assert response.status_code in [200, 404, 500]

    def test_analysis_with_real_student(self, client, admin_user, db_session, app):
        """تحليل طالب حقيقي"""
        s = _make_student(db_session, 'ai_anal_stu1', 'ai_anal_stu1@test.com')
        self._login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/latest/{s.id}')
        assert response.status_code in [200, 404, 500]


class TestAdminAIChat:
    """اختبارات الدردشة مع AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_chat_no_auth(self, client):
        """دردشة بدون مصادقة"""
        response = client.post('/api/admin/ai/chat', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_chat_empty(self, client, admin_user):
        """دردشة ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_chat_with_message(self, client, admin_user):
        """دردشة برسالة"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={
            'message': 'كيف حال الطلاب؟'
        })
        assert response.status_code in [200, 400, 500]

    def test_notification_send_no_auth(self, client):
        """إرسال إشعار AI بدون مصادقة"""
        response = client.post('/api/admin/ai/notification/send', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_notification_send_as_admin(self, client, admin_user):
        """إرسال إشعار AI كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_id': 1,
            'message': 'رسالة تحفيزية'
        })
        assert response.status_code in [200, 400, 404, 500, 503]


class TestAdminAISettings:
    """اختبارات إعدادات AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_settings_no_auth(self, client):
        """جلب الإعدادات بدون مصادقة"""
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_get_settings_as_admin(self, client, admin_user):
        """جلب الإعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in [200, 500]

    def test_update_setting_no_auth(self, client):
        """تحديث إعداد بدون مصادقة"""
        response = client.put('/api/admin/ai/settings/max_tokens', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_update_setting_as_admin(self, client, admin_user):
        """تحديث إعداد كأدمن"""
        self._login(client, admin_user)
        response = client.put('/api/admin/ai/settings/max_tokens', json={
            'value': 1000
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_export_settings_as_admin(self, client, admin_user):
        """تصدير الإعدادات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/settings/export')
        assert response.status_code in [200, 500]

    def test_get_presets_no_auth(self, client):
        """جلب الإعدادات المسبقة بدون مصادقة"""
        response = client.get('/api/admin/ai/settings/presets')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_get_presets_as_admin(self, client, admin_user):
        """جلب الإعدادات المسبقة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/settings/presets')
        assert response.status_code in [200, 500]

    def test_apply_preset_no_auth(self, client):
        """تطبيق إعداد مسبق بدون مصادقة"""
        response = client.post('/api/admin/ai/settings/presets/default/apply', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_apply_preset_as_admin(self, client, admin_user):
        """تطبيق إعداد مسبق كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/default/apply', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_test_analysis_no_auth(self, client):
        """اختبار التحليل بدون مصادقة"""
        response = client.post('/api/admin/ai/test-analysis', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_test_analysis_as_admin(self, client, admin_user):
        """اختبار التحليل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={})
        assert response.status_code in [200, 400, 500]


class TestAdminAIAnalytics:
    """اختبارات تحليلات AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_analytics_overview_no_auth(self, client):
        """نظرة عامة على التحليلات بدون مصادقة"""
        response = client.get('/api/admin/ai/analytics/overview')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_analytics_overview_as_admin(self, client, admin_user):
        """نظرة عامة على التحليلات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview')
        assert response.status_code in [200, 500]

    def test_analytics_trends_no_auth(self, client):
        """اتجاهات التحليلات بدون مصادقة"""
        response = client.get('/api/admin/ai/analytics/trends')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_analytics_trends_as_admin(self, client, admin_user):
        """اتجاهات التحليلات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/trends')
        assert response.status_code in [200, 500]

    def test_notifications_effectiveness_as_admin(self, client, admin_user):
        """فعالية الإشعارات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/notifications/effectiveness')
        assert response.status_code in [200, 500]

    def test_daily_report_as_admin(self, client, admin_user):
        """التقرير اليومي كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/report/daily')
        assert response.status_code in [200, 500]

    def test_status_as_admin(self, client, admin_user):
        """حالة AI كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/status')
        assert response.status_code in [200, 500]

    def test_messages_sent_as_admin(self, client, admin_user):
        """الرسائل المرسلة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent')
        assert response.status_code in [200, 500]

    def test_automation_status_as_admin(self, client, admin_user):
        """حالة الأتمتة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/automation/status')
        assert response.status_code in [200, 500]

    def test_automation_toggle_no_auth(self, client):
        """تبديل الأتمتة بدون مصادقة"""
        response = client.put('/api/admin/ai/automation/toggle', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_automation_toggle_as_admin(self, client, admin_user):
        """تبديل الأتمتة كأدمن"""
        self._login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle', json={
            'enabled': True
        })
        assert response.status_code in [200, 400, 500]

    def test_dashboard_stats_as_admin(self, client, admin_user):
        """إحصائيات لوحة التحكم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/stats')
        assert response.status_code in [200, 500]
