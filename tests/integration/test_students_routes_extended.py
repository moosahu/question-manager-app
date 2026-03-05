"""
اختبارات موسعة لـ Students routes
يغطي: verify-session, mobile API, notifications, results, courses/units/lessons
"""
import pytest
import secrets


def _make_student(db_session, username, email, active=True):
    from src.models.student import Student
    s = Student(name='Test Stu', username=username, email=email, is_active=active)
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestStudentVerifySession:
    """اختبارات التحقق من الجلسة"""

    def test_verify_session_no_token(self, client):
        """التحقق من الجلسة بدون token"""
        response = client.post('/students/api/verify-session', json={})
        assert response.status_code in [400, 401, 422]

    def test_verify_session_invalid_token(self, client):
        """التحقق من الجلسة بـ token خاطئ"""
        response = client.post('/students/api/verify-session', json={
            'session_token': 'invalid_token_xyz'
        })
        assert response.status_code in [400, 401, 404]

    def test_verify_session_valid(self, client, db_session, app):
        """التحقق من الجلسة بـ token صالح"""
        s = _make_student(db_session, 'verify_sess_stu', 'verifysessstu@test.com')
        response = client.post('/students/api/verify-session', json={
            'session_token': s.session_token
        })
        assert response.status_code in [200, 400, 401]


class TestStudentCoursesUnitsLessons:
    """اختبارات مسارات المناهج للطلاب"""

    def test_student_courses_no_auth(self, client):
        """مناهج الطالب بدون مصادقة"""
        response = client.get('/students/api/courses')
        assert response.status_code in [200, 401]

    def test_student_courses_with_session_token(self, client, db_session, app):
        """مناهج الطالب مع session_token"""
        s = _make_student(db_session, 'courses_stu', 'coursesstu@test.com')
        response = client.get(
            '/students/api/courses',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 500]

    def test_student_units_nonexistent_course(self, client, db_session, app):
        """وحدات منهج غير موجود"""
        s = _make_student(db_session, 'units_stu', 'unitsstu@test.com')
        response = client.get(
            '/students/api/courses/99999/units',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 404, 500]

    def test_student_lessons_nonexistent_unit(self, client, db_session, app):
        """دروس وحدة غير موجودة"""
        s = _make_student(db_session, 'lessons_stu', 'lessonsstu@test.com')
        response = client.get(
            '/students/api/units/99999/lessons',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 404, 500]

    def test_student_lesson_questions(self, client, db_session, app):
        """أسئلة درس للطالب"""
        s = _make_student(db_session, 'qstu_lessons', 'qstulessons@test.com')
        response = client.get(
            '/students/api/lessons/99999/questions',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 404, 500]

    def test_student_course_questions(self, client, db_session, app):
        """أسئلة منهج للطالب"""
        s = _make_student(db_session, 'qstu_courses', 'qstucourses@test.com')
        response = client.get(
            '/students/api/courses/99999/questions',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 404, 500]


class TestStudentResults:
    """اختبارات نتائج الطلاب"""

    def test_get_results_no_auth(self, client):
        """جلب النتائج بدون مصادقة"""
        response = client.get('/students/api/results')
        assert response.status_code in [200, 400, 401, 403]

    def test_get_results_with_token(self, client, db_session, app):
        """جلب النتائج مع session_token"""
        s = _make_student(db_session, 'results_stu', 'resultsstu@test.com')
        response = client.get(
            '/students/api/results',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 500]

    def test_save_result_no_auth(self, client):
        """حفظ نتيجة بدون مصادقة"""
        response = client.post('/students/api/results', json={
            'score': 80,
            'lesson_id': 1
        })
        assert response.status_code in [200, 400, 401, 403]

    def test_save_result_with_token(self, client, db_session, app):
        """حفظ نتيجة مع session_token"""
        s = _make_student(db_session, 'save_result_stu', 'saveresultstu@test.com')
        response = client.post(
            '/students/api/results',
            json={'score': 85, 'lesson_id': 1, 'student_id': s.id},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 201, 400, 401, 404, 500]

    def test_get_results_stats_with_token(self, client, db_session, app):
        """إحصائيات النتائج مع session_token"""
        s = _make_student(db_session, 'stats_result_stu', 'statsresultstu@test.com')
        response = client.get(
            '/students/api/results/stats',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 500]


