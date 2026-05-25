"""
سكريبت ترحيل — يشفّر البيانات الموجودة في DB مرة وحدة
شغّله بعد رفع الكود الجديد على Render:
    python migrate_encrypt_fields.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('FLASK_ENV', 'production')

from src.main import create_app
from src.extensions import db
from src.utils.field_encryption import encrypt, make_email_hash

app = create_app()


def migrate_students():
    rows = db.session.execute(db.text(
        "SELECT id, phone, email, device_id, fcm_token, session_token FROM students"
    )).fetchall()

    count = 0
    for r in rows:
        sid, phone, email, device_id, fcm_token, session_token = r

        # نتجاهل البيانات المشفرة مسبقاً (تبدأ بـ gAAAAA — Fernet prefix)
        def needs_enc(val):
            return val and not val.startswith('gAAAAA')

        updates = {}
        if needs_enc(phone):      updates['phone']         = encrypt(phone)
        if needs_enc(email):
            updates['email']      = encrypt(email)
            updates['email_hash'] = make_email_hash(email)
        if needs_enc(device_id):  updates['device_id']     = encrypt(device_id)
        if needs_enc(fcm_token):  updates['fcm_token']     = encrypt(fcm_token)
        if needs_enc(session_token): updates['session_token'] = encrypt(session_token)

        if updates:
            set_clause = ', '.join(f"{k} = :{k}" for k in updates)
            updates['sid'] = sid
            db.session.execute(
                db.text(f"UPDATE students SET {set_clause} WHERE id = :sid"),
                updates
            )
            count += 1

    db.session.commit()
    print(f'✅ students: شُفِّر {count} سجل')


def migrate_teachers():
    rows = db.session.execute(db.text(
        "SELECT id, phone, email, device_id, fcm_token, session_token FROM teachers"
    )).fetchall()

    count = 0
    for r in rows:
        tid, phone, email, device_id, fcm_token, session_token = r

        def needs_enc(val):
            return val and not val.startswith('gAAAAA')

        updates = {}
        if needs_enc(phone):      updates['phone']         = encrypt(phone)
        if needs_enc(email):
            updates['email']      = encrypt(email)
            updates['email_hash'] = make_email_hash(email)
        if needs_enc(device_id):  updates['device_id']     = encrypt(device_id)
        if needs_enc(fcm_token):  updates['fcm_token']     = encrypt(fcm_token)
        if needs_enc(session_token): updates['session_token'] = encrypt(session_token)

        if updates:
            set_clause = ', '.join(f"{k} = :{k}" for k in updates)
            updates['tid'] = tid
            db.session.execute(
                db.text(f"UPDATE teachers SET {set_clause} WHERE id = :tid"),
                updates
            )
            count += 1

    db.session.commit()
    print(f'✅ teachers: شُفِّر {count} سجل')


def migrate_users():
    rows = db.session.execute(db.text(
        'SELECT id, phone_number, email, trusted_device_token, fcm_token FROM "user"'
    )).fetchall()

    count = 0
    for r in rows:
        uid, phone, email, device_token, fcm_token = r

        def needs_enc(val):
            return val and not val.startswith('gAAAAA')

        updates = {}
        if needs_enc(phone):        updates['phone_number']        = encrypt(phone)
        if needs_enc(email):
            updates['email']         = encrypt(email)
            updates['email_hash']    = make_email_hash(email)
        if needs_enc(device_token): updates['trusted_device_token'] = encrypt(device_token)
        if needs_enc(fcm_token):    updates['fcm_token']            = encrypt(fcm_token)

        if updates:
            set_clause = ', '.join(f"{k} = :{k}" for k in updates)
            updates['uid'] = uid
            db.session.execute(
                db.text(f'UPDATE "user" SET {set_clause} WHERE id = :uid'),
                updates
            )
            count += 1

    db.session.commit()
    print(f'✅ user: شُفِّر {count} سجل')


if __name__ == '__main__':
    with app.app_context():
        print('🔐 بدء تشفير البيانات الموجودة...')
        migrate_students()
        migrate_teachers()
        migrate_users()
        print('✅ انتهى التشفير بنجاح')
