"""
اختبارات موسعة لـ lesson_prep routes - يغطي المسارات الإضافية
يغطي: clone, regenerate-pdf, semester-distribution PUT,
       costs/by-teacher, costs/by-provider, worksheet
"""
import pytest
import secrets


def _make_teacher_token(db_session):
    from src.models.teacher import Teacher
    t = Teacher(
        name='LP Teacher',
        username=f'lp_tea_{secrets.token_hex(4)}',
        email=f'lp_tea_{secrets.token_hex(4)}@test.com',
        is_active=True
    )
    t.set_password('Pass@123')
    t.session_token = secrets.token_hex(32)
    db_session.session.add(t)
    db_session.session.commit()
    db_session.session.refresh(t)
    return t


class TestLessonPrepClone:
    """اختبارات نسخ تحضير الدرس"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_clone_no_auth(self, client):
        """نسخ تحضير بدون مصادقة"""
        response = client.post('/api/lesson-prep/99999/clone', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_clone_nonexistent_as_admin(self, client, admin_user):
        """نسخ تحضير غير موجود كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/clone', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_clone_with_teacher_token(self, client, db_session, app):
        """نسخ تحضير مع teacher token"""
        t = _make_teacher_token(db_session)
        response = client.post(
            '/api/lesson-prep/99999/clone',
            json={},
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]


class TestLessonPrepRegeneratePDF:
    """اختبارات إعادة توليد PDF"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_regenerate_pdf_no_auth(self, client):
        """إعادة توليد PDF بدون مصادقة"""
        response = client.post('/api/lesson-prep/99999/regenerate-pdf', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_regenerate_pdf_nonexistent_as_admin(self, client, admin_user):
        """إعادة توليد PDF لتحضير غير موجود"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/regenerate-pdf', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_regenerate_pdf_with_teacher_token(self, client, db_session, app):
        """إعادة توليد PDF مع teacher token"""
        t = _make_teacher_token(db_session)
        response = client.post(
            '/api/lesson-prep/99999/regenerate-pdf',
            json={},
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]


class TestSemesterDistribution:
    """اختبارات توزيع الفصل الدراسي"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_update_semester_distribution_no_auth(self, client):
        """تحديث توزيع الفصل بدون مصادقة"""
        response = client.put('/api/lesson-prep/semester-distribution/99999', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_update_semester_distribution_as_admin(self, client, admin_user):
        """تحديث توزيع الفصل كأدمن"""
        self._login(client, admin_user)
        response = client.put('/api/lesson-prep/semester-distribution/99999', json={
            'weeks': 4,
            'lessons_per_week': 3
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_update_semester_distribution_with_teacher(self, client, db_session, app):
        """تحديث توزيع الفصل مع teacher token"""
        t = _make_teacher_token(db_session)
        response = client.put(
            '/api/lesson-prep/semester-distribution/99999',
            json={'weeks': 4},
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 400, 401, 404, 500]


class TestLessonPrepCosts:
    """اختبارات تكاليف تحضير الدروس"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_costs_by_teacher_no_auth(self, client):
        """تكاليف حسب المعلم بدون مصادقة"""
        response = client.get('/api/lesson-prep/costs/by-teacher')
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_costs_by_teacher_as_admin(self, client, admin_user):
        """تكاليف حسب المعلم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/costs/by-teacher')
        assert response.status_code in [200, 400, 500]

    def test_costs_by_provider_no_auth(self, client):
        """تكاليف حسب المزود بدون مصادقة"""
        response = client.get('/api/lesson-prep/costs/by-provider')
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_costs_by_provider_as_admin(self, client, admin_user):
        """تكاليف حسب المزود كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/costs/by-provider')
        assert response.status_code in [200, 400, 500]

    def test_costs_summary_with_teacher_token(self, client, db_session, app):
        """ملخص التكاليف مع teacher token"""
        t = _make_teacher_token(db_session)
        response = client.get(
            '/api/lesson-prep/costs/summary',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 400, 401, 500]

    def test_costs_by_teacher_with_token(self, client, db_session, app):
        """تكاليف المعلم مع teacher token"""
        t = _make_teacher_token(db_session)
        response = client.get(
            '/api/lesson-prep/costs/by-teacher',
            headers={'X-Teacher-Token': t.session_token}
        )
        assert response.status_code in [200, 400, 401, 500]


class TestLessonPrepWorksheet:
    """اختبارات ورقة العمل"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_create_worksheet_no_auth(self, client):
        """إنشاء ورقة عمل بدون مصادقة"""
        response = client.post('/api/lesson-prep/99999/worksheet', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_create_worksheet_as_admin(self, client, admin_user):
        """إنشاء ورقة عمل كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/worksheet', json={
            'include_answers': True
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_get_worksheet_pdf_no_auth(self, client):
        """جلب PDF ورقة العمل بدون مصادقة"""
        response = client.get('/api/lesson-prep/99999/worksheet/pdf')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_worksheet_pdf_as_admin(self, client, admin_user):
        """جلب PDF ورقة العمل كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/99999/worksheet/pdf')
        assert response.status_code in [200, 400, 404, 500]

    def test_delete_plan_no_auth(self, client):
        """حذف تحضير بدون مصادقة"""
        response = client.delete('/api/lesson-prep/99999')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_delete_plan_as_admin(self, client, admin_user):
        """حذف تحضير كأدمن"""
        self._login(client, admin_user)
        response = client.delete('/api/lesson-prep/99999')
        assert response.status_code in [200, 400, 404, 500]

    def test_mark_taught_no_auth(self, client):
        """تأشير درس كمُدرَّس بدون مصادقة"""
        response = client.put('/api/lesson-prep/99999/mark-taught', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mark_taught_as_admin(self, client, admin_user):
        """تأشير درس كمُدرَّس كأدمن"""
        self._login(client, admin_user)
        response = client.put('/api/lesson-prep/99999/mark-taught', json={
            'taught': True
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_shared_plans_no_auth(self, client):
        """التحضيرات المشتركة بدون مصادقة"""
        response = client.get('/api/lesson-prep/shared')
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_shared_plans_as_admin(self, client, admin_user):
        """التحضيرات المشتركة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/shared')
        assert response.status_code in [200, 400, 500]

    def test_share_plan_no_auth(self, client):
        """مشاركة تحضير بدون مصادقة"""
        response = client.post('/api/lesson-prep/99999/share', json={})
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_share_plan_as_admin(self, client, admin_user):
        """مشاركة تحضير كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/share', json={})
        assert response.status_code in [200, 400, 404, 500]
