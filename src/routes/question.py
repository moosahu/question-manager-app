# src/routes/question.py (Updated to use os.environ directly and fix edit POST error handling)

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

# --- Updated save_upload function to use os.environ directly --- #
def save_upload(file, subfolder="questions"):
    if not IMAGEKIT_ENABLED:
        current_app.logger.error("ImageKit.io SDK not loaded. Cannot upload file.")
        # Avoid flashing here if the goal is just to return None and let the route handle feedback
        # flash("خطأ في إعدادات رفع الصور. يرجى مراجعة المسؤول.", "danger")
        return None

    if file and file.filename and allowed_file(file.filename):
        # Initialize ImageKit client using environment variables directly
        try:
            private_key = os.environ.get('IMAGEKIT_PRIVATE_KEY')
            public_key = os.environ.get('IMAGEKIT_PUBLIC_KEY')
            url_endpoint = os.environ.get('IMAGEKIT_URL_ENDPOINT')

            if not all([private_key, public_key, url_endpoint]):
                missing_keys = []
                if not private_key: missing_keys.append('IMAGEKIT_PRIVATE_KEY')
                if not public_key: missing_keys.append('IMAGEKIT_PUBLIC_KEY')
                if not url_endpoint: missing_keys.append('IMAGEKIT_URL_ENDPOINT')
                current_app.logger.error(f"ImageKit configuration missing from environment variables: {', '.join(missing_keys)}. Please ensure they are set correctly in Render.")
                flash("خطأ في إعدادات رفع الصور. يرجى مراجعة المسؤول.", "danger")
                return None

            current_app.logger.debug("Attempting to initialize ImageKit using os.environ values.")
            imagekit = ImageKit(
                private_key=private_key,
                public_key=public_key,
                url_endpoint=url_endpoint
            )
            current_app.logger.debug("ImageKit client initialized successfully using os.environ.")

        except Exception as e:
             current_app.logger.error(f"Failed to initialize ImageKit client using os.environ: {e}")
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
                # Log the raw response for detailed debugging
                raw_response = upload_response.response_metadata.raw if upload_response and upload_response.response_metadata else 'No response metadata'
                current_app.logger.error(f"ImageKit upload failed. Raw Response: {raw_response}")
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
        return redirect(url_for("index")) # Redirect to a safe page like index

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
        return redirect(url_for("curriculum.list_courses") if "curriculum" in current_app.blueprints else url_for("index"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        q_image_url = save_upload(q_image_file, subfolder="questions")

        error_messages = []
        if not question_text and not q_image_url:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")

        option_keys_submitted = [key for key in request.form if key.startswith("option_text_")]
        if correct_option_index_str is None and option_keys_submitted:
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
        max_submitted_index = -1
        # Iterate through potential indices based on submitted keys
        indices_submitted = set()
        for key in request.form:
            if key.startswith("option_text_") or key.startswith("option_image_"):
                try:
                    index_str = key.split("_")[-1]
                    indices_submitted.add(int(index_str))
                except (ValueError, IndexError):
                    continue

        if not indices_submitted:
             max_submitted_index = -1 # No options submitted
        else:
             max_submitted_index = max(indices_submitted)

        for current_index in range(max_submitted_index + 1):
            # Check if this index was actually submitted (might have gaps if user deletes)
            option_text_key = f"option_text_{current_index}"
            option_image_key = f"option_image_{current_index}"

            # Only process if either text field exists or image file was potentially uploaded for this index
            if option_text_key in request.form or option_image_key in request.files:
                option_text = request.form.get(option_text_key, "").strip()
                option_image_file = request.files.get(option_image_key)
                option_image_url = save_upload(option_image_file, subfolder="options")

                if option_text or option_image_url:
                    is_correct = (current_index == correct_option_index)
                    options_data_from_form.append({
                        "index": current_index,
                        "option_text": option_text,
                        "image_url": option_image_url,
                        "is_correct": is_correct
                    })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index > max_submitted_index and correct_option_index_str is not None:
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Reconstruct form data for template, preserving input values
            form_data_rebuilt = {
                'question_text': question_text,
                'lesson_id': int(lesson_id) if lesson_id else None,
                'image_url': q_image_url, # Pass potentially uploaded question image URL
                'explanation': request.form.get("explanation", ""),
                'options': [],
                'correct_option_index': correct_option_index # Pass the integer index
            }
            for i in range(max_submitted_index + 1):
                found_in_processed = False
                for opt in options_data_from_form:
                    if opt['index'] == i:
                        form_data_rebuilt['options'].append(opt)
                        found_in_processed = True
                        break
                if not found_in_processed:
                    # Add placeholder for indices that were submitted but maybe invalid
                    # Use request.form to get the original input value
                    form_data_rebuilt['options'].append({
                        'index': i,
                        'option_text': request.form.get(f'option_text_{i}', ''),
                        'image_url': None, # Image wasn't saved if error occurred
                        'is_correct': (str(i) == correct_option_index_str)
                    })
            # Ensure options list has at least 4 items for consistent display if adding
            while len(form_data_rebuilt['options']) < 4:
                 form_data_rebuilt['options'].append({'index': len(form_data_rebuilt['options']), 'option_text': '', 'image_url': None, 'is_correct': False})

            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data_rebuilt, submit_text="إضافة سؤال")

        try:
            new_question = Question(
                question_text=question_text if question_text else None,
                lesson_id=lesson_id,
                image_url=q_image_url
            )
            db.session.add(new_question)
            db.session.flush() # Get the ID for options
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

        # Re-render form on error after attempting DB operations
        form_data_rebuilt = {
            'question_text': question_text,
            'lesson_id': int(lesson_id) if lesson_id else None,
            'image_url': q_image_url,
            'explanation': request.form.get("explanation", ""),
            'options': options_data_from_form, # Use the processed data
            'correct_option_index': correct_option_index
        }
        # Ensure options list has at least 4 items for consistent display if adding
        while len(form_data_rebuilt['options']) < 4:
             form_data_rebuilt['options'].append({'index': len(form_data_rebuilt['options']), 'option_text': '', 'image_url': None, 'is_correct': False})

        return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data_rebuilt, submit_text="إضافة سؤال")

    # GET request
    # Prepare empty structure for the template in add mode
    empty_question_data = {
        'question_text': '',
        'lesson_id': None,
        'image_url': None,
        'explanation': '',
        'options': [{'index': i, 'option_text': '', 'image_url': None, 'is_correct': False} for i in range(4)],
        'correct_option_index': -1
    }
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=empty_question_data, submit_text="إضافة سؤال")


