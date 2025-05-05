# src/routes/question.py (Cloudinary integration added)

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

# Import Cloudinary libraries
import cloudinary
import cloudinary.uploader
import cloudinary.api

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
            print("Error: Database object \'db\' could not be imported.")
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

# --- Cloudinary Configuration Check --- #
# Cloudinary configuration is usually done once at app startup using CLOUDINARY_URL env var
# or individual keys (CLOUD_NAME, API_KEY, API_SECRET). We check if they exist here.
def check_cloudinary_config():
    if not os.environ.get("CLOUDINARY_URL") and not (
        os.environ.get("CLOUDINARY_CLOUD_NAME") and
        os.environ.get("CLOUDINARY_API_KEY") and
        os.environ.get("CLOUDINARY_API_SECRET")
    ):
        current_app.logger.error("Cloudinary environment variables (CLOUDINARY_URL or CLOUD_NAME/API_KEY/API_SECRET) are missing.")
        return False
    # The cloudinary library automatically picks up the env vars, no need to call config explicitly here
    # unless we want to override or handle it differently.
    current_app.logger.debug("Cloudinary environment variables seem to be present.")
    return True

# --- save_upload function (Implemented with Cloudinary) --- #
def save_upload(file, subfolder="default"):
    if current_app.logger.level > logging.DEBUG:
         current_app.logger.warning("Logger level is higher than DEBUG, detailed logs might be suppressed.")

    current_app.logger.debug(f"Entering save_upload for subfolder: {subfolder}")
    if not file or not file.filename:
        current_app.logger.debug("No file or filename provided to save_upload.")
        return None # Return None for URL

    current_app.logger.debug(f"Processing file: {file.filename}")

    if not allowed_file(file.filename):
        current_app.logger.warning(f"File type not allowed: {file.filename}")
        return None # Return None for URL
    
    current_app.logger.debug(f"File type allowed for: {file.filename}")

    # Check Cloudinary config
    if not check_cloudinary_config():
        flash("خطأ في إعدادات رفع الصور على الخادم (Cloudinary). يرجى مراجعة متغيرات البيئة.", "danger")
        return None # Return None for URL

    # Generate a unique public_id for Cloudinary (without extension)
    original_filename = secure_filename(file.filename)
    # Keep extension for potential use, but Cloudinary uses public_id
    filename_base, file_extension = os.path.splitext(original_filename)
    unique_public_id = f"{subfolder}/{int(time.time())}_{uuid.uuid4().hex[:8]}_{filename_base}"
    current_app.logger.debug(f"Generated unique public_id for Cloudinary: {unique_public_id}")

    try:
        current_app.logger.debug(f"Attempting to upload to Cloudinary with public_id: {unique_public_id}...")
        # Upload to Cloudinary
        # The library reads config from env vars automatically
        upload_result = cloudinary.uploader.upload(
            file.stream, # Pass the file stream
            public_id=unique_public_id,
            folder=subfolder, # Optional: Can also be controlled via public_id path
            resource_type="auto" # Detect if it's image/video etc.
        )
        current_app.logger.debug("Cloudinary upload call completed.")

        # Log the result (be careful about sensitive info if any)
        # The result is a dictionary
        current_app.logger.debug(f"Cloudinary Upload Result: {upload_result}")

        # Check for success and return the secure URL
        if upload_result and upload_result.get("secure_url"):
            image_url = upload_result["secure_url"]
            public_id = upload_result.get("public_id") # Get the public_id for potential deletion
            current_app.logger.info(f"File uploaded successfully to Cloudinary: {image_url} (Public ID: {public_id})")
            # IMPORTANT: For deletion, you NEED the public_id. 
            # Currently, we only return the URL. Consider modifying the DB model 
            # to store public_id alongside image_url for reliable deletion.
            return image_url # Return only the URL for now
        else:
            current_app.logger.error(f"Cloudinary upload failed. Result: {upload_result}")
            flash("حدث خطأ أثناء رفع الصورة إلى Cloudinary. راجع السجلات لمزيد من التفاصيل.", "danger")
            return None # Return None for URL

    except Exception as e:
        current_app.logger.error(f"Exception during Cloudinary upload process: {e}", exc_info=True)
        flash("حدث خطأ غير متوقع أثناء عملية رفع الصورة إلى Cloudinary. راجع السجلات لمزيد من التفاصيل.", "danger")
        return None # Return None for URL

