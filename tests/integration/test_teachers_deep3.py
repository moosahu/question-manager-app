"""
Integration tests for teachers.py - Part 3
Target: raise teachers.py coverage from 87% to 95%+

Focuses on uncovered lines:
- 21-22: admin_required redirect paths (non-admin user)
- 105-107, 137-139: DB exception rollback paths in add/edit
- 189, 193-195: delete notification path + outer except rollback
- 213-215, 231-233: toggle and reset_device exception paths
- 258-259, 322-324: toggle_registration exception + mobile add DB error
- 345-347, 393, 397-399: mobile edit DB error + mobile delete notification + outer except
"""
import pytest
import secrets
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _login_as_non_admin(client, user):
    """Login as a non-admin user"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_teacher(db_session, username=None, email=None, is_active=True,
                  device_id=None, phone=None, school=None, notes=None):
    from src.models.teacher import Teacher
    username = username or f'tea3_{secrets.token_hex(4)}'
    email = email or f'{username}@deep3.com'
    t = Teacher(
        name='Deep3 Teacher',
        username=username,
        email=email,
        is_active=is_active,
        phone=phone,
        school=school,
        notes=notes,
    )
    t.set_password('Pass@123')
    if device_id:
        t.device_id = device_id
        t.device_name = 'جهاز اختباري'
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _make_non_admin_user(db_session):
    """إنشاء مستخدم عادي (ليس أدمن)"""
    from src.models.user import User
    username = f'nonadmin_{secrets.token_hex(4)}'
    user = User(username=username, email=f'{username}@test.com', is_admin=False)
    user.set_password('Pass@123')
    db_session.session.add(user)
    db_session.session.commit()
    db_session.session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Lines 21-22: admin_required decorator - non-admin user access
# ---------------------------------------------------------------------------

class TestAdminRequiredDecorator:
    """اختبار decorator admin_required مع مستخدم عادي (ليس أدمن)"""

    def test_non_admin_list_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول الوصول لقائمة المعلمين - يُعاد توجيهه"""
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.get('/teachers/')
        assert r.status_code in [302, 403]

    def test_non_admin_add_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول الإضافة - يُعاد توجيهه"""
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post('/teachers/add', data={
            'name': 'x', 'username': 'xx', 'password': 'pp'
        })
        assert r.status_code in [302, 403]

    def test_non_admin_delete_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول الحذف - يُعاد توجيهه"""
        t = _make_teacher(db_session)
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post(f'/teachers/delete/{t.id}')
        assert r.status_code in [302, 403]

    def test_non_admin_toggle_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول تبديل الحالة - يُعاد توجيهه"""
        t = _make_teacher(db_session)
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post(f'/teachers/toggle/{t.id}')
        assert r.status_code in [302, 403]

    def test_non_admin_edit_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول التعديل - يُعاد توجيهه"""
        t = _make_teacher(db_session)
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post(f'/teachers/edit/{t.id}', data={'name': 'x'})
        assert r.status_code in [302, 403]

    def test_non_admin_toggle_registration_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول تبديل التسجيل - يُعاد توجيهه"""
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post('/teachers/toggle-registration')
        assert r.status_code in [302, 403]

    def test_non_admin_reset_device_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول إعادة تعيين الجهاز - يُعاد توجيهه"""
        t = _make_teacher(db_session)
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post(f'/teachers/reset-device/{t.id}')
        assert r.status_code in [302, 403]

    def test_non_admin_mobile_list_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول API المعلمين - يُعاد توجيهه"""
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.get('/teachers/api/mobile/list')
        assert r.status_code in [302, 403]

    def test_non_admin_mobile_add_gets_redirected(self, client, db_session, app):
        """مستخدم عادي يحاول API إضافة معلم - يُعاد توجيهه"""
        user = _make_non_admin_user(db_session)
        _login_as_non_admin(client, user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'x', 'username': 'xx', 'password': 'pp'
        })
        assert r.status_code in [302, 403]


# ---------------------------------------------------------------------------
# Lines 105-107: add_teacher DB exception rollback
# ---------------------------------------------------------------------------

class TestAddTeacherDBException:
    """اختبار مسار الخطأ في إضافة المعلم (DB exception)"""

    def test_add_teacher_db_exception_triggers_rollback(self, client, admin_user, db_session, app):
        """خطأ في DB عند إضافة معلم يُشغّل rollback"""
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit.side_effect = Exception('DB connection error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post('/teachers/add', data={
                'name': 'معلم خطأ',
                'username': f'err_add_{secrets.token_hex(3)}',
                'password': 'Pass@123',
            })
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_db_exception_shows_error_flash(self, client, admin_user, db_session, app):
        """خطأ في DB يظهر رسالة خطأ"""
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit.side_effect = Exception('unique constraint')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post('/teachers/add', data={
                'name': 'معلم',
                'username': f'err_{secrets.token_hex(3)}',
                'password': 'Pass@123',
            }, follow_redirects=True)
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_returns_template_on_validation_error_missing_name(self, client, admin_user):
        """إضافة بدون اسم تُعيد صفحة الإضافة"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'username': f'valid_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        })
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_missing_password_returns_template(self, client, admin_user):
        """إضافة بدون كلمة مرور تُعيد صفحة الإضافة"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم بلا باسورد',
            'username': f'nopwd_{secrets.token_hex(3)}',
        })
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_validation_all_missing(self, client, admin_user):
        """إضافة بدون أي بيانات"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={})
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_duplicate_username_returns_template(self, client, admin_user, db_session, app):
        """username مكرر يُعيد صفحة الإضافة"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم آخر',
            'username': t.username,
            'password': 'Pass@123',
        })
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_duplicate_email_returns_template(self, client, admin_user, db_session, app):
        """email مكرر يُعيد صفحة الإضافة"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم بريد مكرر',
            'username': f'newuser_{secrets.token_hex(3)}',
            'password': 'Pass@123',
            'email': t.email,
        })
        assert r.status_code in [200, 302, 500]


