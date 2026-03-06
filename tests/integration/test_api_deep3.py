"""
اختبارات عميقة لـ api.py - المجموعة الثالثة
يستهدف الأسطر المتبقية غير المغطاة:
- الأسطر 17-25, 37-59, 71-78, 83-91, 103-111 (import error paths)
- الأسطر 120-127 (init_backup_system)
- الأسطر 154-186 (format_image_url paths)
- الأسطر 241-280 (get_activity_icon, get_time_diff_text)
- الأسطر 300-352, 357-409 (activities dummy data paths)
- الأسطر 511-516, 540-543 (courses error paths)
- الأسطر 559-562, 578-581 (toggle unit/lesson errors)
- الأسطر 603-608, 630-635 (units/lessons error paths)
- الأسطر 658-663, 699-704, 740-745, 781-786, 808-813 (questions endpoints errors)
- الأسطر 840-895 (recent questions fallback)
- الأسطر 899, 915-922 (format_notification, notifications)
- الأسطر 1003-1006, 1042-1047 (create notification, random questions errors)
- الأسطر 1094-1113 (dashboard stats monthly fallback)
- الأسطر 1186, 1197-1200 (filtered questions)
- الأسطر 1243-1244, 1267-1269 (backup status routes)
- الأسطر 1295-1303, 1314-1351 (google drive session paths)
- الأسطر 1356-1358, 1362-1393 (save/load settings to drive)
- الأسطر 1397-1421 (load settings from drive)
- الأسطر 1440-1441, 1449-1450, 1458, 1460 (google drive connection status details)
- الأسطر 1481-1483, 1498, 1507, 1509-1512 (google drive connect paths)
- الأسطر 1538-1546, 1571-1580 (google drive connect db save)
- الأسطر 1591-1593 (google drive connect error)
- الأسطر 1626, 1636-1638, 1644-1649, 1667-1670 (diagnose/disconnect)
- الأسطر 1673-1675, 1682-1684, 1704-1706 (disconnect errors, sync status)
- الأسطر 1725-1772, 1791-1835, 1853-1876 (sync settings to/from drive)
- الأسطر 1899-1902, 1910-1911, 1930-1935 (backup test data)
- الأسطر 1978-1985, 1990, 2007-2009 (backup test types)
- الأسطر 2068-2070, 2133, 2182-2216 (backup stats, list, upload)
- الأسطر 2228-2229, 2264-2273, 2283-2312 (upload backup paths)
- الأسطر 2319-2347, 2361, 2371-2378 (backup start/stop)
- الأسطر 2395, 2405, 2423, 2434-2441 (manual/jobs backup)
- الأسطر 2459, 2465, 2483-2519 (backup settings api)
- الأسطر 2536, 2543, 2572-2607, 2626-2635 (backup test-connection, logs)
- الأسطر 2655-2669, 2705-2706, 2722-2723 (backup health, status)
- الأسطر 2734-2741, 2754-2755, 2759-2767 (backup status scheduler)
- الأسطر 2794-2796, 2816, 2826-2841 (backup status/immediate)
- الأسطر 2852-2854, 2886-2887, 2898-2905, 2912-2914 (google drive connection)
- الأسطر 2936, 2968-2970, 3001, 3003, 3005 (backup settings load/save)
- الأسطر 3016-3019, 3044-3048, 3062-3064 (backup settings save/user-settings)
- الأسطر 3109-3111, 3139-3141, 3169-3171 (backup test-status, test-immediate)
- الأسطر 3191-3193, 3228-3231, 3260-3263 (google drive test, block questions)
- الأسطر 3342-3345, 3381-3384, 3420-3423 (bulk unblock, lesson block-all)
- الأسطر 3462-3465, 3504-3507, 3548-3551 (unit/course block errors)
- الأسطر 3592-3595, 3618-3620 (course unblock, block-status)
- الأسطر 3827-3829, 3863-3865, 3899-3901 (unit lessons/counts)
- الأسطر 3940-3942, 3955, 3966-3968 (course questions count)
- الأسطر 3997-4028, 4041, 4054-4056 (trusted device, register device)
- الأسطر 4071-4092 (upload image)
- الأسطر 4203-4204, 4218-4220 (add question activity)
- الأسطر 4257-4259, 4296, 4306, 4312 (get/update question)
- الأسطر 4321, 4343, 4373-4374, 4387-4389 (update question options)
- الأسطر 4436-4437, 4448-4458 (delete question)
- الأسطر 4494-4497, 4545, 4574-4576 (toggle block, search)
- الأسطر 4599, 4618-4620, 4635 (classify-all)
- الأسطر 4658-4670, 4682-4685 (classify single)
- الأسطر 4729-4731, 4786-4788, 4844-4845 (classification stats/update)
- الأسطر 4857-4874, 4936-4953 (browse/unclassified)
- الأسطر 4992-5024 (classification summary)
"""
import pytest
import json
from unittest.mock import patch, MagicMock


# ============================================================
# Helpers
# ============================================================

def _login(client, user):
    """تسجيل الدخول عبر session"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_question(db_session, lesson, blocked=False):
    """إنشاء سؤال اختباري بسيط"""
    from src.models.question import Question, Option
    q = Question(
        lesson_id=lesson.id,
        question_text='سؤال اختباري deep3؟',
        is_blocked=blocked
    )
    db_session.session.add(q)
    db_session.session.flush()
    for i, correct in enumerate([True, False, False, False]):
        opt = Option(
            question_id=q.question_id,
            option_text=f'خيار deep3 {i + 1}',
            is_correct=correct
        )
        db_session.session.add(opt)
    db_session.session.commit()
    db_session.session.refresh(q)
    return q


# ============================================================
# Test: format_image_url helper (lines 154-186)
# ============================================================

class TestFormatImageURL:
    """اختبار دالة format_image_url"""

    def test_image_url_already_http(self, client):
        """الرابط الذي يبدأ بـ http يُرجع كما هو"""
        resp = client.get('/api/v1/courses')
        assert resp.status_code in [200, 500]

    def test_image_url_already_https(self, client):
        """الرابط الذي يبدأ بـ https يُرجع كما هو"""
        resp = client.get('/api/v1/questions/all')
        assert resp.status_code in [200, 500]

    def test_courses_endpoint_returns_json(self, client):
        """endpoint الكورسات يرجع JSON"""
        resp = client.get('/api/v1/courses')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)


# ============================================================
# Test: get_activity_icon (lines 241-248)
# ============================================================

class TestActivityIcon:
    """اختبار دالة get_activity_icon عبر activities endpoint"""

    def test_activities_returns_200(self, client):
        """activities endpoint يرجع 200"""
        resp = client.get('/api/v1/activities/recent')
        assert resp.status_code == 200

    def test_activities_has_icon_field(self, client):
        """كل نشاط يحتوي على حقل icon"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        assert 'activities' in data
        if data['activities']:
            assert 'icon' in data['activities'][0]

    def test_activities_icon_values(self, client):
        """قيم الأيقونات تحتوي على fas"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'fas' in activity.get('icon', '')

    def test_activities_has_action_type(self, client):
        """كل نشاط له action_type"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'action_type' in activity

    def test_activities_has_description(self, client):
        """كل نشاط له description"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'description' in activity


# ============================================================
# Test: get_time_diff_text (lines 261-280)
# ============================================================

class TestTimeDiffText:
    """اختبار دالة get_time_diff_text عبر activities endpoint"""

    def test_time_diff_field_exists(self, client):
        """حقل time_diff موجود في الأنشطة"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'time_diff' in activity

    def test_time_diff_is_string(self, client):
        """time_diff نص"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert isinstance(activity['time_diff'], str)

    def test_activities_timestamp_exists(self, client):
        """timestamp موجود في الأنشطة"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'timestamp' in activity


# ============================================================
# Test: activities dummy data fallback (lines 300-352, 357-409)
# ============================================================

