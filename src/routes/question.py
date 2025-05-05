# src/routes/question.py (Updated with ImageKit.io integration and Detailed Logging - v2)

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

# Import ImageKit
from imagekitio.client import ImageKit

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

# --- Updated save_upload function with Correct Options Passing --- #
def save_upload(file, subfolder="questions"):
    current_app.logger.debug(f"Entering save_upload for subfolder: {subfolder}")
    if not file or not file.filename:
        current_app.logger.debug("No file or filename provided to save_upload.")
        return None

    current_app.logger.debug(f"Processing file: {file.filename}")

    if not allowed_file(file.filename):
        current_app.logger.warning(f"File type not allowed: {file.filename}")
        return None
    
    current_app.logger.debug(f"File type allowed for: {file.filename}")

    # Read ImageKit credentials from environment variables
    private_key = os.environ.get('IMAGEKIT_PRIVATE_KEY')
    public_key = os.environ.get('IMAGEKIT_PUBLIC_KEY')
    url_endpoint = os.environ.get('IMAGEKIT_URL_ENDPOINT')

    # Log existence of keys (avoid logging the actual keys)
    current_app.logger.debug(f"IMAGEKIT_PRIVATE_KEY exists: {bool(private_key)}")
    current_app.logger.debug(f"IMAGEKIT_PUBLIC_KEY exists: {bool(public_key)}")
    current_app.logger.debug(f"IMAGEKIT_URL_ENDPOINT exists: {bool(url_endpoint)}")

    if not all([private_key, public_key, url_endpoint]):
        current_app.logger.error("ImageKit environment variables are missing or incomplete.")
        flash("خطأ في إعدادات رفع الصور على الخادم. يرجى مراجعة متغيرات البيئة.", "danger")
        return None
    
    current_app.logger.debug("All ImageKit environment variables seem to be present.")

    try:
        current_app.logger.debug("Initializing ImageKit client...")
        # Initialize ImageKit client
        imagekit = ImageKit(
            private_key=private_key,
            public_key=public_key,
            url_endpoint=url_endpoint
        )
        current_app.logger.debug("ImageKit client initialized successfully.")

        # Generate a unique filename for ImageKit
        original_filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{original_filename}"
        safe_subfolder = secure_filename(subfolder) if subfolder else "default"
        current_app.logger.debug(f"Generated unique filename: {unique_filename} for folder: /{safe_subfolder}/")

        # Read file content for upload
        current_app.logger.debug("Reading file content...")
        file_content = file.read()
        file_size = len(file_content)
        current_app.logger.debug(f"File content read. Size: {file_size} bytes.")
        file.seek(0) # Reset file pointer if needed elsewhere

        # Upload the file to ImageKit - Pass options as direct keyword arguments
        current_app.logger.debug(f"Attempting to upload '{unique_filename}' to ImageKit folder '/{safe_subfolder}/'...")
        upload_response = imagekit.upload(
            file=file_content,
            file_name=unique_filename,
            folder=f"/{safe_subfolder}/",       # Pass folder directly
            is_private_file=False,          # Pass is_private_file directly
            use_unique_file_name=False      # Pass use_unique_file_name directly
        )
        current_app.logger.debug("ImageKit upload call completed.")

        # Log the raw response details
        if upload_response and upload_response.response_metadata:
            current_app.logger.debug(f"ImageKit Response Status Code: {upload_response.response_metadata.http_status_code}")
            current_app.logger.debug(f"ImageKit Response Headers: {upload_response.response_metadata.headers}")
            current_app.logger.debug(f"ImageKit Response Raw Body: {upload_response.response_metadata.raw}")
        else:
            current_app.logger.error("ImageKit response or response_metadata is missing.")

        # Check response and return the URL
        if upload_response.response_metadata.http_status_code == 200 and upload_response.url:
            image_url = upload_response.url
            current_app.logger.info(f"File uploaded successfully to ImageKit: {image_url}")
            return image_url
        else:
            current_app.logger.error(f"ImageKit upload failed. Status: {upload_response.response_metadata.http_status_code}")
            flash("حدث خطأ أثناء رفع الصورة إلى خدمة التخزين. راجع السجلات لمزيد من التفاصيل.", "danger")
            return None

    except Exception as e:
        # Log the exception with traceback
        current_app.logger.error(f"Exception during ImageKit upload process: {e}", exc_info=True)
        flash("حدث خطأ غير متوقع أثناء عملية رفع الصورة. راجع السجلات لمزيد من التفاصيل.", "danger")
        return None

