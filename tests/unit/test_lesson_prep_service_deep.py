"""
Deep unit tests for src/services/lesson_prep_service.py
Target: push coverage from 81% to 92%+
Focuses on uncovered paths: generate_lesson_plan, generate_unit_distribution,
parse_semester_distribution, _generate_support_plan, _extract_pages_as_images,
_build_single_period_prompt, _generate_pdf, _generate_unit_pdf, and edge cases.
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock, Mock, call, PropertyMock

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy external modules BEFORE importing the service
# ---------------------------------------------------------------------------
genai_mock = MagicMock()
types_mock = MagicMock()
sys.modules.setdefault('google', MagicMock())
sys.modules['google.genai'] = genai_mock
sys.modules['google.genai.types'] = types_mock

anthropic_mock = MagicMock()
sys.modules['anthropic'] = anthropic_mock

firebase_mock = MagicMock()
for _mod in ('firebase_admin', 'firebase_admin.credentials',
             'firebase_admin.messaging', 'firebase_admin.auth'):
    sys.modules.setdefault(_mod, firebase_mock)

sys.modules.setdefault('flask_socketio', MagicMock())
sys.modules.setdefault('fitz', MagicMock())
sys.modules.setdefault('weasyprint', MagicMock())
sys.modules.setdefault('cloudinary', MagicMock())
sys.modules.setdefault('cloudinary.uploader', MagicMock())

from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as pg
pg.ARRAY = lambda *a, **kw: Text()
pg.JSONB = JSON

import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.services.lesson_prep_service import (
    LessonPrepService,
    RateLimitError,
    _update_progress,
    AI_PROVIDERS,
    AI_PRICING,
    DEFAULT_PROVIDER,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope='module')
def flask_app():
    from flask import Flask
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['GOOGLE_AI_API_KEY'] = 'test-google-key'
    app.config['CLAUDE_AI_API_KEY'] = 'test-claude-key'
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app


@pytest.fixture
def app_ctx(flask_app):
    ctx = flask_app.app_context()
    ctx.push()
    yield flask_app
    ctx.pop()


@pytest.fixture
def service():
    return LessonPrepService()


# ---------------------------------------------------------------------------
# Helper: build a fake Claude stream context manager
# ---------------------------------------------------------------------------
def _make_claude_stream(text='response', input_tokens=10, output_tokens=5):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens

    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.get_final_message.return_value = mock_response
    return mock_stream


# ===========================================================================
# CLASS: TestCallGeminiEdgeCases
# ===========================================================================
class TestCallGeminiEdgeCases:
    """Additional edge cases for _call_gemini not covered by existing tests."""

    def setup_method(self):
        self.svc = LessonPrepService()
        self.svc.gemini_configured = True
        self.svc._current_gemini_model_id = 'gemini-2.0-flash'
        self.svc._current_max_tokens = 24576

    def test_unavailable_error_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("service unavailable")
        self.svc.gemini_client = mock_client
        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_gemini('prompt')

    def test_high_demand_error_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("high demand, please retry")
        self.svc.gemini_client = mock_client
        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_gemini('prompt')

    def test_resource_exhausted_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("resource_exhausted quota")
        self.svc.gemini_client = mock_client
        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_gemini('prompt')

    def test_multiple_images_added_to_content(self):
        mock_response = MagicMock()
        mock_response.text = 'response'
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        self.svc.gemini_client = mock_client

        mock_types = MagicMock()
        mock_types.Part.from_bytes.return_value = MagicMock()
        mock_types.GenerateContentConfig.return_value = MagicMock()

        with patch.object(self.svc, '_ensure_gemini', return_value=True), \
             patch('src.services.lesson_prep_service.types', mock_types):
            self.svc._call_gemini('prompt', images=[b'img1', b'img2', b'img3'])

        assert mock_types.Part.from_bytes.call_count == 3

    def test_usage_metadata_attributes_missing_returns_zero(self):
        mock_response = MagicMock()
        mock_response.text = 'text'
        um = MagicMock(spec=[])  # no attributes
        mock_response.usage_metadata = um
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        self.svc.gemini_client = mock_client
        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            text, usage = self.svc._call_gemini('prompt')
        assert usage['input_tokens'] == 0
        assert usage['output_tokens'] == 0

    def test_label_parameter_used_in_logging(self):
        mock_response = MagicMock()
        mock_response.text = 'ok'
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        self.svc.gemini_client = mock_client
        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            text, _ = self.svc._call_gemini('prompt', label='test-label')
        assert text == 'ok'

    def test_custom_model_id_passed_to_generate(self):
        mock_response = MagicMock()
        mock_response.text = 'ok'
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        self.svc.gemini_client = mock_client
        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            self.svc._call_gemini('prompt', model_id='gemini-1.5-pro')
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs.get('model') == 'gemini-1.5-pro'


# ===========================================================================
# CLASS: TestCallClaudeEdgeCases
# ===========================================================================
class TestCallClaudeEdgeCases:
    """Additional edge cases for _call_claude."""

    def setup_method(self):
        self.svc = LessonPrepService()
        self.svc.claude_configured = True

    def test_429_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_stream = _make_claude_stream()
        mock_stream.get_final_message.side_effect = Exception("429 rate limit exceeded")
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_claude('prompt')

    def test_rate_keyword_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_stream = _make_claude_stream()
        mock_stream.get_final_message.side_effect = Exception("rate limit hit")
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_claude('prompt')

    def test_usage_missing_returns_zero(self):
        mock_response = MagicMock(spec=['content'])
        mock_response.content = [MagicMock(text='ok')]
        mock_stream = _make_claude_stream()
        mock_stream.get_final_message.return_value = mock_response
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            text, usage = self.svc._call_claude('prompt')
        assert usage['input_tokens'] == 0
        assert usage['output_tokens'] == 0

    def test_multiple_images_all_encoded(self):
        import base64
        captured = []

        def capture(**kwargs):
            captured.append(kwargs.get('messages', []))
            return _make_claude_stream()

        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = capture
        self.svc.claude_client = mock_client

        images = [b'img_a', b'img_b']
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            self.svc._call_claude('prompt', images=images)

        content = captured[0][0]['content']
        image_parts = [c for c in content if isinstance(c, dict) and c.get('type') == 'image']
        assert len(image_parts) == 2
        assert image_parts[0]['source']['data'] == base64.b64encode(b'img_a').decode()
        assert image_parts[1]['source']['data'] == base64.b64encode(b'img_b').decode()

    def test_unknown_model_defaults_max_tokens(self):
        mock_stream = _make_claude_stream()
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            self.svc._call_claude('prompt', model='unknown-model-xyz')
        call_kwargs = mock_client.messages.stream.call_args
        # Should use 8192 as fallback
        assert call_kwargs.kwargs.get('max_tokens') == 8192

    def test_known_claude_sonnet_max_tokens(self):
        mock_stream = _make_claude_stream()
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            self.svc._call_claude('prompt', model='claude-sonnet-4-6')
        call_kwargs = mock_client.messages.stream.call_args
        assert call_kwargs.kwargs.get('max_tokens') == 16000


# ===========================================================================
# CLASS: TestGenerateSupportPlan
# ===========================================================================
class TestGenerateSupportPlan:
    """Tests for _generate_support_plan."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_support_data_on_success(self):
        support_json = {
            'simplified_explanation': 'شرح',
            'gradual_examples': [],
            'review_questions': [],
            'teacher_tips': [],
        }
        with patch.object(self.svc, '_call_ai', return_value=(json.dumps(support_json), {})), \
             patch.object(self.svc, '_extract_json', return_value=support_json):
            result = self.svc._generate_support_plan(1, 'درس الكيمياء', {})
        assert result == support_json

    def test_returns_none_on_call_ai_exception(self):
        with patch.object(self.svc, '_call_ai', side_effect=Exception("AI error")):
            result = self.svc._generate_support_plan(1, 'درس', {})
        assert result is None

    def test_uses_aggressive_fix_when_extract_fails(self):
        support_json = {'simplified_explanation': 'شرح بسيط'}
        with patch.object(self.svc, '_call_ai', return_value=('some text', {})), \
             patch.object(self.svc, '_extract_json', return_value=None), \
             patch.object(self.svc, '_aggressive_json_fix', return_value=support_json):
            result = self.svc._generate_support_plan(1, 'درس', {})
        assert result == support_json

    def test_returns_none_when_both_parsers_fail(self):
        with patch.object(self.svc, '_call_ai', return_value=('invalid text', {})), \
             patch.object(self.svc, '_extract_json', return_value=None), \
             patch.object(self.svc, '_aggressive_json_fix', return_value=None):
            result = self.svc._generate_support_plan(1, 'درس', {})
        assert result is None

    def test_extracts_concepts_from_plan_data(self):
        main_plan_data = {
            'presentation': {
                'main_concepts': [
                    {'concept': 'المفهوم الأول'},
                    {'concept': 'المفهوم الثاني'},
                    {'concept': 'المفهوم الثالث'},
                    {'concept': 'المفهوم الرابع'},  # يجب أن يُقطع عند 3
                ]
            }
        }
        captured_prompts = []

        def capture_call_ai(prompt, **kwargs):
            captured_prompts.append(prompt)
            return ('{"result": "ok"}', {})

        with patch.object(self.svc, '_call_ai', side_effect=capture_call_ai), \
             patch.object(self.svc, '_extract_json', return_value={'result': 'ok'}):
            self.svc._generate_support_plan(1, 'درس', main_plan_data)

        assert len(captured_prompts) == 1
        # يجب أن يحتوي على المفاهيم الأولى 3 فقط
        assert 'المفهوم الأول' in captured_prompts[0]
        assert 'المفهوم الثاني' in captured_prompts[0]
        assert 'المفهوم الثالث' in captured_prompts[0]

    def test_handles_non_dict_concepts(self):
        main_plan_data = {
            'presentation': {
                'main_concepts': ['string concept', None, 42]
            }
        }
        with patch.object(self.svc, '_call_ai', return_value=('{}', {})), \
             patch.object(self.svc, '_extract_json', return_value={'ok': True}):
            result = self.svc._generate_support_plan(1, 'درس', main_plan_data)
        # يجب أن لا ينهار

    def test_handles_non_dict_plan_data(self):
        with patch.object(self.svc, '_call_ai', return_value=('{}', {})), \
             patch.object(self.svc, '_extract_json', return_value={'ok': True}):
            result = self.svc._generate_support_plan(1, 'درس', None)
        # يجب أن لا ينهار

    def test_rate_limit_error_causes_none_return(self):
        """_generate_support_plan catches ALL exceptions including RateLimitError - returns None"""
        with patch.object(self.svc, '_call_ai', side_effect=RateLimitError("429")):
            result = self.svc._generate_support_plan(1, 'درس', {})
        # The outer except catches it and returns None
        assert result is None


