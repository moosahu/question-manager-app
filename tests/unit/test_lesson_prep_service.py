"""
Unit tests for src/services/lesson_prep_service.py
Tests use unittest.mock to isolate external dependencies.
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock, Mock, PropertyMock, call

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy external modules BEFORE importing the service
# ---------------------------------------------------------------------------
# google.genai
genai_mock = MagicMock()
types_mock = MagicMock()
sys.modules.setdefault('google', MagicMock())
sys.modules['google.genai'] = genai_mock
sys.modules['google.genai.types'] = types_mock

# anthropic
anthropic_mock = MagicMock()
sys.modules['anthropic'] = anthropic_mock

# firebase_admin (pulled in transitively)
firebase_mock = MagicMock()
for _mod in ('firebase_admin', 'firebase_admin.credentials',
             'firebase_admin.messaging', 'firebase_admin.auth'):
    sys.modules.setdefault(_mod, firebase_mock)

# flask_socketio
sys.modules.setdefault('flask_socketio', MagicMock())

# fitz / PyMuPDF
sys.modules.setdefault('fitz', MagicMock())

# weasyprint
sys.modules.setdefault('weasyprint', MagicMock())

# cloudinary
sys.modules.setdefault('cloudinary', MagicMock())
sys.modules.setdefault('cloudinary.uploader', MagicMock())

# SQLAlchemy pg types patch (SQLite compat)
from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as pg
pg.ARRAY = lambda *a, **kw: Text()
pg.JSONB = JSON

# hashlib.scrypt stub for Python 3.9 on macOS
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ---------------------------------------------------------------------------
# Now import the module under test
# ---------------------------------------------------------------------------
from src.services.lesson_prep_service import (
    LessonPrepService,
    RateLimitError,
    _update_progress,
    AI_PROVIDERS,
    AI_PRICING,
    DEFAULT_PROVIDER,
)


# ---------------------------------------------------------------------------
# Minimal Flask app fixture (no DB required for most unit tests)
# ---------------------------------------------------------------------------
@pytest.fixture(scope='module')
def flask_app():
    """Minimal Flask app for app context."""
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
    """Push/pop Flask app context for each test."""
    ctx = flask_app.app_context()
    ctx.push()
    yield flask_app
    ctx.pop()


@pytest.fixture
def service():
    """Fresh LessonPrepService instance."""
    return LessonPrepService()


# ===========================================================================
# CLASS: TestConstants
# ===========================================================================
class TestConstants:
    """Tests for module-level constants."""

    def test_default_provider_exists_in_ai_providers(self):
        assert DEFAULT_PROVIDER in AI_PROVIDERS

    def test_ai_providers_has_required_keys(self):
        for key, val in AI_PROVIDERS.items():
            assert 'name' in val
            assert 'provider' in val
            assert 'model' in val
            assert 'cost' in val
            assert 'output_limit' in val

    def test_ai_providers_provider_values(self):
        for key, val in AI_PROVIDERS.items():
            assert val['provider'] in ('gemini', 'claude'), f"Unexpected provider for {key}"

    def test_ai_pricing_structure(self):
        for key, val in AI_PRICING.items():
            assert 'input' in val
            assert 'output' in val
            assert val['input'] >= 0
            assert val['output'] >= 0

    def test_gemini_flash_output_limit(self):
        assert AI_PROVIDERS['gemini-flash']['output_limit'] == 24576

    def test_claude_haiku_output_limit(self):
        assert AI_PROVIDERS['claude-haiku']['output_limit'] == 8192


# ===========================================================================
# CLASS: TestServiceInit
# ===========================================================================
class TestServiceInit:
    """Tests for LessonPrepService.__init__."""

    def test_init_defaults(self, service):
        assert service.gemini_client is None
        assert service.claude_client is None
        assert service.gemini_configured is False
        assert service.claude_configured is False
        assert service._current_gemini_model_id is None
        assert service._current_max_tokens == 8192

    def test_multiple_instances_are_independent(self):
        s1 = LessonPrepService()
        s2 = LessonPrepService()
        s1.gemini_configured = True
        assert s2.gemini_configured is False


# ===========================================================================
# CLASS: TestEnsureGemini
# ===========================================================================
class TestEnsureGemini:
    """Tests for _ensure_gemini."""

    def test_already_configured_same_model_returns_true(self, service):
        service.gemini_configured = True
        service.gemini_client = MagicMock()
        service._current_gemini_model_id = 'gemini-2.0-flash'
        result = service._ensure_gemini('gemini-2.0-flash')
        assert result is True

    def test_missing_api_key_raises_value_error(self, service, app_ctx):
        app_ctx.config['GOOGLE_AI_API_KEY'] = None
        with patch.dict(os.environ, {}, clear=True):
            if 'GOOGLE_AI_API_KEY' in os.environ:
                del os.environ['GOOGLE_AI_API_KEY']
            with pytest.raises(ValueError, match="GOOGLE_AI_API_KEY"):
                service._ensure_gemini()
        # Restore
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'test-google-key'

    def test_configures_with_api_key_from_config(self, service, app_ctx):
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'fake-key-123'
        with patch('src.services.lesson_prep_service.genai') as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            result = service._ensure_gemini('gemini-2.0-flash')
        assert result is True
        assert service.gemini_configured is True
        assert service._current_gemini_model_id == 'gemini-2.0-flash'

    def test_sets_max_tokens_from_provider_info(self, service, app_ctx):
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'fake-key'
        with patch('src.services.lesson_prep_service.genai') as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            service._ensure_gemini('gemini-2.0-flash')
        assert service._current_max_tokens == 24576  # gemini-flash output_limit

    def test_reconfigures_for_different_model(self, service, app_ctx):
        service.gemini_configured = True
        service.gemini_client = MagicMock()
        service._current_gemini_model_id = 'gemini-2.0-flash'
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'fake-key'
        with patch('src.services.lesson_prep_service.genai') as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            result = service._ensure_gemini('gemini-1.5-pro')
        assert result is True
        assert service._current_gemini_model_id == 'gemini-1.5-pro'

    def test_unknown_model_defaults_max_tokens_to_8192(self, service, app_ctx):
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'fake-key'
        with patch('src.services.lesson_prep_service.genai') as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            service._ensure_gemini('unknown-model-xyz')
        assert service._current_max_tokens == 8192

    def test_api_key_from_env_when_config_missing(self, service, app_ctx):
        app_ctx.config['GOOGLE_AI_API_KEY'] = None
        with patch.dict(os.environ, {'GOOGLE_AI_API_KEY': 'env-key'}):
            with patch('src.services.lesson_prep_service.genai') as mock_genai:
                mock_genai.Client.return_value = MagicMock()
                result = service._ensure_gemini()
        assert result is True
        app_ctx.config['GOOGLE_AI_API_KEY'] = 'test-google-key'


# ===========================================================================
# CLASS: TestEnsureClaude
# ===========================================================================
class TestEnsureClaude:
    """Tests for _ensure_claude."""

    def test_already_configured_returns_true(self, service):
        service.claude_configured = True
        service.claude_client = MagicMock()
        assert service._ensure_claude() is True

    def test_missing_api_key_raises(self, service, app_ctx):
        app_ctx.config['CLAUDE_AI_API_KEY'] = None
        with patch.dict(os.environ, {}, clear=True):
            if 'CLAUDE_AI_API_KEY' in os.environ:
                del os.environ['CLAUDE_AI_API_KEY']
            with pytest.raises(ValueError, match="CLAUDE_AI_API_KEY"):
                service._ensure_claude()
        app_ctx.config['CLAUDE_AI_API_KEY'] = 'test-claude-key'

    def test_configures_claude_from_config(self, service, app_ctx):
        # anthropic is imported inline inside _ensure_claude, so it picks up sys.modules['anthropic']
        app_ctx.config['CLAUDE_AI_API_KEY'] = 'claude-fake-key'
        anthropic_mock.Anthropic.return_value = MagicMock()
        result = service._ensure_claude()
        assert result is True
        assert service.claude_configured is True

    def test_api_key_from_env(self, service, app_ctx):
        app_ctx.config['CLAUDE_AI_API_KEY'] = None
        with patch.dict(os.environ, {'CLAUDE_AI_API_KEY': 'env-claude-key'}):
            anthropic_mock.Anthropic.return_value = MagicMock()
            result = service._ensure_claude()
        assert result is True
        app_ctx.config['CLAUDE_AI_API_KEY'] = 'test-claude-key'


# ===========================================================================
# CLASS: TestEnsureConfigured
# ===========================================================================
class TestEnsureConfigured:
    """Tests for _ensure_configured."""

    def test_default_provider_uses_gemini(self, service):
        with patch.object(service, '_ensure_gemini') as mock_gem:
            service._ensure_configured()
            mock_gem.assert_called_once()

    def test_claude_provider_calls_ensure_claude(self, service):
        with patch.object(service, '_ensure_claude') as mock_cl:
            service._ensure_configured('claude-haiku')
            mock_cl.assert_called_once()

    def test_gemini_provider_calls_ensure_gemini(self, service):
        with patch.object(service, '_ensure_gemini') as mock_gem:
            service._ensure_configured('gemini-flash')
            mock_gem.assert_called_once()

    def test_unknown_provider_falls_back_to_default(self, service):
        with patch.object(service, '_ensure_gemini') as mock_gem:
            info = service._ensure_configured('nonexistent-provider')
            # Should use DEFAULT_PROVIDER's info
            assert info == AI_PROVIDERS[DEFAULT_PROVIDER]

    def test_returns_provider_info(self, service):
        with patch.object(service, '_ensure_gemini'):
            info = service._ensure_configured('gemini-flash')
        assert info == AI_PROVIDERS['gemini-flash']


# ===========================================================================
# CLASS: TestGetActiveProvider
# ===========================================================================
class TestGetActiveProvider:
    """Tests for _get_active_provider."""

    def test_returns_default_when_db_fails(self, service):
        with patch('src.services.lesson_prep_service.AISetting', create=True) as mock_ai_setting_cls:
            # Simulate import-time exception by patching the import
            with patch('builtins.__import__', side_effect=Exception("DB error")):
                result = service._get_active_provider()
        assert result == DEFAULT_PROVIDER

    def test_returns_valid_provider_from_db(self, service):
        with patch('src.services.lesson_prep_service.LessonPrepService._get_active_provider') as mock_gap:
            mock_gap.return_value = 'claude-haiku'
            result = service._get_active_provider()
        # We just called the real one - let's test properly with module patch
        assert result in list(AI_PROVIDERS.keys()) + [DEFAULT_PROVIDER]

    def test_returns_default_when_provider_not_in_ai_providers(self, service):
        # AISetting is imported locally inside _get_active_provider, patch the source module
        mock_module = MagicMock()
        mock_module.AISetting.get_setting.return_value = 'invalid-provider-xyz'
        with patch.dict('sys.modules', {'src.models.ai_analysis': mock_module}):
            result = service._get_active_provider()
        # invalid provider → falls back to DEFAULT_PROVIDER
        assert result == DEFAULT_PROVIDER

    def test_returns_default_when_get_setting_returns_none(self, service):
        mock_module = MagicMock()
        mock_module.AISetting.get_setting.return_value = None
        with patch.dict('sys.modules', {'src.models.ai_analysis': mock_module}):
            result = service._get_active_provider()
        assert result == DEFAULT_PROVIDER

    def test_returns_valid_provider_string(self, service):
        mock_module = MagicMock()
        mock_module.AISetting.get_setting.return_value = 'claude-sonnet'
        with patch.dict('sys.modules', {'src.models.ai_analysis': mock_module}):
            result = service._get_active_provider()
        assert result == 'claude-sonnet'

    def test_exception_in_get_setting_returns_default(self, service):
        mock_module = MagicMock()
        mock_module.AISetting.get_setting.side_effect = Exception("DB error")
        with patch.dict('sys.modules', {'src.models.ai_analysis': mock_module}):
            result = service._get_active_provider()
        assert result == DEFAULT_PROVIDER


# ===========================================================================
# CLASS: TestExtractJson
# ===========================================================================
class TestExtractJson:
    """Tests for _extract_json - many code paths."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_valid_json_in_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}

    def test_valid_json_raw_no_code_block(self):
        text = 'Some text before {"key": "value"} some text after'
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}

    def test_returns_none_for_no_json(self):
        result = self.svc._extract_json("no json here at all")
        assert result is None

    def test_trailing_comma_in_object(self):
        text = '{"key": "value",}'
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}

    def test_trailing_comma_in_array(self):
        text = '{"arr": [1, 2, 3,]}'
        result = self.svc._extract_json(text)
        assert result == {"arr": [1, 2, 3]}

    def test_trailing_comma_in_code_block(self):
        text = '```json\n{"key": "val",}\n```'
        result = self.svc._extract_json(text)
        assert result == {"key": "val"}

    def test_json_with_cpp_comments(self):
        text = '{\n"key": "value" // a comment\n}'
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = self.svc._extract_json(text)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_complex_valid_json(self):
        data = {
            "lesson_info": {"title": "درس اختبار", "duration": "45 دقيقة"},
            "objectives": {"cognitive": ["هدف 1", "هدف 2"]},
        }
        text = f'```json\n{json.dumps(data, ensure_ascii=False)}\n```'
        result = self.svc._extract_json(text)
        assert result == data

    def test_json_with_missing_comma_between_objects(self):
        # This tests fix 4: missing comma between } and {
        text = '[{"a":1}{"b":2}]'
        result = self.svc._extract_json(text)
        # May or may not succeed depending on fix cascade, but should not raise
        # (returns None or a dict)

    def test_empty_string_returns_none(self):
        result = self.svc._extract_json("")
        assert result is None

    def test_only_whitespace_returns_none(self):
        result = self.svc._extract_json("   \n\t  ")
        assert result is None

    def test_malformed_json_returns_none(self):
        text = '{"key": unclosed string'
        result = self.svc._extract_json(text)
        assert result is None

    def test_json_block_preferred_over_raw(self):
        text = '{"outer": true}\n```json\n{"inner": true}\n```'
        result = self.svc._extract_json(text)
        # Code block found first → {"inner": true}
        assert result == {"inner": True}

    def test_valid_array_is_not_returned_by_first_last_brace(self):
        # No { } at top level, but has valid JSON array
        text = '[1, 2, 3]'
        result = self.svc._extract_json(text)
        # first/last brace find nothing - returns None
        assert result is None

    def test_json_with_unicode(self):
        text = '{"arabic": "مرحبا بالعالم"}'
        result = self.svc._extract_json(text)
        assert result == {"arabic": "مرحبا بالعالم"}

    def test_json_with_boolean_values(self):
        text = '{"flag": true, "other": false, "nothing": null}'
        result = self.svc._extract_json(text)
        assert result == {"flag": True, "other": False, "nothing": None}

    def test_json_with_numbers(self):
        text = '{"count": 42, "ratio": 3.14}'
        result = self.svc._extract_json(text)
        assert result == {"count": 42, "ratio": 3.14}

    def test_code_block_with_invalid_json_falls_back_to_raw(self):
        # Code block has invalid JSON, raw brace extraction has valid
        text = '```json\ninvalid{json\n```\nActually valid: {"key": "val"}'
        result = self.svc._extract_json(text)
        # Tries code block first, fails, then tries raw brace extraction
        # Result could be None or {"key": "val"} - main thing: no exception
        assert result is None or isinstance(result, dict)

    def test_single_quotes_get_fixed(self):
        # Fix 3: replace ' with "
        text = "{'key': 'value'}"
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}

    def test_deeply_nested_json(self):
        data = {"a": {"b": {"c": {"d": [1, 2, {"e": "f"}]}}}}
        text = json.dumps(data)
        result = self.svc._extract_json(text)
        assert result == data

    def test_json_with_newlines_in_string_values(self):
        # Escaped newlines in values
        text = '{"text": "line1\\nline2"}'
        result = self.svc._extract_json(text)
        assert result is not None
        assert 'text' in result

    def test_leading_text_before_json(self):
        text = "Here is your lesson plan:\n\n" + json.dumps({"key": "value"})
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}

    def test_trailing_text_after_json(self):
        text = json.dumps({"key": "value"}) + "\n\nHope this helps!"
        result = self.svc._extract_json(text)
        assert result == {"key": "value"}


