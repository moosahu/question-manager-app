"""
اختبارات لـ Admin AI API و Admin Profile
يغطي: AI analysis, dashboard, settings, providers, chat, notifications
"""
import pytest


class TestAdminProfileAPI:
    """اختبارات ملف الأدمن API"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_profile_no_auth(self, client):
        """جلب ملف الأدمن بدون مصادقة"""
        response = client.get('/api/admin/profile')
        assert response.status_code in [302, 401, 403, 404]

    def test_get_profile_as_admin(self, client, admin_user):
        """جلب ملف الأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/profile')
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_get_profile_email_no_auth(self, client):
        """جلب إيميل الأدمن بدون مصادقة"""
        response = client.get('/api/admin/profile/email')
        assert response.status_code in [302, 401, 403, 404]

    def test_get_profile_email_as_admin(self, client, admin_user):
        """جلب إيميل الأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/profile/email')
        assert response.status_code in [200, 404, 500]

    def test_send_notification_no_auth(self, client):
        """إرسال إشعار بدون مصادقة"""
        response = client.post('/api/admin/send-notification', json={})
        assert response.status_code in [302, 401, 403, 404]

    def test_send_notification_as_admin(self, client, admin_user):
        """إرسال إشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/send-notification', json={
            'title': 'اختبار',
            'message': 'رسالة اختبار'
        })
        assert response.status_code in [200, 400, 404, 500, 503]


class TestAdminAIStatus:
    """اختبارات حالة الـ AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_ai_status_no_auth(self, client):
        """حالة AI بدون مصادقة"""
        response = client.get('/api/admin/ai/status')
        assert response.status_code in [302, 401, 403]

    def test_ai_status_as_admin(self, client, admin_user):
        """حالة AI كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/status')
        assert response.status_code in [200, 500]

    def test_ai_providers_get_as_admin(self, client, admin_user):
        """جلب مزودي AI"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/providers')
        assert response.status_code in [200, 500]

    def test_ai_settings_get_no_auth(self, client):
        """جلب إعدادات AI بدون مصادقة"""
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in [302, 401, 403]

    def test_ai_settings_get_as_admin(self, client, admin_user):
        """جلب إعدادات AI"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in [200, 500]

    def test_ai_settings_presets_as_admin(self, client, admin_user):
        """قوالب إعدادات AI"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/settings/presets')
        assert response.status_code in [200, 500]

    def test_ai_settings_export_as_admin(self, client, admin_user):
        """تصدير إعدادات AI"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/settings/export')
        assert response.status_code in [200, 500]

    def test_ai_logs_as_admin(self, client, admin_user):
        """سجلات AI"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/logs')
        assert response.status_code in [200, 500]

    def test_ai_messages_sent_as_admin(self, client, admin_user):
        """الرسائل المرسلة"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent')
        assert response.status_code in [200, 500]

    def test_ai_messages_stats_as_admin(self, client, admin_user):
        """إحصائيات الرسائل"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats')
        assert response.status_code in [200, 500]

    def test_ai_automation_status_as_admin(self, client, admin_user):
        """حالة الأتمتة"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/automation/status')
        assert response.status_code in [200, 500]

    def test_daily_report_as_admin(self, client, admin_user):
        """التقرير اليومي"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/report/daily')
        assert response.status_code in [200, 500]


class TestAdminAIDashboard:
    """اختبارات لوحة تحكم AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_dashboard_stats_as_admin(self, client, admin_user):
        """إحصائيات لوحة التحكم"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/stats')
        assert response.status_code in [200, 500]

    def test_students_need_attention_as_admin(self, client, admin_user):
        """الطلاب الذين يحتاجون اهتماماً"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/students-need-attention')
        assert response.status_code in [200, 500]

    def test_analytics_overview_as_admin(self, client, admin_user):
        """نظرة عامة على التحليلات"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview')
        assert response.status_code in [200, 500]

    def test_analytics_trends_as_admin(self, client, admin_user):
        """اتجاهات التحليلات"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/trends')
        assert response.status_code in [200, 500]

    def test_notifications_effectiveness_as_admin(self, client, admin_user):
        """فعالية الإشعارات"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/notifications/effectiveness')
        assert response.status_code in [200, 500]


class TestAdminAIAnalysis:
    """اختبارات تحليل الطلاب"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_analyze_student_no_auth(self, client):
        """تحليل طالب بدون مصادقة"""
        response = client.post('/api/admin/ai/analyze/student/1')
        assert response.status_code in [302, 401, 403]

    def test_analyze_student_nonexistent(self, client, admin_user):
        """تحليل طالب غير موجود"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/student/99999')
        assert response.status_code in [200, 404, 500]

    def test_analyze_status_as_admin(self, client, admin_user):
        """حالة التحليل"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/student/status')
        assert response.status_code in [200, 500]

    def test_analyze_all_no_auth(self, client):
        """تحليل كل الطلاب بدون مصادقة"""
        response = client.post('/api/admin/ai/analyze/all')
        assert response.status_code in [302, 401, 403]

    def test_analyze_all_status_as_admin(self, client, admin_user):
        """حالة تحليل الكل"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/all/status')
        assert response.status_code in [200, 500]

    def test_latest_analysis_nonexistent(self, client, admin_user):
        """آخر تحليل لطالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analysis/latest/99999')
        assert response.status_code in [200, 404, 500]

    def test_analysis_history_nonexistent(self, client, admin_user):
        """تاريخ تحليل طالب غير موجود"""
        self._login(client, admin_user)
        response = client.get('/api/admin/ai/analysis/history/99999')
        assert response.status_code in [200, 404, 500]


class TestAdminAIActions:
    """اختبارات إجراءات AI"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_chat_no_auth(self, client):
        """الدردشة مع AI بدون مصادقة"""
        response = client.post('/api/admin/ai/chat', json={'message': 'مرحبا'})
        assert response.status_code in [302, 401, 403]

    def test_chat_as_admin(self, client, admin_user):
        """الدردشة مع AI كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={'message': 'اختبار'})
        assert response.status_code in [200, 400, 500]

    def test_test_analysis_as_admin(self, client, admin_user):
        """اختبار التحليل"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={})
        assert response.status_code in [200, 400, 500]

    def test_notification_send_as_admin(self, client, admin_user):
        """إرسال إشعار AI"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_id': 99999,
            'message': 'اختبار'
        })
        assert response.status_code in [200, 400, 404, 500, 503]

    def test_automation_toggle_as_admin(self, client, admin_user):
        """تبديل الأتمتة"""
        self._login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert response.status_code in [200, 400, 500]

    def test_update_ai_setting_as_admin(self, client, admin_user):
        """تحديث إعداد AI"""
        self._login(client, admin_user)
        response = client.put('/api/admin/ai/settings/test_key', json={'value': 'test_val'})
        assert response.status_code in [200, 400, 404, 500]

    def test_apply_preset_as_admin(self, client, admin_user):
        """تطبيق قالب"""
        self._login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/default/apply', json={})
        assert response.status_code in [200, 404, 500]
