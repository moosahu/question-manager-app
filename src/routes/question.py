"""
Modifies question.py to handle dynamic options and fixes the ORDER BY clause
in the lesson query by explicitly joining the related tables.
"""

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager # Import contains_eager

# Assuming db is imported correctly (e.g., from src.extensions or src.main)
try:
    from src.extensions import db
except ImportError:
    from src.main import db # Adjust if your structure is different

from src.models.question import Question, Option
from src.models.curriculum import Lesson, Unit, Course

question_bp = Blueprint("question", __name__, template_folder="../templates/question")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)

def sanitize_path(path):
    if path:
        sanitized = path.replace("\\", "/").replace("//", "/")
        if sanitized.startswith("/"):
            sanitized = sanitized[1:]
        return sanitized
    return path

def save_upload(file, subfolder="questions"):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{filename}"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder, "uploads"))
        upload_dir = os.path.join(upload_folder, subfolder)
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        try:
            file.save(file_path)
            relative_path = f"uploads/{subfolder}/{filename}"
            return sanitize_path(relative_path)
        except Exception as e:
            current_app.logger.error(f"Error saving file {filename} to {file_path}: {e}")
            return None
    return None

@question_bp.route("/")
@login_required
def list_questions():
    current_app.logger.info("Entering list_questions route.")
    page = request.args.get("page", 1, type=int)
    per_page = 10
    current_app.logger.info(f"Requesting page {page} with {per_page} items per page.")

    try:
        # Use joinedload for efficiency here as order is on Question.question_id
        questions_pagination = (Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            ).order_by(Question.question_id.desc()) # Assuming PK is question_id now
            .paginate(page=page, per_page=per_page, error_out=False))
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")

        if questions_pagination and questions_pagination.items:
            for question in questions_pagination.items:
                # Use the renamed attribute image_url
                if question.image_url:
                    question.image_url = sanitize_path(question.image_url)
                if question.explanation_image_path:
                    question.explanation_image_path = sanitize_path(question.explanation_image_path)
                if question.options:
                    for option in question.options:
                        if option.image_path:
                            option.image_path = sanitize_path(option.image_path)

        rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
        current_app.logger.info("Template rendering successful.")
        return rendered_template

    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash(f"حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة. التفاصيل: {sanitize_path(str(e))}", "danger")
        # --- FIX: Redirect to 'index' instead of 'dashboard' --- #
        return redirect(url_for("index"))

# Helper function to get sorted lessons
def get_sorted_lessons():
    try:
        # Explicitly join and use contains_eager for ordering on joined tables
        lessons = (
            Lesson.query
            .join(Lesson.unit)
            .join(Unit.course)
            .options(
                contains_eager(Lesson.unit).contains_eager(Unit.course)
            )
            .order_by(Course.name, Unit.name, Lesson.name)
            .all()
        )
        return lessons
    except Exception as e:
        current_app.logger.exception("Error fetching sorted lessons.")
        # Raise the error to be handled by the route
        raise e

