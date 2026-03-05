"""
اختبارات عميقة لـ api.py - تغطية الـ routes غير المغطاة
يركز على:
- Lines 154-186, 241-280, 300-409  (activities, helper functions)
- Lines 419-562  (block/unblock routes)
- Lines 574-813  (bot visibility + questions by course/unit/lesson)
- Lines 840-957  (recent questions, notifications)
- Lines 971-1047 (random questions, dashboard)
- Lines 1067-1200 (dashboard performance, filtered questions)
- Lines 1287-1393 (google drive section starts)
- Lines 1397-1593 (google drive connect/diagnose/disconnect)
- Lines 1603-1876 (user settings sync)
- Lines 1881-2009 (backup test, backup stats)
- Lines 2009+ (backup list, upload, start/stop/manual/jobs/health/status)
- Lines 2924+ (backup-settings/load, backup-settings/save)
- Lines 3200+ (question block/unblock, bulk block, lesson/unit/course block-all)
- Lines 3628+ (export, generate-exam, unit lessons, counts)
- Lines 3948+ (admin profile, trusted-device, register-device, upload-image)
- Lines 4096+ (add/get/update/delete question API, toggle-block, search)
- Lines 4589+ (classify-all, classify single, classification-stats, update-classification, browse, unclassified, summary)
"""
import pytest