# --- Function to delete Cloudinary file by Public ID (Requires Public ID to be stored) --- #
def delete_cloudinary_file(public_id):
    if not public_id:
        current_app.logger.warning("Attempted to delete Cloudinary file with no public_id.")
        return False
    
    if not check_cloudinary_config():
        current_app.logger.error("Cannot delete Cloudinary file, config is missing.")
        return False
        
    current_app.logger.info(f"Attempting to delete Cloudinary file with public_id: {public_id}")
    try:
        # Deletion requires the public_id
        delete_result = cloudinary.uploader.destroy(public_id)
        current_app.logger.debug(f"Cloudinary delete result for {public_id}: {delete_result}")
        if delete_result.get("result") == "ok" or delete_result.get("result") == "not found":
            current_app.logger.info(f"Cloudinary file deletion successful or file not found for public_id: {public_id}")
            return True
        else:
            current_app.logger.error(f"Cloudinary file deletion failed for public_id: {public_id}. Result: {delete_result}")
            return False
    except Exception as e:
        current_app.logger.error(f"Exception during Cloudinary deletion for public_id {public_id}: {e}", exc_info=True)
        return False

# --- Helper to extract Public ID from URL (Basic - Might need refinement) --- #
# This is a basic attempt and might fail for complex URL structures or transformations.
# Storing public_id directly is the robust way.
def extract_public_id_from_url(url):
    if not url or not isinstance(url, str):
        return None
    try:
        # Assuming standard Cloudinary URL structure: .../upload/v<version>/<public_id>.<format>
        parts = url.split("/")
        # Find the version part (like v1234567890)
        version_index = -1
        for i, part in enumerate(parts):
            if part.startswith("v") and part[1:].isdigit():
                version_index = i
                break
        
        if version_index != -1 and version_index + 1 < len(parts):
            # Get the part after the version, remove extension
            filename_part = parts[version_index + 1]
            public_id, _ = os.path.splitext(filename_part)
            # Reconstruct potential folder structure if present before version
            folder_parts = parts[parts.index("upload") + 1 : version_index]
            if folder_parts:
                public_id = "/".join(folder_parts) + "/" + public_id
            return public_id
    except Exception as e:
        current_app.logger.error(f"Error extracting public_id from URL {url}: {e}")
    current_app.logger.warning(f"Could not reliably extract public_id from URL: {url}")
    return None

# --- Routes --- #

@question_bp.route("/")
@login_required
def list_questions():
    # ... (same as before) ...
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
        try:
            return redirect(url_for("main.index")) 
        except:
             return redirect(url_for("auth.login"))

