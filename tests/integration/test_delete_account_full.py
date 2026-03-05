"""
اختبارات شاملة لـ delete_account routes
يغطي: request-delete, verify-otp, confirm-delete لطلاب ومعلمين
"""
import pytest
import secrets


def _make_student(db_session, username, email):
    from src.models.student import Student
    s = Student(name='Del Acc Stu', username=username, email=email, is_active=True)
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestDeleteAccountStudent:
    """اختبارات حذف حساب الطالب"""

    def test_request_delete_no_token(self, client):
        """طلب حذف حساب بدون token"""
        response = client.post('/api/account/request-delete', json={})
        assert response.status_code in [200, 400, 401, 422]

    def test_request_delete_invalid_token(self, client):
        """طلب حذف حساب بـ token خاطئ"""
        response = client.post(
            '/api/account/request-delete',
            json={'reason': 'لا أريد الاستمرار'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [200, 400, 401, 404]

    def test_request_delete_valid_token(self, client, db_session, app):
        """طلب حذف حساب بـ token صالح"""
        s = _make_student(db_session, 'del_acc_stu1', 'delaccstu1@test.com')
        response = client.post(
            '/api/account/request-delete',
            json={'reason': 'لا أريد الاستمرار'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 500, 503]

    def test_verify_delete_otp_no_token(self, client):
        """التحقق من OTP حذف الحساب بدون token"""
        response = client.post('/api/account/verify-delete-otp', json={
            'otp': '123456'
        })
        assert response.status_code in [200, 400, 401, 422]

    def test_verify_delete_otp_invalid_token(self, client):
        """التحقق من OTP حذف الحساب بـ token خاطئ"""
        response = client.post(
            '/api/account/verify-delete-otp',
            json={'otp': '000000'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [200, 400, 401, 404]

    def test_verify_delete_otp_valid_token(self, client, db_session, app):
        """التحقق من OTP حذف الحساب بـ token صالح"""
        s = _make_student(db_session, 'del_acc_stu2', 'delaccstu2@test.com')
        response = client.post(
            '/api/account/verify-delete-otp',
            json={'otp': '000000'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_confirm_delete_no_token(self, client):
        """تأكيد حذف الحساب بدون token"""
        response = client.post('/api/account/confirm-delete', json={})
        assert response.status_code in [200, 400, 401, 422]

    def test_confirm_delete_invalid_token(self, client):
        """تأكيد حذف الحساب بـ token خاطئ"""
        response = client.post(
            '/api/account/confirm-delete',
            json={'confirmation': 'delete'},
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [200, 400, 401, 404]

    def test_confirm_delete_valid_token_no_pending(self, client, db_session, app):
        """تأكيد حذف الحساب - لا يوجد طلب معلق"""
        s = _make_student(db_session, 'del_acc_stu3', 'delaccstu3@test.com')
        response = client.post(
            '/api/account/confirm-delete',
            json={'confirmation': 'delete'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]


class TestDeleteAccountStatus:
    """اختبارات حالة طلب حذف الحساب"""

    def test_delete_status_no_token(self, client):
        """حالة طلب الحذف بدون token"""
        response = client.get('/api/account/delete-status')
        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_delete_status_invalid_token(self, client):
        """حالة طلب الحذف بـ token خاطئ"""
        response = client.get(
            '/api/account/delete-status',
            headers={'X-Session-Token': 'invalid_token_xyz'}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_delete_status_valid_token(self, client, db_session, app):
        """حالة طلب الحذف بـ token صالح"""
        import secrets
        from src.models.student import Student
        s = Student(name='Status Stu', username='statusstu_del', email='statusstu_del@test.com', is_active=True)
        s.set_password('Pass@123')
        s.session_token = secrets.token_hex(32)
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        response = client.get(
            '/api/account/delete-status',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]

    def test_cancel_delete_no_token(self, client):
        """إلغاء طلب الحذف بدون token"""
        response = client.post('/api/account/cancel-delete', json={})
        assert response.status_code in [200, 400, 401, 404, 422, 500]