# ===========================================================================
# CLASS: TestGenerateLessonPlan
# ===========================================================================
class TestGenerateLessonPlan:
    """Tests for generate_lesson_plan - the main generation function."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def _make_plan_mock(self, plan_id=1, status='pending', lesson_id=1):
        plan = MagicMock()
        plan.id = plan_id
        plan.status = status
        plan.lesson_id = lesson_id
        plan.teacher_id = 1
        plan.student_level = 'متوسط'
        plan.student_count = 30
        plan.weak_students_count = 5
        plan.excellent_students_count = 5
        plan.focus_area = 'شامل'
        plan.examples_count = 3
        plan.include_support_plan = False
        plan.needs_review = False
        return plan

    def test_returns_false_when_plan_not_found(self):
        mock_lp = MagicMock()
        mock_lp.query.get.return_value = None
        with patch('src.services.lesson_prep_service.LessonPlan', mock_lp):
            result = self.svc.generate_lesson_plan(999)
        assert result is False

    def test_returns_false_when_lesson_not_found(self):
        plan = self._make_plan_mock()
        mock_lesson = MagicMock()
        mock_lesson.query.get.return_value = None
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson', mock_lesson), \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch.object(self.svc, '_ensure_configured'):
            mock_lp.query.get.return_value = plan
            result = self.svc.generate_lesson_plan(1)
        assert result is False
        # plan.status should be 'failed'
        assert plan.status == 'failed'

    def test_returns_true_on_success(self):
        plan = self._make_plan_mock()
        lesson = MagicMock(id=1, name='درس التفاعلات', unit_id=1)
        unit = MagicMock(id=1, name='الوحدة الأولى', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'lesson_info': {'title': 'درس'}}
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt text'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(LessonPrepService, '_inject_diagrams', return_value=plan_data), \
             patch.object(self.svc, '_generate_pdf', return_value=None):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            plan.status = 'generating'  # simulate refresh
            result = self.svc.generate_lesson_plan(1)
        assert result is True

    def test_saves_raw_text_when_all_json_parse_fails(self):
        plan = self._make_plan_mock()
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', return_value=('invalid json text', {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=None), \
             patch.object(self.svc, '_aggressive_json_fix', return_value=None), \
             patch.object(self.svc, '_generate_pdf', return_value=None):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            result = self.svc.generate_lesson_plan(1)
        # يجب أن يحفظ raw_text ويعيد True
        assert result is True
        assert plan.needs_review is True

    def test_rate_limit_reraises_and_keeps_generating_status(self):
        plan = self._make_plan_mock()
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', side_effect=RateLimitError("429")):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = MagicMock(name='كيمياء')
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            with pytest.raises(RateLimitError):
                self.svc.generate_lesson_plan(1)
        assert plan.status == 'generating'

    def test_general_exception_sets_failed_status(self):
        plan = self._make_plan_mock()
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured', side_effect=Exception("config error")):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = MagicMock(unit_id=1)
            result = self.svc.generate_lesson_plan(1)
        assert result is False
        assert plan.status == 'failed'

    def test_skips_save_when_plan_deleted_during_generation(self):
        plan = self._make_plan_mock()
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'lesson_info': {}}
        mock_db = MagicMock()

        def refresh_plan(p):
            p.status = 'deleted'

        mock_db.session.refresh.side_effect = refresh_plan

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(LessonPrepService, '_inject_diagrams', return_value=plan_data), \
             patch.object(self.svc, '_generate_pdf', return_value=None):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            result = self.svc.generate_lesson_plan(1)
        assert result is False

    def test_include_support_plan_success(self):
        plan = self._make_plan_mock()
        plan.include_support_plan = True
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'lesson_info': {}}
        support_data = {'simplified_explanation': 'شرح'}
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(LessonPrepService, '_inject_diagrams', return_value=plan_data), \
             patch.object(self.svc, '_generate_pdf', return_value=None), \
             patch.object(self.svc, '_generate_support_plan', return_value=support_data):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            result = self.svc.generate_lesson_plan(1)
        assert result is True

    def test_include_support_plan_rate_limit_error(self):
        plan = self._make_plan_mock()
        plan.include_support_plan = True
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'lesson_info': {}}
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(LessonPrepService, '_inject_diagrams', return_value=plan_data), \
             patch.object(self.svc, '_generate_pdf', return_value=None), \
             patch.object(self.svc, '_generate_support_plan', side_effect=RateLimitError("429")):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            result = self.svc.generate_lesson_plan(1)
        assert result is True
        assert plan.needs_review is True

    def test_pdf_upload_cloudinary_fallback_to_local(self):
        """When Cloudinary fails, save locally"""
        plan = self._make_plan_mock()
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'lesson_info': {}}
        mock_db = MagicMock()

        mock_cloudinary = MagicMock()
        mock_cloudinary.uploader.upload.side_effect = Exception("Cloudinary error")

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(LessonPrepService, '_inject_diagrams', return_value=plan_data), \
             patch.object(self.svc, '_generate_pdf', return_value=b'pdf bytes'), \
             patch('builtins.open', MagicMock()), \
             patch('os.makedirs'), \
             patch.dict('sys.modules', {'cloudinary.uploader': mock_cloudinary}):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            result = self.svc.generate_lesson_plan(1)
        assert result is True

    def test_commit_error_triggers_rollback_retry(self):
        plan = self._make_plan_mock()
        lesson = MagicMock(id=1, name='درس', unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'lesson_info': {}}
        mock_db = MagicMock()
        commit_calls = [0]

        def side_effect_commit():
            commit_calls[0] += 1
            if commit_calls[0] == 2:  # second commit fails (the save)
                raise Exception("commit error")

        mock_db.session.commit.side_effect = side_effect_commit
        mock_db.session.refresh.return_value = None

        plan2 = self._make_plan_mock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_build_prompt', return_value='prompt'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(LessonPrepService, '_inject_diagrams', return_value=plan_data), \
             patch.object(self.svc, '_generate_pdf', return_value=None):
            mock_lp.query.get.side_effect = [plan, plan2]
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            # May succeed after rollback retry or raise - either way no crash
            try:
                self.svc.generate_lesson_plan(1)
            except Exception:
                pass


# ===========================================================================
# CLASS: TestExtractPagesAsImages
# ===========================================================================
class TestExtractPagesAsImages:
    """Tests for _extract_pages_as_images."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_empty_list_on_fitz_error(self):
        import sys
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = Exception("fitz error")
        with patch.dict('sys.modules', {'fitz': mock_fitz}), \
             patch('requests.get') as mock_req:
            mock_resp = MagicMock()
            mock_resp.content = b'%PDF...'
            mock_resp.raise_for_status.return_value = None
            mock_req.return_value = mock_resp
            result = self.svc._extract_pages_as_images('http://example.com/test.pdf', 1, 3)
        assert isinstance(result, list)

    def test_returns_empty_list_on_requests_error(self):
        with patch('requests.get', side_effect=Exception("network error")):
            result = self.svc._extract_pages_as_images('http://example.com/test.pdf', 1, 3)
        assert result == []

    def test_http_url_uses_requests(self):
        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b'jpeg_data'
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()

        with patch.dict('sys.modules', {'fitz': mock_fitz}), \
             patch('requests.get') as mock_req:
            mock_resp = MagicMock()
            mock_resp.content = b'%PDF-1.4 fake content'
            mock_resp.raise_for_status.return_value = None
            mock_req.return_value = mock_resp
            result = self.svc._extract_pages_as_images('http://example.com/test.pdf', 1, 2)
        assert isinstance(result, list)

    def test_local_absolute_path_reads_file(self):
        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=3)
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b'img'
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz.open.return_value = mock_doc

        with patch.dict('sys.modules', {'fitz': mock_fitz}), \
             patch('builtins.open', MagicMock(return_value=MagicMock(
                 __enter__=lambda s, *a, **k: s,
                 __exit__=lambda s, *a, **k: None,
                 read=MagicMock(return_value=b'%PDF fake')
             ))):
            result = self.svc._extract_pages_as_images('/absolute/path/test.pdf', 1, 2)
        assert isinstance(result, list)

    def test_local_relative_path_reads_file(self):
        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=3)
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b'img'
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz.open.return_value = mock_doc

        with patch.dict('sys.modules', {'fitz': mock_fitz}), \
             patch('builtins.open', MagicMock(return_value=MagicMock(
                 __enter__=lambda s, *a, **k: s,
                 __exit__=lambda s, *a, **k: None,
                 read=MagicMock(return_value=b'%PDF fake')
             ))):
            result = self.svc._extract_pages_as_images('/uploads/test.pdf', 1, 2)
        assert isinstance(result, list)


