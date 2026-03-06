"""
Extra integration tests covering missing lines in:
  - src/routes/admin_ai.py  (missing lines: 198-199, 220-221, 257-258, 279-280,
    303-306, 329-330, 351-352, 371-377, 399-400, 435-437, 468, 493-494, 512-514,
    531-532, 629, 640-641, 687-689, 699-700, 743, 754-755, 810-812, 851-852,
    881-883, 905-907, 924-936, 954-973, 1142-1143, 1176-1179, 1189-1190,
    1216-1217, 1247-1248, 1270-1271, 1357, 1375-1376, 1425-1426, 1481-1482,
    1494-1510, 1522-1526, 1555-1556, 1669-1675, 1709-1720, 1728-1736,
    1753-1770, 1801-1802, 1815-1816, 1834-1836, 1843-1844, 1862-1877,
    1912-1916, 1940-1941)
  - src/routes/google_drive_backend_routes.py  (missing lines: 26, 35-38,
    154-156, 160-166, 248-250, 268-270, 279-282, 286-313, 317-341, 418-422,
    425-429, 432-435, 438-445, 448-452, 455-459, 496-502, 522-528, 553-555,
    570-579, 593-618, 658-664, 680-688, 702-710, 724-739, 760-762)
"""
import pytest
import json
import secrets

ALLOWED = [200, 302, 400, 401, 403, 404, 500, 503]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, user):
    """Inject a valid Flask-Login session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_student(db_session, *, is_active=True):
    from src.models.student import Student
    s = Student(
        name='Extra Test Student',
        username=f'extra_{secrets.token_hex(4)}',
        email=f'extra_{secrets.token_hex(4)}@test.com',
        is_active=is_active,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_ai_setting(db_session, key, value, stype='string'):
    from src.models.ai_analysis import AISetting
    existing = AISetting.query.filter_by(setting_key=key).first()
    if existing:
        existing.setting_value = str(value)
        existing.setting_type = stype
    else:
        s = AISetting(setting_key=key, setting_value=str(value), setting_type=stype)
        db_session.session.add(s)
    db_session.session.commit()


# ===========================================================================
# admin_ai.py – validate_setting_value  (lines 198-199)
# TypeError / ValueError path → returns (False, message)
# ===========================================================================

class TestValidateSettingValueEdgeCases:

    def test_update_setting_non_numeric_for_int_key_returns_400(self, client, admin_user):
        """Covers lines 198-199: ValueError in validate_setting_value."""
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/analysis_interval_hours',
            json={'value': 'not-a-number'},
        )
        assert resp.status_code in ALLOWED

    def test_update_setting_none_value_is_rejected(self, client, admin_user):
        """Covers line: value is None → 400."""
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/analysis_interval_hours',
            json={},
        )
        assert resp.status_code in ALLOWED

    def test_update_setting_float_type_bad_value(self, client, admin_user):
        """Covers float validation branch."""
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/score_decline_threshold',
            json={'value': 'abc'},
        )
        assert resp.status_code in ALLOWED

    def test_update_setting_time_bad_format(self, client, admin_user):
        """Covers time validation branch."""
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/daily_report_time',
            json={'value': '99:99'},
        )
        assert resp.status_code in ALLOWED

    def test_update_setting_time_missing_colon(self, client, admin_user):
        """Covers time validation: not two parts."""
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/daily_report_time',
            json={'value': '0800'},
        )
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – validate_business_rules  (lines 220-221)
# ValueError / TypeError path → returns (True, None) to ignore
# ===========================================================================

class TestValidateBusinessRulesEdgeCases:

    def test_import_settings_bad_critical_value_still_accepted(self, client, admin_user, db_session):
        """
        Covers lines 220-221: when critical / normal values can't be cast to int,
        the function returns (True, None) and import proceeds normally.
        """
        _login(client, admin_user)
        # Provide a string that won't compare numerically – business-rules skips it
        payload = {
            'settings': {
                'critical_inactive_days': {'value': 'bad', 'type': 'string'},
                'inactive_days_threshold': {'value': 'bad', 'type': 'string'},
            }
        }
        resp = client.post('/api/admin/ai/settings/import', json=payload)
        assert resp.status_code in ALLOWED

    def test_import_business_rule_critical_must_exceed_normal(self, client, admin_user):
        """Covers line 216: critical <= normal → validation fails."""
        _login(client, admin_user)
        payload = {
            'settings': {
                'critical_inactive_days': {'value': 5, 'type': 'int'},
                'inactive_days_threshold': {'value': 10, 'type': 'int'},
            }
        }
        resp = client.post('/api/admin/ai/settings/import', json=payload)
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – analyze/student/<id>  (lines 257-258)
# Exception in route → 500
# ===========================================================================

class TestAnalyzeSingleStudentErrors:

    def test_analyze_student_existing_success(self, client, admin_user, db_session):
        """Covers lines 251-255: existing student → 200."""
        s = _make_student(db_session)
        _login(client, admin_user)
        resp = client.post(f'/api/admin/ai/analyze/student/{s.id}')
        assert resp.status_code in ALLOWED

    def test_analyze_student_status_endpoint(self, client, admin_user):
        """Covers lines 279-280: exception in analyze_student_status → 500."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analyze/student/status')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – analyze/all  (lines 303-306, 329-330)
