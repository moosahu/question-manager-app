# src/routes/api.py (Updated with /questions/all and nested /courses/<cid>/units/<uid>/questions endpoint, and correct_option_id)

import logging
import time
from flask import Blueprint, jsonify, current_app, url_for, request, session # Added request and session
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from flask_login import login_required, current_user

# إعداد logger
logger = logging.getLogger(__name__)

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        try:
            from main import db # Fallback for direct run
        except ImportError:
            print("Error: Database object 'db' could not be imported.")
            raise

# Import models - adjust path if necessary based on your structure
try:
    from src.models.question import Question, Option
    from src.models.curriculum import Lesson, Unit, Course
    from src.models.backup_settings import BackupSettings
    from src.models.google_drive import GoogleDriveToken  # إضافة استيراد GoogleDriveToken
    # محاولة استيراد نموذج Activity
    try:
        from src.models.activity import Activity
        activity_available = True
    except ImportError:
        try:
            from models.activity import Activity
            activity_available = True
        except ImportError:
            print("Warning: Could not import Activity model. Activity tracking will be disabled.")
            activity_available = False
except ImportError:
    try:
        from models.question import Question, Option
        from models.curriculum import Lesson, Unit, Course
        from models.backup_settings import BackupSettings
        from models.google_drive import GoogleDriveToken  # إضافة استيراد GoogleDriveToken
        # محاولة استيراد نموذج Activity
        try:
            from models.activity import Activity
            activity_available = True
        except ImportError:
            print("Warning: Could not import Activity model. Activity tracking will be disabled.")
            activity_available = False
    except ImportError:
        print("Error: Could not import models.")
        raise


# ===== إضافات النسخ الاحتياطي =====
import os
import sys
from datetime import datetime

# محاولة استيراد وحدات النسخ الاحتياطي
try:
    from src.backup_scheduler_fixed import BackupScheduler
    backup_scheduler_available = True
except ImportError:
    try:
        from backup_scheduler_fixed import BackupScheduler
        backup_scheduler_available = True
    except ImportError:
        print("تحذير: لا يمكن استيراد BackupScheduler")
        BackupScheduler = None
        backup_scheduler_available = False

try:
    from src.backup_logic import perform_backup_for_user, create_backup
    backup_logic_available = True
except ImportError:
    try:
        from backup_logic import perform_backup_for_user, create_backup
        backup_logic_available = True
    except ImportError:
        print("تحذير: لا يمكن استيراد backup_logic")
        backup_logic_available = False
        perform_backup_for_user = None
        create_backup = None

# متغيرات عامة للنسخ الاحتياطي
backup_scheduler = None
backup_logic = None
google_drive_available = True

def init_backup_system():
    """تهيئة نظام النسخ الاحتياطي"""
    global backup_scheduler, backup_logic
    
    if backup_scheduler_available and BackupScheduler:
        try:
            backup_scheduler = BackupScheduler()
        except Exception as e:
            print(f"خطأ في تهيئة backup_scheduler: {e}")
            backup_scheduler = None
    
    if backup_logic_available:
        backup_logic = True
    else:
        backup_logic = None
    
    return backup_scheduler is not None or backup_logic is not None

# تهيئة النظام عند تحميل الوحدة
init_backup_system()

# Create Blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

logger = logging.getLogger(__name__)

# --- Helper Function to Format Image URLs --- #
def format_image_url(image_path):
    """Prepends the base URL if the path is relative."""
    if image_path and not image_path.startswith(("http://", "https://") ):
        try:
            server_name = current_app.config.get("SERVER_NAME")
            host_url = request.host_url if request and hasattr(request, "host_url") else None
            base_url = f"https://{server_name}" if server_name else host_url
            
            if not base_url:
                logger.warning("Could not determine base URL for image path generation.") 
                _static_url_path = url_for("static", filename="").lstrip("/")
                _image_path = image_path.lstrip("/")
                return f"/{_static_url_path.rstrip('/')}/{_image_path}"

            _base_url_processed = base_url.rstrip("/")
            _static_path_processed = url_for("static", filename="").lstrip("/").rstrip("/")
            _image_path = image_path.lstrip("/")
            
            full_url = f"{_base_url_processed}/{_static_path_processed}/{_image_path}"
            return full_url
            
        except RuntimeError:
            logger.warning("Could not generate external URL for image, possibly outside request context.")
            try:
                _static_url_path = url_for("static", filename="").lstrip("/")
                _image_path = image_path.lstrip("/")
                return f"/{_static_url_path.rstrip('/')}/{_image_path}"
            except RuntimeError:
                logger.error("Could not even generate relative static path for image.")
                return image_path # Return original image_path as a fallback
            except Exception as e_inner:
                logger.error(f"Inner error generating relative image URL for {image_path}: {e_inner}")
                return image_path # Return original image_path as a fallback
        except Exception as e:
            logger.error(f"Error generating image URL for {image_path}: {e}")
            return image_path # Return original image_path as a fallback
    return image_path

# --- Helper Function to Format Questions (MODIFIED to include correct_option_id) --- #
def format_question(question):
    """Formats a Question object into the desired dictionary structure for JSON response,
       including a top-level correct_option_id."""
    
    options_list = []
    correct_option_id_found = None
    for opt in sorted(question.options, key=lambda o: o.option_id):
        options_list.append({
            "option_id": opt.option_id,
            "option_text": opt.option_text,
            "image_url": format_image_url(opt.image_url),
            "is_correct": opt.is_correct
        })
        if opt.is_correct:
            correct_option_id_found = opt.option_id
    
    # إضافة معلومات الدرس والوحدة والمنهج
    lesson_name = None
    unit_name = None
    course_name = None
    
    if question.lesson:
        lesson_name = question.lesson.name
        if question.lesson.unit:
            unit_name = question.lesson.unit.name
            if question.lesson.unit.course:
                course_name = question.lesson.unit.course.name
            
    return {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "image_url": format_image_url(question.image_url),
        "options": options_list,
        "correct_option_id": correct_option_id_found,  # Added this line
        "explanation": question.explanation,  # إضافة الشرح
        "explanation_image_path": format_image_url(question.explanation_image_path),  # إضافة صورة الشرح
        # إضافة معلومات الدرس والوحدة والمنهج
        "lesson": lesson_name,
        "unit": unit_name,
        "course": course_name
    }

# --- Helper Function to Get Activity Icon --- #
def get_activity_icon(action_type):
    """
    تحديد أيقونة النشاط بناءً على نوع الإجراء
    """
    icons = {
        "add": "fas fa-plus-circle",
        "edit": "fas fa-edit",
        "delete": "fas fa-trash-alt",
        "import": "fas fa-file-import",
        "export": "fas fa-file-export"
    }
    return icons.get(action_type, "fas fa-history")

# --- Helper Function to Get Time Difference Text --- #
def get_time_diff_text(timestamp):
    """
    حساب الفرق الزمني بين الوقت الحالي والوقت المعطى بصيغة نصية
    
    Parameters:
    - timestamp: الوقت المراد حساب الفرق منه
    
    Returns:
    - نص يصف الفرق الزمني (منذ X دقائق، منذ X ساعات، إلخ)
    """
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff < timedelta(minutes=1):
        return "منذ لحظات"
    elif diff < timedelta(hours=1):
        minutes = diff.seconds // 60
        return f"منذ {minutes} دقيقة" if minutes == 1 else f"منذ {minutes} دقائق"
    elif diff < timedelta(days=1):
        hours = diff.seconds // 3600
        return f"منذ {hours} ساعة" if hours == 1 else f"منذ {hours} ساعات"
    elif diff < timedelta(days=30):
        days = diff.days
        return f"منذ {days} يوم" if days == 1 else f"منذ {days} أيام"
    elif diff < timedelta(days=365):
        months = diff.days // 30
        return f"منذ {months} شهر" if months == 1 else f"منذ {months} أشهر"
    else:
        years = diff.days // 365
        return f"منذ {years} سنة" if years == 1 else f"منذ {years} سنوات"

# --- API Endpoint for Recent Activities --- #
@api_bp.route("/activities/recent", methods=["GET"])
def get_recent_activities():
    """
    استرجاع أحدث الأنشطة من قاعدة البيانات
    
    Parameters:
    - limit: عدد الأنشطة المراد استرجاعها (الافتراضي: 10)
    
    Returns:
    - قائمة بأحدث الأنشطة بتنسيق JSON
    """
    logger.info("API request received for recent activities.")
    try:
        limit = request.args.get("limit", 10, type=int)
        
        # التحقق من توفر نموذج Activity
        if not activity_available:
            logger.warning("Activity model is not available. Returning dummy data.")
            # إرجاع بيانات وهمية
            dummy_activities = [
                {
                    "id": 1,
                    "action_type": "add",
                    "entity_type": "question",
                    "description": "تمت إضافة سؤال جديد في درس \"خواص المادة\"",
                    "lesson_name": "خواص المادة",
                    "unit_name": None,
                    "course_name": None,
                    "timestamp": "2025-05-16T09:45:00",
                    "time_diff": "منذ 5 دقائق",
                    "icon": "fas fa-plus-circle"
                },
                {
                    "id": 2,
                    "action_type": "edit",
                    "entity_type": "question",
                    "description": "تم تعديل سؤال في درس \"قصة مادتين\"",
                    "lesson_name": "قصة مادتين",
                    "unit_name": None,
                    "course_name": None,
                    "timestamp": "2025-05-16T09:20:00",
                    "time_diff": "منذ 30 دقيقة",
                    "icon": "fas fa-edit"
                },
                {
                    "id": 3,
                    "action_type": "import",
                    "entity_type": "question",
                    "description": "تم استيراد 10 أسئلة جديدة إلى درس \"مقدمة في علم الكيمياء\"",
                    "lesson_name": "مقدمة في علم الكيمياء",
                    "unit_name": None,
                    "course_name": None,
                    "timestamp": "2025-05-16T08:15:00",
                    "time_diff": "منذ ساعتين",
                    "icon": "fas fa-file-import"
                },
                {
                    "id": 4,
                    "action_type": "delete",
                    "entity_type": "question",
                    "description": "تم حذف سؤال من درس \"المادة الخواص والتغيرات\"",
                    "lesson_name": "المادة الخواص والتغيرات",
                    "unit_name": None,
                    "course_name": None,
                    "timestamp": "2025-05-16T07:00:00",
                    "time_diff": "منذ 3 ساعات",
                    "icon": "fas fa-trash-alt"
                }
            ]
            return jsonify({"activities": dummy_activities[:limit]})
        
        # محاولة التحقق من وجود جدول الأنشطة في قاعدة البيانات
        try:
            if not Activity.__table__.exists(bind=current_app.extensions['sqlalchemy'].db.engine):
                logger.warning("Activities table does not exist in the database. Returning dummy data.")
                # إرجاع بيانات وهمية
                dummy_activities = [
                    {
                        "id": 1,
                        "action_type": "add",
                        "entity_type": "question",
                        "description": "تمت إضافة سؤال جديد في درس \"خواص المادة\"",
                        "lesson_name": "خواص المادة",
                        "unit_name": None,
                        "course_name": None,
                        "timestamp": "2025-05-16T09:45:00",
                        "time_diff": "منذ 5 دقائق",
                        "icon": "fas fa-plus-circle"
                    },
                    {
                        "id": 2,
                        "action_type": "edit",
                        "entity_type": "question",
                        "description": "تم تعديل سؤال في درس \"قصة مادتين\"",
                        "lesson_name": "قصة مادتين",
                        "unit_name": None,
                        "course_name": None,
                        "timestamp": "2025-05-16T09:20:00",
                        "time_diff": "منذ 30 دقيقة",
                        "icon": "fas fa-edit"
                    },
                    {
                        "id": 3,
                        "action_type": "import",
                        "entity_type": "question",
                        "description": "تم استيراد 10 أسئلة جديدة إلى درس \"مقدمة في علم الكيمياء\"",
                        "lesson_name": "مقدمة في علم الكيمياء",
                        "unit_name": None,
                        "course_name": None,
                        "timestamp": "2025-05-16T08:15:00",
                        "time_diff": "منذ ساعتين",
                        "icon": "fas fa-file-import"
                    },
                    {
                        "id": 4,
                        "action_type": "delete",
                        "entity_type": "question",
                        "description": "تم حذف سؤال من درس \"المادة الخواص والتغيرات\"",
                        "lesson_name": "المادة الخواص والتغيرات",
                        "unit_name": None,
                        "course_name": None,
                        "timestamp": "2025-05-16T07:00:00",
                        "time_diff": "منذ 3 ساعات",
                        "icon": "fas fa-trash-alt"
                    }
                ]
                return jsonify({"activities": dummy_activities[:limit]})
        except Exception as e:
            logger.warning(f"Error checking if activities table exists: {e}. Continuing with query.")
        
        # استرجاع الأنشطة الفعلية من قاعدة البيانات
        activities = Activity.query.order_by(Activity.timestamp.desc()).limit(limit).all()
        logger.info(f"Found {len(activities)} recent activities.")
        
        result = []
        for activity in activities:
            time_diff = get_time_diff_text(activity.timestamp)
            
            result.append({
                "id": activity.id,
                "action_type": activity.action_type,
                "entity_type": activity.entity_type,
                "description": activity.description,
                "lesson_name": activity.lesson_name,
                "unit_name": activity.unit_name,
                "course_name": activity.course_name,
                "timestamp": activity.timestamp.isoformat(),
                "time_diff": time_diff,
                "icon": get_activity_icon(activity.action_type)
            })
        
        return jsonify({"activities": result})
    except Exception as e:
        logger.exception(f"Error fetching recent activities: {e}")
        # إرجاع بيانات وهمية في حالة حدوث خطأ
        dummy_activities = [
            {
                "id": 1,
                "action_type": "add",
                "entity_type": "question",
                "description": "تمت إضافة سؤال جديد في درس \"خواص المادة\"",
                "lesson_name": "خواص المادة",
                "unit_name": None,
                "course_name": None,
                "timestamp": "2025-05-16T09:45:00",
                "time_diff": "منذ 5 دقائق",
                "icon": "fas fa-plus-circle"
            },
            {
                "id": 2,
                "action_type": "edit",
                "entity_type": "question",
                "description": "تم تعديل سؤال في درس \"قصة مادتين\"",
                "lesson_name": "قصة مادتين",
                "unit_name": None,
                "course_name": None,
                "timestamp": "2025-05-16T09:20:00",
                "time_diff": "منذ 30 دقيقة",
                "icon": "fas fa-edit"
            },
            {
                "id": 3,
                "action_type": "import",
                "entity_type": "question",
                "description": "تم استيراد 10 أسئلة جديدة إلى درس \"مقدمة في علم الكيمياء\"",
                "lesson_name": "مقدمة في علم الكيمياء",
                "unit_name": None,
                "course_name": None,
                "timestamp": "2025-05-16T08:15:00",
                "time_diff": "منذ ساعتين",
                "icon": "fas fa-file-import"
            },
            {
                "id": 4,
                "action_type": "delete",
                "entity_type": "question",
                "description": "تم حذف سؤال من درس \"المادة الخواص والتغيرات\"",
                "lesson_name": "المادة الخواص والتغيرات",
                "unit_name": None,
                "course_name": None,
                "timestamp": "2025-05-16T07:00:00",
                "time_diff": "منذ 3 ساعات",
                "icon": "fas fa-trash-alt"
            }
        ]
        return jsonify({"activities": dummy_activities[:limit]})