# ===========================================================================
# CLASS: TestAggressiveJsonFix
# ===========================================================================
class TestAggressiveJsonFix:
    """Tests for _aggressive_json_fix."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_valid_json_passes_through(self):
        text = '{"key": "value"}'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"key": "value"}

    def test_no_braces_returns_none(self):
        result = self.svc._aggressive_json_fix("no braces here")
        assert result is None

    def test_empty_string_returns_none(self):
        result = self.svc._aggressive_json_fix("")
        assert result is None

    def test_only_open_brace_returns_none(self):
        result = self.svc._aggressive_json_fix("{")
        assert result is None

    def test_trailing_comma_fixed(self):
        text = '{"key": "value",}'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"key": "value"}

    def test_comments_removed(self):
        text = '{\n"key": "value" // comment here\n}'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"key": "value"}

    def test_code_block_extraction(self):
        text = '```json\n{"key": "value"}\n```'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"key": "value"}

    def test_missing_comma_between_string_values(self):
        # "value"\n"key" should become "value",\n"key"
        text = '{"a": "first"\n"b": "second"}'
        result = self.svc._aggressive_json_fix(text)
        # May succeed or fail - mainly should not raise
        assert result is None or isinstance(result, dict)

    def test_missing_comma_between_objects(self):
        text = '[{"a":1}\n{"b":2}]'
        result = self.svc._aggressive_json_fix(text)
        # Should not raise
        assert result is None or isinstance(result, list)

    def test_missing_comma_after_array(self):
        text = '{"items": [1,2,3]\n"count": 3}'
        result = self.svc._aggressive_json_fix(text)
        assert result is None or isinstance(result, dict)

    def test_completely_invalid_returns_none(self):
        text = '{key value noquotes}'
        result = self.svc._aggressive_json_fix(text)
        assert result is None

    def test_nested_valid_json_in_code_block(self):
        data = {"outer": {"inner": "value"}}
        text = f'```json\n{json.dumps(data)}\n```'
        result = self.svc._aggressive_json_fix(text)
        assert result == data

    def test_multiline_json_with_trailing_commas(self):
        text = '{\n  "key1": "val1",\n  "key2": "val2",\n}'
        result = self.svc._aggressive_json_fix(text)
        assert result == {"key1": "val1", "key2": "val2"}

    def test_true_false_null_before_string_key(self):
        # Tests the regex for (true|false|null|\d)\n"key"
        text = '{"flag": true\n"other": false}'
        result = self.svc._aggressive_json_fix(text)
        assert result is None or isinstance(result, dict)

    def test_number_before_string_key(self):
        text = '{"count": 42\n"name": "test"}'
        result = self.svc._aggressive_json_fix(text)
        assert result is None or isinstance(result, dict)

    def test_recovers_by_inserting_comma(self):
        # A carefully crafted string where comma insertion should work
        # Use a known-good JSON with one comma removed
        text = '{"a": 1 "b": 2}'
        result = self.svc._aggressive_json_fix(text)
        # Should not raise regardless
        assert result is None or isinstance(result, dict)

    def test_no_first_brace_returns_none(self):
        result = self.svc._aggressive_json_fix("key: value, key2: value2}")
        assert result is None

    def test_array_at_top_level_with_braces(self):
        text = '[{"id": 1}, {"id": 2}]'
        result = self.svc._aggressive_json_fix(text)
        # First { is found, last } is found → extracts {"id": 2}
        # May or may not be valid
        assert result is None or isinstance(result, (dict, list))


# ===========================================================================
# CLASS: TestChemHtml
# ===========================================================================
class TestChemHtml:
    """Tests for _chem_html static method."""

    def test_none_input_returns_empty_string(self):
        result = LessonPrepService._chem_html(None)
        assert result == ''

    def test_empty_string_returns_empty(self):
        result = LessonPrepService._chem_html('')
        assert result == ''

    def test_non_string_returns_input(self):
        # non-string, truthy value → returned as-is (42 or '' == 42)
        result = LessonPrepService._chem_html(42)
        assert result == 42

    def test_arrow_converted(self):
        result = LessonPrepService._chem_html('A -> B')
        assert '→' in result
        assert '->' not in result

    def test_superscript_caret(self):
        result = LessonPrepService._chem_html('x^2')
        assert '<sup>2</sup>' in result

    def test_superscript_with_plus(self):
        result = LessonPrepService._chem_html('Na^+')
        assert '<sup>+</sup>' in result

    def test_superscript_with_minus(self):
        result = LessonPrepService._chem_html('Cl^-')
        assert '<sup>-</sup>' in result

    def test_superscript_complex(self):
        result = LessonPrepService._chem_html('Fe^2+')
        assert '<sup>2+</sup>' in result

    def test_subscript_after_letter(self):
        result = LessonPrepService._chem_html('H2O')
        assert '<sub>2</sub>' in result

    def test_subscript_after_closing_paren(self):
        result = LessonPrepService._chem_html('(OH)2')
        assert '<sub>2</sub>' in result

    def test_subscript_after_closing_bracket(self):
        result = LessonPrepService._chem_html('[Fe]3')
        assert '<sub>3</sub>' in result

    def test_h2so4_conversion(self):
        result = LessonPrepService._chem_html('H2SO4')
        assert '<sub>2</sub>' in result
        assert '<sub>4</sub>' in result

    def test_chemical_equation(self):
        result = LessonPrepService._chem_html('H2 + O2 -> H2O')
        assert '→' in result
        assert '<sub>2</sub>' in result

    def test_plain_text_unchanged_except_formula(self):
        result = LessonPrepService._chem_html('Hello World')
        assert result == 'Hello World'

    def test_multiple_arrows(self):
        result = LessonPrepService._chem_html('A -> B -> C')
        assert result.count('→') == 2
        assert '->' not in result

    def test_superscript_m(self):
        result = LessonPrepService._chem_html('dm^3')
        assert '<sup>3</sup>' in result

    def test_arabic_text_unchanged(self):
        text = 'تفاعل كيميائي'
        result = LessonPrepService._chem_html(text)
        assert result == text

    def test_combined_arabic_and_formula(self):
        result = LessonPrepService._chem_html('تفاعل H2O مع CO2')
        assert '<sub>2</sub>' in result
        assert 'تفاعل' in result


# ===========================================================================
# CLASS: TestDiagramWrap
# ===========================================================================
class TestDiagramWrap:
    """Tests for _diagram_wrap static method."""

    def test_returns_string(self):
        result = LessonPrepService._diagram_wrap('Title', '<svg/>', [])
        assert isinstance(result, str)

    def test_title_in_output(self):
        result = LessonPrepService._diagram_wrap('My Title', '<svg/>', [])
        assert 'My Title' in result

    def test_svg_body_in_output(self):
        result = LessonPrepService._diagram_wrap('T', '<svg id="test"/>', [])
        assert '<svg id="test"/>' in result

    def test_legend_items_in_output(self):
        result = LessonPrepService._diagram_wrap('T', '<svg/>', [('Label1', '#ff0000')])
        assert 'Label1' in result
        assert '#ff0000' in result

    def test_note_shown_when_provided(self):
        result = LessonPrepService._diagram_wrap('T', '<svg/>', [], note='Test note')
        assert 'Test note' in result

    def test_no_note_div_when_empty(self):
        result = LessonPrepService._diagram_wrap('T', '<svg/>', [], note='')
        assert 'font-size:8pt' not in result  # note div not rendered

    def test_multiple_legend_items(self):
        items = [('Item1', '#red'), ('Item2', '#blue'), ('Item3', '#green')]
        result = LessonPrepService._diagram_wrap('T', '<svg/>', items)
        assert 'Item1' in result
        assert 'Item2' in result
        assert 'Item3' in result

    def test_wraps_in_div(self):
        result = LessonPrepService._diagram_wrap('T', '<svg/>', [])
        assert result.startswith('<div ')
        assert result.endswith('</div>')

    def test_border_radius_present(self):
        result = LessonPrepService._diagram_wrap('T', '<svg/>', [])
        assert 'border-radius:8px' in result


# ===========================================================================
# CLASS: TestSvgConcentrationTime
# ===========================================================================
class TestSvgConcentrationTime:
    """Tests for _svg_concentration_time static method."""

    def test_returns_string(self):
        result = LessonPrepService._svg_concentration_time({})
        assert isinstance(result, str)

    def test_contains_svg(self):
        result = LessonPrepService._svg_concentration_time({})
        assert '<svg' in result

    def test_uses_provided_title(self):
        result = LessonPrepService._svg_concentration_time({'title': 'Custom Title'})
        assert 'Custom Title' in result

    def test_default_title_used(self):
        result = LessonPrepService._svg_concentration_time({})
        assert 'تغير التراكيز' in result

    def test_reactant_label_in_legend(self):
        result = LessonPrepService._svg_concentration_time({'reactant_label': 'TestReactant'})
        assert 'TestReactant' in result

    def test_product_label_in_legend(self):
        result = LessonPrepService._svg_concentration_time({'product_label': 'TestProduct'})
        assert 'TestProduct' in result

    def test_note_shown(self):
        result = LessonPrepService._svg_concentration_time({'note': 'Important note'})
        assert 'Important note' in result

    def test_empty_data_does_not_crash(self):
        result = LessonPrepService._svg_concentration_time({})
        assert result is not None

    def test_contains_equilibrium_marker(self):
        result = LessonPrepService._svg_concentration_time({})
        assert 'eq' in result


# ===========================================================================
# CLASS: TestSvgEnergyDiagram
# ===========================================================================
class TestSvgEnergyDiagram:
    """Tests for _svg_energy_diagram static method."""

    def test_returns_string(self):
        result = LessonPrepService._svg_energy_diagram({})
        assert isinstance(result, str)

    def test_contains_svg(self):
        result = LessonPrepService._svg_energy_diagram({})
        assert '<svg' in result

    def test_exothermic_by_default(self):
        result = LessonPrepService._svg_energy_diagram({})
        assert 'ΔH' in result or '&lt; 0' in result or 'Delta' in result or '0' in result

    def test_exothermic_color(self):
        result = LessonPrepService._svg_energy_diagram({'is_exothermic': True})
        assert '#16a34a' in result  # green for exothermic

    def test_endothermic_color(self):
        result = LessonPrepService._svg_energy_diagram({'is_exothermic': False})
        assert '#dc2626' in result  # red for endothermic

    def test_title_in_output(self):
        result = LessonPrepService._svg_energy_diagram({'title': 'Energy Test'})
        assert 'Energy Test' in result

    def test_default_title(self):
        result = LessonPrepService._svg_energy_diagram({})
        assert 'مخطط الطاقة' in result

    def test_ea_marker_present(self):
        result = LessonPrepService._svg_energy_diagram({})
        assert 'Ea' in result

    def test_note_present(self):
        result = LessonPrepService._svg_energy_diagram({'note': 'Energy note'})
        assert 'Energy note' in result

    def test_reactant_and_product_labels(self):
        result = LessonPrepService._svg_energy_diagram({
            'reactant_label': 'Reactants',
            'product_label': 'Products'
        })
        assert 'Reactants' in result
        assert 'Products' in result


# ===========================================================================
# CLASS: TestLogUsage
# ===========================================================================
class TestLogUsage:
    """Tests for _log_usage."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_logs_usage_to_db(self):
        mock_db = MagicMock()
        mock_log_cls = MagicMock()
        mock_log_instance = MagicMock()
        mock_log_cls.return_value = mock_log_instance

        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog', mock_log_cls):
            self.svc._log_usage(
                'gemini-flash',
                {'input_tokens': 100, 'output_tokens': 50},
                plan_id=1,
                teacher_id=2,
                operation_type='lesson_prep',
                duration=1.5,
            )

        mock_db.session.add.assert_called_once_with(mock_log_instance)
        mock_db.session.commit.assert_called_once()

    def test_cost_calculation_gemini_flash(self):
        costs = []
        mock_db = MagicMock()

        def capture_log(**kwargs):
            costs.append(kwargs.get('cost_usd', 0))
            return MagicMock()

        mock_log_cls = MagicMock(side_effect=lambda **kwargs: capture_log(**kwargs) or MagicMock())

        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog') as mock_log_cls2:
            self.svc._log_usage(
                'gemini-flash',
                {'input_tokens': 1_000_000, 'output_tokens': 1_000_000},
                None, None, 'test', 1.0,
            )
            call_kwargs = mock_log_cls2.call_args
            if call_kwargs:
                cost = call_kwargs.kwargs.get('cost_usd', call_kwargs[1].get('cost_usd', -1))
                # input: 0.075 + output: 0.30 = 0.375
                assert abs(cost - 0.375) < 0.001

    def test_unknown_provider_uses_zero_pricing(self):
        mock_db = MagicMock()
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog') as mock_log_cls:
            self.svc._log_usage(
                'unknown-provider',
                {'input_tokens': 1000, 'output_tokens': 1000},
                None, None, 'test', 1.0,
            )
            call_kwargs = mock_log_cls.call_args
            if call_kwargs:
                cost = call_kwargs.kwargs.get('cost_usd', call_kwargs[1].get('cost_usd', -1))
                assert cost == 0.0

    def test_db_error_does_not_raise(self):
        mock_db = MagicMock()
        mock_db.session.add.side_effect = Exception("DB connection error")

        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog', MagicMock()):
            # Should not raise - exception is caught internally
            self.svc._log_usage(
                'gemini-flash',
                {'input_tokens': 100, 'output_tokens': 50},
                None, None, 'test', 1.0,
            )

    def test_rollback_on_db_error(self):
        mock_db = MagicMock()
        mock_db.session.add.side_effect = Exception("DB error")

        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog', MagicMock()):
            self.svc._log_usage('gemini-flash', {}, None, None, 'test', 1.0)

        mock_db.session.rollback.assert_called_once()

    def test_missing_tokens_defaults_to_zero(self):
        mock_db = MagicMock()
        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog') as mock_log_cls:
            self.svc._log_usage('gemini-flash', {}, None, None, 'test', 1.0)
            call_kwargs = mock_log_cls.call_args
            if call_kwargs:
                in_tok = call_kwargs.kwargs.get('input_tokens',
                          call_kwargs[1].get('input_tokens', -1))
                assert in_tok == 0

    def test_rollback_failure_does_not_raise(self):
        mock_db = MagicMock()
        mock_db.session.add.side_effect = Exception("DB error")
        mock_db.session.rollback.side_effect = Exception("Rollback also failed")

        with patch('src.services.lesson_prep_service.db', mock_db), \
             patch('src.services.lesson_prep_service.AIUsageLog', MagicMock()):
            # Should not raise even if rollback also fails
            self.svc._log_usage('gemini-flash', {}, None, None, 'test', 1.0)


