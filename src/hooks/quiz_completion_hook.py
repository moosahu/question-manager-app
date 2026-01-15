# src/hooks/quiz_completion_hook.py
"""
Hook موحد يتم تشغيله عند إكمال الطالب لاختبار

يتولى:
1. تحديث النقاط في student_points table
2. التحقق من الإنجازات والتحديات
3. إرسال إشعار ذكي واحد (بدون تكرار)
"""

from datetime import datetime, timedelta
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
            print(f"   ⭐ المستوى: {student_points['old_level']} → {student_points['new_level']}")
        
        # 4. حساب السلسلة
        print("   3️⃣ حساب السلسلة...")
        streak = calculate_streak(student_id)
        print(f"   🔥 السلسلة: {streak} يوم")
        
        # 5. التحقق من الإنجازات
        print("   4️⃣ التحقق من الإنجازات...")
        achievements = check_achievements(student_id, quiz_result, student_points)
        
        if achievements:
            print(f"   🏆 فتح {len(achievements)} إنجاز جديد:")
            for ach in achievements:
                print(f"      - {ach['title']} (+{ach['points']} نقطة)")
        
        # 6. التحقق من التحديات
        print("   5️⃣ التحقق من التحديات...")
        challenges = check_challenges(student_id, quiz_result)
        
        if challenges:
            print(f"   🎯 أكمل {len(challenges)} تحدي:")
            for ch in challenges:
                print(f"      - {ch['title']} (+{ch['points']} نقطة)")
        
        # 7. إرسال إشعار ذكي واحد فقط
        print("   6️⃣ إرسال الإشعار...")
        send_notification(
            student=student,
            quiz_result=quiz_result,
            points_earned=points_earned,
            student_points=student_points,
            streak=streak,
            achievements=achievements,
            challenges=challenges
        )
        
        print(f"\n{'='*60}")
        print(f"🎉 اكتملت معالجة الاختبار بنجاح!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ خطأ في on_quiz_completed: {e}")
        import traceback
        traceback.print_exc()


def calculate_points(quiz_result: StudentResult) -> int:
    """حساب النقاط المكتسبة من الاختبار"""
    base_points = 20
    bonus_points = 0
    
    score = quiz_result.score_percentage
    
    # بونص حسب الدرجة
    if score == 100:
        bonus_points += 10
    elif score >= 90:
        bonus_points += 5
    elif score >= 80:
        bonus_points += 3
    
    # بونص للسرعة (أقل من دقيقة)
    if quiz_result.time_spent and quiz_result.time_spent < 60:
        bonus_points += 2
    
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
        
        # حساب المستوى الجديد (بدون حفظه في القاعدة)
        new_level = calculate_level(student_points.total_points)
        
        # حفظ transaction
        transaction = PointTransaction(
            student_id=student_id,
            amount=points_earned,
            reason=f"إكمال اختبار: {quiz_result.quiz_name}",
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


def calculate_streak(student_id: int) -> int:
    """حساب عدد الأيام المتتالية"""
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
        print(f"      ⚠️ خطأ في calculate_streak: {e}")
        return 0


def check_achievements(student_id: int, quiz_result: StudentResult, student_points: dict) -> list:
    """
    التحقق من الإنجازات المفتوحة
    
    Returns:
        قائمة بالإنجازات المفتوحة
    """
    achievements = []
    
    try:
        # إنجاز الدرجة الكاملة
        if quiz_result.score_percentage == 100:
            achievements.append({
                'type': 'perfect_score',
                'title': 'الكمال',
                'description': 'حصلت على درجة كاملة!',
                'points': 10,
                'icon': '🏆'
            })
        
        # إنجاز 10 اختبارات
        total_quizzes = StudentResult.query.filter_by(
            student_id=student_id
        ).count()
        
        if total_quizzes == 10:
            achievements.append({
                'type': 'quiz_master_10',
                'title': 'خبير الاختبارات',
                'description': 'أكملت 10 اختبارات!',
                'points': 25,
                'icon': '📚'
            })
        
        # إنجاز سلسلة 7 أيام
        streak = calculate_streak(student_id)
        if streak == 7:
            achievements.append({
                'type': 'streak_7',
                'title': 'أسبوع متواصل',
                'description': 'سلسلة 7 أيام متتالية!',
                'points': 50,
                'icon': '🔥'
            })
        
        # حفظ الإنجازات
        if achievements:
            save_achievements(student_id, achievements)
        
    except Exception as e:
        print(f"      ⚠️ خطأ في check_achievements: {e}")
    
    return achievements


def check_challenges(student_id: int, quiz_result: StudentResult) -> list:
    """التحقق من التحديات المكتملة"""
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
                'title': 'تحدي اليوم',
                'description': '3 اختبارات في يوم واحد!',
                'points': 50,
                'icon': '🎯'
            })
        
    except Exception as e:
        print(f"      ⚠️ خطأ في check_challenges: {e}")
    
    return challenges


def save_achievements(student_id: int, achievements: list):
    """حفظ الإنجازات في القاعدة"""
    try:
        from src.models.gamification import (
            StudentAchievement, Achievement, StudentPoints
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
                db.session.add(student_achievement)
                
                # إضافة النقاط
                student_points = StudentPoints.query.filter_by(
                    student_id=student_id
                ).first()
                if student_points:
                    student_points.total_points += ach_data['points']
        
        db.session.commit()
        
    except Exception as e:
        print(f"      ⚠️ خطأ في save_achievements: {e}")
        db.session.rollback()


def send_notification(student, quiz_result, points_earned, 
                     student_points, streak, achievements, challenges):
    """
    إرسال إشعار واحد شامل
    """
    try:
        from src.models.notification import Notification
        
        # عنوان الإشعار
        score = quiz_result.score_percentage
        if score == 100:
            title = "🎉 ماشاء الله! درجة كاملة!"
        elif score >= 90:
            title = "⭐ ممتاز! أداء رائع!"
        elif score >= 80:
            title = "💪 أحسنت! أداء جيد جداً!"
        else:
            title = "👍 جيد! استمر!"
        
        # محتوى الإشعار
        body_parts = [
            f"حليت \"{quiz_result.quiz_name}\" بنسبة {score:.0f}%!",
            ""
        ]
        
        # معلومات النقاط
        if student_points:
            body_parts.append(f"💎 +{points_earned} نقطة • إجمالي: {student_points['new_points']} نقطة")
            body_parts.append(f"⭐ المستوى: {student_points['new_level']}")
        else:
            body_parts.append(f"💎 +{points_earned} نقطة")
        
        # السلسلة
        if streak > 0:
            body_parts.append(f"🔥 السلسلة: {streak} يوم")
        
        # الإنجازات
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
