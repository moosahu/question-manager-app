"""
اختبارات شاملة للنماذج (Models)
يغطي: Student, Teacher, Curriculum (Course/Unit/Lesson), Question/Option
"""
import pytest
from datetime import datetime


class TestStudentModel:
    """اختبارات نموذج الطالب"""

    def test_create_student(self, db_session, app):
        """إنشاء طالب جديد"""
        from src.models.student import Student
        s = Student(name='أحمد علي', username='ahmed_ali', email='ahmed@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        found = Student.query.filter_by(username='ahmed_ali').first()
        assert found is not None
        assert found.name == 'أحمد علي'

    def test_password_hash_not_plain(self, db_session, app):
        """كلمة المرور مشفرة وليست نصًا"""
        from src.models.student import Student
        s = Student(name='Test', username='plain_test', email='plain@test.com')
        s.set_password('Secret@123')
        assert s.password_hash != 'Secret@123'
        assert len(s.password_hash) > 20

    def test_check_password_correct(self, db_session, app):
        """التحقق من كلمة المرور الصحيحة"""
        from src.models.student import Student
        s = Student(name='Test', username='check_pass', email='check@test.com')
        s.set_password('Correct@Pass')
        assert s.check_password('Correct@Pass') is True

    def test_check_password_wrong(self, db_session, app):
        """رفض كلمة المرور الخاطئة"""
        from src.models.student import Student
        s = Student(name='Test', username='wrong_pass', email='wrong@test.com')
        s.set_password('Correct@Pass')
        assert s.check_password('Wrong@Pass') is False

    def test_update_last_login(self, db_session, app):
        """تحديث وقت آخر تسجيل دخول"""
        from src.models.student import Student
        s = Student(name='Login', username='login_test', email='login@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        s.update_last_login()
        db_session.session.refresh(s)
        assert s.last_login is not None

    def test_update_device_info(self, db_session, app):
        """تحديث معلومات الجهاز"""
        from src.models.student import Student
        s = Student(name='Device', username='device_test', email='device@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        s.update_device_info('device_123', 'iPhone 14')
        db_session.session.refresh(s)
        assert s.device_id == 'device_123'
        assert s.device_name == 'iPhone 14'

    def test_update_device_info_default_name(self, db_session, app):
        """اسم الجهاز الافتراضي عند عدم تحديده"""
        from src.models.student import Student
        s = Student(name='Device2', username='device_test2', email='device2@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        s.update_device_info('dev_456')
        db_session.session.refresh(s)
        assert s.device_name == 'جهاز غير معروف'

    def test_clear_device_info(self, db_session, app):
        """مسح معلومات الجهاز"""
        from src.models.student import Student
        s = Student(name='Clear', username='clear_device', email='clear@test.com')
        s.set_password('Pass@123')
        s.device_id = 'some_device'
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        s.clear_device_info()
        db_session.session.refresh(s)
        assert s.device_id is None
        assert s.session_token is None

    def test_is_same_device_true(self, app):
        """نفس الجهاز"""
        from src.models.student import Student
        with app.app_context():
            s = Student(name='T', username='t1', email='t1@t.com')
            s.device_id = 'abc'
            assert s.is_same_device('abc') is True

    def test_is_same_device_false(self, app):
        """جهاز مختلف"""
        from src.models.student import Student
        with app.app_context():
            s = Student(name='T', username='t2', email='t2@t.com')
            s.device_id = 'abc'
            assert s.is_same_device('xyz') is False

    def test_is_same_device_no_device(self, app):
        """لا يوجد جهاز مسجل - يسمح بالدخول"""
        from src.models.student import Student
        with app.app_context():
            s = Student(name='T', username='t3', email='t3@t.com')
            s.device_id = None
            assert s.is_same_device('any_device') is True

    def test_has_registered_device_true(self, app):
        """يوجد جهاز مسجل"""
        from src.models.student import Student
        with app.app_context():
            s = Student(name='T', username='t4', email='t4@t.com')
            s.device_id = 'dev'
            assert s.has_registered_device() is True

    def test_has_registered_device_false(self, app):
        """لا يوجد جهاز مسجل"""
        from src.models.student import Student
        with app.app_context():
            s = Student(name='T', username='t5', email='t5@t.com')
            s.device_id = None
            assert s.has_registered_device() is False

    def test_update_fcm_token(self, db_session, app):
        """تحديث FCM Token"""
        from src.models.student import Student
        s = Student(name='FCM', username='fcm_student', email='fcm@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        s.update_fcm_token('fcm_token_xyz')
        db_session.session.refresh(s)
        assert s.fcm_token == 'fcm_token_xyz'
        assert s.fcm_token_updated_at is not None

    def test_clear_fcm_token(self, db_session, app):
        """مسح FCM Token"""
        from src.models.student import Student
        s = Student(name='FCMClear', username='fcm_clear', email='fcmclear@test.com')
        s.set_password('Pass@123')
        s.fcm_token = 'some_token'
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        s.clear_fcm_token()
        db_session.session.refresh(s)
        assert s.fcm_token is None

    def test_get_active_students(self, db_session, app):
        """جلب الطلاب المفعلين فقط"""
        from src.models.student import Student
        s1 = Student(name='Active', username='active_s', email='active_s@test.com', is_active=True)
        s1.set_password('Pass@123')
        s2 = Student(name='Inactive', username='inactive_s', email='inactive_s@test.com', is_active=False)
        s2.set_password('Pass@123')
        db_session.session.add_all([s1, s2])
        db_session.session.commit()
        active = Student.get_active_students()
        usernames = [s.username for s in active]
        assert 'active_s' in usernames
        assert 'inactive_s' not in usernames

    def test_get_all_students(self, db_session, app):
        """جلب جميع الطلاب"""
        from src.models.student import Student
        s = Student(name='All', username='all_test', email='all@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        all_students = Student.get_all_students()
        assert len(all_students) >= 1

    def test_search_students(self, db_session, app):
        """البحث عن الطلاب بالاسم"""
        from src.models.student import Student
        s = Student(name='محمد خالد', username='mohammed_khalid', email='mk@test.com')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        results = Student.search_students('محمد')
        names = [r.name for r in results]
        assert 'محمد خالد' in names

    def test_get_students_with_fcm_tokens(self, db_session, app):
        """جلب الطلاب الذين لديهم FCM Tokens"""
        from src.models.student import Student
        s = Student(name='FCMList', username='fcm_list', email='fcmlist@test.com', is_active=True)
        s.set_password('Pass@123')
        s.fcm_token = 'valid_token'
        db_session.session.add(s)
        db_session.session.commit()
        with_tokens = Student.get_students_with_fcm_tokens()
        assert any(st.username == 'fcm_list' for st in with_tokens)

    def test_get_students_by_grade(self, db_session, app):
        """جلب الطلاب حسب الصف"""
        from src.models.student import Student
        s = Student(name='Grade', username='grade_student', email='grade@test.com', grade='ثالث ثانوي', is_active=True)
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        graders = Student.get_students_by_grade('ثالث ثانوي')
        assert any(st.username == 'grade_student' for st in graders)

    def test_get_students_with_devices(self, db_session, app):
        """جلب الطلاب الذين لديهم أجهزة مسجلة"""
        from src.models.student import Student
        s = Student(name='WithDev', username='with_device', email='withdev@test.com')
        s.set_password('Pass@123')
        s.device_id = 'registered_device'
        db_session.session.add(s)
        db_session.session.commit()
        with_devices = Student.get_students_with_devices()
        assert any(st.username == 'with_device' for st in with_devices)

    def test_to_dict(self, db_session, app):
        """تحويل الطالب لـ dictionary"""
        from src.models.student import Student
        s = Student(name='Dict', username='dict_student', email='dict@test.com', grade='أول ثانوي')
        s.set_password('Pass@123')
        db_session.session.add(s)
        db_session.session.commit()
        db_session.session.refresh(s)
        d = s.to_dict()
        assert d['username'] == 'dict_student'
        assert d['grade'] == 'أول ثانوي'
        assert 'password_hash' not in d

    def test_repr(self, app):
        """__repr__ يعمل بشكل صحيح"""
        from src.models.student import Student
        with app.app_context():
            s = Student(name='T', username='repr_test', email='repr@test.com')
            assert 'repr_test' in repr(s)


class TestTeacherModel:
    """اختبارات نموذج المعلم"""

    def test_create_teacher(self, db_session, app):
        """إنشاء معلم جديد"""
        from src.models.teacher import Teacher
        t = Teacher(name='مريم أحمد', username='mariam_t', email='mariam@test.com')
        t.set_password('Teacher@123')
        db_session.session.add(t)
        db_session.session.commit()
        found = Teacher.query.filter_by(username='mariam_t').first()
        assert found is not None
        assert found.name == 'مريم أحمد'

    def test_teacher_password(self, app):
        """تشفير كلمة مرور المعلم"""
        from src.models.teacher import Teacher
        with app.app_context():
            t = Teacher(name='T', username='t_pass', email='tpass@test.com')
            t.set_password('Teacher@Pass')
            assert t.password_hash != 'Teacher@Pass'
            assert t.check_password('Teacher@Pass') is True
            assert t.check_password('Wrong') is False

    def test_teacher_update_last_login(self, db_session, app):
        """تحديث وقت آخر تسجيل دخول للمعلم"""
        from src.models.teacher import Teacher
        t = Teacher(name='Login', username='t_login', email='tlogin@test.com')
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        t.update_last_login()
        db_session.session.refresh(t)
        assert t.last_login is not None

    def test_teacher_device_info(self, db_session, app):
        """تحديث ومسح معلومات الجهاز للمعلم"""
        from src.models.teacher import Teacher
        t = Teacher(name='Device', username='t_device', email='tdevice@test.com')
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        t.update_device_info('dev_t_001', 'iPad Pro')
        db_session.session.refresh(t)
        assert t.device_id == 'dev_t_001'
        assert t.device_name == 'iPad Pro'
        t.clear_device_info()
        db_session.session.refresh(t)
        assert t.device_id is None

    def test_teacher_is_same_device(self, app):
        """التحقق من الجهاز للمعلم"""
        from src.models.teacher import Teacher
        with app.app_context():
            t = Teacher(name='T', username='t_same', email='tsame@test.com')
            t.device_id = 'dev_123'
            assert t.is_same_device('dev_123') is True
            assert t.is_same_device('other') is False
            t.device_id = None
            assert t.is_same_device('any') is True

    def test_teacher_get_active(self, db_session, app):
        """جلب المعلمين المفعلين"""
        from src.models.teacher import Teacher
        t1 = Teacher(name='Active T', username='active_t', email='activet@test.com', is_active=True)
        t1.set_password('Pass@123')
        t2 = Teacher(name='Inactive T', username='inactive_t', email='inactivet@test.com', is_active=False)
        t2.set_password('Pass@123')
        db_session.session.add_all([t1, t2])
        db_session.session.commit()
        active = Teacher.get_active_teachers()
        usernames = [t.username for t in active]
        assert 'active_t' in usernames
        assert 'inactive_t' not in usernames

    def test_teacher_search(self, db_session, app):
        """البحث عن معلمين"""
        from src.models.teacher import Teacher
        t = Teacher(name='سعد الغامدي', username='saad_ghamdi', email='saad@test.com')
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        results = Teacher.search_teachers('سعد')
        names = [r.name for r in results]
        assert 'سعد الغامدي' in names

    def test_teacher_fcm_token(self, db_session, app):
        """تحديث ومسح FCM Token للمعلم"""
        from src.models.teacher import Teacher
        t = Teacher(name='FCM T', username='t_fcm', email='tfcm@test.com')
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        t.update_fcm_token('teacher_token_abc')
        db_session.session.refresh(t)
        assert t.fcm_token == 'teacher_token_abc'
        t.clear_fcm_token()
        db_session.session.refresh(t)
        assert t.fcm_token is None

    def test_teacher_to_dict(self, db_session, app):
        """تحويل المعلم لـ dictionary"""
        from src.models.teacher import Teacher
        t = Teacher(name='Dict T', username='t_dict', email='tdict@test.com', school='مدرسة اختبار')
        t.set_password('Pass@123')
        db_session.session.add(t)
        db_session.session.commit()
        db_session.session.refresh(t)
        d = t.to_dict()
        assert d['username'] == 't_dict'
        assert d['school'] == 'مدرسة اختبار'

    def test_teacher_repr(self, app):
        """__repr__ المعلم"""
        from src.models.teacher import Teacher
        with app.app_context():
            t = Teacher(name='R', username='t_repr', email='trepr@test.com')
            assert 't_repr' in repr(t)


class TestCurriculumModels:
    """اختبارات نماذج المنهج"""

    def test_create_course(self, db_session, app):
        """إنشاء منهج جديد"""
        from src.models.curriculum import Course
        c = Course(name='كيمياء أول ثانوي', order_num=1, show_in_bot=True)
        db_session.session.add(c)
        db_session.session.commit()
        found = Course.query.filter_by(name='كيمياء أول ثانوي').first()
        assert found is not None
        assert found.show_in_bot is True

    def test_create_unit_with_course(self, db_session, app):
        """إنشاء وحدة مرتبطة بمنهج"""
        from src.models.curriculum import Course, Unit
        c = Course(name='كيمياء ثاني', order_num=2)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة المواد', course_id=c.id, order_num=1, show_in_bot=True)
        db_session.session.add(u)
        db_session.session.commit()
        found = Unit.query.filter_by(name='وحدة المواد').first()
        assert found is not None
        assert found.course_id == c.id

    def test_create_lesson_with_unit(self, db_session, app):
        """إنشاء درس مرتبط بوحدة"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='كيمياء ثالث', order_num=3)
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة الغازات', course_id=c.id, order_num=1)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس الغازات المثالية', unit_id=u.id, order_num=1, show_in_bot=True)
        db_session.session.add(l)
        db_session.session.commit()
        found = Lesson.query.filter_by(name='درس الغازات المثالية').first()
        assert found is not None
        assert found.unit_id == u.id

    def test_course_show_in_bot_default(self, db_session, app):
        """show_in_bot القيمة الافتراضية"""
        from src.models.curriculum import Course
        c = Course(name='كيمياء افتراضي')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        assert c.show_in_bot is True

    def test_unit_show_in_bot(self, db_session, app):
        """show_in_bot للوحدة"""
        from src.models.curriculum import Course, Unit
        c = Course(name='منهج Unit Test')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة مخفية', course_id=c.id, show_in_bot=False)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        assert u.show_in_bot is False

    def test_lesson_show_in_bot(self, db_session, app):
        """show_in_bot للدرس"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='منهج Lesson Test')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة L', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس مخفي', unit_id=u.id, show_in_bot=False)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        assert l.show_in_bot is False

    def test_course_repr(self, app):
        """__repr__ المنهج"""
        from src.models.curriculum import Course
        with app.app_context():
            c = Course(name='Test Course')
            assert 'Test Course' in repr(c)

    def test_unit_repr(self, app):
        """__repr__ الوحدة"""
        from src.models.curriculum import Unit
        with app.app_context():
            u = Unit(name='Test Unit', course_id=1)
            assert 'Test Unit' in repr(u)

    def test_lesson_repr(self, app):
        """__repr__ الدرس"""
        from src.models.curriculum import Lesson
        with app.app_context():
            l = Lesson(name='Test Lesson', unit_id=1)
            assert 'Test Lesson' in repr(l)

    def test_lesson_has_content_false(self, db_session, app):
        """الدرس بدون محتوى"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='منهج HasContent')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة HC', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس بدون محتوى', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        # الدرس لا يحتوي على summary أو concept_map
        result = l.has_content()
        assert result is False

    def test_lesson_content_completion_zero(self, db_session, app):
        """نسبة الاكتمال صفر بدون محتوى"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='منهج Completion')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة Comp', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس نسبة صفر', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        assert l.content_completion_percentage() == 0

    def test_course_cascade_delete(self, db_session, app):
        """حذف المنهج يحذف الوحدات والدروس معه"""
        from src.models.curriculum import Course, Unit, Lesson
        c = Course(name='منهج للحذف')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        course_id = c.id
        u = Unit(name='وحدة للحذف', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        unit_id = u.id
        l = Lesson(name='درس للحذف', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        lesson_id = l.id
        db_session.session.delete(c)
        db_session.session.commit()
        assert Course.query.get(course_id) is None
        assert Unit.query.get(unit_id) is None
        assert Lesson.query.get(lesson_id) is None


class TestQuestionModel:
    """اختبارات نموذج الأسئلة"""

    def test_create_question(self, db_session, app):
        """إنشاء سؤال مع خيارات"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question, Option
        c = Course(name='منهج أسئلة')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة أسئلة', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس أسئلة', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='ما هو الرقم الذري للكربون؟', lesson_id=l.id, difficulty='easy', bloom_level='remember')
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        assert q.question_id is not None
        assert q.difficulty == 'easy'
        assert q.bloom_level == 'remember'
        assert q.is_blocked is False

    def test_question_with_options(self, db_session, app):
        """سؤال مع خيارات صحيحة وخاطئة"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question, Option
        c = Course(name='منهج خيارات')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة خيارات', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس خيارات', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال اختبار', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        opt1 = Option(option_text='خطأ 1', is_correct=False, question_id=q.question_id)
        opt2 = Option(option_text='صواب', is_correct=True, question_id=q.question_id)
        opt3 = Option(option_text='خطأ 2', is_correct=False, question_id=q.question_id)
        opt4 = Option(option_text='خطأ 3', is_correct=False, question_id=q.question_id)
        db_session.session.add_all([opt1, opt2, opt3, opt4])
        db_session.session.commit()
        db_session.session.refresh(q)
        assert len(q.options) == 4
        correct = [o for o in q.options if o.is_correct]
        assert len(correct) == 1
        assert correct[0].option_text == 'صواب'

    def test_question_repr(self, db_session, app):
        """__repr__ السؤال"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='منهج repr')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة repr', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس repr', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال قصير', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        assert 'Question' in repr(q)

    def test_question_is_blocked_default(self, db_session, app):
        """السؤال غير محجوب افتراضياً"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        c = Course(name='منهج blocked')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة blocked', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس blocked', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال افتراضي', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        assert q.is_blocked is False

    def test_option_repr(self, db_session, app):
        """__repr__ الخيار"""
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question, Option
        c = Course(name='منهج opt repr')
        db_session.session.add(c)
        db_session.session.commit()
        db_session.session.refresh(c)
        u = Unit(name='وحدة opt repr', course_id=c.id)
        db_session.session.add(u)
        db_session.session.commit()
        db_session.session.refresh(u)
        l = Lesson(name='درس opt repr', unit_id=u.id)
        db_session.session.add(l)
        db_session.session.commit()
        db_session.session.refresh(l)
        q = Question(question_text='سؤال', lesson_id=l.id)
        db_session.session.add(q)
        db_session.session.commit()
        db_session.session.refresh(q)
        o = Option(option_text='خيار', is_correct=False, question_id=q.question_id)
        db_session.session.add(o)
        db_session.session.commit()
        db_session.session.refresh(o)
        assert 'Option' in repr(o)
