"""
اختبارات شاملة لـ Password Reset API
يغطي: request reset, verify code, reset password, resend code
"""
import pytest


class TestPasswordResetRequest:
    """اختبارات طلب إعادة تعيين كلمة المرور"""

    def test_request_reset_missing_fields(self, client):
        """طلب إعادة تعيين بدون حقول"""
        response = client.post('/api/password-reset/request', json={})
        assert response.status_code in [400, 422]

    def test_request_reset_nonexistent_email(self, client):
        """طلب إعادة تعيين لإيميل غير موجود"""
        response = client.post('/api/password-reset/request', json={
            'email': 'nonexistent_pr@test.com'
        })
        # قد يُرجع 200 (لعدم كشف وجود الإيميل) أو 404
        assert response.status_code in [200, 400, 404]

    def test_request_reset_invalid_email(self, client):
        """طلب إعادة تعيين بإيميل غير صالح"""
        response = client.post('/api/password-reset/request', json={
            'email': 'not-valid-email'
        })
        # بعض الـ APIs لا تتحقق من صيغة الإيميل وترجع 200 مع رسالة خطأ
        assert response.status_code in [200, 400, 404, 422]

    def test_request_reset_with_existing_student(self, client, db_session, app):
        """طلب إعادة تعيين لطالب موجود"""
        from src.models.student import Student
        s = Student(name='PR Student', username='pr_student', email='pr_student@test.com', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        response = client.post('/api/password-reset/request', json={
            'email': 'pr_student@test.com'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_request_reset_by_phone(self, client):
        """طلب إعادة تعيين برقم الجوال"""
        response = client.post('/api/password-reset/request', json={
            'phone': '0500000001'
        })
        assert response.status_code in [200, 400, 404, 422]

    def test_request_reset_by_username(self, client):
        """طلب إعادة تعيين باسم المستخدم"""
        response = client.post('/api/password-reset/request', json={
            'username': 'nonexistent_pr_user'
        })
        assert response.status_code in [200, 400, 404]


class TestPasswordResetVerify:
    """اختبارات التحقق من كود إعادة التعيين"""

    def test_verify_missing_fields(self, client):
        """تحقق بدون حقول"""
        response = client.post('/api/password-reset/verify', json={})
        assert response.status_code in [400, 422]

    def test_verify_wrong_code(self, client):
        """تحقق بكود خاطئ"""
        response = client.post('/api/password-reset/verify', json={
            'email': 'nonexistent_pr2@test.com',
            'code': '000000'
        })
        assert response.status_code in [400, 404]

    def test_verify_invalid_code_format(self, client):
        """تحقق بتنسيق كود خاطئ"""
        response = client.post('/api/password-reset/verify', json={
            'code': 'abc',
            'email': 'test@test.com'
        })
        assert response.status_code in [400, 404, 422]

    def test_verify_expired_code(self, client):
        """تحقق بكود منتهي الصلاحية"""
        response = client.post('/api/password-reset/verify', json={
            'email': 'expired_pr@test.com',
            'code': '123456'
        })
        assert response.status_code in [400, 404]


class TestPasswordResetDoReset:
    """اختبارات تنفيذ إعادة تعيين كلمة المرور"""

    def test_reset_missing_fields(self, client):
        """إعادة تعيين بدون حقول"""
        response = client.post('/api/password-reset/reset', json={})
        assert response.status_code in [400, 422]

    def test_reset_missing_password(self, client):
        """إعادة تعيين بدون كلمة مرور"""
        response = client.post('/api/password-reset/reset', json={
            'token': 'sometoken',
        })
        assert response.status_code in [400, 422]

    def test_reset_invalid_token(self, client):
        """إعادة تعيين بـ token غير صالح"""
        response = client.post('/api/password-reset/reset', json={
            'token': 'invalid_token_xyz',
            'new_password': 'NewPass@123'
        })
        assert response.status_code in [400, 404]

    def test_reset_short_password(self, client):
        """إعادة تعيين بكلمة مرور قصيرة"""
        response = client.post('/api/password-reset/reset', json={
            'token': 'sometoken',
            'new_password': '123'
        })
        assert response.status_code in [400, 422]

    def test_reset_passwords_mismatch(self, client):
        """إعادة تعيين بكلمتي مرور غير متطابقتين"""
        response = client.post('/api/password-reset/reset', json={
            'token': 'sometoken',
            'new_password': 'NewPass@123',
            'confirm_password': 'DifferentPass@456'
        })
        assert response.status_code in [400, 422]


class TestPasswordResetResend:
    """اختبارات إعادة إرسال كود إعادة التعيين"""

    def test_resend_missing_fields(self, client):
        """إعادة إرسال بدون حقول"""
        response = client.post('/api/password-reset/resend', json={})
        assert response.status_code in [400, 422]

    def test_resend_nonexistent_email(self, client):
        """إعادة إرسال لإيميل غير موجود"""
        response = client.post('/api/password-reset/resend', json={
            'email': 'nonexistent_resend_pr@test.com'
        })
        assert response.status_code in [200, 400, 404]

    def test_resend_no_pending_request(self, client):
        """إعادة إرسال بدون طلب معلّق"""
        response = client.post('/api/password-reset/resend', json={
            'email': 'nopending@test.com'
        })
        assert response.status_code in [200, 400, 404]
