# src/services/claude_client.py
"""
مدير مفاتيح Claude المركزي
- يدعم مفتاحين: CLAUDE_AI_API_KEY و CLAUDE_AI_API_KEY_2
- ينتقل تلقائياً للمفتاح الثاني عند نفاد الأول (429 / rate limit)
- كل الخدمات تستخدم هذا المدير بدل إنشاء client مستقل
"""

import os
import logging

logger = logging.getLogger(__name__)

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


class ClaudeKeyManager:
    """مدير مفاتيح Claude مع دعم التحويل التلقائي"""

    def __init__(self):
        self._keys = []
        self._current_index = 0
        self._client = None

    def _load_keys(self):
        key1 = os.getenv('CLAUDE_AI_API_KEY')
        key2 = os.getenv('CLAUDE_AI_API_KEY_2')
        self._keys = [k for k in [key1, key2] if k]
        self._current_index = 0
        self._client = None

    def get_client(self):
        """يرجع الـ client الحالي — ينشئه إذا لم يكن موجوداً"""
        if not self._keys:
            self._load_keys()
        if not self._keys or not CLAUDE_AVAILABLE:
            return None
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._keys[self._current_index])
        return self._client

    def rotate_key(self) -> bool:
        """ينتقل للمفتاح التالي — يرجع True إذا نجح، False إذا ما في مفاتيح ثانية"""
        next_index = self._current_index + 1
        if next_index < len(self._keys):
            self._current_index = next_index
            self._client = anthropic.Anthropic(api_key=self._keys[self._current_index])
            logger.warning(f"🔄 تحويل لمفتاح Claude رقم {self._current_index + 1}")
            return True
        logger.error("❌ خلصت كل مفاتيح Claude")
        return False

    def get_current_key(self) -> str:
        """يرجع المفتاح الحالي كـ string"""
        if not self._keys:
            self._load_keys()
        return self._keys[self._current_index] if self._keys else ''

    def is_quota_error(self, error_str: str) -> bool:
        return '429' in error_str or 'rate_limit' in error_str.lower() or 'overloaded' in error_str.lower()


# singleton — كل الخدمات تستورد هذا
claude_key_manager = ClaudeKeyManager()
