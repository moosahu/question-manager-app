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
    from src.models.teacher import Teacher
    teacher = Teacher.query.filter_by(username=current_user.username).first()
    return (teacher.id if teacher else None), None


def _ensure_aruco_ids(links):
    """يعيّن aruco_id لأي سجل فيه NULL — يحفظ في DB."""
    null_links = [l for l in links if l.aruco_id is None]
    if not null_links:
        return
    used = {l.aruco_id for l in links if l.aruco_id is not None}
    # ترتيب أبجدي للتوافق مع الكروت المطبوعة قبل التحديث
    null_links.sort(key=lambda l: (
        Student.query.get(l.student_id).name
        if Student.query.get(l.student_id) else ''))
    for lnk in null_links:
        for i in range(250):
            if i not in used:
                lnk.aruco_id = i
                used.add(i)
                break
    db.session.commit()


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
    import random
    shuffled = list(question_ids)
    random.shuffle(shuffled)
    session.question_ids = shuffled
    db.session.add(session)
    db.session.commit()

    return jsonify({'success': True, 'session': session.to_dict()}), 201


# ── 1b. جلب الأسئلة لكيم ريسبونس (بدون تصفية is_bank) ────────────────────────

@kim_response_bp.route('/api/kim-response/questions', methods=['GET'])
@login_required
def get_kim_questions():
    """
    جلب الأسئلة لشاشة إعداد كيم ريسبونس.
    يرجع كل الأسئلة بغض النظر عن is_bank.
    """
    from src.models.curriculum import Lesson, Unit

    course_id = request.args.get('course_id', type=int)
    unit_id   = request.args.get('unit_id',   type=int)
    lesson_id = request.args.get('lesson_id', type=int)
    per_page  = request.args.get('per_page',  50, type=int)
    source    = request.args.get('source', 'both')  # regular | bank | both

    from sqlalchemy.orm import joinedload
    query = Question.query.options(joinedload(Question.options))

    # فلتر مصدر الأسئلة
    if source == 'bank':
        query = query.filter(Question.is_bank == True)
    elif source == 'regular':
        query = query.filter(Question.is_bank == False)
    # both = بدون فلتر

    if lesson_id:
        query = query.filter(Question.lesson_id == lesson_id)
    elif unit_id:
        query = query.filter(Question.lesson.has(Lesson.unit_id == unit_id))
    elif course_id:
        query = query.filter(Question.lesson.has(Lesson.unit.has(Unit.course_id == course_id)))

    total     = query.count()
    questions = query.order_by(Question.question_id.desc()).limit(per_page).all()

    return jsonify({
        'success':    True,
        'questions':  [_question_to_dict(q.question_id) for q in questions],
        'total':      total,
    })


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

    grade             = request.args.get('grade')        # فلتر المرحلة (Student.grade)
    section           = request.args.get('section')      # فلتر الشعبة (TeacherStudent.section)
    student_ids_param = request.args.get('student_ids')  # "1,2,3"
    teacher_id, admin_id = _get_caller_ids()

    # جلب كل الطلاب أولاً لضمان تعيين aruco_id للجميع
    all_links = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).all()

    if not all_links:
        return jsonify({'success': False, 'error': 'لا يوجد طلاب مرتبطون'}), 400

    _ensure_aruco_ids(all_links)   # يعيّن aruco_id للجميع قبل الفلتر

    # الآن نطبّق فلتر الشعبة إن وُجد
    if section:
        links = [l for l in all_links if l.section == section]
    else:
        links = all_links

    # بناء قائمة (student, aruco_id)
    pairs = []
    for l in links:
        s = Student.query.get(l.student_id)
        if s and s.is_active and l.aruco_id is not None:
            pairs.append((s, l.aruco_id))

    if grade:
        pairs = [(s, a) for s, a in pairs if s.grade == grade]
    if student_ids_param:
        ids = {int(x) for x in student_ids_param.split(',') if x.strip().isdigit()}
        pairs = [(s, a) for s, a in pairs if s.id in ids]
    if not pairs:
        return jsonify({'success': False, 'error': 'لا يوجد طلاب في هذا الاختيار'}), 400
    pairs.sort(key=lambda p: p[0].name)

    if len(pairs) > 250:
        return jsonify({'success': False, 'error': 'الحد الأقصى 250 طالباً لبطاقات ArUco'}), 400

    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        return jsonify({'success': False, 'error': f'مكتبات مفقودة: {e}'}), 500

    # جرّب الخطوط بالترتيب — Tajawal أولاً ثم Cairo كـ fallback
    _fonts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts'))
    font_path = os.path.join(_fonts_dir, 'Tajawal-Regular.ttf')
    if not os.path.exists(font_path):
        font_path = os.path.join(_fonts_dir, 'Cairo-Regular.ttf')

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

    from bidi.algorithm import get_display
    import arabic_reshaper

    # إيقاف الـ ligatures — يمنع استخدام Unicode range FB50-FDFF التي بعض الخطوط ما تدعمها
    _reshaper = arabic_reshaper.ArabicReshaper(configuration={
        'support_ligatures': False,
        'delete_tatweel':    False,
    })

    def ar(text):
        try:
            reshaped = _reshaper.reshape(text)
            reshaped = reshaped.replace('\u200c', '').replace('\u200d', '')
            return get_display(reshaped)
        except Exception:
            return text

    # تسجيل خط عربي في ReportLab
    arabic_font = 'Helvetica'
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('Cairo', font_path))
            arabic_font = 'Cairo'
        except Exception:
            pass

    import random

    def _card_positions(aruco_id):
        """ترتيب حروف A/B/C/D لكل بطاقة بشكل عشوائي ثابت حسب aruco_id."""
        rng = random.Random(aruco_id * 1337)
        positions = ['A', 'B', 'C', 'D']
        rng.shuffle(positions)
        return positions  # [top, right, bottom, left]

    def make_marker_image(aruco_id):
        """توليد صورة PIL للـ marker فقط (بدون اسم) — مربع CARD×CARD.
        ترتيب الحروف عشوائي ثابت لكل بطاقة لمنع الغش."""
        CARD   = 350
        MARKER = 240

        marker_np = np.zeros((MARKER, MARKER), dtype=np.uint8)
        cv2.aruco.generateImageMarker(aruco_dict, int(aruco_id), MARKER, marker_np, 1)
        marker_pil = Image.fromarray(marker_np).convert('RGB')

        card = Image.new('RGB', (CARD, CARD), 'white')
        draw = ImageDraw.Draw(card)

        # لصق الـ marker في المنتصف
        offset = (CARD - MARKER) // 2
        card.paste(marker_pil, (offset, offset))

        # إطار خارجي
        draw.rectangle([0, 0, CARD - 1, CARD - 1], outline='black', width=4)

        # حروف الإجابة — عشوائية لكل بطاقة
        LBL = 36
        try:
            font_lbl = ImageFont.truetype(font_path, LBL) if os.path.exists(font_path) else ImageFont.load_default()
        except Exception:
            font_lbl = ImageFont.load_default()

        positions = _card_positions(aruco_id)  # [top, right, bottom, left]
        mid  = CARD // 2
        edge = 12
        draw.text((mid, edge),        positions[0], fill='black', font=font_lbl, anchor='mt')
        draw.text((CARD - edge, mid), positions[1], fill='black', font=font_lbl, anchor='rm')
        draw.text((mid, CARD - edge), positions[2], fill='black', font=font_lbl, anchor='mb')
        draw.text((edge, mid),        positions[3], fill='black', font=font_lbl, anchor='lm')

        # رقم البطاقة في الأركان
        try:
            font_num = ImageFont.truetype(font_path, 13) if os.path.exists(font_path) else ImageFont.load_default()
        except Exception:
            font_num = ImageFont.load_default()

        num = str(aruco_id)
        draw.text((6, 6),               fill='#9ca3af', text=num, font=font_num, anchor='lt')
        draw.text((CARD - 6, 6),        fill='#9ca3af', text=num, font=font_num, anchor='rt')
        draw.text((6, CARD - 6),        fill='#9ca3af', text=num, font=font_num, anchor='lb')
        draw.text((CARD - 6, CARD - 6), fill='#9ca3af', text=num, font=font_num, anchor='rb')

        return card

    # ── دالة مساعدة: شريط الاسم كصورة PIL ────────────────────────────────────
    # المنهج الصحيح: PIL + libraqm (layout_engine=1) + نص عربي خام
    # libraqm يتولى التشكيل والـ bidi — لا نستخدم arabic_reshaper هنا
    # النسبة تطابق CARD_W/NAME_H في الـ PDF (343/48 ≈ 7.14) → لوجو مربع بدون تشويه
    NAME_PX_H = 72
    NAME_PX_W = int(NAME_PX_H * 343 / 48)  # = 514

    def _draw_arabic(draw_obj, xy, text, fill, font):
        """يرسم نص عربي باستخدام libraqm إذا متاح، وإلا arabic_reshaper."""
        try:
            draw_obj.text(xy, text, fill=fill, font=font,
                          anchor='mm', direction='rtl', language='ar')
        except Exception:
            # fallback: arabic_reshaper + bidi + basic layout
            draw_obj.text(xy, ar(text), fill=fill, font=font, anchor='mm')

    _logo_app_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), '..', 'static', 'images', 'app_logo.png'))

    def make_name_image(name, aruco_id):
        img    = Image.new('RGB', (NAME_PX_W, NAME_PX_H), '#F3F4F6')
        draw_n = ImageDraw.Draw(img)
        # إطار خفيف حول الشريط
        draw_n.rectangle([0, 0, NAME_PX_W-1, NAME_PX_H-1], outline='#D1D5DB', width=2)

        LOGO_SIZE = 56
        LOGO_PAD  = 8

        # لوجو كيم تحصيلي — يمين (مربع بزوايا دائرية)
        if os.path.exists(_logo_app_path):
            try:
                logo_app = Image.open(_logo_app_path).convert('RGBA')
                logo_app = logo_app.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
                r = int(LOGO_SIZE * 0.22)
                S = LOGO_SIZE
                m = Image.new('L', (S, S), 0)
                d = ImageDraw.Draw(m)
                d.rectangle([r, 0, S-r, S], fill=255)
                d.rectangle([0, r, S, S-r], fill=255)
                d.ellipse([0, 0, r*2, r*2], fill=255)
                d.ellipse([S-r*2, 0, S, r*2], fill=255)
                d.ellipse([0, S-r*2, r*2, S], fill=255)
                d.ellipse([S-r*2, S-r*2, S, S], fill=255)
                logo_app.putalpha(m)
                ly = (NAME_PX_H - LOGO_SIZE) // 2
                lx = NAME_PX_W - LOGO_SIZE - LOGO_PAD
                img.paste(logo_app, (lx, ly), logo_app)
            except Exception:
                pass

        # layout_engine=1 → libraqm
        try:
            fn_big   = ImageFont.truetype(font_path, 26, layout_engine=1)
            fn_small = ImageFont.truetype(font_path, 13, layout_engine=1)
        except Exception:
            fn_big   = ImageFont.load_default()
            fn_small = ImageFont.load_default()

        # نص في المنتصف (مع مراعاة مساحة اللوجو)
        cx = (NAME_PX_W - LOGO_SIZE - LOGO_PAD) // 2
        _draw_arabic(draw_n, (cx, 26), name,                        'black',   fn_big)
        _draw_arabic(draw_n, (cx, 56), f'تطبيق كيم تحصيلي  |  #{aruco_id}',
                                                                     '#374151', fn_small)
        return img

    # ── تجميع PDF — بطاقتان لكل صفحة ────────────────────────────────────────
    PAGE_W, PAGE_H = A4
    MARGIN = 20
    NAME_H = 48
    SLOT_H = (PAGE_H - 3 * MARGIN) / 2
    IMG_H  = SLOT_H - NAME_H
    CARD_W = min(PAGE_W - 2 * MARGIN, IMG_H)
    CARD_X = (PAGE_W - CARD_W) / 2

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    for page_idx, (student, aruco_id) in enumerate(pairs):
        if page_idx > 0 and page_idx % 2 == 0:
            c.showPage()

        pos    = page_idx % 2
        slot_y = PAGE_H - MARGIN - (pos + 1) * SLOT_H - pos * MARGIN
        img_y  = slot_y + NAME_H

        # ArUco
        marker_img = make_marker_image(aruco_id)
        cbuf = io.BytesIO()
        marker_img.save(cbuf, format='PNG')
        cbuf.seek(0)
        c.drawImage(ImageReader(cbuf), CARD_X, img_y,
                    width=CARD_W, height=IMG_H,
                    preserveAspectRatio=True, anchor='c')

        # شريط الاسم — تحت الكرت
        name_img = make_name_image(student.name, aruco_id)
        nbuf = io.BytesIO()
        name_img.save(nbuf, format='PNG')
        nbuf.seek(0)
        c.drawImage(ImageReader(nbuf), CARD_X, slot_y,
                    width=CARD_W, height=NAME_H,
                    preserveAspectRatio=False)

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

    _ensure_aruco_ids(links)   # يعيّن تلقائياً للسجلات القديمة

    students_map = {}   # aruco_id → (student, link)
    for l in links:
        s = Student.query.get(l.student_id)
        if s and s.is_active and l.aruco_id is not None:
            students_map[l.aruco_id] = (s, l)

    # المراحل من Student.grade + الشعب من TeacherStudent.section
    grades   = sorted({s.grade   for s, _ in students_map.values() if s.grade})
    sections = sorted({l.section for _, l in students_map.values() if l.section})

    import random

    def _card_positions_map(aruco_id):
        rng = random.Random(aruco_id * 1337)
        positions = ['A', 'B', 'C', 'D']
        rng.shuffle(positions)
        return positions

    aruco_map     = {str(aid): s.id for aid, (s, _) in students_map.items()}
    students_info = [
        {
            'aruco_id':    aid,
            'student_id':  s.id,
            'student_name': s.name,
            'positions':   _card_positions_map(aid),
            'grade':       s.grade or '',
            'section':     l.section or '',
        }
        for aid, (s, l) in sorted(students_map.items())
    ]

    return jsonify({
        'success':   True,
        'aruco_map': aruco_map,
        'students':  students_info,
        'total':     len(students_info),
        'grades':    grades,
        'sections':  sections,
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

    # دعم إعادة المحاولة: إذا أُرسل question_id صراحةً، استخدمه
    question_id = data.get('question_id') or session.current_question_id
    if not question_id:
        return jsonify({'success': False, 'error': 'لا يوجد سؤال نشط'}), 400

    # تحقق من الإجابة الصحيحة (مع مراعاة خلط الخيارات)
    question = Question.query.get(question_id)
    correct_letter = _correct_letter_after_shuffle(question, session_id) if question else 'A'
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
        'current_question':  _question_to_dict(question_id, session_id=session_id),
        'total_answers':     total,
        'total_students':    total_students,
        'correct_count':     correct,
        'wrong_count':       total - correct,
        'not_answered':      total_students - total,
        'breakdown':         breakdown,
        'answers':           [a.to_dict() for a in answers],
    })


