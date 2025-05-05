# src/routes/question.py (Updated for ImageKit.io)

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

# --- ImageKit.io Integration --- #
try:
    from imagekitio import ImageKit
    from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
    IMAGEKIT_ENABLED = True
except ImportError:
    IMAGEKIT_ENABLED = False
    print("Warning: imagekitio library not found. Image uploads will be disabled or fallback to local.")
# --- End ImageKit.io Integration --- #

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

# --- Updated save_upload function for ImageKit.io --- #
def save_upload(file, subfolder="questions"):
    if not IMAGEKIT_ENABLED:
        current_app.logger.error("ImageKit.io SDK not loaded. Cannot upload file.")
        flash("خطأ في إعدادات رفع الصور. يرجى مراجعة المسؤول.", "danger")
        return None

    if file and file.filename and allowed_file(file.filename):
        # Initialize ImageKit client (ensure these config keys are set in your Flask app)
        try:
            imagekit = ImageKit(
                private_key=current_app.config['IMAGEKIT_PRIVATE_KEY'],
                public_key=current_app.config['IMAGEKIT_PUBLIC_KEY'],
                url_endpoint=current_app.config['IMAGEKIT_URL_ENDPOINT']
            )
        except KeyError as e:
            current_app.logger.error(f"ImageKit configuration missing: {e}. Please set IMAGEKIT_PRIVATE_KEY, IMAGEKIT_PUBLIC_KEY, and IMAGEKIT_URL_ENDPOINT in your Flask config.")
            flash("خطأ في إعدادات رفع الصور. يرجى مراجعة المسؤول.", "danger")
            return None
        except Exception as e:
             current_app.logger.error(f"Failed to initialize ImageKit client: {e}")
             flash("خطأ في إعدادات رفع الصور. يرجى مراجعة المسؤول.", "danger")
             return None

        # Generate a unique filename for ImageKit
        original_filename = secure_filename(file.filename)
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{original_filename}"
        safe_subfolder = secure_filename(subfolder) if subfolder else "default"

        try:
            # Read file content for upload
            file_content = file.read()
            file.seek(0) # Reset file pointer if needed elsewhere

            # Upload to ImageKit
            upload_response = imagekit.upload_file(
                file=file_content, # Pass file content as bytes
                file_name=filename,
                options=UploadFileRequestOptions(
                    folder=f"/{safe_subfolder}/", # Specify folder in ImageKit
                    is_private_file=False,
                    use_unique_file_name=False # We already created a unique name
                )
            )

            # Check response and return URL
            if upload_response and upload_response.url:
                image_url = upload_response.url
                current_app.logger.info(f"File uploaded successfully to ImageKit: {image_url}")
                return image_url
            else:
                current_app.logger.error(f"ImageKit upload failed. Response: {upload_response}")
                flash("حدث خطأ أثناء رفع الصورة إلى خدمة التخزين.", "danger")
                return None

        except Exception as e:
            current_app.logger.error(f"Error uploading file {filename} to ImageKit: {e}", exc_info=True)
            flash("حدث خطأ غير متوقع أثناء رفع الصورة.", "danger")
            return None

    elif file and file.filename:
        current_app.logger.warning(f"File type not allowed: {file.filename}")
        flash(f"نوع الملف غير مسموح به: {file.filename}", "warning")
    return None
# --- End Updated save_upload function --- #

