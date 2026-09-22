"""
اختبار مقارنة البرومبت القديم vs الجديد
يشتغل بـ system python3 بدون Flask context
"""
import os, sys, time, re, json
sys.path.insert(0, os.path.dirname(__file__))

EXCEL_FILE    = "/Users/hussain/Desktop/بنك أسئله كيمياء/excel_final_v2/كيمياء_2-1_الفصل_الثالث_الجدول_الدوري_والتدرج_في_خواص_العناصر.xlsx"
NUM_QUESTIONS = 30
MIN_DELAY     = 7.0

# ── API Key من البيئة فقط ────────────────────────────────
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
if not API_KEY:
    sys.exit("❌ GEMINI_API_KEY غير موجود في البيئة")

# ── النموذج من البيئة أو الافتراضي ──────────────────────
MODEL = os.getenv("GEMINI_MODEL") or os.getenv("AI_MODEL") or "gemini-2.0-flash"

from google import genai
client = genai.Client(api_key=API_KEY)

# ── استيراد _build_prompt من الكلاسر مباشرة ────────────
from src.services.question_classifier import QuestionClassifier
_cls = QuestionClassifier()

import openpyxl

# ── قراءة الأسئلة من Excel ───────────────────────────────
def load_questions(path, limit):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]

    def find_col(kws):
        for i, h in enumerate(headers):
            if any(k in h for k in kws):
                return i
        return None

    q_col    = find_col(["سؤال", "question", "نص"])
    opt_cols = [i for i, h in enumerate(headers)
                if any(k in h for k in ["خيار","option","بديل","إجابة"])]

    qs = []
    for row in rows[1:]:
        if len(qs) >= limit:
            break
        text = str(row[q_col] if q_col is not None else row[0] or "").strip()
        if not text or text == "None":
            continue
        opts = [str(row[oc] or "").strip() for oc in opt_cols[:4]
                if str(row[oc] or "").strip() not in ("", "None")]
        qs.append({"text": text, "options": opts})
    wb.close()
    return qs

# ── البرومبت القديم ───────────────────────────────────────
def old_prompt(q_text, options):
    opts = "\nالخيارات: " + " | ".join(options) if options else ""
    return f"""أنت خبير في تصنيف أسئلة الكيمياء. صنّف السؤال التالي:

السؤال: {q_text}{opts}

أجب بـ JSON فقط:
{{"difficulty": "easy/medium/hard", "bloom_level": "remember/understand/apply/analyze/evaluate/create"}}

معايير الصعوبة:
🟢 easy: تذكر معلومة مباشرة أو تعريف، لا حسابات
🟡 medium: فهم مفهوم، حساب بخطوة أو خطوتين، مقارنة بسيطة
🔴 hard: ربط عدة مفاهيم، حسابات متعددة الخطوات، تحليل نتائج

مستويات بلوم:
remember: يعرّف، يحدد، يذكر، يسمّي، ما هو، ما رمز، كم عدد
understand: يلخّص، يقارن، يستنتج، يفسّر، يشرح، وضّح
apply: يحلّ، يستخدم، يحوّل، احسب، طبّق، أوجد، وازن
analyze: يقارن بعمق، يفكّك، يحلّل، استنتج، ما العلاقة، ميّز
evaluate: يحكم، يدافع، يقدّر، قيّم، برّر، أيهما أفضل
create: يصمّم، يصيغ، ينشئ، اقترح، ابتكر، خطّط

قواعد:
1. أسئلة ما هو/عرّف/اذكر = remember + easy
2. أسئلة احسب/أوجد = apply + medium أو hard
3. أسئلة لماذا/فسّر = understand أو analyze"""

# ── استدعاء API ───────────────────────────────────────────
_last = 0.0
def call(prompt_text):
    global _last
    wait = MIN_DELAY - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    try:
        r = client.models.generate_content(model=MODEL, contents=prompt_text)
        return r.text
    except Exception as e:
        print(f"   ⚠️ {str(e)[:80]}")
        return None

def parse(text):
    if not text:
        return None
    m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group())
        diff  = d.get("difficulty","")
        bloom = d.get("bloom_level","")
        if diff in ["easy","medium","hard"] and bloom in ["remember","understand","apply","analyze","evaluate","create"]:
            return {"difficulty": diff, "bloom_level": bloom}
    except Exception:
        pass
    return None

# ── التشغيل ───────────────────────────────────────────────
def main():
    print(f"\n{'='*64}")
    print(f"  النموذج : {MODEL}")
    print(f"  الملف   : {os.path.basename(EXCEL_FILE)}")
    print(f"{'='*64}\n")

    qs = load_questions(EXCEL_FILE, NUM_QUESTIONS)
    print(f"✅ {len(qs)} سؤال محمّل\n")

    results = []
    old_bloom, new_bloom = {}, {}
    old_diff,  new_diff  = {}, {}
    changed = 0

    for i, q in enumerate(qs):
        print(f"[{i+1:02d}/{len(qs)}] {q['text'][:68]}")

        old_r = parse(call(old_prompt(q['text'], q['options'])))
        new_r = parse(call(_cls._build_prompt(q['text'], q['options'])))

        if not old_r or not new_r:
            print("   ⏭️ تخطي\n")
            continue

        did = old_r['difficulty'] != new_r['difficulty'] or old_r['bloom_level'] != new_r['bloom_level']
        if did:
            changed += 1

        icon = "🔄" if did else "  "
        print(f"   قديم : {old_r['difficulty']:6s} / {old_r['bloom_level']}")
        print(f"   جديد : {new_r['difficulty']:6s} / {new_r['bloom_level']}  {icon}\n")

        old_diff[old_r['difficulty']]   = old_diff.get(old_r['difficulty'], 0) + 1
        new_diff[new_r['difficulty']]   = new_diff.get(new_r['difficulty'], 0) + 1
        old_bloom[old_r['bloom_level']] = old_bloom.get(old_r['bloom_level'], 0) + 1
        new_bloom[new_r['bloom_level']] = new_bloom.get(new_r['bloom_level'], 0) + 1
        results.append({"q": q['text'][:75], "old": old_r, "new": new_r, "changed": did})

    total = len(results)
    pct   = round(changed / total * 100) if total else 0

    print(f"\n{'='*64}")
    print(f"  النتائج  |  {total} سؤال  |  تغيّر: {changed} ({pct}%)")
    print(f"{'='*64}")

    print(f"\n  الصعوبة      {'قديم':>6}  {'جديد':>6}")
    for k in ["easy","medium","hard"]:
        print(f"  {k:12s}  {old_diff.get(k,0):>6}  {new_diff.get(k,0):>6}")

    print(f"\n  بلوم         {'قديم':>6}  {'جديد':>6}")
    for k in ["remember","understand","apply","analyze","evaluate","create"]:
        o, n = old_bloom.get(k,0), new_bloom.get(k,0)
        arr = " ↑" if n>o else (" ↓" if n<o else "")
        print(f"  {k:12s}  {o:>6}  {n:>6}{arr}")

    if changed:
        print(f"\n  🔄 الأسئلة التي تغيّرت:")
        for r in results:
            if r['changed']:
                print(f"  • {r['q'][:65]}")
                print(f"    {r['old']['difficulty']}/{r['old']['bloom_level']} → {r['new']['difficulty']}/{r['new']['bloom_level']}")

    print(f"\n{'='*64}\n")

if __name__ == "__main__":
    main()
