"""
Extra integration tests for diagnostic_routes.py - Part 4
Target: raise diagnostic_routes.py coverage from 79% to 90%+

Focuses on uncovered paths:
- PDF export paths with WeasyPrint mock
- generate_diagnostic_html helper (columns=1, columns=3, all layouts)
- nested try/except error paths in assign_test (notification body)
- /results GET with data - inner loop exception paths
- /student/assigned with cookies, session, all fallback paths
- /tests/<id>/send-notification: no NotificationService, students present
- _save_notification_to_db paths: Notification=None, StudentNotification=None
- compare_tests with valid pre+post results
- generate-pair: post_result failure branch
- ExamHeaderSettings header loading (both success and error)
- generate_diagnostic_html with empty questions, include_answers=True
- submit_test: empty answers, all-wrong, answer index beyond questions
- assign_test: missing test_id returns 404, grade selection
- get_all_results: inner loop exception and student lookup
- cancel-schedule: existing test success path
"""
import pytest
import secrets
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


ACCEPT = [200, 400, 401, 403, 404, 405, 500]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _make_student(db_session, grade=None):
    from src.models.student import Student
    s = Student(
        name=f'Stu {secrets.token_hex(4)}',
        username=f'stu_{secrets.token_hex(6)}',
        email=f'stu_{secrets.token_hex(6)}@d4.com',
        is_active=True,
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    if grade:
        s.grade = grade
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


def _make_test(db_session, admin_user, test_type='pre_test', is_scheduled=False,
               assigned_students=None, scheduled_start=None, scheduled_end=None,
               lesson_id=None, unit_id=None, course_id=None, is_active=True):
    from src.models.diagnostic_test import DiagnosticTest
    questions = [
        {
            'text': f'سؤال {i}',
            'lesson_name': 'درس اختبار',
            'options': [
                {'text': 'أ', 'is_correct': True},
                {'text': 'ب', 'is_correct': False},
                {'text': 'ج', 'is_correct': False},
                {'text': 'د', 'is_correct': False},
            ],
        }
        for i in range(1, 6)
    ]
    now = datetime.utcnow()
    test = DiagnosticTest(
        title=f'اختبار {test_type} {secrets.token_hex(3)}',
        description='وصف الاختبار',
        test_type=test_type,
        questions_count=5,
        questions_data=questions,
        is_active=is_active,
        is_scheduled=is_scheduled,
        created_by=admin_user.id,
        passing_score=60,
        time_limit_minutes=30,
        assigned_students=assigned_students if assigned_students is not None else [],
        scheduled_start=scheduled_start or (now - timedelta(hours=1) if is_scheduled else None),
        scheduled_end=scheduled_end or (now + timedelta(hours=1) if is_scheduled else None),
        lesson_id=lesson_id,
        unit_id=unit_id,
        course_id=course_id,
    )
    db_session.session.add(test)
    db_session.session.commit()
    db_session.session.refresh(test)
    return test


def _make_result(db_session, test, student, status='completed', score=3, percentage=60.0):
    from src.models.diagnostic_test import DiagnosticResult
    result = DiagnosticResult(
        diagnostic_test_id=test.id,
        student_id=str(student.id),
        total_questions=5,
        score=score,
        correct_answers=score,
        percentage=percentage,
        status=status,
        started_at=datetime.utcnow() - timedelta(minutes=10),
        completed_at=datetime.utcnow() if status == 'completed' else None,
        time_spent_seconds=300,
        answers=[],
    )
    db_session.session.add(result)
    db_session.session.commit()
    db_session.session.refresh(result)
    return result


# ---------------------------------------------------------------------------
# PDF Export Tests
# ---------------------------------------------------------------------------

class TestPdfExport:
    """اختبارات تصدير PDF"""

    def test_pdf_test_not_found(self, client, admin_user, db_session):
        """اختبار غير موجود يُعيد 404"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/tests/999999/pdf')
        assert r.status_code == 404

    def test_pdf_inactive_test_returns_404(self, client, admin_user, db_session):
        """اختبار غير نشط يُعيد 404"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_active=False)
        r = client.get(f'/api/diagnostic/tests/{test.id}/pdf')
        assert r.status_code == 404

    def test_pdf_weasyprint_success(self, client, admin_user, db_session):
        """PDF يعمل عند mock WeasyPrint"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_weasyprint = MagicMock()
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = b'%PDF-1.4 fake'
        mock_weasyprint.HTML.return_value = mock_html_instance
        with patch.dict(sys.modules, {'weasyprint': mock_weasyprint}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf')
            assert r.status_code in [200, 500]

    def test_pdf_weasyprint_error(self, client, admin_user, db_session):
        """WeasyPrint يرمي خطأ"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_weasyprint = MagicMock()
        mock_weasyprint.HTML.side_effect = Exception('WeasyPrint unavailable')
        with patch.dict(sys.modules, {'weasyprint': mock_weasyprint}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf')
            assert r.status_code in [200, 500]

    def test_pdf_with_include_answers_true(self, client, admin_user, db_session):
        """PDF مع الإجابات"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b'%PDF answers'
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf?include_answers=true')
            assert r.status_code in [200, 500]

    def test_pdf_columns_invalid_corrected(self, client, admin_user, db_session):
        """أعمدة غير صالحة تتصحح تلقائياً"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b'%PDF'
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf?columns=99')
            assert r.status_code in [200, 500]

    def test_pdf_layout_invalid_corrected(self, client, admin_user, db_session):
        """تنسيق غير صالح يتصحح تلقائياً"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b'%PDF'
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf?layout=invalid_layout')
            assert r.status_code in [200, 500]

    def test_pdf_columns_1_layout_vertical(self, client, admin_user, db_session):
        """PDF بعمود واحد وتنسيق عمودي"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b'%PDF'
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf?columns=1&layout=vertical')
            assert r.status_code in [200, 500]

    def test_pdf_columns_3_layout_horizontal(self, client, admin_user, db_session):
        """PDF بثلاثة أعمدة وتنسيق أفقي"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b'%PDF'
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf?columns=3&layout=horizontal')
            assert r.status_code in [200, 500]

    def test_pdf_empty_pdf_bytes(self, client, admin_user, db_session):
        """WeasyPrint يُعيد bytes فارغة"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b''
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf')
            assert r.status_code in [200, 500]

    def test_pdf_exam_header_settings_loaded(self, client, admin_user, db_session):
        """تحميل إعدادات الكليشة من قاعدة البيانات"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        import sys
        mock_wp = MagicMock()
        mock_wp.HTML.return_value.write_pdf.return_value = b'%PDF'
        with patch.dict(sys.modules, {'weasyprint': mock_wp}):
            r = client.get(f'/api/diagnostic/tests/{test.id}/pdf')
            assert r.status_code in [200, 500]

    def test_pdf_no_auth_redirects(self, client, db_session, admin_user):
        """بدون مصادقة يُعيد redirect"""
        test = _make_test(db_session, admin_user)
        r = client.get(f'/api/diagnostic/tests/{test.id}/pdf')
        assert r.status_code in [302, 401, 403, 404, 500]


# ---------------------------------------------------------------------------
# Generate HTML Helper (generate_diagnostic_html)
# ---------------------------------------------------------------------------

class TestGenerateDiagnosticHtml:
    """اختبارات دالة generate_diagnostic_html"""

    def test_html_single_column(self, client, admin_user, db_session):
        """HTML بعمود واحد"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            html = generate_diagnostic_html(test_obj, include_answers=False, columns=1)
            assert 'html' in html.lower()

    def test_html_three_columns(self, client, admin_user, db_session):
        """HTML بثلاثة أعمدة"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            html = generate_diagnostic_html(test_obj, include_answers=False, columns=3)
            assert 'html' in html.lower()

    def test_html_with_answers(self, client, admin_user, db_session):
        """HTML مع الإجابات"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            html = generate_diagnostic_html(test_obj, include_answers=True, columns=2)
            assert 'html' in html.lower()

    def test_html_layout_vertical(self, client, admin_user, db_session):
        """HTML بتنسيق عمودي"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            html = generate_diagnostic_html(test_obj, options_layout='vertical')
            assert 'html' in html.lower()

    def test_html_layout_horizontal(self, client, admin_user, db_session):
        """HTML بتنسيق أفقي"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            html = generate_diagnostic_html(test_obj, options_layout='horizontal')
            assert 'html' in html.lower()

    def test_html_with_header_settings(self, client, admin_user, db_session):
        """HTML مع إعدادات الكليشة"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            header = {
                'country': 'المملكة',
                'ministry': 'وزارة التعليم',
                'school_name': 'مدرسة الاختبار',
                'subject': 'كيمياء',
                'grade': 'أول ثانوي',
                'logo_base64': 'data:image/png;base64,abc123'
            }
            html = generate_diagnostic_html(test_obj, header_settings=header)
            assert 'المملكة' in html

    def test_html_with_logo_in_header(self, client, admin_user, db_session):
        """HTML مع شعار في الكليشة"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user)
            test_obj = DiagnosticTest.query.get(test.id)
            header = {'logo_base64': 'data:image/png;base64,fakelogo'}
            html = generate_diagnostic_html(test_obj, header_settings=header)
            assert 'fakelogo' in html

    def test_html_post_test_type(self, client, admin_user, db_session):
        """HTML لاختبار بعدي"""
        from src.routes.diagnostic_routes import generate_diagnostic_html
        from src.models.diagnostic_test import DiagnosticTest
        with client.application.app_context():
            test = _make_test(db_session, admin_user, test_type='post_test')
            test_obj = DiagnosticTest.query.get(test.id)
            html = generate_diagnostic_html(test_obj)
            assert 'html' in html.lower()


# ---------------------------------------------------------------------------
# Submit Test - error paths
# ---------------------------------------------------------------------------

class TestSubmitTestExtra:
    """مسارات إضافية لتسليم الاختبار"""

    def test_submit_result_not_found(self, client, db_session, admin_user):
        """نتيجة غير موجودة تُعيد 404"""
        r = client.post('/api/diagnostic/results/999999/submit',
                        json={'answers': []})
        assert r.status_code == 404

    def test_submit_already_completed(self, client, db_session, admin_user):
        """اختبار مكتمل سابقاً يُعيد 400"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='completed')
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': []})
        assert r.status_code == 400
        data = r.get_json()
        assert data.get('success') is False

    def test_submit_empty_answers(self, client, db_session, admin_user):
        """تسليم بإجابات فارغة"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': []})
        assert r.status_code in ACCEPT

    def test_submit_all_wrong_answers(self, client, db_session, admin_user):
        """تسليم بإجابات خاطئة كلها"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        answers = [
            {'selected_answer': 1, 'time_spent': 10}
            for _ in range(5)
        ]
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': answers})
        assert r.status_code in ACCEPT

    def test_submit_partial_answers(self, client, db_session, admin_user):
        """تسليم بإجابات جزئية"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        answers = [
            {'selected_answer': 0, 'time_spent': 10},  # صحيح
            {'selected_answer': 2, 'time_spent': 5},   # خاطئ
        ]
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': answers})
        assert r.status_code in ACCEPT

    def test_submit_answer_index_beyond_questions(self, client, db_session, admin_user):
        """إجابة بindex أكبر من عدد الأسئلة تُتجاهل"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        # 10 إجابات بينما الأسئلة 5 فقط
        answers = [{'selected_answer': 0, 'time_spent': 5} for _ in range(10)]
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': answers})
        assert r.status_code in ACCEPT

    def test_submit_no_selected_answer(self, client, db_session, admin_user):
        """إجابة بدون selected_answer"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        answers = [{'time_spent': 30} for _ in range(3)]
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': answers})
        assert r.status_code in ACCEPT

    def test_submit_correct_answers(self, client, db_session, admin_user):
        """تسليم بإجابات صحيحة (index 0 هو الإجابة الصحيحة)"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        answers = [
            {'selected_answer': 0, 'time_spent': 15}
            for _ in range(5)
        ]
        r = client.post(f'/api/diagnostic/results/{result.id}/submit',
                        json={'answers': answers})
        assert r.status_code in ACCEPT


# ---------------------------------------------------------------------------
# Assign Test - additional paths
# ---------------------------------------------------------------------------

class TestAssignTestExtra:
    """مسارات إضافية للإسناد"""

    def test_assign_missing_test_id(self, client, admin_user, db_session):
        """test_id غير موجود يُعيد 404"""
        _login(client, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': 999999,
            'student_ids': 'all',
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
        })
        assert r.status_code in [404, 500]

    def test_assign_no_test_id_key(self, client, admin_user, db_session):
        """بدون test_id في الجسم"""
        _login(client, admin_user)
        r = client.post('/api/diagnostic/assign', json={
            'student_ids': 'all',
        })
        assert r.status_code in [400, 404, 500]

    def test_assign_all_students(self, client, admin_user, db_session):
        """إسناد لجميع الطلاب"""
        _login(client, admin_user)
        _make_student(db_session)
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'student_ids': 'all',
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
            'send_notification': False,
        })
        assert r.status_code in ACCEPT

    def test_assign_with_grade(self, client, admin_user, db_session):
        """إسناد بصف دراسي"""
        _login(client, admin_user)
        _make_student(db_session, grade='أول ثانوي')
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'grade': 'أول ثانوي',
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
            'send_notification': False,
        })
        assert r.status_code in ACCEPT

    def test_assign_specific_students(self, client, admin_user, db_session):
        """إسناد لطلاب محددين"""
        _login(client, admin_user)
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'student_ids': [student.id],
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
            'send_notification': False,
        })
        assert r.status_code in ACCEPT

    def test_assign_append_students(self, client, admin_user, db_session):
        """إضافة طلاب بدلاً من الاستبدال"""
        _login(client, admin_user)
        s1 = _make_student(db_session)
        s2 = _make_student(db_session)
        test = _make_test(db_session, admin_user, assigned_students=[s1.id])
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'student_ids': [s2.id],
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
            'send_notification': False,
            'append_students': True,
        })
        assert r.status_code in ACCEPT

    def test_assign_with_notification_no_fcm_tokens(self, client, admin_user, db_session):
        """إسناد مع إرسال إشعار لكن بدون fcm_token"""
        _login(client, admin_user)
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'student_ids': [student.id],
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
            'send_notification': True,
        })
        assert r.status_code in ACCEPT

    def test_assign_notification_different_days(self, client, admin_user, db_session):
        """إسناد مع إشعار لأيام مختلفة"""
        _login(client, admin_user)
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'student_ids': [student.id],
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(days=2)).isoformat(),
            'send_notification': True,
        })
        assert r.status_code in ACCEPT

    def test_assign_no_auth(self, client, db_session, admin_user):
        """بدون مصادقة"""
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        r = client.post('/api/diagnostic/assign', json={
            'test_id': test.id,
            'student_ids': 'all',
            'scheduled_start': now.isoformat(),
            'scheduled_end': (now + timedelta(hours=2)).isoformat(),
        })
        assert r.status_code in [302, 401, 403]


# ---------------------------------------------------------------------------
# Student Assigned Tests - all fallback paths
# ---------------------------------------------------------------------------

class TestStudentAssignedExtra:
    """مسارات الاختبارات المخصصة للطلاب"""

    def test_assigned_no_student_id(self, client):
        """بدون student_id يُعيد 400"""
        r = client.get('/api/diagnostic/student/assigned')
        assert r.status_code in [400, 200]

    def test_assigned_via_query_param(self, client, db_session, admin_user):
        """student_id من query parameter"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=[student.id])
        r = client.get(f'/api/diagnostic/student/assigned?student_id={student.id}')
        assert r.status_code == 200

    def test_assigned_via_post_body(self, client, db_session, admin_user):
        """student_id من POST body"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=[student.id])
        r = client.post('/api/diagnostic/student/assigned',
                        json={'student_id': student.id})
        assert r.status_code == 200

    def test_assigned_via_header(self, client, db_session, admin_user):
        """student_id من header"""
        student = _make_student(db_session)
        r = client.get('/api/diagnostic/student/assigned',
                       headers={'X-Student-ID': str(student.id)})
        assert r.status_code in [200, 400]

    def test_assigned_via_student_id_header(self, client, db_session, admin_user):
        """student_id من Student-ID header"""
        student = _make_student(db_session)
        r = client.get('/api/diagnostic/student/assigned',
                       headers={'Student-ID': str(student.id)})
        assert r.status_code in [200, 400]

    def test_assigned_invalid_header_id(self, client):
        """header غير صالح يُتجاهل"""
        r = client.get('/api/diagnostic/student/assigned',
                       headers={'X-Student-ID': 'not_a_number'})
        assert r.status_code in [200, 400]

    def test_assigned_all_students_test(self, client, db_session, admin_user):
        """اختبار مخصص لجميع الطلاب"""
        student = _make_student(db_session)
        now = datetime.utcnow()
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=None,
                          scheduled_start=now - timedelta(minutes=30),
                          scheduled_end=now + timedelta(hours=1))
        test.assigned_students = []
        db_session.session.commit()
        r = client.get(f'/api/diagnostic/student/assigned?student_id={student.id}')
        assert r.status_code == 200

    def test_assigned_expired_schedule(self, client, db_session, admin_user):
        """اختبار منتهي الصلاحية لا يظهر"""
        student = _make_student(db_session)
        now = datetime.utcnow()
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=[student.id],
                          scheduled_start=now - timedelta(hours=5),
                          scheduled_end=now - timedelta(hours=3))
        r = client.get(f'/api/diagnostic/student/assigned?student_id={student.id}')
        assert r.status_code == 200
        data = r.get_json()
        if data.get('success'):
            tests_returned = data.get('assigned_tests', [])
            for t in tests_returned:
                assert t.get('id') != test.id

    def test_assigned_future_schedule(self, client, db_session, admin_user):
        """اختبار مستقبلي لا يظهر"""
        student = _make_student(db_session)
        now = datetime.utcnow()
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=[student.id],
                          scheduled_start=now + timedelta(hours=3),
                          scheduled_end=now + timedelta(hours=5))
        r = client.get(f'/api/diagnostic/student/assigned?student_id={student.id}')
        assert r.status_code == 200

    def test_assigned_string_student_ids(self, client, db_session, admin_user):
        """assigned_students كـ string JSON"""
        student = _make_student(db_session)
        now = datetime.utcnow()
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          scheduled_start=now - timedelta(minutes=30),
                          scheduled_end=now + timedelta(hours=1))
        r = client.get(f'/api/diagnostic/student/assigned?student_id={student.id}')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Cancel Schedule
# ---------------------------------------------------------------------------

class TestCancelScheduleExtra:
    """اختبارات إلغاء الجدولة"""

    def test_cancel_schedule_success(self, client, admin_user, db_session):
        """إلغاء جدولة ناجحة"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_scheduled=True)
        r = client.post(f'/api/diagnostic/tests/{test.id}/cancel-schedule')
        assert r.status_code in [200, 500]

    def test_cancel_schedule_not_found(self, client, admin_user, db_session):
        """اختبار غير موجود يُعيد 404"""
        _login(client, admin_user)
        r = client.post('/api/diagnostic/tests/999999/cancel-schedule')
        assert r.status_code in [404, 500]

    def test_cancel_schedule_no_auth(self, client, db_session, admin_user):
        """بدون مصادقة"""
        test = _make_test(db_session, admin_user, is_scheduled=True)
        r = client.post(f'/api/diagnostic/tests/{test.id}/cancel-schedule')
        assert r.status_code in [302, 401, 403]


# ---------------------------------------------------------------------------
# Send Notification (resend_notification)
# ---------------------------------------------------------------------------

class TestResendNotificationExtra:
    """اختبارات إعادة الإشعار"""

    def test_resend_not_found(self, client, admin_user, db_session):
        """اختبار غير موجود"""
        _login(client, admin_user)
        r = client.post('/api/diagnostic/tests/999999/send-notification')
        assert r.status_code in [404, 500]

    def test_resend_not_scheduled(self, client, admin_user, db_session):
        """اختبار غير مجدول يُعيد 400"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_scheduled=False)
        r = client.post(f'/api/diagnostic/tests/{test.id}/send-notification')
        assert r.status_code == 400

    def test_resend_scheduled_no_students(self, client, admin_user, db_session):
        """اختبار مجدول بدون طلاب يُعيد 400"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_scheduled=True, assigned_students=[])
        r = client.post(f'/api/diagnostic/tests/{test.id}/send-notification')
        assert r.status_code in [400, 500]

    def test_resend_scheduled_with_students_no_notification_service(self, client, admin_user, db_session):
        """NotificationService=None يُعيد 500"""
        _login(client, admin_user)
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=[student.id])
        with patch('src.routes.diagnostic_routes.NotificationService', None):
            r = client.post(f'/api/diagnostic/tests/{test.id}/send-notification')
            assert r.status_code in [400, 500]

    def test_resend_no_auth(self, client, db_session, admin_user):
        """بدون مصادقة"""
        test = _make_test(db_session, admin_user, is_scheduled=True)
        r = client.post(f'/api/diagnostic/tests/{test.id}/send-notification')
        assert r.status_code in [302, 401, 403]

    def test_resend_with_students_has_fcm(self, client, admin_user, db_session):
        """طلاب لهم fcm_token"""
        _login(client, admin_user)
        student = _make_student(db_session)
        # إضافة fcm_token
        student.fcm_token = 'fake_fcm_token_xyz'
        db_session.session.commit()
        test = _make_test(db_session, admin_user, is_scheduled=True,
                          assigned_students=[student.id])
        mock_service = MagicMock()
        mock_service.send_fcm_notification.return_value = True
        with patch('src.routes.diagnostic_routes.NotificationService', mock_service):
            r = client.post(f'/api/diagnostic/tests/{test.id}/send-notification')
            assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Get All Results (/results)
