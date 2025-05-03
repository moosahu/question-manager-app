# src/routes/question.py (Corrected)

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
    try:
        from extensions import db
    except ImportError:
        print("Warning: Could not import db from src.extensions or extensions. Trying from main.")
        try:
            from main import db
        except ImportError:
            print("Error: Database object 'db' could not be imported.")
            raise

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

question_bp = Blueprint("question", __name__, template_folder="../templates/question")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)

def sanitize_path(path):
    if not path:
        return None
    path = path.replace("\\", "/")
    if path.startswith("/") or "../" in path:
        current_app.logger.warning(f"Attempted path traversal or absolute path: {path}")
        return None
    path = path.strip("/")
    return path

def save_upload(file, subfolder="questions"):
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{filename}"
        safe_subfolder = secure_filename(subfolder)
        if not safe_subfolder:
            safe_subfolder = "default_uploads"
            current_app.logger.warning(f"Invalid subfolder name '{subfolder}', using '{safe_subfolder}'.")
        upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder, "uploads"))
        upload_dir = os.path.join(upload_folder, safe_subfolder)
        try:
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            relative_path = f"uploads/{safe_subfolder}/{filename}"
            current_app.logger.info(f"File saved successfully: {relative_path}")
            return relative_path
        except Exception as e:
            current_app.logger.error(f"Error saving file {filename} to {upload_dir}: {e}", exc_info=True)
            return None
    elif file and file.filename:
        current_app.logger.warning(f"File type not allowed: {file.filename}")
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
            Question.query
            .options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            )
            .order_by(Question.question_id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")
        rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
        current_app.logger.info("Template rendering successful.")
        return rendered_template
    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash(f"حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger")
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
        return []

@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        q_image_path = save_upload(q_image_file, subfolder="questions")

        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        if correct_option_index_str is None:
            error_messages.append("يجب تحديد الإجابة الصحيحة.")
        
        correct_option_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                     error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")

        options_data_from_form = []
        option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))
        
        for i, key in enumerate(option_keys):
            index_str = key.split("_")[-1]
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            option_image_path = save_upload(option_image_file, subfolder="options")

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index >= len(options_data_from_form) and correct_option_index_str is not None:
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            form_data = request.form.to_dict()
            form_data['options'] = options_data_from_form
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        if question_text:
            try:
                existing_question = Question.query.filter_by(question_text=question_text, lesson_id=lesson_id).first()
                if existing_question:
                    flash("هذا السؤال (بنفس النص والدرس) موجود بالفعل. لم يتم الحفظ.", "warning")
                    form_data = request.form.to_dict()
                    form_data['options'] = options_data_from_form
                    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")
            except Exception as query_error:
                current_app.logger.exception("Error during duplicate question check.")
                flash("حدث خطأ أثناء التحقق من تكرار السؤال.", "danger")
                form_data = request.form.to_dict()
                form_data['options'] = options_data_from_form
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        try:
            new_question = Question(
                question_text=question_text if question_text else None,
                lesson_id=lesson_id,
                image_url=q_image_path
            )
            db.session.add(new_question)
            db.session.flush()
            current_app.logger.info(f"New question added (pending commit) with ID: {new_question.question_id}")

            for opt_data in options_data_from_form:
                option = Option(
                    option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                    image_url=opt_data["image_url"],
                    is_correct=opt_data["is_correct"],
                    question_id=new_question.question_id
                )
                db.session.add(option)
            
            db.session.commit()
            current_app.logger.info("Transaction committed successfully. Question and options saved.")
            flash("تمت إضافة السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error adding question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء إضافة السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال.", "danger")
        
        form_data = request.form.to_dict()
        form_data['options'] = options_data_from_form
        return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")