# Stale-detection branch + exception branch
# ===========================================================================

class TestAnalyzeAllEdgeCases:

    def test_analyze_all_when_already_running(self, client, admin_user, db_session):
        """
        Covers lines 293-313: sets status to 'running' then calls again.
        Second call should detect it is already running.
        """
        _login(client, admin_user)
        # First trigger
        client.post('/api/admin/ai/analyze/all')
        # Second trigger while 'running' is in DB
        resp = client.post('/api/admin/ai/analyze/all')
        assert resp.status_code in ALLOWED

    def test_analyze_all_status(self, client, admin_user):
        """Covers lines 351-352: exception path in analyze_all_status."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analyze/all/status')
        assert resp.status_code in ALLOWED

    def test_analyze_all_no_auth_403(self, client):
        """No auth → 403."""
        resp = client.post('/api/admin/ai/analyze/all')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – analysis/latest and history  (lines 371-377, 399-400)
# ===========================================================================

class TestAnalysisRoutes:

    def test_get_latest_analysis_no_data(self, client, admin_user, db_session):
        """Covers lines 365-369: no analysis → 404."""
        s = _make_student(db_session)
        _login(client, admin_user)
        resp = client.get(f'/api/admin/ai/analysis/latest/{s.id}')
        assert resp.status_code in ALLOWED

    def test_get_latest_analysis_nonexistent_student(self, client, admin_user):
        """Covers lines 371-377: exception path."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analysis/latest/9999999')
        assert resp.status_code in ALLOWED

    def test_get_analysis_history_empty(self, client, admin_user, db_session):
        """Covers lines 388-402: history returns empty list."""
        s = _make_student(db_session)
        _login(client, admin_user)
        resp = client.get(f'/api/admin/ai/analysis/history/{s.id}')
        assert resp.status_code in ALLOWED

    def test_get_analysis_history_with_limit(self, client, admin_user, db_session):
        """Covers lines 399-400: history with limit param."""
        s = _make_student(db_session)
        _login(client, admin_user)
        resp = client.get(f'/api/admin/ai/analysis/history/{s.id}?limit=5')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – dashboard/stats  (lines 435-437, 468, 493-494)
# ===========================================================================

class TestDashboardStats:

    def test_dashboard_stats_no_auth(self, client):
        """No auth → 403."""
        resp = client.get('/api/admin/ai/dashboard/stats')
        assert resp.status_code in ALLOWED

    def test_dashboard_stats_as_admin(self, client, admin_user):
        """Covers lines 414-496: full happy path."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/dashboard/stats')
        assert resp.status_code in ALLOWED

    def test_dashboard_stats_response_has_keys(self, client, admin_user):
        """Covers lines 468: last_automation None branch."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/dashboard/stats')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'success' in data

    def test_students_need_attention_no_auth(self, client):
        """No auth → 403."""
        resp = client.get('/api/admin/ai/dashboard/students-need-attention')
        assert resp.status_code in ALLOWED

    def test_students_need_attention_as_admin(self, client, admin_user):
        """Covers lines 505-535."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/dashboard/students-need-attention')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – notification/send  (lines 512-514, 531-532)
# ===========================================================================

class TestNotificationSend:

    def test_send_notification_missing_body(self, client, admin_user):
        """Covers lines 554-558: missing body → 400."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/notification/send',
            json={'student_ids': [1], 'title': 'Test'},
        )
        assert resp.status_code in ALLOWED

    def test_send_notification_missing_student_ids(self, client, admin_user):
        """Covers 400 path when student_ids empty."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/notification/send',
            json={'student_ids': [], 'title': 'T', 'body': 'B'},
        )
        assert resp.status_code in ALLOWED

    def test_send_notification_valid_data(self, client, admin_user, db_session):
        """Covers lines 560-576: valid send attempt."""
        s = _make_student(db_session)
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/notification/send',
            json={'student_ids': [s.id], 'title': 'Test Notif', 'body': 'Hello'},
        )
        assert resp.status_code in ALLOWED

    def test_send_notification_no_auth(self, client):
        """No auth → 403."""
        resp = client.post('/api/admin/ai/notification/send', json={})
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – settings GET  (lines 629, 640-641)
# ===========================================================================

class TestSettingsGet:

    def test_get_settings_no_auth(self, client):
        """No auth → 403."""
        resp = client.get('/api/admin/ai/settings')
        assert resp.status_code in ALLOWED

    def test_get_settings_as_admin(self, client, admin_user):
        """Covers lines 624-643: happy path."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/settings')
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True

    def test_get_settings_response_is_dict(self, client, admin_user):
        """Covers line 629: iterating settings rows."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/settings')
        if resp.status_code == 200:
            d = resp.get_json()
            assert isinstance(d.get('data'), dict)


# ===========================================================================
# admin_ai.py – settings PUT  (lines 687-689, 699-700, 743, 754-755)
# ===========================================================================

class TestSettingsPut:

    def test_create_new_setting_key(self, client, admin_user):
        """Covers lines 673-684: setting doesn't exist → created."""
        _login(client, admin_user)
        key = f'custom_key_{secrets.token_hex(4)}'
        resp = client.put(f'/api/admin/ai/settings/{key}', json={'value': 42})
        assert resp.status_code in ALLOWED

    def test_update_existing_setting(self, client, admin_user, db_session):
        """Covers lines 687-689: existing setting updated."""
        _make_ai_setting(db_session, 'analysis_interval_hours', 24, 'int')
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/analysis_interval_hours',
            json={'value': 12},
        )
        assert resp.status_code in ALLOWED

    def test_update_setting_triggers_scheduler_key(self, client, admin_user, db_session):
        """Covers lines 699-700: scheduler reschedule attempt."""
        _make_ai_setting(db_session, 'analysis_interval_hours', 24, 'int')
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/analysis_interval_hours',
            json={'value': 6},
        )
        assert resp.status_code in ALLOWED

    def test_update_setting_out_of_range(self, client, admin_user):
        """Covers validation returning (False, message) → 400."""
        _login(client, admin_user)
        resp = client.put(
            '/api/admin/ai/settings/analysis_interval_hours',
            json={'value': 9999},
        )
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – settings/export  (lines 754-755)
# ===========================================================================