# --- (Rest of the code remains largely the same, calling the updated save_upload) --- #

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
        # Call the updated save_upload function
        q_image_url = save_upload(q_image_file, subfolder="questions")

        error_messages = []
        if not question_text and not q_image_url:
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
            # Call the updated save_upload function
            option_image_url = save_upload(option_image_file, subfolder="options")

            if option_text or option_image_url:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_text": option_text,
                    "image_url": option_image_url, # Use the URL from ImageKit
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
            # Pass the potentially uploaded question image URL back to the template if validation fails
            form_data['image_url'] = q_image_url
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        # Duplicate check (optional, consider if needed with image URLs)
        # ... (existing duplicate check logic might need adjustment if based solely on text)

        try:
            new_question = Question(
                question_text=question_text if question_text else None,
                lesson_id=lesson_id,
                image_url=q_image_url # Use the URL from ImageKit
            )
            db.session.add(new_question)
            db.session.flush()
            current_app.logger.info(f"New question added (pending commit) with ID: {new_question.question_id}")

            for opt_data in options_data_from_form:
                option = Option(
                    option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                    image_url=opt_data["image_url"], # Use the URL from ImageKit
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
        # Pass the potentially uploaded question image URL back to the template if error occurs after upload
        form_data['image_url'] = q_image_url
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

        # Call the updated save_upload function
        new_q_image_url = save_upload(q_image_file, subfolder="questions")
        final_q_image_url = question.image_url

        if new_q_image_url:
            # TODO: Optionally delete old image from ImageKit using its API if needed
            # imagekit.delete_file(file_id=...) # Need file_id of the old image
            final_q_image_url = new_q_image_url
        elif remove_question_image:
            # TODO: Optionally delete old image from ImageKit using its API if needed
            final_q_image_url = None

        error_messages = []
        if not question_text and not final_q_image_url:
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
        options_to_delete = []
        existing_options_map = {opt.option_id: opt for opt in question.options}

        # Iterate through form fields related to options
        for key in request.form:
            if key.startswith("option_text_"):
                index_str = key.split("_")[-1]
                try:
                    current_index = int(index_str)
                    max_option_index = max(max_option_index, current_index)

                    option_id_str = request.form.get(f"option_id_{index_str}") # Existing option ID
                    option_id = int(option_id_str) if option_id_str else None
                    option_text = request.form.get(f"option_text_{index_str}", "").strip()
                    option_image_file = request.files.get(f"option_image_{index_str}")
                    remove_option_image = request.form.get(f"remove_option_image_{index_str}") == 'on'
                    existing_image_url = request.form.get(f"existing_image_url_{index_str}") # Hidden field for existing URL

                    # Call the updated save_upload function
                    new_option_image_url = save_upload(option_image_file, subfolder="options")
                    final_option_image_url = existing_image_url # Start with existing

                    if new_option_image_url:
                        # TODO: Optionally delete old option image from ImageKit if needed
                        final_option_image_url = new_option_image_url
                    elif remove_option_image:
                        # TODO: Optionally delete old option image from ImageKit if needed
                        final_option_image_url = None

                    # Only consider the option if it has text OR an image
                    if option_text or final_option_image_url:
                        is_correct = (correct_option_index_str is not None and current_index == correct_option_index)
                        options_data_from_form.append({
                            "index": current_index, # Original index from form
                            "option_id": option_id,
                            "option_text": option_text,
                            "image_url": final_option_image_url, # Use URL from ImageKit
                            "is_correct": is_correct
                        })
                        if option_id:
                            option_ids_submitted.add(option_id)
                    elif option_id: # If an existing option has no text and no image after update, mark for deletion
                        options_to_delete.append(option_id)

                except ValueError:
                    current_app.logger.warning(f"Could not parse index or ID from key: {key}")
                    continue # Skip this malformed key

        # Determine which existing options were *not* submitted and should be deleted
        for existing_id in existing_options_map.keys():
            if existing_id not in option_ids_submitted:
                options_to_delete.append(existing_id)

        # --- Further Validation --- #
        if len(options_data_from_form) < 2:
            error_messages.append("يجب توفير خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index_str is not None and correct_option_index > max_option_index:
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        # --- Handle Validation Errors --- #
        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form data for rendering
            form_data = {
                'question_id': question.question_id,
                'text': question_text,
                'lesson_id': int(lesson_id) if lesson_id else None,
                'image_url': final_q_image_url, # Use potentially updated URL
                'options': options_data_from_form, # Use data processed from form
                'correct_option': correct_option_index if correct_option_index_str is not None else None
            }
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=form_data, submit_text="حفظ التعديلات")

        # --- Apply Changes to Database --- #
        try:
            # Update Question
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_url # Use URL from ImageKit

            # Update/Add Options
            for opt_data in options_data_from_form:
                if opt_data["option_id"] and opt_data["option_id"] in existing_options_map:
                    # Update existing option
                    existing_option = existing_options_map[opt_data["option_id"]]
                    existing_option.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                    existing_option.image_url = opt_data["image_url"] # Use URL from ImageKit
                    existing_option.is_correct = opt_data["is_correct"]
                elif opt_data["option_id"] is None: # Check if it's a new option
                    # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"], # Use URL from ImageKit
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)

            # Delete Options marked for deletion
            for option_id_to_delete in set(options_to_delete): # Use set to avoid duplicates
                if option_id_to_delete in existing_options_map:
                    # TODO: Optionally delete image from ImageKit before deleting DB record
                    option_to_delete = existing_options_map[option_id_to_delete]
                    db.session.delete(option_to_delete)
                    current_app.logger.info(f"Marked option ID {option_id_to_delete} for deletion.")

            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully. Question ID {question_id} and options updated/added/deleted.")
            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question ID {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question ID {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")

        # Repopulate form data if save fails after validation
        form_data = {
            'question_id': question.question_id,
            'text': question_text,
            'lesson_id': int(lesson_id) if lesson_id else None,
            'image_url': final_q_image_url,
            'options': options_data_from_form,
            'correct_option': correct_option_index if correct_option_index_str is not None else None
        }
        return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=form_data, submit_text="حفظ التعديلات")

    # GET request
    # Prepare data for the form, ensuring options have indices for the template
    question_data_for_form = {
        'question_id': question.question_id,
        'text': question.question_text,
        'lesson_id': question.lesson_id,
        'image_url': question.image_url,
        'options': [
            {
                'option_id': opt.option_id,
                'option_text': opt.option_text,
                'image_url': opt.image_url,
                'is_correct': opt.is_correct,
                'index': i # Add index for template logic
            } for i, opt in enumerate(question.options)
        ]
    }
    # Find the index of the correct option
    correct_option_index = next((i for i, opt in enumerate(question.options) if opt.is_correct), None)
    question_data_for_form['correct_option'] = correct_option_index

    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question_data_for_form, submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    try:
        # TODO: Optionally delete all associated images (question + options) from ImageKit
        # before deleting from DB. This requires storing file_id or iterating through URLs.

        # Deleting the question will cascade delete options due to relationship settings
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال وجميع خياراته بنجاح.", "success")
        current_app.logger.info(f"Successfully deleted question ID {question_id}.")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database error deleting question ID {question_id}: {db_error}")
        flash("حدث خطأ في قاعدة البيانات أثناء محاولة حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic error deleting question ID {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء محاولة حذف السؤال.", "danger")
    return redirect(url_for("question.list_questions"))

