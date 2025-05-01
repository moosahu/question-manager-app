"""
Modifies the add_question route in src/routes/question.py to check for duplicate questions
(same text and same lesson_id) before adding a new one.
"""

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError

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
        questions_pagination = (Question.query.options(
                db.joinedload(Question.options),
                db.joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
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

@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    lessons = (Lesson.query.options(db.joinedload(Lesson.unit).joinedload(Unit.course))
                      .order_by(Course.name, Unit.name, Lesson.name).all())
    if not lessons:
        flash("الرجاء إضافة المناهج (دورات، وحدات، دروس) أولاً قبل إضافة الأسئلة.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text")
        lesson_id = request.form.get("lesson_id")
        explanation = request.form.get("explanation")
        correct_option_index_str = request.form.get("correct_option")

        # Basic validation
        if not question_text or not lesson_id or correct_option_index_str is None:
            flash("يرجى ملء جميع الحقول المطلوبة (نص السؤال، الدرس، تحديد الإجابة الصحيحة).", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        try:
            correct_option_index = int(correct_option_index_str)
        except ValueError:
            flash("اختيار الإجابة الصحيحة غير صالح.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        # *** START: Duplicate Question Check ***
        try:
            existing_question = Question.query.filter_by(text=question_text, lesson_id=lesson_id).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to add duplicate question (Text: '{question_text}', Lesson ID: {lesson_id}).")
                flash("هذا السؤال موجود بالفعل لهذا الدرس. لم يتم الحفظ.", "warning")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate question check.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال: {query_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        # *** END: Duplicate Question Check ***

        # File uploads (continue only if not duplicate)
        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")
        current_app.logger.info("Attempting to save question image...")
        q_image_path = save_upload(q_image_file, subfolder="questions")
        current_app.logger.info(f"Question image path: {q_image_path}")
        current_app.logger.info("Attempting to save explanation image...")
        e_image_path = save_upload(e_image_file, subfolder="explanations")
        current_app.logger.info(f"Explanation image path: {e_image_path}")

        # Database Operations
        try:
            current_app.logger.info("Creating Question object...")
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

            # Options processing
            options_data = []
            options_added = 0
            for i in range(4):
                option_text = request.form.get(f"option_text_{i}")
                if option_text:
                    option_image_file = request.files.get(f"option_image_{i}")
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    is_correct = (i == correct_option_index)
                    options_data.append({
                        "text": option_text,
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": new_question.id
                    })
                    options_added += 1

            if options_added < 2:
                 current_app.logger.warning("Less than 2 options provided. Rolling back implicitly.")
                 flash("يجب إضافة خيارين على الأقل.", "danger")
                 # No explicit rollback needed here as commit hasn't happened
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
            else:
                current_app.logger.info(f"Adding {len(options_data)} options to the session...")
                for opt_data in options_data:
                    option = Option(**opt_data)
                    db.session.add(option)

                # Commit transaction
                current_app.logger.info("Attempting to commit transaction...")
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
            current_app.logger.exception(f"Database Error adding question (before commit attempt): {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء إضافة السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question (before commit attempt): {e}")
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال: {e}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
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

        # *** START: Duplicate Check (for edit - slightly different logic might be needed if text/lesson changes) ***
        # Check if the text/lesson combination already exists for *another* question.
        try:
            existing_question = Question.query.filter(
                Question.text == question_text,
                Question.lesson_id == lesson_id,
                Question.id != question_id # Exclude the current question being edited
            ).first()
            if existing_question:
                current_app.logger.warning(f"Attempt to edit question ID {question_id} to duplicate another question (Text: '{question_text}', Lesson ID: {lesson_id}).")
                flash("يوجد سؤال آخر بنفس النص والدرس. لا يمكن حفظ التعديل.", "warning")
                # Re-render with original question data before modification attempt
                question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id) # Re-fetch original
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as query_error:
            current_app.logger.exception("Error during duplicate check in edit_question.")
            flash(f"حدث خطأ أثناء التحقق من تكرار السؤال عند التعديل: {query_error}", "danger")
            question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id) # Re-fetch original
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        # *** END: Duplicate Check (for edit) ***

        q_image_file = request.files.get("question_image")
        e_image_file = request.files.get("explanation_image")

        q_image_path = question.image_path
        if q_image_file:
            new_q_path = save_upload(q_image_file, subfolder="questions")
            if new_q_path:
                q_image_path = new_q_path
            else:
                flash("فشل تحميل صورة السؤال الجديدة.", "warning")

        e_image_path = question.explanation_image_path
        if e_image_file:
            new_e_path = save_upload(e_image_file, subfolder="explanations")
            if new_e_path:
                e_image_path = new_e_path
            else:
                flash("فشل تحميل صورة الشرح الجديدة.", "warning")

        try:
            question.text = question_text
            question.lesson_id = lesson_id
            question.image_path = q_image_path
            question.explanation = explanation
            question.explanation_image_path = e_image_path

            existing_options = {opt.id: opt for opt in question.options}
            options_to_keep = set()
            options_updated = 0

            for i in range(4):
                option_id_str = request.form.get(f"option_id_{i}")
                option_text = request.form.get(f"option_text_{i}")
                option_image_file = request.files.get(f"option_image_{i}")
                is_correct = (i == correct_option_index)

                if option_text:
                    options_updated += 1
                    option_id = int(option_id_str) if option_id_str else None
                    option = existing_options.get(option_id) if option_id else None

                    opt_image_path = option.image_path if option else None
                    if option_image_file:
                        new_opt_path = save_upload(option_image_file, subfolder="options")
                        if new_opt_path:
                            opt_image_path = new_opt_path
                        else:
                            flash(f"فشل تحميل صورة الخيار {i+1} الجديدة.", "warning")

                    if option:
                        option.text = option_text
                        option.image_path = opt_image_path
                        option.is_correct = is_correct
                        options_to_keep.add(option_id)
                    else:
                        new_option = Option(
                            text=option_text,
                            image_path=opt_image_path,
                            is_correct=is_correct,
                            question_id=question_id
                        )
                        db.session.add(new_option)

            options_to_delete = set(existing_options.keys()) - options_to_keep
            if options_to_delete:
                for opt_id in options_to_delete:
                    db.session.delete(existing_options[opt_id])

            if options_updated < 2:
                 db.session.rollback()
                 flash("يجب توفير خيارين على الأقل.", "danger")
                 question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id)
                 return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            try:
                db.session.commit()
                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit while editing question ID {question_id}: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ تعديلات السؤال: {commit_error}", "danger")
                question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id)
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question ID {question_id} (before commit attempt): {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            question = Question.query.options(db.joinedload(Question.options)).get_or_404(question_id)
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
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
        # TODO: Delete associated image files
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))

"""
Note: I also added a similar duplicate check within the edit_question route
to prevent editing a question in a way that makes it a duplicate of *another* existing question.
"""
