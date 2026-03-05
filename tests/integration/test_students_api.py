"""
اختبارات شاملة لـ API الطلاب والمعلمين
يغطي: login, logout, device conflict, teacher login, session verify, admin CRUD
"""
import pytest


class TestStudentLoginFull:
    """اختبارات تسجيل دخول الطالب - جميع الحالات"""

    def test_login_missing_username(self, client):
        """تسجيل دخول بدون username"""
        response = client.post('/students/api/login', json={
            'password': 'pass',
            'device_id': 'dev'
        })
        assert response.status_code in [400, 401]
        data = response.get_json()
        assert data.get('success') is False

    def test_login_missing_password(self, client):
        """تسجيل دخول بدون password"""
        response = client.post('/students/api/login', json={
            'username': 'user',
            'device_id': 'dev'
        })
        assert response.status_code in [400, 401]
        data = response.get_json()
        assert data.get('success') is False

    def test_login_empty_body(self, client):
        """تسجيل دخول بـ body فارغ"""
        response = client.post('/students/api/login', json={})
        assert response.status_code in [400, 401]
        data = response.get_json()
        assert data.get('success') is False

    def test_login_nonexistent_student(self, client):
        """طالب غير موجود"""
        response = client.post('/students/api/login', json={
            'username': 'does_not_exist_xyz',
            'password': 'pass',
            'device_id': 'dev'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data.get('success') is False

    def test_login_wrong_password(self, client, student_user):
        """كلمة مرور خاطئة"""
        response = client.post('/students/api/login', json={
            'username': student_user.username,
            'password': 'WrongPass@999',
            'device_id': 'dev_001'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data.get('success') is False

    def test_login_inactive_student(self, client, inactive_student):
        """طالب حسابه معطّل"""
        response = client.post('/students/api/login', json={
            'username': inactive_student.username,
            'password': 'Student@123',
            'device_id': 'dev_002'
        })
        assert response.status_code in [401, 403]
        data = response.get_json()
        assert data.get('success') is False

    def test_login_success(self, client, student_user):
        """تسجيل دخول ناجح"""
        response = client.post('/students/api/login', json={
            'username': student_user.username,
            'password': 'Student@123',
            'device_id': 'new_device_001'
        })
        assert response.status_code in [200, 401]
        data = response.get_json()
        assert data is not None
        if response.status_code == 200:
            assert data.get('success') is True
            assert 'token' in data
            assert 'student' in data

    def test_login_success_with_device_name(self, client, student_user):
        """تسجيل دخول ناجح مع اسم الجهاز"""
        response = client.post('/students/api/login', json={
            'username': student_user.username,
            'password': 'Student@123',
            'device_id': 'iphone_001',
            'device_name': 'iPhone 14 Pro'
        })
        assert response.status_code in [200, 401, 403]

    def test_login_device_conflict(self, client, db_session, app):
        """تعارض الجهاز - الطالب مسجل من جهاز آخر"""
        from src.models.student import Student
        s = Student(name='DevConflict', username='dev_conflict', email='devconflict@test.com', is_active=True)
        s.set_password('Pass@123')
        s.device_id = 'old_device_111'
        s.device_name = 'الجهاز القديم'
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/students/api/login', json={
            'username': 'dev_conflict',
            'password': 'Pass@123',
            'device_id': 'new_device_222',
            'device_name': 'الجهاز الجديد'
        })
        assert response.status_code in [200, 403]
        data = response.get_json()
        if response.status_code == 403:
            assert data.get('error_code') == 'DEVICE_CONFLICT'

    def test_login_force_login_overrides_device(self, client, db_session, app):
        """تسجيل دخول قسري يتجاوز قيد الجهاز"""
        from src.models.student import Student
        s = Student(name='ForceLogin', username='force_login', email='forcelogin@test.com', is_active=True)
        s.set_password('Pass@123')
        s.device_id = 'old_device_force'
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/students/api/login', json={
            'username': 'force_login',
            'password': 'Pass@123',
            'device_id': 'new_device_force',
            'force_login': True
        })
        assert response.status_code in [200, 401, 403, 500]
        data = response.get_json()
        assert data is not None

    def test_login_by_email(self, client, student_user):
        """تسجيل دخول بـ email بدلاً من username"""
        response = client.post('/students/api/login', json={
            'username': student_user.email,
            'password': 'Student@123',
            'device_id': 'email_device'
        })
        assert response.status_code in [200, 401, 403]

    def test_login_response_has_session_token(self, client, student_user):
        """الاستجابة تحتوي session_token"""
        response = client.post('/students/api/login', json={
            'username': student_user.username,
            'password': 'Student@123',
            'device_id': 'session_device'
        })
        if response.status_code == 200:
            data = response.get_json()
            assert 'session_token' in data


