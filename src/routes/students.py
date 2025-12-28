"""
إدارة الطلاب - Routes
يسمح للأدمن بإضافة وتعديل وحذف الطلاب
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from src.extensions import db
from src.models.student import Student
from functools import wraps

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
    search = request.args.get('search', '')
    
    if search:
        students = Student.search_students(search)
    else:
        students = Student.get_all_students()
    
    # إحصائيات
    total = Student.query.count()
    active = Student.query.filter_by(is_active=True).count()
    inactive = total - active
    
    return render_template('students/list.html', 
                         students=students,
                         search=search,
                         total=total,
                         active=active,
                         inactive=inactive)


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
    
    return jsonify({
        'success': True,
        'message': 'تم تسجيل الدخول بنجاح',
        'student': student.to_dict()
    })


# ==================== APIs المناهج للطلاب ====================

@students_bp.route('/api/courses', methods=['GET'])
def api_get_courses():
    """جلب المناهج للطالب"""
    try:
        from src.models.curriculum import Course, Unit, Lesson
        from src.models.question import Question
        
        courses = Course.query.filter_by(show_in_bot=True).all()
        
        result = []
        for c in courses:
            # حساب عدد الوحدات
            units = Unit.query.filter_by(course_id=c.id).all()
            units_count = len(units)
            
            # حساب عدد الأسئلة الإجمالي للمنهج
            questions_count = 0
            for u in units:
                lessons = Lesson.query.filter_by(unit_id=u.id).all()
                for l in lessons:
                    questions_count += Question.query.filter_by(lesson_id=l.id).count()
            
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
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/courses/<int:course_id>/units', methods=['GET'])
def api_get_units(course_id):
    """جلب الوحدات للطالب"""
    try:
        from src.models.curriculum import Unit, Lesson
        from src.models.question import Question
        
        units = Unit.query.filter_by(course_id=course_id).all()
        
        result = []
        for u in units:
            # حساب عدد الدروس
            lessons = Lesson.query.filter_by(unit_id=u.id).all()
            lessons_count = len(lessons)
            
            # حساب عدد الأسئلة الإجمالي للوحدة
            questions_count = 0
            for l in lessons:
                questions_count += Question.query.filter_by(lesson_id=l.id).count()
            
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
                        'text': o.option_text,
                        'image': o.image_url,
                        'is_correct': o.is_correct,
                    })
                    if o.is_correct:
                        correct_option_id = o.option_id
            
            result.append({
                'id': q.question_id,
                'text': q.question_text,
                'image': q.image_url,
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
                        'text': o.option_text,
                        'image': o.image_url,
                        'is_correct': o.is_correct,
                    })
                    if o.is_correct:
                        correct_option_id = o.option_id
            
            result.append({
                'id': q.question_id,
                'text': q.question_text,
                'image': q.image_url,
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
                        'text': o.option_text,
                        'image': o.image_url,
                        'is_correct': o.is_correct,
                    })
                    if o.is_correct:
                        correct_option_id = o.option_id
            
            result.append({
                'id': q.question_id,
                'text': q.question_text,
                'image': q.image_url,
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
