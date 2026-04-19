"""
formula_routes.py
ربط القوانين الكيميائية بالأسئلة — ميزة ④

Routes:
  GET  /api/formulas/by-formula?key=X         ← طالب: أسئلة مرتبطة بقانون
  POST /api/formulas/auto-tag                 ← أدمن: تصنيف AI تلقائي
  PUT  /api/formulas/questions/<id>/key       ← أدمن: تعديل يدوي
  GET  /api/formulas/stats                    ← أدمن: إحصائيات التصنيف
"""

import json
import logging
import time
import threading
from flask import Blueprint, jsonify, request
from src.extensions import db
from src.models.question import Question

logger = logging.getLogger(__name__)

formula_bp = Blueprint('formula', __name__, url_prefix='/api/formulas')

# ──────────────────────────────────────────────
# قائمة القوانين الصالحة (تطابق formulaKey في Flutter)
# ──────────────────────────────────────────────
VALID_FORMULA_KEYS = [
    # كيمياء 1
    'قواعد وزن المعادلات', 'تفاعل التوليف', 'تفاعل التحليل',
    'تفاعل الإحلال البسيط', 'تفاعل الإحلال المزدوج', 'تفاعل الاحتراق',
    'سلسلة النشاط', 'الأيونات الأحادية الشحنة', 'الأيونات متعددة الذرات',
    'الأيونات الانتقالية', 'تسمية المركبات الثنائية', 'تسمية مركبات البولي آتومي',
    'عدد أفوجادرو', 'الكتلة المولية', 'عدد المولات',
    'المول والكتلة والجسيمات',
    # كيمياء 2-1
    'نموذج بور', 'مستويات الطاقة', 'التوزيع الإلكتروني',
    'قاعدة هوند', 'مبدأ أوفباو', 'الأعداد الكمية',
    'الرابطة الأيونية', 'الرابطة التساهمية', 'الرابطة الفلزية',
    'طاقة الشبكة البلورية', 'VSEPR', 'عدد التأكسد',
    'الخصائص الدورية', 'الطيف الضوئي', 'المدارات الهجينة',
    # كيمياء 2-2
    'المولارية', 'الضغط الأسموزي', 'درجة غليان المحلول',
    'درجة تجمد المحلول', 'قانون بويل', 'قانون شارل',
    'قانون جاي-لوساك', 'قانون الغاز المثالي', 'قانون دالتون',
    'سرعة التفاعل', 'قانون السرعة', 'العمر النصفي',
    'الكيمياء العضوية — الألكانات', 'الكيمياء العضوية — الألكينات',
    'المجموعات الوظيفية', 'الكحولات', 'الألدهيدات والكيتونات', 'الإسترات',
    # كيمياء 3
    'ثابت الاتزان Kc', 'ثابت الاتزان Kp', 'مبدأ لو شاتيليه',
    'الذائبية Ksp', 'pH وpOH', 'ثابت تأين الحمض Ka',
    'ثابت تأين القاعدة Kb', 'التفاعل الحمض-القاعدة',
    'تغير الإنتالبي ΔH', 'قانون هس', 'طاقة الرابطة',
    'التفاعلات الجلفانية', 'معادلة نيرنست',
]