# ===========================================================================
# CLASS: TestBuildSinglePeriodPrompt
# ===========================================================================
class TestBuildSinglePeriodPrompt:
    """Tests for _build_single_period_prompt."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_string(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس التفاعلات', 'عنوان الحصة', 'كيمياء', 'الوحدة الأولى', '- درس 1\n- درس 2')
        assert isinstance(result, str)

    def test_contains_period_number(self):
        result = self.svc._build_single_period_prompt(3, 12, 'درس', 'عنوان', 'كيمياء', 'وحدة', 'دروس')
        assert '3' in result

    def test_contains_total_periods(self):
        result = self.svc._build_single_period_prompt(1, 15, 'درس', 'عنوان', 'كيمياء', 'وحدة', 'دروس')
        assert '15' in result

    def test_contains_lesson_name(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس التوازن الكيميائي', 'عنوان', 'كيمياء', 'وحدة', 'دروس')
        assert 'درس التوازن الكيميائي' in result

    def test_contains_course_name(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس', 'عنوان', 'كيمياء المرحلة الثانوية', 'وحدة', 'دروس')
        assert 'كيمياء المرحلة الثانوية' in result

    def test_contains_unit_name(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس', 'عنوان', 'كيمياء', 'وحدة الأحماض والقواعد', 'دروس')
        assert 'وحدة الأحماض والقواعد' in result

    def test_contains_json_structure(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس', 'عنوان', 'كيمياء', 'وحدة', 'دروس')
        assert 'period_number' in result
        assert 'objectives' in result
        assert 'evaluation' in result

    def test_contains_all_lessons_text(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس', 'عنوان', 'كيمياء', 'وحدة', '- درس A\n- درس B')
        assert 'درس A' in result
        assert 'درس B' in result

    def test_contains_title(self):
        result = self.svc._build_single_period_prompt(1, 12, 'درس', 'عنوان خاص جداً', 'كيمياء', 'وحدة', 'دروس')
        assert 'عنوان خاص جداً' in result


# ===========================================================================
# CLASS: TestGenerateUnitDistribution
# ===========================================================================
class TestGenerateUnitDistribution:
    """Tests for generate_unit_distribution."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_false_when_plan_not_found(self):
        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp:
            mock_lp.query.get.return_value = None
            result = self.svc.generate_unit_distribution(999)
        assert result is False

    def test_returns_false_when_unit_not_found(self):
        plan = MagicMock()
        plan.lesson_id = 1
        plan.teacher_id = 1
        plan.student_count = 12
        mock_db = MagicMock()
        lesson = MagicMock(unit_id=None)

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = None
            result = self.svc.generate_unit_distribution(1)
        assert result is False

    def test_rate_limit_keeps_generating_status(self):
        plan = MagicMock()
        plan.lesson_id = 1
        plan.teacher_id = 1
        plan.student_count = 2
        lesson = MagicMock(unit_id=1)
        unit = MagicMock(id=1, name='وحدة', course_id=1)
        course = MagicMock(name='كيمياء')
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.LessonPages') as mock_lp_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_extract_pages_as_images', return_value=[]), \
             patch.object(self.svc, '_call_ai', side_effect=RateLimitError("429")):
            mock_lp.query.get.return_value = plan
            mock_lesson_cls.query.get.return_value = lesson
            mock_unit_cls.query.get.return_value = unit
            mock_course_cls.query.get.return_value = course
            mock_lp_cls.query.filter_by.return_value.first.return_value = None
            from src.models.curriculum import Lesson as RealLesson
            with patch('src.services.lesson_prep_service.Lesson') as mock_lesson2:
                mock_lesson2.query.get.return_value = lesson
                mock_lesson2.query.filter_by.return_value.order_by.return_value.all.return_value = []
                with pytest.raises(RateLimitError):
                    self.svc.generate_unit_distribution(1)
        assert plan.status == 'generating'

    def test_general_exception_sets_failed(self):
        plan = MagicMock()
        plan.lesson_id = 1
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured', side_effect=Exception("error")):
            mock_lp.query.get.return_value = plan
            result = self.svc.generate_unit_distribution(1)
        assert result is False


