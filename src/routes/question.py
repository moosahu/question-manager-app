#!/usr/bin/python3
# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging # Import logging
from sqlalchemy.exc import IntegrityError, DBAPIError # Import specific DB errors
from sqlalchemy.orm import contains_eager # Import contains_eager

from src.models.user import db # Import db instance
from src.models.question import Question, Option
# Import Lesson, Unit, and Course from curriculum model
from src.models.curriculum import Lesson, Unit, Course

question_bp = Blueprint("question", __name__, template_folder="../templates/question")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    # Use parentheses for implicit line continuation instead of backslash
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)

# Helper function to sanitize path
def sanitize_path(path):
    if path:
        # Replace backslashes, then double slashes, then remove leading slash
        sanitized = path.replace("\\", "/").replace("//", "/")
        if sanitized.startswith("/"):
            sanitized = sanitized[1:]
        return sanitized
    return path # Return None if input is None

# Helper function to save uploaded file
def save_upload(file, subfolder="questions"):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Prepend timestamp or UUID to filename to avoid collisions
        import time
        import uuid
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{filename}"
        # Ensure UPLOAD_FOLDER is configured in main.py
        upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder, "uploads"))
        upload_dir = os.path.join(upload_folder, subfolder)
        os.makedirs(upload_dir, exist_ok=True) # Ensure subfolder exists
        file_path = os.path.join(upload_dir, filename)
        try:
            current_app.logger.info(f"Attempting to save file to: {file_path}") # LOG: Before save
            file.save(file_path)
            current_app.logger.info(f"File saved successfully to: {file_path}") # LOG: After save
            # Return the relative path to be stored in DB (relative to static folder)
            # Use forward slashes for URL paths
            relative_path = f"uploads/{subfolder}/{filename}"
            sanitized_relative_path = sanitize_path(relative_path) # Sanitize path before returning
            current_app.logger.info(f"Returning sanitized relative path: {sanitized_relative_path}") # LOG: Return path
            return sanitized_relative_path
        except Exception as e:
            current_app.logger.exception(f"CRITICAL ERROR saving file {filename} to {file_path}: {e}") # LOG: Exception on save
            return None # Return None if saving fails
    elif file:
        current_app.logger.warning(f"File upload failed: Invalid file type or name for {file.filename}") # LOG: Invalid file
    else:
        current_app.logger.info("No file provided for upload.") # LOG: No file
    return None

# --- Routes for Question Management ---

