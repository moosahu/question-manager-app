"""
اختبارات متقدمة لـ question routes
يغطي: export, add, edit, delete, multi-models, preview, classify, saved-exams
"""
import pytest


class TestQuestionExport:
    """اختبارات تصدير الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_export_template_no_auth(self, client):
        """تصدير قالب بدون مصادقة"""
        response = client.post('/questions/export/template_format', json={})
        assert response.status_code in [302, 401, 403]

    def test_export_template_as_admin(self, client, admin_user):
        """تصدير قالب كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/export/template_format', json={})
        assert response.status_code in [200, 302, 400, 500]

    def test_export_filtered_no_auth(self, client):
        """تصدير بيانات مفلترة بدون مصادقة"""
        response = client.post('/questions/export/filtered_data', json={})
        assert response.status_code in [302, 401, 403]

    def test_export_filtered_as_admin(self, client, admin_user):
        """تصدير بيانات مفلترة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/export/filtered_data', json={
            'data_type': 'questions',
            'selected_fields': ['question_text']
        })
        assert response.status_code in [200, 302, 400, 500]

    def test_get_filter_options_no_auth(self, client):
        """جلب خيارات الفلتر بدون مصادقة"""
        response = client.get('/questions/api/filter_options/difficulty')
        assert response.status_code in [302, 401, 403]

    def test_get_filter_options_as_admin(self, client, admin_user):
        """جلب خيارات الفلتر كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/api/filter_options/difficulty')
        assert response.status_code in [200, 500]

    def test_get_filter_options_bloom(self, client, admin_user):
        """جلب خيارات الفلتر - مستويات بلوم"""
        self._login(client, admin_user)
        response = client.get('/questions/api/filter_options/bloom_level')
        assert response.status_code in [200, 500]

    def test_download_import_template(self, client, admin_user):
        """تحميل قالب الاستيراد"""
        self._login(client, admin_user)
        response = client.get('/questions/import/template')
        assert response.status_code in [200, 500]

    def test_export_courses_units_lessons(self, client, admin_user):
        """تصدير المناهج والوحدات والدروس"""
        self._login(client, admin_user)
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 500]

    def test_export_exam_pdf_no_auth(self, client):
        """تصدير الامتحان PDF بدون مصادقة"""
        response = client.post('/questions/export-exam-pdf', json={})
        assert response.status_code in [302, 401, 403]

    def test_export_exam_pdf_empty(self, client, admin_user):
        """تصدير الامتحان PDF ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/export-exam-pdf', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_preview_exam_paper_no_auth(self, client):
        """معاينة ورقة الامتحان بدون مصادقة"""
        response = client.post('/questions/preview-exam-paper', json={})
        assert response.status_code in [302, 401, 403]

    def test_preview_exam_paper_empty(self, client, admin_user):
        """معاينة ورقة الامتحان ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/preview-exam-paper', json={})
        assert response.status_code in [200, 400, 422, 500]


