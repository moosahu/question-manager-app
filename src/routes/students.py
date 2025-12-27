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
