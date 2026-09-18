# src/routes/survey_routes.py
"""استبيانات عامة يبنيها الأدمن (اختيار متعدد/نص حر/تقييم/نعم-لا) ويرسلها لطالب/معلم/الكل/طلابه"""

from flask import Blueprint, request, jsonify, render_template, send_file
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from io import BytesIO

try:
    from src.extensions import db
    from src.models.survey import Survey, SurveyQuestion, SurveyResponse, SurveyAnswer, QUESTION_TYPES, TARGET_TYPES
    from src.models.student import Student
    from src.models.teacher import Teacher
    from src.models.teacher_student import TeacherStudent
    from src.middleware.auth_middleware import verify_student_token, verify_teacher_token
except ImportError:  # pragma: no cover
    from extensions import db
    from models.survey import Survey, SurveyQuestion, SurveyResponse, SurveyAnswer, QUESTION_TYPES, TARGET_TYPES
    from models.student import Student
    from models.teacher import Teacher
    from models.teacher_student import TeacherStudent
    from middleware.auth_middleware import verify_student_token, verify_teacher_token

survey_bp = Blueprint('survey', __name__, url_prefix='/api/survey')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'يجب تسجيل الدخول'}), 401
        if not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated


# ==================== أدوات مساعدة ====================

def _admin_of_student(student_id):
    """يرجع admin_id المرتبط بهذا الطالب (أو None)"""
    link = TeacherStudent.query.filter_by(student_id=student_id).first()
    return link.admin_id if link else None


def _visible_to_student(survey, student_id, admin_id):
    if survey.target_type == 'all':
        return True
    if survey.target_type == 'student':
        return student_id in (survey.target_ids or [])
    if survey.target_type == 'my_students':
        return admin_id is not None and survey.created_by == admin_id
    return False


def _visible_to_teacher(survey, teacher_id):
    if survey.target_type == 'all':
        return True
    if survey.target_type == 'teacher':
        return teacher_id in (survey.target_ids or [])
    return False


def _answered_survey_ids(respondent_type, respondent_id):
    rows = SurveyResponse.query.filter_by(respondent_type=respondent_type, respondent_id=respondent_id).all()
    return {r.survey_id for r in rows}


def _validate_questions(questions_data):
    """يتحقق من صحة بيانات الأسئلة، يرجع (أسئلة نظيفة, رسالة خطأ أو None)"""
    if not questions_data or not isinstance(questions_data, list):
        return None, 'الاستبيان يحتاج سؤال واحد على الأقل'
    cleaned = []
    for i, q in enumerate(questions_data):
        text = (q.get('text') or '').strip()
        qtype = q.get('type') or 'choice'
        if not text:
            return None, f'السؤال رقم {i + 1} بدون نص'
        if qtype not in QUESTION_TYPES:
            return None, f'نوع السؤال رقم {i + 1} غير صحيح'
        options = None
        if qtype == 'choice':
            options = [o.strip() for o in (q.get('options') or []) if o and o.strip()]
            if len(options) < 2:
                return None, f'السؤال رقم {i + 1} (اختيار متعدد) يحتاج خيارين على الأقل'
        rating_max = None
        rating_min_label = None
        rating_max_label = None
        if qtype == 'rating':
            try:
                rating_max = int(q.get('rating_max') or 5)
            except (TypeError, ValueError):
                rating_max = 5
            rating_max = max(3, min(10, rating_max))
            rating_min_label = (q.get('rating_min_label') or '').strip()[:100] or None
            rating_max_label = (q.get('rating_max_label') or '').strip()[:100] or None
        cleaned.append({
            'text': text, 'type': qtype, 'options': options, 'rating_max': rating_max,
            'rating_min_label': rating_min_label, 'rating_max_label': rating_max_label,
        })
    return cleaned, None


# ==================== لوحة الأدمن (ويب) ====================

@survey_bp.route('/page', methods=['GET'])
@login_required
@admin_required
def admin_page():
    return render_template('survey_admin.html')


