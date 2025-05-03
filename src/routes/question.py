# src/routes/question.py (Updated)

import os
import logging
import time
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import joinedload, contains_eager

try:
    from src.extensions import db
except ImportError:
    # This fallback might be needed if running directly or in certain structures
    try:
        from extensions import db
    except ImportError:
        # If extensions is not directly importable, try relative path from main
        # This assumes a structure where main.py and extensions.py are siblings
        # Adjust the import path based on your actual project structure
        print("Warning: Could not import db from src.extensions or extensions. Trying from main.")
        try:
            from main import db # Fallback if needed, adjust based on structure
        except ImportError:
            print("Error: Database object 'db' could not be imported.")
            # Handle the error appropriately, maybe exit or raise
            raise

# Import models - adjust path if necessary based on your structure
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

def sanitize_path(path):
    # Basic sanitization to prevent path traversal and normalize slashes
    if not path:
        return None
    # Normalize separators
    path = path.replace("\\", "/")
    # Prevent absolute paths or path traversal
    if path.startswith("/") or "../" in path:
        # Log the attempt or handle it as an error
        current_app.logger.warning(f"Attempted path traversal or absolute path: {path}")
        # Return a safe default or raise an error
        return None # Or raise ValueError("Invalid path")
    # Remove leading/trailing slashes if necessary for consistency
    path = path.strip("/")
    return path

def save_upload(file, subfolder="questions"):
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Create a unique filename to prevent overwrites and potential conflicts
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{filename}"
        
        # Ensure subfolder is safe
        safe_subfolder = secure_filename(subfolder) 
        if not safe_subfolder: # Handle cases where subfolder name is invalid
            safe_subfolder = "default_uploads"
            current_app.logger.warning(f"Invalid subfolder name '{subfolder}', using '{safe_subfolder}'.")

        # Define the base upload folder from config or default
        upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder, "uploads"))
        # Create the full directory path
        upload_dir = os.path.join(upload_folder, safe_subfolder)
        
        try:
            # Ensure the directory exists
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            # Construct the relative path for web access
            relative_path = f"uploads/{safe_subfolder}/{filename}"
            # No need to sanitize here as we constructed it safely
            current_app.logger.info(f"File saved successfully: {relative_path}")
            return relative_path
        except Exception as e:
            current_app.logger.error(f"Error saving file {filename} to {upload_dir}: {e}", exc_info=True)
            return None
    elif file and file.filename:
        current_app.logger.warning(f"File type not allowed: {file.filename}")
    return None

@question_bp.route("/")
@login_required
def list_questions():
    current_app.logger.info("Entering list_questions route.")
    page = request.args.get("page", 1, type=int)
    per_page = 10
    current_app.logger.info(f"Requesting page {page} with {per_page} items per page.")
    try:
        # Eager load related data to avoid N+1 queries
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

        # No need to sanitize paths here if they were saved correctly
        # Sanitization should happen on input (save_upload) or output if needed

        rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
        current_app.logger.info("Template rendering successful.")
        return rendered_template

    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash(f"حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة.", "danger") # Avoid exposing raw error details
        return redirect(url_for("index")) # Redirect to a safe page

def get_sorted_lessons():
    try:
        # Eager load relationships for efficiency
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
        # Don't raise the raw exception, handle it gracefully
        # Maybe return an empty list or None and let the caller handle it
        return [] # Return empty list on error

