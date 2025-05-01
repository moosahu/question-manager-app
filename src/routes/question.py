#!/usr/bin/python3
# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging # Import logging
from sqlalchemy.exc import IntegrityError, DBAPIError # Import specific DB errors

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
            file.save(file_path)
            # Return the relative path to be stored in DB (relative to static folder)
            # Use forward slashes for URL paths
            relative_path = f"uploads/{subfolder}/{filename}"
            return sanitize_path(relative_path) # Sanitize path before returning
        except Exception as e:
            current_app.logger.error(f"Error saving file {filename} to {file_path}: {e}")
            return None # Return None if saving fails
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
    # RESTORED ORIGINAL FULL FUNCTION
    lessons = (Lesson.query.options(db.joinedload(Lesson.unit).joinedload(Unit.course))
                      .order_by(Course.name, Unit.name, Lesson.name).all())
    if not lessons:
        flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for FULL add_question.")
        question_text = request.form.get("text")
        lesson_id = request.form.get("lesson_id")
        explanation = request.form.get("explanation")
        correct_option_index_str = request.form.get("correct_option")

        # Full validation
        if not question_text or not lesson_id or correct_option_index_str is None:
            flash("يرجى ملء جميع الحقول المطلوبة (نص السؤال، الدرس، تحديد الإجابة الصحيحة).", "danger")
            # Use the original form template
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        try:
            correct_option_index = int(correct_option_index_str)
        except ValueError:
            flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        # File uploads
        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")
        current_app.logger.info("Attempting to save question image...")
        q_image_path = save_upload(q_image_file, subfolder="questions")
        current_app.logger.info(f"Question image path: {q_image_path}")
        current_app.logger.info("Attempting to save explanation image...")
        e_image_path = save_upload(e_image_file, subfolder="explanations")
        current_app.logger.info(f"Explanation image path: {e_image_path}")

        # --- Database Operations (with Enhanced Logging) ---
        try:
            current_app.logger.info("Creating Question object...")
            new_question = Question(
                text=question_text,
                lesson_id=lesson_id,
                image_path=q_image_path,
                explanation=explanation,
                explanation_image_path=e_image_path
            )
            current_app.logger.info("Adding Question object to session...")
            db.session.add(new_question)
            current_app.logger.info("Question object added to session.")

            # Need to flush to get the new_question.id for options
            current_app.logger.info("Flushing session to get new question ID...")
            db.session.flush()
            current_app.logger.info(f"New question ID obtained: {new_question.id}")

            # Options processing
            options_data = []
            options_added = 0
            for i in range(4): # Assuming max 4 options
                option_text = request.form.get(f"option_text_{i}")
                if option_text:
                    current_app.logger.info(f"Processing option {i}...")
                    option_image_file = request.files.get(f"option_image_{i}")
                    current_app.logger.info(f"Attempting to save option {i} image...")
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    current_app.logger.info(f"Option {i} image path: {option_image_path}")
                    is_correct = (i == correct_option_index)
                    options_data.append({
                        "text": option_text,
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": new_question.id
                    })
                    options_added += 1

            if options_added < 2:
                 current_app.logger.warning("Less than 2 options provided. Rolling back.")
                 # No need to rollback here as commit hasn't happened, just flash and re-render
                 flash("يجب إضافة خيارين على الأقل.", "danger")
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
            else:
                current_app.logger.info(f"Adding {len(options_data)} options to the session...")
                for opt_data in options_data:
                    option = Option(**opt_data)
                    db.session.add(option)
                current_app.logger.info("Options added to session.")

                # --- CRITICAL COMMIT STEP --- #
                current_app.logger.info("Attempting to commit transaction...")
                try:
                    db.session.commit()
                    current_app.logger.info("Transaction committed successfully.")
                    flash("تمت إضافة السؤال بنجاح!", "success")
                    return redirect(url_for("question.list_questions"))
                except Exception as commit_error:
                    # Log the specific commit error, including original exception if available
                    orig_error = getattr(commit_error, 'orig', None)
                    current_app.logger.exception(f"CRITICAL ERROR during commit: {commit_error}. Original error: {orig_error}")
                    db.session.rollback()
                    current_app.logger.info("Session rolled back due to commit error.")
                    flash(f"حدث خطأ فادح أثناء حفظ السؤال في قاعدة البيانات: {commit_error}", "danger")
                    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
                # --- END CRITICAL COMMIT STEP --- #

        except IntegrityError as ie:
            db.session.rollback()
            current_app.logger.exception(f"Database Integrity Error adding question (before commit attempt): {ie}")
            flash(f"خطأ في تكامل قاعدة البيانات أثناء إضافة السؤال (قد يكون بسبب بيانات مكررة أو غير صالحة): {ie}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except DBAPIError as dbe:
            db.session.rollback()
            current_app.logger.exception(f"Database API Error adding question (before commit attempt): {dbe}")
            flash(f"خطأ في واجهة برمجة تطبيقات قاعدة البيانات أثناء إضافة السؤال: {dbe}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question (before commit attempt): {e}") # Log full traceback
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال: {e}", "danger")
            # Re-render form with submitted data
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    # GET request
    # Use the original form template
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # Keep the original edit function
    question = Question.query.options(
        db.joinedload(Question.options),
        db.joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    ).get_or_404(question_id)
    lessons = (Lesson.query.options(db.joinedload(Lesson.unit).joinedload(Unit.course))
                      .order_by(Course.name, Unit.name, Lesson.name).all())

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")
        question_text = request.form.get("text")
        lesson_id = request.form.get("lesson_id")
        explanation = request.form.get("explanation")
        correct_option_index_str = request.form.get("correct_option")

        if not question_text or not lesson_id or correct_option_index_str is None:
            flash("يرجى ملء جميع الحقول المطلوبة.", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        try:
            correct_option_index = int(correct_option_index_str)
        except ValueError:
            flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")

        q_image_path = question.image_path # Keep existing if no new file
        if q_image_file:
            current_app.logger.info("Attempting to save new question image...")
            new_q_path = save_upload(q_image_file, subfolder="questions")
            if new_q_path:
                # TODO: Delete old image if needed
                q_image_path = new_q_path
            else:
                flash("فشل تحميل صورة السؤال الجديدة.", "warning")

        e_image_path = question.explanation_image_path # Keep existing if no new file
        if e_image_file:
            current_app.logger.info("Attempting to save new explanation image...")
            new_e_path = save_upload(e_image_file, subfolder="explanations")
            if new_e_path:
                # TODO: Delete old image if needed
                e_image_path = new_e_path
            else:
                flash("فشل تحميل صورة الشرح الجديدة.", "warning")

        try:
            current_app.logger.info(f"Updating Question object ID: {question_id}")
            question.text = question_text
            question.lesson_id = lesson_id
            question.image_path = q_image_path
            question.explanation = explanation
            question.explanation_image_path = e_image_path

            current_app.logger.info("Processing options for update...")
            # Update existing options or add new ones
            existing_options = {opt.id: opt for opt in question.options}
            options_to_keep = set()
            options_updated = 0

            for i in range(4):
                option_id_str = request.form.get(f"option_id_{i}")
                option_text = request.form.get(f"option_text_{i}")
                option_image_file = request.files.get(f"option_image_{i}")
                is_correct = (i == correct_option_index)

                if option_text: # Only process if text is provided
                    options_updated += 1
                    option_id = int(option_id_str) if option_id_str else None
                    option = existing_options.get(option_id) if option_id else None

                    opt_image_path = None
                    if option:
                        opt_image_path = option.image_path # Keep existing if no new file

                    if option_image_file:
                        current_app.logger.info(f"Attempting to save new/updated option {i} image...")
                        new_opt_path = save_upload(option_image_file, subfolder="options")
                        if new_opt_path:
                            # TODO: Delete old image if needed
                            opt_image_path = new_opt_path
                        else:
                            flash(f"فشل تحميل صورة الخيار {i+1} الجديدة.", "warning")

                    if option: # Update existing option
                        current_app.logger.info(f"Updating existing option ID: {option_id}")
                        option.text = option_text
                        option.image_path = opt_image_path
                        option.is_correct = is_correct
                        options_to_keep.add(option_id)
                    else: # Add new option
                        current_app.logger.info(f"Adding new option for question ID: {question_id}")
                        new_option = Option(
                            text=option_text,
                            image_path=opt_image_path,
                            is_correct=is_correct,
                            question_id=question_id
                        )
                        db.session.add(new_option)
                        # We don't get the ID immediately, but it will be linked

            # Delete options that were removed from the form
            options_to_delete = set(existing_options.keys()) - options_to_keep
            if options_to_delete:
                current_app.logger.info(f"Deleting options with IDs: {options_to_delete}")
                for opt_id in options_to_delete:
                    # TODO: Delete associated image files
                    db.session.delete(existing_options[opt_id])

            if options_updated < 2:
                 current_app.logger.warning("Less than 2 options provided during edit. Rolling back.")
                 db.session.rollback() # Rollback changes made so far
                 flash("يجب توفير خيارين على الأقل.", "danger")
                 # Re-fetch question data as rollback occurred
                 question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id)
                 return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # --- CRITICAL COMMIT STEP --- #
            current_app.logger.info(f"Attempting to commit transaction for editing question ID: {question_id}")
            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully.")
                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit while editing question ID {question_id}: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                current_app.logger.info("Session rolled back due to commit error.")
                flash(f"حدث خطأ فادح أثناء حفظ تعديلات السؤال: {commit_error}", "danger")
                # Re-fetch question data as rollback occurred
                question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id)
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
            # --- END CRITICAL COMMIT STEP --- #

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question ID {question_id} (before commit attempt): {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            # Re-fetch question data as rollback occurred
            question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id)
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # Ensure options are loaded for the template
    if not question.options:
        current_app.logger.warning(f"Question {question_id} has no options when rendering edit form.")
        # You might want to add placeholder options if the form expects them

    # Sanitize paths before sending to template
    if question.image_path:
        question.image_path = sanitize_path(question.image_path)
    if question.explanation_image_path:
        question.explanation_image_path = sanitize_path(question.explanation_image_path)
    for option in question.options:
        if option.image_path:
            option.image_path = sanitize_path(option.image_path)

    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        current_app.logger.info(f"Attempting to delete question ID: {question_id}")
        # TODO: Delete associated image files (question, explanation, options)
        db.session.delete(question)
        db.session.commit()
        current_app.logger.info(f"Question ID: {question_id} deleted successfully.")
        flash("تم حذف السؤال بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))

