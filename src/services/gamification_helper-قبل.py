# src/services/gamification_helper.py
"""
دوال مساعدة لجلب بيانات Gamification للرسائل الذكية
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.extensions import db


def get_student_gamification_data(student_id: int) -> Dict:
    """
    جلب جميع بيانات Gamification للطالب
    
    Returns:
        {
            'points': int,
            'level': int,
            'rank': int,
            'total_students': int,
            'recent_achievements': List[Dict],
            'active_challenges': List[Dict],
            'next_level_points': int,
            'streak_days': int
        }
    """
    try:
        # استيراد النماذج الأساسية
        from src.models.student import Student
        from src.models.gamification import StudentPoints
        
        # 1. النقاط والمستوى
        student_points = StudentPoints.query.filter_by(student_id=student_id).first()
        
        if not student_points:
            # إنشاء سجل نقاط إذا لم يكن موجود
            student_points = StudentPoints(
                student_id=student_id,
                total_points=0
            )
            db.session.add(student_points)
            db.session.commit()
        
        # 2. الترتيب
        rank = db.session.query(StudentPoints).filter(
            StudentPoints.total_points > student_points.total_points
        ).count() + 1
        
        total_students = db.session.query(Student).count()
        
        # 3. حساب المستوى من النقاط
        level = calculate_level_from_points(student_points.total_points)
        
        # 4. الإنجازات الحديثة (مع معالجة الأخطاء)
        achievements_list = []
        try:
            from src.models.gamification import Achievement, StudentAchievement
            
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_achievements = db.session.query(
                Achievement, StudentAchievement.unlocked_at
            ).join(
                StudentAchievement
            ).filter(
                StudentAchievement.student_id == student_id,
                StudentAchievement.unlocked_at >= week_ago
            ).order_by(
                StudentAchievement.unlocked_at.desc()
            ).limit(3).all()
            
            for achievement, unlocked_at in recent_achievements:
                achievements_list.append({
                    'title': achievement.title,
                    'description': achievement.description,
                    'points': achievement.points,
                    'icon': achievement.icon,
                    'unlocked_at': unlocked_at.isoformat()
                })
        except Exception as e:
            print(f"⚠️ لا يمكن جلب الإنجازات: {e}")
            db.session.rollback()  # ✅ إضافة rollback
        
        # 5. التحديات النشطة (مع معالجة الأخطاء)
        challenges_list = []
        try:
            from src.models.gamification import Challenge, StudentChallenge
            
            today = datetime.utcnow().date()
            active_challenges = db.session.query(
                Challenge, StudentChallenge
            ).outerjoin(
                StudentChallenge,
                db.and_(
                    StudentChallenge.challenge_id == Challenge.id,
                    StudentChallenge.student_id == student_id
                )
            ).filter(
                Challenge.is_active == True,
                db.or_(
                    Challenge.end_date == None,
                    Challenge.end_date >= today
                )
            ).all()
            
            for challenge, student_challenge in active_challenges:
                progress = 0
                completed = False
                
                if student_challenge:
                    progress = student_challenge.progress
                    completed = student_challenge.completed
                
                challenges_list.append({
                    'id': challenge.id,
                    'title': challenge.title,
                    'description': challenge.description,
                    'target': challenge.target_value,
                    'progress': progress,
                    'completed': completed,
                    'points': challenge.points,
                    'type': challenge.challenge_type
                })
        except Exception as e:
            print(f"⚠️ لا يمكن جلب التحديات: {e}")
            db.session.rollback()  # ✅ إضافة rollback
        
        # 6. النقاط المطلوبة للمستوى التالي
        next_level = level + 1
        next_level_points = calculate_level_threshold(next_level)
        
        # 7. سلسلة الأيام المتتالية
        streak_days = calculate_streak(student_id)
        
        return {
            'points': student_points.total_points,
            'level': level,
            'rank': rank,
            'total_students': total_students,
            'recent_achievements': achievements_list,
            'active_challenges': challenges_list,
            'next_level_points': next_level_points,
            'points_to_next_level': next_level_points - student_points.total_points,
            'streak_days': streak_days
        }
        
    except Exception as e:
        print(f"❌ خطأ في get_student_gamification_data: {e}")
        import traceback
        traceback.print_exc()
        
        # تنظيف الـ session
        try:
            db.session.rollback()
        except:
            pass
        
        # إرجاع بيانات افتراضية (آمنة)
        return {
            'points': 0,
            'level': 1,
            'rank': 0,
            'total_students': 0,
            'recent_achievements': [],
            'active_challenges': [],
            'next_level_points': 100,
            'points_to_next_level': 100,
            'streak_days': 0
        }


def calculate_level_from_points(total_points: int) -> int:
    """حساب المستوى من النقاط"""
    if total_points >= 1000:
        return 5
    elif total_points >= 500:
        return 4
    elif total_points >= 250:
        return 3
    elif total_points >= 100:
        return 2
    else:
        return 1


def calculate_level_threshold(level: int) -> int:
    """
    حساب النقاط المطلوبة للوصول لمستوى معين
    
    المستويات:
    - المستوى 1: 0-99 نقطة
    - المستوى 2: 100-249 نقطة  
    - المستوى 3: 250-499 نقطة
    - المستوى 4: 500-999 نقطة
    - المستوى 5: 1000+ نقطة
    """
    thresholds = {
        1: 0,      # البداية
        2: 100,    # للوصول للمستوى 2
        3: 250,    # للوصول للمستوى 3
        4: 500,    # للوصول للمستوى 4
        5: 1000    # للوصول للمستوى 5
    }
    return thresholds.get(level, 1000)


def calculate_streak(student_id: int) -> int:
    """
    حساب عدد الأيام المتتالية التي حل فيها الطالب اختبارات
    """
    try:
        from src.models.student_result import StudentResult
        
        # جلب تواريخ الاختبارات
        results = db.session.query(
            db.func.date(StudentResult.created_at).label('date')
        ).filter(
            StudentResult.student_id == student_id
        ).group_by(
            db.func.date(StudentResult.created_at)
        ).order_by(
            db.func.date(StudentResult.created_at).desc()
        ).all()
        
        if not results:
            return 0
        
        # حساب السلسلة المتتالية
        streak = 0
        current_date = datetime.utcnow().date()
        
        for result in results:
            result_date = result.date
            
            # التحقق من التتالي
            if result_date == current_date or result_date == current_date - timedelta(days=1):
                streak += 1
                current_date = result_date - timedelta(days=1)
            else:
                break
        
        return streak
        
    except Exception as e:
        print(f"❌ خطأ في calculate_streak: {e}")
        return 0


def format_gamification_section(data: Dict) -> str:
    """
    تنسيق قسم Gamification للرسالة
    
    Args:
        data: بيانات من get_student_gamification_data
    
    Returns:
        نص منسق جاهز للإضافة للرسالة
    """
    sections = []
    
    # 1. الإحصائيات الأساسية (تُعرض دائماً)
    rank_text = f"#{data['rank']}" if data['rank'] > 0 else "جديد"
    sections.append(f"""📊 إحصائياتك:
