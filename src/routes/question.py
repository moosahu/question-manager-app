# src/routes/question.py (Modified with detailed logging for import function)

import os
import logging
import time
import uuid
import io # Added for reading/writing file in memory
import pandas as pd # Added for reading Excel/CSV
import traceback # Added for detailed error logging
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
    from src.models.activity import Activity  # استيراد نموذج النشاط
except ImportError:
    try:
        from models.question import Question, Option
        from models.curriculum import Lesson, Unit, Course
        from models.activity import Activity  # استيراد نموذج النشاط
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
            "question/list.html", 
            questions=questions_pagination.items, 
            pagination=questions_pagination,
            courses=courses,
            units=units,
            lessons=lessons
        )
        
        current_app.logger.info("Template rendering successful.")
        return rendered_template
        
    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash("حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger")
        return redirect(url_for("index"))

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
                 # Uses the Cloudinary-compatible save_upload function
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
                    # Uses the Cloudinary-compatible save_upload function
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
                # --- Logic to set option_text to image_url if option_text is empty and image_url exists ---
                option_text_to_save = opt_data["option_text"]
                if not option_text_to_save and opt_data["image_url"]:
                    option_text_to_save = opt_data["image_url"] # Set option_text to the image_url
                elif not option_text_to_save: # If option_text is still empty (and no image_url or image_url was not used)
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
            
            # تسجيل نشاط إضافة السؤال
            try:
                lesson = Lesson.query.get(lesson_id)
                lesson_name = lesson.name if lesson else None
                unit_name = lesson.unit.name if lesson and lesson.unit else None
                course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
                
                Activity.log_activity(
                    action_type="add",
                    entity_type="question",
                    entity_id=new_question.question_id,
                    description=f"تمت إضافة سؤال جديد: {question_text[:50] + '...' if question_text and len(question_text) > 50 else question_text or '[سؤال بصورة]'}",
                    lesson_name=lesson_name,
                    unit_name=unit_name,
                    course_name=course_name,
                    user_id=current_user.id if current_user.is_authenticated else None
                )
                current_app.logger.info("Activity logged successfully for question addition.")
            except Exception as activity_error:
                # تسجيل الخطأ فقط دون التأثير على تدفق الدالة
                current_app.logger.error(f"Error logging activity for question addition: {activity_error}")
            
            flash("تمت إضافة السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Error adding question: {e}")
            flash("حدث خطأ أثناء إضافة السؤال.", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, submit_text="إضافة سؤال")

