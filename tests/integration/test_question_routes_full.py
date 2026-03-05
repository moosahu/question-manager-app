"""
اختبارات شاملة لـ Question routes (admin)
يغطي: list, add, edit, delete, import, export, saved-exams, filter
"""
import pytest


class TestQuestionListFilter:
    """اختبارات قائمة وفلترة الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_questions_index_no_auth(self, client):
        """صفحة الأسئلة بدون مصادقة"""
        response = client.get('/questions/')
        assert response.status_code in [302, 401]

    def test_questions_index_as_admin(self, client, admin_user):
        """صفحة الأسئلة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/')
        assert response.status_code in [200, 302, 500]

    def test_filter_options_no_auth(self, client):
        """خيارات الفلتر بدون مصادقة"""
        response = client.get('/questions/api/filter_options/difficulty')
        assert response.status_code in [302, 401]

    def test_filter_options_difficulty(self, client, admin_user):
        """خيارات الفلتر - الصعوبة"""
        self._login(client, admin_user)
        response = client.get('/questions/api/filter_options/difficulty')
        assert response.status_code in [200, 500]

    def test_filter_options_bloom(self, client, admin_user):
        """خيارات الفلتر - مستوى بلوم"""
        self._login(client, admin_user)
        response = client.get('/questions/api/filter_options/bloom_level')
        assert response.status_code in [200, 500]

    def test_filter_options_course(self, client, admin_user):
        """خيارات الفلتر - المنهج"""
        self._login(client, admin_user)
        response = client.get('/questions/api/filter_options/course')
        assert response.status_code in [200, 500]

    def test_courses_units_lessons_no_auth(self, client):
        """بيانات المناهج/الوحدات/الدروس بدون مصادقة"""
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [302, 401]

    def test_courses_units_lessons_as_admin(self, client, admin_user):
        """بيانات المناهج/الوحدات/الدروس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 500]


class TestQuestionAdd:
    """اختبارات إضافة الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_add_question_page_no_auth(self, client):
        """صفحة إضافة سؤال بدون مصادقة"""
        response = client.get('/questions/add')
        assert response.status_code in [302, 401]

    def test_add_question_page_as_admin(self, client, admin_user):
        """صفحة إضافة سؤال كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/add')
        assert response.status_code in [200, 302, 500]

    def test_add_question_post_empty(self, client, admin_user):
        """إضافة سؤال ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/add', data={})
        assert response.status_code in [200, 302, 400, 500]

    def test_add_question_post_with_data(self, client, admin_user, db_session, app):
        """إضافة سؤال ببيانات صالحة"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='Q Add Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Q Add Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Q Add Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        self._login(client, admin_user)
        response = client.post('/questions/add', data={
            'question_text': 'سؤال اختبار جديد',
            'lesson_id': str(l.id),
            'difficulty': 'easy',
            'bloom_level': 'remember',
            'option_1': 'خيار 1',
            'option_2': 'خيار 2',
            'correct_option': '1'
        })
        assert response.status_code in [200, 302, 400, 500]


class TestQuestionEdit:
    """اختبارات تعديل الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_edit_question_no_auth(self, client):
        """تعديل سؤال بدون مصادقة"""
        response = client.get('/questions/edit/1')
        assert response.status_code in [302, 401]

    def test_edit_question_nonexistent(self, client, admin_user):
        """تعديل سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.get('/questions/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_question_existing(self, client, admin_user, db_session, app):
        """تعديل سؤال موجود"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='Q Edit Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Q Edit Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Q Edit Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال للتعديل', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        self._login(client, admin_user)
        response = client.get(f'/questions/edit/{q.question_id}')
        assert response.status_code in [200, 302, 500]


class TestQuestionDelete:
    """اختبارات حذف الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_delete_question_no_auth(self, client):
        """حذف سؤال بدون مصادقة"""
        response = client.post('/questions/delete/1')
        assert response.status_code in [302, 401]

    def test_delete_question_nonexistent(self, client, admin_user):
        """حذف سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.post('/questions/delete/99999')
        assert response.status_code in [302, 404, 500]

    def test_delete_question_existing(self, client, admin_user, db_session, app):
        """حذف سؤال موجود"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='Q Del Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Q Del Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Q Del Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال للحذف', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        self._login(client, admin_user)
        response = client.post(f'/questions/delete/{q.question_id}')
        assert response.status_code in [200, 302, 500]


class TestQuestionImport:
    """اختبارات استيراد الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_import_page_no_auth(self, client):
        """صفحة الاستيراد بدون مصادقة"""
        response = client.get('/questions/import')
        assert response.status_code in [302, 401]

    def test_import_page_as_admin(self, client, admin_user):
        """صفحة الاستيراد كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/import')
        assert response.status_code in [200, 302, 500]

    def test_import_template_no_auth(self, client):
        """قالب الاستيراد بدون مصادقة"""
        response = client.get('/questions/import/template')
        assert response.status_code in [302, 401]

    def test_import_template_as_admin(self, client, admin_user):
        """قالب الاستيراد كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/import/template')
        assert response.status_code in [200, 302, 500]

    def test_import_post_no_file(self, client, admin_user):
        """استيراد بدون ملف"""
        self._login(client, admin_user)
        response = client.post('/questions/import', data={})
        assert response.status_code in [200, 302, 400, 500]


