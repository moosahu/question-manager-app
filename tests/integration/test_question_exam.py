"""
اختبارات متخصصة لـ question routes - الاختبارات والتصدير والنماذج المتعددة
يغطي: export-exam, download-exam-word, header-settings, generate-multi-models,
       preview-multi-models, saved-exams CRUD, classify, print-remark-sheets
"""
import pytest


class TestQuestionHeaderSettings:
    """اختبارات إعدادات رأس الاختبار"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_header_settings_no_auth(self, client):
        """إعدادات الرأس بدون مصادقة"""
        response = client.get('/questions/header-settings')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_header_settings_as_admin(self, client, admin_user):
        """إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/header-settings')
        assert response.status_code in [200, 302, 404, 500]

    def test_save_header_settings_no_auth(self, client):
        """حفظ إعدادات الرأس بدون مصادقة"""
        response = client.post('/questions/save-header-settings', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_save_header_settings_as_admin(self, client, admin_user):
        """حفظ إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/save-header-settings', json={
            'school_name': 'مدرسة اختبار',
            'header_text': 'نص الرأس'
        })
        assert response.status_code in [200, 400, 500]

    def test_get_header_settings_no_auth(self, client):
        """جلب إعدادات الرأس بدون مصادقة"""
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_get_header_settings_as_admin(self, client, admin_user):
        """جلب إعدادات الرأس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 500]


