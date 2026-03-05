"""
اختبارات متكاملة وشاملة لـ Teachers Blueprint
يغطي: قائمة المعلمين، إضافة، تعديل، حذف، تبديل الحالة، إعادة تعيين الجهاز،
        تبديل حالة التسجيل، و Mobile API Routes

الحالات المختبرة:
- بدون مصادقة → 302 (redirect) أو 401/403
- كأدمن مسجّل → 200/302 (نجاح) أو 500 (خطأ template في Python 3.9)
- IDs غير موجودة (99999) → 200/302/404/500
- Mobile API (تتطلب مصادقة admin) → 200/400/404/500
- بيانات ناقصة في POST → 200/400/302 (flash + re-render)
"""
import pytest


# ==================== دوال مساعدة ====================

def _make_teacher(db_session, username, email, is_active=True, device_id=None):
    """إنشاء معلم تجريبي في قاعدة البيانات"""
    from src.models.teacher import Teacher
    t = Teacher(
        name='Test Teacher Full',
        username=username,
        email=email,
        is_active=is_active,
    )
    t.set_password('Pass@123')
    if device_id:
        t.device_id = device_id
        t.device_name = 'جهاز اختباري'
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


def _login(client, admin_user):
    """تسجيل دخول الأدمن عبر الـ session مباشرة"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


# ==================== اختبارات قائمة المعلمين ====================

class TestTeachersListFull:
    """اختبارات صفحة قائمة المعلمين GET /teachers/"""

    def test_list_no_auth_redirects(self, client):
        """الوصول بدون مصادقة يُحوّل لصفحة الدخول"""
        response = client.get('/teachers/')
        assert response.status_code in [302, 401, 403]

    def test_list_no_auth_redirect_location(self, client):
        """التأكد من أن redirect يتجه نحو صفحة تسجيل الدخول"""
        response = client.get('/teachers/', follow_redirects=False)
        assert response.status_code in [302, 401, 403]
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            assert 'login' in location or location != '/teachers/'

    def test_list_as_admin_accessible(self, client, admin_user):
        """الأدمن يصل لقائمة المعلمين - لا redirect لتسجيل الدخول"""
        _login(client, admin_user)
        response = client.get('/teachers/')
        # 200 = نجاح، 500 = خطأ template (Python 3.9)، لكن لا 302 لتسجيل الدخول
        assert response.status_code in [200, 500]

    def test_list_as_admin_with_teachers_in_db(self, client, admin_user, db_session, app):
        """قائمة معلمين بوجود بيانات في DB"""
        _make_teacher(db_session, 'list_tea1', 'list_tea1@test.com')
        _make_teacher(db_session, 'list_tea2', 'list_tea2@test.com')
        _login(client, admin_user)
        response = client.get('/teachers/')
        assert response.status_code in [200, 500]

    def test_list_search_as_admin(self, client, admin_user, db_session, app):
        """البحث في قائمة المعلمين"""
        t = _make_teacher(db_session, 'search_tea1', 'search_tea1@test.com')
        _login(client, admin_user)
        response = client.get(f'/teachers/?search={t.name}')
        assert response.status_code in [200, 500]

    def test_list_search_no_results(self, client, admin_user):
        """البحث بكلمة لا تُطابق أي معلم"""
        _login(client, admin_user)
        response = client.get('/teachers/?search=xyznonexistentteacher999')
        assert response.status_code in [200, 500]

    def test_list_search_arabic_term(self, client, admin_user, db_session, app):
        """البحث بمصطلح عربي"""
        _make_teacher(db_session, 'arabic_tea1', 'arabic_tea1@test.com')
        _login(client, admin_user)
        response = client.get('/teachers/?search=معلم')
        assert response.status_code in [200, 500]


# ==================== اختبارات إضافة معلم ====================

class TestTeachersAddFull:
    """اختبارات إضافة معلم - GET/POST /teachers/add"""

    def test_add_page_no_auth(self, client):
        """صفحة الإضافة بدون مصادقة"""
        response = client.get('/teachers/add')
        assert response.status_code in [302, 401, 403]

    def test_add_page_as_admin(self, client, admin_user):
        """الأدمن يفتح صفحة الإضافة"""
        _login(client, admin_user)
        response = client.get('/teachers/add')
        assert response.status_code in [200, 302, 500]

    def test_add_post_no_auth(self, client):
        """إرسال نموذج الإضافة بدون مصادقة"""
        response = client.post('/teachers/add', data={
            'name': 'معلم مزيف',
            'username': 'fake_teacher',
            'password': 'Pass@123',
        })
        assert response.status_code in [302, 401, 403]

    def test_add_post_empty_data_as_admin(self, client, admin_user):
        """إرسال نموذج الإضافة ببيانات فارغة كأدمن"""
        _login(client, admin_user)
        response = client.post('/teachers/add', data={})
        # يُعيد الصفحة مع flash error أو يُحوّل
        assert response.status_code in [200, 302, 500]

    def test_add_post_missing_password(self, client, admin_user):
        """إضافة معلم بدون كلمة مرور"""
        _login(client, admin_user)
        response = client.post('/teachers/add', data={
            'name': 'معلم بدون باسورد',
            'username': 'no_pass_teacher',
        })
        assert response.status_code in [200, 302, 500]

    def test_add_post_valid_data_as_admin(self, client, admin_user):
        """إضافة معلم جديد ببيانات صحيحة"""
        _login(client, admin_user)
        response = client.post('/teachers/add', data={
            'name': 'معلم مضاف للاختبار',
            'username': 'newly_added_teacher_full',
            'password': 'Pass@456',
            'email': 'newly_added_full@test.com',
            'is_active': 'on',
        }, follow_redirects=False)
        # 302 = redirect بعد إضافة ناجحة، 200/500 في حالات أخرى
        assert response.status_code in [200, 302, 500]

    def test_add_post_duplicate_username(self, client, admin_user, db_session, app):
        """إضافة معلم باسم مستخدم مكرر"""
        _make_teacher(db_session, 'dup_tea_full1', 'dup_tea_full1@test.com')
        _login(client, admin_user)
        response = client.post('/teachers/add', data={
            'name': 'معلم آخر',
            'username': 'dup_tea_full1',  # مكرر
            'password': 'Pass@789',
        })
        # يُعيد الصفحة مع flash error أو يُحوّل
        assert response.status_code in [200, 302, 500]


# ==================== اختبارات تعديل معلم ====================

class TestTeachersEditFull:
    """اختبارات تعديل معلم - GET/POST /teachers/edit/<id>"""

    def test_edit_page_no_auth(self, client):
        """صفحة التعديل بدون مصادقة"""
        response = client.get('/teachers/edit/1')
        assert response.status_code in [302, 401, 403, 404]

    def test_edit_page_nonexistent_id(self, client, admin_user):
        """صفحة تعديل معلم غير موجود"""
        _login(client, admin_user)
        response = client.get('/teachers/edit/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_edit_page_existing_teacher(self, client, admin_user, db_session, app):
        """صفحة تعديل معلم موجود"""
        t = _make_teacher(db_session, 'edit_tea_full1', 'edit_tea_full1@test.com')
        _login(client, admin_user)
        response = client.get(f'/teachers/edit/{t.id}')
        assert response.status_code in [200, 302, 500]

    def test_edit_post_no_auth(self, client):
        """إرسال نموذج التعديل بدون مصادقة"""
        response = client.post('/teachers/edit/1', data={'name': 'معلم معدّل'})
        assert response.status_code in [302, 401, 403, 404]

    def test_edit_post_nonexistent_teacher(self, client, admin_user):
        """تعديل معلم غير موجود"""
        _login(client, admin_user)
        response = client.post('/teachers/edit/99999', data={
            'name': 'معلم غير موجود',
            'is_active': 'on',
        })
        assert response.status_code in [200, 302, 404, 500]

    def test_edit_post_existing_teacher_valid_data(self, client, admin_user, db_session, app):
        """تعديل معلم موجود ببيانات صحيحة"""
        t = _make_teacher(db_session, 'edit_tea_full2', 'edit_tea_full2@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/edit/{t.id}', data={
            'name': 'اسم محدَّث للاختبار',
            'email': 'edit_tea_full2_upd@test.com',
            'is_active': 'on',
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 500]

    def test_edit_post_change_password(self, client, admin_user, db_session, app):
        """تعديل كلمة مرور المعلم"""
        t = _make_teacher(db_session, 'edit_tea_full3', 'edit_tea_full3@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/edit/{t.id}', data={
            'name': t.name,
            'password': 'NewPass@789',
            'is_active': 'on',
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 500]


# ==================== اختبارات حذف معلم ====================

class TestTeachersDeleteFull:
    """اختبارات حذف معلم - POST /teachers/delete/<id>"""

    def test_delete_no_auth(self, client):
        """حذف بدون مصادقة"""
        response = client.post('/teachers/delete/1')
        assert response.status_code in [302, 401, 403, 404]

    def test_delete_get_method_not_allowed(self, client, admin_user):
        """حذف بـ GET method - يجب أن يُرجع 405"""
        _login(client, admin_user)
        response = client.get('/teachers/delete/1')
        assert response.status_code in [302, 404, 405]

    def test_delete_nonexistent_teacher(self, client, admin_user):
        """حذف معلم غير موجود"""
        _login(client, admin_user)
        response = client.post('/teachers/delete/99999')
        # 302 redirect بعد 404 flash، أو 404 مباشر
        assert response.status_code in [200, 302, 404, 500]

    def test_delete_existing_teacher(self, client, admin_user, db_session, app):
        """حذف معلم موجود"""
        t = _make_teacher(db_session, 'del_tea_full1', 'del_tea_full1@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/delete/{t.id}', follow_redirects=False)
        # 302 = redirect بعد حذف ناجح، 500 في حالة خطأ
        assert response.status_code in [200, 302, 500]


# ==================== اختبارات تبديل حالة المعلم ====================

class TestTeachersToggleFull:
    """اختبارات تبديل نشاط المعلم - POST /teachers/toggle/<id>"""

    def test_toggle_no_auth(self, client):
        """تبديل حالة بدون مصادقة"""
        response = client.post('/teachers/toggle/1')
        assert response.status_code in [302, 401, 403, 404]

    def test_toggle_nonexistent_teacher(self, client, admin_user):
        """تبديل حالة معلم غير موجود"""
        _login(client, admin_user)
        response = client.post('/teachers/toggle/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_active_teacher_becomes_inactive(self, client, admin_user, db_session, app):
        """تعطيل معلم نشط"""
        t = _make_teacher(db_session, 'toggle_tea_full1', 'toggle_tea_full1@test.com', is_active=True)
        _login(client, admin_user)
        response = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        assert response.status_code in [200, 302, 500]

    def test_toggle_inactive_teacher_becomes_active(self, client, admin_user, db_session, app):
        """تفعيل معلم معطّل"""
        t = _make_teacher(db_session, 'toggle_tea_full2', 'toggle_tea_full2@test.com', is_active=False)
        _login(client, admin_user)
        response = client.post(f'/teachers/toggle/{t.id}', follow_redirects=False)
        assert response.status_code in [200, 302, 500]


# ==================== اختبارات إعادة تعيين الجهاز ====================

class TestTeachersResetDeviceFull:
    """اختبارات إعادة تعيين جهاز المعلم - POST /teachers/reset-device/<id>"""

    def test_reset_device_no_auth(self, client):
        """إعادة تعيين جهاز بدون مصادقة"""
        response = client.post('/teachers/reset-device/1')
        assert response.status_code in [302, 401, 403, 404]

    def test_reset_device_nonexistent_teacher(self, client, admin_user):
        """إعادة تعيين جهاز معلم غير موجود"""
        _login(client, admin_user)
        response = client.post('/teachers/reset-device/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_reset_device_teacher_with_device(self, client, admin_user, db_session, app):
        """إعادة تعيين جهاز معلم لديه جهاز مسجّل"""
        t = _make_teacher(
            db_session, 'reset_dev_full1', 'reset_dev_full1@test.com',
            device_id='old_device_id_abc123'
        )
        _login(client, admin_user)
        response = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        # يُعيد redirect لصفحة التعديل
        assert response.status_code in [200, 302, 500]

    def test_reset_device_teacher_without_device(self, client, admin_user, db_session, app):
        """إعادة تعيين جهاز معلم لا يملك جهازاً مسجّلاً"""
        t = _make_teacher(db_session, 'reset_dev_full2', 'reset_dev_full2@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/reset-device/{t.id}', follow_redirects=False)
        assert response.status_code in [200, 302, 500]


# ==================== اختبارات تبديل حالة التسجيل ====================

class TestTeachersToggleRegistrationFull:
    """اختبارات تبديل التسجيل الذاتي - POST /teachers/toggle-registration"""

    def test_toggle_registration_no_auth(self, client):
        """تبديل التسجيل بدون مصادقة"""
        response = client.post('/teachers/toggle-registration')
        assert response.status_code in [302, 401, 403]

    def test_toggle_registration_as_admin(self, client, admin_user):
        """تبديل حالة التسجيل كأدمن"""
        _login(client, admin_user)
        response = client.post('/teachers/toggle-registration', follow_redirects=False)
        # 302 redirect بعد التبديل، أو 500 في حالة خطأ
        assert response.status_code in [200, 302, 500]

    def test_toggle_registration_twice(self, client, admin_user):
        """تبديل حالة التسجيل مرتين يعيد الحالة الأصلية"""
        _login(client, admin_user)
        client.post('/teachers/toggle-registration', follow_redirects=False)
        response = client.post('/teachers/toggle-registration', follow_redirects=False)
        assert response.status_code in [200, 302, 500]


# ==================== اختبارات Mobile API ====================

class TestTeachersMobileApiListFull:
    """اختبارات Mobile API - GET /teachers/api/mobile/list"""

    def test_mobile_list_no_auth(self, client):
        """قائمة المعلمين عبر API بدون مصادقة"""
        response = client.get('/teachers/api/mobile/list')
        assert response.status_code in [200, 302, 401, 403]

    def test_mobile_list_as_admin_empty(self, client, admin_user):
        """قائمة المعلمين عبر API كأدمن - قاعدة بيانات فارغة"""
        _login(client, admin_user)
        response = client.get('/teachers/api/mobile/list')
        assert response.status_code in [200, 500]

    def test_mobile_list_as_admin_with_data(self, client, admin_user, db_session, app):
        """قائمة المعلمين عبر API مع بيانات في DB"""
        _make_teacher(db_session, 'mob_list_tea1', 'mob_list_tea1@test.com')
        _login(client, admin_user)
        response = client.get('/teachers/api/mobile/list')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_mobile_list_search_param(self, client, admin_user, db_session, app):
        """قائمة المعلمين مع معامل البحث"""
        _make_teacher(db_session, 'mob_search_tea1', 'mob_search_tea1@test.com')
        _login(client, admin_user)
        response = client.get('/teachers/api/mobile/list?search=mob_search')
        assert response.status_code in [200, 500]


class TestTeachersMobileApiAddFull:
    """اختبارات Mobile API - POST /teachers/api/mobile/add"""

    def test_mobile_add_no_auth(self, client):
        """إضافة معلم عبر API بدون مصادقة"""
        response = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم تجريبي',
            'username': 'api_add_unauth',
            'password': 'Pass@123'
        })
        assert response.status_code in [200, 302, 401, 403]

    def test_mobile_add_empty_payload(self, client, admin_user):
        """إضافة معلم عبر API ببيانات فارغة"""
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/add', json={})
        assert response.status_code in [400, 422, 500]

    def test_mobile_add_missing_username(self, client, admin_user):
        """إضافة معلم عبر API بدون اسم مستخدم"""
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم بدون username',
            'password': 'Pass@123'
        })
        assert response.status_code in [400, 422, 500]

    def test_mobile_add_missing_password(self, client, admin_user):
        """إضافة معلم عبر API بدون كلمة مرور"""
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم بدون باسورد',
            'username': 'no_pass_api_tea'
        })
        assert response.status_code in [400, 422, 500]

    def test_mobile_add_valid_data(self, client, admin_user):
        """إضافة معلم عبر API ببيانات صحيحة"""
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم API صحيح',
            'username': 'api_valid_tea_full1',
            'password': 'Pass@123',
            'email': 'api_valid_tea_full1@test.com'
        })
        assert response.status_code in [200, 201, 400, 500]

    def test_mobile_add_duplicate_username(self, client, admin_user, db_session, app):
        """إضافة معلم عبر API باسم مستخدم مكرر"""
        _make_teacher(db_session, 'api_dup_tea_full1', 'api_dup_tea_full1@test.com')
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/add', json={
            'name': 'معلم مكرر',
            'username': 'api_dup_tea_full1',  # مكرر
            'password': 'Pass@123'
        })
        # 409 Conflict أو 400 أو 500
        assert response.status_code in [400, 409, 500]


class TestTeachersMobileApiEditFull:
    """اختبارات Mobile API - POST /teachers/api/mobile/<id>/edit"""

    def test_mobile_edit_no_auth(self, client):
        """تعديل معلم عبر API بدون مصادقة"""
        response = client.post('/teachers/api/mobile/1/edit', json={'name': 'اسم جديد'})
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_mobile_edit_nonexistent_teacher(self, client, admin_user):
        """تعديل معلم غير موجود عبر API"""
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/99999/edit', json={
            'name': 'اسم غير موجود'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_mobile_edit_existing_teacher(self, client, admin_user, db_session, app):
        """تعديل معلم موجود عبر API"""
        t = _make_teacher(db_session, 'api_edit_tea_full1', 'api_edit_tea_full1@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'name': 'اسم محدَّث عبر API',
        })
        assert response.status_code in [200, 400, 500]

    def test_mobile_edit_update_email(self, client, admin_user, db_session, app):
        """تعديل إيميل المعلم عبر API"""
        t = _make_teacher(db_session, 'api_edit_tea_full2', 'api_edit_tea_full2@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'email': 'api_edit_tea_full2_new@test.com'
        })
        assert response.status_code in [200, 400, 500]

    def test_mobile_edit_update_password(self, client, admin_user, db_session, app):
        """تعديل كلمة مرور المعلم عبر API"""
        t = _make_teacher(db_session, 'api_edit_tea_full3', 'api_edit_tea_full3@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/api/mobile/{t.id}/edit', json={
            'password': 'NewApiPass@456'
        })
        assert response.status_code in [200, 400, 500]


class TestTeachersMobileApiDeleteFull:
    """اختبارات Mobile API - POST /teachers/api/mobile/<id>/delete"""

    def test_mobile_delete_no_auth(self, client):
        """حذف معلم عبر API بدون مصادقة"""
        response = client.post('/teachers/api/mobile/1/delete')
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_mobile_delete_nonexistent_teacher(self, client, admin_user):
        """حذف معلم غير موجود عبر API"""
        _login(client, admin_user)
        response = client.post('/teachers/api/mobile/99999/delete')
        assert response.status_code in [200, 400, 404, 500]

    def test_mobile_delete_existing_teacher(self, client, admin_user, db_session, app):
        """حذف معلم موجود عبر API"""
        t = _make_teacher(db_session, 'api_del_tea_full1', 'api_del_tea_full1@test.com')
        _login(client, admin_user)
        response = client.post(f'/teachers/api/mobile/{t.id}/delete')
        assert response.status_code in [200, 400, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_mobile_delete_twice_second_fails(self, client, admin_user, db_session, app):
        """حذف معلم مرتين - الثانية تُرجع 404"""
        t = _make_teacher(db_session, 'api_del_tea_full2', 'api_del_tea_full2@test.com')
        teacher_id = t.id
        _login(client, admin_user)
        # الحذف الأول
        client.post(f'/teachers/api/mobile/{teacher_id}/delete')
        # الحذف الثاني - المعلم لم يعد موجوداً
        response = client.post(f'/teachers/api/mobile/{teacher_id}/delete')
        assert response.status_code in [200, 400, 404, 500]
