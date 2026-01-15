# src/hooks/quiz_completion_hook.py
"""
Hook موحد يتم تشغيله عند إكمال الطالب لاختبار

يتولى:
1. تحديث النقاط في student_points table
2. التحقق من الإنجازات والتحديات (مع دعم Challenge الجديد)
3. إرسال إشعار ذكي واحد (بدون تكرار)

محدّث: يناير 2026 - دعم كامل لنظام التحديات الجديد
✅ تم إصلاح: استخدام >= بدلاً من == في check_achievements
✅ تم إضافة: التحقق من قاعدة البيانات لتجنب تكرار الإنجازات
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from src.extensions import db
from src.models.student import Student
from src.models.student_result import StudentResult


def on_quiz_completed(student_id: int, quiz_result: StudentResult):
    """
    يتم استدعاؤه بعد حفظ نتيجة الاختبار في قاعدة البيانات
    
    Args:
        student_id: رقم الطالب
        quiz_result: نتيجة الاختبار
    """
    try:
        print(f"\n{'='*60}")
        print(f"🎯 معالجة إكمال اختبار للطالب {student_id}")
        print(f"{'='*60}")
        
        # 1. جلب الطالب
        student = Student.query.get(student_id)
        if not student:
            print(f"   ❌ الطالب {student_id} غير موجود!")
            return
        
        print(f"   ✅ الطالب: {student.name} ({student.username})")
        
        # 2. حساب النقاط
        print("   1️⃣ حساب النقاط...")
        points_earned = calculate_points(quiz_result)
        print(f"   💰 النقاط المكتسبة: {points_earned}")
        
        # 3. تحديث student_points
        print("   2️⃣ تحديث student_points...")
        student_points = update_student_points(student_id, points_earned, quiz_result)
        
        if student_points:
            print(f"   📊 النقاط: {student_points['old_points']} → {student_points['new_points']}")
            if student_points['new_level'] > student_points['old_level']:
                print(f"   ⭐ ترقية المستوى: {student_points['old_level']} → {student_points['new_level']} 🎉")
            else:
                print(f"   ⭐ المستوى: {student_points['new_level']}")
        
        # 4. حساب وتحديث السلسلة
        print("   3️⃣ حساب السلسلة...")
        streak = update_streak(student_id)
        print(f"   🔥 السلسلة: {streak} يوم")
        
        # 5. التحقق من الإنجازات
        print("   4️⃣ التحقق من الإنجازات...")
        achievements = check_achievements(student_id, quiz_result, student_points, streak)
        
        if achievements:
            print(f"   🏆 فتح {len(achievements)} إنجاز جديد:")
            for ach in achievements:
                print(f"      - {ach['title']} (+{ach['points']} نقطة)")
            save_achievements(student_id, achievements)
        else:
            print("   ℹ️ لا توجد إنجازات جديدة")
        
        # 6. التحقق من التحديات (مع دعم Challenge الجديد)
        print("   5️⃣ التحقق من التحديات...")
        completed_challenges = check_and_update_challenges(student_id, quiz_result, student_points)
        
        if completed_challenges:
            print(f"   🎯 أكمل {len(completed_challenges)} تحدي:")
            for ch in completed_challenges:
                print(f"      - {ch['title']} (+{ch['points']} نقطة)")
        else:
            print("   ℹ️ لا توجد تحديات مكتملة")
        
        # 7. إرسال إشعار ذكي واحد فقط
        print("   6️⃣ إرسال الإشعار...")
        send_notification(
            student=student,
            quiz_result=quiz_result,
            points_earned=points_earned,
            student_points=student_points,
            streak=streak,
            achievements=achievements,
            challenges=completed_challenges
        )
        
        print(f"\n{'='*60}")
        print(f"✅ اكتملت معالجة الاختبار بنجاح!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ خطأ في on_quiz_completed: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            db.session.rollback()
        except:
            pass


def calculate_points(quiz_result: StudentResult) -> int:
    """
    حساب النقاط المكتسبة من الاختبار
    
    Returns:
        int: عدد النقاط
    """
    base_points = 10  # نقاط أساسية
    bonus_points = 0
    
    score = quiz_result.score_percentage
    
    # بونص حسب الدرجة
    if score == 100:
        bonus_points += 20  # درجة كاملة
    elif score >= 90:
        bonus_points += 15
    elif score >= 80:
        bonus_points += 10
    elif score >= 70:
        bonus_points += 5
    
    # بونص للسرعة (أقل من 5 دقائق مع درجة عالية)
    if quiz_result.time_spent and quiz_result.time_spent < 300 and score >= 90:
        bonus_points += 5
    
    return base_points + bonus_points


def update_student_points(student_id: int, points_earned: int, quiz_result: StudentResult) -> dict:
    """
    تحديث النقاط في student_points table
    
    Returns:
        dict: {old_points, new_points, old_level, new_level}
    """
    try:
        from src.models.gamification import StudentPoints, PointTransaction
        
        # جلب أو إنشاء سجل النقاط
        student_points = StudentPoints.query.filter_by(student_id=student_id).first()
        
        if not student_points:
            student_points = StudentPoints(
                student_id=student_id,
                total_points=0,
                lifetime_points=0
            )
            db.session.add(student_points)
            db.session.flush()
        
        # حفظ القيم القديمة
        old_points = student_points.total_points
        old_level = calculate_level(old_points)
        
        # تحديث النقاط
        student_points.total_points += points_earned
        student_points.lifetime_points += points_earned
        
        # حساب المستوى الجديد
        new_level = calculate_level(student_points.total_points)
        
        # تحديث المستوى في القاعدة إذا كان الحقل موجود
        if hasattr(student_points, 'level'):
            student_points.level = new_level
        
        # حفظ transaction
        transaction = PointTransaction(
            student_id=student_id,
            amount=points_earned,
            reason=f"إكمال اختبار: {quiz_result.quiz_name or 'اختبار'}",
            reference_type='quiz',
            reference_id=quiz_result.id
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return {
            'old_points': old_points,
            'new_points': student_points.total_points,
            'old_level': old_level,
            'new_level': new_level
        }
        
    except Exception as e:
        print(f"      ⚠️ خطأ في update_student_points: {e}")
        db.session.rollback()
        return None


def calculate_level(total_points: int) -> int:
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


def update_streak(student_id: int) -> int:
    """
    تحديث وحساب السلسلة
    
    Returns:
        int: عدد أيام السلسلة الحالية
    """
    try:
        from src.models.gamification import StudentPoints
        
        # جلب student_points
        student_points = StudentPoints.query.filter_by(student_id=student_id).first()
        
        if not student_points:
            return 0
        
        # إذا كان الحقل موجود في StudentPoints، استخدمه
        if hasattr(student_points, 'update_streak'):
            student_points.update_streak()
            db.session.commit()
            return student_points.current_streak
        
        # وإلا احسبها يدوياً
        return calculate_streak(student_id)
        
    except Exception as e:
        print(f"      ⚠️ خطأ في update_streak: {e}")
        return calculate_streak(student_id)


def calculate_streak(student_id: int) -> int:
    """حساب عدد الأيام المتتالية (طريقة بديلة)"""
    try:
        # جلب تواريخ الاختبارات (مجموعة بحسب اليوم)
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
        
        # حساب السلسلة
        streak = 0
        today = datetime.utcnow().date()
        
        for i, result in enumerate(results):
            result_date = result[0] if isinstance(result, tuple) else result.date
            
            if i == 0:
                # أول تاريخ
                if result_date == today or result_date == today - timedelta(days=1):
                    streak = 1
                else:
                    break  # انقطعت السلسلة
            else:
                # التواريخ اللاحقة
                prev_date = results[i-1][0] if isinstance(results[i-1], tuple) else results[i-1].date
                
                if (prev_date - result_date).days == 1:
                    streak += 1
                else:
                    break  # انقطعت السلسلة
        
        return streak
        
    except Exception as e:
        print(f"      ⚠️ خطأ في calculate_streak: {e}")
        return 0


def check_achievements(student_id: int, quiz_result: StudentResult, student_points: dict, streak: int = 0) -> list:
    """
    التحقق من الإنجازات المكتملة
    
    ✅ محدّث: يستخدم >= بدلاً من ==
    ✅ محدّث: يتحقق من قاعدة البيانات لتجنب التكرار
    
    Args:
        student_id: معرف الطالب
        quiz_result: نتيجة الاختبار
        student_points: معلومات النقاط والمستوى
        streak: عدد أيام السلسلة
    
    Returns:
        list: قائمة الإنجازات الجديدة فقط
    """
    achievements = []
    
    try:
        from src.models.gamification import Achievement, StudentAchievement
        
        # عدد الاختبارات الكلي
        total_quizzes = StudentResult.query.filter_by(student_id=student_id).count()
        
        # عدد الدرجات الكاملة
        perfect_scores = StudentResult.query.filter_by(
            student_id=student_id
        ).filter(
            StudentResult.score_percentage == 100
        ).count()
        
        # قائمة الإنجازات المحتملة مع شروطها
        potential_achievements = []
        
        # ===== إنجازات الاختبارات =====
        if total_quizzes >= 1:
            potential_achievements.append({
                'type': 'first_quiz',
                'title': '🎯 البداية',
                'description': 'أكمل أول اختبار',
                'icon': '🎯',
                'points': 10
            })
        
        if total_quizzes >= 10:
            potential_achievements.append({
                'type': 'quiz_10',
                'title': '📚 المثابر',
                'description': 'أكمل 10 اختبارات',
                'icon': '📚',
                'points': 50
            })
        
        if total_quizzes >= 50:
            potential_achievements.append({
                'type': 'quiz_50',
                'title': '🏅 الخبير',
                'description': 'أكمل 50 اختبار',
                'icon': '🏅',
                'points': 200
            })
        
        if total_quizzes >= 100:
            potential_achievements.append({
                'type': 'quiz_100',
                'title': '👑 الأسطورة',
                'description': 'أكمل 100 اختبار',
                'icon': '👑',
                'points': 500
            })
        
        # ===== إنجازات الدرجات الكاملة =====
        if perfect_scores >= 1:
            potential_achievements.append({
                'type': 'perfect_first',
                'title': '⭐ الكمال',
                'description': 'احصل على أول درجة كاملة',
                'icon': '⭐',
                'points': 20
            })
        
        if perfect_scores >= 5:
            potential_achievements.append({
                'type': 'perfect_5',
                'title': '🌟 الكمال المتكرر',
                'description': 'احصل على 5 درجات كاملة',
                'icon': '🌟',
                'points': 100
            })
        
        if perfect_scores >= 10:
            potential_achievements.append({
                'type': 'perfect_10',
                'title': '✨ سيد الكمال',
                'description': 'احصل على 10 درجات كاملة',
                'icon': '✨',
                'points': 250
            })
        
        # ===== إنجازات النقاط =====
        if student_points:
            total_points = student_points['new_points']
            
            if total_points >= 100:
                potential_achievements.append({
                    'type': 'points_100',
                    'title': '💰 جامع النقاط',
                    'description': 'اجمع 100 نقطة',
                    'icon': '💰',
                    'points': 10
                })
            
            if total_points >= 500:
                potential_achievements.append({
                    'type': 'points_500',
                    'title': '💎 الثري',
                    'description': 'اجمع 500 نقطة',
                    'icon': '💎',
                    'points': 50
                })
            
            if total_points >= 1000:
                potential_achievements.append({
                    'type': 'points_1000',
                    'title': '👑 الملك',
                    'description': 'اجمع 1000 نقطة',
                    'icon': '👑',
                    'points': 100
                })
        
        # ===== إنجازات السلسلة =====
        if streak >= 3:
            potential_achievements.append({
                'type': 'streak_3',
                'title': '🔥 الملتزم',
                'description': '3 أيام متتالية',
                'icon': '🔥',
                'points': 30
            })
        
        if streak >= 7:
            potential_achievements.append({
                'type': 'streak_7',
                'title': '⚡ المستمر',
                'description': '7 أيام متتالية',
                'icon': '⚡',
                'points': 100
            })
        
        if streak >= 30:
            potential_achievements.append({
                'type': 'streak_30',
                'title': '💪 المثابر',
                'description': '30 يوم متتالي',
                'icon': '💪',
                'points': 500
            })
        
        if streak >= 90:
            potential_achievements.append({
                'type': 'streak_90',
                'title': '🏆 الأسطوري',
                'description': '90 يوم متتالي',
                'icon': '🏆',
                'points': 2000
            })
        
        # ===== إنجازات المستويات (عند الترقية فقط) =====
        if student_points and student_points['new_level'] > student_points['old_level']:
            new_level = student_points['new_level']
            
            if new_level == 2:
                potential_achievements.append({
                    'type': 'level_2',
                    'title': '🌱 مبتدئ',
                    'description': 'وصلت للمستوى 2',
                    'icon': '🌱',
                    'points': 25
                })
            elif new_level == 3:
                potential_achievements.append({
                    'type': 'level_3',
                    'title': '🌿 متقدم',
                    'description': 'وصلت للمستوى 3',
                    'icon': '🌿',
                    'points': 50
                })
            elif new_level == 4:
                potential_achievements.append({
                    'type': 'level_4',
                    'title': '🏆 محترف',
                    'description': 'وصلت للمستوى 4',
                    'icon': '🏆',
                    'points': 100
                })
            elif new_level == 5:
                potential_achievements.append({
                    'type': 'level_5',
                    'title': '🌳 خبير',
                    'description': 'وصلت للمستوى 5',
                    'icon': '🌳',
                    'points': 100
                })
        
        # ===== إنجازات خاصة =====
        # الطائر المبكر (أول اختبار قبل 8 صباحاً)
        if quiz_result.created_at.hour < 8:
            potential_achievements.append({
                'type': 'early_bird',
                'title': '🌅 الطائر المبكر',
                'description': 'أكمل اختبار قبل 8 صباحاً',
                'icon': '🌅',
                'points': 50
            })
        
        # البومة الليلية (اختبار بعد 10 مساءً)
        if quiz_result.created_at.hour >= 22:
            potential_achievements.append({
                'type': 'night_owl',
                'title': '🦉 البومة الليلية',
                'description': 'أكمل اختبار بعد 10 مساءً',
                'icon': '🦉',
                'points': 50
            })
        
        # سريع البرق (اختبار كامل في أقل من دقيقة)
        if quiz_result.time_spent and quiz_result.time_spent < 60 and quiz_result.score_percentage >= 90:
            potential_achievements.append({
                'type': 'speed_master',
                'title': '⚡ سريع البرق',
                'description': 'أكمل اختبار في أقل من دقيقة',
                'icon': '⚡',
                'points': 100
            })
        
        # ===== التحقق من كل إنجاز محتمل =====
        for ach_data in potential_achievements:
            # البحث عن الإنجاز في قاعدة البيانات
            achievement = Achievement.query.filter_by(
                achievement_type=ach_data['type']
            ).first()
            
            # إذا لم يكن موجوداً في القاعدة، سيتم إنشاؤه في save_achievements
            # لكن نتحقق إذا الطالب حصل عليه من قبل
            if achievement:
                # التحقق من عدم التكرار
                existing = StudentAchievement.query.filter_by(
                    student_id=student_id,
                    achievement_id=achievement.id
                ).first()
                
                if existing:
                    continue  # تخطي - الطالب حصل على هذا الإنجاز من قبل
            
            # إضافة الإنجاز الجديد
            achievements.append(ach_data)
        
    except Exception as e:
        print(f"      ⚠️ خطأ في check_achievements: {e}")
        import traceback
        traceback.print_exc()
    
    return achievements


def check_and_update_challenges(
    student_id: int, 
    quiz_result: StudentResult,
    student_points: dict
) -> list:
    """
    التحقق من التحديات وتحديثها (مع دعم Challenge الجديد)
    
    Returns:
        list: قائمة التحديات المكتملة للتو
    """
    completed_challenges = []
    
    try:
        # محاولة استخدام النظام الجديد أولاً
        try:
            from src.models.gamification import Challenge, StudentChallenge
            
            # استخدام النظام الجديد
            completed_challenges = _update_new_challenges(
                student_id, 
                quiz_result, 
                student_points
            )
            
        except ImportError:
            # النظام القديم (DailyChallenge)
            completed_challenges = _check_old_challenges(
                student_id, 
                quiz_result
            )
    
    except Exception as e:
        print(f"      ⚠️ خطأ في check_and_update_challenges: {e}")
    
    return completed_challenges


def _update_new_challenges(
    student_id: int,
    quiz_result: StudentResult,
    student_points: dict
) -> list:
    """تحديث التحديات باستخدام النظام الجديد (Challenge)"""
    from src.models.gamification import Challenge, StudentChallenge
    
    completed = []
    today = date.today()
    
    # جلب التحديات النشطة
    active_challenges = Challenge.query.filter(
        Challenge.is_active == True,
        db.or_(
            Challenge.start_date == None,
            Challenge.start_date <= today
        ),
        db.or_(
            Challenge.end_date == None,
            Challenge.end_date >= today
        )
    ).all()
    
    for challenge in active_challenges:
        # جلب أو إنشاء تقدم الطالب
        progress = StudentChallenge.query.filter_by(
            student_id=student_id,
            challenge_id=challenge.id
        ).first()
        
        if not progress:
            progress = StudentChallenge(
                student_id=student_id,
                challenge_id=challenge.id,
                progress=0,
                target=challenge.target_value,
                is_completed=False
            )
            db.session.add(progress)
            db.session.flush()
        
        # تخطي إذا كان مكتمل بالفعل
        if progress.is_completed:
            continue
        
        # تحديث التقدم حسب نوع التحدي
        should_update = False
        increment = 0
        
        if challenge.target_type == 'quiz_count':
            # عدد الاختبارات
            should_update = True
            increment = 1
        
        elif challenge.target_type == 'perfect_score':
            # درجات كاملة
            if quiz_result.score_percentage >= 100:
                should_update = True
                increment = 1
        
        elif challenge.target_type == 'streak':
            # السلسلة
            streak = update_streak(student_id)
            if streak >= challenge.target_value:
                progress.progress = streak
                should_update = True
        
        # تحديث التقدم
        if should_update and increment > 0:
            progress.progress += increment
        
        # التحقق من الإكمال
        if progress.progress >= progress.target and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = datetime.utcnow()
            
            # إضافة النقاط
            from src.models.gamification import StudentPoints, PointTransaction
            
            student_pts = StudentPoints.query.filter_by(student_id=student_id).first()
            if student_pts:
                student_pts.total_points += challenge.points
                student_pts.lifetime_points += challenge.points
                
                transaction = PointTransaction(
                    student_id=student_id,
                    amount=challenge.points,
                    reason=f"تحدي: {challenge.title}",
                    reference_type='challenge',
                    reference_id=challenge.id
                )
                db.session.add(transaction)
            
            completed.append({
                'type': challenge.code,
                'title': challenge.title,
                'description': challenge.description,
                'points': challenge.points,
                'icon': challenge.icon
            })
    
    db.session.commit()
    return completed


def _check_old_challenges(student_id: int, quiz_result: StudentResult) -> list:
    """التحقق من التحديات القديمة (DailyChallenge) - للتوافق"""
    challenges = []
    
    try:
        # تحدي 3 اختبارات في يوم واحد
        today = datetime.utcnow().date()
        today_quizzes = StudentResult.query.filter(
            StudentResult.student_id == student_id,
            db.func.date(StudentResult.created_at) == today
        ).count()
        
        if today_quizzes == 3:
            challenges.append({
                'type': 'daily_3_quizzes',
                'title': '🎯 تحدي اليوم',
                'description': '3 اختبارات في يوم واحد!',
                'points': 50,
                'icon': '🎯'
            })
        
        # تحدي درجة كاملة
        if quiz_result.score_percentage >= 100:
            # التحقق إذا كانت أول درجة كاملة اليوم
            perfect_today = StudentResult.query.filter(
                StudentResult.student_id == student_id,
                db.func.date(StudentResult.created_at) == today,
                StudentResult.score_percentage == 100
            ).count()
            
            if perfect_today == 1:
                challenges.append({
                    'type': 'daily_perfect',
                    'title': '⭐ تحدي الكمال',
                    'description': 'درجة كاملة اليوم!',
                    'points': 30,
                    'icon': '⭐'
                })
    
    except Exception as e:
        print(f"      ⚠️ خطأ في _check_old_challenges: {e}")
    
    return challenges


def save_achievements(student_id: int, achievements: list):
    """حفظ الإنجازات في القاعدة"""
    try:
        from src.models.gamification import (
            StudentAchievement, Achievement, StudentPoints, PointTransaction
        )
        
        for ach_data in achievements:
            # البحث عن الإنجاز
            achievement = Achievement.query.filter_by(
                achievement_type=ach_data['type']
            ).first()
            
            if not achievement:
                # إنشاء الإنجاز
                achievement = Achievement(
                    achievement_type=ach_data['type'],
                    title=ach_data['title'],
                    description=ach_data['description'],
                    icon=ach_data['icon'],
                    points=ach_data['points']
                )
                db.session.add(achievement)
                db.session.flush()
            
            # التحقق من عدم التكرار
            existing = StudentAchievement.query.filter_by(
                student_id=student_id,
                achievement_id=achievement.id
            ).first()
            
            if not existing:
                student_achievement = StudentAchievement(
                    student_id=student_id,
                    achievement_id=achievement.id,
                    unlocked_at=datetime.utcnow()
                )
                
                # إذا كان الحقل موجود
                if hasattr(student_achievement, 'is_unlocked'):
                    student_achievement.is_unlocked = True
                
                db.session.add(student_achievement)
                
                # إضافة النقاط
                student_points = StudentPoints.query.filter_by(
                    student_id=student_id
                ).first()
                
                if student_points:
                    student_points.total_points += ach_data['points']
                    student_points.lifetime_points += ach_data['points']
                    
                    transaction = PointTransaction(
                        student_id=student_id,
                        amount=ach_data['points'],
                        reason=f"إنجاز: {ach_data['title']}",
                        reference_type='achievement',
                        reference_id=achievement.id
                    )
                    db.session.add(transaction)
        
        db.session.commit()
        
    except Exception as e:
        print(f"      ⚠️ خطأ في save_achievements: {e}")
        db.session.rollback()


def send_notification(
    student: Student,
    quiz_result: StudentResult,
    points_earned: int,
    student_points: dict,
    streak: int,
    achievements: list,
    challenges: list
):
    """إرسال إشعار واحد شامل"""
    try:
        from src.models.notification import Notification
        
        # بناء العنوان
        score = quiz_result.score_percentage
        
        if score >= 100:
            title = f"🎉 ماشاء الله {student.name}! درجة كاملة!"
        elif score >= 90:
            title = f"⭐ ممتاز {student.name}! أداء رائع!"
        elif score >= 80:
            title = f"👏 أحسنت {student.name}! استمر!"
        elif score >= 70:
            title = f"👍 جيد {student.name}! يمكنك التحسن!"
        else:
            title = f"💪 {student.name}، لا تستسلم!"
        
        # بناء الجسم
        body_parts = []
        
        # النتيجة
        body_parts.append(f"حصلت على {score:.0f}%")
        
        # النقاط
        if student_points:
            body_parts.append(f"\n💎 +{points_earned} نقطة • إجمالي: {student_points['new_points']} نقطة")
            body_parts.append(f"⭐ المستوى: {student_points['new_level']}")
        else:
            body_parts.append(f"\n💎 +{points_earned} نقطة")
        
        # السلسلة
        if streak > 0:
            body_parts.append(f"🔥 السلسلة: {streak} يوم")
        
        # الإنجازات (أول 2 فقط)
        if achievements:
            body_parts.append("")
            body_parts.append("🏆 إنجازات جديدة:")
            for ach in achievements[:2]:
                body_parts.append(f"✨ {ach['title']}!")
        
        # التحديات
        if challenges:
            body_parts.append("")
            for ch in challenges:
                body_parts.append(f"🎯 أكملت: {ch['title']}!")
        
        # رسالة تحفيزية
        if score >= 80:
            body_parts.append("")
            body_parts.append("استمر على هذا الأداء الرائع! 🌟")
        elif score >= 60:
            body_parts.append("")
            body_parts.append("جيد! حاول تحسين النتيجة المرة القادمة! 💪")
        
        body = "\n".join(body_parts)
        
        # إنشاء الإشعار في جدول notifications
        notification = Notification(
            student_id=student.id,
            title=title,
            body=body,
            message=body,
            notification_type='quiz_completed',
            type='success' if score >= 80 else 'info',
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.flush()  # للحصول على notification.id
        
        # ✅ إضافة السجل في student_notifications
        try:
            db.session.execute(
                db.text("""
                    INSERT INTO student_notifications 
                    (student_id, notification_id, is_read, created_at)
                    VALUES (:student_id, :notification_id, FALSE, NOW())
                """),
                {
                    'student_id': student.id,
                    'notification_id': notification.id
                }
            )
        except Exception as e:
            print(f"      ⚠️ فشل إضافة في student_notifications: {e}")
        
        db.session.commit()
        
        print(f"      ✅ تم إنشاء إشعار: {title}")
        
        # محاولة إرسال FCM
        try:
            from src.services.notification_service import send_fcm_notification
            
            if hasattr(student, 'fcm_token') and student.fcm_token:
                send_fcm_notification(student.fcm_token, title, body)
                print(f"      ✅ تم إرسال FCM")
        except Exception as e:
            print(f"      ⚠️ فشل إرسال FCM: {e}")
        
    except Exception as e:
        print(f"      ❌ خطأ في إرسال الإشعار: {e}")
        import traceback
        traceback.print_exc()
