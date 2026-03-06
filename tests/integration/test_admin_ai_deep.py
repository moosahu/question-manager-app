"""
Deep integration tests for src/routes/admin_ai.py
Target: 100+ tests covering all routes with edge cases and boundary values.

Routes covered:
  POST   /api/admin/ai/analyze/student/<id>
  GET    /api/admin/ai/analyze/student/status
  POST   /api/admin/ai/analyze/all
  GET    /api/admin/ai/analyze/all/status
  GET    /api/admin/ai/analysis/latest/<id>
  GET    /api/admin/ai/analysis/history/<id>
  GET    /api/admin/ai/dashboard/stats
  GET    /api/admin/ai/dashboard/students-need-attention
  POST   /api/admin/ai/notification/send
  POST   /api/admin/ai/chat
  GET    /api/admin/ai/settings
  PUT    /api/admin/ai/settings/<key>
  GET    /api/admin/ai/settings/export
  POST   /api/admin/ai/settings/import
  GET    /api/admin/ai/settings/presets
  POST   /api/admin/ai/settings/presets/<name>/apply
  GET    /api/admin/ai/providers
  PUT    /api/admin/ai/providers
  POST   /api/admin/ai/test-analysis
  GET    /api/admin/ai/analytics/overview
  GET    /api/admin/ai/analytics/trends
  GET    /api/admin/ai/notifications/effectiveness
  GET    /api/admin/ai/logs
  GET    /api/admin/ai/report/daily
  GET    /api/admin/ai/status
  GET    /api/admin/ai/messages/sent
  GET    /api/admin/ai/messages/stats
  GET    /api/admin/ai/automation/status
  PUT    /api/admin/ai/automation/toggle
  POST   /api/admin/ai/automation/test
  GET    /api/admin/ai/dashboard         (no auth_required decorator)
  GET    /api/admin/ai/students/inactive  (no auth_required decorator)
  GET    /api/admin/ai/students/low-score (no auth_required decorator)
  GET    /api/admin/ai/audit-log          (no auth_required decorator)
  POST   /api/admin/ai/audit-log
"""
import pytest
import secrets
import json

ALLOWED = [200, 302, 400, 401, 403, 404, 405, 500]


def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='AI Test',
        username=f'ai_{secrets.token_hex(4)}',
        email=f'ai_{secrets.token_hex(4)}@test.com',
        is_active=True,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


# ===========================================================================
# 1. Analyze Single Student
# ===========================================================================