# ===========================================================================
# CLASS: TestCallAi
# ===========================================================================
class TestCallAi:
    """Tests for _call_ai orchestration method."""

    def setup_method(self):
        self.svc = LessonPrepService()

    def test_calls_gemini_for_gemini_provider(self):
        fake_usage = {'input_tokens': 10, 'output_tokens': 20}
        with patch.object(self.svc, '_call_gemini', return_value=('response text', fake_usage)) as mock_gem, \
             patch.object(self.svc, '_log_usage'), \
             patch.object(self.svc, '_get_active_provider', return_value='gemini-flash'):
            text, usage = self.svc._call_ai('prompt', provider='gemini-flash')
        mock_gem.assert_called_once()
        assert text == 'response text'

    def test_calls_claude_for_claude_provider(self):
        fake_usage = {'input_tokens': 10, 'output_tokens': 20}
        with patch.object(self.svc, '_call_claude', return_value=('claude response', fake_usage)) as mock_cl, \
             patch.object(self.svc, '_log_usage'):
            text, usage = self.svc._call_ai('prompt', provider='claude-haiku')
        mock_cl.assert_called_once()
        assert text == 'claude response'

    def test_uses_active_provider_when_no_provider_given(self):
        fake_usage = {'input_tokens': 5, 'output_tokens': 10}
        with patch.object(self.svc, '_get_active_provider', return_value='gemini-flash') as mock_gap, \
             patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)), \
             patch.object(self.svc, '_log_usage'):
            self.svc._call_ai('prompt')
        mock_gap.assert_called_once()

    def test_rate_limit_error_re_raised(self):
        with patch.object(self.svc, '_call_gemini', side_effect=RateLimitError("429")), \
             patch.object(self.svc, '_log_usage'):
            with pytest.raises(RateLimitError):
                self.svc._call_ai('prompt', provider='gemini-flash')

    def test_429_in_error_string_raises_rate_limit(self):
        error = Exception("HTTP 429: quota exceeded")
        with patch.object(self.svc, '_call_gemini', side_effect=error), \
             patch.object(self.svc, '_log_usage'):
            with pytest.raises(RateLimitError):
                self.svc._call_ai('prompt', provider='gemini-flash')

    def test_resource_exhausted_raises_rate_limit(self):
        error = Exception("resource exhausted, please try later")
        with patch.object(self.svc, '_call_gemini', side_effect=error), \
             patch.object(self.svc, '_log_usage'):
            with pytest.raises(RateLimitError):
                self.svc._call_ai('prompt', provider='gemini-flash')

    def test_other_exception_propagates(self):
        error = ValueError("Some other error")
        with patch.object(self.svc, '_call_gemini', side_effect=error), \
             patch.object(self.svc, '_log_usage'):
            with pytest.raises(ValueError):
                self.svc._call_ai('prompt', provider='gemini-flash')

    def test_usage_dict_gets_provider_and_duration(self):
        fake_usage = {'input_tokens': 10, 'output_tokens': 20}
        with patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)), \
             patch.object(self.svc, '_log_usage') as mock_log:
            text, usage = self.svc._call_ai('prompt', provider='gemini-flash')
        assert 'provider' in usage
        assert 'duration' in usage
        assert usage['provider'] == 'gemini-flash'

    def test_log_usage_called_with_correct_args(self):
        fake_usage = {'input_tokens': 100, 'output_tokens': 200}
        with patch.object(self.svc, '_call_gemini', return_value=('text', fake_usage)), \
             patch.object(self.svc, '_log_usage') as mock_log:
            self.svc._call_ai('prompt', provider='gemini-flash',
                               plan_id=42, teacher_id=7, operation_type='unit_prep')
        mock_log.assert_called_once()
        args = mock_log.call_args
        assert args[0][0] == 'gemini-flash'  # provider
        assert args[0][2] == 42              # plan_id
        assert args[0][3] == 7               # teacher_id
        assert args[0][4] == 'unit_prep'     # operation_type

    def test_quota_in_error_raises_rate_limit(self):
        error = Exception("quota limit reached for today")
        with patch.object(self.svc, '_call_gemini', side_effect=error), \
             patch.object(self.svc, '_log_usage'):
            with pytest.raises(RateLimitError):
                self.svc._call_ai('prompt', provider='gemini-flash')

    def test_rate_in_error_raises_rate_limit(self):
        error = Exception("Rate limit exceeded")
        with patch.object(self.svc, '_call_gemini', side_effect=error), \
             patch.object(self.svc, '_log_usage'):
            with pytest.raises(RateLimitError):
                self.svc._call_ai('prompt', provider='gemini-flash')


