"""
إدارة الطلاب - Routes
يسمح للأدمن بإضافة وتعديل وحذف الطلاب
✅ محدث: إضافة منطق تسجيل الدخول من جهاز واحد
✅ محدث: نظام توقيت ذكي يدعم جميع المناطق الزمنية
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from src.extensions import db
from src.models.student import Student
from functools import wraps
from src.middleware.auth_middleware import create_student_token
from datetime import datetime
import secrets
import pytz  # ✅ إضافة لنظام التوقيت الذكي

students_bp = Blueprint('students', __name__, url_prefix='/students')

# ==================== نظام التوقيت الذكي ====================
# الحل الأمثل: حفظ بـ UTC في قاعدة البيانات، تحويل عند العرض

def get_utc_time():
    """
    الحصول على الوقت الحالي بتوقيت UTC
    يُستخدم للحفظ في قاعدة البيانات
    """
    return datetime.now(pytz.utc)

def convert_utc_to_timezone(utc_dt, timezone_str='Asia/Riyadh'):
    """
    تحويل وقت UTC إلى أي منطقة زمنية
    
    Args:
        utc_dt: التاريخ والوقت بتوقيت UTC
        timezone_str: اسم المنطقة الزمنية (افتراضي: السعودية)
    
    Returns:
        datetime object بالمنطقة الزمنية المحددة
    
    أمثلة:
        'Asia/Riyadh' - السعودية (UTC+3)
        'Asia/Dubai' - الإمارات (UTC+4)
        'Africa/Cairo' - مصر (UTC+2)
        'Europe/London' - بريطانيا (UTC+0)
        'America/New_York' - نيويورك (UTC-5)
    """
    if utc_dt is None:
        return None
    
    try:
        # التأكد من أن الوقت بـ UTC
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        
        # تحويل للمنطقة الزمنية المطلوبة
        target_tz = pytz.timezone(timezone_str)
        return utc_dt.astimezone(target_tz)
    except Exception as e:
        print(f"⚠️ خطأ في تحويل التوقيت: {e}")
        return utc_dt

def get_user_timezone_from_request():
    """
    الحصول على المنطقة الزمنية من الـ request
    يمكن إرسالها من التطبيق في الـ headers
    """
    # محاولة الحصول على timezone من الـ header
    timezone = request.headers.get('X-Timezone', 'Asia/Riyadh')
    
    # التحقق من صحة الـ timezone
    try:
        pytz.timezone(timezone)
        return timezone
    except:
        # إذا كان timezone غير صحيح، استخدم السعودية كافتراضي
        return 'Asia/Riyadh'

# ملاحظة هامة:
# - جميع الأوقات تُحفظ في قاعدة البيانات بتوقيت UTC
# - عند الإرسال للتطبيق، يتم التحويل حسب timezone المستخدم
# - التطبيق يُرسل timezone في الـ header: X-Timezone
# ==================== نهاية نظام التوقيت ====================


def admin_required(f):
    """التحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('ليس لديك صلاحية الوصول لهذه الصفحة', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== عرض قائمة الطلاب (الصفحة الرئيسية) ====================
@students_bp.route('/', methods=['GET'])
@students_bp.route('', methods=['GET'])
@login_required
@admin_required
def list_students():
    """عرض قائمة جميع الطلاب مع إمكانية البحث"""
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
    """حذف طالب مع جميع بياناته المرتبطة"""
    student = Student.query.get_or_404(student_id)
    name = student.name

    try:
        # حذف البيانات المرتبطة أولاً
        related_tables = [
            'ai_actions', 'ai_analysis', 'ai_logs',
            'challenge_completions', 'diagnostic_comparisons', 'diagnostic_results',
            'notifications', 'password_resets', 'point_transactions',
            'student_achievements', 'student_challenges', 'student_notifications',
            'student_points', 'student_results',
        ]
        for table in related_tables:
            try:
                db.session.execute(
                    db.text(f"DELETE FROM {table} WHERE student_id = :id"),
                    {'id': student_id}
                )
            except Exception:
                pass

        # حذف login_attempts
        try:
            db.session.execute(
                db.text("DELETE FROM login_attempts WHERE user_id = :id AND user_type = 'student'"),
                {'id': student_id}
            )
        except Exception:
            pass

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
        force_login = data.get('force_login', False)  # ✅ جديد: تسجيل دخول قسري
        
        print(f"\n🔐 ========== Student Login Request ==========")
        print(f"Username: {username}")
        print(f"Device ID: {device_id}")
        print(f"Device Name: {device_name}")
        print(f"Force Login: {force_login}")
        
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
                # ✅ إذا لم يكن تسجيل دخول قسري، نرجع خطأ
                if not force_login:
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
                else:
                    # ✅ تسجيل دخول قسري - إلغاء الجهاز القديم
                    print(f"🔄 تسجيل دخول قسري للطالب {username}")
                    print(f"   إلغاء الجهاز القديم: {student.device_id} ({student.device_name})")
                    print(f"   تسجيل الجهاز الجديد: {device_id} ({device_name})")
            
            # تحديث معلومات الجهاز
            student.device_id = device_id
            student.device_name = device_name or 'جهاز غير معروف'
            student.last_device_login = get_utc_time()  # ✅ UTC للتوافق العالمي
        
        # تحديث آخر تسجيل دخول
        student.last_login = get_utc_time()  # ✅ UTC للتوافق العالمي
        
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
        force_login = data.get('force_login', False)  # ✅ جديد: تسجيل دخول قسري
        
        print(f"\n🔐 ========== Teacher Login Request ==========")
        print(f"Username: {username}")
        print(f"Device ID: {device_id}")
        print(f"Device Name: {device_name}")
        print(f"Force Login: {force_login}")
        
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
                # ✅ إذا لم يكن تسجيل دخول قسري، نرجع خطأ
                if not force_login:
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
                else:
                    # ✅ تسجيل دخول قسري - إلغاء الجهاز القديم
                    print(f"🔄 تسجيل دخول قسري للمعلم {username}")
                    print(f"   إلغاء الجهاز القديم: {teacher.device_id} ({teacher.device_name})")
                    print(f"   تسجيل الجهاز الجديد: {device_id} ({device_name})")
            
            # تحديث معلومات الجهاز
            teacher.device_id = device_id
            teacher.device_name = device_name or 'جهاز غير معروف'
            teacher.last_device_login = get_utc_time()  # ✅ UTC للتوافق العالمي
        
        # تحديث آخر تسجيل دخول
        teacher.last_login = get_utc_time()  # ✅ UTC للتوافق العالمي
        
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
    """جلب إشعارات المستخدم - محدثة لدعم إشعارات الذكاء الاصطناعي"""
    try:
        print(f"\n🔍 ========== Get Notifications Request ==========")
        print(f"user_id: {user_id}")
        
        # ✅ تحديث: إزالة الفلترة حسب النوع لعرض جميع الإشعارات
        # أو يمكنك تحديد الأنواع المستبعدة بشكل دقيق
        # ✅ استخدام DISTINCT لإزالة التكرار
        notifications = db.session.execute(
            db.text("""
                WITH all_notifications AS (
                    -- إشعارات قديمة (مرتبطة مباشرة بالطالب)
                    SELECT 
                        n.id,
                        n.title,
                        n.message,
                        n.type,
                        n.student_id,
                        n.is_read,
                        n.created_at,
                        n.read_at
                    FROM notifications n
                    WHERE n.student_id = :student_id
                      AND n.type NOT IN ('admin_activity', 'security_alert', 'system_error', 'failed_login')

                    UNION

                    -- إشعارات جديدة (مرتبطة عبر student_notifications)
                    SELECT 
                        n.id,
                        n.title,
                        n.message,
                        n.type,
                        sn.student_id,
                        sn.is_read,
                        n.created_at,
                        sn.read_at
                    FROM student_notifications sn
                    JOIN notifications n ON n.id = sn.notification_id
                    WHERE sn.student_id = :student_id
                      AND n.type NOT IN ('admin_activity', 'security_alert', 'system_error', 'failed_login')
                )
                SELECT DISTINCT ON (id) *
                FROM all_notifications
                ORDER BY id DESC, created_at DESC
                LIMIT 100
            """),
            {'student_id': user_id}
        ).fetchall()
        
        result = []
        for n in notifications:
            # ✅ طباعة للتتبع
            #                print(f"   📩 ID:{n[0]} | Type:{n[3]} | Title:{n[1][:30]}")
            
            result.append({
                'id': n[0],
                'title': n[1],
                'message': n[2],
                'body': n[2],  # ✅ إضافة body للتوافق
                'notification_type': n[3],
                'type': n[3],
                'student_id': n[4],
                'is_read': n[5],
                'created_at': convert_utc_to_timezone(n[6], get_user_timezone_from_request()).isoformat() if n[6] else None,
                'timestamp': convert_utc_to_timezone(n[6], get_user_timezone_from_request()).isoformat() if n[6] else None,
                'read_at': convert_utc_to_timezone(n[7], get_user_timezone_from_request()).isoformat() if n[7] else None
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



# حفظ الإشعار عندما يفتحه الطالب في التطبيق
@students_bp.route('/api/notifications/save', methods=['POST'])
def api_save_notification():
    """حفظ إشعار جديد في قاعدة البيانات"""
    try:
        from src.models.notification import Notification

        data = request.get_json() or request.form

        student_id = data.get('student_id')
        title = data.get('title', '').strip()
        message = data.get('message', '').strip() or data.get('body', '').strip()
        notification_type = data.get('type', 'info')

        print(f"\n🔍 ========== Save Single Notification ==========")
        print(f"student_id: {student_id}")
        print(f"title: {title}")
        print(f"message: {message}")
        print(f"type: {notification_type}")

        if not student_id or not title or not message:
            print("❌ بيانات ناقصة")
            return jsonify({
                'success': False,
                'error': 'البيانات المطلوبة: student_id, title, message'
            }), 400

        # تحقق من وجود الطالب
        student = Student.query.get(student_id)
        if not student:
            print(f"❌ الطالب {student_id} غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404


        # تحقق من وجود إشعار مماثل (في كلا الجدولين)
        existing_check = db.session.execute(
            db.text("""
                -- التحقق في جدول notifications
                SELECT id FROM notifications 
                WHERE title = :title 
                AND message = :message
                AND created_at > NOW() - INTERVAL '5 minutes'
                LIMIT 1
            """),
            {'title': title, 'message': message}
        ).fetchone()

        if existing_check:
            notification_id = existing_check[0]
            print(f"⚠️  الإشعار موجود مسبقاً - ID: {notification_id}")
            
            # التحقق من وجود الربط في student_notifications
            link_check = db.session.execute(
                db.text("""
                    SELECT id FROM student_notifications
                    WHERE notification_id = :notif_id
                    AND student_id = :student_id
                    LIMIT 1
                """),
                {'notif_id': notification_id, 'student_id': student_id}
            ).fetchone()
            
            if not link_check:
                # الإشعار موجود لكن غير مربوط بهذا الطالب - ربطه
                from src.models.notification import StudentNotification
                student_notif = StudentNotification(
                    notification_id=notification_id,
                    student_id=student_id,
                    is_read=False,
                    created_at=get_utc_time()
                )
                db.session.add(student_notif)
                db.session.commit()
                print(f"✅ تم ربط الإشعار {notification_id} بالطالب {student_id}")
            
            return jsonify({
                'success': True,
                'message': 'الإشعار موجود مسبقاً',
                'notification_id': notification_id,
                'duplicate': True
            }), 200

        # إنشاء الإشعار
        notification = Notification(
            student_id=student_id,
            title=title,
            message=message,
            type=notification_type,
            is_read=False,
            created_at=get_utc_time()
        )

        db.session.add(notification)
        db.session.flush()  # نحصل على notification.id قبل commit

        # ✅ ربط الإشعار بالطالب في student_notifications
        # حتى يشتغل mark-as-read و delete لاحقاً
        from src.models.notification import StudentNotification
        student_notif = StudentNotification(
            notification_id=notification.id,
            student_id=student_id,
            is_read=False,
            created_at=get_utc_time()
        )
        db.session.add(student_notif)
        db.session.commit()

        print(f"✅ تم حفظ الإشعار بنجاح - ID: {notification.id}")
        print("========== End Save Single Notification ==========\n")

        return jsonify({
            'success': True,
            'message': 'تم حفظ الإشعار بنجاح',
            'notification_id': notification.id
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حفظ الإشعار: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
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
        
        # تحديث student_notifications أولاً
        result = db.session.execute(
            db.text("""
                UPDATE student_notifications
                SET is_read = TRUE, read_at = NOW()
                WHERE notification_id = :notification_id
                  AND student_id = :student_id
            """),
            {'notification_id': notification_id, 'student_id': user_id}
        )
        # ✅ نحفظ rowcount قبل commit (يُفقد بعده في بعض الـ drivers)
        rows_updated = result.rowcount

        # تحديث notifications مباشرة دائماً
        db.session.execute(
            db.text("""
                UPDATE notifications
                SET is_read = TRUE, read_at = NOW()
                WHERE id = :notification_id
            """),
            {'notification_id': notification_id}
        )
        db.session.commit()

        # إذا ما كان في student_notifications → أنشئ record وعلّمه مقروء
        if rows_updated == 0:
            notif_exists = db.session.execute(
                db.text("SELECT id FROM notifications WHERE id = :id"),
                {'id': notification_id}
            ).fetchone()
            if notif_exists:
                db.session.execute(
                    db.text("""
                        INSERT INTO student_notifications
                            (notification_id, student_id, is_read, read_at, created_at)
                        VALUES (:notif_id, :student_id, TRUE, NOW(), NOW())
                        ON CONFLICT DO NOTHING
                    """),
                    {'notif_id': notification_id, 'student_id': user_id}
                )
                db.session.commit()
            else:
                print(f"❌ الإشعار {notification_id} غير موجود")
                return jsonify({'success': False, 'error': 'الإشعار غير موجود'}), 404
        
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
    """جلب نتائج الطالب - محسّنة"""
    try:
        # جلب student_id من الـ header أولاً ثم query parameter
        student_id = None
        header_id = request.headers.get('X-Student-Id')
        if header_id:
            try:
                student_id = int(header_id)
            except (ValueError, TypeError):
                pass
        if not student_id:
            student_id = request.args.get('student_id', type=int)

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        if not student_id:
            return jsonify({
                'success': False,
                'error': 'student_id مطلوب'
            }), 400

        # ✅ التحقق من session_token إن أُرسل
        session_token = request.headers.get('X-Session-Token')
        if session_token:
            student = Student.query.get(student_id)
            if not student or not student.session_token or student.session_token != session_token:
                return jsonify({'success': False, 'error': 'جلسة غير صالحة'}), 401
        
        # استيراد النموذج
        try:
            from src.models.student_result import StudentResult
        except ImportError:
            from models.student_result import StudentResult
        
        # جلب النتائج مرتبة بالأحدث مع pagination
        results = StudentResult.query.filter_by(student_id=student_id)\
            .order_by(StudentResult.created_at.desc())\
            .limit(limit).offset(offset).all()
        
        # تحويل النتائج مع التأكد من وجود time_spent
        results_list = []
        for r in results:
            # ✅ إرسال الوقت بصيغة UTC مع Z - التطبيق سيحول للتوقيت المحلي
            created_time_str = None
            if r.created_at:
                # إضافة Z للإشارة أنه UTC
                created_time_str = r.created_at.isoformat() + 'Z' if not r.created_at.isoformat().endswith('Z') else r.created_at.isoformat()
            
            result_dict = r.to_dict() if hasattr(r, 'to_dict') else {
                'id': r.id,
                'quiz_type': r.quiz_type,
                'quiz_name': r.quiz_name,
                'total_questions': r.total_questions,
                'correct_answers': r.correct_answers,
                'wrong_answers': r.wrong_answers,
                'score_percentage': round(r.score_percentage, 1) if r.score_percentage else 0,
                'course_id': r.course_id,
                'unit_id': r.unit_id,
                'lesson_id': r.lesson_id,
                'created_at': created_time_str,  # ✅ UTC format مع Z
            }
            # ✅ التأكد من وجود time_spent
            result_dict['time_spent'] = r.time_spent or 0
            results_list.append(result_dict)
        
        return jsonify({
            'success': True,
            'results': results_list,
            'count': len(results_list)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/results/stats', methods=['GET'])
def api_get_results_stats():
    """جلب إحصائيات نتائج الطالب - محسّنة"""
    try:
        # جلب student_id من الـ header أولاً ثم query parameter
        student_id = None
        header_id = request.headers.get('X-Student-Id')
        if header_id:
            try:
                student_id = int(header_id)
            except (ValueError, TypeError):
                pass
        if not student_id:
            student_id = request.args.get('student_id', type=int)

        # ✅ التحقق من session_token إن أُرسل
        session_token = request.headers.get('X-Session-Token')
        if session_token and student_id:
            student = Student.query.get(student_id)
            if not student or not student.session_token or student.session_token != session_token:
                return jsonify({'success': False, 'error': 'جلسة غير صالحة'}), 401
        
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
        
        # ✅ إحصائيات شاملة في استعلام واحد
        stats = db.session.query(
            func.count(StudentResult.id).label('total_quizzes'),
            func.coalesce(func.avg(StudentResult.score_percentage), 0).label('avg_score'),
            func.coalesce(func.max(StudentResult.score_percentage), 0).label('best_score'),
            func.coalesce(func.min(StudentResult.score_percentage), 0).label('worst_score'),
            func.coalesce(func.sum(StudentResult.total_questions), 0).label('total_questions'),
            func.coalesce(func.sum(StudentResult.correct_answers), 0).label('correct_answers'),
            func.coalesce(func.sum(StudentResult.wrong_answers), 0).label('wrong_answers'),
            func.coalesce(func.sum(StudentResult.time_spent), 0).label('total_time'),
        ).filter(StudentResult.student_id == student_id).first()
        
        # آخر 7 نتائج للرسم البياني
        recent_results = StudentResult.query.filter_by(student_id=student_id)\
            .order_by(StudentResult.created_at.desc()).limit(7).all()
        
        chart_data = [{
            'date': r.created_at.strftime('%m/%d') if r.created_at else '',
            'score': round(r.score_percentage, 0) if r.score_percentage else 0
        } for r in reversed(recent_results)]
        
        return jsonify({
            'success': True,
            'stats': {
                'total_quizzes': stats.total_quizzes or 0,
                'avg_score': round(float(stats.avg_score or 0), 1),
                'best_score': round(float(stats.best_score or 0), 1),
                'worst_score': round(float(stats.worst_score or 0), 1),
                'total_questions': stats.total_questions or 0,
                'correct_answers': stats.correct_answers or 0,
                'wrong_answers': stats.wrong_answers or 0,
                'total_time': stats.total_time or 0,
                'chart_data': chart_data
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/results', methods=['POST'])
def api_save_result():
    """حفظ نتيجة اختبار الطالب - محسّنة ومطوّرة"""
    try:
        data = request.get_json() or request.form

        print(f"\n💾 ========== Save Student Result ==========")
        print(f"📊 البيانات المستلمة:")
        print(f"   - student_id: {data.get('student_id')}")
        print(f"   - quiz_type: {data.get('quiz_type')}")
        print(f"   - quiz_name: {data.get('quiz_name')}")
        print(f"   - total_questions: {data.get('total_questions')}")
        print(f"   - correct_answers: {data.get('correct_answers')}")
        print(f"   - score_percentage: {data.get('score_percentage')}")
        print(f"   - time_spent: {data.get('time_spent')}")

        student_id = data.get('student_id')

        if not student_id:
            print(f"❌ خطأ: student_id مفقود")
            return jsonify({
                'success': False,
                'error': 'student_id مطلوب'
            }), 400

        # ✅ التحقق من وجود الطالب
        student = Student.query.get(student_id)
        if not student:
            print(f"❌ خطأ: الطالب {student_id} غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404

        print(f"✅ الطالب موجود: {student.name} ({student.username})")

        # ✅ التحقق من session_token إن أُرسل
        session_token = data.get('session_token')
        if session_token and student.session_token:
            if student.session_token != session_token:
                return jsonify({'success': False, 'error': 'جلسة غير صالحة، أعد تسجيل الدخول'}), 401

        try:
            from src.models.student_result import StudentResult
        except ImportError:
            from models.student_result import StudentResult

        # ✅ حساب الإجابات الخاطئة تلقائياً
        total_questions = data.get('total_questions', 0)
        correct_answers = data.get('correct_answers', 0)
        wrong_answers = data.get('wrong_answers', total_questions - correct_answers)

        # إنشاء سجل النتيجة
        result = StudentResult(
            student_id=student_id,
            quiz_type=data.get('quiz_type', 'lesson'),
            course_id=data.get('course_id'),
            unit_id=data.get('unit_id'),
            lesson_id=data.get('lesson_id'),
            quiz_name=data.get('quiz_name', 'اختبار'),
            total_questions=total_questions,
            correct_answers=correct_answers,
            wrong_answers=wrong_answers,
            score_percentage=data.get('score_percentage', 0.0),
            time_spent=data.get('time_spent', 0),  # ✅ الوقت المستغرق بالثواني
            created_at=get_utc_time()  # ✅ حفظ بـ UTC للتوافق العالمي
        )

        db.session.add(result)
        db.session.commit()

        print(f"✅ تم حفظ النتيجة بنجاح!")
        print(f"   - معرف النتيجة: {result.id}")
        print(f"   - اسم الاختبار: {result.quiz_name}")
        print(f"   - النتيجة: {result.score_percentage:.1f}%")
        print(f"   - الإجابات الصحيحة: {result.correct_answers}/{result.total_questions}")
        print(f"   - الوقت المستغرق: {result.time_spent} ثانية")
        
        # 🎯 تشغيل نظام Gamification
        try:
            from src.hooks.quiz_completion_hook import on_quiz_completed
            print(f"🎯 تشغيل Gamification Hook للطالب {student_id}")
            on_quiz_completed(student_id, result)
            print(f"✅ تم تشغيل Gamification Hook بنجاح")
        except ImportError as e:
            print(f"⚠️ Gamification Hook غير متاح: {e}")
        except Exception as e:
            print(f"❌ خطأ في Gamification Hook: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"========== End Save Result ==========\n")

        return jsonify({
            'success': True,
            'message': 'تم حفظ النتيجة بنجاح',
            'result_id': result.id
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حفظ النتيجة: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500



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
                    created_at=get_utc_time()  # ✅ UTC للتوافق العالمي
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


from src.models.notification import StudentNotification

@students_bp.route('/api/notifications/unread-count/<int:student_id>', methods=['GET'])
def api_get_unread_notifications_count(student_id):
    """جلب عدد الإشعارات غير المقروءة"""
    try:
        print("\n🔍 ========== Get Unread Count Request ==========")
        print(f"student_id: {student_id}")

        student = Student.query.get(student_id)
        if not student:
            print("❌ الطالب غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود',
                'unread_count': 0
            }), 404

        unread_count = StudentNotification.get_unread_count(student_id)
        print(f"✅ عدد الإشعارات غير المقروءة: {unread_count}")
        print("========== End Get Unread Count Request ==========\n")

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




from src.models.notification import StudentNotification

@students_bp.route('/api/notifications/mark-all-read/<int:student_id>', methods=['POST'])
def api_mark_all_notifications_read(student_id):
    """تحديث جميع إشعارات الطالب كمقروءة"""
    try:
        print("\n🔍 ========== Mark All Notifications Read Request ==========")
        print(f"student_id: {student_id}")

        student = Student.query.get(student_id)
        if not student:
            print("❌ الطالب غير موجود")
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404

        StudentNotification.mark_all_as_read(student_id)
        print("✅ تم تحديث جميع إشعارات الطالب كمقروءة")
        print("========== End Mark All Notifications Read Request ==========\n")

        return jsonify({
            'success': True,
            'message': 'تم تحديث جميع الإشعارات'
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




@students_bp.route('/api/notifications/<int:notification_id>/delete', methods=['DELETE', 'POST'])
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
            # قد يكون الإشعار محذوفاً من notifications لكن لا زال في student_notifications
            # احذفه من student_notifications وأرجع نجاح حتى لا يتكرر الطلب
            if student_id:
                db.session.execute(
                    db.text("""
                        DELETE FROM student_notifications
                        WHERE notification_id = :notif_id AND student_id = :student_id
                    """),
                    {'notif_id': notification_id, 'student_id': student_id}
                )
                db.session.commit()
            print(f"⚠️ الإشعار {notification_id} غير موجود في notifications — تم تنظيف student_notifications")
            return jsonify({'success': True, 'message': 'تم الحذف'}), 200

        # التحقق من أن الإشعار يخص الطالب (notifications.student_id أو student_notifications)
        if student_id and notification.student_id != int(student_id):
            # تحقق إذا كان مربوطاً عبر student_notifications
            linked = db.session.execute(
                db.text("SELECT id FROM student_notifications WHERE notification_id = :nid AND student_id = :sid"),
                {'nid': notification_id, 'sid': student_id}
            ).fetchone()
            if not linked:
                print(f"❌ الإشعار لا يخص هذا الطالب")
                return jsonify({'success': False, 'error': 'الإشعار لا يخص هذا الطالب'}), 403
            # احذف رابط student_notifications فقط
            db.session.execute(
                db.text("DELETE FROM student_notifications WHERE notification_id = :nid AND student_id = :sid"),
                {'nid': notification_id, 'sid': student_id}
            )
            db.session.commit()
            print(f"✅ تم حذف رابط الإشعار من student_notifications")
            return jsonify({'success': True, 'message': 'تم حذف الإشعار بنجاح'}), 200

        # حذف من student_notifications أولاً ثم notifications
        db.session.execute(
            db.text("DELETE FROM student_notifications WHERE notification_id = :nid"),
            {'nid': notification_id}
        )
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


# ===============================================
# ✅ جديد: API Endpoint لجلب قائمة الطلاب للبحث
# ===============================================

@students_bp.route('/api/list', methods=['GET'])
@login_required
@admin_required
def api_get_students_list():
    """
    جلب قائمة الطلاب للأدمن (للبحث عند إرسال الإشعارات)
    يرجع: id, name, username, grade فقط
    """
    try:
        print(f"\n🔍 ========== Get Students List Request ==========")
        
        # جلب الطلاب النشطين فقط
        students = Student.query.filter_by(is_active=True).order_by(Student.name).all()
        
        # تحويل لـ dictionary مبسط
        students_list = [{
            'id': student.id,
            'name': student.name,
            'username': student.username,
            'grade': student.grade,
            'school': student.school
        } for student in students]
        
        print(f'✅ تم جلب {len(students_list)} طالب')
        print(f"========== End Get Students List Request ==========\n")
        
        return jsonify({
            'success': True,
            'students': students_list,
            'total': len(students_list)
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب قائمة الطلاب: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'students': []
        }), 500


# ==================== عرض تفاصيل الإشعار وإحصائيات القراءة ====================
@students_bp.route('/api/admin/notification/<int:notification_id>/read-stats', methods=['GET'])
@login_required
@admin_required
def get_notification_read_stats(notification_id):
    """
    جلب تفاصيل الإشعار وإحصائيات القراءة
    يعرض الطلاب الذين قرأوا والذين لم يقرأوا الإشعار
    """
    try:
        from src.models.notification import Notification, StudentNotification
        
        # جلب الإشعار
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({
                'success': False,
                'error': 'الإشعار غير موجود'
            }), 404
        
        # جلب جميع الطلاب النشطين
        all_students = Student.query.filter_by(is_active=True).all()
        
        # جلب الطلاب الذين قرأوا الإشعار
        read_students = []
        unread_students = []
        
        for student in all_students:
            # البحث عن StudentNotification
            student_notif = StudentNotification.query.filter_by(
                student_id=student.id,
                notification_id=notification_id
            ).first()
            
            if student_notif and student_notif.is_read:
                read_students.append({
                    'id': student.id,
                    'name': student.name,
                    'username': student.username,
                    'read_at': student_notif.read_at.isoformat() if student_notif.read_at else None
                })
            else:
                unread_students.append({
                    'id': student.id,
                    'name': student.name,
                    'username': student.username
                })
        
        # حساب الإحصائيات
        total_students = len(all_students)
        read_count = len(read_students)
        unread_count = len(unread_students)
        
        return jsonify({
            'success': True,
            'notification': {
                'id': notification.id,
                'title': notification.title,
                'message': notification.message or notification.content,
                'created_at': notification.created_at.isoformat() if notification.created_at else None
            },
            'stats': {
                'total_students': total_students,
                'read_count': read_count,
                'unread_count': unread_count,
                'read_percentage': round((read_count / total_students * 100) if total_students > 0 else 0, 2)
            },
            'read_students': read_students,
            'unread_students': unread_students
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في جلب إحصائيات الإشعار: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'خطأ في جلب البيانات: {str(e)}'
        }), 500


# ==================== Mobile API Endpoints ====================

@students_bp.route('/api/mobile/students', methods=['GET'])
@login_required
@admin_required
def api_mobile_list_students():
    """قائمة الطلاب للموبايل مع بحث وفلترة"""
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = Student.query
    if search:
        query = query.filter(
            db.or_(
                Student.name.ilike(f'%{search}%'),
                Student.username.ilike(f'%{search}%'),
                Student.email.ilike(f'%{search}%'),
            )
        )

    total = query.count()
    students = query.order_by(Student.name).offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'success': True,
        'students': [
            {
                'id': s.id,
                'name': s.name,
                'username': s.username,
                'email': s.email or '',
                'phone': s.phone or '',
                'school': s.school or '',
                'grade': s.grade or '',
                'is_active': s.is_active,
                'notes': s.notes or '',
                'created_at': s.created_at.isoformat() if hasattr(s, 'created_at') and s.created_at else '',
            }
            for s in students
        ],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    })


@students_bp.route('/api/mobile/students/add', methods=['POST'])
@login_required
@admin_required
def api_mobile_add_student():
    """إضافة طالب جديد عبر الموبايل"""
    data = request.get_json() or {}

    name = data.get('name', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip() or None
    phone = data.get('phone', '').strip() or None
    school = data.get('school', '').strip() or None
    grade = data.get('grade', '').strip() or None
    is_active = data.get('is_active', True)
    notes = data.get('notes', '').strip() or None

    if not name or not username or not password:
        return jsonify({'success': False, 'error': 'الاسم واسم المستخدم وكلمة المرور مطلوبة'}), 400

    if len(password) < 8:
        return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'}), 400

    if Student.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'اسم المستخدم موجود مسبقاً'}), 409

    if email and Student.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'البريد الإلكتروني موجود مسبقاً'}), 409

    student = Student(
        name=name,
        username=username,
        email=email,
        phone=phone,
        school=school,
        grade=grade,
        is_active=is_active,
        notes=notes,
    )
    student.set_password(password)

    try:
        db.session.add(student)
        db.session.commit()
        try:
            from src.models.audit_log import AuditLog
            from flask_login import current_user
            AuditLog.log('add_student', f'إضافة طالب جديد: {name}',
                        admin_name=current_user.username if current_user.is_authenticated else 'الادمن',
                        target_type='student', target_id=student.id)
        except Exception:
            pass
        return jsonify({
            'success': True,
            'message': f'تم إضافة الطالب "{name}" بنجاح',
            'student_id': student.id,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/mobile/students/<int:student_id>', methods=['GET'])
@login_required
@admin_required
def api_mobile_get_student(student_id):
    """جلب بيانات طالب محدد"""
    student = Student.query.get_or_404(student_id)
    return jsonify({
        'success': True,
        'student': {
            'id': student.id,
            'name': student.name,
            'username': student.username,
            'email': student.email or '',
            'phone': student.phone or '',
            'school': student.school or '',
            'grade': student.grade or '',
            'is_active': student.is_active,
            'notes': student.notes or '',
        },
    })


@students_bp.route('/api/mobile/students/<int:student_id>/edit', methods=['POST'])
@login_required
@admin_required
def api_mobile_edit_student(student_id):
    """تعديل بيانات طالب"""
    student = Student.query.get_or_404(student_id)
    data = request.get_json() or {}

    if 'name' in data:
        student.name = data['name'].strip()
    if 'email' in data:
        student.email = data['email'].strip() or None
    if 'phone' in data:
        student.phone = data['phone'].strip() or None
    if 'school' in data:
        student.school = data['school'].strip() or None
    if 'grade' in data:
        student.grade = data['grade'].strip() or None
    if 'is_active' in data:
        student.is_active = bool(data['is_active'])
    if 'notes' in data:
        student.notes = data['notes'].strip() or None

    new_password = data.get('password', '')
    if new_password:
        if len(new_password) < 8:
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'}), 400
        student.set_password(new_password)

    try:
        db.session.commit()
        try:
            from src.models.audit_log import AuditLog
            from flask_login import current_user
            AuditLog.log('edit_student', f'تعديل بيانات الطالب: {student.name}',
                        admin_name=current_user.username if current_user.is_authenticated else 'الادمن',
                        target_type='student', target_id=student_id)
        except Exception:
            pass
        return jsonify({'success': True, 'message': f'تم تحديث بيانات الطالب "{student.name}" بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/mobile/students/<int:student_id>/delete', methods=['POST'])
@login_required
@admin_required
def api_mobile_delete_student(student_id):
    """حذف طالب مع جميع بياناته المرتبطة"""
    student = Student.query.get_or_404(student_id)
    name = student.name
    try:
        # حذف البيانات المرتبطة أولاً
        related_tables = [
            'ai_actions', 'ai_analysis', 'ai_logs',
            'challenge_completions', 'diagnostic_comparisons', 'diagnostic_results',
            'notifications', 'password_resets', 'point_transactions',
            'student_achievements', 'student_challenges', 'student_notifications',
            'student_points', 'student_results',
        ]
        for table in related_tables:
            try:
                db.session.execute(
                    db.text(f"DELETE FROM {table} WHERE student_id = :id"),
                    {'id': student_id}
                )
            except Exception:
                pass

        # حذف login_attempts
        try:
            db.session.execute(
                db.text("DELETE FROM login_attempts WHERE user_id = :id AND user_type = 'student'"),
                {'id': student_id}
            )
        except Exception:
            pass

        db.session.delete(student)
        db.session.commit()
        try:
            from src.models.audit_log import AuditLog
            from flask_login import current_user
            AuditLog.log('delete_student', f'حذف الطالب: {name}',
                        admin_name=current_user.username if current_user.is_authenticated else 'الادمن',
                        target_type='student', target_id=student_id)
        except Exception:
            pass
        return jsonify({'success': True, 'message': f'تم حذف الطالب "{name}" بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@students_bp.route('/api/mobile/students/<int:student_id>/toggle', methods=['POST'])
@login_required
@admin_required
def api_mobile_toggle_student(student_id):
    """تفعيل/تعطيل حساب طالب"""
    student = Student.query.get_or_404(student_id)
    student.is_active = not student.is_active
    try:
        db.session.commit()
        status = 'مفعل' if student.is_active else 'معطل'
        return jsonify({
            'success': True,
            'message': f'تم تغيير حالة الطالب إلى {status}',
            'is_active': student.is_active,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
