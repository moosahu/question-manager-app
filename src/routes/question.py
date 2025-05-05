# src/routes/question.py (Updated with ImageKit.io integration)

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

# --- Updated save_upload function for ImageKit.io --- #
def save_upload(file, subfolder="questions"):
    if not (file and file.filename and allowed_file(file.filename)):
        if file and file.filename:
            current_app.logger.warning(f"File type not allowed or invalid file: {file.filename}")
        return None

    # Read ImageKit credentials from environment variables
    private_key = os.environ.get('IMAGEKIT_PRIVATE_KEY')
    public_key = os.environ.get('IMAGEKIT_PUBLIC_KEY')
    url_endpoint = os.environ.get('IMAGEKIT_URL_ENDPOINT')

    if not all([private_key, public_key, url_endpoint]):
        current_app.logger.error("ImageKit environment variables not configured.")
        flash("خطأ في إعدادات رفع الصور على الخادم.", "danger")
        return None

    try:
        # Initialize ImageKit client
        imagekit = ImageKit(
            private_key=private_key,
            public_key=public_key,
            url_endpoint=url_endpoint
        )

        # Generate a unique filename for ImageKit
        original_filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{original_filename}"
        safe_subfolder = secure_filename(subfolder) if subfolder else "default"

        # Read file content for upload
        file_content = file.read()
        file.seek(0) # Reset file pointer if needed elsewhere

        # Upload the file to ImageKit
        upload_response = imagekit.upload(
            file=file_content,
            file_name=unique_filename,
            options={
                "folder": f"/{safe_subfolder}/", # Specify the folder in ImageKit
                "is_private_file": False, # Make files public by default
                "use_unique_file_name": False # We are generating a unique name
            }
        )

        # Check response and return the URL
        if upload_response.response_metadata.http_status_code == 200 and upload_response.url:
            image_url = upload_response.url
            current_app.logger.info(f"File uploaded successfully to ImageKit: {image_url}")
            return image_url
        else:
            current_app.logger.error(f"ImageKit upload failed. Status: {upload_response.response_metadata.http_status_code}, Response: {upload_response.response_metadata.raw}")
            flash("حدث خطأ أثناء رفع الصورة إلى خدمة التخزين.", "danger")
            return None

    except Exception as e:
        current_app.logger.error(f"Error during ImageKit upload: {e}", exc_info=True)
        flash("حدث خطأ غير متوقع أثناء عملية رفع الصورة.", "danger")
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
        # Pass the original question objects to the template
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

        # --- Duplicate Check (Optional but recommended) ---
        # Consider if duplicate check needs adjustment based on image URLs
        # if question_text:
        #     try:
        #         existing_question = Question.query.filter_by(question_text=question_text, lesson_id=lesson_id).first()
        #         if existing_question:
        #             flash("هذا السؤال (بنفس النص والدرس) موجود بالفعل. لم يتم الحفظ.", "warning")
        #             # Repopulate form data as above
        #             return render_template("question/form.html", ...)
        #     except Exception as query_error:
        #         current_app.logger.exception("Error during duplicate question check.")
        #         flash("حدث خطأ أثناء التحقق من تكرار السؤال.", "danger")
        #         # Repopulate form data as above
        #         return render_template("question/form.html", ...)

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
            error_messages.append("يجب توفير نص للسؤال أو صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        
        # Check if any options were submitted before requiring a correct one
        option_keys_check = [key for key in request.form if key.startswith("option_text_")]
        option_files_check = [key for key in request.files if key.startswith("option_image_")]
        if correct_option_index_str is None and (option_keys_check or option_files_check):
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
        max_submitted_index = -1

        # Determine the highest index submitted
        for key in list(request.form.keys()) + list(request.files.keys()):
            if key.startswith(("option_text_", "option_image_", "option_id_")):
                try:
                    index_str = key.split("_")[-1]
                    max_submitted_index = max(max_submitted_index, int(index_str))
                except (ValueError, IndexError):
                    continue

        # Iterate through all possible indices up to the max submitted
        for i in range(max_submitted_index + 1):
            index_str = str(i)
            option_id = request.form.get(f"option_id_{index_str}") # Existing option ID
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            remove_option_image = request.form.get(f"remove_option_image_{index_str}") == 'on'
            
            # Find the corresponding existing option if ID is provided
            existing_option = None
            if option_id:
                try:
                    opt_id_int = int(option_id)
                    existing_option = next((opt for opt in question.options if opt.option_id == opt_id_int), None)
                    option_ids_submitted.add(opt_id_int) # Track submitted existing IDs
                except ValueError:
                    option_id = None # Treat as new if ID is invalid
            
            existing_image_url = existing_option.image_url if existing_option else None

            # Use the updated save_upload function
            new_option_image_path = save_upload(option_image_file, subfolder="options")
            final_option_image_path = existing_image_url # Start with existing

            if new_option_image_path:
                # TODO: Delete old image from ImageKit if existing_image_url exists?
                final_option_image_path = new_option_image_path
            elif remove_option_image:
                # TODO: Delete old image from ImageKit if existing_image_url exists?
                final_option_image_path = None

            # Only consider the option if it has text OR an image
            if option_text or final_option_image_path:
                is_correct = (correct_option_index_str is not None and i == correct_option_index)
                options_data_from_form.append({
                    "index": i, # Original index from form
                    "option_id": int(option_id) if option_id else None,
                    "option_text": option_text,
                    "image_url": final_option_image_path,
                    "is_correct": is_correct
                })

        # --- Further Validation --- #
        if len(options_data_from_form) < 2:
            error_messages.append("يجب توفير خيارين صالحين على الأقل (بنص أو صورة).")
        # Adjust validation: Check if correct_option_index is valid within the *processed* options
        if correct_option_index_str is not None and correct_option_index >= len(options_data_from_form):
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        # --- Handle Validation Errors --- #
        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form data correctly for rendering
            form_data = request.form.to_dict()
            form_data['question_text'] = question_text # Use updated text
            form_data['lesson_id'] = lesson_id # Use updated lesson_id
            form_data['image_url'] = final_q_image_path # Use potentially updated image URL
            
            # Reconstruct options with potential image URLs for display
            repop_options = []
            for i in range(max_submitted_index + 1):
                 idx_str = str(i)
                 opt_id = request.form.get(f"option_id_{idx_str}")
                 opt_text = request.form.get(f"option_text_{idx_str}", "")
                 # Find if this option was processed and has an image URL
                 processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
                 img_url = processed_opt["image_url"] if processed_opt else None
                 repop_options.append({"option_id": opt_id, "option_text": opt_text, "image_url": img_url})
            form_data["options_repop"] = repop_options
            form_data["correct_option_repop"] = correct_option_index_str
            
            # Pass the modified form_data as 'question' to the template
            return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", lessons=lessons, question=form_data, submit_text="حفظ التعديلات")

        # --- Database Operations --- #
        try:
            # Update Question fields
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_path # URL from ImageKit or None

            # --- Update/Add/Delete Options --- #
            existing_option_ids = {opt.option_id for opt in question.options}
            
            # Update existing or add new options
            for opt_data in options_data_from_form:
                if opt_data["option_id"] is not None and opt_data["option_id"] in existing_option_ids:
                    # Update existing option
                    opt_to_update = next((opt for opt in question.options if opt.option_id == opt_data["option_id"]), None)
                    if opt_to_update:
                        opt_to_update.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                        opt_to_update.image_url = opt_data["image_url"] # URL from ImageKit or None
                        opt_to_update.is_correct = opt_data["is_correct"]
                elif opt_data["option_id"] is None: # Should be a new option
                    # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)
            
            # Delete options that were removed from the form
            options_to_delete_ids = existing_option_ids - option_ids_submitted
            if options_to_delete_ids:
                # TODO: Delete images from ImageKit for deleted options?
                Option.query.filter(Option.option_id.in_(options_to_delete_ids)).delete(synchronize_session=False)

            # Commit the transaction
            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully. Question {question_id} and options updated.")
            flash("تم حفظ التعديلات بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء حفظ التعديلات.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء حفظ التعديلات.", "danger")
        
        # If errors occurred, repopulate form data for rendering (similar to validation error handling)
        form_data = request.form.to_dict()
        form_data['question_text'] = question_text
        form_data['lesson_id'] = lesson_id
        form_data['image_url'] = final_q_image_path
        repop_options = []
        for i in range(max_submitted_index + 1):
             idx_str = str(i)
             opt_id = request.form.get(f"option_id_{idx_str}")
             opt_text = request.form.get(f"option_text_{idx_str}", "")
             processed_opt = next((opt for opt in options_data_from_form if opt["index"] == i), None)
             img_url = processed_opt["image_url"] if processed_opt else None
             repop_options.append({"option_id": opt_id, "option_text": opt_text, "image_url": img_url})
        form_data["options_repop"] = repop_options
        form_data["correct_option_repop"] = correct_option_index_str
        return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", lessons=lessons, question=form_data, submit_text="حفظ التعديلات")

    # GET request - Prepare data for the form
    # Convert question object to a dictionary-like structure for the template
    question_data_for_form = {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "lesson_id": question.lesson_id,
        "image_url": question.image_url,
        "options": sorted([ # Sort options for consistent display
            {
                "option_id": opt.option_id,
                "option_text": opt.option_text,
                "image_url": opt.image_url,
                "is_correct": opt.is_correct
            }
            for opt in question.options
        ], key=lambda x: x["option_id"])
    }
    # Find the index of the correct option for the radio button
    correct_option_index_form = -1
    for i, opt in enumerate(question_data_for_form["options"]):
        if opt["is_correct"]:
            correct_option_index_form = i
            break
    question_data_for_form["correct_option_index"] = correct_option_index_form

    return render_template("question/form.html", title=f"تعديل السؤال: {question_id}", lessons=lessons, question=question_data_for_form, submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        # TODO: Delete associated images from ImageKit?
        # Delete options first due to foreign key constraint
        Option.query.filter_by(question_id=question_id).delete()
        # Delete the question
        db.session.delete(question)
        db.session.commit()
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

