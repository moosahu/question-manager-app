# src/routes/question.py (Modified for Cloudinary, Import & Template Download)
# MODIFIED TO SUPPORT CASCADING DROPDOWNS FOR COURSE/UNIT/LESSON

import os
import logging
import time
import uuid
import io # Added for reading/writing file in memory
import pandas as pd # Added for reading Excel/CSV
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app,
    send_file # Added for sending generated files
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

# Import Cloudinary
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
            print("Error: Database object 'db' could not be imported.")
            raise

try:
    from src.models.question import Question, Option
    from src.models.curriculum import Lesson, Unit, Course # Course is now needed directly
except ImportError:
    try:
        from models.question import Question, Option
        from models.curriculum import Lesson, Unit, Course
    except ImportError:
        print("Error: Could not import models.")
        raise

question_bp = Blueprint("question", __name__, template_folder="../templates/question")

# Allowed extensions for image uploads
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
# Allowed extensions for question import files
ALLOWED_IMPORT_EXTENSIONS = {"xlsx", "csv"}

# Define expected columns for import template (used in import and download)
EXPECTED_IMPORT_COLUMNS = [
    "Question Text", "Question Image URL",
    "Option 1 Text", "Option 1 Image URL",
    "Option 2 Text", "Option 2 Image URL",
    "Option 3 Text", "Option 3 Image URL",
    "Option 4 Text", "Option 4 Image URL",
    "Correct Option Number"
]

def allowed_image_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS)

def allowed_import_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in ALLOWED_IMPORT_EXTENSIONS)

# --- save_upload function (Modified for Cloudinary) --- #
def save_upload(file, subfolder="questions"):
    current_app.logger.debug(f"Entering save_upload for Cloudinary, subfolder: {subfolder}")
    if not file or not file.filename:
        current_app.logger.debug("No file or filename provided to save_upload.")
        return None

    current_app.logger.debug(f"Processing file: {file.filename}")

    if not allowed_image_file(file.filename):
        current_app.logger.warning(f"Image file type not allowed: {file.filename}")
        return None
    
    current_app.logger.debug(f"Image file type allowed for: {file.filename}")

    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
         current_app.logger.error("Cloudinary environment variables (CLOUD_NAME, API_KEY, API_SECRET) are missing or incomplete.")
         if os.environ.get("CLOUDINARY_URL"):
             current_app.logger.info("Attempting to configure Cloudinary from CLOUDINARY_URL.")
             try:
                 cloudinary.config()
                 current_app.logger.info("Cloudinary configured from URL.")
             except Exception as config_err:
                 current_app.logger.error(f"Failed to configure Cloudinary from URL: {config_err}")
                 return None
         else:
             current_app.logger.error("CLOUDINARY_URL is also missing.")
             return None
    else:
        try:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            current_app.logger.debug("Cloudinary configured from individual variables.")
        except Exception as config_err:
            current_app.logger.error(f"Failed to configure Cloudinary from individual variables: {config_err}")
            return None

    try:
        original_filename = secure_filename(file.filename)
        public_id = f"{subfolder}/{int(time.time())}_{uuid.uuid4().hex[:8]}_{os.path.splitext(original_filename)[0]}"
        current_app.logger.debug(f"Generated Cloudinary public_id: {public_id}")
        file.seek(0)
        upload_result = cloudinary.uploader.upload(
            file.stream, 
            public_id=public_id,
            folder=subfolder, 
            resource_type="auto"
        )
        current_app.logger.debug("Cloudinary upload call completed.")

        if upload_result and upload_result.get("secure_url"):
            image_url = upload_result["secure_url"]
            current_app.logger.info(f"File uploaded successfully to Cloudinary: {image_url}")
            return image_url
        else:
            error_message = upload_result.get("error", {}).get("message", "Unknown error") if upload_result else "No response"
            current_app.logger.error(f"Cloudinary upload failed: {error_message}")
            current_app.logger.debug(f"Cloudinary upload response: {upload_result}")
            return None

    except Exception as e:
        current_app.logger.error(f"Exception during Cloudinary upload process: {e}", exc_info=True)
        return None