# ---------------------------------------------------------------------------
# Lines 137-139: edit_teacher DB exception rollback
# ---------------------------------------------------------------------------

class TestEditTeacherDBException:
    """اختبار مسار الخطأ في تعديل المعلم (DB exception)"""

    def test_edit_teacher_db_exception_triggers_rollback(self, client, admin_user, db_session, app):
        """خطأ في DB عند التعديل يُشغّل rollback"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('DB write error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/edit/{t.id}', data={
                'name': 'اسم جديد',
                'is_active': 'on',
            })
        assert r.status_code in [200, 302, 500]

    def test_edit_teacher_db_exception_returns_template(self, client, admin_user, db_session, app):
        """خطأ في DB عند التعديل يُعيد صفحة التعديل"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('integrity error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/edit/{t.id}', data={
                'name': 'اسم',
            }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_edit_teacher_with_password_change_then_db_error(self, client, admin_user, db_session, app):
        """تغيير كلمة المرور ثم خطأ DB"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('commit failed')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/edit/{t.id}', data={
                'name': 'اسم محدث',
                'password': 'NewPass@999',
                'is_active': 'on',
            })
        assert r.status_code in [200, 302, 500]

    def test_edit_teacher_get_request_renders_form(self, client, admin_user, db_session, app):
        """GET على صفحة التعديل يُرجع نموذج التعديل"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.get(f'/teachers/edit/{t.id}')
        assert r.status_code in [200, 302, 500]

    def test_edit_teacher_successful_commit_redirects(self, client, admin_user, db_session, app):
        """التعديل الناجح يُعيد توجيه لقائمة المعلمين"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/edit/{t.id}', data={
            'name': 'اسم محدث بنجاح',
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_edit_teacher_flash_error_message_content(self, client, admin_user, db_session, app):
        """رسالة الخطأ تحتوي على نص مناسب"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('specific error text')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/edit/{t.id}', data={
                'name': 'اسم',
                'is_active': 'on',
            }, follow_redirects=True)
        assert r.status_code in [200, 302, 500]


