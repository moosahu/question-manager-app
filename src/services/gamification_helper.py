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
        # استيراد النماذج
        from src.models.student import Student
        from src.models.gamification import (
            StudentPoints, Achievement, StudentAchievement,
            Challenge, StudentChallenge
        )
        
        # 1. النقاط والمستوى
        student_points = StudentPoints.query.filter_by(student_id=student_id).first()
        
        if not student_points:
            # إنشاء سجل نقاط إذا لم يكن موجود
            student_points = StudentPoints(
                student_id=student_id,
                total_points=0,
                level=1
            )
            db.session.add(student_points)
            db.session.commit()
        
        # 2. الترتيب
        rank = db.session.query(StudentPoints).filter(
            StudentPoints.total_points > student_points.total_points
        ).count() + 1
        
        total_students = db.session.query(Student).filter_by(role='student').count()
        
        # 3. الإنجازات الحديثة (آخر 7 أيام)
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
        
        achievements_list = []
        for achievement, unlocked_at in recent_achievements:
            achievements_list.append({
                'title': achievement.title,
                'description': achievement.description,
                'points': achievement.points,
                'icon': achievement.icon,
                'unlocked_at': unlocked_at.isoformat()
            })
        
        # 4. التحديات النشطة
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
        
        challenges_list = []
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
        
        # 5. النقاط المطلوبة للمستوى التالي
        next_level = student_points.level + 1
        next_level_points = calculate_level_threshold(next_level)
        
        # 6. سلسلة الأيام المتتالية
        streak_days = calculate_streak(student_id)
        
        return {
            'points': student_points.total_points,
            'level': student_points.level,
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
        # إرجاع بيانات افتراضية
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


def calculate_level_threshold(level: int) -> int:
    """
    حساب النقاط المطلوبة للوصول لمستوى معين
    
    المعادلة: level * 500 (مثال بسيط)
    يمكن تعديلها حسب الرغبة
    """
    return level * 500


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
    
    # 1. الإحصائيات الأساسية
    if data['points'] > 0 or data['level'] > 1:
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
    
    # 4. التقدم للمستوى التالي
    if data['points_to_next_level'] > 0 and data['points_to_next_level'] <= 1000:
        progress = int((data['points'] / data['next_level_points']) * 15)
        progress_bar = "█" * progress + "░" * (15 - progress)
        percentage = int((data['points'] / data['next_level_points']) * 100)
        
        sections.append(f"""💪 قريب من المستوى التالي:
[{progress_bar}] {percentage}%
باقي: {data['points_to_next_level']:,} نقطة!""")
    
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
