# src/hooks/quiz_completion_hook.py
"""
Hook يتم تشغيله عند إكمال الطالب لاختبار
يتولى:
1. منح النقاط
2. التحقق من الإنجازات
3. التحقق من التحديات
4. إرسال الإشعارات
"""

from src.models.student_result import StudentResult
from src.services.gamification_service import gamification_service
from src.services.smart_notifications import smart_notifications


def on_quiz_completed(student_id: int, quiz_result: StudentResult):
    """
    يتم استدعاؤه بعد حفظ نتيجة الاختبار في قاعدة البيانات
    
    Args:
        student_id: رقم الطالب
        quiz_result: نتيجة الاختبار
    """
    try:
        print(f"🎯 معالجة إكمال اختبار للطالب {student_id}")
        
        # 1. منح النقاط
        print("   1️⃣ منح النقاط...")
        points_result = gamification_service.award_points_for_quiz(
            student_id, quiz_result
        )
        
        if points_result['success']:
            print(f"   ✅ منح {points_result['points_awarded']} نقطة")
            print(f"   💰 الإجمالي: {points_result['total_points']} نقطة")
            
            # 2. التحقق من الإنجازات المفتوحة
            achievements = points_result.get('achievements_unlocked', [])
            if achievements:
                print(f"   🏆 فتح {len(achievements)} إنجاز جديد!")
                for ach in achievements:
                    print(f"      - {ach['title']} (+{ach['points']} نقطة)")
                    
                    # إرسال إشعار بالإنجاز
                    smart_notifications.send_achievement_notification(
                        student_id, ach
                    )
            
            # 3. التحقق من إكمال تحدي اليوم
            print("   3️⃣ التحقق من تحدي اليوم...")
            challenge_result = gamification_service.check_challenge_completion(
                student_id, quiz_result
            )
            
            if challenge_result:
                print(f"   🎉 أكمل تحدي اليوم!")
                print(f"      {challenge_result['title']} (+{challenge_result['points_awarded']} نقطة)")
                
                # إرسال إشعار بالإكمال
                smart_notifications.send_challenge_completion_notification(
                    student_id, challenge_result
                )
        
        print(f"   ✅ اكتملت معالجة الاختبار بنجاح")
        
    except Exception as e:
        print(f"   ❌ خطأ في on_quiz_completed: {e}")
        import traceback
        traceback.print_exc()


# مثال على الاستخدام في route حفظ الاختبار:
"""
# في ملف routes/quiz_routes.py أو المكان الذي يحفظ فيه نتائج الاختبارات

from src.hooks.quiz_completion_hook import on_quiz_completed

@quiz_bp.route('/submit', methods=['POST'])
def submit_quiz():
    # ... كود حفظ الاختبار ...
    
    # حفظ النتيجة
    result = StudentResult(
        student_id=student_id,
        quiz_name=quiz_name,
        score_percentage=score,
        # ...
    )
    db.session.add(result)
    db.session.commit()
    
    # 🎯 تشغيل الـ Hook
    on_quiz_completed(student_id, result)
    
    return jsonify({'success': True, 'result': result.to_dict()})
"""