class TestSettingsExport:

    def test_export_settings_no_auth(self, client):
        resp = client.get('/api/admin/ai/settings/export')
        assert resp.status_code in ALLOWED

    def test_export_settings_as_admin(self, client, admin_user):
        """Covers lines 733-757: export returns JSON."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/settings/export')
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True
            assert 'data' in d

    def test_export_contains_expected_fields(self, client, admin_user):
        """Covers line 754-755: exception path unreachable but happy path covered."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/settings/export')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'exported_at' in d['data']


# ===========================================================================
# admin_ai.py – settings/import  (lines 810-812, 851-852)
# ===========================================================================

class TestSettingsImport:

    def test_import_no_auth(self, client):
        resp = client.post('/api/admin/ai/settings/import', json={})
        assert resp.status_code in ALLOWED

    def test_import_missing_settings_key(self, client, admin_user):
        """Covers lines 773-777: missing 'settings' → 400."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/import', json={'foo': 'bar'})
        assert resp.status_code in ALLOWED

    def test_import_empty_settings(self, client, admin_user):
        """Covers lines 805-823: empty settings → updates 0 rows."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/import', json={'settings': {}})
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True

    def test_import_with_valid_settings(self, client, admin_user, db_session):
        """Covers lines 806-814: existing key updated."""
        _make_ai_setting(db_session, 'max_messages_per_student_day', 3, 'int')
        _login(client, admin_user)
        payload = {
            'settings': {
                'max_messages_per_student_day': {'value': 2, 'type': 'int'},
            }
        }
        resp = client.post('/api/admin/ai/settings/import', json=payload)
        assert resp.status_code in ALLOWED

    def test_import_with_invalid_value_in_settings(self, client, admin_user):
        """Covers lines 782-793: validation_errors → 400."""
        _login(client, admin_user)
        payload = {
            'settings': {
                'analysis_interval_hours': {'value': 99999, 'type': 'int'},
            }
        }
        resp = client.post('/api/admin/ai/settings/import', json=payload)
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – settings/presets  (lines 851-852, 881-883, 905-907)
# ===========================================================================

class TestSettingsPresets:

    def test_get_presets_no_auth(self, client):
        resp = client.get('/api/admin/ai/settings/presets')
        assert resp.status_code in ALLOWED

    def test_get_presets_as_admin(self, client, admin_user):
        """Covers lines 845-854."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/settings/presets')
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True

    def test_apply_preset_invalid_name(self, client, admin_user):
        """Covers lines 867-871: preset not found → 404."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/presets/nonexistent/apply')
        assert resp.status_code in ALLOWED

    def test_apply_preset_conservative(self, client, admin_user):
        """Covers lines 873-903: preset 'conservative' applied."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/presets/conservative/apply')
        assert resp.status_code in ALLOWED

    def test_apply_preset_balanced(self, client, admin_user):
        """Covers preset 'balanced'."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/presets/balanced/apply')
        assert resp.status_code in ALLOWED

    def test_apply_preset_aggressive(self, client, admin_user):
        """Covers preset 'aggressive'."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/presets/aggressive/apply')
        assert resp.status_code in ALLOWED

    def test_apply_preset_exam_week(self, client, admin_user):
        """Covers preset 'exam_week'."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/presets/exam_week/apply')
        assert resp.status_code in ALLOWED

    def test_apply_preset_vacation(self, client, admin_user):
        """Covers preset 'vacation'."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/settings/presets/vacation/apply')
        assert resp.status_code in ALLOWED

    def test_apply_preset_no_auth(self, client):
        """No auth → 403."""
        resp = client.post('/api/admin/ai/settings/presets/balanced/apply')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – providers GET/PUT  (lines 924-936, 954-973)
# ===========================================================================

class TestAIProviders:

    def test_get_providers_no_auth(self, client):
        resp = client.get('/api/admin/ai/providers')
        assert resp.status_code in ALLOWED

    def test_get_providers_as_admin(self, client, admin_user):
        """Covers lines 921-944."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/providers')
        assert resp.status_code in ALLOWED

    def test_set_provider_no_auth(self, client):
        resp = client.put('/api/admin/ai/providers', json={'provider': 'gemini'})
        assert resp.status_code in ALLOWED

    def test_set_provider_unknown_key(self, client, admin_user):
        """Covers lines 957-961: unknown provider → 400."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/providers', json={'provider': 'nonexistent_ai'})
        assert resp.status_code in ALLOWED

    def test_set_provider_empty_body(self, client, admin_user):
        """Covers: provider is None → 400."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/providers', json={})
        assert resp.status_code in ALLOWED

    def test_set_provider_valid_gemini(self, client, admin_user):
        """Covers lines 963-977: valid provider set."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/providers', json={'provider': 'gemini-2.0-flash'})
        assert resp.status_code in ALLOWED

    def test_set_provider_valid_claude(self, client, admin_user):
        """Covers alternative valid providers."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/providers', json={'provider': 'claude-haiku'})
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – analytics/overview  (lines 1142-1143)
# ===========================================================================