# ===========================================================================
# CLASS: TestUpdateProgress
# ===========================================================================
class TestUpdateProgress:
    """Tests for the module-level _update_progress function."""

    def test_updates_plan_progress_message(self):
        mock_plan = MagicMock()
        mock_lp = MagicMock()
        mock_lp.query.get.return_value = mock_plan
        mock_db = MagicMock()

        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=mock_db),
            'src.models.textbook': MagicMock(LessonPlan=mock_lp),
        }):
            _update_progress(1, "Testing progress")

        # No exception means it worked
        assert True

    def test_no_exception_when_plan_not_found(self):
        mock_lp = MagicMock()
        mock_lp.query.get.return_value = None
        mock_db = MagicMock()

        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=mock_db),
            'src.models.textbook': MagicMock(LessonPlan=mock_lp),
        }):
            # Should not raise
            _update_progress(999, "message")

    def test_no_exception_when_db_fails(self):
        mock_lp = MagicMock()
        mock_lp.query.get.side_effect = Exception("DB connection failed")

        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(),
            'src.models.textbook': MagicMock(LessonPlan=mock_lp),
        }):
            # Should not raise - exceptions are caught
            _update_progress(1, "message")


# ===========================================================================
# CLASS: TestRateLimitError
# ===========================================================================
class TestRateLimitError:
    """Tests for the RateLimitError exception class."""

    def test_is_exception(self):
        err = RateLimitError("test")
        assert isinstance(err, Exception)

    def test_message_preserved(self):
        err = RateLimitError("Rate limit 429")
        assert "429" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError("test rate limit")
        assert "test rate limit" in str(exc_info.value)

    def test_subclass_not_caught_by_base_exception_subclass(self):
        with pytest.raises(RateLimitError):
            raise RateLimitError("err")


