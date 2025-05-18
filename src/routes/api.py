# src/routes/api.py (Updated with /questions/all and nested /courses/<cid>/units/<uid>/questions endpoint, and correct_option_id)

import logging
from flask import Blueprint, jsonify, current_app, url_for, request # Added request
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta

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
            
    return {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "image_url": format_image_url(question.image_url),
        "options": options_list,
        "correct_option_id": correct_option_id_found  # Added this line
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
        courses = Course.query.order_by(Course.id).all()
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
            .order_by(Unit.id)
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
            .order_by(Lesson.id)
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
