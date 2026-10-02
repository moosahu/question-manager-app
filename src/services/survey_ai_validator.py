"""
مولّد الاستبيان بالذكاء الاصطناعي — النسخة المحسّنة (مرحلة 1: النواة)
مبني على مواصفات "تعديلات مولّد الاستبيان بالذكاء الاصطناعي" (حسين، 2 أكتوبر 2026).

المسؤوليات هنا فقط:
  - بناء البرومبت الجديد (محاور + فقرات مصحّحة + عكسية + تفرّع...).
  - التحقق من رد النموذج ضد القواعد 1-21 من المواصفات (أخطاء بنيوية = تمنع
    الحفظ وتستدعي إعادة توليد تلقائية، تحذيرات = تُعرض للمعلم بس تسمح بالحفظ).
  - إصلاح آلي بسيط (القاعدة 15: استبدال تسميات ليكرت غير المطابقة).

لا يسوي أي استدعاء شبكة هنا - فقط نص/تحقق خالص، يُستدعى من survey_routes.py.
"""
import re

LIKERT5_OPTIONS = ['موافق بشدة', 'موافق', 'محايد', 'غير موافق', 'غير موافق بشدة']

_ABSOLUTE_WORDS = ['دائماً', 'دائما', 'جميع', 'كل', 'أبداً', 'ابدا', 'مطلقاً', 'مطلقا']
_NEGATION_WORDS = ['لا', 'ليس', 'لم', 'غير', 'عدم']
_EXPOSED_REVERSE_WORDS = ['عكسي', 'عكسية']

VALID_QUESTION_TYPES = ('likert5', 'rating', 'yes_no', 'single_choice', 'multi_choice', 'text')
VALID_AXIS_CODE_RE = re.compile(r'^[A-F]$')


# ─────────────────────────── البرومبت ───────────────────────────

_PROMPT_TEMPLATE = """أنت خبير في القياس والتقويم وبناء الاستبيانات وفق منهجية البحث العلمي.
مهمتك: بناء أداة استبيان قابلة لحساب الصدق والثبات، لا مجرد قائمة أسئلة.

## المعطيات
- الموضوع: {topic}
- نوع الاستبيان: {survey_type}
- الهدف أو القرار المبني على النتائج: {purpose}
- الفئة المستهدفة: {audience} — المرحلة: {grade_level}
- المحاور المحددة: {axes_line}
- عدد المحاور المصحّحة لكل محور: {items_per_axis}
- متغيرات المقارنة: {compare_by}
- فقرات عكسية: {include_reverse} — أسئلة معرفية موضوعية: {include_knowledge_check}
- مقدمة: {include_intro} — سؤال مفتوح ختامي: {include_open_question}
- ملاحظات المستخدم: {notes}

## بناء المحاور
1. كل محور يقيس مفهوماً واحداً محدداً، ولا يتداخل محوران في المفهوم.
2. اكتب لكل محور {items_per_axis} فقرة تقيس بالضبط نفس المفهوم من زوايا مختلفة (معرفة، سلوك، شعور، ممارسة...).
3. يُمنع تكرار الصياغة الحرفي أو المعنى لنفس المفهوم للفقرة الواحدة؛ لكن تعدد الفقرات للمفهوم الواحد مطلوب.
4. لا تخلط داخل المحور الواحد بين أكثر من مقياس ليكرت خماسي.

## صياغة الفقرات
5. "فكرة واحدة في كل فقرة"؛ لا تجمع فكرتين بـ"و" أو "أو".
6. صياغة محايدة لا توحي بإجابة معينة.
7. لغة مناسبة لمرحلة {grade_level}، بلا مصطلحات متخصصة غير مشروحة.
8. الفقرة 15 كلمة تقريباً كحد أعلى.
9. لا كلمات مطلقة (دائماً، أبداً، كل، جميع).
10. لا نفي مزدوج.
11. اكتب الفقرة بصيغة المتكلم ("أعرف..."، "أخصص...") حين يكون المقصود هو المستجيب نفسه.

## الفقرات العكسية (إن كانت مفعّلة: {include_reverse})
12. فقرة عكسية واحدة لكل محور على الأقل، ولا تتجاوز ثلث فقرات المحور.
13. العكسية تعبّر عن عكس المفهوم بصيغة مثبتة (مثال: "أؤجّل التحضير" لا بنفي "لا أخصص وقتاً أخرى").
14. ضع reverse=true بنص الفقرة؛ لا تكتب كلمة "عكسية" بنص الفقرة نفسه.
15. لا تجعلها أول فقرة في المحور ولا آخرها.

## أنواع الأسئلة الأخرى
16. للفقرات المصحّحة فقط، بالخيارات: ["موافق بشدة","موافق","محايد","غير موافق","غير موافق بشدة"] — نوع likert5.
17. لتقييم عام منفرد فقط، ويكون مقياس (1-5 أو 1-10) مع تسمية الطرفين — نوع rating، ولا scored=false لمحور.
18. أسئلة الفلترة الثنائية فقط. إن كان لها درجات فاكتبه single_choice بخيارات مدرجة. نوع yes_no.
19. single_choice وmulti_choice: خيارات شاملة وغير متداخلة، وأضف "غير ذلك" إن الحاجة. حدّد max_select عند الحاجة للمتعدد.
20. أسئلة ديموغرافية {compare_by} أسئلة فقط، غير محورية.
21. لكل أسئلة 2-3 معرفية إن كانت الأسئلة المعرفية مفعّلة: single_choice إجابة واحدة صحيحة مؤكدة وحقل correct_option، وscored=false ولا تضع "لا أعرف" معلومة متأكداً منها.
22. سؤال موجّه في النهاية؛ إن كان السؤال المفتوح مفعّلاً: text اختياري (مثال: "ما أهم شيء تتمنى أن...")، لا "هل لديك ملاحظات؟".

## الترتيب
23. المقدمة، ثم الديموغرافية، ثم المحاور من العام إلى الخاص، ثم الحساس، ثم المفتوح.
24. فاضبط skip_to لرمز أول سؤال في فلترة إذا كان سؤال فلترة يجعل محوراً لا ينطبق، فاضبط skip_to للمحور التالي المنطقي.

## الترميز
25. رمز الفقرة = رمز المحور + رقم (A1, A2...). وأسئلة الديموغرافية والمعرفية والمفتوح DM1, DM2... KN1, KN2... Q1 — اختيار رموز حروف A إلى F لا تتعارض مع رموز المحاور غير المصحّحة (X1, X2...).
26. الهدف، الاختيارية، السرية وأن الإجابات لا تؤثر على الدرجات، لا توجد إجابة صحيحة، الزمن التقريبي.

## المخرجات
27. أرجع JSON صالحاً فقط، بلا نص قبله أو بعده، وبلا علامات ```.
28. التزم بالمخطط التالي حرفياً:
{output_schema}"""

