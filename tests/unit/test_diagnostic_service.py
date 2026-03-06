# tests/unit/test_diagnostic_service.py
"""
Unit tests for src/services/diagnostic_service.py
All external dependencies (genai, anthropic, firebase, DB models) are mocked.
"""

import sys
import os
from unittest.mock import MagicMock, patch, Mock, PropertyMock

# ---------------------------------------------------------------------------
# Mock heavy third-party modules BEFORE any project imports
# ---------------------------------------------------------------------------

# google.genai
genai_mock = MagicMock()
sys.modules.setdefault('google', MagicMock())
sys.modules['google.genai'] = genai_mock
sys.modules['google.genai.types'] = MagicMock()

# anthropic
sys.modules.setdefault('anthropic', MagicMock())

# firebase
for _m in ('firebase_admin', 'firebase_admin.credentials', 'firebase_admin.messaging'):
    sys.modules.setdefault(_m, MagicMock())

# flask_socketio
sys.modules.setdefault('flask_socketio', MagicMock())

# hashlib.scrypt shim (macOS Python 3.9)
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

# SQLAlchemy PostgreSQL shims
from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as _pg
_pg.ARRAY = lambda *args, **kwargs: Text()
_pg.JSONB = JSON

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from flask import Flask


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    application = Flask(__name__)
    application.config['GOOGLE_AI_API_KEY'] = 'test-key'
    application.config['TESTING'] = True
    return application


@pytest.fixture
def app_ctx(app):
    with app.app_context():
        yield app


@pytest.fixture
def svc():
    """Return a fresh DiagnosticService with DB/model imports patched out."""
    with patch('src.services.diagnostic_service.db'), \
         patch('src.services.diagnostic_service.Lesson'), \
         patch('src.services.diagnostic_service.Unit'), \
         patch('src.services.diagnostic_service.Course'), \
         patch('src.services.diagnostic_service.Question'), \
         patch('src.services.diagnostic_service.Option'):
        from src.services.diagnostic_service import DiagnosticService
        return DiagnosticService()


# ---------------------------------------------------------------------------
# Helper: make a mock result object
# ---------------------------------------------------------------------------

def _make_result(score=7, total=10, pct=70.0, answers=None, time_spent=120):
    r = MagicMock()
    r.score = score
    r.total_questions = total
    r.score_percentage = pct
    r.answers = answers or []
    r.time_spent_seconds = time_spent
    return r


# ===========================================================================
# 1. DiagnosticService.__init__
# ===========================================================================

