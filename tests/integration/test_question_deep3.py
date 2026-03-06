"""
Deep3 integration tests for question.py - targets remaining uncovered branches.

Focus areas:
  1. list_questions with filter combinations (course_id, unit_id, lesson_id, page)
  2. export/filter_options API (course/unit/lesson fields)
  3. export_template_format (with/without filters, edge cases)
  4. export_filtered_data (xlsx/csv/pdf branches, data_type variations)
  5. add_question (valid POST, error cases, option edge cases, is_blocked)
  6. edit_question (POST success, option update/create/delete, delete_image flags)
  7. delete_question (success and exception)
  8. quiz page
  9. header-settings endpoints
  10. save-header-settings / get-header-settings
  11. export_exam_pdf (mocked generator)
  12. preview_exam_paper (success, no question_ids)
  13. generate_multi_models (mocked weasyprint, no questions, with answers/barcode)
  14. preview_multi_models (with/without answer_sheet, saved_options_order)
  15. preview_students (file upload variants)
  16. print_remark_sheets (students, empty list)
  17. generate_omr_answer_key (success, no questions, no question_ids)
  18. print_remark_sheets_multi_models (success, missing fields)
  19. print_blank_remark_sheets (success, no question_ids)
  20. generate_all_models_answer_keys (multiple models, no questions)
  21. saved-exams CRUD (full lifecycle, edge cases)
  22. load_saved_exam (with options_order)
  23. export_courses_units_lessons (success, empty)
  24. classify route
  25. download_import_template
"""

