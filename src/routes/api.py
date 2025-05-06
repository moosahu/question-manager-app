# src/routes/api.py (Updated with /units/<id>/lessons endpoint)

import logging
from flask import Blueprint, jsonify, current_app, url_for, request # Added request
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

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
except ImportError:
    try:
        from models.question import Question, Option
        from models.curriculum import Lesson, Unit, Course
    except ImportError:
        print("Error: Could not import models.")
        raise

# Create Blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

logger = logging.getLogger(__name__)

# --- Helper Function to Format Image URLs --- #
def format_image_url(image_path):
    """Prepends the base URL if the path is relative."""
    if image_path and not image_path.startswith(('http://', 'https://')):
        try:
            server_name = current_app.config.get('SERVER_NAME')
            host_url = request.host_url if request and hasattr(request, 'host_url') else None
            base_url = f"https://{server_name}" if server_name else host_url
            
            if not base_url:
                 logger.warning("Could not determine base URL for image path generation.")
                 static_url_path = url_for('static', filename='').lstrip('/')
                 return f"/{static_url_path.rstrip('/')}/{image_path.lstrip('/')}"

            if not base_url.endswith('/'):
                base_url += '/'
            static_url_path = url_for('static', filename='').lstrip('/') 
            full_url = f"{base_url.rstrip('/')}/{static_url_path.rstrip('/')}/{image_path.lstrip('/')}"
            return full_url
        except RuntimeError:
            logger.warning("Could not generate external URL for image, possibly outside request context.")
            try:
                 static_url_path = url_for('static', filename='').lstrip('/')
                 return f"/{static_url_path.rstrip('/')}/{image_path.lstrip('/')}"
            except RuntimeError:
                 logger.error("Could not even generate relative static path.")
                 return None 
        except Exception as e:
             logger.error(f"Error generating image URL for {image_path}: {e}")
             return None 
    return image_path 

# --- Helper Function to Format Questions --- #
def format_question(question):
    """Formats a Question object into the desired dictionary structure for JSON response."""
    return {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "image_url": format_image_url(question.image_url),
        "options": [
            {
                "option_id": opt.option_id,
                "option_text": opt.option_text,
                "image_url": format_image_url(opt.image_url),
                "is_correct": opt.is_correct
            }
            for opt in sorted(question.options, key=lambda o: o.option_id)
        ]
    }

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

# +++ NEW API Endpoint for Lessons by Unit +++ #
@api_bp.route("/units/<int:unit_id>/lessons", methods=["GET"])
def get_unit_lessons(unit_id):
    """Returns a list of lessons for a specific unit."""
    logger.info(f"API request received for lessons of unit_id: {unit_id}")
    try:
        # Check if unit exists
        unit = Unit.query.get(unit_id)
        if not unit:
            logger.warning(f"Unit with id {unit_id} not found.")
            return jsonify({"error": "Unit not found"}), 404

        # Query lessons for the unit
        lessons = (
            Lesson.query
            .filter(Lesson.unit_id == unit_id)
            .order_by(Lesson.id) # Optional: order lessons
            .all()
        )
        logger.info(f"Found {len(lessons)} lessons for unit_id: {unit_id}")

        # Format lessons for JSON response
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

# --- API Endpoint for Questions by Unit --- #
@api_bp.route("/units/<int:unit_id>/questions", methods=["GET"])
def get_unit_questions(unit_id):
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

# --- API Endpoint for Questions by Course --- #
@api_bp.route("/courses/<int:course_id>/questions", methods=["GET"])
def get_course_questions(course_id):
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



import random # Added for shuffling if needed
from sqlalchemy import func # Added for random ordering in DB




# --- API Endpoint for Random Questions --- #
@api_bp.route("/questions/random", methods=["GET"])
def get_random_questions():
    """Returns a list of random questions, optionally limited by count."""
    logger.info("API request received for random questions.")
    try:
        count = request.args.get("count", 10, type=int)
        if count <= 0:
            count = 10 # Default to 10 if count is invalid
        logger.info(f"Requesting {count} random questions.")

        # Use database-specific random function (func.random() for SQLite/PostgreSQL)
        # For other DBs, adjust accordingly (e.g., RAND() for MySQL)
        questions = (
            Question.query
            .options(joinedload(Question.options))
            .order_by(func.random()) # Order randomly
            .limit(count) # Limit the number of results
            .all()
        )
        
        # Alternative if func.random() isn't suitable or for large datasets:
        # Fetch all IDs, shuffle in Python, then query by selected IDs.
        # This can be less efficient for the DB but avoids DB-specific functions.
        # all_ids = [q.question_id for q in Question.query.with_entities(Question.question_id).all()]
        # if len(all_ids) < count:
        #     selected_ids = all_ids
        # else:
        #     selected_ids = random.sample(all_ids, count)
        # questions = Question.query.options(joinedload(Question.options)).filter(Question.question_id.in_(selected_ids)).all()
        # random.shuffle(questions) # Shuffle the final list if order matters

        logger.info(f"Found {len(questions)} random questions.")
        formatted_questions = [format_question(q) for q in questions]
        return jsonify(formatted_questions)

    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching random questions: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching random questions: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