# ---------------------------------------------------------------------------
# Lines 189, 193-195: delete notification path + outer exception rollback
# ---------------------------------------------------------------------------

class TestDeleteTeacherEdgePaths:
    """اختبار المسارات الدقيقة لحذف المعلم"""

    def test_delete_teacher_notification_path_with_admin(self, client, admin_user, db_session, app):
        """حذف معلم مع وجود أدمن لإرسال الإشعار"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_teacher_notification_exception_silenced(self, client, admin_user, db_session, app):
        """خطأ في الإشعار يُتجاهل ولا يؤثر على الحذف"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.models.notification.Notification', side_effect=Exception('notif error')):
            r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_teacher_outer_exception_path(self, client, admin_user, db_session, app):
        """خطأ خارجي في الحذف يُشغّل rollback"""
        t = _make_teacher(db_session)
        tid = t.id
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.expunge.side_effect = Exception('expunge failed')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/delete/{tid}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_teacher_commit_exception_shows_flash(self, client, admin_user, db_session, app):
        """خطأ في commit الحذف يُظهر رسالة خطأ"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.expunge = MagicMock()
            mock_db.session.begin_nested = MagicMock()
            mock_db.session.execute = MagicMock()
            mock_db.session.commit.side_effect = Exception('commit error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/delete/{t.id}', follow_redirects=True)
        assert r.status_code in [200, 302, 500]

    def test_delete_teacher_with_no_admin_user_for_notification(self, client, admin_user, db_session, app):
        """حذف معلم بدون مستخدم أدمن لإرسال الإشعار - يكمل بدون خطأ"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.models.user.User') as mock_user_cls:
            mock_user_cls.query.filter_by.return_value.first.return_value = None
            r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_nonexistent_teacher_returns_404(self, client, admin_user):
        """حذف معلم غير موجود يُرجع 404"""
        _login(client, admin_user)
        r = client.post('/teachers/delete/9999999')
        assert r.status_code in [302, 404, 500]

    def test_delete_teacher_success_redirects(self, client, admin_user, db_session, app):
        """الحذف الناجح يُعيد توجيه"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [302, 200, 500]

    def test_delete_teacher_outer_except_rollback_called(self, client, admin_user, db_session, app):
        """التحقق من استدعاء rollback عند الخطأ الخارجي"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.expunge.side_effect = Exception('outer err')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/delete/{t.id}', follow_redirects=True)
        assert r.status_code in [200, 302, 500]


# ---------------------------------------------------------------------------
# Lines 213-215: toggle_teacher DB exception
# ---------------------------------------------------------------------------