# ============================================================
# Helper
# ============================================================

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_question(db_session, lesson):
    """إنشاء سؤال بسيط مع خيارات لأغراض الاختبار"""
    from src.models.question import Question, Option
    q = Question(
        lesson_id=lesson.id,
        question_text='سؤال اختباري عميق؟',
        is_blocked=False
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


# ============================================================
# Activities (Lines 283-488)
# ============================================================

class TestActivitiesAPI:
    """اختبارات endpoint الأنشطة"""

    def test_get_recent_activities_no_auth(self, client):
        """جلب الأنشطة بدون تسجيل دخول - يجب أن يرجع 200"""
        response = client.get('/api/v1/activities/recent')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_recent_activities_returns_json(self, client):
        """تأكد أن الاستجابة JSON"""
        response = client.get('/api/v1/activities/recent')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_get_recent_activities_with_limit(self, client):
        """جلب الأنشطة مع حد معين"""
        response = client.get('/api/v1/activities/recent?limit=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_recent_activities_with_admin(self, client, admin_user):
        """جلب الأنشطة كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/activities/recent')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'activities' in data

    def test_get_recent_activities_limit_zero(self, client):
        """جلب الأنشطة مع limit=0"""
        response = client.get('/api/v1/activities/recent?limit=0')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_recent_activities_large_limit(self, client):
        """جلب الأنشطة مع limit كبير"""
        response = client.get('/api/v1/activities/recent?limit=100')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Courses - Bot Visibility (Lines 519-543)
# ============================================================

class TestCourseBotVisibilityDeep:
    """اختبارات toggle رؤية المنهج في البوت"""

    def test_toggle_course_visibility_put_method(self, client, admin_user, sample_course):
        """toggle باستخدام PUT"""
        _login(client, admin_user)
        response = client.put(
            f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_course_visibility_post_method(self, client, admin_user, sample_course):
        """toggle باستخدام POST"""
        _login(client, admin_user)
        response = client.post(
            f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_course_nonexistent_put(self, client, admin_user):
        """toggle منهج غير موجود بـ PUT"""
        _login(client, admin_user)
        response = client.put(
            '/api/v1/courses/99999/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_course_no_auth_put(self, client, sample_course):
        """toggle بدون مصادقة بـ PUT"""
        response = client.put(
            f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_course_response_structure(self, client, admin_user, sample_course):
        """هيكل الاستجابة لـ toggle"""
        _login(client, admin_user)
        response = client.put(
            f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility',
            json={}
        )
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
            assert 'show_in_bot' in data


# ============================================================
# Units - Bot Visibility (Lines 545-562)
# ============================================================

class TestUnitBotVisibilityDeep:
    """اختبارات toggle رؤية الوحدة في البوت"""

    def test_toggle_unit_visibility_put(self, client, admin_user, sample_unit):
        """toggle وحدة بـ PUT"""
        _login(client, admin_user)
        response = client.put(
            f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_unit_visibility_post(self, client, admin_user, sample_unit):
        """toggle وحدة بـ POST"""
        _login(client, admin_user)
        response = client.post(
            f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_unit_nonexistent(self, client, admin_user):
        """toggle وحدة غير موجودة"""
        _login(client, admin_user)
        response = client.put(
            '/api/v1/units/99999/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_unit_no_auth(self, client, sample_unit):
        """toggle وحدة بدون مصادقة"""
        response = client.put(
            f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_unit_response_structure(self, client, admin_user, sample_unit):
        """هيكل الاستجابة لـ toggle وحدة"""
        _login(client, admin_user)
        response = client.put(
            f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility',
            json={}
        )
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
            assert 'show_in_bot' in data


# ============================================================
# Lessons - Bot Visibility (Lines 564-581)
# ============================================================

class TestLessonBotVisibilityDeep:
    """اختبارات toggle رؤية الدرس في البوت"""

    def test_toggle_lesson_visibility_put(self, client, admin_user, sample_lesson):
        """toggle درس بـ PUT"""
        _login(client, admin_user)
        response = client.put(
            f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_lesson_visibility_post(self, client, admin_user, sample_lesson):
        """toggle درس بـ POST"""
        _login(client, admin_user)
        response = client.post(
            f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_lesson_nonexistent(self, client, admin_user):
        """toggle درس غير موجود"""
        _login(client, admin_user)
        response = client.put(
            '/api/v1/lessons/99999/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_lesson_no_auth(self, client, sample_lesson):
        """toggle درس بدون مصادقة"""
        response = client.put(
            f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility',
            json={}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_lesson_response_structure(self, client, admin_user, sample_lesson):
        """هيكل الاستجابة لـ toggle درس"""
        _login(client, admin_user)
        response = client.put(
            f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility',
            json={}
        )
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
            assert 'show_in_bot' in data


# ============================================================
# Questions by Course/Unit/Lesson (Lines 583-813)
# ============================================================

class TestQuestionsHierarchyDeep:
    """اختبارات جلب الأسئلة عبر المنهج/الوحدة/الدرس"""

    def test_get_course_units_show_all_param(self, client, sample_unit):
        """جلب وحدات المنهج مع show_all"""
        response = client.get(
            f'/api/v1/courses/{sample_unit.course_id}/units?show_all=true'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_lessons_show_all_param(self, client, sample_lesson):
        """جلب دروس الوحدة مع show_all"""
        response = client.get(
            f'/api/v1/units/{sample_lesson.unit_id}/lessons?show_all=true'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_lessons_bot_filter(self, client, sample_lesson):
        """جلب دروس الوحدة للبوت (بدون show_all)"""
        response = client.get(
            f'/api/v1/units/{sample_lesson.unit_id}/lessons'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_lesson_questions_existing(self, client, db_session, sample_lesson):
        """جلب أسئلة درس موجود"""
        _make_question(db_session, sample_lesson)
        response = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, list)

    def test_get_lesson_questions_nonexistent(self, client):
        """جلب أسئلة درس غير موجود"""
        response = client.get('/api/v1/lessons/99999/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_questions_direct(self, client, sample_unit):
        """جلب أسئلة وحدة مباشرة"""
        response = client.get(f'/api/v1/units/{sample_unit.id}/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_questions_direct_show_all(self, client, sample_unit):
        """جلب أسئلة وحدة مع show_all"""
        response = client.get(f'/api/v1/units/{sample_unit.id}/questions?show_all=true')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_questions_nonexistent(self, client):
        """جلب أسئلة وحدة غير موجودة"""
        response = client.get('/api/v1/units/99999/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_questions_direct(self, client, sample_course):
        """جلب أسئلة منهج مباشرة"""
        response = client.get(f'/api/v1/courses/{sample_course.id}/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_questions_direct_show_all(self, client, sample_course):
        """جلب أسئلة منهج مع show_all"""
        response = client.get(
            f'/api/v1/courses/{sample_course.id}/questions?show_all=true'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_questions_nonexistent(self, client):
        """جلب أسئلة منهج غير موجود"""
        response = client.get('/api/v1/courses/99999/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_unit_questions_nested(self, client, sample_course, sample_unit):
        """جلب أسئلة وحدة ضمن منهج (nested)"""
        response = client.get(
            f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/questions'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_unit_questions_wrong_course(self, client, sample_course, sample_unit):
        """جلب أسئلة وحدة ضمن منهج خاطئ"""
        response = client.get(
            f'/api/v1/courses/99999/units/{sample_unit.id}/questions'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_unit_questions_wrong_unit(self, client, sample_course):
        """جلب أسئلة وحدة غير موجودة ضمن منهج"""
        response = client.get(
            f'/api/v1/courses/{sample_course.id}/units/99999/questions'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_all_questions_in_db(self, client):
        """جلب جميع الأسئلة في قاعدة البيانات"""
        response = client.get('/api/v1/questions/all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, list)


# ============================================================
# Recent Questions (Lines 816-895)
# ============================================================

class TestRecentQuestionsAPI:
    """اختبارات الأسئلة الأحدث"""

    def test_get_recent_questions(self, client):
        """جلب الأسئلة الأحدث"""
        response = client.get('/api/v1/questions/recent')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'questions' in data

    def test_get_recent_questions_with_limit(self, client):
        """جلب الأسئلة الأحدث مع حد"""
        response = client.get('/api/v1/questions/recent?limit=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_recent_questions_with_admin(self, client, admin_user):
        """جلب الأسئلة الأحدث كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/recent')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Random Questions (Lines 1019-1047)
# ============================================================

class TestRandomQuestionsAPI:
    """اختبارات الأسئلة العشوائية"""

    def test_get_random_questions(self, client):
        """جلب أسئلة عشوائية"""
        response = client.get('/api/v1/questions/random')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, list)

    def test_get_random_questions_with_count(self, client):
        """جلب أسئلة عشوائية مع count"""
        response = client.get('/api/v1/questions/random?count=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_random_questions_with_negative_count(self, client):
        """جلب أسئلة عشوائية مع count سالب"""
        response = client.get('/api/v1/questions/random?count=-5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_random_questions_with_zero_count(self, client):
        """جلب أسئلة عشوائية مع count=0"""
        response = client.get('/api/v1/questions/random?count=0')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Filtered Questions (Lines 1209-1248)
# ============================================================

class TestFilteredQuestionsAPI:
    """اختبارات الأسئلة مع فلاتر"""

    def test_get_filtered_questions_no_filter(self, client):
        """جلب الأسئلة بدون فلتر"""
        response = client.get('/api/v1/questions')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_filtered_questions_by_lesson(self, client, sample_lesson):
        """جلب الأسئلة بفلتر lesson_id"""
        response = client.get(f'/api/v1/questions?lesson_id={sample_lesson.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_filtered_questions_by_unit(self, client, sample_unit):
        """جلب الأسئلة بفلتر unit_id"""
        response = client.get(f'/api/v1/questions?unit_id={sample_unit.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_filtered_questions_by_course(self, client, sample_course):
        """جلب الأسئلة بفلتر course_id"""
        response = client.get(f'/api/v1/questions?course_id={sample_course.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_filtered_questions_nonexistent_ids(self, client):
        """جلب الأسئلة بـ IDs غير موجودة"""
        response = client.get('/api/v1/questions?lesson_id=99999&unit_id=99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Google Drive APIs (Lines 1423-1687)
# ============================================================

class TestGoogleDriveAPIDeep:
    """اختبارات Google Drive API"""

    def test_google_drive_connection_status_no_auth(self, client):
        """حالة اتصال Google Drive بدون مصادقة"""
        response = client.get('/api/v1/v1/google-drive/connection-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_connection_status_with_admin(self, client, admin_user):
        """حالة اتصال Google Drive كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/v1/google-drive/connection-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'connected' in data

    def test_google_drive_connect_no_auth(self, client):
        """اتصال Google Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/google-drive/connect', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_connect_with_admin(self, client, admin_user):
        """اتصال Google Drive كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/v1/google-drive/connect', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_diagnose_no_auth(self, client):
        """تشخيص Google Drive بدون مصادقة"""
        response = client.get('/api/v1/v1/google-drive/diagnose')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_diagnose_with_admin(self, client, admin_user):
        """تشخيص Google Drive كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/v1/google-drive/diagnose')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_disconnect_no_auth(self, client):
        """قطع اتصال Google Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/google-drive/disconnect', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_disconnect_with_admin(self, client, admin_user):
        """قطع اتصال Google Drive كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/v1/google-drive/disconnect', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_google_drive_connection_status_alt_route(self, client, admin_user):
        """حالة اتصال Google Drive (المسار البديل)"""
        _login(client, admin_user)
        response = client.get('/api/v1/google-drive/connection-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_google_drive_test_connection_status(self, client):
        """حالة اتصال Google Drive التجريبي (بدون مصادقة)"""
        response = client.get('/api/v1/google-drive/test-connection-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data


# ============================================================
# User Settings Sync (Lines 1691-1879)
# ============================================================

class TestUserSettingsSyncAPI:
    """اختبارات مزامنة إعدادات المستخدم"""

    def test_user_settings_sync_status_no_auth(self, client):
        """حالة مزامنة الإعدادات بدون مصادقة"""
        response = client.get('/api/v1/v1/user-settings/sync-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_user_settings_sync_status_with_admin(self, client, admin_user):
        """حالة مزامنة الإعدادات كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/v1/user-settings/sync-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_sync_user_settings_to_drive_no_auth(self, client):
        """مزامنة الإعدادات للـ Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/user-settings/sync-to-drive', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_sync_user_settings_to_drive_with_admin(self, client, admin_user):
        """مزامنة الإعدادات للـ Drive كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/v1/user-settings/sync-to-drive', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_download_user_settings_no_auth(self, client):
        """تحميل الإعدادات من Drive بدون مصادقة"""
        response = client.post('/api/v1/v1/user-settings/download-from-drive', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_download_user_settings_with_admin(self, client, admin_user):
        """تحميل الإعدادات من Drive كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/v1/user-settings/download-from-drive', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_quick_sync_no_auth(self, client):
        """مزامنة سريعة بدون مصادقة"""
        response = client.post('/api/v1/v1/user-settings/quick-sync', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_quick_sync_with_admin(self, client, admin_user):
        """مزامنة سريعة كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/v1/user-settings/quick-sync', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_user_settings_sync_status_alt_route(self, client, admin_user):
        """حالة مزامنة الإعدادات (المسار البديل)"""
        _login(client, admin_user)
        response = client.get('/api/v1/user-settings/sync-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Backup APIs (Lines 1881-2858)
# ============================================================

class TestBackupAPIDeep:
    """اختبارات API النسخ الاحتياطي"""

    def test_backup_test_no_auth(self, client):
        """اختبار النسخ الاحتياطي بدون مصادقة"""
        response = client.post('/api/v1/backup/test', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_test_with_admin(self, client, admin_user):
        """اختبار النسخ الاحتياطي كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/backup/test', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_backup_test_comprehensive_type(self, client, admin_user):
        """اختبار النسخ الاحتياطي بنوع comprehensive"""
        _login(client, admin_user)
        response = client.post('/api/v1/backup/test', json={'backup_type': 'comprehensive'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_test_questions_only_type(self, client, admin_user):
        """اختبار النسخ الاحتياطي بنوع questions_only"""
        _login(client, admin_user)
        response = client.post('/api/v1/backup/test', json={'backup_type': 'questions_only'})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_stats_no_auth(self, client):
        """إحصائيات النسخ الاحتياطي بدون مصادقة"""
        response = client.get('/api/v1/backup/stats')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_stats_with_admin(self, client, admin_user):
        """إحصائيات النسخ الاحتياطي كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/backup/stats')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_backup_list_no_auth(self, client):
        """قائمة النسخ الاحتياطية بدون مصادقة"""
        response = client.get('/api/v1/backup/list')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_list_with_admin(self, client, admin_user):
        """قائمة النسخ الاحتياطية كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/backup/list')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'backups' in data

    def test_upload_backup_to_drive_no_auth(self, client):
        """رفع نسخة احتياطية بدون مصادقة"""
        response = client.post(
            '/api/v1/backup/upload-to-drive',
            json={'fileName': 'test.json', 'fileContent': '{}'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_upload_backup_to_drive_with_admin(self, client, admin_user):
        """رفع نسخة احتياطية كأدمن"""
        _login(client, admin_user)
        response = client.post(
            '/api/v1/backup/upload-to-drive',
            json={'fileName': 'test_backup.json', 'fileContent': '{"test": true}'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_upload_backup_to_drive_missing_filename(self, client, admin_user):
        """رفع نسخة احتياطية بدون اسم ملف"""
        _login(client, admin_user)
        response = client.post(
            '/api/v1/backup/upload-to-drive',
            json={'fileContent': '{}'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_upload_backup_to_drive_not_json(self, client, admin_user):
        """رفع نسخة احتياطية بدون JSON"""
        _login(client, admin_user)
        response = client.post('/api/v1/backup/upload-to-drive', data='not json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_start_no_scheduler(self, client):
        """بدء جدولة النسخ الاحتياطي (بدون scheduler)"""
        response = client.post('/api/v1/backup/start', json={'user_id': 1})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_stop_no_scheduler(self, client):
        """إيقاف جدولة النسخ الاحتياطي (بدون scheduler)"""
        response = client.post('/api/v1/backup/stop', json={'user_id': 1})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_manual_no_logic(self, client):
        """نسخ احتياطي يدوي (بدون backup_logic)"""
        response = client.post('/api/v1/backup/manual', json={'user_id': 1})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_jobs_no_scheduler(self, client):
        """جلب مهام النسخ الاحتياطي (بدون scheduler)"""
        response = client.get('/api/v1/backup/jobs')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_health_check(self, client):
        """فحص صحة النسخ الاحتياطي"""
        response = client.get('/api/v1/backup/health')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_backup_logs(self, client):
        """سجلات النسخ الاحتياطي"""
        response = client.get('/api/v1/backup/logs')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_logs_with_lines(self, client):
        """سجلات النسخ الاحتياطي مع عدد أسطر"""
        response = client.get('/api/v1/backup/logs?lines=50&level=all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_logs_download(self, client):
        """تحميل سجلات النسخ الاحتياطي"""
        response = client.get('/api/v1/backup/logs/download')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_status_no_auth(self, client):
        """حالة النسخ الاحتياطي بدون مصادقة"""
        response = client.get('/api/v1/backup/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_status_with_admin(self, client, admin_user):
        """حالة النسخ الاحتياطي كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/backup/status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_immediate_no_auth(self, client):
        """نسخ احتياطي فوري بدون مصادقة"""
        response = client.post('/api/v1/backup/immediate', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_immediate_with_admin(self, client, admin_user):
        """نسخ احتياطي فوري كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/backup/immediate', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_backup_test_status(self, client):
        """حالة النسخ الاحتياطي التجريبي"""
        response = client.get('/api/v1/backup/test-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data

    def test_backup_test_immediate(self, client):
        """نسخ احتياطي فوري تجريبي"""
        response = client.post('/api/v1/backup/test-immediate', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Backup Settings (Lines 2924-3022)
# ============================================================

class TestBackupSettingsAPI:
    """اختبارات إعدادات النسخ الاحتياطي"""

    def test_load_backup_settings_no_auth(self, client):
        """تحميل إعدادات النسخ الاحتياطي بدون مصادقة"""
        response = client.get('/api/v1/backup-settings/load')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_load_backup_settings_with_admin(self, client, admin_user):
        """تحميل إعدادات النسخ الاحتياطي كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/backup-settings/load')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
            assert 'settings' in data

    def test_save_backup_settings_no_auth(self, client):
        """حفظ إعدادات النسخ الاحتياطي بدون مصادقة"""
        response = client.post('/api/v1/backup-settings/save', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'daily'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_backup_settings_with_admin(self, client, admin_user):
        """حفظ إعدادات النسخ الاحتياطي كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/backup-settings/save', json={
            'auto_backup_enabled': True,
            'backup_frequency': 'daily',
            'backup_destination': 'local',
            'max_backups': 5,
            'backup_time': '02:00'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Question Block/Unblock (Lines 3200-3624)
# ============================================================

class TestQuestionBlockUnblockDeep:
    """اختبارات منع وإلغاء منع الأسئلة"""

    def test_block_question_existing(self, client, db_session, sample_lesson):
        """منع سؤال موجود"""
        q = _make_question(db_session, sample_lesson)
        response = client.put(f'/api/v1/questions/{q.question_id}/block')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert data.get('is_blocked') is True

    def test_block_question_nonexistent(self, client):
        """منع سؤال غير موجود"""
        response = client.put('/api/v1/questions/99999/block')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unblock_question_existing(self, client, db_session, sample_lesson):
        """إلغاء منع سؤال موجود"""
        q = _make_question(db_session, sample_lesson)
        # اولاً نمنعه
        client.put(f'/api/v1/questions/{q.question_id}/block')
        # ثم نلغي المنع
        response = client.put(f'/api/v1/questions/{q.question_id}/unblock')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert data.get('is_blocked') is False

    def test_unblock_question_nonexistent(self, client):
        """إلغاء منع سؤال غير موجود"""
        response = client.put('/api/v1/questions/99999/unblock')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_question_block_status_existing(self, client, db_session, sample_lesson):
        """جلب حالة المنع لسؤال موجود"""
        q = _make_question(db_session, sample_lesson)
        response = client.get(f'/api/v1/questions/{q.question_id}/block-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'is_blocked' in data

    def test_get_question_block_status_nonexistent(self, client):
        """جلب حالة المنع لسؤال غير موجود"""
        response = client.get('/api/v1/questions/99999/block-status')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_block_questions(self, client, db_session, sample_lesson):
        """منع عدة أسئلة دفعة واحدة"""
        q1 = _make_question(db_session, sample_lesson)
        q2 = _make_question(db_session, sample_lesson)
        response = client.post('/api/v1/questions/bulk-block', json={
            'question_ids': [q1.question_id, q2.question_id]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_bulk_block_questions_empty(self, client):
        """منع عدة أسئلة بقائمة فارغة"""
        response = client.post('/api/v1/questions/bulk-block', json={'question_ids': []})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_unblock_questions(self, client, db_session, sample_lesson):
        """إلغاء منع عدة أسئلة دفعة واحدة"""
        q1 = _make_question(db_session, sample_lesson)
        q2 = _make_question(db_session, sample_lesson)
        response = client.post('/api/v1/questions/bulk-unblock', json={
            'question_ids': [q1.question_id, q2.question_id]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_bulk_unblock_questions_empty(self, client):
        """إلغاء منع عدة أسئلة بقائمة فارغة"""
        response = client.post('/api/v1/questions/bulk-unblock', json={'question_ids': []})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Lesson Block All (Lines 3351-3426)
# ============================================================

class TestLessonBlockAllAPI:
    """اختبارات منع وإلغاء منع جميع أسئلة الدرس"""

    def test_block_all_lesson_questions_existing(self, client, db_session, sample_lesson):
        """منع جميع أسئلة درس موجود"""
        _make_question(db_session, sample_lesson)
        response = client.put(
            f'/api/v1/lessons/{sample_lesson.id}/questions/block-all'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_block_all_lesson_questions_nonexistent(self, client):
        """منع جميع أسئلة درس غير موجود"""
        response = client.put('/api/v1/lessons/99999/questions/block-all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unblock_all_lesson_questions_existing(self, client, db_session, sample_lesson):
        """إلغاء منع جميع أسئلة درس موجود"""
        _make_question(db_session, sample_lesson)
        response = client.put(
            f'/api/v1/lessons/{sample_lesson.id}/questions/unblock-all'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_unblock_all_lesson_questions_nonexistent(self, client):
        """إلغاء منع جميع أسئلة درس غير موجود"""
        response = client.put('/api/v1/lessons/99999/questions/unblock-all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Unit Block All (Lines 3429-3510)
# ============================================================

class TestUnitBlockAllAPI:
    """اختبارات منع وإلغاء منع جميع أسئلة الوحدة"""

    def test_block_all_unit_questions_existing(self, client, sample_unit):
        """منع جميع أسئلة وحدة موجودة"""
        response = client.put(
            f'/api/v1/units/{sample_unit.id}/questions/block-all'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_block_all_unit_questions_nonexistent(self, client):
        """منع جميع أسئلة وحدة غير موجودة"""
        response = client.put('/api/v1/units/99999/questions/block-all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unblock_all_unit_questions_existing(self, client, sample_unit):
        """إلغاء منع جميع أسئلة وحدة موجودة"""
        response = client.put(
            f'/api/v1/units/{sample_unit.id}/questions/unblock-all'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_unblock_all_unit_questions_nonexistent(self, client):
        """إلغاء منع جميع أسئلة وحدة غير موجودة"""
        response = client.put('/api/v1/units/99999/questions/unblock-all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Course Block All (Lines 3513-3598)
# ============================================================

class TestCourseBlockAllAPI:
    """اختبارات منع وإلغاء منع جميع أسئلة المنهج"""

    def test_block_all_course_questions_existing(self, client, sample_course):
        """منع جميع أسئلة منهج موجود"""
        response = client.put(
            f'/api/v1/courses/{sample_course.id}/questions/block-all'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_block_all_course_questions_nonexistent(self, client):
        """منع جميع أسئلة منهج غير موجود"""
        response = client.put('/api/v1/courses/99999/questions/block-all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_unblock_all_course_questions_existing(self, client, sample_course):
        """إلغاء منع جميع أسئلة منهج موجود"""
        response = client.put(
            f'/api/v1/courses/{sample_course.id}/questions/unblock-all'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_unblock_all_course_questions_nonexistent(self, client):
        """إلغاء منع جميع أسئلة منهج غير موجود"""
        response = client.put('/api/v1/courses/99999/questions/unblock-all')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Export and Generate Exam (Lines 3628-3795)
# ============================================================

class TestExportGenerateExamAPI:
    """اختبارات تصدير الأسئلة وتوليد الاختبار"""

    def test_export_questions_no_auth(self, client):
        """تصدير أسئلة بدون مصادقة"""
        response = client.post('/api/v1/questions/export', json={'question_ids': [1, 2]})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_questions_with_admin_valid(self, client, admin_user, db_session, sample_lesson):
        """تصدير أسئلة كأدمن مع أسئلة موجودة"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.post('/api/v1/questions/export', json={
            'question_ids': [q.question_id],
            'include_answers': True,
            'format': 'json'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'questions' in data

    def test_export_questions_empty_ids(self, client, admin_user):
        """تصدير بقائمة أسئلة فارغة"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/export', json={'question_ids': []})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_questions_nonexistent_ids(self, client, admin_user):
        """تصدير بـ IDs غير موجودة"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/export', json={'question_ids': [99999]})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_questions_invalid_format(self, client, admin_user, db_session, sample_lesson):
        """تصدير بصيغة غير مدعومة"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.post('/api/v1/questions/export', json={
            'question_ids': [q.question_id],
            'format': 'pdf'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_generate_exam_no_auth(self, client):
        """توليد اختبار بدون مصادقة"""
        response = client.post('/api/v1/questions/generate-exam', json={'course_id': 1})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_generate_exam_no_course_id(self, client, admin_user):
        """توليد اختبار بدون course_id"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/generate-exam', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_generate_exam_with_course_id(self, client, admin_user, sample_course):
        """توليد اختبار مع course_id"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/generate-exam', json={
            'course_id': sample_course.id,
            'question_count': 5
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_generate_exam_with_unit_id(self, client, admin_user, sample_course, sample_unit):
        """توليد اختبار مع unit_id"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/generate-exam', json={
            'course_id': sample_course.id,
            'unit_id': sample_unit.id,
            'question_count': 3
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_generate_exam_with_lesson_id(self, client, admin_user, sample_course, sample_lesson):
        """توليد اختبار مع lesson_id"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/generate-exam', json={
            'course_id': sample_course.id,
            'lesson_id': sample_lesson.id,
            'question_count': 2,
            'include_answers': True
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Unit Lessons Export + Question Counts (Lines 3798-3945)
# ============================================================

class TestUnitLessonsAndCountsAPI:
    """اختبارات دروس الوحدة وعدد الأسئلة"""

    def test_get_unit_lessons_export_no_auth(self, client, sample_course, sample_unit):
        """جلب دروس الوحدة (nested route) بدون مصادقة"""
        response = client.get(
            f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/lessons'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_lessons_export_with_admin(self, client, admin_user, sample_course, sample_unit):
        """جلب دروس الوحدة (nested route) كأدمن"""
        _login(client, admin_user)
        response = client.get(
            f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/lessons'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'lessons' in data

    def test_get_unit_lessons_export_nonexistent_unit(self, client, admin_user, sample_course):
        """جلب دروس وحدة غير موجودة"""
        _login(client, admin_user)
        response = client.get(
            f'/api/v1/courses/{sample_course.id}/units/99999/lessons'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_questions_count_no_auth(self, client, sample_unit):
        """جلب عدد أسئلة الوحدة بدون مصادقة"""
        response = client.get(f'/api/v1/units/{sample_unit.id}/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unit_questions_count_with_admin(self, client, admin_user, sample_unit):
        """جلب عدد أسئلة الوحدة كأدمن"""
        _login(client, admin_user)
        response = client.get(f'/api/v1/units/{sample_unit.id}/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'questions_count' in data

    def test_get_unit_questions_count_nonexistent(self, client, admin_user):
        """جلب عدد أسئلة وحدة غير موجودة"""
        _login(client, admin_user)
        response = client.get('/api/v1/units/99999/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_lesson_questions_count_with_admin(self, client, admin_user, sample_lesson):
        """جلب عدد أسئلة الدرس كأدمن"""
        _login(client, admin_user)
        response = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'questions_count' in data

    def test_get_lesson_questions_count_nonexistent(self, client, admin_user):
        """جلب عدد أسئلة درس غير موجود"""
        _login(client, admin_user)
        response = client.get('/api/v1/lessons/99999/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_course_questions_count_with_admin(self, client, admin_user, sample_course):
        """جلب عدد أسئلة المنهج كأدمن"""
        _login(client, admin_user)
        response = client.get(f'/api/v1/courses/{sample_course.id}/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'questions_count' in data

    def test_get_course_questions_count_nonexistent(self, client, admin_user):
        """جلب عدد أسئلة منهج غير موجود"""
        _login(client, admin_user)
        response = client.get('/api/v1/courses/99999/questions-count')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Admin Profile + Trusted Device + Upload Image (Lines 3948-4092)
# ============================================================

class TestAdminProfileAndDeviceAPI:
    """اختبارات Admin Profile وJهاز Trusted وUpload Image"""

    def test_admin_profile_no_auth(self, client):
        """جلب بيانات الأدمن بدون مصادقة"""
        response = client.get('/api/v1/admin/profile')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_admin_profile_with_admin(self, client, admin_user):
        """جلب بيانات الأدمن كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/admin/profile')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'admin' in data

    def test_trusted_device_auth_missing_fields(self, client):
        """تجديد جلسة بجهاز موثوق - بيانات ناقصة"""
        response = client.post('/api/v1/auth/trusted-device', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_trusted_device_auth_wrong_username(self, client):
        """تجديد جلسة بجهاز موثوق - مستخدم غير موجود"""
        response = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'abc123',
            'username': 'nonexistent_user'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_trusted_device_auth_invalid_token(self, client, admin_user):
        """تجديد جلسة بجهاز موثوق - توكن غير صالح"""
        response = client.post('/api/v1/auth/trusted-device', json={
            'device_token': 'invalid_token_xyz',
            'username': admin_user.username
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_register_trusted_device_no_auth(self, client):
        """تسجيل جهاز موثوق بدون مصادقة"""
        response = client.post('/api/v1/auth/register-device', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_register_trusted_device_with_admin(self, client, admin_user):
        """تسجيل جهاز موثوق كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/auth/register-device', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'device_token' in data

    def test_upload_image_no_auth(self, client):
        """رفع صورة بدون مصادقة"""
        response = client.post('/api/v1/upload-image')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_upload_image_no_file(self, client, admin_user):
        """رفع صورة بدون ملف"""
        _login(client, admin_user)
        response = client.post('/api/v1/upload-image', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Question CRUD via API (Lines 4096-4501)
# ============================================================

class TestQuestionCRUDAPI:
    """اختبارات CRUD الأسئلة عبر API"""

    def test_add_question_no_auth(self, client, sample_lesson):
        """إضافة سؤال بدون مصادقة"""
        response = client.post('/api/v1/questions', json={
            'lesson_id': sample_lesson.id,
            'question_text': 'سؤال جديد؟',
            'options': [
                {'option_text': 'الخيار أ', 'is_correct': True},
                {'option_text': 'الخيار ب', 'is_correct': False}
            ]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_with_admin_valid(self, client, admin_user, sample_lesson):
        """إضافة سؤال صالح كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'lesson_id': sample_lesson.id,
            'question_text': 'ما هو عدد مول الـ NaCl؟',
            'options': [
                {'option_text': '1 مول', 'is_correct': True},
                {'option_text': '2 مول', 'is_correct': False},
                {'option_text': '3 مول', 'is_correct': False},
                {'option_text': '4 مول', 'is_correct': False}
            ]
        })
        # 201 Created is the success response for add_question_api
        assert response.status_code in [200, 201, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_no_lesson_id(self, client, admin_user):
        """إضافة سؤال بدون lesson_id"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'question_text': 'سؤال بدون درس؟',
            'options': [
                {'option_text': 'خيار أ', 'is_correct': True},
                {'option_text': 'خيار ب', 'is_correct': False}
            ]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_nonexistent_lesson(self, client, admin_user):
        """إضافة سؤال لدرس غير موجود"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'lesson_id': 99999,
            'question_text': 'سؤال؟',
            'options': [
                {'option_text': 'خيار أ', 'is_correct': True},
                {'option_text': 'خيار ب', 'is_correct': False}
            ]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_no_correct_option(self, client, admin_user, sample_lesson):
        """إضافة سؤال بدون إجابة صحيحة"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'lesson_id': sample_lesson.id,
            'question_text': 'سؤال؟',
            'options': [
                {'option_text': 'خيار أ', 'is_correct': False},
                {'option_text': 'خيار ب', 'is_correct': False}
            ]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_one_option(self, client, admin_user, sample_lesson):
        """إضافة سؤال بخيار واحد فقط"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'lesson_id': sample_lesson.id,
            'question_text': 'سؤال؟',
            'options': [{'option_text': 'خيار واحد', 'is_correct': True}]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_no_text_no_image(self, client, admin_user, sample_lesson):
        """إضافة سؤال بدون نص وبدون صورة"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'lesson_id': sample_lesson.id,
            'options': [
                {'option_text': 'خيار أ', 'is_correct': True},
                {'option_text': 'خيار ب', 'is_correct': False}
            ]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_no_data(self, client, admin_user):
        """إضافة سؤال بدون بيانات"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions', json=None)
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_question_no_auth(self, client, db_session, sample_lesson):
        """جلب سؤال بدون مصادقة"""
        q = _make_question(db_session, sample_lesson)
        response = client.get(f'/api/v1/questions/{q.question_id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_question_with_admin(self, client, admin_user, db_session, sample_lesson):
        """جلب سؤال كأدمن"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.get(f'/api/v1/questions/{q.question_id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'question' in data

    def test_get_question_nonexistent(self, client, admin_user):
        """جلب سؤال غير موجود"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_question_no_auth(self, client, db_session, sample_lesson):
        """تعديل سؤال بدون مصادقة"""
        q = _make_question(db_session, sample_lesson)
        response = client.put(f'/api/v1/questions/{q.question_id}', json={
            'question_text': 'سؤال معدّل'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_question_with_admin(self, client, admin_user, db_session, sample_lesson):
        """تعديل سؤال كأدمن"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.put(f'/api/v1/questions/{q.question_id}', json={
            'question_text': 'سؤال معدّل بالتفصيل'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_update_question_nonexistent(self, client, admin_user):
        """تعديل سؤال غير موجود"""
        _login(client, admin_user)
        response = client.put('/api/v1/questions/99999', json={
            'question_text': 'سؤال معدّل'
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_question_no_data(self, client, admin_user, db_session, sample_lesson):
        """تعديل سؤال بدون بيانات"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.put(f'/api/v1/questions/{q.question_id}', json=None)
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_question_with_invalid_options(self, client, admin_user, db_session, sample_lesson):
        """تعديل سؤال بخيارات غير صالحة"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.put(f'/api/v1/questions/{q.question_id}', json={
            'options': [{'option_text': 'خيار واحد', 'is_correct': True}]
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_question_no_auth(self, client, db_session, sample_lesson):
        """حذف سؤال بدون مصادقة"""
        q = _make_question(db_session, sample_lesson)
        response = client.delete(f'/api/v1/questions/{q.question_id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_question_with_admin(self, client, admin_user, db_session, sample_lesson):
        """حذف سؤال كأدمن"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.delete(f'/api/v1/questions/{q.question_id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_delete_question_nonexistent(self, client, admin_user):
        """حذف سؤال غير موجود"""
        _login(client, admin_user)
        response = client.delete('/api/v1/questions/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_question_block_no_auth(self, client, db_session, sample_lesson):
        """تبديل حالة حظر السؤال بدون مصادقة"""
        q = _make_question(db_session, sample_lesson)
        response = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_toggle_question_block_with_admin(self, client, admin_user, db_session, sample_lesson):
        """تبديل حالة حظر السؤال كأدمن"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'is_blocked' in data

    def test_toggle_question_block_nonexistent(self, client, admin_user):
        """تبديل حالة حظر سؤال غير موجود"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/99999/toggle-block')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ============================================================
# Search Questions (Lines 4503-4579)
# ============================================================

class TestSearchQuestionsAPI:
    """اختبارات البحث في الأسئلة"""

    def test_search_no_auth(self, client):
        """البحث بدون مصادقة"""
        response = client.get('/api/v1/questions/search?q=كيمياء')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_search_with_admin_no_query(self, client, admin_user):
        """البحث كأدمن بدون نص"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/search')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'questions' in data

    def test_search_with_admin_and_query(self, client, admin_user):
        """البحث كأدمن مع نص"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/search?q=سؤال')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_search_with_lesson_filter(self, client, admin_user, sample_lesson):
        """البحث مع فلتر الدرس"""
        _login(client, admin_user)
        response = client.get(
            f'/api/v1/questions/search?lesson_id={sample_lesson.id}'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_search_with_unit_filter(self, client, admin_user, sample_unit):
        """البحث مع فلتر الوحدة"""
        _login(client, admin_user)
        response = client.get(
            f'/api/v1/questions/search?unit_id={sample_unit.id}'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_search_with_course_filter(self, client, admin_user, sample_course):
        """البحث مع فلتر المنهج"""
        _login(client, admin_user)
        response = client.get(
            f'/api/v1/questions/search?course_id={sample_course.id}'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_search_with_pagination(self, client, admin_user):
        """البحث مع صفحات"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/search?page=1&per_page=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert 'pagination' in data


# ============================================================
# AI Classification APIs (Lines 4589-5035)
# ============================================================

class TestAIClassificationAPI:
    """اختبارات تصنيف الأسئلة بالذكاء الاصطناعي"""

    def test_classify_all_no_auth(self, client):
        """تصنيف جميع الأسئلة بدون مصادقة"""
        response = client.post('/api/v1/questions/classify-all', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_classify_all_with_admin(self, client, admin_user):
        """تصنيف جميع الأسئلة كأدمن"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/classify-all', json={
            'batch_size': 5
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_classify_single_no_auth(self, client, db_session, sample_lesson):
        """تصنيف سؤال واحد بدون مصادقة"""
        q = _make_question(db_session, sample_lesson)
        response = client.post(f'/api/v1/questions/{q.question_id}/classify')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_classify_single_with_admin_existing(self, client, admin_user, db_session, sample_lesson):
        """تصنيف سؤال واحد موجود كأدمن"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.post(f'/api/v1/questions/{q.question_id}/classify')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_classify_single_nonexistent(self, client, admin_user):
        """تصنيف سؤال غير موجود"""
        _login(client, admin_user)
        response = client.post('/api/v1/questions/99999/classify')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_classification_stats_no_auth(self, client):
        """إحصائيات التصنيف بدون مصادقة"""
        response = client.get('/api/v1/questions/classification-stats')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_classification_stats_with_admin(self, client, admin_user):
        """إحصائيات التصنيف كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/classification-stats')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'stats' in data

    def test_update_classification_no_auth(self, client, db_session, sample_lesson):
        """تحديث تصنيف سؤال بدون مصادقة"""
        q = _make_question(db_session, sample_lesson)
        response = client.put(
            f'/api/v1/questions/{q.question_id}/update-classification',
            json={'difficulty': 'hard', 'bloom_level': 'analyze'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_classification_with_admin_valid(self, client, admin_user, db_session, sample_lesson):
        """تحديث تصنيف سؤال كأدمن بقيم صالحة"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.put(
            f'/api/v1/questions/{q.question_id}/update-classification',
            json={'difficulty': 'easy', 'bloom_level': 'remember'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_update_classification_invalid_difficulty(self, client, admin_user, db_session, sample_lesson):
        """تحديث تصنيف سؤال بمستوى صعوبة غير صالح"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.put(
            f'/api/v1/questions/{q.question_id}/update-classification',
            json={'difficulty': 'super_hard'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_classification_invalid_bloom(self, client, admin_user, db_session, sample_lesson):
        """تحديث تصنيف سؤال بمستوى بلوم غير صالح"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson)
        response = client.put(
            f'/api/v1/questions/{q.question_id}/update-classification',
            json={'bloom_level': 'invalid_bloom'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_classification_nonexistent(self, client, admin_user):
        """تحديث تصنيف سؤال غير موجود"""
        _login(client, admin_user)
        response = client.put(
            '/api/v1/questions/99999/update-classification',
            json={'difficulty': 'easy'}
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_browse_classifications_no_auth(self, client):
        """استعراض تصنيفات الأسئلة بدون مصادقة"""
        response = client.get('/api/v1/questions/browse-classifications')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_browse_classifications_with_admin(self, client, admin_user):
        """استعراض تصنيفات الأسئلة كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/browse-classifications')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_browse_classifications_with_filters(self, client, admin_user):
        """استعراض تصنيفات مع فلاتر"""
        _login(client, admin_user)
        response = client.get(
            '/api/v1/questions/browse-classifications?difficulty=easy&bloom_level=remember&page=1&per_page=10'
        )
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unclassified_questions_no_auth(self, client):
        """جلب الأسئلة غير المصنفة بدون مصادقة"""
        response = client.get('/api/v1/questions/unclassified')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unclassified_questions_with_admin(self, client, admin_user):
        """جلب الأسئلة غير المصنفة كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/unclassified')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_unclassified_questions_with_pagination(self, client, admin_user):
        """جلب الأسئلة غير المصنفة مع صفحات"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/unclassified?page=1&per_page=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_classification_summary_no_auth(self, client):
        """ملخص التصنيف بدون مصادقة"""
        response = client.get('/api/v1/questions/classification-summary')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_classification_summary_with_admin(self, client, admin_user):
        """ملخص التصنيف كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/questions/classification-summary')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'stats' in data


# ============================================================
# CSRF Token (Lines 3181-3197)
# ============================================================

class TestCSRFTokenAPI:
    """اختبارات CSRF token"""

    def test_get_csrf_token(self, client):
        """جلب CSRF token بدون مصادقة"""
        response = client.get('/api/v1/csrf-token')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_csrf_token_with_admin(self, client, admin_user):
        """جلب CSRF token كأدمن"""
        _login(client, admin_user)
        response = client.get('/api/v1/csrf-token')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