# --- edit_question route (Modified to ensure proper lesson data) --- #
@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # استرجاع السؤال مع الخيارات والدرس والوحدة والدورة
    question = Question.query.options(
        joinedload(Question.options),
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    ).get_or_404(question_id)
    
    # الحصول على قائمة الدروس المرتبة
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس.", "danger")
        return redirect(url_for("question.list_questions"))

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")
        original_lesson_id = question.lesson_id
        original_question_text = question.question_text

        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")
        remove_q_image = request.form.get("remove_question_image") == "1"

        q_image_path = question.image_url
        if remove_q_image:
            q_image_path = None
            current_app.logger.info(f"Request to remove question image for ID: {question_id}")
        elif q_image_file and q_image_file.filename:
            if not allowed_image_file(q_image_file.filename):
                flash("نوع ملف صورة السؤال غير مسموح به.", "danger")
            else:
                # Uses the Cloudinary-compatible save_upload function
                new_q_image_path = save_upload(q_image_file, subfolder="questions")
                if new_q_image_path:
                    q_image_path = new_q_image_path
                    current_app.logger.info(f"New question image uploaded for ID: {question_id}")
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
        existing_option_ids = {opt.option_id for opt in question.options}
        processed_option_ids = set()

        possible_indices = set()
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_", "existing_option_id_", "remove_option_image_")):
                try:
                    index_str = key.split("_")[-1]
                    possible_indices.add(int(index_str))
                except (ValueError, IndexError):
                    continue
        max_submitted_index = max(possible_indices) if possible_indices else -1

        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            existing_option_id_str = request.form.get(f"existing_option_id_{index_str}")
            remove_opt_image = request.form.get(f"remove_option_image_{index_str}") == "1"
            option_image_path = request.form.get(f"existing_image_url_{index_str}")
            existing_option_id = None

            if existing_option_id_str:
                try:
                    existing_option_id = int(existing_option_id_str)
                    if existing_option_id in existing_option_ids:
                        processed_option_ids.add(existing_option_id)
                    else:
                        existing_option_id = None
                except ValueError:
                    existing_option_id = None
            
            if remove_opt_image:
                option_image_path = None
                current_app.logger.info(f"Request to remove option image for index {i}, existing ID: {existing_option_id}")
            elif option_image_file and option_image_file.filename:
                if not allowed_image_file(option_image_file.filename):
                    error_messages.append(f"نوع ملف صورة الخيار في الموضع {i+1} غير مسموح به.")
                else:
                    # Uses the Cloudinary-compatible save_upload function
                    new_opt_image_path = save_upload(option_image_file, subfolder="options")
                    if new_opt_image_path:
                        option_image_path = new_opt_image_path
                        current_app.logger.info(f"New option image uploaded for index {i}, existing ID: {existing_option_id}")
                    else:
                        error_messages.append(f"فشل رفع صورة الخيار الجديدة في الموضع {i+1}. تحقق من إعدادات Cloudinary والسجلات.")
            
            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i,
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct,
                    "existing_id": existing_option_id
                })

        if len(options_data_from_form) < 2:
            error_messages.append("يجب توفير خيارين صالحين على الأقل (بنص أو صورة).")
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            return render_template("question/form.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        try:
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = q_image_path
            current_app.logger.info(f"Updating question ID: {question_id}")

            options_to_delete = existing_option_ids - processed_option_ids
            if options_to_delete:
                current_app.logger.info(f"Deleting options with IDs: {options_to_delete} for question ID: {question_id}")
                Option.query.filter(Option.option_id.in_(options_to_delete)).delete(synchronize_session=False)

            for opt_data in options_data_from_form:
                if opt_data["existing_id"]:
                    option_to_update = Option.query.get(opt_data["existing_id"])
                    if option_to_update:
                        # --- Logic to set option_text to image_url if option_text is empty and image_url exists ---
                        option_text_to_save = opt_data["option_text"]
                        if not option_text_to_save and opt_data["image_url"]:
                            option_text_to_save = opt_data["image_url"] # Set option_text to the image_url
                        elif not option_text_to_save: # If option_text is still empty (and no image_url or image_url was not used)
                            option_text_to_save = None

                        option_to_update.option_text = option_text_to_save
                        option_to_update.image_url = opt_data["image_url"]
                        option_to_update.is_correct = opt_data["is_correct"]
                        current_app.logger.info(f"Updated existing option ID: {opt_data['existing_id']} for question ID: {question_id}")
                else:
                    # --- Logic to set option_text to image_url if option_text is empty and image_url exists ---
                    option_text_to_save = opt_data["option_text"]
                    if not option_text_to_save and opt_data["image_url"]:
                        option_text_to_save = opt_data["image_url"] # Set option_text to the image_url
                    elif not option_text_to_save: # If option_text is still empty (and no image_url or image_url was not used)
                        option_text_to_save = None

                    new_option = Option(
                        option_text=option_text_to_save,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)
                    current_app.logger.info(f"Added new option for question ID: {question_id}")
            
            db.session.commit()
            current_app.logger.info(f"Successfully updated question ID: {question_id}")
            
            # تسجيل نشاط تعديل السؤال
            try:
                lesson = Lesson.query.get(lesson_id)
                lesson_name = lesson.name if lesson else None
                unit_name = lesson.unit.name if lesson and lesson.unit else None
                course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
                
                Activity.log_activity(
                    action_type="edit",
                    entity_type="question",
                    entity_id=question.question_id,
                    description=f"تم تعديل سؤال: {question_text[:50] + '...' if question_text and len(question_text) > 50 else question_text or '[سؤال بصورة]'}",
                    lesson_name=lesson_name,
                    unit_name=unit_name,
                    course_name=course_name,
                    user_id=current_user.id if current_user.is_authenticated else None
                )
                current_app.logger.info("Activity logged successfully for question edit.")
            except Exception as activity_error:
                # تسجيل الخطأ فقط دون التأثير على تدفق الدالة
                current_app.logger.error(f"Error logging activity for question edit: {activity_error}")
            
            flash("تم تحديث السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error updating question: {db_error}")
            flash("خطأ في قاعدة البيانات أثناء تحديث السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error updating question: {e}")
            flash("حدث خطأ غير متوقع أثناء تحديث السؤال.", "danger")
        
        return render_template("question/form.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # تأكد من أن السؤال يحتوي على معلومات الدرس والوحدة والدورة
    if question.lesson and question.lesson.unit and question.lesson.unit.course:
        current_app.logger.info(f"Question {question_id} has complete lesson path: {question.lesson.unit.course.name} / {question.lesson.unit.name} / {question.lesson.name}")
    else:
        current_app.logger.warning(f"Question {question_id} has incomplete lesson path")
        
    return render_template("question/form.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question, submit_text="حفظ التعديلات")

# --- delete_question route (keep as is) --- #
@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    current_app.logger.info(f"Received request to delete question ID: {question_id}")
    question = Question.query.get_or_404(question_id)
    
    # حفظ معلومات السؤال قبل حذفه لاستخدامها في تسجيل النشاط
    question_text = question.question_text
    lesson = question.lesson
    lesson_name = lesson.name if lesson else None
    unit_name = lesson.unit.name if lesson and lesson.unit else None
    course_name = lesson.unit.course.name if lesson and lesson.unit and lesson.unit.course else None
    
    try:
        # Manually delete options first due to potential cascade issues
        Option.query.filter_by(question_id=question_id).delete()
        db.session.delete(question)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted question ID: {question_id}")
        
        # تسجيل نشاط حذف السؤال
        try:
            Activity.log_activity(
                action_type="delete",
                entity_type="question",
                entity_id=question_id,
                description=f"تم حذف سؤال: {question_text[:50] + '...' if question_text and len(question_text) > 50 else question_text or '[سؤال بصورة]'}",
                lesson_name=lesson_name,
                unit_name=unit_name,
                course_name=course_name,
                user_id=current_user.id if current_user.is_authenticated else None
            )
            current_app.logger.info("Activity logged successfully for question deletion.")
        except Exception as activity_error:
            # تسجيل الخطأ فقط دون التأثير على تدفق الدالة
            current_app.logger.error(f"Error logging activity for question deletion: {activity_error}")
        
        flash("تم حذف السؤال بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question: {e}")
        flash("حدث خطأ أثناء محاولة حذف السؤال.", "danger")
    
    return redirect(url_for("question.list_questions"))

# --- import_questions route (Modified with detailed logging) --- #
@question_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_questions():
    """Import questions from Excel or CSV file."""
    current_app.logger.info("=== IMPORT QUESTIONS: Starting import_questions function ===")
    
    lessons = get_sorted_lessons()
    if not lessons:
        current_app.logger.error("=== IMPORT QUESTIONS: No lessons available ===")
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("=== IMPORT QUESTIONS: POST request received ===")
        
        # Get form data
        lesson_id = request.form.get("lesson_id")
        current_app.logger.info(f"=== IMPORT QUESTIONS: Lesson ID from form: {lesson_id} ===")
        
        if not lesson_id:
            current_app.logger.error("=== IMPORT QUESTIONS: No lesson_id provided ===")
            flash("يجب اختيار درس لاستيراد الأسئلة إليه.", "danger")
            return render_template("question/import_questions.html", lessons=lessons)
        
        # Check if file was uploaded
        current_app.logger.info("=== IMPORT QUESTIONS: Checking for import_file in request.files ===")
        current_app.logger.info(f"=== IMPORT QUESTIONS: request.files keys: {list(request.files.keys())} ===")
        
        if "import_file" not in request.files:
            current_app.logger.error("=== IMPORT QUESTIONS: import_file not in request.files ===")
            flash("لم يتم تحديد ملف للاستيراد.", "danger")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
        
        import_file = request.files["import_file"]
        if not import_file or not import_file.filename:
            current_app.logger.error("=== IMPORT QUESTIONS: import_file is empty or has no filename ===")
            flash("لم يتم تحديد ملف للاستيراد.", "danger")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
        
        current_app.logger.info(f"=== IMPORT QUESTIONS: File received: {import_file.filename} ===")
        
        if not allowed_import_file(import_file.filename):
            current_app.logger.error(f"=== IMPORT QUESTIONS: File type not allowed: {import_file.filename} ===")
            flash("نوع الملف غير مدعوم. يرجى استخدام ملف Excel (.xlsx) أو CSV (.csv).", "danger")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
        
        try:
            current_app.logger.info("=== IMPORT QUESTIONS: Starting to read file ===")
            # Read the file
            if import_file.filename.endswith(".xlsx"):
                current_app.logger.info("=== IMPORT QUESTIONS: Reading Excel file ===")
                try:
                    df = pd.read_excel(import_file)
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Excel file read successfully. Shape: {df.shape} ===")
                except Exception as excel_error:
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Error reading Excel file: {excel_error} ===")
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Traceback: {traceback.format_exc()} ===")
                    flash(f"حدث خطأ أثناء قراءة ملف Excel: {str(excel_error)}", "danger")
                    return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
            else:  # CSV
                current_app.logger.info("=== IMPORT QUESTIONS: Reading CSV file ===")
                try:
                    df = pd.read_csv(import_file)
                    current_app.logger.info(f"=== IMPORT QUESTIONS: CSV file read successfully. Shape: {df.shape} ===")
                except Exception as csv_error:
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Error reading CSV file: {csv_error} ===")
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Traceback: {traceback.format_exc()} ===")
                    flash(f"حدث خطأ أثناء قراءة ملف CSV: {str(csv_error)}", "danger")
                    return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
            
            # Validate columns
            current_app.logger.info(f"=== IMPORT QUESTIONS: Validating columns. File columns: {list(df.columns)} ===")
            current_app.logger.info(f"=== IMPORT QUESTIONS: Expected columns: {EXPECTED_IMPORT_COLUMNS} ===")
            
            missing_columns = [col for col in EXPECTED_IMPORT_COLUMNS if col not in df.columns]
            if missing_columns:
                current_app.logger.error(f"=== IMPORT QUESTIONS: Missing columns: {missing_columns} ===")
                flash(f"الملف لا يحتوي على الأعمدة المطلوبة: {', '.join(missing_columns)}", "danger")
                return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
            
            # Process each row
            imported_count = 0
            error_details = []
            
            current_app.logger.info(f"=== IMPORT QUESTIONS: Starting to process {len(df)} rows ===")
            
            for index, row in df.iterrows():
                try:
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Processing row {index+1} ===")
                    
                    # Extract question data
                    question_text = str(row["Question Text"]).strip() if not pd.isna(row["Question Text"]) else None
                    question_image_url = str(row["Question Image URL"]).strip() if not pd.isna(row["Question Image URL"]) else None
                    
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Question text: {question_text[:30] + '...' if question_text and len(question_text) > 30 else question_text} ===")
                    
                    # Validate question data
                    if not question_text and not question_image_url:
                        current_app.logger.error(f"=== IMPORT QUESTIONS: Row {index+1} - No question text or image URL ===")
                        error_details.append(f"صف {index+2}: يجب توفير نص للسؤال أو صورة له.")
                        continue
                    
                    # Extract options data
                    options_data = []
                    for i in range(1, 5):  # Assuming 4 options
                        option_text = str(row[f"Option {i} Text"]).strip() if not pd.isna(row[f"Option {i} Text"]) else None
                        option_image_url = str(row[f"Option {i} Image URL"]).strip() if not pd.isna(row[f"Option {i} Image URL"]) else None
                        
                        if option_text or option_image_url:
                            options_data.append({
                                "option_text": option_text,
                                "image_url": option_image_url,
                                "is_correct": False  # Will set correct one later
                            })
                    
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Found {len(options_data)} options ===")
                    
                    # Validate options
                    if len(options_data) < 2:
                        current_app.logger.error(f"=== IMPORT QUESTIONS: Row {index+1} - Not enough options (minimum 2 required) ===")
                        error_details.append(f"صف {index+2}: يجب توفير خيارين صالحين على الأقل.")
                        continue
                    
                    # Set correct option
                    correct_option = row["Correct Option Number"]
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Correct option number: {correct_option} ===")
                    
                    if pd.isna(correct_option) or not isinstance(correct_option, (int, float)) or correct_option < 1 or correct_option > len(options_data):
                        current_app.logger.error(f"=== IMPORT QUESTIONS: Row {index+1} - Invalid correct option number ===")
                        error_details.append(f"صف {index+2}: رقم الإجابة الصحيحة غير صالح.")
                        continue
                    
                    correct_index = int(correct_option) - 1  # Convert to 0-based index
                    options_data[correct_index]["is_correct"] = True
                    
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Creating question in database ===")
                    
                    # Create question
                    new_question = Question(
                        question_text=question_text,
                        lesson_id=lesson_id,
                        image_url=question_image_url
                    )
                    db.session.add(new_question)
                    db.session.flush()  # Get the question ID
                    
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Question created with ID: {new_question.question_id} ===")
                    
                    # Create options
                    for opt_index, opt_data in enumerate(options_data):
                        current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Creating option {opt_index+1} ===")
                        option = Option(
                            option_text=opt_data["option_text"],
                            image_url=opt_data["image_url"],
                            is_correct=opt_data["is_correct"],
                            question_id=new_question.question_id
                        )
                        db.session.add(option)
                    
                    imported_count += 1
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Row {index+1} - Successfully processed ===")
                    
                except Exception as row_error:
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Error processing row {index+1}: {row_error} ===")
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Traceback: {traceback.format_exc()} ===")
                    error_details.append(f"صف {index+2}: {str(row_error)}")
            
            # Commit all changes if there were any successful imports
            if imported_count > 0:
                current_app.logger.info(f"=== IMPORT QUESTIONS: Committing {imported_count} questions to database ===")
                try:
                    db.session.commit()
                    current_app.logger.info(f"=== IMPORT QUESTIONS: Successfully committed {imported_count} questions ===")
                    flash(f"تم استيراد {imported_count} سؤال بنجاح!", "success")
                except Exception as commit_error:
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Error during commit: {commit_error} ===")
                    current_app.logger.error(f"=== IMPORT QUESTIONS: Traceback: {traceback.format_exc()} ===")
                    db.session.rollback()
                    flash(f"حدث خطأ أثناء حفظ الأسئلة في قاعدة البيانات: {str(commit_error)}", "danger")
                    return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
            
            # Show errors if any
            if error_details:
                current_app.logger.warning(f"=== IMPORT QUESTIONS: {len(error_details)} errors occurred during import ===")
                error_summary = f"تم استيراد {imported_count} سؤال، مع {len(error_details)} أخطاء:"
                for i, error in enumerate(error_details[:5]):  # Show first 5 errors
                    flash(error, "warning")
                if len(error_details) > 5:
                    flash(f"... و {len(error_details) - 5} أخطاء أخرى.", "warning")
                
                flash(error_summary, "danger")
                return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)
            else:
                if imported_count > 0:
                    current_app.logger.info("=== IMPORT QUESTIONS: Import completed successfully, redirecting to questions list ===")
                    return redirect(url_for("question.list_questions"))
                else:
                    current_app.logger.warning("=== IMPORT QUESTIONS: No valid questions found in file ===")
                    flash("لم يتم العثور على أسئلة صالحة للاستيراد في الملف.", "warning")
                    return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)

        except Exception as e:
            current_app.logger.error(f"=== IMPORT QUESTIONS: Unhandled exception: {e} ===")
            current_app.logger.error(f"=== IMPORT QUESTIONS: Traceback: {traceback.format_exc()} ===")
            flash(f"حدث خطأ أثناء معالجة ملف الاستيراد: {str(e)}", "danger")
            return render_template("question/import_questions.html", lessons=lessons, selected_lesson_id=lesson_id)

    # GET request: Render the import form
    current_app.logger.info("=== IMPORT QUESTIONS: GET request, rendering import form ===")
    return render_template("question/import_questions.html", lessons=lessons)

# --- END: Import Questions Route --- #

# --- START: Download Template Route (Integrated) --- #
@question_bp.route("/download_template/<format>")
@login_required
def download_template(format):
    """Generates and serves an empty template file (Excel or CSV) with headers."""
    current_app.logger.info(f"Request received to download template in {format} format.")
    
    # Create a DataFrame with only the header row
    df_template = pd.DataFrame(columns=EXPECTED_IMPORT_COLUMNS)
    
    output = io.BytesIO()
    filename = "question_import_template"
    mimetype = ""

    try:
        if format == "xlsx":
            df_template.to_excel(output, index=False, engine='openpyxl')
            filename += ".xlsx"
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            current_app.logger.debug("Generated Excel template in memory.")
        elif format == "csv":
            df_template.to_csv(output, index=False, encoding='utf-8-sig') # utf-8-sig for better Excel compatibility
            filename += ".csv"
            mimetype = "text/csv"
            current_app.logger.debug("Generated CSV template in memory.")
        else:
            flash("تنسيق الملف المطلوب غير صالح.", "danger")
            return redirect(url_for('question.import_questions'))

        output.seek(0)
        current_app.logger.info(f"Sending template file: {filename}")
        return send_file(
            output, 
            mimetype=mimetype, 
            as_attachment=True, 
            download_name=filename
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating or sending template file ({format}): {e}")
        flash(f"حدث خطأ أثناء إنشاء ملف القالب: {e}", "danger")
        return redirect(url_for('question.import_questions'))

# --- END: Download Template Route --- #
