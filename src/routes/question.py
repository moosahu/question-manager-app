# تعديل دالة edit_question في ملف question.py

@question_bp.route("/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    # استرجاع السؤال مع الخيارات والدرس والوحدة والدورة
    question = Question.query.options(
        joinedload(Question.options),
        joinedload(Question.lesson).joinedload(Lesson.unit).joinedload(Unit.course)
    ).get_or_404(question_id)
    
    lessons = get_sorted_lessons()
    if not lessons:
        flash("حدث خطأ أثناء تحميل قائمة الدروس.", "danger")
        return redirect(url_for("question.list_questions"))

    if request.method == "POST":
        current_app.logger.info(f"POST request received for edit_question ID: {question_id}")
        original_lesson_id = question.lesson_id

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
            # تجهيز بيانات السؤال للعرض في القالب
            question_data = prepare_question_data_for_template(question)
            return render_template("question/form_updated_fixed.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question_data, submit_text="حفظ التعديلات")

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
        
        # تجهيز بيانات السؤال للعرض في القالب
        question_data = prepare_question_data_for_template(question)
        return render_template("question/form_updated_fixed.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question_data, submit_text="حفظ التعديلات")

    # GET request
    # تجهيز بيانات السؤال للعرض في القالب
    question_data = prepare_question_data_for_template(question)
    return render_template("question/form_updated_fixed.html", title=f"تعديل السؤال #{question.question_id}", lessons=lessons, question=question_data, submit_text="حفظ التعديلات")

# دالة مساعدة لتجهيز بيانات السؤال للعرض في القالب
def prepare_question_data_for_template(question):
    """تجهيز بيانات السؤال للعرض في القالب بما في ذلك معلومات الدورة والوحدة والدرس"""
    options_for_form = []
    correct_option_index = None
    for i, option in enumerate(sorted(question.options, key=lambda o: o.option_id)):
        if option.is_correct:
            correct_option_index = i
        options_for_form.append({
            "option_text": option.option_text,
            "image_url": option.image_url,
            "option_id": option.option_id
        })
    
    # تجهيز بيانات السؤال مع معلومات الدورة والوحدة والدرس
    question_data = {
        "question_id": question.question_id,
        "text": question.question_text,
        "lesson_id": question.lesson_id,
        "image_url": question.image_url,
        "options": options_for_form,
        "correct_option_index": correct_option_index,
        "lesson": {
            "id": question.lesson_id,
            "name": question.lesson.name if question.lesson else "",
            "unit": {
                "id": question.lesson.unit_id if question.lesson and question.lesson.unit else "",
                "name": question.lesson.unit.name if question.lesson and question.lesson.unit else "",
                "course_id": question.lesson.unit.course_id if question.lesson and question.lesson.unit else "",
                "course": {
                    "id": question.lesson.unit.course_id if question.lesson and question.lesson.unit else "",
                    "name": question.lesson.unit.course.name if question.lesson and question.lesson.unit and question.lesson.unit.course else ""
                }
            }
        }
    }
    
    return question_data