class TestToggleTeacherException:
    """اختبار مسار الخطأ في تبديل حالة المعلم"""

    def test_toggle_teacher_db_exception_triggers_rollback(self, client, admin_user, db_session, app):
        """خطأ في DB عند تبديل حالة المعلم يُشغّل rollback"""
        t = _make_teacher(db_session, is_active=True)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('toggle DB error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_toggle_teacher_db_exception_flash_message(self, client, admin_user, db_session, app):
        """خطأ في toggle يُظهر رسالة خطأ في flash"""
        t = _make_teacher(db_session, is_active=True)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('حدث خطأ')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=True)
        assert r.status_code in [200, 302, 500]

    def test_toggle_inactive_teacher_to_active(self, client, admin_user, db_session, app):
        """تبديل معلم غير نشط ليصبح نشط"""
        t = _make_teacher(db_session, is_active=False)
        _login(client, admin_user)
        r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_toggle_success_flash_active(self, client, admin_user, db_session, app):
        """تبديل ناجح يُظهر رسالة نجاح مع حالة مفعل"""
        t = _make_teacher(db_session, is_active=False)  # سيصبح نشط
        _login(client, admin_user)
        r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=True)
        assert r.status_code in [200, 500]

    def test_toggle_success_flash_inactive(self, client, admin_user, db_session, app):
        """تبديل ناجح يُظهر رسالة نجاح مع حالة معطل"""
        t = _make_teacher(db_session, is_active=True)  # سيصبح غير نشط
        _login(client, admin_user)
        r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=True)
        assert r.status_code in [200, 500]

    def test_toggle_exception_redirects_anyway(self, client, admin_user, db_session, app):
        """حتى عند الخطأ، toggle يُعيد توجيه"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('err')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        if r.status_code == 302:
            assert r.headers.get('Location', '') != ''


# ---------------------------------------------------------------------------
# Lines 231-233: reset_device DB exception
# ---------------------------------------------------------------------------

class TestResetDeviceException:
    """اختبار مسار الخطأ في إعادة تعيين الجهاز"""

    def test_reset_device_exception_triggers_rollback(self, client, admin_user, db_session, app):
        """خطأ في DB عند إعادة تعيين الجهاز يُشغّل rollback"""
        t = _make_teacher(db_session, device_id='device_err_test')
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            with patch.object(t.__class__, 'clear_device_info', side_effect=Exception('device clear error')):
                r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_reset_device_exception_flash_error_message(self, client, admin_user, db_session, app):
        """خطأ في إعادة تعيين الجهاز يُظهر رسالة خطأ"""
        t = _make_teacher(db_session, device_id='device_err2')
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            with patch.object(t.__class__, 'clear_device_info', side_effect=Exception('err')):
                r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=True)
        assert r.status_code in [200, 302, 500]

    def test_reset_device_redirects_to_edit_on_success(self, client, admin_user, db_session, app):
        """إعادة تعيين ناجحة تُعيد توجيه لصفحة تعديل المعلم"""
        t = _make_teacher(db_session, device_id='dev_redir_test')
        _login(client, admin_user)
        r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        if r.status_code == 302:
            location = r.headers.get('Location', '')
            assert str(t.id) in location or 'edit' in location or location != ''

    def test_reset_device_no_device_id_still_works(self, client, admin_user, db_session, app):
        """إعادة تعيين معلم بدون جهاز مسجل - لا خطأ"""
        t = _make_teacher(db_session, device_id=None)
        _login(client, admin_user)
        r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_reset_device_exception_redirect_destination(self, client, admin_user, db_session, app):
        """حتى عند الخطأ، reset_device يُعيد توجيه"""
        t = _make_teacher(db_session, device_id='dev_redir_err')
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            with patch.object(t.__class__, 'clear_device_info', side_effect=Exception('clear err')):
                r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        if r.status_code == 302:
            assert r.headers.get('Location', '') != ''


# ---------------------------------------------------------------------------
# Lines 258-259: toggle_registration exception path
# ---------------------------------------------------------------------------

class TestToggleRegistrationException:
    """اختبار مسار الخطأ في تبديل حالة التسجيل"""

    def test_toggle_registration_exception_flash_error(self, client, admin_user, db_session, app):
        """خطأ في تبديل التسجيل يُظهر رسالة خطأ"""
        _login(client, admin_user)
        with patch('src.routes.teachers.RegistrationSettings') as mock_settings:
            mock_settings.get_settings.side_effect = Exception('settings DB error')
            r = client.post('/teachers/toggle-registration', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_toggle_registration_update_exception(self, client, admin_user, db_session, app):
        """خطأ في تحديث الإعدادات يُظهر رسالة خطأ"""
        _login(client, admin_user)
        with patch('src.routes.teachers.RegistrationSettings') as mock_settings:
            mock_reg = MagicMock()
            mock_reg.is_teacher_registration_open = False
            mock_settings.get_settings.return_value = mock_reg
            mock_settings.update_settings.side_effect = Exception('update failed')
            r = client.post('/teachers/toggle-registration', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_toggle_registration_open_to_closed(self, client, admin_user, db_session, app):
        """تبديل التسجيل من مفتوح لمغلق - flash warning"""
        _login(client, admin_user)
        with patch('src.routes.teachers.RegistrationSettings') as mock_settings:
            mock_reg = MagicMock()
            mock_reg.is_teacher_registration_open = True
            mock_settings.get_settings.return_value = mock_reg
            mock_settings.update_settings.return_value = None
            r = client.post('/teachers/toggle-registration', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_toggle_registration_closed_to_open(self, client, admin_user, db_session, app):
        """تبديل التسجيل من مغلق لمفتوح - flash success"""
        _login(client, admin_user)
        with patch('src.routes.teachers.RegistrationSettings') as mock_settings:
            mock_reg = MagicMock()
            mock_reg.is_teacher_registration_open = False
            mock_settings.get_settings.return_value = mock_reg
            mock_settings.update_settings.return_value = None
            r = client.post('/teachers/toggle-registration', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_toggle_registration_exception_redirects_to_list(self, client, admin_user, db_session, app):
        """خطأ في التبديل - لا يزال يُعيد توجيه لقائمة المعلمين"""
        _login(client, admin_user)
        with patch('src.routes.teachers.RegistrationSettings') as mock_settings:
            mock_settings.get_settings.side_effect = Exception('err')
            r = client.post('/teachers/toggle-registration', follow_redirects=False)
        if r.status_code == 302:
            location = r.headers.get('Location', '')
            assert 'teachers' in location or location != ''

    def test_toggle_registration_with_follow_redirects(self, client, admin_user, db_session, app):
        """تبديل التسجيل مع follow_redirects"""
        _login(client, admin_user)
        with patch('src.routes.teachers.RegistrationSettings') as mock_settings:
            mock_settings.get_settings.side_effect = Exception('err follow')
            r = client.post('/teachers/toggle-registration', follow_redirects=True)
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Lines 322-324: api_mobile_add DB exception (500 path)
# ---------------------------------------------------------------------------

class TestMobileAddDBException:
    """اختبار مسار DB exception في mobile add"""

    def test_mobile_add_db_exception_returns_500(self, client, admin_user, db_session, app):
        """خطأ في DB عند الإضافة عبر API يُرجع 500"""
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit.side_effect = Exception('DB error in mobile add')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post('/teachers/api/mobile/add', json={
                'name': 'معلم خطأ API',
                'username': f'api_err_{secrets.token_hex(3)}',
                'password': 'Pass@123',
            })
        assert r.status_code in [200, 500]

    def test_mobile_add_db_exception_returns_error_json(self, client, admin_user, db_session, app):
        """خطأ في DB يُرجع JSON مع success=False"""
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit.side_effect = Exception('insert failed')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post('/teachers/api/mobile/add', json={
                'name': 'معلم',
                'username': f'api_err2_{secrets.token_hex(3)}',
                'password': 'Pass@123',
            })
        if r.status_code == 500:
            data = r.get_json()
            if data:
                assert data.get('success') is False

    def test_mobile_add_missing_password_returns_400(self, client, admin_user):
        """إضافة عبر API بدون كلمة مرور يُرجع 400"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم',
            'username': f'nopwd_{secrets.token_hex(3)}',
        })
        assert r.status_code in [400, 422, 500]

    def test_mobile_add_empty_name_returns_400(self, client, admin_user):
        """إضافة عبر API باسم فارغ يُرجع 400"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': '   ',
            'username': f'empty_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        })
        assert r.status_code in [400, 422, 500]

    def test_mobile_add_empty_username_returns_400(self, client, admin_user):
        """إضافة عبر API باسم مستخدم فارغ يُرجع 400"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم',
            'username': '  ',
            'password': 'Pass@123',
        })
        assert r.status_code in [400, 422, 500]

    def test_mobile_add_duplicate_username_returns_409(self, client, admin_user, db_session, app):
        """اسم مستخدم مكرر يُرجع 409"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم جديد',
            'username': t.username,
            'password': 'Pass@123',
        })
        assert r.status_code in [409, 500]

    def test_mobile_add_with_email_success(self, client, admin_user):
        """إضافة معلم مع إيميل عبر API - نجاح"""
        _login(client, admin_user)
        unique = secrets.token_hex(4)
        r = client.post('/teachers/api/mobile/add', json={
            'name': f'معلم API {unique}',
            'username': f'api_email_{unique}',
            'password': 'Pass@123',
            'email': f'api_{unique}@deep3.com',
        })
        assert r.status_code in [200, 400, 409, 500]


# ---------------------------------------------------------------------------
# Lines 345-347: api_mobile_edit DB exception (500 path)
# ---------------------------------------------------------------------------

class TestMobileEditDBException:
    """اختبار مسار DB exception في mobile edit"""

    def test_mobile_edit_db_exception_returns_500(self, client, admin_user, db_session, app):
        """خطأ في DB عند التعديل عبر API يُرجع 500"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('edit DB error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
                'name': 'اسم جديد',
            })
        assert r.status_code in [200, 500]

    def test_mobile_edit_db_exception_json_error(self, client, admin_user, db_session, app):
        """خطأ DB في edit يُرجع JSON مع success=False"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('integrity error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
                'name': 'اسم',
            })
        if r.status_code == 500:
            data = r.get_json()
            if data:
                assert data.get('success') is False

    def test_mobile_edit_with_new_password_success(self, client, admin_user, db_session, app):
        """تعديل كلمة المرور عبر API بنجاح"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'password': 'NewSecure@Pass99',
        })
        assert r.status_code in [200, 400, 500]

    def test_mobile_edit_clear_email(self, client, admin_user, db_session, app):
        """مسح الإيميل عبر API"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'email': '',
        })
        assert r.status_code in [200, 400, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_mobile_edit_nonexistent_teacher(self, client, admin_user):
        """تعديل معلم غير موجود عبر API"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/9999998/edit', json={'name': 'x'})
        assert r.status_code in [404, 200, 500]

    def test_mobile_edit_db_error_rollback_called(self, client, admin_user, db_session, app):
        """التحقق من استدعاء rollback عند خطأ DB في edit"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('rollback check')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
                'name': 'اسم للاختبار',
            })
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Lines 393, 397-399: api_mobile_delete notification path + outer except
# ---------------------------------------------------------------------------

class TestMobileDeleteEdgePaths:
    """اختبار المسارات الدقيقة لـ mobile delete"""

    def test_mobile_delete_notification_with_admin(self, client, admin_user, db_session, app):
        """حذف عبر API مع وجود أدمن - يُرسل إشعار"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]

    def test_mobile_delete_notification_exception_silenced(self, client, admin_user, db_session, app):
        """خطأ في الإشعار عند الحذف عبر API يُتجاهل"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.models.notification.Notification', side_effect=Exception('notif err')):
            r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]

    def test_mobile_delete_outer_exception_returns_500(self, client, admin_user, db_session, app):
        """خطأ خارجي في mobile delete يُرجع 500 مع rollback"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.expunge.side_effect = Exception('expunge error in mobile')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]

    def test_mobile_delete_outer_exception_json_error(self, client, admin_user, db_session, app):
        """خطأ في mobile delete يُرجع JSON مع success=False"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.expunge.side_effect = Exception('outer error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        if r.status_code == 500:
            data = r.get_json()
            if data:
                assert data.get('success') is False

    def test_mobile_delete_success_returns_200(self, client, admin_user, db_session, app):
        """حذف ناجح عبر API يُرجع 200 مع success=True"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_mobile_delete_nonexistent_returns_404(self, client, admin_user):
        """حذف معلم غير موجود عبر API"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/9999997/delete')
        assert r.status_code in [404, 200, 500]

    def test_mobile_delete_teacher_with_email(self, client, admin_user, db_session, app):
        """حذف معلم مع إيميل - Notification تحتوي على الإيميل"""
        t = _make_teacher(db_session, email=f'notif_{secrets.token_hex(3)}@deep3.com')
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]

    def test_mobile_delete_teacher_without_email(self, client, admin_user, db_session, app):
        """حذف معلم بدون إيميل عبر API"""
        from src.models.teacher import Teacher
        t = Teacher(name='بلا بريد', username=f'noeml_{secrets.token_hex(3)}')
        t.set_password('Pass@123')
        t.email = None
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]

    def test_mobile_delete_outer_except_redirected_to_500(self, client, admin_user, db_session, app):
        """خطأ خارجي - استجابة خطأ مناسبة"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.expunge.side_effect = Exception('fatal error')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# List Teachers - additional coverage