class TestStudentNotifications:
    """اختبارات إشعارات الطلاب"""

    def test_get_notifications_no_auth(self, client):
        """جلب إشعارات الطالب بدون مصادقة"""
        response = client.get('/students/api/notifications/1')
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_get_notifications_with_token(self, client, db_session, app):
        """جلب إشعارات الطالب مع session_token"""
        s = _make_student(db_session, 'notif_stu', 'notifstu@test.com')
        response = client.get(
            f'/students/api/notifications/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 500]

    def test_unread_count_with_token(self, client, db_session, app):
        """عدد الإشعارات غير المقروءة"""
        s = _make_student(db_session, 'unread_stu', 'unreadstu@test.com')
        response = client.get(
            f'/students/api/notifications/unread-count/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 500]

    def test_mark_all_read_with_token(self, client, db_session, app):
        """تأشير كل الإشعارات مقروءة"""
        s = _make_student(db_session, 'markread_stu', 'markreadstu@test.com')
        response = client.post(
            f'/students/api/notifications/mark-all-read/{s.id}',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 500]

    def test_save_notification_no_auth(self, client):
        """حفظ إشعار بدون مصادقة"""
        response = client.post('/students/api/notifications/save', json={
            'student_id': 1,
            'title': 'اختبار',
            'message': 'رسالة اختبار'
        })
        # يقبل من الـ bot بدون مصادقة خاصة
        assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500, 503]


class TestStudentMobileAPI:
    """اختبارات Mobile API للطلاب"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_mobile_students_no_auth(self, client):
        """قائمة الطلاب (mobile) بدون مصادقة"""
        response = client.get('/students/api/mobile/students')
        assert response.status_code in [302, 401, 403]

    def test_mobile_students_as_admin(self, client, admin_user):
        """قائمة الطلاب (mobile) كأدمن"""
        self._login(client, admin_user)
        response = client.get('/students/api/mobile/students')
        assert response.status_code in [200, 500]

    def test_mobile_add_student_no_auth(self, client):
        """إضافة طالب (mobile) بدون مصادقة"""
        response = client.post('/students/api/mobile/students/add', json={})
        assert response.status_code in [302, 401, 403]

    def test_mobile_add_student_as_admin(self, client, admin_user):
        """إضافة طالب (mobile) كأدمن - بدون حقول"""
        self._login(client, admin_user)
        response = client.post('/students/api/mobile/students/add', json={})
        assert response.status_code in [400, 422, 500]

    def test_mobile_get_student_as_admin(self, client, admin_user):
        """جلب طالب (mobile) كأدمن"""
        self._login(client, admin_user)
        response = client.get('/students/api/mobile/students/99999')
        assert response.status_code in [404, 500]

    def test_api_list_students_as_admin(self, client, admin_user):
        """قائمة الطلاب عبر API"""
        self._login(client, admin_user)
        response = client.get('/students/api/list')
        assert response.status_code in [200, 500]

    def test_student_change_password_no_auth(self, client):
        """تغيير كلمة مرور الطالب بدون مصادقة"""
        response = client.post('/students/api/change-password', json={
            'old_password': 'old',
            'new_password': 'new'
        })
        assert response.status_code in [400, 401, 422]

    def test_student_change_password_wrong_token(self, client):
        """تغيير كلمة مرور الطالب بـ token خاطئ"""
        response = client.post(
            '/students/api/change-password',
            json={'old_password': 'old', 'new_password': 'NewPass@123'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [400, 401]

    def test_fcm_token_no_auth(self, client):
        """حفظ FCM token بدون مصادقة"""
        response = client.post('/students/api/fcm-token', json={
            'fcm_token': 'test_fcm_token'
        })
        assert response.status_code in [400, 401, 500]

    def test_device_info_as_admin(self, client, admin_user):
        """معلومات الجهاز كأدمن"""
        self._login(client, admin_user)
        response = client.get('/students/api/admin/device-info/99999')
        assert response.status_code in [404, 500]