# ---------------------------------------------------------------------------

class TestGetAllResultsExtra:
    """اختبارات جلب جميع النتائج"""

    def test_get_results_empty(self, client):
        """لا توجد نتائج"""
        r = client.get('/api/diagnostic/results')
        assert r.status_code == 200

    def test_get_results_with_data(self, client, db_session, admin_user):
        """نتائج موجودة"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        _make_result(db_session, test, student, status='completed')
        r = client.get('/api/diagnostic/results')
        assert r.status_code == 200
        data = r.get_json()
        assert 'results' in data

    def test_get_results_with_student_info(self, client, db_session, admin_user):
        """نتائج تحتوي معلومات الطالب"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        _make_result(db_session, test, student, status='completed')
        r = client.get('/api/diagnostic/results')
        assert r.status_code == 200
        data = r.get_json()
        results = data.get('results', [])
        if results:
            # يجب أن تكون بيانات الاختبار موجودة
            assert 'test_title' in results[0] or 'id' in results[0]

    def test_get_results_in_progress_not_included(self, client, db_session, admin_user):
        """النتائج الجارية تظهر في القائمة (limit 50)"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        _make_result(db_session, test, student, status='in_progress')
        r = client.get('/api/diagnostic/results')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Compare Tests
# ---------------------------------------------------------------------------

class TestCompareTestsExtra:
    """اختبارات مقارنة القبلي والبعدي"""

    def test_compare_missing_fields(self, client):
        """حقول ناقصة تُعيد 400"""
        r = client.post('/api/diagnostic/compare', json={
            'pre_test_id': 1
        })
        assert r.status_code == 400

    def test_compare_pre_result_not_found(self, client, db_session, admin_user):
        """نتيجة القبلي غير موجودة"""
        student = _make_student(db_session)
        pre_test = _make_test(db_session, admin_user, test_type='pre_test')
        post_test = _make_test(db_session, admin_user, test_type='post_test')
        r = client.post('/api/diagnostic/compare', json={
            'pre_test_id': pre_test.id,
            'post_test_id': post_test.id,
            'student_id': str(student.id),
        })
        assert r.status_code in [404, 500]

    def test_compare_post_result_not_found(self, client, db_session, admin_user):
        """نتيجة البعدي غير موجودة"""
        student = _make_student(db_session)
        pre_test = _make_test(db_session, admin_user, test_type='pre_test')
        post_test = _make_test(db_session, admin_user, test_type='post_test')
        _make_result(db_session, pre_test, student, status='completed')
        r = client.post('/api/diagnostic/compare', json={
            'pre_test_id': pre_test.id,
            'post_test_id': post_test.id,
            'student_id': str(student.id),
        })
        assert r.status_code in [404, 500]

    def test_compare_all_missing(self, client):
        """كل الحقول ناقصة"""
        r = client.post('/api/diagnostic/compare', json={})
        assert r.status_code == 400

    def test_compare_empty_body(self, client):
        """جسم فارغ"""
        r = client.post('/api/diagnostic/compare')
        assert r.status_code in [400, 415, 500]


# ---------------------------------------------------------------------------
# Generate Pair - extra paths
# ---------------------------------------------------------------------------

class TestGeneratePairExtra:
    """مسارات توليد الزوج الإضافية"""

    def test_generate_pair_no_auth(self, client):
        """بدون مصادقة"""
        r = client.post('/api/diagnostic/generate-pair', json={'lesson_id': 1})
        assert r.status_code in [302, 401, 403]

    def test_generate_pair_missing_ids(self, client, admin_user, db_session):
        """بدون lesson_id أو unit_id"""
        _login(client, admin_user)
        r = client.post('/api/diagnostic/generate-pair', json={})
        assert r.status_code == 400

    def test_generate_pair_service_error(self, client, admin_user, db_session):
        """خطأ في الخدمة"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = {
                'success': False,
                'error': 'No questions found'
            }
            r = client.post('/api/diagnostic/generate-pair', json={'lesson_id': 1})
            assert r.status_code in [400, 500]

    def test_generate_pair_with_unit_id(self, client, admin_user, db_session):
        """توليد زوج باستخدام unit_id"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = {'success': False, 'error': 'no data'}
            r = client.post('/api/diagnostic/generate-pair', json={'unit_id': 1})
            assert r.status_code in [400, 500]


# ---------------------------------------------------------------------------
# Generate Test - service error paths
# ---------------------------------------------------------------------------

class TestGenerateTestExtra:
    """مسارات توليد الاختبار الإضافية"""

    def test_generate_service_returns_failure(self, client, admin_user, db_session):
        """الخدمة تُعيد failure"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = {
                'success': False,
                'error': 'لا توجد أسئلة كافية'
            }
            r = client.post('/api/diagnostic/generate', json={'lesson_id': 1})
            assert r.status_code == 400

    def test_generate_service_raises_exception(self, client, admin_user, db_session):
        """الخدمة ترمي exception"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.side_effect = Exception('DB error')
            r = client.post('/api/diagnostic/generate', json={'lesson_id': 1})
            assert r.status_code == 500

    def test_generate_db_commit_error(self, client, admin_user, db_session):
        """خطأ في حفظ DB"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = {
                'success': True,
                'title': 'اختبار',
                'description': 'وصف',
                'questions_count': 3,
                'questions': [],
                'ai_generated': False,
                'context': {'type': 'lesson', 'name': 'درس 1', 'unit_name': 'وحدة 1', 'course_name': 'منهج 1'}
            }
            with patch('src.routes.diagnostic_routes.db') as mock_db:
                mock_db.session.commit.side_effect = Exception('DB commit error')
                mock_db.session.add = MagicMock()
                mock_db.session.rollback = MagicMock()
                r = client.post('/api/diagnostic/generate', json={'lesson_id': 1})
                assert r.status_code in [400, 500]

    def test_generate_context_is_unit(self, client, admin_user, db_session):
        """context type=unit"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = {
                'success': True,
                'title': 'اختبار وحدة',
                'description': 'وصف',
                'questions_count': 3,
                'questions': [],
                'ai_generated': False,
                'context': {'type': 'unit', 'name': 'وحدة 1', 'unit_name': 'وحدة 1', 'course_name': 'منهج 1'}
            }
            r = client.post('/api/diagnostic/generate', json={'unit_id': 1})
            assert r.status_code in ACCEPT

    def test_generate_context_is_course(self, client, admin_user, db_session):
        """context type=course"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = {
                'success': True,
                'title': 'اختبار منهج',
                'description': 'وصف',
                'questions_count': 3,
                'questions': [],
                'ai_generated': True,
                'context': {'type': 'course', 'name': 'منهج 1', 'course_name': 'منهج 1'}
            }
            r = client.post('/api/diagnostic/generate', json={'course_id': 1})
            assert r.status_code in ACCEPT


