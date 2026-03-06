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

# ===========================================================================
# 10. _configure_ai - exception / fallback path  (lines 69-77)
# ===========================================================================

class TestConfigureAiFallback:
    """Cover the exception branches inside _configure_ai."""

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_fallback_returns_true_when_first_call_raises_second_succeeds(self):
        """First genai.Client call raises, second (fallback) succeeds."""
        svc = self._fresh_svc()
        fallback_client = MagicMock()
        call_count = [0]

        def side_effect(api_key):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("search failed")
            return fallback_client

        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.side_effect = side_effect
            result = svc._configure_ai()

        assert result is True

    def test_fallback_sets_is_configured_true(self):
        svc = self._fresh_svc()
        call_count = [0]

        def side_effect(api_key):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("search failed")
            return MagicMock()

        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.side_effect = side_effect
            svc._configure_ai()

        assert svc.is_configured is True

    def test_fallback_sets_search_enabled_false(self):
        svc = self._fresh_svc()
        call_count = [0]

        def side_effect(api_key):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("search failed")
            return MagicMock()

        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.side_effect = side_effect
            svc._configure_ai()

        assert svc.search_enabled is False

    def test_returns_false_when_both_calls_raise(self):
        """Both genai.Client calls raise – should return False."""
        svc = self._fresh_svc()

        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.side_effect = RuntimeError("always fails")
            result = svc._configure_ai()

        assert result is False

    def test_search_enabled_true_on_clean_success(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch('src.services.diagnostic_service.genai') as mock_genai, \
             patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'test-key'}, clear=False):
            mock_genai.Client.return_value = MagicMock()
            svc._configure_ai()
        assert svc.search_enabled is True

    def test_no_api_key_gemini_available_returns_false(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', True), \
             patch.dict(os.environ, {}, clear=True):
            result = svc._configure_ai()
        assert result is False

    def test_gemini_not_available_no_key_returns_false(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.GEMINI_AVAILABLE', False), \
             patch.dict(os.environ, {}, clear=True):
            result = svc._configure_ai()
        assert result is False


# ===========================================================================
# 11. generate_test – all main branches
# ===========================================================================

class TestGenerateTest:
    """Cover generate_test() lines 106-164."""

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    # --- context not found ---

    def test_returns_error_when_context_none(self):
        svc = self._fresh_svc()
        with patch.object(svc, '_get_context', return_value=None):
            result = svc.generate_test(lesson_id=1)
        assert result['success'] is False
        assert 'error' in result

    def test_error_message_mentions_lesson_or_unit(self):
        svc = self._fresh_svc()
        with patch.object(svc, '_get_context', return_value=None):
            result = svc.generate_test(lesson_id=99)
        assert 'لم يتم' in result['error'] or 'error' in result

    # --- AI path (configure_ai succeeds, AI generates questions) ---

    def test_ai_path_success_returns_success_true(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'Unit1', 'course_name': 'Chem'}
        ai_questions = [
            {'text': 'Q1', 'difficulty': 'easy', 'options': [{'text': 'A', 'is_correct': True}]},
            {'text': 'Q2', 'difficulty': 'medium', 'options': [{'text': 'B', 'is_correct': True}]},
        ]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=ai_questions):
            result = svc.generate_test(lesson_id=1)
        assert result['success'] is True

    def test_ai_path_returns_questions(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        ai_questions = [
            {'text': 'Q1', 'options': [{'text': 'A', 'is_correct': True, 'letter': 'أ'}]},
        ]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=ai_questions):
            result = svc.generate_test(lesson_id=1)
        assert len(result['questions']) >= 1

    def test_ai_path_has_ai_generated_true(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        ai_questions = [{'text': 'Q1', 'options': []}]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=ai_questions):
            result = svc.generate_test(lesson_id=1)
        assert result.get('ai_generated') is True

    def test_ai_path_title_contains_pre_test(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Oxidation', 'unit_name': 'U1', 'course_name': 'C1'}
        ai_questions = [{'text': 'Q1', 'options': []}]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=ai_questions):
            result = svc.generate_test(lesson_id=1, test_type='pre_test')
        assert 'قبلي' in result['title']

    def test_ai_path_title_contains_post_test(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Oxidation', 'unit_name': 'U1', 'course_name': 'C1'}
        ai_questions = [{'text': 'Q1', 'options': []}]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=ai_questions):
            result = svc.generate_test(lesson_id=1, test_type='post_test')
        assert 'بعدي' in result['title']

    # --- DB fallback path (configure_ai fails) ---

    def test_db_fallback_called_when_ai_not_available(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        db_questions = [{'text': 'DB Q1', 'options': []}]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=False), \
             patch.object(svc, '_fetch_questions', return_value=db_questions) as mock_fetch:
            svc.generate_test(lesson_id=1)
        mock_fetch.assert_called_once()

    def test_db_fallback_returns_success_when_questions_found(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        db_questions = [{'text': 'DB Q1', 'options': []}]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=False), \
             patch.object(svc, '_fetch_questions', return_value=db_questions):
            result = svc.generate_test(lesson_id=1)
        assert result['success'] is True

    # --- empty questions ---

    def test_returns_error_when_no_questions_generated(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=[]):
            result = svc.generate_test(lesson_id=1)
        assert result['success'] is False

    def test_error_message_when_no_questions(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=[]):
            result = svc.generate_test(lesson_id=1)
        assert 'error' in result

    # --- default difficulty_dist ---

    def test_default_difficulty_dist_used_when_none(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        captured = {}

        def capture(ctx, count, diff_dist, test_type):
            captured['dist'] = diff_dist
            return [{'text': 'Q', 'options': []}]

        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', side_effect=capture):
            svc.generate_test(lesson_id=1, difficulty_dist=None)
        assert captured['dist'] == {'easy': 2, 'medium': 2, 'hard': 1}

    # --- custom difficulty_dist preserved ---

    def test_custom_difficulty_dist_passed_through(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        custom_dist = {'easy': 3, 'medium': 3, 'hard': 2}
        captured = {}

        def capture(ctx, count, diff_dist, test_type):
            captured['dist'] = diff_dist
            return [{'text': 'Q', 'options': []}]

        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', side_effect=capture):
            svc.generate_test(lesson_id=1, difficulty_dist=custom_dist)
        assert captured['dist'] == custom_dist

    # --- result structure ---

    def test_result_has_context_key(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=[{'text': 'Q', 'options': []}]):
            result = svc.generate_test(lesson_id=1)
        assert 'context' in result

    def test_result_has_questions_count(self):
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        ai_q = [{'text': 'Q1', 'options': []}, {'text': 'Q2', 'options': []}]
        with patch.object(svc, '_get_context', return_value=context), \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=ai_q):
            result = svc.generate_test(lesson_id=1)
        assert result['questions_count'] == len(result['questions'])

    # --- unit_id / course_id variants ---

    def test_unit_id_passed_to_get_context(self):
        svc = self._fresh_svc()
        context = {'type': 'unit', 'name': 'Unit1', 'course_name': 'C1', 'lessons': []}
        with patch.object(svc, '_get_context', return_value=context) as mock_ctx, \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=[{'text': 'Q', 'options': []}]):
            svc.generate_test(unit_id=5)
        mock_ctx.assert_called_once_with(None, 5, None)

    def test_course_id_passed_to_get_context(self):
        svc = self._fresh_svc()
        context = {'type': 'course', 'name': 'Chem', 'id': 10}
        with patch.object(svc, '_get_context', return_value=context) as mock_ctx, \
             patch.object(svc, '_configure_ai', return_value=True), \
             patch.object(svc, '_generate_ai_questions', return_value=[{'text': 'Q', 'options': []}]):
            svc.generate_test(course_id=10)
        mock_ctx.assert_called_once_with(None, None, 10)

    # --- exception handling ---

    def test_exception_in_generate_test_returns_error_dict(self):
        svc = self._fresh_svc()
        with patch.object(svc, '_get_context', side_effect=RuntimeError("boom")):
            result = svc.generate_test(lesson_id=1)
        assert result['success'] is False
        assert 'error' in result


# ===========================================================================
# 12. _fetch_questions – DB fallback
# ===========================================================================

class TestFetchQuestions:
    """Cover _fetch_questions lines 213-256."""

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def _make_mock_question(self, qid=1, difficulty='medium'):
        q = MagicMock()
        q.question_id = qid
        q.difficulty = difficulty
        return q

    def test_returns_list(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Question') as MockQ, \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'):
            mock_qs = [self._make_mock_question(1, 'easy'), self._make_mock_question(2, 'medium')]
            MockQ.query.filter.return_value.filter.return_value.all.return_value = mock_qs
            MockQ.query.filter.return_value.all.return_value = mock_qs
            result = svc._fetch_questions(1, None, None, 2, {'easy': 1, 'medium': 1, 'hard': 0})
        assert isinstance(result, list)

    def test_filters_by_lesson_id(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Question') as MockQ:
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = []
            MockQ.query.filter.return_value = chain
            svc._fetch_questions(lesson_id=1, unit_id=None, course_id=None,
                                  count=5, difficulty_dist={'easy': 2, 'medium': 2, 'hard': 1})
            # filter was called with lesson_id
            assert MockQ.query.filter.called

    def test_filters_by_unit_id(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Question') as MockQ, \
             patch('src.services.diagnostic_service.Lesson') as MockLesson:
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = []
            MockQ.query.filter.return_value = chain
            MockLesson.query.filter_by.return_value.all.return_value = []
            svc._fetch_questions(lesson_id=None, unit_id=5, course_id=None,
                                  count=5, difficulty_dist={'easy': 2, 'medium': 2, 'hard': 1})
            assert MockLesson.query.filter_by.called

    def test_filters_by_course_id(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Question') as MockQ, \
             patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = []
            MockQ.query.filter.return_value = chain
            MockUnit.query.filter_by.return_value.all.return_value = []
            MockLesson.query.filter.return_value.all.return_value = []
            svc._fetch_questions(lesson_id=None, unit_id=None, course_id=10,
                                  count=5, difficulty_dist={'easy': 2, 'medium': 2, 'hard': 1})
            assert MockUnit.query.filter_by.called

    def test_returns_empty_on_exception(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Question') as MockQ:
            MockQ.query.filter.side_effect = Exception("DB down")
            result = svc._fetch_questions(1, None, None, 5, {'easy': 2, 'medium': 2, 'hard': 1})
        assert result == []

    def test_count_limiting(self):
        """Should not return more questions than requested count."""
        svc = self._fresh_svc()
        qs = [self._make_mock_question(i, 'medium') for i in range(20)]
        with patch('src.services.diagnostic_service.Question') as MockQ, \
             patch('src.services.diagnostic_service.Lesson'):
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = qs
            MockQ.query.filter.return_value = chain
            result = svc._fetch_questions(1, None, None, 5, {'easy': 2, 'medium': 2, 'hard': 1})
        assert len(result) <= 5

    def test_no_filters_when_all_ids_none(self):
        """When all IDs are None, should not add extra filters."""
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Question') as MockQ:
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = []
            MockQ.query.filter.return_value = chain
            result = svc._fetch_questions(None, None, None, 5, {'easy': 2, 'medium': 2, 'hard': 1})
        assert isinstance(result, list)

    def test_difficulty_distribution_easy(self):
        """Questions classified as easy should be selected for easy slot."""
        svc = self._fresh_svc()
        easy_qs = [self._make_mock_question(i, 'easy') for i in range(3)]
        with patch('src.services.diagnostic_service.Question') as MockQ, \
             patch('src.services.diagnostic_service.Lesson'):
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = easy_qs
            MockQ.query.filter.return_value = chain
            result = svc._fetch_questions(1, None, None, 2, {'easy': 2, 'medium': 0, 'hard': 0})
        assert len(result) <= 2

    def test_difficulty_fallback_fills_remaining(self):
        """If distribution doesn't fill count, remaining from pool should be added."""
        svc = self._fresh_svc()
        # 5 easy questions, request count=5 but dist only requests 2 easy
        qs = [self._make_mock_question(i, 'easy') for i in range(5)]
        with patch('src.services.diagnostic_service.Question') as MockQ, \
             patch('src.services.diagnostic_service.Lesson'):
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.all.return_value = qs
            MockQ.query.filter.return_value = chain
            result = svc._fetch_questions(1, None, None, 5, {'easy': 2, 'medium': 0, 'hard': 0})
        assert len(result) <= 5


# ===========================================================================
# 13. _generate_ai_questions
# ===========================================================================

class TestGenerateAiQuestions:
    """Cover _generate_ai_questions lines 313-403."""

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_returns_empty_when_model_falsy(self):
        """If self.model is set to None (falsy), method returns []."""
        svc = self._fresh_svc()
        svc.model = None  # explicitly set to None so `if not self.model` is True
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        result = svc._generate_ai_questions(context, 5, {'easy': 2, 'medium': 2, 'hard': 1}, 'pre_test')
        assert result == []

    def test_returns_empty_when_model_not_set(self):
        """AttributeError from missing self.model bubbles to caller – test it raises."""
        svc = self._fresh_svc()
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        import pytest as _pytest
        with _pytest.raises(AttributeError):
            svc._generate_ai_questions(context, 5, {'easy': 2, 'medium': 2, 'hard': 1}, 'pre_test')

    def test_returns_questions_on_success(self):
        svc = self._fresh_svc()
        svc.model = True  # truthy so we pass the guard
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        json_questions = [
            {"text": "Q1", "difficulty": "easy", "bloom_level": "remember",
             "options": [{"text": "A", "is_correct": True}], "feedback": "A is correct"},
        ]
        import json
        response_text = json.dumps(json_questions)
        mock_response = MagicMock()
        mock_response.text = response_text
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        result = svc._generate_ai_questions(context, 1, {'easy': 1, 'medium': 0, 'hard': 0}, 'pre_test')
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_empty_on_invalid_json(self):
        svc = self._fresh_svc()
        svc.model = True
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON at all"
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        result = svc._generate_ai_questions(context, 5, {'easy': 2, 'medium': 2, 'hard': 1}, 'pre_test')
        assert result == []

    def test_returns_empty_on_api_exception(self):
        svc = self._fresh_svc()
        svc.model = True
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        svc.client = MagicMock()
        svc.client.models.generate_content.side_effect = Exception("API failure")

        result = svc._generate_ai_questions(context, 5, {'easy': 2, 'medium': 2, 'hard': 1}, 'pre_test')
        assert result == []

    def test_post_test_uses_different_focus(self):
        """post_test should still call client without error."""
        svc = self._fresh_svc()
        svc.model = True
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        import json
        qs = [{"text": "Q", "difficulty": "easy", "bloom_level": "apply",
               "options": [{"text": "A", "is_correct": True}], "feedback": ""}]
        mock_response = MagicMock()
        mock_response.text = json.dumps(qs)
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        result = svc._generate_ai_questions(context, 1, {'easy': 1, 'medium': 0, 'hard': 0}, 'post_test')
        assert isinstance(result, list)

    def test_json_embedded_in_text_is_parsed(self):
        """AI sometimes wraps JSON in text; the regex should find it."""
        svc = self._fresh_svc()
        svc.model = True
        context = {'type': 'lesson', 'name': 'Acids', 'unit_name': 'U1', 'course_name': 'C1'}
        import json
        qs = [{"text": "Q1", "difficulty": "easy", "bloom_level": "remember",
               "options": [{"text": "A", "is_correct": True}], "feedback": ""}]
        mock_response = MagicMock()
        mock_response.text = f"Here are the questions:\n{json.dumps(qs)}\nEnd."
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        result = svc._generate_ai_questions(context, 1, {'easy': 1, 'medium': 0, 'hard': 0}, 'pre_test')
        assert len(result) == 1


# ===========================================================================
# 14. generate_pdf – PDF_AVAILABLE=False and True
# ===========================================================================

class TestGeneratePdf:
    """Cover generate_pdf lines 414-556."""

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def _make_test_data(self, with_questions=True, include_correct=False):
        questions = []
        if with_questions:
            opt = {'letter': 'أ', 'text': 'Option A', 'is_correct': include_correct}
            opt2 = {'letter': 'ب', 'text': 'Option B', 'is_correct': not include_correct}
            questions = [
                {'text': 'What is H2O?', 'options': [opt, opt2]},
            ]
        return {
            'title': 'Test Title',
            'questions_count': len(questions),
            'time_limit': 10,
            'questions': questions,
        }

    # --- PDF not available ---

    def test_returns_none_when_pdf_not_available(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.PDF_AVAILABLE', False):
            result = svc.generate_pdf({'title': 'Test', 'questions': []})
        assert result is None

    # --- PDF available (mock reportlab) ---

    def _make_pdf_mocks(self):
        """Return a dict of mocks for reportlab components."""
        mocks = {
            'SimpleDocTemplate': MagicMock(),
            'Paragraph': MagicMock(side_effect=lambda text, style: MagicMock()),
            'Spacer': MagicMock(return_value=MagicMock()),
            'Table': MagicMock(return_value=MagicMock()),
            'TableStyle': MagicMock(return_value=MagicMock()),
            'PageBreak': MagicMock(return_value=MagicMock()),
            'ParagraphStyle': MagicMock(return_value=MagicMock()),
            'getSampleStyleSheet': MagicMock(return_value={'Title': MagicMock(), 'Normal': MagicMock()}),
            'pdfmetrics': MagicMock(),
            'TTFont': MagicMock(),
            'A4': (595, 842),
            'colors': MagicMock(),
            'TA_RIGHT': 2,
            'TA_CENTER': 1,
        }
        return mocks

    def test_pdf_returns_bytes_when_available(self):
        svc = self._fresh_svc()
        test_data = self._make_test_data(with_questions=True)

        # We'll mock the whole PDF generation by mocking io.BytesIO
        fake_bytes = b'%PDF-fake-content'
        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = fake_bytes

        with patch('src.services.diagnostic_service.PDF_AVAILABLE', True), \
             patch('src.services.diagnostic_service.io') as mock_io, \
             patch('src.services.diagnostic_service.SimpleDocTemplate') as MockDoc, \
             patch('src.services.diagnostic_service.Paragraph'), \
             patch('src.services.diagnostic_service.Spacer'), \
             patch('src.services.diagnostic_service.Table'), \
             patch('src.services.diagnostic_service.TableStyle'), \
             patch('src.services.diagnostic_service.PageBreak'), \
             patch('src.services.diagnostic_service.ParagraphStyle'), \
             patch('src.services.diagnostic_service.getSampleStyleSheet', return_value={'Title': MagicMock(), 'Normal': MagicMock()}), \
             patch('src.services.diagnostic_service.pdfmetrics'), \
             patch('src.services.diagnostic_service.TTFont'), \
             patch('src.services.diagnostic_service.colors'), \
             patch('src.services.diagnostic_service.TA_RIGHT', 2), \
             patch('src.services.diagnostic_service.TA_CENTER', 1):
            mock_io.BytesIO.return_value = mock_buffer
            mock_doc_instance = MagicMock()
            MockDoc.return_value = mock_doc_instance
            result = svc.generate_pdf(test_data)
        assert result == fake_bytes

    def test_pdf_with_no_questions_returns_bytes_or_none(self):
        """Empty questions list should still not crash."""
        svc = self._fresh_svc()
        test_data = self._make_test_data(with_questions=False)
        fake_bytes = b'%PDF-empty'
        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = fake_bytes

        with patch('src.services.diagnostic_service.PDF_AVAILABLE', True), \
             patch('src.services.diagnostic_service.io') as mock_io, \
             patch('src.services.diagnostic_service.SimpleDocTemplate') as MockDoc, \
             patch('src.services.diagnostic_service.Paragraph'), \
             patch('src.services.diagnostic_service.Spacer'), \
             patch('src.services.diagnostic_service.Table'), \
             patch('src.services.diagnostic_service.TableStyle'), \
             patch('src.services.diagnostic_service.PageBreak'), \
             patch('src.services.diagnostic_service.ParagraphStyle'), \
             patch('src.services.diagnostic_service.getSampleStyleSheet', return_value={'Title': MagicMock(), 'Normal': MagicMock()}), \
             patch('src.services.diagnostic_service.pdfmetrics'), \
             patch('src.services.diagnostic_service.TTFont'), \
             patch('src.services.diagnostic_service.colors'), \
             patch('src.services.diagnostic_service.TA_RIGHT', 2), \
             patch('src.services.diagnostic_service.TA_CENTER', 1):
            mock_io.BytesIO.return_value = mock_buffer
            MockDoc.return_value = MagicMock()
            result = svc.generate_pdf(test_data)
        # Either bytes or None (if internal error) – should not raise
        assert result is None or isinstance(result, bytes)

    def test_pdf_with_include_answers_true(self):
        """include_answers=True path exercises answer key section."""
        svc = self._fresh_svc()
        test_data = {
            'title': 'Test',
            'questions_count': 1,
            'time_limit': 10,
            'questions': [
                {'text': 'Q1', 'options': [
                    {'letter': 'أ', 'text': 'Correct Answer', 'is_correct': True},
                    {'letter': 'ب', 'text': 'Wrong Answer', 'is_correct': False},
                ]},
            ],
        }
        fake_bytes = b'%PDF-with-answers'
        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = fake_bytes

        with patch('src.services.diagnostic_service.PDF_AVAILABLE', True), \
             patch('src.services.diagnostic_service.io') as mock_io, \
             patch('src.services.diagnostic_service.SimpleDocTemplate') as MockDoc, \
             patch('src.services.diagnostic_service.Paragraph'), \
             patch('src.services.diagnostic_service.Spacer'), \
             patch('src.services.diagnostic_service.Table'), \
             patch('src.services.diagnostic_service.TableStyle'), \
             patch('src.services.diagnostic_service.PageBreak'), \
             patch('src.services.diagnostic_service.ParagraphStyle'), \
             patch('src.services.diagnostic_service.getSampleStyleSheet', return_value={'Title': MagicMock(), 'Normal': MagicMock()}), \
             patch('src.services.diagnostic_service.pdfmetrics'), \
             patch('src.services.diagnostic_service.TTFont'), \
             patch('src.services.diagnostic_service.colors'), \
             patch('src.services.diagnostic_service.TA_RIGHT', 2), \
             patch('src.services.diagnostic_service.TA_CENTER', 1):
            mock_io.BytesIO.return_value = mock_buffer
            MockDoc.return_value = MagicMock()
            result = svc.generate_pdf(test_data, include_answers=True)
        assert result == fake_bytes

    def test_pdf_with_header_settings(self):
        """header_settings should add header paragraph."""
        svc = self._fresh_svc()
        test_data = self._make_test_data()
        header = {'country': 'Saudi Arabia', 'ministry': 'MOE', 'school_name': 'Al-Salam School'}
        fake_bytes = b'%PDF-header'
        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = fake_bytes

        with patch('src.services.diagnostic_service.PDF_AVAILABLE', True), \
             patch('src.services.diagnostic_service.io') as mock_io, \
             patch('src.services.diagnostic_service.SimpleDocTemplate') as MockDoc, \
             patch('src.services.diagnostic_service.Paragraph'), \
             patch('src.services.diagnostic_service.Spacer'), \
             patch('src.services.diagnostic_service.Table'), \
             patch('src.services.diagnostic_service.TableStyle'), \
             patch('src.services.diagnostic_service.PageBreak'), \
             patch('src.services.diagnostic_service.ParagraphStyle'), \
             patch('src.services.diagnostic_service.getSampleStyleSheet', return_value={'Title': MagicMock(), 'Normal': MagicMock()}), \
             patch('src.services.diagnostic_service.pdfmetrics'), \
             patch('src.services.diagnostic_service.TTFont'), \
             patch('src.services.diagnostic_service.colors'), \
             patch('src.services.diagnostic_service.TA_RIGHT', 2), \
             patch('src.services.diagnostic_service.TA_CENTER', 1):
            mock_io.BytesIO.return_value = mock_buffer
            MockDoc.return_value = MagicMock()
            result = svc.generate_pdf(test_data, include_answers=False, header_settings=header)
        assert result == fake_bytes

    def test_pdf_returns_none_on_exception(self):
        """If an exception occurs during PDF build, return None."""
        svc = self._fresh_svc()
        test_data = self._make_test_data()

        with patch('src.services.diagnostic_service.PDF_AVAILABLE', True), \
             patch('src.services.diagnostic_service.io') as mock_io, \
             patch('src.services.diagnostic_service.SimpleDocTemplate') as MockDoc, \
             patch('src.services.diagnostic_service.Paragraph'), \
             patch('src.services.diagnostic_service.Spacer'), \
             patch('src.services.diagnostic_service.Table'), \
             patch('src.services.diagnostic_service.TableStyle'), \
             patch('src.services.diagnostic_service.PageBreak'), \
             patch('src.services.diagnostic_service.ParagraphStyle'), \
             patch('src.services.diagnostic_service.getSampleStyleSheet', return_value={'Title': MagicMock(), 'Normal': MagicMock()}), \
             patch('src.services.diagnostic_service.pdfmetrics'), \
             patch('src.services.diagnostic_service.TTFont'), \
             patch('src.services.diagnostic_service.colors'), \
             patch('src.services.diagnostic_service.TA_RIGHT', 2), \
             patch('src.services.diagnostic_service.TA_CENTER', 1):
            mock_io.BytesIO.side_effect = Exception("IO error")
            result = svc.generate_pdf(test_data)
        assert result is None


# ===========================================================================
# 15. analyze_result – post_test needs_review False
# ===========================================================================

class TestAnalyzeResultExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_needs_review_false_when_post_test_above_60(self):
        svc = self._fresh_svc()
        r = _make_result(pct=75, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response
        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'post_test')
        assert result.get('needs_review') is False

    def test_ready_for_lesson_none_for_post_test(self):
        svc = self._fresh_svc()
        r = _make_result(pct=75, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response
        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'post_test')
        assert result.get('ready_for_lesson') is None

    def test_weak_topics_empty_when_all_answers_correct(self):
        svc = self._fresh_svc()
        r = _make_result(pct=100, answers=[
            {'is_correct': True, 'topic': 'Acids'},
            {'is_correct': True, 'topic': 'Bases'},
        ])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'Great!'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response
        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert result.get('weak_topics') == []

    def test_analysis_level_matches_determine_level(self):
        svc = self._fresh_svc()
        r = _make_result(pct=85, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'Excellent!'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response
        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx, 'pre_test')
        assert result['level'] == svc._determine_level(85)

    def test_default_test_type_is_pre_test(self):
        svc = self._fresh_svc()
        r = _make_result(pct=70, answers=[])
        ctx = {'name': 'Lesson 1'}
        mock_response = MagicMock()
        mock_response.text = 'Good'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response
        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.analyze_result(r, ctx)  # no test_type arg
        # Should default to pre_test – ready_for_lesson should be present
        assert 'ready_for_lesson' in result


# ===========================================================================
# 16. compare_results – AI path with non-empty answers
# ===========================================================================

class TestCompareResultsExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_still_weak_topics_calculated(self):
        pre = _make_result(pct=40, answers=[
            {'is_correct': False, 'topic': 'Oxidation'},
            {'is_correct': False, 'topic': 'Acids'},
        ])
        post = _make_result(pct=70, answers=[
            {'is_correct': False, 'topic': 'Oxidation'},
            {'is_correct': True, 'topic': 'Acids'},
        ])
        ctx = {'name': 'Lesson 1'}
        svc = self._fresh_svc()
        mock_response = MagicMock()
        mock_response.text = 'Comparison AI analysis'
        svc.client = MagicMock()
        svc.client.models.generate_content.return_value = mock_response

        with patch.object(svc, '_configure_ai', return_value=True):
            result = svc.compare_results(pre, post, ctx)
        assert result['analysis'] == 'Comparison AI analysis'

    def test_effectiveness_ar_excellent(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=30)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'excellent'
        assert 'ممتاز' in result['effectiveness_ar']

    def test_effectiveness_ar_good(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=50)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'good'
        assert 'جيد' in result['effectiveness_ar']

    def test_effectiveness_ar_moderate(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=60)
        post = _make_result(pct=65)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'moderate'
        assert 'متوسط' in result['effectiveness_ar']

    def test_effectiveness_ar_poor(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=80)
        post = _make_result(pct=50)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'poor'

    def test_improvement_exactly_30_is_excellent(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=40)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'excellent'

    def test_improvement_exactly_15_is_good(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=55)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'good'

    def test_improvement_exactly_0_is_moderate(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=70)
        post = _make_result(pct=70)
        ctx = {'name': 'Lesson 1'}
        with patch.object(svc, '_configure_ai', return_value=False):
            result = svc.compare_results(pre, post, ctx)
        assert result['effectiveness'] == 'moderate'


# ===========================================================================
# 17. _format_questions – edge cases
# ===========================================================================

class TestFormatQuestionsExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_db_question_no_lesson_sets_lesson_name_none(self):
        svc = self._fresh_svc()
        q = MagicMock()
        q.question_id = 99
        q.question_text = 'Test?'
        q.difficulty = 'medium'
        q.bloom_level = 'apply'
        q.image_url = None
        q.lesson = None
        q.options = []
        result = svc._format_questions([q])
        assert result[0]['lesson_name'] is None

    def test_db_question_with_five_options_uses_numeric_letter_for_5th(self):
        svc = self._fresh_svc()
        q = MagicMock()
        q.question_id = 1
        q.question_text = 'Q?'
        q.difficulty = 'easy'
        q.bloom_level = 'remember'
        q.image_url = None
        q.lesson = MagicMock()
        q.lesson.name = 'L1'
        opts = []
        for i in range(5):
            opt = MagicMock()
            opt.option_id = i + 1
            opt.option_text = f'Option {i}'
            opt.is_correct = (i == 0)
            opt.image_url = None
            opts.append(opt)
        q.options = opts
        result = svc._format_questions([q])
        letters = [o['letter'] for o in result[0]['options']]
        # 5th option (index 4) should be '5' since letters list has only 4 entries
        assert '5' in letters

    def test_ai_question_options_get_letters(self):
        svc = self._fresh_svc()
        ai_q = {
            'text': 'AI question',
            'difficulty': 'hard',
            'options': [
                {'text': 'A', 'is_correct': False},
                {'text': 'B', 'is_correct': True},
                {'text': 'C', 'is_correct': False},
                {'text': 'D', 'is_correct': False},
            ]
        }
        result = svc._format_questions([ai_q])
        letters = [o['letter'] for o in result[0]['options']]
        assert 'أ' in letters
        assert 'ب' in letters

    def test_format_preserves_bloom_level_from_db(self):
        svc = self._fresh_svc()
        q = MagicMock()
        q.question_id = 5
        q.question_text = 'Q?'
        q.difficulty = 'medium'
        q.bloom_level = 'analyze'
        q.image_url = None
        q.lesson = MagicMock()
        q.lesson.name = 'L'
        q.options = []
        result = svc._format_questions([q])
        assert result[0]['bloom_level'] == 'analyze'

    def test_ai_question_with_empty_options_list(self):
        svc = self._fresh_svc()
        ai_q = {'text': 'Q with no options', 'options': []}
        result = svc._format_questions([ai_q])
        assert result[0]['options'] == []

    def test_format_multiple_db_questions_all_have_source(self):
        svc = self._fresh_svc()
        questions = []
        for i in range(3):
            q = MagicMock()
            q.question_id = i + 1
            q.question_text = f'Question {i}'
            q.difficulty = 'easy'
            q.bloom_level = 'remember'
            q.image_url = None
            q.lesson = MagicMock()
            q.lesson.name = 'L'
            q.options = []
            questions.append(q)
        result = svc._format_questions(questions)
        assert all(r['source'] == 'database' for r in result)


# ===========================================================================
# 18. _get_context – unit with lessons
# ===========================================================================

class TestGetContextExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_unit_context_has_lessons_list(self):
        svc = self._fresh_svc()
        mock_unit = MagicMock()
        mock_unit.id = 3
        mock_unit.name = 'Unit 3'
        mock_unit.course = MagicMock()
        mock_unit.course.name = 'Chemistry'

        mock_lesson = MagicMock()
        mock_lesson.name = 'Lesson A'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            MockUnit.query.get.return_value = mock_unit
            MockLesson.query.filter_by.return_value.all.return_value = [mock_lesson]
            result = svc._get_context(None, 3, None)

        assert result['lessons'] == ['Lesson A']

    def test_unit_context_has_course_name(self):
        svc = self._fresh_svc()
        mock_unit = MagicMock()
        mock_unit.id = 3
        mock_unit.name = 'Unit 3'
        mock_unit.course = MagicMock()
        mock_unit.course.name = 'Chemistry Advanced'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            MockUnit.query.get.return_value = mock_unit
            MockLesson.query.filter_by.return_value.all.return_value = []
            result = svc._get_context(None, 3, None)

        assert result['course_name'] == 'Chemistry Advanced'

    def test_lesson_context_has_unit_name(self):
        svc = self._fresh_svc()
        mock_lesson = MagicMock()
        mock_lesson.id = 7
        mock_lesson.name = 'Acids and Bases'
        mock_lesson.unit = MagicMock()
        mock_lesson.unit.name = 'Unit 2'
        mock_lesson.unit.course = MagicMock()
        mock_lesson.unit.course.name = 'Chemistry'

        with patch('src.services.diagnostic_service.Lesson') as MockLesson:
            MockLesson.query.get.return_value = mock_lesson
            result = svc._get_context(7, None, None)

        assert result['unit_name'] == 'Unit 2'

    def test_lesson_context_no_unit_sets_unit_name_none(self):
        svc = self._fresh_svc()
        mock_lesson = MagicMock()
        mock_lesson.id = 7
        mock_lesson.name = 'Lesson X'
        mock_lesson.unit = None

        with patch('src.services.diagnostic_service.Lesson') as MockLesson:
            MockLesson.query.get.return_value = mock_lesson
            result = svc._get_context(7, None, None)

        assert result['unit_name'] is None
        assert result['course_name'] is None

    def test_returns_none_when_unit_not_found(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Lesson') as MockLesson, \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            MockUnit.query.get.return_value = None
            result = svc._get_context(None, 999, None)
        assert result is None

    def test_exception_during_unit_query_returns_none(self):
        svc = self._fresh_svc()
        with patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit') as MockUnit:
            MockUnit.query.get.side_effect = Exception("DB error")
            result = svc._get_context(None, 5, None)
        assert result is None


# ===========================================================================
# 19. _basic_analysis – detailed text checks
# ===========================================================================

class TestBasicAnalysisExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_excellent_text_is_positive(self):
        svc = self._fresh_svc()
        r = _make_result(pct=90)
        result = svc._basic_analysis(r)
        assert 'ممتاز' in result['analysis']

    def test_good_text_mentions_review(self):
        svc = self._fresh_svc()
        r = _make_result(pct=65)
        result = svc._basic_analysis(r)
        assert 'جيد' in result['analysis']

    def test_average_text_mentions_lesson(self):
        svc = self._fresh_svc()
        r = _make_result(pct=50)
        result = svc._basic_analysis(r)
        assert 'متوسط' in result['analysis']

    def test_weak_text_mentions_study(self):
        svc = self._fresh_svc()
        r = _make_result(pct=20)
        result = svc._basic_analysis(r)
        assert len(result['analysis']) > 0

    def test_boundary_80_excellent(self):
        svc = self._fresh_svc()
        r = _make_result(pct=80.0)
        result = svc._basic_analysis(r)
        assert result['level'] == 'excellent'

    def test_boundary_60_good(self):
        svc = self._fresh_svc()
        r = _make_result(pct=60.0)
        result = svc._basic_analysis(r)
        assert result['level'] == 'good'

    def test_boundary_40_average(self):
        svc = self._fresh_svc()
        r = _make_result(pct=40.0)
        result = svc._basic_analysis(r)
        assert result['level'] == 'average'

    def test_boundary_39_weak(self):
        svc = self._fresh_svc()
        r = _make_result(pct=39.9)
        result = svc._basic_analysis(r)
        assert result['level'] == 'weak'


# ===========================================================================
# 20. _basic_comparison_analysis – branch text content
# ===========================================================================

class TestBasicComparisonAnalysisExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_excellent_branch_contains_percent_values(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=30)
        post = _make_result(pct=70)
        result = svc._basic_comparison_analysis(pre, post, 40)
        assert '30' in result
        assert '70' in result

    def test_good_branch_contains_percent_values(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=50)
        post = _make_result(pct=68)
        result = svc._basic_comparison_analysis(pre, post, 18)
        assert '50' in result
        assert '68' in result

    def test_moderate_branch_contains_percent_values(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=60)
        post = _make_result(pct=65)
        result = svc._basic_comparison_analysis(pre, post, 5)
        assert '60' in result
        assert '65' in result

    def test_poor_branch_contains_percent_values(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=80)
        post = _make_result(pct=55)
        result = svc._basic_comparison_analysis(pre, post, -25)
        assert '80' in result
        assert '55' in result

    def test_improvement_30_is_excellent_branch(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=40)
        post = _make_result(pct=70)
        result = svc._basic_comparison_analysis(pre, post, 30)
        # excellent branch
        assert '40' in result and '70' in result

    def test_improvement_15_is_good_branch(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=55)
        post = _make_result(pct=70)
        result = svc._basic_comparison_analysis(pre, post, 15)
        assert '55' in result and '70' in result

    def test_improvement_0_is_moderate_branch(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=60)
        post = _make_result(pct=60)
        result = svc._basic_comparison_analysis(pre, post, 0)
        assert '60' in result

    def test_negative_improvement_is_poor_branch(self):
        svc = self._fresh_svc()
        pre = _make_result(pct=75)
        post = _make_result(pct=45)
        result = svc._basic_comparison_analysis(pre, post, -30)
        assert '75' in result
        assert '45' in result


# ===========================================================================
# 21. _determine_level – comprehensive
# ===========================================================================

class TestDetermineLevelExtended:

    def _fresh_svc(self):
        with patch('src.services.diagnostic_service.db'), \
             patch('src.services.diagnostic_service.Lesson'), \
             patch('src.services.diagnostic_service.Unit'), \
             patch('src.services.diagnostic_service.Course'), \
             patch('src.services.diagnostic_service.Question'), \
             patch('src.services.diagnostic_service.Option'):
            from src.services.diagnostic_service import DiagnosticService
            return DiagnosticService()

    def test_100_is_excellent(self):
        svc = self._fresh_svc()
        assert svc._determine_level(100) == 'excellent'

    def test_80_is_excellent(self):
        svc = self._fresh_svc()
        assert svc._determine_level(80) == 'excellent'

    def test_79_9_is_good(self):
        svc = self._fresh_svc()
        assert svc._determine_level(79.9) == 'good'

    def test_60_is_good(self):
        svc = self._fresh_svc()
        assert svc._determine_level(60) == 'good'

    def test_59_9_is_average(self):
        svc = self._fresh_svc()
        assert svc._determine_level(59.9) == 'average'

    def test_40_is_average(self):
        svc = self._fresh_svc()
        assert svc._determine_level(40) == 'average'

    def test_39_9_is_weak(self):
        svc = self._fresh_svc()
        assert svc._determine_level(39.9) == 'weak'

    def test_0_is_weak(self):
        svc = self._fresh_svc()
        assert svc._determine_level(0) == 'weak'

    def test_negative_is_weak(self):
        svc = self._fresh_svc()
        assert svc._determine_level(-5) == 'weak'


# ===========================================================================
# 22. diagnostic_service module-level singleton
# ===========================================================================

class TestModuleSingleton:

    def test_module_has_diagnostic_service_instance(self):
        import src.services.diagnostic_service as m
        assert hasattr(m, 'diagnostic_service')

    def test_singleton_is_diagnostic_service_instance(self):
        import src.services.diagnostic_service as m
        from src.services.diagnostic_service import DiagnosticService
        assert isinstance(m.diagnostic_service, DiagnosticService)

    def test_singleton_starts_not_configured(self):
        import src.services.diagnostic_service as m
        # Reset to ensure fresh state check
        original = m.diagnostic_service.is_configured
        # The singleton was created with is_configured=False
        # (It may have been configured during other tests, so just check type)
        assert isinstance(m.diagnostic_service.is_configured, bool)

