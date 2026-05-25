"""
تشفير الحقول الحساسة في DB
يستخدم مفتاحين من متغيرات البيئة:
  FIELD_ENC_KEY_1 — في Render
  FIELD_ENC_KEY_2 — عند المستخدم + في Render
المفتاح الفعلي = SHA256(KEY_1 + KEY_2) لا يُخزَّن أي مكان
"""

import os
import hashlib
import hmac
import base64
import logging
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import types

logger = logging.getLogger(__name__)

_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is not None:
        return _cipher

    key1 = os.getenv('KEY_1', '')
    key2 = os.getenv('KEY_2', '')

    if not key1 or not key2:
        raise RuntimeError(
            'KEY_1 و KEY_2 غير موجودين في متغيرات البيئة'
        )

    combined = (key1 + key2).encode('utf-8')
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(combined).digest())
    _cipher = Fernet(fernet_key)
    return _cipher


def encrypt(value: str | None) -> str | None:
    """يشفّر النص — يرجع None لو القيمة None"""
    if value is None:
        return None
    try:
        return _get_cipher().encrypt(value.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.error(f'❌ field_encryption.encrypt: {e}')
        raise


def decrypt(value: str | None) -> str | None:
    """يفك تشفير النص — يرجع None لو القيمة None أو غير مشفرة"""
    if value is None:
        return None
    try:
        return _get_cipher().decrypt(value.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        # القيمة غير مشفرة (بيانات قديمة قبل التشفير) — نرجعها كما هي
        return value
    except Exception as e:
        logger.error(f'❌ field_encryption.decrypt: {e}')
        return value


def make_email_hash(email: str | None) -> str | None:
    """HMAC-SHA256 للإيميل — للبحث والتحقق من التفرد بدون فك التشفير"""
    if not email:
        return None
    key1 = os.getenv('KEY_1', '').encode('utf-8')
    return hmac.new(key1, email.lower().strip().encode('utf-8'),
                    hashlib.sha256).hexdigest()


# ── SQLAlchemy TypeDecorator — تشفير شفاف تلقائي ──────────────
class EncryptedString(types.TypeDecorator):
    """
    نوع عمود مشفر — يشفّر عند الحفظ ويفك عند القراءة تلقائياً.
    استخدام:
        phone = db.Column(EncryptedString(500), nullable=True)
    """
    impl = types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """قبل الحفظ في DB — شفّر"""
        return encrypt(value)

    def process_result_value(self, value, dialect):
        """بعد القراءة من DB — افك التشفير"""
        return decrypt(value)
