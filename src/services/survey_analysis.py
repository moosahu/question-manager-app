# src/services/survey_analysis.py
"""التحليل الإحصائي داخل التطبيق للاستبيانات القائمة على محاور (كشفي/تقويمي) — المرحلة 4
ثبات ألفا كرونباخ + تجزئة نصفية + ارتباط الفقرة ببقية المحور + تفسير المتوسطات + جودة الردود
(إجابة مسطّحة/تناقض العكسية/سرعة غير منطقية/رد مكرر من نفس الجهاز) + مقارنات بين الفئات
(Mann-Whitney/Kruskal-Wallis/ANOVA) + فجوة الأسئلة المعرفية.
بدون طلبات شبكة — يُستدعى من survey_routes.py فقط بعد جلب الردود والإجابات من القاعدة.

ملاحظة: فحص السرعة يحتاج SurveyResponse.started_at وSurvey.estimated_minutes، وفحص التكرار
يحتاج SurveyResponse.device_id — كلها تُملأ فقط للردود المُرسلة من نسخة التطبيق بعد هذا التحديث؛
الردود الأقدم تبقى بدونها فتُستثنى تلقائياً من هذين الفحصين تحديداً (بقية التحليل يشملها عادي).
"""
import numpy as np
from scipy import stats as sstats

LIKERT_SCORE_MAP = {
    'غير موافق بشدة': 1, 'غير موافق': 2, 'محايد': 3, 'موافق': 4, 'موافق بشدة': 5,
}

MEAN_BANDS = [
    (1.00, 1.80, 'منخفض جداً'),
    (1.81, 2.60, 'منخفض'),
    (2.61, 3.40, 'متوسط'),
    (3.41, 4.20, 'مرتفع'),
    (4.21, 5.00, 'مرتفع جداً'),
]


def _interpret_mean(mean):
    for lo, hi, label in MEAN_BANDS:
        if lo <= mean <= hi:
            return label
    return ''


def _item_score(raw_choice, reverse):
    """يحوّل نص إجابة ليكرت لدرجة 1-5، ويقلبها لو الفقرة عكسية: x' = 6 - x. يرجع None لو الإجابة مو ليكرت صالحة"""
    if raw_choice not in LIKERT_SCORE_MAP:
        return None
    x = LIKERT_SCORE_MAP[raw_choice]
    return 6 - x if reverse else x


def _axis_scores_matrix(items, responses, by_response):
    """مصفوفة درجات محور واحد — صف لكل مستجيب جاوب على كل فقرات المحور (بعد قلب العكسية)، يرجع (rows, response_ids)"""
    rows, resp_ids = [], []
    for r in responses:
        ans = by_response.get(r.id, {})
        scores, complete = [], True
        for q in items:
            a = ans.get(q.id)
            sc = _item_score(a.answer_choice if a else None, q.reverse)
            if sc is None:
                complete = False
                break
            scores.append(sc)
        if complete:
            rows.append(scores)
            resp_ids.append(r.id)
    return rows, resp_ids