@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    lessons = get_sorted_lessons()
    if not lessons:
        # Check if the error was logged in get_sorted_lessons
        flash("حدث خطأ أثناء تحميل قائمة الدروس أو لا توجد دروس متاحة. الرجاء إضافة المناهج أولاً.", "warning")
        return redirect(url_for("curriculum.list_courses"))

    if request.method == "POST":
        current_app.logger.info("POST request received for add_question.")
        
        # --- Get Form Data --- #
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option")
        q_image_file = request.files.get("question_image")

        # --- Save Question Image --- #
        q_image_path = save_upload(q_image_file, subfolder="questions")

        # --- Validation --- #
        error_messages = []
        if not question_text and not q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو رفع صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        if correct_option_index_str is None:
            error_messages.append("يجب تحديد الإجابة الصحيحة.")
        
        correct_option_index = -1 # Default invalid index
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                     error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")

        # --- Process Options --- #
        options_data_from_form = []
        option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))
        
        for i, key in enumerate(option_keys):
            index_str = key.split("_")[-1]
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            option_image_path = save_upload(option_image_file, subfolder="options")

            # Option Validation: Must have text OR image
            if option_text or option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "index": i, # Keep track of original index for correct answer check
                    "option_text": option_text,
                    "image_url": option_image_path,
                    "is_correct": is_correct
                })
            # else: Ignore option if both text and image are empty/failed

        # --- Further Validation --- #
        if len(options_data_from_form) < 2:
            error_messages.append("يجب إضافة خيارين صالحين على الأقل (بنص أو صورة).")
        
        # Check if the selected correct_option_index corresponds to a valid option
        if correct_option_index >= len(options_data_from_form) and correct_option_index_str is not None:
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        # --- Handle Validation Errors --- #
        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Repopulate form with submitted data
            form_data = request.form.to_dict()
            form_data['options'] = options_data_from_form # Pass processed options back
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        # --- Check for Duplicate Question (Optional - based on text and lesson) --- #
        if question_text: # Only check duplicates if text is provided
            try:
                existing_question = Question.query.filter_by(question_text=question_text, lesson_id=lesson_id).first()
                if existing_question:
                    flash("هذا السؤال (بنفس النص والدرس) موجود بالفعل. لم يتم الحفظ.", "warning")
                    form_data = request.form.to_dict()
                    form_data['options'] = options_data_from_form
                    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")
            except Exception as query_error:
                current_app.logger.exception("Error during duplicate question check.")
                flash("حدث خطأ أثناء التحقق من تكرار السؤال.", "danger")
                form_data = request.form.to_dict()
                form_data['options'] = options_data_from_form
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

        # --- Create and Save Question and Options --- #
        try:
            new_question = Question(
                question_text=question_text if question_text else None, # Store None if empty
                lesson_id=lesson_id,
                image_url=q_image_path
                # quiz_id=... # Add if needed
            )
            db.session.add(new_question)
            # Flush to get the new_question.question_id for options
            db.session.flush()
            current_app.logger.info(f"New question added (pending commit) with ID: {new_question.question_id}")

            # Create Option objects
            for opt_data in options_data_from_form:
                option = Option(
                    option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                    image_url=opt_data["image_url"],
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
        
        # If commit failed, render form again with data
        form_data = request.form.to_dict()
        form_data['options'] = options_data_from_form
        return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=form_data, submit_text="إضافة سؤال")

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")


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

        # --- Get Form Data --- #
        question_text = request.form.get("text", "").strip()
        lesson_id = request.form.get("lesson_id")
        correct_option_index_str = request.form.get("correct_option") # Index based on submitted options
        q_image_file = request.files.get("question_image")
        remove_question_image = request.form.get("remove_question_image") == 'on'

        # --- Handle Question Image --- #
        new_q_image_path = save_upload(q_image_file, subfolder="questions")
        final_q_image_path = question.image_url # Start with existing
        if new_q_image_path:
            # TODO: Delete old image question.image_url if it exists?
            final_q_image_path = new_q_image_path
        elif remove_question_image:
            # TODO: Delete old image question.image_url if it exists?
            final_q_image_path = None

        # --- Basic Validation --- #
        error_messages = []
        if not question_text and not final_q_image_path:
            error_messages.append("يجب توفير نص للسؤال أو صورة له.")
        if not lesson_id:
            error_messages.append("يجب اختيار درس.")
        if correct_option_index_str is None:
             # Check if there are options being submitted. If not, maybe allow saving without correct option?
             # For now, assume correct option is always required if options exist.
             option_keys_check = [key for key in request.form if key.startswith("option_text_")]
             if option_keys_check: # Only require correct option if options are present
                 error_messages.append("يجب تحديد الإجابة الصحيحة.")

        correct_option_index = -1
        if correct_option_index_str is not None:
            try:
                correct_option_index = int(correct_option_index_str)
                if correct_option_index < 0:
                    error_messages.append("اختيار الإجابة الصحيحة غير صالح.")
            except ValueError:
                error_messages.append("اختيار الإجابة الصحيحة يجب أن يكون رقمًا.")

        # --- Process Options (More Complex for Edit) --- #
        options_data_from_form = [] # Stores data for valid options from the form
        option_ids_submitted = set() # Keep track of IDs submitted to find deleted ones
        option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))

        for i, key in enumerate(option_keys):
            index_str = key.split("_")[-1]
            option_id_str = request.form.get(f"option_id_{index_str}") # Existing option ID
            option_text = request.form.get(f"option_text_{index_str}", "").strip()
            option_image_file = request.files.get(f"option_image_{index_str}")
            remove_option_image = request.form.get(f"remove_option_image_{index_str}") == 'on'
            
            option_id = None
            if option_id_str:
                try:
                    option_id = int(option_id_str)
                    option_ids_submitted.add(option_id)
                except ValueError:
                    current_app.logger.warning(f"Invalid option_id submitted: {option_id_str}")
                    # Decide how to handle: skip this option, flash error?
                    # For now, we might ignore it if ID is invalid, but text/image might still be valid for a *new* option?
                    # Let's assume invalid ID means we skip processing this as an existing option.
                    continue 

            # Find the existing option object if ID was provided
            existing_option = None
            if option_id:
                existing_option = next((opt for opt in question.options if opt.option_id == option_id), None)

            # Handle Option Image Upload/Removal
            new_option_image_path = save_upload(option_image_file, subfolder="options")
            final_option_image_path = existing_option.image_url if existing_option else None # Start with existing
            
            if new_option_image_path:
                # TODO: Delete old image if existing_option and existing_option.image_url?
                final_option_image_path = new_option_image_path
            elif remove_option_image:
                # TODO: Delete old image if existing_option and existing_option.image_url?
                final_option_image_path = None

            # Option Validation: Must have text OR image
            if option_text or final_option_image_path:
                is_correct = (i == correct_option_index)
                options_data_from_form.append({
                    "option_id": option_id, # Will be None for new options
                    "option_text": option_text,
                    "image_url": final_option_image_path,
                    "is_correct": is_correct,
                    "existing_option_obj": existing_option # Pass the object for easier update/delete
                })
            elif existing_option: 
                 # If an existing option becomes invalid (no text/image), mark it for deletion implicitly?
                 # For now, we just don't include it in options_data_from_form, deletion handled later.
                 pass 

        # --- Further Validation --- #
        if len(options_data_from_form) < 2:
            error_messages.append("يجب أن يحتوي السؤال على خيارين صالحين على الأقل (بنص أو صورة).")
        
        # Check if the selected correct_option_index corresponds to a valid option being submitted
        if correct_option_index >= len(options_data_from_form) and correct_option_index_str is not None and len(options_data_from_form) > 0:
             error_messages.append("الخيار المحدد كصحيح غير موجود أو غير صالح.")

        # --- Handle Validation Errors --- #
        if error_messages:
            for error in error_messages:
                flash(error, "danger")
            # Need to reconstruct the state of the form for re-rendering
            # This is complex because options might have changed
            # It's often easier to just show the errors and let the user refill
            # Or pass the processed data back carefully
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات") # Pass original question for now

        # --- Check for Duplicate Question (Optional) --- #
        if question_text: # Only check if text is provided
            try:
                existing_duplicate = Question.query.filter(
                    Question.question_text == question_text,
                    Question.lesson_id == lesson_id,
                    Question.question_id != question_id # Exclude self
                ).first()
                if existing_duplicate:
                    flash("يوجد سؤال آخر بنفس النص والدرس. لا يمكن حفظ التعديل.", "warning")
                    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
            except Exception as query_error:
                current_app.logger.exception("Error during duplicate check in edit_question.")
                flash("حدث خطأ أثناء التحقق من تكرار السؤال.", "danger")
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        # --- Update Question and Options in Database --- #
        try:
            # Update Question fields
            question.question_text = question_text if question_text else None
            question.lesson_id = lesson_id
            question.image_url = final_q_image_path

            # --- Update/Add/Delete Options --- # 
            existing_option_ids = {opt.option_id for opt in question.options}
            options_to_keep_or_update_ids = set()

            for opt_data in options_data_from_form:
                option_id = opt_data["option_id"]
                if option_id: # Update existing option
                    options_to_keep_or_update_ids.add(option_id)
                    option_obj = opt_data["existing_option_obj"]
                    if option_obj: # Should always exist if ID was valid
                        option_obj.option_text = opt_data["option_text"] if opt_data["option_text"] else None
                        option_obj.image_url = opt_data["image_url"]
                        option_obj.is_correct = opt_data["is_correct"]
                        db.session.add(option_obj) # Add to session to track changes
                    else:
                         current_app.logger.error(f"Could not find existing option object for ID {option_id} during update.")
                else: # Add new option
                    new_option = Option(
                        option_text=opt_data["option_text"] if opt_data["option_text"] else None,
                        image_url=opt_data["image_url"],
                        is_correct=opt_data["is_correct"],
                        question_id=question.question_id
                    )
                    db.session.add(new_option)
            
            # Delete options that were not submitted or became invalid
            options_to_delete_ids = existing_option_ids - options_to_keep_or_update_ids
            if options_to_delete_ids:
                current_app.logger.info(f"Deleting options with IDs: {options_to_delete_ids}")
                # Fetch objects to delete
                options_to_delete = Option.query.filter(Option.option_id.in_(options_to_delete_ids)).all()
                for opt_to_delete in options_to_delete:
                     # TODO: Delete associated image file? 
                     db.session.delete(opt_to_delete)
            
            # Commit changes
            db.session.commit()
            current_app.logger.info(f"Transaction committed successfully for editing question ID: {question_id}")
            flash("تم تعديل السؤال بنجاح!", "success")
            return redirect(url_for("question.list_questions"))

        except (IntegrityError, DBAPIError) as db_error:
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question ID {question_id}: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question ID {question_id}: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال.", "danger")
        
        # If commit failed, render form again
        # Reload question data from DB in case rollback occurred
        question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
        return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # Ensure image paths are correctly formatted if needed for the template
    # (Assuming template handles relative paths correctly)
    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")


