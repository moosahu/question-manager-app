# src/routes/question.py (Modified for Cloudinary, Import & Template Download)

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
    from src.models.curriculum import Lesson, Unit, Course
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

    # Configure Cloudinary (should ideally be done once at app startup)
    # Ensure CLOUDINARY_URL or individual CLOUD_NAME, API_KEY, API_SECRET are set in environment
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
         current_app.logger.error("Cloudinary environment variables (CLOUD_NAME, API_KEY, API_SECRET) are missing or incomplete.")
         # Attempt to configure from CLOUDINARY_URL as a fallback
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
        # Generate a unique public_id using timestamp and UUID
        public_id = f"{subfolder}/{int(time.time())}_{uuid.uuid4().hex[:8]}_{os.path.splitext(original_filename)[0]}"
        current_app.logger.debug(f"Generated Cloudinary public_id: {public_id}")

        current_app.logger.debug(f"Attempting to upload to Cloudinary with public_id: {public_id}")
        
        # Ensure file pointer is at the beginning
        file.seek(0)
        
        upload_result = cloudinary.uploader.upload(
            file.stream, # Pass the file stream
            public_id=public_id,
            folder=subfolder, # Optional: Organize within Cloudinary folders
            resource_type="auto" # Automatically detect resource type (image/video/raw)
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
    
    # استقبال معاملات التصفية من الطلب
    course_id = request.args.get("course_id", type=int)
    unit_id = request.args.get("unit_id", type=int)
    lesson_id = request.args.get("lesson_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = 10
    
    current_app.logger.info(f"Filter parameters: course_id={course_id}, unit_id={unit_id}, lesson_id={lesson_id}, page={page}")
    
    try:
        # بناء الاستعلام الأساسي
        query = Question.query.options(
            joinedload(Question.options),
            joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
        )
        
        # إضافة شروط التصفية إذا تم تحديدها
        if lesson_id:
            query = query.filter(Question.lesson_id == lesson_id)
        elif unit_id:
            query = query.join(Question.lesson).filter(Lesson.unit_id == unit_id)
        elif course_id:
            query = query.join(Question.lesson).join(Lesson.unit).filter(Unit.course_id == course_id)
        
        # ترتيب النتائج وتقسيمها إلى صفحات
        questions_pagination = query.order_by(Question.question_id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")
        
        # جلب قوائم الدورات والوحدات والدروس للتصفية
        courses = Course.query.order_by(Course.name).all()
        units = []
        lessons = []
        
        if course_id:
            units = Unit.query.filter_by(course_id=course_id).order_by(Unit.name).all()
            if unit_id:
                lessons = Lesson.query.filter_by(unit_id=unit_id).order_by(Lesson.name).all()
        
        rendered_template = render_template(
            "list_complete.html", 
            questions=questions_pagination.items, 
            pagination=questions_pagination,
            courses=courses,
            units=units,
            lessons=lessons,
            title="قائمة الأسئلة"
        )
        
        current_app.logger.info("Template rendering successful.")
        return rendered_template
        
    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash("حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger")
        return redirect(url_for("index")) # Should be dashboard or a general error page

# --- get_sorted_lessons function (keep as is) --- #
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

# --- add_question route (Uses modified save_upload) --- #
@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        # Consider redirecting to a more relevant page like curriculum management
        return redirect(url_for("curriculum.list_courses")) 

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
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
            error_messages.append("يجب اختيار درس.")
        
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
        # Determine the maximum index submitted for options to iterate correctly
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue # Skip malformed keys

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

            if option_text or option_image_path: # Only add if there's text or a successfully uploaded image
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i, # Store original index for repopulation
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        
        # Validate correct_option_index against the actual number of valid options collected
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح ضمن الخيارات المعبأة.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form data for rendering again
            form_data = request.form.to_dict()
            # Prepare options for repopulation, including any previously uploaded (but failed validation) images
            repop_options = []
            for i in range(max_submitted_index + 1): # Iterate up to the max index found
                 idx_str = str(i)
                 opt_text = request.form.get(f"option_text_{idx_str}", "")
                 # Find if this option was processed and had an image URL (even if validation failed later)
                 processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                 img_url = processed_opt["image_url"] if processed_opt and "image_url" in processed_opt else None
                 # If image upload failed for this specific option, its image_url would be None here
                 # but we might want to show the text if it was entered.
                 repop_options.append({"option_text": opt_text, "image_url": img_url})
            
            form_data["options_repop"] = repop_options
            form_data["correct_option_repop"] = correct_option_index_str
            form_data["question_image_url_repop"] = q_image_path # Repopulate question image if it was uploaded
            return render_template("form_complete.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        try:
            new_question = Question(
                question_text=question_text if question_text else None, # Store None if empty
                lesson_id=lesson_id,
                image_url=q_image_path
            )
            db.session.add(new_question)
            db.session.flush() # Get the ID for the new question
            current_app.logger.info(f"New question added (pending commit) with ID: {new_question.question_id}")

            for opt_data in options_data_from_form:
                option_text_to_save = opt_data["option_text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"] 
                elif not option_text_to_save:
                    option_text_to_save = None # Ensure None is saved if truly empty

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

        except (IntegrityError, DBAPIError) as e:
            db.session.rollback()
            current_app.logger.error(f"Database error during question/option creation: {e}", exc_info=True)
            flash("حدث خطأ في قاعدة البيانات أثناء إضافة السؤال. يرجى المحاولة مرة أخرى.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error during question/option creation: {e}", exc_info=True)
            flash("حدث خطأ غير متوقع أثناء إضافة السؤال.", "danger")
        
        # If any exception occurred, re-render the form with existing data
        form_data = request.form.to_dict()
        repop_options = []
        for i in range(max_submitted_index + 1):
                idx_str = str(i)
                opt_text = request.form.get(f"option_text_{idx_str}", "")
                processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                img_url = processed_opt["image_url"] if processed_opt and "image_url" in processed_opt else None
                repop_options.append({"option_text": opt_text, "image_url": img_url})
        form_data["options_repop"] = repop_options
        form_data["correct_option_repop"] = correct_option_index_str
        form_data["question_image_url_repop"] = q_image_path
        return render_template("form_complete.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

    # GET request
    return render_template("form_complete.html", title="إضافة سؤال جديد", lessons=lessons, submit_text="إضافة سؤال")

# --- edit_question route (Uses modified save_upload) --- #
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
        delete_q_image = request.form.get("delete_question_image") == "true"

        q_image_path = question.image_url # Keep existing if not changed
        if delete_q_image:
            q_image_path = None # Mark for deletion/clearing
            # Add Cloudinary deletion logic here if needed, though often just clearing the DB URL is enough
        elif q_image_file and q_image_file.filename:
            if not allowed_image_file(q_image_file.filename):
                flash("نوع ملف صورة السؤال غير مسموح به.", "danger")
            else:
                new_q_image_path = save_upload(q_image_file, subfolder="questions")
                if new_q_image_path:
                    q_image_path = new_q_image_path
                else:
                    flash("فشل رفع صورة السؤال الجديدة. تحقق من إعدادات Cloudinary والسجلات.", "danger")
        
        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        
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
            if key.startswith(("option_text_", "option_image_", "option_id_")):
                try:
                    # Try to get index from option_text_ or option_image_ or option_id_
                    if key.startswith("option_text_") or key.startswith("option_image_"):
                        index_str = key.split("_")[-1]
                    elif key.startswith("option_id_"):
                        index_str = key.replace("option_id_","") # For existing options
                    else: 
                        continue
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue
        
        current_app.logger.debug(f"Max submitted index for options: {max_submitted_index}")

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_id_str = request.form.get(f"option_id_{index_str}") # For existing options
            option_id = int(option_id_str) if option_id_str else None
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            delete_opt_image = request.form.get(f"delete_option_image_{index_str}") == "true"
            
            # Determine existing image URL for this option if it's an existing option
            existing_option_for_image = None
            if option_id:
                existing_option_for_image = next((opt for opt in question.options if opt.option_id == option_id), None)
            
            option_image_path = existing_option_for_image.image_url if existing_option_for_image else None

            if delete_opt_image:
                option_image_path = None
            elif option_image_file and option_image_file.filename:
                if not allowed_image_file(option_image_file.filename):
                    error_messages.append(f"نوع ملف صورة الخيار رقم {i+1} غير مسموح به.")
                else:
                    new_opt_image_path = save_upload(option_image_file, subfolder="options")
                    if new_opt_image_path:
                        option_image_path = new_opt_image_path
                    else:
                        error_messages.append(f"فشل رفع صورة الخيار رقم {i+1}. تحقق من إعدادات Cloudinary والسجلات.")
            
            if option_text or option_image_path: # Only consider if there's text or an image
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i, # Original form index
                    "option_id": option_id, # Existing ID or None for new
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب توفير خيارين صالحين على الأقل (بنص أو صورة).")
        
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
            error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح ضمن الخيارات المعبأة.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form for re-rendering
            # We need to pass the question object as it was, but with form values overriding it for display
            form_data_for_repop = {
                "question_id": question.question_id,
                "text": request.form.get("text", question.question_text),
                "lesson_id": request.form.get("lesson_id", str(question.lesson_id)),
                "image_url": q_image_path, # This will be the new or cleared path
                "options_repop": [],
                "correct_option_repop": correct_option_index_str
            }
            for i in range(max_submitted_index + 1):
                idx_str = str(i)
                opt_text = request.form.get(f"option_text_{idx_str}", "")
                # Find the processed option data for this index to get its image_url
                processed_opt_data = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                img_url = processed_opt_data["image_url"] if processed_opt_data else None
                form_data_for_repop["options_repop"].append({"option_text": opt_text, "image_url": img_url})

            return render_template("form_complete.html", title=f"تعديل السؤال رقم {question.question_id}", question=form_data_for_repop, lessons=lessons, submit_text="حفظ التعديلات")

        try:
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = q_image_path

            # --- Option Update/Delete/Add Logic --- # 
            existing_option_ids_in_db = {opt.option_id for opt in question.options}
            submitted_option_ids = {opt_data["option_id"] for opt_data in options_data_from_form if opt_data["option_id"] is not None}

            # 1. Delete options not in submission
            options_to_delete = existing_option_ids_in_db - submitted_option_ids
            for opt_id_to_delete in options_to_delete:
                option_to_delete = Option.query.get(opt_id_to_delete)
                if option_to_delete:
                    db.session.delete(option_to_delete)
                    current_app.logger.info(f"Option ID {opt_id_to_delete} marked for deletion.")

            # 2. Update existing options and add new ones
            for opt_data in options_data_from_form:
                option_text_to_save = opt_data["option_text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"]
                elif not option_text_to_save:
                    option_text_to_save = None
                
                if opt_data["option_id"] is not None: # Existing option
                    option_to_update = Option.query.get(opt_data["option_id"])
                    if option_to_update:
                        option_to_update.option_text = option_text_to_save
                        option_to_update.image_url = opt_data["image_url"]
                        option_to_update.is_correct = opt_data["is_correct"]
                        current_app.logger.info(f"Option ID {opt_data['option_id']} updated.")
                else: # New option
                    new_option = Option(
                        option_text=option_text_to_save,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)
                    current_app.logger.info(f"New option added for question ID {question.question_id}.")
            
            db.session.commit()
            current_app.logger.info(f"Transaction committed for editing question ID: {question_id}")
            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as e:
            db.session.rollback()
            current_app.logger.error(f"Database error during question edit: {e}", exc_info=True)
            flash("حدث خطأ في قاعدة البيانات أثناء تعديل السؤال. يرجى المحاولة مرة أخرى.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error during question edit: {e}", exc_info=True)
            flash("حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")
        
        # If any exception occurred, re-render the form with existing data
        form_data_for_repop = {
            "question_id": question.question_id,
            "text": request.form.get("text", question.question_text),
            "lesson_id": request.form.get("lesson_id", str(question.lesson_id)),
            "image_url": q_image_path,
            "options_repop": [],
            "correct_option_repop": correct_option_index_str
        }
        for i in range(max_submitted_index + 1):
            idx_str = str(i)
            opt_text = request.form.get(f"option_text_{idx_str}", "")
            processed_opt_data = next((opt for opt in options_data_from_form if opt["index"] == i), None)
            img_url = processed_opt_data["image_url"] if processed_opt_data else None
            form_data_for_repop["options_repop"].append({"option_text": opt_text, "image_url": img_url})
        return render_template("form_complete.html", title=f"تعديل السؤال رقم {question.question_id}", question=form_data_for_repop, lessons=lessons, submit_text="حفظ التعديلات")

    # GET request - prepare data for the form
    # We need to pass the existing question data, including its options, to the template
    question_data_for_form = {
        "question_id": question.question_id,
        "text": question.question_text,
        "lesson_id": str(question.lesson_id), # Ensure it's a string for form selection
        "image_url": question.image_url,
        "options": [], # This will be populated for the template
        "correct_option": None # This will be set for the template
    }
    for i, opt in enumerate(question.options):
        question_data_for_form["options"].append({
            "option_id": opt.option_id,
            "option_text": opt.option_text,
            "image_url": opt.image_url
        })
        if opt.is_correct:
            question_data_for_form["correct_option"] = str(i) # Store index as string

    return render_template("form_complete.html", title=f"تعديل السؤال رقم {question.question_id}", question=question_data_for_form, lessons=lessons, submit_text="حفظ التعديلات")

# --- delete_question route (keep as is) --- #
@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        # Delete associated options first
        Option.query.filter_by(question_id=question.question_id).delete()
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting question {question_id}: {e}", exc_info=True)
        flash("حدث خطأ أثناء حذف السؤال.", "danger")
    return redirect(url_for("question.list_questions"))

# --- import_questions route (Modified for template download and processing) --- #
@question_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_questions():
    lessons = get_sorted_lessons()
    if not lessons:
        flash("لا توجد دروس متاحة للاستيراد إليها. يرجى إضافة المناهج أولاً.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request for import_questions")
        if "file" not in request.files:
            flash("لم يتم اختيار أي ملف.", "danger")
            return redirect(request.url)
        
        file = request.files["file"]
        lesson_id_for_import = request.form.get("lesson_id_for_import")

        if not lesson_id_for_import:
            flash("يجب اختيار درس لاستيراد الأسئلة إليه.", "danger")
            return render_template("import_questions_complete.html", title="استيراد أسئلة", lessons=lessons)

        if file.filename == "":
            flash("لم يتم اختيار أي ملف.", "danger")
            return redirect(request.url)

        if file and allowed_import_file(file.filename):
            filename = secure_filename(file.filename)
            current_app.logger.info(f"Processing import file: {filename} for lesson ID: {lesson_id_for_import}")
            try:
                # Read the file into a pandas DataFrame
                if filename.endswith(".xlsx"):
                    df = pd.read_excel(file, engine='openpyxl')
                elif filename.endswith(".csv"):
                    # Try common encodings for CSV
                    try:
                        df = pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        try:
                            df = pd.read_csv(file, encoding='windows-1256') # Arabic Windows
                        except UnicodeDecodeError:
                            df = pd.read_csv(file, encoding='iso-8859-1') # Latin-1
                else:
                    flash("نوع ملف غير مدعوم للاستيراد.", "danger")
                    return redirect(request.url)

                # Validate columns (case-insensitive check)
                df.columns = [col.strip().lower() for col in df.columns]
                expected_cols_lower = [col.lower() for col in EXPECTED_IMPORT_COLUMNS]
                missing_cols = [col for col in expected_cols_lower if col not in df.columns]
                if missing_cols:
                    flash(f"الأعمدة التالية مفقودة في الملف: {', '.join(missing_cols)}. يرجى استخدام القالب الموفر.", "danger")
                    return render_template("import_questions_complete.html", title="استيراد أسئلة", lessons=lessons)

                questions_added_count = 0
                errors_encountered = []

                for index, row in df.iterrows():
                    try:
                        question_text = str(row.get(expected_cols_lower[0], "")).strip() if pd.notna(row.get(expected_cols_lower[0])) else None
                        q_image_url = str(row.get(expected_cols_lower[1], "")).strip() if pd.notna(row.get(expected_cols_lower[1])) else None
                        
                        if not question_text and not q_image_url:
                            errors_encountered.append(f"صف {index + 2}: يجب توفير نص للسؤال أو رابط صورة له.")
                            continue

                        options_data = []
                        for i in range(1, 5): # Options 1 to 4
                            opt_text_col = expected_cols_lower[i*2]
                            opt_img_col = expected_cols_lower[i*2 + 1]
                            opt_text = str(row.get(opt_text_col, "")).strip() if pd.notna(row.get(opt_text_col)) else None
                            opt_img_url = str(row.get(opt_img_col, "")).strip() if pd.notna(row.get(opt_img_col)) else None
                            if opt_text or opt_img_url:
                                options_data.append({"text": opt_text, "image_url": opt_img_url})
                        
                        if len(options_data) < 2:
                            errors_encountered.append(f"صف {index + 2}: يجب توفير خيارين على الأقل.")
                            continue

                        correct_option_num_str = str(row.get(expected_cols_lower[-1], "")).strip()
                        if not correct_option_num_str:
                            errors_encountered.append(f"صف {index + 2}: يجب تحديد رقم الخيار الصحيح.")
                            continue
                        try:
                            correct_option_num = int(float(correct_option_num_str)) # Handle potential float from Excel
                            if not (1 <= correct_option_num <= len(options_data)):
                                errors_encountered.append(f"صف {index + 2}: رقم الخيار الصحيح ({correct_option_num}) خارج النطاق (1-{len(options_data)}).")
                                continue
                        except ValueError:
                            errors_encountered.append(f"صف {index + 2}: رقم الخيار الصحيح ({correct_option_num_str}) يجب أن يكون رقمًا.")
                            continue
                        
                        # Create Question
                        new_q = Question(
                            question_text=question_text,
                            image_url=q_image_url,
                            lesson_id=lesson_id_for_import
                        )
                        db.session.add(new_q)
                        db.session.flush() # Get ID

                        # Create Options
                        for idx, opt_data in enumerate(options_data):
                            is_correct = (idx + 1 == correct_option_num)
                            option_text_to_save = opt_data["text"]
                            if not option_text_to_save and opt_data["image_url"]:
                                option_text_to_save = opt_data["image_url"]
                            elif not option_text_to_save:
                                option_text_to_save = None
                                
                            new_opt = Option(
                                option_text=option_text_to_save,
                                image_url=opt_data["image_url"],
                                is_correct=is_correct,
                                question_id=new_q.question_id
                            )
                            db.session.add(new_opt)
                        
                        questions_added_count += 1
                        db.session.commit() # Commit per question to avoid losing all on one error

                    except Exception as e_row:
                        db.session.rollback()
                        errors_encountered.append(f"صف {index + 2}: خطأ غير متوقع - {str(e_row)}")
                        current_app.logger.error(f"Error processing row {index + 2} of import file: {e_row}", exc_info=True)
                
                if questions_added_count > 0:
                    flash(f"تم استيراد {questions_added_count} سؤال بنجاح إلى الدرس المحدد!", "success")
                if errors_encountered:
                    for error in errors_encountered:
                        flash(error, "danger")
                    flash("تم العثور على أخطاء أثناء الاستيراد. يرجى مراجعة الملف وتصحيح الأخطاء المذكورة.", "warning")
                elif questions_added_count == 0:
                    flash("لم يتم استيراد أي أسئلة. قد يكون الملف فارغًا أو يحتوي على أخطاء في جميع الصفوف.", "info")
                
                return redirect(url_for("question.list_questions", lesson_id=lesson_id_for_import))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error during file import processing: {e}", exc_info=True)
                flash(f"حدث خطأ أثناء معالجة الملف: {str(e)}. يرجى التأكد من أن الملف بالتنسيق الصحيح.", "danger")
                return redirect(request.url)
        else:
            flash("نوع الملف غير مسموح به. يرجى تحميل ملف Excel (.xlsx) أو CSV (.csv).", "danger")
            return redirect(request.url)

    # GET request
    return render_template("import_questions_complete.html", title="استيراد أسئلة", lessons=lessons)

# --- download_template route (New route for downloading the import template) --- #
@question_bp.route("/download_template")
@login_required
def download_template():
    try:
        # Create a DataFrame with the expected columns
        template_df = pd.DataFrame(columns=EXPECTED_IMPORT_COLUMNS)
        
        # Create an in-memory Excel file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False, sheet_name='QuestionsImportTemplate')
        output.seek(0)
        
        current_app.logger.info("Import template generated successfully for download.")
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='question_import_template.xlsx'
        )
    except Exception as e:
        current_app.logger.error(f"Error generating import template: {e}", exc_info=True)
        flash("حدث خطأ أثناء إنشاء قالب الاستيراد.", "danger")
        return redirect(url_for("question.import_questions"))

# --- view_question route (Optional, if you need a dedicated view page) --- #
@question_bp.route("/view/<int:question_id>")
@login_required
def view_question(question_id):
    question = Question.query.options(
        joinedload(Question.options),
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    ).get_or_404(question_id)
    # You might want a specific template for viewing a single question in detail
    # For now, let's reuse the list template's logic or a simplified one.
    # This is just a placeholder; you'd create a 'view_question.html' or similar.
    return render_template("form_simplified_complete.html", title=f"عرض السؤال رقم {question.question_id}", question=question, view_mode=True)