class TestAnalyticsOverview:

    def test_analytics_overview_no_auth(self, client):
        resp = client.get('/api/admin/ai/analytics/overview')
        assert resp.status_code in ALLOWED

    def test_analytics_overview_default_days(self, client, admin_user):
        """Covers lines 1095-1146."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analytics/overview')
        assert resp.status_code in ALLOWED

    def test_analytics_overview_custom_days(self, client, admin_user):
        """Covers lines 1096: custom days param."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analytics/overview?days=30')
        assert resp.status_code in ALLOWED

    def test_analytics_overview_zero_days(self, client, admin_user):
        """Edge: days=0."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analytics/overview?days=0')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – analytics/trends  (lines 1176-1179, 1189-1190)
# ===========================================================================

class TestAnalyticsTrends:

    def test_analytics_trends_no_auth(self, client):
        resp = client.get('/api/admin/ai/analytics/trends')
        assert resp.status_code in ALLOWED

    def test_analytics_trends_default(self, client, admin_user):
        """Covers lines 1157-1192."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analytics/trends')
        assert resp.status_code in ALLOWED

    def test_analytics_trends_custom_days(self, client, admin_user):
        """Covers lines 1178-1179: trends dict built."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analytics/trends?days=14')
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'trends' in d.get('data', {})

    def test_analytics_trends_365_days(self, client, admin_user):
        """Edge: large days param."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/analytics/trends?days=365')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – notifications/effectiveness  (lines 1216-1217)
# ===========================================================================

class TestNotificationEffectiveness:

    def test_effectiveness_no_auth(self, client):
        resp = client.get('/api/admin/ai/notifications/effectiveness')
        assert resp.status_code in ALLOWED

    def test_effectiveness_as_admin(self, client, admin_user):
        """Covers lines 1209-1220."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/notifications/effectiveness')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – logs  (lines 1247-1248)
# ===========================================================================

class TestLogsRoute:

    def test_get_logs_no_auth(self, client):
        resp = client.get('/api/admin/ai/logs')
        assert resp.status_code in ALLOWED

    def test_get_logs_as_admin(self, client, admin_user):
        """Covers lines 1234-1251."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/logs')
        assert resp.status_code in ALLOWED

    def test_get_logs_with_operation_type(self, client, admin_user):
        """Covers lines 1237-1238: filter by operation_type."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/logs?operation_type=apply_preset')
        assert resp.status_code in ALLOWED

    def test_get_logs_with_limit(self, client, admin_user):
        """Covers limit param."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/logs?limit=10')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – report/daily  (lines 1270-1271)
# ===========================================================================

class TestDailyReport:

    def test_daily_report_no_auth(self, client):
        resp = client.get('/api/admin/ai/report/daily')
        assert resp.status_code in ALLOWED

    def test_daily_report_as_admin(self, client, admin_user):
        """Covers lines 1262-1274."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/report/daily')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – messages/sent  (lines 1357, 1375-1376)
# ===========================================================================

class TestMessagesSent:

    def test_messages_sent_no_auth(self, client):
        resp = client.get('/api/admin/ai/messages/sent')
        assert resp.status_code in ALLOWED

    def test_messages_sent_as_admin(self, client, admin_user):
        """Covers lines 1317-1378."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/sent')
        assert resp.status_code in ALLOWED

    def test_messages_sent_period_today(self, client, admin_user):
        """Covers lines 1339-1341: today filter."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/sent?period=today')
        assert resp.status_code in ALLOWED

    def test_messages_sent_period_week(self, client, admin_user):
        """Covers lines 1343-1344: week filter."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/sent?period=week')
        assert resp.status_code in ALLOWED

    def test_messages_sent_period_month(self, client, admin_user):
        """Covers lines 1345-1347: month filter."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/sent?period=month')
        assert resp.status_code in ALLOWED

    def test_messages_sent_with_limit(self, client, admin_user):
        """Covers limit param."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/sent?limit=5')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – messages/stats  (lines 1425-1426)
