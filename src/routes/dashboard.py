from datetime import datetime
from sqlalchemy import desc
from src.models.course import Course
from src.models.unit import Unit
from src.models.lesson import Lesson
from src.models.question import Question
from src.extensions import db

# دالة مساعدة لتحويل الوقت إلى صيغة نصية مناسبة
def format_time_ago(timestamp):
    time_diff = datetime.utcnow() - timestamp
    if time_diff.days > 0:
        return f"منذ {time_diff.days} يوم"
    elif time_diff.seconds // 3600 > 0:
        return f"منذ {time_diff.seconds // 3600} ساعة"
    else:
        return f"منذ {time_diff.seconds // 60} دقيقة"

# دالة لجلب بيانات لوحة التحكم
def get_dashboard_data():
    # جلب البيانات الإحصائية
    courses_count = Course.query.count()
    units_count = Unit.query.count()
    lessons_count = Lesson.query.count()
    questions_count = Question.query.count()
    
    # جلب الأسئلة الأخيرة
    recent_questions = []
    questions = Question.query.order_by(desc(Question.created_at)).limit(4).all()
    for question in questions:
        lesson = Lesson.query.get(question.lesson_id)
        lesson_name = lesson.name if lesson else "غير محدد"
        recent_questions.append({
            'id': question.id,
            'text': question.text,
            'lesson_name': lesson_name
        })
    
    # إنشاء بيانات النشاط الأخير (يمكن استبدالها بنموذج Activity إذا كان موجوداً)
    recent_activities = [
        {
            'description': "تمت إضافة سؤال جديد في درس 'خواص المادة'",
            'icon': "fa-plus-circle",
            'time': "منذ 5 دقائق"
        },
        {
            'description': "تم تعديل سؤال في درس 'قصة مادتين'",
            'icon': "fa-edit",
            'time': "منذ 30 دقيقة"
        },
        {
            'description': "تم استيراد 10 أسئلة جديدة إلى درس 'مقدمة في علم الكيمياء'",
            'icon': "fa-file-import",
            'time': "منذ ساعتين"
        },
        {
            'description': "تم حذف سؤال من درس 'المادة الخواص والتغيرات'",
            'icon': "fa-trash-alt",
            'time': "منذ 3 ساعات"
        }
    ]
    
    return {
        'courses_count': courses_count,
        'units_count': units_count,
        'lessons_count': lessons_count,
        'questions_count': questions_count,
        'recent_questions': recent_questions,
        'recent_activities': recent_activities
    }
