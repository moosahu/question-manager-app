# src/routes/video_views_routes.py
# routes لتتبع مشاهدات فيديو الشرح + إحصائيات الأدمن والمعلم

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func

try:
    from src.extensions import db
    from src.models.question_video_view import QuestionVideoView
    from src.models.student import Student
    from src.models.student_result import StudentResult
    from src.models.question import Question
    from src.models.curriculum import Lesson
    from src.models.teacher_student import TeacherStudent
except ImportError:
    from extensions import db
    from models.question_video_view import QuestionVideoView
    from models.student import Student
    from models.student_result import StudentResult
    from models.question import Question
    from models.curriculum import Lesson
    from models.teacher_student import TeacherStudent

video_views_bp = Blueprint('video_views', __name__)


# ─────────────────────────────────────────────────────────────
# POST /api/questions/<id>/video-view
# يُستدعى من Flutter عند إغلاق مشغّل الفيديو
# ─────────────────────────────────────────────────────────────
@video_views_bp.route('/api/questions/<int:question_id>/video-view', methods=['POST'])
def record_video_view(question_id):
    """تسجيل مشاهدة الطالب لفيديو شرح سؤال"""
    try:
        data = request.get_json() or {}

        student_id     = data.get('student_id')
        watch_duration = int(data.get('watch_duration', 0))
        video_duration = int(data.get('video_duration', 0))

        if not student_id:
            return jsonify({'success': False, 'error': 'student_id مطلوب'}), 400

        # التحقق من وجود الطالب والسؤال
        student  = Student.query.get(student_id)
        question = Question.query.get(question_id)
        if not student:
            return jsonify({'success': False, 'error': 'الطالب غير موجود'}), 404
        if not question:
            return jsonify({'success': False, 'error': 'السؤال غير موجود'}), 404

        # هل شاهد 80%+ ؟
        completed = (video_duration > 0) and (watch_duration >= video_duration * 0.8)

        # إذا سجّل سابقاً: حدّث + زِد view_count
        existing = QuestionVideoView.query.filter_by(
            student_id=student_id,
            question_id=question_id
        ).first()

        if existing:
            existing.watch_duration = max(existing.watch_duration, watch_duration)
            existing.video_duration = video_duration if video_duration > 0 else existing.video_duration
            existing.completed      = existing.completed or completed
            existing.view_count     += 1
            existing.watched_at     = datetime.utcnow()
        else:
            view = QuestionVideoView(
                student_id=student_id,
                question_id=question_id,
                watch_duration=watch_duration,
                video_duration=video_duration,
                completed=completed,
                view_count=1,
            )
            db.session.add(view)

        db.session.commit()
        return jsonify({'success': True, 'completed': completed})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# GET /api/admin/video-views/stats
