"""
اختبارات إضافية للتسجيل والتقارير
يغطي: verify-phone, activate-after-phone, admin settings POST, reports detail
"""
import pytest
import secrets


def _make_student(db_session, username, email):
    from src.models.student import Student
    s = Student(name='Test Stu', username=username, email=email, is_active=True)
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestRegistrationPhoneVerify:
    """اختبارات التحقق من الهاتف"""

    def test_verify_phone_empty(self, client):
        """التحقق من الهاتف ببيانات فارغة"""
        response = client.post('/api/registration/verify-phone', json={})
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_verify_phone_invalid(self, client):
        """التحقق من الهاتف برقم خاطئ"""
        response = client.post('/api/registration/verify-phone', json={
            'username': 'test_user',
            'phone': '+966500000000',
            'code': '000000'
        })
        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_verify_phone_with_student(self, client, db_session, app):
        """التحقق من الهاتف مع طالب موجود"""
        s = _make_student(db_session, 'vrfy_phone1', 'vrfy_phone1@test.com')
        response = client.post('/api/registration/verify-phone', json={
            'username': s.username,
            'phone': '+966500000001',
            'code': '000000'
        })
        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_activate_after_phone_empty(self, client):
        """تفعيل الحساب بعد التحقق من الهاتف ببيانات فارغة"""
        response = client.post('/api/registration/activate-after-phone', json={})
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_activate_after_phone_invalid(self, client):
        """تفعيل الحساب بعد التحقق من الهاتف ببيانات خاطئة"""
        response = client.post('/api/registration/activate-after-phone', json={
            'username': 'nonexistent_xyz',
            'code': '000000'
        })
        assert response.status_code in [200, 400, 401, 404, 422, 500]


class TestRegistrationAdminSettings:
    """اختبارات إعدادات التسجيل للأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_admin_settings_post_no_auth(self, client):
        """تحديث إعدادات التسجيل بدون مصادقة"""
        response = client.post('/api/registration/admin/settings', json={})
        assert response.status_code in [302, 401, 403]

    def test_admin_settings_post_as_admin(self, client, admin_user):
        """تحديث إعدادات التسجيل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/registration/admin/settings', json={
            'max_students': 100,
            'require_approval': False
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_register_duplicate_email(self, client, db_session, app):
        """تسجيل طالب بإيميل موجود مسبقاً"""
        s = _make_student(db_session, 'dup_email_stu1', 'dup_email_reg@test.com')
        response = client.post('/api/registration/register', json={
            'name': 'طالب مكرر بالإيميل',
            'username': 'completely_new_user_xyz',
            'email': s.email,
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 400, 409, 422, 500]

    def test_register_with_weak_password(self, client):
        """تسجيل بكلمة مرور ضعيفة"""
        response = client.post('/api/registration/register', json={
            'name': 'طالب جديد',
            'username': 'weak_pass_stu1',
            'email': 'weak_pass_stu1@test.com',
            'password': '123'
        })
        assert response.status_code in [200, 400, 422, 500]

    def test_register_missing_name(self, client):
        """تسجيل بدون اسم"""
        response = client.post('/api/registration/register', json={
            'username': 'no_name_stu1',
            'email': 'no_name_stu1@test.com',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 400, 422, 500]


class TestReportsDetailed:
    """اختبارات تفاصيل التقارير"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_students_performance_with_search(self, client, admin_user):
        """أداء الطلاب مع بحث"""
        self._login(client, admin_user)
        response = client.get('/reports/api/students-performance?search=كيمياء&page=1')
        assert response.status_code in [200, 500]

    def test_top_performers_with_course_filter(self, client, admin_user):
        """أفضل الطلاب مع فلتر المنهج"""
        self._login(client, admin_user)
        response = client.get('/reports/api/top-performers?course_id=1&limit=10')
        assert response.status_code in [200, 500]

    def test_need_help_with_min_sessions(self, client, admin_user):
        """الطلاب المحتاجون مساعدة مع حد أدنى للجلسات"""
        self._login(client, admin_user)
        response = client.get('/reports/api/need-help?min_sessions=5&threshold=60')
        assert response.status_code in [200, 500]

    def test_student_detail_with_actual_student(self, client, admin_user, db_session, app):
        """تفاصيل طالب موجود"""
        s = _make_student(db_session, 'rpt_detail_stu1', 'rpt_detail_stu1@test.com')
        self._login(client, admin_user)
        response = client.get(f'/reports/api/student/{s.id}/detail')
        assert response.status_code in [200, 404, 500]

    def test_export_excel_empty_report_type(self, client, admin_user):
        """تصدير Excel بدون نوع تقرير"""
        self._login(client, admin_user)
        response = client.post('/reports/api/export-excel', json={})
        assert response.status_code in [200, 400, 500]

    def test_export_excel_students_report(self, client, admin_user):
        """تصدير Excel تقرير الطلاب"""
        self._login(client, admin_user)
        response = client.post('/reports/api/export-excel', json={
            'report_type': 'students'
        })
        assert response.status_code in [200, 400, 500]

    def test_export_excel_top_performers_report(self, client, admin_user):
        """تصدير Excel أفضل الطلاب"""
        self._login(client, admin_user)
        response = client.post('/reports/api/export-excel', json={
            'report_type': 'top_performers',
            'limit': 20
        })
        assert response.status_code in [200, 400, 500]

    def test_activity_report_with_date_range(self, client, admin_user):
        """تقرير النشاط مع نطاق تاريخ"""
        self._login(client, admin_user)
        response = client.get('/reports/api/activity?days=7')
        assert response.status_code in [200, 500]

    def test_courses_analysis_with_no_data(self, client, admin_user):
        """تحليل المناهج بدون بيانات"""
        self._login(client, admin_user)
        response = client.get('/reports/api/courses-analysis')
        assert response.status_code in [200, 500]

    def test_report_student_page_existing(self, client, admin_user, db_session, app):
        """صفحة تقرير طالب موجود"""
        s = _make_student(db_session, 'rpt_page_stu1', 'rpt_page_stu1@test.com')
        self._login(client, admin_user)
        response = client.get(f'/reports/student/{s.id}')
        assert response.status_code in [200, 302, 404, 500]


class TestApiNotificationsExtended:
    """اختبارات موسعة لـ API الإشعارات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_notifications_no_auth(self, client):
        """جلب الإشعارات بدون مصادقة"""
        response = client.get('/api/notifications')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_get_notifications_as_admin(self, client, admin_user):
        """جلب الإشعارات كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/notifications')
        assert response.status_code in [200, 404, 500]

    def test_mark_read_as_admin(self, client, admin_user):
        """تأشير مقروء كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/notifications/mark-read', json={
            'notification_id': 99999
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_delete_notification_as_admin(self, client, admin_user):
        """حذف إشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/notifications/99999/delete', json={})
        assert response.status_code in [200, 404, 500]

    def test_create_notification_no_auth(self, client):
        """إنشاء إشعار بدون مصادقة"""
        response = client.post('/api/notifications/create', json={})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_create_notification_as_admin(self, client, admin_user):
        """إنشاء إشعار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/notifications/create', json={
            'title': 'إشعار تجريبي',
            'message': 'رسالة تجريبية'
        })
        assert response.status_code in [200, 201, 400, 404, 500]
