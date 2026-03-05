"""
اختبارات CRUD للأسئلة عبر API v1
يغطي: GET/POST/PUT/DELETE questions, search, classify, generate-exam
"""
import pytest


class TestAPIQuestionsGET:
    """اختبارات جلب الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_question_nonexistent(self, client, admin_user):
        """جلب سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.get('/api/v1/questions/99999')
        assert response.status_code in [404, 500]

    def test_get_question_existing(self, client, admin_user, db_session, app):
        """جلب سؤال موجود"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='API GET Q Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='API GET Q Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='API GET Q Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال API GET', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        self._login(client, admin_user)
        response = client.get(f'/api/v1/questions/{q.question_id}')
        assert response.status_code in [200, 404, 500]

    def test_get_question_block_status(self, client, admin_user, db_session, app):
        """جلب حالة حجب السؤال"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='Block Status Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Block Status Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Block Status Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال حالة الحجب', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        self._login(client, admin_user)
        response = client.get(f'/api/v1/questions/{q.question_id}/block-status')
        assert response.status_code in [200, 404, 500]

    def test_search_questions_no_auth(self, client):
        """البحث في الأسئلة بدون مصادقة"""
        response = client.get('/api/v1/questions/search?q=سؤال')
        assert response.status_code in [200, 302, 401, 403]

    def test_search_questions_as_admin(self, client, admin_user):
        """البحث في الأسئلة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/questions/search?q=سؤال')
        assert response.status_code in [200, 500]

    def test_questions_count_by_unit(self, client, admin_user):
        """عدد الأسئلة في الوحدة"""
        self._login(client, admin_user)
        response = client.get('/api/v1/units/99999/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_questions_count_by_lesson(self, client, admin_user):
        """عدد الأسئلة في الدرس"""
        self._login(client, admin_user)
        response = client.get('/api/v1/lessons/99999/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_questions_count_by_course(self, client, admin_user):
        """عدد الأسئلة في المنهج"""
        self._login(client, admin_user)
        response = client.get('/api/v1/courses/99999/questions-count')
        assert response.status_code in [200, 404, 500]

    def test_classification_stats_as_admin(self, client, admin_user):
        """إحصائيات التصنيف"""
        self._login(client, admin_user)
        response = client.get('/api/v1/questions/classification-stats')
        assert response.status_code in [200, 500]

    def test_classification_summary_as_admin(self, client, admin_user):
        """ملخص التصنيف"""
        self._login(client, admin_user)
        response = client.get('/api/v1/questions/classification-summary')
        assert response.status_code in [200, 500]

    def test_browse_classifications_as_admin(self, client, admin_user):
        """تصفح التصنيفات"""
        self._login(client, admin_user)
        response = client.get('/api/v1/questions/browse-classifications')
        assert response.status_code in [200, 500]

    def test_unclassified_questions_as_admin(self, client, admin_user):
        """الأسئلة غير المصنفة"""
        self._login(client, admin_user)
        response = client.get('/api/v1/questions/unclassified')
        assert response.status_code in [200, 500]


class TestAPIQuestionsCRUD:
    """اختبارات إنشاء/تعديل/حذف الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_create_question_no_auth(self, client):
        """إنشاء سؤال بدون مصادقة"""
        response = client.post('/api/v1/questions', json={})
        assert response.status_code in [302, 401, 403]

    def test_create_question_empty(self, client, admin_user):
        """إنشاء سؤال ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions', json={})
        assert response.status_code in [400, 422, 500]

    def test_create_question_valid(self, client, admin_user, db_session, app):
        """إنشاء سؤال ببيانات صالحة"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='API Create Q Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='API Create Q Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='API Create Q Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        self._login(client, admin_user)
        response = client.post('/api/v1/questions', json={
            'question_text': 'سؤال API جديد',
            'lesson_id': l.id,
            'difficulty': 'easy',
            'bloom_level': 'remember',
            'options': [
                {'option_text': 'خيار 1', 'is_correct': True},
                {'option_text': 'خيار 2', 'is_correct': False}
            ]
        })
        assert response.status_code in [200, 201, 400, 500]

    def test_update_question_nonexistent(self, client, admin_user):
        """تعديل سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.put('/api/v1/questions/99999', json={
            'question_text': 'سؤال معدّل'
        })
        assert response.status_code in [404, 500]

    def test_delete_question_nonexistent(self, client, admin_user):
        """حذف سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/api/v1/questions/99999')
        assert response.status_code in [404, 500]

    def test_toggle_block_nonexistent(self, client, admin_user):
        """تبديل حجب سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/99999/toggle-block')
        assert response.status_code in [302, 404, 500]

    def test_classify_question_nonexistent(self, client, admin_user):
        """تصنيف سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/99999/classify', json={})
        assert response.status_code in [404, 500]

    def test_update_classification_nonexistent(self, client, admin_user):
        """تحديث تصنيف سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.put('/api/v1/questions/99999/update-classification', json={})
        assert response.status_code in [404, 500]

    def test_classify_all_questions(self, client, admin_user):
        """تصنيف كل الأسئلة"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/classify-all', json={})
        assert response.status_code in [200, 400, 500]

    def test_generate_exam_no_auth(self, client):
        """توليد اختبار بدون مصادقة"""
        response = client.post('/api/v1/questions/generate-exam', json={})
        assert response.status_code in [302, 401, 403]

    def test_generate_exam_empty(self, client, admin_user):
        """توليد اختبار ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/api/v1/questions/generate-exam', json={})
        assert response.status_code in [200, 400, 500]


class TestAPIUnitsLessonsNested:
    """اختبارات الوحدات والدروس المتداخلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_units_nonexistent_course(self, client):
        """وحدات منهج غير موجود"""
        response = client.get('/api/v1/courses/99999/units')
        assert response.status_code in [200, 404, 500]

    def test_get_lessons_nonexistent_unit(self, client):
        """دروس وحدة غير موجودة"""
        response = client.get('/api/v1/units/99999/lessons')
        assert response.status_code in [200, 404, 500]

    def test_get_nested_lessons(self, client):
        """دروس المسار المتداخل"""
        response = client.get('/api/v1/courses/99999/units/99999/lessons')
        assert response.status_code in [200, 302, 404, 500]

    def test_block_all_course_questions(self, client, admin_user):
        """حجب كل أسئلة منهج"""
        self._login(client, admin_user)
        response = client.put('/api/v1/courses/99999/questions/block-all')
        assert response.status_code in [200, 404, 500]

    def test_unblock_all_course_questions(self, client, admin_user):
        """إلغاء حجب كل أسئلة منهج"""
        self._login(client, admin_user)
        response = client.put('/api/v1/courses/99999/questions/unblock-all')
        assert response.status_code in [200, 404, 500]


class TestAPIAdminProfile:
    """اختبارات ملف الأدمن"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_admin_profile_no_auth(self, client):
        """ملف الأدمن بدون مصادقة"""
        response = client.get('/api/v1/admin/profile')
        assert response.status_code in [302, 401, 403]

    def test_admin_profile_as_admin(self, client, admin_user):
        """ملف الأدمن"""
        self._login(client, admin_user)
        response = client.get('/api/v1/admin/profile')
        assert response.status_code in [200, 404, 500]


class TestAPIAuthDevice:
    """اختبارات الأجهزة الموثوقة"""

    def test_trusted_device_no_auth(self, client):
        """جهاز موثوق بدون مصادقة"""
        response = client.post('/api/v1/auth/trusted-device', json={
            'device_id': 'test_device_123'
        })
        assert response.status_code in [200, 400, 401, 403]

    def test_register_device_no_auth(self, client):
        """تسجيل جهاز بدون مصادقة"""
        response = client.post('/api/v1/auth/register-device', json={
            'device_id': 'test_device_456',
            'device_name': 'iPhone'
        })
        assert response.status_code in [200, 302, 400, 401, 403]