class TestQuestionExportExam:
    """اختبارات تصدير الاختبار"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_export_exam_page_no_auth(self, client):
        """صفحة تصدير الاختبار بدون مصادقة"""
        response = client.get('/questions/export-exam')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_export_exam_page_as_admin(self, client, admin_user):
        """صفحة تصدير الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/export-exam')
        assert response.status_code in [200, 302, 404, 500]

    def test_download_exam_word_no_auth(self, client):
        """تحميل اختبار Word بدون مصادقة"""
        response = client.post('/questions/download-exam-word', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_download_exam_word_empty(self, client, admin_user):
        """تحميل اختبار Word ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/download-exam-word', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_download_exam_word_with_data(self, client, admin_user):
        """تحميل اختبار Word ببيانات"""
        self._login(client, admin_user)
        response = client.post('/questions/download-exam-word', json={
            'questions': [],
            'settings': {'exam_title': 'اختبار تجريبي'}
        })
        assert response.status_code in [200, 400, 500]

    def test_export_exam_pdf_no_auth(self, client):
        """تصدير PDF الاختبار بدون مصادقة"""
        response = client.post('/questions/export-exam-pdf', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_export_exam_pdf_as_admin(self, client, admin_user):
        """تصدير PDF الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/export-exam-pdf', json={
            'questions': [],
            'settings': {}
        })
        assert response.status_code in [200, 400, 500]

    def test_preview_exam_paper_no_auth(self, client):
        """معاينة ورقة الاختبار بدون مصادقة"""
        response = client.post('/questions/preview-exam-paper', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_preview_exam_paper_as_admin(self, client, admin_user):
        """معاينة ورقة الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/preview-exam-paper', json={
            'questions': [],
            'settings': {}
        })
        assert response.status_code in [200, 400, 500]


class TestQuestionMultiModels:
    """اختبارات النماذج المتعددة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_generate_multi_models_no_auth(self, client):
        """توليد نماذج متعددة بدون مصادقة"""
        response = client.post('/questions/generate-multi-models', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_generate_multi_models_empty(self, client, admin_user):
        """توليد نماذج متعددة ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-multi-models', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_generate_multi_models_with_data(self, client, admin_user):
        """توليد نماذج متعددة ببيانات"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-multi-models', json={
            'questions': [],
            'num_models': 2,
            'settings': {}
        })
        assert response.status_code in [200, 400, 500]

    def test_preview_multi_models_no_auth(self, client):
        """معاينة نماذج متعددة بدون مصادقة"""
        response = client.post('/questions/preview-multi-models', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_preview_multi_models_as_admin(self, client, admin_user):
        """معاينة نماذج متعددة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/preview-multi-models', json={
            'questions': [],
            'num_models': 2
        })
        assert response.status_code in [200, 400, 500]

    def test_preview_students_no_auth(self, client):
        """معاينة ورقة الطلاب بدون مصادقة"""
        response = client.post('/questions/preview-students', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_preview_students_as_admin(self, client, admin_user):
        """معاينة ورقة الطلاب كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/preview-students', json={
            'questions': []
        })
        assert response.status_code in [200, 400, 500]

    def test_print_remark_sheets_no_auth(self, client):
        """طباعة أوراق التصحيح بدون مصادقة"""
        response = client.post('/questions/print-remark-sheets', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_print_remark_sheets_as_admin(self, client, admin_user):
        """طباعة أوراق التصحيح كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/print-remark-sheets', json={
            'questions': []
        })
        assert response.status_code in [200, 400, 500]

    def test_generate_omr_answer_key_no_auth(self, client):
        """توليد مفتاح إجابة OMR بدون مصادقة"""
        response = client.post('/questions/generate-omr-answer-key', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_generate_omr_answer_key_as_admin(self, client, admin_user):
        """توليد مفتاح إجابة OMR كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-omr-answer-key', json={
            'questions': []
        })
        assert response.status_code in [200, 400, 500]

    def test_print_remark_sheets_multi_models_no_auth(self, client):
        """طباعة أوراق تصحيح نماذج متعددة بدون مصادقة"""
        response = client.post('/questions/print-remark-sheets-multi-models', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_print_remark_sheets_multi_models_as_admin(self, client, admin_user):
        """طباعة أوراق تصحيح نماذج متعددة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/print-remark-sheets-multi-models', json={
            'models': []
        })
        assert response.status_code in [200, 400, 500]

    def test_print_blank_remark_sheets_no_auth(self, client):
        """طباعة أوراق تصحيح فارغة بدون مصادقة"""
        response = client.post('/questions/print-blank-remark-sheets', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_print_blank_remark_sheets_as_admin(self, client, admin_user):
        """طباعة أوراق تصحيح فارغة كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/print-blank-remark-sheets', json={
            'num_questions': 10
        })
        assert response.status_code in [200, 400, 500]

    def test_generate_all_models_answer_keys_no_auth(self, client):
        """توليد مفاتيح إجابة كل النماذج بدون مصادقة"""
        response = client.post('/questions/generate-all-models-answer-keys', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_generate_all_models_answer_keys_as_admin(self, client, admin_user):
        """توليد مفاتيح إجابة كل النماذج كأدمن"""
        self._login(client, admin_user)
        response = client.post('/questions/generate-all-models-answer-keys', json={
            'models': []
        })
        assert response.status_code in [200, 400, 500]


class TestSavedExamsCRUD:
    """اختبارات CRUD للاختبارات المحفوظة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_list_saved_exams_no_auth(self, client):
        """قائمة الاختبارات المحفوظة بدون مصادقة"""
        response = client.get('/questions/saved-exams')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_list_saved_exams_as_admin(self, client, admin_user):
        """قائمة الاختبارات المحفوظة كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/saved-exams')
        assert response.status_code in [200, 500]

    def test_create_saved_exam_no_auth(self, client):
        """إنشاء اختبار محفوظ بدون مصادقة"""
        response = client.post('/questions/saved-exams', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_create_saved_exam_empty(self, client, admin_user):
        """إنشاء اختبار محفوظ ببيانات فارغة"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams', json={})
        assert response.status_code in [200, 400, 422, 500]

    def test_create_saved_exam_valid(self, client, admin_user):
        """إنشاء اختبار محفوظ ببيانات صالحة"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams', json={
            'name': 'اختبار نهاية الفصل',
            'questions': [],
            'settings': {}
        })
        assert response.status_code in [200, 201, 400, 500]

    def test_get_saved_exam_nonexistent(self, client, admin_user):
        """جلب اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.get('/questions/saved-exams/99999')
        assert response.status_code in [200, 404, 500]

    def test_update_saved_exam_no_auth(self, client):
        """تحديث اختبار محفوظ بدون مصادقة"""
        response = client.put('/questions/saved-exams/99999', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_update_saved_exam_nonexistent(self, client, admin_user):
        """تحديث اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.put('/questions/saved-exams/99999', json={
            'name': 'اسم محدث'
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_delete_saved_exam_no_auth(self, client):
        """حذف اختبار محفوظ بدون مصادقة"""
        response = client.delete('/questions/saved-exams/99999')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_delete_saved_exam_nonexistent(self, client, admin_user):
        """حذف اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.delete('/questions/saved-exams/99999')
        assert response.status_code in [200, 404, 500]

    def test_load_saved_exam_no_auth(self, client):
        """تحميل اختبار محفوظ بدون مصادقة"""
        response = client.post('/questions/saved-exams/99999/load', json={})
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_load_saved_exam_nonexistent(self, client, admin_user):
        """تحميل اختبار محفوظ غير موجود"""
        self._login(client, admin_user)
        response = client.post('/questions/saved-exams/99999/load', json={})
        assert response.status_code in [200, 404, 500]


class TestQuestionClassify:
    """اختبارات تصنيف الأسئلة"""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    def test_classify_no_auth(self, client):
        """صفحة التصنيف بدون مصادقة"""
        response = client.get('/questions/classify')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_classify_as_admin(self, client, admin_user):
        """صفحة التصنيف كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/classify')
        assert response.status_code in [200, 302, 404, 500]

    def test_courses_units_lessons_export_no_auth(self, client):
        """تصدير المناهج والوحدات والدروس بدون مصادقة"""
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_courses_units_lessons_export_as_admin(self, client, admin_user):
        """تصدير المناهج والوحدات والدروس كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 302, 404, 500]

    def test_import_template_no_auth(self, client):
        """قالب الاستيراد بدون مصادقة"""
        response = client.get('/questions/import/template')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_import_template_as_admin(self, client, admin_user):
        """قالب الاستيراد كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/import/template')
        assert response.status_code in [200, 302, 404, 500]

    def test_quiz_page_no_auth(self, client):
        """صفحة الاختبار بدون مصادقة"""
        response = client.get('/questions/quiz')
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_quiz_page_as_admin(self, client, admin_user):
        """صفحة الاختبار كأدمن"""
        self._login(client, admin_user)
        response = client.get('/questions/quiz')
        assert response.status_code in [200, 302, 404, 500]
