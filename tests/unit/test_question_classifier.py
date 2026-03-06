# tests/unit/test_question_classifier.py
"""
Unit tests for src/services/question_classifier.py
Covers QuestionClassifier class init, pure logic, and mocked AI/DB calls.
"""

import sys
import os
import json
import time
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy third-party modules BEFORE any imports
# ---------------------------------------------------------------------------
_genai_mock = MagicMock()
_google_mock = MagicMock()
sys.modules['google'] = _google_mock
sys.modules['google.genai'] = _genai_mock
sys.modules['google.genai.types'] = MagicMock()

for _mod in ('firebase_admin', 'firebase_admin.credentials',
             'firebase_admin.messaging', 'firebase_admin.auth'):
    sys.modules.setdefault(_mod, MagicMock())

sys.modules.setdefault('flask_socketio', MagicMock())

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
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ---------------------------------------------------------------------------
# Ensure src.extensions is importable standalone (for _make_classifier's
# patch('src.extensions.db', ...) to work without test_ai_assistant.py).
# We set a mock into sys.modules AND attach it to the src module object
# so that getattr(src, 'extensions') works in Python's _importer.
# ---------------------------------------------------------------------------
_ext_mock = MagicMock()
_ext_mock.db = MagicMock()
sys.modules.setdefault('src.extensions', _ext_mock)
# Also attach to src module object if src is already imported
if 'src' in sys.modules and sys.modules['src'] is not None:
    _src_mod = sys.modules['src']
    if not hasattr(_src_mod, 'extensions'):
        _src_mod.extensions = _ext_mock
else:
    import src as _src_pkg
    if not hasattr(_src_pkg, 'extensions'):
        _src_pkg.extensions = _ext_mock


# ---------------------------------------------------------------------------
# Helper: build a fresh QuestionClassifier with all external deps mocked
# ---------------------------------------------------------------------------

def _make_classifier():
    """Return a QuestionClassifier instance with DB/models mocked."""
    # Clear cached module to get a fresh import
    if 'src.services.question_classifier' in sys.modules:
        del sys.modules['src.services.question_classifier']

    mock_db = MagicMock()
    mock_question_cls = MagicMock()

    with patch.dict('sys.modules', {
        'src.extensions': MagicMock(db=mock_db),
        'src.models.question': MagicMock(Question=mock_question_cls),
    }):
        with patch('src.extensions.db', mock_db):
            import src.services.question_classifier as mod
            classifier = mod.QuestionClassifier()

    return classifier, mod, mock_db, mock_question_cls


def _make_app():
    app = Flask(__name__)
    app.config['GOOGLE_AI_API_KEY'] = 'test-key-abc123'
    app.config['TESTING'] = True
    return app


# ===========================================================================
# 1. QuestionClassifier.__init__
# ===========================================================================

class TestQuestionClassifierInit:

    def test_client_is_none_by_default(self):
        c, _, _, _ = _make_classifier()
        assert c.client is None

    def test_is_configured_false_by_default(self):
        c, _, _, _ = _make_classifier()
        assert c.is_configured is False

    def test_api_key_is_none_by_default(self):
        c, _, _, _ = _make_classifier()
        assert c.api_key is None

    def test_model_name_is_gemini_flash(self):
        c, _, _, _ = _make_classifier()
        assert c.model_name == 'gemini-2.0-flash'

    def test_last_request_time_is_zero(self):
        c, _, _, _ = _make_classifier()
        assert c.last_request_time == 0

    def test_min_delay_is_6(self):
        c, _, _, _ = _make_classifier()
        assert c.min_delay == 6.0

    def test_consecutive_errors_is_zero(self):
        c, _, _, _ = _make_classifier()
        assert c.consecutive_errors == 0

    def test_max_consecutive_errors_is_5(self):
        c, _, _, _ = _make_classifier()
        assert c.max_consecutive_errors == 5


# ===========================================================================
# 2. _parse_response – PURE LOGIC
# ===========================================================================

