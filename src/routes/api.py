# ============================================
# تعديلات API لفلترة المناهج حسب show_in_bot
# ============================================

# ========== 1. تعديل endpoint المناهج للبوت ==========
# استبدل الـ endpoint الحالي في api.py:

@api_bp.route("/courses", methods=["GET"])
def get_all_courses():
    """Returns a list of all available courses (filtered by show_in_bot for bot)."""
    logger.info("API request received for listing all courses.")
    try:
        # التحقق من مصدر الطلب - هل هو من البوت أم من لوحة التحكم
        # يمكن استخدام header أو query parameter للتمييز
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
        if show_all:
            # عرض جميع المناهج (للوحة التحكم)
            courses = Course.query.order_by(Course.order_num.asc(), Course.id).all()
        else:
            # عرض المناهج المفعلة فقط (للبوت)
            courses = Course.query.filter(Course.show_in_bot == True).order_by(Course.order_num.asc(), Course.id).all()
        
        logger.info(f"Found {len(courses)} courses.")
        formatted_courses = [{"id": c.id, "name": c.name, "show_in_bot": c.show_in_bot} for c in courses]
        return jsonify(formatted_courses)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching courses: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching courses: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


# ========== 2. إضافة endpoint جديد للبوت فقط (اختياري) ==========
# يمكنك إضافة endpoint منفصل للبوت:

@api_bp.route("/courses/bot", methods=["GET"])
def get_bot_courses():
    """Returns a list of courses visible in bot only."""
    logger.info("API request received for listing bot courses.")
    try:
        courses = Course.query.filter(Course.show_in_bot == True).order_by(Course.order_num.asc(), Course.id).all()
        logger.info(f"Found {len(courses)} bot courses.")
        formatted_courses = [{"id": c.id, "name": c.name} for c in courses]
        return jsonify(formatted_courses)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while fetching bot courses: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error while fetching bot courses: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


# ========== 3. إضافة endpoint لتغيير حالة show_in_bot ==========

@api_bp.route("/courses/<int:course_id>/toggle-bot-visibility", methods=["PUT", "POST"])
@login_required
def toggle_course_bot_visibility(course_id):
    """Toggle the show_in_bot status of a course."""
    try:
        course = Course.query.get(course_id)
        if not course:
            return jsonify({"success": False, "error": "المنهج غير موجود"}), 404
        
        # تبديل الحالة
        course.show_in_bot = not course.show_in_bot
        db.session.commit()
        
        status_text = "مفعل" if course.show_in_bot else "معطل"
        return jsonify({
            "success": True,
            "message": f"تم تغيير حالة المنهج في البوت إلى: {status_text}",
            "show_in_bot": course.show_in_bot
        })
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error toggling course bot visibility: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ========== 4. تعديل في routes لحفظ المنهج ==========
# في ملف curriculum routes، عدل دالة إضافة/تعديل المنهج:

# عند إنشاء منهج جديد:
# show_in_bot = 'show_in_bot' in request.form  # True إذا كان checkbox محدد
# course = Course(name=name, show_in_bot=show_in_bot)

# عند تعديل منهج:
# course.show_in_bot = 'show_in_bot' in request.form
