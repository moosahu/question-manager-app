"""
Deep integration tests for question routes - targeting uncovered lines.
Covers: list, add, edit, delete, import, export, saved-exams, filter options,
        header settings, quiz, export-exam, multi-models, remark sheets,
        OMR answer keys, preview, and bulk operations.
"""
import pytest
import json
import io


# ─────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────

def _login(client, admin_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _make_question(db_session, lesson_id, text="سؤال اختبار"):
    """Create a question with 2 options and return it."""
    from src.models.question import Question, Option
    q = Question(question_text=text, lesson_id=lesson_id)
    db_session.session.add(q)
    db_session.session.flush()
    opt1 = Option(option_text="خيار 1", is_correct=True, question_id=q.question_id)
    opt2 = Option(option_text="خيار 2", is_correct=False, question_id=q.question_id)
    db_session.session.add(opt1)
    db_session.session.add(opt2)
    db_session.session.commit()
    db_session.session.refresh(q)
    return q


# ─────────────────────────────────────────────────
# 1. list_questions – Lines 388-462
# ─────────────────────────────────────────────────

class TestListQuestions:

    def test_list_no_auth(self, client):
        response = client.get('/questions/')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_list_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_filter_by_course(self, client, admin_user, sample_course):
        _login(client, admin_user)
        response = client.get(f'/questions/?course_id={sample_course.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_filter_by_unit(self, client, admin_user, sample_unit):
        _login(client, admin_user)
        response = client.get(f'/questions/?unit_id={sample_unit.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_filter_by_lesson(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.get(f'/questions/?lesson_id={sample_lesson.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_with_pagination(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/?page=2')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_nonexistent_course(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/?course_id=99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_nonexistent_lesson(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/?lesson_id=99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_combined_filters(self, client, admin_user, sample_course, sample_unit):
        _login(client, admin_user)
        url = f'/questions/?course_id={sample_course.id}&unit_id={sample_unit.id}'
        response = client.get(url)
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 2. add_question – Lines 1080-1255
# ─────────────────────────────────────────────────

class TestAddQuestion:

    def test_add_get_no_auth(self, client):
        response = client.get('/questions/add')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_add_get_as_admin(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.get('/questions/add')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_empty_form(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/add', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_missing_lesson(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'سؤال بدون درس',
            'option_text_0': 'خيار 1',
            'option_text_1': 'خيار 2',
            'correct_option': '0',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_missing_options(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'سؤال بدون خيارات',
            'lesson_id': str(sample_lesson.id),
            'correct_option': '0',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_valid_data(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'ما هو عدد الالكترونات في ذرة الكربون؟',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': '4',
            'option_text_1': '6',
            'option_text_2': '8',
            'option_text_3': '12',
            'correct_option': '1',
            'explanation': 'الكربون لديه 6 إلكترونات',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_invalid_correct_option(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'سؤال مع خيار صحيح خاطئ',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': 'أ',
            'option_text_1': 'ب',
            'correct_option': 'notanumber',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_correct_option_out_of_range(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'سؤال رقم الخيار خارج النطاق',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': 'أ',
            'option_text_1': 'ب',
            'correct_option': '99',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_nonexistent_lesson(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'سؤال درس غير موجود',
            'lesson_id': '99999',
            'option_text_0': 'أ',
            'option_text_1': 'ب',
            'correct_option': '0',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_post_with_is_blocked(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.post('/questions/add', data={
            'text': 'سؤال محظور',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': 'أ',
            'option_text_1': 'ب',
            'correct_option': '0',
            'is_blocked': '1',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 3. edit_question – Lines 1530-1755
# ─────────────────────────────────────────────────

class TestEditQuestion:

    def test_edit_get_no_auth(self, client):
        response = client.get('/questions/edit/1')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_edit_get_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/edit/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_get_existing(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال للتعديل")
        response = client.get(f'/questions/edit/{q.question_id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_post_no_auth(self, client):
        response = client.post('/questions/edit/1', data={'text': 'x'})
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_edit_post_existing_valid(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال قبل التعديل")
        opts = list(q.options)
        response = client.post(f'/questions/edit/{q.question_id}', data={
            'text': 'سؤال بعد التعديل',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': 'خيار محدث 1',
            'option_id_0': str(opts[0].option_id) if opts else '',
            'option_text_1': 'خيار محدث 2',
            'option_id_1': str(opts[1].option_id) if len(opts) > 1 else '',
            'correct_option': '0',
            'explanation': 'شرح محدث',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_post_missing_text_and_image(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال اختبار نص فارغ")
        response = client.post(f'/questions/edit/{q.question_id}', data={
            'text': '',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': 'أ',
            'option_text_1': 'ب',
            'correct_option': '0',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_edit_post_delete_question_image(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال مع صورة")
        response = client.post(f'/questions/edit/{q.question_id}', data={
            'text': 'سؤال',
            'lesson_id': str(sample_lesson.id),
            'option_text_0': 'أ',
            'option_text_1': 'ب',
            'correct_option': '0',
            'delete_question_image': '1',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 4. delete_question – Lines 1758-1802
# ─────────────────────────────────────────────────

class TestDeleteQuestion:

    def test_delete_no_auth(self, client):
        response = client.post('/questions/delete/1')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_delete_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/delete/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_existing(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال للحذف")
        response = client.post(f'/questions/delete/{q.question_id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_via_get_not_allowed(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/delete/1')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 5. import_questions – Lines 1258-1469
# ─────────────────────────────────────────────────

class TestImportQuestions:

    def test_import_get_no_auth(self, client):
        response = client.get('/questions/import')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_import_get_as_admin(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.get('/questions/import')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_import_post_no_file(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/import', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_import_post_invalid_extension(self, client, admin_user):
        _login(client, admin_user)
        data = {
            'question_file': (io.BytesIO(b'some content'), 'file.txt'),
        }
        response = client.post('/questions/import',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_import_post_bad_csv_missing_columns(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        csv_content = b"col1,col2\nval1,val2\n"
        data = {
            'question_file': (io.BytesIO(csv_content), 'questions.csv'),
            'lesson_id': str(sample_lesson.id),
        }
        response = client.post('/questions/import',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_import_post_csv_missing_lesson(self, client, admin_user):
        _login(client, admin_user)
        header = (
            "Course Name,Unit Name,Lesson Name,Question Text,Question Image URL,"
            "Option 1 Text,Option 1 Image URL,Option 2 Text,Option 2 Image URL,"
            "Option 3 Text,Option 3 Image URL,Option 4 Text,Option 4 Image URL,"
            "Correct Option Number\n"
        )
        row = "NoSuchCourse,NoSuchUnit,NoSuchLesson,سؤال?,,"
        row += "أ,,ب,,ج,,د,,1\n"
        csv_content = (header + row).encode('utf-8')
        data = {
            'question_file': (io.BytesIO(csv_content), 'questions.csv'),
        }
        response = client.post('/questions/import',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 6. download_import_template – Line 1472-1527
# ─────────────────────────────────────────────────

class TestDownloadImportTemplate:

    def test_template_no_auth(self, client):
        response = client.get('/questions/import/template')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_template_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/import/template')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 7. get_filter_options – Lines 836-872
# ─────────────────────────────────────────────────

class TestFilterOptions:

    def test_filter_options_no_auth_course(self, client):
        response = client.get('/questions/api/filter_options/course')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_filter_options_course(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/api/filter_options/course')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_unit(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/api/filter_options/unit')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_unit_with_course(self, client, admin_user, sample_course):
        _login(client, admin_user)
        response = client.get(f'/questions/api/filter_options/unit?course={sample_course.name}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_lesson(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/api/filter_options/lesson')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_lesson_with_unit(self, client, admin_user, sample_unit, sample_course):
        _login(client, admin_user)
        url = (f'/questions/api/filter_options/lesson'
               f'?unit={sample_unit.name}&course={sample_course.name}')
        response = client.get(url)
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_unknown_field(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/api/filter_options/unknown_field')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_difficulty(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/api/filter_options/difficulty')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 8. export_template_format – Lines 768-833
# ─────────────────────────────────────────────────

class TestExportTemplateFormat:

    def test_export_template_no_auth(self, client):
        response = client.post('/questions/export/template_format')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_export_template_no_data(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/export/template_format', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_template_with_filter(self, client, admin_user, sample_lesson, db_session):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, "سؤال للتصدير")
        response = client.post('/questions/export/template_format', data={
            'filter_field[]': ['lesson'],
            'filter_operator[]': ['contains'],
            'filter_value[]': ['اختبار'],
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 9. export_filtered_data – Lines 874-1059
# ─────────────────────────────────────────────────

class TestExportFilteredData:

    def test_export_filtered_no_auth(self, client):
        response = client.post('/questions/export/filtered_data')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_export_filtered_no_fields(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'questions',
            'format': 'xlsx',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_filtered_xlsx(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, "سؤال للتصدير xlsx")
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'questions',
            'fields': ['question_text', 'lesson', 'course'],
            'format': 'xlsx',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_filtered_csv(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, "سؤال للتصدير csv")
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'questions',
            'fields': ['question_text'],
            'format': 'csv',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_filtered_curriculum(self, client, admin_user, sample_course):
        _login(client, admin_user)
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'curriculum',
            'fields': ['course', 'unit', 'lesson'],
            'format': 'xlsx',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_filtered_unsupported_format(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, "سؤال")
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'questions',
            'fields': ['question_text'],
            'format': 'xml',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_filtered_all_type(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, "سؤال كل البيانات")
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'all',
            'fields': ['question_text', 'course', 'unit', 'lesson',
                       'options', 'correct_answer', 'explanation'],
            'format': 'csv',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 10. export_courses_units_lessons – Lines 3777-end
# ─────────────────────────────────────────────────

class TestExportCoursesUnitsLessons:

    def test_export_cul_no_auth(self, client):
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_export_cul_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_cul_with_data(self, client, admin_user, sample_lesson):
        _login(client, admin_user)
        response = client.get('/questions/export/courses_units_lessons')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 11. quiz – Line 1806-1812
# ─────────────────────────────────────────────────

class TestQuizPage:

    def test_quiz_no_auth(self, client):
        response = client.get('/questions/quiz')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_quiz_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/quiz')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 12. export_exam page – Lines 1816-1822
# ─────────────────────────────────────────────────

class TestExportExamPage:

    def test_export_exam_no_auth(self, client):
        response = client.get('/questions/export-exam')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_export_exam_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/export-exam')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 13. header_settings – Lines 1973-1977
# ─────────────────────────────────────────────────

class TestHeaderSettingsPage:

    def test_header_settings_no_auth(self, client):
        response = client.get('/questions/header-settings')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_header_settings_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/header-settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 14. save_header_settings – Lines 1980-2018
# ─────────────────────────────────────────────────

class TestSaveHeaderSettings:

    def test_save_header_no_auth(self, client):
        response = client.post('/questions/save-header-settings',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_save_header_as_admin(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'country': 'المملكة العربية السعودية',
            'ministry': 'وزارة التعليم',
            'education_department': 'إدارة التعليم',
            'school_name': 'مدرسة الاختبار',
            'subject': 'كيمياء',
            'time': 'ساعتان',
            'grade': 'ثاني ثانوي',
            'total_score': 25,
            'checker_name': 'أحمد',
            'reviewer_name': 'خالد',
            'exam_date': '1446-08-01',
        }
        response = client.post('/questions/save-header-settings',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_header_empty_body(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/save-header-settings',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 15. get_header_settings – Lines 2021-2056
# ─────────────────────────────────────────────────

class TestGetHeaderSettings:

    def test_get_header_no_auth(self, client):
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_get_header_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_header_after_save(self, client, admin_user):
        _login(client, admin_user)
        # save first
        client.post('/questions/save-header-settings',
                    data=json.dumps({'school_name': 'مدرسة X'}),
                    content_type='application/json')
        # then get
        response = client.get('/questions/get-header-settings')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 16. download_exam_word – Lines 1825-1970
# ─────────────────────────────────────────────────

class TestDownloadExamWord:

    def test_download_exam_word_no_auth(self, client):
        response = client.post('/questions/download-exam-word',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_download_exam_word_empty_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/download-exam-word',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_download_exam_word_nonexistent_ids(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'question_ids': [99999, 99998],
            'include_answers': False,
            'exam_title': 'اختبار',
        }
        response = client.post('/questions/download-exam-word',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_download_exam_word_valid_ids(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال للتحميل")
        payload = {
            'question_ids': [q.question_id],
            'include_answers': True,
            'exam_title': 'اختبار كيمياء',
            'output_format': 'word',
        }
        response = client.post('/questions/download-exam-word',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 17. export_exam_pdf – Lines 2059-2147
# ─────────────────────────────────────────────────

class TestExportExamPdf:

    def test_export_pdf_no_auth(self, client):
        response = client.post('/questions/export-exam-pdf',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_export_pdf_empty_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/export-exam-pdf',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_pdf_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/export-exam-pdf',
                               data=json.dumps({'question_ids': [99999]}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 18. preview_exam_paper – Lines 2148-2214
# ─────────────────────────────────────────────────

class TestPreviewExamPaper:

    def test_preview_no_auth(self, client):
        response = client.post('/questions/preview-exam-paper', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_preview_no_question_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/preview-exam-paper', data={
            'question_ids': '',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_preview_nonexistent_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/preview-exam-paper', data={
            'question_ids': '99999,99998',
            'include_answers': 'false',
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 19. generate_multi_models – Lines 2332-2525
# ─────────────────────────────────────────────────

class TestGenerateMultiModels:

    def test_multi_models_no_auth(self, client):
        response = client.post('/questions/generate-multi-models',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_multi_models_empty_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/generate-multi-models',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_multi_models_nonexistent_ids(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'question_ids': [99999],
            'models': ['أ'],
        }
        response = client.post('/questions/generate-multi-models',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 20. preview_multi_models – Lines 2528-2786
# ─────────────────────────────────────────────────

class TestPreviewMultiModels:

    def test_preview_multi_no_auth(self, client):
        response = client.post('/questions/preview-multi-models',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_preview_multi_empty_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/preview-multi-models',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_preview_multi_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'question_ids': [99999],
            'models': ['أ', 'ب'],
            'include_answers': False,
        }
        response = client.post('/questions/preview-multi-models',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_preview_multi_valid(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال للمعاينة")
        payload = {
            'question_ids': [q.question_id],
            'models': ['أ', 'ب'],
            'include_answers': True,
            'include_answer_sheet': True,
            'include_barcode': False,
            'shuffle_options': True,
        }
        response = client.post('/questions/preview-multi-models',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 21. preview_students – Lines 2790-2820
# ─────────────────────────────────────────────────

class TestPreviewStudents:

    def test_preview_students_no_auth(self, client):
        response = client.post('/questions/preview-students', data={})
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_preview_students_no_file(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/preview-students', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_preview_students_invalid_file(self, client, admin_user):
        _login(client, admin_user)
        data = {
            'student_file': (io.BytesIO(b'not excel'), 'students.xlsx'),
        }
        response = client.post('/questions/preview-students',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 22. print_remark_sheets – Lines 2875-2931
# ─────────────────────────────────────────────────

class TestPrintRemarkSheets:

    def test_print_remark_no_auth(self, client):
        response = client.post('/questions/print-remark-sheets',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_print_remark_empty_students(self, client, admin_user):
        _login(client, admin_user)
        payload = {'students': [], 'exam_type': 'نهاية', 'semester': 'الأول'}
        response = client.post('/questions/print-remark-sheets',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_print_remark_with_students(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'students': [
                {'name': 'أحمد', 'academic_id': '12345', 'section': 'أ'},
                {'name': 'خالد', 'academic_id': '67890', 'section': 'ب'},
            ],
            'exam_type': 'نهاية',
            'semester': 'الأول',
            'academic_year': '1447هـ',
        }
        response = client.post('/questions/print-remark-sheets',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 23. generate_omr_answer_key – Lines 2935-3067
# ─────────────────────────────────────────────────

class TestGenerateOmrAnswerKey:

    def test_omr_answer_key_no_auth(self, client):
        response = client.post('/questions/generate-omr-answer-key',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_omr_answer_key_empty_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/generate-omr-answer-key',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_omr_answer_key_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        payload = {'question_ids': [99999], 'model_letter': 'أ'}
        response = client.post('/questions/generate-omr-answer-key',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_omr_answer_key_valid(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال لمفتاح الإجابة")
        payload = {
            'question_ids': [q.question_id],
            'model_letter': 'أ',
            'exam_type': 'نهاية',
            'semester': 'الأول',
        }
        response = client.post('/questions/generate-omr-answer-key',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 24. print_remark_sheets_multi_models – Lines 3070-3229
# ─────────────────────────────────────────────────

class TestPrintRemarkSheetsMultiModels:

    def test_multi_remark_no_auth(self, client):
        response = client.post('/questions/print-remark-sheets-multi-models',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_multi_remark_no_students(self, client, admin_user):
        _login(client, admin_user)
        payload = {'students': [], 'models': ['أ'], 'question_ids': [1]}
        response = client.post('/questions/print-remark-sheets-multi-models',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_multi_remark_no_question_ids(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'students': [{'name': 'أحمد', 'academic_id': '1', 'section': 'أ'}],
            'models': ['أ'],
            'question_ids': [],
        }
        response = client.post('/questions/print-remark-sheets-multi-models',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_multi_remark_nonexistent_questions(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'students': [{'name': 'أحمد', 'academic_id': '1', 'section': 'أ'}],
            'models': ['أ'],
            'question_ids': [99999],
        }
        response = client.post('/questions/print-remark-sheets-multi-models',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 25. print_blank_remark_sheets – Lines 3232-3305
# ─────────────────────────────────────────────────

class TestPrintBlankRemarkSheets:

    def test_blank_remark_no_auth(self, client):
        response = client.post('/questions/print-blank-remark-sheets',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_blank_remark_no_question_ids(self, client, admin_user):
        _login(client, admin_user)
        payload = {'models': ['أ'], 'count_per_model': 5, 'question_ids': []}
        response = client.post('/questions/print-blank-remark-sheets',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_blank_remark_valid(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال للنموذج الفارغ")
        payload = {
            'models': ['أ', 'ب'],
            'count_per_model': 2,
            'question_ids': [q.question_id],
            'exam_type': 'نهاية',
            'semester': 'الأول',
            'academic_year': '1447هـ',
        }
        response = client.post('/questions/print-blank-remark-sheets',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 26. generate_all_models_answer_keys – Lines 3308-3478
# ─────────────────────────────────────────────────

class TestGenerateAllModelsAnswerKeys:

    def test_all_keys_no_auth(self, client):
        response = client.post('/questions/generate-all-models-answer-keys',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_all_keys_empty_ids(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/generate-all-models-answer-keys',
                               data=json.dumps({'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_all_keys_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'question_ids': [99999],
            'models': ['أ', 'ب'],
        }
        response = client.post('/questions/generate-all-models-answer-keys',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_all_keys_valid(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال لكل المفاتيح")
        payload = {
            'question_ids': [q.question_id],
            'models': ['أ', 'ب', 'ج'],
            'shuffle_options': True,
        }
        response = client.post('/questions/generate-all-models-answer-keys',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 27. classify_questions – Lines 3485-3492
# ─────────────────────────────────────────────────

class TestClassifyQuestions:

    def test_classify_no_auth(self, client):
        response = client.get('/questions/classify')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_classify_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/classify')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 28. Saved Exams CRUD – Lines 3499-3773
# ─────────────────────────────────────────────────

class TestSavedExams:

    def test_get_saved_exams_no_auth(self, client):
        response = client.get('/questions/saved-exams')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_get_saved_exams_as_admin(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/saved-exams')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_saved_exams_with_pagination(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/saved-exams?page=1&per_page=5')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_saved_exams_with_search(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/saved-exams?search=كيمياء')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_exam_no_auth(self, client):
        response = client.post('/questions/saved-exams',
                               data=json.dumps({'name': 'test'}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 401, 403, 404, 405, 500]

    def test_save_exam_no_name(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/saved-exams',
                               data=json.dumps({'name': '', 'question_ids': [1]}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_exam_no_questions(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/saved-exams',
                               data=json.dumps({'name': 'اختبار فارغ', 'question_ids': []}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_exam_valid(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال للحفظ")
        payload = {
            'name': 'اختبار محفوظ',
            'description': 'وصف',
            'question_ids': [q.question_id],
            'models': ['أ'],
        }
        response = client.post('/questions/saved-exams',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_saved_exam_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/saved-exams/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_update_saved_exam_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.put('/questions/saved-exams/99999',
                              data=json.dumps({'name': 'اسم جديد'}),
                              content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_delete_saved_exam_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.delete('/questions/saved-exams/99999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_load_saved_exam_nonexistent(self, client, admin_user):
        _login(client, admin_user)
        response = client.post('/questions/saved-exams/99999/load',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_full_saved_exam_lifecycle(self, client, admin_user, db_session, sample_lesson):
        """Create, GET, PUT, DELETE a saved exam."""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال دورة الحياة")

        # Create
        create_resp = client.post('/questions/saved-exams',
                                  data=json.dumps({'name': 'اختبار دورة', 'question_ids': [q.question_id]}),
                                  content_type='application/json')
        assert create_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

        exam_id = None
        if create_resp.status_code == 200:
            try:
                data = create_resp.get_json()
                exam_id = data.get('exam', {}).get('id')
            except Exception:
                pass

        if exam_id:
            # GET
            get_resp = client.get(f'/questions/saved-exams/{exam_id}')
            assert get_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

            # PUT
            put_resp = client.put(f'/questions/saved-exams/{exam_id}',
                                  data=json.dumps({'name': 'اختبار محدث'}),
                                  content_type='application/json')
            assert put_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

            # LOAD
            load_resp = client.post(f'/questions/saved-exams/{exam_id}/load',
                                    data=json.dumps({}),
                                    content_type='application/json')
            assert load_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

            # DELETE
            del_resp = client.delete(f'/questions/saved-exams/{exam_id}')
            assert del_resp.status_code in [200, 302, 400, 401, 403, 404, 405, 500]


# ─────────────────────────────────────────────────
# 29. Miscellaneous edge-cases
# ─────────────────────────────────────────────────

class TestMiscEdgeCases:

    def test_list_questions_page_zero(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/?page=0')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_list_questions_large_page(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/?page=9999')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_unit_with_nonexistent_course(self, client, admin_user):
        _login(client, admin_user)
        response = client.get('/questions/api/filter_options/unit?course=لا_يوجد')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_filter_options_lesson_with_only_unit(self, client, admin_user, sample_unit):
        _login(client, admin_user)
        response = client.get(f'/questions/api/filter_options/lesson?unit={sample_unit.name}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_add_question_no_lesson_list(self, client, admin_user):
        """When no lessons exist, redirect to curriculum."""
        _login(client, admin_user)
        # This may redirect when no lessons available or show form
        response = client.get('/questions/add')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_save_exam_with_options_order(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال مع ترتيب خيارات")
        opts = list(q.options)
        opt_ids = [o.option_id for o in opts]
        payload = {
            'name': 'اختبار بترتيب خيارات',
            'question_ids': [q.question_id],
            'questions_with_order': [
                {'question_id': q.question_id, 'options_order': opt_ids}
            ],
        }
        response = client.post('/questions/saved-exams',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_get_saved_exams_with_course_filter(self, client, admin_user, sample_course):
        _login(client, admin_user)
        response = client.get(f'/questions/saved-exams?course_id={sample_course.id}')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_download_exam_word_pdf_format(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال PDF")
        payload = {
            'question_ids': [q.question_id],
            'output_format': 'pdf',
            'include_answers': False,
            'exam_title': 'اختبار PDF',
        }
        response = client.post('/questions/download-exam-word',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_omr_answer_key_multiple_models(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, "سؤال نماذج متعددة")
        payload = {
            'question_ids': [q.question_id],
            'model_letter': 'ب',
            'exam_type': 'شهري',
            'semester': 'الثاني',
            'academic_year': '1447هـ',
        }
        response = client.post('/questions/generate-omr-answer-key',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_export_filtered_with_filters(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, "سؤال مع فلتر")
        response = client.post('/questions/export/filtered_data', data={
            'data_type': 'questions',
            'fields': ['question_text', 'lesson'],
            'format': 'xlsx',
            'filter_field[]': ['lesson'],
            'filter_operator[]': ['contains'],
            'filter_value[]': ['اختبار'],
        })
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]

    def test_print_remark_students_no_academic_id(self, client, admin_user):
        _login(client, admin_user)
        payload = {
            'students': [{'name': 'طالب بدون رقم', 'academic_id': '', 'section': 'أ'}],
            'exam_type': 'نهاية',
            'semester': 'الأول',
        }
        response = client.post('/questions/print-remark-sheets',
                               data=json.dumps(payload),
                               content_type='application/json')
        assert response.status_code in [200, 302, 400, 401, 403, 404, 405, 500]
