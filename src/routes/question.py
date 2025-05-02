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
        # Use joinedload for efficiency here as order is on Question.id
        questions_pagination = (Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            ).order_by(Question.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False))
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
        # Redirect to a safe place, maybe dashboard or curriculum list
        return redirect(url_for("dashboard"))

    if not lessons:
        flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text")
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

        # Duplicate Question Check
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

        # File uploads
        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")
        q_image_path = save_upload(q_image_file, subfolder="questions")
        e_image_path = save_upload(e_image_file, subfolder="explanations")

        # Database Operations
        try:
            new_question = Question(
                text=question_text,
                lesson_id=lesson_id,
                image_path=q_image_path,
                explanation=explanation,
                explanation_image_path=e_image_path
            )
            db.session.add(new_question)
            db.session.flush() # Get new_question.id
            current_app.logger.info(f"New question ID obtained: {new_question.id}")

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
                        "question_id": new_question.id
                    })
                    if is_correct:
                        actual_correct_option_text = option_text.strip()

            if len(options_data) < 2:
                 current_app.logger.warning("Less than 2 valid options provided. Rolling back implicitly.")
                 flash("يجب إضافة خيارين على الأقل بنص غير فارغ.", "danger")
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            if correct_option_index >= len(options_data):
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(options_data)} options.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
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
    # Fetch question with related data eagerly
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
        question_text = request.form.get("text")
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

        # Duplicate Check (for edit)
        try:
            existing_question = Question.query.filter(
                Question.text == question_text,
                Question.lesson_id == lesson_id,
                Question.id != question_id
            ).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to edit question ID {question_id} to duplicate another question.")
                flash("يوجد سؤال آخر بنفس النص والدرس. لا يمكن حفظ التعديل.", "warning")
                # Re-render with original data before modification attempt
                # No need to re-fetch, question object is already loaded
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate check in edit_question.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال عند التعديل: {query_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        # File uploads
        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")

        q_image_path = question.image_path
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
            # Update question details first
            question.text = question_text
            question.lesson_id = lesson_id
            question.image_path = q_image_path
            question.explanation = explanation
            question.explanation_image_path = e_image_path

            # --- Dynamic Options Processing for Edit --- #
            existing_options_map = {opt.id: opt for opt in question.options}
            submitted_option_ids = set()
            options_to_process = []

            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")

                if option_text and option_text.strip():
                    option_id_str = request.form.get(f"option_id_{index_str}")
                    option_id = int(option_id_str) if option_id_str else None
                    option_image_file = request.files.get(f"option_image_{index_str}")
                    is_correct = (i == correct_option_index)

                    options_to_process.append({
                        "index": i,
                        "id": option_id,
                        "text": option_text.strip(),
                        "image_file": option_image_file,
                        "is_correct": is_correct
                    })
                    if option_id:
                        submitted_option_ids.add(option_id)

            if len(options_to_process) < 2:
                 db.session.rollback()
                 flash("يجب توفير خيارين على الأقل بنص غير فارغ.", "danger")
                 # Re-fetch might be needed if relationships were modified before rollback
                 question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
                 return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            if correct_option_index >= len(options_to_process):
                db.session.rollback()
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(options_to_process)} options during edit.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # Process Adds/Updates
            for opt_data in options_to_process:
                option = existing_options_map.get(opt_data["id"]) if opt_data["id"] else None
                opt_image_path = option.image_path if option else None

                if opt_data["image_file"]:
                    new_opt_path = save_upload(opt_data["image_file"], subfolder="options")
                    if new_opt_path:
                        # TODO: Delete old image if needed
                        opt_image_path = new_opt_path
                    else:
                        flash(f"فشل تحميل صورة الخيار \'{opt_data['text']}\' الجديدة.", "warning")

                if option: # Update existing option
                    current_app.logger.info(f"Updating existing option ID: {opt_data['id']}")
                    option.text = opt_data["text"]
                    option.image_path = opt_image_path
                    option.is_correct = opt_data["is_correct"]
                else: # Add new option
                    current_app.logger.info(f"Adding new option for question ID: {question_id}")
                    new_option = Option(
                        text=opt_data["text"],
                        image_path=opt_image_path,
                        is_correct=opt_data["is_correct"],
                        question_id=question_id
                    )
                    db.session.add(new_option)

            # Process Deletes
            options_to_delete_ids = set(existing_options_map.keys()) - submitted_option_ids
            if options_to_delete_ids:
                current_app.logger.info(f"Deleting options with IDs: {options_to_delete_ids}")
                for opt_id in options_to_delete_ids:
                    option_to_delete = existing_options_map[opt_id]
                    # TODO: Delete associated image files
                    db.session.delete(option_to_delete)
            # --- End Dynamic Options Processing for Edit --- #

            # Commit transaction
            try:
                db.session.commit()
                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit while editing question ID {question_id}: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ تعديلات السؤال: {commit_error}", "danger")
                question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question ID {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # Sanitize paths before rendering
    if question.image_path:
        question.image_path = sanitize_path(question.image_path)
    if question.explanation_image_path:
        question.explanation_image_path = sanitize_path(question.explanation_image_path)
    if question.options:
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
        # TODO: Delete associated image files
        # Explicitly delete options first if cascade delete is not configured or reliable
        Option.query.filter_by(question_id=question_id).delete()
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))





@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    current_app.logger.info(f"POST request received for delete_question ID: {question_id}")
    question = Question.query.get_or_404(question_id)

    try:
        # Delete associated options first
        options = Option.query.filter_by(question_id=question.id).all()
        for option in options:
            # TODO: Optionally delete associated image files from storage if they exist
            # if option.image_path:
            #     try:
            #         image_full_path = os.path.join(current_app.static_folder, option.image_path)
            #         if os.path.exists(image_full_path):
            #             os.remove(image_full_path)
            #             current_app.logger.info(f"Deleted option image: {option.image_path}")
            #     except Exception as img_del_err:
            #         current_app.logger.error(f"Error deleting option image {option.image_path}: {img_del_err}")
            db.session.delete(option)
        current_app.logger.info(f"Deleted {len(options)} options associated with question {question_id}.")

        # TODO: Optionally delete question image and explanation image files from storage
        # if question.image_path:
        #     try:
        #         q_image_full_path = os.path.join(current_app.static_folder, question.image_path)
        #         if os.path.exists(q_image_full_path):
        #             os.remove(q_image_full_path)
        #             current_app.logger.info(f"Deleted question image: {question.image_path}")
        #     except Exception as img_del_err:
        #         current_app.logger.error(f"Error deleting question image {question.image_path}: {img_del_err}")
        # if question.explanation_image_path:
        #     try:
        #         e_image_full_path = os.path.join(current_app.static_folder, question.explanation_image_path)
        #         if os.path.exists(e_image_full_path):
        #             os.remove(e_image_full_path)
        #             current_app.logger.info(f"Deleted explanation image: {question.explanation_image_path}")
        #     except Exception as img_del_err:
        #         current_app.logger.error(f"Error deleting explanation image {question.explanation_image_path}: {img_del_err}")

        # Delete the question itself
        db.session.delete(question)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted question ID: {question_id}")
        flash("تم حذف السؤال بنجاح.", "success")

    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database Error deleting question ID {question_id}: {db_error}")
        flash(f"خطأ في قاعدة البيانات أثناء حذف السؤال: {db_error}", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ غير متوقع أثناء حذف السؤال: {e}", "danger")

    return redirect(url_for("question.list_questions"))

