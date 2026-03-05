# قواعد العمل على مشروع question_manager

## قاعدة الاختبارات (إلزامية)
**عند إنشاء أو تعديل أي ملف Python في `src/`، يجب إضافة اختبارات مقابلة في `tests/integration/`.**

- كل route جديد → اختبار `test_<route>_no_auth` + `test_<route>_as_admin`
- كل model جديد → اختبار في `test_models.py`
- كل service جديد → اختبار في ملف مخصص
- أمر التحقق: `python3 -m pytest tests/integration/ -q --tb=short --ignore=tests/integration/test_students_api.py --ignore=tests/integration/test_api_comprehensive.py --ignore=tests/integration/test_api_extended.py`

## قواعد عامة
- لا تُعدّل ملفات الـ migration يدوياً - استخدم alembic
- قاعدة البيانات الحقيقية: PostgreSQL على Render
- بيئة الاختبار: SQLite in-memory (عبر pytest fixtures)
- الـ CI/CD يشتغل على GitHub Actions عند كل push