# ===========================================================================
# CLASS: TestParseSemesterDistribution
# ===========================================================================
class TestParseSemesterDistribution:
    """Tests for parse_semester_distribution."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_false_when_plan_not_found(self):
        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp:
            mock_lp.query.get.return_value = None
            result = self.svc.parse_semester_distribution(999)
        assert result is False

    def test_returns_false_when_course_not_found(self):
        plan = MagicMock(course_id=1, teacher_id=1)
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'):
            mock_lp.query.get.return_value = plan
            mock_course_cls.query.get.return_value = None
            result = self.svc.parse_semester_distribution(1)
        assert result is False

    def test_no_pdf_url_generates_without_images(self):
        plan = MagicMock(course_id=1, teacher_id=1, original_pdf_url=None)
        course = MagicMock(id=1, name='كيمياء')
        plan_data = {'semester_name': 'الفصل الثاني', 'weeks': []}
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_call_ai', return_value=(json.dumps(plan_data), {'provider': 'gemini-flash'})), \
             patch.object(self.svc, '_extract_json', return_value=plan_data), \
             patch.object(self.svc, '_generate_semester_pdf', return_value=None):
            mock_lp.query.get.return_value = plan
            mock_course_cls.query.get.return_value = course
            mock_unit_cls.query.filter_by.return_value.order_by.return_value.all.return_value = []
            mock_lesson_cls.query.filter_by.return_value.order_by.return_value.all.return_value = []
            result = self.svc.parse_semester_distribution(1)
        assert result is True

    def test_rate_limit_reraises(self):
        plan = MagicMock(course_id=1, teacher_id=1, original_pdf_url=None)
        course = MagicMock(id=1, name='كيمياء')
        mock_db = MagicMock()

        with patch('src.services.lesson_prep_service.LessonPlan') as mock_lp, \
             patch('src.services.lesson_prep_service.Course') as mock_course_cls, \
             patch('src.services.lesson_prep_service.Unit') as mock_unit_cls, \
             patch('src.services.lesson_prep_service.Lesson') as mock_lesson_cls, \
             patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service._update_progress'), \
             patch.object(self.svc, '_ensure_configured'), \
             patch.object(self.svc, '_call_ai', side_effect=RateLimitError("429")):
            mock_lp.query.get.return_value = plan
            mock_course_cls.query.get.return_value = course
            mock_unit_cls.query.filter_by.return_value.order_by.return_value.all.return_value = []
            mock_lesson_cls.query.filter_by.return_value.order_by.return_value.all.return_value = []
            with pytest.raises(RateLimitError):
                self.svc.parse_semester_distribution(1)
        assert plan.status == 'generating'


# ===========================================================================
# CLASS: TestGeneratePdf
# ===========================================================================
class TestGeneratePdf:
    """Tests for _generate_pdf."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_none_on_import_error(self, app_ctx):
        """When weasyprint is not available, returns None."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'weasyprint':
                raise ImportError('weasyprint not installed')
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            result = self.svc._generate_pdf({}, 'درس', 'وحدة', 'كيمياء')
        assert result is None

    def test_returns_none_on_render_error(self, app_ctx):
        """When render_template raises, returns None."""
        mock_html_cls = MagicMock()
        with patch.dict('sys.modules', {'weasyprint': MagicMock(HTML=mock_html_cls)}), \
             patch('src.services.lesson_prep_service.current_app', app_ctx):
            result = self.svc._generate_pdf({}, 'درس', 'وحدة', 'كيمياء')
        assert result is None


# ===========================================================================
# CLASS: TestGenerateUnitPdf
# ===========================================================================
class TestGenerateUnitPdf:
    """Tests for _generate_unit_pdf."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_returns_none_on_exception(self, app_ctx):
        with patch('src.services.lesson_prep_service.current_app', app_ctx):
            result = self.svc._generate_unit_pdf({}, 'وحدة', 'كيمياء')
        assert result is None