def analyze_survey(survey, responses, answers):
    """التحليل الكامل لاستبيان مبني بمحاور — يرجع القاموس الجاهز للعرض بالتطبيق"""
    axes_meta = survey.axes or []
    questions = list(survey.questions)
    by_response = {}
    for a in answers:
        by_response.setdefault(a.response_id, {})[a.question_id] = a

    axes_out = []
    for axis in axes_meta:
        code = axis.get('code')
        items = [q for q in questions if q.axis_code == code and q.type == 'likert5' and q.scored]
        entry = {
            'code': code, 'name': axis.get('name', ''), 'construct': axis.get('construct', ''),
            'high_score_means': axis.get('high_score_means', ''),
            'items_count': len(items),
        }
        if not items:
            entry['insufficient_data'] = True
            axes_out.append(entry)
            continue

        rows, _resp_ids = _axis_scores_matrix(items, responses, by_response)
        k, n = len(items), len(rows)
        entry['n_responses'] = n
        if n < 2:
            entry['insufficient_data'] = True
            axes_out.append(entry)
            continue

        mat = np.array(rows, dtype=float)  # شكل (n, k)
        axis_totals = mat.sum(axis=1)
        axis_means = mat.mean(axis=1)
        overall_mean = float(axis_means.mean())
        entry['mean'] = round(overall_mean, 2)
        entry['interpretation'] = _interpret_mean(overall_mean)
        if n < 30:
            entry['stability_warning'] = 'عدد الردود أقل من 30 — الثبات غير مستقر'

        # ألفا كرونباخ: α = k/(k-1) * (1 - Σσ²ᵢ/σ²ₜ)
        if k > 1:
            item_vars = mat.var(axis=0, ddof=1)
            total_var = axis_totals.var(ddof=1)
            if total_var > 0:
                alpha = (k / (k - 1)) * (1 - (float(item_vars.sum()) / total_var))
                entry['alpha'] = round(float(alpha), 3)
                entry['alpha_rating'] = (
                    'مقبول' if alpha >= 0.70 else
                    'ضعيف — راجع الفقرات' if alpha >= 0.60 else
                    'غير مقبول — أعد بناء المحور'
                )
            else:
                entry['alpha'] = None
                entry['alpha_rating'] = None
        else:
            entry['alpha'] = None
            entry['alpha_rating'] = None

        # التجزئة النصفية (فردي/زوجي) مع تصحيح سبيرمان-براون: r_SB = 2r/(1+r)
        if k >= 4:
            odd_idx, even_idx = list(range(0, k, 2)), list(range(1, k, 2))
            odd_sum, even_sum = mat[:, odd_idx].sum(axis=1), mat[:, even_idx].sum(axis=1)
            if np.std(odd_sum) > 0 and np.std(even_sum) > 0:
                r = float(np.corrcoef(odd_sum, even_sum)[0, 1])
                entry['split_half_r'] = round(r, 3)
                entry['split_half_spearman_brown'] = round((2 * r) / (1 + r), 3) if (1 + r) != 0 else None
            else:
                entry['split_half_r'] = None
                entry['split_half_spearman_brown'] = None
        else:
            entry['split_half_r'] = None
            entry['split_half_spearman_brown'] = None

        # ارتباط كل فقرة ببقية فقرات المحور (item-rest) — تحت 0.30 = فقرة مرشّحة للحذف
        items_out = []
        for i, q in enumerate(items):
            rest = axis_totals - mat[:, i]
            item_col = mat[:, i]
            corr = float(np.corrcoef(item_col, rest)[0, 1]) if (np.std(item_col) > 0 and np.std(rest) > 0) else None
            items_out.append({
                'item_code': q.item_code, 'text': q.text, 'reverse': q.reverse,
                'item_rest_correlation': round(corr, 3) if corr is not None else None,
                'flagged': bool(corr is not None and corr < 0.30),
            })
        entry['items'] = items_out
        axes_out.append(entry)

    return {
        'total_responses': len(responses),
        'axes': axes_out,
        'response_quality': _response_quality(survey, questions, responses, by_response, axes_meta),
        'comparisons': _group_comparisons(survey, questions, responses, by_response, axes_meta),
        'knowledge_questions': _knowledge_analysis(questions, responses, by_response, axes_out),
    }


def _speed_and_duplicate_flags(survey, responses):
    """سرعة غير منطقية: مدة الإكمال أقل من ثلث الزمن المتوقع (estimated_minutes).
    رد مكرر: نفس device_id استُخدم بأكثر من رد لنفس الاستبيان (يهم خصوصاً بالاستبيانات المجهولة)."""
    fast_ids, device_counts = set(), {}
    expected = survey.estimated_minutes
    for r in responses:
        if r.started_at and r.submitted_at and expected:
            duration_min = (r.submitted_at - r.started_at).total_seconds() / 60
            if duration_min >= 0 and duration_min < (expected / 3):
                fast_ids.add(r.id)
        if r.device_id:
            device_counts.setdefault(r.device_id, []).append(r.id)
    duplicate_ids = set()
    for ids in device_counts.values():
        if len(ids) > 1:
            duplicate_ids.update(ids)
    return fast_ids, duplicate_ids