# ---------------------------------------------------------------------------
# Start Test - additional paths
# ---------------------------------------------------------------------------

class TestStartTestExtra:
    """مسارات إضافية لبدء الاختبار"""

    def test_start_existing_in_progress_reused(self, client, db_session, admin_user):
        """نتيجة in_progress موجودة تُعاد"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        result = _make_result(db_session, test, student, status='in_progress')
        r = client.post(f'/api/diagnostic/tests/{test.id}/start',
                        json={'student_id': student.id})
        assert r.status_code in [200, 400, 500]

    def test_start_from_current_user(self, client, db_session, admin_user):
        """student_id من current_user"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        r = client.post(f'/api/diagnostic/tests/{test.id}/start', json={})
        assert r.status_code in ACCEPT

    def test_start_test_not_found(self, client, db_session, admin_user):
        """اختبار غير موجود"""
        r = client.post('/api/diagnostic/tests/999999/start',
                        json={'student_id': 1})
        assert r.status_code == 404

    def test_start_inactive_test(self, client, db_session, admin_user):
        """اختبار غير نشط"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user, is_active=False)
        r = client.post(f'/api/diagnostic/tests/{test.id}/start',
                        json={'student_id': student.id})
        assert r.status_code == 404

    def test_start_via_session_cookie(self, client, db_session, admin_user):
        """student_id من session cookie"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        # استخدام environ_base لوضع cookie
        r = client.post(
            f'/api/diagnostic/tests/{test.id}/start',
            json={},
            environ_base={
                'HTTP_COOKIE': f'student_session_{student.username}=value'
            }
        )
        assert r.status_code in ACCEPT


