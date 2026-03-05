"""
إعداد بيئة الاختبار المشتركة
يُشغَّل تلقائياً قبل كل الاختبارات
"""
import pytest
import sys
import os
from unittest.mock import MagicMock

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ===== إصلاح hashlib.scrypt لـ Python 3.9 =====
# macOS Python 3.9 لا يدعم scrypt - نضيف stub يعمل بـ pbkdf2
import hashlib
if not hasattr(hashlib, 'scrypt'):
    def _scrypt_stub(password, *, salt, n=16384, r=8, p=1, maxmem=0, dklen=64):
        """Fallback لـ scrypt باستخدام pbkdf2 (للاختبارات فقط)"""
        return hashlib.pbkdf2_hmac('sha256', password, salt, 100000, dklen)
    hashlib.scrypt = _scrypt_stub

# ===== Mock الخدمات الخارجية قبل أي استيراد =====
# Firebase
firebase_mock = MagicMock()
sys.modules['firebase_admin'] = firebase_mock
sys.modules['firebase_admin.credentials'] = firebase_mock
sys.modules['firebase_admin.messaging'] = firebase_mock
sys.modules['firebase_admin.auth'] = firebase_mock

# flask_socketio (غير مثبت في بيئة الاختبار)
socketio_mock = MagicMock()
sys.modules['flask_socketio'] = socketio_mock

# تجاوز ARRAY و JSONB من PostgreSQL - SQLite لا يدعمها
from sqlalchemy import Text, JSON
import sqlalchemy.dialects.postgresql as pg
pg.ARRAY = lambda *args, **kwargs: Text()
pg.JSONB = JSON


@pytest.fixture(scope='session')
def app():
    """إنشاء تطبيق Flask للاختبار - مرة واحدة لكل session"""
    os.environ['FLASK_ENV'] = 'testing'

    from src.main import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    application.config['PROPAGATE_EXCEPTIONS'] = False  # لا نريد exceptions تنكسر الاختبارات

    yield application


@pytest.fixture(scope='session')
def db(app):
    """إنشاء قاعدة البيانات التجريبية - مرة واحدة لكل session"""
    from src.extensions import db as _db

    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """HTTP test client - جديد لكل اختبار"""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(db, app):
    """جلسة DB نظيفة لكل اختبار - يُحذف كل شي بعد الانتهاء"""
    with app.app_context():
        yield db
        # تنظيف بعد كل اختبار
        db.session.rollback()
        from sqlalchemy import text
        db.session.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.execute(text("PRAGMA foreign_keys = ON"))
        db.session.commit()


# ===== Fixtures: بيانات تجريبية =====
# ملاحظة: لا نستخدم "with app.app_context()" هنا لأن db_session يوفره بالفعل

@pytest.fixture
def admin_user(db_session, app):
    """أدمن تجريبي"""
    from src.models.user import User
    user = User(username='test_admin', email='admin@test.com', is_admin=True)
    user.set_password('Admin@123')
    db_session.session.add(user)
    db_session.session.commit()
    db_session.session.refresh(user)
    return user


@pytest.fixture
def student_user(db_session, app):
    """طالب تجريبي"""
    from src.models.student import Student
    student = Student(
        name='طالب تجريبي',
        username='test_student',
        email='student@test.com',
        is_active=True
    )
    student.set_password('Student@123')
    db_session.session.add(student)
    db_session.session.commit()
    db_session.session.refresh(student)
    return student


@pytest.fixture
def inactive_student(db_session, app):
    """طالب معطّل الحساب"""
    from src.models.student import Student
    student = Student(
        name='طالب معطّل',
        username='inactive_student',
        email='inactive@test.com',
        is_active=False
    )
    student.set_password('Student@123')
    db_session.session.add(student)
    db_session.session.commit()
    db_session.session.refresh(student)
    return student


@pytest.fixture
def sample_course(db_session, app):
    """منهج تجريبي"""
    from src.models.curriculum import Course
    course = Course(name='كيمياء - اختبار', order_num=1, show_in_bot=True)
    db_session.session.add(course)
    db_session.session.commit()
    db_session.session.refresh(course)
    return course


@pytest.fixture
def sample_course_hidden(db_session, app):
    """منهج مخفي عن البوت"""
    from src.models.curriculum import Course
    course = Course(name='كيمياء - مخفي', order_num=2, show_in_bot=False)
    db_session.session.add(course)
    db_session.session.commit()
    db_session.session.refresh(course)
    return course


@pytest.fixture
def sample_unit(db_session, sample_course, app):
    """وحدة تجريبية"""
    from src.models.curriculum import Unit
    unit = Unit(
        name='المحاليل - اختبار',
        course_id=sample_course.id,
        order_num=1,
        show_in_bot=True
    )
    db_session.session.add(unit)
    db_session.session.commit()
    db_session.session.refresh(unit)
    return unit


@pytest.fixture
def sample_lesson(db_session, sample_unit, app):
    """درس تجريبي"""
    from src.models.curriculum import Lesson
    lesson = Lesson(
        name='أنواع المحاليل - اختبار',
        unit_id=sample_unit.id,
        order_num=1,
        show_in_bot=True
    )
    db_session.session.add(lesson)
    db_session.session.commit()
    db_session.session.refresh(lesson)
    return lesson