def _response_quality(survey, questions, responses, by_response, axes_meta):
    """إجابة مسطّحة (نفس الدرجة بكل فقرات المحور قبل القلب) + تناقض العكسية (عادية وعكسية كلاهما مرتفع
    أو كلاهما منخفض قبل القلب) — لكل محور ولكل رد. + سرعة غير منطقية ورد مكرر من نفس الجهاز (على مستوى الرد كامل)."""
    flat_count, contradiction_count = 0, 0
    flagged_response_ids = set()
    fast_ids, duplicate_ids = _speed_and_duplicate_flags(survey, responses)
    flagged_response_ids |= fast_ids | duplicate_ids
    for axis in axes_meta:
        code = axis.get('code')
        items = [q for q in questions if q.axis_code == code and q.type == 'likert5' and q.scored]
        if not items:
            continue
        regular = [q for q in items if not q.reverse]
        reverse = [q for q in items if q.reverse]
        for r in responses:
            ans = by_response.get(r.id, {})
            raw_vals, ok = [], True
            for q in items:
                a = ans.get(q.id)
                if not a or a.answer_choice not in LIKERT_SCORE_MAP:
                    ok = False
                    break
                raw_vals.append(LIKERT_SCORE_MAP[a.answer_choice])
            if not ok:
                continue
            if len(items) >= 4 and len(set(raw_vals)) == 1:
                flat_count += 1
                flagged_response_ids.add(r.id)
            if regular and reverse:
                reg_vals = [LIKERT_SCORE_MAP[ans[q.id].answer_choice] for q in regular
                            if ans.get(q.id) and ans[q.id].answer_choice in LIKERT_SCORE_MAP]
                rev_vals = [LIKERT_SCORE_MAP[ans[q.id].answer_choice] for q in reverse
                            if ans.get(q.id) and ans[q.id].answer_choice in LIKERT_SCORE_MAP]
                if reg_vals and rev_vals:
                    reg_avg, rev_avg = sum(reg_vals) / len(reg_vals), sum(rev_vals) / len(rev_vals)
                    if (reg_avg >= 4 and rev_avg >= 4) or (reg_avg <= 2 and rev_avg <= 2):
                        contradiction_count += 1
                        flagged_response_ids.add(r.id)
    result = {
        'flat_answer_count': flat_count,
        'reverse_contradiction_count': contradiction_count,
        'fast_completion_count': len(fast_ids),
        'duplicate_device_count': len(duplicate_ids),
        'flagged_responses_count': len(flagged_response_ids),
    }
    if not survey.estimated_minutes:
        result['speed_check_note'] = 'فحص السرعة معطّل — هذا الاستبيان ما عنده زمن متوقع محفوظ (estimated_minutes)'
    return result


