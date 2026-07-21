"""
دالة مشتركة لترتيب/خلط نموذج اختبار واحد (أ/ب/ج/د) — تُستخدم من api.py
(توليد ملف PDF الاختبار الفعلي) ومن question.py (توليد مفتاح ريمارك/OMR)
بنفس المدخلات بالضبط (نفس question_ids + matching_pair_ids + رقم النموذج)،
عشان الاثنين يطلعوا بنفس ترتيب الأسئلة/الخيارات/عمود المزاوجة لنفس النموذج.

قبل هذا الملف، كل مسار كان يعيد تنفيذ خلطه الخاص بصيغة seed مختلفة وخوارزمية
مختلفة (خلط القائمة كاملة مرة وحدة بمسار PDF، مقابل 3 خلطات منفصلة لكل نوع
لحاله بمسار الريمارك) — فيؤدي لاختلاف الإجابة الصحيحة المطبوعة عن مفتاح
التصحيح لنفس النموذج، وهو باغ تصحيح حقيقي (درجات الطلاب تُحتسب غلط).

هذا الملف هو المرجع الوحيد لخوارزمية الترتيب/الخلط — أي تعديل عليها لازم
ينعكس هنا فقط، ويُستدعى من الطرفين بدل إعادة كتابته.
"""
import random
from types import SimpleNamespace

EXAM_SUPPORTED_TYPES = ['mcq', 'true_false', 'fill_blank', 'matching', 'essay']
MATCHING_LETTERS = ['أ', 'ب', 'ج', 'د', 'هـ', 'و', 'ز', 'ح', 'ط', 'ي']


def group_by_type_order(qs):
    """تجميع نهائي حسب النوع بترتيب ثابت — تقسيم مستقر (stable) يحافظ على
    الترتيب الداخلي لكل نوع كما هو (لا يعيد خلطه)."""
    return [q for t in EXAM_SUPPORTED_TYPES for q in qs if q.question_type == t]


def build_pooled_matching_fq(selected_pairs, distractor):
    """يبني سؤال مزاوجة اصطناعي واحد موحّد من قائمة أزواج مُختارة بالضبط."""
    from src.routes.api import format_image_url
    return SimpleNamespace(**{
        'question_id': -1,
        'question_text': 'اربط العمود (أ) بما يناسبه من العمود (ب):',
        'image_url': None,
        'options': [],
        'correct_option_id': None,
        'explanation': None,
        'explanation_image_path': None,
        'lesson': None, 'unit': None, 'course': None,
        'difficulty': 'medium', 'bloom_level': 'remember',
        'video_url': None, 'r2_video_url': None, 'video_explanation': None, 'video_status': 'none',
        'is_blocked': False,
        'question_type': 'matching',
        'matching_pairs': [
            {
                'left_text': p.left_text,
                'left_image_url': format_image_url(p.left_image_url),
                'right_text': p.right_text,
                'right_image_url': format_image_url(p.right_image_url),
            }
            for p in selected_pairs
        ],
        'matching_pair_ids': [p.pair_id for p in selected_pairs],
        'matching_distractor': (
            {'text': distractor.right_text, 'image_url': format_image_url(distractor.right_image_url)}
            if distractor else None
        ),
        'fill_blank_answer': None,
        'fill_blank_alt_answers': [],
        'essay_model_answer': None,
        '_pooled_matching': True,
    })


def build_manual_matching_fq(pair_ids, rng=None):
    """سؤال مزاوجة اصطناعي من أزواج مُختارة بالضبط (pair_ids) — نفس منطق
    api.py's _build_manual_matching_fq بالحرف، يُستخدم من الطرفين."""
    from src.models.question import Question, MatchingPair
    from src.extensions import db

    chooser = rng.choice if rng else random.choice
    all_pairs = MatchingPair.query.filter(MatchingPair.pair_id.in_(pair_ids)).all()
    if not all_pairs:
        return None
    order = {pid: i for i, pid in enumerate(pair_ids)}
    selected_pairs = sorted(all_pairs, key=lambda p: order.get(p.pair_id, 0))

    lesson_ids = {p.question.lesson_id for p in selected_pairs if p.question}
    distractor = None
    if lesson_ids:
        distractor = (
            MatchingPair.query
            .join(Question, MatchingPair.question_id == Question.question_id)
            .filter(Question.lesson_id.in_(lesson_ids))
            .filter(Question.question_type == 'matching')
            .filter(~MatchingPair.pair_id.in_(pair_ids))
            .order_by(db.func.random())
            .first()
        )
    return build_pooled_matching_fq(selected_pairs, distractor)


