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
from flask import Blueprint, jsonify, request, render_template_string
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

    # نمرر IDs فقط للـ thread — نتجنب detached instance بعد انتهاء الـ session
    from flask import current_app
    app = current_app._get_current_object()
    question_ids = [q.question_id for q in questions]

    _auto_tag_status.update({'running': True, 'progress': 0,
                              'total': len(question_ids), 'done': 0, 'errors': 0})

    thread = threading.Thread(
        target=_run_auto_tag,
        args=(question_ids, app),
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


def _run_auto_tag(question_ids, app):
    """دالة AI تعمل في thread منفصل — تأخذ IDs وتحمّل الأسئلة داخل session جديدة"""
    global _auto_tag_status
    keys_list = '\n'.join(f'- {k}' for k in VALID_FORMULA_KEYS)
    from src.extensions import db as _db
    from sqlalchemy.orm import joinedload

    consecutive_errors = 0

    with app.app_context():
        try:
            from src.services.gemini_client import gemini_key_manager
            from src.models.ai_analysis import AISetting
            client = gemini_key_manager.get_client()
            model = AISetting.get_setting('explanation_ai_model', 'gemini-2.0-flash')
        except Exception as e:
            logger.error(f'❌ لا يمكن تهيئة Gemini: {e}')
            _auto_tag_status['running'] = False
            return
        for i, qid in enumerate(question_ids):
            try:
                _auto_tag_status['progress'] = i + 1

                # تحميل السؤال مع خياراته في session جديدة
                q = Question.query.options(joinedload(Question.options)).get(qid)
                if not q:
                    _auto_tag_status['done'] += 1
                    continue

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
                    consecutive_errors = 0  # ريست عند النجاح
                except Exception as api_err:
                    err_str = str(api_err)
                    consecutive_errors += 1
                    logger.warning(f'⚠️ خطأ API سؤال {qid}: {err_str[:120]} (متتالية: {consecutive_errors})')
                    if '429' in err_str or 'quota' in err_str.lower() or '404' in err_str:
                        rotated = gemini_key_manager.rotate_key()
                        if rotated:
                            client = gemini_key_manager.get_client()
                            consecutive_errors = 0
                            logger.info('🔄 تم تدوير مفتاح Gemini')
                        else:
                            logger.error('❌ لا يوجد مفتاح Gemini صالح — إيقاف التصنيف')
                            _auto_tag_status['errors'] += 1
                            break
                    if consecutive_errors >= 5:
                        logger.error('❌ أوقف التصنيف: 5 أخطاء متتالية')
                        _auto_tag_status['errors'] += 1
                        break
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
                logger.error(f'❌ خطأ سؤال {qid}: {e}')
                _db.session.rollback()
                _auto_tag_status['errors'] += 1

    _auto_tag_status['running'] = False
    logger.info(f'✅ انتهى التصنيف: {_auto_tag_status["done"]} نجح، {_auto_tag_status["errors"]} خطأ')


# ──────────────────────────────────────────────
# 5. GET /admin/formulas — صفحة الأدمن
# ──────────────────────────────────────────────
_ADMIN_PAGE = '''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ربط القوانين بالأسئلة</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", Tahoma, Arial, sans-serif; background: #f0f4f8; color: #1e293b; direction: rtl; }
  .header { background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); color: #fff; padding: 20px 28px; }
  .header h1 { font-size: 20px; font-weight: 700; }
  .header p  { font-size: 13px; opacity: .8; margin-top: 4px; }
  .container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 14px; padding: 22px; margin-bottom: 20px;
          box-shadow: 0 2px 10px rgba(0,0,0,.07); }
  .card h2 { font-size: 15px; font-weight: 700; color: #1e3a5f; margin-bottom: 14px;
             border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }

  /* إحصائيات */
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
  .stat { text-align: center; padding: 16px 10px; border-radius: 10px; }
  .stat.total   { background: #eff6ff; border: 1px solid #bfdbfe; }
  .stat.tagged  { background: #f0fdf4; border: 1px solid #bbf7d0; }
  .stat.untagged{ background: #fef2f2; border: 1px solid #fecaca; }
  .stat.pct     { background: #faf5ff; border: 1px solid #e9d5ff; }
  .stat .num { font-size: 32px; font-weight: 800; line-height: 1; }
  .stat .lbl { font-size: 12px; margin-top: 4px; opacity: .75; }
  .stat.total    .num { color: #2563eb; }
  .stat.tagged   .num { color: #059669; }
  .stat.untagged .num { color: #dc2626; }
  .stat.pct      .num { color: #7c3aed; }

  /* شريط تقدم */
  .progress-wrap { background: #e2e8f0; border-radius: 99px; height: 18px; overflow: hidden; margin: 10px 0; }
  .progress-bar  { height: 100%; background: linear-gradient(90deg, #059669, #34d399);
                   border-radius: 99px; transition: width .4s; }

  /* أزرار */
  .btn { display: inline-block; padding: 10px 24px; border-radius: 8px; font-size: 14px;
         font-weight: 700; cursor: pointer; border: none; transition: opacity .2s; }
  .btn:hover { opacity: .85; }
  .btn:disabled { opacity: .45; cursor: not-allowed; }
  .btn-primary { background: #2563eb; color: #fff; }
  .btn-danger  { background: #dc2626; color: #fff; }
  .btn-gray    { background: #64748b; color: #fff; }

  /* الإعدادات */
  .form-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .form-row label { font-size: 13px; font-weight: 600; min-width: 140px; }
  .form-row input[type=number] { width: 90px; padding: 7px 10px; border: 1px solid #cbd5e1;
                                  border-radius: 7px; font-size: 14px; text-align: center; }
  .form-row input[type=checkbox] { width: 18px; height: 18px; cursor: pointer; }

  /* جدول التوزيع */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #1e3a5f; color: #fff; padding: 9px 12px; text-align: right; }
  td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
  tr:nth-child(even) td { background: #f8fafc; }
  tr:hover td { background: #eff6ff; }
  .badge { display: inline-block; background: #2563eb; color: #fff; font-size: 11px;
           padding: 2px 9px; border-radius: 99px; font-weight: 700; }

  /* حالة */
  .status-box { padding: 12px 16px; border-radius: 9px; font-size: 13px; font-weight: 600;
                margin-top: 12px; display: none; }
  .status-box.show { display: block; }
  .status-box.running { background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; }
  .status-box.done    { background: #f0fdf4; border: 1px solid #bbf7d0; color: #059669; }
  .status-box.error   { background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; }

  .spin { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* صفوف الجدول قابلة للضغط */
  tbody tr { cursor: pointer; }
  tbody tr:hover td { background: #dbeafe !important; }

  /* Modal */
  .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.45);
                   z-index: 9999; align-items: center; justify-content: center; }
  .modal-overlay.open { display: flex; }
  .modal { background: #fff; border-radius: 16px; width: min(95vw, 820px);
           max-height: 88vh; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,.25); }
  .modal-head { padding: 18px 22px; border-bottom: 1px solid #e2e8f0; display: flex;
                align-items: center; justify-content: space-between; }
  .modal-head h3 { font-size: 16px; font-weight: 700; color: #1e3a5f; }
  .modal-close { background: none; border: none; font-size: 22px; cursor: pointer; color: #64748b; }
  .modal-body { flex: 1; overflow-y: auto; padding: 16px 22px; }
  .modal-foot { padding: 14px 22px; border-top: 1px solid #e2e8f0; display: flex;
                gap: 10px; align-items: center; }

  /* بطاقة سؤال */
  .q-card { border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 12px;
            padding: 14px 16px; background: #f8fafc; }
  .q-card .q-id { font-size: 11px; color: #94a3b8; margin-bottom: 6px; }
  .q-card .q-text { font-size: 14px; color: #1e293b; margin-bottom: 10px; line-height: 1.6; }
  .q-card .q-options { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .q-card .q-opt { font-size: 12px; padding: 3px 10px; border-radius: 6px;
                   background: #e2e8f0; color: #475569; }
  .q-card .q-opt.correct { background: #dcfce7; color: #166534; font-weight: 700; }
  .q-card .q-row { display: flex; align-items: center; gap: 10px; }
  .q-card select { flex: 1; padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 7px;
                   font-size: 13px; background: #fff; }
  .q-card .save-btn { padding: 6px 16px; background: #2563eb; color: #fff; border: none;
                      border-radius: 7px; font-size: 12px; font-weight: 700; cursor: pointer; }
  .q-card .save-btn:hover { background: #1d4ed8; }
  .q-card .save-btn.saved { background: #059669; }
  .q-card .save-btn:disabled { opacity: .5; cursor: not-allowed; }

  /* pagination */
  .pag { display: flex; gap: 6px; align-items: center; margin-top: 6px; }
  .pag button { padding: 5px 14px; border: 1px solid #cbd5e1; border-radius: 6px;
                background: #fff; cursor: pointer; font-size: 12px; }
  .pag button:disabled { opacity: .4; cursor: not-allowed; }
  .pag .pag-info { font-size: 12px; color: #64748b; }
</style>
</head>
<body>

<div class="header">
  <h1>🔗 ربط القوانين الكيميائية بالأسئلة</h1>
  <p>تصنيف الأسئلة تلقائياً باستخدام Gemini AI</p>
</div>

<div class="container">

  <!-- الإحصائيات -->
  <div class="card">
    <h2>📊 إحصائيات التصنيف</h2>
    <div class="stats-grid">
      <div class="stat total">
        <div class="num" id="s-total">—</div>
        <div class="lbl">إجمالي الأسئلة</div>
      </div>
      <div class="stat tagged">
        <div class="num" id="s-tagged">—</div>
        <div class="lbl">مصنّفة ✓</div>
      </div>
      <div class="stat untagged">
        <div class="num" id="s-untagged">—</div>
        <div class="lbl">غير مصنّفة</div>
      </div>
      <div class="stat pct">
        <div class="num" id="s-pct">—</div>
        <div class="lbl">نسبة التصنيف</div>
      </div>
    </div>
    <div style="margin-top:14px;">
      <div style="font-size:12px;color:#64748b;margin-bottom:4px;">نسبة الاكتمال</div>
      <div class="progress-wrap">
        <div class="progress-bar" id="pct-bar" style="width:0%"></div>
      </div>
    </div>
    <button class="btn btn-gray" style="margin-top:12px;font-size:12px;padding:7px 16px"
            onclick="loadStats()">🔄 تحديث</button>
  </div>

  <!-- تشغيل التصنيف -->
  <div class="card">
    <h2>🤖 تشغيل التصنيف بالذكاء الاصطناعي</h2>

    <div class="form-row">
      <label>عدد الأسئلة:</label>
      <input type="number" id="batch-size" value="50" min="1" max="200">
      <span style="font-size:12px;color:#64748b">(الحد الأقصى 200)</span>
    </div>
    <div class="form-row">
      <label>إعادة تصنيف المصنّفة:</label>
      <input type="checkbox" id="retag-all">
      <span style="font-size:12px;color:#64748b">يُصنّف الأسئلة التي لها مفتاح مسبق</span>
    </div>

    <div style="display:flex;gap:10px;flex-wrap:wrap;">
      <button class="btn btn-primary" id="btn-start" onclick="startTagging()">
        ▶ تشغيل التصنيف
      </button>
      <button class="btn btn-gray" id="btn-status" onclick="checkStatus(true)">
        📡 تحقق من الحالة
      </button>
    </div>

    <div class="status-box" id="status-box">
      <span id="status-icon">⏳</span> <span id="status-text">جارٍ التحميل...</span>
      <div style="margin-top:8px;" id="progress-detail"></div>
    </div>
  </div>

  <!-- توزيع التصنيف -->
  <div class="card">
    <h2>📋 توزيع الأسئلة حسب القانون <span style="font-size:12px;font-weight:400;color:#64748b">— اضغط على صف لعرض الأسئلة</span></h2>
    <div id="dist-table">
      <p style="color:#94a3b8;font-size:13px">اضغط "تحديث" لتحميل البيانات</p>
    </div>
    <button class="btn btn-gray" style="margin-top:12px;font-size:12px;padding:7px 16px"
            onclick="loadStats()">🔄 تحديث الجدول</button>
  </div>

</div>

<!-- Modal عرض الأسئلة -->
<div class="modal-overlay" id="q-modal">
  <div class="modal">
    <div class="modal-head">
      <h3 id="modal-title">أسئلة القانون</h3>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body">
      <p style="color:#94a3b8;text-align:center;padding:40px">جارٍ التحميل...</p>
    </div>
    <div class="modal-foot">
      <div class="pag" id="modal-pag"></div>
      <div style="flex:1"></div>
      <span id="modal-info" style="font-size:12px;color:#64748b"></span>
    </div>
  </div>
</div>

<script>
let pollTimer = null;

async function loadStats() {
  try {
    const r = await fetch('/api/formulas/stats');
    const d = await r.json();
    if (!d.success) return;

    document.getElementById('s-total').textContent   = d.total.toLocaleString();
    document.getElementById('s-tagged').textContent  = d.tagged.toLocaleString();
    document.getElementById('s-untagged').textContent = d.untagged.toLocaleString();
    document.getElementById('s-pct').textContent     = d.percentage + '%';
    document.getElementById('pct-bar').style.width   = d.percentage + '%';

    // جدول التوزيع
    if (d.distribution && d.distribution.length) {
      let html = '<table><thead><tr><th>#</th><th>القانون</th><th>عدد الأسئلة</th></tr></thead><tbody>';
      d.distribution.forEach((row, i) => {
        const ek = row.key.replace(/'/g, "\\'");
        html += `<tr onclick="openModal('${ek}', ${row.count})">
          <td>${i+1}</td>
          <td>🔗 ${row.key}</td>
          <td><span class="badge">${row.count}</span></td>
        </tr>`;
      });
      html += '</tbody></table>';
      document.getElementById('dist-table').innerHTML = html;
    } else {
      document.getElementById('dist-table').innerHTML =
        '<p style="color:#94a3b8;font-size:13px">لا توجد بيانات بعد</p>';
    }
  } catch(e) {
    console.error(e);
  }
}

async function startTagging() {
  const batchSize = parseInt(document.getElementById('batch-size').value) || 50;
  const retagAll  = document.getElementById('retag-all').checked;

  document.getElementById('btn-start').disabled = true;
  showStatus('running', '⏳', 'جارٍ بدء التصنيف...');

  try {
    const r = await fetch('/api/formulas/auto-tag', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ batch_size: batchSize, retag_all: retagAll })
    });
    const d = await r.json();

    if (d.success) {
      showStatus('running', '<span class="spin">⚙️</span>',
        `بدأ تصنيف ${d.total} سؤال في الخلفية...`);
      startPolling();
    } else {
      showStatus('error', '❌', d.error || 'خطأ غير معروف');
      document.getElementById('btn-start').disabled = false;
    }
  } catch(e) {
    showStatus('error', '❌', 'فشل الاتصال بالسيرفر');
    document.getElementById('btn-start').disabled = false;
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(checkStatus, 5000);
}

async function checkStatus(manual = false) {
  try {
    const r = await fetch('/api/formulas/auto-tag/status');
    const d = await r.json();
    if (!d.success) return;

    const st = d.status;
    const pct = st.total > 0 ? Math.round(st.progress / st.total * 100) : 0;

    if (st.running) {
      showStatus('running', '<span class="spin">⚙️</span>',
        `جارٍ التصنيف...`,
        `✅ ${st.done} نجح | ❌ ${st.errors} خطأ | 📊 ${st.progress}/${st.total} (${pct}%)`);
    } else if (st.done > 0 || st.errors > 0) {
      showStatus('done', '✅',
        `انتهى التصنيف`,
        `✅ ${st.done} سؤال نجح | ❌ ${st.errors} خطأ`);
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      document.getElementById('btn-start').disabled = false;
      await loadStats();
    } else {
      if (manual) showStatus('done', '💤', 'لا يوجد تصنيف جارٍ حالياً');
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      document.getElementById('btn-start').disabled = false;
    }
  } catch(e) {
    if (manual) showStatus('error', '❌', 'فشل الاتصال');
  }
}

function showStatus(type, icon, text, detail='') {
  const box = document.getElementById('status-box');
  box.className = 'status-box show ' + type;
  document.getElementById('status-icon').innerHTML = icon;
  document.getElementById('status-text').textContent = text;
  document.getElementById('progress-detail').innerHTML = detail
    ? `<div style="font-size:12px;margin-top:4px;opacity:.85">${detail}</div>` : '';
}

// ── Modal ──
let _modalKey = '';
let _modalPage = 1;
let _validKeys = [];

async function openModal(key, count) {
  _modalKey = key;
  _modalPage = 1;
  document.getElementById('modal-title').textContent = `📋 ${key} — ${count} سؤال`;
  document.getElementById('modal-body').innerHTML =
    '<p style="color:#94a3b8;text-align:center;padding:40px">جارٍ التحميل...</p>';
  document.getElementById('q-modal').classList.add('open');
  await loadModalPage(1);
}

function closeModal() {
  document.getElementById('q-modal').classList.remove('open');
}
document.getElementById('q-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

async function loadModalPage(page) {
  _modalPage = page;
  try {
    const r = await fetch(`/api/formulas/admin-questions?key=${encodeURIComponent(_modalKey)}&page=${page}&per_page=10`);
    const d = await r.json();
    if (!d.success) { document.getElementById('modal-body').innerHTML = `<p style="color:red">${d.error}</p>`; return; }
    _validKeys = d.valid_keys || [];

    const body = document.getElementById('modal-body');
    if (!d.questions.length) { body.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:40px">لا توجد أسئلة</p>'; return; }

    body.innerHTML = d.questions.map(q => `
      <div class="q-card" id="qcard-${q.id}">
        <div class="q-id">سؤال #${q.id}${q.is_blocked ? ' 🚫 محظور' : ''} · ${q.difficulty}</div>
        <div class="q-text">${q.image_url ? '<span style="color:#7c3aed">📷 سؤال بصورة</span><br>' : ''}${escHtml(q.text || '(بدون نص)')}</div>
        <div class="q-options">
          ${q.options.map(o => `<span class="q-opt${o.is_correct?' correct':''}">${o.is_correct?'✓ ':''}${escHtml(o.text||'صورة')}</span>`).join('')}
        </div>
        <div class="q-row">
          <select id="sel-${q.id}" onchange="markChanged(${q.id})">
            <option value="">— بدون قانون —</option>
            ${_validKeys.map(k => `<option value="${escHtml(k)}"${k===q.formula_key?' selected':''}>${escHtml(k)}</option>`).join('')}
          </select>
          <button class="save-btn" id="savebtn-${q.id}" onclick="saveKey(${q.id})" disabled>حفظ</button>
        </div>
      </div>`).join('');

    // pagination
    const pag = document.getElementById('modal-pag');
    if (d.pages > 1) {
      pag.innerHTML = `
        <button onclick="loadModalPage(${page-1})" ${page<=1?'disabled':''}>◀ السابق</button>
        <span class="pag-info">صفحة ${page} من ${d.pages}</span>
        <button onclick="loadModalPage(${page+1})" ${page>=d.pages?'disabled':''}>التالي ▶</button>`;
    } else { pag.innerHTML = ''; }
    document.getElementById('modal-info').textContent = `إجمالي: ${d.total} سؤال`;

  } catch(e) {
    document.getElementById('modal-body').innerHTML = '<p style="color:red">فشل التحميل</p>';
  }
}

function markChanged(qid) {
  const btn = document.getElementById('savebtn-' + qid);
  btn.disabled = false;
  btn.textContent = 'حفظ';
  btn.className = 'save-btn';
}

async function saveKey(qid) {
  const sel = document.getElementById('sel-' + qid);
  const btn = document.getElementById('savebtn-' + qid);
  const key = sel.value || null;
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const r = await fetch(`/api/formulas/questions/${qid}/key`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({formula_key: key})
    });
    const d = await r.json();
    if (d.success) {
      btn.textContent = '✓ محفوظ';
      btn.className = 'save-btn saved';
    } else {
      btn.textContent = '✕ خطأ';
      btn.disabled = false;
    }
  } catch(e) {
    btn.textContent = '✕ فشل';
    btn.disabled = false;
  }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// تحميل البيانات عند فتح الصفحة
loadStats();
checkStatus();
</script>
</body>
</html>'''


@formula_bp.route('/admin', methods=['GET'])
def formula_admin_page():
    """صفحة الأدمن لإدارة تصنيف القوانين"""
    return render_template_string(_ADMIN_PAGE)


# ──────────────────────────────────────────────
# 6. GET /api/formulas/admin-questions — أدمن: أسئلة قانون مع تفاصيل كاملة
# ──────────────────────────────────────────────
@formula_bp.route('/admin-questions', methods=['GET'])
def admin_get_questions():
    """جلب الأسئلة المرتبطة بقانون — للأدمن مع إمكانية التعديل"""
    key = request.args.get('key', '').strip()
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(int(request.args.get('per_page', 20)), 50)

    if not key:
        return jsonify({'success': False, 'error': 'key مطلوب'}), 400

    try:
        from sqlalchemy.orm import joinedload
        q_query = Question.query.options(joinedload(Question.options))\
            .filter_by(formula_key=key)\
            .order_by(Question.question_id.desc())

        total = q_query.count()
        questions = q_query.offset((page - 1) * per_page).limit(per_page).all()

        result = []
        for q in questions:
            options = [{'id': o.option_id, 'text': o.option_text or '',
                        'is_correct': o.is_correct} for o in q.options]
            result.append({
                'id': q.question_id,
                'text': q.question_text or '',
                'image_url': q.image_url,
                'formula_key': q.formula_key,
                'difficulty': q.difficulty or 'medium',
                'is_blocked': q.is_blocked,
                'options': options,
            })

        return jsonify({
            'success': True,
            'questions': result,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'valid_keys': VALID_FORMULA_KEYS,
        })
    except Exception as e:
        logger.error(f'❌ admin_get_questions: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