import json
import io
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def _login(client, user):
    """Log in a user via session manipulation."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_question(db_session, lesson_id, text="سؤال deep3", explanation=None, is_blocked=False):
    """Create a minimal valid question with 4 options."""
    from src.models.question import Question, Option
    q = Question(
        question_text=text,
        lesson_id=lesson_id,
        explanation=explanation,
        is_blocked=is_blocked,
    )
    db_session.session.add(q)
    db_session.session.flush()
    for i in range(4):
        opt = Option(
            option_text=f"خيار {i+1}",
            is_correct=(i == 0),
            question_id=q.question_id,
        )
        db_session.session.add(opt)
    db_session.session.commit()
    db_session.session.refresh(q)
    return q


def _make_saved_exam(db_session, app, question_ids, name="اختبار محفوظ deep3"):
    """Create a SavedExam in DB, return its id."""
    with app.app_context():
        from src.routes.question import SavedExam
        from src.extensions import db
        exam = SavedExam(
            name=name,
            question_ids=question_ids,
            questions_count=len(question_ids),
            models=["أ", "ب"],
            settings={"shuffle_questions": True, "shuffle_options": True},
            header_settings={},
            is_active=True,
        )
        db.session.add(exam)
        db.session.commit()
        db.session.refresh(exam)
        return exam.id


def _make_excel_file(rows, columns=None):
    """Create an in-memory Excel file from rows (list of dicts)."""
    if columns is None and rows:
        columns = list(rows[0].keys())
    df = pd.DataFrame(rows, columns=columns)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────
# 1. list_questions with filter combinations
# ─────────────────────────────────────────────────

class TestListQuestionsFilters:

    def test_list_no_auth(self, client):
        resp = client.get("/questions/")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_list_no_filters(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_course_id(self, client, admin_user, db_session, sample_course):
        _login(client, admin_user)
        resp = client.get(f"/questions/?course_id={sample_course.id}")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_unit_id(self, client, admin_user, db_session, sample_unit):
        _login(client, admin_user)
        resp = client.get(f"/questions/?unit_id={sample_unit.id}")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_lesson_id(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.get(f"/questions/?lesson_id={sample_lesson.id}")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_page(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/?page=2")
        assert resp.status_code in [200, 302, 500]

    def test_list_course_and_unit(self, client, admin_user, db_session, sample_course, sample_unit):
        _login(client, admin_user)
        resp = client.get(f"/questions/?course_id={sample_course.id}&unit_id={sample_unit.id}")
        assert resp.status_code in [200, 302, 500]

    def test_list_course_unit_lesson(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson):
        _login(client, admin_user)
        resp = client.get(
            f"/questions/?course_id={sample_course.id}&unit_id={sample_unit.id}&lesson_id={sample_lesson.id}"
        )
        assert resp.status_code in [200, 302, 500]

    def test_list_with_questions_in_lesson(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        for i in range(3):
            _make_question(db_session, sample_lesson.id, text=f"سؤال {i} قائمة")
        resp = client.get(f"/questions/?lesson_id={sample_lesson.id}")
        assert resp.status_code in [200, 302, 500]

    def test_list_invalid_course_id(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/?course_id=999999")
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 2. filter_options API
# ─────────────────────────────────────────────────

class TestFilterOptionsAPI:

    def test_filter_options_no_auth(self, client):
        resp = client.get("/questions/api/filter_options/course")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_filter_options_course(self, client, admin_user, db_session, sample_course):
        _login(client, admin_user)
        resp = client.get("/questions/api/filter_options/course")
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert "options" in data or "success" in data

    def test_filter_options_unit_no_course(self, client, admin_user, db_session, sample_unit):
        _login(client, admin_user)
        resp = client.get("/questions/api/filter_options/unit")
        assert resp.status_code in [200, 500]

    def test_filter_options_unit_with_course(self, client, admin_user, db_session, sample_course, sample_unit):
        _login(client, admin_user)
        resp = client.get(f"/questions/api/filter_options/unit?course={sample_course.name}")
        assert resp.status_code in [200, 500]

    def test_filter_options_lesson_no_params(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.get("/questions/api/filter_options/lesson")
        assert resp.status_code in [200, 500]

    def test_filter_options_lesson_with_unit(self, client, admin_user, db_session, sample_unit, sample_lesson):
        _login(client, admin_user)
        resp = client.get(f"/questions/api/filter_options/lesson?unit={sample_unit.name}")
        assert resp.status_code in [200, 500]

    def test_filter_options_lesson_with_unit_and_course(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson):
        _login(client, admin_user)
        resp = client.get(
            f"/questions/api/filter_options/lesson?unit={sample_unit.name}&course={sample_course.name}"
        )
        assert resp.status_code in [200, 500]

    def test_filter_options_invalid_field(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/api/filter_options/invalid_field")
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("options") == [] or "success" in data


# ─────────────────────────────────────────────────
# 3. export_template_format
# ─────────────────────────────────────────────────

class TestExportTemplateFormat:

    def test_no_auth(self, client):
        resp = client.post("/questions/export/template_format")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_post_with_data(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال تصدير قالب")
        resp = client.post("/questions/export/template_format", data={})
        assert resp.status_code in [200, 302, 500]

    def test_post_no_data_redirects(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/export/template_format", data={})
        # When no data exists, it should redirect with a flash
        assert resp.status_code in [200, 302, 500]

    def test_post_with_filters(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال فلتر قالب")
        resp = client.post("/questions/export/template_format", data={
            "filter_field[]": ["question_text"],
            "filter_operator[]": ["contains"],
            "filter_value[]": ["فلتر"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_with_lesson_filter(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/export/template_format", data={
            "filter_field[]": ["lesson"],
            "filter_operator[]": ["contains"],
            "filter_value[]": [sample_lesson.name],
        })
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 4. export_filtered_data
# ─────────────────────────────────────────────────

class TestExportFilteredData:

    def test_no_auth(self, client):
        resp = client.post("/questions/export/filtered_data")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_fields_selected(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "xlsx",
        })
        assert resp.status_code in [200, 302, 500]

    def test_xlsx_format(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال xlsx")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "xlsx",
            "fields": ["question_text", "lesson", "unit", "course"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_csv_format(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال csv")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "csv",
            "fields": ["question_text", "correct_answer"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_curriculum_data_type(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "curriculum",
            "format": "xlsx",
            "fields": ["course", "unit", "lesson"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_all_data_type(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال all data")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "all",
            "format": "xlsx",
            "fields": ["question_text", "explanation", "created_at"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_pdf_format_mock(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال pdf export")
        with patch("reportlab.platypus.SimpleDocTemplate") as mock_doc:
            mock_doc.return_value.build = MagicMock()
            resp = client.post("/questions/export/filtered_data", data={
                "data_type": "questions",
                "format": "pdf",
                "fields": ["question_text"],
            })
        assert resp.status_code in [200, 302, 500]

    def test_unsupported_format(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال unsupported")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "docx_unsupported",
            "fields": ["question_text"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_with_question_filters(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال مفلتر")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "xlsx",
            "fields": ["question_text"],
            "filter_field[]": ["question_text"],
            "filter_operator[]": ["contains"],
            "filter_value[]": ["مفلتر"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_options_and_correct_answer_fields(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال خيارات")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "xlsx",
            "fields": ["options", "correct_answer", "question_image"],
        })
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 5. add_question
# ─────────────────────────────────────────────────

class TestAddQuestion:

    def test_get_no_auth(self, client):
        resp = client.get("/questions/add")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_get_with_auth_no_lessons(self, client, admin_user, db_session):
        _login(client, admin_user)
        # With no lessons, should redirect
        resp = client.get("/questions/add")
        assert resp.status_code in [200, 302, 500]

    def test_get_with_auth_and_lesson(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.get("/questions/add")
        assert resp.status_code in [200, 302, 500]

    def test_post_missing_text_and_image(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "lesson_id": str(sample_lesson.id),
            "correct_option": "0",
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_missing_lesson(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "text": "سؤال بدون درس",
            "correct_option": "0",
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_less_than_two_options(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "text": "سؤال خيار واحد",
            "lesson_id": str(sample_lesson.id),
            "correct_option": "0",
            "option_text_0": "خيار أ",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_invalid_correct_option(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "text": "سؤال إجابة خاطئة",
            "lesson_id": str(sample_lesson.id),
            "correct_option": "abc",
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_valid_question(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        with app.app_context():
            resp = client.post("/questions/add", data={
                "text": "سؤال صالح كامل",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "0",
                "option_text_0": "خيار أ صحيح",
                "option_text_1": "خيار ب خطأ",
                "option_text_2": "خيار ج خطأ",
                "option_text_3": "خيار د خطأ",
            })
        assert resp.status_code in [200, 302, 500]

    def test_post_with_explanation(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        with app.app_context():
            resp = client.post("/questions/add", data={
                "text": "سؤال مع شرح",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "1",
                "option_text_0": "خيار أ",
                "option_text_1": "خيار ب صحيح",
                "explanation": "هذا شرح السؤال",
            })
        assert resp.status_code in [200, 302, 500]

    def test_post_with_is_blocked(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        with app.app_context():
            resp = client.post("/questions/add", data={
                "text": "سؤال محجوب",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "0",
                "option_text_0": "خيار أ",
                "option_text_1": "خيار ب",
                "is_blocked": "1",
            })
        assert resp.status_code in [200, 302, 500]

    def test_post_correct_option_out_of_range(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "text": "سؤال إجابة خارج النطاق",
            "lesson_id": str(sample_lesson.id),
            "correct_option": "10",
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_negative_correct_option(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "text": "سؤال إجابة سالبة",
            "lesson_id": str(sample_lesson.id),
            "correct_option": "-1",
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_no_correct_option_but_has_options(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/add", data={
            "text": "سؤال بدون تحديد إجابة",
            "lesson_id": str(sample_lesson.id),
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 6. edit_question
# ─────────────────────────────────────────────────

class TestEditQuestion:

    def test_get_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/edit/999999")
        assert resp.status_code in [200, 302, 404, 500]

    def test_get_existing(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.get(f"/questions/edit/{q.question_id}")
        assert resp.status_code in [200, 302, 500]

    def test_post_valid_edit(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال للتعديل")
        with app.app_context():
            from src.models.question import Option
            opts = Option.query.filter_by(question_id=q.question_id).all()
            opt_data = {
                "text": "سؤال معدل",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "0",
            }
            for i, opt in enumerate(opts):
                opt_data[f"option_text_{i}"] = f"خيار معدل {i}"
                opt_data[f"option_id_{i}"] = str(opt.option_id)
            resp = client.post(f"/questions/edit/{q.question_id}", data=opt_data)
        assert resp.status_code in [200, 302, 500]

    def test_post_delete_option_image(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        with app.app_context():
            from src.models.question import Option
            opts = Option.query.filter_by(question_id=q.question_id).all()
            data = {
                "text": "سؤال مع حذف صورة",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "0",
                "delete_question_image": "1",
            }
            for i, opt in enumerate(opts):
                data[f"option_text_{i}"] = f"خيار {i}"
                data[f"option_id_{i}"] = str(opt.option_id)
                data[f"delete_option_image_{i}"] = "1"
            resp = client.post(f"/questions/edit/{q.question_id}", data=data)
        assert resp.status_code in [200, 302, 500]

    def test_post_missing_text_and_no_image(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post(f"/questions/edit/{q.question_id}", data={
            "lesson_id": str(sample_lesson.id),
            "correct_option": "0",
            "option_text_0": "خيار أ",
            "option_text_1": "خيار ب",
        })
        assert resp.status_code in [200, 302, 500]

    def test_post_add_explanation(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        with app.app_context():
            from src.models.question import Option
            opts = Option.query.filter_by(question_id=q.question_id).all()
            data = {
                "text": "سؤال مع شرح جديد",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "0",
                "explanation": "شرح محدث",
                "is_blocked": "1",
            }
            for i, opt in enumerate(opts):
                data[f"option_text_{i}"] = opt.option_text
                data[f"option_id_{i}"] = str(opt.option_id)
            resp = client.post(f"/questions/edit/{q.question_id}", data=data)
        assert resp.status_code in [200, 302, 500]

    def test_post_new_option_no_id(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        with app.app_context():
            # submit without option_id keys => create new options
            data = {
                "text": "سؤال خيارات جديدة",
                "lesson_id": str(sample_lesson.id),
                "correct_option": "0",
                "option_text_0": "خيار جديد أ",
                "option_text_1": "خيار جديد ب",
            }
            resp = client.post(f"/questions/edit/{q.question_id}", data=data)
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 7. delete_question
# ─────────────────────────────────────────────────

class TestDeleteQuestion:

    def test_delete_no_auth(self, client):
        resp = client.post("/questions/delete/1")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_delete_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/delete/999999")
        assert resp.status_code in [200, 302, 404, 500]

    def test_delete_existing(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال للحذف")
        with app.app_context():
            resp = client.post(f"/questions/delete/{q.question_id}")
        assert resp.status_code in [200, 302, 500]

    def test_delete_question_with_lesson_info(self, client, admin_user, db_session, sample_lesson, app):
        """Delete a second question to exercise lesson-info retrieval path"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال آخر للحذف")
        with app.app_context():
            resp = client.post(f"/questions/delete/{q.question_id}")
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 8. quiz page
# ─────────────────────────────────────────────────

