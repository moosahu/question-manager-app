# src/routes/learning_style_routes.py
"""أنماط التعلم (VARK) — استبيان يحدد نمط تعلم الطالب، ويعرض للمعلم إحصائيات طلابه"""

from flask import Blueprint, request, jsonify
from datetime import datetime

try:
    from src.extensions import db
    from src.models.learning_style import LearningStyleResult
    from src.models.student import Student
    from src.models.teacher_student import TeacherStudent
    from src.middleware.auth_middleware import verify_student_token, verify_teacher_token
except ImportError:  # pragma: no cover
    from extensions import db
    from models.learning_style import LearningStyleResult
    from models.student import Student
    from models.teacher_student import TeacherStudent
    from middleware.auth_middleware import verify_student_token, verify_teacher_token

learning_style_bp = Blueprint('learning_style', __name__, url_prefix='/api/learning-style')

_STYLE_NAMES = {'V': 'بصري', 'A': 'سمعي', 'R': 'قرائي/كتابي', 'K': 'حركي'}

# استبيان أنماط التعلم — كل سؤال له 4 خيارات بنفس الترتيب دايماً: بصري، سمعي، قرائي/كتابي، حركي
_QUESTIONS = [
    {'id': 1, 'text': 'عندما تتعلم موضوعًا جديدًا لأول مرة، فإنك تفضل أن:', 'options': [
        {'key': 'V', 'text': 'تشاهد فيديو أو صورًا توضيحية عنه.'},
        {'key': 'A', 'text': 'تستمع لشخص يشرحه لك.'},
        {'key': 'R', 'text': 'تقرأ عنه من كتاب أو مقال.'},
        {'key': 'K', 'text': 'تجربه بنفسك مباشرة.'},
    ]},
    {'id': 2, 'text': 'عندما تحاول تتذكر معلومة مهمة، فإنك تتذكرها أفضل إذا:', 'options': [
        {'key': 'V', 'text': 'تخيّلتها في صورة أو شكل.'},
        {'key': 'A', 'text': 'سمعتها أو ناقشتها مع أحد.'},
        {'key': 'R', 'text': 'كتبتها بنفسك.'},
        {'key': 'K', 'text': 'مارستها أو طبّقتها عمليًا.'},
    ]},
    {'id': 3, 'text': 'عندما يشرح معلم المادة درسًا جديدًا، فإنك تفضل أن:', 'options': [
        {'key': 'V', 'text': 'تشاهد المخططات والصور والرسوم التوضيحية.'},
        {'key': 'A', 'text': 'تستمع إلى شرحه بصوته أو مناقشته مع الطلاب.'},
        {'key': 'R', 'text': 'تقرأ الشرح من الكتاب أو من الملاحظات المكتوبة.'},
        {'key': 'K', 'text': 'تطبق الدرس من خلال تجربة أو نشاط عملي.'},
    ]},
    {'id': 4, 'text': 'إذا استخدم المعلم عرضًا مرئيًا (شرائح / فيديو)، فإن أكثر ما يفيدك هو:', 'options': [
        {'key': 'V', 'text': 'الصور والمخططات الملونة.'},
        {'key': 'A', 'text': 'شرح المعلم الصوتي لما يظهر.'},
        {'key': 'R', 'text': 'النصوص المكتوبة على الشاشة.'},
        {'key': 'K', 'text': 'مشاهدة التجربة أو النشاط العملي في العرض.'},
    ]},
    {'id': 5, 'text': 'عندما يُطلب منك تلخيص درس، فإنك:', 'options': [
        {'key': 'V', 'text': 'تلخصه برسوم بيانية أو مخطط.'},
        {'key': 'A', 'text': 'تشرحه بصوتك أو تناقشه مع الآخرين.'},
        {'key': 'R', 'text': 'تكتبه في شكل نقاط أو فقرات.'},
        {'key': 'K', 'text': 'تربطه بتجربة أو نشاط عملي قمت به.'},
    ]},
    {'id': 6, 'text': 'إذا أردت حفظ معلومة جديدة (تعريف / قاعدة)، فإنك تفضل أن:', 'options': [
        {'key': 'V', 'text': 'تتخيلها في صورة أو رسم.'},
        {'key': 'A', 'text': 'تكررها بصوت مسموع.'},
        {'key': 'R', 'text': 'تكتبها عدة مرات حتى تحفظها.'},
        {'key': 'K', 'text': 'تربطها بمثال عملي أو حركة.'},
    ]},
    {'id': 7, 'text': 'إذا طلب منك المعلم إعداد واجب كتابي، فإنك تفضل أن:', 'options': [
        {'key': 'V', 'text': 'يحتوي على صور ورسوم توضيحية.'},
        {'key': 'A', 'text': 'تشرحه بصوتك أو تعرضه شفويًا.'},
        {'key': 'R', 'text': 'تكتبه بالتفصيل مع شرح كتابي.'},
        {'key': 'K', 'text': 'تجعله في صورة تجربة أو نشاط عملي.'},
    ]},
    {'id': 8, 'text': 'عند تنفيذ مشروع مدرسي، فإنك تفضل أن:', 'options': [
        {'key': 'V', 'text': 'تستخدم مخططات ورسومات توضيحية.'},
        {'key': 'A', 'text': 'تعرضه شفويًا وتشرحه للآخرين.'},
        {'key': 'R', 'text': 'تكتب تقريرًا منظمًا عنه.'},
        {'key': 'K', 'text': 'تبني نموذجًا عمليًا أو تنفذ تجربة.'},
    ]},
    {'id': 9, 'text': 'عند مراجعة الدروس قبل الاختبار، فإنك تفضل أن:', 'options': [
        {'key': 'V', 'text': 'تستخدم الخرائط الذهنية والرسومات.'},
        {'key': 'A', 'text': 'تستمع لتسجيلات صوتية أو تناقشها مع الآخرين.'},
        {'key': 'R', 'text': 'تقرأ الملخصات والكتب.'},
        {'key': 'K', 'text': 'تحل تدريبات عملية وأسئلة تطبيقية.'},
    ]},
    {'id': 10, 'text': 'بعد انتهاء الاختبار، عندما تفكر في إجاباتك، فإنك عادةً:', 'options': [
        {'key': 'V', 'text': 'تتذكر مكان المعلومة في الكتاب أو الشكل.'},
        {'key': 'A', 'text': 'تتذكر صوت المعلم أو النقاش.'},
        {'key': 'R', 'text': 'تتذكر الجملة كما كتبتها.'},
        {'key': 'K', 'text': 'تتذكر التجربة أو النشاط العملي المرتبط بها.'},
    ]},
]