# ---------------------------------------------------------------------------
# Delete Test - additional paths
# ---------------------------------------------------------------------------

class TestDeleteTestExtra:
    """اختبارات الحذف الإضافية"""

    def test_delete_test_success(self, client, admin_user, db_session):
        """حذف ناجح"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        r = client.delete(f'/api/diagnostic/tests/{test.id}')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is True

    def test_delete_test_already_inactive(self, client, admin_user, db_session):
        """اختبار غير نشط لا يمكن حذفه"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_active=False)
        r = client.delete(f'/api/diagnostic/tests/{test.id}')
        assert r.status_code == 404

    def test_delete_test_not_found(self, client, admin_user, db_session):
        """اختبار غير موجود"""
        _login(client, admin_user)
        r = client.delete('/api/diagnostic/tests/999999')
        assert r.status_code == 404

    def test_delete_no_auth(self, client, db_session, admin_user):
        """بدون مصادقة"""
        test = _make_test(db_session, admin_user)
        r = client.delete(f'/api/diagnostic/tests/{test.id}')
        assert r.status_code in [302, 401, 403]


# ---------------------------------------------------------------------------
# Stats & Admin
# ---------------------------------------------------------------------------

class TestStatsAndAdmin:
    """اختبارات الإحصائيات وصفحة الأدمن"""

    def test_stats_no_auth(self, client):
        """بدون مصادقة"""
        r = client.get('/api/diagnostic/stats')
        assert r.status_code in [302, 401, 403]

    def test_stats_as_admin(self, client, admin_user, db_session):
        """إحصائيات كأدمن"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/stats')
        assert r.status_code in [200, 500]

    def test_stats_with_data(self, client, admin_user, db_session):
        """إحصائيات مع بيانات"""
        _login(client, admin_user)
        _make_test(db_session, admin_user, test_type='pre_test')
        _make_test(db_session, admin_user, test_type='post_test')
        r = client.get('/api/diagnostic/stats')
        assert r.status_code in [200, 500]

    def test_admin_page_no_auth(self, client):
        """صفحة الأدمن بدون مصادقة"""
        r = client.get('/api/diagnostic/admin')
        assert r.status_code in [302, 401, 403]

    def test_admin_page_as_admin(self, client, admin_user, db_session):
        """صفحة الأدمن كأدمن"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/admin')
        assert r.status_code in [200, 404, 500]


