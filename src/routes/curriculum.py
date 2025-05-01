from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app # Import current_app
from flask_login import login_required

from src.models.user import db # Import db instance
from src.models.curriculum import Course, Unit, Lesson

curriculum_bp = Blueprint("curriculum", __name__, template_folder="../templates/curriculum")

# Helper function to sanitize path
def sanitize_path(path):
    if path:
        # Replace backslashes, then double slashes, then remove leading slash
        sanitized = path.replace("\\", "/").replace("//", "/")
        if sanitized.startswith("/"):
            sanitized = sanitized[1:]
        return sanitized
    return path

# --- Course Routes ---

@curriculum_bp.route("/")
@login_required
def list_courses():
    try:
        # Eager load units and lessons to avoid N+1 queries in the template
        courses = Course.query.options(
            db.joinedload(Course.units).joinedload(Unit.lessons)
        ).order_by(Course.name).all()

        # Explicitly sanitize image paths (if any) before rendering
        # Although curriculum models don't have image paths currently, this is a safeguard
        # for course in courses:
        #     if hasattr(course, 'image_path'):
        #         course.image_path = sanitize_path(course.image_path)
        #     for unit in course.units:
        #         if hasattr(unit, 'image_path'):
        #             unit.image_path = sanitize_path(unit.image_path)
        #         for lesson in unit.lessons:
        #             if hasattr(lesson, 'image_path'):
        #                 lesson.image_path = sanitize_path(lesson.image_path)

        return render_template("curriculum/list.html", courses=courses)
    except Exception as e:
        # Log the detailed error and flash a more informative message
        detailed_error = f"Error listing courses: {e}"
        current_app.logger.error(detailed_error)
        # Ensure the error message itself doesn't contain problematic characters for flashing
        safe_error_message = sanitize_path(str(e)) # Sanitize error message
        flash(f"حدث خطأ أثناء عرض قائمة المناهج. التفاصيل: {safe_error_message}", "danger")
        # Redirect to dashboard or a safe page in case of error
        return redirect(url_for("dashboard")) # Ensure dashboard route exists

@curriculum_bp.route("/courses/add", methods=["GET", "POST"])
@login_required
def add_course():
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            existing_course = Course.query.filter_by(name=name).first()
            if existing_course:
                flash("دورة بهذا الاسم موجودة بالفعل.", "warning")
            else:
                new_course = Course(name=name)
                db.session.add(new_course)
                try:
                    db.session.commit()
                    flash("تمت إضافة الدورة بنجاح!", "success")
                    return redirect(url_for("curriculum.list_courses"))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error adding course: {e}")
                    flash(f"خطأ في إضافة الدورة: {e}", "danger")
        else:
            flash("اسم الدورة لا يمكن أن يكون فارغاً.", "danger")
    # Pass request.form to retain data on failed POST
    return render_template("curriculum/course_form.html", title="إضافة دورة جديدة", course=None, submit_text="إضافة دورة")

@curriculum_bp.route("/courses/edit/<int:course_id>", methods=["GET", "POST"])
@login_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            existing_course = Course.query.filter(Course.name == name, Course.id != course_id).first()
            if existing_course:
                flash("توجد دورة أخرى بهذا الاسم بالفعل.", "warning")
            else:
                course.name = name
                try:
                    db.session.commit()
                    flash("تم تحديث الدورة بنجاح!", "success")
                    return redirect(url_for("curriculum.list_courses"))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error editing course {course_id}: {e}")
                    flash(f"خطأ في تحديث الدورة: {e}", "danger")
        else:
            flash("اسم الدورة لا يمكن أن يكون فارغاً.", "danger")
    # Pass course object for GET or failed POST
    return render_template("curriculum/course_form.html", title="تعديل الدورة", course=course, submit_text="تحديث الدورة")

@curriculum_bp.route("/courses/delete/<int:course_id>", methods=["GET"]) # Use GET for simplicity
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    try:
        # Cascade delete should handle units, lessons, and questions based on model relationships
        db.session.delete(course)
        db.session.commit()
        flash("تم حذف الدورة وجميع محتوياتها بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting course {course_id}: {e}")
        flash(f"خطأ في حذف الدورة: {e}", "danger")
    return redirect(url_for("curriculum.list_courses"))

