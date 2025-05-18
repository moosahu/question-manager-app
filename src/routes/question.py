# تعديل نهائي لملف question.py لإضافة تسجيل النشاط بطريقة آمنة

# أضف هذا الاستيراد في بداية الملف (بعد استيرادات النماذج الأخرى):
from src.models.activity import Activity  # استيراد نموذج النشاط

# ابحث عن دالة import_questions وأضف الكود التالي بعد السطر:
# if imported_count > 0:
#     db.session.commit()
#     current_app.logger.info(f"Successfully imported {imported_count} questions.")

# أضف هذا الكود مباشرة بعد السطر المذكور أعلاه:
                # تسجيل نشاط استيراد الأسئلة (في كتلة try-except منفصلة)
                try:
                    lesson = Lesson.query.get(lesson_id)
                    lesson_name = lesson.name if lesson else None
                    unit_name = lesson.unit.name if lesson and lesson.unit else None
                    course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
                    
                    Activity.log_activity(
                        action_type="import",
                        entity_type="question",
                        entity_id=None,
                        description=f"تم استيراد {imported_count} سؤال من ملف",
                        lesson_name=lesson_name,
                        unit_name=unit_name,
                        course_name=course_name,
                        user_id=current_user.id if current_user.is_authenticated else None
                    )
                    current_app.logger.info("Activity logged successfully for question import.")
                except Exception as activity_error:
                    # تسجيل الخطأ فقط دون التأثير على تدفق الدالة
                    current_app.logger.error(f"Error logging activity for question import: {activity_error}")
                    # لا نقوم بإعادة رفع الاستثناء هنا لتجنب التأثير على تدفق الدالة

# لا تغير أي شيء آخر في الملف