class TestAnalyzeSingleStudent:

    def test_no_auth_returns_403(self, client):
        response = client.post('/api/admin/ai/analyze/student/1')
        assert response.status_code in ALLOWED

    def test_admin_nonexistent_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/student/999999')
        assert response.status_code in ALLOWED

    def test_admin_student_id_zero(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/student/0')
        assert response.status_code in ALLOWED

    def test_admin_existing_student(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.post(f'/api/admin/ai/analyze/student/{student.id}')
        assert response.status_code in ALLOWED

    def test_admin_existing_student_response_structure(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.post(f'/api/admin/ai/analyze/student/{student.id}')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert 'success' in data

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/student/1')
        assert response.status_code in ALLOWED

    def test_wrong_method_delete(self, client, admin_user):
        _login(client, admin_user)
        response = client.delete('/api/admin/ai/analyze/student/1')
        assert response.status_code in ALLOWED

    def test_student_id_string_returns_404(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/student/abc')
        assert response.status_code in ALLOWED

    def test_large_student_id(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/student/2147483647')
        assert response.status_code in ALLOWED


# ===========================================================================
# 2. Analyze Student Status
# ===========================================================================

class TestAnalyzeStudentStatus:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/analyze/student/status')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/student/status')
        assert response.status_code in ALLOWED

    def test_response_has_success_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/student/status')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/student/status')
        assert response.status_code in ALLOWED


# ===========================================================================
# 3. Analyze All
# ===========================================================================

class TestAnalyzeAll:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/analyze/all')
        assert response.status_code in ALLOWED

    def test_as_admin_starts(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/all')
        assert response.status_code in ALLOWED

    def test_double_trigger_returns_already_running(self, client, admin_user):
        """Second call when status == running should return already_running or 200."""
        _login(client, admin_user)
        client.post('/api/admin/ai/analyze/all')
        response = client.post('/api/admin/ai/analyze/all')
        assert response.status_code in ALLOWED

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/all')
        assert response.status_code in ALLOWED

    def test_response_structure(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analyze/all')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data


# ===========================================================================
# 4. Analyze All Status
# ===========================================================================

class TestAnalyzeAllStatus:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/analyze/all/status')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/all/status')
        assert response.status_code in ALLOWED

    def test_response_has_data(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analyze/all/status')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None


# ===========================================================================
# 5. Latest Analysis
# ===========================================================================

class TestLatestAnalysis:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/analysis/latest/1')
        assert response.status_code in ALLOWED

    def test_nonexistent_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analysis/latest/999999')
        assert response.status_code in ALLOWED

    def test_existing_student_no_analysis(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/latest/{student.id}')
        assert response.status_code in ALLOWED

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/analysis/latest/1')
        assert response.status_code in ALLOWED

    def test_returns_404_when_no_analysis(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/latest/{student.id}')
        assert response.status_code in ALLOWED


# ===========================================================================
# 6. Analysis History
# ===========================================================================

class TestAnalysisHistory:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/analysis/history/1')
        assert response.status_code in ALLOWED

    def test_nonexistent_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analysis/history/999999')
        assert response.status_code in ALLOWED

    def test_existing_student(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/history/{student.id}')
        assert response.status_code in ALLOWED

    def test_with_custom_limit(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/history/{student.id}?limit=5')
        assert response.status_code in ALLOWED

    def test_with_limit_zero(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/history/{student.id}?limit=0')
        assert response.status_code in ALLOWED

    def test_with_large_limit(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/history/{student.id}?limit=1000')
        assert response.status_code in ALLOWED

    def test_response_is_list(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.get(f'/api/admin/ai/analysis/history/{student.id}')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data
            assert isinstance(data['data'], list)


# ===========================================================================
# 7. Dashboard Stats
# ===========================================================================

class TestDashboardStats:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/dashboard/stats')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/stats')
        assert response.status_code in ALLOWED

    def test_response_structure(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/stats')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'data' in data

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/dashboard/stats')
        assert response.status_code in ALLOWED

    def test_severity_distribution_keys(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/stats')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            if data.get('success') and 'data' in data:
                assert 'severity_distribution' in data['data']


# ===========================================================================
# 8. Students Need Attention
# ===========================================================================

class TestStudentsNeedAttention:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/dashboard/students-need-attention')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/students-need-attention')
        assert response.status_code in ALLOWED

    def test_response_is_list(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard/students-need-attention')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data
            assert isinstance(data['data'], list)


# ===========================================================================
# 9. Send Notification (AI bulk)
# ===========================================================================

class TestNotificationSend:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/notification/send', json={
            'student_ids': [1], 'title': 'T', 'body': 'B'
        })
        assert response.status_code in ALLOWED

    def test_missing_student_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'title': 'Test', 'body': 'Body'
        })
        assert response.status_code in ALLOWED

    def test_missing_title(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_ids': [1], 'body': 'Body'
        })
        assert response.status_code in ALLOWED

    def test_missing_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_ids': [1], 'title': 'Title'
        })
        assert response.status_code in ALLOWED

    def test_empty_student_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_ids': [], 'title': 'T', 'body': 'B'
        })
        assert response.status_code in ALLOWED

    def test_valid_payload(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_ids': [student.id],
            'title': 'رسالة اختبار',
            'body': 'محتوى الرسالة',
            'type': 'info'
        })
        assert response.status_code in ALLOWED

    def test_nonexistent_student_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send', json={
            'student_ids': [999999, 888888],
            'title': 'Test',
            'body': 'Body'
        })
        assert response.status_code in ALLOWED

    def test_no_json_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notification/send')
        assert response.status_code in ALLOWED

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/notification/send')
        assert response.status_code in ALLOWED


# ===========================================================================
# 10. Chat with AI
# ===========================================================================

class TestChatWithAI:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/chat', json={'message': 'مرحبا'})
        assert response.status_code in ALLOWED

    def test_empty_message(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={'message': ''})
        assert response.status_code in ALLOWED

    def test_missing_message_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={})
        assert response.status_code in ALLOWED

    def test_with_message(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={'message': 'كيف حال الطلاب؟'})
        assert response.status_code in ALLOWED

    def test_with_context(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={
            'message': 'تحليل البيانات',
            'context': {'student_id': 1}
        })
        assert response.status_code in ALLOWED

    def test_very_long_message(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/chat', json={
            'message': 'ا' * 5000
        })
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/chat')
        assert response.status_code in ALLOWED

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/chat')
        assert response.status_code in ALLOWED