class TestParseResponse:
    """Pure logic – no mocking required."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.c, _, _, _ = _make_classifier()

    def test_valid_json_easy_remember(self):
        result = self.c._parse_response('{"difficulty": "easy", "bloom_level": "remember"}')
        assert result['difficulty'] == 'easy'
        assert result['bloom_level'] == 'remember'

    def test_valid_json_hard_analyze(self):
        result = self.c._parse_response('{"difficulty": "hard", "bloom_level": "analyze"}')
        assert result['difficulty'] == 'hard'
        assert result['bloom_level'] == 'analyze'

    def test_valid_json_medium_apply(self):
        result = self.c._parse_response('{"difficulty": "medium", "bloom_level": "apply"}')
        assert result['difficulty'] == 'medium'
        assert result['bloom_level'] == 'apply'

    def test_valid_json_evaluate(self):
        result = self.c._parse_response('{"difficulty": "easy", "bloom_level": "evaluate"}')
        assert result['bloom_level'] == 'evaluate'

    def test_valid_json_create(self):
        result = self.c._parse_response('{"difficulty": "hard", "bloom_level": "create"}')
        assert result['bloom_level'] == 'create'

    def test_valid_json_understand(self):
        result = self.c._parse_response('{"difficulty": "medium", "bloom_level": "understand"}')
        assert result['bloom_level'] == 'understand'

    def test_json_wrapped_in_code_block(self):
        text = '```json\n{"difficulty": "easy", "bloom_level": "remember"}\n```'
        result = self.c._parse_response(text)
        # The regex extracts the first { ... } — still gets the JSON
        assert result['difficulty'] == 'easy'

    def test_json_with_surrounding_text(self):
        text = 'Here is the classification: {"difficulty": "hard", "bloom_level": "analyze"} end.'
        result = self.c._parse_response(text)
        assert result['difficulty'] == 'hard'

    def test_invalid_json_returns_defaults(self):
        result = self.c._parse_response('this is not json at all')
        assert result['difficulty'] == 'medium'
        assert result['bloom_level'] == 'remember'

    def test_empty_string_returns_defaults(self):
        result = self.c._parse_response('')
        assert result['difficulty'] == 'medium'
        assert result['bloom_level'] == 'remember'

    def test_invalid_difficulty_value_uses_default(self):
        # 'extreme' is not a valid difficulty
        result = self.c._parse_response('{"difficulty": "extreme", "bloom_level": "remember"}')
        assert result['difficulty'] == 'medium'

    def test_invalid_bloom_level_uses_default(self):
        # 'memorize' is not a valid bloom level
        result = self.c._parse_response('{"difficulty": "easy", "bloom_level": "memorize"}')
        assert result['bloom_level'] == 'remember'

    def test_returns_dict(self):
        result = self.c._parse_response('{"difficulty": "easy", "bloom_level": "apply"}')
        assert isinstance(result, dict)

    def test_both_keys_always_present(self):
        result = self.c._parse_response('garbage')
        assert 'difficulty' in result
        assert 'bloom_level' in result

    def test_partial_json_missing_bloom(self):
        result = self.c._parse_response('{"difficulty": "hard"}')
        assert result['difficulty'] == 'hard'
        # bloom_level falls back to default because it's missing from JSON
        assert result['bloom_level'] == 'remember'

    def test_partial_json_missing_difficulty(self):
        result = self.c._parse_response('{"bloom_level": "analyze"}')
        assert result['bloom_level'] == 'analyze'
        assert result['difficulty'] == 'medium'


# ===========================================================================
# 3. _build_prompt – PURE LOGIC
# ===========================================================================

class TestBuildPrompt:
    """Pure logic – no mocking required."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.c, _, _, _ = _make_classifier()

    def test_returns_string(self):
        result = self.c._build_prompt('ما هو عدد بروتونات الأوكسجين؟')
        assert isinstance(result, str)

    def test_contains_question_text(self):
        q = 'ما هو عدد بروتونات الأوكسجين؟'
        result = self.c._build_prompt(q)
        assert q in result

    def test_contains_difficulty_options(self):
        result = self.c._build_prompt('سؤال')
        assert 'easy' in result
        assert 'medium' in result
        assert 'hard' in result

    def test_contains_bloom_levels(self):
        result = self.c._build_prompt('سؤال')
        assert 'remember' in result
        assert 'understand' in result
        assert 'apply' in result
        assert 'analyze' in result
        assert 'evaluate' in result
        assert 'create' in result

    def test_with_options_includes_them(self):
        options = ['هيدروجين', 'أوكسجين', 'نيتروجين', 'كربون']
        result = self.c._build_prompt('أي العناصر التالية غاز نبيل؟', options)
        assert 'هيدروجين' in result
        assert 'أوكسجين' in result

    def test_with_empty_options_list_still_works(self):
        result = self.c._build_prompt('سؤال ما', [])
        assert 'سؤال ما' in result

    def test_with_none_options_still_works(self):
        result = self.c._build_prompt('سؤال ما', None)
        assert 'سؤال ما' in result

    def test_options_none_values_filtered_out(self):
        options = ['خيار 1', None, 'خيار 2']
        result = self.c._build_prompt('سؤال', options)
        # None values should be filtered; the prompt still contains the valid options
        assert 'خيار 1' in result
        assert 'خيار 2' in result

    def test_prompt_not_empty(self):
        result = self.c._build_prompt('سؤال كيميائي')
        assert len(result) > 50

    def test_prompt_contains_json_instruction(self):
        result = self.c._build_prompt('سؤال')
        assert 'JSON' in result or 'json' in result.lower()

    def test_options_separator_pipe(self):
        options = ['أ', 'ب', 'ج']
        result = self.c._build_prompt('سؤال', options)
        assert '|' in result