def get_sorted_lessons():
    # ... (same as before) ...
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
    # ... (logic mostly same, uses new save_upload) ...
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        try:
            return redirect(url_for("curriculum.list_courses"))
        except:
            return redirect(url_for("main.index"))

    if request.method == "POST":
        current_app.logger.debug("***** ENTERING add_question POST request handler *****")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")

        # Call the NEW save_upload function (returns URL or None)
        q_image_path = save_upload(q_image_file, subfolder="questions")

        error_messages = []
        # ... (validation logic remains largely the same) ...
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
        # ... (logic to find max index remains same) ...
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
            
            # Call the NEW save_upload function
            option_image_path = save_upload(option_image_file, subfolder="options")

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_text": option_text,
                    "image_url": option_image_path, # Will be URL or None
                    "is_correct": is_correct
                })
        # ... (validation logic remains largely the same) ...
        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            # ... (error handling and form repopulation remains same) ...
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
            # ... (DB insertion logic remains same, uses image_url which is now URL or None) ...
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
            # ... (error handling remains same) ...
            db.session.rollback()
            current_app.logger.exception(f"Database Error adding question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء إضافة السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال.", "danger")
        
        # ... (repopulate form on error remains same) ...
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
    # ... (logic mostly same, uses new save_upload and placeholder deletion) ...
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
        old_q_public_id = extract_public_id_from_url(q_image_path) if q_image_path else None

        if delete_q_image:
            current_app.logger.info(f"Request to delete question image for question {question_id}")
            if old_q_public_id:
                delete_cloudinary_file(old_q_public_id)
            else:
                 current_app.logger.warning(f"Could not delete question image for QID {question_id}, public_id unknown for URL: {q_image_path}")
            q_image_path = None
        elif q_image_file and q_image_file.filename:
            new_q_image_path = save_upload(q_image_file, subfolder="questions")
            if new_q_image_path:
                # Delete old image if upload successful and path changed
                if old_q_public_id and q_image_path != new_q_image_path:
                     delete_cloudinary_file(old_q_public_id)
                q_image_path = new_q_image_path
            else:
                flash("فشل رفع صورة السؤال الجديدة. تم الاحتفاظ بالصورة القديمة إن وجدت.", "warning")

        error_messages = []
        # ... (validation logic remains largely the same) ...
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو صورة له.")
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
        options_to_delete_later = [] # Store options marked for deletion

        max_submitted_index = -1
        # ... (logic to find max index remains same) ...
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
                    pass

            option_image_path = existing_option.image_url if existing_option else None
            old_opt_public_id = extract_public_id_from_url(option_image_path) if option_image_path else None

            if delete_option_image:
                current_app.logger.info(f"Request to delete option image for option index {i} (ID: {option_id})")
                if old_opt_public_id:
                    # Defer actual deletion until after DB commit success
                    options_to_delete_later.append(old_opt_public_id)
                else:
                    current_app.logger.warning(f"Could not delete option image for OptID {option_id}, public_id unknown for URL: {option_image_path}")
                option_image_path = None
            elif option_image_file and option_image_file.filename:
                new_opt_image_path = save_upload(option_image_file, subfolder="options")
                if new_opt_image_path:
                    if old_opt_public_id and option_image_path != new_opt_image_path:
                        # Defer actual deletion until after DB commit success
                        options_to_delete_later.append(old_opt_public_id)
                    option_image_path = new_opt_image_path
                else:
                    flash(f"فشل رفع الصورة الجديدة للخيار رقم {i+1}. تم الاحتفاظ بالصورة القديمة إن وجدت.", "warning")

            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_id": option_id,
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })
        # ... (validation logic remains largely the same) ...
        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            # ... (error handling and form repopulation remains same) ...
            for error in error_messages:
                flash(error, "danger")
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

        # --- Database Operations --- #
        try:
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = q_image_path

            updated_option_ids = set()
            options_to_delete_from_db = []
            public_ids_to_delete_on_success = list(options_to_delete_later) # Copy deferred deletions

            for opt_data in options_data_from_form:
                option_id = opt_data["option_id"]
                if option_id and option_id in existing_options:
                    option = existing_options[option_id]
                    option.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                    option.image_url = opt_data["image_url"]
                    option.is_correct = opt_data["is_correct"]
                    updated_option_ids.add(option_id)
                    current_app.logger.debug(f"Updating existing option ID: {option_id}")
                else:
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question_id
                    )
                    db.session.add(new_option)
                    current_app.logger.debug(f"Adding new option for question ID: {question_id}")
            
            # Find options in DB that were submitted but are no longer valid (removed from form)
            for opt_id, opt in existing_options.items():
                if opt_id not in updated_option_ids and opt_id in processed_option_ids:
                    options_to_delete_from_db.append(opt)
            
            for opt in options_to_delete_from_db:
                current_app.logger.info(f"Deleting option ID: {opt.option_id} from DB for question ID: {question_id}")
                if opt.image_url:
                    opt_public_id = extract_public_id_from_url(opt.image_url)
                    if opt_public_id:
                        public_ids_to_delete_on_success.append(opt_public_id)
                    else:
                         current_app.logger.warning(f"Could not get public_id for deleted option {opt.option_id} URL: {opt.image_url}")
                db.session.delete(opt)

            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully. Question {question_id} updated.")

            # Now, delete Cloudinary files for options marked/deleted if DB commit was successful
            for public_id in set(public_ids_to_delete_on_success): # Use set to avoid duplicates
                delete_cloudinary_file(public_id)

            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            # ... (error handling remains same) ...
            db.session.rollback()
            current_app.logger.exception(f"Database Error updating question {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error updating question {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")

        # ... (repopulate form on error remains same) ...
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
    # ... (GET request logic remains same) ...
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
            } for opt in sorted(question.options, key=lambda o: o.option_id)
        ]
    }
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
    
    public_ids_to_delete_on_success = []

    # Get public_id for question image
    if question.image_url:
        q_public_id = extract_public_id_from_url(question.image_url)
        if q_public_id:
            public_ids_to_delete_on_success.append(q_public_id)
        else:
            current_app.logger.warning(f"Could not get public_id for deleted question {question_id} URL: {question.image_url}")

    # Get public_ids for option images
    for option in question.options:
        if option.image_url:
            opt_public_id = extract_public_id_from_url(option.image_url)
            if opt_public_id:
                public_ids_to_delete_on_success.append(opt_public_id)
            else:
                current_app.logger.warning(f"Could not get public_id for deleted option {option.option_id} URL: {option.image_url}")

    try:
        db.session.delete(question) # Deletes question and cascades to options due to relationship settings
        db.session.commit()
        current_app.logger.info(f"Successfully deleted question ID: {question_id} and associated options from DB.")

        # Now, delete Cloudinary files if DB commit was successful
        for public_id in set(public_ids_to_delete_on_success):
            delete_cloudinary_file(public_id)

        flash("تم حذف السؤال بنجاح!", "success")
    except (IntegrityError, DBAPIError) as db_error:
        # ... (error handling remains same) ...
        db.session.rollback()
        current_app.logger.exception(f"Database Error deleting question {question_id}: {db_error}")
        flash("خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic Error deleting question {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")

    return redirect(url_for("question.list_questions"))