# --- list_questions route (keep as is) --- #
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
        flash("حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger")
        return redirect(url_for("index"))

# --- Helper function to get all courses, ordered by name --- #
def get_all_courses_sorted():
    try:
        courses = Course.query.order_by(Course.name).all()
        return courses
    except Exception as e:
        current_app.logger.exception("Error fetching all courses.")
        return []

# --- add_question route (Modified to pass courses) --- #
@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    # courses = get_all_courses_sorted() # Pass courses for the first dropdown
    # if not courses:
    #     flash("حدث خطأ أثناء تحميل قائمة الدورات أو لا توجد دورات متاحة. الرجاء إضافة المناهج أولاً.", "warning")
    #     return redirect(url_for("curriculum.list_courses"))
    # The courses will be fetched by JS from API, so no need to pass them here initially for an empty form.
    # However, for consistency and if there's a desire to show the first dropdown populated on load, we can pass them.
    # For now, we will rely on JS to populate the first dropdown as well for a cleaner approach.

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id") # This will be the final selected lesson_id
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")

        q_image_path = None
        if q_image_file and q_image_file.filename:
             if not allowed_image_file(q_image_file.filename):
                 flash("نوع ملف صورة السؤال غير مسموح به.", "danger")
             else:
                 q_image_path = save_upload(q_image_file, subfolder="questions")
                 if q_image_path is None:
                     flash("فشل رفع صورة السؤال. تحقق من إعدادات Cloudinary والسجلات.", "danger")

        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس (من خلال تحديد الدورة ثم الوحدة ثم الدرس).")
        
        option_keys_check = [key for key in request.form if key.startswith("option_text_")]
        option_files_check = [key for key in request.files if key.startswith("option_image_")]
        if (option_keys_check or option_files_check) and correct_option_index_str is None:
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
            option_image_path = None

            if option_image_file and option_image_file.filename:
                if not allowed_image_file(option_image_file.filename):
                    error_messages.append(f"نوع ملف صورة الخيار رقم {i+1} غير مسموح به.")
                else:
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    if option_image_path is None:
                        error_messages.append(f"فشل رفع صورة الخيار رقم {i+1}. تحقق من إعدادات Cloudinary والسجلات.")

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
            # Pass courses again for repopulation in case of error, or rely on JS to fetch
            # For simplicity with JS fetching, we might not need to pass 'courses' here on POST error.
            # The JS should ideally handle repopulating dropdowns based on selected values if they exist in form_data.
            return render_template("question/form.html", title="إضافة سؤال جديد", question=form_data, submit_text="إضافة سؤال")

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
                option_text_to_save = opt_data["option_text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"]
                elif not option_text_to_save:
                    option_text_to_save = None

                option = Option(
                    option_text=option_text_to_save,
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
            flash("خطأ في قاعدة البيانات أثناء إضافة السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question: {e}")
            flash("حدث خطأ غير متوقع أثناء إضافة السؤال.", "danger")
        
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
        return render_template("question/form.html", title="إضافة سؤال جديد", question=form_data, submit_text="إضافة سؤال")

    # For GET request, we don't need to pass 'lessons' or 'courses' if JS handles all dropdown population.
    # The 'question' object will be None for a new question.
    return render_template("question/form.html", title="إضافة سؤال جديد", question=None, submit_text="إضافة سؤال")

# --- edit_question route (Uses modified save_upload, passes courses) --- #
@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    question = Question.query.options(
        joinedload(Question.options),
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course) # Eager load for pre-selection data
    ).get_or_404(question_id)

    # courses = get_all_courses_sorted() # Pass courses for the first dropdown
    # if not courses:
    #     flash("حدث خطأ أثناء تحميل قائمة الدورات أو لا توجد دورات متاحة.", "warning")
    #     return redirect(url_for("question.list_questions"))
    # Again, relying on JS to fetch courses. The 'question' object contains necessary IDs for JS to pre-select.

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")
        question.question_text = request.form.get("text", "").strip()
        new_lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        delete_q_image = request.form.get("delete_question_image") == "1"

        if new_lesson_id:
            question.lesson_id = new_lesson_id
        else:
            flash("يجب اختيار درس (من خلال تحديد الدورة ثم الوحدة ثم الدرس).", "danger")
            # Repopulate with existing question data for the form
            return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

        if delete_q_image and question.image_url:
            # Add logic to delete from Cloudinary if needed, then clear DB field
            # For now, just clearing DB field. Proper Cloudinary deletion requires public_id.
            # Assuming image_url from Cloudinary is the full URL.
            # If you store public_id, use cloudinary.uploader.destroy(public_id)
            current_app.logger.info(f"Deleting question image: {question.image_url}")
            question.image_url = None 

        if q_image_file and q_image_file.filename:
            if not allowed_image_file(q_image_file.filename):
                flash("نوع ملف صورة السؤال غير مسموح به.", "danger")
            else:
                new_q_image_path = save_upload(q_image_file, subfolder="questions")
                if new_q_image_path:
                    # Delete old image from Cloudinary if it exists and a new one is uploaded
                    question.image_url = new_q_image_path
                else:
                    flash("فشل رفع صورة السؤال الجديدة. تحقق من إعدادات Cloudinary والسجلات.", "danger")
        
        if not question.question_text and not question.image_url:
            flash("يجب توفير نص للسؤال أو رفع صورة له.", "danger")
            return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

        # Process options
        options_from_form = []
        max_submitted_index = -1
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_", "option_id_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue
        
        correct_option_new_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_new_index = int(correct_option_index_str)
            except ValueError:
                flash("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.", "danger")
                return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

        # Store existing option IDs to find deleted ones
        existing_option_ids_in_db = {opt.option_id for opt in question.options}
        processed_option_ids_from_form = set()

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_id_str = request.form.get(f"option_id_{index_str}")
            option_id = int(option_id_str) if option_id_str else None
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            delete_opt_image = request.form.get(f"delete_option_image_{index_str}") == "1"
            is_correct = (i == correct_option_new_index)

            current_option_in_db = None
            if option_id:
                current_option_in_db = next((opt for opt in question.options if opt.option_id == option_id), None)
                processed_option_ids_from_form.add(option_id)

            opt_image_path = current_option_in_db.image_url if current_option_in_db else None

            if delete_opt_image and current_option_in_db and current_option_in_db.image_url:
                # Add logic to delete from Cloudinary
                current_app.logger.info(f"Deleting option image: {current_option_in_db.image_url}")
                opt_image_path = None 
            
            if option_image_file and option_image_file.filename:
                if not allowed_image_file(option_image_file.filename):
                    flash(f"نوع ملف صورة الخيار رقم {i+1} غير مسموح به.", "danger")
                    # Continue to process other fields but this image won't be saved
                else:
                    new_opt_image_path = save_upload(option_image_file, subfolder="options")
                    if new_opt_image_path:
                        # Delete old image from Cloudinary if it exists and a new one is uploaded
                        opt_image_path = new_opt_image_path
                    else:
                        flash(f"فشل رفع صورة الخيار رقم {i+1} الجديدة. تحقق من إعدادات Cloudinary والسجلات.", "danger")
            
            if option_text or opt_image_path: # Only add/update if there's content
                options_from_form.append({
                    "id": option_id,
                    "text": option_text,
                    "image_url": opt_image_path,
                    "is_correct": is_correct,
                    "original_db_object": current_option_in_db
                })
        
        if len(options_from_form) < 2:
            flash("يجب توفير خيارين صالحين على الأقل (بنص أو صورة).", "danger")
            return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

        if correct_option_index_str is None:
            flash("يجب تحديد الإجابة الصحيحة.", "danger")
            return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

        try:
            # Update existing options or add new ones
            for opt_data in options_from_form:
                option_text_to_save = opt_data["text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"]
                elif not option_text_to_save:
                    option_text_to_save = None

                if opt_data["id"] and opt_data["original_db_object"]:
                    # Update existing option
                    opt_to_update = opt_data["original_db_object"]
                    opt_to_update.option_text = option_text_to_save
                    opt_to_update.image_url = opt_data["image_url"]
                    opt_to_update.is_correct = opt_data["is_correct"]
                elif option_text_to_save or opt_data["image_url"]: # Add as new option only if it has content
                    new_opt = Option(
                        option_text=option_text_to_save,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_opt)
            
            # Delete options that were removed from the form
            options_to_delete_ids = existing_option_ids_in_db - processed_option_ids_from_form
            for opt_id_to_delete in options_to_delete_ids:
                opt_to_delete = Option.query.get(opt_id_to_delete)
                if opt_to_delete:
                    # Add logic to delete image from Cloudinary if opt_to_delete.image_url exists
                    db.session.delete(opt_to_delete)

            db.session.commit()
            current_app.logger.info(f"Question ID {question_id} and its options updated successfully.")
            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question {question_id}: {db_error}")
            flash("خطأ في قاعدة البيانات أثناء تعديل السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question {question_id}: {e}")
            flash("حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")
        
        # If any error occurs, re-render the form with the current question state
        return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

    # For GET request
    # The 'question' object (already fetched) contains question.lesson.unit.course_id etc.
    # This data will be used by JavaScript to pre-select the dropdowns.
    return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", question=question, submit_text="حفظ التعديلات")