@survey_bp.route('/admin/list', methods=['GET'])
@login_required
@admin_required
def admin_list():
    try:
        surveys = Survey.query.filter_by(created_by=current_user.id).order_by(Survey.created_at.desc()).all()
        return jsonify({'success': True, 'surveys': [s.to_dict() for s in surveys]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/admin/create', methods=['POST'])
@login_required
@admin_required
def admin_create():
    try:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'العنوان مطلوب'}), 400

        target_type = data.get('target_type') or 'all'
        if target_type not in TARGET_TYPES:
            return jsonify({'success': False, 'error': 'نوع الاستهداف غير صحيح'}), 400
        target_ids = data.get('target_ids') or []
        if target_type in ('student', 'teacher') and not target_ids:
            return jsonify({'success': False, 'error': 'اختر مستلم واحد على الأقل'}), 400

        questions, err = _validate_questions(data.get('questions'))
        if err:
            return jsonify({'success': False, 'error': err}), 400

        survey = Survey(
            title=title,
            description=(data.get('description') or '').strip(),
            created_by=current_user.id,
            is_anonymous=bool(data.get('is_anonymous')),
            target_type=target_type,
            target_ids=target_ids if target_type in ('student', 'teacher') else None,
            status='active',
        )
        db.session.add(survey)
        db.session.flush()

        for i, q in enumerate(questions):
            db.session.add(SurveyQuestion(
                survey_id=survey.id, order=i, text=q['text'], type=q['type'],
                options=q['options'], rating_max=q['rating_max'],
                rating_min_label=q['rating_min_label'], rating_max_label=q['rating_max_label'],
            ))
        db.session.commit()
        return jsonify({'success': True, 'survey': survey.to_dict(with_questions=True)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_owned_survey(survey_id):
    return Survey.query.filter_by(id=survey_id, created_by=current_user.id).first()


@survey_bp.route('/admin/<int:survey_id>', methods=['GET'])
@login_required
@admin_required
def admin_detail(survey_id):
    survey = _get_owned_survey(survey_id)
    if not survey:
        return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
    return jsonify({'success': True, 'survey': survey.to_dict(with_questions=True)})


@survey_bp.route('/admin/<int:survey_id>/status', methods=['POST'])
@login_required
@admin_required
def admin_set_status(survey_id):
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        status = (request.get_json() or {}).get('status')
        if status not in ('active', 'closed'):
            return jsonify({'success': False, 'error': 'حالة غير صحيحة'}), 400
        survey.status = status
        db.session.commit()
        return jsonify({'success': True, 'survey': survey.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/admin/<int:survey_id>', methods=['DELETE'])
@login_required
@admin_required
def admin_delete(survey_id):
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        db.session.delete(survey)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/admin/candidates', methods=['GET'])
@login_required
@admin_required
def admin_candidates():
    """بحث عن طلاب/معلمين لاختيارهم كمستلمين — ?type=student|teacher&q=نص"""
    try:
        ctype = request.args.get('type')
        q = (request.args.get('q') or '').strip()
        if ctype == 'student':
            query = Student.query.filter_by(is_active=True)
            if q:
                query = query.filter(Student.name.ilike(f'%{q}%'))
            items = query.order_by(Student.name).limit(30).all()
        elif ctype == 'teacher':
            query = Teacher.query.filter_by(is_active=True)
            if q:
                query = query.filter(Teacher.name.ilike(f'%{q}%'))
            items = query.order_by(Teacher.name).limit(30).all()
        else:
            return jsonify({'success': False, 'error': 'type مطلوب'}), 400
        return jsonify({'success': True, 'items': [{'id': it.id, 'name': it.name} for it in items]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _notify_targets(survey, restrict_ids=None):
    """إشعار داخل التطبيق + push لمستلمي استبيان مستهدَف بطالب/معلم/طلابي — يُستدعى من زر 'إرسال إشعار'
    restrict_ids: لو معبّى، يرسل بس لهالمعرّفات (تُستخدم من زر 'إرسال لمن لم يجاوب')"""
    sent = 0
    try:
        if survey.target_type in ('student', 'my_students'):
            try:
                from src.models.notification import Notification, StudentNotification
                from src.services.notification_service import NotificationService
            except ImportError:  # pragma: no cover
                from models.notification import Notification, StudentNotification
                from services.notification_service import NotificationService

            if survey.target_type == 'student':
                student_ids = list(survey.target_ids or [])
            else:
                student_ids = [l.student_id for l in TeacherStudent.query.filter_by(admin_id=survey.created_by).all()]
            if restrict_ids is not None:
                student_ids = [sid for sid in student_ids if sid in restrict_ids]

            title = f'📋 استبيان: {survey.title}'
            message = survey.description or 'وصلك استبيان جديد — عبّئه من التطبيق.'
            for sid in student_ids:
                notification = Notification(
                    student_id=sid, title=title, message=message, body=message,
                    type='survey', notification_type='survey',
                    data={'survey_id': survey.id},
                    is_read=False, status='delivered', sent_at=datetime.utcnow(),
                )
                db.session.add(notification)
                db.session.flush()
                db.session.add(StudentNotification(student_id=sid, notification_id=notification.id, is_read=False))
            db.session.commit()

            students = Student.query.filter(Student.id.in_(student_ids), Student.fcm_token.isnot(None)).all() if student_ids else []
            for st in students:
                try:
                    NotificationService.send_fcm_notification(st.fcm_token, title, message, {'type': 'survey', 'survey_id': survey.id})
                    sent += 1
                except Exception:
                    pass

        elif survey.target_type == 'teacher':
            try:
                from src.models.teacher_notification import TeacherNotification
            except ImportError:  # pragma: no cover
                from models.teacher_notification import TeacherNotification
            title = f'📋 استبيان: {survey.title}'
            message = survey.description or 'وصلك استبيان جديد — عبّئه من التطبيق.'
            teacher_ids = list(survey.target_ids or [])
            if restrict_ids is not None:
                teacher_ids = [tid for tid in teacher_ids if tid in restrict_ids]
            for tid in teacher_ids:
                TeacherNotification.create(teacher_id=tid, title=title, message=message, type='survey')
                sent += 1
    except Exception:
        db.session.rollback()
    return sent


@survey_bp.route('/admin/<int:survey_id>/notify', methods=['POST'])
@login_required
@admin_required
def admin_notify(survey_id):
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        sent = _notify_targets(survey)
        return jsonify({'success': True, 'sent': sent})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/admin/<int:survey_id>/notify-pending', methods=['POST'])
@login_required
@admin_required
def admin_notify_pending(survey_id):
    """يرسل إشعار بس لمن لسه ما جاوب من الجمهور المستهدَف — نفس فكرة 'تذكير لمن لم يكمل' بالاختبار التشخيصي"""
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        if survey.target_type == 'all':
            return jsonify({'success': False, 'error': 'الاستهداف "الكل" ما له قائمة مستلمين محددة نقدر نحسب منها لمن لم يجاوب'}), 400

        _, audience = _survey_audience(survey)
        if not audience:
            return jsonify({'success': True, 'sent': 0})

        answered_ids = {r.respondent_id for r in SurveyResponse.query.filter_by(survey_id=survey.id).all()}
        pending_ids = {aid for aid, _ in audience if aid not in answered_ids}
        if not pending_ids:
            return jsonify({'success': True, 'sent': 0, 'message': 'الكل جاوب بالفعل'})

        sent = _notify_targets(survey, restrict_ids=pending_ids)
        return jsonify({'success': True, 'sent': sent, 'pending_count': len(pending_ids)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _survey_audience(survey):
    """يرجع (نوع المستجيب، قائمة (id, name) للجمهور المستهدَف) — None لو ما نقدر نحسب جمهور محدد (target_type='all')"""
    if survey.target_type == 'teacher':
        ids = survey.target_ids or []
        rows = Teacher.query.filter(Teacher.id.in_(ids)).all() if ids else []
        return 'teacher', [(t.id, t.name) for t in rows]
    if survey.target_type == 'student':
        ids = survey.target_ids or []
        rows = Student.query.filter(Student.id.in_(ids)).all() if ids else []
        return 'student', [(s.id, s.name) for s in rows]
    if survey.target_type == 'my_students':
        links = TeacherStudent.query.join(TeacherStudent.student).filter(
            TeacherStudent.admin_id == survey.created_by
        ).all()
        return 'student', [(l.student_id, l.student.name) for l in links if l.student]
    return None, []


def _results_for_survey(survey):
    responses = SurveyResponse.query.filter_by(survey_id=survey.id).all()
    response_ids = [r.id for r in responses]
    answers = SurveyAnswer.query.filter(SurveyAnswer.response_id.in_(response_ids)).all() if response_ids else []

    respondent_type = 'teacher' if survey.target_type == 'teacher' else 'student'
    respondent_names = {}
    if not survey.is_anonymous:
        Model = Teacher if respondent_type == 'teacher' else Student
        ids = [r.respondent_id for r in responses]
        rows = Model.query.filter(Model.id.in_(ids)).all() if ids else []
        respondent_names = {r.id: r.name for r in rows}

    respondents_out = None
    pending_out = None
    if not survey.is_anonymous:
        respondents_out = sorted([
            {
                'id': r.respondent_id,
                'name': respondent_names.get(r.respondent_id, f'#{r.respondent_id}'),
                'submitted_at': (r.submitted_at.isoformat() + 'Z') if r.submitted_at else None,
            }
            for r in responses
        ], key=lambda x: x['submitted_at'] or '')

    _, audience = _survey_audience(survey)
    if audience:
        answered_ids = {r.respondent_id for r in responses}
        pending_out = [{'id': aid, 'name': aname} for aid, aname in audience if aid not in answered_ids]

    by_response = {}
    for a in answers:
        by_response.setdefault(a.response_id, []).append(a)

    questions_out = []
    for q in survey.questions:
        q_answers = [a for a in answers if a.question_id == q.id]
        entry = {'question': q.to_dict()}
        if q.type == 'choice' or q.type == 'yesno':
            options = q.options if q.type == 'choice' else ['نعم', 'لا']
            counts = {o: 0 for o in options}
            for a in q_answers:
                if a.answer_choice in counts:
                    counts[a.answer_choice] += 1
            entry['counts'] = counts
        elif q.type == 'rating':
            values = [a.answer_rating for a in q_answers if a.answer_rating is not None]
            entry['average'] = round(sum(values) / len(values), 2) if values else 0
            entry['count'] = len(values)
            dist = {}
            for v in values:
                dist[v] = dist.get(v, 0) + 1
            entry['distribution'] = dist
        elif q.type == 'text':
            texts = []
            for a in q_answers:
                resp = next((r for r in responses if r.id == a.response_id), None)
                name = None if survey.is_anonymous else respondent_names.get(resp.respondent_id if resp else None)
                texts.append({'text': a.answer_text or '', 'respondent_name': name})
            entry['texts'] = texts
        questions_out.append(entry)

    return {
        'survey': survey.to_dict(),
        'total_responses': len(responses),
        'questions': questions_out,
        'respondents': respondents_out,  # None لو مجهول
        'audience_size': len(audience) if audience else None,  # None لو target_type='all' (ما نقدر نحسب الجمهور)
        'pending_respondents': pending_out,  # None لو مجهول أو ما نقدر نحسب الجمهور (target_type='all')
    }


@survey_bp.route('/admin/<int:survey_id>/results', methods=['GET'])
@login_required
@admin_required
def admin_results(survey_id):
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        return jsonify({'success': True, 'results': _results_for_survey(survey)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/admin/<int:survey_id>/export-excel', methods=['GET'])
@login_required
@admin_required
def admin_export_excel(survey_id):
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404

        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'نتائج الاستبيان'
        ws.sheet_view.rightToLeft = True

        questions = survey.questions
        headers = (['المستجيب'] if not survey.is_anonymous else []) + [q.text for q in questions]
        thin = Side(style='thin', color='CBD5E1')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_fill = PatternFill('solid', fgColor='6366F1')
        for col, h in enumerate(headers, start=1):
            c = ws.cell(1, col, h)
            c.font = Font(color='FFFFFF', bold=True, size=11)
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True, readingOrder=2)
            c.fill = header_fill
            c.border = border
        ws.row_dimensions[1].height = 30

        responses = SurveyResponse.query.filter_by(survey_id=survey.id).order_by(SurveyResponse.submitted_at).all()
        name_lookup = {}
        if not survey.is_anonymous:
            Model = Teacher if survey.target_type == 'teacher' else Student
            ids = [r.respondent_id for r in responses]
            rows = Model.query.filter(Model.id.in_(ids)).all() if ids else []
            name_lookup = {r.id: r.name for r in rows}

        row = 2
        for resp in responses:
            answers_by_q = {a.question_id: a for a in resp.answers}
            values = []
            if not survey.is_anonymous:
                values.append(name_lookup.get(resp.respondent_id, f'#{resp.respondent_id}'))
            for q in questions:
                a = answers_by_q.get(q.id)
                if not a:
                    values.append('')
                elif q.type == 'text':
                    values.append(a.answer_text or '')
                elif q.type == 'rating':
                    values.append(a.answer_rating if a.answer_rating is not None else '')
                else:
                    values.append(a.answer_choice or '')
            for col, v in enumerate(values, start=1):
                cell = ws.cell(row, col, v)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            row += 1

        for col in range(1, len(headers) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 24

        footer_row = row + 1
        ws.merge_cells(start_row=footer_row, start_column=1, end_row=footer_row, end_column=max(len(headers), 1))
        fc = ws.cell(footer_row, 1)
        fc.value = f'⚗️  تم استخراج هذا التقرير من تطبيق كيم تحصيلي  |  منصة تعليمية للكيمياء  |  جميع الحقوق محفوظة © {datetime.now().year}'
        fc.font = Font(size=9, color='888888', italic=True)
        fc.alignment = Alignment(horizontal='center', vertical='center')
        fc.fill = PatternFill('solid', fgColor='F1F5F9')

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(
            output, as_attachment=True, download_name=f'استبيان_{survey.id}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _survey_dataframe(survey):
    """يبني DataFrame + تسميات المتغيرات/القيم لتصدير SPSS — عمود لكل سؤال (Q1, Q2...)، ترميز رقمي لأسئلة الاختيار/نعم-لا"""
    import pandas as pd

    questions = survey.questions
    responses = SurveyResponse.query.filter_by(survey_id=survey.id).order_by(SurveyResponse.submitted_at).all()

    name_lookup = {}
    if not survey.is_anonymous:
        Model = Teacher if survey.target_type == 'teacher' else Student
        ids = [r.respondent_id for r in responses]
        rows = Model.query.filter(Model.id.in_(ids)).all() if ids else []
        name_lookup = {r.id: r.name for r in rows}

    id_col = 'respondent_name' if not survey.is_anonymous else 'respondent_no'
    rows_data = []
    for idx, resp in enumerate(responses, start=1):
        row = {id_col: (name_lookup.get(resp.respondent_id, f'#{resp.respondent_id}') if not survey.is_anonymous else idx)}
        answers_by_q = {a.question_id: a for a in resp.answers}
        for qi, q in enumerate(questions, start=1):
            varname = f'Q{qi}'
            a = answers_by_q.get(q.id)
            if q.type == 'text':
                row[varname] = (a.answer_text if a else '') or ''
            elif q.type == 'rating':
                row[varname] = a.answer_rating if (a and a.answer_rating is not None) else None
            else:
                options = q.options if q.type == 'choice' else ['نعم', 'لا']
                code = None
                if a and a.answer_choice in (options or []):
                    code = options.index(a.answer_choice) + 1
                row[varname] = code
        rows_data.append(row)

    columns = [id_col] + [f'Q{i}' for i in range(1, len(questions) + 1)]
    df = pd.DataFrame(rows_data, columns=columns)

    variable_labels = {id_col: 'اسم المستجيب' if not survey.is_anonymous else 'رقم الرد'}
    value_labels = {}
    for qi, q in enumerate(questions, start=1):
        varname = f'Q{qi}'
        variable_labels[varname] = q.text[:255]
        if q.type == 'choice':
            value_labels[varname] = {i + 1: opt for i, opt in enumerate(q.options or [])}
        elif q.type == 'yesno':
            value_labels[varname] = {1: 'نعم', 2: 'لا'}

    return df, variable_labels, value_labels


@survey_bp.route('/admin/<int:survey_id>/export-spss', methods=['GET'])
@login_required
@admin_required
def admin_export_spss(survey_id):
    """تصدير ملف .sav متوافق مع SPSS مباشرة — ترميز رقمي + تسميات متغيرات/قيم مضمّنة"""
    try:
        survey = _get_owned_survey(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404

        import os
        import uuid
        import tempfile
        import pyreadstat

        df, variable_labels, value_labels = _survey_dataframe(survey)

        tmp_path = os.path.join(tempfile.gettempdir(), f'survey_spss_{uuid.uuid4().hex}.sav')
        try:
            pyreadstat.write_sav(
                df, tmp_path,
                column_labels=[variable_labels.get(c, c) for c in df.columns],
                variable_value_labels=value_labels,
            )
            with open(tmp_path, 'rb') as f:
                data = f.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        return send_file(
            BytesIO(data), as_attachment=True, download_name=f'استبيان_{survey.id}.sav',
            mimetype='application/octet-stream',
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== الطالب ====================

@survey_bp.route('/student/pending', methods=['GET'])
@verify_student_token
def student_pending():
    try:
        student_id = request.student_id
        admin_id = _admin_of_student(student_id)
        answered = _answered_survey_ids('student', student_id)
        surveys = Survey.query.filter_by(status='active').all()
        pending = [
            s.to_dict() for s in surveys
            if s.id not in answered and _visible_to_student(s, student_id, admin_id)
        ]
        return jsonify({'success': True, 'surveys': pending})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/student/<int:survey_id>', methods=['GET'])
@verify_student_token
def student_detail(survey_id):
    try:
        student_id = request.student_id
        survey = Survey.query.get(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        admin_id = _admin_of_student(student_id)
        if not _visible_to_student(survey, student_id, admin_id):
            return jsonify({'success': False, 'error': 'هذا الاستبيان مو متاح لك'}), 403
        already = SurveyResponse.query.filter_by(
            survey_id=survey.id, respondent_type='student', respondent_id=student_id,
        ).first() is not None
        return jsonify({'success': True, 'survey': survey.to_dict(with_questions=True), 'already_answered': already})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _submit_answers(survey, respondent_type, respondent_id, answers_data):
    if survey.status != 'active':
        return {'success': False, 'error': 'هذا الاستبيان مغلق حالياً'}, 400
    existing = SurveyResponse.query.filter_by(
        survey_id=survey.id, respondent_type=respondent_type, respondent_id=respondent_id,
    ).first()
    if existing:
        return {'success': False, 'error': 'already_answered', 'message': 'جاوبت على هذا الاستبيان من قبل'}, 400

    questions_by_id = {q.id: q for q in survey.questions}
    if len(answers_data or []) < len(questions_by_id):
        return {'success': False, 'error': 'لازم تجاوب على كل الأسئلة'}, 400

    response = SurveyResponse(survey_id=survey.id, respondent_type=respondent_type, respondent_id=respondent_id)
    db.session.add(response)
    db.session.flush()

    for a in answers_data:
        q = questions_by_id.get(a.get('question_id'))
        if not q:
            continue
        answer = SurveyAnswer(response_id=response.id, question_id=q.id)
        if q.type == 'text':
            answer.answer_text = (a.get('answer_text') or '').strip()
        elif q.type == 'rating':
            try:
                answer.answer_rating = int(a.get('answer_rating'))
            except (TypeError, ValueError):
                answer.answer_rating = None
        else:
            answer.answer_choice = a.get('answer_choice')
        db.session.add(answer)

    db.session.commit()
    return {'success': True, 'message': 'تم إرسال إجاباتك، شكراً لك'}, 200


@survey_bp.route('/student/<int:survey_id>/submit', methods=['POST'])
@verify_student_token
def student_submit(survey_id):
    try:
        student_id = request.student_id
        survey = Survey.query.get(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        admin_id = _admin_of_student(student_id)
        if not _visible_to_student(survey, student_id, admin_id):
            return jsonify({'success': False, 'error': 'هذا الاستبيان مو متاح لك'}), 403
        data = request.get_json() or {}
        result, code = _submit_answers(survey, 'student', student_id, data.get('answers'))
        return jsonify(result), code
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== المعلم ====================

@survey_bp.route('/teacher/pending', methods=['GET'])
@verify_teacher_token
def teacher_pending():
    try:
        teacher_id = request.teacher_id
        answered = _answered_survey_ids('teacher', teacher_id)
        surveys = Survey.query.filter_by(status='active').all()
        pending = [
            s.to_dict() for s in surveys
            if s.id not in answered and _visible_to_teacher(s, teacher_id)
        ]
        return jsonify({'success': True, 'surveys': pending})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/teacher/<int:survey_id>', methods=['GET'])
@verify_teacher_token
def teacher_detail(survey_id):
    try:
        teacher_id = request.teacher_id
        survey = Survey.query.get(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        if not _visible_to_teacher(survey, teacher_id):
            return jsonify({'success': False, 'error': 'هذا الاستبيان مو متاح لك'}), 403
        already = SurveyResponse.query.filter_by(
            survey_id=survey.id, respondent_type='teacher', respondent_id=teacher_id,
        ).first() is not None
        return jsonify({'success': True, 'survey': survey.to_dict(with_questions=True), 'already_answered': already})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_bp.route('/teacher/<int:survey_id>/submit', methods=['POST'])
@verify_teacher_token
def teacher_submit(survey_id):
    try:
        teacher_id = request.teacher_id
        survey = Survey.query.get(survey_id)
        if not survey:
            return jsonify({'success': False, 'error': 'الاستبيان غير موجود'}), 404
        if not _visible_to_teacher(survey, teacher_id):
            return jsonify({'success': False, 'error': 'هذا الاستبيان مو متاح لك'}), 403
        data = request.get_json() or {}
        result, code = _submit_answers(survey, 'teacher', teacher_id, data.get('answers'))
        return jsonify(result), code
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
