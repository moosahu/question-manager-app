# ... (imports and other functions remain the same) ...

@question_bp.route("/")
@login_required
def list_questions():
    # ... (code for listing - check if explanation fields are used here, comment if needed) ...
    # Example: Comment out access if it causes errors
    # if question.explanation_image_path:
    #     question.explanation_image_path = sanitize_path(question.explanation_image_path)
    # ... (rest of the function) ...
    try:
        # Use joinedload for efficiency here as order is on Question.question_id
        questions_pagination = (Question.query.options(
                joinedload(Question.options),
                joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
            ).order_by(Question.question_id.desc())
            .paginate(page=page, per_page=per_page, error_out=False))
        current_app.logger.info(f"Database query successful. Found {len(questions_pagination.items)} questions on this page (total: {questions_pagination.total}).")

        if questions_pagination and questions_pagination.items:
            for question in questions_pagination.items:
                if question.image_url:
                    question.image_url = sanitize_path(question.image_url)
                # --- Temporarily Commented Out Usage --- #
                # if question.explanation_image_path:
                #     question.explanation_image_path = sanitize_path(question.explanation_image_path)
                # ------------------------------------- #
                if question.options:
                    for option in question.options:
                        if option.image_path:
                            option.image_path = sanitize_path(option.image_path)

        rendered_template = render_template("question/list.html", questions=questions_pagination.items, pagination=questions_pagination)
        current_app.logger.info("Template rendering successful.")
        return rendered_template

    except Exception as e:
        current_app.logger.exception("Error occurred in list_questions.")
        flash(f"حدث خطأ غير متوقع أثناء عرض قائمة الأسئلة. التفاصيل: {sanitize_path(str(e))}", "danger")
        return redirect(url_for("index"))

# ... (get_sorted_lessons remains the same) ...