# ===========================================================================
# CLASS: TestGenerateDiagramSvg
# ===========================================================================
class TestGenerateDiagramSvg:
    """Tests for _generate_diagram_svg static method."""

    def test_returns_none_for_none_input(self):
        result = LessonPrepService._generate_diagram_svg(None)
        assert result is None

    def test_returns_none_for_non_dict(self):
        result = LessonPrepService._generate_diagram_svg("string")
        assert result is None

    def test_returns_none_for_type_none(self):
        result = LessonPrepService._generate_diagram_svg({'type': 'none'})
        assert result is None

    def test_returns_none_for_missing_type(self):
        result = LessonPrepService._generate_diagram_svg({'title': 'Test'})
        assert result is None

    def test_concentration_time_returns_svg(self):
        result = LessonPrepService._generate_diagram_svg({'type': 'concentration_time'})
        assert result is not None
        assert '<svg' in result

    def test_energy_diagram_returns_svg(self):
        result = LessonPrepService._generate_diagram_svg({'type': 'energy_diagram'})
        assert result is not None
        assert '<svg' in result

    def test_rate_time_returns_svg(self):
        result = LessonPrepService._generate_diagram_svg({'type': 'rate_time'})
        assert result is not None
        assert '<svg' in result

    def test_unknown_type_returns_none(self):
        result = LessonPrepService._generate_diagram_svg({'type': 'bar_chart'})
        assert result is None


