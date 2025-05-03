# src/routes/question.py

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

try:
    from src.extensions import db
except ImportError:
    from src.main import db

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
        questions_pagination = (Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            ).order_by(Question.question_id.desc())
            .paginate(page=page, per_page=per_page, error_out=False))
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")

        if questions_pagination and questions_pagination.items:
            for question in questions_pagination.items:
                if question.image_url:
                    question.image_url = sanitize_path(question.image_url)
                # --- Temporarily Commented Out Usage --- #
                # if question.explanation_image_path:
                #     question.explanation_image_path = sanitize_path(question.explanation_image_path)
                # ------------------------------------- #
                # --- FIX: Removed loop for option image path --- #
                # if question.options:
                #     for option in question.options:
                #         if option.image_path:
                #             option.image_path = sanitize_path(option.image_path)
                # --------------------------------------------- #

        rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
        current_app.logger.info("Template rendering successful.")
        return rendered_template

    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash(f"حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة. التفاصيل: {sanitize_path(str(e))}", "danger")
        return redirect(url_for("index"))

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
        return redirect(url_for("index"))

    if not lessons:
        flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        # --- FIX: Changed field name from 'question_text' to 'text' --- #
        question_text = request.form.get("text")
        # ------------------------------------------------------------- #
        lesson_id = request.form.get("lesson_id")
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
            existing_question = Question.query.filter_by(question_text=question_text, lesson_id=lesson_id).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to add duplicate question (Text: {question_text}, Lesson ID: {lesson_id}).")
                flash("هذا السؤال موجود بالفعل لهذا الدرس. لم يتم الحفظ.", "warning")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate question check.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال: {query_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        q_image_file = request.files.get("question_image")
        q_image_path = save_upload(q_image_file, subfolder="questions")

        try:
            new_question = Question(
                question_text=question_text,
                lesson_id=lesson_id,
                image_url=q_image_path,
                # quiz_id=... 
            )
            db.session.add(new_question)
            db.session.flush() 
            current_app.logger.info(f"New question ID obtained: {new_question.question_id}")

            options_data = []
            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))
            actual_correct_option_text = None

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")

                if option_text and option_text.strip():
                    # --- FIX: Removed option image handling --- #
                    # option_image_file = request.files.get(f"option_image_{index_str}")
                    # option_image_path = save_upload(option_image_file, subfolder="options")
                    # ---------------------------------------- #
                    is_correct = (i == correct_option_index)

                    options_data.append({
                        "option_text": option_text.strip(),
                        # "image_path": option_image_path, # Removed
                        "is_correct": is_correct,
                        "question_id": new_question.question_id
                    })
                    if is_correct:
                        actual_correct_option_text = option_text.strip()

            if len(options_data) < 2:
                 current_app.logger.warning("Less than 2 valid options provided. Rolling back implicitly.")
                 flash("يجب إضافة خيارين على الأقل بنص غير فارغ.", "danger")
                 db.session.rollback()
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            if correct_option_index >= len(options_data):
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(options_data)} options.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                db.session.rollback()
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            current_app.logger.info(f"Adding {len(options_data)} options to the session...")
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
        # --- FIX: Changed field name from 'question_text' to 'text' --- #
        question_text = request.form.get("text")
        # ------------------------------------------------------------- #
        lesson_id = request.form.get("lesson_id")
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
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال: {query_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        q_image_file = request.files.get("question_image")
        q_image_path = save_upload(q_image_file, subfolder="questions")

        try:
            question.question_text = question_text
            question.lesson_id = lesson_id
            if q_image_path:
                # TODO: Delete old image if replaced?
                question.image_url = q_image_path
            elif request.form.get("remove_question_image"): # Checkbox to remove image
                 question.image_url = None

            # --- Handle Options --- #
            options_data = []
            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))
            option_ids_submitted = {request.form.get(f"option_id_{key.split('_')[-1]}") for key in option_keys if request.form.get(f"option_id_{key.split('_')[-1]}")}

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")
                option_id = request.form.get(f"option_id_{index_str}")

                if option_text and option_text.strip():
                    is_correct = (i == correct_option_index)
                    options_data.append({
                        "option_id": int(option_id) if option_id else None,
                        "option_text": option_text.strip(),
                        "is_correct": is_correct,
                        "question_id": question.question_id
                    })

            if len(options_data) < 2:
                 current_app.logger.warning("Less than 2 valid options provided during edit. Rolling back implicitly.")
                 flash("يجب أن يحتوي السؤال على خيارين على الأقل بنص غير فارغ.", "danger")
                 db.session.rollback() # Rollback changes made to question object
                 return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            if correct_option_index >= len(options_data):
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(options_data)} options during edit.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                db.session.rollback()
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            # Update existing options and add new ones
            existing_options_map = {opt.option_id: opt for opt in question.options}
            updated_option_ids = set()

            for opt_data in options_data:
                opt_id = opt_data.pop("option_id")
                if opt_id and opt_id in existing_options_map:
                    # Update existing option
                    existing_option = existing_options_map[opt_id]
                    existing_option.option_text = opt_data["option_text"]
                    existing_option.is_correct = opt_data["is_correct"]
                    # Update image if needed (not implemented here)
                    updated_option_ids.add(opt_id)
                else:
                    # Add new option
                    new_option = Option(**opt_data)
                    question.options.append(new_option) # Associate with question

            # Remove options that were deleted in the form
            options_to_delete = [opt for opt_id, opt in existing_options_map.items() if opt_id not in updated_option_ids and str(opt_id) not in option_ids_submitted]
            for opt_to_delete in options_to_delete:
                db.session.delete(opt_to_delete)

            try:
                db.session.commit()
                current_app.logger.info(f"Question ID {question_id} updated successfully.")
                flash("تم حفظ التعديلات بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit for edit_question ID {question_id}: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ التعديلات: {commit_error}", "danger")
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question ID {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question ID {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))