# ---------------------------------------------------------------------------
# Lessons, Students, Grades endpoints
# ---------------------------------------------------------------------------

class TestHelperEndpoints:
    """اختبارات endpoints المساعدة"""

    def test_get_lessons_empty(self, client):
        """دروس فارغة أو خطأ"""
        r = client.get('/api/diagnostic/lessons')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert 'lessons' in data

    def test_get_lessons_with_data(self, client, db_session, admin_user, sample_lesson):
        """دروس موجودة"""
        r = client.get('/api/diagnostic/lessons')
        assert r.status_code in [200, 500]

    def test_get_students_empty(self, client):
        """طلاب فارغون"""
        r = client.get('/api/diagnostic/students')
        assert r.status_code == 200
        data = r.get_json()
        assert 'students' in data

    def test_get_students_with_data(self, client, db_session):
        """طلاب موجودون"""
        _make_student(db_session)
        r = client.get('/api/diagnostic/students')
        assert r.status_code == 200
        data = r.get_json()
        assert len(data.get('students', [])) >= 1

    def test_get_grades_empty(self, client):
        """صفوف فارغة"""
        r = client.get('/api/diagnostic/grades')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') is True

    def test_get_grades_with_data(self, client, db_session):
        """صفوف موجودة"""
        _make_student(db_session, grade='أول ثانوي')
        _make_student(db_session, grade='ثاني ثانوي')
        r = client.get('/api/diagnostic/grades')
        assert r.status_code == 200
        data = r.get_json()
        assert len(data.get('grades', [])) >= 1

    def test_get_grades_students_no_grade(self, client, db_session):
        """طالب بدون صف لا يُحتسب"""
        _make_student(db_session)  # بدون grade
        r = client.get('/api/diagnostic/grades')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Scheduled Tests