# --- Rest of the file remains the same --- #

@question_bp.route("/")
@login_required
def list_questions():
    # ... (keep existing code) ...
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
        # Pass the original question objects to the template
        rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
        current_app.logger.info("Template rendering successful.")
        return rendered_template
    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash(f"حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger")
        return redirect(url_for("index")) # Redirect to a safe page like index

def get_sorted_lessons():
    # ... (keep existing code) ...
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
    # ... (keep existing code, including call to save_upload) ...
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        # Redirect to curriculum management if no lessons exist
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")

        # Use the updated save_upload function
        q_image_path = save_upload(q_image_file, subfolder="questions")

        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        if correct_option_index_str is None:
            # Check if any options were actually submitted before requiring a correct one
            option_keys_check = [key for key in request.form if key.startswith("option_text_")]
            option_files_check = [key for key in request.files if key.startswith("option_image_")]
            if option_keys_check or option_files_check:
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
        # Determine the highest index submitted to iterate correctly
        max_submitted_index = -1
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            
            # Use the updated save_upload function
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
        # Adjust validation: Check if correct_option_index is valid within the *processed* options
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form data correctly for rendering
            form_data = request.form.to_dict()
            # Reconstruct options with potential image URLs for display
            repop_options = []
            for i in range(max_submitted_index + 1):
                 idx_str = str(i)
                 opt_text = request.form.get(f"option_text_{idx_str}", "")
                 # Find if this option was processed and has an image URL
                 processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                 img_url = processed_opt["image_url"] if processed_opt else None
                 repop_options.append({"option_text": opt_text, "image_url": img_url}) # Add image_url here
            form_data["options_repop"] = repop_options # Use a different key to avoid conflicts
            form_data["correct_option_repop"] = correct_option_index_str # Pass the raw string back
            form_data["question_image_url_repop"] = q_image_path # Pass question image URL
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        # --- Database Operations --- #
        try:
            new_question = Question(
                question_text=question_text if question_text else None,
                lesson_id=lesson_id,
                image_url=q_image_path # URL from ImageKit or None
            )
            db.session.add(new_question)
            # Flush to get the new_question.question_id for options
            db.session.flush()
            current_app.logger.info(f"New question added (pending commit) with ID: {new_question.question_id}")

            for opt_data in options_data_from_form:
                option = Option(
                    option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                    image_url=opt_data["image_url"], # URL from ImageKit or None
                    is_correct=opt_data["is_correct"],
                    question_id=new_question.question_id
                )
                db.session.add(option)
            
            # Commit the transaction
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
        
        # If errors occurred, repopulate form data for rendering
        form_data = request.form.to_dict()
        repop_options = []
        for i in range(max_submitted_index + 1):
             idx_str = str(i)
             opt_text = request.form.get(f"option_text_{idx_str}", "")
             processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
             img_url = processed_opt["image_url"] if processed_opt else None
             repop_options.append({"option_text": opt_text, "image_url": img_url})
        form_data["options_repop"] = repop_options
        form_data["correct_option_repop"] = correct_option_index_str
        form_data["question_image_url_repop"] = q_image_path
        return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

    # GET request
    # Pass an empty dictionary or None for 'question' on GET
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")


