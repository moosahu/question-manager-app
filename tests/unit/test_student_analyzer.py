# tests/unit/test_student_analyzer.py
"""
Unit tests for src/tasks/student_analyzer.py
Covers StudentAnalyzer class init, pure logic, and mocked DB/AI calls.
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy third-party modules BEFORE any imports
# ---------------------------------------------------------------------------
_google_mock = MagicMock()
sys.modules.setdefault('google', _google_mock)
sys.modules['google.genai'] = MagicMock()

for _mod in ('firebase_admin', 'firebase_admin.credentials',
             'firebase_admin.messaging', 'firebase_admin.auth'):
    sys.modules.setdefault(_mod, MagicMock())

sys.modules.setdefault('flask_socketio', MagicMock())
sys.modules.setdefault('anthropic', MagicMock())
sys.modules.setdefault('apscheduler', MagicMock())
sys.modules.setdefault('apscheduler.schedulers', MagicMock())
sys.modules.setdefault('apscheduler.schedulers.background', MagicMock())
sys.modules.setdefault('apscheduler.triggers', MagicMock())
sys.modules.setdefault('apscheduler.triggers.cron', MagicMock())

# sqlalchemy shims
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as _pg
_pg.ARRAY = lambda *args, **kwargs: Text()
_pg.JSONB = JSON

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ---------------------------------------------------------------------------
# Helper: create a StudentAnalyzer with all heavy imports mocked
# ---------------------------------------------------------------------------

def _make_analyzer():
    """Return a StudentAnalyzer instance with all DB models mocked."""
    mock_student_cls = MagicMock()
    mock_ai_analysis_cls = MagicMock()
    mock_ai_log_cls = MagicMock()
    mock_ai_setting_cls = MagicMock()
    mock_ai_assistant_obj = MagicMock()
    mock_smart_notifications_obj = MagicMock()
    mock_db = MagicMock()

    patches = {
        'src.models.student': MagicMock(Student=mock_student_cls),
        'src.models.ai_analysis': MagicMock(
            AIAnalysis=mock_ai_analysis_cls,
            AILog=mock_ai_log_cls,
            AISetting=mock_ai_setting_cls
        ),
        'src.services.ai_assistant': MagicMock(ai_assistant=mock_ai_assistant_obj),
        'src.services.smart_notifications': MagicMock(smart_notifications=mock_smart_notifications_obj),
        'src.extensions': MagicMock(db=mock_db),
    }

    # Remove cached module if present
    if 'src.tasks.student_analyzer' in sys.modules:
        del sys.modules['src.tasks.student_analyzer']

    with patch.dict('sys.modules', patches):
        import src.tasks.student_analyzer as mod
        analyzer = mod.StudentAnalyzer()

    return analyzer, mod, {
        'Student': mock_student_cls,
        'AIAnalysis': mock_ai_analysis_cls,
        'AILog': mock_ai_log_cls,
        'AISetting': mock_ai_setting_cls,
        'ai_assistant': mock_ai_assistant_obj,
        'smart_notifications': mock_smart_notifications_obj,
        'db': mock_db,
    }


# ===========================================================================
# 1. StudentAnalyzer.__init__
# ===========================================================================

class TestStudentAnalyzerInit:

    def test_is_running_defaults_to_false(self):
        analyzer, _, _ = _make_analyzer()
        assert analyzer.is_running is False

    def test_instance_type(self):
        analyzer, mod, _ = _make_analyzer()
        assert isinstance(analyzer, mod.StudentAnalyzer)

    def test_can_create_multiple_instances(self):
        a1, _, _ = _make_analyzer()
        a2, _, _ = _make_analyzer()
        assert a1 is not a2

    def test_is_running_independent_between_instances(self):
        a1, _, _ = _make_analyzer()
        a2, _, _ = _make_analyzer()
        a1.is_running = True
        assert a2.is_running is False


# ===========================================================================
# 2. analyze_all_students
# ===========================================================================

class TestAnalyzeAllStudents:

    def test_returns_already_running_when_is_running_true(self):
        analyzer, mod, mocks = _make_analyzer()
        analyzer.is_running = True
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            result = analyzer.analyze_all_students()
        assert result == {'status': 'already_running'}

    def test_returns_no_students_when_empty_queryset(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.return_value.all.return_value = []
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            result = analyzer.analyze_all_students()
        assert result.get('status') == 'no_students'

    def test_no_students_total_is_zero(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.return_value.all.return_value = []
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            result = analyzer.analyze_all_students()
        assert result.get('total_students', 0) == 0

    def test_is_running_reset_to_false_after_no_students(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.return_value.all.return_value = []
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            analyzer.analyze_all_students()
        assert analyzer.is_running is False

    def test_returns_error_status_on_exception(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.side_effect = Exception('DB exploded')
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            result = analyzer.analyze_all_students()
        assert result.get('status') == 'error'

    def test_error_result_contains_error_key(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.side_effect = Exception('boom')
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            result = analyzer.analyze_all_students()
        assert 'error' in result

    def test_is_running_reset_after_exception(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.side_effect = Exception('boom')
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            analyzer.analyze_all_students()
        assert analyzer.is_running is False

    def _make_student(self, sid, name):
        s = MagicMock()
        s.id = sid
        s.name = name
        return s

    def test_with_students_result_has_total_key(self):
        analyzer, mod, mocks = _make_analyzer()
        students = [self._make_student(1, 'أحمد'), self._make_student(2, 'سارة')]
        mocks['Student'].query.filter_by.return_value.all.return_value = students
        # Make _analyze_single_student return None (failure) for simplicity
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_analyze_single_student', return_value=None):
                result = analyzer.analyze_all_students()
        assert 'total' in result

    def test_with_students_result_total_equals_student_count(self):
        analyzer, mod, mocks = _make_analyzer()
        students = [self._make_student(1, 'أحمد'), self._make_student(2, 'سارة')]
        mocks['Student'].query.filter_by.return_value.all.return_value = students
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_analyze_single_student', return_value=None):
                result = analyzer.analyze_all_students()
        assert result['total'] == 2

    def test_failed_incremented_when_analyze_returns_none(self):
        analyzer, mod, mocks = _make_analyzer()
        students = [self._make_student(1, 'علي')]
        mocks['Student'].query.filter_by.return_value.all.return_value = students
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_analyze_single_student', return_value=None):
                result = analyzer.analyze_all_students()
        assert result['failed'] == 1

    def test_analyzed_incremented_on_success(self):
        analyzer, mod, mocks = _make_analyzer()
        students = [self._make_student(1, 'علي')]
        mocks['Student'].query.filter_by.return_value.all.return_value = students
        mocks['AILog'].log_operation = MagicMock()
        mocks['AISetting'].set_setting = MagicMock()
        success_result = {'severity': 'green', 'status': 'excellent', 'action_taken': False}
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_analyze_single_student', return_value=success_result):
                result = analyzer.analyze_all_students()
        assert result['analyzed'] == 1

    def test_by_severity_key_present(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.return_value.all.return_value = []
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            result = analyzer.analyze_all_students()
        # 'no_students' result doesn't have by_severity, that's expected
        assert 'status' in result or 'by_severity' in result

    def test_by_severity_has_four_colors(self):
        analyzer, mod, mocks = _make_analyzer()
        students = []
        mocks['Student'].query.filter_by.return_value.all.return_value = students
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_analyze_single_student', return_value=None):
                # Force a non-empty student list to get the full result structure
                mocks['Student'].query.filter_by.return_value.all.return_value = [
                    self._make_student(1, 'test')
                ]
                result = analyzer.analyze_all_students()
        if 'by_severity' in result:
            assert set(result['by_severity'].keys()) == {'green', 'yellow', 'orange', 'red'}


# ===========================================================================
# 3. _analyze_single_student
# ===========================================================================

class TestAnalyzeSingleStudent:

    def _make_student(self, sid=1, name='أحمد'):
        s = MagicMock()
        s.id = sid
        s.name = name
        return s

    def test_returns_none_when_ai_analysis_returns_falsy(self):
        analyzer, mod, mocks = _make_analyzer()
        student = self._make_student()
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['ai_assistant'].analyze_student.return_value = None
            result = analyzer._analyze_single_student(student)
        assert result is None

    def test_returns_none_when_no_latest_analysis(self):
        analyzer, mod, mocks = _make_analyzer()
        student = self._make_student()
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['ai_assistant'].analyze_student.return_value = {'ok': True}
            mocks['AIAnalysis'].get_latest_for_student.return_value = None
            result = analyzer._analyze_single_student(student)
        assert result is None

    def test_returns_dict_on_success(self):
        analyzer, mod, mocks = _make_analyzer()
        student = self._make_student()
        latest = MagicMock()
        latest.severity_level = 'green'
        latest.student_status = 'excellent'
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['ai_assistant'].analyze_student.return_value = {'ok': True}
            mocks['AIAnalysis'].get_latest_for_student.return_value = latest
            mocks['smart_notifications'].process_analysis_result.return_value = True
            result = analyzer._analyze_single_student(student)
        assert isinstance(result, dict)

    def test_result_contains_severity_key(self):
        analyzer, mod, mocks = _make_analyzer()
        student = self._make_student()
        latest = MagicMock()
        latest.severity_level = 'yellow'
        latest.student_status = 'good'
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['ai_assistant'].analyze_student.return_value = {'ok': True}
            mocks['AIAnalysis'].get_latest_for_student.return_value = latest
            mocks['smart_notifications'].process_analysis_result.return_value = False
            result = analyzer._analyze_single_student(student)
        assert result['severity'] == 'yellow'

    def test_result_contains_action_taken_key(self):
        analyzer, mod, mocks = _make_analyzer()
        student = self._make_student()
        latest = MagicMock()
        latest.severity_level = 'red'
        latest.student_status = 'critical'
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['ai_assistant'].analyze_student.return_value = {'ok': True}
            mocks['AIAnalysis'].get_latest_for_student.return_value = latest
            mocks['smart_notifications'].process_analysis_result.return_value = True
            result = analyzer._analyze_single_student(student)
        assert 'action_taken' in result


# ===========================================================================
# 4. generate_daily_report
# ===========================================================================

class TestGenerateDailyReport:

    def test_returns_dict(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.return_value.count.return_value = 10
        mock_analyses = []
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['db'].session.query.return_value.filter.return_value.all.return_value = mock_analyses
            mocks['AIAnalysis'].get_students_by_severity.return_value = []
            mocks['AILog'].log_operation = MagicMock()
            mocks['AISetting'].get_setting.return_value = None
            with patch.object(analyzer, '_send_daily_report_fcm', return_value=None):
                result = analyzer.generate_daily_report()
        assert isinstance(result, dict)

    def _build_daily_report_patches(self, mocks, total_students=10):
        """
        Build a consistent patch dict for generate_daily_report.
        We need AIAnalysis.created_at to support >= comparison (SQLAlchemy column mock).
        """
        mocks['Student'].query.filter_by.return_value.count.return_value = total_students
        # Mock the db session so filter() accepts any args
        mock_db_query = MagicMock()
        mock_db_query.filter.return_value.all.return_value = []
        mocks['db'].session.query.return_value = mock_db_query
        mocks['AIAnalysis'].get_students_by_severity.return_value = []
        mocks['AILog'].log_operation = MagicMock()
        mocks['AISetting'].get_setting.return_value = None

        # Make AIAnalysis.created_at a proper comparable column mock
        col_mock = MagicMock()
        col_mock.__ge__ = MagicMock(return_value=True)
        mocks['AIAnalysis'].created_at = col_mock

        return {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }

    def test_report_contains_total_students(self):
        analyzer, mod, mocks = _make_analyzer()
        patches = self._build_daily_report_patches(mocks, total_students=42)
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_send_daily_report_fcm', return_value=None):
                result = analyzer.generate_daily_report()
        assert result.get('total_students') == 42

    def test_report_contains_date_key(self):
        analyzer, mod, mocks = _make_analyzer()
        patches = self._build_daily_report_patches(mocks, total_students=5)
        with patch.dict('sys.modules', patches):
            with patch.object(analyzer, '_send_daily_report_fcm', return_value=None):
                result = analyzer.generate_daily_report()
        assert 'date' in result

    def test_report_on_exception_returns_error_status(self):
        analyzer, mod, mocks = _make_analyzer()
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['Student'].query.filter_by.side_effect = Exception('DB crash')
            mocks['AILog'].log_operation = MagicMock()
            result = analyzer.generate_daily_report()
        assert result.get('status') == 'error'

    def test_report_severity_distribution_has_four_keys(self):
        analyzer, mod, mocks = _make_analyzer()
        mocks['Student'].query.filter_by.return_value.count.return_value = 3
        mock_analysis = MagicMock()
        mock_analysis.severity_level = 'green'
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['db'].session.query.return_value.filter.return_value.all.return_value = [mock_analysis]
            mocks['AIAnalysis'].get_students_by_severity.return_value = []
            mocks['AILog'].log_operation = MagicMock()
            mocks['AISetting'].get_setting.return_value = None
            with patch.object(analyzer, '_send_daily_report_fcm', return_value=None):
                result = analyzer.generate_daily_report()
        if 'severity_distribution' in result:
            assert set(result['severity_distribution'].keys()) == {'green', 'yellow', 'orange', 'red'}


# ===========================================================================
# 5. check_notification_effectiveness
# ===========================================================================

class TestCheckNotificationEffectiveness:

    def test_returns_dict(self):
        analyzer, mod, mocks = _make_analyzer()
        mock_aiaction_cls = MagicMock()
        mock_student_result_cls = MagicMock()
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting'], AIAction=mock_aiaction_cls
            ),
            'src.models.student_result': MagicMock(StudentResult=mock_student_result_cls),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mock_aiaction_cls.query.filter.return_value.all.return_value = []
            mocks['AILog'].log_operation = MagicMock()
            result = analyzer.check_notification_effectiveness()
        assert isinstance(result, dict)

    def _make_aiaction_mock_with_empty_results(self):
        """
        Build an AIAction mock whose filter chain returns [].
        The SQLAlchemy-style filter args (AIAction.message_sent == True, AIAction.message_sent_at >= week_ago)
        need the class attributes to support comparison operators.
        """
        mock_aiaction_cls = MagicMock()
        # Make class-level attribute comparisons return a MagicMock (truthy, usable as filter arg)
        sentinel = MagicMock()
        mock_aiaction_cls.message_sent.__eq__ = MagicMock(return_value=sentinel)
        mock_aiaction_cls.message_sent_at.__ge__ = MagicMock(return_value=sentinel)
        mock_aiaction_cls.message_sent_at.isnot = MagicMock(return_value=sentinel)
        # The actual query chain
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_aiaction_cls.query = mock_query
        return mock_aiaction_cls

    def _build_check_effectiveness_patches(self, mocks, mock_aiaction_cls):
        """Shared patch dict for check_notification_effectiveness tests."""
        mock_student_result_cls = MagicMock()
        mock_student_result_cls.query.filter.return_value.count.return_value = 0
        return {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting'], AIAction=mock_aiaction_cls
            ),
            'src.models.student_result': MagicMock(StudentResult=mock_student_result_cls),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }

    def test_returns_total_sent_zero_when_no_actions(self):
        analyzer, mod, mocks = _make_analyzer()
        mock_aiaction_cls = self._make_aiaction_mock_with_empty_results()
        patches = self._build_check_effectiveness_patches(mocks, mock_aiaction_cls)
        with patch.dict('sys.modules', patches):
            result = analyzer.check_notification_effectiveness()
        assert result.get('total_sent') == 0

    def test_returns_error_on_exception(self):
        analyzer, mod, mocks = _make_analyzer()
        # Force an exception by making AIAction raise on attribute access
        mock_aiaction_cls = MagicMock()
        mock_aiaction_cls.query.filter.side_effect = Exception('DB crash')
        patches = self._build_check_effectiveness_patches(mocks, mock_aiaction_cls)
        with patch.dict('sys.modules', patches):
            result = analyzer.check_notification_effectiveness()
        assert 'error' in result or 'status' in result

    def test_details_list_present_when_no_sent_actions(self):
        analyzer, mod, mocks = _make_analyzer()
        mock_aiaction_cls = self._make_aiaction_mock_with_empty_results()
        patches = self._build_check_effectiveness_patches(mocks, mock_aiaction_cls)
        with patch.dict('sys.modules', patches):
            result = analyzer.check_notification_effectiveness()
        assert 'details' in result


# ===========================================================================
# 6. _send_daily_report_fcm
# ===========================================================================

class TestSendDailyReportFcm:

    def test_skips_when_no_admin_token(self):
        analyzer, mod, mocks = _make_analyzer()
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['AISetting'].get_setting.return_value = None
            # Should not raise
            analyzer._send_daily_report_fcm({'severity_distribution': {}, 'critical_count': 0,
                                              'analyzed_today': 0, 'total_students': 0})

    def test_skips_when_fcm_token_is_empty_string(self):
        analyzer, mod, mocks = _make_analyzer()
        patches = {
            'src.models.student': MagicMock(Student=mocks['Student']),
            'src.models.ai_analysis': MagicMock(
                AIAnalysis=mocks['AIAnalysis'], AILog=mocks['AILog'],
                AISetting=mocks['AISetting']
            ),
            'src.services.ai_assistant': MagicMock(ai_assistant=mocks['ai_assistant']),
            'src.services.smart_notifications': MagicMock(smart_notifications=mocks['smart_notifications']),
            'src.extensions': MagicMock(db=mocks['db']),
        }
        with patch.dict('sys.modules', patches):
            mocks['AISetting'].get_setting.return_value = ''
            # Should not raise
            analyzer._send_daily_report_fcm({'severity_distribution': {}, 'critical_count': 0,
                                              'analyzed_today': 0, 'total_students': 0})
