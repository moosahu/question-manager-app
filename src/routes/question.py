# src/routes/question.py (Updated with ImageKit.io integration and Detailed Logging)

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

# --- Updated save_upload function with Detailed Logging --- #
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

        # Upload the file to ImageKit
        current_app.logger.debug(f"Attempting to upload '{unique_filename}' to ImageKit folder '/{safe_subfolder}/'...")
        upload_response = imagekit.upload(
            file=file_content,
            file_name=unique_filename,
            options={
                "folder": f"/{safe_subfolder}/", # Specify the folder in ImageKit
                "is_private_file": False, # Make files public by default
                "use_unique_file_name": False # We are generating a unique name
            }
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
    # ... (keep existing code, including calls to save_upload) ...
    # Eager load options when fetching the question
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

        # Use the updated save_upload function
        new_q_image_path = save_upload(q_image_file, subfolder="questions")
        final_q_image_path = question.image_url # Start with the existing URL

        if new_q_image_path:
            # TODO: Delete old image from ImageKit if question.image_url exists?
            final_q_image_path = new_q_image_path
        elif remove_question_image:
            # TODO: Delete old image from ImageKit if question.image_url exists?
            final_q_image_path = None

        error_messages = []
        if not question_text and not final_q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        if correct_option_index_str is None:
            # Check if any options were actually submitted before requiring a correct one
            option_keys_check = [key for key in request.form if key.startswith("option_text_")]
            option_files_check = [key for key in request.files if key.startswith("option_image_")]
            existing_options_check = any(opt.option_text or opt.image_url for opt in question.options)
            if option_keys_check or option_files_check or existing_options_check:
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
            if key.startswith(("option_text_", "option_image_", "existing_option_id_", "remove_option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue
        
        options_to_delete = []
        options_to_update = {}
        options_to_add = []

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            existing_option_id = request.form.get(f"existing_option_id_{index_str}")
            remove_option_image = request.form.get(f"remove_option_image_{index_str}") == 'on'

            new_option_image_path = save_upload(option_image_file, subfolder="options")
            final_option_image_path = None
            existing_option = None

            if existing_option_id:
                try:
                    existing_option = next((opt for opt in question.options if str(opt.option_id) == existing_option_id), None)
                    if existing_option:
                        final_option_image_path = existing_option.image_url # Start with existing
                except Exception as e:
                     current_app.logger.error(f"Error finding existing option {existing_option_id}: {e}")

            if new_option_image_path:
                # TODO: Delete old image from ImageKit if existing_option and existing_option.image_url?
                final_option_image_path = new_option_image_path
            elif remove_option_image and existing_option:
                # TODO: Delete old image from ImageKit if existing_option.image_url?
                final_option_image_path = None

            # Determine if the option is valid (has text or image)
            is_valid_option = bool(option_text or final_option_image_path)
            is_correct = (i == correct_option_index)

            if existing_option:
                if is_valid_option:
                    # Update existing option
                    options_to_update[existing_option_id] = {
                        "option_text": option_text if option_text else None,
                        "image_url": final_option_image_path,
                        "is_correct": is_correct
                    }
                else:
                    # Mark existing option for deletion if it becomes invalid
                    options_to_delete.append(existing_option_id)
            elif is_valid_option:
                # Add new option
                options_to_add.append({
                    "option_text": option_text if option_text else None,
                    "image_url": final_option_image_path,
                    "is_correct": is_correct
                })
        
        # Calculate final number of options after updates/additions/deletions
        final_option_count = len(question.options) - len(options_to_delete) + len(options_to_add)
        if final_option_count < 2:
             error_messages.append("يجب أن يحتوي السؤال على خيارين صالحين على الأقل بعد التعديل.")
        # Adjust validation: Check if correct_option_index is valid within the *final* options
        # This check is complex because indices change. Simpler to check if *any* option is marked correct.
        is_any_option_correct = any(opt["is_correct"] for opt in options_to_update.values()) or \
                                any(opt["is_correct"] for opt in options_to_add)
        if correct_option_index_str is not None and not is_any_option_correct:
             error_messages.append("يجب تحديد إجابة صحيحة من بين الخيارات المتاحة.")


        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form data - This is complex, might be simpler to just show existing data again
            # For simplicity, we'll just re-render with the original question data on error
            return render_template("question/form.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        # --- Database Operations --- #
        try:
            # Update question fields
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_path
            current_app.logger.info(f"Updating question ID: {question_id}")

            # Process deletions
            for opt_id_to_delete in options_to_delete:
                opt_to_del = Option.query.get(opt_id_to_delete)
                if opt_to_del and opt_to_del.question_id == question.question_id: # Ensure it belongs to this question
                    # TODO: Delete image from ImageKit if opt_to_del.image_url?
                    db.session.delete(opt_to_del)
                    current_app.logger.info(f"Marked option ID {opt_id_to_delete} for deletion.")

            # Process updates
            for opt_id_to_update, update_data in options_to_update.items():
                opt_to_upd = Option.query.get(opt_id_to_update)
                if opt_to_upd and opt_to_upd.question_id == question.question_id:
                    opt_to_upd.option_text = update_data["option_text"]
                    opt_to_upd.image_url = update_data["image_url"]
                    opt_to_upd.is_correct = update_data["is_correct"]
                    current_app.logger.info(f"Marked option ID {opt_id_to_update} for update.")

            # Process additions
            for new_opt_data in options_to_add:
                new_option = Option(
                    option_text=new_opt_data["option_text"],
                    image_url=new_opt_data["image_url"],
                    is_correct=new_opt_data["is_correct"],
                    question_id=question.question_id
                )
                db.session.add(new_option)
                current_app.logger.info(f"Marked new option for addition: Text='{new_opt_data['option_text'][:20]}...', Image='{bool(new_opt_data['image_url'])}', Correct={new_opt_data['is_correct']}")

            # Commit the transaction
            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully for question ID: {question_id}.")
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

        # If errors occurred, re-render with original data
        # Fetch fresh data in case rollback occurred
        question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
        return render_template("question/form.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    return render_template("question/form.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    try:
        # TODO: Delete images from ImageKit for the question and all its options before deleting from DB
        # for option in question.options:
        #     if option.image_url:
        #         # Call ImageKit delete function
        #         pass
        # if question.image_url:
        #     # Call ImageKit delete function
        #     pass
        
        # Delete options first due to foreign key constraint
        Option.query.filter_by(question_id=question.question_id).delete()
        # Then delete the question
        db.session.delete(question)
        db.session.commit()
        flash(f"تم حذف السؤال #{question_id} وجميع خياراته بنجاح.", "success")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database error deleting question {question_id}: {db_error}")
        flash("خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Generic error deleting question {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")
    return redirect(url_for("question.list_questions"))