# إحصائيات كاملة للأدمن
# ─────────────────────────────────────────────────────────────
@video_views_bp.route('/api/admin/video-views/stats', methods=['GET'])
def admin_video_stats():
    """إحصائيات مشاهدات الفيديو للأدمن"""
    try:
        # ── إجماليات ──────────────────────────────────────────
        total_views     = QuestionVideoView.query.count()
        total_completed = QuestionVideoView.query.filter_by(completed=True).count()
        total_students  = db.session.query(
            func.count(func.distinct(QuestionVideoView.student_id))
        ).scalar()

        completion_rate = round(total_completed / total_views * 100, 1) if total_views else 0

        # ── نسبة التحسّن ───────────────────────────────────────
        # تعريف: أخطأ في سؤال → شاهد فيديوه → أجاب صح في اختبار لاحق
        # نقارن آخر نتيجة قبل المشاهدة مع أول نتيجة بعدها
        # (تقريب: من لديهم مشاهدات نقارن نسبة نجاحهم العامة)
        improved_count = 0
        watched_students = db.session.query(
            QuestionVideoView.student_id,
            func.min(QuestionVideoView.watched_at).label('first_watch')
        ).group_by(QuestionVideoView.student_id).all()

        for row in watched_students:
            sid, first_watch = row.student_id, row.first_watch
            # نتيجة قبل المشاهدة
            before = StudentResult.query.filter(
                StudentResult.student_id == sid,
                StudentResult.created_at < first_watch
            ).order_by(StudentResult.created_at.desc()).first()
            # نتيجة بعد المشاهدة
            after = StudentResult.query.filter(
                StudentResult.student_id == sid,
                StudentResult.created_at > first_watch
            ).order_by(StudentResult.created_at.asc()).first()

            if before and after and after.score_percentage > before.score_percentage:
                improved_count += 1

        improvement_rate = round(improved_count / len(watched_students) * 100, 1) if watched_students else 0

        # ── أكثر 10 أسئلة مشاهدةً ────────────────────────────
        top_questions_q = db.session.query(
            QuestionVideoView.question_id,
            func.count(QuestionVideoView.student_id).label('viewers'),
            func.sum(func.cast(QuestionVideoView.completed, db.Integer)).label('completions'),
            func.avg(QuestionVideoView.view_count).label('avg_views')
        ).group_by(QuestionVideoView.question_id)\
         .order_by(func.count(QuestionVideoView.student_id).desc())\
         .limit(10).all()

        top_questions = []
        for row in top_questions_q:
            q = Question.query.get(row.question_id)
            if not q:
                continue
            viewers    = row.viewers or 0
            completions = int(row.completions or 0)
            top_questions.append({
                'question_id':   row.question_id,
                'question_text': (q.question_text or '')[:80],
                'viewers':       viewers,
                'completion_rate': round(completions / viewers * 100, 1) if viewers else 0,
                'avg_view_count': round(float(row.avg_views or 1), 1),
            })

        # ── أسئلة عندها فيديو لكن مشاهدات = 0 ───────────────
        viewed_ids = db.session.query(
            func.distinct(QuestionVideoView.question_id)
        ).subquery()

        no_views_questions = Question.query.filter(
            (Question.video_url.isnot(None)) | (Question.r2_video_url.isnot(None)),
            Question.question_id.notin_(viewed_ids)
        ).limit(20).all()

        no_views_list = [{
            'question_id':   q.question_id,
            'question_text': (q.question_text or '')[:80],
        } for q in no_views_questions]

        return jsonify({
            'success': True,
            'stats': {
                'total_views':       total_views,
                'total_students':    total_students,
                'completion_rate':   completion_rate,
                'improvement_rate':  improvement_rate,
                'improved_count':    improved_count,
            },
            'top_questions':    top_questions,
            'no_views_count':   len(no_views_list),
            'no_views_sample':  no_views_list[:5],
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# GET /api/teacher/video-views/my-students
# إحصائيات طلاب المعلم
# ─────────────────────────────────────────────────────────────
@video_views_bp.route('/api/teacher/video-views/my-students', methods=['GET'])
def teacher_video_stats():
    """إحصائيات مشاهدات فيديو طلاب المعلم"""
    try:
        teacher_id = request.args.get('teacher_id', type=int)
        if not teacher_id:
            return jsonify({'success': False, 'error': 'teacher_id مطلوب'}), 400

        # جلب معرّفات طلاب المعلم
        links = TeacherStudent.query.filter_by(teacher_id=teacher_id).all()
        student_ids = [l.student_id for l in links]

        if not student_ids:
            return jsonify({'success': True, 'students': [], 'at_risk': []})

        one_week_ago = datetime.utcnow() - timedelta(days=7)

        # لكل طالب: عدد الفيديوهات هذا الأسبوع
        weekly_views = db.session.query(
            QuestionVideoView.student_id,
            func.count(QuestionVideoView.id).label('views_this_week')
        ).filter(
            QuestionVideoView.student_id.in_(student_ids),
            QuestionVideoView.watched_at >= one_week_ago
        ).group_by(QuestionVideoView.student_id).all()

        views_map = {row.student_id: row.views_this_week for row in weekly_views}

        students_data = []
        for sid in student_ids:
            student = Student.query.get(sid)
            if not student:
                continue
            total_views_student = QuestionVideoView.query.filter_by(student_id=sid).count()
            completed_student   = QuestionVideoView.query.filter_by(student_id=sid, completed=True).count()
            students_data.append({
                'student_id':       sid,
                'student_name':     student.name,
                'views_this_week':  views_map.get(sid, 0),
                'total_views':      total_views_student,
                'completed_videos': completed_student,
            })

        # طلاب في خطر: أخطأوا في سؤال عنده فيديو ولم يشاهدوه
        at_risk = []
        for sid in student_ids:
            # آخر 10 نتائج سيئة (أقل من 60%)
            bad_results = StudentResult.query.filter(
                StudentResult.student_id == sid,
                StudentResult.score_percentage < 60
            ).order_by(StudentResult.created_at.desc()).limit(5).all()

            if bad_results:
                watched_q_ids = {
                    v.question_id for v in
                    QuestionVideoView.query.filter_by(student_id=sid).all()
                }
                # أسئلة عندها فيديو ولم يشاهدها
                unwatched = Question.query.filter(
                    (Question.video_url.isnot(None)) | (Question.r2_video_url.isnot(None)),
                    Question.question_id.notin_(watched_q_ids)
                ).count()

                if unwatched > 0:
                    student = Student.query.get(sid)
                    at_risk.append({
                        'student_id':   sid,
                        'student_name': student.name if student else '—',
                        'unwatched_with_video': unwatched,
                    })

        return jsonify({
            'success':  True,
            'students': students_data,
            'at_risk':  at_risk,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
