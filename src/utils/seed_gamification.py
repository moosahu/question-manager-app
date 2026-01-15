# src/utils/seed_gamification.py
"""
إنشاء بيانات أولية لنظام التحفيز
- إنجازات
- تحديات
"""
from datetime import datetime, date, timedelta
from src.extensions import db
from src.models.gamification import Achievement, Challenge


def seed_achievements():
    """إنشاء الإنجازات الأساسية"""
    
    achievements_data = [
        # ==================== إنجازات الاختبارات ====================
        {
            'code': 'first_quiz',
            'achievement_type': 'quiz',
            'title': '🎯 البداية',
            'description': 'أكمل أول اختبار',
            'icon': '🎯',
            'points': 10,
            'rarity': 'common',
            'conditions': {'type': 'quiz_count', 'value': 1},
            'sort_order': 1
        },
        {
            'code': 'quiz_10',
            'achievement_type': 'quiz',
            'title': '📚 المثابر',
            'description': 'أكمل 10 اختبارات',
            'icon': '📚',
            'points': 50,
            'rarity': 'common',
            'conditions': {'type': 'quiz_count', 'value': 10},
            'sort_order': 2
        },
        {
            'code': 'quiz_50',
            'achievement_type': 'quiz',
            'title': '🏅 الخبير',
            'description': 'أكمل 50 اختبار',
            'icon': '🏅',
            'points': 200,
            'rarity': 'rare',
            'conditions': {'type': 'quiz_count', 'value': 50},
            'sort_order': 3
        },
        {
            'code': 'quiz_100',
            'achievement_type': 'quiz',
            'title': '👑 الأسطورة',
            'description': 'أكمل 100 اختبار',
            'icon': '👑',
            'points': 500,
            'rarity': 'legendary',
            'conditions': {'type': 'quiz_count', 'value': 100},
            'sort_order': 4
        },
        
        # ==================== إنجازات الدرجات الكاملة ====================
        {
            'code': 'perfect_first',
            'achievement_type': 'score',
            'title': '⭐ الكمال',
            'description': 'احصل على درجة كاملة 100%',
            'icon': '⭐',
            'points': 20,
            'rarity': 'common',
            'conditions': {'type': 'perfect_score', 'count': 1},
            'sort_order': 10
        },
        {
            'code': 'perfect_5',
            'achievement_type': 'score',
            'title': '🌟 الكمال المتكرر',
            'description': 'احصل على 5 درجات كاملة',
            'icon': '🌟',
            'points': 100,
            'rarity': 'rare',
            'conditions': {'type': 'perfect_score', 'count': 5},
            'sort_order': 11
        },
        {
            'code': 'perfect_10',
            'achievement_type': 'score',
            'title': '✨ سيد الكمال',
            'description': 'احصل على 10 درجات كاملة',
            'icon': '✨',
            'points': 250,
            'rarity': 'epic',
            'conditions': {'type': 'perfect_score', 'count': 10},
            'sort_order': 12
        },
        
        # ==================== إنجازات السلسلة ====================
        {
            'code': 'streak_3',
            'achievement_type': 'streak',
            'title': '🔥 الملتزم',
            'description': 'حافظ على سلسلة 3 أيام',
            'icon': '🔥',
            'points': 30,
            'rarity': 'common',
            'conditions': {'type': 'streak_days', 'days': 3},
            'sort_order': 20
        },
        {
            'code': 'streak_7',
            'achievement_type': 'streak',
            'title': '💪 المستمر',
            'description': 'حافظ على سلسلة 7 أيام',
            'icon': '💪',
            'points': 100,
            'rarity': 'rare',
            'conditions': {'type': 'streak_days', 'days': 7},
            'sort_order': 21
        },
        {
            'code': 'streak_30',
            'achievement_type': 'streak',
            'title': '🏆 المتفاني',
            'description': 'حافظ على سلسلة 30 يوم',
            'icon': '🏆',
            'points': 500,
            'rarity': 'epic',
            'conditions': {'type': 'streak_days', 'days': 30},
            'sort_order': 22
        },
        {
            'code': 'streak_90',
            'achievement_type': 'streak',
            'title': '💎 الأسطوري',
            'description': 'حافظ على سلسلة 90 يوم',
            'icon': '💎',
            'points': 2000,
            'rarity': 'legendary',
            'conditions': {'type': 'streak_days', 'days': 90},
            'sort_order': 23
        },
        
        # ==================== إنجازات النقاط ====================
        {
            'code': 'points_100',
            'achievement_type': 'points',
            'title': '💰 جامع النقاط',
            'description': 'اجمع 100 نقطة',
            'icon': '💰',
            'points': 10,
            'rarity': 'common',
            'conditions': {'type': 'points', 'value': 100},
            'sort_order': 30
        },
        {
            'code': 'points_500',
            'achievement_type': 'points',
            'title': '💎 الثري',
            'description': 'اجمع 500 نقطة',
            'icon': '💎',
            'points': 50,
            'rarity': 'rare',
            'conditions': {'type': 'points', 'value': 500},
            'sort_order': 31
        },
        {
            'code': 'points_1000',
            'achievement_type': 'points',
            'title': '👑 الملك',
            'description': 'اجمع 1000 نقطة',
            'icon': '👑',
            'points': 100,
            'rarity': 'epic',
            'conditions': {'type': 'points', 'value': 1000},
            'sort_order': 32
        },
        
        # ==================== إنجازات خاصة ====================
        {
            'code': 'night_owl',
            'achievement_type': 'special',
            'title': '🦉 البومة الليلية',
            'description': 'أكمل اختبار بعد منتصف الليل',
            'icon': '🦉',
            'points': 50,
            'rarity': 'rare',
            'conditions': {},
            'sort_order': 40
        },
        {
            'code': 'early_bird',
            'achievement_type': 'special',
            'title': '🐦 الطائر المبكر',
            'description': 'أكمل اختبار قبل الساعة 6 صباحاً',
            'icon': '🐦',
            'points': 50,
            'rarity': 'rare',
            'conditions': {},
            'sort_order': 41
        },
        {
            'code': 'speed_master',
            'achievement_type': 'special',
            'title': '⚡ السريع',
            'description': 'أكمل اختبار بدرجة 100% في أقل من 5 دقائق',
            'icon': '⚡',
            'points': 100,
            'rarity': 'epic',
            'conditions': {},
            'sort_order': 42
        },
    ]
    
    print("🎯 بدء إنشاء الإنجازات...")
    created_count = 0
    
    for ach_data in achievements_data:
        existing = Achievement.query.filter_by(code=ach_data['code']).first()
        if not existing:
            achievement = Achievement(**ach_data)
            db.session.add(achievement)
            created_count += 1
            print(f"   ✅ تم إنشاء: {ach_data['title']}")
        else:
            print(f"   ⚠️ موجود مسبقاً: {ach_data['title']}")
    
    db.session.commit()
    print(f"✅ تم إنشاء {created_count} إنجاز جديد\n")