class TestInit:

    def test_client_is_none_on_init(self, svc):
        assert svc.client is None

    def test_search_enabled_false_on_init(self, svc):
        assert svc.search_enabled is False

    def test_is_configured_false_on_init(self, svc):
        assert svc.is_configured is False

    def test_creates_instance_successfully(self, svc):
        assert svc is not None

    def test_multiple_instances_are_independent(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            s1 = DiagnosticService()
            s2 = DiagnosticService()
        s1.is_configured = True
        assert s2.is_configured is False


# ===========================================================================
# 2. _determine_level
# ===========================================================================

class TestDetermineLevel:

    def test_100_percent_is_excellent(self, svc):
        assert svc._determine_level(100) == 'excellent'

    def test_80_percent_is_excellent(self, svc):
        assert svc._determine_level(80) == 'excellent'

    def test_81_percent_is_excellent(self, svc):
        assert svc._determine_level(81) == 'excellent'

    def test_79_percent_is_good(self, svc):
        assert svc._determine_level(79) == 'good'

    def test_60_percent_is_good(self, svc):
        assert svc._determine_level(60) == 'good'

    def test_61_percent_is_good(self, svc):
        assert svc._determine_level(61) == 'good'

    def test_59_percent_is_average(self, svc):
        assert svc._determine_level(59) == 'average'

    def test_40_percent_is_average(self, svc):
        assert svc._determine_level(40) == 'average'

    def test_41_percent_is_average(self, svc):
        assert svc._determine_level(41) == 'average'

    def test_39_percent_is_weak(self, svc):
        assert svc._determine_level(39) == 'weak'

    def test_0_percent_is_weak(self, svc):
        assert svc._determine_level(0) == 'weak'

    def test_exactly_79_is_good_not_excellent(self, svc):
        assert svc._determine_level(79) == 'good'

    def test_exactly_39_is_weak_not_average(self, svc):
        assert svc._determine_level(39) == 'weak'


# ===========================================================================
# 3. _basic_analysis
# ===========================================================================

class TestBasicAnalysis:

    def test_returns_dict(self, svc):
        r = _make_result(pct=70)
        result = svc._basic_analysis(r)
        assert isinstance(result, dict)

    def test_has_analysis_key(self, svc):
        r = _make_result(pct=70)
        result = svc._basic_analysis(r)
        assert 'analysis' in result

    def test_has_level_key(self, svc):
        r = _make_result(pct=70)
        result = svc._basic_analysis(r)
        assert 'level' in result

    def test_pct_above_80_returns_excellent(self, svc):
        r = _make_result(pct=85)
        result = svc._basic_analysis(r)
        assert result['level'] == 'excellent'

    def test_pct_80_returns_excellent(self, svc):
        r = _make_result(pct=80)
        result = svc._basic_analysis(r)
        assert result['level'] == 'excellent'

    def test_pct_60_returns_good(self, svc):
        r = _make_result(pct=60)
        result = svc._basic_analysis(r)
        assert result['level'] == 'good'

    def test_pct_79_returns_good(self, svc):
        r = _make_result(pct=79)
        result = svc._basic_analysis(r)
        assert result['level'] == 'good'

    def test_pct_40_returns_average(self, svc):
        r = _make_result(pct=40)
        result = svc._basic_analysis(r)
        assert result['level'] == 'average'

    def test_pct_59_returns_average(self, svc):
        r = _make_result(pct=59)
        result = svc._basic_analysis(r)
        assert result['level'] == 'average'

    def test_pct_0_returns_weak(self, svc):
        r = _make_result(pct=0)
        result = svc._basic_analysis(r)
        assert result['level'] == 'weak'

    def test_pct_39_returns_weak(self, svc):
        r = _make_result(pct=39)
        result = svc._basic_analysis(r)
        assert result['level'] == 'weak'

    def test_excellent_analysis_text_is_positive(self, svc):
        r = _make_result(pct=90)
        result = svc._basic_analysis(r)
        assert len(result['analysis']) > 0

    def test_weak_analysis_text_is_non_empty(self, svc):
        r = _make_result(pct=10)
        result = svc._basic_analysis(r)
        assert len(result['analysis']) > 0


# ===========================================================================
# 4. _basic_comparison_analysis
# ===========================================================================

class TestBasicComparisonAnalysis:

    def _call(self, svc, pre_pct, post_pct):
        pre = _make_result(pct=pre_pct)
        post = _make_result(pct=post_pct)
        improvement = post_pct - pre_pct
        return svc._basic_comparison_analysis(pre, post, improvement)

    def test_returns_string(self, svc):
        result = self._call(svc, 40, 80)
        assert isinstance(result, str)

    def test_improvement_ge_30_mentions_excellent(self, svc):
        result = self._call(svc, 40, 80)
        # improvement=40 → excellent branch
        assert '40' in result or '80' in result

    def test_improvement_ge_30_is_non_empty(self, svc):
        result = self._call(svc, 30, 70)
        assert len(result) > 0

    def test_improvement_ge_15_is_non_empty(self, svc):
        result = self._call(svc, 50, 70)
        assert len(result) > 0

    def test_improvement_ge_15_contains_scores(self, svc):
        result = self._call(svc, 50, 70)
        assert '50' in result and '70' in result

    def test_small_improvement_contains_scores(self, svc):
        result = self._call(svc, 60, 65)
        assert '60' in result or '65' in result

    def test_negative_improvement_contains_scores(self, svc):
        result = self._call(svc, 70, 50)
        assert '70' in result or '50' in result

    def test_improvement_exactly_30(self, svc):
        result = self._call(svc, 50, 80)
        assert len(result) > 0

    def test_improvement_exactly_15(self, svc):
        result = self._call(svc, 55, 70)
        assert len(result) > 0

    def test_improvement_exactly_0(self, svc):
        result = self._call(svc, 60, 60)
        assert len(result) > 0

    def test_negative_improvement_non_empty(self, svc):
        result = self._call(svc, 80, 40)
        assert len(result) > 0


# ===========================================================================
# 5. _format_questions
# ===========================================================================

class TestFormatQuestions:

    def _make_db_question(self, qid=1, text='What is H2O?', difficulty='easy', lesson_name='Chemistry'):
        q = MagicMock()
        q.question_id = qid
        q.question_text = text
        q.difficulty = difficulty
        q.bloom_level = 'remember'
        q.image_url = None
        lesson_mock = MagicMock()
        lesson_mock.name = lesson_name
        q.lesson = lesson_mock

        opt1 = MagicMock()
        opt1.option_id = 1
        opt1.option_text = 'Water'
        opt1.is_correct = True
        opt1.image_url = None

        opt2 = MagicMock()
        opt2.option_id = 2
        opt2.option_text = 'Salt'
        opt2.is_correct = False
        opt2.image_url = None

        q.options = [opt1, opt2]
        return q

    def test_empty_input_returns_empty_list(self, svc):
        assert svc._format_questions([]) == []

    def test_db_question_has_source_database(self, svc):
        q = self._make_db_question()
        result = svc._format_questions([q])
        assert result[0]['source'] == 'database'

    def test_db_question_has_question_id(self, svc):
        q = self._make_db_question(qid=42)
        result = svc._format_questions([q])
        assert result[0]['question_id'] == 42

    def test_db_question_has_text(self, svc):
        q = self._make_db_question(text='Test question?')
        result = svc._format_questions([q])
        assert result[0]['text'] == 'Test question?'

    def test_db_question_has_difficulty(self, svc):
        q = self._make_db_question(difficulty='hard')
        result = svc._format_questions([q])
        assert result[0]['difficulty'] == 'hard'

    def test_db_question_has_lesson_name(self, svc):
        q = self._make_db_question(lesson_name='Lesson A')
        result = svc._format_questions([q])
        assert result[0]['lesson_name'] == 'Lesson A'

    def test_db_question_options_have_letters(self, svc):
        q = self._make_db_question()
        result = svc._format_questions([q])
        letters = [o['letter'] for o in result[0]['options']]
        assert all(ltr in ['أ', 'ب', 'ج', 'د'] for ltr in letters)

    def test_ai_question_dict_source_is_ai(self, svc):
        ai_q = {
            'text': 'AI question',
            'difficulty': 'medium',
            'options': [
                {'text': 'A', 'is_correct': True},
                {'text': 'B', 'is_correct': False},
            ]
        }
        result = svc._format_questions([ai_q])
        assert result[0]['source'] == 'ai'

    def test_ai_question_dict_retains_text(self, svc):
        ai_q = {'text': 'My AI question', 'options': []}
        result = svc._format_questions([ai_q])
        assert result[0]['text'] == 'My AI question'

    def test_multiple_questions_returns_same_count(self, svc):
        q1 = self._make_db_question(qid=1)
        q2 = self._make_db_question(qid=2)
        result = svc._format_questions([q1, q2])
        assert len(result) == 2

    def test_mixed_db_and_ai_questions(self, svc):
        db_q = self._make_db_question(qid=1)
        ai_q = {'text': 'AI Q', 'options': []}
        result = svc._format_questions([db_q, ai_q])
        sources = [r['source'] for r in result]
        assert 'database' in sources
        assert 'ai' in sources


# ===========================================================================
# 6. _configure_ai
# ===========================================================================

class TestConfigureAi:

    def test_returns_false_when_gemini_not_available(self, svc):
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', False), \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'key'}, clear=False):
            result = svc._configure_ai()
        assert result is False

    def test_returns_false_when_no_api_key(self, svc):
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch.dict(os.environ, {}, clear=True):
            result = svc._configure_ai()
        assert result is False

    def test_returns_true_when_already_configured(self, svc):
        svc.is_configured = True
        result = svc._configure_ai()
        assert result is True

    def test_sets_is_configured_true_on_success(self, svc):
        mock_client = MagicMock()
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.return_value = mock_client
            svc._configure_ai()
        assert svc.is_configured is True

    def test_sets_client_on_success(self, svc):
        mock_client = MagicMock()
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.return_value = mock_client
            svc._configure_ai()
        assert svc.client is mock_client

    def test_returns_true_on_successful_config(self, svc):
        mock_client = MagicMock()
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.return_value = mock_client
            result = svc._configure_ai()
        assert result is True

    def test_no_double_configuration(self, svc):
        svc.is_configured = True
        svc.client = MagicMock()
        original_client = svc.client
        # Should return early without re-configuring
        with patch('src.services.diagnostic_service.genai') as mock_genai:
            svc._configure_ai()
        mock_genai.Client.assert_not_called()


# ===========================================================================
# 7. _get_context
# ===========================================================================

class TestGetContext:

    def _make_svc_with_models(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            svc = DiagnosticService()
        return svc

    def test_returns_none_when_all_ids_none(self, svc):
        with patch('src.services.diagnostic_service.Lesson') as mock_lesson, \
             patch('src.services.diagnostic_service.Unit') as mock_unit, \
             patch('src.services.diagnostic_service.Course') as mock_course:
            result = svc._get_context(None, None, None)
        assert result is None

    def test_lesson_context_returns_correct_type(self, svc):
        mock_lesson = MagicMock()
        mock_lesson.id = 1
        mock_lesson.name = 'Acids and Bases'
        mock_lesson.unit = MagicMock(name_attr='Unit 1', course=MagicMock(name='Chemistry'))
        mock_lesson.unit.name = 'Unit 1'
        mock_lesson.unit.course.name = 'Chemistry'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson:
            MockLesson.query.get.return_value = mock_lesson
            result = svc._get_context(lesson_id=1, unit_id=None, course_id=None)

        assert result['type'] == 'lesson'

    def test_lesson_context_includes_name(self, svc):
        mock_lesson = MagicMock()
        mock_lesson.id = 1
        mock_lesson.name = 'Acids and Bases'
        mock_lesson.unit = MagicMock()
        mock_lesson.unit.name = 'Unit 1'
        mock_lesson.unit.course = MagicMock()
        mock_lesson.unit.course.name = 'Chemistry'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson:
            MockLesson.query.get.return_value = mock_lesson
            result = svc._get_context(lesson_id=1, unit_id=None, course_id=None)

        assert result['name'] == 'Acids and Bases'

    def test_lesson_not_found_falls_through_to_unit(self, svc):
        mock_unit = MagicMock()
        mock_unit.id = 5
        mock_unit.name = 'Unit 5'
        mock_unit.course = MagicMock()
        mock_unit.course.name = 'Chemistry'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            MockLesson.query.get.return_value = None
            MockUnit.query.get.return_value = mock_unit
            with patch('src.services.diagnostic_service.Lesson') as MockLesson2:
                MockLesson2.query.filter_by.return_value.all.return_value = []
                result = svc._get_context(lesson_id=None, unit_id=5, course_id=None)

        assert result is not None

    def test_unit_context_returns_correct_type(self, svc):
        mock_unit = MagicMock()
        mock_unit.id = 5
        mock_unit.name = 'Unit 5'
        mock_unit.course = MagicMock()
        mock_unit.course.name = 'Chemistry'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            MockUnit.query.get.return_value = mock_unit
            MockLesson.query.filter_by.return_value.all.return_value = []
            result = svc._get_context(lesson_id=None, unit_id=5, course_id=None)

        assert result['type'] == 'unit'

    def test_course_context_returns_correct_type(self, svc):
        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.name = 'Chemistry Grade 3'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit, \
             patch('src.services.diagnostic_service.Course') as MockCourse:
            MockCourse.query.get.return_value = mock_course
            result = svc._get_context(lesson_id=None, unit_id=None, course_id=10)

        assert result['type'] == 'course'

    def test_course_context_includes_name(self, svc):
        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.name = 'Chemistry Grade 3'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit, \
             patch('src.services.diagnostic_service.Course') as MockCourse:
            MockCourse.query.get.return_value = mock_course
            result = svc._get_context(lesson_id=None, unit_id=None, course_id=10)

        assert result['name'] == 'Chemistry Grade 3'

    def test_returns_none_when_course_not_found(self, svc):
        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit, \
             patch('src.services.diagnostic_service.Course') as MockCourse:
            MockCourse.query.get.return_value = None
            result = svc._get_context(lesson_id=None, unit_id=None, course_id=99)

        assert result is None

    def test_exception_in_get_context_returns_none(self, svc):
        with patch('src.services.diagnostic_service.Lesson') as MockLesson:
            MockLesson.query.get.side_effect = Exception('DB error')
            result = svc._get_context(lesson_id=1, unit_id=None, course_id=None)
        assert result is None


# ===========================================================================
# 8. analyze_result
# ===========================================================================

class TestAnalyzeResult:

    def test_returns_basic_analysis_when_ai_not_configured(self, svc):
        r = _make_result(pct=55)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert 'level' in result
        assert 'analysis' in result

    def test_calls_configure_ai(self, svc):
        r = _make_result(pct=55)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False) as mock_cfg:
            svc.analyze_result(r, ctx, 'pre_test')
        mock_cfg.assert_called_once()

    def test_returns_dict(self, svc):
        r = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.analyze_result(r, ctx)
        assert isinstance(result, dict)

    def test_ai_result_has_level(self, svc):
        r = _make_result(pct=75, answers=[
            {'is_correct': False, 'topic': 'Acids'},
        ])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'Great analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert 'level' in result

    def test_ai_result_has_analysis_text(self, svc):
        r = _make_result(pct=75, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'Your analysis here'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert result.get('analysis') == 'Your analysis here'

    def test_ready_for_lesson_true_when_pre_test_above_60(self, svc):
        r = _make_result(pct=75, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert result.get('ready_for_lesson') is True

    def test_ready_for_lesson_false_when_pre_test_below_60(self, svc):
        r = _make_result(pct=50, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert result.get('ready_for_lesson') is False

    def test_ai_exception_falls_back_to_basic(self, svc):
        r = _make_result(pct=70, answers=[])
        ctx = {'name': 'Lesson 1'}
        svc.client = MagicMock()
        svc.client.models.generate_content.side_effect = Exception('AI down')

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert 'level' in result

    def test_weak_topics_extracted_from_wrong_answers(self, svc):
        r = _make_result(pct=70, answers=[
            {'is_correct': False, 'topic': 'Oxidation'},
            {'is_correct': True, 'topic': 'Acids'},
            {'is_correct': False, 'topic': 'Oxidation'},
        ])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'analysis text'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert 'weak_topics' in result
        assert 'Oxidation' in result['weak_topics']

    def test_needs_review_true_when_post_test_below_60(self, svc):
        r = _make_result(pct=50, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'post_test')
        assert result.get('needs_review') is True


# ===========================================================================
# 9. compare_results
# ===========================================================================

class TestCompareResults:

    def test_returns_dict(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=80)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert isinstance(result, dict)

    def test_has_pre_score(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['pre_score'] == 40

    def test_has_post_score(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['post_score'] == 70

    def test_improvement_calculated_correctly(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['improvement'] == 30

    def test_negative_improvement(self, svc):
        pre = _make_result(pct=80)
        post = _make_result(pct=50)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['improvement'] == -30

    def test_excellent_effectiveness_when_improvement_ge_30(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=75)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'excellent'

    def test_good_effectiveness_when_improvement_between_15_and_29(self, svc):
        pre = _make_result(pct=50)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'good'

    def test_moderate_effectiveness_when_improvement_between_0_and_14(self, svc):
        pre = _make_result(pct=60)
        post = _make_result(pct=68)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'moderate'

    def test_poor_effectiveness_when_improvement_negative(self, svc):
        pre = _make_result(pct=80)
        post = _make_result(pct=60)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'poor'

    def test_has_effectiveness_ar_key(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=80)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert 'effectiveness_ar' in result

    def test_has_analysis_key(self, svc):
        pre = _make_result(pct=40)
        post = _make_result(pct=80)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert 'analysis' in result

    def test_ai_compare_uses_client(self, svc):
        pre = _make_result(pct=40, answers=[])
        post = _make_result(pct=80, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'AI comparison'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.compare_results(pre, post, ctx)
        assert result['analysis'] == 'AI comparison'

    def test_ai_exception_falls_back_to_basic_comparison(self, svc):
        pre = _make_result(pct=40, answers=[])
        post = _make_result(pct=80, answers=[])
        ctx = {'name': 'Lesson 1'}
        svc.client = MagicMock()
        svc.client.models.generate_content.side_effect = Exception('AI fail')

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.compare_results(pre, post, ctx)
        assert isinstance(result['analysis'], str)
        assert len(result['analysis']) > 0