OUTPUT_SCHEMA_TEXT = """{
  "title": "عنوان الاستبيان",
  "intro": "نص المقدمة (فاضي لو include_intro=false)",
  "estimated_minutes": 5,
  "axes": [
    {"code": "A", "name": "اسم المحور", "construct": "تعريف المفهوم بجملة", "high_score_means": "ماذا تعني الدرجة المرتفعة"}
  ],
  "questions": [
    {
      "code": "A1", "axis": "A", "text": "نص الفقرة",
      "type": "likert5|rating|yes_no|single_choice|multi_choice|text",
      "options": ["خيار1", "خيار2"],
      "scale_min": 1, "scale_max": 5, "scale_labels": ["التسمية الدنيا", "التسمية العليا"],
      "max_select": 2,
      "correct_option": "الإجابة الصحيحة (معرفية فقط)",
      "reverse": false, "scored": true, "required": true,
      "skip_to": "رمز السؤال التالي (تفرّع فقط)"
    }
  ]
}"""


def build_prompt(params: dict) -> str:
    axes = params.get('axes') or []
    axes_line = (
        '، '.join(f"{a.get('name', '')} ({a.get('description', '')})" for a in axes)
        if axes else f"لم يحدد المستخدم محاور — اقترح {params.get('axes_count', 3)} محاور مناسبة مستمدة من الموضوع والهدف"
    )
    return _PROMPT_TEMPLATE.format(
        topic=params.get('topic', ''),
        survey_type=params.get('survey_type', 'كشفي'),
        purpose=params.get('purpose', ''),
        audience='، '.join(params.get('audience') or ['طلاب']),
        grade_level=params.get('grade_level', 'ثانوي'),
        axes_line=axes_line,
        items_per_axis=params.get('items_per_axis', 5),
        compare_by='، '.join(params.get('compare_by') or []) or 'بدون',
        include_reverse='مفعّلة' if params.get('include_reverse') else 'معطّلة - لا تضف فقرات عكسية إطلاقاً',
        include_knowledge_check='مفعّلة' if params.get('include_knowledge_check') else 'معطّلة - لا تضف أسئلة معرفية',
        include_intro='مفعّلة' if params.get('include_intro') else 'معطّلة - اترك intro فاضي',
        include_open_question='مفعّلة' if params.get('include_open_question') else 'معطّلة - لا تضف سؤال مفتوح ختامي',
        notes=params.get('notes') or 'بدون',
        output_schema=OUTPUT_SCHEMA_TEXT,
    )