@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # ... (keep existing code, including call to save_upload) ...
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
        delete_q_image = request.form.get("delete_question_image") == "1"

        q_image_path = question.image_url # Keep existing image by default
        if delete_q_image:
            # TODO: Implement actual deletion from ImageKit if needed
            current_app.logger.info(f"Request to delete question image for question {question_id}")
            q_image_path = None
        elif q_image_file and q_image_file.filename:
            # Use the updated save_upload function
            new_q_image_path = save_upload(q_image_file, subfolder="questions")
            if new_q_image_path:
                # TODO: Delete old image from ImageKit if needed
                q_image_path = new_q_image_path
            else:
                # Upload failed, keep existing image and flash message handled in save_upload
                pass

        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        if correct_option_index_str is None:
            option_keys_check = [key for key in request.form if key.startswith("option_text_")]
            option_files_check = [key for key in request.files if key.startswith("option_image_")]
            if option_keys_check or option_files_check:
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
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_", "option_id_", "delete_option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            option_id = request.form.get(f"option_id_{index_str}") # Get existing option ID if present
            delete_opt_image = request.form.get(f"delete_option_image_{index_str}") == "1"

            # Find existing option data if ID is provided
            existing_option = None
            if option_id:
                try:
                    existing_option = next((opt for opt in question.options if opt.option_id == int(option_id)), None)
                except ValueError:
                    pass # Invalid option_id format
            
            option_image_path = existing_option.image_url if existing_option else None # Keep existing image

            if delete_opt_image:
                # TODO: Implement actual deletion from ImageKit if needed
                current_app.logger.info(f"Request to delete option image for option ID {option_id} (index {i})")
                option_image_path = None
            elif option_image_file and option_image_file.filename:
                # Use the updated save_upload function
                new_opt_image_path = save_upload(option_image_file, subfolder="options")
                if new_opt_image_path:
                    # TODO: Delete old image from ImageKit if needed
                    option_image_path = new_opt_image_path
                else:
                    # Upload failed, keep existing image
                    pass

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_id": int(option_id) if option_id else None, # Store ID for update/delete
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form data correctly for rendering on error
            form_data = request.form.to_dict()
            # Reconstruct options with potential image URLs for display
            repop_options = []
            for i in range(max_submitted_index + 1):
                 idx_str = str(i)
                 opt_text = request.form.get(f"option_text_{idx_str}", "")
                 opt_id = request.form.get(f"option_id_{idx_str}")
                 # Find if this option was processed and has an image URL
                 processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                 img_url = processed_opt["image_url"] if processed_opt else None
                 repop_options.append({"option_id": opt_id, "option_text": opt_text, "image_url": img_url})
            form_data["options_repop"] = repop_options
            form_data["correct_option_repop"] = correct_option_index_str
            form_data["question_image_url_repop"] = q_image_path
            # Important: Pass the original question object too for IDs etc.
            form_data["question_id"] = question.question_id
            form_data["lesson_id"] = question.lesson_id # Ensure lesson_id is passed back
            form_data["question_text"] = question.question_text # Ensure original text is available
            # We need to pass the structure expected by the template
            # Let's rebuild a structure similar to the original question object
            rebuilt_question_data = {
                "question_id": question.question_id,
                "question_text": request.form.get("text", question.question_text), # Use form value if present
                "image_url": q_image_path,
                "lesson_id": request.form.get("lesson_id", question.lesson_id),
                "options": repop_options, # Use the reconstructed options
                "correct_option": correct_option_index_str # Pass the raw string
            }
            return render_template("question/form.html", title=f"تعديل السؤال #{question_id}", lessons=lessons, question=rebuilt_question_data, submit_text="حفظ التعديلات")

        # --- Database Operations --- #
        try:
            # Update question fields
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = q_image_path

            # Process options: Update existing, add new, delete removed
            existing_option_ids = {opt.option_id for opt in question.options}
            processed_option_ids = set()

            for opt_data in options_data_from_form:
                option_id = opt_data["option_id"]
                if option_id and option_id in existing_option_ids:
                    # Update existing option
                    opt_to_update = next(opt for opt in question.options if opt.option_id == option_id)
                    opt_to_update.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                    opt_to_update.image_url = opt_data["image_url"]
                    opt_to_update.is_correct = opt_data["is_correct"]
                    processed_option_ids.add(option_id)
                else:
                    # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)
                    # We don't have the ID yet, but it will be handled by SQLAlchemy
            
            # Delete options that were removed from the form
            options_to_delete_ids = existing_option_ids - processed_option_ids
            if options_to_delete_ids:
                for opt_id in options_to_delete_ids:
                    opt_to_delete = next(opt for opt in question.options if opt.option_id == opt_id)
                    # TODO: Delete image from ImageKit if needed
                    current_app.logger.info(f"Deleting option ID {opt_id} for question {question_id}")
                    db.session.delete(opt_to_delete)

            # Commit the transaction
            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully. Question {question_id} and options updated.")
            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")

        # If errors occurred, repopulate form data for rendering (similar to error block above)
        form_data = request.form.to_dict()
        repop_options = []
        for i in range(max_submitted_index + 1):
             idx_str = str(i)
             opt_text = request.form.get(f"option_text_{idx_str}", "")
             opt_id = request.form.get(f"option_id_{idx_str}")
             processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
             img_url = processed_opt["image_url"] if processed_opt else None
             repop_options.append({"option_id": opt_id, "option_text": opt_text, "image_url": img_url})
        form_data["options_repop"] = repop_options
        form_data["correct_option_repop"] = correct_option_index_str
        form_data["question_image_url_repop"] = q_image_path
        rebuilt_question_data = {
            "question_id": question.question_id,
            "question_text": request.form.get("text", question.question_text),
            "image_url": q_image_path,
            "lesson_id": request.form.get("lesson_id", question.lesson_id),
            "options": repop_options,
            "correct_option": correct_option_index_str
        }
        return render_template("question/form.html", title=f"تعديل السؤال #{question_id}", lessons=lessons, question=rebuilt_question_data, submit_text="حفظ التعديلات")

    # GET request
    # Prepare data structure similar to what's expected on POST error for consistency
    options_for_template = []
    correct_option_get_index = -1
    for i, opt in enumerate(question.options):
        options_for_template.append({
            "option_id": opt.option_id,
            "option_text": opt.option_text,
            "image_url": opt.image_url
        })
        if opt.is_correct:
            correct_option_get_index = i
    
    question_data_for_template = {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "image_url": question.image_url,
        "lesson_id": question.lesson_id,
        "options": options_for_template,
        "correct_option": str(correct_option_get_index) if correct_option_get_index != -1 else None
    }
    return render_template("question/form.html", title=f"تعديل السؤال #{question_id}", lessons=lessons, question=question_data_for_template, submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    # ... (keep existing code, add ImageKit deletion logic if possible) ...
    current_app.logger.info(f"POST request received for delete_question ID: {question_id}")
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)

    try:
        # TODO: Implement deletion from ImageKit for question image and all option images
        # This might require storing file IDs from ImageKit upon upload
        # For now, we just delete from DB
        if question.image_url:
            current_app.logger.warning(f"ImageKit deletion for question image {question.image_url} not implemented.")
        for opt in question.options:
            if opt.image_url:
                current_app.logger.warning(f"ImageKit deletion for option image {opt.image_url} not implemented.")
            db.session.delete(opt)
        
        db.session.delete(question)
        db.session.commit()
        current_app.logger.info(f"Question {question_id} and its options deleted successfully from DB.")
        flash("تم حذف السؤال بنجاح.", "success")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database Error deleting question {question_id}: {db_error}")
        flash("خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic Error deleting question {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")

    return redirect(url_for("question.list_questions"))