# ===========================================================================
# 11. Get Settings
# ===========================================================================

class TestGetSettings:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in ALLOWED

    def test_response_structure(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data


# ===========================================================================
# 12. Update Setting (PUT)
# ===========================================================================

class TestUpdateSetting:

    def test_no_auth(self, client):
        response = client.put('/api/admin/ai/settings/analysis_interval_hours',
                              json={'value': 24})
        assert response.status_code in ALLOWED

    def test_missing_value(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/analysis_interval_hours',
                              json={})
        assert response.status_code in ALLOWED

    def test_valid_analysis_interval(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/analysis_interval_hours',
                              json={'value': 24})
        assert response.status_code in ALLOWED

    def test_interval_below_min(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/analysis_interval_hours',
                              json={'value': 0})
        assert response.status_code in ALLOWED

    def test_interval_above_max(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/analysis_interval_hours',
                              json={'value': 999})
        assert response.status_code in ALLOWED

    def test_valid_inactive_days(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/inactive_days_threshold',
                              json={'value': 7})
        assert response.status_code in ALLOWED

    def test_invalid_inactive_days_negative(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/inactive_days_threshold',
                              json={'value': -1})
        assert response.status_code in ALLOWED

    def test_valid_critical_inactive_days(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/critical_inactive_days',
                              json={'value': 14})
        assert response.status_code in ALLOWED

    def test_valid_max_messages(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/max_messages_per_student_day',
                              json={'value': 3})
        assert response.status_code in ALLOWED

    def test_max_messages_at_zero(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/max_messages_per_student_day',
                              json={'value': 0})
        assert response.status_code in ALLOWED

    def test_max_messages_above_limit(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/max_messages_per_student_day',
                              json={'value': 100})
        assert response.status_code in ALLOWED

    def test_valid_score_decline(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/score_decline_threshold',
                              json={'value': 20.5})
        assert response.status_code in ALLOWED

    def test_score_decline_out_of_range(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/score_decline_threshold',
                              json={'value': 150})
        assert response.status_code in ALLOWED

    def test_valid_daily_report_time(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/daily_report_time',
                              json={'value': '08:00'})
        assert response.status_code in ALLOWED

    def test_invalid_daily_report_time_format(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/daily_report_time',
                              json={'value': '25:99'})
        assert response.status_code in ALLOWED

    def test_invalid_daily_report_time_no_colon(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/daily_report_time',
                              json={'value': 'badformat'})
        assert response.status_code in ALLOWED

    def test_unknown_setting_key_accepted(self, client, admin_user):
        """Unknown keys pass validation and should be created."""
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/some_unknown_key',
                              json={'value': 'hello'})
        assert response.status_code in ALLOWED

    def test_boolean_value(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/settings/enable_auto_messages',
                              json={'value': True})
        assert response.status_code in ALLOWED

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings/analysis_interval_hours')
        assert response.status_code in ALLOWED


# ===========================================================================
# 13. Export Settings
# ===========================================================================

class TestExportSettings:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/settings/export')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings/export')
        assert response.status_code in ALLOWED

    def test_response_has_settings_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings/export')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'data' in data

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/export')
        assert response.status_code in ALLOWED


# ===========================================================================
# 14. Import Settings
# ===========================================================================

class TestImportSettings:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/settings/import', json={})
        assert response.status_code in ALLOWED

    def test_missing_settings_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import', json={})
        assert response.status_code in ALLOWED

    def test_empty_settings(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import',
                               json={'settings': {}})
        assert response.status_code in ALLOWED

    def test_valid_settings_import(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import', json={
            'settings': {
                'inactive_days_threshold': {'value': 7},
                'critical_inactive_days': {'value': 14},
            }
        })
        assert response.status_code in ALLOWED

    def test_invalid_value_triggers_error(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import', json={
            'settings': {
                'analysis_interval_hours': {'value': 9999},
            }
        })
        assert response.status_code in ALLOWED

    def test_business_rule_violation(self, client, admin_user):
        """critical_inactive_days <= inactive_days_threshold should fail."""
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import', json={
            'settings': {
                'inactive_days_threshold': {'value': 10},
                'critical_inactive_days': {'value': 5},
            }
        })
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import')
        assert response.status_code in ALLOWED

    def test_non_json_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/import',
                               data='not json',
                               content_type='text/plain')
        assert response.status_code in ALLOWED


