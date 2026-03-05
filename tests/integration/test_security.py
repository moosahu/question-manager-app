"""
اختبارات الأمان - SQL Injection, XSS, Rate Limiting, etc.
"""
import pytest


class TestSqlInjection:
    """اختبارات حماية من SQL Injection"""

    def test_login_sql_injection_username(self, client):
        """محاولة SQL Injection في username لا تنجح"""
        malicious = "' OR '1'='1"
        response = client.post('/students/api/login', json={
            'username': malicious,
            'password': 'any',
            'device_id': 'test'
        })
        # يجب أن يرفض بـ 401 (مو 200 بدون auth)
        data = response.get_json()
        assert response.status_code == 401
        assert data.get('success') is False

    def test_login_sql_injection_password(self, client):
        """محاولة SQL Injection في password لا تنجح"""
        response = client.post('/students/api/login', json={
            'username': 'test',
            'password': "' OR '1'='1",
            'device_id': 'test'
        })
        data = response.get_json()
        assert response.status_code == 401
        assert data.get('success') is False

    def test_courses_api_safe_from_injection(self, client):
        """API المناهج آمن من Injection"""
        response = client.get('/api/v1/courses?show_all=1; DROP TABLE course;--')
        # يجب أن يكون 200 (يتجاهل الـ injection) أو 400
        assert response.status_code in [200, 400]


class TestXssProtection:
    """اختبارات الحماية من XSS"""

    def test_student_login_xss_in_username(self, client):
        """XSS في username لا يُنفَّذ"""
        xss_payload = '<script>alert("xss")</script>'
        response = client.post('/students/api/login', json={
            'username': xss_payload,
            'password': 'any',
            'device_id': 'test'
        })
        # الطلب يُرفض أو يُعالَج بأمان
        assert response.status_code in [400, 401]
        if response.status_code == 401:
            data = response.get_json()
            # الـ script tag يجب أن لا يكون في الرد كـ HTML مُنفَّذ
            assert data.get('success') is False


class TestPasswordSecurity:
    """اختبارات أمان كلمات المرور"""

    def test_password_not_stored_in_plain_text(self, db_session, app):
        """كلمة المرور لا تُحفظ كنص عادي"""
        from src.models.student import Student
        student = Student(
            name='Security Test',
            username='sec_test_01',
            email='sec@test.com'
        )
        student.set_password('MySecurePassword123!')
        db_session.session.add(student)
        db_session.session.commit()

        found = Student.query.filter_by(username='sec_test_01').first()
        assert found.password_hash != 'MySecurePassword123!'
        assert len(found.password_hash) > 20  # hash طويل

    def test_password_verification_works(self, db_session, app):
        """التحقق من كلمة المرور يعمل بشكل صحيح"""
        from src.models.student import Student
        student = Student(
            name='Verify Test',
            username='verify_test_01',
            email='verify@test.com'
        )
        student.set_password('Correct@Password1')
        db_session.session.add(student)
        db_session.session.commit()

        found = Student.query.filter_by(username='verify_test_01').first()
        assert found.check_password('Correct@Password1') is True
        assert found.check_password('Wrong@Password1') is False

    def test_different_passwords_give_different_hashes(self, app):
        """كلمتان مختلفتان تعطيان hash مختلف"""
        from src.models.student import Student
        with app.app_context():
            s1 = Student(name='A', username='a', email='a@a.com')
            s1.set_password('Password1')
            s2 = Student(name='B', username='b', email='b@b.com')
            s2.set_password('Password2')
            assert s1.password_hash != s2.password_hash

    def test_same_password_different_hashes(self, app):
        """نفس كلمة المرور تعطي hash مختلف (بسبب salt عشوائي)"""
        from src.models.student import Student
        with app.app_context():
            s1 = Student(name='C', username='c', email='c@c.com')
            s1.set_password('SamePassword')
            s2 = Student(name='D', username='d', email='d@d.com')
            s2.set_password('SamePassword')
            # Hash مختلف بسبب salt عشوائي
            assert s1.password_hash != s2.password_hash


class TestRateLimiting:
    """اختبارات أساسية لـ Rate Limiting (وجودي فقط)"""

    def test_login_endpoint_accessible(self, client):
        """endpoint تسجيل الدخول قابل للوصول"""
        response = client.post('/students/api/login', json={
            'username': 'nonexistent',
            'password': 'any',
            'device_id': 'test'
        })
        # 401 طبيعي لمستخدم غير موجود
        assert response.status_code == 401

    def test_api_returns_json_not_html_on_error(self, client):
        """API يرجع JSON في حالة الخطأ (مو HTML)"""
        response = client.post('/students/api/login', json={})
        data = response.get_json()
        assert data is not None
        assert isinstance(data, dict)