def format_selected(qs_list, rng=None, shuffle_options=True, include_answers=False):
    """نفس منطق api.py's format_selected بالحرف — لكن rng.shuffle بدل
    random.shuffle العامة غير المُبذّرة، عشان يصير الناتج قابل لإعادة الإنتاج
    بنفس الـseed من أي مكان يستدعيها."""
    from src.routes.api import format_question
    shuffler = rng.shuffle if rng is not None else random.shuffle
    formatted = []
    for q in qs_list:
        if getattr(q, '_pooled_matching', False):
            fq = dict(vars(q))
            fq.pop('_pooled_matching', None)
        else:
            fq = format_question(q)
        if shuffle_options and fq.get('options'):
            opts = list(fq['options'])
            shuffler(opts)
            fq['options'] = opts
        if not include_answers:
            fq.pop('correct_option_id', None)

        if fq.get('question_type') == 'matching' and fq.get('matching_pairs'):
            pairs = fq['matching_pairs']
            right_items = [
                {'text': p['right_text'], 'image_url': p['right_image_url']}
                for p in pairs
            ]
            if fq.get('matching_distractor'):
                right_items.append(fq['matching_distractor'])
            order = list(range(len(right_items)))
            shuffler(order)
            shuffled_right = []
            correct_letter_by_index = {}
            for pos, orig_idx in enumerate(order):
                letter = MATCHING_LETTERS[pos] if pos < len(MATCHING_LETTERS) else str(pos + 1)
                item = right_items[orig_idx]
                shuffled_right.append({'letter': letter, 'text': item['text'], 'image_url': item['image_url']})
                if orig_idx < len(pairs):
                    correct_letter_by_index[orig_idx] = letter
            fq['matching_right_shuffled'] = shuffled_right
            for i, p in enumerate(pairs):
                p['correct_letter'] = correct_letter_by_index.get(i, '') if include_answers else ''

        formatted.append(fq)
    return formatted


def compute_stable_seed(question_ids, matching_pair_ids=None):
    """صيغة الـseed الموحّدة — لازم تُستخدم بنفس الشكل بمسار PDF ومسار الريمارك.
    ترجع None لو ما فيه أي معرّفات (يعني وضع تلقائي بدون قفل أسئلة — لا حاجة
    لإعادة إنتاج، ما فيه طلب ريمارك لاحق مرتبط أصلاً بهذا التوليد)."""
    question_ids = question_ids or []
    matching_pair_ids = matching_pair_ids or []
    if not question_ids and not matching_pair_ids:
        return None
    return sum(question_ids) + sum(matching_pair_ids)


def format_exam_number(stable_seed):
    """رقم نموذج قصير قابل للقراءة، مشتق من نفس بذرة الأسئلة المشتركة —
    يطلع متطابق حرفياً بين ورقة الاختبار ومفتاح الريمارك لنفس التوليد،
    بدون أي تنسيق إضافي بين مسار PDF ومسار الريمارك (نفس مبدأ compute_stable_seed).
    يرجع '' لو ما فيه seed (وضع تلقائي بدون قفل أسئلة)."""
    if stable_seed is None:
        return ''
    return str(abs(stable_seed) % 1_000_000).zfill(6)


def build_exam_model(available, model_index, stable_seed,
                      shuffle_options=True, include_answers=False):
    """
    available: قائمة كائنات الأسئلة النهائية (ORM Question، أو كائن مزاوجة
               مُجمَّع عبر build_manual_matching_fq) بترتيب الإدخال (عادة نفس
               ترتيب question_ids كما أرسله العميل بوضع manual).
    model_index: رقم النموذج (0 لـ"أ"، 1 لـ"ب"، 2 لـ"ج"، 3 لـ"د").
    stable_seed: من compute_stable_seed(question_ids, matching_pair_ids) —
                 يجب حسابها بنفس القيم بالضبط بمسار PDF ومسار الريمارك.

    يرجّع القائمة النهائية المُنسّقة/المُرتّبة (نفس تنسيق format_selected) —
    استدعاؤها من مسارين مختلفين بنفس المدخلات يضمن نفس الترتيب حرفياً.
    """
    # ملاحظة حرجة: ما نستدعي group_by_type_order هنا — api.py بوضع manual
    # (اللي يمثّله هذا الاستدعاء دائماً: أسئلة مُقفلة بمعرّفات محددة) يتجاوز
    # هذا التجميع تماماً (`if mode != "manual": selected = group_by_type_order(...)`)،
    # فيبقى الترتيب المُختلط (بعد الخلط مباشرة) هو اللي يُمرَّر لـformat_selected.
    # لو جمّعنا حسب النوع هنا قبل format_selected، كل سؤال ياخذ فرصته من rng
    # بترتيب مختلف عن ورقة الاختبار الفعلية، فيختلف ترتيب خيارات كل سؤال رغم
    # تطابق الـseed (rng.shuffle يستهلك التدفق العشوائي حسب ترتيب العناصر
    # بالضبط وقت النداء). قسم الأنواع بمفتاح الريمارك يصير لاحقاً بعد
    # format_selected (فلترة تحافظ على الترتيب، بدون التأثير على استهلاك rng).
    rng = random.Random(stable_seed + model_index * 31337) if stable_seed is not None else None
    selected = list(available)
    if rng is not None:
        rng.shuffle(selected)
    return format_selected(selected, rng=rng, shuffle_options=shuffle_options, include_answers=include_answers)