_STYLE_TIPS = {
    'بصري': 'تتعلم أفضل بالصور والمخططات والألوان — استخدم الخرائط الذهنية والرسوم التوضيحية بمذاكرتك.',
    'سمعي': 'تتعلم أفضل بالاستماع والنقاش — سجّل الشروحات واستمع لها، وناقش زملاءك بصوت عالٍ.',
    'قرائي/كتابي': 'تتعلم أفضل بالقراءة والكتابة — لخّص دروسك بنقاط مكتوبة وأعد كتابتها.',
    'حركي': 'تتعلم أفضل بالتجربة والتطبيق العملي — حل تمارين وتدريبات عملية بدل القراءة النظرية فقط.',
}


@learning_style_bp.route('/questions', methods=['GET'])
def get_questions():
    """أسئلة الاستبيان — بدون كشف أي خيار يقابل أي نمط بالاستجابة (فقط النص)"""
    questions = [{
        'id': q['id'], 'text': q['text'],
        'options': [{'key': o['key'], 'text': o['text']} for o in q['options']],
    } for q in _QUESTIONS]
    return jsonify({'success': True, 'questions': questions})


def _compute_result(answers):
    scores = {'V': 0, 'A': 0, 'R': 0, 'K': 0}
    for a in (answers or []):
        key = (a.get('option') or '').upper()
        if key in scores:
            scores[key] += 1
    max_score = max(scores.values()) if any(scores.values()) else 0
    dominant_keys = [k for k, v in scores.items() if v == max_score and max_score > 0]
    dominant_style = '/'.join(_STYLE_NAMES[k] for k in dominant_keys)
    return scores, dominant_style


@learning_style_bp.route('/submit', methods=['POST'])
@verify_student_token
def submit_result():
    """الطالب يرسل إجاباته — يُحسب النمط ويُحفظ (يستبدل أي نتيجة سابقة لو أعاد الاستبيان)"""
    try:
        student_id = request.student_id
        data = request.get_json() or {}
        answers = data.get('answers') or []
        if not answers:
            return jsonify({'success': False, 'error': 'answers مطلوبة'}), 400

        # ✅ الاستبيان يُؤخذ مرة واحدة بس — إلا لو المعلم/الأدمن أعاد الفرصة (يمسح نتيجته القديمة)
        result = LearningStyleResult.query.filter_by(student_id=student_id).first()
        if result:
            return jsonify({
                'success': False, 'error': 'already_taken',
                'message': 'أخذت الاستبيان من قبل — اطلب من معلمك يعيد لك الفرصة عشان تقدر تعيده',
            }), 400

        scores, dominant_style = _compute_result(answers)
        result = LearningStyleResult(student_id=student_id)
        db.session.add(result)

        result.visual_score = scores['V']
        result.auditory_score = scores['A']
        result.reading_score = scores['R']
        result.kinesthetic_score = scores['K']
        result.dominant_style = dominant_style
        result.answers = answers
        db.session.commit()

        result_dict = result.to_dict()
        result_dict['tips'] = [_STYLE_TIPS[s] for s in dominant_style.split('/') if s in _STYLE_TIPS]
        return jsonify({'success': True, 'message': 'تم حفظ النتيجة', 'result': result_dict})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_style_bp.route('/my-result', methods=['GET'])