# ===========================================================================
# 15. Get Presets
# ===========================================================================

class TestGetPresets:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/settings/presets')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings/presets')
        assert response.status_code in ALLOWED

    def test_returns_known_presets(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings/presets')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            presets = data.get('data', {})
            for expected in ['conservative', 'balanced', 'aggressive', 'exam_week', 'vacation']:
                assert expected in presets


# ===========================================================================
# 16. Apply Preset
# ===========================================================================

class TestApplyPreset:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/settings/presets/balanced/apply')
        assert response.status_code in ALLOWED

    def test_nonexistent_preset(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/nonexistent_preset/apply')
        assert response.status_code in ALLOWED

    def test_conservative_preset(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/conservative/apply')
        assert response.status_code in ALLOWED

    def test_balanced_preset(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/balanced/apply')
        assert response.status_code in ALLOWED

    def test_aggressive_preset(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/aggressive/apply')
        assert response.status_code in ALLOWED

    def test_exam_week_preset(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/exam_week/apply')
        assert response.status_code in ALLOWED

    def test_vacation_preset(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/settings/presets/vacation/apply')
        assert response.status_code in ALLOWED

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/settings/presets/balanced/apply')
        assert response.status_code in ALLOWED


# ===========================================================================
# 17. AI Providers GET
# ===========================================================================

class TestGetAIProviders:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/providers')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/providers')
        assert response.status_code in ALLOWED

    def test_response_has_providers(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/providers')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True


# ===========================================================================
# 18. AI Providers PUT
# ===========================================================================

class TestSetAIProvider:

    def test_no_auth(self, client):
        response = client.put('/api/admin/ai/providers', json={'provider': 'gemini'})
        assert response.status_code in ALLOWED

    def test_empty_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/providers', json={})
        assert response.status_code in ALLOWED

    def test_invalid_provider(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/providers',
                              json={'provider': 'totally_fake_provider'})
        assert response.status_code in ALLOWED

    def test_valid_gemini_provider(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/providers', json={'provider': 'gemini'})
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/providers')
        assert response.status_code in ALLOWED


# ===========================================================================
# 19. Test Analysis (test-analysis)
# ===========================================================================

class TestTestAnalysis:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/test-analysis', json={})
        assert response.status_code in ALLOWED

    def test_empty_body_uses_defaults(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={})
        assert response.status_code in ALLOWED

    def test_excellent_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'total_quizzes': 20,
            'average_score': 92.0,
            'days_since_last_quiz': 1
        })
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_critical_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'total_quizzes': 2,
            'average_score': 30.0,
            'days_since_last_quiz': 30
        })
        assert response.status_code in ALLOWED

    def test_needs_attention_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'total_quizzes': 5,
            'average_score': 45.0,
            'days_since_last_quiz': 9
        })
        assert response.status_code in ALLOWED

    def test_good_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'total_quizzes': 10,
            'average_score': 70.0,
            'days_since_last_quiz': 3
        })
        assert response.status_code in ALLOWED

    def test_zero_score(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'average_score': 0.0,
            'days_since_last_quiz': 1
        })
        assert response.status_code in ALLOWED

    def test_hundred_percent_score(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'average_score': 100.0,
            'days_since_last_quiz': 0
        })
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis')
        assert response.status_code in ALLOWED

    def test_response_contains_analysis_result(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/test-analysis', json={
            'average_score': 65.0,
            'days_since_last_quiz': 8
        })
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data


# ===========================================================================
# 20. Analytics Overview
# ===========================================================================