# ──────────────────────────────────────────────
# 1. GET /api/formulas/by-formula — طالب/معلم
# ──────────────────────────────────────────────
@formula_bp.route('/by-formula', methods=['GET'])
def get_questions_by_formula():
    """جلب أسئلة مرتبطة بقانون معين"""
    key = request.args.get('key', '').strip()
    limit = min(int(request.args.get('limit', 20)), 50)

    if not key:
        return jsonify({'success': False, 'error': 'key مطلوب'}), 400

    try:
        questions = Question.query.filter_by(formula_key=key)\
            .filter_by(is_blocked=False)\
            .limit(limit).all()

        result = []
        for q in questions:
            options = []
            for opt in q.options:
                options.append({
                    'id': opt.option_id,
                    'text': opt.option_text or '',
                    'image_url': opt.image_url,
                    'is_correct': opt.is_correct,
                })
            result.append({
                'id': q.question_id,
                'text': q.question_text or '',
                'image_url': q.image_url,
                'options': options,
                'explanation': q.explanation or '',
                'difficulty': q.difficulty or 'medium',
            })

        return jsonify({'success': True, 'questions': result, 'count': len(result)})

    except Exception as e:
        logger.error(f'❌ get_questions_by_formula: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────
# 2. GET /api/formulas/stats — أدمن
# ──────────────────────────────────────────────
@formula_bp.route('/stats', methods=['GET'])
def get_tagging_stats():
    """إحصائيات تصنيف القوانين"""
    try:
        total = Question.query.filter_by(is_blocked=False).count()
        tagged = Question.query.filter(
            Question.formula_key.isnot(None),
            Question.formula_key != ''
        ).count()
        untagged = total - tagged

        # توزيع حسب القانون
        from sqlalchemy import func
        distribution = db.session.query(
            Question.formula_key,
            func.count(Question.question_id).label('count')
        ).filter(
            Question.formula_key.isnot(None),
            Question.formula_key != ''
        ).group_by(Question.formula_key)\
         .order_by(func.count(Question.question_id).desc())\
         .all()

        return jsonify({
            'success': True,
            'total': total,
            'tagged': tagged,
            'untagged': untagged,
            'percentage': round(tagged / total * 100, 1) if total else 0,
            'distribution': [{'key': r[0], 'count': r[1]} for r in distribution],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────
# 3. PUT /api/formulas/questions/<id>/key — أدمن: تعديل يدوي
# ──────────────────────────────────────────────
@formula_bp.route('/questions/<int:question_id>/key', methods=['PUT'])
def update_formula_key(question_id):
    """تعديل formula_key يدوياً"""
    data = request.get_json() or {}
    key = data.get('formula_key', '').strip() or None  # '' → None

    if key and key not in VALID_FORMULA_KEYS:
        return jsonify({
            'success': False,
            'error': f'المفتاح "{key}" غير موجود في القائمة المعتمدة'
        }), 400

    try:
        q = Question.query.get_or_404(question_id)
        q.formula_key = key
        db.session.commit()
        return jsonify({'success': True, 'question_id': question_id, 'formula_key': key})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────
# 4. POST /api/formulas/auto-tag — أدمن: تصنيف AI
# ──────────────────────────────────────────────
_auto_tag_status = {'running': False, 'progress': 0, 'total': 0, 'done': 0, 'errors': 0}

@formula_bp.route('/auto-tag', methods=['POST'])
def auto_tag_formulas():
    """تشغيل AI لتصنيف الأسئلة غير المصنّفة — يعمل في الخلفية"""
    if _auto_tag_status['running']:
        return jsonify({'success': False, 'error': 'التصنيف يعمل بالفعل',
                        'status': _auto_tag_status}), 409

    data = request.get_json() or {}
    batch_size = min(int(data.get('batch_size', 50)), 200)
    retag_all = data.get('retag_all', False)  # إعادة تصنيف المصنّف مسبقاً

    # جلب الأسئلة
    query = Question.query.filter_by(is_blocked=False)
    if not retag_all:
        query = query.filter(
            (Question.formula_key == None) | (Question.formula_key == '')
        )
    questions = query.limit(batch_size).all()

    if not questions:
        return jsonify({'success': True, 'message': 'لا توجد أسئلة تحتاج تصنيف', 'count': 0})

    # شغّل في خلفية
    _auto_tag_status.update({'running': True, 'progress': 0,
                              'total': len(questions), 'done': 0, 'errors': 0})

    thread = threading.Thread(
        target=_run_auto_tag,
        args=(questions,),
        daemon=True
    )
    thread.start()

    return jsonify({
        'success': True,
        'message': f'بدأ التصنيف لـ {len(questions)} سؤال في الخلفية',
        'total': len(questions),
    })


@formula_bp.route('/auto-tag/status', methods=['GET'])
def auto_tag_status():
    """حالة عملية التصنيف الجارية"""
    return jsonify({'success': True, 'status': _auto_tag_status})


def _run_auto_tag(questions):
    """دالة AI تعمل في thread منفصل"""
    global _auto_tag_status
    try:
        from src.services.gemini_client import gemini_key_manager
        client = gemini_key_manager.get_client()
        model = 'gemini-2.0-flash'
    except Exception as e:
        logger.error(f'❌ لا يمكن تهيئة Gemini: {e}')
        _auto_tag_status['running'] = False
        return

    keys_list = '\n'.join(f'- {k}' for k in VALID_FORMULA_KEYS)

    from src.main import create_app
    # نحتاج app context للوصول لقاعدة البيانات
    try:
        from src.extensions import db as _db
        # استخدم current_app إذا كنا في context، وإلا أنشئ واحداً
        from flask import current_app
        app = current_app._get_current_object()
    except RuntimeError:
        logger.error('❌ لا يوجد Flask app context')
        _auto_tag_status['running'] = False
        return

    with app.app_context():
        for i, q in enumerate(questions):
            try:
                _auto_tag_status['progress'] = i + 1

                question_text = q.question_text or ''
                options_text = ''
                if q.options:
                    opts = [o.option_text or '' for o in q.options if o.option_text]
                    options_text = ' | '.join(opts[:4])

                if not question_text and not options_text:
                    _auto_tag_status['done'] += 1
                    continue

                prompt = f"""أنت مساعد متخصص في تصنيف أسئلة الكيمياء للمنهج السعودي.

السؤال: {question_text}
الخيارات: {options_text}

من القائمة التالية، أي قانون كيميائي يختبره هذا السؤال بشكل مباشر؟
{keys_list}

قواعد:
- أجب بالاسم الدقيق من القائمة فقط
- إذا لم يرتبط السؤال بأي قانون محدد، أجب بكلمة: لا_ينطبق
- لا تضف أي شرح أو نص إضافي

الجواب:"""

                time.sleep(4)  # تجنب rate limit
                try:
                    resp = client.models.generate_content(model=model, contents=prompt)
                    raw = resp.text.strip().replace('\n', '').strip()
                except Exception as api_err:
                    if '429' in str(api_err) or 'quota' in str(api_err).lower():
                        if gemini_key_manager.rotate_key():
                            client = gemini_key_manager.get_client()
                    _auto_tag_status['errors'] += 1
                    continue

                # تحقق أن الجواب في القائمة
                formula_key = None
                if raw in VALID_FORMULA_KEYS:
                    formula_key = raw
                elif raw != 'لا_ينطبق':
                    # بحث جزئي
                    match = next((k for k in VALID_FORMULA_KEYS if k in raw or raw in k), None)
                    formula_key = match

                # احفظ
                q.formula_key = formula_key
                _db.session.commit()
                _auto_tag_status['done'] += 1

            except Exception as e:
                logger.error(f'❌ خطأ سؤال {q.question_id}: {e}')
                _db.session.rollback()
                _auto_tag_status['errors'] += 1

    _auto_tag_status['running'] = False
    logger.info(f'✅ انتهى التصنيف: {_auto_tag_status["done"]} نجح، {_auto_tag_status["errors"]} خطأ')
