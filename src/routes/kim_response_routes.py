"""
كيم ريسبونس — نظام الإجابة بالبطاقات (مشابه لـ Plickers)
المعلم أو الأدمن ينشئ جلسة، يطبع بطاقات الطلاب،
ويمسح إجاباتهم بالكاميرا مباشرة في الفصل.
"""

import json
import qrcode
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

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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


def _generate_qr_image(data: str, size: int = 120):
    """يولّد صورة QR ويرجعها كـ BytesIO"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


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


# ── 2. توليد PDF البطاقات ──────────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/cards', methods=['GET'])
@login_required
def generate_cards(session_id):
    """
    يولّد PDF فيه بطاقة لكل طالب تابع للمعلم/الأدمن.
    كل بطاقة تحتوي 4 QR codes (A, B, C, D).
    """
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    teacher_id, admin_id = _get_caller_ids()

    # جلب الطلاب
    links = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).all()

    if not links:
        return jsonify({'success': False, 'error': 'لا يوجد طلاب مرتبطون'}), 400

    students = [Student.query.get(l.student_id) for l in links]
    students = [s for s in students if s and s.is_active]
    students.sort(key=lambda s: s.name)

    # تسجيل خط عربي
    font_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts', 'Cairo-Regular.ttf')
    font_path = os.path.normpath(font_path)
    arabic_font = 'Helvetica'
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('Cairo', font_path))
            arabic_font = 'Cairo'
        except Exception:
            pass

    ANSWERS     = ['A', 'B', 'C', 'D']
    BG_COLORS   = [
        colors.HexColor('#dcfce7'),  # A — أخضر فاتح
        colors.HexColor('#dbeafe'),  # B — أزرق فاتح
        colors.HexColor('#fee2e2'),  # C — أحمر فاتح
        colors.HexColor('#fef9c3'),  # D — أصفر فاتح
    ]
    FG_COLORS   = [
        colors.HexColor('#16a34a'),  # A
        colors.HexColor('#2563eb'),  # B
        colors.HexColor('#dc2626'),  # C
        colors.HexColor('#d97706'),  # D
    ]
    PAGE_W, PAGE_H = A4  # 595 × 842 pts

    buf = io.BytesIO()

    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader

    c = rl_canvas.Canvas(buf, pagesize=A4)

    MARGIN     = 0.8 * cm
    CARD_W     = (PAGE_W - 2 * MARGIN) / 2      # بطاقتان في كل صف
    CARD_H     = (PAGE_H - 2 * MARGIN) / 2      # صفّان في كل صفحة
    QR_SIZE    = 3.2 * cm

    def draw_card(cx, cy, student_obj):
        """يرسم بطاقة كاملة — cx,cy هو الركن السفلي الأيسر"""
        # إطار البطاقة
        c.setStrokeColor(colors.HexColor('#1e3a8a'))
        c.setLineWidth(1.5)
        c.rect(cx, cy, CARD_W, CARD_H)

        # شريط الاسم
        name_h = 1.1 * cm
        c.setFillColor(colors.HexColor('#1e3a8a'))
        c.rect(cx, cy + CARD_H - name_h, CARD_W, name_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(arabic_font, 11)
        # عكس النص للعربي
        from bidi.algorithm import get_display
        import arabic_reshaper
        def ar(text):
            try:
                return get_display(arabic_reshaper.reshape(text))
            except Exception:
                return text

        c.drawCentredString(cx + CARD_W / 2, cy + CARD_H - name_h + 0.3 * cm, ar(student_obj.name))

        # تعليمات
        instr_h = 0.7 * cm
        c.setFillColor(colors.HexColor('#f1f5f9'))
        c.rect(cx, cy + CARD_H - name_h - instr_h, CARD_W, instr_h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor('#475569'))
        c.setFont(arabic_font, 7.5)
        c.drawCentredString(cx + CARD_W / 2, cy + CARD_H - name_h - instr_h + 0.15 * cm,
                            ar('أظهر رمز إجابتك للمعلم واحجب الباقي'))

        # منطقة الـ QR — 4 أرباع
        content_y      = cy
        content_h      = CARD_H - name_h - instr_h
        half_w         = CARD_W / 2
        half_h         = content_h / 2

        positions = [
            (cx,          cy + half_h, 0),   # A — أعلى يسار
            (cx + half_w, cy + half_h, 1),   # B — أعلى يمين
            (cx,          cy,          2),   # C — أسفل يسار
            (cx + half_w, cy,          3),   # D — أسفل يمين
        ]

        for qx, qy, j in positions:
            answer = ANSWERS[j]
            # خلفية ملوّنة
            c.setFillColor(BG_COLORS[j])
            c.rect(qx, qy, half_w, half_h, fill=1, stroke=0)
            # خط فاصل داخلي
            c.setStrokeColor(colors.HexColor('#cbd5e1'))
            c.setLineWidth(0.5)
            c.rect(qx, qy, half_w, half_h, fill=0, stroke=1)

            # حرف الإجابة (كبير - في الزاوية)
            c.setFont('Helvetica-Bold', 20)
            c.setFillColor(FG_COLORS[j])
            c.drawCentredString(qx + half_w / 2, qy + half_h - 0.75 * cm, answer)

            # QR code
            qr_data = json.dumps({'s': student_obj.id, 'a': answer}, separators=(',', ':'))
            qr_buf  = _generate_qr_image(qr_data)
            qr_buf.seek(0)
            qr_reader = ImageReader(qr_buf)
            qr_x = qx + (half_w - QR_SIZE) / 2
            qr_y = qy + (half_h - QR_SIZE) / 2 - 0.2 * cm
            c.drawImage(qr_reader, qr_x, qr_y, width=QR_SIZE, height=QR_SIZE)

    # رسم البطاقات — 4 في كل صفحة
    cards_per_page = 4
    for i, student in enumerate(students):
        if i > 0 and i % cards_per_page == 0:
            c.showPage()

        pos_in_page = i % cards_per_page
        col = pos_in_page % 2          # 0=يسار، 1=يمين
        row = 1 - (pos_in_page // 2)   # 0=أسفل، 1=أعلى

        card_x = MARGIN + col * CARD_W
        card_y = MARGIN + row * CARD_H
        draw_card(card_x, card_y, student)

    c.save()
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'kim_response_cards_{session_id}.pdf'
    )


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
