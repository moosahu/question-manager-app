"""
كيم ريسبونس — نظام الإجابة بالبطاقات (مشابه لـ Plickers)
المعلم أو الأدمن ينشئ جلسة، يطبع بطاقات الطلاب،
ويمسح إجاباتهم بالكاميرا مباشرة في الفصل.
"""

import io
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required, current_user
from src.extensions import db
from src.models.kim_response import KimResponseSession, KimResponseAnswer
from src.models.question import Question, Option
from src.models.student import Student
from src.models.student_result import StudentResult
from src.models.teacher_student import TeacherStudent

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

kim_response_bp = Blueprint('kim_response', __name__)


# ── مساعدات ───────────────────────────────────────────────────────────────────

def _get_caller_ids():
    """يرجع (teacher_id, admin_id) حسب نوع المستخدم الحالي"""
    if hasattr(current_user, 'is_admin') and current_user.is_admin:
        return None, current_user.id
    # المعلم — نجيب teacher_id من الـ prefs
    from src.models.teacher import Teacher
    teacher = Teacher.query.filter_by(username=current_user.username).first()
    return (teacher.id if teacher else None), None


def _get_session_or_404(session_id):
    """يرجع الجلسة إذا كانت تابعة للمستخدم الحالي"""
    teacher_id, admin_id = _get_caller_ids()
    session = KimResponseSession.query.get_or_404(session_id)
    if admin_id and session.admin_id != admin_id:
        return None
    if teacher_id and session.teacher_id != teacher_id:
        return None
    return session


def _get_correct_option_letter(question):
    """يرجع حرف الإجابة الصحيحة A/B/C/D"""
    for i, opt in enumerate(question.options):
        if opt.is_correct:
            letters = ['A', 'B', 'C', 'D']
            return letters[i] if i < 4 else 'A'
    return 'A'



# ── 1. إنشاء جلسة ─────────────────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session', methods=['POST'])
@login_required
def create_session():
    """
    إنشاء جلسة كيم ريسبونس جديدة.
    Body: { "title": str, "question_ids": [int, ...] }
    """
    data = request.get_json() or {}
    question_ids = data.get('question_ids', [])
    title        = data.get('title', 'جلسة كيم ريسبونس')

    if not question_ids:
        return jsonify({'success': False, 'error': 'يجب اختيار سؤال واحد على الأقل'}), 400

    # تحقق من وجود الأسئلة
    questions = Question.query.filter(Question.question_id.in_(question_ids)).all()
    if len(questions) != len(question_ids):
        return jsonify({'success': False, 'error': 'بعض الأسئلة غير موجودة'}), 400

    teacher_id, admin_id = _get_caller_ids()

    session = KimResponseSession(
        teacher_id   = teacher_id,
        admin_id     = admin_id,
        title        = title,
        status       = 'waiting',
    )
    session.question_ids = question_ids
    db.session.add(session)
    db.session.commit()

    return jsonify({'success': True, 'session': session.to_dict()}), 201


