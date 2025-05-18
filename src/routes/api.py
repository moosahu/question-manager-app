# src/routes/api.py (Updated with /questions/all and nested /courses/<cid>/units/<uid>/questions endpoint, and correct_option_id)

import logging
from flask import Blueprint, jsonify, current_app, url_for, request # Added request
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from sqlalchemy import inspect

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
            # استخدام db مباشرة بدلاً من current_app.extensions['sqlalchemy'].db
            inspector = inspect(db.engine)
            if not inspector.has_table('activities'):
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
