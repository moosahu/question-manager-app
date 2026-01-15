# src/hooks/quiz_completion_hook.py
"""
Hook موحد يتم تشغيله عند إكمال الطالب لاختبار

يتولى:
1. تحديث النقاط والمستوى في students table (مباشرة)
2. زامن مع student_points (للتوافق الخلفي)
3. التحقق من الإنجازات والتحديات
4. إرسال إشعار ذكي واحد (بدون تكرار)
"""

from datetime import datetime, timedelta
from src.extensions import db
from src.models import Student
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
        
        # 3. تحديث students table مباشرة
        print("   2️⃣ تحديث جدول students...")
        old_points = student.total_points or 0
        old_level = student.level or 1
        
        student.total_points = old_points + points_earned
        student.level = calculate_level(student.total_points)
        
        # تحديث السلسلة
        update_streak(student)
        
        # تحديث آخر نشاط
        student.last_activity = datetime.utcnow()
        
        print(f"   📊 النقاط: {old_points} → {student.total_points}")
        print(f"   ⭐ المستوى: {old_level} → {student.level}")
        print(f"   🔥 السلسلة: {student.current_streak} يوم")
        
        # 4. زامن مع student_points (للتوافق الخلفي)
        print("   3️⃣ زامن مع student_points...")
        sync_with_student_points(student_id, points_earned, quiz_result)
        
        # 5. حفظ التغييرات
        db.session.commit()
        print(f"   ✅ تم حفظ التغييرات")
        
        # 6. التحقق من الإنجازات
        print("   4️⃣ التحقق من الإنجازات...")
        achievements = check_achievements(student, quiz_result)
        
        if achievements:
            print(f"   🏆 فتح {len(achievements)} إنجاز جديد:")
            for ach in achievements:
                print(f"      - {ach['title']} (+{ach['points']} نقطة)")
        
        # 7. التحقق من التحديات
        print("   5️⃣ التحقق من التحديات...")
        challenges = check_challenges(student_id, quiz_result)
        
        if challenges:
            print(f"   🎯 أكمل {len(challenges)} تحدي:")
            for ch in challenges:
                print(f"      - {ch['title']} (+{ch['points']} نقطة)")
        
        # 8. إرسال إشعار ذكي واحد فقط
        print("   6️⃣ إرسال الإشعار...")
        send_smart_notification(
            student=student,
            quiz_result=quiz_result,
            points_earned=points_earned,
            level_up=(student.level > old_level),
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
    
    # بونص للسرعة
    if quiz_result.time_spent and quiz_result.time_spent < 60:
        bonus_points += 2
    
    return base_points + bonus_points


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


def update_streak(student: Student):
    """تحديث سلسلة الأيام المتتالية"""
    today = datetime.utcnow().date()
    
    if student.last_activity:
        last_day = student.last_activity.date()
        days_diff = (today - last_day).days
        
        if days_diff == 0:
            # نفس اليوم
            pass
        elif days_diff == 1:
            # أمس - زود السلسلة
            student.current_streak = (student.current_streak or 0) + 1
            student.longest_streak = max(
                student.longest_streak or 0,
                student.current_streak
            )
        else:
            # انقطعت
            student.current_streak = 1
    else:
        # أول نشاط
        student.current_streak = 1
        student.longest_streak = 1


def sync_with_student_points(student_id: int, points_earned: int, quiz_result: StudentResult):
    """
    زامن النقاط مع جدول student_points (للتوافق الخلفي)
    """
    try:
        from src.models.gamification import StudentPoints
        
        # جلب أو إنشاء سجل
        student_points = StudentPoints.query.filter_by(student_id=student_id).first()
        
        if not student_points:
            student_points = StudentPoints(
                student_id=student_id,
                total_points=points_earned,
                lifetime_points=points_earned
            )
            db.session.add(student_points)
        else:
            student_points.total_points += points_earned
            student_points.lifetime_points += points_earned
        
        # حفظ في point_transactions
        from src.models.gamification import PointTransaction
        transaction = PointTransaction(
            student_id=student_id,
            amount=points_earned,
            reason=f"إكمال اختبار: {quiz_result.quiz_name}",
            reference_type='quiz',
            reference_id=quiz_result.id
        )
        db.session.add(transaction)
        
        print(f"      ✅ تم الزامن مع student_points")
        
    except Exception as e:
        print(f"      ⚠️ فشل الزامن مع student_points: {e}")


def check_achievements(student: Student, quiz_result: StudentResult) -> list:
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
            student_id=student.id
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
        if student.current_streak == 7:
            achievements.append({
                'type': 'streak_7',
                'title': 'أسبوع متواصل',
                'description': 'سلسلة 7 أيام متتالية!',
                'points': 50,
                'icon': '🔥'
            })
        
        # حفظ الإنجازات في القاعدة (لو موجود نظام achievements)
        if achievements:
            save_achievements(student.id, achievements)
        
    except Exception as e:
        print(f"      ⚠️ خطأ في check_achievements: {e}")
    
    return achievements


def check_challenges(student_id: int, quiz_result: StudentResult) -> list:
    """
    التحقق من التحديات المكتملة
    
    Returns:
        قائمة بالتحديات المكتملة
    """
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
        from src.models.gamification import StudentAchievement, Achievement
        
        for ach_data in achievements:
            # البحث عن الإنجاز
            achievement = Achievement.query.filter_by(
                achievement_type=ach_data['type']
            ).first()
            
            if not achievement:
                # إنشاء الإنجاز إذا لم يكن موجوداً
                achievement = Achievement(
                    achievement_type=ach_data['type'],
                    title=ach_data['title'],
                    description=ach_data['description'],
                    icon=ach_data['icon'],
                    points=ach_data['points']
                )
                db.session.add(achievement)
                db.session.flush()
            
            # التحقق من عدم تكرار الإنجاز
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
                student = Student.query.get(student_id)
                if student:
                    student.total_points = (student.total_points or 0) + ach_data['points']
        
        db.session.commit()
        
    except Exception as e:
        print(f"      ⚠️ خطأ في save_achievements: {e}")


def send_smart_notification(student, quiz_result, points_earned, 
                            level_up, achievements, challenges):
    """
    إرسال إشعار ذكي واحد يجمع كل المعلومات
    """
    try:
        # محاولة استخدام smart_notifications (AI)
        try:
            from src.services.smart_notifications import smart_notifications
            
            # إرسال إشعار ذكي بتحليل AI
            smart_notifications.send_quiz_completion_notification(
                student_id=student.id,
                quiz_result=quiz_result,
                points_earned=points_earned,
                level_up=level_up,
                achievements=achievements,
                challenges=challenges
            )
            print(f"      ✅ تم إرسال إشعار ذكي (AI)")
            return
            
        except ImportError:
            print(f"      ⚠️ smart_notifications غير متاح، استخدام الإشعار العادي")
        
        # البديل: إشعار عادي
        from src.models.notification import Notification
        
        # عنوان الإشعار
        if quiz_result.score_percentage == 100:
            title = "🎉 ماشاء الله! درجة كاملة!"
        elif quiz_result.score_percentage >= 80:
            title = "💪 أحسنت! أداء ممتاز!"
        else:
            title = "👍 جيد! استمر!"
        
        # محتوى الإشعار
        body_parts = [
            f"حليت \"{quiz_result.quiz_name}\" بنسبة {quiz_result.score_percentage:.0f}%!",
            "",
            f"💎 +{points_earned} نقطة • إجمالي: {student.total_points} نقطة",
            f"⭐ المستوى: {student.level} • 🔥 السلسلة: {student.current_streak} يوم"
        ]
        
        # إضافة الإنجازات
        if achievements:
            body_parts.append("")
            body_parts.append("🏆 إنجازات جديدة:")
            for ach in achievements[:2]:  # أول 2 فقط
                body_parts.append(f"✨ {ach['title']}!")
        
        # إضافة التحديات
        if challenges:
            body_parts.append("")
            for ch in challenges:
                body_parts.append(f"🎯 أكملت: {ch['title']}!")
        
        # إضافة رسالة تحفيزية
        if quiz_result.score_percentage >= 80:
            body_parts.append("")
            body_parts.append("استمر على هذا الأداء الرائع! 🌟")
        
        body = "\n".join(body_parts)
        
        # إنشاء الإشعار
        notification = Notification(
            student_id=student.id,
            title=title,
            body=body,
            message=body,
            notification_type='quiz_completed',
            type='success' if quiz_result.score_percentage >= 80 else 'info',
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
        
        print(f"      ✅ تم إنشاء إشعار عادي: {title}")
        
        # محاولة إرسال FCM
        try:
            from src.services.notification_service import send_fcm_notification
            
            if student.fcm_token:
                send_fcm_notification(student.fcm_token, title, body)
                print(f"      ✅ تم إرسال FCM")
        except Exception as e:
            print(f"      ⚠️ فشل إرسال FCM: {e}")
        
    except Exception as e:
        print(f"      ❌ خطأ في إرسال الإشعار: {e}")
        import traceback
        traceback.print_exc()
