"""
سكريبت إعادة التشفير — لو غيّرت KEY_1 أو KEY_2
الاستخدام:
    OLD_KEY_1=<القديم> OLD_KEY_2=<القديم> KEY_1=<الجديد> KEY_2=<الجديد> python reencrypt_fields.py
"""

import os
import sys
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'production')

from src.main import create_app
from src.extensions import db

# ── المفاتيح القديمة ──────────────────────────────────────────
old_k1 = os.environ.get('OLD_KEY_1', '')
old_k2 = os.environ.get('OLD_KEY_2', '')
# ── المفاتيح الجديدة ──────────────────────────────────────────
new_k1 = os.environ.get('KEY_1', '')
new_k2 = os.environ.get('KEY_2', '')

if not all([old_k1, old_k2, new_k1, new_k2]):
    print('❌ يجب تحديد OLD_KEY_1 و OLD_KEY_2 و KEY_1 و KEY_2')
    sys.exit(1)


def _make_cipher(k1, k2):
    combined = (k1 + k2).encode('utf-8')
    key = base64.urlsafe_b64encode(hashlib.sha256(combined).digest())
    return Fernet(key)


old_cipher = _make_cipher(old_k1, old_k2)
new_cipher = _make_cipher(new_k1, new_k2)


def reenc(value):
    if not value:
        return value
    try:
        plain = old_cipher.decrypt(value.encode()).decode()
        return new_cipher.encrypt(plain.encode()).decode()
    except InvalidToken:
        # القيمة غير مشفرة أصلاً — شفّرها بالمفاتيح الجديدة
        return new_cipher.encrypt(value.encode()).decode()


app = create_app()

TABLES = [
    ('students', 'id',   ['phone', 'email', 'device_id', 'fcm_token', 'session_token']),
    ('teachers', 'id',   ['phone', 'email', 'device_id', 'fcm_token', 'session_token']),
    ('"user"',   'id',   ['phone_number', 'email', 'trusted_device_token', 'fcm_token']),
]

with app.app_context():
    print('🔄 بدء إعادة التشفير بالمفاتيح الجديدة...')
    for table, pk, cols in TABLES:
        rows = db.session.execute(
            db.text(f"SELECT {pk}, {', '.join(cols)} FROM {table}")
        ).fetchall()

        count = 0
        for row in rows:
            rid = row[0]
            updates = {}
            for i, col in enumerate(cols):
                val = row[i + 1]
                if val:
                    updates[col] = reenc(val)

            if updates:
                set_clause = ', '.join(f"{c} = :{c}" for c in updates)
                updates[pk] = rid
                db.session.execute(
                    db.text(f"UPDATE {table} SET {set_clause} WHERE {pk} = :{pk}"),
                    updates
                )
                count += 1

        db.session.commit()
        print(f'✅ {table}: أُعيد تشفير {count} سجل')

    print('✅ انتهت إعادة التشفير')
