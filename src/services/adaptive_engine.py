# src/services/adaptive_engine.py
"""
منطق الاختبار التشخيصي التكيفي (سلّم صعوبة من 3 مستويات):
- يبدأ بمتوسط، الإجابة الصحيحة تنقل لمستوى أصعب والخاطئة لأسهل.
- لو نفذت أسئلة المستوى المطلوب يرجع لمستوى مجاور، ولا يتكرر سؤال بنفس الجلسة.
- يسحب فقط من أسئلة الدروس المعتمدة (human_verified=True) وغير المحجوبة.
"""
import math
import random
from typing import Dict, List, Optional

try:
    from src.extensions import db
    from src.models.question import Question
    from src.models.curriculum import Lesson, Unit
except ImportError:  # pragma: no cover
    from extensions import db
    from models.question import Question
    from models.curriculum import Lesson, Unit

LEVELS = ['easy', 'medium', 'hard']
LEVEL_VALUE = {'easy': 1, 'medium': 2, 'hard': 3}
LEVEL_LABEL_AR = {'easy': 'مبتدئ', 'medium': 'متوسط', 'hard': 'متقدم'}
LEVEL_LABEL_AR_DIFF = {'easy': 'سهل', 'medium': 'متوسط', 'hard': 'صعب'}

# لو نفذت أسئلة المستوى المطلوب: جرّب هذه المستويات بالترتيب (مجاور أسهل أولاً)
FALLBACK_ORDER = {
    'easy': ['easy', 'medium', 'hard'],
    'medium': ['medium', 'easy', 'hard'],
    'hard': ['hard', 'medium', 'easy'],
}

MIN_PER_LEVEL = 2


def resolve_lesson_ids(lesson_id=None, unit_id=None, course_id=None) -> List[int]:
    """الدروس اللي يُسحب منها الاختبار حسب النطاق المختار (درس / وحدة / منهج)"""
    if lesson_id:
        return [lesson_id]
    if unit_id:
        return [l.id for l in Lesson.query.filter_by(unit_id=unit_id).all()]
    if course_id:
        return [
            l.id for l in Lesson.query.join(Unit, Lesson.unit_id == Unit.id)
            .filter(Unit.course_id == course_id).all()
        ]
    return []


def _pool_query(lesson_ids: List[int]):
    return Question.query.filter(
        Question.lesson_id.in_(lesson_ids),
        Question.question_type == 'mcq',
        Question.human_verified == True,  # noqa: E712
        Question.is_blocked == False,     # noqa: E712
    )


def bank_readiness(lesson_ids: List[int], questions_count: int) -> Dict:
    """جاهزية بنك الأسئلة المعتمد: عدد كل مستوى + هل يكفي لاختبار بهذا العدد"""
    counts = {lvl: 0 for lvl in LEVELS}
    if lesson_ids:
        rows = db.session.query(Question.difficulty, db.func.count(Question.question_id)).filter(
            Question.lesson_id.in_(lesson_ids),
            Question.question_type == 'mcq',
            Question.human_verified == True,  # noqa: E712
            Question.is_blocked == False,     # noqa: E712
        ).group_by(Question.difficulty).all()
        for difficulty, cnt in rows:
            if difficulty in counts:
                counts[difficulty] = cnt

    total = sum(counts.values())
    problems = []
    if total < questions_count:
        problems.append(f'البنك المعتمد فيه {total} سؤال فقط والاختبار يحتاج {questions_count}')
    for lvl in LEVELS:
        if counts[lvl] < MIN_PER_LEVEL:
            problems.append(f'مستوى {LEVEL_LABEL_AR_DIFF[lvl]} فيه {counts[lvl]} سؤال معتمد (الحد الأدنى {MIN_PER_LEVEL})')
    return {'ready': not problems, 'counts': counts, 'total': total, 'problems': problems}



def next_level(level: str, is_correct: bool) -> str:
    """صح → أصعب، غلط → أسهل (بحدود المستويات الثلاثة)"""
    i = LEVELS.index(level) if level in LEVELS else 1
    i = min(len(LEVELS) - 1, i + 1) if is_correct else max(0, i - 1)
    return LEVELS[i]


def pick_question(
    lesson_ids: List[int],
    level: str,
    served_ids: List[int],
    lesson_counts: Dict[str, int],
    recent_blooms: List[str],
    rng: random.Random,
) -> Optional[Question]:
    """
    يختار سؤال بالمستوى المطلوب (وإلا أقرب مستوى متاح). عند وجود عدة دروس يفضّل الأقل ظهوراً،
    وبين المرشحين يفضّل مستوى بلوم لم يظهر مؤخراً لتنويع الأسئلة.
    """
    for lvl in FALLBACK_ORDER.get(level, FALLBACK_ORDER['medium']):
        query = _pool_query(lesson_ids).filter(Question.difficulty == lvl)
        if served_ids:
            query = query.filter(~Question.question_id.in_(served_ids))
        candidates = [q for q in query.all() if any(o.is_correct for o in q.options)
                      and len(q.options) >= 2]
        if not candidates:
            continue

        least = min(lesson_counts.get(str(q.lesson_id), 0) for q in candidates)
        candidates = [q for q in candidates if lesson_counts.get(str(q.lesson_id), 0) == least]
        fresh_bloom = [q for q in candidates if q.bloom_level not in recent_blooms]
        return rng.choice(fresh_bloom or candidates)
    return None


def estimate_level(served_levels: List[str], upcoming_level: str) -> str:
    """
    المستوى المقدّر: متوسط مستويات النصف الأخير من الأسئلة مع المستوى القادم
    (الطريقة المعتادة بالسلّم لأن أول الاختبار يكون تخمين والسلّم يستقر بعدها).
    """
    if not served_levels:
        return upcoming_level if upcoming_level in LEVELS else 'medium'
    tail = served_levels[-max(1, math.ceil(len(served_levels) / 2)):] + [upcoming_level]
    avg = sum(LEVEL_VALUE.get(l, 2) for l in tail) / len(tail)
    return LEVELS[max(0, min(2, int(math.floor(avg + 0.5)) - 1))]