@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.options(joinedload(Question.options)).get_or_404(question_id)
    try:
        # TODO: Delete associated image files (question image and option images)
        # Need to implement logic to find and delete files from the filesystem
        # Example (needs refinement and error handling):
        # if question.image_url:
        #     try:
        #         image_path = os.path.join(current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder)), question.image_url)
        #         if os.path.exists(image_path):
        #             os.remove(image_path)
        #             current_app.logger.info(f"Deleted question image file: {image_path}")
        #     except Exception as file_del_error:
        #         current_app.logger.error(f"Error deleting question image file {question.image_url}: {file_del_error}")
        # 
        # for option in question.options:
        #     if option.image_url:
        #         try:
        #             opt_image_path = os.path.join(current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder)), option.image_url)
        #             if os.path.exists(opt_image_path):
        #                 os.remove(opt_image_path)
        #                 current_app.logger.info(f"Deleted option image file: {opt_image_path}")
        #         except Exception as file_del_error:
        #             current_app.logger.error(f"Error deleting option image file {option.image_url}: {file_del_error}")

        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح.", "success")
        current_app.logger.info(f"Successfully deleted question ID: {question_id}")
    except (IntegrityError, DBAPIError) as db_error:
        db.session.rollback()
        current_app.logger.exception(f"Database error deleting question ID {question_id}: {db_error}")
        flash("حدث خطأ في قاعدة البيانات أثناء حذف السؤال.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash("حدث خطأ غير متوقع أثناء حذف السؤال.", "danger")
        
    return redirect(url_for("question.list_questions"))

# --- Helper function to get option data for the form --- #
def get_options_for_form(question):
    """Prepares options data in a format suitable for the form template."""
    if not question or not question.options:
        return []
    options_list = []
    for i, option in enumerate(question.options):
        options_list.append({
            'id': option.option_id,
            'text': option.option_text or '', # Ensure text is string
            'image_url': option.image_url,
            'is_correct': option.is_correct,
            'index': i # Index for radio button value
        })
    return options_list

