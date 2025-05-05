# src/routes/question.py (Updated for ImageKit.io + Debug Logging)

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

# --- Updated save_upload function for ImageKit.io + Debug Logging --- #
def save_upload(file, subfolder="questions"):
    if not IMAGEKIT_ENABLED:
        current_app.logger.error("ImageKit.io SDK not loaded. Cannot upload file.")
        flash("خطأ في إعدادات رفع الصور. يرجى مراجعة المسؤول.", "danger")
        return None

    if file and file.filename and allowed_file(file.filename):
        # Initialize ImageKit client (ensure these config keys are set in your Flask app)
        try:
            # --- Add Debug Logging --- #
            private_key = current_app.config.get('IMAGEKIT_PRIVATE_KEY')
            public_key = current_app.config.get('IMAGEKIT_PUBLIC_KEY')
            url_endpoint = current_app.config.get('IMAGEKIT_URL_ENDPOINT')
            current_app.logger.debug(f"Attempting to initialize ImageKit. Private Key found: {'Yes' if private_key else 'No'}, Public Key found: {'Yes' if public_key else 'No'}, URL Endpoint found: {'Yes' if url_endpoint else 'No'}")
            # Log the actual values for debugging (be cautious in production)
            current_app.logger.debug(f"IMAGEKIT_PRIVATE_KEY from config: {private_key}")
            current_app.logger.debug(f"IMAGEKIT_PUBLIC_KEY from config: {public_key}")
            current_app.logger.debug(f"IMAGEKIT_URL_ENDPOINT from config: {url_endpoint}")
            # --- End Debug Logging --- #

            # Use the values directly now, which will raise KeyError if None/missing
            imagekit = ImageKit(
                private_key=current_app.config['IMAGEKIT_PRIVATE_KEY'],
                public_key=current_app.config['IMAGEKIT_PUBLIC_KEY'],
                url_endpoint=current_app.config['IMAGEKIT_URL_ENDPOINT']
            )
        except KeyError as e:
            # Log the specific missing key
            current_app.logger.error(f"ImageKit configuration missing: Key '{e}' not found in Flask config. Please ensure IMAGEKIT_PRIVATE_KEY, IMAGEKIT_PUBLIC_KEY, and IMAGEKIT_URL_ENDPOINT are set correctly as environment variables in Render and loaded into Flask config.")
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
                    final_option_image_url = existing_image_url

                    if new_option_image_url:
                        # TODO: Optionally delete old image from ImageKit
                        final_option_image_url = new_option_image_url
                    elif remove_option_image:
                        # TODO: Optionally delete old image from ImageKit
                        final_option_image_url = None

                    if option_text or final_option_image_url:
                        is_correct = (current_index == correct_option_index)
                        options_data_from_form.append({
                            "id": option_id,
                            "index": current_index,
                            "option_text": option_text,
                            "image_url": final_option_image_url,
                            "is_correct": is_correct
                        })
                        if option_id:
                            option_ids_submitted.add(option_id)

                except ValueError:
                    current_app.logger.warning(f"Invalid index found in form key: {key}")
                    continue # Skip this malformed key

        # Determine options to delete
        for existing_id in existing_options_map.keys():
            if existing_id not in option_ids_submitted:
                options_to_delete.append(existing_id)

        if len(options_data_from_form) < 2:
            error_messages.append("يجب أن يحتوي السؤال على خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index > max_option_index and correct_option_index_str is not None:
            error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Re-populate form data for rendering, including existing options not modified
            form_data = {
                'question_id': question.question_id,
                'question_text': question_text,
                'lesson_id': int(lesson_id) if lesson_id else question.lesson_id,
                'image_url': final_q_image_url,
                'options': []
            }
            # Reconstruct options as they would appear in the form
            current_options_state = []
            for i in range(max_option_index + 1):
                found = False
                for opt_data in options_data_from_form:
                    if opt_data['index'] == i:
                        current_options_state.append(opt_data)
                        found = True
                        break
                if not found:
                     # Add placeholder for removed/empty options if needed for template logic
                     pass 
            form_data['options'] = current_options_state
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=form_data, submit_text="حفظ التعديلات")

        try:
            # Update Question
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_url
            current_app.logger.info(f"Updating question ID: {question_id}")

            # Update/Add Options
            for opt_data in options_data_from_form:
                if opt_data["id"] and opt_data["id"] in existing_options_map:
                    # Update existing option
                    option_to_update = existing_options_map[opt_data["id"]]
                    option_to_update.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                    option_to_update.image_url = opt_data["image_url"]
                    option_to_update.is_correct = opt_data["is_correct"]
                    current_app.logger.info(f"Updating option ID: {opt_data['id']}")
                else:
                    # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)
                    current_app.logger.info(f"Adding new option for question ID: {question_id}")

            # Delete Options
            for option_id_to_delete in options_to_delete:
                option_to_delete = Option.query.get(option_id_to_delete)
                if option_to_delete:
                    # TODO: Optionally delete image from ImageKit before deleting DB record
                    db.session.delete(option_to_delete)
                    current_app.logger.info(f"Deleting option ID: {option_id_to_delete}")

            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully for question ID: {question_id}")
            flash("تم تحديث السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error updating question ID {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تحديث السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error updating question ID {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تحديث السؤال.", "danger")

        # Re-populate form data on error
        form_data = {
            'question_id': question.question_id,
            'question_text': question_text,
            'lesson_id': int(lesson_id) if lesson_id else question.lesson_id,
            'image_url': final_q_image_url,
            'options': options_data_from_form # Use the processed data
        }
        return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=form_data, submit_text="حفظ التعديلات")

    # GET request
    # Prepare existing data for the form
    question_data = {
        'question_id': question.question_id,
        'question_text': question.question_text,
        'lesson_id': question.lesson_id,
        'image_url': question.image_url,
        'options': [
            {
                'id': opt.option_id,
                'option_text': opt.option_text,
                'image_url': opt.image_url,
                'is_correct': opt.is_correct
            } for opt in sorted(question.options, key=lambda o: o.option_id) # Ensure consistent order
        ]
    }
    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question_data, submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    try:
        # TODO: Optionally delete all associated images from ImageKit first
        # for opt in question.options:
        #     if opt.image_url:
        #         # Need file_id to delete from ImageKit
        #         pass
        # if question.image_url:
        #     # Need file_id to delete from ImageKit
        #     pass

        # Delete options first due to relationship
        Option.query.filter_by(question_id=question_id).delete()
        # Delete the question
        db.session.delete(question)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted question ID: {question_id}")
        flash("تم حذف السؤال بنجاح!", "success")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database Error deleting question ID {question_id}: {db_error}")
        flash("خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic Error deleting question ID {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")

    return redirect(url_for("question.list_questions"))