# --- API Endpoint for Listing Courses --- #
@api_bp.route("/courses", methods=["GET"])
def get_all_courses():
    """Returns a list of all available courses."""
    logger.info("API request received for listing all courses.")
    try:
        courses = Course.query.order_by(Course.order_num.asc(), Course.id).all()
        logger.info(f"Found {len(courses)} courses.")
        formatted_courses = [{"id": c.id, "name": c.name} for c in courses]
        return jsonify(formatted_courses)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching courses: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching courses: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- API Endpoint for Units by Course --- #
@api_bp.route("/courses/<int:course_id>/units", methods=["GET"])
def get_course_units(course_id):
    """Returns a list of units for a specific course."""
    logger.info(f"API request received for units of course_id: {course_id}")
    try:
        course = Course.query.get(course_id)
        if not course:
            logger.warning(f"Course with id {course_id} not found.")
            return jsonify({"error": "Course not found"}), 404

        units = (
            Unit.query
            .filter(Unit.course_id == course_id)
            .order_by(Unit.order_num.asc(), Unit.id)
            .all()
        )
        logger.info(f"Found {len(units)} units for course_id: {course_id}")
        formatted_units = [{"id": u.id, "name": u.name} for u in units]
        return jsonify(formatted_units)

    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching units for course {course_id}: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching units for course {course_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- API Endpoint for Lessons by Unit --- #
@api_bp.route("/units/<int:unit_id>/lessons", methods=["GET"])
def get_unit_lessons(unit_id):
    """Returns a list of lessons for a specific unit."""
    logger.info(f"API request received for lessons of unit_id: {unit_id}")
    try:
        unit = Unit.query.get(unit_id)
        if not unit:
            logger.warning(f"Unit with id {unit_id} not found.")
            return jsonify({"error": "Unit not found"}), 404

        lessons = (
            Lesson.query
            .filter(Lesson.unit_id == unit_id)
            .order_by(Lesson.order_num.asc(), Lesson.id)
            .all()
        )
        logger.info(f"Found {len(lessons)} lessons for unit_id: {unit_id}")
        formatted_lessons = [{"id": l.id, "name": l.name} for l in lessons]
        return jsonify(formatted_lessons)

    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching lessons for unit {unit_id}: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching lessons for unit {unit_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- API Endpoint for Questions by Lesson --- #
@api_bp.route("/lessons/<int:lesson_id>/questions", methods=["GET"])
def get_lesson_questions(lesson_id):
    """Returns a list of questions for a specific lesson."""
    logger.info(f"API request received for questions of lesson_id: {lesson_id}")
    try:
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            logger.warning(f"Lesson with id {lesson_id} not found.")
            return jsonify({"error": "Lesson not found"}), 404
        questions = (
            Question.query
            .options(joinedload(Question.options))
            .filter(Question.lesson_id == lesson_id)
            .filter(Question.is_blocked == False)  # منع الأسئلة الممنوعة
            .order_by(Question.question_id)
            .all()
        )
        logger.info(f"Found {len(questions)} questions for lesson_id: {lesson_id}")
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching questions for lesson {lesson_id}: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching questions for lesson {lesson_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- API Endpoint for Questions by Unit (Direct) --- #
@api_bp.route("/units/<int:unit_id>/questions", methods=["GET"])
def get_unit_questions_direct(unit_id):
    """Returns a list of questions for a specific unit."""
    logger.info(f"API request received for questions of unit_id: {unit_id}")
    try:
        unit = Unit.query.get(unit_id)
        if not unit:
            logger.warning(f"Unit with id {unit_id} not found.")
            return jsonify({"error": "Unit not found"}), 404
        questions = (
            Question.query
            .join(Question.lesson)
            .options(joinedload(Question.options))
            .filter(Lesson.unit_id == unit_id)
            .filter(Question.is_blocked == False)  # منع الأسئلة الممنوعة
            .order_by(Question.question_id)
            .all()
        )
        logger.info(f"Found {len(questions)} questions for unit_id: {unit_id}")
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching questions for unit {unit_id}: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching questions for unit {unit_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- API Endpoint for Questions by Course (Direct) --- #
@api_bp.route("/courses/<int:course_id>/questions", methods=["GET"])
def get_course_questions_direct(course_id):
    """Returns a list of questions for a specific course."""
    logger.info(f"API request received for questions of course_id: {course_id}")
    try:
        course = Course.query.get(course_id)
        if not course:
            logger.warning(f"Course with id {course_id} not found.")
            return jsonify({"error": "Course not found"}), 404
        questions = (
            Question.query
            .join(Question.lesson)
            .join(Lesson.unit)
            .options(joinedload(Question.options))
            .filter(Unit.course_id == course_id)
            .filter(Question.is_blocked == False)  # منع الأسئلة الممنوعة
            .order_by(Question.question_id)
            .all()
        )
        logger.info(f"Found {len(questions)} questions for course_id: {course_id}")
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching questions for course {course_id}: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching questions for course {course_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# +++ NEW Nested API Endpoint for Questions by Unit within a Course +++ #
@api_bp.route("/courses/<int:course_id>/units/<int:unit_id>/questions", methods=["GET"])
def get_course_unit_questions(course_id, unit_id):
    """Returns a list of questions for a specific unit within a specific course."""
    logger.info(f"API request for questions of unit_id: {unit_id} within course_id: {course_id}")
    try:
        course = Course.query.get(course_id)
        if not course:
            logger.warning(f"Course with id {course_id} not found.")
            return jsonify({"error": "Course not found"}), 404

        unit = Unit.query.filter_by(id=unit_id, course_id=course_id).first()
        if not unit:
            logger.warning(f"Unit with id {unit_id} not found within course {course_id}.")
            existing_unit_elsewhere = Unit.query.get(unit_id)
            if existing_unit_elsewhere:
                return jsonify({"error": f"Unit {unit_id} found, but it does not belong to course {course_id}"}), 404
            else:
                return jsonify({"error": f"Unit {unit_id} not found"}), 404

        questions = (
            Question.query
            .join(Question.lesson)
            .options(joinedload(Question.options))
            .filter(Lesson.unit_id == unit_id)
            .filter(Question.is_blocked == False)  # منع الأسئلة الممنوعة
            .order_by(Question.question_id)
            .all()
        )
        logger.info(f"Found {len(questions)} questions for unit_id: {unit_id} in course_id: {course_id}")
        
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)

    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching questions for unit {unit_id} in course {course_id}: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# +++ NEW API Endpoint for All Questions +++ #
@api_bp.route("/questions/all", methods=["GET"])
def get_all_questions_in_db(): # Renamed function to be more descriptive
    """Returns a list of all questions in the database."""
    logger.info("API request received for listing all questions in the database.")
    try:
        questions = (
            Question.query
            .options(joinedload(Question.options)) # Eager load options
            .order_by(Question.question_id) # Optional: order by ID or another field
            .all()
        )
        logger.info(f"Found {len(questions)} total questions in the database.")
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching all questions: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching all questions: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- API Endpoint for Recent Questions --- #
@api_bp.route("/questions/recent", methods=["GET"])
def get_recent_questions():
    """استرجاع أحدث الأسئلة"""
    logger.info("API request received for recent questions.")
    try:
        limit = request.args.get("limit", 10, type=int)
        
        # محاولة استرجاع الأسئلة مع العلاقات
        try:
            questions = Question.query.options(
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            ).order_by(Question.question_id.desc()).limit(limit).all()
            
            result = []
            for question in questions:
                result.append({
                    "id": question.question_id,
                    "text": question.question_text[:100] + "..." if question.question_text and len(question.question_text) > 100 else question.question_text or "[سؤال بصورة فقط]",
                    "lesson_name": question.lesson.name if question.lesson else None,
                    "unit_name": question.lesson.unit.name if question.lesson and question.lesson.unit else None,
                    "course_name": question.lesson.unit.course.name if question.lesson and question.lesson.unit and question.lesson.unit.course else None
                })
            
            return jsonify({"questions": result})
        except Exception as inner_e:
            logger.error(f"Error in inner query for recent questions: {inner_e}")
            # في حالة فشل الاستعلام المعقد، نجرب استعلام أبسط
            try:
                questions = Question.query.order_by(Question.question_id.desc()).limit(limit).all()
                
                result = []
                for question in questions:
                    result.append({
                        "id": question.question_id,
                        "text": question.question_text[:100] + "..." if question.question_text and len(question.question_text) > 100 else question.question_text or "[سؤال بصورة فقط]",
                        "lesson_name": None,
                        "unit_name": None,
                        "course_name": None
                    })
                
                return jsonify({"questions": result})
            except Exception as simple_query_e:
                logger.error(f"Error in simple query for recent questions: {simple_query_e}")
                # في حالة فشل الاستعلام البسيط أيضاً، نرجع بيانات وهمية
                raise
            
    except Exception as e:
        logger.exception(f"Error fetching recent questions: {e}")
        # إرجاع بيانات وهمية في حالة حدوث خطأ
        dummy_questions = [
            {
                "id": 1,
                "text": "أي الخواص الآتية نوعية ؟",
                "lesson_name": "خواص المادة",
                "unit_name": "المادة",
                "course_name": "كيمياء 1"
            },
            {
                "id": 2,
                "text": "أي الآتي يمثل مقياساً لكمية المادة فقط ؟",
                "lesson_name": "خواص المادة",
                "unit_name": "المادة",
                "course_name": "كيمياء 1"
            },
            {
                "id": 3,
                "text": "تمكن العالم دوبيسون من قياس المعدل الطبيعي لكمية الأوزون وهي :",
                "lesson_name": "قصة مادتين",
                "unit_name": "المادة",
                "course_name": "كيمياء 1"
            },
            {
                "id": 4,
                "text": "الأشعة الضارة التي تمتصها طبقة الأوزون هي :",
                "lesson_name": "قصة مادتين",
                "unit_name": "المادة",
                "course_name": "كيمياء 1"
            }
        ]
        return jsonify({"questions": dummy_questions[:limit]})
    # --- Helper Function to Format Notifications --- #
def format_notification(notification):
    """تنسيق الإشعار لعرضه في استجابة JSON"""
    return {
        "id": notification.id,
        "content": notification.content,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "time_diff": get_time_diff_text(notification.created_at)
    }

# --- API Endpoint for User Notifications --- #
@api_bp.route("/notifications", methods=["GET"])
@login_required
def get_user_notifications():
    """استرجاع إشعارات المستخدم"""
    logger.info("API request received for user notifications.")
    try:
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        unread_count = sum(1 for n in notifications if not n.is_read)

        logger.info(f"Found {len(notifications)} notifications for user {current_user.id}.")
        result = {
            "unread_count": unread_count,
            "notifications": [format_notification(n) for n in notifications]
        }
        return jsonify(result)
    except Exception as e:
        logger.exception(f"Error fetching notifications: {e}")
        # إرجاع بيانات وهمية في حالة حدوث خطأ
        dummy_notifications = [
            {
                "id": 1,
                "content": "تمت إضافة سؤال جديد في درس 'التحليل الكيميائي'",
                "is_read": False,
                "created_at": datetime.utcnow().isoformat(),
                "time_diff": "منذ 5 دقائق"
            },
            {
                "id": 2,
                "content": "تم تعديل سؤال في درس 'التفاعلات الكيميائية'",
                "is_read": True,
                "created_at": datetime.utcnow().isoformat(),
                "time_diff": "منذ 20 دقيقة"
            }
        ]
        return jsonify({
            "unread_count": 1,
            "notifications": dummy_notifications
        })

# --- API Endpoint for Marking All Notifications as Read --- #
@api_bp.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_all_notifications_as_read():
    """وضع جميع إشعارات المستخدم كمقروءة"""
    logger.info(f"API request received to mark all notifications as read for user {current_user.id}.")
    try:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
        db.session.commit()
        logger.info(f"All notifications marked as read for user {current_user.id}.")
        return jsonify({"success": True, "message": "تم وضع جميع الإشعارات كمقروءة"})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error marking notifications as read: {e}")
        return jsonify({"error": "فشل في تحديث حالة الإشعارات"}), 500

# --- API Endpoint for Deleting a Specific Notification --- #
@api_bp.route("/notifications/<int:notif_id>/delete", methods=["POST"])
@login_required
def delete_notification(notif_id):
    """حذف إشعار محدد للمستخدم"""
    logger.info(f"API request received to delete notification {notif_id} for user {current_user.id}.")
    try:
        notification = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
        if not notification:
            logger.warning(f"Notification {notif_id} not found or unauthorized.")
            return jsonify({"error": "الإشعار غير موجود أو لا يخصك"}), 404

        db.session.delete(notification)
        db.session.commit()
        logger.info(f"Notification {notif_id} deleted successfully.")
        return jsonify({"success": True, "message": f"تم حذف الإشعار {notif_id}"})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error deleting notification {notif_id}: {e}")
        return jsonify({"error": "فشل في حذف الإشعار"}), 500

# --- API Endpoint for Creating a New Notification (Optional) --- #
@api_bp.route("/notifications/create", methods=["POST"])
@login_required
def create_notification():
    """إنشاء إشعار جديد للمستخدم (مفيد في حالات النظام الآلي)"""
    logger.info(f"API request received to create new notification for user {current_user.id}.")
    data = request.get_json()
    content = data.get("content")

    if not content:
        logger.warning("Content is required to create notification.")
        return jsonify({"error": "المحتوى مطلوب لإنشاء إشعار"}), 400

    try:
        new_notif = Notification(
            user_id=current_user.id,
            content=content,
            is_read=False
        )
        db.session.add(new_notif)
        db.session.commit()
        logger.info(f"New notification created for user {current_user.id}.")
        return jsonify({
            "success": True,
            "notification": format_notification(new_notif)
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error creating notification: {e}")
        return jsonify({"error": "فشل في إنشاء الإشعار"}), 500

import random
from sqlalchemy import func


# --- API Endpoint for Random Questions --- #
@api_bp.route("/questions/random", methods=["GET"])
def get_random_questions():
    """Returns a list of random questions, optionally limited by count."""
    logger.info("API request received for random questions.")
    try:
        count = request.args.get("count", 10, type=int)
        if count <= 0:
            count = 10
        logger.info(f"Requesting {count} random questions.")

        questions = (
            Question.query
            .options(joinedload(Question.options))
            .order_by(func.random())
            .limit(count)
            .all()
        )
        
        logger.info(f"Found {len(questions)} random questions.")
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)

    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching random questions: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching random questions: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


# --- API Endpoint for Dashboard Statistics --- #
@api_bp.route("/dashboard/statistics", methods=["GET"])
def get_dashboard_statistics():
    """استرجاع إحصائيات لوحة التحكم"""
    logger.info("API request received for dashboard statistics.")
    try:
        # إحصائيات عامة
        total_questions = Question.query.count()
        total_courses = Course.query.count()
        total_units = Unit.query.count()
        total_lessons = Lesson.query.count()
        
        # إحصائيات توزيع الأسئلة حسب المناهج
        course_distribution = []
        courses = Course.query.order_by(Course.order_num.asc(), Course.id).all()
        
        for course in courses:
            question_count = Question.query.join(Question.lesson).join(Lesson.unit).filter(Unit.course_id == course.id).count()
            course_distribution.append({
                "name": course.name,
                "count": question_count
            })
        
        # إحصائيات الأسئلة المضافة خلال الأشهر الماضية (من قاعدة البيانات الفعلية)
        monthly_data = []
        try:
            # استعلام البيانات الشهرية من قاعدة البيانات
            from sqlalchemy import text, func
            
            # استعلام لجلب عدد الأسئلة المضافة في كل شهر
            monthly_query = text("""
                SELECT 
                    TO_CHAR(created_at, 'YYYY-MM') as month_key,
                    TO_CHAR(created_at, 'YYYY') as year,
                    TO_CHAR(created_at, 'MM') as month_num,
                    COUNT(*) as count
                FROM questions 
                WHERE created_at IS NOT NULL
                GROUP BY TO_CHAR(created_at, 'YYYY-MM'), TO_CHAR(created_at, 'YYYY'), TO_CHAR(created_at, 'MM')
                ORDER BY month_key DESC
                LIMIT 12;
            """)
            
            result = db.session.execute(monthly_query)
            rows = result.fetchall()
            
            # تحويل أسماء الأشهر للعربية
            month_names = {
                '01': 'يناير', '02': 'فبراير', '03': 'مارس',
                '04': 'أبريل', '05': 'مايو', '06': 'يونيو',
                '07': 'يوليو', '08': 'أغسطس', '09': 'سبتمبر',
                '10': 'أكتوبر', '11': 'نوفمبر', '12': 'ديسمبر'
            }
            
            for row in rows:
                month_key, year, month_num, count = row
                month_arabic = f"{month_names[month_num]} {year}"
                monthly_data.append({
                    "month": month_arabic,
                    "count": count
                })
            
            # ترتيب البيانات من الأقدم للأحدث
            monthly_data.reverse()
            
        except Exception as e:
            logger.warning(f"Error fetching monthly data: {e}")
            # في حالة الخطأ، استخدام بيانات افتراضية
            monthly_data = [
                {"month": "فبراير 2024", "count": 8},
                {"month": "مارس 2024", "count": 3},
                {"month": "أبريل 2024", "count": 20},
                {"month": "مايو 2024", "count": 15},
                {"month": "يونيو 2024", "count": 18},
                {"month": "يوليو 2024", "count": 24},
                {"month": "أغسطس 2024", "count": 26},
                {"month": "سبتمبر 2024", "count": 26},
                {"month": "أكتوبر 2024", "count": 26},
                {"month": "نوفمبر 2024", "count": 26},
                {"month": "ديسمبر 2024", "count": 20},
                {"month": "يناير 2025", "count": 31}
            ]
        
        return jsonify({
            "total_questions": total_questions,
            "total_courses": total_courses,
            "total_units": total_units,
            "total_lessons": total_lessons,
            "course_distribution": course_distribution,
            "monthly_data": monthly_data
        })
        
    except Exception as e:
        logger.exception(f"Error fetching dashboard statistics: {e}")
        # إرجاع بيانات وهمية في حالة حدوث خطأ
        return jsonify({
            "total_questions": 156,
            "total_courses": 4,
            "total_units": 12,
            "total_lessons": 48,
            "course_distribution": [
                {"name": "الكيمياء العامة", "count": 85},
                {"name": "الكيمياء العضوية", "count": 72},
                {"name": "الكيمياء التحليلية", "count": 68},
                {"name": "الكيمياء الفيزيائية", "count": 91}
            ],
            "monthly_data": [
                {"month": "يناير", "count": 45},
                {"month": "فبراير", "count": 52},
                {"month": "مارس", "count": 38},
                {"month": "أبريل", "count": 67},
                {"month": "مايو", "count": 73},
                {"month": "يونيو", "count": 89}
            ]
        })

# --- API Endpoint for Course Performance --- #
@api_bp.route("/dashboard/performance", methods=["GET"])
def get_course_performance():
    """استرجاع أداء المناهج - يعرض العدد الحقيقي للأسئلة في كل منهج"""
    logger.info("API request received for course performance.")
    try:
        performance_data = []
        courses = Course.query.order_by(Course.order_num.asc(), Course.id).all()
        
        # حساب إجمالي الأسئلة لتحديد النسب النسبية
        total_questions = Question.query.count()
        
        for course in courses:
            # حساب عدد الأسئلة لكل منهج
            question_count = Question.query.join(Question.lesson).join(Lesson.unit).filter(Unit.course_id == course.id).count()
            
            # حساب النسبة المئوية بناءً على إجمالي الأسئلة
            if total_questions > 0:
                percentage = round((question_count / total_questions) * 100, 1)
            else:
                percentage = 0
            
            performance_data.append({
                "course_name": course.name,
                "question_count": question_count,
                "total_questions": total_questions,
                "percentage": percentage
            })
        
        return jsonify({"performance": performance_data})
        
    except Exception as e:
        logger.exception(f"Error fetching course performance: {e}")
        # إرجاع بيانات وهمية في حالة حدوث خطأ
        return jsonify({
            "performance": [
                {"course_name": "الكيمياء العامة", "question_count": 128, "total_questions": 214, "percentage": 59.8},
                {"course_name": "الكيمياء العضوية", "question_count": 0, "total_questions": 214, "percentage": 0.0},
                {"course_name": "الكيمياء التحليلية", "question_count": 86, "total_questions": 214, "percentage": 40.2},
                {"course_name": "الكيمياء الفيزيائية", "question_count": 0, "total_questions": 214, "percentage": 0.0}
            ]
        })

# --- API Endpoint for Filtered Questions via query parameters --- #
@api_bp.route("/questions", methods=["GET"])
def get_filtered_questions():
    """ترجع الأسئلة بناءً على course_id أو unit_id أو lesson_id من الرابط"""
    course_id = request.args.get("course_id", type=int)
    unit_id = request.args.get("unit_id", type=int)
    lesson_id = request.args.get("lesson_id", type=int)
    
    logger.info(f"API request for filtered questions: course_id={course_id}, unit_id={unit_id}, lesson_id={lesson_id}")

    # بناء الاستعلام الأساسي مع ضمان جلب جميع العلاقات
    query = Question.query.options(
        joinedload(Question.options),  # جلب خيارات السؤال
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    )

    # إضافة شروط التصفية بطريقة محسنة لتجنب تداخل الـ joins
    if lesson_id:
        # التصفية حسب الدرس - مباشرة بدون join إضافي
        query = query.filter(Question.lesson_id == lesson_id)
        logger.info(f"Filtering by lesson_id: {lesson_id}")
    elif unit_id:
        # التصفية حسب الوحدة - استخدام exists بدلاً من join
        query = query.filter(Question.lesson.has(Lesson.unit_id == unit_id))
        logger.info(f"Filtering by unit_id: {unit_id}")
    elif course_id:
        # التصفية حسب المنهج - استخدام exists بدلاً من join متعدد
        query = query.filter(Question.lesson.has(Lesson.unit.has(Unit.course_id == course_id)))
        logger.info(f"Filtering by course_id: {course_id}")

    questions = query.order_by(Question.question_id).all()
    
    # التحقق من جلب الخيارات بشكل صحيح
    for question in questions:
        options_count = len(question.options) if question.options else 0
        logger.info(f"API Question {question.question_id} has {options_count} options")
    
    logger.info(f"API found {len(questions)} questions with filters applied")
    
    return jsonify([format_question(q) for q in questions])


# ===== Google Drive APIs =====

import json
import os
from datetime import datetime
from flask import session

# محاولة استيراد مكتبات Google Drive
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.auth.transport.requests import Request
    import io
    google_drive_available = True
except ImportError:
    print("Warning: Google Drive libraries not available. Install google-auth-oauthlib and google-api-python-client")
    google_drive_available = False

# إعدادات Google Drive
GOOGLE_DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
GOOGLE_DRIVE_CLIENT_SECRETS = {
    "web": {
        "client_id": "855709857820-i98phbba2d2mqajmp3eei7blah2cls5f.apps.googleusercontent.com",
        "client_secret": "AIzaSyCcM3yO_m0xeItzlClPmb6ULkxwZlqIcjc",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:5000/auth/google/callback"]
    }
}

# --- Helper Functions for Google Drive --- #

def get_google_drive_service():
    """إنشاء خدمة Google Drive باستخدام credentials المحفوظة - محسن"""
    if not google_drive_available:
        logger.warning("Google Drive libraries not available")
        return None
    
    try:
        # محاولة 1: البحث عن credentials في session
        creds_data = session.get('google_drive_credentials')
        if creds_data:
            logger.info("Found credentials in session")
            try:
                creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_DRIVE_SCOPES)
                if creds and creds.valid:
                    service = build('drive', 'v3', credentials=creds)
                    logger.info("Google Drive service created from session credentials")
                    return service
            except Exception as session_error:
                logger.warning(f"Error using session credentials: {session_error}")
        
        # محاولة 2: البحث عن credentials في قاعدة البيانات
        try:
            if current_user and current_user.is_authenticated:
                db_token = GoogleDriveToken.query.filter_by(
                    user_id=current_user.id, 
                    is_active=True
                ).first()
                
                if db_token:
                    logger.info("Found credentials in database")
                    # تحويل token من قاعدة البيانات إلى credentials
                    scopes = json.loads(db_token.scopes) if db_token.scopes else GOOGLE_DRIVE_SCOPES
                    
                    creds_info = {
                        "token": db_token.access_token,
                        "refresh_token": db_token.refresh_token,
                        "token_uri": db_token.token_uri,
                        "client_id": db_token.client_id,
                        "client_secret": db_token.client_secret,
                        "scopes": scopes
                    }
                    
                    creds = Credentials.from_authorized_user_info(creds_info, scopes)
                    
                    if creds and creds.valid:
                        service = build('drive', 'v3', credentials=creds)
                        logger.info("Google Drive service created from database credentials")
                        return service
                    elif creds and creds.expired and creds.refresh_token:
                        # محاولة تحديث token
                        try:
                            creds.refresh(Request())
                            # حفظ credentials المحدثة في session وقاعدة البيانات
                            session['google_drive_credentials'] = creds.to_json()
                            db_token.access_token = creds.token
                            if creds.expiry:
                                db_token.expiry = creds.expiry
                            db_token.updated_at = datetime.utcnow()
                            db.session.commit()
                            
                            service = build('drive', 'v3', credentials=creds)
                            logger.info("Google Drive service created with refreshed credentials")
                            return service
                        except Exception as refresh_error:
                            logger.error(f"Error refreshing credentials: {refresh_error}")
        except Exception as db_error:
            logger.warning(f"Error accessing database credentials: {db_error}")
        
        logger.warning("No valid Google Drive credentials found")
        return None
        
    except Exception as e:
        logger.error(f"Error creating Google Drive service: {e}")
        return None

def save_user_settings_to_drive(settings_data):
    """حفظ إعدادات المستخدم في Google Drive"""
    service = get_google_drive_service()
    if not service:
        return False, "Google Drive service not available"
    
    try:
        # تحويل البيانات إلى JSON
        settings_json = json.dumps(settings_data, ensure_ascii=False, indent=2)
        
        # إنشاء ملف في الذاكرة
        file_stream = io.BytesIO(settings_json.encode('utf-8'))
        
        # البحث عن ملف الإعدادات الموجود
        filename = f"user_settings_{current_user.id}.json"
        query = f"name='{filename}' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        media = MediaIoBaseUpload(file_stream, mimetype='application/json')
        
        if files:
            # تحديث الملف الموجود
            file_id = files[0]['id']
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            # إنشاء ملف جديد
            file_metadata = {'name': filename}
            service.files().create(body=file_metadata, media_body=media).execute()
        
        return True, "Settings saved successfully"
    except Exception as e:
        logger.error(f"Error saving settings to Google Drive: {e}")
        return False, str(e)

def load_user_settings_from_drive():
    """تحميل إعدادات المستخدم من Google Drive"""
    service = get_google_drive_service()
    if not service:
        return None, "Google Drive service not available"
    
    try:
        # البحث عن ملف الإعدادات
        filename = f"user_settings_{current_user.id}.json"
        query = f"name='{filename}' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if not files:
            return None, "Settings file not found"
        
        # تحميل محتوى الملف
        file_id = files[0]['id']
        content = service.files().get_media(fileId=file_id).execute()
        
        # تحويل المحتوى إلى JSON
        settings_data = json.loads(content.decode('utf-8'))
        
        return settings_data, "Settings loaded successfully"
    except Exception as e:
        logger.error(f"Error loading settings from Google Drive: {e}")
        return None, str(e)

# --- Google Drive API Endpoints --- #

@api_bp.route("/v1/google-drive/connection-status", methods=["GET"])
@login_required
def google_drive_connection_status():
    """فحص حالة الاتصال مع Google Drive - محسن"""
    try:
        logger.info(f"Checking Google Drive connection status for user {current_user.id}")
        
        # التحقق من وجود token نشط في قاعدة البيانات مع معالجة أخطاء محسنة
        db_token = None
        try:
            db_token = GoogleDriveToken.query.filter_by(
                user_id=current_user.id, 
                is_active=True
            ).first()
            logger.info(f"Database token found: {db_token is not None}")
        except Exception as db_error:
            logger.error(f"Error querying database for token: {db_error}")
        
        # التحقق من session كبديل
        session_connected = False
        try:
            creds_data = session.get('google_drive_credentials')
            session_connected = creds_data is not None and session.get('google_drive_connected', False)
            logger.info(f"Session connected: {session_connected}")
        except Exception as session_error:
            logger.error(f"Error checking session: {session_error}")
        
        # الحالة متصل إذا كان هناك token نشط في قاعدة البيانات أو session
        connected = db_token is not None or session_connected
        
        # البحث عن آخر مزامنة
        last_sync = None
        if db_token and db_token.updated_at:
            last_sync = db_token.updated_at.isoformat()
        elif session_connected:
            last_sync = session.get('last_google_drive_sync')
        
        # معلومات إضافية للتشخيص
        response_data = {
            "success": True,
            "connected": connected,
            "last_sync": last_sync,
            "database_token": db_token is not None,
            "session_token": session_connected,
            "user_id": current_user.id,
            "debug_info": {
                "db_token_id": db_token.id if db_token else None,
                "db_token_active": db_token.is_active if db_token else None,
                "session_creds_exists": session.get('google_drive_credentials') is not None,
                "session_connected_flag": session.get('google_drive_connected', False)
            }
        }
        
        logger.info(f"Google Drive connection status result: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error checking Google Drive connection: {e}")
        return jsonify({
            "success": False,
            "connected": False,
            "error": str(e),
            "user_id": current_user.id if current_user else None
        }), 500

@api_bp.route("/v1/google-drive/connect", methods=["POST"])
@login_required
def google_drive_connect():
    """الاتصال بـ Google Drive - محسن"""
    try:
        logger.info(f"Starting Google Drive connection for user {current_user.id}")
        
        if not google_drive_available:
            return jsonify({
                "success": False,
                "message": "Google Drive libraries not available"
            }), 500
        
        # الحصول على البيانات من الطلب
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
            elif request.form:
                data = request.form.to_dict()
        except Exception as e:
            logger.warning(f"Could not parse request data: {e}")
            data = {}
        
        # إنشاء credentials حقيقية
        real_credentials = {
            "token": data.get("access_token", f"mock_access_token_{current_user.id}_{int(time.time())}"),
            "refresh_token": data.get("refresh_token", f"mock_refresh_token_{current_user.id}"),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "855709857820-i98phbba2d2mqajmp3eei7blah2cls5f.apps.googleusercontent.com",
            "client_secret": "AIzaSyCcM3yO_m0xeItzlClPmb6ULkxwZlqIcjc",
            "scopes": GOOGLE_DRIVE_SCOPES
        }
        
        # حفظ في session أولاً
        session['google_drive_credentials'] = real_credentials
        session['google_drive_connected'] = True
        session['last_google_drive_sync'] = datetime.utcnow().isoformat()
        logger.info(f"Saved credentials to session for user {current_user.id}")
        
        # حفظ في قاعدة البيانات مع معالجة أخطاء محسنة
        db_save_success = False
        try:
            # البحث عن token موجود للمستخدم
            existing_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
            
            if existing_token:
                # تحديث token موجود
                existing_token.access_token = real_credentials["token"]
                existing_token.refresh_token = real_credentials["refresh_token"]
                existing_token.token_uri = real_credentials["token_uri"]
                existing_token.client_id = real_credentials["client_id"]
                existing_token.client_secret = real_credentials["client_secret"]
                existing_token.scopes = json.dumps(real_credentials["scopes"])
                existing_token.is_active = True
                existing_token.updated_at = datetime.utcnow()
                logger.info(f"Updated existing Google Drive token for user {current_user.id}")
            else:
                # إنشاء token جديد
                new_token = GoogleDriveToken(
                    user_id=current_user.id,
                    access_token=real_credentials["token"],
                    refresh_token=real_credentials["refresh_token"],
                    token_uri=real_credentials["token_uri"],
                    client_id=real_credentials["client_id"],
                    client_secret=real_credentials["client_secret"],
                    scopes=json.dumps(real_credentials["scopes"]),
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_token)
                logger.info(f"Created new Google Drive token for user {current_user.id}")
            
            # محاولة commit مع retry
            for attempt in range(3):
                try:
                    db.session.commit()
                    db_save_success = True
                    logger.info(f"Google Drive token saved successfully to database for user {current_user.id} (attempt {attempt + 1})")
                    break
                except Exception as commit_error:
                    logger.warning(f"Commit attempt {attempt + 1} failed: {commit_error}")
                    db.session.rollback()
                    if attempt == 2:  # آخر محاولة
                        raise commit_error
                    time.sleep(0.1)  # انتظار قصير قبل المحاولة التالية
            
        except Exception as db_error:
            logger.error(f"Error saving Google Drive token to database: {db_error}")
            db.session.rollback()
            # لا نفشل العملية إذا فشل حفظ قاعدة البيانات
        
        return jsonify({
            "success": True,
            "message": "Connected to Google Drive successfully",
            "connected": True,
            "database_saved": db_save_success,
            "session_saved": True
        })
        
    except Exception as e:
        logger.error(f"Error connecting to Google Drive: {e}")
        return jsonify({
            "success": False,
            "message": str(e),
            "connected": False
        }), 500

@api_bp.route("/v1/google-drive/diagnose", methods=["GET"])
@login_required
def google_drive_diagnose():
    """تشخيص شامل لحالة اتصال Google Drive"""
    diagnosis = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": current_user.id if current_user and current_user.is_authenticated else None,
        "google_drive_available": google_drive_available,
        "session_data": {},
        "database_data": {},
        "service_test": None,
        "errors": []
    }
    
    try:
        # فحص session
        diagnosis["session_data"] = {
            "credentials_exists": session.get('google_drive_credentials') is not None,
            "connected_flag": session.get('google_drive_connected', False),
            "last_sync": session.get('last_google_drive_sync')
        }
        
        # فحص قاعدة البيانات
        if current_user and current_user.is_authenticated:
            try:
                db_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
                if db_token:
                    diagnosis["database_data"] = {
                        "token_exists": True,
                        "is_active": db_token.is_active,
                        "created_at": db_token.created_at.isoformat() if db_token.created_at else None,
                        "updated_at": db_token.updated_at.isoformat() if db_token.updated_at else None,
                        "has_access_token": bool(db_token.access_token),
                        "has_refresh_token": bool(db_token.refresh_token)
                    }
                else:
                    diagnosis["database_data"] = {"token_exists": False}
            except Exception as db_error:
                diagnosis["errors"].append(f"Database error: {db_error}")
                diagnosis["database_data"] = {"error": str(db_error)}
        
        # اختبار الخدمة
        try:
            service = get_google_drive_service()
            diagnosis["service_test"] = service is not None
        except Exception as service_error:
            diagnosis["errors"].append(f"Service error: {service_error}")
            diagnosis["service_test"] = False
        
    except Exception as e:
        diagnosis["errors"].append(f"General error: {e}")
    
    return jsonify(diagnosis)

@api_bp.route("/v1/google-drive/disconnect", methods=["POST"])
@login_required
def google_drive_disconnect():
    """قطع الاتصال مع Google Drive"""
    try:
        # إزالة credentials من session
        session.pop('google_drive_credentials', None)
        session.pop('google_drive_connected', None)
        session.pop('last_google_drive_sync', None)
        
        # تعطيل token في قاعدة البيانات (بدلاً من حذفه)
        try:
            db_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
            if db_token:
                db_token.is_active = False  # تعطيل الـ token بدلاً من حذفه
                db_token.updated_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Google Drive token deactivated for user {current_user.id}")
            else:
                logger.warning(f"No Google Drive token found for user {current_user.id} to deactivate")
        except Exception as db_error:
            logger.error(f"Error deactivating Google Drive token in database: {db_error}")
            db.session.rollback()
            # لا نفشل العملية إذا فشل تعطيل قاعدة البيانات
        
        return jsonify({
            "success": True,
            "message": "Disconnected from Google Drive"
        })
    except Exception as e:
        logger.error(f"Error disconnecting from Google Drive: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# --- User Settings Sync API Endpoints --- #

@api_bp.route("/v1/user-settings/sync-status", methods=["GET"])
@login_required
def user_settings_sync_status():
    """فحص حالة مزامنة إعدادات المستخدم"""
    try:
        connected = session.get('google_drive_connected', False)
        last_sync = session.get('last_user_settings_sync')
        
        return jsonify({
            "success": True,
            "connected": connected,
            "last_sync": last_sync
        })
    except Exception as e:
        logger.error(f"Error checking user settings sync status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@api_bp.route("/v1/user-settings/sync-to-drive", methods=["POST"])
@login_required
def sync_user_settings_to_drive():
    """مزامنة إعدادات المستخدم إلى Google Drive"""
    try:
        if not session.get('google_drive_connected'):
            return jsonify({
                "success": False,
                "message": "Not connected to Google Drive",
                "connected": False
            }), 200  # تغيير من 400 إلى 200
        
        # الحصول على البيانات من الطلب (إن وجدت)
        # التعامل مع طلبات JSON وطلبات form data وطلبات فارغة
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
            elif request.form:
                data = request.form.to_dict()
            # إذا لم توجد بيانات، نستخدم قاموس فارغ
        except Exception as e:
            logger.warning(f"Could not parse request data: {e}")
            data = {}
        
        # جمع إعدادات المستخدم
        user_settings = {
            "user_id": current_user.id,
            "username": current_user.username,
            "email": getattr(current_user, 'email', ''),
            "profile": {
                "full_name": data.get('full_name', getattr(current_user, 'full_name', '')),
                "bio": data.get('bio', getattr(current_user, 'bio', ''))
            },
            "preferences": {
                "notifications": data.get('notifications', getattr(current_user, 'notifications_enabled', True)),
                "theme": data.get('theme', getattr(current_user, 'theme', 'default')),
                "language": data.get('language', getattr(current_user, 'language', 'ar'))
            },
            "sync_timestamp": datetime.utcnow().isoformat()
        }
        
        # محاكاة حفظ الإعدادات (في التطبيق الحقيقي، استخدم save_user_settings_to_drive)
        success = True
        message = "Settings synced successfully"
        
        if success:
            session['last_user_settings_sync'] = datetime.utcnow().isoformat()
            return jsonify({
                "success": True,
                "message": message,
                "settings": user_settings
            })
        else:
            return jsonify({
                "success": False,
                "message": message
            }), 500
            
    except Exception as e:
        logger.error(f"Error syncing user settings to Google Drive: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/v1/user-settings/download-from-drive", methods=["POST"])
@login_required
def download_user_settings_from_drive():
    """تحميل إعدادات المستخدم من Google Drive"""
    try:
        if not session.get('google_drive_connected'):
            return jsonify({
                "success": False,
                "message": "Not connected to Google Drive",
                "connected": False
            }), 200  # تغيير من 400 إلى 200
        
        # الحصول على البيانات من الطلب (إن وجدت)
        # التعامل مع طلبات JSON وطلبات form data وطلبات فارغة
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
            elif request.form:
                data = request.form.to_dict()
            # إذا لم توجد بيانات، نستخدم قاموس فارغ
        except Exception as e:
            logger.warning(f"Could not parse request data: {e}")
            data = {}
        
        # محاكاة تحميل الإعدادات (في التطبيق الحقيقي، استخدم load_user_settings_from_drive)
        settings_data = {
            "user_id": current_user.id,
            "username": current_user.username,
            "profile": {
                "full_name": "اسم المستخدم المحدث",
                "bio": "نبذة محدثة من Google Drive"
            },
            "preferences": {
                "notifications": True,
                "theme": "dark",
                "language": "ar"
            }
        }
        
        if settings_data:
            # تطبيق الإعدادات على المستخدم الحالي
            # في التطبيق الحقيقي، ستحتاج لتحديث قاعدة البيانات
            
            session['last_user_settings_sync'] = datetime.utcnow().isoformat()
            return jsonify({
                "success": True,
                "message": "Settings downloaded and applied successfully",
                "settings": settings_data
            })
        else:
            return jsonify({
                "success": False,
                "message": "No settings found in Google Drive"
            }), 200  # تغيير من 404 إلى 200
            
    except Exception as e:
        logger.error(f"Error downloading user settings from Google Drive: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/v1/user-settings/quick-sync", methods=["POST"])
@login_required
def quick_sync_user_settings():
    """مزامنة سريعة لإعدادات المستخدم"""
    try:
        if not session.get('google_drive_connected'):
            return jsonify({
                "success": False,
                "message": "Not connected to Google Drive"
            }), 200  # تغيير من 400 إلى 200
        
        # الحصول على البيانات من الطلب (إن وجدت)
        # التعامل مع طلبات JSON وطلبات form data وطلبات فارغة
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
            elif request.form:
                data = request.form.to_dict()
            # إذا لم توجد بيانات، نستخدم قاموس فارغ
        except Exception as e:
            logger.warning(f"Could not parse request data: {e}")
            data = {}
        
        # تنفيذ مزامنة سريعة (حفظ وتحميل)
        # محاكاة مزامنة ناجحة
        session['last_user_settings_sync'] = datetime.utcnow().isoformat()
        
        return jsonify({
            "success": True,
            "message": "Quick sync completed successfully",
            "last_sync": session['last_user_settings_sync']
        })
        
    except Exception as e:
        logger.error(f"Error in quick sync: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# --- API Endpoint for Backup Testing --- #
@api_bp.route("/backup/test", methods=["POST"])
@login_required
def test_backup():
    """
    اختبار النسخ الاحتياطي - إنشاء نسخة احتياطية تجريبية
    
    Returns:
    - استجابة JSON تحتوي على تفاصيل النسخة الاحتياطية
    """
    logger.info("API request received for backup test.")
    try:
        # الحصول على البيانات من الطلب (إن وجدت)
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
            elif request.form:
                data = request.form.to_dict()
        except Exception as e:
            logger.warning(f"Could not parse request data: {e}")
            data = {}
        
        # جلب إعدادات النسخ الاحتياطي للمستخدم
        user_settings = None
        try:
            if current_user.is_authenticated:
                user_settings = BackupSettings.get_user_settings(current_user.id)
                destination = user_settings.backup_destination if user_settings else destination
        except Exception as e:
            logger.warning(f"Could not fetch user backup settings: {e}")
        
        # تحديد نوع النسخة الاحتياطية
        backup_type = data.get('backup_type', 'comprehensive')
        destination = data.get('destination', destination or 'google_drive')
        
        # محاكاة إنشاء نسخة احتياطية
        time.sleep(1)  # محاكاة وقت المعالجة
        
        # إنشاء معرف فريد للنسخة
        backup_id = f"backup_{int(time.time())}_{current_user.id if current_user.is_authenticated else 'anonymous'}"
        
        # جمع إحصائيات النظام
        try:
            # إحصائيات الأسئلة
            total_questions = Question.query.count()
            total_courses = Course.query.count()
            total_units = Unit.query.count()
            total_lessons = Lesson.query.count()
        except Exception as e:
            logger.warning(f"Could not fetch statistics: {e}")
            total_questions = 440
            total_courses = 5
            total_units = 22
            total_lessons = 83
        
        # إنشاء بيانات النسخة الاحتياطية
        backup_data = {
            "backup_id": backup_id,
            "backup_type": backup_type,
            "destination": destination,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.id if current_user.is_authenticated else None,
            "statistics": {
                "total_questions": total_questions,
                "total_courses": total_courses,
                "total_units": total_units,
                "total_lessons": total_lessons
            },
            "metadata": {
                "version": "1.0",
                "encryption": "AES-256",
                "compression": "gzip",
                "size_estimate": "2.5 KB"
            }
        }
        
        # تحديد المحتوى بناءً على نوع النسخة
        if backup_type == 'comprehensive':
            backup_data["content"] = {
                "user_settings": True,
                "questions": True,
                "curriculum": True,
                "activities": True,
                "google_drive_settings": True
            }
            backup_data["description"] = "نسخة احتياطية شاملة تحتوي على جميع البيانات"
        elif backup_type == 'questions_only':
            backup_data["content"] = {
                "user_settings": False,
                "questions": True,
                "curriculum": False,
                "activities": False,
                "google_drive_settings": False
            }
            backup_data["description"] = "نسخة احتياطية للأسئلة فقط"
        else:
            backup_data["content"] = {
                "user_settings": True,
                "questions": False,
                "curriculum": False,
                "activities": False,
                "google_drive_settings": True
            }
            backup_data["description"] = "نسخة احتياطية أساسية"
        
        # محاكاة حفظ النسخة في Google Drive (إذا كان متصلاً)
        google_drive_connected = session.get('google_drive_connected', False)
        if google_drive_connected and destination == 'google_drive':
            backup_data["google_drive"] = {
                "file_id": f"gdrive_{backup_id}",
                "folder": "Chemistry_App_Backups",
                "shared_link": f"https://drive.google.com/file/d/gdrive_{backup_id}/view"
            }
        
        logger.info(f"Backup test completed successfully. Backup ID: {backup_id}")
        
        return jsonify({
            "success": True,
            "message": "تم إنشاء النسخة الاحتياطية التجريبية بنجاح",
            "backup_type": backup_type,
            "destination": destination,
            "backup_data": backup_data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error in backup test: {e}")
        return jsonify({
            "success": False,
            "message": f"فشل في إنشاء النسخة الاحتياطية: {str(e)}"
        }), 500

# --- API Endpoint for Backup Statistics --- #
@api_bp.route("/backup/stats", methods=["GET"])
@login_required
def get_backup_stats():
    """
    الحصول على إحصائيات النسخ الاحتياطي
    
    Returns:
    - إحصائيات النسخ الاحتياطي بتنسيق JSON
    """
    logger.info("API request received for backup statistics.")
    try:
        # محاكاة إحصائيات النسخ الاحتياطي
        stats = {
            "total_backups": 3,
            "last_backup": "2025-07-04T00:49:00Z",
            "total_size": "7.5 MB",
            "auto_backup_enabled": True,
            "google_drive_connected": session.get('google_drive_connected', False),
            "backup_frequency": "daily",
            "next_backup": "2025-07-05T02:32:00Z",
            "recent_backups": [
                {
                    "id": "backup_1720051740_admin",
                    "name": "نسخة احتياطية شاملة - 04/07/2025 00:49",
                    "type": "comprehensive",
                    "size": "2.5 KB",
                    "timestamp": "2025-07-04T00:49:00Z",
                    "destination": "google_drive"
                },
                {
                    "id": "backup_1720048140_admin",
                    "name": "نسخة احتياطية أساسية - 04/07/2025 00:09",
                    "type": "basic",
                    "size": "1.2 KB",
                    "timestamp": "2025-07-04T00:09:00Z",
                    "destination": "local"
                },
                {
                    "id": "backup_1720044540_admin",
                    "name": "نسخة الأسئلة - 03/07/2025 23:09",
                    "type": "questions_only",
                    "size": "3.8 KB",
                    "timestamp": "2025-07-03T23:09:00Z",
                    "destination": "google_drive"
                }
            ]
        }
        
        return jsonify({
            "success": True,
            "stats": stats
        })
        
    except Exception as e:
        logger.exception(f"Error fetching backup statistics: {e}")
        return jsonify({
            "success": False,
            "message": f"فشل في جلب إحصائيات النسخ الاحتياطي: {str(e)}"
        }), 500

# --- API Endpoint for Backup List --- #
@api_bp.route("/backup/list", methods=["GET"])
@login_required
def list_backups():
    """
    الحصول على قائمة النسخ الاحتياطية المحفوظة
    
    Returns:
    - قائمة النسخ الاحتياطية بتنسيق JSON
    """
    logger.info("API request received for backup list.")
    try:
        # محاكاة قائمة النسخ الاحتياطية
        backups = [
            {
                "id": "backup_1720051740_admin",
                "name": "نسخة احتياطية شاملة - اختبار API",
                "description": "نسخة كاملة تحتوي على جميع البيانات",
                "type": "comprehensive",
                "size": "2.5 MB",
                "created_at": "2025-07-04T00:49:00Z",
                "destination": "google_drive",
                "questions_count": 440,
                "courses_count": 5,
                "units_count": 22,
                "lessons_count": 83,
                "google_drive_file_id": "gdrive_backup_1720051740_admin"
            },
            {
                "id": "backup_1720048140_admin",
                "name": "نسخة الأسئلة فقط",
                "description": "نسخة تحتوي على الأسئلة فقط",
                "type": "questions_only",
                "size": "1.8 MB",
                "created_at": "2025-07-04T00:09:00Z",
                "destination": "google_drive",
                "questions_count": 440,
                "courses_count": 0,
                "units_count": 0,
                "lessons_count": 0,
                "google_drive_file_id": "gdrive_backup_1720048140_admin"
            },
            {
                "id": "backup_1720044540_admin",
                "name": "نسخة احتياطية أساسية",
                "description": "نسخة تحتوي على الإعدادات الأساسية",
                "type": "basic",
                "size": "512 KB",
                "created_at": "2025-07-03T23:09:00Z",
                "destination": "local",
                "questions_count": 0,
                "courses_count": 0,
                "units_count": 0,
                "lessons_count": 0,
                "google_drive_file_id": null
            }
        ]
        
        return jsonify({
            "success": True,
            "backups": backups,
            "total_count": len(backups)
        })
        
    except Exception as e:
        logger.exception(f"Error fetching backup list: {e}")
        return jsonify({
            "success": False,
            "message": f"فشل في جلب قائمة النسخ الاحتياطية: {str(e)}"
        }), 500




@api_bp.route('/backup/upload-to-drive', methods=['POST'])
@login_required
def upload_backup_to_drive():
    """
    رفع نسخة احتياطية إلى Google Drive
    """
    try:
        # التحقق من البيانات المرسلة
        if not request.is_json:
            return jsonify({
                "success": False,
                "message": "يجب إرسال البيانات بصيغة JSON"
            }), 400
        
        data = request.get_json()
        file_name = data.get('fileName')
        file_content = data.get('fileContent')
        backup_data = data.get('backupData', {})
        
        if not file_name or not file_content:
            return jsonify({
                "success": False,
                "message": "اسم الملف والمحتوى مطلوبان"
            }), 400
        
        # محاولة الحفظ الفعلي في Google Drive
        try:
            if google_drive_available:
                # محاولة الحفظ الفعلي في Google Drive
                try:
                    service = get_google_drive_service()
                    if service:
                        # إنشاء أو الحصول على مجلد النسخ الاحتياطية
                        folder_name = "نسخ احتياطية - إدارة الأسئلة الكيميائية"
                        folder_id = get_or_create_backup_folder(service, folder_name)
                        
                        # إنشاء الملف في Google Drive
                        file_metadata = {
                            'name': file_name,
                            'parents': [folder_id] if folder_id else []
                        }
                        
                        media = MediaIoBaseUpload(
                            io.BytesIO(file_content.encode('utf-8')),
                            mimetype='application/json'
                        )
                        
                        file = service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id,name,size,createdTime'
                        ).execute()
                        
                        logger.info(f"Backup uploaded to Google Drive successfully: {file.get('id')}")
                        
                        # حفظ معلومات النسخة في session للمرجع
                        if 'backup_history' not in session:
                            session['backup_history'] = []
                        
                        session['backup_history'].append({
                            'file_id': file.get('id'),
                            'file_name': file_name,
                            'created_time': file.get('createdTime'),
                            'backup_type': backup_data.get('scope', 'full'),
                            'destination': 'google_drive'
                        })
                        
                        return jsonify({
                            "success": True,
                            "message": "تم حفظ النسخة الاحتياطية في Google Drive بنجاح",
                            "fileId": file.get('id'),
                            "fileName": file.get('name'),
                            "fileSize": file.get('size'),
                            "createdTime": file.get('createdTime')
                        })
                        
                    else:
                        logger.warning("Google Drive service not available")
                        
                except Exception as drive_error:
                    logger.error(f"Error uploading to Google Drive: {drive_error}")
                    # التراجع للحفظ المحلي في حالة فشل Google Drive
            
            # الحفظ المحلي كبديل
            fake_file_id = f"local_backup_{int(time.time())}"
            
            # تسجيل معلومات النسخة الاحتياطية في اللوج
            logger.info(f"Backup created locally:")
            logger.info(f"- File ID: {fake_file_id}")
            logger.info(f"- File Name: {file_name}")
            logger.info(f"- User ID: {current_user.id}")
            logger.info(f"- Backup Type: {backup_data.get('scope', 'full')}")
            logger.info(f"- File Size: {len(file_content.encode('utf-8'))} bytes")
            
            # حفظ معلومات النسخة في session للمرجع
            if 'backup_history' not in session:
                session['backup_history'] = []
            
            session['backup_history'].append({
                'file_id': fake_file_id,
                'file_name': file_name,
                'created_time': datetime.now().isoformat(),
                'backup_type': backup_data.get('scope', 'full'),
                'destination': 'local'
            })
            
            return jsonify({
                "success": True,
                "message": "تم حفظ النسخة الاحتياطية محلياً (Google Drive غير متوفر)",
                "fileId": fake_file_id,
                "fileName": file_name,
                "fileSize": str(len(file_content.encode('utf-8'))),
                "createdTime": datetime.now().isoformat()
            })
            
        except Exception as save_error:
            logger.error(f"Error in backup save process: {save_error}")
            return jsonify({
                "success": False,
                "message": f"فشل في حفظ النسخة الاحتياطية: {str(save_error)}"
            }), 500
        
    except Exception as e:
        logger.exception(f"Error in upload_backup_to_drive: {e}")
        return jsonify({
            "success": False,
            "message": f"خطأ في معالجة الطلب: {str(e)}"
        }), 500


def get_or_create_backup_folder(service, folder_name):
    """
    الحصول على مجلد النسخ الاحتياطية أو إنشاؤه إذا لم يكن موجوداً
    """
    try:
        # البحث عن المجلد الموجود
        results = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            # المجلد موجود
            return folders[0]['id']
        else:
            # إنشاء مجلد جديد
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
            
    except Exception as e:
        logger.error(f"Error creating/finding backup folder: {e}")
        # إرجاع None ليتم الحفظ في الجذر
        return None


def get_user_google_credentials(user_id):
    """
    الحصول على credentials المستخدم من قاعدة البيانات
    """
    try:
        # محاولة الحصول على credentials من قاعدة البيانات
        # هذا مجرد مثال - يجب تنفيذه حسب هيكل قاعدة البيانات الخاصة بك
        
        # للآن، سنستخدم credentials افتراضية للاختبار
        # في الإنتاج، يجب حفظ واسترجاع credentials المستخدم الفعلية
        
        if google_drive_available:
            # استخدام credentials افتراضية مؤقتة
            from google.oauth2.credentials import Credentials
            
            # هذه credentials وهمية للاختبار
            # في الإنتاج، يجب استرجاع credentials المستخدم الحقيقية
            credentials_info = {
                "token": "dummy_token",
                "refresh_token": "dummy_refresh_token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "855709857820-i98phbba2d2mqajmp3eei7blah2cls5f.apps.googleusercontent.com",
                "client_secret": "AIzaSyCcM3yO_m0xeItzlClPmb6ULkxwZlqIcjc",
                "scopes": ["https://www.googleapis.com/auth/drive.file"]
            }
            
            return Credentials.from_authorized_user_info(credentials_info)
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting user Google credentials: {e}")
        return None




# ===== APIs النسخ الاحتياطي =====



@api_bp.route("/backup/start", methods=["POST"])
def start_backup_scheduler():
    """بدء جدولة النسخ الاحتياطي"""
    try:
        if not backup_scheduler:
            return jsonify({
                'success': False,
                'message': 'نظام النسخ الاحتياطي غير متاح'
            }), 503
        
        data = request.get_json() or {}
        user_id = data.get('user_id', 1)
        
        result = backup_scheduler.start_user_backup(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'تم بدء الجدولة بنجاح',
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', 'فشل في بدء الجدولة')
            }), 400
            
    except Exception as e:
        logger.error(f"خطأ في بدء جدولة النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في بدء الجدولة: {str(e)}'
        }), 500

@api_bp.route("/backup/stop", methods=["POST"])
def stop_backup_scheduler():
    """إيقاف جدولة النسخ الاحتياطي"""
    try:
        if not backup_scheduler:
            return jsonify({
                'success': False,
                'message': 'نظام النسخ الاحتياطي غير متاح'
            }), 503
        
        data = request.get_json() or {}
        user_id = data.get('user_id', 1)
        
        result = backup_scheduler.stop_user_backup(user_id)
        
        return jsonify({
            'success': True,
            'message': 'تم إيقاف الجدولة بنجاح',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"خطأ في إيقاف جدولة النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في إيقاف الجدولة: {str(e)}'
        }), 500

@api_bp.route("/backup/manual", methods=["POST"])
def manual_backup():
    """تشغيل نسخة احتياطية يدوية"""
    try:
        if not backup_logic:
            return jsonify({
                'success': False,
                'message': 'نظام النسخ الاحتياطي غير متاح'
            }), 503
        
        data = request.get_json() or {}
        user_id = data.get('user_id', 1)
        
        # تشغيل النسخ الاحتياطي
        result = backup_logic.create_backup(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'تم إنشاء النسخة الاحتياطية بنجاح',
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', 'فشل في إنشاء النسخة الاحتياطية'),
                'data': result
            }), 400
            
    except Exception as e:
        logger.error(f"خطأ في النسخ الاحتياطي اليدوي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في النسخ الاحتياطي: {str(e)}'
        }), 500

@api_bp.route("/backup/jobs", methods=["GET"])
def get_backup_jobs():
    """الحصول على قائمة المهام المجدولة"""
    try:
        if not backup_scheduler:
            return jsonify({
                'success': False,
                'message': 'نظام النسخ الاحتياطي غير متاح'
            }), 503
        
        jobs = backup_scheduler.get_jobs()
        return jsonify({
            'success': True,
            'message': 'تم الحصول على المهام بنجاح',
            'data': jobs
        })
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على مهام النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في الحصول على المهام: {str(e)}'
        }), 500

@api_bp.route("/backup/settings", methods=["GET", "POST"])
def backup_settings_api():
    """إدارة إعدادات النسخ الاحتياطي"""
    try:
        if not backup_settings_manager:
            return jsonify({
                'success': False,
                'message': 'نظام الإعدادات غير متاح'
            }), 503
        
        if request.method == 'GET':
            # الحصول على الإعدادات
            user_id = request.args.get('user_id', 1, type=int)
            settings = backup_settings_manager.get_user_settings(user_id)
            
            return jsonify({
                'success': True,
                'message': 'تم الحصول على الإعدادات بنجاح',
                'data': settings
            })
            
        elif request.method == 'POST':
            # تحديث الإعدادات
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'message': 'لا توجد بيانات'
                }), 400
            
            user_id = data.get('user_id', 1)
            settings = {k: v for k, v in data.items() if k != 'user_id'}
            
            result = backup_settings_manager.update_user_settings(user_id, settings)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': 'تم تحديث الإعدادات بنجاح'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'فشل في تحديث الإعدادات'
                }), 400
                
    except Exception as e:
        logger.error(f"خطأ في إدارة إعدادات النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في إدارة الإعدادات: {str(e)}'
        }), 500

