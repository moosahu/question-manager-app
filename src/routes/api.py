# src/routes/api.py (Updated)

import logging
from flask import Blueprint, jsonify, current_app, url_for
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
        # Use url_for to generate the correct URL for static files
        # Assumes 'static' is the endpoint for your static folder
        try:
            # The filename should be relative to the static folder, 
            # e.g., 'uploads/questions/image.png'
            return url_for('static', filename=image_path, _external=True)
        except RuntimeError:
            # This can happen if url_for is called outside of an application context
            # Fallback to simple concatenation (less robust)
            # You might need to configure SERVER_NAME in Flask for _external=True to work reliably
            base_url = current_app.config.get('SERVER_NAME') or request.host_url
            if base_url.endswith('/'):
                base_url = base_url[:-1]
            return f"{base_url}/static/{image_path}"
    return image_path # Return as is if it's already absolute or None

# --- Helper Function to Format Questions --- #
def format_question(question):
    """Formats a Question object into the desired dictionary structure for JSON response."""
    return {
        "question_id": question.question_id,
        "question_text": question.question_text,
        # Format question image URL
        "image_url": format_image_url(question.image_url),
        "options": [
            {
                "option_id": opt.option_id,
                "option_text": opt.option_text,
                # Add and format option image URL
                "image_url": format_image_url(opt.image_url),
                "is_correct": opt.is_correct
            }
            # Sort options by ID for consistency
            for opt in sorted(question.options, key=lambda o: o.option_id) 
        ]
    }

# --- API Endpoint for Questions by Lesson --- #
@api_bp.route("/lessons/<int:lesson_id>/questions", methods=["GET"])
def get_lesson_questions(lesson_id):
    """Returns a list of questions for a specific lesson."""
    logger.info(f"API request received for questions of lesson_id: {lesson_id}")
    try:
        # Check if lesson exists
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            logger.warning(f"Lesson with id {lesson_id} not found.")
            return jsonify({"error": "Lesson not found"}), 404

        # Query questions for the lesson, eagerly loading options
        questions = (
            Question.query
            .options(joinedload(Question.options))
            .filter(Question.lesson_id == lesson_id)
            .order_by(Question.question_id) # Optional: order questions
            .all()
        )
        logger.info(f"Found {len(questions)} questions for lesson_id: {lesson_id}")

        # Format questions for JSON response using the updated helper
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

        # Query questions belonging to lessons within this unit
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

        # Query questions belonging to lessons within units within this course
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


