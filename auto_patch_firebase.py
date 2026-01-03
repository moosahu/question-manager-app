#!/usr/bin/env python3
"""
auto_patch_firebase.py
إضافة Firebase initialization تلقائياً إلى main.py
"""

import os
import shutil
from datetime import datetime

FIREBASE_INIT_CODE = '''
# ✅ تهيئة Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials
    import json
    
    try:
        firebase_admin.get_app()
        logger.info("✅ Firebase already initialized")
    except ValueError:
        firebase_config_json = os.getenv('FIREBASE_CONFIG') or os.getenv('FIREBASE_CREDENTIALS_JSON')
        
        if firebase_config_json:
            try:
                firebase_config = json.loads(firebase_config_json)
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase initialized from environment variable")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid Firebase config JSON: {e}")
        elif os.path.exists('serviceAccountKey.json'):
            cred = credentials.Certificate('serviceAccountKey.json')
            firebase_admin.initialize_app(cred)
            logger.info("✅ Firebase initialized from serviceAccountKey.json")
        else:
            logger.warning("⚠️  No Firebase credentials found")
            logger.warning("💡 Push notifications disabled")
except ImportError:
    logger.warning("⚠️  Firebase Admin SDK not installed")
except Exception as e:
    logger.error(f"❌ Firebase error: {e}")
'''

print("=" * 70)
print("🔧 Auto-Patch Firebase Initialization")
print("=" * 70)

# 1. Find main.py
main_paths = ['main.py', 'src/main.py', 'app.py']
main_path = None

for path in main_paths:
    if os.path.exists(path):
        main_path = path
        break

if not main_path:
    print("\n❌ main.py not found!")
    print(f"   Searched in: {main_paths}")
    exit(1)

print(f"\n✅ Found: {main_path}")

# 2. Backup
backup_path = f"{main_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy(main_path, backup_path)
print(f"✅ Backup created: {backup_path}")

# 3. Read file
with open(main_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 4. Check if already patched
already_patched = any('firebase_admin.initialize_app' in line for line in lines)

if already_patched:
    print("\n⚠️  Firebase initialization already exists!")
    print("   Skipping patch.")
    exit(0)

# 5. Find insertion point (after load_dotenv)
insert_index = None
for i, line in enumerate(lines):
    if 'load_dotenv()' in line:
        # Find next non-empty, non-comment line
        for j in range(i + 1, len(lines)):
            if lines[j].strip() and not lines[j].strip().startswith('#'):
                insert_index = j
                break
        break

if insert_index is None:
    print("\n❌ Could not find insertion point (load_dotenv)")
    exit(1)

print(f"✅ Found insertion point at line {insert_index + 1}")

# 6. Insert Firebase code
firebase_lines = FIREBASE_INIT_CODE.split('\n')
lines[insert_index:insert_index] = [line + '\n' for line in firebase_lines]

# 7. Write file
with open(main_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"✅ Patched {main_path}")

# 8. Verify
with open(main_path, 'r', encoding='utf-8') as f:
    content = f.read()
    
has_init = 'firebase_admin.initialize_app' in content
has_config = 'FIREBASE_CONFIG' in content

print("\n" + "=" * 70)
print("📊 Verification:")
print("=" * 70)
print(f"{'✅' if has_init else '❌'} firebase_admin.initialize_app found")
print(f"{'✅' if has_config else '❌'} FIREBASE_CONFIG check found")

if has_init and has_config:
    print("\n✅ Patch successful!")
    print("\n📝 Next steps:")
    print("   1. Review changes: git diff main.py")
    print("   2. Commit: git add main.py")
    print("   3. Commit: git commit -m 'Add Firebase initialization'")
    print("   4. Push: git push origin main")
    print("\n   Render will auto-deploy in ~2 minutes")
else:
    print("\n❌ Patch may have failed")
    print(f"   Restore backup: cp {backup_path} {main_path}")

print("\n" + "=" * 70)