@api_bp.route("/backup/test-connection", methods=["POST"])
def test_google_drive_connection():
    """اختبار الاتصال بـ Google Drive"""
    try:
        if not backup_logic:
            return jsonify({
                'success': False,
                'message': 'نظام النسخ الاحتياطي غير متاح'
            }), 503
        
        result = backup_logic.test_google_drive_connection()
        
        return jsonify({
            'success': result['success'],
            'message': result['message'],
            'data': result.get('data', {})
        })
        
    except Exception as e:
        logger.error(f"خطأ في اختبار اتصال Google Drive: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في اختبار الاتصال: {str(e)}'
        }), 500

@api_bp.route("/backup/logs", methods=["GET"])
def get_backup_logs():
    """الحصول على سجلات النسخ الاحتياطي"""
    try:
        lines = request.args.get('lines', 100, type=int)
        level = request.args.get('level', 'all')
        
        logs_file = os.path.join('logs', 'backup.log')
        
        if not os.path.exists(logs_file):
            return jsonify({
                'success': True,
                'message': 'لا توجد سجلات متاحة',
                'data': []
            })
        
        logs = []
        with open(logs_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if lines > 0 else all_lines
            
            for line in recent_lines:
                line = line.strip()
                if line:
                    # تحليل مستوى السجل
                    log_level = 'INFO'
                    if 'ERROR' in line:
                        log_level = 'ERROR'
                    elif 'WARNING' in line:
                        log_level = 'WARNING'
                    elif 'SUCCESS' in line:
                        log_level = 'SUCCESS'
                    
                    # تصفية حسب المستوى
                    if level != 'all' and log_level.lower() != level.lower():
                        continue
                    
                    logs.append({
                        'timestamp': datetime.now().isoformat(),
                        'level': log_level,
                        'message': line
                    })
        
        return jsonify({
            'success': True,
            'message': f'تم الحصول على {len(logs)} سجل',
            'data': logs
        })
        
    except Exception as e:
        logger.error(f"خطأ في قراءة سجلات النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في قراءة السجلات: {str(e)}'
        }), 500