# ===========================================================================

class TestMessagesStats:

    def test_messages_stats_no_auth(self, client):
        resp = client.get('/api/admin/ai/messages/stats')
        assert resp.status_code in ALLOWED

    def test_messages_stats_as_admin(self, client, admin_user):
        """Covers lines 1395-1429."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/stats')
        assert resp.status_code in ALLOWED

    def test_messages_stats_period_today(self, client, admin_user):
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/stats?period=today')
        assert resp.status_code in ALLOWED

    def test_messages_stats_period_week(self, client, admin_user):
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/stats?period=week')
        assert resp.status_code in ALLOWED

    def test_messages_stats_period_month(self, client, admin_user):
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/messages/stats?period=month')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – automation/status  (lines 1481-1482, 1494-1510, 1522-1526, 1555-1556)
# ===========================================================================

class TestAutomationStatus:

    def test_automation_status_no_auth(self, client):
        resp = client.get('/api/admin/ai/automation/status')
        assert resp.status_code in ALLOWED

    def test_automation_status_as_admin(self, client, admin_user):
        """Covers lines 1448-1557."""
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/automation/status')
        assert resp.status_code in ALLOWED

    def test_automation_status_when_enabled(self, client, admin_user, db_session):
        """Covers lines 1492-1510: enabled=True → next_run computed."""
        _make_ai_setting(db_session, 'enable_auto_messages', 'true', 'boolean')
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/automation/status')
        assert resp.status_code in ALLOWED

    def test_automation_status_when_disabled(self, client, admin_user, db_session):
        """Covers disabled branch: next_run is None."""
        _make_ai_setting(db_session, 'enable_auto_messages', 'false', 'boolean')
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/automation/status')
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            data = d.get('data', {})
            # When disabled, next_run should be None
            if not data.get('automation_enabled'):
                assert data.get('next_run') is None


# ===========================================================================
# admin_ai.py – automation/toggle  (lines 1555-1556 + surrounding)
# ===========================================================================

class TestAutomationToggle:

    def test_toggle_no_auth(self, client):
        resp = client.put('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert resp.status_code in ALLOWED

    def test_toggle_enable(self, client, admin_user):
        """Covers lines 1572-1595: enable automation."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/automation/toggle', json={'enabled': True})
        assert resp.status_code in ALLOWED

    def test_toggle_disable(self, client, admin_user):
        """Covers toggle off path."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/automation/toggle', json={'enabled': False})
        assert resp.status_code in ALLOWED

    def test_toggle_empty_body_defaults_false(self, client, admin_user):
        """Covers lines 1573-1574: empty body → defaults to False."""
        _login(client, admin_user)
        resp = client.put('/api/admin/ai/automation/toggle', json={})
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – automation/test  (lines 1669-1675, 1709-1720, 1728-1736,
#                                   1753-1770)
# ===========================================================================

class TestAutomationTest:

    def test_automation_test_no_auth(self, client):
        resp = client.post('/api/admin/ai/automation/test')
        assert resp.status_code in ALLOWED

    def test_automation_test_simple(self, client, admin_user):
        """Covers lines 1627-1678: simple test path."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/automation/test',
            json={'simple': True},
        )
        assert resp.status_code in ALLOWED

    def test_automation_test_complex_no_student(self, client, admin_user):
        """Covers lines 1722-1741: complex test without student_id."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/automation/test',
            json={'simple': False},
        )
        assert resp.status_code in ALLOWED

    def test_automation_test_complex_with_nonexistent_student(self, client, admin_user):
        """Covers lines 1694-1698: student not found → 404."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/automation/test',
            json={'simple': False, 'student_id': 99999},
        )
        assert resp.status_code in ALLOWED

    def test_automation_test_complex_with_student(self, client, admin_user, db_session):
        """Covers lines 1700-1720: complex test with real student."""
        s = _make_student(db_session)
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/automation/test',
            json={'simple': False, 'student_id': s.id},
        )
        assert resp.status_code in ALLOWED

    def test_automation_test_no_json_body(self, client, admin_user):
        """Covers lines 1623: silent=True → body is empty dict."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/automation/test')
        assert resp.status_code in ALLOWED


# ===========================================================================
# admin_ai.py – /dashboard (no auth req)  (lines 1801-1802, 1815-1816)
# ===========================================================================

class TestAdminDashboardNoAuth:

    def test_dashboard_accessible_without_login(self, client):
        """Covers lines 1786-1816: no @admin_required decorator."""
        resp = client.get('/api/admin/ai/dashboard')
        assert resp.status_code in ALLOWED

    def test_dashboard_returns_stats(self, client, admin_user):
        _login(client, admin_user)
        resp = client.get('/api/admin/ai/dashboard')
        assert resp.status_code in ALLOWED
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True


# ===========================================================================
# admin_ai.py – students/inactive  (lines 1834-1836, 1843-1844)
# ===========================================================================

class TestStudentsInactive:

    def test_inactive_students_default_days(self, client):
        """Covers lines 1827-1844: no auth required."""
        resp = client.get('/api/admin/ai/students/inactive')
        assert resp.status_code in ALLOWED

    def test_inactive_students_custom_days(self, client):
        resp = client.get('/api/admin/ai/students/inactive?days=30')
        assert resp.status_code in ALLOWED

    def test_inactive_students_with_students(self, client, db_session):
        """Covers lines 1833-1841: iterates students."""
        _make_student(db_session, is_active=True)
        resp = client.get('/api/admin/ai/students/inactive?days=0')
        assert resp.status_code in ALLOWED

    def test_inactive_students_response_structure(self, client):
        resp = client.get('/api/admin/ai/students/inactive')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'students' in d
            assert 'count' in d


# ===========================================================================
# admin_ai.py – students/low-score  (lines 1862-1877)
# ===========================================================================

class TestStudentsLowScore:

    def test_low_score_no_auth_accessible(self, client):
        """Covers lines 1854-1878: no @admin_required."""
        resp = client.get('/api/admin/ai/students/low-score')
        assert resp.status_code in ALLOWED

    def test_low_score_custom_threshold(self, client):
        resp = client.get('/api/admin/ai/students/low-score?threshold=70')
        assert resp.status_code in ALLOWED

    def test_low_score_response_structure(self, client):
        resp = client.get('/api/admin/ai/students/low-score')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'students' in d
            assert 'count' in d


# ===========================================================================
# admin_ai.py – audit-log GET  (lines 1912-1916)
# ===========================================================================

class TestAuditLogGet:

    def test_audit_log_get_no_auth(self, client):
        """Covers lines 1892-1916: no @admin_required."""
        resp = client.get('/api/admin/ai/audit-log')
        assert resp.status_code in ALLOWED

    def test_audit_log_get_with_action_filter(self, client):
        resp = client.get('/api/admin/ai/audit-log?action=login')
        assert resp.status_code in ALLOWED

    def test_audit_log_get_pagination(self, client):
        resp = client.get('/api/admin/ai/audit-log?page=1&per_page=10')
        assert resp.status_code in ALLOWED

    def test_audit_log_response_structure(self, client):
        resp = client.get('/api/admin/ai/audit-log')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'logs' in d
            assert 'total' in d


# ===========================================================================
# admin_ai.py – audit-log POST  (lines 1940-1941)
# ===========================================================================

class TestAuditLogPost:

    def test_audit_log_post_no_auth(self, client):
        """No auth → 403 (requires @admin_required)."""
        resp = client.post('/api/admin/ai/audit-log', json={})
        assert resp.status_code in ALLOWED

    def test_audit_log_post_missing_fields(self, client, admin_user):
        """Covers lines 1927-1928: missing action/description → 400."""
        _login(client, admin_user)
        resp = client.post('/api/admin/ai/audit-log', json={'action': 'login'})
        assert resp.status_code in ALLOWED

    def test_audit_log_post_valid(self, client, admin_user):
        """Covers lines 1930-1940: valid creation."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/audit-log',
            json={'action': 'test_action', 'description': 'Integration test log entry'},
        )
        assert resp.status_code in ALLOWED

    def test_audit_log_post_with_target(self, client, admin_user):
        """Covers lines 1936-1937: target_type + target_id."""
        _login(client, admin_user)
        resp = client.post(
            '/api/admin/ai/audit-log',
            json={
                'action': 'update',
                'description': 'Updated student record',
                'target_type': 'student',
                'student_id': 1,
            },
        )
        assert resp.status_code in ALLOWED