@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    try:
        lessons = get_sorted_lessons()
    except Exception as e:
        flash(f"حدث خطأ أثناء تحميل قائمة الدروس: {e}", "danger")
        # --- FIX: Redirect to 'index' on lesson load error --- #
        return redirect(url_for("index"))

    if not lessons:
        flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        # Use the renamed attribute question_text
        question_text = request.form.get("question_text") # Match form field name if changed
        lesson_id = request.form.get("lesson_id")
        explanation = request.form.get("explanation")
        correct_option_index_str = request.form.get("correct_option") # Dynamic index

        # Basic validation
        if not question_text or not lesson_id or correct_option_index_str is None:
            flash("يرجى ملء جميع الحقول المطلوبة (نص السؤال، الدرس، تحديد الإجابة الصحيحة).", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        try:
            correct_option_index = int(correct_option_index_str)
        except ValueError:
            flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        # Duplicate Question Check (using renamed attribute)
        try:
            existing_question = Question.query.filter_by(question_text=question_text, lesson_id=lesson_id).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to add duplicate question (Text: {question_text}, Lesson ID: {lesson_id}).")
                flash("هذا السؤال موجود بالفعل لهذا الدرس. لم يتم الحفظ.", "warning")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate question check.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال: {query_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        # File uploads
        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")
        # Use the renamed attribute image_url
        q_image_path = save_upload(q_image_file, subfolder="questions") # save_upload returns relative path
        e_image_path = save_upload(e_image_file, subfolder="explanations")

        # Database Operations
        try:
            new_question = Question(
                # Use renamed attributes
                question_text=question_text,
                lesson_id=lesson_id,
                image_url=q_image_path, # Assign saved path to image_url
                explanation=explanation,
                explanation_image_path=e_image_path,
                # quiz_id=... # Assign quiz_id if needed/available
            )
            db.session.add(new_question)
            db.session.flush() # Get new_question.question_id
            current_app.logger.info(f"New question ID obtained: {new_question.question_id}")

            # --- Dynamic Options Processing --- #
            options_data = []
            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))
            actual_correct_option_text = None

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")

                if option_text and option_text.strip():
                    option_image_file = request.files.get(f"option_image_{index_str}")
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    is_correct = (i == correct_option_index)

                    options_data.append({
                        "text": option_text.strip(),
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": new_question.question_id # Use the correct PK name
                    })
                    if is_correct:
                        actual_correct_option_text = option_text.strip()

            if len(options_data) < 2:
                 current_app.logger.warning("Less than 2 valid options provided. Rolling back implicitly.")
                 flash("يجب إضافة خيارين على الأقل بنص غير فارغ.", "danger")
                 # Rollback before returning
                 db.session.rollback()
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            if correct_option_index >= len(options_data):
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(options_data)} options.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                # Rollback before returning
                db.session.rollback()
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            current_app.logger.info(f"Adding {len(options_data)} options to the session...")
            for opt_data in options_data:
                option = Option(**opt_data)
                db.session.add(option)
            # --- End Dynamic Options Processing --- #

            # Commit transaction
            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully.")
                flash("تمت إضافة السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ السؤال في قاعدة البيانات: {commit_error}", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error adding question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء إضافة السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال: {e}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # Fetch question with related data eagerly (using renamed PK)
    question = Question.query.options(
        joinedload(Question.options),
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    ).get_or_404(question_id)

    try:
        lessons = get_sorted_lessons()
    except Exception as e:
        flash(f"حدث خطأ أثناء تحميل قائمة الدروس: {e}", "danger")
        return redirect(url_for("question.list_questions")) # Redirect to list on error

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")
        # Use renamed attribute
        question_text = request.form.get("question_text") # Match form field name if changed
        lesson_id = request.form.get("lesson_id")
        explanation = request.form.get("explanation")
        correct_option_index_str = request.form.get("correct_option") # Dynamic index

        if not question_text or not lesson_id or correct_option_index_str is None:
            flash("يرجى ملء جميع الحقول المطلوبة.", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        try:
            correct_option_index = int(correct_option_index_str)
        except ValueError:
            flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        # Duplicate Check (for edit, using renamed attribute and PK)
        try:
            existing_question = Question.query.filter(
                Question.question_text == question_text,
                Question.lesson_id == lesson_id,
                Question.question_id != question_id
            ).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to edit question ID {question_id} to duplicate another question.")
                flash("يوجد سؤال آخر بنفس النص والدرس. لا يمكن حفظ التعديل.", "warning")
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate check in edit_question.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال عند التعديل: {query_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        # File uploads
        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")

        # Use renamed attribute image_url
        q_image_path = question.image_url
        if q_image_file:
            new_q_path = save_upload(q_image_file, subfolder="questions")
            if new_q_path:
                # TODO: Delete old image if needed
                q_image_path = new_q_path
            else:
                flash("فشل تحميل صورة السؤال الجديدة.", "warning")

        e_image_path = question.explanation_image_path
        if e_image_file:
            new_e_path = save_upload(e_image_file, subfolder="explanations")
            if new_e_path:
                # TODO: Delete old image if needed
                e_image_path = new_e_path
            else:
                flash("فشل تحميل صورة الشرح الجديدة.", "warning")

        try:
            # Update question details first (using renamed attributes)
            question.question_text = question_text
            question.lesson_id = lesson_id
            question.image_url = q_image_path
            question.explanation = explanation
            question.explanation_image_path = e_image_path
            # question.quiz_id = ... # Update quiz_id if needed

            # --- Dynamic Options Processing for Edit --- #
            existing_options_map = {opt.id: opt for opt in question.options}
            submitted_option_ids = set()
            options_to_process = [] # Store tuples (option_obj, data_dict)

            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")
                option_id_str = request.form.get(f"option_id_{index_str}") # Get existing option ID
                option_image_file = request.files.get(f"option_image_{index_str}")
                is_correct = (i == correct_option_index)

                if option_text and option_text.strip():
                    option_image_path = None # Default
                    existing_option = None

                    if option_id_str:
                        try:
                            option_id = int(option_id_str)
                            if option_id in existing_options_map:
                                existing_option = existing_options_map[option_id]
                                option_image_path = existing_option.image_path # Keep old image unless new one uploaded
                                submitted_option_ids.add(option_id)
                        except ValueError:
                            pass # Ignore invalid ID

                    if option_image_file:
                        new_opt_img_path = save_upload(option_image_file, subfolder="options")
                        if new_opt_img_path:
                            # TODO: Delete old image if replaced
                            option_image_path = new_opt_img_path
                        else:
                            flash(f"فشل تحميل صورة الخيار \'{option_text}\'.", "warning")

                    option_data = {
                        "text": option_text.strip(),
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": question.question_id # Use correct PK
                    }
                    options_to_process.append((existing_option, option_data))

            if len(options_to_process) < 2:
                flash("يجب أن يحتوي السؤال على خيارين على الأقل بنص غير فارغ.", "danger")
                db.session.rollback() # Rollback potential question changes
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            if correct_option_index >= len(options_to_process):
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                db.session.rollback()
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # Process options: Update existing, add new
            current_app.logger.info(f"Processing {len(options_to_process)} options for edit...")
            for existing_opt, data_dict in options_to_process:
                if existing_opt:
                    # Update existing option
                    existing_opt.text = data_dict["text"]
                    existing_opt.image_path = data_dict["image_path"]
                    existing_opt.is_correct = data_dict["is_correct"]
                    current_app.logger.info(f"Updating option ID: {existing_opt.id}")
                else:
                    # Add new option
                    new_option = Option(**data_dict)
                    db.session.add(new_option)
                    current_app.logger.info(f"Adding new option with text: {data_dict['text']}")

            # Delete options that were removed from the form
            options_to_delete = [opt for opt_id, opt in existing_options_map.items() if opt_id not in submitted_option_ids]
            if options_to_delete:
                current_app.logger.info(f"Deleting {len(options_to_delete)} options...")
                for opt in options_to_delete:
                    db.session.delete(opt)
            # --- End Dynamic Options Processing for Edit --- #

            # Commit transaction
            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully for edit.")
                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit on edit: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ التعديلات: {commit_error}", "danger")
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # Ensure options are loaded for the template
    if not question.options:
         question.options = [] # Ensure it's iterable even if empty
    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        # Cascade delete should handle options
        db.session.delete(question)
        db.session.commit()
        # TODO: Delete associated image files from storage
        flash("تم حذف السؤال بنجاح.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))