# ── 2. توليد PDF بطاقات ArUco ─────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/cards', methods=['GET'])
@login_required
def generate_cards(session_id):
    """
    يولّد PDF فيه بطاقة ArUco لكل طالب (نمط Plickers).
    كل بطاقة تحمل marker فريد — الإجابة تُحدَّد بالاتجاه (A=أعلى، B=يمين، C=أسفل، D=يسار).
    """
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    teacher_id, admin_id = _get_caller_ids()

    links = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).all()

    if not links:
        return jsonify({'success': False, 'error': 'لا يوجد طلاب مرتبطون'}), 400

    students = [Student.query.get(l.student_id) for l in links]
    students = [s for s in students if s and s.is_active]
    students.sort(key=lambda s: s.name)

    if len(students) > 250:
        return jsonify({'success': False, 'error': 'الحد الأقصى 250 طالباً لبطاقات ArUco'}), 400

    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        return jsonify({'success': False, 'error': f'مكتبات مفقودة: {e}'}), 500

    font_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts', 'Cairo-Regular.ttf')
    font_path = os.path.normpath(font_path)

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

    from bidi.algorithm import get_display
    import arabic_reshaper

    def ar(text):
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text

    def make_card_image(student, aruco_id):
        """توليد صورة PIL للبطاقة — CARD×(CARD+STRIP) بكسل."""
        CARD   = 600   # منطقة الـ marker (مربعة)
        MARKER = 400   # حجم الـ ArUco marker (أصغر من الكارت ليترك هامش للحروف)
        STRIP  = 90    # شريط اسم الطالب
        TOTAL  = CARD + STRIP

        # ── توليد marker ──────────────────────────────────────
        marker_np = np.zeros((MARKER, MARKER), dtype=np.uint8)
        cv2.aruco.generateImageMarker(aruco_dict, int(aruco_id), MARKER, marker_np, 1)
        marker_pil = Image.fromarray(marker_np).convert('RGB')

        # ── كانفاس أبيض ───────────────────────────────────────
        card = Image.new('RGB', (CARD, TOTAL), 'white')
        draw = ImageDraw.Draw(card)

        # لصق الـ marker في مركز منطقة CARD
        offset = (CARD - MARKER) // 2   # = 100 بكسل على كل جانب
        card.paste(marker_pil, (offset, offset))

        # إطار خارجي
        draw.rectangle([0, 0, CARD - 1, CARD - 1], outline='black', width=4)

        # حروف الإجابة داخل هامش الـ 100 بكسل (خارج الـ marker)
        LBL = 60
        try:
            font_lbl = ImageFont.truetype(font_path, LBL) if os.path.exists(font_path) else ImageFont.load_default()
        except Exception:
            font_lbl = ImageFont.load_default()

        mid  = CARD // 2
        edge = 12

        draw.text((mid, edge),         'A', fill='black', font=font_lbl, anchor='mt')
        draw.text((CARD - edge, mid),  'B', fill='black', font=font_lbl, anchor='rm')
        draw.text((mid, CARD - edge),  'C', fill='black', font=font_lbl, anchor='mb')
        draw.text((edge, mid),         'D', fill='black', font=font_lbl, anchor='lm')

        # رقم البطاقة في الأركان (صغير)
        try:
            font_num = ImageFont.truetype(font_path, 18) if os.path.exists(font_path) else ImageFont.load_default()
        except Exception:
            font_num = ImageFont.load_default()

        num = str(aruco_id)
        draw.text((6, 6),                fill='#9ca3af', text=num, font=font_num, anchor='lt')
        draw.text((CARD - 6, 6),         fill='#9ca3af', text=num, font=font_num, anchor='rt')
        draw.text((6, CARD - 6),         fill='#9ca3af', text=num, font=font_num, anchor='lb')
        draw.text((CARD - 6, CARD - 6),  fill='#9ca3af', text=num, font=font_num, anchor='rb')

        # ── شريط الاسم ─────────────────────────────────────────
        draw.rectangle([0, CARD, CARD, TOTAL], fill='#1e3a8a')

        try:
            font_name = ImageFont.truetype(font_path, 30) if os.path.exists(font_path) else ImageFont.load_default()
        except Exception:
            font_name = ImageFont.load_default()

        name_display = ar(student.name)
        draw.text((CARD // 2, CARD + 14), name_display,       fill='white',   font=font_name, anchor='mt')
        draw.text((CARD // 2, CARD + 54), f'#{aruco_id}',     fill='#93c5fd', font=font_name, anchor='mt')

        return card

    # ── تجميع PDF — بطاقتان لكل صفحة ─────────────────────────────────────────
    PAGE_W, PAGE_H = A4
    MARGIN   = 20   # pts
    CARD_AREA_H = (PAGE_H - 3 * MARGIN) / 2

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    for idx, student in enumerate(students):
        if idx > 0 and idx % 2 == 0:
            c.showPage()

        pos     = idx % 2                          # 0=أعلى، 1=أسفل
        card_x  = MARGIN
        card_y  = PAGE_H - MARGIN - (pos + 1) * CARD_AREA_H - pos * MARGIN

        card_img = make_card_image(student, idx)

        cbuf = io.BytesIO()
        card_img.save(cbuf, format='PNG')
        cbuf.seek(0)

        draw_w = PAGE_W - 2 * MARGIN
        c.drawImage(ImageReader(cbuf), card_x, card_y,
                    width=draw_w, height=CARD_AREA_H,
                    preserveAspectRatio=True, anchor='c')

    c.save()
    buf.seek(0)

    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'kim_aruco_cards_{session_id}.pdf')


# ── 2b. خريطة ArUco → Student ─────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/aruco-map', methods=['GET'])
@login_required
def get_aruco_map(session_id):
    """
    يرجع الخريطة aruco_id → student_id مرتّبة أبجدياً.
    تُستخدَم في شاشة المسح لمعرفة الطالب بعد اكتشاف الـ marker.
    """
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    teacher_id, admin_id = _get_caller_ids()

    links = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).all()

    students = [Student.query.get(l.student_id) for l in links]
    students = [s for s in students if s and s.is_active]
    students.sort(key=lambda s: s.name)

    aruco_map   = {str(i): s.id   for i, s in enumerate(students)}
    students_info = [
        {'aruco_id': i, 'student_id': s.id, 'student_name': s.name}
        for i, s in enumerate(students)
    ]

    return jsonify({
        'success':  True,
        'aruco_map': aruco_map,
        'students': students_info,
        'total':    len(students),
    })


# ── 3. تسجيل إجابة ممسوحة ─────────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/scan', methods=['POST'])
@login_required
def record_scan(session_id):
    """
    يسجّل إجابة طالب بعد مسح QR.
    Body: { "qr_data": '{"s":123,"a":"A"}' }
    أو:   { "student_id": 123, "answer": "A" }
    """
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    if session.status == 'finished':
        return jsonify({'success': False, 'error': 'الجلسة منتهية'}), 400

    data = request.get_json() or {}

    # قراءة البيانات من QR أو مباشرة
    if 'qr_data' in data:
        try:
            qr = json.loads(data['qr_data'])
            student_id = int(qr['s'])
            answer     = str(qr['a']).upper()
        except Exception:
            return jsonify({'success': False, 'error': 'QR غير صالح'}), 400
    else:
        student_id = data.get('student_id')
        answer     = str(data.get('answer', '')).upper()

    if not student_id or answer not in ['A', 'B', 'C', 'D']:
        return jsonify({'success': False, 'error': 'بيانات غير صالحة'}), 400

    question_id = session.current_question_id
    if not question_id:
        return jsonify({'success': False, 'error': 'لا يوجد سؤال نشط'}), 400

    # تحقق من الإجابة الصحيحة
    question = Question.query.get(question_id)
    correct_letter = _get_correct_option_letter(question) if question else 'A'
    is_correct = (answer == correct_letter)

    # احفظ أو حدّث الإجابة
    existing = KimResponseAnswer.query.filter_by(
        session_id=session_id, student_id=student_id, question_id=question_id
    ).first()

    if existing:
        existing.answer     = answer
        existing.is_correct = is_correct
        existing.scanned_at = datetime.utcnow()
    else:
        ans = KimResponseAnswer(
            session_id  = session_id,
            student_id  = student_id,
            question_id = question_id,
            answer      = answer,
            is_correct  = is_correct,
        )
        db.session.add(ans)

    if session.status == 'waiting':
        session.status = 'active'

    db.session.commit()

    student = Student.query.get(student_id)
    return jsonify({
        'success':      True,
        'student_name': student.name if student else '',
        'answer':       answer,
        'is_correct':   is_correct,
        'correct':      correct_letter,
    })


# ── 4. نتائج السؤال الحالي ────────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/results', methods=['GET'])
@login_required
def get_results(session_id):
    """نتائج السؤال الحالي + ملخص الجلسة"""
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    question_id = session.current_question_id
    answers = KimResponseAnswer.query.filter_by(
        session_id=session_id, question_id=question_id
    ).all() if question_id else []

    total     = len(answers)
    correct   = sum(1 for a in answers if a.is_correct)
    breakdown = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    for a in answers:
        breakdown[a.answer] = breakdown.get(a.answer, 0) + 1

    # إجمالي الطلاب
    teacher_id, admin_id = _get_caller_ids()
    total_students = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).count()

    return jsonify({
        'success':           True,
        'session':           session.to_dict(),
        'current_question':  _question_to_dict(question_id),
        'total_answers':     total,
        'total_students':    total_students,
        'correct_count':     correct,
        'wrong_count':       total - correct,
        'not_answered':      total_students - total,
        'breakdown':         breakdown,
        'answers':           [a.to_dict() for a in answers],
    })


# ── 5. السؤال التالي ──────────────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/next', methods=['POST'])
@login_required
def next_question(session_id):
    """ينتقل للسؤال التالي أو ينهي الجلسة"""
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    next_idx = session.current_question_idx + 1
    if next_idx >= session.total_questions:
        session.status      = 'finished'
        session.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'finished': True, 'session': session.to_dict()})

    session.current_question_idx = next_idx
    db.session.commit()
    return jsonify({'success': True, 'finished': False, 'session': session.to_dict()})