@question_bp.route("/")
@login_required
def list_questions():
    current_app.logger.info("Entering list_questions route (Comprehensive Error Handling).") # LOG: Start
    page = request.args.get("page", 1, type=int)
    per_page = 10 # Number of questions per page
    current_app.logger.info(f"Requesting page {page} with {per_page} items per page.") # LOG: Page info

    questions_pagination = None
    rendered_template = None

    try:
        # --- Step 1: Database Query ---
        try:
            current_app.logger.info("Attempting to query questions from database...") # LOG: Before query
            # Using joinedload for efficiency here as ORDER BY is on Question itself
            questions_pagination = (Question.query.options(
                    db.joinedload(Question.options),
                    db.joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
                ).order_by(Question.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))
            current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).") # LOG: After query
        except Exception as db_error:
            current_app.logger.exception("Error occurred during database query in list_questions.")
            raise Exception(f"Database Query Error: {db_error}") # Re-raise to be caught by outer block

        # --- Step 2: Data Processing (Path Sanitization) ---
        try:
            current_app.logger.info("Starting path sanitization for questions...") # LOG: Before sanitization loop
            if questions_pagination and questions_pagination.items:
                for i, question in enumerate(questions_pagination.items):
                    current_app.logger.debug(f"Processing question ID: {question.id} (item {i+1} on page)") # LOG: Inside loop
                    if question.image_path:
                        question.image_path = sanitize_path(question.image_path)
                    if question.explanation_image_path:
                        question.explanation_image_path = sanitize_path(question.explanation_image_path)
                    if question.options:
                        for j, option in enumerate(question.options):
                            current_app.logger.debug(f"  Processing option {j+1} of question ID: {question.id}") # LOG: Inside option loop
                            if option.image_path:
                                option.image_path = sanitize_path(option.image_path)
                    else:
                        current_app.logger.debug(f"  Question ID: {question.id} has no options.")
            current_app.logger.info("Path sanitization completed.") # LOG: After sanitization loop
        except Exception as processing_error:
            current_app.logger.exception("Error occurred during data processing (sanitization) in list_questions.")
            raise Exception(f"Data Processing Error: {processing_error}") # Re-raise

        # --- Step 3: Template Rendering ---
        try:
            current_app.logger.info("Attempting to render question/list.html template...") # LOG: Before render
            if questions_pagination:
                # Use the original, non-simplified template
                rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
            else:
                # Handle case where pagination object might be None (though unlikely with error_out=False)
                current_app.logger.warning("questions_pagination is None before rendering. Rendering empty list.")
                rendered_template = render_template("question/list.html", questions=[], pagination=None)
            current_app.logger.info("Template rendering successful.") # LOG: After render
            return rendered_template
        except Exception as render_error:
            current_app.logger.exception("Error occurred during template rendering in list_questions.")
            raise Exception(f"Template Rendering Error: {render_error}") # Re-raise

    except Exception as e:
        # --- Outer Catch Block --- #
        # Log the detailed error (already logged by inner blocks if specific)
        detailed_error = f"Overall Error in list_questions: {e}"
        # Log exception only if not already logged by inner blocks (check error message prefix)
        if not str(e).startswith(("Database Query Error:", "Data Processing Error:", "Template Rendering Error:")):
             current_app.logger.exception(detailed_error)

        # Flash a more specific message if possible, otherwise generic
        error_prefix = "حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة."
        if str(e).startswith("Database Query Error:"):
            error_prefix = "حدث خطأ أثناء استعلام قاعدة البيانات."
        elif str(e).startswith("Data Processing Error:"):
            error_prefix = "حدث خطأ أثناء معالجة بيانات الأسئلة."
        elif str(e).startswith("Template Rendering Error:"):
            error_prefix = "حدث خطأ أثناء عرض القالب."

        safe_error_message = sanitize_path(str(e)) # Sanitize error message
        flash(f"{error_prefix} التفاصيل: {safe_error_message}", "danger")

        # Redirect to dashboard or a safe page in case of error
        current_app.logger.warning("Redirecting to dashboard due to error in list_questions.") # LOG: Redirect on error
        return redirect(url_for("dashboard")) # Ensure dashboard route exists