• النقاط: {data['points']:,} 💎
• المستوى: {data['level']} ⭐
• الترتيب: {rank_text} من {data['total_students']}""")
    
    # 2. الإنجازات الحديثة
    if data['recent_achievements']:
        achievements_text = "🏅 إنجازات جديدة:\n"
        for ach in data['recent_achievements'][:2]:  # أحدث 2 فقط
            achievements_text += f"✨ {ach['title']}! (+{ach['points']} نقطة)\n"
        sections.append(achievements_text.strip())
    
    # 3. التحديات النشطة
    active_challenges = [c for c in data['active_challenges'] if not c['completed']]
    if active_challenges:
        challenge = active_challenges[0]  # أول تحدي نشط
        progress_bars = int((challenge['progress'] / challenge['target']) * 10)
        progress_bar = "█" * progress_bars + "░" * (10 - progress_bars)
        
        sections.append(f"""🎯 تحدي اليوم:
{challenge['title']}
[{progress_bar}] {challenge['progress']}/{challenge['target']}
الجائزة: +{challenge['points']} نقطة! 💰""")
    
    # 4. التقدم للمستوى التالي (تُعرض إذا لم يصل للمستوى 5)
    if data['level'] < 5 and data['points_to_next_level'] > 0:
        progress = int((data['points'] / data['next_level_points']) * 15)
        progress_bar = "█" * progress + "░" * (15 - progress)
        percentage = int((data['points'] / data['next_level_points']) * 100)
        
        sections.append(f"""💪 قريب من المستوى التالي:
[{progress_bar}] {percentage}%
باقي: {data['points_to_next_level']:,} نقطة!""")
    elif data['level'] >= 5:
        sections.append(f"""🏆 وصلت للمستوى الأقصى!
أنت من النخبة! 👑""")
    
    # 5. سلسلة الأيام
    if data['streak_days'] >= 3:
        sections.append(f"🔥 سلسلة: {data['streak_days']} أيام متتالية!")
    
    return "\n\n".join(sections)


def get_compact_gamification_text(data: Dict) -> str:
    """
    نسخة مختصرة من معلومات Gamification
    للرسائل القصيرة
    """
    parts = []
    
    if data['points'] > 0:
        parts.append(f"💎 {data['points']:,} نقطة")
    
    if data['level'] > 1:
        parts.append(f"⭐ مستوى {data['level']}")
    
    if data['rank'] > 0 and data['rank'] <= 10:
        parts.append(f"🏆 #{data['rank']}")
    
    if data['streak_days'] >= 3:
        parts.append(f"🔥 {data['streak_days']} أيام")
    
    return " • ".join(parts) if parts else ""