# ── 6. حفظ النتائج في StudentResult ──────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/save', methods=['POST'])
@login_required
def save_results(session_id):
    """
    يحفظ نتائج كل طالب في StudentResult بعد انتهاء الجلسة.
    يمكن استدعاؤه أكثر من مرة (يتجنب التكرار).
    """
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    if session.status != 'finished':
        return jsonify({'success': False, 'error': 'الجلسة لم تنته بعد'}), 400

    # جمع إجابات كل طالب
    all_answers = KimResponseAnswer.query.filter_by(session_id=session_id).all()
    from itertools import groupby
    from operator import attrgetter

    sorted_answers = sorted(all_answers, key=attrgetter('student_id'))
    saved_count = 0

    for student_id, student_answers in groupby(sorted_answers, key=attrgetter('student_id')):
        answers_list = list(student_answers)
        total_q      = session.total_questions
        correct_q    = sum(1 for a in answers_list if a.is_correct)
        wrong_q      = len(answers_list) - correct_q
        score_pct    = round((correct_q / total_q) * 100, 1) if total_q > 0 else 0

        # تجنب التكرار
        existing = StudentResult.query.filter_by(
            student_id  = student_id,
            quiz_type   = 'kim_response',
            quiz_id     = session_id,
        ).first()
        if existing:
            continue

        result = StudentResult(
            student_id       = student_id,
            quiz_type        = 'kim_response',
            quiz_name        = session.title,
            quiz_id          = session_id,
            total_questions  = total_q,
            correct_answers  = correct_q,
            wrong_answers    = wrong_q,
            score_percentage = score_pct,
            time_spent       = 0,
        )
        db.session.add(result)
        saved_count += 1

    db.session.commit()
    return jsonify({'success': True, 'saved_count': saved_count})


# ── 7. قائمة الجلسات السابقة ──────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/sessions', methods=['GET'])
@login_required
def list_sessions():
    """قائمة جلسات المعلم/الأدمن"""
    teacher_id, admin_id = _get_caller_ids()
    sessions = KimResponseSession.query.filter(
        (KimResponseSession.teacher_id == teacher_id) if teacher_id
        else (KimResponseSession.admin_id == admin_id)
    ).order_by(KimResponseSession.created_at.desc()).limit(20).all()

    return jsonify({'success': True, 'sessions': [s.to_dict() for s in sessions]})


# ── مساعد: بيانات السؤال ─────────────────────────────────────────────────────

def _question_to_dict(question_id):
    if not question_id:
        return None
    q = Question.query.get(question_id)
    if not q:
        return None
    return {
        'id':          q.question_id,
        'text':        q.question_text or '',
        'image_url':   q.image_url or '',
        'options': [
            {
                'letter':     chr(65 + i),
                'text':       opt.option_text or '',
                'image_url':  opt.image_url or '',
                'is_correct': opt.is_correct,
            }
            for i, opt in enumerate(q.options[:4])
        ],
    }