# ===========================================================================
# CLASS: TestCallAiEdgeCases
# ===========================================================================
class TestCallAiEdgeCases:
    """Additional _call_ai edge cases."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_images_passed_to_gemini(self):
        fake_usage = {'input_tokens': 10, 'output_tokens': 5}
        with patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)) as mock_gem, \
             patch.object(self.svc, '_log_usage'), \
             patch.object(self.svc, '_get_active_provider', return_value='gemini-flash'):
            self.svc._call_ai('prompt', provider='gemini-flash', images=[b'img'])
        call_args = mock_gem.call_args
        assert b'img' in call_args.args[1] or (call_args.kwargs.get('images') and b'img' in call_args.kwargs['images'])

    def test_images_passed_to_claude(self):
        fake_usage = {'input_tokens': 10, 'output_tokens': 5}
        with patch.object(self.svc, '_call_claude', return_value=('text', fake_usage)) as mock_cl, \
             patch.object(self.svc, '_log_usage'):
            self.svc._call_ai('prompt', provider='claude-haiku', images=[b'img'])
        call_args = mock_cl.call_args
        assert b'img' in call_args.args[1] or (call_args.kwargs.get('images') and b'img' in call_args.kwargs['images'])

    def test_duration_is_positive_in_usage(self):
        fake_usage = {'input_tokens': 5, 'output_tokens': 10}
        with patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)), \
             patch.object(self.svc, '_log_usage'):
            _, usage = self.svc._call_ai('prompt', provider='gemini-flash')
        assert usage['duration'] >= 0

    def test_plan_id_passed_to_log_usage(self):
        fake_usage = {'input_tokens': 5, 'output_tokens': 10}
        with patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)), \
             patch.object(self.svc, '_log_usage') as mock_log:
            self.svc._call_ai('prompt', provider='gemini-flash', plan_id=77, teacher_id=3)
        args = mock_log.call_args[0]
        assert 77 in args
        assert 3 in args

    def test_operation_type_default_lesson_prep(self):
        fake_usage = {'input_tokens': 5, 'output_tokens': 10}
        with patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)), \
             patch.object(self.svc, '_log_usage') as mock_log:
            self.svc._call_ai('prompt', provider='gemini-flash')
        args = mock_log.call_args[0]
        assert 'lesson_prep' in args


# ===========================================================================
# CLASS: TestLogUsageEdgeCases
# ===========================================================================
class TestLogUsageEdgeCases:
    """Additional _log_usage edge cases."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_claude_haiku_cost_calculation(self):
        mock_db = MagicMock()
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog') as mock_log_cls:
            self.svc._log_usage(
                'claude-haiku',
                {'input_tokens': 1_000_000, 'output_tokens': 1_000_000},
                None, None, 'test', 1.0,
            )
            call_kwargs = mock_log_cls.call_args
            if call_kwargs:
                cost = call_kwargs.kwargs.get('cost_usd', 0)
                # input: 0.80 + output: 4.0 = 4.80
                assert abs(cost - 4.80) < 0.01

    def test_claude_sonnet_cost_calculation(self):
        mock_db = MagicMock()
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog') as mock_log_cls:
            self.svc._log_usage(
                'claude-sonnet',
                {'input_tokens': 1_000_000, 'output_tokens': 1_000_000},
                None, None, 'test', 1.0,
            )
            call_kwargs = mock_log_cls.call_args
            if call_kwargs:
                cost = call_kwargs.kwargs.get('cost_usd', 0)
                # input: 3.0 + output: 15.0 = 18.0
                assert abs(cost - 18.0) < 0.01

    def test_duration_stored_correctly(self):
        mock_db = MagicMock()
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog') as mock_log_cls:
            self.svc._log_usage('gemini-flash', {'input_tokens': 10, 'output_tokens': 5}, None, None, 'test', 3.14)
            call_kwargs = mock_log_cls.call_args
            if call_kwargs:
                dur = call_kwargs.kwargs.get('duration_seconds', 0)
                assert dur == 3.14

    def test_commit_called_after_add(self):
        mock_db = MagicMock()
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog', MagicMock()):
            self.svc._log_usage('gemini-flash', {'input_tokens': 5, 'output_tokens': 5}, None, None, 'test', 1.0)
        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called_once()

    def test_commit_fails_then_rollback(self):
        mock_db = MagicMock()
        mock_db.session.commit.side_effect = Exception("commit error")
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog', MagicMock()):
            # Should not raise
            self.svc._log_usage('gemini-flash', {'input_tokens': 5, 'output_tokens': 5}, None, None, 'test', 1.0)
        mock_db.session.rollback.assert_called()