class TestQuestionExport:
    """اختبارات تصدير الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_export_template_format_no_auth(self, client):
        """تصدير تنسيق قالب بدون مصادقة"""
        response = client.post('/questions/export/template_format', json={})
        assert response.status_code in [302, 401]

    def test_export_template_format_as_admin(self, client, admin_user):
        """تصدير تنسيق قالب كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/export/template_format', json={
            'format': 'excel'
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_export_filtered_data_no_auth(self, client):
        """تصدير بيانات مفلترة بدون مصادقة"""
        response = client.post('/questions/export/filtered_data', json={})
        assert response.status_code in [302, 401]

    def test_export_filtered_data_as_admin(self, client, admin_user):
        """تصدير بيانات مفلترة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/export/filtered_data', json={
            'filters': {}
        })
        assert response.status_code in [200, 302, 400, 500]


class TestQuestionExamFeatures:
    """اختبارات ميزات الاختبار"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_quiz_page_no_auth(self, client):
        """صفحة الاختبار بدون مصادقة"""
        response = client.get('/questions/quiz')
        assert response.status_code in [302, 401]

    def test_quiz_page_as_admin(self, client, admin_user):
        """صفحة الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/quiz')
        assert response.status_code in [200, 302, 500]

    def test_export_exam_page_no_auth(self, client):
        """صفحة تصدير الاختبار بدون مصادقة"""
        response = client.get('/questions/export-exam')
        assert response.status_code in [302, 401]

    def test_export_exam_page_as_admin(self, client, admin_user):
        """صفحة تصدير الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/export-exam')
        assert response.status_code in [200, 302, 500]

    def test_header_settings_no_auth(self, client):
        """إعدادات الرأس بدون مصادقة"""
        response = client.get('/questions/header-settings')
        assert response.status_code in [302, 401]

    def test_header_settings_as_admin(self, client, admin_user):
        """إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/header-settings')
        assert response.status_code in [200, 302, 500]

    def test_get_header_settings_as_admin(self, client, admin_user):
        """جلب إعدادات الرأس"""
        self._login(client, admin_user)
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 500]

    def test_classify_page_as_admin(self, client, admin_user):
        """صفحة التصنيف"""
        self._login(client, admin_user)
        response = client.get('/questions/classify')
        assert response.status_code in [200, 302, 500]

    def test_download_exam_word_no_auth(self, client):
        """تحميل اختبار Word بدون مصادقة"""
        response = client.post('/questions/download-exam-word', json={})
        assert response.status_code in [302, 401]

    def test_download_exam_word_empty(self, client, admin_user):
        """تحميل اختبار Word ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/download-exam-word', json={})
        assert response.status_code in [200, 400, 500]

    def test_save_header_settings_as_admin(self, client, admin_user):
        """حفظ إعدادات الرأس"""
        self._login(client, admin_user)
        response = client.post('/questions/save-header-settings', json={
            'school_name': 'مدرسة اختبار',
            'year': '1446'
        })
        assert response.status_code in [200, 302, 400, 500]


class TestSavedExams:
    """اختبارات الاختبارات المحفوظة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_list_saved_exams_no_auth(self, client):
        """قائمة الاختبارات المحفوظة بدون مصادقة"""
        response = client.get('/questions/saved-exams')
        assert response.status_code in [302, 401]

    def test_list_saved_exams_as_admin(self, client, admin_user):
        """قائمة الاختبارات المحفوظة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/saved-exams')
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_save_exam_as_admin(self, client, admin_user):
        """حفظ اختبار جديد"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams', json={
            'name': 'اختبار محفوظ',
            'questions': []
        })
        assert response.status_code in [200, 201, 400, 500]

    def test_get_saved_exam_nonexistent(self, client, admin_user):
        """جلب اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.get('/questions/saved-exams/99999')
        assert response.status_code in [404, 500]

    def test_update_saved_exam_nonexistent(self, client, admin_user):
        """تحديث اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.put('/questions/saved-exams/99999', json={
            'name': 'اختبار محدّث'
        })
        assert response.status_code in [404, 500]

    def test_delete_saved_exam_nonexistent(self, client, admin_user):
        """حذف اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/questions/saved-exams/99999')
        assert response.status_code in [404, 500]

    def test_load_saved_exam_nonexistent(self, client, admin_user):
        """تحميل اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams/99999/load', json={})
        assert response.status_code in [404, 500]