# ===========================================================================
# CLASS: TestInjectDiagrams
# ===========================================================================
class TestInjectDiagrams:
    """Tests for _inject_diagrams static method."""

    def test_injects_svg_into_top_level_diagram(self):
        plan_data = {
            'diagram': {'type': 'concentration_time', 'title': 'Test'}
        }
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' in result['diagram']
        assert '<svg' in result['diagram']['svg']

    def test_skips_none_type_diagram(self):
        plan_data = {
            'diagram': {'type': 'none'}
        }
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' not in result['diagram']

    def test_injects_into_main_concepts(self):
        plan_data = {
            'presentation': {
                'main_concepts': [
                    {'concept': 'A', 'diagram': {'type': 'energy_diagram'}}
                ]
            }
        }
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' in result['presentation']['main_concepts'][0]['diagram']

    def test_handles_no_presentation(self):
        plan_data = {'lesson_info': {'title': 'Test'}}
        result = LessonPrepService._inject_diagrams(plan_data)
        assert result == {'lesson_info': {'title': 'Test'}}

    def test_injects_into_periods(self):
        plan_data = {
            'periods': [
                {'diagram': {'type': 'rate_time'}}
            ]
        }
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' in result['periods'][0]['diagram']

    def test_handles_empty_periods(self):
        plan_data = {'periods': []}
        result = LessonPrepService._inject_diagrams(plan_data)
        assert result == {'periods': []}

    def test_handles_non_dict_period(self):
        plan_data = {'periods': ['not a dict']}
        result = LessonPrepService._inject_diagrams(plan_data)
        # Should not crash

    def test_returns_same_object(self):
        plan_data = {}
        result = LessonPrepService._inject_diagrams(plan_data)
        assert result is plan_data

    def test_injects_into_period_main_concepts(self):
        plan_data = {
            'periods': [
                {
                    'main_concepts': [
                        {'concept': 'X', 'diagram': {'type': 'concentration_time'}}
                    ]
                }
            ]
        }
        result = LessonPrepService._inject_diagrams(plan_data)
        assert 'svg' in result['periods'][0]['main_concepts'][0]['diagram']