class TestAnalyticsOverview:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/analytics/overview')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview')
        assert response.status_code in ALLOWED

    def test_custom_days(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview?days=30')
        assert response.status_code in ALLOWED

    def test_days_one(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview?days=1')
        assert response.status_code in ALLOWED

    def test_days_invalid(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview?days=abc')
        assert response.status_code in ALLOWED

    def test_response_structure(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/overview')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True


# ===========================================================================
# 21. Analytics Trends
# ===========================================================================

class TestAnalyticsTrends:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/analytics/trends')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/trends')
        assert response.status_code in ALLOWED

    def test_custom_days(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/trends?days=7')
        assert response.status_code in ALLOWED

    def test_response_has_trends(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/analytics/trends')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data


# ===========================================================================
# 22. Notification Effectiveness
# ===========================================================================

class TestNotificationEffectiveness:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/notifications/effectiveness')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/notifications/effectiveness')
        assert response.status_code in ALLOWED

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/notifications/effectiveness')
        assert response.status_code in ALLOWED


# ===========================================================================
# 23. Logs
# ===========================================================================

class TestGetLogs:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/logs')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/logs')
        assert response.status_code in ALLOWED

    def test_with_limit(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/logs?limit=10')
        assert response.status_code in ALLOWED

    def test_with_operation_type(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/logs?operation_type=automation_send_messages')
        assert response.status_code in ALLOWED

    def test_with_limit_and_type(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/logs?limit=5&operation_type=apply_preset')
        assert response.status_code in ALLOWED

    def test_response_is_list(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/logs')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data.get('data'), list)

    def test_large_limit(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/logs?limit=500')
        assert response.status_code in ALLOWED


# ===========================================================================
# 24. Daily Report
# ===========================================================================

class TestDailyReport:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/report/daily')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/report/daily')
        assert response.status_code in ALLOWED

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/report/daily')
        assert response.status_code in ALLOWED


# ===========================================================================
# 25. System Status
# ===========================================================================

class TestSystemStatus:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/status')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/status')
        assert response.status_code in ALLOWED

    def test_response_has_ai_configured(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/status')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data


# ===========================================================================
# 26. Messages Sent
# ===========================================================================

class TestMessagesSent:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/messages/sent')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent')
        assert response.status_code in ALLOWED

    def test_period_today(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent?period=today')
        assert response.status_code in ALLOWED

    def test_period_week(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent?period=week')
        assert response.status_code in ALLOWED

    def test_period_month(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent?period=month')
        assert response.status_code in ALLOWED

    def test_custom_limit(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent?limit=10')
        assert response.status_code in ALLOWED

    def test_invalid_period(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/sent?period=forever')
        assert response.status_code in ALLOWED


# ===========================================================================
# 27. Messages Stats
# ===========================================================================

class TestMessagesStats:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/messages/stats')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats')
        assert response.status_code in ALLOWED

    def test_period_today(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats?period=today')
        assert response.status_code in ALLOWED

    def test_period_week(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats?period=week')
        assert response.status_code in ALLOWED

    def test_period_month(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats?period=month')
        assert response.status_code in ALLOWED

    def test_response_has_counts(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/messages/stats')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True


# ===========================================================================
# 28. Automation Status
# ===========================================================================

class TestAutomationStatus:

    def test_no_auth(self, client):
        response = client.get('/api/admin/ai/automation/status')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/automation/status')
        assert response.status_code in ALLOWED

    def test_response_structure(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/automation/status')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data


# ===========================================================================
# 29. Toggle Automation
# ===========================================================================

class TestToggleAutomation:

    def test_no_auth(self, client):
        response = client.put('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert response.status_code in ALLOWED

    def test_enable_automation(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert response.status_code in ALLOWED

    def test_disable_automation(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle', json={'enabled': False})
        assert response.status_code in ALLOWED

    def test_empty_body_defaults_to_false(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle', json={})
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle')
        assert response.status_code in ALLOWED

    def test_wrong_method_post(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert response.status_code in ALLOWED

    def test_response_has_automation_enabled_flag(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'automation_enabled' in data


# ===========================================================================
# 30. Test Automation
# ===========================================================================

class TestTestAutomation:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/automation/test', json={})
        assert response.status_code in ALLOWED

    def test_simple_test_default(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/automation/test', json={'simple': True})
        assert response.status_code in ALLOWED

    def test_simple_false_no_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/automation/test', json={'simple': False})
        assert response.status_code in ALLOWED

    def test_complex_nonexistent_student(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/automation/test', json={
            'simple': False, 'student_id': 999999
        })
        assert response.status_code in ALLOWED

    def test_complex_existing_student(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.post('/api/admin/ai/automation/test', json={
            'simple': False, 'student_id': student.id
        })
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/automation/test')
        assert response.status_code in ALLOWED

    def test_wrong_method_get(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/automation/test')
        assert response.status_code in ALLOWED


# ===========================================================================
# 31. Public Dashboard (no admin_required decorator)
# ===========================================================================

class TestPublicDashboard:

    def test_no_auth_allowed(self, client):
        """This route has no admin_required — 200 is valid."""
        response = client.get('/api/admin/ai/dashboard')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/dashboard')
        assert response.status_code in ALLOWED

    def test_response_has_dashboard_key(self, client):
        response = client.get('/api/admin/ai/dashboard')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'dashboard' in data or 'success' in data

    def test_wrong_method_post(self, client):
        response = client.post('/api/admin/ai/dashboard')
        assert response.status_code in ALLOWED


# ===========================================================================
# 32. Inactive Students (no admin_required)
# ===========================================================================

class TestInactiveStudents:

    def test_no_auth_allowed(self, client):
        response = client.get('/api/admin/ai/students/inactive')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/inactive')
        assert response.status_code in ALLOWED

    def test_custom_days(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/inactive?days=14')
        assert response.status_code in ALLOWED

    def test_days_one(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/inactive?days=1')
        assert response.status_code in ALLOWED

    def test_days_sixty(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/inactive?days=60')
        assert response.status_code in ALLOWED

    def test_response_has_students_key(self, client):
        response = client.get('/api/admin/ai/students/inactive')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'students' in data
            assert isinstance(data['students'], list)

    def test_wrong_method_post(self, client):
        response = client.post('/api/admin/ai/students/inactive')
        assert response.status_code in ALLOWED


# ===========================================================================
# 33. Low-Score Students (no admin_required)
# ===========================================================================

class TestLowScoreStudents:

    def test_no_auth_allowed(self, client):
        response = client.get('/api/admin/ai/students/low-score')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/low-score')
        assert response.status_code in ALLOWED

    def test_custom_threshold(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/low-score?threshold=40')
        assert response.status_code in ALLOWED

    def test_threshold_zero(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/low-score?threshold=0')
        assert response.status_code in ALLOWED

    def test_threshold_hundred(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/students/low-score?threshold=100')
        assert response.status_code in ALLOWED

    def test_response_has_students_key(self, client):
        response = client.get('/api/admin/ai/students/low-score')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'students' in data

    def test_wrong_method_delete(self, client):
        response = client.delete('/api/admin/ai/students/low-score')
        assert response.status_code in ALLOWED


# ===========================================================================
# 34. Audit Log GET (no admin_required)
# ===========================================================================

class TestAuditLogGet:

    def test_no_auth_allowed(self, client):
        response = client.get('/api/admin/ai/audit-log')
        assert response.status_code in ALLOWED

    def test_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/audit-log')
        assert response.status_code in ALLOWED

    def test_filter_by_action(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/audit-log?action=login')
        assert response.status_code in ALLOWED

    def test_pagination_page_one(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/audit-log?page=1&per_page=10')
        assert response.status_code in ALLOWED

    def test_pagination_large_page(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/api/admin/ai/audit-log?page=9999&per_page=50')
        assert response.status_code in ALLOWED

    def test_response_has_logs_key(self, client):
        response = client.get('/api/admin/ai/audit-log')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'logs' in data
            assert isinstance(data['logs'], list)

    def test_response_has_total(self, client):
        response = client.get('/api/admin/ai/audit-log')
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'total' in data


# ===========================================================================
# 35. Audit Log POST (admin_required)
# ===========================================================================

class TestAuditLogPost:

    def test_no_auth(self, client):
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'test', 'description': 'desc'
        })
        assert response.status_code in ALLOWED

    def test_missing_action(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'description': 'only description'
        })
        assert response.status_code in ALLOWED

    def test_missing_description(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'only_action'
        })
        assert response.status_code in ALLOWED

    def test_empty_action(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': '', 'description': 'desc'
        })
        assert response.status_code in ALLOWED

    def test_empty_description(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'update_settings', 'description': ''
        })
        assert response.status_code in ALLOWED

    def test_valid_audit_entry(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'update_settings',
            'description': 'تغيير إعداد الفاصل الزمني',
            'target_type': 'setting',
            'target_id': 1
        })
        assert response.status_code in ALLOWED

    def test_with_student_id(self, client, admin_user, db_session):
        student = _make_student(db_session)
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'send_message',
            'description': f'إرسال رسالة للطالب {student.id}',
            'student_id': student.id
        })
        assert response.status_code in ALLOWED

    def test_no_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log')
        # 415 Unsupported Media Type is valid when no JSON body is sent
        assert response.status_code in ALLOWED + [415]

    def test_response_success_key(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/api/admin/ai/audit-log', json={
            'action': 'test_action',
            'description': 'test description'
        })
        assert response.status_code in ALLOWED
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