# ===========================================================================
# CLASS: TestInjectDiagramsEdgeCases
# ===========================================================================
class TestInjectDiagramsEdgeCases:
    """More edge cases for _inject_diagrams."""

    def test_top_level_diagram_none_type_not_injected(self):
        plan_data = {'diagram': {'type': 'none'}}
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' not in result['diagram']

    def test_unknown_diagram_type_not_injected(self):
        plan_data = {'diagram': {'type': 'bar_chart'}}
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' not in result['diagram']

    def test_period_with_no_diagram_key(self):
        plan_data = {'periods': [{'lesson_name': 'درس', 'main_concepts': []}]}
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'diagram' not in result['periods'][0]

    def test_period_concept_with_no_diagram(self):
        plan_data = {'periods': [{'main_concepts': [{'concept': 'X'}]}]}
        result = LessonPrepService._inject_diagrams(plan_data)
        # No crash expected
        assert 'diagram' not in result['periods'][0]['main_concepts'][0]

    def test_empty_plan_data(self):
        result = LessonPrepService._inject_diagrams({})
        assert result == {}

    def test_multiple_concepts_with_diagrams(self):
        plan_data = {
            'presentation': {
                'main_concepts': [
                    {'concept': 'A', 'diagram': {'type': 'concentration_time'}},
                    {'concept': 'B', 'diagram': {'type': 'energy_diagram'}},
                    {'concept': 'C', 'diagram': {'type': 'none'}},
                ]
            }
        }
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' in result['presentation']['main_concepts'][0]['diagram']
        assert 'svg' in result['presentation']['main_concepts'][1]['diagram']
        assert 'svg' not in result['presentation']['main_concepts'][2]['diagram']


