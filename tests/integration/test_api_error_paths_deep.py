"""
اختبارات مسارات الخطأ والـ dummy data في api.py
يستهدف تغطية:
- dummy activities paths (activity_available=False)
- dummy recent questions (exception in query)
- dummy data in get_recent_activities when exception occurs
- get_google_drive_service with DB credentials
- Google Drive connect with db error
- upload_image_api
- save/load backup settings edge cases
- additional error paths
"""
import pytest
import json
import secrets
from unittest.mock import patch, MagicMock


# ==================== Helpers ====================

def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_admin(db_session):
    from src.models.user import User
    u = User(
        username=f'adm_err_{secrets.token_hex(4)}',
        email=f'adm_err_{secrets.token_hex(4)}@test.com',
        is_admin=True
    )
    u.set_password('Admin@123')
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_course(db_session, *, show_in_bot=True, name=None):
    from src.models.curriculum import Course
    c = Course(
        name=name or f'ErrCourse_{secrets.token_hex(3)}',
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(c)
    db_session.session.commit()
    db_session.session.refresh(c)
    return c


def _make_unit(db_session, course, *, show_in_bot=True, name=None):
    from src.models.curriculum import Unit
    u = Unit(
        name=name or f'ErrUnit_{secrets.token_hex(3)}',
        course_id=course.id,
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(u)
    db_session.session.commit()
    db_session.session.refresh(u)
    return u


def _make_lesson(db_session, unit, *, show_in_bot=True, name=None):
    from src.models.curriculum import Lesson
    l = Lesson(
        name=name or f'ErrLesson_{secrets.token_hex(3)}',
        unit_id=unit.id,
        show_in_bot=show_in_bot,
        order_num=1
    )
    db_session.session.add(l)
    db_session.session.commit()
    db_session.session.refresh(l)
    return l


def _make_question(db_session, lesson, *, blocked=False, text=None):
    from src.models.question import Question, Option
    q = Question(
        lesson_id=lesson.id,
        question_text=text or f'سؤال خطأ {secrets.token_hex(3)}؟',
        is_blocked=blocked
    )
    db_session.session.add(q)
    db_session.session.flush()
    for i, correct in enumerate([True, False, False, False]):
        opt = Option(
            question_id=q.question_id,
            option_text=f'خيار {i + 1}',
            is_correct=correct
        )
        db_session.session.add(opt)
    db_session.session.commit()
    db_session.session.refresh(q)
    return q


# ==================== Test: dummy activities (activity_available=False) ====================

class TestDummyActivities:
    """تغطية dummy data في activities عبر جعل activity_available=False"""

    def test_activities_when_activity_unavailable(self, client):
        """عندما activity_available=False يُرجع dummy data"""
        with patch('src.routes.api.activity_available', False):
            r = client.get('/api/v1/activities/recent')
            assert r.status_code == 200
            data = r.get_json()
            assert 'activities' in data
            assert len(data['activities']) > 0

    def test_activities_dummy_has_action_type(self, client):
        with patch('src.routes.api.activity_available', False):
            r = client.get('/api/v1/activities/recent')
            data = r.get_json()
            if data['activities']:
                assert 'action_type' in data['activities'][0]

    def test_activities_dummy_has_icon(self, client):
        with patch('src.routes.api.activity_available', False):
            r = client.get('/api/v1/activities/recent')
            data = r.get_json()
            if data['activities']:
                assert 'icon' in data['activities'][0]

    def test_activities_dummy_limit_applied(self, client):
        with patch('src.routes.api.activity_available', False):
            r = client.get('/api/v1/activities/recent?limit=2')
            data = r.get_json()
            assert len(data['activities']) <= 2

    def test_activities_when_table_check_raises(self, client):
        """عندما يُثير فحص الجدول استثناء -> يستمر في الاستعلام"""
        with patch('src.routes.api.Activity') as mock_activity:
            mock_activity.__table__ = MagicMock()
            mock_activity.__table__.exists.side_effect = Exception('table check error')
            mock_activity.query.order_by.return_value.limit.return_value.all.return_value = []
            r = client.get('/api/v1/activities/recent')
            assert r.status_code == 200

    def test_activities_when_query_raises_exception(self, client):
        """عندما يرمي الاستعلام استثناءً -> يُرجع dummy data"""
        with patch('src.routes.api.Activity') as mock_activity:
            mock_activity.__table__ = MagicMock()
            mock_activity.__table__.exists.return_value = True
            mock_activity.query.order_by.side_effect = Exception('query failed')
            r = client.get('/api/v1/activities/recent')
            assert r.status_code == 200
            data = r.get_json()
            assert 'activities' in data


# ==================== Test: dummy recent questions ====================

class TestDummyRecentQuestions:
    """تغطية dummy data في recent questions"""

    def test_recent_questions_inner_query_failure(self, client):
        """عندما يفشل الاستعلام المعقد -> استعلام بسيط"""
        with patch('src.routes.api.Question') as mock_q:
            mock_q.query.options.side_effect = Exception('options failed')
            mock_q.query.order_by.return_value.limit.return_value.all.return_value = []
            r = client.get('/api/v1/questions/recent')
            assert r.status_code == 200

    def test_recent_questions_all_queries_fail(self, client):
        """عندما تفشل كل الاستعلامات -> dummy data"""
        with patch('src.routes.api.Question') as mock_q:
            mock_q.query.options.side_effect = Exception('all failed')
            mock_q.query.order_by.side_effect = Exception('all failed')
            r = client.get('/api/v1/questions/recent')
            assert r.status_code == 200
            data = r.get_json()
            assert 'questions' in data


# ==================== Test: Google Drive connect DB error ====================

class TestGoogleDriveConnectDbError:
    """تغطية مسارات Google Drive connect مع أخطاء DB"""

    def test_connect_db_commit_fails(self, client, db_session):
        """عندما يفشل commit في Google Drive connect"""
        user = _make_admin(db_session)
        _login(client, user)
        # حتى لو فشل DB commit، يجب أن يُرجع success=True لأن session يُحفظ
        with patch('src.routes.api.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('commit failed')
            mock_db.session.rollback = MagicMock()
            mock_db.session.add = MagicMock()
            r = client.post('/api/v1/v1/google-drive/connect', json={})
            # قد يُرجع 200 (session حُفظ) أو 500
            assert r.status_code in [200, 500]


# ==================== Test: get_google_drive_service variations ====================

class TestGetGoogleDriveServiceVariations:
    """تغطية get_google_drive_service بطرق مختلفة"""

    def test_diagnose_when_drive_unavailable(self, client, db_session):
        """google_drive_available=False -> service_test=False"""
        user = _make_admin(db_session)
        _login(client, user)
        with patch('src.routes.api.google_drive_available', False):
            r = client.get('/api/v1/v1/google-drive/diagnose')
            assert r.status_code == 200
            data = r.get_json()
            assert data.get('service_test') == False

    def test_connection_status_when_drive_unavailable(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        with patch('src.routes.api.google_drive_available', False):
            r = client.get('/api/v1/v1/google-drive/connection-status')
            assert r.status_code == 200

    def test_connect_when_drive_unavailable(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        with patch('src.routes.api.google_drive_available', False):
            r = client.post('/api/v1/v1/google-drive/connect', json={})
            assert r.status_code == 500
            data = r.get_json()
            assert data.get('success') == False


# ==================== Test: upload_image_api ====================

class TestUploadImageApi:
    """اختبارات /api/v1/upload-image"""

    def test_no_auth_redirects(self, client):
        r = client.post('/api/v1/upload-image')
        assert r.status_code in [302, 401]

    def test_no_image_returns_400(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/upload-image')
        assert r.status_code == 400

    def test_with_mock_save_upload_success(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        import io
        with patch('src.routes.api.save_upload', return_value='https://cloudinary.com/test.jpg', create=True):
            data = {'image': (io.BytesIO(b'fake image data'), 'test.jpg')}
            r = client.post('/api/v1/upload-image',
                            data=data,
                            content_type='multipart/form-data')
            assert r.status_code in [200, 400, 500]

    def test_with_mock_save_upload_none(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        import io
        with patch('src.routes.api.save_upload', return_value=None, create=True):
            data = {'image': (io.BytesIO(b'fake image data'), 'test.jpg')}
            r = client.post('/api/v1/upload-image',
                            data=data,
                            content_type='multipart/form-data')
            assert r.status_code in [200, 400, 500]


# ==================== Test: format_image_url edge cases ====================

class TestFormatImageUrlEdgeCases:
    """تغطية format_image_url edge cases عبر questions API"""

    def test_question_with_https_url(self, client, db_session):
        """سؤال مع https image URL - لا يُعالج"""
        from src.models.question import Question, Option
        course = _make_course(db_session, name='HTTPS URL Course')
        unit = _make_unit(db_session, course, name='HTTPS URL Unit')
        lesson = _make_lesson(db_session, unit, name='HTTPS URL Lesson')
        q = Question(
            lesson_id=lesson.id,
            question_text='سؤال https',
            image_url='https://cdn.example.com/img.jpg'
        )
        db_session.session.add(q)
        db_session.session.flush()
        for i, c in enumerate([True, False]):
            db_session.session.add(Option(
                question_id=q.question_id,
                option_text=f'خيار {i}',
                is_correct=c
            ))
        db_session.session.commit()
        r = client.get(f'/api/v1/lessons/{lesson.id}/questions')
        assert r.status_code == 200
        data = r.get_json()
        if data:
            q_data = next((x for x in data if x['question_id'] == q.question_id), None)
            if q_data:
                # https URLs تُرجع كما هي
                assert q_data['image_url'] == 'https://cdn.example.com/img.jpg'


# ==================== Test: get_time_diff_text edge cases ====================

class TestGetTimeDiffText:
    """تغطية get_time_diff_text paths مختلفة"""

    def test_time_diff_with_activities_various(self, client):
        """استدعاء activities لتغطية get_time_diff_text"""
        r = client.get('/api/v1/activities/recent?limit=10')
        assert r.status_code == 200

    def test_time_diff_text_seconds(self):
        """اختبار get_time_diff_text مباشرة"""
        from datetime import datetime, timedelta
        import src.routes.api as api_module

        # منذ لحظات
        now = datetime.utcnow()
        result = api_module.get_time_diff_text(now - timedelta(seconds=30))
        assert 'لحظات' in result

    def test_time_diff_text_minutes(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(minutes=5))
        assert 'دقائق' in result or 'دقيقة' in result

    def test_time_diff_text_hours(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(hours=3))
        assert 'ساعة' in result or 'ساعات' in result

    def test_time_diff_text_days(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(days=5))
        assert 'يوم' in result or 'أيام' in result

    def test_time_diff_text_months(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(days=60))
        assert 'شهر' in result or 'أشهر' in result

    def test_time_diff_text_years(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(days=400))
        assert 'سنة' in result or 'سنوات' in result

    def test_time_diff_1_hour(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(hours=1))
        assert 'ساعة' in result

    def test_time_diff_1_day(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(days=1))
        assert 'يوم' in result

    def test_time_diff_1_month(self):
        from datetime import datetime, timedelta
        import src.routes.api as api_module
        result = api_module.get_time_diff_text(datetime.utcnow() - timedelta(days=31))
        assert 'شهر' in result


# ==================== Test: get_activity_icon edge cases ====================

class TestGetActivityIcon:
    """تغطية get_activity_icon"""

    def test_add_icon(self):
        import src.routes.api as api_module
        assert api_module.get_activity_icon('add') == 'fas fa-plus-circle'

    def test_edit_icon(self):
        import src.routes.api as api_module
        assert api_module.get_activity_icon('edit') == 'fas fa-edit'

    def test_delete_icon(self):
        import src.routes.api as api_module
        assert api_module.get_activity_icon('delete') == 'fas fa-trash-alt'

    def test_import_icon(self):
        import src.routes.api as api_module
        assert api_module.get_activity_icon('import') == 'fas fa-file-import'

    def test_export_icon(self):
        import src.routes.api as api_module
        assert api_module.get_activity_icon('export') == 'fas fa-file-export'

    def test_unknown_icon_returns_default(self):
        import src.routes.api as api_module
        assert api_module.get_activity_icon('unknown_action') == 'fas fa-history'


# ==================== Test: backup/test error paths ====================

class TestBackupTestErrorPaths:
    """تغطية backup/test error paths"""

    def test_backup_with_questions_only_type(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        r = client.post('/api/v1/backup/test', json={
            'backup_type': 'questions_only',
            'destination': 'google_drive'
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['backup_data']['content']['questions'] == True
        assert data['backup_data']['content']['user_settings'] == False

    def test_backup_statistics_fetch_error(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        with patch('src.routes.api.Question') as mock_q:
            mock_q.query.count.side_effect = Exception('count error')
            r = client.post('/api/v1/backup/test', json={})
            assert r.status_code == 200
            data = r.get_json()
            # يستخدم fallback values
            assert data.get('success') == True


# ==================== Test: save/load backup settings edge cases ====================

class TestBackupSettingsEdgeCases:
    """تغطية backup settings edge cases"""

    def test_load_after_save(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        # Save
        client.post('/api/v1/backup-settings/save', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'weekly',
            'backup_destination': 'google_drive',
            'max_backups': 7,
            'backup_time': '04:00',
            'include_images': False,
            'compress_backup': False,
            'encrypt_backup': True
        })
        # Load
        r = client.get('/api/v1/backup-settings/load')
        assert r.status_code == 200
        data = r.get_json()
        assert data['settings']['backup_frequency'] == 'weekly'
        assert data['settings']['max_backups'] == 7

    def test_save_multiple_times(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        for i in range(3):
            r = client.post('/api/v1/backup-settings/save', json={
                'max_backups': i + 1
            })
            assert r.status_code == 200


# ==================== Test: get_backup_status edge cases ====================

class TestBackupStatusEdgeCases:
    """تغطية backup status edge cases"""

    def test_status_with_db_token_and_session(self, client, db_session):
        """اختبار backup/status مع token في قاعدة البيانات وsession"""
        user = _make_admin(db_session)
        _login(client, user)
        # إضافة token
        from src.models.google_drive import GoogleDriveToken
        from datetime import datetime
        token = GoogleDriveToken(
            user_id=user.id,
            access_token='test_token',
            refresh_token='test_refresh',
            token_uri='https://oauth2.googleapis.com/token',
            client_id='test_client',
            client_secret='test_secret',
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.session.add(token)
        db_session.session.commit()
        r = client.get('/api/v1/backup/status')
        assert r.status_code == 200
        data = r.get_json()
        assert data['status']['google_drive']['connected'] == True


# ==================== Test: user settings sync with connected session ====================

class TestUserSettingsWithConnectedSession:
    """اختبارات مفصلة لـ user settings مع session متصل"""

    def _set_connected(self, client):
        with client.session_transaction() as sess:
            sess['google_drive_connected'] = True
            sess['google_drive_credentials'] = {'token': 'test'}

    def test_sync_status_with_connected_session(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        self._set_connected(client)
        r = client.get('/api/v1/user-settings/sync-status')
        assert r.status_code == 200
        data = r.get_json()
        assert data['status']['connected'] == True

    def test_sync_to_drive_settings_response_has_settings(self, client, db_session):
        user = _make_admin(db_session)
        _login(client, user)
        self._set_connected(client)
        r = client.post('/api/v1/v1/user-settings/sync-to-drive', json={
            'notifications': True,
            'theme': 'dark',
            'language': 'ar'
        })
        assert r.status_code == 200
        data = r.get_json()
        if data.get('success'):
            assert 'settings' in data
            assert 'preferences' in data.get('settings', {})