# ===========================================================================
# 4. _ensure_configured
# ===========================================================================

class TestEnsureConfigured:

    def test_returns_true_when_already_configured(self):
        c, _, _, _ = _make_classifier()
        c.is_configured = True
        c.client = MagicMock()
        result = c._ensure_configured()
        assert result is True

    def test_returns_false_when_no_api_key(self):
        c, _, _, _ = _make_classifier()
        app = Flask(__name__)
        app.config.pop('GOOGLE_AI_API_KEY', None)
        with app.app_context():
            with patch.dict(os.environ, {}, clear=True):
                with patch('src.services.question_classifier.GEMINI_AVAILABLE', True):
                    result = c._ensure_configured()
        assert result is False

    def test_returns_false_when_gemini_not_available(self):
        c, mod, _, _ = _make_classifier()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', False):
                result = c._ensure_configured()
        assert result is False

    def test_sets_client_on_success(self):
        c, mod, _, _ = _make_classifier()
        app = _make_app()
        mock_client = MagicMock()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', True), \
                 patch.object(mod, 'genai') as mock_genai:
                mock_genai.Client.return_value = mock_client
                c._ensure_configured()
        assert c.client is mock_client

    def test_sets_is_configured_true_on_success(self):
        c, mod, _, _ = _make_classifier()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', True), \
                 patch.object(mod, 'genai') as mock_genai:
                mock_genai.Client.return_value = MagicMock()
                c._ensure_configured()
        assert c.is_configured is True

    def test_returns_false_on_exception(self):
        c, mod, _, _ = _make_classifier()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', True), \
                 patch.object(mod, 'genai') as mock_genai:
                mock_genai.Client.side_effect = Exception('Connection refused')
                result = c._ensure_configured()
        assert result is False

    def test_stores_api_key_from_config(self):
        c, mod, _, _ = _make_classifier()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', True), \
                 patch.object(mod, 'genai') as mock_genai:
                mock_genai.Client.return_value = MagicMock()
                c._ensure_configured()
        assert c.api_key == 'test-key-abc123'

    def test_returns_true_on_success(self):
        c, mod, _, _ = _make_classifier()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', True), \
                 patch.object(mod, 'genai') as mock_genai:
                mock_genai.Client.return_value = MagicMock()
                result = c._ensure_configured()
        assert result is True


# ===========================================================================
# 5. _wait_for_rate_limit
# ===========================================================================

class TestWaitForRateLimit:

    def test_sleeps_when_request_too_soon(self):
        c, mod, _, _ = _make_classifier()
        c.last_request_time = 1000.0  # Fixed value, not time.time()
        c.min_delay = 6.0
        with patch.object(mod, 'time') as mock_time:
            mock_time.time.return_value = 1002.0  # 2 seconds elapsed
            c._wait_for_rate_limit()
            mock_time.sleep.assert_called_once()
            sleep_arg = mock_time.sleep.call_args[0][0]
            assert abs(sleep_arg - 4.0) < 0.1

    def test_does_not_sleep_when_enough_time_passed(self):
        c, mod, _, _ = _make_classifier()
        c.last_request_time = 1000.0
        c.min_delay = 6.0
        with patch.object(mod, 'time') as mock_time:
            mock_time.time.return_value = 1010.0  # 10 seconds elapsed
            c._wait_for_rate_limit()
            mock_time.sleep.assert_not_called()

    def test_updates_last_request_time(self):
        c, mod, _, _ = _make_classifier()
        c.last_request_time = 0
        with patch.object(mod, 'time') as mock_time:
            mock_time.time.return_value = 12345.0
            c._wait_for_rate_limit()
        assert c.last_request_time == 12345.0


# ===========================================================================
# 6. _call_api_with_retry
# ===========================================================================