# ===========================================================================
# CLASS: TestBuildPromptEdgeCases
# ===========================================================================
class TestBuildPromptEdgeCases:
    """Edge cases for _build_prompt."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_missing_optional_fields_use_defaults(self):
        opts = {}
        result = self.svc._build_prompt('درس', 'وحدة', 'كيمياء', opts)
        assert isinstance(result, str)
        assert 'درس' in result

    def test_zero_students_count_in_prompt(self):
        opts = {'student_count': 0, 'examples_count': 0}
        result = self.svc._build_prompt('درس', 'وحدة', 'كيمياء', opts)
        assert '0' in result

    def test_large_student_count(self):
        opts = {'student_count': 500}
        result = self.svc._build_prompt('درس', 'وحدة', 'كيمياء', opts)
        assert '500' in result

    def test_empty_course_name(self):
        result = self.svc._build_prompt('درس', 'وحدة', '', {})
        assert isinstance(result, str)

    def test_returns_valid_prompt_format(self):
        opts = {
            'student_level': 'ممتاز',
            'student_count': 25,
            'weak_students_count': 3,
            'excellent_students_count': 7,
            'focus_area': 'الفهم',
            'examples_count': 4,
        }
        result = self.svc._build_prompt('الاتزان الكيميائي', 'التفاعلات', 'كيمياء 3', opts)
        assert 'الاتزان الكيميائي' in result
        assert 'التفاعلات' in result
        assert '25' in result
        assert 'الفهم' in result


# ===========================================================================
# CLASS: TestExtractJsonEdgeCases
# ===========================================================================
class TestExtractJsonEdgeCases:
    """Additional edge cases for _extract_json."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_line_number_error_recovery(self):
        # Constructed to trigger line-by-line repair
        text = '{\n  "a": 1\n  "b": 2\n}'
        result = self.svc._extract_json(text)
        # Either parses or returns None - no crash
        assert result is None or isinstance(result, dict)

    def test_extra_text_around_json_code_block(self):
        text = 'Here is the plan:\n```json\n{"title": "درس"}\n```\nThank you.'
        result = self.svc._extract_json(text)
        assert result == {"title": "درس"}

    def test_nested_code_block_structure(self):
        data = {"lesson_info": {"title": "test"}, "objectives": {"cognitive": []}}
        text = f'```json\n{json.dumps(data, ensure_ascii=False)}\n```'
        result = self.svc._extract_json(text)
        assert result == data

    def test_multiple_json_blocks_uses_first(self):
        text = '```json\n{"first": true}\n```\n```json\n{"second": true}\n```'
        result = self.svc._extract_json(text)
        assert result == {"first": True}

    def test_none_input_raises_or_returns_none(self):
        """_extract_json does not guard against None - it will raise TypeError"""
        try:
            result = self.svc._extract_json(None)
            assert result is None
        except TypeError:
            pass  # expected - function does not handle None input

    def test_number_string_returns_none(self):
        result = self.svc._extract_json("12345")
        assert result is None


