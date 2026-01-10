# src/models/result.py

# Alias for StudentResult to maintain compatibility with reports.py

try:
    # في حالة استخدام هيكلية الحزم مع src.
    from src.models.student_result import StudentResult as Result
except ImportError:
    # في حالة الاستيراد المباشر من نفس المجلد
    from student_result import StudentResult as Result