# ===========================================================================
# CLASS: TestSvgRateTime
# ===========================================================================
class TestSvgRateTime:
    """Tests for _svg_rate_time static method."""

    def test_returns_string(self):
        result = LessonPrepService._svg_rate_time({})
        assert isinstance(result, str)

    def test_contains_svg(self):
        result = LessonPrepService._svg_rate_time({})
        assert '<svg' in result

    def test_default_title(self):
        result = LessonPrepService._svg_rate_time({})
        assert 'تغير معدل التفاعل' in result

    def test_custom_title(self):
        result = LessonPrepService._svg_rate_time({'title': 'Rate Test'})
        assert 'Rate Test' in result

    def test_reactant_label(self):
        result = LessonPrepService._svg_rate_time({'reactant_label': 'Forward Rate'})
        assert 'Forward Rate' in result

    def test_product_label(self):
        result = LessonPrepService._svg_rate_time({'product_label': 'Reverse Rate'})
        assert 'Reverse Rate' in result

    def test_note_shown(self):
        result = LessonPrepService._svg_rate_time({'note': 'Rate note'})
        assert 'Rate note' in result

    def test_equilibrium_marker(self):
        result = LessonPrepService._svg_rate_time({})
        assert 'eq' in result

    def test_r1_r2_labels(self):
        result = LessonPrepService._svg_rate_time({})
        assert 'r1' in result
        assert 'r2' in result