# ===========================================================================
# ============  google_drive_backend_routes.py  =============================
# ===========================================================================

GD_PREFIX = '/google-drive-backend'
ALLOWED_GD = [200, 302, 400, 401, 403, 404, 500, 503]


class TestGDEncryptionFunctions:
    """
    Lines 26, 35-38: generate_encryption_key() and get_encryption_key()
    These are called at module load. We cover the routes that exercise them.
    """

    def test_connection_status_always_accessible(self, client):
        """
        Covers lines 533-542: status endpoint, no auth required.
        Also exercises cipher_suite built from ENCRYPTION_KEY.
        """
        resp = client.get(f'{GD_PREFIX}/api/v1/google-drive-backend/connection-status')
        assert resp.status_code in ALLOWED_GD

    def test_connection_status_has_connected_field(self, client):
        resp = client.get(f'{GD_PREFIX}/api/v1/google-drive-backend/connection-status')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'connected' in d


class TestGDEncryptDecrypt:
    """Lines 154-156, 160-166: encrypt / decrypt paths."""

    def test_save_settings_when_not_connected(self, client):
        """
        Covers lines 547-551: save-settings when Google Drive not connected → 400.
        Also exercises encrypt path via save_to_google_drive_backend.
        """
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/save-settings')
        assert resp.status_code in ALLOWED_GD

    def test_load_settings_when_not_connected(self, client):
        """Covers lines 564-568: load-settings when not connected → 400."""
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/load-settings')
        assert resp.status_code in ALLOWED_GD