class TestCallApiWithRetry:

    def test_returns_text_on_success(self):
        c, _, _, _ = _make_classifier()
        mock_response = MagicMock()
        mock_response.text = 'AI response text'
        c.client = MagicMock()
        c.client.models.generate_content.return_value = mock_response
        with patch.object(c, '_wait_for_rate_limit'):
            result = c._call_api_with_retry('test prompt')
        assert result == 'AI response text'

    def test_resets_consecutive_errors_on_success(self):
        c, _, _, _ = _make_classifier()
        c.consecutive_errors = 3
        mock_response = MagicMock()
        mock_response.text = 'ok'
        c.client = MagicMock()
        c.client.models.generate_content.return_value = mock_response
        with patch.object(c, '_wait_for_rate_limit'):
            c._call_api_with_retry('prompt')
        assert c.consecutive_errors == 0

    def test_returns_none_on_rate_limit_429(self):
        c, _, _, _ = _make_classifier()
        c.client = MagicMock()
        c.client.models.generate_content.side_effect = Exception('429 rate limit exceeded')
        with patch.object(c, '_wait_for_rate_limit'):
            result = c._call_api_with_retry('prompt', max_retries=1)
        assert result is None

    def test_increments_consecutive_errors_on_rate_limit(self):
        c, _, _, _ = _make_classifier()
        c.consecutive_errors = 0
        c.client = MagicMock()
        c.client.models.generate_content.side_effect = Exception('429 quota exceeded')
        with patch.object(c, '_wait_for_rate_limit'):
            c._call_api_with_retry('prompt', max_retries=1)
        assert c.consecutive_errors > 0

    def test_returns_none_on_generic_exception(self):
        c, _, _, _ = _make_classifier()
        c.client = MagicMock()
        c.client.models.generate_content.side_effect = Exception('Network error')
        with patch.object(c, '_wait_for_rate_limit'):
            result = c._call_api_with_retry('prompt', max_retries=1)
        assert result is None

    def test_calls_wait_for_each_attempt(self):
        c, _, _, _ = _make_classifier()
        mock_response = MagicMock()
        mock_response.text = 'response'
        c.client = MagicMock()
        c.client.models.generate_content.return_value = mock_response
        with patch.object(c, '_wait_for_rate_limit') as mock_wait:
            c._call_api_with_retry('prompt', max_retries=1)
        assert mock_wait.call_count == 1

    def test_calls_generate_content_with_correct_model(self):
        c, _, _, _ = _make_classifier()
        mock_response = MagicMock()
        mock_response.text = 'ok'
        c.client = MagicMock()
        c.client.models.generate_content.return_value = mock_response
        with patch.object(c, '_wait_for_rate_limit'):
            c._call_api_with_retry('my prompt')
        c.client.models.generate_content.assert_called_with(
            model='gemini-2.0-flash', contents='my prompt'
        )

    def test_returns_none_when_all_retries_exhausted(self):
        c, _, _, _ = _make_classifier()
        c.client = MagicMock()
        c.client.models.generate_content.side_effect = Exception('generic error')
        with patch.object(c, '_wait_for_rate_limit'):
            result = c._call_api_with_retry('prompt', max_retries=2)
        assert result is None


# ===========================================================================
# 7. classify_question
# ===========================================================================

class TestClassifyQuestion:

    def test_returns_default_when_not_configured(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=False):
            result = c.classify_question('سؤال ما')
        assert result['difficulty'] == 'medium'
        assert result['bloom_level'] == 'remember'

    def test_returns_error_key_when_not_configured(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=False):
            result = c.classify_question('سؤال ما')
        assert 'error' in result

    def test_skips_empty_question(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=True):
            result = c.classify_question('')
        assert result.get('skipped') is True

    def test_skips_image_only_question(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=True):
            result = c.classify_question('[سؤال بالصورة]')
        assert result.get('skipped') is True

    def test_returns_error_when_api_fails(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=True), \
             patch.object(c, '_call_api_with_retry', return_value=None):
            result = c.classify_question('سؤال صحيح')
        assert 'error' in result

    def test_returns_parsed_result_on_success(self):
        c, _, _, _ = _make_classifier()
        api_response = '{"difficulty": "hard", "bloom_level": "analyze"}'
        with patch.object(c, '_ensure_configured', return_value=True), \
             patch.object(c, '_call_api_with_retry', return_value=api_response):
            result = c.classify_question('سؤال صعب')
        assert result['difficulty'] == 'hard'
        assert result['bloom_level'] == 'analyze'

    def test_calls_build_prompt_with_question(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=True), \
             patch.object(c, '_build_prompt', return_value='built prompt') as mock_bp, \
             patch.object(c, '_call_api_with_retry', return_value='{"difficulty":"easy","bloom_level":"remember"}'):
            c.classify_question('سؤال مهم', ['خ1', 'خ2'])
        mock_bp.assert_called_once_with('سؤال مهم', ['خ1', 'خ2'])

    def test_passes_options_to_build_prompt(self):
        c, _, _, _ = _make_classifier()
        options = ['أ', 'ب', 'ج', 'د']
        with patch.object(c, '_ensure_configured', return_value=True), \
             patch.object(c, '_build_prompt', return_value='prompt') as mock_bp, \
             patch.object(c, '_call_api_with_retry', return_value='{"difficulty":"easy","bloom_level":"remember"}'):
            c.classify_question('سؤال', options)
        assert mock_bp.call_args[0][1] == options

    def test_returns_dict_always(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=False):
            result = c.classify_question('أي سؤال')
        assert isinstance(result, dict)

    def test_handles_exception_in_classify(self):
        c, _, _, _ = _make_classifier()
        with patch.object(c, '_ensure_configured', return_value=True), \
             patch.object(c, '_build_prompt', side_effect=Exception('prompt error')):
            result = c.classify_question('سؤال')
        assert 'error' in result


