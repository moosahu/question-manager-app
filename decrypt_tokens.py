"""
سكريبت لفك تشفير session_token و device_id فقط
(هذين الحقلين رجعا String عادي في الموديل)
شغّله مرة وحدة:
    KEY_1=<...> KEY_2=<...> python decrypt_tokens.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'development')

from src.main import create_app
from src.extensions import db
from src.utils.field_encryption import decrypt

app = create_app()

TABLES = [
    ('students', 'id', ['session_token', 'device_id']),
    ('teachers', 'id', ['session_token', 'device_id']),
]

with app.app_context():
    print('🔓 فك تشفير session_token و device_id...')
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
                    plain = decrypt(val)
                    if plain != val:  # كانت مشفّرة
                        updates[col] = plain

            if updates:
                set_clause = ', '.join(f"{c} = :{c}" for c in updates)
                updates[pk] = rid
                db.session.execute(
                    db.text(f"UPDATE {table} SET {set_clause} WHERE {pk} = :{pk}"),
                    updates
                )
                count += 1

        db.session.commit()
        print(f'✅ {table}: فُك تشفير {count} سجل')

    print('✅ انتهى')