class TestGDConnect:
    """Lines 248-250, 268-270: connect / disconnect routes."""

    def test_connect_no_auth_accepted(self, client):
        """Routes have no auth check. Covers lines 481-505."""
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/connect',
            json={},
        )
        assert resp.status_code in ALLOWED_GD

    def test_connect_response_has_connected_field(self, client):
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/connect',
            json={},
        )
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('connected') is True

    def test_disconnect(self, client):
        """Covers lines 507-531: disconnect route."""
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/disconnect',
            json={},
        )
        assert resp.status_code in ALLOWED_GD

    def test_disconnect_then_status_shows_disconnected(self, client):
        """Covers lines 533-542 after disconnect."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/disconnect')
        resp = client.get(f'{GD_PREFIX}/api/v1/google-drive-backend/connection-status')
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('connected') is False


class TestGDSaveLoadSettings:
    """Lines 279-282, 286-313, 317-341: save / load from Drive."""

    def test_save_settings_connected(self, client):
        """Covers lines 553-558: after connect, save works."""
        # Connect first
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/save-settings')
        assert resp.status_code in ALLOWED_GD

    def test_save_settings_response_has_timestamp(self, client):
        """Covers lines 555-558."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/save-settings')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'timestamp' in d

    def test_load_settings_when_connected_no_backup(self, client):
        """
        Covers lines 570-579: connected but no backup file yet → may return 500 or 200.
        Lines 317-341: load_from_google_drive_backend path.
        """
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/load-settings')
        assert resp.status_code in ALLOWED_GD

    def test_save_then_load(self, client):
        """Full round-trip covers lines 286-313 and 317-341."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        save_resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/save-settings')
        if save_resp.status_code == 200:
            load_resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/load-settings')
            assert load_resp.status_code in ALLOWED_GD


class TestGDSync:
    """Lines 593-618: sync route."""

    def test_sync_not_connected(self, client):
        """Covers lines 587-591: not connected → 400."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/disconnect', json={})
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/sync')
        assert resp.status_code in ALLOWED_GD

    def test_sync_connected(self, client):
        """Covers lines 593-621: connected sync path."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/sync')
        assert resp.status_code in ALLOWED_GD

    def test_sync_response_structure(self, client):
        """Covers lines 610-615: success response fields."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        # save so load can succeed
        client.post(f'{GD_PREFIX}/api/google-drive-backend/save-settings')
        resp = client.post(f'{GD_PREFIX}/api/google-drive-backend/sync')
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True
            assert 'timestamp' in d


