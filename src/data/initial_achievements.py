# src/data/initial_achievements.py
"""
البيانات الأولية للإنجازات
"""

ACHIEVEMENTS = [
    {
        'achievement_type': 'first_quiz',
        'title': '🎯 البداية القوية',
        'description': 'أكملت أول اختبار!',
        'icon': '🎯',
        'points': 10,
        'conditions': {'quiz_count': 1}
    },
    {
        'achievement_type': 'streak_3',
        'title': '🔥 متواصل 3',
        'description': '3 أيام متتالية من الحل',
        'icon': '🔥',
        'points': 20,
        'conditions': {'streak_days': 3}
    },
    {
        'achievement_type': 'streak_7',
        'title': '⚡ متواصل 7',
        'description': 'أسبوع كامل من النشاط',
        'icon': '⚡',
        'points': 50,
        'conditions': {'streak_days': 7}
    },
    {
        'achievement_type': 'perfect_score',
        'title': '💯 الكمال',
        'description': 'حصلت على 100%!',
        'icon': '💯',
        'points': 30,
        'conditions': {'perfect_score': True}
    },
    {
        'achievement_type': 'improvement_20',
        'title': '📈 قفزة نوعية',
        'description': 'تحسن 20% في المعدل',
        'icon': '📈',
        'points': 40,
        'conditions': {'improvement_percent': 20}
    },
    {
        'achievement_type': 'solve_5_day',
        'title': '🚀 السرعة',
        'description': 'حل 5 اختبارات في يوم واحد',
        'icon': '🚀',
        'points': 25,
        'conditions': {'quizzes_per_day': 5}
    },
    {
        'achievement_type': 'top_performer',
        'title': '🥇 الأول في الصف',
        'description': 'أعلى معدل هذا الشهر',
        'icon': '🥇',
        'points': 100,
        'conditions': {'rank': 1}
    },
]


def init_achievements():
    """تهيئة الإنجازات في قاعدة البيانات"""
    from src.models.gamification import Achievement
    from src.extensions import db
    
    try:
        for ach_data in ACHIEVEMENTS:
            existing = Achievement.query.filter_by(
                achievement_type=ach_data['achievement_type']
            ).first()
            
            if not existing:
                achievement = Achievement(**ach_data)
                db.session.add(achievement)
                print(f"✅ تم إضافة إنجاز: {ach_data['title']}")
            else:
                print(f"⚠️ إنجاز موجود: {ach_data['title']}")
        
        db.session.commit()
        print(f"\n✅ تم تهيئة {len(ACHIEVEMENTS)} إنجاز بنجاح")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في تهيئة الإنجازات: {e}")
        db.session.rollback()
        return False


if __name__ == '__main__':
    # للاختبار المباشر
    from src import create_app
    app = create_app()
    with app.app_context():
        init_achievements()
