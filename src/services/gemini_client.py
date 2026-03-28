# src/services/gemini_client.py
"""
مدير مفاتيح Gemini المركزي
- يدعم مفتاحين: GOOGLE_AI_API_KEY و GOOGLE_AI_API_KEY_2
- ينتقل تلقائياً للمفتاح الثاني عند نفاد الأول (429 / quota)
- كل الخدمات تستخدم هذا المدير بدل إنشاء client مستقل
"""

import os
import logging

logger = logging.getLogger(__name__)

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiKeyManager:
    """مدير مفاتيح Gemini مع دعم التحويل التلقائي"""

    def __init__(self):
        self._keys = []
        self._current_index = 0
        self._client = None

    def _load_keys(self):
        key1 = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')
        key2 = os.getenv('GOOGLE_AI_API_KEY_2')
        self._keys = [k for k in [key1, key2] if k]
        self._current_index = 0
        self._client = None

    def get_client(self):
        """يرجع الـ client الحالي — ينشئه إذا لم يكن موجوداً"""
        if not self._keys:
            self._load_keys()
        if not self._keys or not GEMINI_AVAILABLE:
            return None
        if self._client is None:
            self._client = genai.Client(api_key=self._keys[self._current_index])
        return self._client

    def rotate_key(self) -> bool:
        """ينتقل للمفتاح التالي — يرجع True إذا نجح، False إذا ما في مفاتيح ثانية"""
        next_index = self._current_index + 1
        if next_index < len(self._keys):
            self._current_index = next_index
            self._client = genai.Client(api_key=self._keys[self._current_index])
            logger.warning(f"🔄 تحويل لمفتاح Gemini رقم {self._current_index + 1}")
            return True
        logger.error("❌ خلصت كل مفاتيح Gemini")
        return False

    def get_current_key(self) -> str:
        """يرجع المفتاح الحالي كـ string (للخدمات اللي تحتاج المفتاح مباشرة)"""
        if not self._keys:
            self._load_keys()
        return self._keys[self._current_index] if self._keys else ''

    def is_quota_error(self, error_str: str) -> bool:
        return '429' in error_str or 'quota' in error_str.lower() or 'resource_exhausted' in error_str.lower()


# singleton — كل الخدمات تستورد هذا
gemini_key_manager = GeminiKeyManager()