# --- Unit Routes ---

@curriculum_bp.route("/units/add/<int:course_id>", methods=["GET", "POST"])
@login_required
def add_unit(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            new_unit = Unit(name=name, course_id=course_id)
            db.session.add(new_unit)
            try:
                db.session.commit()
                flash("تمت إضافة الوحدة بنجاح!", "success")
                return redirect(url_for("curriculum.list_courses"))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error adding unit to course {course_id}: {e}")
                flash(f"خطأ في إضافة الوحدة: {e}", "danger")
        else:
            flash("اسم الوحدة لا يمكن أن يكون فارغاً.", "danger")
    # Pass course_id for the form's hidden input
    return render_template("curriculum/unit_form.html", title=f"إضافة وحدة إلى {course.name}", unit=None, course_id=course_id, submit_text="إضافة وحدة")

@curriculum_bp.route("/units/edit/<int:unit_id>", methods=["GET", "POST"])
@login_required
def edit_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            unit.name = name
            try:
                db.session.commit()
                flash("تم تحديث الوحدة بنجاح!", "success")
                return redirect(url_for("curriculum.list_courses"))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error editing unit {unit_id}: {e}")
                flash(f"خطأ في تحديث الوحدة: {e}", "danger")
        else:
            flash("اسم الوحدة لا يمكن أن يكون فارغاً.", "danger")
    # Pass unit object and course_id
    return render_template("curriculum/unit_form.html", title=f"تعديل الوحدة {unit.name}", unit=unit, course_id=unit.course_id, submit_text="تحديث الوحدة")

@curriculum_bp.route("/units/delete/<int:unit_id>", methods=["GET"]) # Use GET for simplicity
@login_required
def delete_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    try:
        # Cascade delete should handle lessons and questions
        db.session.delete(unit)
        db.session.commit()
        flash("تم حذف الوحدة وجميع محتوياتها بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting unit {unit_id}: {e}")
        flash(f"خطأ في حذف الوحدة: {e}", "danger")
    return redirect(url_for("curriculum.list_courses"))

# --- Lesson Routes ---

@curriculum_bp.route("/lessons/add/<int:unit_id>", methods=["GET", "POST"])
@login_required
def add_lesson(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            new_lesson = Lesson(name=name, unit_id=unit_id)
            db.session.add(new_lesson)
            try:
                db.session.commit()
                flash("تمت إضافة الدرس بنجاح!", "success")
                return redirect(url_for("curriculum.list_courses"))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error adding lesson to unit {unit_id}: {e}")
                flash(f"خطأ في إضافة الدرس: {e}", "danger")
        else:
            flash("اسم الدرس لا يمكن أن يكون فارغاً.", "danger")
    # Pass unit_id for the form's hidden input
    return render_template("curriculum/lesson_form.html", title=f"إضافة درس إلى {unit.name}", lesson=None, unit_id=unit_id, submit_text="إضافة درس")

@curriculum_bp.route("/lessons/edit/<int:lesson_id>", methods=["GET", "POST"])
@login_required
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            lesson.name = name
            try:
                db.session.commit()
                flash("تم تحديث الدرس بنجاح!", "success")
                return redirect(url_for("curriculum.list_courses"))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error editing lesson {lesson_id}: {e}")
                flash(f"خطأ في تحديث الدرس: {e}", "danger")
        else:
            flash("اسم الدرس لا يمكن أن يكون فارغاً.", "danger")
    # Pass lesson object and unit_id
    return render_template("curriculum/lesson_form.html", title=f"تعديل الدرس {lesson.name}", lesson=lesson, unit_id=lesson.unit_id, submit_text="تحديث الدرس")

@curriculum_bp.route("/lessons/delete/<int:lesson_id>", methods=["GET"]) # Use GET for simplicity
@login_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    # Check if questions are associated before deleting?
    # For now, assume cascade delete handles questions if relationship is set up correctly
    try:
        db.session.delete(lesson)
        db.session.commit()
        flash("تم حذف الدرس وأسئلته بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting lesson {lesson_id}: {e}")
        flash(f"خطأ في حذف الدرس: {e}", "danger")
    return redirect(url_for("curriculum.list_courses"))

