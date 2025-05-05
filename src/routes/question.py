# src/routes/question.py (Updated with ImageKit.io integration - v5 - Removed faulty decorator)

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

# Import ImageKit and necessary options class
from imagekitio.client import ImageKit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions # Correct import

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

# Removed the faulty @question_bp.before_app_first_request decorator

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)

# --- Updated save_upload function with Correct Options Passing via Class --- #
def save_upload(file, subfolder="questions"):
    # Ensure logger is available and potentially set level if needed (though Render setting should prevail)
    if current_app.logger.level > logging.DEBUG:
         current_app.logger.warning("Logger level is higher than DEBUG, detailed logs might be suppressed.")
         # Optionally force level here if Render setting isn't working, but be cautious
         # current_app.logger.setLevel(logging.DEBUG)

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
    private_key = os.environ.get("IMAGEKIT_PRIVATE_KEY")
    public_key = os.environ.get("IMAGEKIT_PUBLIC_KEY")
    url_endpoint = os.environ.get("IMAGEKIT_URL_ENDPOINT")

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
        imagekit_folder_path = f"/{safe_subfolder}/" # Define folder path
        current_app.logger.debug(f"Generated unique filename: {unique_filename} for folder: {imagekit_folder_path}")

        # Read file content for upload
        current_app.logger.debug("Reading file content...")
        file_content = file.read()
        file_size = len(file_content)
        current_app.logger.debug(f"File content read. Size: {file_size} bytes.")
        file.seek(0) # Reset file pointer if needed elsewhere

        # --- Correctly create and pass UploadFileRequestOptions --- #
        current_app.logger.debug("Creating UploadFileRequestOptions...")
        upload_options = UploadFileRequestOptions(
            folder=imagekit_folder_path,
            is_private_file=False,
            use_unique_file_name=False # We handle unique name generation ourselves
            # Add other options here if needed, e.g., tags=["tag1", "tag2"]
        )
        current_app.logger.debug(f"Upload options created: {upload_options.__dict__}")

        # Upload the file to ImageKit using the options parameter
        current_app.logger.debug(f"Attempting to upload \'{unique_filename}\' to ImageKit...")
        upload_response = imagekit.upload(
            file=file_content,
            file_name=unique_filename,
            options=upload_options # Pass the options object here
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
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        # ***** TEST DEBUG MESSAGE *****
        current_app.logger.debug("*****************************************************")
        current_app.logger.debug("***** ENTERING add_question POST request handler *****")
        current_app.logger.debug("*****************************************************")
        # *****************************

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
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
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
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question={}, submit_text="إضافة سؤال")

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
        delete_q_image = request.form.get("delete_question_image")

        q_image_path = question.image_url # Keep existing image by default
        if delete_q_image:
            current_app.logger.info(f"Request to delete question image for question {question_id}")
            # Attempt to delete from ImageKit (best effort, needs file_id for reliability)
            if q_image_path and q_image_path.startswith("http"):
                # We need the file_id from the URL or stored separately to delete reliably
                # This is a placeholder - proper deletion needs file_id management
                current_app.logger.warning(f"ImageKit deletion skipped for {q_image_path} - file_id needed.")
                # try:
                #     imagekit.delete_file(file_id=...) # Requires file_id
                # except Exception as del_err:
                #     current_app.logger.error(f"Error deleting old ImageKit file: {del_err}")
            q_image_path = None
        elif q_image_file and q_image_file.filename:
            # Upload new image, potentially replacing old one
            new_q_image_path = save_upload(q_image_file, subfolder="questions")
            if new_q_image_path:
                # Attempt to delete old image if replaced (best effort)
                if q_image_path and q_image_path != new_q_image_path and q_image_path.startswith("http"):
                     current_app.logger.warning(f"ImageKit deletion skipped for old image {q_image_path} - file_id needed.")
                q_image_path = new_q_image_path
            else:
                # Upload failed, keep old image path but flash error
                flash("فشل رفع صورة السؤال الجديدة. تم الاحتفاظ بالصورة القديمة إن وجدت.", "warning")

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
        existing_options = {opt.option_id: opt for opt in question.options}
        processed_option_ids = set()

        max_submitted_index = -1
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_", "option_id_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_id_str = request.form.get(f"option_id_{index_str}")
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            delete_option_image = request.form.get(f"delete_option_image_{index_str}")

            option_id = None
            existing_option = None
            if option_id_str:
                try:
                    option_id = int(option_id_str)
                    existing_option = existing_options.get(option_id)
                    processed_option_ids.add(option_id)
                except ValueError:
                    pass # Invalid ID, treat as new option

            option_image_path = existing_option.image_url if existing_option else None

            if delete_option_image:
                current_app.logger.info(f"Request to delete option image for option index {i} (ID: {option_id})")
                if option_image_path and option_image_path.startswith("http"):
                    current_app.logger.warning(f"ImageKit deletion skipped for option image {option_image_path} - file_id needed.")
                option_image_path = None
            elif option_image_file and option_image_file.filename:
                new_opt_image_path = save_upload(option_image_file, subfolder="options")
                if new_opt_image_path:
                    if option_image_path and option_image_path != new_opt_image_path and option_image_path.startswith("http"):
                        current_app.logger.warning(f"ImageKit deletion skipped for old option image {option_image_path} - file_id needed.")
                    option_image_path = new_opt_image_path
                else:
                    flash(f"فشل رفع الصورة الجديدة للخيار رقم {i+1}. تم الاحتفاظ بالصورة القديمة إن وجدت.", "warning")

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_id": option_id, # Keep track of existing options
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
            # We need to pass the original question object structure for the template
            # Merge form_data into a structure resembling the original question object
            display_question = {
                "question_id": question_id,
                "question_text": request.form.get("text", ""),
                "image_url": q_image_path, # Use the potentially updated path
                "lesson_id": request.form.get("lesson_id"),
                "options": repop_options # Use the reconstructed options
            }
            return render_template("question/form.html", title=f"تعديل السؤال رقم {question_id}", lessons=lessons, question=display_question, submit_text="حفظ التعديلات", correct_option_index=correct_option_index_str) # Pass correct_option_index too

        # --- Database Operations --- #
        try:
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = q_image_path

            # Update existing options and add new ones
            updated_option_ids = set()
            for opt_data in options_data_from_form:
                option_id = opt_data["option_id"]
                if option_id and option_id in existing_options:
                    # Update existing option
                    option = existing_options[option_id]
                    option.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                    option.image_url = opt_data["image_url"]
                    option.is_correct = opt_data["is_correct"]
                    updated_option_ids.add(option_id)
                    current_app.logger.debug(f"Updating existing option ID: {option_id}")
                else:
                    # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question_id
                    )
                    db.session.add(new_option)
                    current_app.logger.debug(f"Adding new option for question ID: {question_id}")
            
            # Delete options that were removed from the form
            options_to_delete = [opt for opt_id, opt in existing_options.items() if opt_id not in updated_option_ids and opt_id in processed_option_ids]
            for opt in options_to_delete:
                current_app.logger.info(f"Deleting option ID: {opt.option_id} for question ID: {question_id}")
                # Attempt to delete image from ImageKit (best effort)
                if opt.image_url and opt.image_url.startswith("http"):
                    current_app.logger.warning(f"ImageKit deletion skipped for deleted option image {opt.image_url} - file_id needed.")
                db.session.delete(opt)

            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully. Question {question_id} updated.")
            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error updating question {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error updating question {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")

        # If errors occurred, repopulate form data for rendering
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
        display_question = {
            "question_id": question_id,
            "question_text": request.form.get("text", ""),
            "image_url": q_image_path,
            "lesson_id": request.form.get("lesson_id"),
            "options": repop_options
        }
        return render_template("question/form.html", title=f"تعديل السؤال رقم {question_id}", lessons=lessons, question=display_question, submit_text="حفظ التعديلات", correct_option_index=correct_option_index_str)

    # GET request
    # Prepare data for the template, ensuring options have image_url
    question_data = {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "image_url": question.image_url,
        "lesson_id": question.lesson_id,
        "options": [
            {
                "option_id": opt.option_id,
                "option_text": opt.option_text,
                "image_url": opt.image_url,
                "is_correct": opt.is_correct
            } for opt in sorted(question.options, key=lambda o: o.option_id) # Ensure consistent order
        ]
    }
    # Find the index of the correct option for the template
    correct_option_index = -1
    for i, opt in enumerate(sorted(question.options, key=lambda o: o.option_id)):
        if opt.is_correct:
            correct_option_index = i
            break
    
    current_app.logger.debug(f"Rendering edit form for question {question_id} with data: {question_data}")
    return render_template("question/form.html", title=f"تعديل السؤال رقم {question_id}", lessons=lessons, question=question_data, submit_text="حفظ التعديلات", correct_option_index=str(correct_option_index))

@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    current_app.logger.info(f"Received request to delete question ID: {question_id}")
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    
    # --- Attempt to delete images from ImageKit (Best Effort) --- #
    # Initialize ImageKit client if needed (consider initializing once per app context)
    private_key = os.environ.get("IMAGEKIT_PRIVATE_KEY")
    public_key = os.environ.get("IMAGEKIT_PUBLIC_KEY")
    url_endpoint = os.environ.get("IMAGEKIT_URL_ENDPOINT")
    imagekit = None
    if all([private_key, public_key, url_endpoint]):
        try:
            imagekit = ImageKit(private_key=private_key, public_key=public_key, url_endpoint=url_endpoint)
        except Exception as init_err:
            current_app.logger.error(f"Failed to initialize ImageKit for deletion: {init_err}")

    def delete_imagekit_file_by_url(url):
        if not imagekit or not url or not url.startswith(url_endpoint):
            return
        # Basic attempt to extract file_id or path - THIS IS UNRELIABLE
        # A robust solution requires storing file_id during upload.
        try:
            # This part is highly dependent on your URL structure and might not work
            path_part = url.replace(url_endpoint, "").lstrip("/")
            # ImageKit Python SDK delete_file needs file_id, not path.
            # We cannot reliably get file_id from URL alone.
            current_app.logger.warning(f"Cannot delete ImageKit file by URL ({url}). File ID is required.")
            # If you stored file_id during upload, use it here:
            # file_id_to_delete = get_file_id_from_storage(url) 
            # if file_id_to_delete:
            #     imagekit.delete_file(file_id=file_id_to_delete)
            #     current_app.logger.info(f"Attempted deletion of ImageKit file ID associated with URL: {url}")
        except Exception as del_err:
            current_app.logger.error(f"Error attempting to delete ImageKit file for URL {url}: {del_err}")

    # Delete question image
    if question.image_url:
        delete_imagekit_file_by_url(question.image_url)

    # Delete option images
    for option in question.options:
        if option.image_url:
            delete_imagekit_file_by_url(option.image_url)
    # ------------------------------------------------------------ #

    try:
        # Deleting the question will cascade delete options due to relationship settings
        db.session.delete(question)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted question ID: {question_id} and associated options from DB.")
        flash("تم حذف السؤال بنجاح!", "success")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database Error deleting question {question_id}: {db_error}")
        flash("خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic Error deleting question {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")

    return redirect(url_for("question.list_questions"))