def _group_comparisons(survey, questions, responses, by_response, axes_meta):
    """مقارنة متوسط كل محور بين فئات متغيرات survey.compare_by — Mann-Whitney لفئتين،
    Kruskal-Wallis لأكثر، + ANOVA إضافية لو العينة الكلية ≥30 (عينات أكبر/مدارس)"""
    compare_by = survey.compare_by or []
    if not compare_by or not axes_meta:
        return []
    out = []
    for var_name in compare_by:
        group_q = next((q for q in questions if (q.text or '').strip() == str(var_name).strip() and not q.scored), None)
        if group_q is None:
            out.append({'variable': var_name, 'error': 'ما فيه سؤال ديموغرافي بالاستبيان نص صريح مطابق لاسم هذا المتغير'})
            continue
        groups = {}
        for r in responses:
            a = by_response.get(r.id, {}).get(group_q.id)
            if a and a.answer_choice:
                groups.setdefault(a.answer_choice, []).append(r.id)
        if len(groups) < 2:
            out.append({'variable': var_name, 'error': 'أقل من فئتين بالردود الفعلية — ما تقدر تسوي مقارنة'})
            continue

        axes_results = []
        for axis in axes_meta:
            code = axis.get('code')
            items = [q for q in questions if q.axis_code == code and q.type == 'likert5' and q.scored]
            if not items:
                continue
            group_values = {}
            for label, resp_ids in groups.items():
                vals = []
                for rid in resp_ids:
                    ans = by_response.get(rid, {})
                    scores, ok = [], True
                    for q in items:
                        a = ans.get(q.id)
                        sc = _item_score(a.answer_choice if a else None, q.reverse)
                        if sc is None:
                            ok = False
                            break
                        scores.append(sc)
                    if ok:
                        vals.append(sum(scores) / len(scores))
                if len(vals) >= 2:
                    group_values[label] = vals
            if len(group_values) < 2:
                continue
            labels = list(group_values.keys())
            samples = [group_values[l] for l in labels]
            result = {
                'axis_code': code, 'axis_name': axis.get('name', ''),
                'groups': {l: {'n': len(group_values[l]), 'mean': round(sum(group_values[l]) / len(group_values[l]), 2)} for l in labels},
            }
            try:
                if len(labels) == 2:
                    stat, p = sstats.mannwhitneyu(samples[0], samples[1], alternative='two-sided')
                    result['test'] = 'Mann-Whitney U'
                    result['statistic'] = round(float(stat), 3)
                    result['p_value'] = round(float(p), 4)
                else:
                    stat_kw, p_kw = sstats.kruskal(*samples)
                    result['test'] = 'Kruskal-Wallis'
                    result['statistic'] = round(float(stat_kw), 3)
                    result['p_value'] = round(float(p_kw), 4)
                    if sum(len(s) for s in samples) >= 30:
                        stat_f, p_f = sstats.f_oneway(*samples)
                        result['anova_statistic'] = round(float(stat_f), 3)
                        result['anova_p_value'] = round(float(p_f), 4)
                result['significant'] = result['p_value'] < 0.05
            except Exception as e:  # عيّنة شاذة (تباين صفري بكل المجموعات...) — نسجّل الخطأ بدل ما نكسر التحليل كامل
                result['error'] = str(e)
            axes_results.append(result)
        out.append({'variable': var_name, 'groups_found': list(groups.keys()), 'axes': axes_results})
    return out


def _knowledge_analysis(questions, responses, by_response, axes_out):
    """نسبة الإجابة الصحيحة لكل سؤال معرفي موضوعي، مقارنة بمتوسط المحور الذاتي المقابل (لو عنده axis_code مشترك)
    — لكشف الفجوة بين ما يظنّه المستجيب عن نفسه وما يعرفه فعلياً"""
    axis_mean_by_code = {a['code']: a.get('mean') for a in axes_out if a.get('mean') is not None}
    out = []
    for q in questions:
        if q.scored or not q.correct_option:
            continue
        total, correct = 0, 0
        for r in responses:
            a = by_response.get(r.id, {}).get(q.id)
            if a and a.answer_choice:
                total += 1
                if a.answer_choice == q.correct_option:
                    correct += 1
        if total == 0:
            continue
        entry = {
            'item_code': q.item_code, 'text': q.text, 'n_answered': total,
            'correct_rate_percent': round((correct / total) * 100, 1),
        }
        if q.axis_code and q.axis_code in axis_mean_by_code:
            entry['related_axis_code'] = q.axis_code
            entry['related_axis_mean'] = axis_mean_by_code[q.axis_code]
        out.append(entry)
    return out