@question_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_question():
    # ... (lesson loading and validation) ...
    if request.method == "POST":
        # ... (get form data, validation, duplicate check) ...
        question_text = request.form.get("question_text")
        lesson_id = request.form.get("lesson_id")
        # --- Temporarily Commented Out --- #
        # explanation = request.form.get("explanation")
        # --------------------------------- #
        correct_option_index_str = request.form.get("correct_option")

        # ... (validation) ...
        
        # File uploads
        q_image_file = request.files.get("question_image")
        # --- Temporarily Commented Out --- #
        # e_image_file = request.files.get("explanation_image")
        # --------------------------------- #
        q_image_path = save_upload(q_image_file, subfolder="questions")
        # --- Temporarily Commented Out --- #
        # e_image_path = save_upload(e_image_file, subfolder="explanations")
        # --------------------------------- #

        # Database Operations
        try:
            new_question = Question(
                question_text=question_text,
                lesson_id=lesson_id,
                image_url=q_image_path,
                # --- Temporarily Commented Out --- #
                # explanation=explanation,
                # explanation_image_path=e_image_path,
                # --------------------------------- #
                # quiz_id=... 
            )
            # ... (rest of add_question, including options and commit) ...
            db.session.add(new_question)
            db.session.flush() 
            current_app.logger.info(f"New question ID obtained: {new_question.question_id}")

            # --- Dynamic Options Processing --- #
            options_data = []
            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))
            actual_correct_option_text = None

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")

                if option_text and option_text.strip():
                    option_image_file = request.files.get(f"option_image_{index_str}")
                    option_image_path = save_upload(option_image_file, subfolder="options")
                    is_correct = (i == correct_option_index)

                    options_data.append({
                        "text": option_text.strip(),
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": new_question.question_id
                    })
                    if is_correct:
                        actual_correct_option_text = option_text.strip()

            if len(options_data) < 2:
                 current_app.logger.warning("Less than 2 valid options provided. Rolling back implicitly.")
                 flash("يجب إضافة خيارين على الأقل بنص غير فارغ.", "danger")
                 db.session.rollback()
                 return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            if correct_option_index >= len(options_data):
                current_app.logger.error(f"Invalid correct_option_index {correct_option_index} for {len(options_data)} options.")
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                db.session.rollback()
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

            current_app.logger.info(f"Adding {len(options_data)} options to the session...")
            for opt_data in options_data:
                option = Option(**opt_data)
                db.session.add(option)
            
            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully.")
                flash("تمت إضافة السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                # ... (commit error handling) ...
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ السؤال في قاعدة البيانات: {commit_error}", "danger")
                return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

        except (IntegrityError, DBAPIError) as db_error:
            # ... (db error handling) ...
            db.session.rollback()
            current_app.logger.exception(f"Database Error adding question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء إضافة السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")
        except Exception as e:
            # ... (generic error handling) ...
            db.session.rollback()
            current_app.logger.exception(f"Generic Error adding question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء إضافة السؤال: {e}", "danger")
            return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=request.form, submit_text="إضافة سؤال")

    # GET request
    return render_template("question/form.html", title="إضافة سؤال جديد", lessons=lessons, question=None, submit_text="إضافة سؤال")

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # ... (fetch question and lessons) ...
    if request.method == "POST":
        # ... (get form data, validation, duplicate check) ...
        question_text = request.form.get("question_text")
        lesson_id = request.form.get("lesson_id")
        # --- Temporarily Commented Out --- #
        # explanation = request.form.get("explanation")
        # --------------------------------- #
        correct_option_index_str = request.form.get("correct_option")

        # ... (validation) ...

        # File uploads
        q_image_file = request.files.get("question_image")
        # --- Temporarily Commented Out --- #
        # e_image_file = request.files.get("explanation_image")
        # --------------------------------- #
        
        q_image_path = question.image_url
        if q_image_file:
            # ... (save question image) ...
            new_q_path = save_upload(q_image_file, subfolder="questions")
            if new_q_path:
                q_image_path = new_q_path
            else:
                flash("فشل تحميل صورة السؤال الجديدة.", "warning")

        # --- Temporarily Commented Out --- #
        # e_image_path = question.explanation_image_path
        # if e_image_file:
        #     new_e_path = save_upload(e_image_file, subfolder="explanations")
        #     if new_e_path:
        #         e_image_path = new_e_path
        #     else:
        #         flash("فشل تحميل صورة الشرح الجديدة.", "warning")
        # --------------------------------- #

        try:
            # Update question details
            question.question_text = question_text
            question.lesson_id = lesson_id
            question.image_url = q_image_path
            # --- Temporarily Commented Out --- #
            # question.explanation = explanation
            # question.explanation_image_path = e_image_path
            # --------------------------------- #
            # question.quiz_id = ...

            # ... (rest of edit_question, including options and commit) ...
            # --- Dynamic Options Processing for Edit --- #
            existing_options_map = {opt.id: opt for opt in question.options}
            submitted_option_ids = set()
            options_to_process = [] 

            option_keys = sorted([key for key in request.form if key.startswith("option_text_")], key=lambda x: int(x.split("_")[-1]))

            for i, key in enumerate(option_keys):
                index_str = key.split("_")[-1]
                option_text = request.form.get(f"option_text_{index_str}")
                option_id_str = request.form.get(f"option_id_{index_str}")
                option_image_file = request.files.get(f"option_image_{index_str}")
                is_correct = (i == correct_option_index)

                if option_text and option_text.strip():
                    option_image_path = None 
                    existing_option = None

                    if option_id_str:
                        try:
                            option_id = int(option_id_str)
                            if option_id in existing_options_map:
                                existing_option = existing_options_map[option_id]
                                option_image_path = existing_option.image_path
                                submitted_option_ids.add(option_id)
                        except ValueError:
                            pass 

                    if option_image_file:
                        new_opt_img_path = save_upload(option_image_file, subfolder="options")
                        if new_opt_img_path:
                            option_image_path = new_opt_img_path
                        else:
                            flash(f"فشل تحميل صورة الخيار \'{option_text}\'.", "warning")

                    option_data = {
                        "text": option_text.strip(),
                        "image_path": option_image_path,
                        "is_correct": is_correct,
                        "question_id": question.question_id
                    }
                    options_to_process.append((existing_option, option_data))

            if len(options_to_process) < 2:
                flash("يجب أن يحتوي السؤال على خيارين على الأقل بنص غير فارغ.", "danger")
                db.session.rollback()
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            if correct_option_index >= len(options_to_process):
                flash("حدث خطأ في تحديد الخيار الصحيح. يرجى المحاولة مرة أخرى.", "danger")
                db.session.rollback()
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

            current_app.logger.info(f"Processing {len(options_to_process)} options for edit...")
            for existing_opt, data_dict in options_to_process:
                if existing_opt:
                    existing_opt.text = data_dict["text"]
                    existing_opt.image_path = data_dict["image_path"]
                    existing_opt.is_correct = data_dict["is_correct"]
                    current_app.logger.info(f"Updating option ID: {existing_opt.id}")
                else:
                    new_option = Option(**data_dict)
                    db.session.add(new_option)
                    current_app.logger.info(f"Adding new option with text: {data_dict['text']}")

            options_to_delete = [opt for opt_id, opt in existing_options_map.items() if opt_id not in submitted_option_ids]
            if options_to_delete:
                current_app.logger.info(f"Deleting {len(options_to_delete)} options...")
                for opt in options_to_delete:
                    db.session.delete(opt)
            
            try:
                db.session.commit()
                current_app.logger.info("Transaction committed successfully for edit.")
                flash("تم تعديل السؤال بنجاح!", "success")
                return redirect(url_for("question.list_questions"))
            except Exception as commit_error:
                # ... (commit error handling) ...
                orig_error = getattr(commit_error, 'orig', None)
                current_app.logger.exception(f"CRITICAL ERROR during commit on edit: {commit_error}. Original error: {orig_error}")
                db.session.rollback()
                flash(f"حدث خطأ فادح أثناء حفظ التعديلات: {commit_error}", "danger")
                return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

        except (IntegrityError, DBAPIError) as db_error:
            # ... (db error handling) ...
            db.session.rollback()
            current_app.logger.exception(f"Database Error editing question: {db_error}")
            flash(f"خطأ في قاعدة البيانات أثناء تعديل السؤال: {db_error}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")
        except Exception as e:
            # ... (generic error handling) ...
            db.session.rollback()
            current_app.logger.exception(f"Generic Error editing question: {e}")
            flash(f"حدث خطأ غير متوقع أثناء تعديل السؤال: {e}", "danger")
            return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

    # GET request
    # ... (render edit form) ...
    if not question.options:
         question.options = []
    return render_template("question/form.html", title="تعديل السؤال", lessons=lessons, question=question, submit_text="حفظ التعديلات")

# ... (delete_question remains the same) ...
@question_bp.route("/delete/<int:question_id>", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        db.session.delete(question)
        db.session.commit()
        flash("تم حذف السؤال بنجاح.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting question ID {question_id}: {e}")
        flash(f"حدث خطأ أثناء حذف السؤال: {e}", "danger")
    return redirect(url_for("question.list_questions"))