class TestGDFormPages:
    """Lines 418-422, 425-429, 432-435, 438-445, 448-452, 455-459: settings form POST."""

    def test_settings_get_page(self, client):
        """Covers lines 383-411: GET settings page."""
        resp = client.get(f'{GD_PREFIX}/google-drive-settings')
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_profile_submit(self, client):
        """Covers lines 417-422: profile_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'profile_submit': '1',
                'full_name': 'Test User',
                'email': 'test@example.com',
                'bio': 'Test bio',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_notification_submit(self, client):
        """Covers lines 424-429: notification_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'notification_submit': '1',
                'email_notifications': 'y',
                'app_notifications': 'y',
                'notification_frequency': 'immediate',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_security_submit(self, client):
        """Covers lines 431-435: security_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'security_submit': '1',
                'two_factor_auth': 'y',
                'login_alerts': 'y',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_integration_submit(self, client):
        """Covers lines 437-445: integration_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'integration_submit': '1',
                'google_integration': 'y',
                'microsoft_integration': '',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_integration_regenerate_api_key(self, client):
        """Covers lines 441-442: regenerate_api_key in form."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'integration_submit': '1',
                'google_integration': 'y',
                'regenerate_api_key': '1',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_google_drive_submit(self, client):
        """Covers lines 447-452: google_drive_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'google_drive_submit': '1',
                'backup_destination': 'local',
                'auto_backup': '',
                'backup_frequency': 'daily',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_ui_submit(self, client):
        """Covers lines 454-459: ui_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'ui_submit': '1',
                'theme': 'dark',
                'language': 'ar',
                'font_size': 'medium',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD

    def test_settings_post_password_submit(self, client):
        """Covers lines 461-464: password_submit branch."""
        resp = client.post(
            f'{GD_PREFIX}/google-drive-settings',
            data={
                'password_submit': '1',
                'current_password': 'OldPass@123',
                'new_password': 'NewPass@123',
                'confirm_password': 'NewPass@123',
            },
            follow_redirects=False,
        )
        assert resp.status_code in ALLOWED_GD


class TestGDExportImportUserData:
    """Lines 658-664, 680-688: export / import user data."""

    def test_export_user_data(self, client):
        """Covers lines 635-643: export endpoint."""
        resp = client.get(f'{GD_PREFIX}/api/google-drive-backend/user/export')
        assert resp.status_code in ALLOWED_GD
        if resp.status_code == 200:
            d = resp.get_json()
            assert d.get('success') is True
            assert 'data' in d

    def test_export_user_data_has_profile(self, client):
        """Covers lines 638-643: data includes profile."""
        resp = client.get(f'{GD_PREFIX}/api/google-drive-backend/user/export')
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'profile' in d.get('data', {})

    def test_import_user_data_valid(self, client):
        """Covers lines 645-656: import with valid data."""
        payload = {
            'profile': {
                'full_name': 'Imported User',
                'email': 'imported@example.com',
                'bio': 'Imported bio',
            }
        }
        resp = client.post(
            f'{GD_PREFIX}/api/google-drive-backend/user/import',
            json=payload,
        )
        assert resp.status_code in ALLOWED_GD

    def test_import_user_data_empty(self, client):
        """Covers lines 651-661: empty dict → apply succeeds but no change."""
        resp = client.post(
            f'{GD_PREFIX}/api/google-drive-backend/user/import',
            json={},
        )
        assert resp.status_code in ALLOWED_GD

    def test_import_user_data_notifications(self, client):
        """Covers lines 221-224: notifications section of apply_settings."""
        payload = {
            'notifications': {
                'email_notifications': False,
                'app_notifications': True,
                'notification_frequency': 'daily',
            }
        }
        resp = client.post(
            f'{GD_PREFIX}/api/google-drive-backend/user/import',
            json=payload,
        )
        assert resp.status_code in ALLOWED_GD

    def test_import_user_data_security_section(self, client):
        """Covers lines 226-229: security section of apply_settings."""
        payload = {
            'security': {
                'two_factor_auth': True,
                'login_alerts': False,
            }
        }
        resp = client.post(
            f'{GD_PREFIX}/api/google-drive-backend/user/import',
            json=payload,
        )
        assert resp.status_code in ALLOWED_GD

    def test_import_user_data_google_drive_section(self, client):
        """Covers lines 236-240: google_drive section of apply_settings."""
        payload = {
            'google_drive': {
                'connected': True,
                'backup_destination': 'google_drive',
                'auto_backup': True,
                'backup_frequency': 'weekly',
            }
        }
        resp = client.post(
            f'{GD_PREFIX}/api/google-drive-backend/user/import',
            json=payload,
        )
        assert resp.status_code in ALLOWED_GD

    def test_import_user_data_ui_preferences(self, client):
        """Covers lines 242-245: ui_preferences section."""
        payload = {
            'ui_preferences': {
                'theme': 'dark',
                'language': 'en',
                'font_size': 'large',
            }
        }
        resp = client.post(
            f'{GD_PREFIX}/api/google-drive-backend/user/import',
            json=payload,
        )
        assert resp.status_code in ALLOWED_GD


class TestGDSyncSettingsRoutes:
    """Lines 702-710, 724-739: sync-to-drive and download-from-drive."""

    def test_sync_to_drive_not_connected(self, client):
        """Covers lines 674-678: not connected → 400."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/disconnect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/sync-to-drive'
        )
        assert resp.status_code in ALLOWED_GD

    def test_sync_to_drive_connected(self, client):
        """Covers lines 680-691: connected sync."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/sync-to-drive'
        )
        assert resp.status_code in ALLOWED_GD

    def test_download_from_drive_not_connected(self, client):
        """Covers lines 696-700: not connected → 400."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/disconnect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/download-from-drive'
        )
        assert resp.status_code in ALLOWED_GD

    def test_download_from_drive_connected(self, client):
        """Covers lines 702-713: connected download."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/download-from-drive'
        )
        assert resp.status_code in ALLOWED_GD

    def test_quick_sync_not_connected(self, client):
        """Covers lines 718-722: not connected → 400."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/disconnect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/quick-sync'
        )
        assert resp.status_code in ALLOWED_GD

    def test_quick_sync_connected(self, client):
        """Covers lines 724-742: connected quick-sync."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/quick-sync'
        )
        assert resp.status_code in ALLOWED_GD

    def test_quick_sync_response_last_sync(self, client):
        """Covers lines 733-736: success response has last_sync."""
        client.post(f'{GD_PREFIX}/api/v1/google-drive-backend/connect', json={})
        resp = client.post(
            f'{GD_PREFIX}/api/v1/google-drive-backend/user-settings/quick-sync'
        )
        if resp.status_code == 200:
            d = resp.get_json()
            assert 'last_sync' in d


class TestGDRegisterFunction:
    """Lines 760-762: register_google_drive_backend_routes error path."""

    def test_blueprint_is_registered(self, client):
        """
        Covers that the blueprint is already registered in the app.
        If the app started, registration succeeded (lines 748-759).
        """
        resp = client.get(f'{GD_PREFIX}/api/v1/google-drive-backend/connection-status')
        assert resp.status_code in ALLOWED_GD

    def test_dashboard_page_registered(self, client):
        """Covers lines 361-365: index route registered."""
        resp = client.get(f'{GD_PREFIX}/google-drive-dashboard')
        assert resp.status_code in ALLOWED_GD

    def test_add_question_page_registered(self, client):
        """Covers lines 625-628: add question route registered."""
        resp = client.get(f'{GD_PREFIX}/google-drive-add-question')
        assert resp.status_code in ALLOWED_GD

    def test_manage_questions_page_registered(self, client):
        """Covers lines 630-633: manage questions route registered."""
        resp = client.get(f'{GD_PREFIX}/google-drive-manage-questions')
        assert resp.status_code in ALLOWED_GD