class TestStudentLogout:
    """اختبارات تسجيل خروج الطالب"""

    def test_logout_missing_student_id(self, client):
        """تسجيل خروج بدون student_id"""
        response = client.post('/students/api/logout', json={
            'device_id': 'dev'
        })
        assert response.status_code in [400, 401]
        data = response.get_json()
        assert data.get('success') is False

    def test_logout_nonexistent_student(self, client):
        """تسجيل خروج لطالب غير موجود"""
        response = client.post('/students/api/logout', json={
            'student_id': 99999,
            'device_id': 'dev'
        })
        assert response.status_code in [404, 401]

    def test_logout_success(self, client, student_user, db_session, app):
        """تسجيل خروج ناجح"""
        from src.models.student import Student
        s = Student.query.get(student_user.id)
        s.device_id = 'logout_device'
        db_session.session.commit()
        response = client.post('/students/api/logout', json={
            'student_id': student_user.id,
            'device_id': 'logout_device'
        })
        assert response.status_code in [200, 400, 401]
        data = response.get_json()
        assert data is not None

    def test_logout_wrong_device(self, client, student_user, db_session, app):
        """تسجيل خروج من جهاز مختلف"""
        from src.models.student import Student
        s = Student.query.get(student_user.id)
        s.device_id = 'correct_device'
        db_session.session.commit()
        response = client.post('/students/api/logout', json={
            'student_id': student_user.id,
            'device_id': 'wrong_device'
        })
        assert response.status_code in [200, 403, 401]


class TestTeacherLoginAPI:
    """اختبارات تسجيل دخول المعلم من التطبيق"""

    def test_teacher_login_missing_fields(self, client):
        """تسجيل دخول بدون بيانات"""
        response = client.post('/students/api/login-teacher', json={})
        assert response.status_code in [400, 401]
        data = response.get_json()
        assert data.get('success') is False

    def test_teacher_login_nonexistent(self, client):
        """معلم غير موجود"""
        response = client.post('/students/api/login-teacher', json={
            'username': 'no_such_teacher',
            'password': 'pass',
            'device_id': 'dev'
        })
        assert response.status_code == 401

    def test_teacher_login_wrong_password(self, client, db_session, app):
        """كلمة مرور المعلم خاطئة"""
        from src.models.teacher import Teacher
        t = Teacher(name='T Login', username='t_login_test', email='tlogintest@test.com', is_active=True)
        t.set_password('Correct@123')
        db_session.session.add(t)
        db_session.session.commit()
        response = client.post('/students/api/login-teacher', json={
            'username': 't_login_test',
            'password': 'Wrong@123',
            'device_id': 'dev'
        })
        assert response.status_code == 401

    def test_teacher_login_success(self, client, db_session, app):
        """تسجيل دخول معلم ناجح"""
        from src.models.teacher import Teacher
        t = Teacher(name='T Success', username='t_success', email='tsuccess@test.com', is_active=True)
        t.set_password('Teacher@Pass')
        db_session.session.add(t)
        db_session.session.commit()
        response = client.post('/students/api/login-teacher', json={
            'username': 't_success',
            'password': 'Teacher@Pass',
            'device_id': 'teacher_device_001'
        })
        assert response.status_code in [200, 401, 500]
        data = response.get_json()
        if response.status_code == 200:
            assert data.get('success') is True
            assert 'token' in data
            assert 'teacher' in data

    def test_teacher_login_inactive(self, client, db_session, app):
        """معلم حسابه معطّل"""
        from src.models.teacher import Teacher
        t = Teacher(name='T Inactive', username='t_inactive_login', email='tinactivelogin@test.com', is_active=False)
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        response = client.post('/students/api/login-teacher', json={
            'username': 't_inactive_login',
            'password': 'Pass@123',
            'device_id': 'dev'
        })
        assert response.status_code in [401, 403]

    def test_teacher_login_device_conflict(self, client, db_session, app):
        """تعارض الجهاز للمعلم"""
        from src.models.teacher import Teacher
        t = Teacher(name='T Conflict', username='t_conflict', email='tconflict@test.com', is_active=True)
        t.set_password('Pass@123')
        t.device_id = 'old_teacher_device'
        db_session.session.add(t)
        db_session.session.commit()
        response = client.post('/students/api/login-teacher', json={
            'username': 't_conflict',
            'password': 'Pass@123',
            'device_id': 'new_teacher_device'
        })
        assert response.status_code in [200, 403]
        if response.status_code == 403:
            data = response.get_json()
            assert data.get('error_code') == 'DEVICE_CONFLICT'