def auto_fix(parsed: dict) -> dict:
    """إصلاحات آلية بسيطة قبل التحقق (القاعدة 15: خيارات ليكرت غير مطابقة حرفياً)"""
    for q in parsed.get('questions') or []:
        if q.get('type') == 'likert5':
            q['options'] = list(LIKERT5_OPTIONS)
    return parsed


def validate_survey_json(parsed: dict, params: dict):
    """يرجّع (hard_errors, warnings) — كل عنصر {rule, code, message}
    hard_errors غير فاضية = لازم إعادة توليد، ما تُحفظ أو تُعرض للمستخدم مباشرة."""
    errors = []
    warnings = []

    def err(rule, code, msg):
        errors.append({'rule': rule, 'code': code, 'message': msg})

    def warn(rule, code, msg):
        warnings.append({'rule': rule, 'code': code, 'message': msg})

    # 1) صحة البنية
    if not isinstance(parsed, dict) or 'title' not in parsed or 'axes' not in parsed or 'questions' not in parsed:
        err(1, None, 'الرد لا يطابق المخطط المطلوب (title/axes/questions)')
        return errors, warnings  # ما نقدر نكمل باقي الفحوصات بدون بنية سليمة

    axes = parsed.get('axes') or []
    questions = parsed.get('questions') or []

    # 2) تفرّد الرموز
    axis_codes = [a.get('code') for a in axes if a.get('code')]
    if len(axis_codes) != len(set(axis_codes)):
        err(2, 'axis_code_dup', 'فيه رمز محور مكرر')
    q_codes = [q.get('code') for q in questions if q.get('code')]
    if len(q_codes) != len(set(q_codes)):
        err(2, 'item_code_dup', 'فيه رمز سؤال مكرر')

    axis_code_set = set(axis_codes)
    items_per_axis_expected = params.get('items_per_axis', 5)
    survey_type = params.get('survey_type', 'كشفي')

    axis_question_count = {}
    for q in questions:
        axis = q.get('axis')
        qtype = q.get('type')
        code = q.get('code', '؟')

        # 3) ربط المحور
        if axis and axis not in axis_code_set:
            err(3, 'axis_ref', f'السؤال {code} فيه axis="{axis}" غير موجود بقائمة axes')

        if axis:
            axis_question_count[axis] = axis_question_count.get(axis, 0) + 1
            # 4) مقياس واحد بالمحور
            if qtype != 'likert5':
                err(4, 'axis_scale_mix', f'السؤال {code} جوا محور لكن نوعه "{qtype}" مو likert5')

        # 5) المصحّح داخل محور
        if q.get('scored') and not axis:
            err(5, 'scored_no_axis', f'السؤال {code} scored=true بدون axis')

        # 7) العكسية خارج ليكرت
        if q.get('reverse') and qtype != 'likert5':
            err(7, 'reverse_not_likert', f'السؤال {code} reverse=true لكن نوعه مو likert5')

        # 10) وسم مكشوف
        text = (q.get('text') or '')
        if any(w in text for w in _EXPOSED_REVERSE_WORDS):
            err(10, 'exposed_reverse', f'نص السؤال {code} يذكر كلمة "عكسي/عكسية" صراحة')

        # 16) خيارات الاختيار
        if qtype in ('single_choice', 'multi_choice'):
            opts = q.get('options') or []
            if len(opts) < 2:
                err(16, 'options_count', f'السؤال {code} عنده أقل من خيارين')
            elif len(opts) != len(set(opts)):
                err(16, 'options_dup', f'السؤال {code} فيه خيار مكرر')

        # 17) تسمية طرفي التقييم
        if qtype == 'rating':
            labels = q.get('scale_labels')
            if not labels or len(labels) != 2:
                err(17, 'rating_no_labels', f'السؤال {code} نوعه rating بدون scale_labels')

        # 18) الأسئلة المعرفية
        if qtype == 'single_choice' and q.get('correct_option') is not None and q.get('scored') is False:
            opts = q.get('options') or []
            if q.get('correct_option') not in opts:
                err(18, 'correct_option_missing', f'السؤال {code}: correct_option غير موجود ضمن options')

        # ── تحذيرات (مو خطأ، تُعرض بس) ──
        words = text.split()
        if len(words) > 20:
            warn(14, 'too_long', f'السؤال {code} أطول من 20 كلمة ({len(words)} كلمة)')
        if any(w in words for w in _ABSOLUTE_WORDS):
            warn(12, 'absolute_word', f'السؤال {code} فيه كلمة مطلقة (دائماً/كل/أبداً...)')
        neg_count = sum(1 for w in words if w in _NEGATION_WORDS)
        if neg_count >= 2:
            warn(13, 'double_negation', f'السؤال {code} فيه نفي مزدوج محتمل')
        if (' و' in f' {text}' or ' أو ' in text) and len(words) > 8:
            warn(11, 'possible_compound', f'السؤال {code} ممكن يكون فقرة مركّبة (يحتوي "و"/"أو")')

    # 6) عدد الفقرات بالمحور (كشفي/تقويمي فقط)
    if survey_type in ('كشفي', 'تقويمي'):
        for axis in axes:
            code = axis.get('code')
            count = axis_question_count.get(code, 0)
            if count < 4:
                err(6, 'axis_too_few_items', f'المحور {code} فيه {count} فقرة مصحّحة فقط (أقل من 4)')

    # 9) موقع العكسية + نسبة العكسية
    for axis in axes:
        code = axis.get('code')
        axis_qs = [q for q in questions if q.get('axis') == code]
        if not axis_qs:
            continue
        reverse_idx = [i for i, q in enumerate(axis_qs) if q.get('reverse')]
        if reverse_idx:
            if 0 in reverse_idx or (len(axis_qs) - 1) in reverse_idx:
                warn(9, 'reverse_position', f'المحور {code}: فقرة عكسية بأول أو آخر المحور')
            if len(reverse_idx) > max(1, len(axis_qs) // 3):
                warn(8, 'reverse_ratio', f'المحور {code}: نسبة العكسية أكثر من ثلث المحور')

    # 19) التفرّع
    code_order = {q.get('code'): i for i, q in enumerate(questions)}
    for q in questions:
        skip_to = q.get('skip_to')
        if skip_to:
            if skip_to not in code_order:
                err(19, 'skip_to_invalid', f'السؤال {q.get("code")}: skip_to="{skip_to}" غير موجود')
            elif code_order[skip_to] <= code_order.get(q.get('code'), -1):
                err(19, 'skip_to_backward', f'السؤال {q.get("code")}: skip_to يشير لسؤال سابق')

    # 20) تكرار دلالي بسيط (مقارنة تشابه نصي بين فقرات نفس المحور)
    for axis in axes:
        code = axis.get('code')
        axis_texts = [(q.get('code'), set((q.get('text') or '').split())) for q in questions if q.get('axis') == code]
        for i in range(len(axis_texts)):
            for j in range(i + 1, len(axis_texts)):
                c1, w1 = axis_texts[i]
                c2, w2 = axis_texts[j]
                if not w1 or not w2:
                    continue
                overlap = len(w1 & w2) / max(len(w1 | w2), 1)
                if overlap >= 0.6:
                    warn(20, 'semantic_overlap', f'الفقرتان {c1} و{c2} متشابهتان لفظياً جداً ({int(overlap*100)}%)')

    # 21) الطول الكلي
    est = parsed.get('estimated_minutes')
    if isinstance(est, (int, float)) and est > 10:
        warn(21, 'too_long_survey', f'الزمن المتوقع {est} دقيقة (أكثر من 10 دقائق)')

    return errors, warnings


def build_correction_message(hard_errors: list) -> str:
    """رسالة تصحيح تُرسل للنموذج مع نفس المحادثة لإصلاح أخطاء بنيوية محددة"""
    lines = ['ردك السابق فيه أخطاء بنيوية لازم تصلحها، أعد الرد كاملاً (JSON فقط) بعد تصحيح:']
    for e in hard_errors:
        lines.append(f"- قاعدة {e['rule']}: {e['message']}")
    return '\n'.join(lines)