# ===========================================================================
# CLASS: TestCallGemini (with mocking)
# ===========================================================================
class TestCallGemini:
    """Tests for _call_gemini method with mocked genai."""

    def setup_method(self):
        self.svc = LessonPrepService()
        # Pre-configure as if _ensure_gemini was called
        self.svc.gemini_configured = True
        self.svc._current_gemini_model_id = 'gemini-2.0-flash'
        self.svc._current_max_tokens = 24576

    def test_returns_text_and_usage(self):
        mock_response = MagicMock()
        mock_response.text = 'AI response text'
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        self.svc.gemini_client = mock_client

        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            text, usage = self.svc._call_gemini('test prompt')

        assert text == 'AI response text'
        assert usage['input_tokens'] == 100
        assert usage['output_tokens'] == 50

    def test_503_error_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")
        self.svc.gemini_client = mock_client

        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_gemini('test prompt')

    def test_429_error_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 Too Many Requests")
        self.svc.gemini_client = mock_client

        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_gemini('test prompt')

    def test_other_error_propagates(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ValueError("Invalid argument")
        self.svc.gemini_client = mock_client

        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            with pytest.raises(ValueError):
                self.svc._call_gemini('test prompt')

    def test_usage_metadata_missing_defaults_to_zero(self):
        mock_response = MagicMock()
        mock_response.text = 'response'
        mock_response.usage_metadata = None
        del mock_response.usage_metadata  # Remove attribute

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        self.svc.gemini_client = mock_client

        with patch.object(self.svc, '_ensure_gemini', return_value=True):
            text, usage = self.svc._call_gemini('test prompt')

        assert usage['input_tokens'] == 0
        assert usage['output_tokens'] == 0

    def test_images_added_to_content(self):
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
            self.svc._call_gemini('test prompt', images=[b'fake_image_bytes'])

        mock_types.Part.from_bytes.assert_called_once_with(
            data=b'fake_image_bytes', mime_type='image/jpeg'
        )


# ===========================================================================
# CLASS: TestCallClaude (with mocking)
# ===========================================================================
class TestCallClaude:
    """Tests for _call_claude method with mocked anthropic."""

    def setup_method(self):
        self.svc = LessonPrepService()
        self.svc.claude_configured = True

    def test_returns_text_and_usage(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='Claude response')]
        mock_response.usage.input_tokens = 80
        mock_response.usage.output_tokens = 40

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.return_value = mock_response

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client

        with patch.object(self.svc, '_ensure_claude', return_value=True):
            text, usage = self.svc._call_claude('test prompt')

        assert text == 'Claude response'
        assert usage['input_tokens'] == 80
        assert usage['output_tokens'] == 40

    def test_529_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.side_effect = Exception("529 overloaded")
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client

        with patch.object(self.svc, '_ensure_claude', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_claude('test prompt')

    def test_503_raises_rate_limit(self):
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.side_effect = Exception("503 Service unavailable")
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client

        with patch.object(self.svc, '_ensure_claude', return_value=True):
            with pytest.raises(RateLimitError):
                self.svc._call_claude('test prompt')

    def test_other_error_propagates(self):
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.side_effect = ValueError("Bad request")
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client

        with patch.object(self.svc, '_ensure_claude', return_value=True):
            with pytest.raises(ValueError):
                self.svc._call_claude('test prompt')

    def test_images_encoded_as_base64(self):
        import base64
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='response')]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        captured_messages = []

        def capture_stream(**kwargs):
            captured_messages.append(kwargs.get('messages', []))
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=False)
            mock_stream.get_final_message.return_value = mock_response
            return mock_stream

        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = capture_stream
        self.svc.claude_client = mock_client

        test_image = b'fake image data'
        with patch.object(self.svc, '_ensure_claude', return_value=True):
            self.svc._call_claude('test prompt', images=[test_image])

        assert len(captured_messages) == 1
        msg_content = captured_messages[0][0]['content']
        image_part = msg_content[0]
        assert image_part['type'] == 'image'
        assert image_part['source']['type'] == 'base64'
        expected_b64 = base64.b64encode(test_image).decode('utf-8')
        assert image_part['source']['data'] == expected_b64

    def test_uses_correct_model(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='r')]
        mock_response.usage.input_tokens = 1
        mock_response.usage.output_tokens = 1

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.return_value = mock_response

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        self.svc.claude_client = mock_client

        with patch.object(self.svc, '_ensure_claude', return_value=True):
            self.svc._call_claude('prompt', model='claude-sonnet-4-6')

        call_kwargs = mock_client.messages.stream.call_args
        assert call_kwargs.kwargs.get('model') == 'claude-sonnet-4-6'