@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    # RESTORED ORIGINAL FULL FUNCTION with ENHANCED LOGGING + FIXED LESSON QUERY
    current_app.logger.info("--- Entering add_question route ---") # LOG: Start add_question
    lessons = []
    try:
        current_app.logger.info("Querying lessons for the form (with explicit join and order)...") # LOG: Before lesson query
        # FIX: Use explicit join and contains_eager for reliable ordering
        lessons = (Lesson.query
                   .join(Lesson.unit) # Explicitly join Unit
                   .join(Unit.course) # Explicitly join Course
                   .options(contains_eager(Lesson.unit).contains_eager(Unit.course)) # Tell SQLAlchemy to use these joins for loading
                   .order_by(Course.name, Unit.name, Lesson.name) # Order by joined entities
                   .all())
        current_app.logger.info(f"Found {len(lessons)} lessons.") # LOG: After lesson query
        if not lessons:
            current_app.logger.warning("No lessons found. Redirecting to curriculum management.") # LOG: No lessons warning
            flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
            return redirect(url_for("curriculum.list_courses"))
    except Exception as lesson_query_error:
        # Log the specific SQL error if available
        orig_error = getattr(lesson_query_error, 'orig', None)
        sql_error_detail = getattr(orig_error, 'pgerror', str(orig_error)) if orig_error else "No specific SQL error detail."
        current_app.logger.exception(f"Error querying lessons in add_question: {lesson_query_error}. SQL Detail: {sql_error_detail}") # LOG: Lesson query error
        flash(f"حدث خطأ أثناء تحميل الدروس: {lesson_query_error}", "danger")
        return redirect(url_for("dashboard")) # Redirect to dashboard on error

    if request.method == "POST":
        current_app.logger.info("--- POST request received for add_question ---") # LOG: POST start
        try:
            # --- Form Data Retrieval --- #
            current_app.logger.info("Retrieving form data...") # LOG: Form data start
            question_text = request.form.get("text")
            lesson_id = request.form.get("lesson_id")
            explanation = request.form.get("explanation")
            correct_option_index_str = request.form.get("correct_option")
            current_app.logger.info(f"Form data retrieved: lesson_id={lesson_id}, correct_option={correct_option_index_str}") # LOG: Form data retrieved
            current_app.logger.debug(f"Question Text: {question_text[:100]}..." if question_text else "None") # LOG: Debug question text
            current_app.logger.debug(f"Explanation: {explanation[:100]}..." if explanation else "None") # LOG: Debug explanation

            # --- Basic Validation --- #
            current_app.logger.info("Performing basic validation...") # LOG: Validation start
            if not question_text or not lesson_id or correct_option_index_str is None:
                current_app.logger.warning("Basic validation failed: Missing required fields.") # LOG: Validation failed
                flash("يرجى ملء جميع الحقول المطلوبة (نص السؤال، الدرس، تحديد الإجابة الصحيحة).", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            try:
                correct_option_index = int(correct_option_index_str)
                current_app.logger.info(f"Correct option index parsed: {correct_option_index}") # LOG: Correct option parsed
            except ValueError:
                current_app.logger.warning("Validation failed: Invalid correct_option index.") # LOG: Invalid index
                flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            # --- File Uploads --- #
            current_app.logger.info("Processing file uploads...") # LOG: File upload start
            q_image_file = request.files.get("question_image")
            e_image_file = request.files.get("explanation_image")
            current_app.logger.info(f"Question image file received: {q_image_file.filename if q_image_file else 'None'}") # LOG: Q image file
            current_app.logger.info(f"Explanation image file received: {e_image_file.filename if e_image_file else 'None'}") # LOG: E image file

            q_image_path = save_upload(q_image_file, subfolder="questions")
            current_app.logger.info(f"Result of saving question image: {q_image_path}") # LOG: Q image save result
            e_image_path = save_upload(e_image_file, subfolder="explanations")
            current_app.logger.info(f"Result of saving explanation image: {e_image_path}") # LOG: E image save result

            # --- Database Operations Start --- #
            current_app.logger.info("--- Starting database operations --- ") # LOG: DB Ops Start
            try:
                current_app.logger.info("Creating Question object...") # LOG: Create Q obj
                new_question = Question(
                    text=question_text,
                    lesson_id=lesson_id,
                    image_path=q_image_path,
                    explanation=explanation,
                    explanation_image_path=e_image_path
                )
                current_app.logger.info(f"Question object created: ID={new_question.id}, LessonID={new_question.lesson_id}") # LOG: Q obj created

                current_app.logger.info("Adding Question object to session...") # LOG: Add Q to session
                db.session.add(new_question)
                current_app.logger.info("Question object added to session.") # LOG: Q added to session

                # Need to flush to get the new_question.id for options
                current_app.logger.info("Attempting to flush session to get new question ID...") # LOG: Before flush
                db.session.flush()
                current_app.logger.info(f"Session flushed. New question ID obtained: {new_question.id}") # LOG: After flush

                # --- Options Processing --- #
                current_app.logger.info("--- Starting options processing --- ") # LOG: Options start
                options_data = []
                options_added = 0
                for i in range(4): # Assuming max 4 options
                    option_text = request.form.get(f"option_text_{i}")
                    current_app.logger.debug(f"Checking option {i}: Text=\"{option_text}\"") # LOG: Check option i
                    if option_text:
                        current_app.logger.info(f"Processing option {i} (Text found)...") # LOG: Process option i
                        option_image_file = request.files.get(f"option_image_{i}")
                        current_app.logger.info(f"Option {i} image file received: {option_image_file.filename if option_image_file else 'None'}") # LOG: Option i image file

                        option_image_path = save_upload(option_image_file, subfolder="options")
                        current_app.logger.info(f"Result of saving option {i} image: {option_image_path}") # LOG: Option i save result

                        is_correct = (i == correct_option_index)
                        current_app.logger.info(f"Option {i} is_correct: {is_correct}") # LOG: Option i is_correct

                        opt_data_entry = {
                            "text": option_text,
                            "image_path": option_image_path,
                            "is_correct": is_correct,
                            "question_id": new_question.id
                        }
                        options_data.append(opt_data_entry)
                        current_app.logger.debug(f"Option {i} data prepared: {opt_data_entry}") # LOG: Option i data prepared
                        options_added += 1
                    else:
                        current_app.logger.debug(f"Skipping option {i}: No text provided.") # LOG: Skip option i

                current_app.logger.info(f"Finished processing options loop. Total options added: {options_added}") # LOG: Options loop end

                if options_added < 2:
                     current_app.logger.warning("Validation failed: Less than 2 options provided. Rolling back implicitly (no commit). Redirecting.") # LOG: Options validation fail
                     flash("يجب إضافة خيارين على الأقل.", "danger")
                     return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
                else:
                    current_app.logger.info(f"Adding {len(options_data)} Option objects to the session...") # LOG: Add options to session
                    for opt_data in options_data:
                        option = Option(**opt_data)
                        current_app.logger.debug(f"Adding option object to session: Text=\"{option.text}\", Correct={option.is_correct}, QID={option.question_id}") # LOG: Adding option obj
                        db.session.add(option)
                    current_app.logger.info("All Option objects added to session.") # LOG: Options added

                    # --- CRITICAL COMMIT STEP --- #
                    current_app.logger.info("--- Attempting final commit --- ") # LOG: Before commit
                    try:
                        db.session.commit()
                        current_app.logger.info("--- COMMIT SUCCESSFUL --- ") # LOG: Commit success
                        flash("تمت إضافة السؤال بنجاح!", "success")
                        return redirect(url_for("question.list_questions"))
                    except Exception as commit_error:
                        # Log the specific commit error, including original exception if available
                        orig_error = getattr(commit_error, 'orig', None)
                        sql_error_detail = getattr(orig_error, 'pgerror', str(orig_error)) if orig_error else "No specific SQL error detail."
                        current_app.logger.exception(f"--- CRITICAL ERROR DURING COMMIT --- : {commit_error}. SQL Detail: {sql_error_detail}") # LOG: Commit exception
                        try:
                            current_app.logger.info("Attempting to rollback session due to commit error...") # LOG: Before rollback
                            db.session.rollback()
                            current_app.logger.info("Session rolled back successfully.") # LOG: Rollback success
                        except Exception as rollback_error:
                            current_app.logger.exception(f"--- CRITICAL ERROR DURING ROLLBACK --- : {rollback_error}") # LOG: Rollback exception
                        flash(f"حدث خطأ فادح أثناء حفظ السؤال في قاعدة البيانات: {commit_error}", "danger")
                        return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
                    # --- END CRITICAL COMMIT STEP --- #

            except IntegrityError as ie:
                current_app.logger.exception(f"Database Integrity Error adding question (before commit attempt): {ie}") # LOG: IntegrityError
                db.session.rollback()
                current_app.logger.info("Session rolled back due to IntegrityError.") # LOG: Rollback IntegrityError
                flash(f"خطأ في تكامل قاعدة البيانات أثناء إضافة السؤال (قد يكون بسبب بيانات مكررة أو غير صالحة): {ie}", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
            except DBAPIError as dbe:
                current_app.logger.exception(f"Database API Error adding question (before commit attempt): {dbe}") # LOG: DBAPIError
                db.session.rollback()
                current_app.logger.info("Session rolled back due to DBAPIError.") # LOG: Rollback DBAPIError
                flash(f"خطأ في واجهة برمجة تطبيقات قاعدة البيانات أثناء إضافة السؤال: {dbe}", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
            except Exception as e:
                current_app.logger.exception(f"Generic Error adding question (before commit attempt): {e}") # LOG: Generic Error pre-commit
                db.session.rollback()
                current_app.logger.info("Session rolled back due to Generic Error.") # LOG: Rollback Generic Error
                flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال: {e}", "danger")
                # Re-render form with submitted data
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
            # --- Database Operations End --- #

        except Exception as outer_e:
            # Catch any unexpected errors during the POST request processing
            current_app.logger.exception(f"--- UNHANDLED EXCEPTION IN add_question POST --- : {outer_e}") # LOG: Unhandled POST exception
            flash(f"حدث خطأ عام غير متوقع أثناء معالجة الطلب: {outer_e}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    # --- GET request --- #
    current_app.logger.info("--- GET request received for add_question. Rendering form. ---") # LOG: GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # Keep the original edit function + FIXED LESSON QUERY
    current_app.logger.info(f"--- Entering edit_question route for ID: {question_id} ---") # LOG: Start edit_question
    question = None
    lessons = []
    try:
        current_app.logger.info(f"Querying question with ID: {question_id}...") # LOG: Before question query
        question = Question.query.options(
            db.joinedload(Question.options),
            db.joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
        ).get_or_404(question_id)
        current_app.logger.info("Question query successful.") # LOG: After question query

        current_app.logger.info("Querying lessons for the edit form (with explicit join and order)...") # LOG: Before lesson query (edit)
        # FIX: Use explicit join and contains_eager for reliable ordering
        lessons = (Lesson.query
                   .join(Lesson.unit) # Explicitly join Unit
                   .join(Unit.course) # Explicitly join Course
                   .options(contains_eager(Lesson.unit).contains_eager(Unit.course)) # Tell SQLAlchemy to use these joins for loading
                   .order_by(Course.name, Unit.name, Lesson.name) # Order by joined entities
                   .all())
        current_app.logger.info(f"Found {len(lessons)} lessons for edit form.") # LOG: After lesson query (edit)

    except Exception as query_error:
        current_app.logger.exception(f"Error querying data for edit_question (ID: {question_id}): {query_error}") # LOG: Query error (edit)
        flash(f"حدث خطأ أثناء تحميل بيانات السؤال أو الدروس للتعديل: {query_error}", "danger")
        return redirect(url_for("question.list_questions"))

    if request.method == "POST":
        current_app.logger.info(f"--- POST request received for edit_question ID: {question_id} ---") # LOG: POST start (edit)
        try:
            # --- Form Data Retrieval & Basic Validation --- #
            current_app.logger.info("Retrieving form data for edit...") # LOG: Form data start (edit)
            question.text = request.form.get("text")
            question.lesson_id = request.form.get("lesson_id")
            question.explanation = request.form.get("explanation")
            correct_option_index_str = request.form.get("correct_option")
            current_app.logger.info(f"Edit form data retrieved: lesson_id={question.lesson_id}, correct_option={correct_option_index_str}") # LOG: Form data retrieved (edit)

            if not question.text or not question.lesson_id or correct_option_index_str is None:
                current_app.logger.warning("Edit validation failed: Missing required fields.") # LOG: Validation failed (edit)
                flash("يرجى ملء جميع الحقول المطلوبة (نص السؤال، الدرس، تحديد الإجابة الصحيحة).", "danger")
                return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            try:
                correct_option_index = int(correct_option_index_str)
                current_app.logger.info(f"Correct option index parsed for edit: {correct_option_index}") # LOG: Correct option parsed (edit)
            except ValueError:
                current_app.logger.warning("Edit validation failed: Invalid correct_option index.") # LOG: Invalid index (edit)
                flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
                return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # --- File Uploads (Handle potential overwrites or new uploads) --- #
            current_app.logger.info("Processing file uploads for edit...") # LOG: File upload start (edit)
            q_image_file = request.files.get("question_image")
            if q_image_file:
                current_app.logger.info(f"New question image received: {q_image_file.filename}") # LOG: New Q image (edit)
                q_image_path = save_upload(q_image_file, subfolder="questions")
                if q_image_path: # Only update if save was successful
                    current_app.logger.info(f"Updating question image path to: {q_image_path}") # LOG: Update Q image path
                    question.image_path = q_image_path
                else:
                    current_app.logger.warning("Failed to save new question image.") # LOG: Q image save fail (edit)
                    flash("حدث خطأ أثناء حفظ صورة السؤال الجديدة.", "warning")

            e_image_file = request.files.get("explanation_image")
            if e_image_file:
                current_app.logger.info(f"New explanation image received: {e_image_file.filename}") # LOG: New E image (edit)
                e_image_path = save_upload(e_image_file, subfolder="explanations")
                if e_image_path:
                    current_app.logger.info(f"Updating explanation image path to: {e_image_path}") # LOG: Update E image path
                    question.explanation_image_path = e_image_path
                else:
                    current_app.logger.warning("Failed to save new explanation image.") # LOG: E image save fail (edit)
                    flash("حدث خطأ أثناء حفظ صورة الشرح الجديدة.", "warning")

            # --- Options Processing (Update existing, add new, handle deletion) --- #
            current_app.logger.info("--- Starting options processing for edit --- ") # LOG: Options start (edit)
            options_count = 0
            correct_option_found = False
            processed_option_ids = set() # Keep track of options processed from the form

            for i in range(4):
                option_text = request.form.get(f"option_text_{i}")
                option_id_str = request.form.get(f"option_id_{i}") # Get existing option ID if available
                option_image_file = request.files.get(f"option_image_{i}")
                is_correct = (i == correct_option_index)
                current_app.logger.debug(f"Processing form option {i}: ID={option_id_str}, Text=\"{option_text}\", Correct={is_correct}") # LOG: Process form option i

                option = None
                if option_id_str:
                    try:
                        option_id = int(option_id_str)
                        processed_option_ids.add(option_id)
                        # Find the existing option associated with this question
                        option = next((opt for opt in question.options if opt.id == option_id), None)
                        if not option:
                             current_app.logger.warning(f"Option ID {option_id} from form not found in question.options.") # LOG: Option ID mismatch
                    except ValueError:
                        current_app.logger.warning(f"Invalid Option ID received from form: {option_id_str}") # LOG: Invalid Option ID
                        pass # Ignore invalid ID

                if option_text: # If text is provided, update or create
                    options_count += 1
                    if is_correct:
                        correct_option_found = True

                    if option: # Update existing option
                        current_app.logger.info(f"Updating existing option ID: {option.id}") # LOG: Update existing option
                        option.text = option_text
                        option.is_correct = is_correct
                        if option_image_file:
                            current_app.logger.info(f"New image received for option ID: {option.id}") # LOG: New image for option
                            opt_image_path = save_upload(option_image_file, subfolder="options")
                            if opt_image_path:
                                current_app.logger.info(f"Updating option {option.id} image path to: {opt_image_path}") # LOG: Update option image path
                                option.image_path = opt_image_path
                            else:
                                 current_app.logger.warning(f"Failed to save new image for option ID: {option.id}") # LOG: Option image save fail
                                 flash(f"حدث خطأ أثناء حفظ صورة الخيار {i+1} الجديدة.", "warning")
                    else: # Add as new option if text provided but no valid existing ID found
                        current_app.logger.info("Adding new option (no valid ID found or provided)...") # LOG: Add new option
                        opt_image_path = save_upload(option_image_file, subfolder="options")
                        new_option = Option(
                            text=option_text,
                            image_path=opt_image_path,
                            is_correct=is_correct,
                            question_id=question.id
                        )
                        db.session.add(new_option) # Add new option to session
                        current_app.logger.info(f"New option added to session: Text=\"{new_option.text}\"") # LOG: New option added
                        # question.options.append(new_option) # Append if needed
                elif option: # If text is empty but option exists, mark for deletion
                    current_app.logger.info(f"Marking option ID {option.id} for deletion (empty text).") # LOG: Mark option for deletion
                    db.session.delete(option)

            # --- Delete options that were present initially but not in the submitted form --- #
            # This handles cases where the user deleted an option field entirely in the form
            # Note: This assumes the form always submits fields for existing options, even if empty.
            # If the form *doesn't* submit empty fields, this logic needs adjustment.
            # current_app.logger.info(f"Checking for options to delete. Processed IDs: {processed_option_ids}")
            # initial_option_ids = {opt.id for opt in question.options if opt in db.session} # Get IDs of options currently associated
            # ids_to_delete = initial_option_ids - processed_option_ids
            # if ids_to_delete:
            #     current_app.logger.info(f"Deleting options not present in form submission: {ids_to_delete}")
            #     for opt_id in ids_to_delete:
            #         opt_to_del = Option.query.get(opt_id)
            #         if opt_to_del:
            #             db.session.delete(opt_to_del)
            # Simplified deletion: Handled above when text is empty for an existing option ID.

            current_app.logger.info(f"Finished processing options for edit. Final count: {options_count}, Correct found: {correct_option_found}") # LOG: Options end (edit)

            # --- Final Validation --- #
            if options_count < 2:
                current_app.logger.warning("Edit validation failed: Less than 2 options provided.") # LOG: Options validation fail (edit)
                flash("يجب توفير خيارين على الأقل.", "danger")
                # Don't commit yet, re-render form
                return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")
            if not correct_option_found:
                 current_app.logger.warning("Edit validation failed: No correct option selected among provided options.") # LOG: Correct option validation fail (edit)
                 flash("يجب تحديد أحد الخيارات المتوفرة كإجابة صحيحة.", "danger")
                 return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # --- CRITICAL COMMIT STEP --- #
            current_app.logger.info(f"--- Attempting final commit for edit question ID: {question_id} --- ") # LOG: Before commit (edit)
            try:
                db.session.commit()
                current_app.logger.info(f"--- COMMIT SUCCESSFUL for edit question ID: {question_id} --- ") # LOG: Commit success (edit)
                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as e:
                orig_error = getattr(e, 'orig', None)
                sql_error_detail = getattr(orig_error, 'pgerror', str(orig_error)) if orig_error else "No specific SQL error detail."
                current_app.logger.exception(f"--- CRITICAL ERROR DURING COMMIT (edit) --- ID: {question_id}: {e}. SQL Detail: {sql_error_detail}") # LOG: Commit exception (edit)
                try:
                    current_app.logger.info("Attempting to rollback session due to commit error (edit)...") # LOG: Before rollback (edit)
                    db.session.rollback()
                    current_app.logger.info("Session rolled back successfully (edit).") # LOG: Rollback success (edit)
                except Exception as rollback_error:
                    current_app.logger.exception(f"--- CRITICAL ERROR DURING ROLLBACK (edit) --- : {rollback_error}") # LOG: Rollback exception (edit)
                flash(f"حدث خطأ أثناء حفظ التعديلات: {e}", "danger")
                # Re-render form with potentially modified (but uncommitted) question object
                return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")
            # --- END CRITICAL COMMIT STEP --- #

        except Exception as outer_e:
            # Catch any unexpected errors during the POST request processing
            current_app.logger.exception(f"--- UNHANDLED EXCEPTION IN edit_question POST --- ID: {question_id}: {outer_e}") # LOG: Unhandled POST exception (edit)
            flash(f"حدث خطأ عام غير متوقع أثناء معالجة التعديل: {outer_e}", "danger")
            return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # --- GET request --- #
    current_app.logger.info(f"--- GET request received for edit_question ID: {question_id}. Rendering form. ---") # LOG: GET request (edit)
    # Sanitize paths before rendering
    if question.image_path:
        question.image_path = sanitize_path(question.image_path)
    if question.explanation_image_path:
        question.explanation_image_path = sanitize_path(question.explanation_image_path)
    for option in question.options:
        if option.image_path:
            option.image_path = sanitize_path(option.image_path)

    return render_template("question/form.html", title=f"تعديل السؤال #{question.id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    # Keep the original delete function
    current_app.logger.info(f"--- Entering delete_question route for ID: {question_id} ---") # LOG: Start delete
    question = Question.query.get_or_404(question_id)
    try:
        # Delete associated options first if cascade delete is not set up
        current_app.logger.info(f"Deleting options associated with question ID: {question_id}...") # LOG: Delete options
        Option.query.filter_by(question_id=question.id).delete()
        current_app.logger.info("Associated options deleted.") # LOG: Options deleted
        # Then delete the question
        current_app.logger.info(f"Deleting question ID: {question_id}...") # LOG: Delete question
        db.session.delete(question)
        current_app.logger.info("Attempting commit for deletion...") # LOG: Before commit delete
        db.session.commit()
        current_app.logger.info(f"--- COMMIT SUCCESSFUL for delete question ID: {question_id} --- ") # LOG: Commit success delete
        flash("تم حذف السؤال بنجاح!", "success")
    except Exception as e:
        orig_error = getattr(e, 'orig', None)
        sql_error_detail = getattr(orig_error, 'pgerror', str(orig_error)) if orig_error else "No specific SQL error detail."
        current_app.logger.exception(f"--- ERROR DURING DELETE --- ID: {question_id}: {e}. SQL Detail: {sql_error_detail}") # LOG: Delete exception
        try:
            current_app.logger.info("Attempting to rollback session due to delete error...") # LOG: Before rollback delete
            db.session.rollback()
            current_app.logger.info("Session rolled back successfully (delete).") # LOG: Rollback success delete
        except Exception as rollback_error:
            current_app.logger.exception(f"--- CRITICAL ERROR DURING ROLLBACK (delete) --- : {rollback_error}") # LOG: Rollback exception delete
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))

