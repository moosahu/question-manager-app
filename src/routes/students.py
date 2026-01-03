"""
إدارة الطلاب - Routes
يسمح للأدمن بإضافة وتعديل وحذف الطلاب
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from src.extensions import db
from src.models.student import Student
from functools import wraps
from src.middleware.auth_middleware import create_student_token

students_bp = Blueprint('students', __name__, url_prefix='/students')


def admin_required(f):
    """التحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('ليس لديك صلاحية الوصول لهذه الصفحة', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== صفحة قائمة الطلاب ====================
@students_bp.route('/')
@login_required
@admin_required
def list_students():
    """عرض قائمة الطلاب"""
    # استيراد RegistrationSettings من email_verification
    from src.models.email_verification import RegistrationSettings
    
    search = request.args.get('search', '')
    
    if search:
        students = Student.search_students(search)
    else:
        students = Student.get_all_students()
    
    # إحصائيات
    total = Student.query.count()
    active = Student.query.filter_by(is_active=True).count()
    inactive = total - active
    
    # جلب إعدادات التسجيل الذاتي
    registration_settings = RegistrationSettings.get_settings()
    
    return render_template('students/list.html', 
                         students=students,
                         search=search,
                         total=total,
                         active=active,
                         inactive=inactive,
                         registration_settings=registration_settings)


# ==================== إضافة طالب جديد ====================
@students_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_student():
    """إضافة طالب جديد"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        school = request.form.get('school', '').strip() or None
        grade = request.form.get('grade', '').strip() or None
        is_active = request.form.get('is_active') == 'on'
        notes = request.form.get('notes', '').strip() or None
        
        # التحقق من البيانات
        if not name or not username or not password:
            flash('الاسم واسم المستخدم وكلمة المرور مطلوبة', 'danger')
            return render_template('students/add.html')
        
        # التحقق من عدم تكرار اسم المستخدم
        if Student.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return render_template('students/add.html')
        
        # التحقق من عدم تكرار البريد
        if email and Student.query.filter_by(email=email).first():
            flash('البريد الإلكتروني موجود مسبقاً', 'danger')
            return render_template('students/add.html')
        
        # إنشاء الطالب
        student = Student(
            name=name,
            username=username,
            email=email,
            phone=phone,
            school=school,
            grade=grade,
            is_active=is_active,
            notes=notes
        )
        student.set_password(password)
        
        try:
            db.session.add(student)
            db.session.commit()
            flash(f'تم إضافة الطالب "{name}" بنجاح', 'success')
            return redirect(url_for('students.list_students'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في إضافة الطالب: {str(e)}', 'danger')
    
    return render_template('students/add.html')


# ==================== تعديل طالب ====================
@students_bp.route('/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student(student_id):
    """تعديل بيانات طالب"""
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        student.name = request.form.get('name', '').strip()
        student.email = request.form.get('email', '').strip() or None
        student.phone = request.form.get('phone', '').strip() or None
        student.school = request.form.get('school', '').strip() or None
        student.grade = request.form.get('grade', '').strip() or None
        student.is_active = request.form.get('is_active') == 'on'
        student.notes = request.form.get('notes', '').strip() or None
        
        # تغيير كلمة المرور (اختياري)
        new_password = request.form.get('password', '')
        if new_password:
            student.set_password(new_password)
        
        try:
            db.session.commit()
            flash(f'تم تحديث بيانات الطالب "{student.name}" بنجاح', 'success')
            return redirect(url_for('students.list_students'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في تحديث البيانات: {str(e)}', 'danger')
    
    return render_template('students/edit.html', student=student)


# ==================== حذف طالب ====================
@students_bp.route('/delete/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def delete_student(student_id):
    """حذف طالب"""
    student = Student.query.get_or_404(student_id)
    name = student.name
    
    try:
        db.session.delete(student)
        db.session.commit()
        flash(f'تم حذف الطالب "{name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في حذف الطالب: {str(e)}', 'danger')
    
    return redirect(url_for('students.list_students'))


# ==================== تبديل حالة الطالب ====================
@students_bp.route('/toggle/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def toggle_student(student_id):
    """تفعيل/تعطيل حساب طالب"""
    student = Student.query.get_or_404(student_id)
    student.is_active = not student.is_active
    
    try:
        db.session.commit()
        status = "مفعل" if student.is_active else "معطل"
        flash(f'تم تغيير حالة الطالب "{student.name}" إلى {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في تغيير الحالة: {str(e)}', 'danger')
    
    return redirect(url_for('students.list_students'))


# ==================== تبديل حالة التسجيل الذاتي ====================
@students_bp.route('/toggle-registration', methods=['POST'])
@login_required
@admin_required
def toggle_registration():
    """تبديل حالة التسجيل الذاتي للطلاب"""
    from src.models.email_verification import RegistrationSettings
    
    try:
        settings = RegistrationSettings.get_settings()
        new_status = not settings.is_registration_open
        
        RegistrationSettings.update_settings(
            is_open=new_status,
            admin_id=current_user.id
        )
        
        status_text = 'مفتوح' if new_status else 'مغلق'
        flash(f'تم تغيير حالة التسجيل الذاتي إلى {status_text}', 'success')
    except Exception as e:
        flash(f'خطأ في تغيير حالة التسجيل: {str(e)}', 'danger')
    
    return redirect(url_for('students.list_students'))


# ==================== حفظ إعدادات التسجيل الذاتي ====================
@students_bp.route('/save-registration-settings', methods=['POST'])
@login_required
@admin_required
def save_registration_settings():
    """حفظ إعدادات التسجيل الذاتي"""
    from src.models.email_verification import RegistrationSettings
    
    try:
        # قراءة القيم من الفورم
        require_phone = request.form.get('require_phone') == 'on'
        require_school = request.form.get('require_school') == 'on'
        auto_activate = request.form.get('auto_activate') == 'on'
        closed_message = request.form.get('closed_message', '').strip()
        
        # تحديث الإعدادات
        RegistrationSettings.update_settings(
            require_phone=require_phone,
            require_school=require_school,
            auto_activate=auto_activate,
            message=closed_message if closed_message else None,
            admin_id=current_user.id
        )
        
        flash('تم حفظ إعدادات التسجيل بنجاح', 'success')
    except Exception as e:
        flash(f'خطأ في حفظ الإعدادات: {str(e)}', 'danger')
    
    return redirect(url_for('students.list_students'))


# ==================== API للتطبيق ====================
@students_bp.route('/api/login', methods=['POST'])
def api_student_login():
    """تسجيل دخول الطالب من التطبيق"""
    data = request.get_json() or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({
            'success': False,
            'error': 'اسم المستخدم وكلمة المرور مطلوبة'
        }), 400
    
    student = Student.query.filter_by(username=username).first()
    
    if not student:
        return jsonify({
            'success': False,
            'error': 'اسم المستخدم غير موجود'
        }), 401
    
    if not student.check_password(password):
        return jsonify({
            'success': False,
            'error': 'كلمة المرور غير صحيحة'
        }), 401
    
    if not student.is_active:
        return jsonify({
            'success': False,
            'error': 'الحساب غير مفعل، تواصل مع الإدارة'
        }), 403
    
    # تحديث آخر تسجيل دخول
    student.update_last_login()
    
    # إنشاء JWT Token
    token = create_student_token(
        student_id=student.id,
        username=student.username
    )
    
    return jsonify({
        'success': True,
        'message': 'تم تسجيل الدخول بنجاح',
        'token': token,
        'student': student.to_dict()
    })


# ==================== APIs المناهج للطلاب ====================

@students_bp.route('/api/courses', methods=['GET'])
def api_get_courses():
    """جلب المناهج للطالب"""
    try:
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        from sqlalchemy import func
        
        courses = Course.query.filter_by(show_in_bot=True).all()
        
        result = []
        for c in courses:
            # حساب عدد الوحدات
            units_count = Unit.query.filter_by(course_id=c.id).count()
            
            # حساب عدد الأسئلة بـ query واحد
            questions_count = db.session.query(func.count(Question.question_id)).join(
                Lesson, Question.lesson_id == Lesson.id
            ).join(
                Unit, Lesson.unit_id == Unit.id
            ).filter(Unit.course_id == c.id).scalar() or 0
            
            result.append({
                'id': c.id,
                'name': c.name,
                'description': getattr(c, 'description', ''),
                'units_count': units_count,
                'questions_count': questions_count,
            })
        
        return jsonify({
            'success': True,
            'courses': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/courses/<int:course_id>/units', methods=['GET'])
def api_get_units(course_id):
    """جلب الوحدات للطالب"""
    try:
        from src.models.curriculum import Unit, Lesson
        from src.models.question import Question
        from sqlalchemy import func
        
        units = Unit.query.filter_by(course_id=course_id).all()
        
        result = []
        for u in units:
            # حساب عدد الدروس
            lessons_count = Lesson.query.filter_by(unit_id=u.id).count()
            
            # حساب عدد الأسئلة بـ query واحد
            questions_count = db.session.query(func.count(Question.question_id)).join(
                Lesson, Question.lesson_id == Lesson.id
            ).filter(Lesson.unit_id == u.id).scalar() or 0
            
            result.append({
                'id': u.id,
                'name': u.name,
                'course_id': u.course_id,
                'lessons_count': lessons_count,
                'questions_count': questions_count,
            })
        
        return jsonify({
            'success': True,
            'units': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/units/<int:unit_id>/lessons', methods=['GET'])
def api_get_lessons(unit_id):
    """جلب الدروس للطالب"""
    try:
        from src.models.curriculum import Lesson
        from src.models.question import Question
        
        lessons = Lesson.query.filter_by(unit_id=unit_id).all()
        
        result = []
        for l in lessons:
            # حساب عدد الأسئلة لكل درس
            questions_count = Question.query.filter_by(lesson_id=l.id).count()
            result.append({
                'id': l.id,
                'name': l.name,
                'unit_id': l.unit_id,
                'questions_count': questions_count,
            })
        
        return jsonify({
            'success': True,
            'lessons': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/lessons/<int:lesson_id>/questions', methods=['GET'])
def api_get_questions(lesson_id):
    """جلب الأسئلة للطالب"""
    try:
        from src.models.question import Question
        questions = Question.query.filter_by(lesson_id=lesson_id).all()
        
        result = []
        for q in questions:
            options_list = []
            correct_option_id = None
            
            if hasattr(q, 'options'):
                for o in sorted(q.options, key=lambda x: x.option_id):
                    options_list.append({
                        'id': o.option_id,
                        'option_text': o.option_text,
                        'image_url': o.image_url,
                        'is_correct': o.is_correct,
                    })
                    if o.is_correct:
                        correct_option_id = o.option_id
            
            result.append({
                'id': q.question_id,
                'question_text': q.question_text,
                'image_url': q.image_url,
                'options': options_list,
                'correct_option_id': correct_option_id,
            })
        
        return jsonify({
            'success': True,
            'questions': result
        })
    except Exception as e:
        import traceback
        print(f"Error in api_get_questions: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/courses/<int:course_id>/questions', methods=['GET'])
def api_get_course_questions(course_id):
    """جلب جميع أسئلة المنهج للطالب"""
    try:
        from src.models.question import Question
        from src.models.curriculum import Lesson, Unit
        
        # جلب جميع الوحدات في المنهج
        units = Unit.query.filter_by(course_id=course_id).all()
        unit_ids = [u.id for u in units]
        
        # جلب جميع الدروس في الوحدات
        lessons = Lesson.query.filter(Lesson.unit_id.in_(unit_ids)).all()
        lesson_ids = [l.id for l in lessons]
        
        # جلب جميع الأسئلة
        questions = Question.query.filter(Question.lesson_id.in_(lesson_ids)).all()
        
        result = []
        for q in questions:
            options_list = []
            correct_option_id = None
            
            if hasattr(q, 'options'):
                for o in sorted(q.options, key=lambda x: x.option_id):
                    options_list.append({
                        'id': o.option_id,
                        'option_text': o.option_text,
                        'image_url': o.image_url,
                        'is_correct': o.is_correct,
                    })
                    if o.is_correct:
                        correct_option_id = o.option_id
            
            result.append({
                'id': q.question_id,
                'question_text': q.question_text,
                'image_url': q.image_url,
                'options': options_list,
                'correct_option_id': correct_option_id,
            })
        
        return jsonify({
            'success': True,
            'questions': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/units/<int:unit_id>/questions', methods=['GET'])
def api_get_unit_questions(unit_id):
    """جلب جميع أسئلة الوحدة للطالب"""
    try:
        from src.models.question import Question
        from src.models.curriculum import Lesson
        
        # جلب جميع الدروس في الوحدة
        lessons = Lesson.query.filter_by(unit_id=unit_id).all()
        lesson_ids = [l.id for l in lessons]
        
        # جلب جميع الأسئلة
        questions = Question.query.filter(Question.lesson_id.in_(lesson_ids)).all()
        
        result = []
        for q in questions:
            options_list = []
            correct_option_id = None
            
            if hasattr(q, 'options'):
                for o in sorted(q.options, key=lambda x: x.option_id):
                    options_list.append({
                        'id': o.option_id,
                        'option_text': o.option_text,
                        'image_url': o.image_url,
                        'is_correct': o.is_correct,
                    })
                    if o.is_correct:
                        correct_option_id = o.option_id
            
            result.append({
                'id': q.question_id,
                'question_text': q.question_text,
                'image_url': q.image_url,
                'options': options_list,
                'correct_option_id': correct_option_id,
            })
        
        return jsonify({
            'success': True,
            'questions': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500



# ==================== تغيير كلمة مرور الطالب ====================
@students_bp.route("/api/change-password", methods=["POST"])
def api_change_password():
    """تغيير كلمة مرور الطالب"""
    try:
        data = request.get_json() or request.form
        username = data.get("username", "").strip()
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        
        if not username or not current_password or not new_password:
            return jsonify({
                "success": False,
                "error": "جميع الحقول مطلوبة"
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                "success": False,
                "error": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"
            }), 400
        
        # البحث عن الطالب
        student = Student.query.filter_by(username=username).first()
        
        if not student:
            return jsonify({
                "success": False,
                "error": "الطالب غير موجود"
            }), 404
        
        # التحقق من كلمة المرور الحالية
        if not student.check_password(current_password):
            return jsonify({
                "success": False,
                "error": "كلمة المرور الحالية غير صحيحة"
            }), 401
        
        # تحديث كلمة المرور
        student.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "تم تغيير كلمة المرور بنجاح"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== حفظ FCM Token للطالب ====================
@students_bp.route('/api/fcm-token', methods=['POST'])
def api_save_fcm_token():
    """حفظ FCM Token للطالب"""
    try:
        data = request.get_json() or request.form
        fcm_token = data.get('fcm_token', '').strip()
        
        if not fcm_token:
            return jsonify({
                'success': False,
                'error': 'FCM token مطلوب'
            }), 400
        
        # جلب معرف الطالب من الـ JWT token أو من البيانات
        student_id = data.get('student_id')
        username = data.get('username')
        
        # البحث عن الطالب
        if student_id:
            student = Student.query.get(student_id)
        elif username:
            student = Student.query.filter_by(username=username).first()
        else:
            return jsonify({
                'success': False,
                'error': 'معرف الطالب أو اسم المستخدم مطلوب'
            }), 400
        
        if not student:
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        # تحديث FCM Token
        student.fcm_token = fcm_token
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ FCM Token بنجاح'
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== APIs نتائج الطالب ====================

@students_bp.route('/api/results', methods=['GET'])
def api_get_results():
    """جلب نتائج الطالب"""
    try:
        # جلب student_id من الـ query parameter
        student_id = request.args.get('student_id', type=int)
        
        if not student_id:
            return jsonify({
                'success': False,
                'error': 'student_id مطلوب'
            }), 400
        
        # استيراد النموذج
        try:
            from src.models.student_result import StudentResult
        except ImportError:
            from models.student_result import StudentResult
        
        # جلب النتائج مرتبة بالأحدث
        results = StudentResult.query.filter_by(student_id=student_id)\
            .order_by(StudentResult.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'results': [r.to_dict() for r in results]
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/results/stats', methods=['GET'])
def api_get_results_stats():
    """جلب إحصائيات نتائج الطالب"""
    try:
        student_id = request.args.get('student_id', type=int)
        
        if not student_id:
            return jsonify({
                'success': False,
                'error': 'student_id مطلوب'
            }), 400
        
        try:
            from src.models.student_result import StudentResult
        except ImportError:
            from models.student_result import StudentResult
        
        from sqlalchemy import func
        
        # إجمالي الاختبارات
        total_quizzes = StudentResult.query.filter_by(student_id=student_id).count()
        
        # متوسط النسبة
        avg_score = db.session.query(func.avg(StudentResult.score_percentage))\
            .filter(StudentResult.student_id == student_id).scalar() or 0
        
        # إجمالي الأسئلة المحلولة
        total_questions = db.session.query(func.sum(StudentResult.total_questions))\
            .filter(StudentResult.student_id == student_id).scalar() or 0
        
        # إجمالي الإجابات الصحيحة
        total_correct = db.session.query(func.sum(StudentResult.correct_answers))\
            .filter(StudentResult.student_id == student_id).scalar() or 0
        
        # أفضل نتيجة
        best_score = db.session.query(func.max(StudentResult.score_percentage))\
            .filter(StudentResult.student_id == student_id).scalar() or 0
        
        # آخر 7 نتائج للرسم البياني
        recent_results = StudentResult.query.filter_by(student_id=student_id)\
            .order_by(StudentResult.created_at.desc()).limit(7).all()
        
        chart_data = [{
            'date': r.created_at.strftime('%m/%d') if r.created_at else '',
            'score': r.score_percentage
        } for r in reversed(recent_results)]
        
        return jsonify({
            'success': True,
            'stats': {
                'total_quizzes': total_quizzes,
                'avg_score': round(avg_score, 1),
                'total_questions': total_questions,
                'total_correct': total_correct,
                'best_score': round(best_score, 1),
                'chart_data': chart_data
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/results', methods=['POST'])
def api_save_result():
    """حفظ نتيجة اختبار الطالب"""
    try:
        data = request.get_json() or request.form
        
        student_id = data.get('student_id')
        if not student_id:
            return jsonify({
                'success': False,
                'error': 'student_id مطلوب'
            }), 400
        
        try:
            from src.models.student_result import StudentResult
        except ImportError:
            from models.student_result import StudentResult
        
        # إنشاء سجل جديد
        result = StudentResult(
            student_id=student_id,
            quiz_type=data.get('quiz_type', 'lesson'),
            course_id=data.get('course_id'),
            unit_id=data.get('unit_id'),
            lesson_id=data.get('lesson_id'),
            quiz_name=data.get('quiz_name', 'اختبار'),
            total_questions=data.get('total_questions', 0),
            correct_answers=data.get('correct_answers', 0),
            wrong_answers=data.get('wrong_answers', 0),
            score_percentage=data.get('score_percentage', 0.0),
            time_spent=data.get('time_spent'),
        )
        
        db.session.add(result)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ النتيجة بنجاح',
            'result_id': result.id
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
