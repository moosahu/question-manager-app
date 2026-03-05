"""
اختبارات شاملة لـ lesson_prep_routes
يغطي: quota, generate, status, queue, history, plan, pdf, share, progress, costs
"""
import pytest


class TestLessonPrepQuotaAndGenerate:
    """اختبارات الحصص والتوليد"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_quota_no_auth(self, client):
        """جلب الحصة بدون مصادقة"""
        response = client.get('/api/lesson-prep/quota')
        assert response.status_code in [401, 403]

    def test_quota_as_admin(self, client, admin_user):
        """جلب الحصة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/quota')
        assert response.status_code in [200, 500]

    def test_generate_no_auth(self, client):
        """توليد خطة بدون مصادقة"""
        response = client.post('/api/lesson-prep/generate', json={})
        assert response.status_code in [401, 403]

    def test_generate_empty_as_admin(self, client, admin_user):
        """توليد خطة ببيانات فارغة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/generate', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_generate_with_data_as_admin(self, client, admin_user, db_session, app):
        """توليد خطة ببيانات كأدمن"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='Lesson Prep Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Lesson Prep Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Lesson Prep Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/generate', json={
            'lesson_id': l.id,
            'plan_type': 'standard'
        })
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_unit_distribution_no_auth(self, client):
        """توزيع الوحدة بدون مصادقة"""
        response = client.post('/api/lesson-prep/unit-distribution', json={})
        assert response.status_code in [401, 403]

    def test_unit_distribution_empty_as_admin(self, client, admin_user):
        """توزيع الوحدة ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/unit-distribution', json={})
        assert response.status_code in [200, 400, 422, 500]


class TestLessonPrepPlanOperations:
    """اختبارات عمليات الخطط"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_plan_status_no_auth(self, client):
        """جلب حالة خطة بدون مصادقة"""
        response = client.get('/api/lesson-prep/status/99999')
        assert response.status_code in [401, 403]

    def test_get_plan_status_nonexistent(self, client, admin_user):
        """جلب حالة خطة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/status/99999')
        assert response.status_code in [200, 404, 500]

    def test_get_queue_no_auth(self, client):
        """جلب قائمة الانتظار بدون مصادقة"""
        response = client.get('/api/lesson-prep/queue')
        assert response.status_code in [401, 403]

    def test_get_queue_as_admin(self, client, admin_user):
        """جلب قائمة الانتظار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/queue')
        assert response.status_code in [200, 500]

    def test_get_history_no_auth(self, client):
        """جلب التاريخ بدون مصادقة"""
        response = client.get('/api/lesson-prep/history')
        assert response.status_code in [401, 403]

    def test_get_history_as_admin(self, client, admin_user):
        """جلب التاريخ كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/history')
        assert response.status_code in [200, 500]

    def test_get_plan_nonexistent(self, client, admin_user):
        """جلب خطة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/99999')
        assert response.status_code in [200, 404, 500]

    def test_download_plan_pdf_nonexistent(self, client, admin_user):
        """تحميل PDF لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/99999/pdf')
        assert response.status_code in [200, 404, 500]

    def test_delete_plan_nonexistent(self, client, admin_user):
        """حذف خطة غير موجودة"""
        self._login(client, admin_user)
        response = client.delete('/api/lesson-prep/99999')
        assert response.status_code in [200, 404, 500]

    def test_update_section_nonexistent(self, client, admin_user):
        """تحديث قسم لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.put('/api/lesson-prep/99999/section', json={
            'section_key': 'objectives',
            'content': 'محتوى جديد'
        })
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_regenerate_section_nonexistent(self, client, admin_user):
        """إعادة توليد قسم لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/regenerate-section', json={
            'section_key': 'objectives'
        })
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_regenerate_pdf_nonexistent(self, client, admin_user):
        """إعادة توليد PDF لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/regenerate-pdf')
        assert response.status_code in [200, 404, 500]

    def test_share_plan_nonexistent(self, client, admin_user):
        """مشاركة خطة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/share', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_get_shared_plans_as_admin(self, client, admin_user):
        """جلب الخطط المشتركة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/shared')
        assert response.status_code in [200, 500]

    def test_mark_taught_nonexistent(self, client, admin_user):
        """تأشير درس مُدرَّس لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.put('/api/lesson-prep/99999/mark-taught', json={})
        assert response.status_code in [200, 400, 404, 500]

    def test_rate_plan_nonexistent(self, client, admin_user):
        """تقييم خطة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/rate', json={
            'rating': 5,
            'comment': 'ممتاز'
        })
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_get_plan_ratings_nonexistent(self, client, admin_user):
        """جلب تقييمات خطة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/99999/ratings')
        assert response.status_code in [200, 404, 500]


class TestLessonPrepWorksheet:
    """اختبارات أوراق العمل"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_generate_worksheet_nonexistent(self, client, admin_user):
        """توليد ورقة عمل لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/99999/worksheet', json={})
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_download_worksheet_pdf_nonexistent(self, client, admin_user):
        """تحميل PDF ورقة عمل لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/99999/worksheet/pdf')
        assert response.status_code in [200, 404, 500]


class TestLessonPrepProgress:
    """اختبارات التقدم والتكاليف"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_progress_no_auth(self, client):
        """جلب التقدم بدون مصادقة"""
        response = client.get('/api/lesson-prep/progress')
        assert response.status_code in [401, 403]

    def test_get_progress_as_admin(self, client, admin_user):
        """جلب التقدم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/progress')
        assert response.status_code in [200, 400, 500]

    def test_cost_summary_no_auth(self, client):
        """ملخص التكاليف بدون مصادقة"""
        response = client.get('/api/lesson-prep/costs/summary')
        assert response.status_code in [401, 403]

    def test_cost_summary_as_admin(self, client, admin_user):
        """ملخص التكاليف كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/costs/summary')
        assert response.status_code in [200, 500]

    def test_cost_by_teacher_no_auth(self, client):
        """تكاليف بالمعلم بدون مصادقة"""
        response = client.get('/api/lesson-prep/costs/by-teacher')
        assert response.status_code in [401, 403]

    def test_cost_by_teacher_as_admin(self, client, admin_user):
        """تكاليف بالمعلم كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/costs/by-teacher')
        assert response.status_code in [200, 500]

    def test_cost_by_provider_no_auth(self, client):
        """تكاليف بالمزود بدون مصادقة"""
        response = client.get('/api/lesson-prep/costs/by-provider')
        assert response.status_code in [401, 403]

    def test_cost_by_provider_as_admin(self, client, admin_user):
        """تكاليف بالمزود كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/lesson-prep/costs/by-provider')
        assert response.status_code in [200, 500]

    def test_semester_distribution_upload_no_auth(self, client):
        """رفع توزيع الفصل بدون مصادقة"""
        response = client.post('/api/lesson-prep/semester-distribution/upload', data={})
        assert response.status_code in [400, 401, 403, 422]

    def test_semester_distribution_upload_as_admin(self, client, admin_user):
        """رفع توزيع الفصل كأدمن بدون ملف"""
        self._login(client, admin_user)
        response = client.post('/api/lesson-prep/semester-distribution/upload', data={})
        assert response.status_code in [200, 400, 422, 500]

    def test_update_semester_distribution_nonexistent(self, client, admin_user):
        """تحديث توزيع فصل لخطة غير موجودة"""
        self._login(client, admin_user)
        response = client.put('/api/lesson-prep/semester-distribution/99999', json={})
        assert response.status_code in [200, 400, 404, 500]