# ── 4b. النتائج النهائية للجلسة كاملة ───────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>/final-results', methods=['GET'])
@login_required
def get_final_results(session_id):
    """
    ملخص نهائي لكل الجلسة (تُستخدم في شاشة النتائج النهائية).
    يجمع إجابات كل الأسئلة — لكل طالب: كم أجاب صح وكم أخطأ.
    """
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    teacher_id, admin_id = _get_caller_ids()

    # كل الطلاب المرتبطين
    links = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).all()
    total_students = len(links)
    student_ids    = {l.student_id for l in links}

    # كل الإجابات في هذه الجلسة
    all_answers = KimResponseAnswer.query.filter_by(session_id=session_id).all()

    # تجميع per-student
    from collections import defaultdict
    per_student = defaultdict(lambda: {'correct': 0, 'wrong': 0, 'answers': []})

    # نحمّل الأسئلة مرة واحدة لتجنب N+1 queries
    q_cache = {}
    for a in all_answers:
        if a.question_id not in q_cache:
            q = Question.query.get(a.question_id)
            correct_ltr = _correct_letter_after_shuffle(q, session_id) if q else '?'
            q_cache[a.question_id] = {
                'text':    (q.question_text or '')[:80] if q else '',
                'image':   q.image_url or '' if q else '',
                'correct': correct_ltr,
                'idx':     session.question_ids.index(a.question_id) + 1
                           if a.question_id in session.question_ids else 0,
            }
        qinfo = q_cache[a.question_id]
        if a.is_correct:
            per_student[a.student_id]['correct'] += 1
        else:
            per_student[a.student_id]['wrong'] += 1
        per_student[a.student_id]['answers'].append({
            **a.to_dict(),
            'question_text':  qinfo['text'],
            'question_image': qinfo['image'],
            'correct_answer': qinfo['correct'],
            'question_num':   qinfo['idx'],
        })

    answered_ids   = set(per_student.keys())
    total_answered = len(answered_ids)
    total_correct  = sum(v['correct'] for v in per_student.values())
    total_wrong    = sum(v['wrong']   for v in per_student.values())
    not_answered   = total_students - total_answered

    # قائمة مفصّلة لكل طالب
    student_rows = []
    for sid in answered_ids:
        s = Student.query.get(sid)
        v = per_student[sid]
        student_rows.append({
            'student_id':   sid,
            'student_name': s.name if s else '',
            'correct':      v['correct'],
            'wrong':        v['wrong'],
            'total':        v['correct'] + v['wrong'],
            'answers':      v['answers'],
        })
    student_rows.sort(key=lambda r: r['student_name'])

    pct = round(total_correct / (total_answered * session.total_questions) * 100, 1) \
          if total_answered > 0 and session.total_questions > 0 else 0.0

    return jsonify({
        'success':        True,
        'session':        session.to_dict(),
        'total_students': total_students,
        'total_answered': total_answered,
        'total_correct':  total_correct,
        'total_wrong':    total_wrong,
        'not_answered':   not_answered,
        'score_pct':      pct,
        'students':       student_rows,
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
            quiz_id          = None,
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


# ── 9. تحليل إحصائي شامل ──────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/analytics', methods=['GET'])
@login_required
def get_analytics():
    """
    تحليل شامل لكل جلسات المعلم/الأدمن:
    - أصعب الأسئلة (نسبة الخطأ + توزيع الإجابات الخاطئة)
    - أداء الطلاب عبر الجلسات (trend)
    - ملخص الجلسات
    """
    teacher_id, admin_id = _get_caller_ids()

    # جلب كل الجلسات المنتهية
    sessions = KimResponseSession.query.filter(
        ((KimResponseSession.teacher_id == teacher_id) if teacher_id
         else (KimResponseSession.admin_id == admin_id)),
        KimResponseSession.status == 'finished'
    ).order_by(KimResponseSession.created_at.asc()).all()

    if not sessions:
        return jsonify({'success': True, 'question_stats': [],
                        'student_trends': [], 'session_overview': []})

    session_ids = [s.id for s in sessions]

    # كل الإجابات
    all_answers = KimResponseAnswer.query.filter(
        KimResponseAnswer.session_id.in_(session_ids)
    ).all()

    # ── إحصاء الأسئلة ────────────────────────────────────────────────────────
    from collections import defaultdict
    q_stats = defaultdict(lambda: {
        'total': 0, 'correct': 0,
        'wrong_choices': {'A': 0, 'B': 0, 'C': 0, 'D': 0},
        'sessions': set(),
    })
    for a in all_answers:
        qs = q_stats[a.question_id]
        qs['total'] += 1
        qs['sessions'].add(a.session_id)
        if a.is_correct:
            qs['correct'] += 1
        else:
            qs['wrong_choices'][a.answer] = qs['wrong_choices'].get(a.answer, 0) + 1

    question_stats = []
    for qid, qs in q_stats.items():
        q = Question.query.get(qid)
        wrong = qs['total'] - qs['correct']
        diff_pct = round(wrong / qs['total'] * 100) if qs['total'] > 0 else 0
        question_stats.append({
            'question_id':    qid,
            'question_text':  (q.question_text or '')[:80] if q else '',
            'question_image': q.image_url or '' if q else '',
            'sessions_count': len(qs['sessions']),
            'total_answers':  qs['total'],
            'correct_count':  qs['correct'],
            'wrong_count':    wrong,
            'difficulty_pct': diff_pct,
            'wrong_choices':  qs['wrong_choices'],
        })
    # ترتيب من الأصعب للأسهل
    question_stats.sort(key=lambda x: x['difficulty_pct'], reverse=True)

    # ── أداء الطلاب عبر الجلسات ──────────────────────────────────────────────
    # جمع الطلاب المرتبطين
    links = TeacherStudent.query.filter(
        (TeacherStudent.teacher_id == teacher_id) if teacher_id
        else (TeacherStudent.admin_id == admin_id)
    ).all()
    linked_student_ids = {l.student_id for l in links}

    student_session_scores = defaultdict(list)
    for s in sessions:
        # إجابات هذه الجلسة
        sess_answers = [a for a in all_answers if a.session_id == s.id]
        per_stu = defaultdict(lambda: {'correct': 0, 'total': 0})
        for a in sess_answers:
            per_stu[a.student_id]['total'] += 1
            if a.is_correct:
                per_stu[a.student_id]['correct'] += 1
        total_q = s.total_questions or 1
        for sid, sc in per_stu.items():
            if sid in linked_student_ids:
                pct = round(sc['correct'] / total_q * 100, 1)
                student_session_scores[sid].append({
                    'session_id':    s.id,
                    'session_title': s.title,
                    'date':          s.created_at.isoformat() + 'Z',
                    'score_pct':     pct,
                    'correct':       sc['correct'],
                    'total':         total_q,
                })

    student_trends = []
    for sid, scores in student_session_scores.items():
        if len(scores) < 2:
            continue  # نحتاج جلستين على الأقل للـ trend
        stu = Student.query.get(sid)
        first = scores[0]['score_pct']
        last  = scores[-1]['score_pct']
        trend = 'up' if last > first else ('down' if last < first else 'stable')
        student_trends.append({
            'student_id':   sid,
            'student_name': stu.name if stu else '',
            'sessions':     scores,
            'trend':        trend,
            'first_score':  first,
            'last_score':   last,
        })
    student_trends.sort(key=lambda x: x['student_name'])

    # ── ملخص الجلسات ─────────────────────────────────────────────────────────
    session_overview = []
    for s in reversed(sessions):  # من الأحدث للأقدم
        sess_answers = [a for a in all_answers if a.session_id == s.id]
        answered_students = len({a.student_id for a in sess_answers})
        correct = sum(1 for a in sess_answers if a.is_correct)
        total   = len(sess_answers)
        avg_pct = round(correct / total * 100, 1) if total > 0 else 0.0
        session_overview.append({
            'session_id':       s.id,
            'title':            s.title,
            'date':             s.created_at.isoformat() + 'Z',
            'total_questions':  s.total_questions,
            'answered_students': answered_students,
            'avg_score':        avg_pct,
        })

    return jsonify({
        'success':          True,
        'question_stats':   question_stats,
        'student_trends':   student_trends,
        'session_overview': session_overview,
    })


# ── 8. حذف جلسة ──────────────────────────────────────────────────────────────

@kim_response_bp.route('/api/kim-response/session/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    """حذف جلسة مع كل إجاباتها"""
    session = _get_session_or_404(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'غير مصرح'}), 403

    KimResponseAnswer.query.filter_by(session_id=session_id).delete()
    db.session.delete(session)
    db.session.commit()

    return jsonify({'success': True})


# ── مساعد: بيانات السؤال ─────────────────────────────────────────────────────

def _question_to_dict(question_id, session_id=None):
    if not question_id:
        return None
    q = Question.query.get(question_id)
    if not q:
        return None

    opts = list(q.options[:4])
    if session_id:
        import random
        indices = list(range(len(opts)))
        random.Random(session_id * 10007 + question_id).shuffle(indices)
        opts = [opts[i] for i in indices]

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
            for i, opt in enumerate(opts)
        ],
    }


def _correct_letter_after_shuffle(question, session_id):
    """يرجع حرف الإجابة الصحيحة بعد خلط الخيارات بناءً على session_id"""
    import random
    opts = list(question.options[:4])
    indices = list(range(len(opts)))
    random.Random(session_id * 10007 + question.question_id).shuffle(indices)
    for display_pos, orig_idx in enumerate(indices):
        if opts[orig_idx].is_correct:
            return chr(65 + display_pos)
    return 'A'
