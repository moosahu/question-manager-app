"""
إدارة الطلاب - Routes
يسمح للأدمن بإضافة وتعديل وحذف الطلاب
✅ محدث: إضافة منطق تسجيل الدخول من جهاز واحد
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from src.extensions import db
from src.models.student import Student
from functools import wraps
from src.middleware.auth_middleware import create_student_token
from datetime import datetime
import secrets

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


# ==================== ✅ API تسجيل دخول الطالب (محدث مع منطق الجهاز الواحد) ====================
@students_bp.route('/api/login', methods=['POST'])
def api_student_login():
    """تسجيل دخول الطالب من التطبيق مع التحقق من الجهاز"""
    try:
        data = request.get_json() or request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        device_id = data.get('device_id', '')  # ✅ جديد: معرف الجهاز
        device_name = data.get('device_name', '')  # ✅ جديد: اسم الجهاز
        
        print(f"\n🔐 ========== Student Login Request ==========")
        print(f"Username: {username}")
        print(f"Device ID: {device_id}")
        print(f"Device Name: {device_name}")
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم وكلمة المرور مطلوبة'
            }), 400
        
        # البحث عن الطالب بالـ username أو email
        student = Student.query.filter(
            db.or_(
                Student.username == username,
                Student.email == username
            )
        ).first()
        
        if not student:
            print(f"❌ الطالب غير موجود: {username}")
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'
            }), 401
        
        if not student.check_password(password):
            print(f"❌ كلمة المرور خاطئة للطالب: {username}")
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'
            }), 401
        
        if not student.is_active:
            print(f"❌ حساب الطالب معطل: {username}")
            return jsonify({
                'success': False,
                'error': 'حسابك معطل. تواصل مع الإدارة'
            }), 403
        
        # ==================== ✅ التحقق من الجهاز ====================
        if device_id:
            # إذا كان الطالب مسجل من جهاز آخر
            if student.device_id and student.device_id != device_id:
                print(f"⚠️ الطالب {username} مسجل من جهاز آخر")
                print(f"   الجهاز المسجل: {student.device_id} ({student.device_name})")
                print(f"   الجهاز الحالي: {device_id} ({device_name})")
                
                return jsonify({
                    'success': False,
                    'error': 'حسابك مسجل على جهاز آخر. قم بتسجيل الخروج من الجهاز الآخر أولاً أو تواصل مع الإدارة',
                    'error_code': 'DEVICE_CONFLICT',
                    'registered_device': student.device_name or 'جهاز غير معروف',
                    'last_login': student.last_device_login.isoformat() if student.last_device_login else None
                }), 403
            
            # تحديث معلومات الجهاز
            student.device_id = device_id
            student.device_name = device_name or 'جهاز غير معروف'
            student.last_device_login = datetime.utcnow()
        
        # تحديث آخر تسجيل دخول
        student.last_login = datetime.utcnow()
        
        # إنشاء session token جديد
        session_token = secrets.token_hex(32)
        student.session_token = session_token
        
        db.session.commit()
        
        # إنشاء JWT Token
        token = create_student_token(
            student_id=student.id,
            username=student.username
        )
        
        print(f"✅ تم تسجيل دخول الطالب: {username} من جهاز: {device_name}")
        print(f"========== End Student Login ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح',
            'token': token,
            'session_token': session_token,  # ✅ جديد
            'student': student.to_dict()
        })
        
    except Exception as e:
        print(f"❌ خطأ في تسجيل الدخول: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في تسجيل الدخول'
        }), 500


# ==================== ✅ جديد: API تسجيل دخول المعلم ====================
@students_bp.route('/api/login-teacher', methods=['POST'])
def api_teacher_login():
    """تسجيل دخول المعلم من التطبيق مع التحقق من الجهاز"""
    try:
        from src.models.teacher import Teacher
        from src.middleware.auth_middleware import create_teacher_token
        
        data = request.get_json() or request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        device_id = data.get('device_id', '')
        device_name = data.get('device_name', '')
        
        print(f"\n🔐 ========== Teacher Login Request ==========")
        print(f"Username: {username}")
        print(f"Device ID: {device_id}")
        print(f"Device Name: {device_name}")
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم وكلمة المرور مطلوبة'
            }), 400
        
        # البحث عن المعلم بالـ username أو email
        teacher = Teacher.query.filter(
            db.or_(
                Teacher.username == username,
                Teacher.email == username
            )
        ).first()
        
        if not teacher:
            print(f"❌ المعلم غير موجود: {username}")
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'
            }), 401
        
        if not teacher.check_password(password):
            print(f"❌ كلمة المرور خاطئة للمعلم: {username}")
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'
            }), 401
        
        if not teacher.is_active:
            print(f"❌ حساب المعلم معطل: {username}")
            return jsonify({
                'success': False,
                'error': 'حسابك معطل. تواصل مع الإدارة'
            }), 403
        
        # ==================== التحقق من الجهاز ====================
        if device_id:
            # إذا كان المعلم مسجل من جهاز آخر
            if teacher.device_id and teacher.device_id != device_id:
                print(f"⚠️ المعلم {username} مسجل من جهاز آخر")
                print(f"   الجهاز المسجل: {teacher.device_id} ({teacher.device_name})")
                print(f"   الجهاز الحالي: {device_id} ({device_name})")
                
                return jsonify({
                    'success': False,
                    'error': 'حسابك مسجل على جهاز آخر. قم بتسجيل الخروج من الجهاز الآخر أولاً أو تواصل مع الإدارة',
                    'error_code': 'DEVICE_CONFLICT',
                    'registered_device': teacher.device_name or 'جهاز غير معروف',
                    'last_login': teacher.last_device_login.isoformat() if teacher.last_device_login else None
                }), 403
            
            # تحديث معلومات الجهاز
            teacher.device_id = device_id
            teacher.device_name = device_name or 'جهاز غير معروف'
            teacher.last_device_login = datetime.utcnow()
        
        # تحديث آخر تسجيل دخول
        teacher.last_login = datetime.utcnow()
        
        # إنشاء session token جديد
        session_token = secrets.token_hex(32)
        teacher.session_token = session_token
        
        db.session.commit()
        
        # إنشاء JWT Token
        token = create_teacher_token(
            teacher_id=teacher.id,
            username=teacher.username
        )
        
        print(f"✅ تم تسجيل دخول المعلم: {username} من جهاز: {device_name}")
        print(f"========== End Teacher Login ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح',
            'token': token,
            'session_token': session_token,
            'teacher': teacher.to_dict()
        })
        
    except Exception as e:
        print(f"❌ خطأ في تسجيل دخول المعلم: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في تسجيل الدخول'
        }), 500


# ==================== ✅ جديد: API تسجيل خروج المعلم ====================
@students_bp.route('/api/logout-teacher', methods=['POST'])
def api_teacher_logout():
    """تسجيل خروج المعلم وإزالة ربط الجهاز"""
    try:
        from src.models.teacher import Teacher
        
        data = request.get_json() or request.form
        teacher_id = data.get('teacher_id')
        device_id = data.get('device_id')
        
        print(f"\n🚪 ========== Teacher Logout Request ==========")
        print(f"Teacher ID: {teacher_id}")
        print(f"Device ID: {device_id}")
        
        if not teacher_id:
            return jsonify({
                'success': False,
                'error': 'معرف المعلم مطلوب'
            }), 400
        
        teacher = Teacher.query.get(teacher_id)
        
        if not teacher:
            return jsonify({
                'success': False,
                'error': 'المعلم غير موجود'
            }), 404
        
        # التحقق من أن الجهاز هو نفس الجهاز المسجل (للأمان)
        if device_id and teacher.device_id and teacher.device_id != device_id:
            print(f"⚠️ محاولة تسجيل خروج من جهاز مختلف")
            return jsonify({
                'success': False,
                'error': 'لا يمكنك تسجيل الخروج من جهاز مختلف'
            }), 403
        
        # إزالة ربط الجهاز
        old_device = teacher.device_name or teacher.device_id
        teacher.device_id = None
        teacher.device_name = None
        teacher.last_device_login = None
        teacher.session_token = None
        
        db.session.commit()
        
        print(f"✅ تم تسجيل خروج المعلم: {teacher.username} من جهاز: {old_device}")
        print(f"========== End Teacher Logout ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم تسجيل الخروج بنجاح'
        })
        
    except Exception as e:
        print(f"❌ خطأ في تسجيل خروج المعلم: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في تسجيل الخروج'
        }), 500


# ==================== ✅ جديد: API التحقق من جلسة المعلم ====================
@students_bp.route('/api/verify-teacher-session', methods=['POST'])
def api_verify_teacher_session():
    """التحقق من صلاحية جلسة المعلم"""
    try:
        from src.models.teacher import Teacher
        
        data = request.get_json() or request.form
        teacher_id = data.get('teacher_id')
        device_id = data.get('device_id')
        session_token = data.get('session_token')
        
        print(f"\n🔍 ========== Verify Teacher Session ==========")
        print(f"Teacher ID: {teacher_id}")
        print(f"Device ID: {device_id}")
        
        if not teacher_id:
            return jsonify({
                'valid': False,
                'error': 'معرف المعلم مطلوب'
            }), 400
        
        teacher = Teacher.query.get(teacher_id)
        
        if not teacher:
            return jsonify({
                'valid': False,
                'error': 'المعلم غير موجود'
            }), 404
        
        if not teacher.is_active:
            return jsonify({
                'valid': False,
                'error': 'حسابك معطل',
                'error_code': 'ACCOUNT_DISABLED'
            })
        
        # التحقق من الجهاز
        if device_id and teacher.device_id and teacher.device_id != device_id:
            return jsonify({
                'valid': False,
                'error': 'تم تسجيل الدخول من جهاز آخر',
                'error_code': 'DEVICE_CHANGED'
            })
        
        # التحقق من session_token
        if session_token and teacher.session_token and teacher.session_token != session_token:
            return jsonify({
                'valid': False,
                'error': 'انتهت صلاحية الجلسة',
                'error_code': 'SESSION_EXPIRED'
            })
        
        print(f"✅ جلسة المعلم صالحة: {teacher.username}")
        print(f"========== End Verify Teacher Session ==========\n")
        
        return jsonify({
            'valid': True,
            'teacher': teacher.to_dict()
        })
        
    except Exception as e:
        print(f"❌ خطأ في التحقق من جلسة المعلم: {str(e)}")
        return jsonify({
            'valid': False,
            'error': 'حدث خطأ في التحقق'
        }), 500


# ==================== ✅ جديد: API تسجيل خروج الطالب ====================
@students_bp.route('/api/logout', methods=['POST'])
def api_student_logout():
    """تسجيل خروج الطالب وإزالة ربط الجهاز"""
    try:
        data = request.get_json() or request.form
        student_id = data.get('student_id')
        device_id = data.get('device_id')
        
        print(f"\n🚪 ========== Student Logout Request ==========")
        print(f"Student ID: {student_id}")
        print(f"Device ID: {device_id}")
        
        if not student_id:
            return jsonify({
                'success': False,
                'error': 'معرف الطالب مطلوب'
            }), 400
        
        student = Student.query.get(student_id)
        
        if not student:
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        # التحقق من أن الجهاز هو نفس الجهاز المسجل (للأمان)
        if device_id and student.device_id and student.device_id != device_id:
            print(f"⚠️ محاولة تسجيل خروج من جهاز مختلف")
            return jsonify({
                'success': False,
                'error': 'لا يمكنك تسجيل الخروج من جهاز مختلف'
            }), 403
        
        # إزالة ربط الجهاز
        old_device = student.device_name or student.device_id
        student.device_id = None
        student.device_name = None
        student.last_device_login = None
        student.session_token = None
        
        db.session.commit()
        
        print(f"✅ تم تسجيل خروج الطالب: {student.username} من جهاز: {old_device}")
        print(f"========== End Student Logout ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم تسجيل الخروج بنجاح'
        })
        
    except Exception as e:
        print(f"❌ خطأ في تسجيل الخروج: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في تسجيل الخروج'
        }), 500


# ==================== ✅ جديد: API التحقق من الجلسة ====================
@students_bp.route('/api/verify-session', methods=['POST'])
def api_verify_student_session():
    """التحقق من صلاحية جلسة الطالب"""
    try:
        data = request.get_json() or request.form
        student_id = data.get('student_id')
        device_id = data.get('device_id')
        session_token = data.get('session_token')
        
        print(f"\n🔍 ========== Verify Session Request ==========")
        print(f"Student ID: {student_id}")
        print(f"Device ID: {device_id}")
        
        if not student_id or not device_id:
            return jsonify({
                'success': False,
                'valid': False,
                'error': 'بيانات ناقصة'
            }), 400
        
        student = Student.query.get(student_id)
        
        if not student:
            return jsonify({
                'success': False,
                'valid': False,
                'error': 'الطالب غير موجود',
                'error_code': 'STUDENT_NOT_FOUND'
            }), 404
        
        # ✅ التحقق من الجهاز
        # إذا لم يكن هناك device_id مسجل = تم إلغاء الربط من الأدمن
        if not student.device_id:
            print(f"⚠️ الجلسة غير صالحة - تم إلغاء ربط الجهاز من الأدمن")
            return jsonify({
                'success': True,
                'valid': False,
                'error': 'تم إلغاء ربط جهازك. يرجى تسجيل الدخول مرة أخرى',
                'error_code': 'DEVICE_UNLINKED'
            })
        
        # إذا كان الجهاز مختلف عن المسجل
        if student.device_id != device_id:
            print(f"⚠️ الجلسة غير صالحة - جهاز مختلف")
            return jsonify({
                'success': True,
                'valid': False,
                'error': 'تم تسجيل الدخول من جهاز آخر',
                'error_code': 'SESSION_EXPIRED'
            })
        
        # التحقق من حالة الحساب
        if not student.is_active:
            print(f"⚠️ حساب الطالب معطل")
            return jsonify({
                'success': True,
                'valid': False,
                'error': 'حسابك معطل',
                'error_code': 'ACCOUNT_DISABLED'
            })
        
        # التحقق من session_token (اختياري)
        if session_token and student.session_token and student.session_token != session_token:
            print(f"⚠️ session_token غير صالح")
            return jsonify({
                'success': True,
                'valid': False,
                'error': 'الجلسة منتهية',
                'error_code': 'INVALID_SESSION'
            })
        
        print(f"✅ الجلسة صالحة للطالب: {student.username}")
        print(f"========== End Verify Session ==========\n")
        
        return jsonify({
            'success': True,
            'valid': True,
            'student': {
                'id': student.id,
                'name': student.name,
                'username': student.username
            }
        })
        
    except Exception as e:
        print(f"❌ خطأ في التحقق من الجلسة: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'valid': False,
            'error': 'حدث خطأ'
        }), 500


# ==================== ✅ جديد: API إزالة ربط الجهاز (للأدمن) ====================
@students_bp.route('/api/admin/reset-device/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def api_admin_reset_student_device(student_id):
    """إزالة ربط جهاز الطالب (للأدمن فقط)"""
    try:
        student = Student.query.get(student_id)
        
        if not student:
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        old_device = student.device_name or student.device_id or 'لا يوجد'
        
        # إزالة ربط الجهاز
        student.device_id = None
        student.device_name = None
        student.last_device_login = None
        student.session_token = None
        
        db.session.commit()
        
        print(f"✅ الأدمن {current_user.username} أزال ربط جهاز الطالب: {student.username}")
        
        return jsonify({
            'success': True,
            'message': f'تم إزالة ربط الجهاز ({old_device}) للطالب {student.name}'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إزالة ربط الجهاز: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'حدث خطأ'
        }), 500


# ==================== ✅ جديد: صفحة إزالة ربط الجهاز (للأدمن) ====================
@students_bp.route('/reset-device/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def reset_student_device(student_id):
    """إزالة ربط جهاز الطالب من لوحة التحكم"""
    student = Student.query.get_or_404(student_id)
    
    old_device = student.device_name or student.device_id or 'غير معروف'
    
    try:
        student.device_id = None
        student.device_name = None
        student.last_device_login = None
        student.session_token = None
        
        db.session.commit()
        flash(f'تم إزالة ربط الجهاز ({old_device}) للطالب "{student.name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في إزالة ربط الجهاز: {str(e)}', 'danger')
    
    return redirect(url_for('students.list_students'))


# ==================== ✅ جديد: جلب معلومات الجهاز (للأدمن) ====================
@students_bp.route('/api/admin/device-info/<int:student_id>', methods=['GET'])
@login_required
@admin_required
def api_get_student_device_info(student_id):
    """جلب معلومات جهاز الطالب (للأدمن)"""
    try:
        student = Student.query.get(student_id)
        
        if not student:
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        return jsonify({
            'success': True,
            'device_info': {
                'has_device': student.device_id is not None,
                'device_id': student.device_id,
                'device_name': student.device_name,
                'last_login': student.last_device_login.isoformat() if student.last_device_login else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'حدث خطأ'
        }), 500


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
        student_id = data.get('student_id')
        username = data.get('username')
        
        print(f"\n🔍 ========== FCM Token Request ==========")
        print(f"student_id: {student_id}")
        print(f"username: {username}")
        print(f"token_length: {len(fcm_token)}")
        print(f"token_preview: {fcm_token[:50]}...")
        
        if not fcm_token:
            print(f"❌ FCM token مفقود")
            return jsonify({
                'success': False,
                'error': 'FCM token مطلوب'
            }), 400
        
        # البحث عن الطالب
        student = None
        if student_id:
            student = Student.query.get(student_id)
            print(f"🔍 بحث بالمعرف: student_id={student_id}, found={student is not None}")
        elif username:
            student = Student.query.filter_by(username=username).first()
            print(f"🔍 بحث بالاسم: username={username}, found={student is not None}")
        else:
            print(f"❌ لم يتم إرسال student_id أو username")
            return jsonify({
                'success': False,
                'error': 'معرف الطالب أو اسم المستخدم مطلوب'
            }), 400
        
        if not student:
            print(f"❌ الطالب غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        # تحديث FCM Token
        print(f"🔍 قبل التحديث: student.fcm_token = {student.fcm_token[:50] if student.fcm_token else 'None'}...")
        student.fcm_token = fcm_token
        db.session.commit()
        print(f"🔍 بعد التحديث: student.fcm_token = {student.fcm_token[:50]}...")
        print(f"✅ تم حفظ FCM Token بنجاح")
        print(f"========== End FCM Token Request ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ FCM Token بنجاح'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حفظ FCM Token: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== APIs الإشعارات ====================

@students_bp.route('/api/notifications/<int:user_id>', methods=['GET'])
def api_get_notifications(user_id):
    """جلب إشعارات المستخدم"""
    try:
        print(f"\n🔍 ========== Get Notifications Request ==========")
        print(f"user_id: {user_id}")
        
        # جلب الإشعارات من جدول notifications
        notifications = db.session.execute(
            db.text("""
                SELECT id, title, message, type, student_id, is_read, created_at, read_at
                FROM notifications
                WHERE student_id = :student_id AND type NOT IN (
                    'admin_activity', 'security_alert', 'error', 'warning', 'failed_login', 'system_error'
                )
                ORDER BY created_at DESC
                LIMIT 50
            """),
            {'student_id': user_id}
        ).fetchall()
        
        result = []
        for n in notifications:
            result.append({
                'id': n[0],
                'title': n[1],
                'message': n[2],
                'body': n[2],
                'notification_type': n[3],
                'type': n[3],
                'student_id': n[4],
                'is_read': n[5],
                'created_at': n[6].isoformat() if n[6] else None,
                'timestamp': n[6].isoformat() if n[6] else None,
                'read_at': n[7].isoformat() if n[7] else None
            })
        
        print(f"✅ تم جلب {len(result)} إشعار")
        print(f"========== End Get Notifications Request ==========\n")
        
        return jsonify({
            'success': True,
            'notifications': result
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب الإشعارات: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'notifications': []
        }), 500


@students_bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def api_mark_notification_read(notification_id):
    """تحديث حالة الإشعار إلى مقروء"""
    try:
        data = request.get_json() or request.form
        user_id = data.get('user_id') or data.get('student_id')
        
        print(f"\n🔍 ========== Mark Notification Read Request ==========")
        print(f"notification_id: {notification_id}")
        print(f"user_id: {user_id}")
        
        if not user_id:
            print(f"❌ معرف المستخدم مفقود")
            return jsonify({
                'success': False,
                'error': 'معرف المستخدم مطلوب'
            }), 400
        
        # تحديث حالة الإشعار
        result = db.session.execute(
            db.text("""
                UPDATE notifications
                SET is_read = TRUE, read_at = NOW()
                WHERE id = :notification_id AND student_id = :student_id
            """),
            {'notification_id': notification_id, 'student_id': user_id}
        )
        db.session.commit()
        
        if result.rowcount == 0:
            print(f"❌ الإشعار غير موجود")
            return jsonify({
                'success': False,
                'error': 'الإشعار غير موجود'
            }), 404
        
        print(f"✅ تم تحديث حالة الإشعار إلى مقروء")
        print(f"========== End Mark Notification Read Request ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم تحديث حالة الإشعار'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في تحديث الإشعار: {str(e)}")
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



# ==================== API لحفظ الإشعارات من Firebase ====================

@students_bp.route('/api/notifications/batch-save', methods=['POST'])
def api_save_notifications_batch():
    """حفظ عدة إشعارات دفعة واحدة"""
    try:
        from src.models.notification import Notification
        
        data = request.get_json() or request.form
        notifications_list = data.get('notifications', [])
        
        print(f"\n🔍 ========== Save Notifications Batch ==========")
        print(f"عدد الإشعارات: {len(notifications_list)}")
        
        if not notifications_list:
            print(f"❌ قائمة الإشعارات فارغة")
            return jsonify({
                'success': False,
                'error': 'قائمة الإشعارات مطلوبة'
            }), 400
        
        saved_ids = []
        failed_count = 0
        
        for notif_data in notifications_list:
            try:
                student_id = notif_data.get('student_id')
                title = notif_data.get('title', '').strip()
                message = notif_data.get('message', '').strip() or notif_data.get('body', '').strip()
                
                if not student_id or not title or not message:
                    print(f"⚠️  إشعار غير كامل - تم تخطيه")
                    failed_count += 1
                    continue
                
                # التحقق من وجود الطالب
                student = Student.query.get(student_id)
                if not student:
                    print(f"⚠️  الطالب {student_id} غير موجود - تم تخطيه")
                    failed_count += 1
                    continue
                
                # إنشاء الإشعار
                notification = Notification(
                    student_id=student_id,
                    title=title,
                    message=message,
                    is_read=False,
                    created_at=datetime.now()
                )
                
                db.session.add(notification)
                db.session.flush()
                saved_ids.append(notification.id)
                
            except Exception as e:
                print(f"❌ خطأ في حفظ إشعار: {str(e)}")
                failed_count += 1
                continue
        
        db.session.commit()
        
        print(f"✅ تم حفظ {len(saved_ids)} إشعار بنجاح")
        print(f"❌ فشل {failed_count} إشعار")
        print(f"========== End Save Notifications Batch ==========\n")
        
        return jsonify({
            'success': True,
            'message': f'تم حفظ {len(saved_ids)} إشعار بنجاح',
            'saved_count': len(saved_ids),
            'failed_count': failed_count,
            'saved_ids': saved_ids
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حفظ الإشعارات: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@students_bp.route('/api/notifications/unread-count/<int:student_id>', methods=['GET'])
def api_get_unread_notifications_count(student_id):
    """جلب عدد الإشعارات غير المقروءة"""
    try:
        from src.models.notification import Notification
        
        print(f"\n🔍 ========== Get Unread Count Request ==========")
        print(f"student_id: {student_id}")
        
        # التحقق من وجود الطالب
        student = Student.query.get(student_id)
        if not student:
            print(f"❌ الطالب غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود',
                'unread_count': 0
            }), 404
        
        # جلب عدد الإشعارات غير المقروءة
        unread_count = Notification.query.filter_by(
            student_id=student_id,
            is_read=False
        ).count()
        
        print(f"✅ عدد الإشعارات غير المقروءة: {unread_count}")
        print(f"========== End Get Unread Count Request ==========\n")
        
        return jsonify({
            'success': True,
            'unread_count': unread_count
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب عدد الإشعارات: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'unread_count': 0
        }), 500


@students_bp.route('/api/notifications/mark-all-read/<int:student_id>', methods=['POST'])
def api_mark_all_notifications_read(student_id):
    """تحديث جميع إشعارات الطالب كمقروءة"""
    try:
        from src.models.notification import Notification
        
        data = request.get_json() or request.form
        
        print(f"\n🔍 ========== Mark All Notifications Read Request ==========")
        print(f"student_id: {student_id}")
        
        # التحقق من وجود الطالب
        student = Student.query.get(student_id)
        if not student:
            print(f"❌ الطالب غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        # تحديث جميع الإشعارات غير المقروءة فقط
        updated_count = Notification.query.filter_by(
            student_id=student_id,
            is_read=False
        ).update({'is_read': True, 'read_at': datetime.now()})
        
        db.session.commit()
        
        print(f"✅ تم تحديث {updated_count} إشعار كمقروء")
        print(f"========== End Mark All Notifications Read Request ==========\n")
        
        return jsonify({
            'success': True,
            'message': f'تم تحديث {updated_count} إشعار',
            'updated_count': updated_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في تحديث الإشعارات: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@students_bp.route('/api/notifications/delete/<int:notification_id>', methods=['DELETE', 'POST'])
def api_delete_notification(notification_id):
    """حذف إشعار معين"""
    try:
        from src.models.notification import Notification
        
        data = request.get_json() or request.form
        student_id = data.get('student_id')
        
        print(f"\n🔍 ========== Delete Notification Request ==========")
        print(f"notification_id: {notification_id}")
        print(f"student_id: {student_id}")
        
        # جلب الإشعار
        notification = Notification.query.get(notification_id)
        if not notification:
            print(f"❌ الإشعار غير موجود")
            return jsonify({
                'success': False,
                'error': 'الإشعار غير موجود'
            }), 404
        
        # التحقق من أن الإشعار يخص الطالب
        if student_id and notification.student_id != student_id:
            print(f"❌ الإشعار لا يخص هذا الطالب")
            return jsonify({
                'success': False,
                'error': 'الإشعار لا يخص هذا الطالب'
            }), 403
        
        # حذف الإشعار
        db.session.delete(notification)
        db.session.commit()
        
        print(f"✅ تم حذف الإشعار بنجاح")
        print(f"========== End Delete Notification Request ==========\n")
        
        return jsonify({
            'success': True,
            'message': 'تم حذف الإشعار بنجاح'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حذف الإشعار: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