@verify_student_token
def my_result():
    """نتيجة الطالب الحالي (لو أخذ الاستبيان من قبل)"""
    try:
        student_id = request.student_id
        result = LearningStyleResult.query.filter_by(student_id=student_id).first()
        if not result:
            return jsonify({'success': True, 'result': None})
        result_dict = result.to_dict()
        result_dict['tips'] = [_STYLE_TIPS[s] for s in result.dominant_style.split('/') if s in _STYLE_TIPS]
        return jsonify({'success': True, 'result': result_dict})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_style_bp.route('/teacher/students', methods=['GET'])
@verify_teacher_token
def teacher_students_styles():
    """قائمة طلاب المعلم مع أنماط تعلمهم + إحصائية جماعية"""
    try:
        teacher_id = request.teacher_id
        links = TeacherStudent.query.join(TeacherStudent.student).filter(
            TeacherStudent.teacher_id == teacher_id
        ).order_by(Student.name).all()

        student_ids = [l.student_id for l in links]
        results = LearningStyleResult.query.filter(LearningStyleResult.student_id.in_(student_ids)).all() if student_ids else []
        by_student = {r.student_id: r for r in results}

        counts = {'بصري': 0, 'سمعي': 0, 'قرائي/كتابي': 0, 'حركي': 0}
        students_data = []
        for l in links:
            st = l.student
            r = by_student.get(l.student_id)
            entry = {
                'student_id': l.student_id,
                'student_name': st.name if st else None,
                'taken': r is not None,
                'result': r.to_dict() if r else None,
            }
            students_data.append(entry)
            if r and r.dominant_style:
                for style in r.dominant_style.split('/'):
                    if style in counts:
                        counts[style] += 1

        return jsonify({
            'success': True,
            'students': students_data,
            'counts': counts,
            'total_students': len(links),
            'taken_count': len(results),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_style_bp.route('/teacher/reopen/<int:student_id>', methods=['POST'])
@verify_teacher_token
def reopen_for_student(student_id):
    """يعيد الفرصة لطالب من طلاب المعلم يعيد الاستبيان (يمسح نتيجته الحالية)"""
    try:
        teacher_id = request.teacher_id
        link = TeacherStudent.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
        if not link:
            return jsonify({'success': False, 'error': 'هذا الطالب مو من ضمن طلابك'}), 403

        result = LearningStyleResult.query.filter_by(student_id=student_id).first()
        if not result:
            return jsonify({'success': False, 'error': 'هذا الطالب ما أخذ الاستبيان أصلاً'}), 400

        db.session.delete(result)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم إعادة الفرصة للطالب'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_style_bp.route('/teacher/notify', methods=['POST'])
@verify_teacher_token
def notify_students():
    """يرسل تذكير (إشعار داخل التطبيق + push لو متاح) لطلاب محددين أو كل طلابي بتعبئة الاستبيان"""
    try:
        teacher_id = request.teacher_id
        data = request.get_json() or {}
        requested_ids = data.get('student_ids')  # None/[] = كل طلاب المعلم

        links = TeacherStudent.query.filter_by(teacher_id=teacher_id).all()
        my_student_ids = {l.student_id for l in links}
        targets = [sid for sid in requested_ids if sid in my_student_ids] if requested_ids else list(my_student_ids)

        if not targets:
            return jsonify({'success': False, 'error': 'ما فيه طلاب لإرسال الاستبيان لهم'}), 400

        try:
            from src.models.notification import Notification, StudentNotification
        except ImportError:  # pragma: no cover
            from models.notification import Notification, StudentNotification

        title = '📋 استبيان أنماط التعلم'
        message = 'معلمك يطلب منك تعبئة استبيان أنماط التعلم من التطبيق — يساعده يفهم طريقة تعلّمك الأفضل.'

        for sid in targets:
            notification = Notification(
                student_id=sid, title=title, message=message, body=message,
                type='learning_style', notification_type='learning_style',
                is_read=False, status='delivered', sent_at=datetime.utcnow(),
            )
            db.session.add(notification)
            db.session.flush()
            db.session.add(StudentNotification(student_id=sid, notification_id=notification.id, is_read=False))
        db.session.commit()

        # إرسال push notification لو عند الطالب FCM token (بدون ما يفشل الطلب لو ما توفر)
        sent_push = 0
        try:
            from src.services.notification_service import NotificationService
            students = Student.query.filter(Student.id.in_(targets), Student.fcm_token.isnot(None)).all()
            for st in students:
                try:
                    NotificationService.send_fcm_notification(
                        st.fcm_token, title, message, {'type': 'learning_style'},
                    )
                    sent_push += 1
                except Exception:
                    pass
        except Exception:
            pass

        return jsonify({'success': True, 'sent_count': len(targets), 'push_sent': sent_push})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
