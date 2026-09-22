"""
قوانين التحصيلي — مسارات API
GET  /api/formulas              — كل القوانين (اختياري: ?course=كيمياء 1)
POST /api/admin/formulas        — إضافة قانون (أدمن)
PUT  /api/admin/formulas/<id>   — تعديل قانون (أدمن)
DELETE /api/admin/formulas/<id> — حذف قانون (أدمن)
POST /api/admin/formulas/seed   — حشر البيانات الأولية (أدمن، مرة وحدة)
"""

from flask import Blueprint, request, jsonify
from flask_login import current_user
from functools import wraps
from src.extensions import db

formulas_bp = Blueprint('formulas', __name__)


# ── حارس الأدمن ──────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated


# ── جلب القوانين (طلاب ومعلمون وأدمن) ───────────────────────
@formulas_bp.route('/api/formulas', methods=['GET'])
def get_formulas():
    try:
        course = request.args.get('course')
        if course:
            rows = db.session.execute(
                db.text("""
                    SELECT id, course_name, category, title,
                           latex, formula, description, diagram_type, sort_order
                    FROM formulas
                    WHERE course_name = :c AND is_active = TRUE
                    ORDER BY sort_order, id
                """),
                {'c': course}
            ).fetchall()
        else:
            rows = db.session.execute(
                db.text("""
                    SELECT id, course_name, category, title,
                           latex, formula, description, diagram_type, sort_order
                    FROM formulas
                    WHERE is_active = TRUE
                    ORDER BY course_name, sort_order, id
                """)
            ).fetchall()

        data = [
            {
                'id': r[0],
                'course_name': r[1],
                'category': r[2],
                'title': r[3],
                'latex': r[4],
                'formula': r[5],
                'description': r[6],
                'diagram_type': r[7],
                'sort_order': r[8],
            }
            for r in rows
        ]
        return jsonify({'success': True, 'formulas': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── إضافة قانون ──────────────────────────────────────────────
@formulas_bp.route('/api/admin/formulas', methods=['POST'])
@admin_required
def add_formula():
    try:
        d = request.get_json()
        db.session.execute(
            db.text("""
                INSERT INTO formulas
                    (course_name, category, title, latex, formula, description, diagram_type, sort_order)
                VALUES
                    (:course_name, :category, :title, :latex, :formula, :description, :diagram_type, :sort_order)
            """),
            {
                'course_name': d['course_name'],
                'category': d['category'],
                'title': d['title'],
                'latex': d.get('latex'),
                'formula': d.get('formula'),
                'description': d.get('description', ''),
                'diagram_type': d.get('diagram_type'),
                'sort_order': d.get('sort_order', 0),
            }
        )
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── تعديل قانون ──────────────────────────────────────────────
@formulas_bp.route('/api/admin/formulas/<int:formula_id>', methods=['PUT'])
@admin_required
def update_formula(formula_id):
    try:
        d = request.get_json()
        db.session.execute(
            db.text("""
                UPDATE formulas SET
                    course_name  = :course_name,
                    category     = :category,
                    title        = :title,
                    latex        = :latex,
                    formula      = :formula,
                    description  = :description,
                    diagram_type = :diagram_type,
                    sort_order   = :sort_order,
                    is_active    = :is_active
                WHERE id = :id
            """),
            {
                'id': formula_id,
                'course_name': d['course_name'],
                'category': d['category'],
                'title': d['title'],
                'latex': d.get('latex'),
                'formula': d.get('formula'),
                'description': d.get('description', ''),
                'diagram_type': d.get('diagram_type'),
                'sort_order': d.get('sort_order', 0),
                'is_active': d.get('is_active', True),
            }
        )
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── حذف قانون ────────────────────────────────────────────────
@formulas_bp.route('/api/admin/formulas/<int:formula_id>', methods=['DELETE'])
@admin_required
def delete_formula(formula_id):
    try:
        db.session.execute(
            db.text("UPDATE formulas SET is_active = FALSE WHERE id = :id"),
            {'id': formula_id}
        )
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── حشر البيانات الأولية (مرة وحدة) ─────────────────────────
@formulas_bp.route('/api/admin/formulas/seed', methods=['POST'])
@admin_required
def seed_formulas():
    """يحشر كل القوانين الموجودة في formulas_data.dart — يُنفَّذ مرة وحدة"""
    try:
        count = db.session.execute(db.text("SELECT COUNT(*) FROM formulas")).scalar()
        if count > 0:
            return jsonify({'success': False, 'error': f'الجدول يحتوي {count} قانون بالفعل — احذفهم أولاً إذا تبي تعيد الحشر'}), 400

        formulas = _get_seed_data()
        for i, f in enumerate(formulas):
            db.session.execute(
                db.text("""
                    INSERT INTO formulas
                        (course_name, category, title, latex, formula, description, diagram_type, sort_order)
                    VALUES
                        (:course_name, :category, :title, :latex, :formula, :description, :diagram_type, :sort_order)
                """),
                {**f, 'sort_order': i}
            )
        db.session.commit()
        return jsonify({'success': True, 'inserted': len(formulas)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_seed_data():
    """بيانات القوانين — منقولة من formulas_data.dart"""
    return [
        # ══════════════════════════════════════════════════════
        # كيمياء 1
        # ══════════════════════════════════════════════════════

        # المادة
        {'course_name': 'كيمياء 1', 'category': 'المادة', 'title': 'قانون حفظ الكتلة',
         'latex': None, 'formula': 'كتلة المتفاعلات = كتلة النواتج',
         'description': 'المادة لا تفنى ولا تستحدث من العدم في أي تفاعل كيميائي', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المادة', 'title': 'النسبة المئوية بالكتلة',
         'latex': r'\% = \frac{m}{M} \times 100',
         'formula': 'm = كتلة العنصر (g)\nM = كتلة المركب الكلية (g)',
         'description': 'نسبة كتلة العنصر إلى كتلة المركب الكلية', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المادة', 'title': 'قانون النسب الثابتة',
         'latex': None, 'formula': 'المركب يتكون دائماً من نفس العناصر بنسب كتلية ثابتة',
         'description': 'تركيب المركب الكيميائي ثابت دائماً بغض النظر عن مصدره', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المادة', 'title': 'قانون النسب المتضاعفة',
         'latex': None, 'formula': 'إذا اتحد عنصران بأكثر من نسبة — النسب بينها أعداد صحيحة بسيطة',
         'description': 'إذا كوّن عنصران أكثر من مركب، فالنسبة بين كتل أحد العنصرين أعداد صحيحة', 'diagram_type': None},

        # الذرة
        {'course_name': 'كيمياء 1', 'category': 'الذرة', 'title': 'العدد الكتلي',
         'latex': r'A = Z + N',
         'formula': 'A = العدد الكتلي | Z = عدد البروتونات | N = عدد النيوترونات',
         'description': 'العدد الكتلي = عدد البروتونات + عدد النيوترونات', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'الذرة', 'title': 'مكونات الذرة',
         'latex': None,
         'formula': 'العدد الذري (Z) = عدد البروتونات = عدد الإلكترونات\nعدد النيوترونات (N) = A - Z',
         'description': 'الذرة المتعادلة: عدد البروتونات = عدد الإلكترونات', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'الذرة', 'title': 'النظائر وحساب الكتلة الذرية',
         'latex': r'M_{avg} = m_1 f_1 + m_2 f_2 + \cdots',
         'formula': 'M_avg = الكتلة الذرية الوسطية (g/mol)\nm₁, m₂ = كتلة كل نظير | f₁, f₂ = نسبته الكسرية (% ÷ 100)\n\nمثال: ³⁵Cl (75.77%) و ³⁷Cl (24.23%)\nM = 35×0.7577 + 37×0.2423 = 35.48 ≈ 35.5 g/mol',
         'description': 'النظائر: ذرات نفس العنصر (Z متساوٍ) تختلف في N وبالتالي في A', 'diagram_type': None},

        # الإشعاع النووي
        {'course_name': 'كيمياء 1', 'category': 'الإشعاع النووي', 'title': 'جسيم ألفا',
         'latex': r'{}^{238}_{92}\mathrm{U} \rightarrow {}^{234}_{90}\mathrm{Th} + {}^{4}_{2}\mathrm{He}',
         'formula': 'التغيرات: A: A−4 | Z: Z−2 | N: N−2\nالجسيم: ⁴₂He (نواة هيليوم)',
         'description': 'يبعث نواة هيليوم — شحنته +2 — تأين عالٍ وإختراق منخفض', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'الإشعاع النووي', 'title': 'جسيم بيتا',
         'latex': r'{}^{14}_{6}\mathrm{C} \rightarrow {}^{14}_{7}\mathrm{N} + {}^{0}_{-1}e',
         'formula': 'التغيرات: A: بلا تغير | Z: Z+1 | N: N−1\nالجسيم: ⁰₋₁e (إلكترون سريع)',
         'description': 'يبعث إلكتروناً سريعاً — شحنته -1', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'الإشعاع النووي', 'title': 'إشعاع جاما',
         'latex': r'{}^{A}_{Z}X^{*} \rightarrow {}^{A}_{Z}X + \gamma',
         'formula': 'التغيرات: لا تغيير في A أو Z أو N\nγ = موجة كهرومغناطيسية عالية الطاقة',
         'description': 'موجات كهرومغناطيسية عالية الطاقة — لا تغيّر Z ولا A', 'diagram_type': None},

        # المول والكتلة المولية
        {'course_name': 'كيمياء 1', 'category': 'المول والكتلة المولية', 'title': 'عدد أفوجادرو',
         'latex': r'N_A = 6.02 \times 10^{23}',
         'formula': 'NA = عدد أفوجادرو (بدون وحدة) | الوحدة: جسيم/mol',
         'description': 'عدد الجسيمات في مول واحد من أي مادة', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المول والكتلة المولية', 'title': 'التحويل بين المولات والجسيمات',
         'latex': r'N = n \times 6.02 \times 10^{23}',
         'formula': 'N = عدد الجسيمات | n = عدد المولات (mol)',
         'description': 'الجسيمات تشمل: ذرات، جزيئات، أيونات', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المول والكتلة المولية', 'title': 'التحويل بين المولات والكتلة',
         'latex': r'n = \frac{m}{M}',
         'formula': 'n = عدد المولات (mol) | m = الكتلة (g) | M = الكتلة المولية (g/mol)',
         'description': 'أساس حسابات المول — استخدمه للتحويل بين الجرام والمول', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المول والكتلة المولية', 'title': 'الكتلة المولية للمركب',
         'latex': None, 'formula': 'مجموع كتل جميع العناصر الموجودة في مول واحد من المركب',
         'description': 'تساوي مجموع الكتل الذرية لجميع عناصر المركب مضروبة بمعاملاتها', 'diagram_type': None},

        {'course_name': 'كيمياء 1', 'category': 'المول والكتلة المولية', 'title': 'مثلث المول — قوانين هامة',
         'latex': None, 'formula': None,
         'description': 'مثلث يوضح العلاقة بين عدد الجسيمات والمولات والكتلة والكتلة المولية',
         'diagram_type': 'mole_triangles'},

        # الصيغ الكيميائية
        {'course_name': 'كيمياء 1', 'category': 'الصيغ الكيميائية', 'title': 'أقصى عدد إلكترونات في مستوى طاقة',
         'latex': r'e = 2n^2', 'formula': None,
         'description': 'n = رقم مستوى الطاقة الرئيسي', 'diagram_type': None},

        # ══════════════════════════════════════════════════════
        # كيمياء 2-1
        # ══════════════════════════════════════════════════════

        # الضوء وطاقة الكم
        {'course_name': 'كيمياء 2-1', 'category': 'الضوء وطاقة الكم', 'title': 'سرعة الموجة',
         'latex': r'c = \lambda \cdot \nu',
         'formula': 'c = سرعة الضوء = 3×10⁸ م/ث | λ = الطول الموجي (m) | ν = التردد (Hz)',
         'description': 'c = سرعة الضوء (3×10⁸ م/ث) | λ = الطول الموجي | ν = التردد', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الضوء وطاقة الكم', 'title': 'طاقة الفوتون',
         'latex': r'E = h\nu',
         'formula': 'E = طاقة الفوتون (J) | h = 6.626×10⁻³⁴ J·s | ν = التردد (Hz)',
         'description': 'h = ثابت بلانك = 6.626×10⁻³⁴ جول·ثانية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الضوء وطاقة الكم', 'title': 'العلاقة بين الجسيم والموجة (دي برولي)',
         'latex': r'\lambda = \frac{h}{m \cdot v}',
         'formula': 'λ = طول الموجة (m) | m = الكتلة (kg) | v = السرعة (m/s)',
         'description': 'λ = طول الموجة | m = كتلة الجسيم | v = سرعة الجسيم', 'diagram_type': None},

        # نموذج بور
        {'course_name': 'كيمياء 2-1', 'category': 'نموذج بور', 'title': 'نموذج بور للذرة',
         'latex': None,
         'formula': 'الإلكترونات تدور في مستويات طاقة دائرية محددة حول النواة\nمستوى 1: max 2 إلكترون | مستوى 2: max 8 | مستوى 3: max 18 | مستوى 4: max 32\nالقاعدة: max = 2n²  حيث n رقم المستوى',
         'description': 'امتصاص طاقة: الإلكترون ينتقل لمستوى أعلى | إصدار فوتون: يعود لمستوى أدنى',
         'diagram_type': 'bohr_diagram'},

        {'course_name': 'كيمياء 2-1', 'category': 'نموذج بور', 'title': 'طاقة الانتقال — خطوط الطيف',
         'latex': r'\Delta E = E_{final} - E_{initial} = h\nu',
         'formula': 'ΔE سالب: إصدار فوتون (انتقال لمستوى أدنى)\nΔE موجب: امتصاص فوتون (انتقال لمستوى أعلى)\nسلسلة بالمر: مرئي | سلسلة لايمان: UV | سلسلة باشن: IR',
         'description': 'كل خط في طيف الهيدروجين يقابل انتقال إلكترون بين مستويين', 'diagram_type': None},

        # التوزيع الإلكتروني
        {'course_name': 'كيمياء 2-1', 'category': 'التوزيع الإلكتروني', 'title': 'أكبر عدد للمستويات الفرعية',
         'latex': r'2n^2', 'formula': None,
         'description': 'أكبر عدد إلكترونات في مستوى الطاقة الرئيسي n', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'التوزيع الإلكتروني', 'title': 'مبدأ باولي للاستبعاد',
         'latex': None,
         'formula': 'لا يمكن لإلكترونَين في نفس الذرة أن يتشاركا نفس الأرقام الكمية الأربعة\nالنتيجة: الحد الأقصى لأي مدار = 2 إلكترون (بزخمين دورانيين متعاكسين ↑↓)',
         'description': 'كل مدار يستوعب إلكترونَين بشرط أن يكون دورانهما متعاكساً', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'التوزيع الإلكتروني', 'title': 'قاعدة هوند',
         'latex': None,
         'formula': 'عند ملء مدارات متساوية الطاقة (مثل 2p أو 3d):\n1. يدخل إلكترون واحد في كل مدار أولاً (↑ ↑ ↑)\n2. يكتمل الملء بإلكترون ثانٍ فقط بعد ملء جميع المدارات\nمثال: N (7 e⁻): 1s² 2s² 2p↑ 2p↑ 2p↑\nمثال: O (8 e⁻): 1s² 2s² 2p↑↓ 2p↑ 2p↑',
         'description': 'أقصى استقرار يحدث عند توزيع الإلكترونات بالتساوي قبل الإزدواج', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'التوزيع الإلكتروني', 'title': 'استثناء الكروم',
         'latex': None, 'formula': '₂₄Cr: [Ar] 4s¹ 3d⁵  (وليس 4s² 3d⁴)',
         'description': 'نصف امتلاء 3d أكثر استقراراً — قاعدة استثنائية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'التوزيع الإلكتروني', 'title': 'استثناء النحاس',
         'latex': None, 'formula': '₂₉Cu: [Ar] 4s¹ 3d¹⁰  (وليس 4s² 3d⁹)',
         'description': 'الامتلاء الكامل لـ 3d أكثر استقراراً — قاعدة استثنائية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'التوزيع الإلكتروني', 'title': 'ترتيب ملء المدارات',
         'latex': None, 'formula': '1s، 2s، 2p، 3s، 3p، 4s، 3d، 4p، 5s، 4d، 5p، 6s، 4f، 5d',
         'description': 'قاعدة أوفباو — تُملأ المستويات من الأقل للأعلى طاقة', 'diagram_type': 'orbital_filling'},

        # الجدول الدوري
        {'course_name': 'كيمياء 2-1', 'category': 'الجدول الدوري', 'title': 'تحديد الدورة',
         'latex': None,
         'formula': 'رقم الدورة = رقم مستوى الطاقة الرئيسي الأخير الذي يحوي إلكترونات\nمثال: Na (2,8,1): مستوى 3، الدورة 3\nمثال: Cl (2,8,7): مستوى 3، الدورة 3',
         'description': 'الدورة = أكبر رقم n في التوزيع الإلكتروني', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الجدول الدوري', 'title': 'تحديد المجموعة',
         'latex': None,
         'formula': 'عناصر s و p: المجموعة = عدد إلكترونات التكافؤ (المجموعات 1,2 و 13-18)\nعناصر d (انتقالية): المجموعة = e⁻ التكافؤ في ns + (n-1)d (المجموعات 3-12)\nمثال: Na — توزيع 3s¹ — المجموعة 1\nمثال: Cl — توزيع 3s²3p⁵ — 7 إلكترونات تكافؤ — المجموعة 17\nمثال: Fe — توزيع 4s²3d⁶ — 8 إلكترونات — المجموعة 8',
         'description': 'المجموعة تحدد عدد إلكترونات التكافؤ وخواص العنصر', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الجدول الدوري', 'title': 'تحديد الفئة (Block)',
         'latex': None,
         'formula': 'آخر مدار يُملأ هو s: فئة s (المجموعات 1 و 2)\nآخر مدار يُملأ هو p: فئة p (المجموعات 13-18)\nآخر مدار يُملأ هو d: فئة d (المجموعات 3-12) عناصر انتقالية\nآخر مدار يُملأ هو f: فئة f (لانثانيدات وأكتينيدات)\nمثال: Na — [Ne]3s¹ — فئة s\nمثال: Cl — [Ne]3s²3p⁵ — فئة p\nمثال: Fe — [Ar]4s²3d⁶ — فئة d',
         'description': 'الفئة تُحدَّد بآخر مستوى فرعي يُملأ بالإلكترونات في التوزيع الإلكتروني', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الجدول الدوري', 'title': 'الخواص الدورية — اتجاهات التغير',
         'latex': None, 'formula': None,
         'description': 'مخطط يوضح اتجاه تغير الخواص الدورية عبر الدورة وأسفل المجموعة',
         'diagram_type': 'periodic_trends'},

        # الروابط الكيميائية
        {'course_name': 'كيمياء 2-1', 'category': 'الروابط الكيميائية', 'title': 'فرق الكهروسالبية ونوع الرابطة',
         'latex': None,
         'formula': 'فرق > 1.7: رابطة أيونية\nفرق 0.4-1.7: تساهمية قطبية\nفرق < 0.4: تساهمية غير قطبية\nفرق = 0: تساهمية غير قطبية',
         'description': 'كلما زاد الفرق في الكهروسالبية زادت القطبية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الروابط الكيميائية', 'title': 'أشكال التهجين — رسم بياني',
         'latex': None, 'formula': None,
         'description': 'رسم يوضح الشكل الهندسي لكل نوع تهجين مع زاوية الرابطة ومثال',
         'diagram_type': 'hybridization_shapes'},

        {'course_name': 'كيمياء 2-1', 'category': 'الروابط الكيميائية', 'title': 'صيغة لويس — قواعد الرسم',
         'latex': None,
         'formula': 'الخطوات:\n1. احسب مجموع إلكترونات التكافؤ الكلية\n2. ضع الذرة المركزية وارسم روابط أحادية لكل ذرة محيطة\n3. أكمل ثماني الذرات المحيطة أولاً\n4. ما تبقى: أزواج منفردة على الذرة المركزية\n5. إن احتاجت المركزية أكثر من 8: روابط مزدوجة',
         'description': 'قاعدة الثمانية: كل ذرة تريد 8 إلكترونات (H تريد 2)', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'الروابط الكيميائية', 'title': 'صيغة لويس — أمثلة',
         'latex': None,
         'formula': 'H₂O: إلكترونات التكافؤ = 2(1) + 6 = 8\n   H—Ö—H  (زوجان منفردان على O)\n\nNH₃: إلكترونات التكافؤ = 5 + 3(1) = 8\n   H—N̈—H  (زوج منفرد واحد على N)\n       H\n\nCO₂: إلكترونات التكافؤ = 4 + 2(6) = 16\n   Ö=C=Ö  (رابطتان مزدوجتان، زوجان على كل O)\n\nHCl: إلكترونات التكافؤ = 1 + 7 = 8\n   H—Cl̈:  (3 أزواج منفردة على Cl)',
         'description': 'رمز النقطتين · · = زوج إلكتروني منفرد | الشرطة — = رابطة تساهمية', 'diagram_type': None},

        # الصيغ الكيميائية
        {'course_name': 'كيمياء 2-1', 'category': 'الصيغ الكيميائية', 'title': 'العلاقة بين الصيغة الأولية والجزيئية',
         'latex': None, 'formula': 'الصيغة الجزيئية = n × الصيغة الأولية',
         'description': 'n = الكتلة المولية التجريبية ÷ الكتلة المولية للصيغة الأولية', 'diagram_type': None},

        # قوانين الغازات
        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون بويل',
         'latex': r'P_1 V_1 = P_2 V_2',
         'formula': 'P = الضغط (atm أو Pa) | V = الحجم (L) | T ثابت',
         'description': 'الضغط يتناسب عكسياً مع الحجم عند ثبوت درجة الحرارة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون شارل',
         'latex': r'\frac{V_1}{T_1} = \frac{V_2}{T_2}',
         'formula': 'V = الحجم (L) | T = درجة الحرارة (K) | P ثابت',
         'description': 'الحجم يتناسب طردياً مع درجة الحرارة المطلقة عند ثبوت الضغط', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون جاي-لوساك',
         'latex': r'\frac{P_1}{T_1} = \frac{P_2}{T_2}',
         'formula': 'P = الضغط (atm) | T = درجة الحرارة (K) | V ثابت',
         'description': 'الضغط يتناسب طردياً مع درجة الحرارة المطلقة عند ثبوت الحجم', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'القانون العام للغازات',
         'latex': r'\frac{P_1 V_1}{T_1} = \frac{P_2 V_2}{T_2}', 'formula': None,
         'description': 'يجمع قوانين بويل وشارل وجاي-لوساك', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون الغاز المثالي',
         'latex': r'PV = nRT',
         'formula': 'P = الضغط (atm) | V = الحجم (L) | n = المولات (mol)\nR = 0.0821 L·atm/mol·K | T = درجة الحرارة (K)',
         'description': 'P = الضغط | V = الحجم | n = المولات | R = ثابت الغاز | T = الحرارة (كلفن)', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون أفوجادرو',
         'latex': r'\frac{V_1}{V_2} = \frac{n_1}{n_2}',
         'formula': 'V = الحجم (L) | n = عدد المولات (mol) | عند نفس P وT',
         'description': 'عند نفس الضغط والحرارة: الحجم يتناسب طردياً مع عدد المولات', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون دالتون للضغوط الجزئية',
         'latex': r'P_{total} = P_1 + P_2 + P_3 + \ldots',
         'formula': 'P_total = الضغط الكلي (atm) | P₁, P₂... = الضغوط الجزئية لكل غاز',
         'description': 'الضغط الكلي لخليط غازات = مجموع الضغوط الجزئية لكل غاز', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'كثافة الغاز',
         'latex': r'D = \frac{M \cdot P}{R \cdot T}',
         'formula': 'D = الكثافة (g/L) | M = الكتلة المولية (g/mol) | P (atm) | T (K)',
         'description': 'كثافة الغاز تتناسب طردياً مع كتلته المولية وضغطه', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'قانون جراهام للانتشار',
         'latex': r'\frac{r_A}{r_B} = \sqrt{\frac{M_B}{M_A}}',
         'formula': 'r = معدل الانتشار | M = الكتلة المولية (g/mol)\nالغاز الأخف ينتشر أسرع',
         'description': 'معدل انتشار الغاز يتناسب عكسياً مع الجذر التربيعي لكتلته المولية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-1', 'category': 'قوانين الغازات', 'title': 'الظروف المعيارية STP',
         'latex': None, 'formula': 'T = 0°C (273 K) | P = 1 atm\nحجم مول أي غاز عند STP = 22.4 L',
         'description': 'Standard Temperature and Pressure — مرجع لحسابات الغازات', 'diagram_type': None},

        # ══════════════════════════════════════════════════════
        # كيمياء 2-2
        # ══════════════════════════════════════════════════════

        # المحاليل
        {'course_name': 'كيمياء 2-2', 'category': 'المحاليل', 'title': 'المولالية',
         'latex': r'm = \frac{n_{solute}}{m_{solvent}(kg)}',
         'formula': 'n = مولات المذاب (mol) | m = كتلة المذيب (kg)',
         'description': 'عدد مولات المذاب في كيلوجرام من المذيب', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'المحاليل', 'title': 'الكسر المولي',
         'latex': r'X_A = \frac{n_A}{n_A + n_B}',
         'formula': 'X = الكسر المولي (بدون وحدة، من 0 إلى 1) | nA, nB = مولات كل مكوّن',
         'description': 'نسبة مولات المذاب أو المذيب إلى المولات الكلية في المحلول', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'المحاليل', 'title': 'النسبة المئوية بالكتلة',
         'latex': r'\% = \frac{m_{solute}}{m_{solution}} \times 100',
         'formula': 'm_solute = كتلة المذاب (g) | m_solution = كتلة المحلول (g)',
         'description': 'كتلة المحلول = كتلة المذاب + كتلة المذيب', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'المحاليل', 'title': 'النسبة المئوية بالحجم',
         'latex': r'\% = \frac{V_{solute}}{V_{solution}} \times 100',
         'formula': 'V_solute = حجم المذاب (mL) | V_solution = حجم المحلول (mL)',
         'description': 'تُستخدم عندما يكون المذاب سائلاً', 'diagram_type': None},

        # الخواص الجامعة
        {'course_name': 'كيمياء 2-2', 'category': 'الخواص الجامعة', 'title': 'الارتفاع في درجة الغليان',
         'latex': r'\Delta T_b = K_b \cdot m',
         'formula': 'ΔTb = الارتفاع (°C) | Kb = ثابت الغليان (°C·kg/mol) | m = المولالية (mol/kg)',
         'description': 'Kb = ثابت ارتفاع الغليان | m = المولالية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الخواص الجامعة', 'title': 'الانخفاض في درجة التجمد',
         'latex': r'\Delta T_f = K_f \cdot m',
         'formula': 'ΔTf = الانخفاض (°C) | Kf = ثابت التجمد (°C·kg/mol) | m = المولالية (mol/kg)',
         'description': 'Kf = ثابت الانخفاض في التجمد | m = المولالية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الخواص الجامعة', 'title': 'قانون هنري',
         'latex': r'\frac{S_1}{P_1} = \frac{S_2}{P_2}', 'formula': None,
         'description': 'S = الذائبية | P = الضغط — ذائبية الغاز تتناسب طردياً مع ضغطه', 'diagram_type': None},

        # الحسابات الكيميائية
        {'course_name': 'كيمياء 2-2', 'category': 'الحسابات الكيميائية', 'title': 'النسبة المولية',
         'latex': None, 'formula': 'النسبة بين أعداد مولات أي مادتين في المعادلة الكيميائية الموزونة',
         'description': 'أساس كل حسابات الكيمياء الكمية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الحسابات الكيميائية', 'title': 'المادة الفائضة والمادة المحددة',
         'latex': None,
         'formula': 'المادة المحددة: تنتهي أولاً وتوقف التفاعل\nالكمية الفائضة = كتلة المادة - الكمية التي تفاعلت',
         'description': 'المادة المحددة تحدد كمية الناتج', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الحسابات الكيميائية', 'title': 'نسبة المردود المئوية',
         'latex': None,
         'formula': 'نسبة المردود = (المردود الفعلي ÷ المردود النظري) × 100\nالوحدة: % | المردود بالجرام أو المول',
         'description': 'المردود الفعلي: ما نحصل عليه تجريبياً | المردود النظري: ما يمكن الحصول عليه نظرياً', 'diagram_type': None},

        # حركية التفاعلات
        {'course_name': 'كيمياء 2-2', 'category': 'حركية التفاعلات', 'title': 'معدل متوسط سرعة التفاعل',
         'latex': r'\text{Rate} = -\frac{\Delta[\text{reactants}]}{\Delta t}', 'formula': None,
         'description': 'السالب لأن تركيز المتفاعلات يقل مع الزمن', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'حركية التفاعلات', 'title': 'القانون العام لسرعة التفاعل',
         'latex': r'\text{Rate} = K[A]^m[B]^n', 'formula': None,
         'description': 'K = ثابت سرعة التفاعل | m,n = رتبة التفاعل | [A],[B] = تركيز المتفاعلات', 'diagram_type': None},

        # الكيمياء الحرارية
        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء الحرارية', 'title': 'الحرارة النوعية',
         'latex': r'Q = m \cdot c \cdot \Delta T',
         'formula': 'Q = الحرارة (J) | m = الكتلة (g) | c = الحرارة النوعية (J/g·°C) | ΔT = T_نهائي - T_ابتدائي (°C)',
         'description': 'Q = الحرارة (جول) | m = الكتلة | c = الحرارة النوعية | ΔT = تغير درجة الحرارة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء الحرارية', 'title': 'المحتوى الحراري للتفاعل',
         'latex': r'\Delta H_{rxn} = H_{products} - H_{reactants}',
         'formula': 'ΔH سالب (−): تفاعل طارد للحرارة | ΔH موجب (+): تفاعل ماص للحرارة\nالوحدة: kJ/mol',
         'description': 'ΔH سالب: تفاعل طارد للحرارة\nΔH موجب: تفاعل ماص للحرارة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء الحرارية', 'title': 'مخطط الحالة الفيزيائية',
         'latex': None,
         'formula': 'ثلاثة مناطق: صلب، سائل، غاز\nنقطة التحول الثلاثي: تتعايش الحالات الثلاث معاً\nنقطة الحرجة: فوقها لا يمكن تمييز السائل عن الغاز',
         'description': 'يوضح حالة المادة عند كل ضغط ودرجة حرارة', 'diagram_type': 'phase_diagram'},

        # الكيمياء العضوية
        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'الألكانات — الصيغة العامة',
         'latex': r'C_nH_{2n+2}',
         'formula': 'روابط أحادية فقط | مثال: CH₄ ميثان، C₃H₈ بروبان',
         'description': 'هيدروكربونات مشبعة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'الألكينات — الصيغة العامة',
         'latex': r'C_nH_{2n}',
         'formula': 'رابطة ثنائية واحدة على الأقل | مثال: C₂H₄ إيثين',
         'description': 'هيدروكربونات غير مشبعة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'الألكاينات — الصيغة العامة',
         'latex': r'C_nH_{2n-2}',
         'formula': 'رابطة ثلاثية واحدة على الأقل | مثال: C₂H₂ إيثاين',
         'description': 'هيدروكربونات غير مشبعة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'تفاعلات الإضافة',
         'latex': None,
         'formula': 'تحدث مع المركبات غير المشبعة (ألكين/ألكاين)\nالهيدرة: C=C + H₂O → كحول  (في وجود H⁺)\nالهلجنة: C=C + Cl₂ → ثنائي الهاليد\nالهيدروجنة: C=C + H₂ → ألكان  (في وجود Ni)\nقاعدة ماركوفنيكوف: H يضاف لذرة C الأكثر هيدروجيناً',
         'description': 'تفاعل الإضافة: يكسر الرابطة المتعددة ويضيف ذرات عليها', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'تفاعلات الاستبدال',
         'latex': None,
         'formula': 'تحدث مع الألكانات والبنزين\nهلجنة الألكانات: R-H + Cl₂ → R-Cl + HCl  (في وجود ضوء UV)\nهلجنة البنزين: C₆H₆ + Cl₂ → C₆H₅Cl + HCl  (في وجود FeCl₃)\nالنترة: C₆H₆ + HNO₃ → C₆H₅NO₂ + H₂O',
         'description': 'تفاعل الاستبدال: تحل مجموعة محل H أو مجموعة أخرى دون كسر الحلقة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'تفاعلات الحذف (الإزالة)',
         'latex': None,
         'formula': 'الجفاف (dehydration): الكحول → ألكين + H₂O  (H₂SO₄ مركز + حرارة)\nمثال: CH₃CH₂OH → CH₂=CH₂ + H₂O\nالهيدروهلجنة: هاليد ألكيل + KOH(كحولي) → ألكين + HX + KX\nقاعدة زايتسف: يُحذف H من الكربون الأقل هيدروجيناً (ناتج الألكين أكثر استقراراً)',
         'description': 'تفاعل الحذف: تنتج رابطة مزدوجة بعد إزالة ذرتين من الجزيء', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'البادئات العددية للتسمية IUPAC',
         'latex': None,
         'formula': '1 ذرة C: ميث (Meth)\n2 ذرات C: إيث (Eth)\n3 ذرات C: بروب (Prop)\n4 ذرات C: بيوت (But)\n5 ذرات C: بنت (Pent)\n6 ذرات C: هكس (Hex)\n7 ذرات C: هبت (Hept)\n8 ذرات C: أوكت (Oct)\n9 ذرات C: نون (Non)\n10 ذرات C: دك (Dec)',
         'description': 'البادئة تدل على عدد ذرات الكربون في السلسلة الرئيسية', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'تسمية الألكانات (IUPAC)',
         'latex': None,
         'formula': 'البادئة العددية + ان (مثال: بروبان، بيوتان)\n\nخطوات التسمية:\n1. ابحث عن أطول سلسلة كربونية متصلة (هي السلسلة الرئيسية)\n2. رقّم السلسلة من الطرف الأقرب للتفرع\n3. سمّ التفرعات بنفس البادئات + يل (مثيل، إيثيل...)\n4. إذا تكرر التفرع: ثنائي (di)، ثلاثي (tri)، رباعي (tetra)\n5. الترتيب: الأصغر رقماً أولاً، وأبجدياً عند التساوي\n\nمثال: CH₃-CH(CH₃)-CH₂-CH₃\nالاسم: 2-ميثيل بيوتان',
         'description': 'قاعدة IUPAC لتسمية الألكانات والمواد العضوية المتفرعة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'تسمية الألكينات والألكاينات',
         'latex': None,
         'formula': 'الألكينات: البادئة + ين (مثال: بروبين، بيوتين)\nالألكاينات: البادئة + اين (مثال: إيثاين، بروباين)\n\nخطوات التسمية:\n1. أطول سلسلة تحوي الرابطة المتعددة\n2. رقّم من الطرف الأقرب للرابطة\n3. حدد موضع الرابطة برقم أصغر كربون فيها\n\nمثال: CH₂=CH-CH₃ — بروب-1-ين\nمثال: CH≡C-CH₃ — بروب-1-اين',
         'description': 'الرقم الذي يسبق ين/اين يدل على موضع الرابطة المتعددة في السلسلة', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'تسمية المركبات ذات المجموعات الوظيفية',
         'latex': None,
         'formula': 'الكحولات: البادئة + ول (مثال: إيثانول)\nالأحماض الكربوكسيلية: البادئة + أنويك + حمض (مثال: حمض إيثانويك)\nالإسترات: اسم الكحول (يل) + اسم الحمض (وات) (مثال: إيثيل إيثانوات)\nالأمينات: البادئة + أمين (مثال: إيثيل أمين)\nالألدهيدات: البادئة + انال (مثال: إيثانال)\nالكيتونات: البادئة + انون (مثال: بروبانون)',
         'description': 'اللاحقة تدل على المجموعة الوظيفية — ال + المجموعة الرئيسية أولى في الترتيب', 'diagram_type': None},

        {'course_name': 'كيمياء 2-2', 'category': 'الكيمياء العضوية', 'title': 'المجموعات الوظيفية الأساسية',
         'latex': None,
         'formula': '-OH: كحول\n-O-: إيثر\n-NH₂: أمين\n-CHO: ألدهيد\n-CO-: كيتون\n-COOH: حمض كربوكسيلي\n-COO-: إستر\n-X (F,Cl,Br,I): هاليد الألكيل',
         'description': 'المجموعة الوظيفية تحدد خواص المركب العضوي', 'diagram_type': None},

        # ══════════════════════════════════════════════════════
        # كيمياء 3
        # ══════════════════════════════════════════════════════

        # المحاليل
        {'course_name': 'كيمياء 3', 'category': 'المحاليل', 'title': 'المولارية',
         'latex': r'M = \frac{n}{V}',
         'formula': 'M = المولارية (mol/L) | n = عدد المولات (mol) | V = الحجم (L)',
         'description': 'تركيز المحلول بالمول لكل لتر', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'المحاليل', 'title': 'معادلة تخفيف المحاليل',
         'latex': r'M_1 V_1 = M_2 V_2',
         'formula': 'M = المولارية (mol/L) | V = الحجم (L أو mL)\n1 = قبل التخفيف | 2 = بعد التخفيف',
         'description': 'M = المولارية | V = الحجم | 1 = قبل التخفيف | 2 = بعد التخفيف', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'المحاليل', 'title': 'حجم الماء المضاف للتخفيف',
         'latex': r'\Delta V = V_2 - V_1',
         'formula': 'ΔV = الماء المضاف (L أو mL) | V2 = الحجم النهائي | V1 = الحجم الابتدائي',
         'description': 'حجم الماء الذي يجب إضافته للتخفيف', 'diagram_type': None},

        # الأكسدة والاختزال
        {'course_name': 'كيمياء 3', 'category': 'الأكسدة والاختزال', 'title': 'تعريفات أساسية',
         'latex': None,
         'formula': 'الأكسدة: فقدان إلكترونات — عدد التأكسد يرتفع\nالاختزال: اكتساب إلكترونات — عدد التأكسد ينخفض\nالمؤكسِد: يكتسب الإلكترونات (يُختزَل هو نفسه)\nالمختزِل: يفقد الإلكترونات (يُؤكسَد هو نفسه)\nمفتاح: OIL RIG — Oxidation Is Loss / Reduction Is Gain',
         'description': 'تفاعلات الأكسدة والاختزال تحدث دائماً معاً — لا يمكن أن تحدث الواحدة دون الأخرى', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأكسدة والاختزال', 'title': 'موازنة معادلات الأكسدة والاختزال — طريقة النصف تفاعل',
         'latex': None,
         'formula': 'الخطوات:\n1. اكتب نصفَي التفاعل (أكسدة واختزال) منفصلَين\n2. وازن الذرات غير الأكسجين والهيدروجين\n3. وازن O بإضافة H₂O | وازن H بإضافة H⁺\n4. وازن الشحنة بإضافة إلكترونات (e⁻)\n5. اضرب النصفين لتساوي عدد الإلكترونات\n6. اجمع النصفَين وحذف المتشابهات\n(في الوسط القاعدي: أضف OH⁻ لكل H⁺ في النهاية)',
         'description': 'طريقة النصف تفاعل أدق وأوضح من طريقة عدد التأكسد لتوازن معادلات الردوكس', 'diagram_type': None},

        # الاتزان الكيميائي
        {'course_name': 'كيمياء 3', 'category': 'الاتزان الكيميائي', 'title': 'ثابت الاتزان',
         'latex': r'K_{eq} = \frac{[C]^c[D]^d}{[A]^a[B]^b}', 'formula': None,
         'description': 'للتفاعل: aA + bB ⇌ cC + dD\nالمواد الصلبة والسائلة لا تُكتب في تعبير الاتزان', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الاتزان الكيميائي', 'title': 'تفسير قيمة Keq',
         'latex': None,
         'formula': 'Keq كبير: النواتج مفضّلة\nKeq صغير: المتفاعلات مفضّلة\nKeq = 1: توازن تقريبي',
         'description': 'قيمة ثابت الاتزان تدل على اتجاه التفاعل', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الاتزان الكيميائي', 'title': 'مبدأ لوشاتيلييه',
         'latex': None,
         'formula': 'إذا أُحدث تغيير في نظام متزن: ينزاح الاتزان لتعويض التغيير\n\nزيادة تركيز متفاعل: اتزان ينزاح لليمين (ناحية النواتج)\nزيادة تركيز ناتج: اتزان ينزاح لليسار (ناحية المتفاعلات)\nرفع الضغط (غازات): ينزاح نحو الجهة الأقل عدداً من مولات الغاز\nرفع درجة الحرارة: ينزاح نحو التفاعل الماص للحرارة (ΔH+)\nخفض درجة الحرارة: ينزاح نحو التفاعل الطارد للحرارة (ΔH−)\nالمحفز: لا يغير موضع الاتزان، فقط يُسرّع الوصول إليه',
         'description': 'يُستخدم لتحديد اتجاه انزياح الاتزان عند تغيير أي عامل', 'diagram_type': None},

        # الذائبية
        {'course_name': 'كيمياء 3', 'category': 'الذائبية', 'title': 'ثابت حاصل الذوبانية',
         'latex': r'K_{sp} = [M^{m+}]^x[A^{n-}]^y', 'formula': None,
         'description': 'حاصل ضرب تراكيز الأيونات كل منها مرفوعاً لأس معاملها في المعادلة', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الذائبية', 'title': 'مثال: Ksp لـ Mg(OH)₂',
         'latex': r'K_{sp} = [Mg^{2+}][OH^-]^2',
         'formula': 'Mg(OH)₂(s) ⇌ Mg²⁺(aq) + 2OH⁻(aq)',
         'description': 'الأس 2 لأن معامل OH⁻ في المعادلة هو 2', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الذائبية', 'title': 'تأثير الأيون المشترك',
         'latex': None,
         'formula': 'إضافة أيون مشترك مع الراسب: تقل الذائبية (Ksp لا يتغير)\n\nمثال: AgCl يذوب في الماء → Ag⁺ + Cl⁻\nإضافة NaCl: يزيد Cl⁻، ينزاح الاتزان يساراً، يترسب AgCl أكثر\n\nالقاعدة: الذائبية = √(Ksp ÷ الأيون المشترك²)',
         'description': 'الأيون المشترك يقلل ذائبية الأملاح القليلة الذوبان — تطبيق مباشر لمبدأ لوشاتيلييه', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الذائبية', 'title': 'الحاصل الأيوني Qsp',
         'latex': None,
         'formula': 'Qsp < Ksp: المحلول غير مشبع، لا يتكون راسب\nQsp = Ksp: مشبع، لا تغير\nQsp > Ksp: يتكون راسب',
         'description': 'يُستخدم للتنبؤ بتكوين الراسب', 'diagram_type': None},

        # الأحماض والقواعد
        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'ثابت تأين الماء',
         'latex': r'K_W = [H^+][OH^-] = 1.0 \times 10^{-14}',
         'formula': 'Kw = ثابت تأين الماء (mol²/L²) | التراكيز بوحدة mol/L',
         'description': 'عند 25°C لأي محلول مائي', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'الرقم الهيدروجيني pH',
         'latex': r'pH = -\log[H^+] \quad \Leftrightarrow \quad [H^+] = 10^{-pH}', 'formula': None,
         'description': 'pH < 7 حمضي | pH = 7 متعادل | pH > 7 قاعدي', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'الرقم الهيدروكسيدي pOH',
         'latex': r'pOH = -\log[OH^-] \quad \Leftrightarrow \quad [OH^-] = 10^{-pOH}', 'formula': None,
         'description': 'العلاقة بين pH و pOH', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'العلاقة بين pH و pOH',
         'latex': r'pH + pOH = 14', 'formula': None,
         'description': 'صحيحة لأي محلول مائي عند 25°C', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'تركيز H⁺ في الأحماض القوية',
         'latex': r'[H^+] = M_a \times n_H',
         'formula': 'Mₐ = مولارية الحمض (mol/L) | nH = عدد ذرات H في الجزيء',
         'description': 'الأحماض القوية تتأين كلياً', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'تركيز OH⁻ في القواعد القوية',
         'latex': r'[OH^-] = M_b \times n_{OH}',
         'formula': 'Mᵦ = مولارية القاعدة (mol/L) | nOH = عدد مجموعات OH في الجزيء',
         'description': 'القواعد القوية تتأين كلياً', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الأحماض والقواعد', 'title': 'التعادل',
         'latex': r'M_A \cdot V_A = M_B \cdot V_B', 'formula': None,
         'description': 'نقطة التكافؤ: مولات H⁺ = مولات OH⁻', 'diagram_type': None},

        # عدد التأكسد
        {'course_name': 'كيمياء 3', 'category': 'عدد التأكسد', 'title': 'قواعد تحديد عدد التأكسد',
         'latex': None,
         'formula': '• العناصر الحرة H₂، O₂، Cl₂: صفر\n• أيون أحادي: يساوي شحنته\n• الأكسجين في المركبات: −2 (إلا H₂O₂: −1)\n• الهيدروجين في المركبات: +1 (إلا الهيدريدات: −1)\n• مجموع أعداد التأكسد في مركب متعادل = صفر\n• مجموع أعداد التأكسد في أيون متعدد الذرات = شحنته',
         'description': 'قواعد أساسية لتحديد أعداد التأكسد — تُستخدم في تفاعلات الأكسدة والاختزال', 'diagram_type': None},

        # الكيمياء الكهربائية
        {'course_name': 'كيمياء 3', 'category': 'الكيمياء الكهربائية', 'title': 'خلية جلفانية (فولتية)',
         'latex': None,
         'formula': 'تحوّل التفاعل الكيميائي التلقائي إلى طاقة كهربائية\n\nالأنود (−): يحدث فيه تفاعل الأكسدة (فقدان e⁻)\nالكاثود (+): يحدث فيه تفاعل الاختزال (اكتساب e⁻)\nالإلكترونات تتدفق: من الأنود إلى الكاثود في الدائرة الخارجية\nجسر الملح: يوازن الشحنات بين محلولَي الخليتَين',
         'description': 'الخلية الجلفانية: التفاعل تلقائي (ΔG سالب) | خلية التحليل الكهربائي: التفاعل غير تلقائي', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الكيمياء الكهربائية', 'title': 'جهد الخلية القياسي E°',
         'latex': r'E^{\circ}_{cell} = E^{\circ}_{cathode} - E^{\circ}_{anode}',
         'formula': 'E°_cell > 0: تفاعل تلقائي (خلية جلفانية)\nE°_cell < 0: تفاعل غير تلقائي (يحتاج طاقة خارجية)\nE° (كاثود) أكبر: هو الطرف الموجب\nجدول جهود الاختزال: الأكبر يُختزَل (كاثود) والأصغر يُؤكسَد (أنود)',
         'description': 'E° يُقاس بالفولت (V) | القيم من جدول جهود الاختزال القياسية', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الكيمياء الكهربائية', 'title': 'التحليل الكهربائي — قانون فاراداي',
         'latex': r'm = \frac{M \cdot I \cdot t}{n \cdot F}',
         'formula': 'm = الكتلة المترسبة (g) | M = الكتلة المولية (g/mol)\nI = شدة التيار (أمبير) | t = الزمن (ثانية)\nn = عدد الإلكترونات المنقولة | F = 96500 C/mol (ثابت فاراداي)',
         'description': 'قانون فاراداي: كتلة المادة المترسبة تتناسب مع كمية الكهرباء المارة', 'diagram_type': None},

        # الكيمياء الحيوية
        {'course_name': 'كيمياء 3', 'category': 'الكيمياء الحيوية', 'title': 'البروتينات والأحماض الأمينية',
         'latex': None,
         'formula': 'الأحماض الأمينية: وحدة بناء البروتين\nالتركيب العام: NH₂-CH(R)-COOH\n   NH₂ = مجموعة أمينية | COOH = مجموعة كربوكسيلية | R = سلسلة جانبية\n\nالرابطة الببتيدية: تربط حمضَين أمينيَّين بفقدان H₂O\n   -CO-NH- هي الرابطة الببتيدية\n\nالبروتين الأولي: تسلسل الأحماض الأمينية\nالبروتين الثانوي: حلزون α أو ورقة β\nالبروتين الثالثي: الشكل ثلاثي الأبعاد الكلي',
         'description': '20 حمضاً أمينياً أساسياً في الطبيعة — R تحدد خصائص كل حمض أميني', 'diagram_type': None},

        {'course_name': 'كيمياء 3', 'category': 'الكيمياء الحيوية', 'title': 'أقسام السكريات',
         'latex': None,
         'formula': 'السكريات الأحادية: 5 أو 6 كربون | مثال: جلكوز، فركتوز\nالسكريات الثنائية: سكران أحاديان | مثال: سكروز، لاكتوز\nالسكريات المتعددة: 12 وحدة بناء أساسية فأكثر | مثال: نشا، سليلوز',
         'description': 'تصنيف السكريات حسب عدد وحدات البناء', 'diagram_type': None},
    ]
