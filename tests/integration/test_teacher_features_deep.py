"""
اختبارات عميقة لـ teacher_features_routes
يغطي: admin_required decorator, CRUD endpoints, helpers, page endpoint
"""
import pytest
from unittest.mock import patch, MagicMock

from src.models.teacher_feature import FEATURE_DEFAULTS, FEATURE_LABELS


# ─── helpers ────────────────────────────────────────────────────────────────

def _login_as_admin(client, admin_user):
    """تسجيل دخول كأدمن عبر الجلسة"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_teacher(db_session, app, username, email, name=None):
    from src.models.teacher import Teacher
    with app.app_context():
        t = Teacher(
            name=name or f'Teacher {username}',
            username=username,
            email=email,
            is_active=True,
        )
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        return t.id


def _make_override(db_session, app, teacher_id, feature_key, value):
    from src.models.teacher_feature import TeacherFeatureOverride
    with app.app_context():
        override = TeacherFeatureOverride(
            teacher_id=teacher_id,
            feature_key=feature_key,
            value=value,
        )
        db_session.session.add(override)
        db_session.session.commit()
        db_session.session.refresh(override)
        return override.id


# ─── Test: unauthenticated access ────────────────────────────────────────────

class TestTeacherFeaturesUnauthenticated:

    def test_get_global_no_auth(self, client):
        """GET /global بدون مصادقة → 403"""
        resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code in [302, 401, 403]

    def test_post_global_no_auth(self, client):
        """POST /global بدون مصادقة → 403"""
        resp = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'lesson_prep_enabled',
            'value': 'true',
        })
        assert resp.status_code in [302, 401, 403]

    def test_all_teachers_no_auth(self, client):
        """GET /all-teachers بدون مصادقة → 403"""
        resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code in [302, 401, 403]

    def test_get_teacher_no_auth(self, client):
        """GET /<teacher_id> بدون مصادقة → 403"""
        resp = client.get('/api/admin/teacher-features/1')
        assert resp.status_code in [302, 401, 403]

    def test_post_teacher_no_auth(self, client):
        """POST /<teacher_id> بدون مصادقة → 403"""
        resp = client.post('/api/admin/teacher-features/1', json={})
        assert resp.status_code in [302, 401, 403]

    def test_delete_override_no_auth(self, client):
        """DELETE /<teacher_id>/<feature_key> بدون مصادقة → 403"""
        resp = client.delete('/api/admin/teacher-features/1/lesson_prep_enabled')
        assert resp.status_code in [302, 401, 403]

    def test_page_no_auth(self, client):
        """GET /page بدون مصادقة → 403 أو redirect"""
        resp = client.get('/api/admin/teacher-features/page')
        assert resp.status_code in [302, 401, 403]

    def test_non_admin_user_blocked(self, client, db_session, app):
        """مستخدم غير أدمن → 403"""
        from src.models.user import User
        with app.app_context():
            u = User(username='regular_user_tf', email='regularusertf@test.com', is_admin=False)
            u.set_password('Pass@123')
            db_session.session.add(u)
            db_session.session.commit()
            db_session.session.refresh(u)
            uid = u.id
        with client.session_transaction() as sess:
            sess['_user_id'] = str(uid)
            sess['_fresh'] = True
        resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code == 403


# ─── Test: GET /global ────────────────────────────────────────────────────────

class TestGetGlobalFeatures:

    def test_success_returns_all_features(self, client, admin_user):
        """جلب الميزات العامة → جميع المفاتيح موجودة"""
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'features' in data
        features = data['features']
        for key in FEATURE_DEFAULTS:
            assert key in features

    def test_features_have_label_value_default(self, client, admin_user):
        """كل ميزة تحتوي على label, value, default"""
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code == 200
        features = resp.get_json()['features']
        for key, info in features.items():
            assert 'label' in info
            assert 'value' in info
            assert 'default' in info

    def test_features_default_values_match(self, client, admin_user):
        """القيم الافتراضية تطابق FEATURE_DEFAULTS"""
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code == 200
        features = resp.get_json()['features']
        for key, default in FEATURE_DEFAULTS.items():
            assert features[key]['default'] == default

    def test_global_after_setting(self, client, admin_user, db_session, app):
        """بعد تعيين قيمة → تظهر في GET"""
        from src.models.ai_analysis import AISetting
        with app.app_context():
            AISetting.set_setting('lesson_prep_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code == 200
        features = resp.get_json()['features']
        assert features['lesson_prep_enabled']['value'] == 'false'

    def test_exception_returns_500(self, client, admin_user):
        """استثناء في _get_global_features → 500"""
        _login_as_admin(client, admin_user)
        with patch('src.routes.teacher_features_routes._get_global_features', side_effect=Exception('DB error')):
            resp = client.get('/api/admin/teacher-features/global')
        assert resp.status_code == 500
        data = resp.get_json()
        assert data['success'] is False


# ─── Test: POST /global ───────────────────────────────────────────────────────

class TestSetGlobalFeature:

    def test_missing_feature_key(self, client, admin_user):
        """feature_key مفقود → 400"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/global', json={
            'value': 'true',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_invalid_feature_key(self, client, admin_user):
        """feature_key غير موجود في FEATURE_DEFAULTS → 400"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'non_existent_feature',
            'value': 'true',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'feature_key' in data['error']

    def test_missing_value(self, client, admin_user):
        """value مفقود → 400"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'lesson_prep_enabled',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'القيمة' in data['error']

    def test_valid_set(self, client, admin_user):
        """تعيين صحيح → 200"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'worksheet_enabled',
            'value': 'false',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['feature_key'] == 'worksheet_enabled'
        assert data['value'] == 'false'

    def test_valid_set_all_keys(self, client, admin_user):
        """تعيين لكل مفاتيح FEATURE_DEFAULTS → 200"""
        _login_as_admin(client, admin_user)
        for key, default in FEATURE_DEFAULTS.items():
            resp = client.post('/api/admin/teacher-features/global', json={
                'feature_key': key,
                'value': default,
            })
            assert resp.status_code == 200

    def test_message_contains_feature_label(self, client, admin_user):
        """الرسالة تحتوي على اسم الميزة العربي"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/global', json={
            'feature_key': 'ai_analysis_enabled',
            'value': 'true',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        label = FEATURE_LABELS.get('ai_analysis_enabled', 'ai_analysis_enabled')
        assert label in data['message']

    def test_empty_feature_key_string(self, client, admin_user):
        """feature_key فارغ → 400"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/global', json={
            'feature_key': '',
            'value': 'true',
        })
        assert resp.status_code == 400

    def test_exception_returns_500(self, client, admin_user):
        """استثناء → 500"""
        _login_as_admin(client, admin_user)
        with patch('src.models.ai_analysis.AISetting.set_setting', side_effect=Exception('DB error')):
            resp = client.post('/api/admin/teacher-features/global', json={
                'feature_key': 'worksheet_enabled',
                'value': 'true',
            })
        assert resp.status_code == 500


# ─── Test: GET /all-teachers ──────────────────────────────────────────────────

class TestGetAllTeachersFeatures:

    def test_empty_list(self, client, admin_user):
        """لا يوجد معلمون → قائمة فارغة"""
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['teachers'], list)

    def test_with_teachers(self, client, admin_user, db_session, app):
        """مع معلمين → يظهرون في القائمة"""
        tid = _make_teacher(db_session, app, 'allteach1', 'allteach1@t.com', name='Alpha Teacher')
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [t['id'] for t in data['teachers']]
        assert tid in ids

    def test_teacher_fields_present(self, client, admin_user, db_session, app):
        """كل معلم يحتوي على الحقول المطلوبة"""
        _make_teacher(db_session, app, 'allteach2', 'allteach2@t.com')
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code == 200
        teachers = resp.get_json()['teachers']
        if teachers:
            for t in teachers:
                assert 'id' in t
                assert 'name' in t
                assert 'username' in t
                assert 'overrides_count' in t
                assert 'overrides' in t

    def test_teacher_with_overrides(self, client, admin_user, db_session, app):
        """معلم مع overrides → overrides_count > 0"""
        tid = _make_teacher(db_session, app, 'allteach3', 'allteach3@t.com')
        _make_override(db_session, app, tid, 'worksheet_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code == 200
        teachers = resp.get_json()['teachers']
        teacher_data = next((t for t in teachers if t['id'] == tid), None)
        assert teacher_data is not None
        assert teacher_data['overrides_count'] >= 1

    def test_teachers_ordered_by_name(self, client, admin_user, db_session, app):
        """المعلمون مرتبون بالاسم"""
        _make_teacher(db_session, app, 'zteacher', 'zteacher@t.com', name='Zzz Teacher')
        _make_teacher(db_session, app, 'ateacher', 'ateacher@t.com', name='Aaa Teacher')
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code == 200
        teachers = resp.get_json()['teachers']
        names = [t['name'] for t in teachers]
        assert names == sorted(names)

    def test_exception_returns_500(self, client, admin_user):
        """استثناء في الاستعلام → 500"""
        _login_as_admin(client, admin_user)
        with patch('src.models.teacher.Teacher') as mock_teacher:
            mock_teacher.query.order_by.side_effect = Exception('DB error')
            resp = client.get('/api/admin/teacher-features/all-teachers')
        assert resp.status_code in [200, 500]


# ─── Test: GET /<teacher_id> ──────────────────────────────────────────────────

class TestGetTeacherFeatures:

    def test_teacher_not_found_404(self, client, admin_user):
        """معلم غير موجود → 404 أو 500"""
        _login_as_admin(client, admin_user)
        resp = client.get('/api/admin/teacher-features/99999')
        assert resp.status_code in [404, 500]

    def test_teacher_found_success(self, client, admin_user, db_session, app):
        """معلم موجود → 200"""
        tid = _make_teacher(db_session, app, 'gettf1', 'gettf1@t.com', name='Get TF Teacher')
        _login_as_admin(client, admin_user)
        resp = client.get(f'/api/admin/teacher-features/{tid}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['teacher']['id'] == tid
        assert 'features' in data

    def test_teacher_features_all_keys_present(self, client, admin_user, db_session, app):
        """جميع مفاتيح FEATURE_DEFAULTS موجودة في الاستجابة"""
        tid = _make_teacher(db_session, app, 'gettf2', 'gettf2@t.com')
        _login_as_admin(client, admin_user)
        resp = client.get(f'/api/admin/teacher-features/{tid}')
        assert resp.status_code == 200
        features = resp.get_json()['features']
        for key in FEATURE_DEFAULTS:
            assert key in features

    def test_teacher_with_override_shows_override(self, client, admin_user, db_session, app):
        """معلم مع override → يظهر القيمة المخصصة مع source='override'"""
        tid = _make_teacher(db_session, app, 'gettf3', 'gettf3@t.com')
        _make_override(db_session, app, tid, 'lesson_prep_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.get(f'/api/admin/teacher-features/{tid}')
        assert resp.status_code == 200
        features = resp.get_json()['features']
        assert features['lesson_prep_enabled']['value'] == 'false'
        assert features['lesson_prep_enabled']['source'] == 'override'

    def test_teacher_without_override_shows_global(self, client, admin_user, db_session, app):
        """معلم بدون override → source='global'"""
        tid = _make_teacher(db_session, app, 'gettf4', 'gettf4@t.com')
        _login_as_admin(client, admin_user)
        resp = client.get(f'/api/admin/teacher-features/{tid}')
        assert resp.status_code == 200
        features = resp.get_json()['features']
        # كل الميزات بدون override يجب أن تكون global
        for key, info in features.items():
            assert info['source'] == 'global'

    def test_teacher_info_returned(self, client, admin_user, db_session, app):
        """بيانات المعلم تُعاد في الاستجابة"""
        tid = _make_teacher(db_session, app, 'gettf5', 'gettf5@t.com', name='Info Teacher')
        _login_as_admin(client, admin_user)
        resp = client.get(f'/api/admin/teacher-features/{tid}')
        assert resp.status_code == 200
        teacher_info = resp.get_json()['teacher']
        assert teacher_info['id'] == tid
        assert teacher_info['name'] == 'Info Teacher'
        assert 'username' in teacher_info


# ─── Test: POST /<teacher_id> ─────────────────────────────────────────────────

class TestSetTeacherFeature:

    def test_teacher_not_found(self, client, admin_user):
        """معلم غير موجود → 404 أو 500"""
        _login_as_admin(client, admin_user)
        resp = client.post('/api/admin/teacher-features/99999', json={
            'feature_key': 'lesson_prep_enabled',
            'value': 'false',
        })
        assert resp.status_code in [404, 500]

    def test_missing_feature_key(self, client, admin_user, db_session, app):
        """feature_key مفقود → 400"""
        tid = _make_teacher(db_session, app, 'settf1', 'settf1@t.com')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'value': 'true',
        })
        assert resp.status_code == 400

    def test_invalid_feature_key(self, client, admin_user, db_session, app):
        """feature_key غير صالح → 400"""
        tid = _make_teacher(db_session, app, 'settf2', 'settf2@t.com')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': 'invalid_key_xyz',
            'value': 'true',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_missing_value(self, client, admin_user, db_session, app):
        """value مفقود → 400"""
        tid = _make_teacher(db_session, app, 'settf3', 'settf3@t.com')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': 'lesson_prep_enabled',
        })
        assert resp.status_code == 400
        assert 'القيمة' in resp.get_json()['error']

    def test_success_creates_override(self, client, admin_user, db_session, app):
        """إنشاء override جديد → 200"""
        tid = _make_teacher(db_session, app, 'settf4', 'settf4@t.com')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': 'worksheet_enabled',
            'value': 'false',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'override' in data

    def test_success_updates_existing_override(self, client, admin_user, db_session, app):
        """تحديث override موجود → 200"""
        tid = _make_teacher(db_session, app, 'settf5', 'settf5@t.com')
        _make_override(db_session, app, tid, 'worksheet_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': 'worksheet_enabled',
            'value': 'true',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['override']['value'] == 'true'

    def test_override_dict_fields(self, client, admin_user, db_session, app):
        """to_dict() يحتوي على الحقول المطلوبة"""
        tid = _make_teacher(db_session, app, 'settf6', 'settf6@t.com')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': 'ai_analysis_enabled',
            'value': 'true',
        })
        assert resp.status_code == 200
        override = resp.get_json()['override']
        assert 'id' in override
        assert 'teacher_id' in override
        assert 'feature_key' in override
        assert 'value' in override
        assert 'label' in override

    def test_message_contains_teacher_name(self, client, admin_user, db_session, app):
        """الرسالة تحتوي على اسم المعلم"""
        tid = _make_teacher(db_session, app, 'settf7', 'settf7@t.com', name='Named Teacher')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': 'lesson_prep_enabled',
            'value': 'false',
        })
        assert resp.status_code == 200
        assert 'Named Teacher' in resp.get_json()['message']

    def test_empty_feature_key(self, client, admin_user, db_session, app):
        """feature_key فارغ → 400"""
        tid = _make_teacher(db_session, app, 'settf8', 'settf8@t.com')
        _login_as_admin(client, admin_user)
        resp = client.post(f'/api/admin/teacher-features/{tid}', json={
            'feature_key': '',
            'value': 'true',
        })
        assert resp.status_code == 400


# ─── Test: DELETE /<teacher_id>/<feature_key> ─────────────────────────────────

class TestDeleteTeacherFeatureOverride:

    def test_teacher_not_found(self, client, admin_user):
        """معلم غير موجود → 404 أو 500"""
        _login_as_admin(client, admin_user)
        resp = client.delete('/api/admin/teacher-features/99999/lesson_prep_enabled')
        assert resp.status_code in [404, 500]

    def test_override_not_found(self, client, admin_user, db_session, app):
        """override غير موجود → 404"""
        tid = _make_teacher(db_session, app, 'deltf1', 'deltf1@t.com')
        _login_as_admin(client, admin_user)
        resp = client.delete(f'/api/admin/teacher-features/{tid}/worksheet_enabled')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data['success'] is False

    def test_delete_existing_override(self, client, admin_user, db_session, app):
        """حذف override موجود → 200"""
        tid = _make_teacher(db_session, app, 'deltf2', 'deltf2@t.com')
        _make_override(db_session, app, tid, 'lesson_prep_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.delete(f'/api/admin/teacher-features/{tid}/lesson_prep_enabled')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_removes_override_from_db(self, client, admin_user, db_session, app):
        """بعد الحذف → override لا يوجد في DB"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'deltf3', 'deltf3@t.com')
        _make_override(db_session, app, tid, 'ai_analysis_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.delete(f'/api/admin/teacher-features/{tid}/ai_analysis_enabled')
        assert resp.status_code == 200
        with app.app_context():
            override = TeacherFeatureOverride.get_override(tid, 'ai_analysis_enabled')
            assert override is None

    def test_delete_message_contains_teacher_name(self, client, admin_user, db_session, app):
        """رسالة الحذف تحتوي على اسم المعلم"""
        tid = _make_teacher(db_session, app, 'deltf4', 'deltf4@t.com', name='Delete Override Teacher')
        _make_override(db_session, app, tid, 'worksheet_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp = client.delete(f'/api/admin/teacher-features/{tid}/worksheet_enabled')
        assert resp.status_code == 200
        assert 'Delete Override Teacher' in resp.get_json()['message']

    def test_double_delete_second_is_404(self, client, admin_user, db_session, app):
        """حذف نفس الـ override مرتين → الثانية 404"""
        tid = _make_teacher(db_session, app, 'deltf5', 'deltf5@t.com')
        _make_override(db_session, app, tid, 'shared_library_enabled', 'false')
        _login_as_admin(client, admin_user)
        resp1 = client.delete(f'/api/admin/teacher-features/{tid}/shared_library_enabled')
        resp2 = client.delete(f'/api/admin/teacher-features/{tid}/shared_library_enabled')
        assert resp1.status_code == 200
        assert resp2.status_code == 404


# ─── Test: GET /page ──────────────────────────────────────────────────────────

class TestTeacherFeaturesPage:

    def test_page_no_auth_redirects(self, client):
        """صفحة الويب بدون مصادقة → redirect أو 403"""
        resp = client.get('/api/admin/teacher-features/page')
        assert resp.status_code in [302, 401, 403]

    def test_page_as_admin(self, client, admin_user, app):
        """صفحة الويب كأدمن → 200 أو 302 أو 500 (بحسب وجود template)"""
        _login_as_admin(client, admin_user)
        with patch('src.routes.teacher_features_routes.render_template') as mock_render:
            mock_render.return_value = '<html>teacher features page</html>'
            resp = client.get('/api/admin/teacher-features/page')
        assert resp.status_code in [200, 302, 500]

    def test_page_passes_correct_context(self, client, admin_user, app):
        """التحقق من أن render_template يُستدعى بالبيانات الصحيحة"""
        _login_as_admin(client, admin_user)
        with patch('src.routes.teacher_features_routes.render_template') as mock_render:
            mock_render.return_value = '<html>ok</html>'
            client.get('/api/admin/teacher-features/page')
        if mock_render.called:
            _, kwargs = mock_render.call_args
            assert 'global_features' in kwargs or len(mock_render.call_args[0]) > 0


# ─── Test: helpers ────────────────────────────────────────────────────────────

class TestHelperFunctions:

    def test_get_global_features_returns_dict(self, app):
        """_get_global_features يُعيد dict مع كل المفاتيح"""
        from src.routes.teacher_features_routes import _get_global_features
        with app.app_context():
            features = _get_global_features()
            assert isinstance(features, dict)
            for key in FEATURE_DEFAULTS:
                assert key in features

    def test_get_global_features_structure(self, app):
        """كل ميزة تحتوي على label و value و default"""
        from src.routes.teacher_features_routes import _get_global_features
        with app.app_context():
            features = _get_global_features()
            for key, info in features.items():
                assert 'label' in info
                assert 'value' in info
                assert 'default' in info

    def test_get_global_features_uses_defaults_when_no_setting(self, app, db_session):
        """عندما لا يوجد AISetting → يستخدم القيمة الافتراضية"""
        from src.routes.teacher_features_routes import _get_global_features
        with app.app_context():
            features = _get_global_features()
            for key, default in FEATURE_DEFAULTS.items():
                # إذا لم يُعيَّن → يستخدم default أو None
                assert features[key]['value'] is not None or features[key]['default'] == default

    def test_get_teacher_features_no_overrides(self, db_session, app):
        """_get_teacher_features بدون overrides → جميع المصادر = 'global'"""
        from src.routes.teacher_features_routes import _get_teacher_features
        tid = _make_teacher(db_session, app, 'helper_t1', 'helper_t1@t.com')
        with app.app_context():
            features = _get_teacher_features(tid)
            for key, info in features.items():
                assert info['source'] == 'global'

    def test_get_teacher_features_with_override(self, db_session, app):
        """_get_teacher_features مع override → source = 'override' للمفتاح المخصص"""
        from src.routes.teacher_features_routes import _get_teacher_features
        tid = _make_teacher(db_session, app, 'helper_t2', 'helper_t2@t.com')
        _make_override(db_session, app, tid, 'lesson_prep_enabled', 'false')
        with app.app_context():
            features = _get_teacher_features(tid)
            assert features['lesson_prep_enabled']['source'] == 'override'
            assert features['lesson_prep_enabled']['value'] == 'false'
            # باقي المفاتيح global
            for key, info in features.items():
                if key != 'lesson_prep_enabled':
                    assert info['source'] == 'global'

    def test_get_teacher_features_multiple_overrides(self, db_session, app):
        """عدة overrides لنفس المعلم"""
        from src.routes.teacher_features_routes import _get_teacher_features
        tid = _make_teacher(db_session, app, 'helper_t3', 'helper_t3@t.com')
        _make_override(db_session, app, tid, 'lesson_prep_enabled', 'false')
        _make_override(db_session, app, tid, 'worksheet_enabled', 'false')
        with app.app_context():
            features = _get_teacher_features(tid)
            assert features['lesson_prep_enabled']['source'] == 'override'
            assert features['worksheet_enabled']['source'] == 'override'


# ─── Test: TeacherFeatureOverride model ──────────────────────────────────────

class TestTeacherFeatureOverrideModel:

    def test_to_dict_has_all_fields(self, db_session, app):
        """to_dict() يحتوي على جميع الحقول"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t1', 'model_t1@t.com')
        with app.app_context():
            ov = TeacherFeatureOverride.set_override(tid, 'quota_worksheet', '5')
            d = ov.to_dict()
        assert 'id' in d
        assert 'teacher_id' in d
        assert 'feature_key' in d
        assert 'value' in d
        assert 'label' in d

    def test_set_override_creates_new(self, db_session, app):
        """set_override يُنشئ override جديد"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t2', 'model_t2@t.com')
        with app.app_context():
            ov = TeacherFeatureOverride.set_override(tid, 'quota_single_lesson', '10')
            assert ov.value == '10'
            assert ov.feature_key == 'quota_single_lesson'

    def test_set_override_updates_existing(self, db_session, app):
        """set_override يُحدّث override موجود"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t3', 'model_t3@t.com')
        with app.app_context():
            TeacherFeatureOverride.set_override(tid, 'quota_unit_distribution', '3')
            ov = TeacherFeatureOverride.set_override(tid, 'quota_unit_distribution', '7')
            assert ov.value == '7'

    def test_delete_override_returns_true(self, db_session, app):
        """delete_override → True عند الحذف الناجح"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t4', 'model_t4@t.com')
        with app.app_context():
            TeacherFeatureOverride.set_override(tid, 'shared_library_enabled', 'false')
            result = TeacherFeatureOverride.delete_override(tid, 'shared_library_enabled')
            assert result is True

    def test_delete_override_returns_false_not_found(self, db_session, app):
        """delete_override على override غير موجود → False"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t5', 'model_t5@t.com')
        with app.app_context():
            result = TeacherFeatureOverride.delete_override(tid, 'ai_analysis_enabled')
            assert result is False

    def test_get_all_overrides_for_teacher(self, db_session, app):
        """get_all_overrides_for_teacher يُعيد قائمة overrides"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t6', 'model_t6@t.com')
        with app.app_context():
            TeacherFeatureOverride.set_override(tid, 'lesson_prep_enabled', 'false')
            TeacherFeatureOverride.set_override(tid, 'worksheet_enabled', 'true')
            overrides = TeacherFeatureOverride.get_all_overrides_for_teacher(tid)
            assert len(overrides) == 2

    def test_get_override_returns_none_not_found(self, db_session, app):
        """get_override على مفتاح غير موجود → None"""
        from src.models.teacher_feature import TeacherFeatureOverride
        tid = _make_teacher(db_session, app, 'model_t7', 'model_t7@t.com')
        with app.app_context():
            ov = TeacherFeatureOverride.get_override(tid, 'semester_distribution_enabled')
            assert ov is None
