from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, make_response # أضفت make_response
from flask_login import login_required
from flask_wtf import FlaskForm
import json # أضفت استيراد json
import time # أضفت استيراد time للتعامل مع الطوابع الزمنية
import logging # أضفت استيراد logging للسجلات التفصيلية

from src.models.user import db # Import db instance
from src.models.curriculum import Course, Unit, Lesson

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

curriculum_bp = Blueprint("curriculum", __name__, template_folder="../templates/curriculum")

# دالة مساعدة لإضافة تعليمات منع التخزين المؤقت
def add_no_cache_headers(response):
    """
    إضافة تعليمات لمنع التخزين المؤقت في رؤوس HTTP
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# دالة مساعدة لإعادة تعيين قيم الترتيب
def reset_order_nums(entity_type, parent_id=None):
    """
    إعادة تعيين قيم الترتيب للمناهج أو الوحدات أو الدروس
    
    Args:
        entity_type: نوع الكيان (course/unit/lesson)
        parent_id: معرف الكيان الأب (اختياري)
    """
    try:
        if entity_type == "course":
            # إعادة تعيين قيم الترتيب للمناهج
            courses = Course.query.order_by(Course.name).all()
            for i, course in enumerate(courses):
                course.order_num = (i + 1) * 10
            logger.info(f"Reset order numbers for {len(courses)} courses")
        elif entity_type == "unit" and parent_id:
            # إعادة تعيين قيم الترتيب للوحدات ضمن منهج محدد
            units = Unit.query.filter_by(course_id=parent_id).order_by(Unit.name).all()
            for i, unit in enumerate(units):
                unit.order_num = (i + 1) * 10
            logger.info(f"Reset order numbers for {len(units)} units in course {parent_id}")
        elif entity_type == "lesson" and parent_id:
            # إعادة تعيين قيم الترتيب للدروس ضمن وحدة محددة
            lessons = Lesson.query.filter_by(unit_id=parent_id).order_by(Lesson.name).all()
            for i, lesson in enumerate(lessons):
                lesson.order_num = (i + 1) * 10
            logger.info(f"Reset order numbers for {len(lessons)} lessons in unit {parent_id}")
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting order numbers for {entity_type}: {e}")
        return False

@curriculum_bp.route("/update_bulk_order", methods=["POST"])
@login_required
def update_bulk_order():
    """
    تحديث ترتيب مجموعة من العناصر (مناهج، وحدات، دروس) دفعة واحدة
    يستخدم مع وظيفة السحب والإفلات في واجهة المستخدم
    """
    try:
        # دعم كلا من parent_id و id للتوافق مع الواجهة الأمامية
        item_type = request.form.get('type')
        parent_id = request.form.get('parent_id') or request.form.get('id')
        new_order = json.loads(request.form.get('new_order', '[]'))
        
        logger.info(f"Bulk order update request: type={item_type}, parent_id={parent_id}, new_order={new_order}")
        
        # التحقق من وجود نوع العنصر
        if not item_type:
            logger.warning("No item type provided")
            return jsonify({"success": False, "error": "نوع العنصر مطلوب"}), 400
        
        if not new_order:
            logger.warning("No new order provided")
            return jsonify({"success": False, "error": "لم يتم توفير ترتيب جديد"}), 400
        
        # تحديد النموذج المناسب بناءً على نوع العنصر
        if item_type == "course":
            model = Course
            parent_id = None
        elif item_type == "unit":
            model = Unit
            parent_id = int(parent_id) if parent_id else None
        elif item_type == "lesson":
            model = Lesson
            parent_id = int(parent_id) if parent_id else None
        else:
            logger.warning(f"Invalid item type: {item_type}")
            return jsonify({"success": False, "error": "نوع عنصر غير صالح"}), 400
        
        # تحديث الترتيب لجميع العناصر
        updated_count = 0
        for index, id_str in enumerate(new_order):
            try:
                item_id_int = int(id_str)
                
                # البحث عن العنصر مع التحقق من parent_id إذا لزم الأمر
                if item_type == "course":
                    item = model.query.get(item_id_int)
                elif item_type == "unit":
                    item = model.query.filter_by(id=item_id_int, course_id=parent_id).first()
                elif item_type == "lesson":
                    item = model.query.filter_by(id=item_id_int, unit_id=parent_id).first()
                
                if item:
                    # تعيين ترتيب جديد بمضاعفات 10 للسماح بإدراج عناصر بينها لاحقاً
                    old_order = item.order_num
                    item.order_num = (index + 1) * 10
                    updated_count += 1
                    logger.info(f"Updated {item_type} {item_id_int} order: {old_order} -> {item.order_num}")
                else:
                    logger.warning(f"{item_type.capitalize()} with ID {item_id_int} not found")
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting ID {id_str} to integer: {e}")
                continue
        
        # التأكد من تنفيذ التغييرات في قاعدة البيانات
        db.session.flush()
        db.session.commit()
        
        logger.info(f"Bulk order updated successfully: type={item_type}, parent_id={parent_id}, updated={updated_count} items")
        
        # إضافة تعليمات لمنع التخزين المؤقت
        response = jsonify({
            "success": True, 
            "timestamp": int(time.time() * 1000),
            "message": f"تم تحديث ترتيب {updated_count} عنصر من نوع {item_type} بنجاح",
            "updated_count": updated_count
        })
        return add_no_cache_headers(response)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating bulk order: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


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
        # التحقق من وجود قيم ترتيب صحيحة للمناهج
        courses_with_zero_order = Course.query.filter_by(order_num=0).count()
        if courses_with_zero_order > 0:
            logger.info(f"Found {courses_with_zero_order} courses with order_num=0, resetting order numbers")
            reset_order_nums("course")
        
        # Eager load units and lessons to avoid N+1 queries in the template
        courses = Course.query.options(
            db.joinedload(Course.units).joinedload(Unit.lessons)
        ).order_by(Course.order_num.asc(), Course.name).all()
        
        # التحقق من وجود قيم ترتيب صحيحة للوحدات والدروس
        for course in courses:
            units_with_zero_order = Unit.query.filter_by(course_id=course.id, order_num=0).count()
            if units_with_zero_order > 0:
                logger.info(f"Found {units_with_zero_order} units with order_num=0 in course {course.id}, resetting order numbers")
                reset_order_nums("unit", course.id)
            
            for unit in course.units:
                lessons_with_zero_order = Lesson.query.filter_by(unit_id=unit.id, order_num=0).count()
                if lessons_with_zero_order > 0:
                    logger.info(f"Found {lessons_with_zero_order} lessons with order_num=0 in unit {unit.id}, resetting order numbers")
                    reset_order_nums("lesson", unit.id)
        
        # إعادة تحميل المناهج بعد إعادة تعيين قيم الترتيب
        courses = Course.query.options(
            db.joinedload(Course.units).joinedload(Unit.lessons)
        ).order_by(Course.order_num.asc(), Course.name).all()

        # إنشاء نموذج فارغ لتوفير رمز CSRF
        form = FlaskForm()
        
        # إضافة سجل تفصيلي
        logger.info(f"Listing {len(courses)} courses")
        
        # إنشاء استجابة مع تعليمات لمنع التخزين المؤقت
        response = make_response(render_template("curriculum/list.html", courses=courses, form=form))
        return add_no_cache_headers(response)
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
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
    if request.method == "POST":
        name = request.form.get("name")
        show_in_bot = 'show_in_bot' in request.form  # True إذا كان checkbox محدد
        if name:
            existing_course = Course.query.filter_by(name=name).first()
            if existing_course:
                flash("المنهج بهذا الاسم موجودة بالفعل.", "warning")
            else:
                # حساب أعلى قيمة ترتيب موجودة وإضافة 10 إليها
                max_order = db.session.query(db.func.max(Course.order_num)).scalar() or 0
                new_course = Course(name=name, order_num=max_order + 10, show_in_bot=show_in_bot)
                db.session.add(new_course)
                try:
                    db.session.commit()
                    flash("تمت إضافة المنهج بنجاح!", "success")
                    return redirect(url_for("curriculum.list_courses"))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error adding course: {e}")
                    flash(f"خطأ في إضافة المنهج: {e}", "danger")
        else:
            flash("اسم المنهج لا يمكن أن يكون فارغاً.", "danger")
    return render_template("curriculum/course_form.html", title="إضافة منهج جديد", course=None, submit_text="إضافة منهج", form=form)

@curriculum_bp.route("/courses/edit/<int:course_id>", methods=["GET", "POST"])
@login_required
def edit_course(course_id):
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        name = request.form.get("name")
        show_in_bot = 'show_in_bot' in request.form  # True إذا كان checkbox محدد
        if name:
            existing_course = Course.query.filter(Course.name == name, Course.id != course_id).first()
            if existing_course:
                flash("يوجد منهج آخر بهذا الاسم بالفعل.", "warning")
            else:
                course.name = name
                course.show_in_bot = show_in_bot
                try:
                    db.session.commit()
                    flash("تم تحديث المنهج بنجاح!", "success")
                    return redirect(url_for("curriculum.list_courses"))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error editing course {course_id}: {e}")
                    flash(f"خطأ في تحديث المنهج: {e}", "danger")
        else:
            flash("اسم المنهج لا يمكن أن يكون فارغاً.", "danger")
    # Pass course object for GET or failed POST
    return render_template("curriculum/course_form.html", title="تعديل المنهج", course=course, submit_text="تحديث المنهج", form=form)

@curriculum_bp.route("/courses/delete/<int:course_id>", methods=["GET"]) # Use GET for simplicity
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    try:
        # Cascade delete should handle units, lessons, and questions based on model relationships
        db.session.delete(course)
        db.session.commit()
        flash("تم حذف المنهج وجميع محتوياتها بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting course {course_id}: {e}")
        flash(f"خطأ في حذف المنهج: {e}", "danger")
    return redirect(url_for("curriculum.list_courses"))

# --- مسارات تحديث ترتيب المناهج ---
@curriculum_bp.route("/courses/order/<int:course_id>/<string:direction>", methods=["POST"])
@login_required
def update_course_order(course_id, direction):
    logger.info(f"Updating course {course_id} order: direction={direction}")
    
    course = Course.query.get_or_404(course_id)
    
    # التحقق من وجود قيم ترتيب صحيحة للمناهج
    courses_with_zero_order = Course.query.filter_by(order_num=0).count()
    if courses_with_zero_order > 0:
        logger.info(f"Found {courses_with_zero_order} courses with order_num=0, resetting order numbers")
        reset_order_nums("course")
        # إعادة تحميل المنهج بعد إعادة تعيين قيم الترتيب
        course = Course.query.get_or_404(course_id)
    
    if direction == "up":
        # البحث عن المنهج الذي يسبق هذا المنهج في الترتيب
        prev_course = Course.query.filter(Course.order_num < course.order_num).order_by(Course.order_num.desc()).first()
        if prev_course:
            # تبديل الترتيب
            logger.info(f"Swapping course {course_id} (order={course.order_num}) with course {prev_course.id} (order={prev_course.order_num})")
            temp_order = prev_course.order_num
            prev_course.order_num = course.order_num
            course.order_num = temp_order
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.flush()
            db.session.commit()
            
            # إضافة سجل تفصيلي
            logger.info(f"Course {course_id} moved up. New order: {course.order_num}")
        else:
            logger.warning(f"No previous course found for course {course_id}")
    elif direction == "down":
        # البحث عن المنهج الذي يلي هذا المنهج في الترتيب
        next_course = Course.query.filter(Course.order_num > course.order_num).order_by(Course.order_num).first()
        if next_course:
            # تبديل الترتيب
            logger.info(f"Swapping course {course_id} (order={course.order_num}) with course {next_course.id} (order={next_course.order_num})")
            temp_order = next_course.order_num
            next_course.order_num = course.order_num
            course.order_num = temp_order
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.flush()
            db.session.commit()
            
            # إضافة سجل تفصيلي
            logger.info(f"Course {course_id} moved down. New order: {course.order_num}")
        else:
            logger.warning(f"No next course found for course {course_id}")
    
    try:
        # إذا كان الطلب من AJAX، أعد استجابة JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({
                "success": True, 
                "timestamp": int(time.time() * 1000),
                "message": f"Course {course_id} order updated successfully",
                "new_order": course.order_num
            })
            return add_no_cache_headers(response)
            
        flash("تم تحديث ترتيب المنهج بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating course order {course_id}: {e}")
        
        # إذا كان الطلب من AJAX، أعد استجابة JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": str(e)})
            
        flash(f"خطأ في تحديث ترتيب المنهج: {e}", "danger")
    
    return redirect(url_for("curriculum.list_courses"))

# --- API Routes for Bot Visibility ---

@curriculum_bp.route("/api/v1/courses/<int:course_id>/toggle-bot-visibility", methods=["POST"])
@login_required
def toggle_bot_visibility(course_id):
    """
    API endpoint لتبديل حالة ظهور المنهج في البوت
    """
    try:
        course = Course.query.get_or_404(course_id)
        
        # تبديل حالة البوت
        course.show_in_bot = not course.show_in_bot
        
        db.session.commit()
        
        logger.info(f"Course {course_id} bot visibility toggled to {course.show_in_bot}")
        
        response = jsonify({
            "success": True,
            "show_in_bot": course.show_in_bot,
            "message": f"تم {'تفعيل' if course.show_in_bot else 'إيقاف'} ظهور المنهج في البوت بنجاح"
        })
        return add_no_cache_headers(response)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling bot visibility for course {course_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --- Unit Routes ---

@curriculum_bp.route("/units/add/<int:course_id>", methods=["GET", "POST"])
@login_required
def add_unit(course_id):
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            # حساب أعلى قيمة ترتيب موجودة في الوحدات لهذا المنهج وإضافة 10 إليها
            max_order = db.session.query(db.func.max(Unit.order_num)).filter(Unit.course_id == course_id).scalar() or 0
            new_unit = Unit(name=name, course_id=course_id, order_num=max_order + 10)
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
    return render_template("curriculum/unit_form.html", title=f"إضافة وحدة إلى {course.name}", unit=None, course_id=course_id, submit_text="إضافة وحدة", form=form)

@curriculum_bp.route("/units/edit/<int:unit_id>", methods=["GET", "POST"])
@login_required
def edit_unit(unit_id):
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
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
    return render_template("curriculum/unit_form.html", title=f"تعديل الوحدة {unit.name}", unit=unit, course_id=unit.course_id, submit_text="تحديث الوحدة", form=form)

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

# --- مسارات تحديث ترتيب الوحدات ---
@curriculum_bp.route("/units/order/<int:unit_id>/<string:direction>", methods=["POST"])
@login_required
def update_unit_order(unit_id, direction):
    logger.info(f"Updating unit {unit_id} order: direction={direction}")
    
    unit = Unit.query.get_or_404(unit_id)
    
    # التحقق من وجود قيم ترتيب صحيحة للوحدات
    units_with_zero_order = Unit.query.filter_by(course_id=unit.course_id, order_num=0).count()
    if units_with_zero_order > 0:
        logger.info(f"Found {units_with_zero_order} units with order_num=0 in course {unit.course_id}, resetting order numbers")
        reset_order_nums("unit", unit.course_id)
        # إعادة تحميل الوحدة بعد إعادة تعيين قيم الترتيب
        unit = Unit.query.get_or_404(unit_id)
    
    if direction == "up":
        # البحث عن الوحدة التي تسبق هذه الوحدة في الترتيب ضمن نفس المنهج
        prev_unit = Unit.query.filter(Unit.course_id == unit.course_id, Unit.order_num < unit.order_num).order_by(Unit.order_num.desc()).first()
        if prev_unit:
            # تبديل الترتيب
            logger.info(f"Swapping unit {unit_id} (order={unit.order_num}) with unit {prev_unit.id} (order={prev_unit.order_num})")
            temp_order = prev_unit.order_num
            prev_unit.order_num = unit.order_num
            unit.order_num = temp_order
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.flush()
            db.session.commit()
            
            # إضافة سجل تفصيلي
            logger.info(f"Unit {unit_id} moved up. New order: {unit.order_num}")
        else:
            logger.warning(f"No previous unit found for unit {unit_id} in course {unit.course_id}")
    elif direction == "down":
        # البحث عن الوحدة التي تلي هذه الوحدة في الترتيب ضمن نفس المنهج
        next_unit = Unit.query.filter(Unit.course_id == unit.course_id, Unit.order_num > unit.order_num).order_by(Unit.order_num).first()
        if next_unit:
            # تبديل الترتيب
            logger.info(f"Swapping unit {unit_id} (order={unit.order_num}) with unit {next_unit.id} (order={next_unit.order_num})")
            temp_order = next_unit.order_num
            next_unit.order_num = unit.order_num
            unit.order_num = temp_order
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.flush()
            db.session.commit()
            
            # إضافة سجل تفصيلي
            logger.info(f"Unit {unit_id} moved down. New order: {unit.order_num}")
        else:
            logger.warning(f"No next unit found for unit {unit_id} in course {unit.course_id}")
    
    try:
        # إذا كان الطلب من AJAX، أعد استجابة JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({
                "success": True, 
                "timestamp": int(time.time() * 1000),
                "message": f"Unit {unit_id} order updated successfully",
                "new_order": unit.order_num
            })
            return add_no_cache_headers(response)
            
        flash("تم تحديث ترتيب الوحدة بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating unit order {unit_id}: {e}")
        
        # إذا كان الطلب من AJAX، أعد استجابة JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": str(e)})
            
        flash(f"خطأ في تحديث ترتيب الوحدة: {e}", "danger")
    
    return redirect(url_for("curriculum.list_courses"))

# --- Lesson Routes ---

@curriculum_bp.route("/lessons/add/<int:unit_id>", methods=["GET", "POST"])
@login_required
def add_lesson(unit_id):
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
    unit = Unit.query.get_or_404(unit_id)
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            # حساب أعلى قيمة ترتيب موجودة في الدروس لهذه الوحدة وإضافة 10 إليها
            max_order = db.session.query(db.func.max(Lesson.order_num)).filter(Lesson.unit_id == unit_id).scalar() or 0
            new_lesson = Lesson(name=name, unit_id=unit_id, order_num=max_order + 10)
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
    return render_template("curriculum/lesson_form.html", title=f"إضافة درس إلى {unit.name}", lesson=None, unit_id=unit_id, submit_text="إضافة درس", form=form)

@curriculum_bp.route("/lessons/edit/<int:lesson_id>", methods=["GET", "POST"])
@login_required
def edit_lesson(lesson_id):
    # إنشاء نموذج فارغ لتوفير رمز CSRF
    form = FlaskForm()
    
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
    return render_template("curriculum/lesson_form.html", title=f"تعديل الدرس {lesson.name}", lesson=lesson, unit_id=lesson.unit_id, submit_text="تحديث الدرس", form=form)

@curriculum_bp.route("/lessons/delete/<int:lesson_id>", methods=["GET"]) # Use GET for simplicity
@login_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    try:
        # Cascade delete should handle questions
        db.session.delete(lesson)
        db.session.commit()
        flash("تم حذف الدرس وأسئلته بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting lesson {lesson_id}: {e}")
        flash(f"خطأ في حذف الدرس: {e}", "danger")
    return redirect(url_for("curriculum.list_courses"))

# --- مسارات تحديث ترتيب الدروس ---
@curriculum_bp.route("/lessons/order/<int:lesson_id>/<string:direction>", methods=["POST"])
@login_required
def update_lesson_order(lesson_id, direction):
    logger.info(f"Updating lesson {lesson_id} order: direction={direction}")
    
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # التحقق من وجود قيم ترتيب صحيحة للدروس
    lessons_with_zero_order = Lesson.query.filter_by(unit_id=lesson.unit_id, order_num=0).count()
    if lessons_with_zero_order > 0:
        logger.info(f"Found {lessons_with_zero_order} lessons with order_num=0 in unit {lesson.unit_id}, resetting order numbers")
        reset_order_nums("lesson", lesson.unit_id)
        # إعادة تحميل الدرس بعد إعادة تعيين قيم الترتيب
        lesson = Lesson.query.get_or_404(lesson_id)
    
    if direction == "up":
        # البحث عن الدرس الذي يسبق هذا الدرس في الترتيب ضمن نفس الوحدة
        prev_lesson = Lesson.query.filter(Lesson.unit_id == lesson.unit_id, Lesson.order_num < lesson.order_num).order_by(Lesson.order_num.desc()).first()
        if prev_lesson:
            # تبديل الترتيب
            logger.info(f"Swapping lesson {lesson_id} (order={lesson.order_num}) with lesson {prev_lesson.id} (order={prev_lesson.order_num})")
            temp_order = prev_lesson.order_num
            prev_lesson.order_num = lesson.order_num
            lesson.order_num = temp_order
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.flush()
            db.session.commit()
            
            # إضافة سجل تفصيلي
            logger.info(f"Lesson {lesson_id} moved up. New order: {lesson.order_num}")
        else:
            logger.warning(f"No previous lesson found for lesson {lesson_id} in unit {lesson.unit_id}")
    elif direction == "down":
        # البحث عن الدرس الذي يلي هذا الدرس في الترتيب ضمن نفس الوحدة
        next_lesson = Lesson.query.filter(Lesson.unit_id == lesson.unit_id, Lesson.order_num > lesson.order_num).order_by(Lesson.order_num).first()
        if next_lesson:
            # تبديل الترتيب
            logger.info(f"Swapping lesson {lesson_id} (order={lesson.order_num}) with lesson {next_lesson.id} (order={next_lesson.order_num})")
            temp_order = next_lesson.order_num
            next_lesson.order_num = lesson.order_num
            lesson.order_num = temp_order
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.flush()
            db.session.commit()
            
            # إضافة سجل تفصيلي
            logger.info(f"Lesson {lesson_id} moved down. New order: {lesson.order_num}")
        else:
            logger.warning(f"No next lesson found for lesson {lesson_id} in unit {lesson.unit_id}")
    
    try:
        # إذا كان الطلب من AJAX، أعد استجابة JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({
                "success": True, 
                "timestamp": int(time.time() * 1000),
                "message": f"Lesson {lesson_id} order updated successfully",
                "new_order": lesson.order_num
            })
            return add_no_cache_headers(response)
            
        flash("تم تحديث ترتيب الدرس بنجاح!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating lesson order {lesson_id}: {e}")
        
        # إذا كان الطلب من AJAX، أعد استجابة JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": str(e)})
            
        flash(f"خطأ في تحديث ترتيب الدرس: {e}", "danger")
    
    return redirect(url_for("curriculum.list_courses"))

# --- مسارات بديلة لتحريك المناهج والوحدات والدروس ---

# مسارات بديلة لتحريك المناهج
@curriculum_bp.route("/course/order/<int:course_id>/<string:direction>", methods=["POST"])
@login_required
def update_course_order_alt(course_id, direction):
    """
    مسار بديل لتحريك المناهج يتوافق مع المسارات المستخدمة في واجهة المستخدم
    """
    logger.info(f"Alternative route: Updating course {course_id} order: direction={direction}")
    return update_course_order(course_id, direction)

# مسارات بديلة لتحريك الوحدات
@curriculum_bp.route("/unit/order/<int:unit_id>/<string:direction>", methods=["POST"])
@login_required
def update_unit_order_alt(unit_id, direction):
    """
    مسار بديل لتحريك الوحدات يتوافق مع المسارات المستخدمة في واجهة المستخدم
    """
    logger.info(f"Alternative route: Updating unit {unit_id} order: direction={direction}")
    return update_unit_order(unit_id, direction)

# مسارات بديلة لتحريك الدروس
@curriculum_bp.route("/lesson/order/<int:lesson_id>/<string:direction>", methods=["POST"])
@login_required
def update_lesson_order_alt(lesson_id, direction):
    """
    مسار بديل لتحريك الدروس يتوافق مع المسارات المستخدمة في واجهة المستخدم
    """
    logger.info(f"Alternative route: Updating lesson {lesson_id} order: direction={direction}")
    return update_lesson_order(lesson_id, direction)

# --- مسارات بديلة لحذف المناهج والوحدات والدروس ---

# مسار بديل لحذف المناهج
@curriculum_bp.route("/course/delete/<int:course_id>", methods=["GET"])
@login_required
def delete_course_alt(course_id):
    """
    مسار بديل لحذف المناهج يتوافق مع المسارات المستخدمة في واجهة المستخدم
    """
    logger.info(f"Alternative route: Deleting course {course_id}")
    return delete_course(course_id)

# مسار بديل لحذف الوحدات
@curriculum_bp.route("/unit/delete/<int:unit_id>", methods=["GET"])
@login_required
def delete_unit_alt(unit_id):
    """
    مسار بديل لحذف الوحدات يتوافق مع المسارات المستخدمة في واجهة المستخدم
    """
    logger.info(f"Alternative route: Deleting unit {unit_id}")
    return delete_unit(unit_id)

# مسار بديل لحذف الدروس
@curriculum_bp.route("/lesson/delete/<int:lesson_id>", methods=["GET"])
@login_required
def delete_lesson_alt(lesson_id):
    """
    مسار بديل لحذف الدروس يتوافق مع المسارات المستخدمة في واجهة المستخدم
    """
    logger.info(f"Alternative route: Deleting lesson {lesson_id}")
    return delete_lesson(lesson_id)