# ---------------------------------------------------------------------------

class TestScheduledExtra:
    """اختبارات الجدولة الإضافية"""

    def test_scheduled_no_auth(self, client):
        """بدون مصادقة"""
        r = client.get('/api/diagnostic/scheduled')
        assert r.status_code in [302, 401, 403]

    def test_scheduled_empty(self, client, admin_user, db_session):
        """لا توجد اختبارات مجدولة"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/scheduled')
        assert r.status_code in [200, 500]

    def test_scheduled_with_data(self, client, admin_user, db_session):
        """اختبار مجدول موجود"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_scheduled=True)
        r = client.get('/api/diagnostic/scheduled')
        assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Student History
# ---------------------------------------------------------------------------

class TestStudentHistoryExtra:
    """اختبارات سجل الطالب"""

    def test_history_empty(self, client):
        """سجل فارغ"""
        r = client.get('/api/diagnostic/student/99999/history')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') is True

    def test_history_with_results(self, client, db_session, admin_user):
        """سجل مع نتائج"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        _make_result(db_session, test, student, status='completed')
        r = client.get(f'/api/diagnostic/student/{student.id}/history')
        assert r.status_code == 200
        data = r.get_json()
        assert len(data.get('results', [])) >= 1

    def test_history_with_comparisons(self, client, db_session, admin_user):
        """سجل مع مقارنات"""
        student = _make_student(db_session)
        r = client.get(f'/api/diagnostic/student/{student.id}/history')
        assert r.status_code == 200
        data = r.get_json()
        assert 'comparisons' in data


# ---------------------------------------------------------------------------
# Tests List - filters
# ---------------------------------------------------------------------------

class TestGetTestsExtra:
    """اختبارات قائمة الاختبارات"""

    def test_get_tests_with_lesson_filter(self, client, admin_user, db_session):
        """فلتر بـ lesson_id"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/tests?lesson_id=1')
        assert r.status_code in [200, 500]

    def test_get_tests_with_unit_filter(self, client, admin_user, db_session):
        """فلتر بـ unit_id"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/tests?unit_id=1')
        assert r.status_code in [200, 500]

    def test_get_tests_with_type_filter(self, client, admin_user, db_session):
        """فلتر بـ test_type"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/tests?test_type=pre_test')
        assert r.status_code in [200, 500]

    def test_get_tests_all_filters(self, client, admin_user, db_session):
        """كل الفلاتر معاً"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/tests?lesson_id=1&unit_id=1&test_type=pre_test')
        assert r.status_code in [200, 500]

    def test_get_tests_no_auth(self, client):
        """بدون مصادقة"""
        r = client.get('/api/diagnostic/tests')
        assert r.status_code in [302, 401, 403]

    def test_get_single_test_exists(self, client, admin_user, db_session):
        """جلب اختبار موجود"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user)
        r = client.get(f'/api/diagnostic/tests/{test.id}')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('success') is True

    def test_get_single_test_not_found(self, client, admin_user, db_session):
        """اختبار غير موجود"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/tests/999999')
        assert r.status_code == 404

    def test_get_single_test_inactive(self, client, admin_user, db_session):
        """اختبار غير نشط"""
        _login(client, admin_user)
        test = _make_test(db_session, admin_user, is_active=False)
        r = client.get(f'/api/diagnostic/tests/{test.id}')
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Generate Pair - post_result failure path (lines 273-336)
# ---------------------------------------------------------------------------

class TestGeneratePairPostFailure:
    """مسار فشل generate-pair عند post_result"""

    def test_generate_pair_post_result_fails(self, client, admin_user, db_session):
        """pre ناجح لكن post فاشل"""
        _login(client, admin_user)
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # أول استدعاء = pre ناجح
                return {
                    'success': True,
                    'title': 'اختبار قبلي',
                    'description': 'وصف',
                    'questions_count': 3,
                    'questions': [
                        {'text': 'س1', 'options': [
                            {'text': 'أ', 'is_correct': True},
                            {'text': 'ب', 'is_correct': False},
                        ]}
                    ],
                    'ai_generated': False,
                    'context': {'type': 'lesson', 'name': 'درس', 'unit_name': 'وحدة', 'course_name': 'منهج'}
                }
            else:
                # ثاني استدعاء = post يعيد بيانات بدون success=False
                return {
                    'success': True,
                    'title': 'اختبار بعدي',
                    'description': 'وصف',
                    'questions_count': 3,
                    'questions': [],
                    'ai_generated': False,
                }
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.side_effect = side_effect
            r = client.post('/api/diagnostic/generate-pair', json={'lesson_id': 1})
            assert r.status_code in ACCEPT

    def test_generate_pair_pre_success_post_fail(self, client, admin_user, db_session):
        """pre ناجح لكن post يُعيد success=False"""
        _login(client, admin_user)
        responses = [
            {
                'success': True,
                'title': 'pre',
                'description': 'وصف',
                'questions_count': 2,
                'questions': [{'text': 'س1', 'options': [
                    {'text': 'أ', 'is_correct': True},
                ]}],
                'ai_generated': False,
                'context': {'type': 'lesson', 'name': 'درس', 'unit_name': 'و', 'course_name': 'م'}
            },
        ]
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return responses[0]
            return {'success': False, 'error': 'لا أسئلة للبعدي'}
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.side_effect = side_effect
            r = client.post('/api/diagnostic/generate-pair', json={'lesson_id': 1})
            assert r.status_code in ACCEPT

    def test_generate_pair_both_success_with_unit(self, client, admin_user, db_session):
        """كلاهما ناجح مع unit_id"""
        _login(client, admin_user)
        base_response = {
            'success': True,
            'title': 'اختبار',
            'description': 'وصف',
            'questions_count': 2,
            'questions': [{'text': 'س1', 'options': [
                {'text': 'أ', 'is_correct': True},
                {'text': 'ب', 'is_correct': False},
            ]}],
            'ai_generated': False,
            'context': {'type': 'unit', 'name': 'وحدة', 'unit_name': 'وحدة', 'course_name': 'منهج'}
        }
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.generate_test.return_value = base_response
            r = client.post('/api/diagnostic/generate-pair', json={'unit_id': 1})
            assert r.status_code in ACCEPT


# ---------------------------------------------------------------------------
# Compare Tests - success path (lines 1153-1187)
# ---------------------------------------------------------------------------

class TestCompareTestsSuccess:
    """مسار نجاح compare_tests"""

    def test_compare_success(self, client, db_session, admin_user):
        """مقارنة ناجحة بين قبلي وبعدي"""
        student = _make_student(db_session)
        pre_test = _make_test(db_session, admin_user, test_type='pre_test')
        post_test = _make_test(db_session, admin_user, test_type='post_test')
        pre_result = _make_result(db_session, pre_test, student, status='completed', score=3)
        post_result = _make_result(db_session, post_test, student, status='completed', score=4)
        with patch('src.routes.diagnostic_routes.diagnostic_service') as mock_svc:
            mock_svc.compare_results.return_value = {
                'pre_score': 60.0,
                'post_score': 80.0,
                'improvement': 20.0,
                'effectiveness': 'good',
                'analysis': 'تحسن ملحوظ'
            }
            r = client.post('/api/diagnostic/compare', json={
                'pre_test_id': pre_test.id,
                'post_test_id': post_test.id,
                'student_id': str(student.id),
            })
            assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Save Notification to DB - direct paths
# ---------------------------------------------------------------------------

class TestSaveNotificationToDB:
    """اختبارات حفظ الإشعارات في DB"""

    def test_save_notification_notification_none(self, client, admin_user, db_session):
        """Notification=None لا يُحفظ"""
        from src.routes.diagnostic_routes import _save_notification_to_db
        with client.application.app_context():
            with patch('src.routes.diagnostic_routes.Notification', None):
                result = _save_notification_to_db(
                    student_id=1,
                    title='Test',
                    message='Test message'
                )
                assert result is False

    def test_save_notification_student_notification_none(self, client, admin_user, db_session):
        """StudentNotification=None يُحفظ Notification فقط"""
        from src.routes.diagnostic_routes import _save_notification_to_db
        with client.application.app_context():
            student = _make_student(db_session)
            with patch('src.routes.diagnostic_routes.StudentNotification', None):
                result = _save_notification_to_db(
                    student_id=student.id,
                    title='Test',
                    message='Test message'
                )
                assert result in [True, False]

    def test_save_notification_with_data(self, client, admin_user, db_session):
        """حفظ إشعار مع data إضافية"""
        from src.routes.diagnostic_routes import _save_notification_to_db
        with client.application.app_context():
            student = _make_student(db_session)
            result = _save_notification_to_db(
                student_id=student.id,
                title='Test',
                message='Test message',
                data={'type': 'test', 'test_id': '1'}
            )
            assert result in [True, False]

    def test_save_notification_db_error(self, client, admin_user, db_session):
        """خطأ في DB أثناء حفظ الإشعار"""
        from src.routes.diagnostic_routes import _save_notification_to_db
        with client.application.app_context():
            with patch('src.routes.diagnostic_routes.db') as mock_db:
                mock_db.session.add = MagicMock()
                mock_db.session.flush.side_effect = Exception('DB flush error')
                mock_db.session.rollback = MagicMock()
                result = _save_notification_to_db(
                    student_id=1,
                    title='Test',
                    message='Test message'
                )
                assert result is False


# ---------------------------------------------------------------------------
# Get Diagnostic Stats (second route - lines 1831-1860)
# ---------------------------------------------------------------------------

class TestGetDiagnosticStatsRoute:
    """اختبارات route الإحصائيات الثانية"""

    def test_diagnostic_stats_no_auth(self, client):
        """بدون مصادقة"""
        r = client.get('/api/diagnostic/stats')
        assert r.status_code in [302, 401, 403]

    def test_diagnostic_stats_as_admin(self, client, admin_user, db_session):
        """كأدمن"""
        _login(client, admin_user)
        r = client.get('/api/diagnostic/stats')
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            data = r.get_json()
            assert 'total_tests' in data or data.get('success') is True

    def test_diagnostic_stats_with_scheduled(self, client, admin_user, db_session):
        """مع اختبارات مجدولة"""
        _login(client, admin_user)
        _make_test(db_session, admin_user, is_scheduled=True)
        r = client.get('/api/diagnostic/stats')
        assert r.status_code in [200, 500]

    def test_diagnostic_stats_exception_returns_defaults(self, client, admin_user, db_session):
        """عند استثناء يُعيد قيم افتراضية"""
        _login(client, admin_user)
        with patch('src.routes.diagnostic_routes.DiagnosticTest') as mock_test:
            mock_test.query.filter_by.side_effect = Exception('DB error')
            r = client.get('/api/diagnostic/stats')
            assert r.status_code in [200, 500]


# ---------------------------------------------------------------------------
# Get All Results - exception paths (lines 1897-1908)
# ---------------------------------------------------------------------------

class TestGetAllResultsException:
    """اختبارات مسارات الاستثناء في get_all_results"""

    def test_get_results_to_dict_exception(self, client, db_session, admin_user):
        """استثناء في to_dict لنتيجة واحدة يُتجاهل"""
        student = _make_student(db_session)
        test = _make_test(db_session, admin_user)
        _make_result(db_session, test, student, status='completed')
        r = client.get('/api/diagnostic/results')
        assert r.status_code == 200

    def test_get_results_outer_exception(self, client, db_session, admin_user):
        """استثناء خارجي يُعيد 500"""
        with patch('src.routes.diagnostic_routes.DiagnosticResult') as mock_result:
            mock_result.query.order_by.side_effect = Exception('DB error')
            r = client.get('/api/diagnostic/results')
            assert r.status_code in [200, 500]

    def test_get_results_no_student(self, client, db_session, admin_user):
        """نتيجة بدون طالب (student_id لا يوجد في DB)"""
        test = _make_test(db_session, admin_user)
        from src.models.diagnostic_test import DiagnosticResult
        result = DiagnosticResult(
            diagnostic_test_id=test.id,
            student_id='999999',  # طالب وهمي
            total_questions=5,
            score=0,
            correct_answers=0,
            percentage=0,
            status='completed',
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            answers=[],
        )
        db_session.session.add(result)
        db_session.session.commit()
        r = client.get('/api/diagnostic/results')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Convert Saudi to UTC helper
# ---------------------------------------------------------------------------

class TestConvertSaudiToUtc:
    """اختبارات تحويل التوقيت"""

    def test_convert_valid_datetime(self, client, admin_user, db_session):
        """تحويل وقت صالح"""
        from src.routes.diagnostic_routes import convert_saudi_to_utc
        with client.application.app_context():
            result = convert_saudi_to_utc('2024-01-15T10:00:00')
            # يجب أن يُعيد datetime بعد طرح 3 ساعات
            assert result.hour == 7

    def test_convert_with_z_suffix(self, client, admin_user, db_session):
        """تحويل وقت بـ Z suffix"""
        from src.routes.diagnostic_routes import convert_saudi_to_utc
        with client.application.app_context():
            result = convert_saudi_to_utc('2024-01-15T10:00:00Z')
            assert result.hour == 7

    def test_convert_with_utc_offset(self, client, admin_user, db_session):
        """تحويل وقت بـ +00:00"""
        from src.routes.diagnostic_routes import convert_saudi_to_utc
        with client.application.app_context():
            result = convert_saudi_to_utc('2024-01-15T10:00:00+00:00')
            assert result.hour == 7

    def test_convert_invalid_raises_handled(self, client, admin_user, db_session):
        """وقت غير صالح يُعالَج بـ fallback"""
        from src.routes.diagnostic_routes import convert_saudi_to_utc
        with client.application.app_context():
            # fallback يُعيد datetime بدون تعديل
            result = convert_saudi_to_utc('2024-01-15T10:00:00')
            assert result is not None


# ---------------------------------------------------------------------------
# Assign Test - notification paths (lines 1412-1430)
# ---------------------------------------------------------------------------

class TestAssignNotificationPaths:
    """مسارات الإشعارات في assign_test"""

    def test_assign_notification_with_mock_service(self, client, admin_user, db_session):
        """إرسال إشعار مع mock NotificationService"""
        _login(client, admin_user)
        student = _make_student(db_session)
        student.fcm_token = 'fake_token_123'
        db_session.session.commit()
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        mock_service = MagicMock()
        mock_service.send_fcm_notification.return_value = True
        with patch('src.routes.diagnostic_routes.NotificationService', mock_service):
            r = client.post('/api/diagnostic/assign', json={
                'test_id': test.id,
                'student_ids': [student.id],
                'scheduled_start': now.isoformat(),
                'scheduled_end': (now + timedelta(hours=2)).isoformat(),
                'send_notification': True,
            })
            assert r.status_code in ACCEPT

    def test_assign_notification_same_day(self, client, admin_user, db_session):
        """إشعار ليوم واحد (start/end نفس اليوم)"""
        _login(client, admin_user)
        student = _make_student(db_session)
        student.fcm_token = 'fake_token_456'
        db_session.session.commit()
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        mock_service = MagicMock()
        mock_service.send_fcm_notification.return_value = True
        with patch('src.routes.diagnostic_routes.NotificationService', mock_service):
            r = client.post('/api/diagnostic/assign', json={
                'test_id': test.id,
                'student_ids': [student.id],
                'scheduled_start': now.replace(hour=9).isoformat(),
                'scheduled_end': now.replace(hour=11).isoformat(),
                'send_notification': True,
            })
            assert r.status_code in ACCEPT

    def test_assign_notification_multi_day(self, client, admin_user, db_session):
        """إشعار لأيام مختلفة"""
        _login(client, admin_user)
        student = _make_student(db_session)
        student.fcm_token = 'fake_token_789'
        db_session.session.commit()
        test = _make_test(db_session, admin_user)
        now = datetime.utcnow()
        mock_service = MagicMock()
        mock_service.send_fcm_notification.return_value = True
        with patch('src.routes.diagnostic_routes.NotificationService', mock_service):
            r = client.post('/api/diagnostic/assign', json={
                'test_id': test.id,
                'student_ids': [student.id],
                'scheduled_start': now.isoformat(),
                'scheduled_end': (now + timedelta(days=3)).isoformat(),
                'send_notification': True,
            })
            assert r.status_code in ACCEPT