def seed_challenges():
    """إنشاء التحديات الأساسية"""
    
    today = date.today()
    
    challenges_data = [
        # ==================== تحديات يومية ====================
        {
            'code': 'daily_quiz_3',
            'challenge_type': 'daily',
            'title': '🎯 تحدي اليوم: 3 اختبارات',
            'description': 'أكمل 3 اختبارات اليوم',
            'icon': '🎯',
            'target_type': 'quiz_count',
            'target_value': 3,
            'points': 50,
            'difficulty': 'easy',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=1)
        },
        {
            'code': 'daily_perfect_1',
            'challenge_type': 'daily',
            'title': '⭐ تحدي اليوم: درجة كاملة',
            'description': 'احصل على درجة كاملة في اختبار واحد',
            'icon': '⭐',
            'target_type': 'perfect_score',
            'target_value': 1,
            'points': 75,
            'difficulty': 'medium',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=1)
        },
        
        # ==================== تحديات أسبوعية ====================
        {
            'code': 'weekly_quiz_15',
            'challenge_type': 'weekly',
            'title': '📚 تحدي الأسبوع: 15 اختبار',
            'description': 'أكمل 15 اختبار هذا الأسبوع',
            'icon': '📚',
            'target_type': 'quiz_count',
            'target_value': 15,
            'points': 200,
            'difficulty': 'medium',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=7)
        },
        {
            'code': 'weekly_perfect_5',
            'challenge_type': 'weekly',
            'title': '🌟 تحدي الأسبوع: 5 درجات كاملة',
            'description': 'احصل على 5 درجات كاملة هذا الأسبوع',
            'icon': '🌟',
            'target_type': 'perfect_score',
            'target_value': 5,
            'points': 300,
            'difficulty': 'hard',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=7)
        },
        {
            'code': 'weekly_streak_7',
            'challenge_type': 'weekly',
            'title': '🔥 تحدي الأسبوع: سلسلة 7 أيام',
            'description': 'حافظ على سلسلة 7 أيام',
            'icon': '🔥',
            'target_type': 'streak',
            'target_value': 7,
            'points': 250,
            'difficulty': 'hard',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=7)
        },
        
        # ==================== تحديات شهرية ====================
        {
            'code': 'monthly_quiz_60',
            'challenge_type': 'monthly',
            'title': '🏆 تحدي الشهر: 60 اختبار',
            'description': 'أكمل 60 اختبار هذا الشهر',
            'icon': '🏆',
            'target_type': 'quiz_count',
            'target_value': 60,
            'points': 800,
            'difficulty': 'hard',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=30)
        },
        {
            'code': 'monthly_top_3',
            'challenge_type': 'monthly',
            'title': '👑 تحدي الشهر: أفضل 3',
            'description': 'كن ضمن أفضل 3 طلاب',
            'icon': '👑',
            'target_type': 'rank',
            'target_value': 3,
            'points': 1000,
            'difficulty': 'hard',
            'is_recurring': True,
            'start_date': today,
            'end_date': today + timedelta(days=30)
        },
    ]
    
    print("🎯 بدء إنشاء التحديات...")
    created_count = 0
    
    for challenge_data in challenges_data:
        existing = Challenge.query.filter_by(code=challenge_data['code']).first()
        if not existing:
            challenge = Challenge(**challenge_data)
            db.session.add(challenge)
            created_count += 1
            print(f"   ✅ تم إنشاء: {challenge_data['title']}")
        else:
            print(f"   ⚠️ موجود مسبقاً: {challenge_data['title']}")
    
    db.session.commit()
    print(f"✅ تم إنشاء {created_count} تحدي جديد\n")


def seed_all():
    """تنفيذ كل عمليات Seeding"""
    print("\n" + "="*60)
    print("🚀 بدء إنشاء البيانات الأولية لنظام التحفيز")
    print("="*60 + "\n")
    
    seed_achievements()
    seed_challenges()
    
    print("="*60)
    print("✅ اكتملت عملية إنشاء البيانات الأولية")
    print("="*60 + "\n")


if __name__ == '__main__':
    from src.main import app
    
    with app.app_context():
        seed_all()