@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # Fetch question with options eagerly loaded
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    lessons = get_sorted_lessons()

    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة.", "warning")
        return redirect(url_for("question.list_questions"))

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")

        # --- Extract Data from Form --- #
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        remove_question_image = request.form.get("remove_question_image") == 'on'
        explanation_text = request.form.get("explanation", "").strip()
        # Add handling for explanation image if needed

        # --- Handle Question Image --- #
        new_q_image_url = save_upload(q_image_file, subfolder="questions")
        final_q_image_url = question.image_url
        if new_q_image_url:
            # TODO: Optionally delete old image from ImageKit
            final_q_image_url = new_q_image_url
        elif remove_question_image:
            # TODO: Optionally delete old image from ImageKit
            final_q_image_url = None

        # --- Basic Validation --- #
        error_messages = []
        if not question_text and not final_q_image_url:
            error_messages.append("يجب توفير نص للسؤال أو صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")

        correct_option_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                    error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")
        else:
            # Check if any options were submitted at all before demanding a correct one
            if any(k.startswith('option_text_') or k.startswith('option_image_') for k in request.form or k in request.files):
                 error_messages.append("يجب تحديد الإجابة الصحيحة.")

        # --- Process Options (Update/Add/Delete) --- #
        options_data_from_form = [] # Stores processed data for valid options from form
        option_ids_submitted = set() # Keep track of existing option IDs submitted
        max_submitted_index = -1 # Track the highest index submitted
        existing_options_map = {opt.option_id: opt for opt in question.options}

        # Determine the highest index present in the form submission
        indices_submitted = set()
        for key in request.form:
            if key.startswith("option_text_") or key.startswith("option_id_"):
                try:
                    index_str = key.split("_")[-1]
                    indices_submitted.add(int(index_str))
                except (ValueError, IndexError):
                    continue
        for key in request.files:
             if key.startswith("option_image_"):
                try:
                    index_str = key.split("_")[-1]
                    indices_submitted.add(int(index_str))
                except (ValueError, IndexError):
                    continue

        if indices_submitted:
            max_submitted_index = max(indices_submitted)

        # Iterate through all possible indices up to the max submitted
        for current_index in range(max_submitted_index + 1):
            option_id_str = request.form.get(f"option_id_{current_index}")
            option_id = int(option_id_str) if option_id_str else None
            option_text = request.form.get(f"option_text_{current_index}", "").strip()
            option_image_file = request.files.get(f"option_image_{current_index}")
            remove_option_image = request.form.get(f"remove_option_image_{current_index}") == 'on'

            # Determine the image URL for this option
            original_image_url = None
            if option_id and option_id in existing_options_map:
                original_image_url = existing_options_map[option_id].image_url

            new_option_image_url = save_upload(option_image_file, subfolder="options")
            final_option_image_url = original_image_url

            if new_option_image_url:
                # TODO: Optionally delete old image from ImageKit
                final_option_image_url = new_option_image_url
            elif remove_option_image:
                # TODO: Optionally delete old image from ImageKit
                final_option_image_url = None

            # Consider the option valid if it has text or an image URL (new or existing)
            if option_text or final_option_image_url:
                is_correct = (current_index == correct_option_index)
                options_data_from_form.append({
                    "id": option_id,
                    "index": current_index, # Keep track of the display index
                    "option_text": option_text,
                    "image_url": final_option_image_url,
                    "is_correct": is_correct
                })
                if option_id:
                    option_ids_submitted.add(option_id)
            elif option_id: # If it had an ID but now has no text/image, it might be marked for deletion implicitly
                 pass # Handled later by checking option_ids_submitted vs existing_options_map

        # Determine options to delete (existing options not submitted)
        options_to_delete_ids = set(existing_options_map.keys()) - option_ids_submitted

        # --- Final Validation --- #
        if len(options_data_from_form) < 2:
            error_messages.append("يجب أن يحتوي السؤال على خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index > max_submitted_index and correct_option_index_str is not None:
            # This check might be redundant if the loop goes up to max_submitted_index
            # Check if the selected correct index corresponds to a valid processed option
            if not any(opt['index'] == correct_option_index for opt in options_data_from_form):
                 error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        # --- Handle Errors: Re-render Form --- #
        if error_messages:
            for error in error_messages:
                flash(error, "danger")

            # Reconstruct form data for template, preserving input values and structure
            form_data_rebuilt = {
                'question_id': question.question_id,
                'question_text': question_text, # Submitted text
                'lesson_id': int(lesson_id) if lesson_id else question.lesson_id, # Submitted or original lesson
                'image_url': final_q_image_url, # Processed question image URL
                'explanation': explanation_text, # Submitted explanation
                # 'explanation_image_path': ..., # Handle explanation image if needed
                'options': [],
                'correct_option_index': correct_option_index # Pass the integer index
            }

            # Populate options based on processed data and original form input
            for i in range(max_submitted_index + 1):
                processed_opt = next((opt for opt in options_data_from_form if opt['index'] == i), None)
                if processed_opt:
                    # Use the data already processed (handles images correctly)
                    form_data_rebuilt['options'].append(processed_opt)
                else:
                    # This index might have been invalid or intentionally skipped
                    # Reconstruct from original form input for display consistency
                    option_id_str = request.form.get(f"option_id_{i}")
                    original_image_url_for_render = None
                    if option_id_str:
                        try:
                            opt_id = int(option_id_str)
                            if opt_id in existing_options_map and opt_id not in options_to_delete_ids:
                                original_image_url_for_render = existing_options_map[opt_id].image_url
                        except ValueError:
                            pass

                    form_data_rebuilt['options'].append({
                        'id': option_id_str,
                        'index': i,
                        'option_text': request.form.get(f'option_text_{i}', ''),
                        'image_url': original_image_url_for_render, # Show original image if not removed/replaced
                        'is_correct': (str(i) == correct_option_index_str)
                    })

            # Ensure at least 2 options are available for display in edit mode
            while len(form_data_rebuilt['options']) < 2:
                 form_data_rebuilt['options'].append({'id': None, 'index': len(form_data_rebuilt['options']), 'option_text': '', 'image_url': None, 'is_correct': False})

            return render_template("question/form.html",
                                   title="تعديل السؤال",
                                   lessons=lessons,
                                   question=form_data_rebuilt, # Pass the carefully reconstructed dict
                                   submit_text="حفظ التعديلات")

        # --- No Errors: Proceed with Database Update --- #
        try:
            # Update Question
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_url
            question.explanation = explanation_text if explanation_text else None
            # Update explanation image if needed
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
                elif opt_data["id"] is None: # Only add if ID is None (truly new option)
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
            for option_id_to_delete in options_to_delete_ids:
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

        # Re-render form on DB error (similar logic to validation error)
        # Reconstruct form data for template, preserving input values and structure
        form_data_rebuilt = {
            'question_id': question.question_id,
            'question_text': question_text,
            'lesson_id': int(lesson_id) if lesson_id else question.lesson_id,
            'image_url': final_q_image_url,
            'explanation': explanation_text,
            'options': [],
            'correct_option_index': correct_option_index
        }
        # Populate options based on processed data and original form input
        for i in range(max_submitted_index + 1):
            processed_opt = next((opt for opt in options_data_from_form if opt['index'] == i), None)
            if processed_opt:
                form_data_rebuilt['options'].append(processed_opt)
            else:
                option_id_str = request.form.get(f"option_id_{i}")
                original_image_url_for_render = None
                if option_id_str:
                    try:
                        opt_id = int(option_id_str)
                        if opt_id in existing_options_map and opt_id not in options_to_delete_ids:
                            original_image_url_for_render = existing_options_map[opt_id].image_url
                    except ValueError:
                        pass
                form_data_rebuilt['options'].append({
                    'id': option_id_str,
                    'index': i,
                    'option_text': request.form.get(f'option_text_{i}', ''),
                    'image_url': original_image_url_for_render,
                    'is_correct': (str(i) == correct_option_index_str)
                })
        while len(form_data_rebuilt['options']) < 2:
             form_data_rebuilt['options'].append({'id': None, 'index': len(form_data_rebuilt['options']), 'option_text': '', 'image_url': None, 'is_correct': False})

        return render_template("question/form.html",
                               title="تعديل السؤال",
                               lessons=lessons,
                               question=form_data_rebuilt,
                               submit_text="حفظ التعديلات")

    # --- GET Request --- #
    # Prepare data structure for the template, ensuring options are structured correctly
    question_data_for_template = {
        'question_id': question.question_id,
        'question_text': question.question_text,
        'lesson_id': question.lesson_id,
        'image_url': question.image_url,
        'explanation': question.explanation,
        # 'explanation_image_path': question.explanation_image_path, # Add if exists
        'options': [],
        'correct_option_index': -1
    }
    # Convert Option objects to dictionaries for consistent template handling
    for i, opt in enumerate(question.options):
        question_data_for_template['options'].append({
            'id': opt.option_id,
            'index': i, # Assign index based on order from DB
            'option_text': opt.option_text,
            'image_url': opt.image_url,
            'is_correct': opt.is_correct
        })
        if opt.is_correct:
            question_data_for_template['correct_option_index'] = i

    # Ensure at least 2 options are available for display in edit mode
    while len(question_data_for_template['options']) < 2:
        question_data_for_template['options'].append({'id': None, 'index': len(question_data_for_template['options']), 'option_text': '', 'image_url': None, 'is_correct': False})

    return render_template("question/form.html",
                           title="تعديل السؤال",
                           lessons=lessons,
                           question=question_data_for_template, # Pass the structured dict
                           submit_text="حفظ التعديلات")

# Add delete route if needed
# @question_bp.route("/delete/<int:question_id>", methods=["POST"])
# @login_required
# def delete_question(question_id):
#     question = Question.query.get_or_404(question_id)
#     try:
#         # TODO: Delete associated images from ImageKit first!
#         # Delete options first due to foreign key constraints
#         Option.query.filter_by(question_id=question.question_id).delete()
#         db.session.delete(question)
#         db.session.commit()
#         flash("تم حذف السؤال بنجاح.", "success")
#     except Exception as e:
#         db.session.rollback()
#         current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
#         flash("حدث خطأ أثناء حذف السؤال.", "danger")
#     return redirect(url_for("question.list_questions"))

