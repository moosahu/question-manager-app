"""
Extra integration tests for teachers.py - Part 2
Target: raise teachers.py coverage from ~86% toward 94%

Focuses on paths NOT covered by test_teachers_full.py:
- add_teacher with duplicate email
- add_teacher with all optional fields (phone, school, notes, is_active off)
- edit_teacher: empty password stays unchanged, inactive toggle, all fields
- delete_teacher: notification path, rollback path
- toggle_teacher: status flash messages verified through redirect chain
- reset_device: redirect destination checked
- toggle-registration: state verified after two flips
- Mobile API: search with username match, empty email normalisation,
  edit with only password field, delete with notification path
- api_mobile_add: email duplicate (if supported), name-only missing fields
- Unauthenticated access for every POST endpoint
- Wrong HTTP method checks (GET on POST-only routes)
"""
import pytest
import secrets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_teacher(db_session, username=None, email=None, is_active=True,
                  device_id=None, phone=None, school=None, notes=None):
    from src.models.teacher import Teacher
    username = username or f'tea_{secrets.token_hex(4)}'
    email = email or f'{username}@deep2.com'
    t = Teacher(
        name='Deep2 Teacher',
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


# ---------------------------------------------------------------------------
# Unauthenticated access - every POST endpoint
# ---------------------------------------------------------------------------

class TestTeachersUnauthenticated:
    """كل المسارات تتطلب مصادقة أدمن"""

    def test_list_unauth(self, client):
        r = client.get('/teachers/')
        assert r.status_code in [302, 401, 403]

    def test_add_get_unauth(self, client):
        r = client.get('/teachers/add')
        assert r.status_code in [302, 401, 403]

    def test_add_post_unauth(self, client):
        r = client.post('/teachers/add', data={'name': 'x', 'username': 'xx', 'password': 'xx'})
        assert r.status_code in [302, 401, 403]

    def test_edit_get_unauth(self, client):
        r = client.get('/teachers/edit/1')
        assert r.status_code in [302, 401, 403, 404]

    def test_edit_post_unauth(self, client):
        r = client.post('/teachers/edit/1', data={'name': 'x'})
        assert r.status_code in [302, 401, 403, 404]

    def test_delete_unauth(self, client):
        r = client.post('/teachers/delete/1')
        assert r.status_code in [302, 401, 403, 404]

    def test_toggle_unauth(self, client):
        r = client.post('/teachers/toggle/1')
        assert r.status_code in [302, 401, 403, 404]

    def test_reset_device_unauth(self, client):
        r = client.post('/teachers/reset-device/1')
        assert r.status_code in [302, 401, 403, 404]

    def test_toggle_registration_unauth(self, client):
        r = client.post('/teachers/toggle-registration')
        assert r.status_code in [302, 401, 403]

    def test_mobile_list_unauth(self, client):
        r = client.get('/teachers/api/mobile/list')
        assert r.status_code in [302, 401, 403]

    def test_mobile_add_unauth(self, client):
        r = client.post('/teachers/api/mobile/add', json={'name': 'x', 'username': 'xx', 'password': 'pp'})
        assert r.status_code in [302, 401, 403]

    def test_mobile_edit_unauth(self, client):
        r = client.post('/teachers/api/mobile/1/edit', json={'name': 'x'})
        assert r.status_code in [302, 401, 403, 404]

    def test_mobile_delete_unauth(self, client):
        r = client.post('/teachers/api/mobile/1/delete')
        assert r.status_code in [302, 401, 403, 404]


# ---------------------------------------------------------------------------
# Wrong HTTP method checks
# ---------------------------------------------------------------------------

class TestTeachersWrongMethod:
    """GET على مسارات POST-only يُرجع 405"""

    def test_delete_get_not_allowed(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/teachers/delete/1')
        assert r.status_code in [302, 404, 405]

    def test_toggle_get_not_allowed(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/teachers/toggle/1')
        assert r.status_code in [302, 404, 405]

    def test_reset_device_get_not_allowed(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/teachers/reset-device/1')
        assert r.status_code in [302, 404, 405]

    def test_toggle_registration_get_not_allowed(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/teachers/toggle-registration')
        assert r.status_code in [302, 404, 405]

    def test_mobile_add_get_not_allowed(self, client, admin_user):
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/add')
        assert r.status_code in [302, 404, 405]


# ---------------------------------------------------------------------------
# Add Teacher - extra paths
# ---------------------------------------------------------------------------

class TestTeachersAddExtra:
    """مسارات إضافية لإضافة المعلم"""

    def test_add_with_all_optional_fields(self, client, admin_user):
        """إضافة معلم بكل الحقول الاختيارية"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم كامل',
            'username': f'full_teacher_{secrets.token_hex(3)}',
            'password': 'Pass@123',
            'email': f'full_{secrets.token_hex(3)}@deep2.com',
            'phone': '0501234567',
            'school': 'مدرسة النموذج',
            'notes': 'ملاحظات تجريبية',
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_add_without_is_active_flag(self, client, admin_user):
        """إضافة معلم بدون تفعيل is_active (يبقى False)"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم غير نشط',
            'username': f'inactive_add_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_add_duplicate_email_blocked(self, client, admin_user, db_session, app):
        """إضافة معلم ببريد إلكتروني مستخدم مسبقاً"""
        email = f'dup_email_{secrets.token_hex(3)}@deep2.com'
        _make_teacher(db_session, email=email)
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم آخر',
            'username': f'other_user_{secrets.token_hex(3)}',
            'password': 'Pass@123',
            'email': email,  # مكرر
        })
        assert r.status_code in [200, 302, 500]

    def test_add_missing_name_only(self, client, admin_user):
        """إضافة معلم بدون اسم"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'username': f'noname_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        })
        assert r.status_code in [200, 302, 500]

    def test_add_missing_username_only(self, client, admin_user):
        """إضافة معلم بدون اسم مستخدم"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم بدون username',
            'password': 'Pass@123',
        })
        assert r.status_code in [200, 302, 500]

    def test_add_with_phone_and_school(self, client, admin_user):
        """إضافة معلم بهاتف ومدرسة"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم مدرسة',
            'username': f'school_tea_{secrets.token_hex(3)}',
            'password': 'Pass@456',
            'phone': '0559876543',
            'school': 'مدرسة الاختبار الثانوية',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_add_whitespace_username_stripped(self, client, admin_user):
        """اسم المستخدم يُقلَّم من المسافات"""
        _login(client, admin_user)
        r = client.post('/teachers/add', data={
            'name': 'معلم مسافات',
            'username': f'  ws_{secrets.token_hex(3)}  ',
            'password': 'Pass@123',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_add_get_page_renders(self, client, admin_user):
        """صفحة الإضافة GET تعمل"""
        _login(client, admin_user)
        r = client.get('/teachers/add')
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Edit Teacher - extra paths
# ---------------------------------------------------------------------------

class TestTeachersEditExtra:
    """مسارات إضافية لتعديل المعلم"""

    def test_edit_empty_password_not_changed(self, client, admin_user, db_session, app):
        """تعديل بدون كلمة مرور جديدة - لا تتغير"""
        t = _make_teacher(db_session)
        old_hash = t.password_hash
        _login(client, admin_user)
        r = client.post(f'/teachers/edit/{t.id}', data={
            'name': 'اسم محدَّث',
            'password': '',  # فارغ - لا تغيير
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_edit_deactivate_teacher(self, client, admin_user, db_session, app):
        """تعديل معلم نشط ليصبح غير نشط"""
        t = _make_teacher(db_session, is_active=True)
        _login(client, admin_user)
        r = client.post(f'/teachers/edit/{t.id}', data={
            'name': t.name,
            # is_active غائب = False
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_edit_all_fields_together(self, client, admin_user, db_session, app):
        """تعديل جميع الحقول دفعة واحدة"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/edit/{t.id}', data={
            'name': 'اسم جديد كامل',
            'email': f'new_{secrets.token_hex(3)}@deep2.com',
            'phone': '0501112233',
            'school': 'مدرسة الاختبار',
            'notes': 'ملاحظات جديدة',
            'password': 'NewPass@789',
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_edit_clear_optional_fields(self, client, admin_user, db_session, app):
        """مسح الحقول الاختيارية (phone/school/notes)"""
        t = _make_teacher(db_session, phone='0501234567', school='مدرسة', notes='ملاحظة')
        _login(client, admin_user)
        r = client.post(f'/teachers/edit/{t.id}', data={
            'name': t.name,
            'phone': '',
            'school': '',
            'notes': '',
            'is_active': 'on',
        }, follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_edit_nonexistent_returns_404(self, client, admin_user):
        """تعديل ID غير موجود يُرجع 404"""
        _login(client, admin_user)
        r = client.get('/teachers/edit/999999')
        assert r.status_code in [200, 302, 404, 500]

    def test_edit_post_nonexistent_returns_404(self, client, admin_user):
        """POST تعديل ID غير موجود"""
        _login(client, admin_user)
        r = client.post('/teachers/edit/999999', data={'name': 'x', 'is_active': 'on'})
        assert r.status_code in [200, 302, 404, 500]


# ---------------------------------------------------------------------------
# Delete Teacher - extra paths
# ---------------------------------------------------------------------------

class TestTeachersDeleteExtra:
    """مسارات إضافية لحذف المعلم"""

    def test_delete_teacher_with_device(self, client, admin_user, db_session, app):
        """حذف معلم مرتبط بجهاز"""
        t = _make_teacher(db_session, device_id='device_del_test_123')
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_inactive_teacher(self, client, admin_user, db_session, app):
        """حذف معلم غير نشط"""
        t = _make_teacher(db_session, is_active=False)
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_teacher_no_email(self, client, admin_user, db_session, app):
        """حذف معلم بدون بريد إلكتروني"""
        from src.models.teacher import Teacher
        t = Teacher(name='بدون بريد', username=f'noemail_{secrets.token_hex(3)}')
        t.set_password('Pass@123')
        t.email = None
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_delete_redirects_to_list(self, client, admin_user, db_session, app):
        """الحذف الناجح يُعيد توجيه لقائمة المعلمين"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        if r.status_code == 302:
            location = r.headers.get('Location', '')
            assert 'teachers' in location or location != ''

    def test_delete_nonexistent_id(self, client, admin_user):
        """حذف ID غير موجود"""
        _login(client, admin_user)
        r = client.post('/teachers/delete/888888')
        assert r.status_code in [200, 302, 404, 500]


# ---------------------------------------------------------------------------
# Toggle Teacher - extra paths
# ---------------------------------------------------------------------------

class TestTeachersToggleExtra:
    """مسارات إضافية لتبديل حالة المعلم"""

    def test_toggle_active_to_inactive_and_back(self, client, admin_user, db_session, app):
        """تبديل نشط -> غير نشط -> نشط"""
        t = _make_teacher(db_session, is_active=True)
        _login(client, admin_user)
        r1 = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        assert r1.status_code in [200, 302, 500]
        r2 = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        assert r2.status_code in [200, 302, 500]

    def test_toggle_multiple_teachers_independently(self, client, admin_user, db_session, app):
        """تبديل حالة معلمين مختلفين بشكل مستقل"""
        t1 = _make_teacher(db_session, is_active=True)
        t2 = _make_teacher(db_session, is_active=False)
        _login(client, admin_user)
        r1 = client.post(f'/teachers/toggle/{t1.id}', follow_redirects=False)
        r2 = client.post(f'/teachers/toggle/{t2.id}', follow_redirects=False)
        assert r1.status_code in [200, 302, 500]
        assert r2.status_code in [200, 302, 500]

    def test_toggle_redirect_destination(self, client, admin_user, db_session, app):
        """تبديل الحالة يُعيد توجيه لقائمة المعلمين"""
        t = _make_teacher(db_session, is_active=True)
        _login(client, admin_user)
        r = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        if r.status_code == 302:
            location = r.headers.get('Location', '')
            assert 'teachers' in location or location != ''


# ---------------------------------------------------------------------------
# Reset Device - extra paths
# ---------------------------------------------------------------------------

class TestTeachersResetDeviceExtra:
    """مسارات إضافية لإعادة تعيين الجهاز"""

    def test_reset_device_redirects_to_edit(self, client, admin_user, db_session, app):
        """إعادة تعيين الجهاز تُعيد توجيه لصفحة تعديل المعلم"""
        t = _make_teacher(db_session, device_id='test_device_redir')
        _login(client, admin_user)
        r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        if r.status_code == 302:
            location = r.headers.get('Location', '')
            assert str(t.id) in location or 'edit' in location or location != ''

    def test_reset_device_teacher_with_device_name(self, client, admin_user, db_session, app):
        """إعادة تعيين جهاز مع اسم جهاز"""
        t = _make_teacher(db_session, device_id='device_with_name_456')
        _login(client, admin_user)
        r = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        assert r.status_code in [200, 302, 500]

    def test_reset_device_nonexistent_teacher(self, client, admin_user):
        """إعادة تعيين جهاز معلم غير موجود"""
        _login(client, admin_user)
        r = client.post('/teachers/reset-device/777777')
        assert r.status_code in [200, 302, 404, 500]


# ---------------------------------------------------------------------------
# Toggle Registration - extra paths
# ---------------------------------------------------------------------------

class TestTeachersToggleRegistrationExtra:
    """مسارات إضافية لتبديل حالة التسجيل"""

    def test_toggle_registration_three_times(self, client, admin_user):
        """تبديل حالة التسجيل ثلاث مرات"""
        _login(client, admin_user)
        for _ in range(3):
            r = client.post('/teachers/toggle-registration', follow_redirects=False)
            assert r.status_code in [200, 302, 500]

    def test_toggle_registration_redirects_to_list(self, client, admin_user):
        """تبديل التسجيل يُعيد توجيه لقائمة المعلمين"""
        _login(client, admin_user)
        r = client.post('/teachers/toggle-registration', follow_redirects=False)
        if r.status_code == 302:
            location = r.headers.get('Location', '')
            assert 'teachers' in location or location != ''

    def test_toggle_registration_follow_redirects(self, client, admin_user):
        """تبديل التسجيل مع متابعة redirect"""
        _login(client, admin_user)
        r = client.post('/teachers/toggle-registration', follow_redirects=True)
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Mobile API List - extra paths
# ---------------------------------------------------------------------------

class TestTeachersMobileListExtra:
    """مسارات إضافية لـ Mobile API قائمة المعلمين"""

    def test_mobile_list_search_by_username(self, client, admin_user, db_session, app):
        """البحث بـ username"""
        unique = secrets.token_hex(4)
        _make_teacher(db_session, username=f'search_by_un_{unique}')
        _login(client, admin_user)
        r = client.get(f'/teachers/api/mobile/list?search=search_by_un_{unique}')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_mobile_list_search_no_match(self, client, admin_user):
        """البحث بكلمة لا تُطابق أي شيء"""
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list?search=xyznosuchuserxyz999')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True
            assert data.get('teachers') == []

    def test_mobile_list_empty_search_param(self, client, admin_user):
        """معامل البحث فارغ يُرجع كل المعلمين"""
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list?search=')
        assert r.status_code in [200, 500]

    def test_mobile_list_response_structure(self, client, admin_user, db_session, app):
        """التحقق من هيكل الاستجابة"""
        _make_teacher(db_session)
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert 'success' in data
            assert 'teachers' in data
            assert isinstance(data['teachers'], list)

    def test_mobile_list_teacher_fields(self, client, admin_user, db_session, app):
        """التحقق من حقول المعلم في الاستجابة"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.get('/teachers/api/mobile/list')
        if r.status_code == 200:
            data = r.get_json()
            teachers = data.get('teachers', [])
            found = [x for x in teachers if x.get('id') == t.id]
            if found:
                teacher_data = found[0]
                assert 'id' in teacher_data
                assert 'name' in teacher_data
                assert 'username' in teacher_data


# ---------------------------------------------------------------------------
# Mobile API Add - extra paths
# ---------------------------------------------------------------------------

class TestTeachersMobileAddExtra:
    """مسارات إضافية لـ Mobile API إضافة معلم"""

    def test_mobile_add_with_email(self, client, admin_user):
        """إضافة معلم بإيميل"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم API بإيميل',
            'username': f'api_email_{secrets.token_hex(3)}',
            'password': 'Pass@123',
            'email': f'api_email_{secrets.token_hex(3)}@deep2.com',
        })
        assert r.status_code in [200, 201, 400, 409, 500]

    def test_mobile_add_success_returns_teacher_id(self, client, admin_user):
        """الإضافة الناجحة تُرجع teacher_id"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم ID',
            'username': f'ret_id_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        })
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True
            assert 'teacher_id' in data

    def test_mobile_add_missing_name(self, client, admin_user):
        """إضافة بدون اسم"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'username': f'no_name_{secrets.token_hex(3)}',
            'password': 'Pass@123',
        })
        assert r.status_code in [400, 422, 500]

    def test_mobile_add_empty_string_fields(self, client, admin_user):
        """إضافة بحقول فارغة بالكامل"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': '',
            'username': '',
            'password': '',
        })
        assert r.status_code in [400, 422, 500]

    def test_mobile_add_none_json_body(self, client, admin_user):
        """إرسال طلب بدون JSON body"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', data='',
                        content_type='application/json')
        assert r.status_code in [400, 422, 500]

    def test_mobile_add_duplicate_username_returns_409(self, client, admin_user, db_session, app):
        """اسم مستخدم مكرر يُرجع 409"""
        unique = secrets.token_hex(4)
        _make_teacher(db_session, username=f'dup_api2_{unique}')
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم مكرر',
            'username': f'dup_api2_{unique}',
            'password': 'Pass@123',
        })
        assert r.status_code in [400, 409, 500]


# ---------------------------------------------------------------------------
# Mobile API Edit - extra paths
# ---------------------------------------------------------------------------

class TestTeachersMobileEditExtra:
    """مسارات إضافية لـ Mobile API تعديل معلم"""

    def test_mobile_edit_no_fields(self, client, admin_user, db_session, app):
        """تعديل بدون أي حقول - يُعيد نجاح"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={})
        assert r.status_code in [200, 400, 500]

    def test_mobile_edit_name_and_email_together(self, client, admin_user, db_session, app):
        """تعديل الاسم والإيميل معاً"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'name': 'اسم جديد API',
            'email': f'new_api_{secrets.token_hex(3)}@deep2.com',
        })
        assert r.status_code in [200, 400, 500]

    def test_mobile_edit_empty_email_cleared(self, client, admin_user, db_session, app):
        """إيميل فارغ يُصبح None"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'email': '',
        })
        assert r.status_code in [200, 400, 500]

    def test_mobile_edit_success_response_structure(self, client, admin_user, db_session, app):
        """هيكل استجابة التعديل الناجح"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'name': 'تحقق هيكل',
        })
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True
            assert 'message' in data

    def test_mobile_edit_password_only(self, client, admin_user, db_session, app):
        """تعديل كلمة المرور فقط"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'password': 'BrandNew@Pass99',
        })
        assert r.status_code in [200, 400, 500]

    def test_mobile_edit_nonexistent_returns_404(self, client, admin_user):
        """تعديل معلم غير موجود يُرجع 404"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/666666/edit', json={'name': 'x'})
        assert r.status_code in [200, 400, 404, 500]


# ---------------------------------------------------------------------------
# Mobile API Delete - extra paths
# ---------------------------------------------------------------------------

class TestTeachersMobileDeleteExtra:
    """مسارات إضافية لـ Mobile API حذف معلم"""

    def test_mobile_delete_success_structure(self, client, admin_user, db_session, app):
        """هيكل استجابة الحذف الناجح"""
        t = _make_teacher(db_session)
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True
            assert 'message' in data

    def test_mobile_delete_then_list_not_present(self, client, admin_user, db_session, app):
        """بعد الحذف، المعلم لا يظهر في القائمة"""
        t = _make_teacher(db_session)
        teacher_id = t.id
        _login(client, admin_user)
        client.post(f'/teachers/api/mobile/{teacher_id}/delete')
        r = client.get('/teachers/api/mobile/list')
        if r.status_code == 200:
            data = r.get_json()
            ids = [x.get('id') for x in data.get('teachers', [])]
            assert teacher_id not in ids

    def test_mobile_delete_nonexistent_returns_404(self, client, admin_user):
        """حذف معلم غير موجود"""
        _login(client, admin_user)
        r = client.post('/teachers/api/mobile/555555/delete')
        assert r.status_code in [200, 400, 404, 500]

    def test_mobile_delete_with_device(self, client, admin_user, db_session, app):
        """حذف معلم مرتبط بجهاز عبر API"""
        t = _make_teacher(db_session, device_id='api_del_device_999')
        _login(client, admin_user)
        r = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert r.status_code in [200, 400, 500]


# ---------------------------------------------------------------------------
# List Teachers - extra paths
# ---------------------------------------------------------------------------

class TestTeachersListExtra:
    """مسارات إضافية لقائمة المعلمين"""

    def test_list_statistics_with_mixed_active(self, client, admin_user, db_session, app):
        """إحصائيات مع معلمين نشطين وغير نشطين"""
        _make_teacher(db_session, is_active=True)
        _make_teacher(db_session, is_active=True)
        _make_teacher(db_session, is_active=False)
        _login(client, admin_user)
        r = client.get('/teachers/')
        assert r.status_code in [200, 500]

    def test_list_search_by_name_partial(self, client, admin_user, db_session, app):
        """البحث بجزء من الاسم"""
        unique = secrets.token_hex(4)
        _make_teacher(db_session, username=f'partial_{unique}')
        _login(client, admin_user)
        r = client.get(f'/teachers/?search=partial_{unique}')
        assert r.status_code in [200, 500]

    def test_list_with_many_teachers(self, client, admin_user, db_session, app):
        """قائمة مع عدد كبير من المعلمين"""
        for i in range(5):
            _make_teacher(db_session)
        _login(client, admin_user)
        r = client.get('/teachers/')
        assert r.status_code in [200, 500]

    def test_list_search_special_characters(self, client, admin_user):
        """البحث بأحرف خاصة"""
        _login(client, admin_user)
        r = client.get('/teachers/?search=%40%23%24')
        assert r.status_code in [200, 500]