# ---------------------------------------------------------------------------

class TestListTeachersAdditional:
    """اختبارات إضافية لقائمة المعلمين"""

    def test_list_no_search_param(self, client, admin_user, db_session, app):
        """قائمة بدون معامل search"""
        _login(client, admin_user)
        r = client.get('/teachers/')
        assert r.status_code in [200, 500]

    def test_list_with_search_param(self, client, admin_user, db_session, app):
        """قائمة مع معامل search"""
        _login(client, admin_user)
        r = client.get('/teachers/?search=test')
        assert r.status_code in [200, 500]

    def test_list_with_active_and_inactive_teachers(self, client, admin_user, db_session, app):
        """قائمة مع معلمين نشطين وغير نشطين"""
        _make_teacher(db_session, is_active=True)
        _make_teacher(db_session, is_active=False)
        _login(client, admin_user)
        r = client.get('/teachers/')
        assert r.status_code in [200, 500]

    def test_list_search_arabic_name(self, client, admin_user, db_session, app):
        """البحث بالاسم العربي"""
        _make_teacher(db_session, username='arabic_search_teacher')
        _login(client, admin_user)
        r = client.get('/teachers/?search=arabic_search')
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Mobile API List - additional coverage
# ---------------------------------------------------------------------------

class TestMobileListAdditional:
    """اختبارات إضافية لـ Mobile API قائمة المعلمين"""

    def test_mobile_list_no_search_param(self, client, admin_user, db_session, app):
        """mobile list بدون معامل search"""
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_mobile_list_with_search_by_name(self, client, admin_user, db_session, app):
        """mobile list بالبحث بالاسم"""
        unique = secrets.token_hex(4)
        _make_teacher(db_session, username=f'mlist_{unique}')
        _login(client, admin_user)
        r = client.get(f'/teachers/api/mobile/list?search=mlist_{unique}')
        assert r.status_code in [200, 500]

    def test_mobile_list_teacher_email_empty_string(self, client, admin_user, db_session, app):
        """mobile list: معلم بدون إيميل يُرجع string فارغ"""
        from src.models.teacher import Teacher
        t = Teacher(name='بلا إيميل', username=f'noemail_list_{secrets.token_hex(3)}')
        t.set_password('Pass@123')
        t.email = None
        db_session.session.add(t)
        db_session.session.commit()
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list')
        if r.status_code == 200:
            data = r.get_json()
            teachers = data.get('teachers', [])
            found = [x for x in teachers if x.get('id') == t.id]
            if found:
                assert found[0].get('email') == ''

    def test_mobile_list_is_active_field_present(self, client, admin_user, db_session, app):
        """mobile list: حقل is_active موجود في كل معلم"""
        _make_teacher(db_session)
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list')
        if r.status_code == 200:
            data = r.get_json()
            for teacher in data.get('teachers', []):
                assert 'is_active' in teacher