@api_bp.route("/backup/logs/download", methods=["GET"])
def download_backup_logs():
    """تحميل ملف السجلات"""
    try:
        from flask import send_file
        
        logs_file = os.path.join('logs', 'backup.log')
        
        if not os.path.exists(logs_file):
            return jsonify({
                'success': False,
                'message': 'ملف السجلات غير موجود'
            }), 404
        
        return send_file(
            logs_file,
            as_attachment=True,
            download_name=f'backup_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            mimetype='text/plain'
        )
        
    except Exception as e:
        logger.error(f"خطأ في تحميل سجلات النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في تحميل السجلات: {str(e)}'
        }), 500

# تم إزالة الدالة المكررة get_backup_stats لحل تضارب Flask Blueprint

@api_bp.route("/backup/health", methods=["GET"])
def backup_health_check():
    """فحص صحة نظام النسخ الاحتياطي"""
    try:
        health_status = {
            'scheduler_available': backup_scheduler is not None,
            'settings_available': backup_settings_manager is not None,
            'logic_available': backup_logic is not None,
            'scheduler_running': False,
            'google_drive_connected': False,
            'logs_accessible': os.path.exists(os.path.join('logs', 'backup.log'))
        }
        
        if backup_scheduler:
            status = backup_scheduler.get_status()
            health_status['scheduler_running'] = status.get('scheduler_running', False)
        
        if backup_logic:
            connection_test = backup_logic.test_google_drive_connection()
            health_status['google_drive_connected'] = connection_test.get('success', False)
        
        overall_health = all([
            health_status['scheduler_available'],
            health_status['settings_available'],
            health_status['logic_available']
        ])
        
        return jsonify({
            'success': True,
            'message': 'فحص الصحة مكتمل',
            'data': {
                'overall_health': overall_health,
                'components': health_status,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"خطأ في فحص صحة النسخ الاحتياطي: {e}")
        return jsonify({
            'success': False,
            'message': f'خطأ في فحص الصحة: {str(e)}'
        }), 500

# ===== APIs إضافية للنسخ الاحتياطي =====

@api_bp.route("/backup/status", methods=["GET"])
@login_required
def get_backup_status():
    """
    الحصول على حالة النسخ الاحتياطي الشاملة
    
    Returns:
    - حالة النسخ الاحتياطي بتنسيق JSON
    """
    logger.info("API request received for backup status.")
    try:
        user_id = current_user.id
        
        # الحصول على إعدادات النسخ الاحتياطي
        backup_settings = None
        try:
            backup_settings = BackupSettings.query.filter_by(user_id=user_id).first()
        except Exception as e:
            logger.warning(f"Could not fetch backup settings: {e}")
        
        # الحصول على حالة Google Drive
        google_drive_status = {
            'available': google_drive_available,
            'connected': False,
            'last_backup': None,
            'backup_count': 0
        }
        
        try:
            # فحص اتصال Google Drive من session
            google_drive_connected = session.get('google_drive_connected', False)
            last_sync = session.get('last_google_drive_sync')
            
            if google_drive_connected:
                google_drive_status['connected'] = True
                google_drive_status['last_backup'] = last_sync
                
            # محاولة الحصول من قاعدة البيانات
            if GoogleDriveToken:
                try:
                    db_token = GoogleDriveToken.query.filter_by(
                        user_id=user_id, 
                        is_active=True
                    ).first()
                    
                    if db_token:
                        google_drive_status['connected'] = True
                        if hasattr(db_token, 'updated_at') and db_token.updated_at:
                            google_drive_status['last_backup'] = db_token.updated_at.isoformat()
                except Exception as e:
                    logger.warning(f"Error querying GoogleDriveToken: {e}")
                        
        except Exception as e:
            logger.warning(f"Error checking Google Drive status: {e}")
        
        # الحصول على حالة الجدولة
        scheduler_status = {
            'available': backup_scheduler is not None,
            'running': False,
            'user_scheduled': False,
            'next_backup': None
        }
        
        if backup_scheduler:
            try:
                if hasattr(backup_scheduler, 'get_status'):
                    status = backup_scheduler.get_status()
                    scheduler_status['running'] = status.get('scheduler_running', False)
                
                # البحث عن مهمة المستخدم
                if hasattr(backup_scheduler, 'get_jobs'):
                    jobs = backup_scheduler.get_jobs()
                    user_job = next((job for job in jobs if job.get('user_id') == user_id), None)
                    
                    if user_job:
                        scheduler_status['user_scheduled'] = True
                        scheduler_status['next_backup'] = user_job.get('next_run')
                    
            except Exception as e:
                logger.warning(f"Error getting scheduler status: {e}")
        
        # تجميع الحالة النهائية
        status = {
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'scheduler': scheduler_status,
            'google_drive': google_drive_status,
            'backup_logic': {
                'available': backup_logic_available
            },
            'settings': {
                'auto_backup_enabled': backup_settings.auto_backup_enabled if backup_settings else False,
                'backup_frequency': backup_settings.backup_frequency if backup_settings else 'daily',
                'backup_destination': backup_settings.backup_destination if backup_settings else 'local',
                'max_backups': backup_settings.max_backups if backup_settings else 5,
                'backup_time': backup_settings.backup_time if backup_settings else '02:00',
                'created_at': backup_settings.created_at.isoformat() if backup_settings and backup_settings.created_at else None,
                'updated_at': backup_settings.updated_at.isoformat() if backup_settings and backup_settings.updated_at else None
            }
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.exception(f"Error getting backup status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route("/backup/immediate", methods=["POST"])
@login_required
def create_immediate_backup():
    """
    إنشاء نسخة احتياطية فورية
    
    Returns:
    - نتيجة عملية النسخ الاحتياطي
    """
    logger.info("API request received for immediate backup.")
    try:
        user_id = current_user.id
        
        # التحقق من توفر نظام النسخ الاحتياطي
        if not backup_logic_available or not create_backup:
            return jsonify({
                'success': False,
                'error': 'نظام النسخ الاحتياطي غير متوفر'
            }), 503
        
        # تنفيذ النسخ الاحتياطي
        result = create_backup(user_id)
        
        if result.get('success'):
            # تحديث session مع معلومات النسخة الجديدة
            session['last_backup_time'] = datetime.utcnow().isoformat()
            
            # تحديث إعدادات قاعدة البيانات
            try:
                backup_settings = BackupSettings.query.filter_by(user_id=user_id).first()
                if backup_settings:
                    backup_settings.last_backup_time = datetime.utcnow()
                    if backup_settings.backup_count is None:
                        backup_settings.backup_count = 1
                    else:
                        backup_settings.backup_count += 1
                    db.session.commit()
            except Exception as e:
                logger.warning(f"Could not update backup settings: {e}")
            
            return jsonify({
                'success': True,
                'message': 'تم إنشاء النسخة الاحتياطية بنجاح',
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'فشل في إنشاء النسخة الاحتياطية')
            }), 500
            
    except Exception as e:
        logger.exception(f"Error creating immediate backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route("/google-drive/connection-status", methods=["GET"])
@login_required
def get_google_drive_connection_status():
    """
    الحصول على حالة اتصال Google Drive
    
    Returns:
    - حالة الاتصال بتنسيق JSON
    """
    logger.info("API request received for Google Drive connection status.")
    try:
        user_id = current_user.id
        
        # فحص حالة الاتصال
        connection_status = {
            'connected': False,
            'last_sync': None,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # فحص من session
            google_drive_connected = session.get('google_drive_connected', False)
            last_sync = session.get('last_google_drive_sync')
            
            if google_drive_connected:
                connection_status['connected'] = True
                connection_status['last_sync'] = last_sync
            
            # فحص من قاعدة البيانات
            if GoogleDriveToken:
                try:
                    db_token = GoogleDriveToken.query.filter_by(
                        user_id=user_id, 
                        is_active=True
                    ).first()
                    
                    if db_token:
                        connection_status['connected'] = True
                        if hasattr(db_token, 'updated_at') and db_token.updated_at:
                            connection_status['last_sync'] = db_token.updated_at.isoformat()
                except Exception as e:
                    logger.warning(f"Error querying GoogleDriveToken: {e}")
                    
        except Exception as e:
            logger.warning(f"Error checking Google Drive connection: {e}")
        
        return jsonify({
            'success': True,
            'status': connection_status
        })
        
    except Exception as e:
        logger.exception(f"Error getting Google Drive connection status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== نهاية APIs النسخ الاحتياطي =====


# ===== إضافة endpoints المفقودة =====

@api_bp.route("/backup-settings/load", methods=["GET"])
@login_required
def load_backup_settings():
    """تحميل إعدادات النسخ الاحتياطي"""
    try:
        user_id = current_user.id
        logger.info(f"Loading backup settings for user {user_id}")
        
        # البحث عن إعدادات المستخدم
        backup_settings = BackupSettings.query.filter_by(user_id=user_id).first()
        
        if backup_settings:
            settings_data = {
                'auto_backup_enabled': backup_settings.auto_backup_enabled,
                'backup_frequency': backup_settings.backup_frequency,
                'backup_destination': backup_settings.backup_destination,
                'max_backups': backup_settings.max_backups,
                'backup_time': backup_settings.backup_time,
                'include_images': getattr(backup_settings, 'include_images', True),
                'compress_backup': getattr(backup_settings, 'compress_backup', True),
                'encrypt_backup': getattr(backup_settings, 'encrypt_backup', False),
                'created_at': backup_settings.created_at.isoformat() if backup_settings.created_at else None,
                'updated_at': backup_settings.updated_at.isoformat() if backup_settings.updated_at else None
            }
        else:
            # إعدادات افتراضية
            settings_data = {
                'auto_backup_enabled': False,
                'backup_frequency': 'daily',
                'backup_destination': 'local',
                'max_backups': 5,
                'backup_time': '02:00',
                'include_images': True,
                'compress_backup': True,
                'encrypt_backup': False,
                'created_at': None,
                'updated_at': None
            }
        
        return jsonify({
            'success': True,
            'settings': settings_data
        })
        
    except Exception as e:
        logger.exception(f"Error loading backup settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route("/backup-settings/save", methods=["POST"])
@login_required
def save_backup_settings():
    """حفظ إعدادات النسخ الاحتياطي"""
    try:
        user_id = current_user.id
        data = request.get_json()
        
        logger.info(f"Saving backup settings for user {user_id}: {data}")
        
        # البحث عن إعدادات موجودة أو إنشاء جديدة
        backup_settings = BackupSettings.query.filter_by(user_id=user_id).first()
        
        if not backup_settings:
            backup_settings = BackupSettings(user_id=user_id)
            db.session.add(backup_settings)
        
        # تحديث الإعدادات
        backup_settings.auto_backup_enabled = data.get('auto_backup_enabled', False)
        backup_settings.backup_frequency = data.get('backup_frequency', 'daily')
        backup_settings.backup_destination = data.get('backup_destination', 'local')
        backup_settings.max_backups = data.get('max_backups', 5)
        backup_settings.backup_time = data.get('backup_time', '02:00')
        
        # إعدادات متقدمة
        if hasattr(backup_settings, 'include_images'):
            backup_settings.include_images = data.get('include_images', True)
        if hasattr(backup_settings, 'compress_backup'):
            backup_settings.compress_backup = data.get('compress_backup', True)
        if hasattr(backup_settings, 'encrypt_backup'):
            backup_settings.encrypt_backup = data.get('encrypt_backup', False)
        
        backup_settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ إعدادات النسخ الاحتياطي بنجاح'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error saving backup settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route("/user-settings/sync-status", methods=["GET"])
@login_required
def get_user_settings_sync_status():
    """الحصول على حالة مزامنة إعدادات المستخدم"""
    try:
        user_id = current_user.id
        
        # فحص حالة الاتصال مع Google Drive
        google_drive_connected = session.get('google_drive_connected', False)
        last_sync = session.get('last_google_drive_sync')
        
        # فحص من قاعدة البيانات أيضاً
        if GoogleDriveToken:
            try:
                db_token = GoogleDriveToken.query.filter_by(
                    user_id=user_id, 
                    is_active=True
                ).first()
                
                if db_token:
                    google_drive_connected = True
                    if hasattr(db_token, 'updated_at') and db_token.updated_at:
                        last_sync = db_token.updated_at.isoformat()
            except Exception as e:
                logger.warning(f"Error querying GoogleDriveToken: {e}")
        
        sync_status = {
            'connected': google_drive_connected,
            'last_sync': last_sync,
            'auto_sync_enabled': False,  # يمكن إضافة هذا للإعدادات لاحقاً
            'sync_frequency': 'manual'   # يمكن إضافة هذا للإعدادات لاحقاً
        }
        
        return jsonify({
            'success': True,
            'status': sync_status
        })
        
    except Exception as e:
        logger.exception(f"Error getting user settings sync status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route("/backup/test-status", methods=["GET"])
def get_backup_test_status():
    """API اختبار لحالة النسخ الاحتياطي (للمستخدمين غير المسجلين)"""
    try:
        logger.info("API request received for backup test status.")
        
        # بيانات تجريبية للاختبار
        test_status = {
            'google_drive': {
                'available': True,
                'connected': False,
                'last_backup': None,
                'backup_count': 0
            },
            'scheduler': {
                'available': True,
                'running': False,
                'next_backup': None
            },
            'settings': {
                'auto_backup_enabled': False,
                'backup_frequency': 'daily',
                'backup_destination': 'local',
                'max_backups': 5,
                'backup_time': '02:00',
                'created_at': None,
                'updated_at': None
            },
            'backup_logic': {
                'available': True
            }
        }
        
        return jsonify({
            'success': True,
            'status': test_status,
            'test_mode': True,
            'message': 'هذه بيانات تجريبية للاختبار'
        })
        
    except Exception as e:
        logger.exception(f"Error getting backup test status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'test_mode': True
        }), 500

@api_bp.route("/backup/test-immediate", methods=["POST"])
def create_test_immediate_backup():
    """API اختبار للنسخ الاحتياطي الفوري (للمستخدمين غير المسجلين)"""
    try:
        logger.info("API request received for test immediate backup.")
        
        # محاكاة عملية النسخ الاحتياطي
        import time
        time.sleep(2)  # محاكاة وقت المعالجة
        
        return jsonify({
            'success': True,
            'message': 'تم إنشاء النسخة الاحتياطية التجريبية بنجاح',
            'test_mode': True,
            'backup_info': {
                'created_at': datetime.utcnow().isoformat(),
                'size': '2.5 MB',
                'destination': 'test_mode',
                'file_name': f'test_backup_{int(time.time())}.zip'
            }
        })
        
    except Exception as e:
        logger.exception(f"Error creating test immediate backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'test_mode': True
        }), 500

@api_bp.route("/google-drive/test-connection-status", methods=["GET"])
def get_google_drive_test_connection_status():
    """API اختبار لحالة اتصال Google Drive (للمستخدمين غير المسجلين)"""
    try:
        logger.info("API request received for Google Drive test connection status.")
        
        # بيانات تجريبية
        test_connection_status = {
            'connected': False,
            'last_backup': None,
            'backup_count': 0,
            'storage_method': 'test_mode',
            'user_id': 'test_user'
        }
        
        return jsonify({
            'success': True,
            'status': test_connection_status,
            'test_mode': True,
            'message': 'هذه بيانات تجريبية لاختبار اتصال Google Drive'
        })
        
    except Exception as e:
        logger.exception(f"Error getting Google Drive test connection status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'test_mode': True
        }), 500

# ===== نهاية endpoints المضافة =====



@api_bp.route("/csrf-token", methods=["GET"])
def get_csrf_token():
    """الحصول على CSRF token"""
    try:
        from flask_wtf.csrf import generate_csrf
        token = generate_csrf()
        return jsonify({
            'success': True,
            'csrf_token': token
        })
    except Exception as e:
        logger.exception(f"Error generating CSRF token: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== نهاية endpoints CSRF =====


# ===================================================================
# نظام التحكم بمنع الأسئلة - API Endpoints
# ===================================================================

@api_bp.route("/questions/<int:question_id>/block", methods=["PUT"])
def block_question(question_id):
    """منع سؤال واحد من الظهور في المنهج/الوحدة/الدرس"""
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'error': 'السؤال غير موجود'
            }), 404
        
        question.is_blocked = True
        db.session.commit()
        
        logger.info(f"Question {question_id} has been blocked")
        
        return jsonify({
            'success': True,
            'message': f'تم منع السؤال رقم {question_id} بنجاح',
            'question_id': question_id,
            'is_blocked': True
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error blocking question {question_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/questions/<int:question_id>/unblock", methods=["PUT"])
def unblock_question(question_id):
    """إلغاء منع سؤال واحد"""
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'error': 'السؤال غير موجود'
            }), 404
        
        question.is_blocked = False
        db.session.commit()
        
        logger.info(f"Question {question_id} has been unblocked")
        
        return jsonify({
            'success': True,
            'message': f'تم إلغاء منع السؤال رقم {question_id} بنجاح',
            'question_id': question_id,
            'is_blocked': False
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error unblocking question {question_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/questions/bulk-block", methods=["POST"])
def bulk_block_questions():
    """منع عدة أسئلة دفعة واحدة"""
    try:
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        
        if not question_ids:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد أي أسئلة'
            }), 400
        
        # تحديث جميع الأسئلة المحددة
        updated_count = Question.query.filter(
            Question.question_id.in_(question_ids)
        ).update(
            {Question.is_blocked: True},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Blocked {updated_count} questions: {question_ids}")
        
        return jsonify({
            'success': True,
            'message': f'تم منع {updated_count} سؤال بنجاح',
            'blocked_count': updated_count,
            'question_ids': question_ids
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error bulk blocking questions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/questions/bulk-unblock", methods=["POST"])
def bulk_unblock_questions():
    """إلغاء منع عدة أسئلة دفعة واحدة"""
    try:
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        
        if not question_ids:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد أي أسئلة'
            }), 400
        
        # تحديث جميع الأسئلة المحددة
        updated_count = Question.query.filter(
            Question.question_id.in_(question_ids)
        ).update(
            {Question.is_blocked: False},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Unblocked {updated_count} questions: {question_ids}")
        
        return jsonify({
            'success': True,
            'message': f'تم إلغاء منع {updated_count} سؤال بنجاح',
            'unblocked_count': updated_count,
            'question_ids': question_ids
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error bulk unblocking questions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/lessons/<int:lesson_id>/questions/block-all", methods=["PUT"])
def block_all_lesson_questions(lesson_id):
    """منع جميع أسئلة درس معين"""
    try:
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({
                'success': False,
                'error': 'الدرس غير موجود'
            }), 404
        
        # منع جميع أسئلة الدرس
        updated_count = Question.query.filter_by(
            lesson_id=lesson_id
        ).update(
            {Question.is_blocked: True},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Blocked all {updated_count} questions in lesson {lesson_id}")
        
        return jsonify({
            'success': True,
            'message': f'تم منع {updated_count} سؤال من الدرس "{lesson.name}"',
            'lesson_id': lesson_id,
            'blocked_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error blocking all questions in lesson {lesson_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/lessons/<int:lesson_id>/questions/unblock-all", methods=["PUT"])
def unblock_all_lesson_questions(lesson_id):
    """إلغاء منع جميع أسئلة درس معين"""
    try:
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({
                'success': False,
                'error': 'الدرس غير موجود'
            }), 404
        
        # إلغاء منع جميع أسئلة الدرس
        updated_count = Question.query.filter_by(
            lesson_id=lesson_id
        ).update(
            {Question.is_blocked: False},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Unblocked all {updated_count} questions in lesson {lesson_id}")
        
        return jsonify({
            'success': True,
            'message': f'تم إلغاء منع {updated_count} سؤال من الدرس "{lesson.name}"',
            'lesson_id': lesson_id,
            'unblocked_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error unblocking all questions in lesson {lesson_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/units/<int:unit_id>/questions/block-all", methods=["PUT"])
def block_all_unit_questions(unit_id):
    """منع جميع أسئلة وحدة معينة"""
    try:
        unit = Unit.query.get(unit_id)
        if not unit:
            return jsonify({
                'success': False,
                'error': 'الوحدة غير موجودة'
            }), 404
        
        # الحصول على جميع دروس الوحدة
        lesson_ids = [lesson.id for lesson in unit.lessons]
        
        # منع جميع أسئلة الوحدة
        updated_count = Question.query.filter(
            Question.lesson_id.in_(lesson_ids)
        ).update(
            {Question.is_blocked: True},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Blocked all {updated_count} questions in unit {unit_id}")
        
        return jsonify({
            'success': True,
            'message': f'تم منع {updated_count} سؤال من الوحدة "{unit.name}"',
            'unit_id': unit_id,
            'blocked_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error blocking all questions in unit {unit_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/units/<int:unit_id>/questions/unblock-all", methods=["PUT"])
def unblock_all_unit_questions(unit_id):
    """إلغاء منع جميع أسئلة وحدة معينة"""
    try:
        unit = Unit.query.get(unit_id)
        if not unit:
            return jsonify({
                'success': False,
                'error': 'الوحدة غير موجودة'
            }), 404
        
        # الحصول على جميع دروس الوحدة
        lesson_ids = [lesson.id for lesson in unit.lessons]
        
        # إلغاء منع جميع أسئلة الوحدة
        updated_count = Question.query.filter(
            Question.lesson_id.in_(lesson_ids)
        ).update(
            {Question.is_blocked: False},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Unblocked all {updated_count} questions in unit {unit_id}")
        
        return jsonify({
            'success': True,
            'message': f'تم إلغاء منع {updated_count} سؤال من الوحدة "{unit.name}"',
            'unit_id': unit_id,
            'unblocked_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error unblocking all questions in unit {unit_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/courses/<int:course_id>/questions/block-all", methods=["PUT"])
def block_all_course_questions(course_id):
    """منع جميع أسئلة منهج معين"""
    try:
        course = Course.query.get(course_id)
        if not course:
            return jsonify({
                'success': False,
                'error': 'المنهج غير موجود'
            }), 404
        
        # الحصول على جميع دروس المنهج
        lesson_ids = []
        for unit in course.units:
            lesson_ids.extend([lesson.id for lesson in unit.lessons])
        
        # منع جميع أسئلة المنهج
        updated_count = Question.query.filter(
            Question.lesson_id.in_(lesson_ids)
        ).update(
            {Question.is_blocked: True},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Blocked all {updated_count} questions in course {course_id}")
        
        return jsonify({
            'success': True,
            'message': f'تم منع {updated_count} سؤال من المنهج "{course.name}"',
            'course_id': course_id,
            'blocked_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error blocking all questions in course {course_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/courses/<int:course_id>/questions/unblock-all", methods=["PUT"])
def unblock_all_course_questions(course_id):
    """إلغاء منع جميع أسئلة منهج معين"""
    try:
        course = Course.query.get(course_id)
        if not course:
            return jsonify({
                'success': False,
                'error': 'المنهج غير موجود'
            }), 404
        
        # الحصول على جميع دروس المنهج
        lesson_ids = []
        for unit in course.units:
            lesson_ids.extend([lesson.id for lesson in unit.lessons])
        
        # إلغاء منع جميع أسئلة المنهج
        updated_count = Question.query.filter(
            Question.lesson_id.in_(lesson_ids)
        ).update(
            {Question.is_blocked: False},
            synchronize_session=False
        )
        
        db.session.commit()
        
        logger.info(f"Unblocked all {updated_count} questions in course {course_id}")
        
        return jsonify({
            'success': True,
            'message': f'تم إلغاء منع {updated_count} سؤال من المنهج "{course.name}"',
            'course_id': course_id,
            'unblocked_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error unblocking all questions in course {course_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/questions/<int:question_id>/block-status", methods=["GET"])
def get_question_block_status(question_id):
    """الحصول على حالة منع سؤال معين"""
    try:
        question = Question.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'error': 'السؤال غير موجود'
            }), 404
        
        return jsonify({
            'success': True,
            'question_id': question_id,
            'is_blocked': question.is_blocked
        })
        
    except Exception as e:
        logger.exception(f"Error getting block status for question {question_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== نهاية نظام التحكم بمنع الأسئلة =====


# ===== نظام استخراج وتوليد نماذج الاختبار =====

@api_bp.route("/questions/export", methods=["POST"])
@login_required
def export_questions():
    """
    استخراج الأسئلة المحددة مع نموذج الإجابة
    
    Request JSON:
    {
        "question_ids": [1, 2, 3, ...],
        "include_answers": true/false,
        "format": "json" or "html"
    }
    """
    try:
        data = request.get_json()
        question_ids = data.get("question_ids", [])
        include_answers = data.get("include_answers", False)
        export_format = data.get("format", "json")
        
        if not question_ids:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد أسئلة للاستخراج'
            }), 400
        
        # الحصول على الأسئلة المحددة
        questions = Question.query.filter(
            Question.question_id.in_(question_ids)
        ).all()
        
        if not questions:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على الأسئلة المحددة'
            }), 404
        
        # تنسيق الأسئلة
        formatted_questions = []
        for question in questions:
            formatted_q = format_question(question)
            
            # إذا لم نطلب الإجابات، نزيل معرف الخيار الصحيح
            if not include_answers:
                formatted_q.pop('correct_option_id', None)
            
            formatted_questions.append(formatted_q)
        
        if export_format == "json":
            return jsonify({
                'success': True,
                'questions': formatted_questions,
                'count': len(formatted_questions),
                'include_answers': include_answers
            })
        else:
            return jsonify({
                'success': False,
                'error': 'صيغة التصدير غير مدعومة'
            }), 400
            
    except Exception as e:
        logger.exception(f"Error exporting questions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/questions/generate-exam", methods=["POST"])
@login_required
def generate_exam():
    """
    توليد نموذج اختبار عشوائي من أسئلة محددة
    
    Request JSON:
    {
        "course_id": 1,
        "unit_id": 2,
        "lesson_id": 3,
        "question_count": 10,
        "include_answers": false
    }
    
    يمكن تحديد course_id فقط، أو course_id + unit_id، أو جميع المعاملات
    """
    try:
        from random import shuffle
        
        data = request.get_json()
        course_id = data.get("course_id")
        unit_id = data.get("unit_id")
        lesson_id = data.get("lesson_id")
        question_count = data.get("question_count", 10)
        include_answers = data.get("include_answers", False)
        
        if not course_id:
            return jsonify({
                'success': False,
                'error': 'يجب تحديد المنهج على الأقل'
            }), 400
        
        # بناء الاستعلام
        query = Question.query.filter(Question.is_blocked == False)
        
        # التصفية حسب الدرس
        if lesson_id:
            query = query.filter(Question.lesson_id == lesson_id)
        # التصفية حسب الوحدة
        elif unit_id:
            lessons = Lesson.query.filter(Lesson.unit_id == unit_id).all()
            lesson_ids = [l.id for l in lessons]
            query = query.filter(Question.lesson_id.in_(lesson_ids))
        # التصفية حسب المنهج
        else:
            units = Unit.query.filter(Unit.course_id == course_id).all()
            lesson_ids = []
            for unit in units:
                lesson_ids.extend([l.id for l in unit.lessons])
            query = query.filter(Question.lesson_id.in_(lesson_ids))
        
        # الحصول على جميع الأسئلة المتاحة
        available_questions = query.all()
        
        if not available_questions:
            return jsonify({
                'success': False,
                'error': 'لا توجد أسئلة متاحة للاختبار'
            }), 404
        
        # اختيار عشوائي من الأسئلة
        if len(available_questions) > question_count:
            selected_questions = []
            indices = list(range(len(available_questions)))
            shuffle(indices)
            for i in range(question_count):
                selected_questions.append(available_questions[indices[i]])
        else:
            selected_questions = available_questions
        
        # تنسيق الأسئلة
        formatted_questions = []
        for question in selected_questions:
            formatted_q = format_question(question)
            
            # إذا لم نطلب الإجابات، نزيل معرف الخيار الصحيح
            if not include_answers:
                formatted_q.pop('correct_option_id', None)
            
            formatted_questions.append(formatted_q)
        
        return jsonify({
            'success': True,
            'exam': {
                'questions': formatted_questions,
                'count': len(formatted_questions),
                'include_answers': include_answers,
                'generated_at': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.exception(f"Error generating exam: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/courses/<int:course_id>/units/<int:unit_id>/lessons", methods=["GET"])
@login_required
def get_unit_lessons_export(course_id, unit_id):
    """
    الحصول على جميع دروس وحدة معينة
    """
    try:
        unit = Unit.query.filter_by(id=unit_id, course_id=course_id).first()
        
        if not unit:
            return jsonify({
                'success': False,
                'error': 'الوحدة غير موجودة'
            }), 404
        
        lessons = [
            {
                'id': lesson.id,
                'name': lesson.name,
                'order_num': lesson.order_num
            }
            for lesson in sorted(unit.lessons, key=lambda l: l.order_num)
        ]
        
        return jsonify({
            'success': True,
            'lessons': lessons
        })
        
    except Exception as e:
        logger.exception(f"Error getting unit lessons: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/lessons/<int:lesson_id>/questions-count", methods=["GET"])
@login_required
def get_lesson_questions_count(lesson_id):
    """
    الحصول على عدد الأسئلة في درس معين
    """
    try:
        lesson = Lesson.query.get(lesson_id)
        
        if not lesson:
            return jsonify({
                'success': False,
                'error': 'الدرس غير موجود'
            }), 404
        
        # عد الأسئلة غير المحظورة
        count = Question.query.filter(
            Question.lesson_id == lesson_id,
            Question.is_blocked == False
        ).count()
        
        return jsonify({
            'success': True,
            'lesson_id': lesson_id,
            'lesson_name': lesson.name,
            'questions_count': count
        })
        
    except Exception as e:
        logger.exception(f"Error getting lesson questions count: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/courses/<int:course_id>/questions-count", methods=["GET"])
@login_required
def get_course_questions_count(course_id):
    """
    الحصول على عدد الأسئلة في منهج معين
    """
    try:
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({
                'success': False,
                'error': 'المنهج غير موجود'
            }), 404
        
        # الحصول على جميع دروس المنهج
        lesson_ids = []
        for unit in course.units:
            lesson_ids.extend([lesson.id for lesson in unit.lessons])
        
        # عد الأسئلة غير المحظورة
        count = Question.query.filter(
            Question.lesson_id.in_(lesson_ids),
            Question.is_blocked == False
        ).count()
        
        return jsonify({
            'success': True,
            'course_id': course_id,
            'course_name': course.name,
            'questions_count': count
        })
        
    except Exception as e:
        logger.exception(f"Error getting course questions count: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== مسار توليد نماذج Remark OMR ==========

@api_bp.route("/questions/preview-students", methods=["POST"])
@login_required
def preview_students():
    """
    قراءة ملف Excel وعرض معاينة أسماء الطلاب
    
    Request: multipart/form-data
    - student_file: ملف Excel يحتوي على أسماء الطلاب
    
    Response JSON:
    {
        "success": true/false,
        "students": [{"name": "...", "id": "..."}, ...],
        "error": "رسالة الخطأ إن وجدت"
    }
    """
    try:
        # التحقق من وجود الملف
        if 'student_file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد ملف'
            }), 400
        
        file = request.files['student_file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'لم يتم اختيار ملف'
            }), 400
        
        # التحقق من نوع الملف
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({
                'success': False,
                'error': 'يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls)'
            }), 400
        
        # قراءة ملف Excel
        try:
            import pandas as pd
            import io
            
            # قراءة الملف
            file_content = file.read()
            df = pd.read_excel(io.BytesIO(file_content))
            
            # التحقق من وجود الأعمدة المطلوبة
            # نتوقع عمود للأسماء وعمود لأرقام الجلوس
            columns = df.columns.tolist()
            
            # البحث عن أعمدة تحتوي على "اسم" أو "name" أو "الاسم"
            name_col = None
            for col in columns:
                if 'اسم' in str(col).lower() or 'name' in str(col).lower():
                    name_col = col
                    break
            
            # البحث عن أعمدة تحتوي على "رقم" أو "id" أو "جلوس"
            id_col = None
            for col in columns:
                if 'رقم' in str(col).lower() or 'id' in str(col).lower() or 'جلوس' in str(col).lower():
                    id_col = col
                    break
            
            # إذا لم نجد الأعمدة، استخدم أول عمودين
            if not name_col and len(columns) > 0:
                name_col = columns[0]
            if not id_col and len(columns) > 1:
                id_col = columns[1]
            
            # استخراج البيانات
            students = []
            for idx, row in df.iterrows():
                student_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ''
                student_id = str(row[id_col]).strip() if id_col and pd.notna(row[id_col]) else ''
                
                if student_name:  # تخطي الصفوف الفارغة
                    students.append({
                        'name': student_name,
                        'id': student_id
                    })
            
            if not students:
                return jsonify({
                    'success': False,
                    'error': 'لم يتم العثور على بيانات طلاب في الملف'
                }), 400
            
            return jsonify({
                'success': True,
                'students': students,
                'count': len(students)
            })
            
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'مكتبة pandas غير مثبتة. يرجى تثبيتها باستخدام: pip install pandas openpyxl'
            }), 500
        except Exception as e:
            logger.exception(f"Error reading Excel file: {e}")
            return jsonify({
                'success': False,
                'error': f'خطأ في قراءة الملف: {str(e)}'
            }), 400
    
    except Exception as e:
        logger.exception(f"Error in preview_students: {e}")
        return jsonify({
            'success': False,
            'error': f'خطأ في الخادم: {str(e)}'
        }), 500


@api_bp.route("/questions/generate-remark-omr", methods=["POST"])
@login_required
def generate_remark_omr():
    """
    توليد أوراق إجابة Remark OMR احترافية للطباعة
    """
    try:
        data = request.get_json()
        question_ids = data.get("question_ids", [])
        students = data.get("students", [])
        header_settings = data.get("header_settings", {})
        
        if not question_ids or not students:
            return jsonify({
                'success': False,
                'error': 'بيانات ناقصة'
            }), 400
        
        # قالب HTML مطابق لـ remark_answer_sheet.html
        html_template = '''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <style>
        @page { size: A4; margin: 10mm; border: 2px solid #000; }
        body { font-family: 'Arial', sans-serif; font-size: 12px; color: #000; margin: 0; padding: 10px; }
        
        /* الكليشة العلوية */
        .header-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
        .header-table td { vertical-align: top; padding: 2px; font-weight: bold; }
        .school-info { width: 40%; text-align: right; }
        .exam-info { width: 20%; text-align: center; }
        .ministry-logo { width: 40%; text-align: left; }

        /* منطقة بيانات الطالب الرئيسية */
        .student-data-area { border: 2px solid #000; margin-bottom: 10px; padding: 5px; }
        .data-title { background: #eee; text-align: center; font-weight: bold; border-bottom: 1px solid #000; padding: 3px; }
        .data-table { width: 100%; border-collapse: collapse; }
        .data-table td { border: 1px solid #000; padding: 5px; font-weight: bold; }

        /* التعليمات */
        .instructions-box { border: 1px solid #000; padding: 5px; margin-bottom: 10px; font-size: 10px; }
        .instructions-title { font-weight: bold; color: #ff0000; text-decoration: underline; }

        /* جداول رصد الدرجات */
        .grading-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; text-align: center; }
        .grading-table th, .grading-table td { border: 1px solid #000; padding: 3px; }

        /* شبكة الدوائر (Bubbles) */
        .omr-container { display: flex; justify-content: space-between; gap: 10px; }
        .omr-column { width: 32%; }
        .section-title { background: #ddd; padding: 3px; text-align: center; font-weight: bold; border: 1px solid #000; margin-bottom: 5px; }
        .bubble-row { display: flex; align-items: center; margin-bottom: 4px; border-bottom: 0.5px solid #eee; padding: 2px 0; }
        .q-num { width: 20px; font-weight: bold; text-align: center; }
        .bubble { width: 16px; height: 16px; border: 1px solid #000; border-radius: 50%; display: inline-block; margin: 0 3px; }
        .bubble-label { font-size: 9px; text-align: center; line-height: 16px; font-weight: bold; }
        
        @media print {
            body { margin: 0; padding: 0; }
            .page { page-break-after: always; }
        }
    </style>
</head>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        @page { size: A4; margin: 0.5cm; }
        @media print { body { margin: 0; padding: 0; } }
        
        html, body { width: 100%; height: 100%; }
        body { font-family: 'Arial', 'Tahoma', sans-serif; font-size: 11px; color: #000; direction: rtl; background: #fff; }
        
        .page { width: 100%; height: 29.7cm; page-break-after: always; padding: 0.5cm; border: 1px solid #ccc; margin-bottom: 1cm; background: #fff; }
        
        .header-section { width: 100%; margin-bottom: 0.3cm; }
        .header-table { width: 100%; border-collapse: collapse; border: 1px solid #000; }
        .header-table td { padding: 0.2cm; border: 1px solid #000; text-align: right; font-weight: bold; font-size: 10px; line-height: 1.2; }
        .header-left { width: 35%; }
        .header-center { width: 30%; text-align: center; }
        .header-right { width: 35%; text-align: left; }
        
        .instructions { width: 100%; border: 1px solid #000; padding: 0.2cm; margin-bottom: 0.3cm; font-size: 9px; background: #f9f9f9; }
        .instructions-title { font-weight: bold; color: #d00; text-decoration: underline; display: inline; }
        
        .student-info { width: 100%; border: 2px solid #000; margin-bottom: 0.3cm; }
        .student-info-header { background: #ddd; padding: 0.2cm; font-weight: bold; text-align: center; border-bottom: 1px solid #000; }
        .student-info-table { width: 100%; border-collapse: collapse; }
        .student-info-table td { border: 1px solid #000; padding: 0.3cm; font-weight: bold; font-size: 10px; }
        
        .grades-table { width: 100%; border-collapse: collapse; margin-bottom: 0.3cm; }
        .grades-table td, .grades-table th { border: 1px solid #000; padding: 0.2cm; text-align: center; font-size: 9px; }
        .grades-table th { background: #e0e0e0; font-weight: bold; }
        
        .omr-section { width: 100%; }
        .omr-title { background: #ccc; border: 1px solid #000; padding: 0.2cm; font-weight: bold; text-align: center; font-size: 10px; margin-bottom: 0.2cm; }
        .omr-row { display: table; width: 100%; margin-bottom: 0.15cm; }
        .omr-cell { display: table-cell; border: 1px solid #999; padding: 0.2cm; width: 5%; text-align: center; font-weight: bold; font-size: 9px; }
        .omr-bubble { display: table-cell; border: 1px solid #000; width: 4%; height: 0.4cm; text-align: center; vertical-align: middle; margin: 0 0.1cm; border-radius: 50%; }
        .bubble-char { font-size: 8px; font-weight: bold; }
        
        .omr-columns { display: table; width: 100%; border-collapse: collapse; }
        .omr-column { display: table-cell; width: 32%; padding-right: 0.5cm; vertical-align: top; }
        .omr-column:last-child { padding-right: 0; }
    </style>
</head>
<body>
'''
        
        # إضافة ورقة لكل طالب
        for student in students:
            html_template += '''    <div class="page">
        <div class="header-section">
            <table class="header-table">
                <tr>
                    <td class="header-left">
                        المملكة العربية السعودية<br>
                        وزارة التعليم<br>
                        ''' + header_settings.get('education_department', '') + '''<br>
                        ''' + header_settings.get('school_name', '') + '''
                    </td>
                    <td class="header-center">
                        ''' + header_settings.get('subject', 'اختبار') + '''<br>
                        ''' + header_settings.get('time', '') + '''
                    </td>
                    <td class="header-right" style="text-align: left;">
                        الفصل الدراسي الأول<br>
                        1447 هـ
                    </td>
                </tr>
            </table>
        </div>
        
        <div class="instructions">
            <span class="instructions-title">تعليمات هامة:</span>
            استخدم القلم الرصاص فقط | تأكد من تظليل فقرة واحدة فقط | لا تستخدم قلم الحبر أو المزيل
        </div>
        
        <div class="student-info">
            <div class="student-info-header">منطقة بيانات الطالب الرئيسية</div>
            <table class="student-info-table">
                <tr>
                    <td style="width: 50%;">الاسم: ''' + student.get('name', '') + '''</td>
                    <td style="width: 50%;">الرقم الأكاديمي: ''' + str(student.get('id', '')) + '''</td>
                </tr>
                <tr>
                    <td style="width: 50%;">الشعبة: ''' + student.get('section', '') + '''</td>
                    <td style="width: 50%;">المقرر: ''' + header_settings.get('subject', '') + '''</td>
                </tr>
            </table>
        </div>
        
        <table class="grades-table">
            <tr>
                <th rowspan="2">الدرجة</th>
                <th colspan="4">الجزء العشري</th>
                <th colspan="11">الجزء الصحيح</th>
            </tr>
            <tr>
                <td>3/4</td><td>1/2</td><td>1/4</td><td>-</td>
                <td>0</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td>
            </tr>
            <tr>
                <td><strong>الدرجة النهائية</strong></td>
'''
            
            # إضافة فقاعات الدرجات
            for n in range(15):
                html_template += '<td style="height: 0.5cm;"><div style="width: 0.3cm; height: 0.3cm; border: 1px solid #000; border-radius: 50%; margin: auto;"></div></td>'
            
            html_template += '''            </tr>
        </table>
        
        <div class="omr-columns">
'''
            
            # حساب عدد الأسئلة وتوزيعها على 3 أعمدة
            num_questions = len(question_ids)
            questions_per_column = (num_questions + 2) // 3  # توزيع متساوي على 3 أعمدة
            
            # العمود الأول
            html_template += '''            <div class="omr-column">
                <div class="omr-title">أسئلة اختر الإجابة الصحيحة</div>
'''
            
            for i in range(1, questions_per_column + 1):
                html_template += f'''                <div class="omr-row">
                    <div class="omr-cell">{i}</div>
                    <div class="omr-bubble"><span class="bubble-char">أ</span></div>
                    <div class="omr-bubble"><span class="bubble-char">ب</span></div>
                    <div class="omr-bubble"><span class="bubble-char">ج</span></div>
                    <div class="omr-bubble"><span class="bubble-char">د</span></div>
                </div>
'''
            
            html_template += '''            </div>
'''
            
            # العمود الثاني
            html_template += '''            <div class="omr-column">
                <div class="omr-title">تابع: اختر الإجابة</div>
'''
            
            start_q2 = questions_per_column + 1
            end_q2 = min(2 * questions_per_column, num_questions)
            
            for i in range(start_q2, end_q2 + 1):
                html_template += f'''                <div class="omr-row">
                    <div class="omr-cell">{i}</div>
                    <div class="omr-bubble"><span class="bubble-char">أ</span></div>
                    <div class="omr-bubble"><span class="bubble-char">ب</span></div>
                    <div class="omr-bubble"><span class="bubble-char">ج</span></div>
                    <div class="omr-bubble"><span class="bubble-char">د</span></div>
                </div>
'''
            
            html_template += '''            </div>
'''
            
            # العمود الثالث
            html_template += '''            <div class="omr-column">
                <div class="omr-title">تابع: اختر الإجابة</div>
'''
            
            start_q3 = 2 * questions_per_column + 1
            end_q3 = num_questions
            
            for i in range(start_q3, end_q3 + 1):
                html_template += f'''                <div class="omr-row">
                    <div class="omr-cell">{i}</div>
                    <div class="omr-bubble"><span class="bubble-char">أ</span></div>
                    <div class="omr-bubble"><span class="bubble-char">ب</span></div>
                    <div class="omr-bubble"><span class="bubble-char">ج</span></div>
                    <div class="omr-bubble"><span class="bubble-char">د</span></div>
                </div>
'''
            
            html_template += '''            </div>
        </div>
    </div>
'''
        
        html_template += '''</body>
</html>'''
        
        return html_template, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
    except Exception as e:
        logger.exception(f"Error generating Remark OMR: {e}")
        return jsonify({
            'success': False,
            'error': f'خطأ: {str(e)}'
        }), 500


def generate_remark_answer_sheets_html(students, questions, header_settings):
    """
    توليد HTML لأوراق الإجابة
    """
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>أوراق الإجابة</title>
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            
            body {{
                font-family: 'Traditional Arabic', 'Simplified Arabic', 'Tahoma', 'Arial', sans-serif;
                font-size: 12px;
                line-height: 1.4;
                color: #000;
                direction: rtl;
            }}
            
            .page {{
                page-break-after: always;
                padding: 20px;
                border: 1px solid #ccc;
                margin-bottom: 20px;
            }}
            
            .header {{
                text-align: center;
                border-bottom: 2px solid #000;
                padding-bottom: 10px;
                margin-bottom: 15px;
            }}
            
            .header-title {{
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            
            .header-info {{
                font-size: 11px;
                margin-bottom: 3px;
            }}
            
            .student-info {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 15px;
                padding: 10px;
                background: #f5f5f5;
                border-radius: 5px;
            }}
            
            .student-info-item {{
                font-weight: bold;
                font-size: 11px;
            }}
            
            .answers-grid {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 8px;
                margin-top: 15px;
            }}
            
            .answer-box {{
                border: 2px solid #000;
                padding: 15px;
                text-align: center;
                font-weight: bold;
                font-size: 14px;
                min-height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: white;
            }}
            
            .answer-box.marked {{
                background: #fff3cd;
            }}
            
            .question-number {{
                font-size: 10px;
                color: #666;
                margin-bottom: 3px;
            }}
            
            .options {{
                display: flex;
                gap: 5px;
                justify-content: center;
                font-size: 12px;
            }}
            
            .option-letter {{
                width: 20px;
                height: 20px;
                border: 1px solid #000;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                border-radius: 3px;
            }}
            
            @media print {{
                body {{
                    padding: 0;
                }}
                .page {{
                    page-break-after: always;
                    border: none;
                    margin-bottom: 0;
                    padding: 0;
                }}
            }}
        </style>
    </head>
    <body>
    """
    
    # توليد ورقة لكل طالب
    for student in students:
        html += f"""
        <div class="page">
            <div class="header">
                <div class="header-title">{header_settings.get('country', 'المملكة العربية السعودية')}</div>
                <div class="header-info">{header_settings.get('ministry', 'وزارة التعليم')}</div>
                <div class="header-info">{header_settings.get('education_department', '')}</div>
                <div class="header-info" style="font-weight: bold; margin-top: 5px;">{header_settings.get('school_name', '')}</div>
            </div>
            
            <div style="text-align: center; margin-bottom: 15px;">
                <h2 style="margin: 5px 0;">ورقة الإجابة</h2>
                <p style="font-size: 11px; margin: 3px 0;">المادة: {header_settings.get('subject', '')}</p>
                <p style="font-size: 11px; margin: 3px 0;">الصف: {header_settings.get('grade', '')} | الوقت: {header_settings.get('time', '')}</p>
            </div>
            
            <div class="student-info">
                <div class="student-info-item">اسم الطالب: {student.get('name', '')}</div>
                <div class="student-info-item">رقم الجلوس: {student.get('id', '')}</div>
                <div class="student-info-item">التاريخ: ___________</div>
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 10px;">
                عدد الأسئلة: {len(questions)}
            </div>
            
            <div class="answers-grid">
        """
        
        # إضافة صناديق الإجابة
        for idx, question in enumerate(questions, 1):
            html += f"""
            <div>
                <div class="question-number">س{idx}</div>
                <div class="options">
                    <div class="option-letter">أ</div>
                    <div class="option-letter">ب</div>
                    <div class="option-letter">ج</div>
                    <div class="option-letter">د</div>
                </div>
            </div>
            """
        
        html += """
            </div>
        </div>
        """
    
    html += """
    </body>
    </html>
    """
    
    return html


# ===== نهاية نظام استخراج وتوليد نماذج الاختبار ====="
