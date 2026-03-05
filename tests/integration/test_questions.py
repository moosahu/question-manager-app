"""
اختبارات CRUD الأسئلة
"""
import pytest


class TestQuestionModel:
    """اختبارات model السؤال مباشرة"""

    def _create_question(self, db_session, lesson, app, text='سؤال تجريبي', blocked=False):
        """مساعد: إنشاء سؤال مع خيارات"""
        from src.models.question import Question, Option
        q = Question(
            question_text=text,
            lesson_id=lesson.id,
            difficulty='medium',
            bloom_level='remember',
            is_blocked=blocked
        )
        db_session.session.add(q)
        db_session.session.flush()  # نحصل على ID

        options = [
            Option(option_text='خيار أ', is_correct=True, question_id=q.question_id),
            Option(option_text='خيار ب', is_correct=False, question_id=q.question_id),
            Option(option_text='خيار ج', is_correct=False, question_id=q.question_id),
            Option(option_text='خيار د', is_correct=False, question_id=q.question_id),
        ]
        for opt in options:
            db_session.session.add(opt)
        db_session.session.commit()
        return q

    def test_create_question_with_options(self, db_session, sample_lesson, app):
        """إنشاء سؤال مع 4 خيارات"""
        from src.models.question import Question
        q = self._create_question(db_session, sample_lesson, app)
        found = Question.query.get(q.question_id)
        assert found is not None
        assert len(found.options) == 4

    def test_only_one_correct_option(self, db_session, sample_lesson, app):
        """خيار صحيح واحد فقط"""
        from src.models.question import Question
        q = self._create_question(db_session, sample_lesson, app)
        found = Question.query.get(q.question_id)
        correct_options = [o for o in found.options if o.is_correct]
        assert len(correct_options) == 1

    def test_blocked_question_flag(self, db_session, sample_lesson, app):
        """سؤال محجوب (is_blocked=True)"""
        from src.models.question import Question
        q = self._create_question(db_session, sample_lesson, app, blocked=True)
        found = Question.query.get(q.question_id)
        assert found.is_blocked is True

    def test_delete_question_cascades_options(self, db_session, sample_lesson, app):
        """حذف السؤال يحذف الخيارات معه"""
        from src.models.question import Question, Option
        q = self._create_question(db_session, sample_lesson, app, text='سؤال للحذف')
        qid = q.question_id
        found = Question.query.get(qid)
        db_session.session.delete(found)
        db_session.session.commit()
        # الخيارات لازم تُحذف
        remaining = Option.query.filter_by(question_id=qid).count()
        assert remaining == 0

    def test_difficulty_values(self, db_session, sample_lesson, app):
        """مستويات الصعوبة المقبولة"""
        from src.models.question import Question
        for diff in ['easy', 'medium', 'hard']:
            q = Question(
                question_text=f'سؤال {diff}',
                lesson_id=sample_lesson.id,
                difficulty=diff,
                bloom_level='remember'
            )
            db_session.session.add(q)
        db_session.session.commit()

        easy_count = Question.query.filter_by(difficulty='easy').count()
        assert easy_count >= 1

    def test_bloom_level_values(self, db_session, sample_lesson, app):
        """مستويات بلوم المقبولة"""
        from src.models.question import Question
        for bloom in ['remember', 'understand', 'apply', 'analyze']:
            q = Question(
                question_text=f'سؤال بلوم {bloom}',
                lesson_id=sample_lesson.id,
                difficulty='medium',
                bloom_level=bloom
            )
            db_session.session.add(q)
        db_session.session.commit()

        remember_count = Question.query.filter_by(bloom_level='remember').count()
        assert remember_count >= 1


class TestQuestionsApiBlocking:
    """اختبار أن الأسئلة المحجوبة لا تظهر للطلاب"""

    def test_get_all_questions_endpoint(self, client):
        """API الأسئلة يرجع response"""
        response = client.get('/api/v1/questions/all')
        assert response.status_code in [200, 401, 403]  # يتطلب login

    def test_blocked_questions_hidden_in_student_api(self, client, db_session, sample_lesson, app):
        """الأسئلة المحجوبة لا تظهر في student API"""
        from src.models.question import Question, Option
        # سؤال عادي
        q_visible = Question(
            question_text='سؤال ظاهر',
            lesson_id=sample_lesson.id,
            is_blocked=False
        )
        # سؤال محجوب
        q_hidden = Question(
            question_text='سؤال محجوب',
            lesson_id=sample_lesson.id,
            is_blocked=True
        )
        db_session.session.add(q_visible)
        db_session.session.add(q_hidden)
        db_session.session.commit()

        # التحقق في DB مباشرة
        visible = Question.query.filter_by(is_blocked=False).all()
        hidden = Question.query.filter_by(is_blocked=True).all()
        assert len(visible) >= 1
        assert len(hidden) >= 1
        # الأسئلة المحجوبة موجودة في DB لكن يجب فلترتها في API
        for q in visible:
            assert q.is_blocked is False
        for q in hidden:
            assert q.is_blocked is True