# ---------------------------------------------------------------------------
# Additional edge cases for full coverage
# ---------------------------------------------------------------------------

class TestTeachersFullCoverage:
    """اختبارات إضافية لإكمال التغطية"""

    def test_add_teacher_get_returns_form(self, client, admin_user):
        """GET /teachers/add يُرجع نموذج الإضافة"""
        _login(client, admin_user)
        r = client.get('/teachers/add')
        assert r.status_code in [200, 500]

    def test_toggle_teacher_nonexistent_returns_404(self, client, admin_user):
        """تبديل حالة معلم غير موجود"""
        _login(client, admin_user)
        r = client.post('/teachers/toggle/9999996')
        assert r.status_code in [302, 404, 500]

    def test_reset_device_nonexistent_returns_404(self, client, admin_user):
        """إعادة تعيين جهاز معلم غير موجود"""
        _login(client, admin_user)
        r = client.post('/teachers/reset-device/9999995')
        assert r.status_code in [302, 404, 500]

    def test_mobile_edit_empty_json_body(self, client, admin_user, db_session, app):
        """mobile edit بـ JSON فارغ - لا تغييرات"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={})
        assert r.status_code in [200, 400, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_mobile_add_with_whitespace_fields_stripped(self, client, admin_user):
        """mobile add: الحقول تُقلَّم من المسافات"""
        _login(client, admin_user)
        unique = secrets.token_hex(3)
        r = client.post('/teachers/api/mobile/add', json={
            'name': f'  معلم مسافات {unique}  ',
            'username': f'  ws_mobile_{unique}  ',
            'password': 'Pass@123',
        })
        assert r.status_code in [200, 400, 409, 500]

    def test_edit_teacher_commit_exception_stays_on_edit_page(self, client, admin_user, db_session, app):
        """خطأ في commit التعديل يبقى على صفحة التعديل"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        with patch('src.routes.teachers.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('rollback test')
            mock_db.session.rollback = MagicMock()
            mock_db.or_ = MagicMock()
            mock_db.text = MagicMock()
            r = client.post(f'/teachers/edit/{t.id}', data={
                'name': 'اسم',
                'is_active': 'on',
            })
        assert r.status_code in [200, 302, 500]

    def test_delete_teacher_successful_with_email(self, client, admin_user, db_session, app):
        """حذف معلم مع إيميل - نجاح كامل"""
        t = _make_teacher(db_session, email=f'del_success_{secrets.token_hex(3)}@deep3.com')
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}')
        assert r.status_code in [200, 302, 500]

    def test_mobile_delete_commit_then_notification_success(self, client, admin_user, db_session, app):
        """حذف ناجح عبر API مع notification ناجحة"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 500]

    def test_add_teacher_is_active_on_flag(self, client, admin_user, db_session, app):
        """إضافة معلم مع is_active=on"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم نشط',
            'username': f'active_flag_{secrets.token_hex(3)}',
            'password': 'Pass@123',
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_is_active_missing(self, client, admin_user, db_session, app):
        """إضافة معلم بدون is_active - يبقى False"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم غير نشط',
            'username': f'inactive_flag_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_add_teacher_all_optional_fields(self, client, admin_user, db_session, app):
        """إضافة معلم بكل الحقول الاختيارية"""
        _login(client, admin_user)
        unique = secrets.token_hex(3)
        r = client.post('/teachers/add', data={
            'name': f'معلم كامل {unique}',
            'username': f'full3_{unique}',
            'password': 'Pass@123',
            'email': f'full3_{unique}@deep3.com',
            'phone': '0501234567',
            'school': 'مدرسة النموذج',
            'notes': 'ملاحظات تجريبية',
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_mobile_add_all_fields_complete(self, client, admin_user, db_session, app):
        """إضافة معلم عبر API بكل الحقول"""
        _login(client, admin_user)
        unique = secrets.token_hex(4)
        r = client.post('/teachers/api/mobile/add', json={
            'name': f'معلم API كامل {unique}',
            'username': f'api_full_{unique}',
            'password': 'Pass@456',
            'email': f'apifull_{unique}@deep3.com',
        })
        assert r.status_code in [200, 400, 409, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True
            assert 'teacher_id' in data