# --- delete_question route (keep as is, ensure Cloudinary images are handled if necessary) --- #
@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    try:
        # Add logic here to delete images from Cloudinary for the question and its options
        # before deleting from DB.
        # Example for question image (if public_id is stored or derivable):
        # if question.public_id: cloudinary.uploader.destroy(question.public_id)
        # For options, iterate and destroy.

        for option in question.options:
            # if option.public_id: cloudinary.uploader.destroy(option.public_id)
            db.session.delete(option)
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting question {question_id}: {e}")
        flash("حدث خطأ أثناء حذف السؤال.", "danger")
    return redirect(url_for("question.list_questions"))

# --- Route to download question import template --- #
@question_bp.route("/download_template")
@login_required
def download_template():
    try:
        df = pd.DataFrame(columns=EXPECTED_IMPORT_COLUMNS)
        # Add a sample row with guidance
        sample_data = {
            EXPECTED_IMPORT_COLUMNS[0]: "ما هو لون السماء؟ (مثال)",
            EXPECTED_IMPORT_COLUMNS[1]: "(رابط صورة السؤال - اختياري)",
            EXPECTED_IMPORT_COLUMNS[2]: "أزرق",
            EXPECTED_IMPORT_COLUMNS[3]: "(رابط صورة الخيار 1 - اختياري)",
            EXPECTED_IMPORT_COLUMNS[4]: "أخضر",
            EXPECTED_IMPORT_COLUMNS[5]: "(رابط صورة الخيار 2 - اختياري)",
            EXPECTED_IMPORT_COLUMNS[6]: "أحمر",
            EXPECTED_IMPORT_COLUMNS[7]: "", # Empty for image URL
            EXPECTED_IMPORT_COLUMNS[8]: "أصفر",
            EXPECTED_IMPORT_COLUMNS[9]: "", # Empty for image URL
            EXPECTED_IMPORT_COLUMNS[10]: "1" # Correct option is 1 (أزرق)
        }
        # df = df.append(sample_data, ignore_index=True) # pandas > 2.0
        df_sample = pd.DataFrame([sample_data])
        df = pd.concat([df, df_sample], ignore_index=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='QuestionsTemplate')
            # Optional: Add comments or formatting to the Excel sheet here if needed
            # workbook  = writer.book
            # worksheet = writer.sheets['QuestionsTemplate']
            # worksheet.set_column('A:K', 20) # Example: Set column width
        output.seek(0)
        
        return send_file(
            output, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, 
            download_name='question_import_template.xlsx'
        )
    except Exception as e:
        current_app.logger.error(f"Error generating template: {e}")
        flash("حدث خطأ أثناء إنشاء ملف القالب.", "danger")
        return redirect(url_for("question.import_questions")) # Redirect to import page

