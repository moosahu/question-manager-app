"""
Modifies question.py to:
1. Handle dynamic options.
2. Fix the ORDER BY clause in the lesson query.
3. Allow options to be valid if they contain either text OR an image.
"""

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

from src.models.user import db
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
        questions_pagination = (
            Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            ).order_by(Question.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")

        if questions_pagination and questions_pagination.items:
            for question in questions_pagination.items:
                if question.image_path:
                    question.image_path = sanitize_path(question.image_path)
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
        return redirect(url_for("dashboard"))

def get_sorted_lessons():
    try:
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
        raise e

@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    try:
        lessons = get_sorted_lessons()
    except Exception as e:
        flash(f"حدث خطأ أثناء تحميل قائمة الدروس: {e}", "danger")
        return redirect(url_for("dashboard"))

    if not lessons:
        flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text")
        lesson_id = request.form.get("lesson_id")
        explanation = request.form.get("explanation")
        correct_option_index_str = request.form.get("correct_option")

        if not question_text or not lesson_id or correct_option_index_str is None:
            flash("يرجى ملء جميع الحقول المطلوبة (نص السؤال، الدرس، تحديد الإجابة الصحيحة).", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        try:
            correct_option_index = int(correct_option_index_str)
        except ValueError:
            flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        try:
            existing_question = Question.query.filter_by(text=question_text, lesson_id=lesson_id).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to add duplicate question (Text: 	{question_text}	, Lesson ID: {lesson_id}).")
                flash("هذا السؤال موجود بالفعل لهذا الدرس. لم يتم الحفظ.", "warning")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate question check.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال: {query_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")
        q_image_path = save_upload(q_image_file, subfolder="questions")
        e_image_path = save_upload(e_image_file, subfolder="explanations")

        try:
            new_question = Question(
                text=question_text,
                lesson_id=lesson_id,
                image_path=q_image_path,
                explanation=explanation,
                explanation_image_path=e_image_path
            )
            db.session.add(new_question)
            db.session.flush()
            current_app.logger.info(f"New question ID obtained: {new_question.id}")

            options_data = []
            valid_options_count = 0
            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")
                option_image_file = request.files.get(f"option_image_{index_str}")

                # Check if option is valid (has text OR an image file is uploaded)
                has_text = option_text and option_text.strip()
                has_image_file = option_image_file and option_image_file.filename != ""

                if has_text or has_image_file:
                    valid_options_count += 1
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    is_correct = (i == correct_option_index)

                    options_data.append({
                        "text": option_text.strip() if has_text else None, # Store None if only image
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": new_question.id
                    })
                else:
                    # Log skipped empty option for debugging if needed
                    current_app.logger.debug(f"Skipping empty option at index {index_str}")

            # Validate number of *valid* options
            if valid_options_count < 2:
                 current_app.logger.warning(f"Less than 2 valid options provided ({valid_options_count}). Rolling back implicitly.")
                 flash("يجب توفير خيارين صالحين على الأقل (نص أو صورة).", "danger")
                 # Clean up potentially saved question image if rollback occurs
                 # TODO: Implement image cleanup on rollback
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            # Validate correct_option_index against the number of options processed
            if correct_option_index >= len(option_keys):
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(option_keys)} potential options.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            current_app.logger.info(f"Adding {len(options_data)} valid options to the session...")
            for opt_data in options_data:
                option = Option(**opt_data)
                db.session.add(option)

            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully.")
                flash("تمت إضافة السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                # TODO: Implement image cleanup on rollback
                flash(f"حدث خطأ فادح أثناء حفظ السؤال في قاعدة البيانات: {commit_error}", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error adding question: {db_error}")
            # TODO: Implement image cleanup on rollback
            flash(f"خطأ في قاعدة البيانات أثناء إضافة السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question: {e}")
            # TODO: Implement image cleanup on rollback
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال: {e}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    question = Question.query.options(
        joinedload(Question.options),
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    ).get_or_404(question_id)

    try:
        lessons = get_sorted_lessons()
    except Exception as e:
        flash(f"حدث خطأ أثناء تحميل قائمة الدروس: {e}", "danger")
        return redirect(url_for("question.list_questions"))

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

        try:
            existing_question = Question.query.filter(
                Question.text == question_text,
                Question.lesson_id == lesson_id,
                Question.id != question_id
            ).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to edit question ID {question_id} to duplicate another question.")
                flash("يوجد سؤال آخر بنفس النص والدرس. لا يمكن حفظ التعديل.", "warning")
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate check in edit_question.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال عند التعديل: {query_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")

        q_image_path = question.image_path
        old_q_image_path = None
        if q_image_file:
            new_q_path = save_upload(q_image_file, subfolder="questions")
            if new_q_path:
                old_q_image_path = q_image_path # Store old path for potential deletion
                q_image_path = new_q_path
            else:
                flash("فشل تحميل صورة السؤال الجديدة.", "warning")

        e_image_path = question.explanation_image_path
        old_e_image_path = None
        if e_image_file:
            new_e_path = save_upload(e_image_file, subfolder="explanations")
            if new_e_path:
                old_e_image_path = e_image_path # Store old path for potential deletion
                e_image_path = new_e_path
            else:
                flash("فشل تحميل صورة الشرح الجديدة.", "warning")

        try:
            question.text = question_text
            question.lesson_id = lesson_id
            question.image_path = q_image_path
            question.explanation = explanation
            question.explanation_image_path = e_image_path

            existing_options_map = {opt.id: opt for opt in question.options}
            submitted_option_ids = set()
            options_to_process = [] # List to hold data for new/updated options
            options_to_delete = [] # List to hold Option objects to delete
            valid_options_count = 0

            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_id_str = request.form.get(f"option_id_{index_str}")
                option_text = request.form.get(f"option_text_{index_str}")
                option_image_file = request.files.get(f"option_image_{index_str}")
                is_correct = (i == correct_option_index)

                option_id = None
                if option_id_str:
                    try:
                        option_id = int(option_id_str)
                        submitted_option_ids.add(option_id)
                    except ValueError:
                        current_app.logger.warning(f"Invalid option_id received: {option_id_str}")
                        # Handle potentially malicious input? For now, ignore.
                        pass

                existing_option = existing_options_map.get(option_id) if option_id else None
                current_image_path = existing_option.image_path if existing_option else None
                old_option_image_path = None

                # Check if a new image was uploaded for this option
                new_option_image_path = None
                if option_image_file and option_image_file.filename != "":
                    new_option_image_path = save_upload(option_image_file, subfolder="options")
                    if new_option_image_path:
                        old_option_image_path = current_image_path # Store old path
                        current_image_path = new_option_image_path
                    else:
                        flash(f"فشل تحميل صورة الخيار {i+1} الجديدة.", "warning")
                        # Keep existing image path if upload fails

                # Determine if the option is valid (has text OR an image)
                has_text = option_text and option_text.strip()
                has_image = current_image_path is not None # Check if there's an image path (new or existing)

                if has_text or has_image:
                    valid_options_count += 1
                    options_to_process.append({
                        "id": option_id,
                        "text": option_text.strip() if has_text else None,
                        "image_path": current_image_path,
                        "is_correct": is_correct,
                        "question_id": question_id,
                        "old_image_path": old_option_image_path # Pass old path for deletion later
                    })
                elif existing_option:
                    # If an existing option becomes invalid (no text and no image), mark for deletion
                    options_to_delete.append(existing_option)

            # Identify options that were present before but not submitted (removed dynamically)
            for opt_id, opt in existing_options_map.items():
                if opt_id not in submitted_option_ids:
                    options_to_delete.append(opt)

            # Validate number of *valid* options
            if valid_options_count < 2:
                current_app.logger.warning(f"Edit resulted in less than 2 valid options ({valid_options_count}). Rolling back implicitly.")
                flash("يجب أن يحتوي السؤال على خيارين صالحين على الأقل (نص أو صورة).", "danger")
                # No need to rollback session yet, just prevent commit and re-render
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # Validate correct_option_index against the number of potential options submitted
            if correct_option_index >= len(option_keys):
                 current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(option_keys)} potential options during edit.")
                 flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                 return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # Process deletions
            images_to_delete_on_commit = []
            for opt in options_to_delete:
                if opt.image_path:
                    images_to_delete_on_commit.append(opt.image_path)
                db.session.delete(opt)
                current_app.logger.info(f"Marked option ID {opt.id} for deletion.")

            # Process updates and additions
            for data in options_to_process:
                opt_id = data["id"]
                old_image_path = data["old_image_path"]
                if old_image_path:
                    images_to_delete_on_commit.append(old_image_path)

                if opt_id and opt_id in existing_options_map:
                    # Update existing option
                    option = existing_options_map[opt_id]
                    option.text = data["text"]
                    option.image_path = data["image_path"]
                    option.is_correct = data["is_correct"]
                    current_app.logger.info(f"Marked option ID {opt_id} for update.")
                else:
                    # Add new option
                    new_option = Option(
                        text=data["text"],
                        image_path=data["image_path"],
                        is_correct=data["is_correct"],
                        question_id=data["question_id"]
                    )
                    db.session.add(new_option)
                    current_app.logger.info("Marked new option for addition.")

            # Commit transaction
            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully.")

                # Delete old image files AFTER commit is successful
                upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder, "uploads"))
                if old_q_image_path:
                    try:
                        os.remove(os.path.join(upload_folder, old_q_image_path.replace("uploads/", "", 1)))
                        current_app.logger.info(f"Deleted old question image: {old_q_image_path}")
                    except OSError as e:
                        current_app.logger.error(f"Error deleting old question image {old_q_image_path}: {e}")
                if old_e_image_path:
                    try:
                        os.remove(os.path.join(upload_folder, old_e_image_path.replace("uploads/", "", 1)))
                        current_app.logger.info(f"Deleted old explanation image: {old_e_image_path}")
                    except OSError as e:
                        current_app.logger.error(f"Error deleting old explanation image {old_e_image_path}: {e}")
                for img_path in images_to_delete_on_commit:
                     try:
                        os.remove(os.path.join(upload_folder, img_path.replace("uploads/", "", 1)))
                        current_app.logger.info(f"Deleted old option image: {img_path}")
                     except OSError as e:
                        current_app.logger.error(f"Error deleting old option image {img_path}: {e}")

                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))

            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit (edit): {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                # Don't delete images if commit failed
                flash(f"حدث خطأ فادح أثناء حفظ التعديلات في قاعدة البيانات: {commit_error}", "danger")
                # Re-fetch question data to reflect rollback state before re-rendering
                question = Question.query.options(joinedload(Question.options)).get(question_id)
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال: {db_error}", "danger")
            question = Question.query.options(joinedload(Question.options)).get(question_id)
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            question = Question.query.options(joinedload(Question.options)).get(question_id)
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # Sanitize paths for display in GET request
    if question.image_path:
        question.image_path = sanitize_path(question.image_path)
    if question.explanation_image_path:
        question.explanation_image_path = sanitize_path(question.explanation_image_path)
    if question.options:
        for option in question.options:
            if option.image_path:
                option.image_path = sanitize_path(option.image_path)

    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

# TODO: Add delete route