@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    lessons = get_sorted_lessons()

    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة.", "warning")
        return redirect(url_for("question.list_questions"))

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")

        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        remove_question_image = request.form.get("remove_question_image") == 'on'

        new_q_image_path = save_upload(q_image_file, subfolder="questions")
        final_q_image_path = question.image_url
        if new_q_image_path:
            # TODO: Delete old image question.image_url if it exists?
            final_q_image_path = new_q_image_path
        elif remove_question_image:
            # TODO: Delete old image question.image_url if it exists?
            final_q_image_path = None

        error_messages = []
        if not question_text and not final_q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        
        submitted_options_count = len([key for key in request.form if key.startswith("option_text_")])
        if correct_option_index_str is None and submitted_options_count > 0:
             error_messages.append("يجب تحديد الإجابة الصحيحة.")

        correct_option_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                    error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")

        # --- Process Options (Update/Add/Delete) --- #
        options_data_from_form = []
        option_ids_submitted = set()
        max_option_index = -1

        # Iterate through form fields related to options
        for key in request.form:
            if key.startswith("option_text_"):
                index_str = key.split("_")[-1]
                try:
                    current_index = int(index_str)
                    max_option_index = max(max_option_index, current_index)
                    
                    option_id = request.form.get(f"option_id_{index_str}") # Existing option ID
                    option_text = request.form.get(f"option_text_{index_str}", "").strip()
                    option_image_file = request.files.get(f"option_image_{index_str}")
                    remove_option_image = request.form.get(f"remove_option_image_{index_str}") == 'on'
                    existing_image_url = request.form.get(f"existing_image_url_{index_str}") # Hidden field for existing URL

                    new_option_image_path = save_upload(option_image_file, subfolder="options")
                    final_option_image_path = existing_image_url # Start with existing

                    if new_option_image_path:
                        # TODO: Delete old image if existing_image_url exists?
                        final_option_image_path = new_option_image_path
                    elif remove_option_image:
                        # TODO: Delete old image if existing_image_url exists?
                        final_option_image_path = None

                    # Only consider the option if it has text OR an image
                    if option_text or final_option_image_path:
                        is_correct = (correct_option_index_str is not None and current_index == correct_option_index)
                        options_data_from_form.append({
                            "index": current_index, # Original index from form
                            "option_id": int(option_id) if option_id else None, # Convert to int if exists
                            "option_text": option_text,
                            "image_url": final_option_image_path,
                            "is_correct": is_correct
                        })
                        if option_id:
                            option_ids_submitted.add(int(option_id))
                except ValueError:
                    current_app.logger.warning(f"Could not parse index from key: {key}")
                    continue # Skip this malformed key

        # --- Further Validation --- #
        if len(options_data_from_form) < 2:
            error_messages.append("يجب توفير خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index_str is not None and correct_option_index > max_option_index:
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        # --- Handle Validation Errors --- #
        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form - Need to pass processed data back carefully
            # We pass the original question object and the partially processed options
            # The template needs logic to handle displaying this mixed state
            return render_template("question/form.html", 
                                   title=f"تعديل السؤال #{question_id}", 
                                   lessons=lessons, 
                                   question=question, # Pass original question for context
                                   # Pass submitted data for repopulation (might need adjustments in template)
                                   submitted_data=request.form.to_dict(), 
                                   processed_options=options_data_from_form,
                                   correct_option_index=correct_option_index,
                                   submit_text="حفظ التعديلات")

        # --- Update Database --- #
        try:
            # Update Question fields
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_path
            # question.quiz_id = ... # Update if needed

            # --- Update/Add Options --- #
            existing_option_ids = {opt.option_id for opt in question.options}
            
            for opt_data in options_data_from_form:
                if opt_data["option_id"] and opt_data["option_id"] in existing_option_ids:
                    # Update existing option
                    option_to_update = next((opt for opt in question.options if opt.option_id == opt_data["option_id"]), None)
                    if option_to_update:
                        option_to_update.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                        option_to_update.image_url = opt_data["image_url"]
                        option_to_update.is_correct = opt_data["is_correct"]
                elif not opt_data["option_id"]:
                    # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question_id
                    )
                    db.session.add(new_option)
            
            # --- Delete Options --- #
            options_to_delete = existing_option_ids - option_ids_submitted
            if options_to_delete:
                Option.query.filter(Option.option_id.in_(options_to_delete)).delete(synchronize_session=False)
                # TODO: Delete associated image files for deleted options?

            db.session.commit()
            current_app.logger.info(f"Question ID {question_id} updated successfully.")
            flash("تم تحديث السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error updating question {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تحديث السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error updating question {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تحديث السؤال.", "danger")

        # If commit failed, render form again with original question data
        # (Repopulating with failed POST data is complex, showing original is safer)
        correct_option_index = -1
        for i, option in enumerate(question.options):
            if option.is_correct:
                correct_option_index = i
                break
        return render_template("question/form.html", 
                               title=f"تعديل السؤال #{question_id}", 
                               lessons=lessons, 
                               question=question, 
                               correct_option_index=correct_option_index,
                               submit_text="حفظ التعديلات")

    # --- GET Request --- 
    # (This code is outside the 'if request.method == "POST":' block)
    # (Correct indentation level)
    
    # Find the index of the correct option to pre-select the radio button
    correct_option_index = -1
    for i, option in enumerate(question.options):
        if option.is_correct:
            correct_option_index = i
            break

    return render_template("question/form.html", 
                           title=f"تعديل السؤال #{question.question_id}", 
                           lessons=lessons, 
                           question=question, # Pass the fetched question object
                           correct_option_index=correct_option_index, # Pass the index for radio button
                           submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        # TODO: Delete associated image files (question and options) before deleting from DB
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح!", "success")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database error deleting question {question_id}: {db_error}")
        flash("خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")
    return redirect(url_for("question.list_questions"))