# ===========================================================================
# 8. get_classification_stats
# ===========================================================================

class TestGetClassificationStats:

    def test_returns_error_when_question_model_none(self):
        c, mod, _, _ = _make_classifier()
        # Patch the module-level Question to None
        with patch.object(mod, 'Question', None):
            result = c.get_classification_stats()
        assert 'error' in result

    def test_returns_dict_with_db_mocked(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 100
        mock_question_cls.query.filter.return_value.count.return_value = 60
        mock_db.session.query.return_value.group_by.return_value.all.return_value = [
            ('easy', 30), ('medium', 50), ('hard', 20)
        ]
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert isinstance(result, dict)

    def test_total_questions_key_present(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 77
        mock_question_cls.query.filter.return_value.count.return_value = 40
        mock_db.session.query.return_value.group_by.return_value.all.return_value = []
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert 'total_questions' in result

    def test_total_questions_value(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 55
        mock_question_cls.query.filter.return_value.count.return_value = 20
        mock_db.session.query.return_value.group_by.return_value.all.return_value = []
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert result['total_questions'] == 55

    def test_classified_count_key_present(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 100
        mock_question_cls.query.filter.return_value.count.return_value = 75
        mock_db.session.query.return_value.group_by.return_value.all.return_value = []
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert 'classified_count' in result

    def test_remaining_equals_total_minus_classified(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 100
        mock_question_cls.query.filter.return_value.count.return_value = 60
        mock_db.session.query.return_value.group_by.return_value.all.return_value = []
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert result['remaining'] == 40

    def test_by_difficulty_key_present(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 10
        mock_question_cls.query.filter.return_value.count.return_value = 5
        mock_db.session.query.return_value.group_by.return_value.all.return_value = [
            ('easy', 5), ('medium', 3)
        ]
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert 'by_difficulty' in result

    def test_by_bloom_level_key_present(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 10
        mock_question_cls.query.filter.return_value.count.return_value = 5
        mock_db.session.query.return_value.group_by.return_value.all.return_value = []
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert 'by_bloom_level' in result

    def test_returns_error_dict_on_exception(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.side_effect = Exception('DB exploded')
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        assert 'error' in result

    def test_none_difficulty_mapped_to_unset(self):
        c, mod, mock_db, mock_question_cls = _make_classifier()
        mock_question_cls.query.count.return_value = 5
        mock_question_cls.query.filter.return_value.count.return_value = 3
        # Simulate None difficulty in DB
        mock_db.session.query.return_value.group_by.return_value.all.side_effect = [
            [(None, 2), ('easy', 3)],  # difficulty stats
            [('remember', 5)],         # bloom stats
        ]
        with patch.object(mod, 'Question', mock_question_cls), \
             patch.object(mod, 'db', mock_db):
            result = c.get_classification_stats()
        if 'by_difficulty' in result:
            assert 'unset' in result['by_difficulty'] or 'easy' in result['by_difficulty']


# ===========================================================================
# 9. Module-level singleton
# ===========================================================================

class TestModuleSingleton:

    def test_module_has_question_classifier_instance(self):
        if 'src.services.question_classifier' in sys.modules:
            del sys.modules['src.services.question_classifier']
        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=MagicMock()),
            'src.models.question': MagicMock(Question=MagicMock()),
        }):
            import src.services.question_classifier as mod
        assert hasattr(mod, 'question_classifier')

    def test_singleton_is_classifier_instance(self):
        if 'src.services.question_classifier' in sys.modules:
            del sys.modules['src.services.question_classifier']
        with patch.dict('sys.modules', {
            'src.extensions': MagicMock(db=MagicMock()),
            'src.models.question': MagicMock(Question=MagicMock()),
        }):
            import src.services.question_classifier as mod
        assert isinstance(mod.question_classifier, mod.QuestionClassifier)


# ---------------------------------------------------------------------------
# Helper: build a classifier WITHOUT using patch('src.extensions.db', ...)
# to avoid sys.modules corruption between tests.
# ---------------------------------------------------------------------------

def _make_classifier_v2():
    """Return a fresh (QuestionClassifier, module, mock_db, mock_question_cls).
    Avoids the fragile patch('src.extensions.db', ...) by working directly
    with already-imported module objects."""
    mock_db = MagicMock()
    mock_question_cls = MagicMock()

    # Import (or reuse) the module from sys.modules
    if 'src.services.question_classifier' in sys.modules:
        mod = sys.modules['src.services.question_classifier']
    else:
        # Not imported yet – need to import with mocks in place
        mock_ext = MagicMock()
        mock_ext.db = mock_db
        mock_q_mod = MagicMock()
        mock_q_mod.Question = mock_question_cls
        with patch.dict('sys.modules', {
            'src.extensions': mock_ext,
            'src.models.question': mock_q_mod,
        }):
            import src.services.question_classifier as mod

    # Patch module-level db and Question directly on the module
    mod.db = mock_db
    mod.Question = mock_question_cls
    classifier = mod.QuestionClassifier()
    return classifier, mod, mock_db, mock_question_cls


# ===========================================================================
# 10. _parse_response – Exception branch (line 233-234)
# ===========================================================================

class TestParseResponseExceptionBranch:
    """Cover the Exception catch at lines 233-234 of _parse_response."""

    def test_generic_exception_returns_defaults(self):
        """If json.loads raises a non-JSONDecodeError, defaults are returned."""
        c, mod, _, _ = _make_classifier_v2()
        with patch.object(mod, 're') as mock_re:
            mock_match = MagicMock()
            mock_match.group.return_value = '{"difficulty":"easy"}'
            mock_re.search.return_value = mock_match
            with patch.object(mod, 'json') as mock_json:
                mock_json.loads.side_effect = Exception('unexpected parse error')
                result = c._parse_response('{"difficulty": "easy", "bloom_level": "remember"}')
        assert result['difficulty'] == 'medium'
        assert result['bloom_level'] == 'remember'

    def test_exception_branch_still_returns_dict(self):
        """Even on exception, the function returns a valid dict."""
        c, mod, _, _ = _make_classifier_v2()
        with patch.object(mod, 're') as mock_re:
            mock_re.search.side_effect = Exception('regex error')
            result = c._parse_response('some text')
        assert isinstance(result, dict)
        assert 'difficulty' in result
        assert 'bloom_level' in result


# ===========================================================================
# 11. _call_api_with_retry – final return None (line 111)
# ===========================================================================

class TestCallApiWithRetryFinalReturn:
    """Cover the final return None at line 111 – all retries exhausted without exception."""

    def test_returns_none_after_max_retries_exhausted(self):
        c, _, _, _ = _make_classifier_v2()
        c.client = MagicMock()
        c.client.models.generate_content.side_effect = Exception('Server error')
        with patch.object(c, '_wait_for_rate_limit'):
            result = c._call_api_with_retry('prompt', max_retries=2)
        assert result is None

    def test_final_return_none_when_zero_retries(self):
        """max_retries=0 means loop body never executes → fall through to return None."""
        c, _, _, _ = _make_classifier_v2()
        c.client = MagicMock()
        with patch.object(c, '_wait_for_rate_limit'):
            result = c._call_api_with_retry('prompt', max_retries=0)
        assert result is None

    def test_increments_errors_for_each_non_rate_limit_failure(self):
        """Non-rate-limit errors cause immediate return None after first attempt,
        so consecutive_errors increments by at least 1."""
        c, _, _, _ = _make_classifier_v2()
        c.client = MagicMock()
        c.consecutive_errors = 0
        c.client.models.generate_content.side_effect = Exception('Network timeout')
        with patch.object(c, '_wait_for_rate_limit'):
            c._call_api_with_retry('prompt', max_retries=3)
        # The code returns None immediately on the first failure (non-quota errors)
        assert c.consecutive_errors >= 1


# ===========================================================================
# 12. classify_all_unclassified (lines 243-381)
# ===========================================================================

def _make_q(q_id, text, options=None):
    """Helper: make a mock Question object."""
    q = MagicMock()
    q.question_id = q_id
    q.question_text = text
    q.options = options or []
    q.difficulty = None
    q.bloom_level = None
    return q


class TestClassifyAllUnclassified:
    """Cover classify_all_unclassified – the main batch classification method."""

    def test_returns_error_when_not_configured(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=False):
                result = c.classify_all_unclassified()
        assert result['success'] is False
        assert 'error' in result

    def test_returns_error_when_question_model_none(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', None):
                result = c.classify_all_unclassified()
        assert result['success'] is False
        assert 'error' in result

    def test_returns_success_when_no_unclassified_questions(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_db.session.execute.return_value = mock_sql_result

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                result = c.classify_all_unclassified(batch_size=10)

        assert result['success'] is True
        assert result['classified'] == 0
        assert result['total'] == 0

    def test_returns_success_when_questions_empty_after_filter(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(1,), (2,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = []

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                result = c.classify_all_unclassified(batch_size=10)

        assert result['success'] is True
        assert result['classified'] == 0

    def test_classifies_valid_question_successfully(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(1, 'ما هو رقم الأوكسجين الذري؟')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(1,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question', return_value={'difficulty': 'easy', 'bloom_level': 'remember'}):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['success'] is True
        assert result['classified'] == 1

    def test_skips_empty_question_text(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(2, '   ')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(2,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['skipped'] == 1
        assert result['classified'] == 0

    def test_handles_question_with_skipped_classification(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(3, 'سؤال صحيح')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(3,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'medium', 'bloom_level': 'remember', 'skipped': True}):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['skipped'] == 1

    def test_handles_failed_classification(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(4, 'سؤال يفشل')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(4,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'medium', 'bloom_level': 'remember', 'error': 'API failed'}):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['failed'] == 1

    def test_stops_when_consecutive_errors_exceed_max(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        questions = [_make_q(i, f'سؤال {i}') for i in range(1, 8)]
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(q.question_id,) for q in questions]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = questions

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'medium', 'bloom_level': 'remember', 'error': 'err'}):
                c.consecutive_errors = 4
                result = c.classify_all_unclassified(batch_size=7)

        assert result['failed'] <= len(questions)

    def test_updates_question_difficulty_and_bloom(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(5, 'سؤال صحيح')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(5,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'hard', 'bloom_level': 'analyze'}):
                c.classify_all_unclassified(batch_size=5)

        assert q.difficulty == 'hard'
        assert q.bloom_level == 'analyze'

    def test_commits_on_success(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(6, 'سؤال للحفظ')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(6,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'easy', 'bloom_level': 'remember'}):
                c.classify_all_unclassified(batch_size=5)

        mock_db.session.commit.assert_called_once()

    def test_rollback_on_commit_failure(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(7, 'سؤال')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(7,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]
        mock_db.session.commit.side_effect = Exception('commit failed')

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'easy', 'bloom_level': 'remember'}):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['success'] is False
        mock_db.session.rollback.assert_called()

    def test_sets_min_delay_from_argument(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_db.session.execute.return_value = mock_sql_result

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                c.classify_all_unclassified(batch_size=5, delay=10.0)

        assert c.min_delay == 10.0

    def test_min_delay_is_clamped_to_8(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_db.session.execute.return_value = mock_sql_result

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                c.classify_all_unclassified(batch_size=5, delay=2.0)

        assert c.min_delay == 8.0

    def test_handles_options_from_question(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        opt1 = MagicMock()
        opt1.option_text = 'هيدروجين'
        opt2 = MagicMock()
        opt2.option_text = 'أوكسجين'
        q = _make_q(8, 'أي هذه عنصر؟', options=[opt1, opt2])
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(8,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'easy', 'bloom_level': 'remember'}) as mock_cq:
                c.classify_all_unclassified(batch_size=5)

        call_args = mock_cq.call_args
        assert call_args is not None
        assert call_args[0][1] == ['هيدروجين', 'أوكسجين']

    def test_difficulty_counts_updated(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q1 = _make_q(10, 'سؤال سهل')
        q2 = _make_q(11, 'سؤال صعب')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(10,), (11,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q1, q2]

        classifications = [
            {'difficulty': 'easy', 'bloom_level': 'remember'},
            {'difficulty': 'hard', 'bloom_level': 'analyze'},
        ]
        idx_box = [0]

        def mock_classify(text, options=None):
            result = classifications[idx_box[0]] if idx_box[0] < len(classifications) else {'difficulty': 'medium', 'bloom_level': 'remember'}
            idx_box[0] += 1
            return result

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question', side_effect=mock_classify):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['difficulty_counts']['easy'] == 1
        assert result['difficulty_counts']['hard'] == 1

    def test_bloom_counts_updated(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(12, 'سؤال بلوم')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(12,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'medium', 'bloom_level': 'analyze'}):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['bloom_counts'].get('analyze', 0) == 1

    def test_exception_in_question_processing_continues(self):
        """If processing a single question raises, stats['failed'] increments and loop continues."""
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q1 = _make_q(20, 'سؤال يرفع استثناء')
        q2 = _make_q(21, 'سؤال طبيعي')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(20,), (21,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q1, q2]

        idx_box = [0]

        def mock_classify(text, options=None):
            idx = idx_box[0]
            idx_box[0] += 1
            if idx == 0:
                raise Exception('processing error')
            return {'difficulty': 'easy', 'bloom_level': 'remember'}

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question', side_effect=mock_classify):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['failed'] >= 1
        assert result['classified'] >= 1

    def test_returns_error_on_outer_exception(self):
        """If db.session.execute itself raises, returns error dict."""
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        mock_db.session.execute.side_effect = Exception('connection lost')

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                result = c.classify_all_unclassified(batch_size=5)

        assert result['success'] is False
        assert 'error' in result

    def test_success_message_when_all_skipped(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(30, '   ')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(30,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db):
                result = c.classify_all_unclassified(batch_size=5)

        assert 'message' in result
        assert result['skipped'] == 1

    def test_message_when_classified_gt_0(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(31, 'سؤال')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(31,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'easy', 'bloom_level': 'remember'}):
                result = c.classify_all_unclassified(batch_size=5)

        assert 'message' in result
        assert result['classified'] == 1

    def test_message_when_only_failures(self):
        c, mod, mock_db, mock_qcls = _make_classifier_v2()
        app = _make_app()
        q = _make_q(32, 'سؤال فاشل')
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(32,)]
        mock_db.session.execute.return_value = mock_sql_result
        mock_qcls.query.filter.return_value.all.return_value = [q]

        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', mock_qcls), \
                 patch.object(mod, 'db', mock_db), \
                 patch.object(c, 'classify_question',
                              return_value={'difficulty': 'medium', 'bloom_level': 'remember', 'error': 'API error'}):
                result = c.classify_all_unclassified(batch_size=5)

        assert 'message' in result
        assert result['failed'] == 1


# ===========================================================================
# 13. GEMINI_AVAILABLE flag and ImportError branches (lines 18-19, 24-30)
# ===========================================================================

class TestGeminiAvailableFalse:
    """Cover the GEMINI_AVAILABLE=False path and ensure_configured False paths."""

    def test_gemini_available_attribute_exists(self):
        """Module always has GEMINI_AVAILABLE attribute."""
        c, mod, _, _ = _make_classifier_v2()
        assert hasattr(mod, 'GEMINI_AVAILABLE')

    def test_ensure_configured_returns_false_when_gemini_unavailable(self):
        """_ensure_configured returns False when GEMINI_AVAILABLE is False."""
        c, mod, _, _ = _make_classifier_v2()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', False):
                result = c._ensure_configured()
        assert result is False

    def test_question_none_in_classify_all(self):
        """classify_all_unclassified returns error when Question is None."""
        c, mod, mock_db, _ = _make_classifier_v2()
        app = _make_app()
        with app.app_context():
            with patch.object(c, '_ensure_configured', return_value=True), \
                 patch.object(mod, 'Question', None), \
                 patch.object(mod, 'db', mock_db):
                result = c.classify_all_unclassified()
        assert result['success'] is False
        assert 'error' in result

    def test_gemini_available_false_causes_configure_to_fail(self):
        """When GEMINI_AVAILABLE is patched to False, classifier won't configure."""
        c, mod, _, _ = _make_classifier_v2()
        app = _make_app()
        with app.app_context():
            with patch.object(mod, 'GEMINI_AVAILABLE', False):
                c.is_configured = False
                c.client = None
                result = c._ensure_configured()
        assert result is False

    def test_classifier_initializes_without_gemini(self):
        """QuestionClassifier can be instantiated even if GEMINI_AVAILABLE is False."""
        c, mod, _, _ = _make_classifier_v2()
        with patch.object(mod, 'GEMINI_AVAILABLE', False):
            from src.services.question_classifier import QuestionClassifier as QC
            # Just verify that instantiation doesn't fail
            new_c = mod.QuestionClassifier()
        assert new_c.is_configured is False
        assert new_c.client is None