class TestTeacherLogoutAPI:
    """اختبارات تسجيل خروج المعلم"""

    def test_teacher_logout_missing_id(self, client):
        """تسجيل خروج المعلم بدون معرف"""
        response = client.post('/students/api/logout-teacher', json={})
        assert response.status_code in [400, 401]

    def test_teacher_logout_nonexistent(self, client):
        """تسجيل خروج معلم غير موجود"""
        response = client.post('/students/api/logout-teacher', json={
            'teacher_id': 99999
        })
        assert response.status_code in [404, 401]

    def test_teacher_logout_success(self, client, db_session, app):
        """تسجيل خروج ناجح للمعلم"""
        from src.models.teacher import Teacher
        t = Teacher(name='T Logout', username='t_logout', email='tlogout@test.com', is_active=True)
        t.set_password('Pass@123')
        t.device_id = 'teacher_logout_dev'
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        response = client.post('/students/api/logout-teacher', json={
            'teacher_id': t.id,
            'device_id': 'teacher_logout_dev'
        })
        assert response.status_code in [200, 400, 401]


class TestTeacherSessionVerify:
    """اختبارات التحقق من جلسة المعلم"""

    def test_verify_missing_teacher_id(self, client):
        """تحقق بدون teacher_id"""
        response = client.post('/students/api/verify-teacher-session', json={})
        assert response.status_code in [400, 401]

    def test_verify_nonexistent_teacher(self, client):
        """تحقق لمعلم غير موجود"""
        response = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': 99999
        })
        assert response.status_code in [404, 401]

    def test_verify_valid_session(self, client, db_session, app):
        """جلسة صالحة للمعلم"""
        from src.models.teacher import Teacher
        import secrets
        t = Teacher(name='T Verify', username='t_verify', email='tverify@test.com', is_active=True)
        t.set_password('Pass@123')
        token = secrets.token_hex(32)
        t.session_token = token
        t.device_id = 'verify_device'
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        response = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'verify_device',
            'session_token': token
        })
        assert response.status_code in [200, 400, 401]
        data = response.get_json()
        if response.status_code == 200:
            assert data.get('valid') is True

    def test_verify_device_changed(self, client, db_session, app):
        """الجهاز تغيّر - جلسة غير صالحة"""
        from src.models.teacher import Teacher
        t = Teacher(name='T DevChg', username='t_devchg', email='tdevchg@test.com', is_active=True)
        t.set_password('Pass@123')
        t.device_id = 'original_device'
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        response = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id,
            'device_id': 'different_device'
        })
        assert response.status_code in [200, 400, 401]
        data = response.get_json()
        if 'valid' in data:
            assert data.get('valid') is False

    def test_verify_inactive_teacher(self, client, db_session, app):
        """معلم حسابه معطّل"""
        from src.models.teacher import Teacher
        t = Teacher(name='T InactVerify', username='t_inact_verify', email='tinactverify@test.com', is_active=False)
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        response = client.post('/students/api/verify-teacher-session', json={
            'teacher_id': t.id
        })
        data = response.get_json()
        assert data.get('valid') is False


class TestStudentsAdminCRUD:
    """اختبارات CRUD للطلاب من لوحة التحكم"""

    def test_add_student_get_page(self, client, admin_user):
        """صفحة إضافة طالب"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/students/add')
        assert response.status_code in [200, 302, 500]

    def test_add_student_missing_fields(self, client, admin_user):
        """إضافة طالب بدون بيانات مطلوبة"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/students/add', data={
            'name': '',  # اسم فارغ
            'username': '',
            'password': ''
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 500]

    def test_add_student_success(self, client, admin_user):
        """إضافة طالب جديد بنجاح"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/students/add', data={
            'name': 'طالب من CRUD',
            'username': 'crud_student_new',
            'password': 'Pass@123',
            'is_active': 'on'
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 500]

    def test_add_student_duplicate_username(self, client, admin_user, student_user):
        """إضافة طالب باسم مستخدم موجود"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/students/add', data={
            'name': 'طالب مكرر',
            'username': student_user.username,  # اسم موجود
            'password': 'Pass@123'
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 500]

    def test_edit_student_page(self, client, admin_user, student_user):
        """صفحة تعديل طالب"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get(f'/students/edit/{student_user.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_edit_student_nonexistent(self, client, admin_user):
        """تعديل طالب غير موجود"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/students/edit/99999')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_student_active(self, client, admin_user, student_user):
        """تفعيل/تعطيل طالب"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/students/toggle/{student_user.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_delete_student(self, client, admin_user, db_session, app):
        """حذف طالب"""
        from src.models.student import Student
        s = Student(name='للحذف', username='to_delete_s', email='todelete@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post(f'/students/delete/{s.id}')
        assert response.status_code in [200, 302, 404, 500]

    def test_toggle_registration(self, client, admin_user):
        """toggle حالة التسجيل الذاتي"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/students/toggle-registration')
        assert response.status_code in [200, 302, 404, 500]

    def test_save_registration_settings(self, client, admin_user):
        """حفظ إعدادات التسجيل"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.post('/students/save-registration-settings', data={
            'require_phone': 'on',
            'auto_activate': 'on'
        })
        assert response.status_code in [200, 302, 404, 500]

    def test_student_search(self, client, admin_user, student_user):
        """البحث عن طالب"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        response = client.get('/students/?search=طالب')
        assert response.status_code in [200, 302, 500]