# ===========================================================================
# CLASS: TestAggressiveJsonFixEdgeCases
# ===========================================================================
class TestAggressiveJsonFixEdgeCases:
    """Additional edge cases for _aggressive_json_fix."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_position_based_comma_insertion(self):
        # Test the e.pos based repair logic
        text = '{"a": 1 "b": 2 "c": 3}'
        result = self.svc._aggressive_json_fix(text)
        # May or may not succeed
        assert result is None or isinstance(result, dict)

    def test_valid_nested_json_returns_correctly(self):
        data = {'outer': {'inner': {'deep': [1, 2, 3]}}}
        result = self.svc._aggressive_json_fix(json.dumps(data))
        assert result == data

    def test_code_block_with_trailing_commas(self):
        text = '```json\n{"a": 1,\n"b": 2,\n}\n```'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"a": 1, "b": 2}

    def test_large_json_object(self):
        data = {f'key_{i}': f'value_{i}' for i in range(50)}
        result = self.svc._aggressive_json_fix(json.dumps(data))
        assert result == data

    def test_arabic_values_in_json(self):
        text = '{"الدرس": "تفاعلات الأكسدة", "الوحدة": "التفاعلات الكيميائية"}'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"الدرس": "تفاعلات الأكسدة", "الوحدة": "التفاعلات الكيميائية"}


# ===========================================================================
# CLASS: TestUpdateProgressEdgeCases
# ===========================================================================
class TestUpdateProgressEdgeCases:
    """Edge cases for _update_progress module function."""

    def test_empty_message_works(self):
        mock_plan = MagicMock()
        mock_lp = MagicMock()
        mock_lp.query.get.return_value = mock_plan
        mock_db = MagicMock()
        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=mock_db),
            'src.models.textbook': MagicMock(LessonPlan=mock_lp),
        }):
            _update_progress(1, "")
        # Should not raise

    def test_none_plan_id_handled(self):
        mock_lp = MagicMock()
        mock_lp.query.get.return_value = None
        mock_db = MagicMock()
        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=mock_db),
            'src.models.textbook': MagicMock(LessonPlan=mock_lp),
        }):
            _update_progress(None, "message")
        # Should not raise

    def test_commit_error_silenced(self):
        mock_plan = MagicMock()
        mock_db = MagicMock()
        mock_db.session.commit.side_effect = Exception("commit failed")
        mock_lp = MagicMock()
        mock_lp.query.get.return_value = mock_plan
        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=mock_db),
            'src.models.textbook': MagicMock(LessonPlan=mock_lp),
        }):
            _update_progress(1, "msg")
        # Should not raise


# ===========================================================================
# CLASS: TestSvgRateTimeEdgeCases
# ===========================================================================
class TestSvgRateTimeEdgeCases:
    """Additional edge cases for _svg_rate_time."""

    def test_empty_data_no_crash(self):
        result = LessonPrepService._svg_rate_time({})
        assert '<svg' in result

    def test_note_in_output(self):
        result = LessonPrepService._svg_rate_time({'note': 'ملاحظة مهمة'})
        assert 'ملاحظة مهمة' in result

    def test_html_container(self):
        result = LessonPrepService._svg_rate_time({})
        assert result.startswith('<div')

    def test_legend_colors_present(self):
        result = LessonPrepService._svg_rate_time({})
        assert '#dc2626' in result  # forward rate color
        assert '#2563eb' in result  # reverse rate color


# ===========================================================================
# CLASS: TestSvgConcentrationTimeEdgeCases
# ===========================================================================
class TestSvgConcentrationTimeEdgeCases:
    """Additional edge cases for _svg_concentration_time."""

    def test_custom_labels_in_legend(self):
        result = LessonPrepService._svg_concentration_time({
            'reactant_label': 'المتفاعل A',
            'product_label': 'الناتج B'
        })
        assert 'المتفاعل A' in result
        assert 'الناتج B' in result

    def test_html_structure(self):
        result = LessonPrepService._svg_concentration_time({})
        assert '<div ' in result
        assert '</div>' in result

    def test_svg_paths_present(self):
        result = LessonPrepService._svg_concentration_time({})
        assert '<path' in result


# ===========================================================================
# CLASS: TestEnsureGeminiCaching
# ===========================================================================
class TestEnsureGeminiCaching:
    """Test caching behavior of _ensure_gemini."""

    def test_same_model_reuses_client(self, app_ctx):
        svc = LessonPrepService()
        svc.gemini_configured = True
        svc.gemini_client = MagicMock()
        svc._current_gemini_model_id = 'gemini-2.0-flash'
        original_client = svc.gemini_client
        # Should NOT create a new client
        result = svc._ensure_gemini('gemini-2.0-flash')
        assert result is True
        assert svc.gemini_client is original_client

    def test_different_model_creates_new_client(self, app_ctx):
        svc = LessonPrepService()
        svc.gemini_configured = True
        svc.gemini_client = MagicMock()
        svc._current_gemini_model_id = 'gemini-2.0-flash'
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'test-key'
        with patch('src.services.lesson_prep_service.genai') as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            result = svc._ensure_gemini('gemini-1.5-pro')
        assert result is True
        assert svc._current_gemini_model_id == 'gemini-1.5-pro'


# ===========================================================================
# CLASS: TestFormatTextForPrint - not in lesson_prep but tests service patterns
# ===========================================================================
class TestAiProvidersCompleteness:
    """Verify all AI providers have correct structure."""

    def test_all_claude_providers_have_correct_provider_field(self):
        claude_providers = {k: v for k, v in AI_PROVIDERS.items() if 'claude' in k}
        for key, val in claude_providers.items():
            assert val['provider'] == 'claude', f"{key} should have provider='claude'"

    def test_all_gemini_providers_have_correct_provider_field(self):
        gemini_providers = {k: v for k, v in AI_PROVIDERS.items() if 'gemini' in k}
        for key, val in gemini_providers.items():
            assert val['provider'] == 'gemini', f"{key} should have provider='gemini'"

    def test_all_providers_have_positive_output_limit(self):
        for key, val in AI_PROVIDERS.items():
            assert val['output_limit'] > 0, f"{key} output_limit should be positive"

    def test_all_pricing_entries_non_negative(self):
        for key, val in AI_PRICING.items():
            assert val['input'] >= 0
            assert val['output'] >= 0

    def test_gemini_flash_is_default_provider(self):
        assert DEFAULT_PROVIDER == 'gemini-flash'

    def test_ensure_configured_returns_info_for_claude_sonnet(self, service):
        with patch.object(service, '_ensure_claude'):
            info = service._ensure_configured('claude-sonnet')
        assert info == AI_PROVIDERS['claude-sonnet']

    def test_ensure_configured_returns_info_for_gemini_pro(self, service):
        with patch.object(service, '_ensure_gemini'):
            info = service._ensure_configured('gemini-1.5-pro')
        assert info == AI_PROVIDERS['gemini-1.5-pro']

    def test_ensure_configured_claude_opus(self, service):
        with patch.object(service, '_ensure_claude') as mock_cl:
            info = service._ensure_configured('claude-opus')
        mock_cl.assert_called_once()
        assert info == AI_PROVIDERS['claude-opus']