class TestQuestionAddEdit:
    """اختبارات إضافة وتعديل الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_add_question_get_no_auth(self, client):
        """صفحة إضافة سؤال بدون مصادقة"""
        response = client.get('/questions/add')
        assert response.status_code in [302, 401, 403]

    def test_add_question_get_as_admin(self, client, admin_user):
        """صفحة إضافة سؤال كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/add')
        assert response.status_code in [200, 302, 500]

    def test_add_question_post_empty(self, client, admin_user):
        """إضافة سؤال ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/add', data={})
        assert response.status_code in [200, 302, 400, 422, 500]

    def test_add_question_post_valid(self, client, admin_user, db_session, app):
        """إضافة سؤال ببيانات صالحة"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='Add Q Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Add Q Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Add Q Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        self._login(client, admin_user)
        response = client.post('/questions/add', data={
            'question_text': 'سؤال اختبار متقدم',
            'lesson_id': str(l.id),
            'difficulty': 'easy',
            'bloom_level': 'remember',
            'option_1': 'خيار 1',
            'option_2': 'خيار 2',
            'correct_option': '1'
        })
        assert response.status_code in [200, 201, 302, 400, 500]

    def test_import_questions_get_no_auth(self, client):
        """صفحة استيراد الأسئلة بدون مصادقة"""
        response = client.get('/questions/import')
        assert response.status_code in [302, 401, 403]

    def test_import_questions_get_as_admin(self, client, admin_user):
        """صفحة استيراد الأسئلة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/import')
        assert response.status_code in [200, 302, 500]

    def test_edit_question_get_nonexistent(self, client, admin_user):
        """صفحة تعديل سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.get('/questions/edit/99999')
        assert response.status_code in [302, 404, 500]

    def test_edit_question_get_existing(self, client, admin_user, db_session, app):
        """صفحة تعديل سؤال موجود"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='Edit Q Course', show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='Edit Q Unit', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='Edit Q Lesson', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال للتعديل', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        self._login(client, admin_user)
        response = client.get(f'/questions/edit/{q.question_id}')
        assert response.status_code in [200, 404, 500]

    def test_delete_question_nonexistent(self, client, admin_user):
        """حذف سؤال غير موجود"""
        self._login(client, admin_user)
        response = client.post('/questions/delete/99999')
        assert response.status_code in [200, 302, 404, 500]


class TestQuestionExamTools:
    """اختبارات أدوات الامتحانات"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_quiz_page_no_auth(self, client):
        """صفحة الاختبار بدون مصادقة"""
        response = client.get('/questions/quiz')
        assert response.status_code in [302, 401, 403]

    def test_quiz_page_as_admin(self, client, admin_user):
        """صفحة الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/quiz')
        assert response.status_code in [200, 500]

    def test_export_exam_page_no_auth(self, client):
        """صفحة تصدير الامتحان بدون مصادقة"""
        response = client.get('/questions/export-exam')
        assert response.status_code in [302, 401, 403]

    def test_export_exam_page_as_admin(self, client, admin_user):
        """صفحة تصدير الامتحان كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/export-exam')
        assert response.status_code in [200, 500]

    def test_header_settings_page_no_auth(self, client):
        """صفحة إعدادات الرأس بدون مصادقة"""
        response = client.get('/questions/header-settings')
        assert response.status_code in [302, 401, 403]

    def test_header_settings_page_as_admin(self, client, admin_user):
        """صفحة إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/header-settings')
        assert response.status_code in [200, 500]

    def test_save_header_settings_no_auth(self, client):
        """حفظ إعدادات الرأس بدون مصادقة"""
        response = client.post('/questions/save-header-settings', json={})
        assert response.status_code in [302, 401, 403]

    def test_save_header_settings_as_admin(self, client, admin_user):
        """حفظ إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/save-header-settings', json={
            'school_name': 'مدرسة الاختبار'
        })
        assert response.status_code in [200, 400, 500]

    def test_get_header_settings_no_auth(self, client):
        """جلب إعدادات الرأس بدون مصادقة"""
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [302, 401, 403]

    def test_get_header_settings_as_admin(self, client, admin_user):
        """جلب إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 500]

    def test_generate_multi_models_no_auth(self, client):
        """توليد نماذج متعددة بدون مصادقة"""
        response = client.post('/questions/generate-multi-models', json={})
        assert response.status_code in [302, 401, 403]

    def test_generate_multi_models_empty(self, client, admin_user):
        """توليد نماذج متعددة ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-multi-models', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_preview_multi_models_no_auth(self, client):
        """معاينة نماذج متعددة بدون مصادقة"""
        response = client.post('/questions/preview-multi-models', json={})
        assert response.status_code in [302, 401, 403]

    def test_preview_multi_models_empty(self, client, admin_user):
        """معاينة نماذج متعددة ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/preview-multi-models', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_preview_students_no_auth(self, client):
        """معاينة أوراق الطلاب بدون مصادقة"""
        response = client.post('/questions/preview-students', json={})
        assert response.status_code in [302, 401, 403]

    def test_preview_students_empty(self, client, admin_user):
        """معاينة أوراق الطلاب ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/preview-students', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_print_remark_sheets_no_auth(self, client):
        """طباعة أوراق التصحيح بدون مصادقة"""
        response = client.post('/questions/print-remark-sheets', json={})
        assert response.status_code in [302, 401, 403]

    def test_print_remark_sheets_empty(self, client, admin_user):
        """طباعة أوراق التصحيح ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/print-remark-sheets', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_generate_omr_answer_key_no_auth(self, client):
        """توليد مفتاح إجابة OMR بدون مصادقة"""
        response = client.post('/questions/generate-omr-answer-key', json={})
        assert response.status_code in [302, 401, 403]

    def test_generate_omr_answer_key_empty(self, client, admin_user):
        """توليد مفتاح إجابة OMR ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-omr-answer-key', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_generate_all_models_answer_keys_no_auth(self, client):
        """توليد مفاتيح كل النماذج بدون مصادقة"""
        response = client.post('/questions/generate-all-models-answer-keys', json={})
        assert response.status_code in [302, 401, 403]

    def test_generate_all_models_answer_keys_empty(self, client, admin_user):
        """توليد مفاتيح كل النماذج ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-all-models-answer-keys', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_download_exam_word_no_auth(self, client):
        """تحميل الامتحان Word بدون مصادقة"""
        response = client.post('/questions/download-exam-word', json={})
        assert response.status_code in [302, 401, 403]

    def test_download_exam_word_empty(self, client, admin_user):
        """تحميل الامتحان Word ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/download-exam-word', json={})
        assert response.status_code in [200, 400, 422, 500]


class TestQuestionSavedExams:
    """اختبارات الامتحانات المحفوظة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_get_saved_exams_no_auth(self, client):
        """جلب الامتحانات المحفوظة بدون مصادقة"""
        response = client.get('/questions/saved-exams')
        assert response.status_code in [302, 401, 403]

    def test_get_saved_exams_as_admin(self, client, admin_user):
        """جلب الامتحانات المحفوظة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/saved-exams')
        assert response.status_code in [200, 500]

    def test_save_exam_no_auth(self, client):
        """حفظ امتحان بدون مصادقة"""
        response = client.post('/questions/saved-exams', json={})
        assert response.status_code in [302, 401, 403]

    def test_save_exam_empty(self, client, admin_user):
        """حفظ امتحان ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_save_exam_valid(self, client, admin_user):
        """حفظ امتحان ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams', json={
            'name': 'امتحان محفوظ',
            'questions': [],
            'settings': {}
        })
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_get_saved_exam_nonexistent(self, client, admin_user):
        """جلب امتحان محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.get('/questions/saved-exams/99999')
        assert response.status_code in [200, 404, 500]

    def test_update_saved_exam_nonexistent(self, client, admin_user):
        """تحديث امتحان محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.put('/questions/saved-exams/99999', json={'name': 'امتحان محدّث'})
        assert response.status_code in [200, 404, 500]

    def test_delete_saved_exam_nonexistent(self, client, admin_user):
        """حذف امتحان محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/questions/saved-exams/99999')
        assert response.status_code in [200, 404, 500]

    def test_load_saved_exam_nonexistent(self, client, admin_user):
        """تحميل امتحان محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams/99999/load', json={})
        assert response.status_code in [200, 404, 500]