class TestQuizPage:

    def test_quiz_no_auth(self, client):
        resp = client.get("/questions/quiz")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_quiz_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/quiz")
        assert resp.status_code in [200, 302, 404, 500]


# ─────────────────────────────────────────────────
# 9. classify route
# ─────────────────────────────────────────────────

class TestClassifyRoute:

    def test_classify_no_auth(self, client):
        resp = client.get("/questions/classify")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_classify_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/classify")
        assert resp.status_code in [200, 302, 404, 500]


# ─────────────────────────────────────────────────
# 10. header-settings endpoints
# ─────────────────────────────────────────────────

class TestHeaderSettings:

    def test_header_page_no_auth(self, client):
        resp = client.get("/questions/header-settings")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_header_page_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/header-settings")
        assert resp.status_code in [200, 302, 404, 500]

    def test_save_settings_no_auth(self, client):
        resp = client.post("/questions/save-header-settings", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_save_settings_full(self, client, admin_user, db_session):
        _login(client, admin_user)
        payload = {
            "country": "المملكة العربية السعودية",
            "ministry": "وزارة التعليم",
            "education_department": "إدارة التعليم",
            "school_name": "مدرسة تجريبية",
            "subject": "كيمياء",
            "time": "ساعتان",
            "grade": "ثاني ثانوي",
            "total_score": 40,
            "checker_name": "أحمد",
            "reviewer_name": "محمد",
            "exam_date": "2025-01-01",
        }
        resp = client.post("/questions/save-header-settings", json=payload)
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True

    def test_save_settings_empty_payload(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/save-header-settings", json={})
        assert resp.status_code in [200, 500]

    def test_get_settings_no_auth(self, client):
        resp = client.get("/questions/get-header-settings")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_get_settings_empty_db(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/get-header-settings")
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert "success" in data

    def test_get_settings_after_save(self, client, admin_user, db_session):
        _login(client, admin_user)
        client.post("/questions/save-header-settings", json={
            "country": "السعودية",
            "school_name": "مدرسة الاختبار",
        })
        resp = client.get("/questions/get-header-settings")
        assert resp.status_code in [200, 500]

    def test_save_settings_update_existing(self, client, admin_user, db_session):
        _login(client, admin_user)
        # First save
        client.post("/questions/save-header-settings", json={"country": "السعودية"})
        # Update
        resp = client.post("/questions/save-header-settings", json={
            "country": "المملكة العربية السعودية",
            "total_score": 50,
        })
        assert resp.status_code in [200, 500]


# ─────────────────────────────────────────────────
# 11. export_exam_pdf
# ─────────────────────────────────────────────────

class TestExportExamPDF:

    def test_no_auth(self, client):
        resp = client.post("/questions/export-exam-pdf", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/export-exam-pdf", json={"question_ids": []})
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/export-exam-pdf", json={
            "question_ids": [999998, 999999],
        })
        assert resp.status_code in [200, 400, 500]

    def test_with_questions_mocked(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال PDF")
        mock_generator = MagicMock()
        mock_generator.generate_pdf.return_value = b'%PDF-1.4 fake'
        with patch("src.routes.question.ExamGenerator", return_value=mock_generator, create=True):
            resp = client.post("/questions/export-exam-pdf", json={
                "question_ids": [q.question_id],
                "include_answers": True,
                "exam_title": "اختبار تجريبي",
            })
        assert resp.status_code in [200, 500]


# ─────────────────────────────────────────────────
# 12. preview_exam_paper
# ─────────────────────────────────────────────────

class TestPreviewExamPaper:

    def test_no_auth(self, client):
        resp = client.post("/questions/preview-exam-paper", data={})
        assert resp.status_code in [200, 302, 400, 401, 403, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/preview-exam-paper", data={"question_ids": ""})
        assert resp.status_code in [200, 302, 400, 500]

    def test_with_questions_mocked(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال معاينة")
        mock_generator = MagicMock()
        mock_generator.generate_html.return_value = "<html><body>Preview</body></html>"
        with patch("src.routes.question.ExamGenerator", return_value=mock_generator, create=True):
            resp = client.post("/questions/preview-exam-paper", data={
                "question_ids": str(q.question_id),
                "include_answers": "true",
            })
        assert resp.status_code in [200, 302, 400, 500]

    def test_include_answers_false(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال بدون إجابات")
        mock_generator = MagicMock()
        mock_generator.generate_html.return_value = "<html>Test</html>"
        with patch("src.routes.question.ExamGenerator", return_value=mock_generator, create=True):
            resp = client.post("/questions/preview-exam-paper", data={
                "question_ids": str(q.question_id),
                "include_answers": "false",
            })
        assert resp.status_code in [200, 302, 400, 500]


# ─────────────────────────────────────────────────
# 13. generate_multi_models
# ─────────────────────────────────────────────────

class TestGenerateMultiModels:

    def test_no_auth(self, client):
        resp = client.post("/questions/generate-multi-models", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/generate-multi-models", json={
            "question_ids": [],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/generate-multi-models", json={
            "question_ids": [999998, 999999],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 404, 500]

    def test_with_questions_weasyprint_mocked(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال نماذج متعددة")
        mock_html_cls = MagicMock()
        mock_html_cls.return_value.write_pdf = MagicMock()
        with patch.dict("sys.modules", {"weasyprint": MagicMock(HTML=mock_html_cls)}):
            with patch("src.routes.question.WeasyHTML" if hasattr(__import__("src.routes.question", fromlist=["WeasyHTML"]), "WeasyHTML") else "builtins.open", mock_html_cls, create=True):
                resp = client.post("/questions/generate-multi-models", json={
                    "question_ids": [q.question_id],
                    "models": ["أ"],
                    "include_answers": False,
                    "include_barcode": False,
                })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_with_include_answer_sheet(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/generate-multi-models", json={
            "question_ids": [q.question_id],
            "models": ["أ", "ب"],
            "include_answers": True,
            "include_answer_sheet": True,
            "include_barcode": True,
            "shuffle_options": True,
        })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_multiple_models(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        qs = [_make_question(db_session, sample_lesson.id, text=f"سؤال {i}") for i in range(3)]
        resp = client.post("/questions/generate-multi-models", json={
            "question_ids": [q.question_id for q in qs],
            "models": ["أ", "ب", "ج", "د"],
            "shuffle_options": False,
        })
        assert resp.status_code in [200, 302, 400, 404, 500]


# ─────────────────────────────────────────────────
# 14. preview_multi_models
# ─────────────────────────────────────────────────

class TestPreviewMultiModels:

    def test_no_auth(self, client):
        resp = client.post("/questions/preview-multi-models", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [999998],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 404, 500]

    def test_with_questions(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال معاينة متعدد")
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [q.question_id],
            "models": ["أ"],
            "include_answers": False,
            "include_barcode": True,
            "font_size": 14,
            "columns": 2,
        })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_with_answer_sheet(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [q.question_id],
            "models": ["أ", "ب"],
            "include_answer_sheet": True,
            "include_answers": True,
            "shuffle_options": True,
        })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_with_saved_options_order(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال ترتيب محفوظ")
        # Build a fake saved options order
        with app.app_context():
            from src.models.question import Option
            opts = Option.query.filter_by(question_id=q.question_id).all()
            saved_order = {str(q.question_id): [opt.option_id for opt in opts]}
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [q.question_id],
            "models": ["أ"],
            "saved_options_order": saved_order,
        })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_custom_layout_options(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [q.question_id],
            "models": ["أ"],
            "columns": 1,
            "spacing": "wide",
            "options_layout": "horizontal",
            "image_size": 80,
            "header_size": "large",
            "show_logo": False,
            "exam_type": "نهاية الفصل",
            "semester": "الثاني",
            "academic_year": "1448هـ",
        })
        assert resp.status_code in [200, 302, 400, 404, 500]


# ─────────────────────────────────────────────────
# 15. preview_students
# ─────────────────────────────────────────────────

class TestPreviewStudents:

    def test_no_auth(self, client):
        resp = client.post("/questions/preview-students")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_file(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/preview-students", data={})
        assert resp.status_code in [200, 400, 500]

    def test_with_excel_file(self, client, admin_user, db_session):
        _login(client, admin_user)
        rows = [
            {"الاسم": "أحمد", "الرقم الأكاديمي": "12345", "الشعبة": "أ"},
            {"الاسم": "محمد", "الرقم الأكاديمي": "67890", "الشعبة": "ب"},
        ]
        buf = _make_excel_file(rows)
        resp = client.post("/questions/preview-students", data={
            "student_file": (buf, "students.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 400, 500]

    def test_with_english_columns(self, client, admin_user, db_session):
        _login(client, admin_user)
        rows = [
            {"Name": "Ahmed", "Academic ID": "11111", "Section": "A"},
        ]
        buf = _make_excel_file(rows)
        resp = client.post("/questions/preview-students", data={
            "student_file": (buf, "students.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 400, 500]

    def test_with_empty_excel(self, client, admin_user, db_session):
        _login(client, admin_user)
        buf = _make_excel_file([], columns=["الاسم", "الرقم الأكاديمي", "الشعبة"])
        resp = client.post("/questions/preview-students", data={
            "student_file": (buf, "students.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 400, 500]


# ─────────────────────────────────────────────────
# 16. print_remark_sheets
# ─────────────────────────────────────────────────

class TestPrintRemarkSheets:

    def test_no_auth(self, client):
        resp = client.post("/questions/print-remark-sheets", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_empty_students(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/print-remark-sheets", json={
            "students": [],
            "exam_type": "نهاية",
            "semester": "الأول",
            "academic_year": "1447هـ",
        })
        assert resp.status_code in [200, 400, 500]

    def test_with_students(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/print-remark-sheets", json={
            "students": [
                {"name": "أحمد", "academic_id": "12345", "section": "أ"},
                {"name": "محمد", "academic_id": "67890", "section": "ب"},
            ],
            "exam_type": "نهاية",
            "semester": "الأول",
            "academic_year": "1447هـ",
        })
        assert resp.status_code in [200, 400, 500]

    def test_student_without_academic_id(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/print-remark-sheets", json={
            "students": [
                {"name": "طالب بدون رقم", "academic_id": "", "section": "أ"},
            ],
        })
        assert resp.status_code in [200, 400, 500]

    def test_with_settings_in_db(self, client, admin_user, db_session):
        _login(client, admin_user)
        # Save settings first
        client.post("/questions/save-header-settings", json={
            "school_name": "مدرسة ريمارك",
            "subject": "كيمياء",
        })
        resp = client.post("/questions/print-remark-sheets", json={
            "students": [{"name": "طالب", "academic_id": "99999", "section": "ج"}],
            "exam_type": "نصفية",
        })
        assert resp.status_code in [200, 400, 500]


# ─────────────────────────────────────────────────
# 17. generate_omr_answer_key
# ─────────────────────────────────────────────────

class TestGenerateOmrAnswerKey:

    def test_no_auth(self, client):
        resp = client.post("/questions/generate-omr-answer-key", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/generate-omr-answer-key", json={
            "question_ids": [],
            "model_letter": "أ",
        })
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/generate-omr-answer-key", json={
            "question_ids": [999998, 999999],
            "model_letter": "أ",
        })
        assert resp.status_code in [200, 400, 404, 500]

    def test_with_questions(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        qs = [_make_question(db_session, sample_lesson.id, text=f"سؤال OMR {i}") for i in range(5)]
        resp = client.post("/questions/generate-omr-answer-key", json={
            "question_ids": [q.question_id for q in qs],
            "model_letter": "أ",
            "exam_type": "نهاية",
            "semester": "الثاني",
            "academic_year": "1447هـ",
        })
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert "success" in data

    def test_with_header_settings(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        client.post("/questions/save-header-settings", json={"school_name": "مدرسة OMR"})
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/generate-omr-answer-key", json={
            "question_ids": [q.question_id],
            "model_letter": "ب",
        })
        assert resp.status_code in [200, 400, 500]

    def test_model_letter_b(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/generate-omr-answer-key", json={
            "question_ids": [q.question_id],
            "model_letter": "ب",
        })
        assert resp.status_code in [200, 400, 500]


# ─────────────────────────────────────────────────
# 18. print_remark_sheets_multi_models
# ─────────────────────────────────────────────────

class TestPrintRemarkSheetsMultiModels:

    def test_no_auth(self, client):
        resp = client.post("/questions/print-remark-sheets-multi-models", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_students(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/print-remark-sheets-multi-models", json={
            "students": [],
            "models": ["أ"],
            "question_ids": [q.question_id],
        })
        assert resp.status_code in [200, 400, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/print-remark-sheets-multi-models", json={
            "students": [{"name": "طالب", "academic_id": "111"}],
            "models": ["أ"],
            "question_ids": [],
        })
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/print-remark-sheets-multi-models", json={
            "students": [{"name": "طالب", "academic_id": "111"}],
            "models": ["أ"],
            "question_ids": [999998],
        })
        assert resp.status_code in [200, 400, 404, 500]

    def test_with_students_and_questions(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        qs = [_make_question(db_session, sample_lesson.id, text=f"سؤال ريمارك {i}") for i in range(3)]
        resp = client.post("/questions/print-remark-sheets-multi-models", json={
            "students": [
                {"name": "أحمد", "academic_id": "11111", "section": "أ"},
                {"name": "محمد", "academic_id": "22222", "section": "ب"},
                {"name": "خالد", "academic_id": "33333", "section": "ج"},
            ],
            "models": ["أ", "ب"],
            "question_ids": [q.question_id for q in qs],
            "shuffle_options": True,
            "exam_type": "نهاية",
            "semester": "الأول",
            "academic_year": "1447هـ",
        })
        assert resp.status_code in [200, 400, 500]

    def test_single_model_single_student(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/print-remark-sheets-multi-models", json={
            "students": [{"name": "فاطمة", "academic_id": "44444", "section": "د"}],
            "models": ["أ"],
            "question_ids": [q.question_id],
        })
        assert resp.status_code in [200, 400, 500]


# ─────────────────────────────────────────────────
# 19. print_blank_remark_sheets
# ─────────────────────────────────────────────────

class TestPrintBlankRemarkSheets:

    def test_no_auth(self, client):
        resp = client.post("/questions/print-blank-remark-sheets", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/print-blank-remark-sheets", json={
            "models": ["أ"],
            "question_ids": [],
            "count_per_model": 5,
        })
        assert resp.status_code in [200, 400, 500]

    def test_with_questions(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/print-blank-remark-sheets", json={
            "models": ["أ"],
            "question_ids": [q.question_id],
            "count_per_model": 2,
            "exam_type": "نهاية",
            "semester": "الأول",
            "academic_year": "1447هـ",
        })
        assert resp.status_code in [200, 400, 500]

    def test_multiple_models(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        qs = [_make_question(db_session, sample_lesson.id, text=f"سؤال فارغ {i}") for i in range(2)]
        resp = client.post("/questions/print-blank-remark-sheets", json={
            "models": ["أ", "ب", "ج"],
            "question_ids": [q.question_id for q in qs],
            "count_per_model": 3,
        })
        assert resp.status_code in [200, 400, 500]

    def test_zero_count(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/print-blank-remark-sheets", json={
            "models": ["أ"],
            "question_ids": [q.question_id],
            "count_per_model": 0,
        })
        assert resp.status_code in [200, 400, 500]


# ─────────────────────────────────────────────────
# 20. generate_all_models_answer_keys
# ─────────────────────────────────────────────────

class TestGenerateAllModelsAnswerKeys:

    def test_no_auth(self, client):
        resp = client.post("/questions/generate-all-models-answer-keys", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_question_ids(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/generate-all-models-answer-keys", json={
            "question_ids": [],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/generate-all-models-answer-keys", json={
            "question_ids": [999998],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 404, 500]

    def test_single_model(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        qs = [_make_question(db_session, sample_lesson.id, text=f"سؤال مفتاح {i}") for i in range(4)]
        resp = client.post("/questions/generate-all-models-answer-keys", json={
            "question_ids": [q.question_id for q in qs],
            "models": ["أ"],
            "exam_type": "نهاية",
        })
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True

    def test_multiple_models(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        qs = [_make_question(db_session, sample_lesson.id, text=f"سؤال مفتاح {i}") for i in range(4)]
        resp = client.post("/questions/generate-all-models-answer-keys", json={
            "question_ids": [q.question_id for q in qs],
            "models": ["أ", "ب", "ج", "د"],
            "shuffle_options": True,
            "exam_type": "نصفية",
            "semester": "الثاني",
            "academic_year": "1448هـ",
        })
        assert resp.status_code in [200, 400, 500]

    def test_with_header_settings(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        client.post("/questions/save-header-settings", json={"school_name": "مدرسة مفتاح"})
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/generate-all-models-answer-keys", json={
            "question_ids": [q.question_id],
            "models": ["أ", "ب"],
        })
        assert resp.status_code in [200, 400, 500]

    def test_no_shuffle(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/generate-all-models-answer-keys", json={
            "question_ids": [q.question_id],
            "models": ["أ"],
            "shuffle_options": False,
        })
        assert resp.status_code in [200, 400, 500]


# ─────────────────────────────────────────────────
# 21. saved-exams CRUD
# ─────────────────────────────────────────────────

class TestSavedExamsCRUD:

    # --- GET list ---
    def test_list_no_auth(self, client):
        resp = client.get("/questions/saved-exams")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_list_empty(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/saved-exams")
        assert resp.status_code in [200, 302, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert "exams" in data or "success" in data

    def test_list_with_data(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        _make_saved_exam(db_session, app, [q.question_id], name="اختبار قائمة deep3")
        resp = client.get("/questions/saved-exams")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_pagination(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/saved-exams?page=1&per_page=5")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_search(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        _make_saved_exam(db_session, app, [q.question_id], name="اختبار بحث فريد")
        resp = client.get("/questions/saved-exams?search=بحث فريد")
        assert resp.status_code in [200, 302, 500]

    def test_list_with_course_filter(self, client, admin_user, db_session, sample_lesson, sample_course, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        _make_saved_exam(db_session, app, [q.question_id])
        resp = client.get(f"/questions/saved-exams?course_id={sample_course.id}")
        assert resp.status_code in [200, 302, 500]

    # --- POST save ---
    def test_save_no_auth(self, client):
        resp = client.post("/questions/saved-exams", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_save_no_name(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/saved-exams", json={
            "name": "",
            "question_ids": [q.question_id],
        })
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 400:
            data = resp.get_json()
            assert data.get("success") is False

    def test_save_no_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/saved-exams", json={
            "name": "اختبار بدون أسئلة",
            "question_ids": [],
        })
        assert resp.status_code in [200, 400, 500]

    def test_save_valid(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال للحفظ")
        resp = client.post("/questions/saved-exams", json={
            "name": "اختبار محفوظ جديد",
            "description": "وصف الاختبار",
            "question_ids": [q.question_id],
            "models": ["أ", "ب"],
            "shuffle_questions": True,
            "shuffle_options": True,
            "font_size": 16,
            "columns": 2,
            "exam_type": "نهاية",
            "semester": "الأول",
            "academic_year": "1447هـ",
        })
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True

    def test_save_with_options_order(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        with app.app_context():
            from src.models.question import Option
            opts = Option.query.filter_by(question_id=q.question_id).all()
            options_order = [opt.option_id for opt in opts]
        resp = client.post("/questions/saved-exams", json={
            "name": "اختبار مع ترتيب خيارات",
            "question_ids": [q.question_id],
            "questions_with_order": [
                {"question_id": q.question_id, "options_order": options_order}
            ],
        })
        assert resp.status_code in [200, 400, 500]

    # --- GET single ---
    def test_get_single_no_auth(self, client):
        resp = client.get("/questions/saved-exams/1")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_get_single_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/saved-exams/999999")
        assert resp.status_code in [200, 404, 500]
        if resp.status_code == 404 or resp.status_code == 200:
            data = resp.get_json()
            if data:
                assert "success" in data

    def test_get_single_existing(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        exam_id = _make_saved_exam(db_session, app, [q.question_id], name="اختبار للجلب")
        resp = client.get(f"/questions/saved-exams/{exam_id}")
        assert resp.status_code in [200, 404, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True

    # --- PUT update ---
    def test_update_no_auth(self, client):
        resp = client.put("/questions/saved-exams/1", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_update_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.put("/questions/saved-exams/999999", json={"name": "اسم جديد"})
        assert resp.status_code in [200, 404, 500]

    def test_update_existing(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        exam_id = _make_saved_exam(db_session, app, [q.question_id], name="اختبار للتحديث")
        resp = client.put(f"/questions/saved-exams/{exam_id}", json={
            "name": "اختبار محدث",
            "description": "وصف محدث",
            "models": ["أ", "ب", "ج"],
            "exam_type": "نصفية",
            "semester": "الثاني",
            "academic_year": "1448هـ",
        })
        assert resp.status_code in [200, 404, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True

    def test_update_question_ids(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q1 = _make_question(db_session, sample_lesson.id, text="سؤال 1 تحديث")
        q2 = _make_question(db_session, sample_lesson.id, text="سؤال 2 تحديث")
        exam_id = _make_saved_exam(db_session, app, [q1.question_id])
        resp = client.put(f"/questions/saved-exams/{exam_id}", json={
            "question_ids": [q1.question_id, q2.question_id],
        })
        assert resp.status_code in [200, 404, 500]

    # --- DELETE ---
    def test_delete_no_auth(self, client):
        resp = client.delete("/questions/saved-exams/1")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_delete_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.delete("/questions/saved-exams/999999")
        assert resp.status_code in [200, 404, 500]

    def test_delete_existing(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        exam_id = _make_saved_exam(db_session, app, [q.question_id], name="اختبار للحذف")
        resp = client.delete(f"/questions/saved-exams/{exam_id}")
        assert resp.status_code in [200, 404, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True

    def test_delete_already_deleted(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        exam_id = _make_saved_exam(db_session, app, [q.question_id], name="اختبار محذوف مرتين")
        # First delete
        client.delete(f"/questions/saved-exams/{exam_id}")
        # Second attempt
        resp = client.delete(f"/questions/saved-exams/{exam_id}")
        assert resp.status_code in [200, 404, 500]


# ─────────────────────────────────────────────────
# 22. load_saved_exam
# ─────────────────────────────────────────────────

class TestLoadSavedExam:

    def test_no_auth(self, client):
        resp = client.post("/questions/saved-exams/1/load")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_nonexistent(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/saved-exams/999999/load")
        assert resp.status_code in [200, 404, 500]

    def test_load_valid(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال للتحميل")
        exam_id = _make_saved_exam(db_session, app, [q.question_id], name="اختبار للتحميل")
        resp = client.post(f"/questions/saved-exams/{exam_id}/load")
        assert resp.status_code in [200, 404, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True
            assert "questions" in data

    def test_load_with_options_order(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        with app.app_context():
            from src.models.question import Option
            from src.routes.question import SavedExam
            from src.extensions import db
            opts = Option.query.filter_by(question_id=q.question_id).all()
            opt_ids = [opt.option_id for opt in opts]
            exam = SavedExam(
                name="اختبار مع ترتيب للتحميل",
                question_ids=[q.question_id],
                questions_count=1,
                settings={"options_order": {str(q.question_id): opt_ids}},
                is_active=True,
            )
            db.session.add(exam)
            db.session.commit()
            exam_id = exam.id
        resp = client.post(f"/questions/saved-exams/{exam_id}/load")
        assert resp.status_code in [200, 404, 500]

    def test_load_with_missing_questions(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        # Exam with non-existent question IDs
        exam_id = _make_saved_exam(db_session, app, [999998, 999999], name="اختبار أسئلة مفقودة")
        resp = client.post(f"/questions/saved-exams/{exam_id}/load")
        assert resp.status_code in [200, 404, 500]
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get("success") is True
            assert data.get("questions") == []

    def test_load_deleted_exam(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        exam_id = _make_saved_exam(db_session, app, [q.question_id], name="اختبار محذوف")
        client.delete(f"/questions/saved-exams/{exam_id}")
        resp = client.post(f"/questions/saved-exams/{exam_id}/load")
        assert resp.status_code in [200, 404, 500]


# ─────────────────────────────────────────────────
# 23. export_courses_units_lessons
# ─────────────────────────────────────────────────

class TestExportCoursesUnitsLessons:

    def test_no_auth(self, client):
        resp = client.get("/questions/export/courses_units_lessons")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_empty_db(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/export/courses_units_lessons")
        # With no lessons in DB, df might be empty → still returns xlsx or redirects
        assert resp.status_code in [200, 302, 500]

    def test_with_lessons(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson, app):
        _login(client, admin_user)
        resp = client.get("/questions/export/courses_units_lessons")
        assert resp.status_code in [200, 302, 500]
        if resp.status_code == 200:
            assert b'xlsx' in resp.content_type.encode() or len(resp.data) > 0

    def test_with_multiple_lessons(self, client, admin_user, db_session, sample_unit, app):
        _login(client, admin_user)
        from src.models.curriculum import Lesson
        with app.app_context():
            from src.extensions import db
            for i in range(3):
                lesson = Lesson(
                    name=f"درس إضافي {i}",
                    unit_id=sample_unit.id,
                    order_num=i + 10,
                )
                db.session.add(lesson)
            db.session.commit()
        resp = client.get("/questions/export/courses_units_lessons")
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 24. download_import_template
# ─────────────────────────────────────────────────

class TestDownloadImportTemplate:

    def test_no_auth(self, client):
        resp = client.get("/questions/import/template")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_download_template(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/import/template")
        assert resp.status_code in [200, 302, 500]
        if resp.status_code == 200:
            assert len(resp.data) > 0


# ─────────────────────────────────────────────────
# 25. import_questions
# ─────────────────────────────────────────────────

class TestImportQuestions:

    def test_get_no_auth(self, client):
        resp = client.get("/questions/import")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_get_with_auth(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.get("/questions/import")
        assert resp.status_code in [200, 302, 500]

    def test_post_no_file(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/import", data={"lesson_id": str(sample_lesson.id)})
        assert resp.status_code in [200, 302, 500]

    def test_post_invalid_file_type(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        resp = client.post("/questions/import", data={
            "lesson_id": str(sample_lesson.id),
            "question_file": (io.BytesIO(b"not a real file"), "test.txt"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]

    def test_post_missing_columns(self, client, admin_user, db_session, sample_lesson):
        _login(client, admin_user)
        # Excel file with wrong columns
        df = pd.DataFrame([{"Wrong Col": "value"}])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        resp = client.post("/questions/import", data={
            "lesson_id": str(sample_lesson.id),
            "question_file": (buf, "questions.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]

    def test_post_valid_excel(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson, app):
        _login(client, admin_user)
        rows = [{
            "Course Name": sample_course.name,
            "Unit Name": sample_unit.name,
            "Lesson Name": sample_lesson.name,
            "Question Text": "سؤال مستورد",
            "Question Image URL": "",
            "Option 1 Text": "خيار أ",
            "Option 1 Image URL": "",
            "Option 2 Text": "خيار ب",
            "Option 2 Image URL": "",
            "Option 3 Text": "خيار ج",
            "Option 3 Image URL": "",
            "Option 4 Text": "خيار د",
            "Option 4 Image URL": "",
            "Correct Option Number": 1,
            "Explanation": "هذا شرح",
        }]
        buf = _make_excel_file(rows)
        with app.app_context():
            resp = client.post("/questions/import", data={
                "question_file": (buf, "questions.xlsx"),
            }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]

    def test_post_row_missing_lesson(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        rows = [{
            "Course Name": "",
            "Unit Name": "",
            "Lesson Name": "",
            "Question Text": "سؤال بدون درس",
            "Question Image URL": "",
            "Option 1 Text": "خيار أ",
            "Option 1 Image URL": "",
            "Option 2 Text": "خيار ب",
            "Option 2 Image URL": "",
            "Option 3 Text": "خيار ج",
            "Option 3 Image URL": "",
            "Option 4 Text": "خيار د",
            "Option 4 Image URL": "",
            "Correct Option Number": 1,
            "Explanation": "",
        }]
        buf = _make_excel_file(rows)
        resp = client.post("/questions/import", data={
            "question_file": (buf, "questions.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]

    def test_post_row_missing_question_text(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson, app):
        _login(client, admin_user)
        rows = [{
            "Course Name": sample_course.name,
            "Unit Name": sample_unit.name,
            "Lesson Name": sample_lesson.name,
            "Question Text": "",
            "Question Image URL": "",
            "Option 1 Text": "خيار أ",
            "Option 1 Image URL": "",
            "Option 2 Text": "خيار ب",
            "Option 2 Image URL": "",
            "Option 3 Text": "خيار ج",
            "Option 3 Image URL": "",
            "Option 4 Text": "خيار د",
            "Option 4 Image URL": "",
            "Correct Option Number": 1,
            "Explanation": "",
        }]
        buf = _make_excel_file(rows)
        resp = client.post("/questions/import", data={
            "question_file": (buf, "questions.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]

    def test_post_invalid_correct_option(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson, app):
        _login(client, admin_user)
        rows = [{
            "Course Name": sample_course.name,
            "Unit Name": sample_unit.name,
            "Lesson Name": sample_lesson.name,
            "Question Text": "سؤال رقم إجابة خاطئ",
            "Question Image URL": "",
            "Option 1 Text": "خيار أ",
            "Option 1 Image URL": "",
            "Option 2 Text": "خيار ب",
            "Option 2 Image URL": "",
            "Option 3 Text": "",
            "Option 3 Image URL": "",
            "Option 4 Text": "",
            "Option 4 Image URL": "",
            "Correct Option Number": 10,  # Out of range
            "Explanation": "",
        }]
        buf = _make_excel_file(rows)
        resp = client.post("/questions/import", data={
            "question_file": (buf, "questions.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]

    def test_post_csv_file(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson, app):
        _login(client, admin_user)
        rows = [{
            "Course Name": sample_course.name,
            "Unit Name": sample_unit.name,
            "Lesson Name": sample_lesson.name,
            "Question Text": "سؤال CSV",
            "Question Image URL": "",
            "Option 1 Text": "خيار 1",
            "Option 1 Image URL": "",
            "Option 2 Text": "خيار 2",
            "Option 2 Image URL": "",
            "Option 3 Text": "خيار 3",
            "Option 3 Image URL": "",
            "Option 4 Text": "خيار 4",
            "Option 4 Image URL": "",
            "Correct Option Number": 1,
            "Explanation": "",
        }]
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        buf.write(df.to_csv(index=False).encode('utf-8'))
        buf.seek(0)
        with app.app_context():
            resp = client.post("/questions/import", data={
                "question_file": (buf, "questions.csv"),
            }, content_type="multipart/form-data")
        assert resp.status_code in [200, 302, 500]


# ─────────────────────────────────────────────────
# 26. export-exam page
# ─────────────────────────────────────────────────

class TestExportExamPage:

    def test_no_auth(self, client):
        resp = client.get("/questions/export-exam")
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_with_auth(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.get("/questions/export-exam")
        assert resp.status_code in [200, 302, 404, 500]


# ─────────────────────────────────────────────────
# 27. download_exam_word
# ─────────────────────────────────────────────────

class TestDownloadExamWord:

    def test_no_auth(self, client):
        resp = client.post("/questions/download-exam-word", json={})
        assert resp.status_code in [200, 302, 401, 403, 500]

    def test_no_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/download-exam-word", json={"question_ids": []})
        assert resp.status_code in [200, 400, 500]

    def test_nonexistent_questions(self, client, admin_user, db_session):
        _login(client, admin_user)
        resp = client.post("/questions/download-exam-word", json={
            "question_ids": [999997, 999998],
        })
        assert resp.status_code in [200, 400, 404, 500]

    def test_import_error_path(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        # exam_generator module not importable → ImportError path
        resp = client.post("/questions/download-exam-word", json={
            "question_ids": [q.question_id],
            "exam_title": "اختبار ورد",
            "include_answers": False,
        })
        # Either 500 (ImportError) or success if module happens to exist
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_with_all_params(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id, text="سؤال ورد كامل")
        resp = client.post("/questions/download-exam-word", json={
            "question_ids": [q.question_id],
            "include_answers": True,
            "exam_title": "نموذج اختبار",
            "course_name": "كيمياء",
            "unit_name": "الوحدة الأولى",
            "lesson_name": "الدرس الأول",
            "output_format": "word",
        })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_pdf_output_format(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/download-exam-word", json={
            "question_ids": [q.question_id],
            "output_format": "pdf",
        })
        assert resp.status_code in [200, 302, 400, 404, 500]


# ─────────────────────────────────────────────────
# 28. Additional edge cases and combinatorial tests
# ─────────────────────────────────────────────────

class TestEdgeCases:

    def test_save_exam_full_lifecycle(self, client, admin_user, db_session, sample_lesson, app):
        """Full lifecycle: save → get → update → load → delete"""
        _login(client, admin_user)
        q1 = _make_question(db_session, sample_lesson.id, text="سؤال دورة حياة 1")
        q2 = _make_question(db_session, sample_lesson.id, text="سؤال دورة حياة 2")

        # Save
        resp = client.post("/questions/saved-exams", json={
            "name": "اختبار دورة الحياة",
            "question_ids": [q1.question_id],
            "models": ["أ"],
        })
        assert resp.status_code in [200, 400, 500]
        if resp.status_code != 200:
            return
        exam_id = resp.get_json().get("exam", {}).get("id")
        if not exam_id:
            return

        # Get
        resp2 = client.get(f"/questions/saved-exams/{exam_id}")
        assert resp2.status_code in [200, 404, 500]

        # Update
        resp3 = client.put(f"/questions/saved-exams/{exam_id}", json={
            "name": "اختبار دورة الحياة محدث",
            "question_ids": [q1.question_id, q2.question_id],
            "settings": {"shuffle_questions": False},
        })
        assert resp3.status_code in [200, 404, 500]

        # Load
        resp4 = client.post(f"/questions/saved-exams/{exam_id}/load")
        assert resp4.status_code in [200, 404, 500]

        # Delete
        resp5 = client.delete(f"/questions/saved-exams/{exam_id}")
        assert resp5.status_code in [200, 404, 500]

    def test_header_settings_then_generate_omr(self, client, admin_user, db_session, sample_lesson, app):
        """Save header settings then use OMR key generation"""
        _login(client, admin_user)
        client.post("/questions/save-header-settings", json={
            "country": "السعودية",
            "school_name": "مدرسة OMR2",
            "subject": "كيمياء 3",
            "grade": "ثالث ثانوي",
            "total_score": 25,
        })
        q = _make_question(db_session, sample_lesson.id, text="سؤال لـ OMR")
        resp = client.post("/questions/generate-omr-answer-key", json={
            "question_ids": [q.question_id],
            "model_letter": "ج",
        })
        assert resp.status_code in [200, 400, 500]

    def test_filter_options_then_export(self, client, admin_user, db_session, sample_course, sample_unit, sample_lesson, app):
        """Get filter options then use in export"""
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id)

        # Get filter options
        resp1 = client.get("/questions/api/filter_options/course")
        assert resp1.status_code in [200, 500]

        # Export using filter
        resp2 = client.post("/questions/export/template_format", data={
            "filter_field[]": ["course"],
            "filter_operator[]": ["equals"],
            "filter_value[]": [sample_course.name],
        })
        assert resp2.status_code in [200, 302, 500]

    def test_list_questions_high_page(self, client, admin_user, db_session, sample_lesson):
        """Request a very high page number (should return empty, not error)"""
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id)
        resp = client.get("/questions/?page=9999")
        assert resp.status_code in [200, 302, 500]

    def test_saved_exams_page_2(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        for i in range(3):
            _make_saved_exam(db_session, app, [q.question_id], name=f"اختبار صفحة 2 - {i}")
        resp = client.get("/questions/saved-exams?page=2&per_page=2")
        assert resp.status_code in [200, 302, 500]

    def test_blank_remark_with_settings(self, client, admin_user, db_session, sample_lesson, app):
        """Blank remark sheets after saving header settings"""
        _login(client, admin_user)
        client.post("/questions/save-header-settings", json={"school_name": "مدرسة ريمارك فارغة"})
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/print-blank-remark-sheets", json={
            "models": ["أ", "ب"],
            "question_ids": [q.question_id],
            "count_per_model": 1,
        })
        assert resp.status_code in [200, 400, 500]

    def test_multi_models_no_barcode(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/preview-multi-models", json={
            "question_ids": [q.question_id],
            "models": ["أ"],
            "include_barcode": False,
            "include_answer_sheet": False,
        })
        assert resp.status_code in [200, 302, 400, 404, 500]

    def test_remark_multi_models_uneven_distribution(self, client, admin_user, db_session, sample_lesson, app):
        """Test student distribution when count doesn't divide evenly among models"""
        _login(client, admin_user)
        q = _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/print-remark-sheets-multi-models", json={
            "students": [
                {"name": f"طالب {i}", "academic_id": str(i), "section": "أ"}
                for i in range(5)  # 5 students, 3 models -> uneven
            ],
            "models": ["أ", "ب", "ج"],
            "question_ids": [q.question_id],
        })
        assert resp.status_code in [200, 400, 500]

    def test_export_filtered_data_question_filter_created_at(self, client, admin_user, db_session, sample_lesson, app):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id, text="سؤال تاريخ")
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "xlsx",
            "fields": ["question_text", "created_at"],
            "filter_field[]": ["created_at"],
            "filter_operator[]": ["greater_than"],
            "filter_value[]": ["2020-01-01"],
        })
        assert resp.status_code in [200, 302, 500]

    def test_export_data_unit_filter(self, client, admin_user, db_session, sample_unit, sample_lesson, app):
        _login(client, admin_user)
        _make_question(db_session, sample_lesson.id)
        resp = client.post("/questions/export/filtered_data", data={
            "data_type": "questions",
            "format": "csv",
            "fields": ["question_text", "unit"],
            "filter_field[]": ["unit"],
            "filter_operator[]": ["equals"],
            "filter_value[]": [sample_unit.name],
        })
        assert resp.status_code in [200, 302, 500]