# --- import_questions route (Modified to pass courses) --- #
@question_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_questions():
    # courses = get_all_courses_sorted() # Pass courses for the first dropdown
    # if not courses:
    #     flash("حدث خطأ أثناء تحميل قائمة الدورات أو لا توجد دورات متاحة. الرجاء إضافة المناهج أولاً.", "warning")
    #     return redirect(url_for("curriculum.list_courses"))
    # Relying on JS to fetch courses. 'lesson_id' will be submitted from the final dropdown.

    if request.method == "POST":
        lesson_id = request.form.get("lesson_id")
        import_file = request.files.get("import_file")

        if not lesson_id:
            flash("يجب اختيار درس ليتم استيراد الأسئلة إليه (من خلال تحديد الدورة ثم الوحدة ثم الدرس).", "danger")
            return render_template("question/import_questions.html", title="استيراد أسئلة من ملف")

        if not import_file or not import_file.filename:
            flash("الرجاء اختيار ملف للاستيراد.", "danger")
            return render_template("question/import_questions.html", title="استيراد أسئلة من ملف", selected_lesson_id=lesson_id)

        if not allowed_import_file(import_file.filename):
            flash("نوع ملف الاستيراد غير مسموح به. استخدم .xlsx أو .csv فقط.", "danger")
            return render_template("question/import_questions.html", title="استيراد أسئلة من ملف", selected_lesson_id=lesson_id)

        try:
            filename = secure_filename(import_file.filename)
            file_ext = filename.rsplit(".", 1)[1].lower()
            
            if file_ext == "xlsx":
                df = pd.read_excel(import_file, engine='openpyxl')
            elif file_ext == "csv":
                # Try to detect encoding, fall back to utf-8
                try:
                    df = pd.read_csv(import_file, encoding='utf-8-sig') # Handles BOM
                except UnicodeDecodeError:
                    import_file.seek(0) # Reset file pointer
                    df = pd.read_csv(import_file, encoding='latin1') # Common alternative
            else:
                # This case should be caught by allowed_import_file, but as a safeguard:
                flash("نوع ملف غير مدعوم.", "danger")
                return render_template("question/import_questions.html", title="استيراد أسئلة من ملف", selected_lesson_id=lesson_id)

            # Validate columns
            if not all(col in df.columns for col in EXPECTED_IMPORT_COLUMNS):
                missing_cols = [col for col in EXPECTED_IMPORT_COLUMNS if col not in df.columns]
                flash(f"الملف المستورد يفتقد للأعمدة المطلوبة: {', '.join(missing_cols)}. يرجى استخدام القالب.", "danger")
                return render_template("question/import_questions.html", title="استيراد أسئلة من ملف", selected_lesson_id=lesson_id)

            imported_count = 0
            error_rows = []

            for index, row in df.iterrows():
                try:
                    question_text = str(row[EXPECTED_IMPORT_COLUMNS[0]]).strip() if pd.notna(row[EXPECTED_IMPORT_COLUMNS[0]]) else None
                    question_image_url = str(row[EXPECTED_IMPORT_COLUMNS[1]]).strip() if pd.notna(row[EXPECTED_IMPORT_COLUMNS[1]]) else None
                    
                    if not question_text and not question_image_url:
                        error_rows.append(f"الصف {index + 2}: نص السؤال والصورة كلاهما فارغ.")
                        continue

                    new_question = Question(
                        question_text=question_text,
                        image_url=question_image_url,
                        lesson_id=lesson_id
                    )
                    db.session.add(new_question)
                    db.session.flush() # Get new_question.question_id

                    options_to_add = []
                    correct_option_number_from_file = None
                    try:
                        correct_option_val = row[EXPECTED_IMPORT_COLUMNS[10]]
                        if pd.notna(correct_option_val):
                            correct_option_number_from_file = int(correct_option_val)
                    except (ValueError, TypeError):
                        error_rows.append(f"الصف {index + 2}: رقم الخيار الصحيح غير صالح ('{row[EXPECTED_IMPORT_COLUMNS[10]]}').")
                        db.session.rollback() # Rollback this question
                        continue
                    
                    if correct_option_number_from_file is None:
                        error_rows.append(f"الصف {index + 2}: لم يتم تحديد رقم الخيار الصحيح.")
                        db.session.rollback()
                        continue

                    option_count_in_row = 0
                    for i in range(1, 5): # Options 1 to 4
                        opt_text_col = EXPECTED_IMPORT_COLUMNS[i*2]
                        opt_img_col = EXPECTED_IMPORT_COLUMNS[i*2 + 1]
                        
                        opt_text = str(row[opt_text_col]).strip() if pd.notna(row[opt_text_col]) else None
                        opt_img_url = str(row[opt_img_col]).strip() if pd.notna(row[opt_img_col]) else None
                        
                        if opt_text or opt_img_url:
                            option_count_in_row += 1
                            is_correct = (i == correct_option_number_from_file)
                            
                            option_text_to_save = opt_text
                            if not option_text_to_save and opt_img_url:
                                option_text_to_save = opt_img_url # Use image URL as text if text is empty
                            elif not option_text_to_save:
                                option_text_to_save = None

                            options_to_add.append(Option(
                                option_text=option_text_to_save,
                                image_url=opt_img_url,
                                is_correct=is_correct,
                                question_id=new_question.question_id
                            ))
                    
                    if option_count_in_row < 2:
                        error_rows.append(f"الصف {index + 2}: يجب توفير خيارين على الأقل.")
                        db.session.rollback()
                        continue
                    
                    if not any(opt.is_correct for opt in options_to_add):
                        error_rows.append(f"الصف {index + 2}: الخيار الصحيح المحدد ({correct_option_number_from_file}) لا يتوافق مع الخيارات الموجودة.")
                        db.session.rollback()
                        continue

                    for opt in options_to_add:
                        db.session.add(opt)
                    
                    db.session.commit() # Commit this question and its options
                    imported_count += 1

                except Exception as e_row:
                    db.session.rollback()
                    error_rows.append(f"الصف {index + 2}: خطأ غير متوقع - {str(e_row)}")
            
            if imported_count > 0:
                flash(f"تم استيراد {imported_count} سؤال بنجاح إلى الدرس المحدد.", "success")
            if error_rows:
                flash("واجهت بعض الصفوف مشاكل أثناء الاستيراد:", "warning")
                for err in error_rows:
                    flash(err, "danger") # Display each error as a separate flash message
            if imported_count == 0 and not error_rows:
                 flash("لم يتم العثور على أسئلة صالحة في الملف أو أن الملف فارغ.", "info")

            return redirect(url_for("question.list_questions"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error importing questions: {e}", exc_info=True)
            flash(f"حدث خطأ أثناء معالجة ملف الاستيراد: {str(e)}", "danger")
            return render_template("question/import_questions.html", title="استيراد أسئلة من ملف", selected_lesson_id=lesson_id)

    # For GET request
    return render_template("question/import_questions.html", title="استيراد أسئلة من ملف")