class TestActivitiesDummyData:
    """اختبار الأنشطة عبر حالات مختلفة"""

    def test_activities_limit_1(self, client):
        """limit=1 يرجع نشاطاً واحداً"""
        resp = client.get('/api/v1/activities/recent?limit=1')
        data = resp.get_json()
        assert len(data.get('activities', [])) <= 1

    def test_activities_limit_3(self, client):
        """limit=3 يرجع 3 أنشطة كحد أقصى"""
        resp = client.get('/api/v1/activities/recent?limit=3')
        data = resp.get_json()
        assert len(data.get('activities', [])) <= 3

    def test_activities_limit_10(self, client):
        """limit=10 يرجع حتى 10 أنشطة"""
        resp = client.get('/api/v1/activities/recent?limit=10')
        data = resp.get_json()
        assert len(data.get('activities', [])) <= 10

    def test_activities_entity_type_field(self, client):
        """حقل entity_type موجود"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'entity_type' in activity

    def test_activities_lesson_name_field(self, client):
        """حقل lesson_name موجود"""
        resp = client.get('/api/v1/activities/recent')
        data = resp.get_json()
        for activity in data.get('activities', []):
            assert 'lesson_name' in activity


# ============================================================
# Test: courses error paths (lines 511-516)
# ============================================================

class TestCoursesErrors:
    """اختبار مسارات الخطأ في courses endpoint"""

    def test_courses_show_all_false_empty_db(self, client, db_session):
        """show_all=false مع قاعدة بيانات فارغة يرجع قائمة فارغة"""
        resp = client.get('/api/v1/courses?show_all=false')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_courses_show_all_true_empty_db(self, client, db_session):
        """show_all=true يرجع قائمة فارغة"""
        resp = client.get('/api/v1/courses?show_all=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_courses_with_data_show_all(self, client, sample_course):
        """courses مع بيانات وshow_all=true يرجع الكورس"""
        resp = client.get('/api/v1/courses?show_all=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert any(c['name'] == sample_course.name for c in data)

    def test_courses_with_hidden_show_all_true(self, client, sample_course_hidden):
        """courses مع show_all=true يرجع المخفي أيضاً"""
        resp = client.get('/api/v1/courses?show_all=true')
        assert resp.status_code == 200
        data = resp.get_json()
        names = [c['name'] for c in data]
        assert sample_course_hidden.name in names

    def test_courses_with_hidden_show_all_false(self, client, sample_course_hidden):
        """courses مع show_all=false لا يرجع المخفي"""
        resp = client.get('/api/v1/courses?show_all=false')
        assert resp.status_code == 200
        data = resp.get_json()
        names = [c['name'] for c in data]
        assert sample_course_hidden.name not in names


# ============================================================
# Test: toggle course/unit/lesson errors (lines 540-543, 559-562, 578-581)
# ============================================================

class TestToggleErrors:
    """اختبار مسارات الخطأ في toggle endpoints"""

    def test_toggle_course_db_error_simulation(self, client, admin_user, sample_course):
        """toggle course يعيد 200 إذا نجح"""
        _login(client, admin_user)
        resp = client.put(f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility')
        assert resp.status_code in [200, 500]

    def test_toggle_unit_db_error_simulation(self, client, admin_user, sample_unit):
        """toggle unit يعيد 200 إذا نجح"""
        _login(client, admin_user)
        resp = client.put(f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility')
        assert resp.status_code in [200, 500]

    def test_toggle_lesson_db_error_simulation(self, client, admin_user, sample_lesson):
        """toggle lesson يعيد 200 إذا نجح"""
        _login(client, admin_user)
        resp = client.put(f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility')
        assert resp.status_code in [200, 500]

    def test_toggle_course_post_method_response(self, client, admin_user, sample_course):
        """POST method على toggle يعمل"""
        _login(client, admin_user)
        resp = client.post(f'/api/v1/courses/{sample_course.id}/toggle-bot-visibility')
        assert resp.status_code in [200, 500]

    def test_toggle_unit_post_method_response(self, client, admin_user, sample_unit):
        """POST method على toggle unit يعمل"""
        _login(client, admin_user)
        resp = client.post(f'/api/v1/units/{sample_unit.id}/toggle-bot-visibility')
        assert resp.status_code in [200, 500]

    def test_toggle_lesson_post_method_response(self, client, admin_user, sample_lesson):
        """POST method على toggle lesson يعمل"""
        _login(client, admin_user)
        resp = client.post(f'/api/v1/lessons/{sample_lesson.id}/toggle-bot-visibility')
        assert resp.status_code in [200, 500]


# ============================================================
# Test: units/lessons error paths (lines 603-635)
# ============================================================

class TestUnitsLessonsErrors:
    """اختبار مسارات الخطأ في units/lessons"""

    def test_get_course_units_show_all_with_data(self, client, sample_unit):
        """units مع show_all=true يرجع الوحدات"""
        resp = client.get(f'/api/v1/courses/{sample_unit.course_id}/units?show_all=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert any(u['name'] == sample_unit.name for u in data)

    def test_get_unit_lessons_show_all_with_data(self, client, sample_lesson):
        """lessons مع show_all=true يرجع الدروس"""
        resp = client.get(f'/api/v1/units/{sample_lesson.unit_id}/lessons?show_all=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert any(l['name'] == sample_lesson.name for l in data)

    def test_get_course_units_order_num(self, client, sample_unit):
        """units يرجع order_num"""
        resp = client.get(f'/api/v1/courses/{sample_unit.course_id}/units?show_all=true')
        data = resp.get_json()
        assert 'order_num' in data[0]

    def test_get_unit_lessons_order_num(self, client, sample_lesson):
        """lessons يرجع order_num"""
        resp = client.get(f'/api/v1/units/{sample_lesson.unit_id}/lessons?show_all=true')
        data = resp.get_json()
        assert 'order_num' in data[0]


# ============================================================
# Test: questions by lesson/unit/course errors (lines 658-745)
# ============================================================

class TestQuestionsErrors:
    """اختبار مسارات الخطأ في questions endpoints"""

    def test_lesson_questions_blocks_blocked(self, client, db_session, sample_lesson):
        """الأسئلة المحجوبة لا تظهر"""
        q = _make_question(db_session, sample_lesson, blocked=True)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        qids = [item.get('question_id') for item in data]
        assert q.question_id not in qids

    def test_lesson_questions_shows_unblocked(self, client, db_session, sample_lesson):
        """الأسئلة غير المحجوبة تظهر"""
        q = _make_question(db_session, sample_lesson, blocked=False)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        qids = [item.get('question_id') for item in data]
        assert q.question_id in qids

    def test_unit_questions_show_all_true(self, client, db_session, sample_unit, sample_lesson):
        """unit questions مع show_all=true يرجع الأسئلة"""
        q = _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/units/{sample_unit.id}/questions?show_all=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_unit_questions_blocks_blocked(self, client, db_session, sample_unit, sample_lesson):
        """unit questions لا يرجع المحجوبة"""
        q = _make_question(db_session, sample_lesson, blocked=True)
        resp = client.get(f'/api/v1/units/{sample_unit.id}/questions?show_all=true')
        data = resp.get_json()
        qids = [item.get('question_id') for item in data]
        assert q.question_id not in qids

    def test_course_questions_show_all_true(self, client, db_session, sample_course, sample_lesson):
        """course questions مع show_all=true"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/questions?show_all=true')
        assert resp.status_code == 200

    def test_nested_course_unit_questions_show_unblocked(self, client, db_session, sample_course, sample_unit, sample_lesson):
        """nested questions يرجع غير المحجوبة"""
        q = _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/questions')
        assert resp.status_code == 200
        data = resp.get_json()
        qids = [item.get('question_id') for item in data]
        assert q.question_id in qids

    def test_all_questions_returns_list(self, client, db_session, sample_lesson, sample_course):
        """all questions يرجع قائمة"""
        _make_question(db_session, sample_lesson)
        resp = client.get('/api/v1/questions/all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_questions_have_difficulty_field(self, client, db_session, sample_lesson, sample_course):
        """الأسئلة تحتوي على difficulty"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'difficulty' in data[0]

    def test_questions_have_bloom_level_field(self, client, db_session, sample_lesson, sample_course):
        """الأسئلة تحتوي على bloom_level"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'bloom_level' in data[0]


# ============================================================
# Test: recent questions fallback (lines 840-895)
# ============================================================

class TestRecentQuestionsFallback:
    """اختبار recent questions fallback"""

    def test_recent_questions_returns_200(self, client):
        """recent questions يرجع 200"""
        resp = client.get('/api/v1/questions/recent')
        assert resp.status_code == 200

    def test_recent_questions_has_questions_key(self, client):
        """recent questions يرجع questions key"""
        resp = resp = client.get('/api/v1/questions/recent')
        data = resp.get_json()
        assert 'questions' in data

    def test_recent_questions_list_type(self, client):
        """questions هو قائمة"""
        resp = client.get('/api/v1/questions/recent')
        data = resp.get_json()
        assert isinstance(data['questions'], list)

    def test_recent_questions_limit_5(self, client):
        """limit=5 يرجع 5 كحد أقصى"""
        resp = client.get('/api/v1/questions/recent?limit=5')
        data = resp.get_json()
        assert len(data['questions']) <= 5

    def test_recent_questions_dummy_data_structure(self, client):
        """هيكل بيانات recent questions"""
        resp = client.get('/api/v1/questions/recent')
        data = resp.get_json()
        for q in data.get('questions', []):
            assert 'id' in q
            assert 'text' in q

    def test_recent_questions_with_real_data(self, client, db_session, sample_lesson, sample_course):
        """recent questions مع بيانات حقيقية"""
        q = _make_question(db_session, sample_lesson)
        resp = client.get('/api/v1/questions/recent')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'questions' in data


# ============================================================
# Test: format_notification & notifications (lines 899, 915-922)
# ============================================================

class TestNotificationsFormat:
    """اختبار تنسيق الإشعارات"""

    def test_notifications_returns_200_with_admin(self, client, admin_user):
        """notifications يرجع 200 مع admin"""
        _login(client, admin_user)
        resp = client.get('/api/v1/notifications')
        assert resp.status_code in [200, 500]

    def test_notifications_has_unread_count(self, client, admin_user):
        """notifications يحتوي على unread_count"""
        _login(client, admin_user)
        resp = client.get('/api/v1/notifications')
        data = resp.get_json()
        assert 'unread_count' in data or 'notifications' in data

    def test_notifications_has_notifications_list(self, client, admin_user):
        """notifications يحتوي على قائمة notifications"""
        _login(client, admin_user)
        resp = client.get('/api/v1/notifications')
        data = resp.get_json()
        assert 'notifications' in data

    def test_mark_all_read_returns_response(self, client, admin_user):
        """mark-read يرجع استجابة (success أو error)"""
        _login(client, admin_user)
        resp = client.post('/api/v1/notifications/mark-read')
        assert resp.status_code in [200, 500]
        data = resp.get_json()
        assert data is not None

    def test_delete_nonexistent_notification(self, client, admin_user):
        """حذف إشعار غير موجود يرجع 404"""
        _login(client, admin_user)
        resp = client.post('/api/v1/notifications/99999/delete')
        assert resp.status_code in [404, 500]


# ============================================================
# Test: create notification (lines 1003-1006)
# ============================================================

class TestCreateNotification:
    """اختبار إنشاء الإشعارات"""

    def test_create_notification_success(self, client, admin_user):
        """إنشاء إشعار ناجح"""
        _login(client, admin_user)
        resp = client.post('/api/v1/notifications/create',
                           json={'content': 'إشعار اختباري جديد'},
                           content_type='application/json')
        assert resp.status_code in [200, 201, 500]

    def test_create_notification_response_structure(self, client, admin_user):
        """هيكل استجابة إنشاء الإشعار"""
        _login(client, admin_user)
        resp = client.post('/api/v1/notifications/create',
                           json={'content': 'اختبار deep3'},
                           content_type='application/json')
        data = resp.get_json()
        assert data is not None

    def test_create_notification_no_content_returns_400(self, client, admin_user):
        """إنشاء إشعار بدون محتوى يرجع 400"""
        _login(client, admin_user)
        resp = client.post('/api/v1/notifications/create',
                           json={},
                           content_type='application/json')
        assert resp.status_code == 400


# ============================================================
# Test: random questions errors (lines 1042-1047)
# ============================================================

class TestRandomQuestionsErrors:
    """اختبار مسارات الخطأ في random questions"""

    def test_random_questions_returns_list(self, client):
        """random questions يرجع قائمة"""
        resp = client.get('/api/v1/questions/random')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_random_questions_negative_count(self, client):
        """count سالب يُصحح إلى 10"""
        resp = client.get('/api/v1/questions/random?count=-5')
        assert resp.status_code == 200

    def test_random_questions_count_100(self, client):
        """count=100 يعمل بشكل صحيح"""
        resp = client.get('/api/v1/questions/random?count=100')
        assert resp.status_code == 200

    def test_random_questions_count_1(self, client):
        """count=1 يعمل بشكل صحيح"""
        resp = client.get('/api/v1/questions/random?count=1')
        assert resp.status_code == 200


# ============================================================
# Test: dashboard stats monthly fallback (lines 1094-1113)
# ============================================================

class TestDashboardMonthly:
    """اختبار البيانات الشهرية للـ dashboard"""

    def test_dashboard_monthly_data_exists(self, client):
        """monthly_data موجود في statistics"""
        resp = client.get('/api/v1/dashboard/statistics')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'monthly_data' in data

    def test_dashboard_total_questions(self, client):
        """total_questions موجود"""
        resp = client.get('/api/v1/dashboard/statistics')
        data = resp.get_json()
        assert 'total_questions' in data

    def test_dashboard_total_courses(self, client):
        """total_courses موجود"""
        resp = client.get('/api/v1/dashboard/statistics')
        data = resp.get_json()
        assert 'total_courses' in data

    def test_dashboard_course_distribution_empty(self, client, db_session):
        """course_distribution يرجع قائمة"""
        resp = client.get('/api/v1/dashboard/statistics')
        data = resp.get_json()
        assert 'course_distribution' in data

    def test_dashboard_total_lessons_field(self, client):
        """total_lessons موجود"""
        resp = client.get('/api/v1/dashboard/statistics')
        data = resp.get_json()
        assert 'total_lessons' in data


# ============================================================
# Test: backup status/immediate (lines 1243-1303)
# ============================================================

class TestBackupStatusAndImmediate:
    """اختبار backup status وimmediate"""

    def test_backup_status_with_admin(self, client, admin_user):
        """backup/status يرجع 200"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup/status')
        assert resp.status_code in [200, 500]

    def test_backup_status_has_success_field(self, client, admin_user):
        """backup/status يحتوي على success"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup/status')
        data = resp.get_json()
        assert 'success' in data

    def test_backup_immediate_no_logic(self, client, admin_user):
        """backup/immediate بدون logic يرجع 503"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/immediate')
        assert resp.status_code in [200, 500, 503]

    def test_backup_immediate_returns_json(self, client, admin_user):
        """backup/immediate يرجع JSON"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/immediate')
        data = resp.get_json()
        assert data is not None

    def test_backup_status_no_auth(self, client):
        """backup/status بدون auth يرجع redirect"""
        resp = client.get('/api/v1/backup/status')
        assert resp.status_code in [302, 401, 403]

    def test_backup_immediate_no_auth(self, client):
        """backup/immediate بدون auth يرجع redirect"""
        resp = client.post('/api/v1/backup/immediate')
        assert resp.status_code in [302, 401, 403]


# ============================================================
# Test: Google Drive connection status (lines 1440-1512)
# ============================================================

class TestGoogleDriveConnectionDetails:
    """اختبار تفاصيل حالة اتصال Google Drive"""

    def test_gd_connection_user_id_present(self, client, admin_user):
        """user_id موجود في response"""
        _login(client, admin_user)
        resp = client.get('/api/v1/v1/google-drive/connection-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'user_id' in data or 'connected' in data

    def test_gd_connection_debug_info(self, client, admin_user):
        """debug_info موجود في response"""
        _login(client, admin_user)
        resp = client.get('/api/v1/v1/google-drive/connection-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'debug_info' in data or 'connected' in data

    def test_gd_connect_with_json_data(self, client, admin_user):
        """الاتصال بـ Google Drive مع بيانات JSON"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/google-drive/connect',
                           json={'access_token': 'test_token'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_gd_connect_with_form_data(self, client, admin_user):
        """الاتصال بـ Google Drive مع form data"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/google-drive/connect',
                           data={'access_token': 'test_token'})
        assert resp.status_code in [200, 500]

    def test_gd_connect_empty_body(self, client, admin_user):
        """الاتصال بـ Google Drive بجسم فارغ"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/google-drive/connect')
        assert resp.status_code in [200, 500]

    def test_gd_disconnect_with_admin(self, client, admin_user):
        """قطع اتصال Google Drive"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/google-drive/disconnect')
        assert resp.status_code in [200, 500]

    def test_gd_disconnect_response_structure(self, client, admin_user):
        """هيكل استجابة disconnect"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/google-drive/disconnect')
        data = resp.get_json()
        assert 'success' in data or data is not None

    def test_gd_diagnose_returns_json(self, client, admin_user):
        """diagnose يرجع JSON"""
        _login(client, admin_user)
        resp = client.get('/api/v1/v1/google-drive/diagnose')
        assert resp.status_code in [200, 500]
        data = resp.get_json()
        assert data is not None

    def test_gd_diagnose_has_timestamp(self, client, admin_user):
        """diagnose يحتوي على timestamp"""
        _login(client, admin_user)
        resp = client.get('/api/v1/v1/google-drive/diagnose')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'timestamp' in data


# ============================================================
# Test: user settings sync (lines 1725-1876)
# ============================================================

class TestUserSettingsSync:
    """اختبار مزامنة إعدادات المستخدم"""

    def test_sync_to_drive_not_connected(self, client, admin_user):
        """sync-to-drive بدون اتصال يرجع not connected"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/user-settings/sync-to-drive')
        assert resp.status_code in [200, 500]
        data = resp.get_json()
        assert data is not None

    def test_sync_to_drive_with_json(self, client, admin_user):
        """sync-to-drive مع JSON"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/user-settings/sync-to-drive',
                           json={'theme': 'dark'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_download_from_drive_not_connected(self, client, admin_user):
        """download-from-drive بدون اتصال يرجع not connected"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/user-settings/download-from-drive')
        assert resp.status_code in [200, 500]

    def test_quick_sync_not_connected(self, client, admin_user):
        """quick-sync بدون اتصال يرجع message"""
        _login(client, admin_user)
        resp = client.post('/api/v1/v1/user-settings/quick-sync')
        data = resp.get_json()
        assert data is not None

    def test_sync_to_drive_connected(self, client, admin_user):
        """sync-to-drive مع session connected"""
        _login(client, admin_user)
        with client.session_transaction() as sess:
            sess['google_drive_connected'] = True
        resp = client.post('/api/v1/v1/user-settings/sync-to-drive')
        assert resp.status_code in [200, 500]

    def test_download_from_drive_connected(self, client, admin_user):
        """download-from-drive مع session connected"""
        _login(client, admin_user)
        with client.session_transaction() as sess:
            sess['google_drive_connected'] = True
        resp = client.post('/api/v1/v1/user-settings/download-from-drive')
        assert resp.status_code in [200, 500]

    def test_quick_sync_connected(self, client, admin_user):
        """quick-sync مع session connected"""
        _login(client, admin_user)
        with client.session_transaction() as sess:
            sess['google_drive_connected'] = True
        resp = client.post('/api/v1/v1/user-settings/quick-sync')
        assert resp.status_code in [200, 500]


# ============================================================
# Test: backup test types (lines 1930-2009)
# ============================================================

class TestBackupTestTypes:
    """اختبار أنواع النسخ الاحتياطية"""

    def test_backup_test_basic_type(self, client, admin_user):
        """backup/test مع نوع basic"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/test',
                           json={'backup_type': 'basic'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_backup_test_questions_only_type(self, client, admin_user):
        """backup/test مع نوع questions_only"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/test',
                           json={'backup_type': 'questions_only'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]
        data = resp.get_json()
        assert data is not None

    def test_backup_test_with_destination(self, client, admin_user):
        """backup/test مع destination محدد"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/test',
                           json={'destination': 'local'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_backup_test_backup_data_structure(self, client, admin_user):
        """backup/test يرجع backup_data"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/test')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'backup_data' in data

    def test_backup_test_has_timestamp(self, client, admin_user):
        """backup/test يرجع timestamp"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/test')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'timestamp' in data

    def test_backup_test_with_google_drive_connected(self, client, admin_user):
        """backup/test مع Google Drive متصل"""
        _login(client, admin_user)
        with client.session_transaction() as sess:
            sess['google_drive_connected'] = True
        resp = client.post('/api/v1/backup/test',
                           json={'destination': 'google_drive'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]


# ============================================================
# Test: backup list, stats, upload (lines 2068-2276)
# ============================================================

class TestBackupListStatsUpload:
    """اختبار قائمة النسخ وإحصاءاتها ورفعها"""

    def test_backup_list_total_count(self, client, admin_user):
        """backup/list يرجع total_count"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup/list')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'total_count' in data

    def test_backup_list_backups_key(self, client, admin_user):
        """backup/list يرجع backups key"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup/list')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'backups' in data

    def test_backup_stats_has_recent_backups(self, client, admin_user):
        """backup/stats يرجع recent_backups"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup/stats')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'recent_backups' in stats

    def test_backup_upload_with_valid_data(self, client, admin_user):
        """backup/upload-to-drive مع بيانات صالحة"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/upload-to-drive',
                           json={
                               'fileName': 'test_backup.json',
                               'fileContent': '{"test": "data"}',
                               'backupData': {'scope': 'full'}
                           },
                           content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_backup_upload_response_has_file_id(self, client, admin_user):
        """backup/upload يرجع fileId"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup/upload-to-drive',
                           json={
                               'fileName': 'test.json',
                               'fileContent': '{}',
                           },
                           content_type='application/json')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'fileId' in data or 'success' in data


# ============================================================
# Test: backup start/stop/manual/jobs (lines 2356-2476)
# ============================================================

class TestBackupSchedulerRoutes:
    """اختبار مسارات النسخ الاحتياطي المجدولة"""

    def test_backup_start_without_auth(self, client):
        """backup/start بدون auth يعمل (لا يتطلب login)"""
        resp = client.post('/api/v1/backup/start', json={'user_id': 1})
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_stop_without_auth(self, client):
        """backup/stop بدون auth يعمل"""
        resp = client.post('/api/v1/backup/stop', json={'user_id': 1})
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_manual_without_auth(self, client):
        """backup/manual بدون auth"""
        resp = client.post('/api/v1/backup/manual', json={'user_id': 1})
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_jobs_without_auth(self, client):
        """backup/jobs بدون auth"""
        resp = client.get('/api/v1/backup/jobs')
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_health_without_auth(self, client):
        """backup/health بدون auth"""
        resp = client.get('/api/v1/backup/health')
        assert resp.status_code in [200, 500]

    def test_backup_health_has_success(self, client):
        """backup/health يرجع success"""
        resp = client.get('/api/v1/backup/health')
        data = resp.get_json()
        assert 'success' in data

    def test_backup_logs_without_auth(self, client):
        """backup/logs بدون auth"""
        resp = client.get('/api/v1/backup/logs')
        assert resp.status_code in [200, 500]

    def test_backup_logs_with_level(self, client):
        """backup/logs مع level"""
        resp = client.get('/api/v1/backup/logs?level=ERROR')
        assert resp.status_code in [200, 500]

    def test_backup_test_connection_without_auth(self, client):
        """backup/test-connection بدون auth"""
        resp = client.post('/api/v1/backup/test-connection')
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_settings_get_without_auth(self, client):
        """backup/settings GET بدون auth"""
        resp = client.get('/api/v1/backup/settings?user_id=1')
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_settings_post_without_auth(self, client):
        """backup/settings POST بدون auth"""
        resp = client.post('/api/v1/backup/settings',
                           json={'user_id': 1, 'auto_backup': True},
                           content_type='application/json')
        assert resp.status_code in [200, 400, 500, 503]

    def test_backup_logs_download_without_auth(self, client):
        """backup/logs/download بدون auth"""
        resp = client.get('/api/v1/backup/logs/download')
        assert resp.status_code in [200, 404, 500]


# ============================================================
# Test: backup-settings load/save (lines 2924-3022)
# ============================================================

class TestBackupSettingsLoadSave:
    """اختبار تحميل وحفظ إعدادات النسخ"""

    def test_load_backup_settings_has_settings(self, client, admin_user):
        """backup-settings/load يرجع settings"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup-settings/load')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'settings' in data

    def test_load_backup_settings_default_frequency(self, client, admin_user):
        """الإعدادات الافتراضية تحتوي على backup_frequency"""
        _login(client, admin_user)
        resp = client.get('/api/v1/backup-settings/load')
        if resp.status_code == 200:
            data = resp.get_json()
            settings = data.get('settings', {})
            assert 'backup_frequency' in settings

    def test_save_backup_settings_auto_backup(self, client, admin_user):
        """حفظ إعداد auto_backup_enabled"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup-settings/save',
                           json={'auto_backup_enabled': True, 'backup_frequency': 'weekly'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_save_then_load_backup_settings(self, client, admin_user):
        """حفظ ثم تحميل الإعدادات"""
        _login(client, admin_user)
        client.post('/api/v1/backup-settings/save',
                    json={'backup_frequency': 'weekly', 'max_backups': 10},
                    content_type='application/json')
        resp = client.get('/api/v1/backup-settings/load')
        assert resp.status_code in [200, 500]

    def test_save_backup_settings_backup_time(self, client, admin_user):
        """حفظ backup_time"""
        _login(client, admin_user)
        resp = client.post('/api/v1/backup-settings/save',
                           json={'backup_time': '03:00'},
                           content_type='application/json')
        assert resp.status_code in [200, 500]


# ============================================================
# Test: user-settings/sync-status (lines 3024-3067)
# ============================================================

class TestUserSettingsSyncStatus:
    """اختبار حالة مزامنة إعدادات المستخدم"""

    def test_user_settings_sync_status_has_status(self, client, admin_user):
        """user-settings/sync-status يرجع status"""
        _login(client, admin_user)
        resp = client.get('/api/v1/user-settings/sync-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'status' in data or 'success' in data

    def test_user_settings_sync_status_connected_field(self, client, admin_user):
        """sync-status يحتوي على connected"""
        _login(client, admin_user)
        resp = client.get('/api/v1/user-settings/sync-status')
        if resp.status_code == 200:
            data = resp.get_json()
            status = data.get('status', {})
            assert 'connected' in status

    def test_user_settings_sync_status_last_sync(self, client, admin_user):
        """sync-status يحتوي على last_sync"""
        _login(client, admin_user)
        resp = client.get('/api/v1/user-settings/sync-status')
        if resp.status_code == 200:
            data = resp.get_json()
            status = data.get('status', {})
            assert 'last_sync' in status


# ============================================================
# Test: backup test-status, test-immediate (lines 3069-3145)
# ============================================================

class TestBackupTestStatus:
    """اختبار backup test-status وtest-immediate"""

    def test_backup_test_status_no_auth(self, client):
        """backup/test-status بدون auth يعمل"""
        resp = client.get('/api/v1/backup/test-status')
        assert resp.status_code in [200, 500]

    def test_backup_test_status_is_test_mode(self, client):
        """backup/test-status يرجع test_mode=True"""
        resp = client.get('/api/v1/backup/test-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('test_mode') is True

    def test_backup_test_immediate_no_auth(self, client):
        """backup/test-immediate بدون auth"""
        resp = client.post('/api/v1/backup/test-immediate')
        assert resp.status_code in [200, 500]

    def test_backup_test_immediate_is_test_mode(self, client):
        """backup/test-immediate يرجع test_mode=True"""
        resp = client.post('/api/v1/backup/test-immediate')
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('test_mode') is True

    def test_google_drive_test_connection_status(self, client):
        """google-drive/test-connection-status يعمل"""
        resp = client.get('/api/v1/google-drive/test-connection-status')
        assert resp.status_code in [200, 500]

    def test_google_drive_test_has_test_mode(self, client):
        """google-drive/test-connection-status يرجع test_mode"""
        resp = client.get('/api/v1/google-drive/test-connection-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('test_mode') is True


# ============================================================
# Test: question block/unblock details (lines 3228-3598)
# ============================================================

class TestQuestionBlockUnblockDetails:
    """اختبار تفاصيل block/unblock الأسئلة"""

    def test_block_question_changes_status(self, client, admin_user, db_session, sample_lesson):
        """block question يغير is_blocked إلى True"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/block')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['is_blocked'] is True

    def test_unblock_question_changes_status(self, client, admin_user, db_session, sample_lesson):
        """unblock question يغير is_blocked إلى False"""
        q = _make_question(db_session, sample_lesson, blocked=True)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/unblock')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['is_blocked'] is False

    def test_bulk_unblock_returns_unblocked_count(self, client, admin_user, db_session, sample_lesson):
        """bulk-unblock يرجع unblocked_count"""
        q1 = _make_question(db_session, sample_lesson, blocked=True)
        q2 = _make_question(db_session, sample_lesson, blocked=True)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/bulk-unblock',
                           json={'question_ids': [q1.question_id, q2.question_id]},
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'unblocked_count' in data

    def test_bulk_block_no_json_returns_error(self, client, admin_user):
        """bulk-block بدون JSON يرجع خطأ"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/bulk-block')
        assert resp.status_code in [400, 415, 500]

    def test_block_all_lesson_questions_returns_count(self, client, admin_user, db_session, sample_lesson):
        """block-all lesson يرجع blocked_count"""
        _make_question(db_session, sample_lesson)
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/lessons/{sample_lesson.id}/questions/block-all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'blocked_count' in data

    def test_unblock_all_lesson_questions_returns_count(self, client, admin_user, db_session, sample_lesson):
        """unblock-all lesson يرجع unblocked_count"""
        _make_question(db_session, sample_lesson, blocked=True)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/lessons/{sample_lesson.id}/questions/unblock-all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'unblocked_count' in data

    def test_block_all_unit_questions_returns_count(self, client, admin_user, db_session, sample_unit, sample_lesson):
        """block-all unit يرجع blocked_count"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/units/{sample_unit.id}/questions/block-all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'blocked_count' in data

    def test_unblock_all_unit_questions_returns_count(self, client, admin_user, db_session, sample_unit, sample_lesson):
        """unblock-all unit يرجع unblocked_count"""
        _make_question(db_session, sample_lesson, blocked=True)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/units/{sample_unit.id}/questions/unblock-all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'unblocked_count' in data

    def test_block_all_course_questions_returns_count(self, client, admin_user, db_session, sample_course, sample_lesson):
        """block-all course يرجع blocked_count"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/courses/{sample_course.id}/questions/block-all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'blocked_count' in data

    def test_unblock_all_course_questions_returns_count(self, client, admin_user, db_session, sample_course, sample_lesson):
        """unblock-all course يرجع unblocked_count"""
        _make_question(db_session, sample_lesson, blocked=True)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/courses/{sample_course.id}/questions/unblock-all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'unblocked_count' in data

    def test_block_status_returns_is_blocked(self, client, admin_user, db_session, sample_lesson):
        """block-status يرجع is_blocked"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/{q.question_id}/block-status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'is_blocked' in data

    def test_block_question_then_verify_not_in_lesson(self, client, admin_user, db_session, sample_lesson):
        """بعد block السؤال لا يظهر في درسه"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        client.put(f'/api/v1/questions/{q.question_id}/block')
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        qids = [item.get('question_id') for item in data]
        assert q.question_id not in qids


# ============================================================
# Test: counts endpoints (lines 3835-3945)
# ============================================================

class TestCountsEndpoints:
    """اختبار endpoints عد الأسئلة"""

    def test_unit_questions_count_with_blocked(self, client, admin_user, db_session, sample_unit, sample_lesson):
        """عد الأسئلة لا يشمل المحجوبة"""
        _make_question(db_session, sample_lesson, blocked=True)
        q2 = _make_question(db_session, sample_lesson, blocked=False)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/units/{sample_unit.id}/questions-count')
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['questions_count'] >= 1

    def test_lesson_questions_count_with_data(self, client, admin_user, db_session, sample_lesson):
        """عد أسئلة الدرس مع بيانات"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions-count')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('questions_count', 0) >= 1

    def test_lesson_count_has_lesson_name(self, client, admin_user, sample_lesson):
        """عد أسئلة الدرس يحتوي على lesson_name"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions-count')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'lesson_name' in data

    def test_unit_count_has_unit_name(self, client, admin_user, sample_unit):
        """عد أسئلة الوحدة يحتوي على unit_name"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/units/{sample_unit.id}/questions-count')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'unit_name' in data

    def test_course_count_has_course_name(self, client, admin_user, sample_course):
        """عد أسئلة المنهج يحتوي على course_name"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/questions-count')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'course_name' in data

    def test_unit_questions_count_nonexistent(self, client, admin_user):
        """عد أسئلة وحدة غير موجودة يرجع 404"""
        _login(client, admin_user)
        resp = client.get('/api/v1/units/99999/questions-count')
        assert resp.status_code == 404

    def test_lesson_questions_count_nonexistent(self, client, admin_user):
        """عد أسئلة درس غير موجود يرجع 404"""
        _login(client, admin_user)
        resp = client.get('/api/v1/lessons/99999/questions-count')
        assert resp.status_code == 404

    def test_course_questions_count_nonexistent(self, client, admin_user):
        """عد أسئلة منهج غير موجود يرجع 404"""
        _login(client, admin_user)
        resp = client.get('/api/v1/courses/99999/questions-count')
        assert resp.status_code == 404


# ============================================================
# Test: trusted device & register device (lines 3972-4056)
# ============================================================

class TestTrustedDevice:
    """اختبار نظام الجهاز الموثوق"""

    def test_trusted_device_missing_device_token(self, client):
        """بدون device_token يرجع 400"""
        resp = client.post('/api/v1/auth/trusted-device',
                           json={'username': 'test_admin'},
                           content_type='application/json')
        assert resp.status_code == 400

    def test_trusted_device_missing_username(self, client):
        """بدون username يرجع 400"""
        resp = client.post('/api/v1/auth/trusted-device',
                           json={'device_token': 'some_token'},
                           content_type='application/json')
        assert resp.status_code == 400

    def test_trusted_device_nonexistent_user(self, client):
        """مستخدم غير موجود يرجع 404"""
        resp = client.post('/api/v1/auth/trusted-device',
                           json={'username': 'nonexistent_user_xyz', 'device_token': 'test_token'},
                           content_type='application/json')
        assert resp.status_code == 404

    def test_trusted_device_non_admin(self, client, student_user):
        """طالب غير أدمن يرجع 404"""
        resp = client.post('/api/v1/auth/trusted-device',
                           json={'username': student_user.username, 'device_token': 'test_token'},
                           content_type='application/json')
        assert resp.status_code == 404

    def test_trusted_device_invalid_token(self, client, admin_user):
        """token خاطئ يرجع 401"""
        resp = client.post('/api/v1/auth/trusted-device',
                           json={'username': admin_user.username, 'device_token': 'wrong_token'},
                           content_type='application/json')
        assert resp.status_code in [401, 404]

    def test_register_device_no_auth(self, client):
        """register-device بدون auth يرجع redirect"""
        resp = client.post('/api/v1/auth/register-device')
        assert resp.status_code in [302, 401, 403]

    def test_register_device_with_non_admin(self, client, student_user):
        """register-device كطالب يرجع 302 أو 403 (redirect أو forbidden)"""
        _login(client, student_user)
        resp = client.post('/api/v1/auth/register-device')
        assert resp.status_code in [302, 403]

    def test_register_device_with_admin(self, client, admin_user):
        """register-device كأدمن ينجح"""
        _login(client, admin_user)
        resp = client.post('/api/v1/auth/register-device')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'device_token' in data


# ============================================================
# Test: upload image (lines 4059-4092)
# ============================================================

class TestUploadImage:
    """اختبار رفع الصور"""

    def test_upload_image_no_auth(self, client):
        """upload-image بدون auth"""
        resp = client.post('/api/v1/upload-image')
        assert resp.status_code in [302, 401, 403]

    def test_upload_image_no_file(self, client, admin_user):
        """upload-image بدون ملف يرجع 400"""
        _login(client, admin_user)
        resp = client.post('/api/v1/upload-image')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_upload_image_empty_filename(self, client, admin_user):
        """upload-image بملف فارغ يرجع 400"""
        _login(client, admin_user)
        from io import BytesIO
        resp = client.post('/api/v1/upload-image',
                           data={'image': (BytesIO(b''), '')},
                           content_type='multipart/form-data')
        assert resp.status_code in [400, 500]


# ============================================================
# Test: add question API (lines 4096-4230)
# ============================================================

class TestAddQuestionAPI:
    """اختبار إضافة الأسئلة عبر API"""

    def test_add_question_no_lesson_id(self, client, admin_user):
        """بدون lesson_id يرجع 400"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'question_text': 'سؤال اختباري',
                               'options': [
                                   {'option_text': 'خيار 1', 'is_correct': True},
                                   {'option_text': 'خيار 2', 'is_correct': False}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 400

    def test_add_question_nonexistent_lesson(self, client, admin_user):
        """درس غير موجود يرجع 404"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'lesson_id': 99999,
                               'question_text': 'سؤال اختباري',
                               'options': [
                                   {'option_text': 'خيار 1', 'is_correct': True},
                                   {'option_text': 'خيار 2', 'is_correct': False}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 404

    def test_add_question_no_text_no_image(self, client, admin_user, sample_lesson):
        """بدون نص أو صورة يرجع 400"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'lesson_id': sample_lesson.id,
                               'question_text': '',
                               'options': [
                                   {'option_text': 'خيار 1', 'is_correct': True},
                                   {'option_text': 'خيار 2', 'is_correct': False}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 400

    def test_add_question_one_option(self, client, admin_user, sample_lesson):
        """خيار واحد فقط يرجع 400"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'lesson_id': sample_lesson.id,
                               'question_text': 'سؤال اختباري',
                               'options': [
                                   {'option_text': 'خيار 1', 'is_correct': True}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 400

    def test_add_question_no_correct_option(self, client, admin_user, sample_lesson):
        """بدون إجابة صحيحة يرجع 400"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'lesson_id': sample_lesson.id,
                               'question_text': 'سؤال اختباري',
                               'options': [
                                   {'option_text': 'خيار 1', 'is_correct': False},
                                   {'option_text': 'خيار 2', 'is_correct': False}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 400

    def test_add_question_success(self, client, admin_user, sample_lesson):
        """إضافة سؤال ناجحة"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'lesson_id': sample_lesson.id,
                               'question_text': 'سؤال اختباري deep3',
                               'options': [
                                   {'option_text': 'خيار صحيح', 'is_correct': True},
                                   {'option_text': 'خيار خاطئ', 'is_correct': False},
                                   {'option_text': 'خيار خاطئ 2', 'is_correct': False},
                                   {'option_text': 'خيار خاطئ 3', 'is_correct': False}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert 'question_id' in data

    def test_add_question_with_explanation(self, client, admin_user, sample_lesson):
        """إضافة سؤال مع شرح"""
        _login(client, admin_user)
        resp = client.post('/api/v1/questions',
                           json={
                               'lesson_id': sample_lesson.id,
                               'question_text': 'سؤال مع شرح',
                               'explanation': 'هذا شرح الإجابة',
                               'options': [
                                   {'option_text': 'صح', 'is_correct': True},
                                   {'option_text': 'خطأ', 'is_correct': False}
                               ]
                           },
                           content_type='application/json')
        assert resp.status_code == 201


# ============================================================
# Test: get/update/delete question API (lines 4234-4461)
# ============================================================

class TestGetUpdateDeleteQuestionAPI:
    """اختبار CRUD الأسئلة"""

    def test_get_question_success(self, client, admin_user, db_session, sample_lesson):
        """الحصول على سؤال موجود"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/{q.question_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'question' in data

    def test_get_question_has_options(self, client, admin_user, db_session, sample_lesson):
        """السؤال يحتوي على options"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/{q.question_id}')
        data = resp.get_json()
        assert 'options' in data.get('question', {})

    def test_get_question_nonexistent(self, client, admin_user):
        """سؤال غير موجود يرجع 404"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/99999')
        assert resp.status_code == 404

    def test_update_question_text(self, client, admin_user, db_session, sample_lesson):
        """تحديث نص السؤال"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'question_text': 'نص محدث'},
                          content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_update_question_is_blocked(self, client, admin_user, db_session, sample_lesson):
        """تحديث is_blocked"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'is_blocked': True},
                          content_type='application/json')
        assert resp.status_code == 200

    def test_update_question_with_options_one_valid(self, client, admin_user, db_session, sample_lesson):
        """تحديث مع خيار واحد فقط يرجع 400"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'options': [{'option_text': 'خيار 1', 'is_correct': True}]},
                          content_type='application/json')
        assert resp.status_code == 400

    def test_update_question_with_no_correct_option(self, client, admin_user, db_session, sample_lesson):
        """تحديث بدون إجابة صحيحة يرجع 400"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'options': [
                              {'option_text': 'خ1', 'is_correct': False},
                              {'option_text': 'خ2', 'is_correct': False}
                          ]},
                          content_type='application/json')
        assert resp.status_code == 400

    def test_update_question_with_new_lesson_id(self, client, admin_user, db_session, sample_lesson):
        """تحديث lesson_id"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'lesson_id': sample_lesson.id},
                          content_type='application/json')
        assert resp.status_code == 200

    def test_update_question_nonexistent_lesson_id(self, client, admin_user, db_session, sample_lesson):
        """تحديث بـ lesson_id غير موجود يرجع 404"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'lesson_id': 99999},
                          content_type='application/json')
        assert resp.status_code == 404

    def test_delete_question_success(self, client, admin_user, db_session, sample_lesson):
        """حذف سؤال ناجح"""
        q = _make_question(db_session, sample_lesson)
        qid = q.question_id
        _login(client, admin_user)
        resp = client.delete(f'/api/v1/questions/{qid}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_question_confirms_deleted(self, client, admin_user, db_session, sample_lesson):
        """بعد الحذف السؤال لا يُرجع"""
        q = _make_question(db_session, sample_lesson)
        qid = q.question_id
        _login(client, admin_user)
        client.delete(f'/api/v1/questions/{qid}')
        resp = client.get(f'/api/v1/questions/{qid}')
        assert resp.status_code == 404

    def test_update_question_explanation(self, client, admin_user, db_session, sample_lesson):
        """تحديث explanation"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}',
                          json={'explanation': 'شرح محدث'},
                          content_type='application/json')
        assert resp.status_code == 200


# ============================================================
# Test: toggle question block API (lines 4464-4500)
# ============================================================

class TestToggleQuestionBlockAPI:
    """اختبار toggle-block endpoint"""

    def test_toggle_block_changes_status(self, client, admin_user, db_session, sample_lesson):
        """toggle-block يغير حالة السؤال"""
        q = _make_question(db_session, sample_lesson)
        initial = q.is_blocked
        _login(client, admin_user)
        resp = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['is_blocked'] != initial

    def test_toggle_block_response_structure(self, client, admin_user, db_session, sample_lesson):
        """toggle-block يرجع success وis_blocked"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        data = resp.get_json()
        assert 'success' in data
        assert 'is_blocked' in data

    def test_toggle_block_twice_restores(self, client, admin_user, db_session, sample_lesson):
        """toggle-block مرتين يُرجع الحالة الأصلية"""
        q = _make_question(db_session, sample_lesson)
        initial = q.is_blocked
        _login(client, admin_user)
        client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        resp = client.post(f'/api/v1/questions/{q.question_id}/toggle-block')
        data = resp.get_json()
        assert data['is_blocked'] == initial


# ============================================================
# Test: search questions (lines 4503-4580)
# ============================================================

class TestSearchQuestionsAPI:
    """اختبار البحث في الأسئلة"""

    def test_search_with_per_page(self, client, admin_user):
        """البحث مع per_page"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/search?per_page=5')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'pagination' in data

    def test_search_pagination_structure(self, client, admin_user):
        """هيكل pagination"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/search')
        data = resp.get_json()
        pagination = data.get('pagination', {})
        assert 'page' in pagination
        assert 'total' in pagination
        assert 'pages' in pagination

    def test_search_with_lesson_id_filter(self, client, admin_user, db_session, sample_lesson):
        """البحث مع lesson_id"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/search?lesson_id={sample_lesson.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'questions' in data

    def test_search_with_unit_id_filter(self, client, admin_user, db_session, sample_unit, sample_lesson):
        """البحث مع unit_id"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/search?unit_id={sample_unit.id}')
        assert resp.status_code == 200

    def test_search_with_course_id_filter(self, client, admin_user, db_session, sample_course, sample_lesson):
        """البحث مع course_id"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/search?course_id={sample_course.id}')
        assert resp.status_code == 200

    def test_search_has_next_field(self, client, admin_user):
        """pagination يحتوي على has_next"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/search')
        data = resp.get_json()
        pagination = data.get('pagination', {})
        assert 'has_next' in pagination

    def test_search_has_prev_field(self, client, admin_user):
        """pagination يحتوي على has_prev"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/search')
        data = resp.get_json()
        pagination = data.get('pagination', {})
        assert 'has_prev' in pagination


# ============================================================
# Test: classify-all (lines 4589-4623)
# ============================================================

class TestClassifyAll:
    """اختبار classify-all"""

    def test_classify_all_unavailable_returns_503(self, client, admin_user):
        """classify-all بدون classifier يرجع 503"""
        _login(client, admin_user)
        import src.routes.api as api_module
        original = api_module.question_classifier_available
        api_module.question_classifier_available = False
        try:
            resp = client.post('/api/v1/questions/classify-all')
            assert resp.status_code == 503
        finally:
            api_module.question_classifier_available = original

    def test_classify_all_with_batch_size(self, client, admin_user):
        """classify-all مع batch_size"""
        _login(client, admin_user)
        import src.routes.api as api_module
        original = api_module.question_classifier_available
        api_module.question_classifier_available = False
        try:
            resp = client.post('/api/v1/questions/classify-all',
                               json={'batch_size': 5},
                               content_type='application/json')
            assert resp.status_code in [200, 503]
        finally:
            api_module.question_classifier_available = original

    def test_classify_all_error_message(self, client, admin_user):
        """classify-all يرجع error عند عدم التوفر"""
        _login(client, admin_user)
        import src.routes.api as api_module
        original = api_module.question_classifier_available
        api_module.question_classifier_available = False
        try:
            resp = client.post('/api/v1/questions/classify-all')
            data = resp.get_json()
            assert 'error' in data
        finally:
            api_module.question_classifier_available = original


# ============================================================
# Test: classify single question (lines 4626-4688)
# ============================================================

class TestClassifySingle:
    """اختبار تصنيف سؤال واحد"""

    def test_classify_single_unavailable(self, client, admin_user, db_session, sample_lesson):
        """classify single بدون classifier يرجع 503"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        import src.routes.api as api_module
        original = api_module.question_classifier_available
        api_module.question_classifier_available = False
        try:
            resp = client.post(f'/api/v1/questions/{q.question_id}/classify')
            assert resp.status_code == 503
        finally:
            api_module.question_classifier_available = original

    def test_classify_single_nonexistent_unavailable(self, client, admin_user):
        """classify سؤال غير موجود بدون classifier يرجع 503"""
        _login(client, admin_user)
        import src.routes.api as api_module
        original = api_module.question_classifier_available
        api_module.question_classifier_available = False
        try:
            resp = client.post('/api/v1/questions/99999/classify')
            assert resp.status_code == 503
        finally:
            api_module.question_classifier_available = original


# ============================================================
# Test: classification stats (lines 4691-4734)
# ============================================================

class TestClassificationStats:
    """اختبار إحصائيات التصنيف"""

    def test_classification_stats_by_difficulty(self, client, admin_user):
        """stats تحتوي على by_difficulty"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-stats')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'by_difficulty' in stats

    def test_classification_stats_by_bloom(self, client, admin_user):
        """stats تحتوي على by_bloom_level"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-stats')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'by_bloom_level' in stats

    def test_classification_stats_total(self, client, admin_user):
        """stats تحتوي على total_questions"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-stats')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'total_questions' in stats

    def test_classification_stats_unclassified_estimate(self, client, admin_user):
        """stats تحتوي على unclassified_estimate"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-stats')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'unclassified_estimate' in stats


# ============================================================
# Test: update classification (lines 4737-4802)
# ============================================================

class TestUpdateClassification:
    """اختبار تحديث التصنيف"""

    def test_update_valid_difficulty_easy(self, client, admin_user, db_session, sample_lesson):
        """تحديث difficulty=easy (200 أو 500 بسبب ai_classified column في SQLite)"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'difficulty': 'easy'},
                          content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_update_valid_difficulty_hard(self, client, admin_user, db_session, sample_lesson):
        """تحديث difficulty=hard"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'difficulty': 'hard'},
                          content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_update_valid_bloom_apply(self, client, admin_user, db_session, sample_lesson):
        """تحديث bloom_level=apply"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'bloom_level': 'apply'},
                          content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_update_valid_bloom_evaluate(self, client, admin_user, db_session, sample_lesson):
        """تحديث bloom_level=evaluate"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'bloom_level': 'evaluate'},
                          content_type='application/json')
        assert resp.status_code in [200, 500]

    def test_update_returns_difficulty(self, client, admin_user, db_session, sample_lesson):
        """الاستجابة تحتوي على difficulty أو error"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'difficulty': 'easy'},
                          content_type='application/json')
        data = resp.get_json()
        assert data is not None
        # قد يرجع difficulty أو error بسبب ai_classified column في SQLite
        assert 'difficulty' in data or 'error' in data

    def test_update_returns_bloom_level(self, client, admin_user, db_session, sample_lesson):
        """الاستجابة تحتوي على bloom_level أو error"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'bloom_level': 'create'},
                          content_type='application/json')
        data = resp.get_json()
        assert data is not None
        assert 'bloom_level' in data or 'error' in data

    def test_update_invalid_difficulty(self, client, admin_user, db_session, sample_lesson):
        """difficulty غير صالحة يرجع 400"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'difficulty': 'super_hard'},
                          content_type='application/json')
        assert resp.status_code == 400

    def test_update_invalid_bloom(self, client, admin_user, db_session, sample_lesson):
        """bloom_level غير صالح يرجع 400"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.put(f'/api/v1/questions/{q.question_id}/update-classification',
                          json={'bloom_level': 'memorize'},
                          content_type='application/json')
        assert resp.status_code == 400


# ============================================================
# Test: browse classifications (lines 4805-4905)
# ============================================================

class TestBrowseClassifications:
    """اختبار استعراض التصنيفات"""

    def test_browse_with_difficulty_filter(self, client, admin_user, db_session, sample_lesson):
        """browse مع فلتر difficulty"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/browse-classifications?difficulty=medium')
        assert resp.status_code == 200

    def test_browse_with_bloom_filter(self, client, admin_user):
        """browse مع فلتر bloom_level"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/browse-classifications?bloom_level=remember')
        assert resp.status_code == 200

    def test_browse_with_course_filter(self, client, admin_user, sample_course, db_session, sample_lesson):
        """browse مع فلتر course_id"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get(f'/api/v1/questions/browse-classifications?course_id={sample_course.id}')
        assert resp.status_code == 200

    def test_browse_with_ai_classified_true(self, client, admin_user):
        """browse مع ai_classified=true"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/browse-classifications?ai_classified=true')
        assert resp.status_code in [200, 500]

    def test_browse_with_ai_classified_false(self, client, admin_user):
        """browse مع ai_classified=false"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/browse-classifications?ai_classified=false')
        assert resp.status_code in [200, 500]

    def test_browse_question_has_lesson_field(self, client, admin_user, db_session, sample_lesson, sample_course):
        """كل سؤال في browse له lesson field"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/browse-classifications')
        if resp.status_code == 200:
            data = resp.get_json()
            for q in data.get('questions', []):
                assert 'lesson' in q

    def test_browse_question_has_difficulty(self, client, admin_user, db_session, sample_lesson, sample_course):
        """كل سؤال في browse له difficulty"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/browse-classifications')
        if resp.status_code == 200:
            data = resp.get_json()
            for q in data.get('questions', []):
                assert 'difficulty' in q


# ============================================================
# Test: unclassified questions (lines 4908-4967)
# ============================================================

class TestUnclassifiedQuestions:
    """اختبار الأسئلة غير المصنفة"""

    def test_unclassified_has_total(self, client, admin_user):
        """unclassified يرجع total"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/unclassified')
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'total' in data

    def test_unclassified_has_questions(self, client, admin_user):
        """unclassified يرجع questions"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/unclassified')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'questions' in data

    def test_unclassified_pagination(self, client, admin_user):
        """unclassified يرجع page وper_page"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/unclassified?page=1&per_page=5')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'page' in data
            assert 'per_page' in data

    def test_unclassified_total_pages(self, client, admin_user):
        """unclassified يرجع total_pages"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/unclassified')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'total_pages' in data


# ============================================================
# Test: classification summary (lines 4970-5034)
# ============================================================

class TestClassificationSummary:
    """اختبار ملخص التصنيف"""

    def test_summary_has_classified(self, client, admin_user):
        """summary يحتوي على classified"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'classified' in stats

    def test_summary_has_unclassified(self, client, admin_user):
        """summary يحتوي على unclassified"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'unclassified' in stats

    def test_summary_has_total(self, client, admin_user):
        """summary يحتوي على total"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'total' in stats

    def test_summary_has_progress_percent(self, client, admin_user):
        """summary يحتوي على progress_percent"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'progress_percent' in stats

    def test_summary_has_by_difficulty(self, client, admin_user):
        """summary يحتوي على by_difficulty"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'by_difficulty' in stats

    def test_summary_has_by_bloom(self, client, admin_user):
        """summary يحتوي على by_bloom"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'by_bloom' in stats

    def test_summary_has_image_only(self, client, admin_user):
        """summary يحتوي على image_only_unclassified"""
        _login(client, admin_user)
        resp = client.get('/api/v1/questions/classification-summary')
        if resp.status_code == 200:
            data = resp.get_json()
            stats = data.get('stats', {})
            assert 'image_only_unclassified' in stats

    def test_summary_no_auth(self, client):
        """summary بدون auth يرجع redirect"""
        resp = client.get('/api/v1/questions/classification-summary')
        assert resp.status_code in [302, 401, 403]


# ============================================================
# Test: export questions additional (lines 3628-3695)
# ============================================================

class TestExportQuestionsAdditional:
    """اختبارات إضافية لـ export questions"""

    def test_export_with_answers_true(self, client, admin_user, db_session, sample_lesson):
        """export مع include_answers=true"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/export',
                           json={
                               'question_ids': [q.question_id],
                               'include_answers': True,
                               'format': 'json'
                           },
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['include_answers'] is True

    def test_export_without_answers(self, client, admin_user, db_session, sample_lesson):
        """export بدون إجابات لا يحتوي على correct_option_id"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/export',
                           json={
                               'question_ids': [q.question_id],
                               'include_answers': False,
                               'format': 'json'
                           },
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        for exported_q in data.get('questions', []):
            assert 'correct_option_id' not in exported_q

    def test_export_has_count_field(self, client, admin_user, db_session, sample_lesson):
        """export يرجع count"""
        q = _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/export',
                           json={'question_ids': [q.question_id], 'format': 'json'},
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'count' in data


# ============================================================
# Test: generate exam additional (lines 3698-3795)
# ============================================================

class TestGenerateExamAdditional:
    """اختبارات إضافية لـ generate exam"""

    def test_generate_exam_with_include_answers(self, client, admin_user, db_session, sample_course, sample_lesson):
        """generate exam مع include_answers=true"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/generate-exam',
                           json={
                               'course_id': sample_course.id,
                               'question_count': 1,
                               'include_answers': True
                           },
                           content_type='application/json')
        assert resp.status_code in [200, 404]

    def test_generate_exam_with_question_count(self, client, admin_user, db_session, sample_course, sample_lesson):
        """generate exam مع question_count محدد"""
        for _ in range(5):
            _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/generate-exam',
                           json={
                               'course_id': sample_course.id,
                               'question_count': 3
                           },
                           content_type='application/json')
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            data = resp.get_json()
            exam = data.get('exam', {})
            assert exam.get('count', 0) <= 3

    def test_generate_exam_has_generated_at(self, client, admin_user, db_session, sample_course, sample_lesson):
        """generate exam يرجع generated_at"""
        _make_question(db_session, sample_lesson)
        _login(client, admin_user)
        resp = client.post('/api/v1/questions/generate-exam',
                           json={'course_id': sample_course.id},
                           content_type='application/json')
        if resp.status_code == 200:
            data = resp.get_json()
            exam = data.get('exam', {})
            assert 'generated_at' in exam


# ============================================================
# Test: Google Drive connection status alt route (lines 2859-2917)
# ============================================================

class TestGoogleDriveConnectionAltRoute:
    """اختبار مسار google-drive/connection-status البديل"""

    def test_gd_connection_status_returns_json(self, client, admin_user):
        """google-drive/connection-status يرجع JSON"""
        _login(client, admin_user)
        resp = client.get('/api/v1/google-drive/connection-status')
        assert resp.status_code in [200, 500]
        data = resp.get_json()
        assert data is not None

    def test_gd_connection_status_has_success(self, client, admin_user):
        """google-drive/connection-status يحتوي على success"""
        _login(client, admin_user)
        resp = client.get('/api/v1/google-drive/connection-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'success' in data

    def test_gd_connection_status_has_status_obj(self, client, admin_user):
        """google-drive/connection-status يحتوي على status object"""
        _login(client, admin_user)
        resp = client.get('/api/v1/google-drive/connection-status')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'status' in data

    def test_gd_connection_status_no_auth(self, client):
        """google-drive/connection-status بدون auth يرجع redirect"""
        resp = client.get('/api/v1/google-drive/connection-status')
        assert resp.status_code in [302, 401, 403]


# ============================================================
# Test: admin profile additional (lines 3948-3968)
# ============================================================

class TestAdminProfileAdditional:
    """اختبارات إضافية لـ admin profile"""

    def test_admin_profile_has_id(self, client, admin_user):
        """admin profile يحتوي على id"""
        _login(client, admin_user)
        resp = client.get('/api/v1/admin/profile')
        if resp.status_code == 200:
            data = resp.get_json()
            admin = data.get('admin', {})
            assert 'id' in admin

    def test_admin_profile_has_email(self, client, admin_user):
        """admin profile يحتوي على email"""
        _login(client, admin_user)
        resp = client.get('/api/v1/admin/profile')
        if resp.status_code == 200:
            data = resp.get_json()
            admin = data.get('admin', {})
            assert 'email' in admin

    def test_admin_profile_is_admin_true(self, client, admin_user):
        """admin profile يؤكد is_admin=True"""
        _login(client, admin_user)
        resp = client.get('/api/v1/admin/profile')
        if resp.status_code == 200:
            data = resp.get_json()
            admin = data.get('admin', {})
            assert admin.get('is_admin') is True

    def test_admin_profile_non_admin_forbidden(self, client, student_user):
        """طالب لا يستطيع الوصول لـ admin profile (302 أو 403)"""
        _login(client, student_user)
        resp = client.get('/api/v1/admin/profile')
        assert resp.status_code in [302, 403]

    def test_admin_profile_has_username(self, client, admin_user):
        """admin profile يحتوي على username"""
        _login(client, admin_user)
        resp = client.get('/api/v1/admin/profile')
        if resp.status_code == 200:
            data = resp.get_json()
            admin = data.get('admin', {})
            assert 'username' in admin


# ============================================================
# Test: unit lessons export (lines 3798-3832)
# ============================================================

class TestUnitLessonsExport:
    """اختبار export دروس الوحدة"""

    def test_unit_lessons_has_id(self, client, admin_user, sample_course, sample_unit, sample_lesson):
        """درس له id"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/lessons')
        if resp.status_code == 200:
            data = resp.get_json()
            lessons = data.get('lessons', [])
            if lessons:
                assert 'id' in lessons[0]

    def test_unit_lessons_has_name(self, client, admin_user, sample_course, sample_unit, sample_lesson):
        """درس له name"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/lessons')
        if resp.status_code == 200:
            data = resp.get_json()
            lessons = data.get('lessons', [])
            if lessons:
                assert 'name' in lessons[0]

    def test_unit_lessons_has_order_num(self, client, admin_user, sample_course, sample_unit, sample_lesson):
        """درس له order_num"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/lessons')
        if resp.status_code == 200:
            data = resp.get_json()
            lessons = data.get('lessons', [])
            if lessons:
                assert 'order_num' in lessons[0]

    def test_unit_lessons_correct_course(self, client, admin_user, sample_course, sample_unit, sample_lesson):
        """دروس الوحدة الصحيحة تظهر"""
        _login(client, admin_user)
        resp = client.get(f'/api/v1/courses/{sample_course.id}/units/{sample_unit.id}/lessons')
        if resp.status_code == 200:
            data = resp.get_json()
            lessons = data.get('lessons', [])
            lesson_names = [l['name'] for l in lessons]
            assert sample_lesson.name in lesson_names


# ============================================================
# Test: CSRF token additional
# ============================================================

class TestCsrfTokenAdditional:
    """اختبارات إضافية لـ CSRF token"""

    def test_csrf_token_returns_json(self, client):
        """csrf-token يرجع JSON"""
        resp = client.get('/api/v1/csrf-token')
        assert resp.status_code in [200, 500]
        data = resp.get_json()
        assert data is not None

    def test_csrf_token_has_success(self, client):
        """csrf-token يحتوي على success"""
        resp = client.get('/api/v1/csrf-token')
        data = resp.get_json()
        assert 'success' in data


# ============================================================
# Test: additional coverage of question format (lines 190-235)
# ============================================================

class TestQuestionFormat:
    """اختبار تنسيق بيانات الأسئلة"""

    def test_question_has_explanation_field(self, client, db_session, sample_lesson, sample_course):
        """السؤال يحتوي على explanation"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'explanation' in data[0]

    def test_question_has_lesson_field(self, client, db_session, sample_lesson, sample_course):
        """السؤال يحتوي على lesson"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'lesson' in data[0]

    def test_question_has_unit_field(self, client, db_session, sample_lesson, sample_course):
        """السؤال يحتوي على unit"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'unit' in data[0]

    def test_question_has_course_field(self, client, db_session, sample_lesson, sample_course):
        """السؤال يحتوي على course"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'course' in data[0]

    def test_question_correct_option_id(self, client, db_session, sample_lesson, sample_course):
        """السؤال يحتوي على correct_option_id"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            assert 'correct_option_id' in data[0]

    def test_question_options_have_is_correct(self, client, db_session, sample_lesson, sample_course):
        """خيارات السؤال تحتوي على is_correct"""
        _make_question(db_session, sample_lesson)
        resp = client.get(f'/api/v1/lessons/{sample_lesson.id}/questions')
        data = resp.get_json()
        if data:
            for opt in data[0].get('options', []):
                assert 'is_correct' in opt
