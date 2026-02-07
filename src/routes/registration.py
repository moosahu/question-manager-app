"""
التسجيل الذاتي للطلاب والمعلمين - Registration Routes
APIs للتسجيل والتحقق من الإيميل
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from src.extensions import db
from src.models.student import Student
from src.models.teacher import Teacher  # ✅ جديد
from src.models.email_verification import EmailVerification, RegistrationSettings
from src.services.email_service import email_service
from src.middleware.auth_middleware import create_student_token, create_teacher_token  # ✅ جديد

registration_bp = Blueprint('registration', __name__, url_prefix='/api/registration')


# ==================== التحقق من حالة التسجيل ====================
@registration_bp.route('/status', methods=['GET'])
def get_registration_status():
    """التحقق من حالة التسجيل (مفتوح/مغلق) للطلاب والمعلمين"""
    try:
        settings = RegistrationSettings.get_settings()
        account_type = request.args.get('type', 'student')  # ✅ جديد: نوع الحساب
        
        if account_type == 'teacher':
            # إعدادات المعلمين
            return jsonify({
                'success': True,
                'is_open': settings.is_teacher_registration_open,
                'message': settings.teacher_closed_message if not settings.is_teacher_registration_open else None,
                'require_phone': settings.teacher_require_phone,
                'require_school': settings.teacher_require_school,
            })
        else:
            # إعدادات الطلاب (الافتراضي)
            return jsonify({
                'success': True,
                'is_open': settings.is_registration_open,
                'message': settings.closed_message if not settings.is_registration_open else None,
                'require_phone': settings.require_phone,
                'require_school': settings.require_school,
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== الخطوة 1: إرسال بيانات التسجيل ====================
@registration_bp.route('/register', methods=['POST'])
def register_student():
    """تسجيل طالب جديد وإرسال رمز التحقق"""
    try:
        # التحقق من حالة التسجيل
        settings = RegistrationSettings.get_settings()
        if not settings.is_registration_open:
            return jsonify({
                'success': False,
                'error': settings.closed_message or 'التسجيل مغلق حالياً'
            }), 403
        
        data = request.get_json() or request.form
        
        # استخراج البيانات
        name = data.get('name', '').strip()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        phone = data.get('phone', '').strip() or None
        school = data.get('school', '').strip() or None
        grade = data.get('grade', '').strip() or None
        
        # التحقق من البيانات المطلوبة
        if not name or not username or not email or not password:
            return jsonify({
                'success': False,
                'error': 'الاسم واسم المستخدم والإيميل وكلمة المرور مطلوبة'
            }), 400
        
        # التحقق من طول كلمة المرور
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'
            }), 400
        
        # التحقق من صيغة الإيميل
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'error': 'صيغة الإيميل غير صحيحة'
            }), 400
        
        # التحقق من الحقول الإضافية المطلوبة
        if settings.require_phone and not phone:
            return jsonify({
                'success': False,
                'error': 'رقم الجوال مطلوب'
            }), 400
        
        if settings.require_school and not school:
            return jsonify({
                'success': False,
                'error': 'اسم المدرسة مطلوب'
            }), 400
        
        # التحقق من عدم تكرار اسم المستخدم
        if Student.query.filter_by(username=username).first():
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم موجود مسبقاً'
            }), 400
        
        # التحقق من عدم تكرار الإيميل
        if Student.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'error': 'الإيميل مسجل مسبقاً'
            }), 400
        
        # تشفير كلمة المرور
        password_hash = generate_password_hash(password)
        
        # إنشاء طلب التحقق
        verification = EmailVerification.create_verification(
            email=email,
            name=name,
            username=username,
            password_hash=password_hash,
            phone=phone,
            school=school,
            grade=grade
        )
        
        # إرسال رمز التحقق بالإيميل
        success, message = email_service.send_verification_code(
            to_email=email,
            code=verification.code,
            student_name=name
        )
        
        if not success:
            # حذف طلب التحقق إذا فشل الإرسال
            db.session.delete(verification)
            db.session.commit()
            return jsonify({
                'success': False,
                'error': f'فشل إرسال رمز التحقق: {message}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم إرسال رمز التحقق إلى بريدك الإلكتروني',
            'email': email,
            'expires_in': 180  # 3 دقائق بالثواني
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في التسجيل: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في التسجيل'
        }), 500


# ==================== ✅ جديد: تسجيل معلم ====================
@registration_bp.route('/register-teacher', methods=['POST'])
def register_teacher():
    """تسجيل معلم جديد وإرسال رمز التحقق"""
    try:
        # التحقق من حالة التسجيل
        settings = RegistrationSettings.get_settings()
        if not settings.is_teacher_registration_open:
            return jsonify({
                'success': False,
                'error': settings.teacher_closed_message or 'تسجيل المعلمين مغلق حالياً'
            }), 403
        
        data = request.get_json() or request.form
        
        # استخراج البيانات
        name = data.get('name', '').strip()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        phone = data.get('phone', '').strip() or None
        school = data.get('school', '').strip() or None
        
        # التحقق من البيانات المطلوبة
        if not name or not username or not email or not password:
            return jsonify({
                'success': False,
                'error': 'الاسم واسم المستخدم والإيميل وكلمة المرور مطلوبة'
            }), 400
        
        # التحقق من طول كلمة المرور
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'
            }), 400
        
        # التحقق من صيغة الإيميل
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'error': 'صيغة الإيميل غير صحيحة'
            }), 400
        
        # التحقق من الحقول الإضافية المطلوبة
        if settings.teacher_require_phone and not phone:
            return jsonify({
                'success': False,
                'error': 'رقم الجوال مطلوب'
            }), 400
        
        if settings.teacher_require_school and not school:
            return jsonify({
                'success': False,
                'error': 'اسم المدرسة مطلوب'
            }), 400
        
        # التحقق من عدم تكرار اسم المستخدم (في الطلاب والمعلمين)
        if Teacher.query.filter_by(username=username).first():
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم موجود مسبقاً'
            }), 400
        
        if Student.query.filter_by(username=username).first():
            return jsonify({
                'success': False,
                'error': 'اسم المستخدم موجود مسبقاً'
            }), 400
        
        # التحقق من عدم تكرار الإيميل
        if Teacher.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'error': 'الإيميل مسجل مسبقاً'
            }), 400
        
        # تشفير كلمة المرور
        password_hash = generate_password_hash(password)
        
        # إنشاء طلب التحقق (نستخدم نفس الجدول مع علامة مميزة)
        verification = EmailVerification.create_verification(
            email=email,
            name=name,
            username=username,
            password_hash=password_hash,
            phone=phone,
            school=school,
            grade='teacher'  # ✅ نستخدم حقل grade للتمييز
        )
        
        # إرسال رمز التحقق بالإيميل
        success, message = email_service.send_verification_code(
            to_email=email,
            code=verification.code,
            student_name=name  # نستخدم نفس القالب
        )
        
        if not success:
            db.session.delete(verification)
            db.session.commit()
            return jsonify({
                'success': False,
                'error': f'فشل إرسال رمز التحقق: {message}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم إرسال رمز التحقق إلى بريدك الإلكتروني',
            'email': email,
            'expires_in': 180
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في تسجيل المعلم: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في التسجيل'
        }), 500


# ==================== الخطوة 2: التحقق من الرمز ====================
@registration_bp.route('/verify', methods=['POST'])
def verify_code():
    """التحقق من رمز الإيميل وإنشاء الحساب (طالب أو معلم)"""
    try:
        data = request.get_json() or request.form
        
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        account_type = data.get('account_type', 'student')  # ✅ جديد
        
        if not email or not code:
            return jsonify({
                'success': False,
                'error': 'الإيميل ورمز التحقق مطلوبان'
            }), 400
        
        # البحث عن طلب التحقق
        verification = EmailVerification.query.filter_by(
            email=email,
            is_verified=False
        ).order_by(EmailVerification.created_at.desc()).first()
        
        if not verification:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على طلب تسجيل. يرجى إعادة التسجيل'
            }), 404
        
        # التحقق من الرمز
        success, message = verification.verify_code(code)
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        # جلب إعدادات التسجيل
        settings = RegistrationSettings.get_settings()
        
        # ✅ التحقق من نوع الحساب
        is_teacher = verification.grade == 'teacher' or account_type == 'teacher'
        
        if is_teacher:
            # ==================== إنشاء حساب معلم ====================
            # التحقق مرة أخرى من عدم تكرار البيانات
            if Teacher.query.filter_by(username=verification.username).first():
                return jsonify({
                    'success': False,
                    'error': 'اسم المستخدم أصبح محجوزاً. يرجى إعادة التسجيل'
                }), 400
            
            if Teacher.query.filter_by(email=verification.email).first():
                return jsonify({
                    'success': False,
                    'error': 'الإيميل أصبح مسجلاً. يرجى إعادة التسجيل'
                }), 400
            
            # إنشاء حساب المعلم
            # ✅ إذا أدخل رقم جوال → لا يُفعّل إلا بعد التحقق من الجوال
            has_phone = bool(verification.phone)
            should_activate = settings.teacher_auto_activate
            if has_phone:
                should_activate = False
            
            teacher = Teacher(
                name=verification.name,
                username=verification.username,
                email=verification.email,
                password_hash=verification.password_hash,
                phone=verification.phone,
                school=verification.school,
                is_active=should_activate
            )
            
            db.session.add(teacher)
            db.session.commit()
            
            # إنشاء JWT Token
            token = create_teacher_token(
                teacher_id=teacher.id,
                username=teacher.username
            )
            
            return jsonify({
                'success': True,
                'message': 'تم إنشاء حساب المعلم بنجاح',
                'token': token,
                'teacher': teacher.to_dict(),
                'account_type': 'teacher',
                'auto_login': should_activate,
                'require_phone_verification': has_phone,
                'phone': verification.phone
            })
        else:
            # ==================== إنشاء حساب طالب ====================
            # التحقق مرة أخرى من عدم تكرار البيانات
            if Student.query.filter_by(username=verification.username).first():
                return jsonify({
                    'success': False,
                    'error': 'اسم المستخدم أصبح محجوزاً. يرجى إعادة التسجيل'
                }), 400
            
            if Student.query.filter_by(email=verification.email).first():
                return jsonify({
                    'success': False,
                    'error': 'الإيميل أصبح مسجلاً. يرجى إعادة التسجيل'
                }), 400
            
            # إنشاء حساب الطالب
            # ✅ إذا أدخل رقم جوال → لا يُفعّل إلا بعد التحقق من الجوال
            has_phone = bool(verification.phone)
            should_activate = settings.auto_activate
            if has_phone:
                should_activate = False  # ينتظر التحقق من الجوال
            
            student = Student(
                name=verification.name,
                username=verification.username,
                email=verification.email,
                password_hash=verification.password_hash,
                phone=verification.phone,
                school=verification.school,
                grade=verification.grade,
                is_active=should_activate
            )
            
            db.session.add(student)
            db.session.commit()
            
            # تحديث آخر تسجيل دخول
            student.update_last_login()
            
            # إنشاء JWT Token
            token = create_student_token(
                student_id=student.id,
                username=student.username
            )
            
            return jsonify({
                'success': True,
                'message': 'تم إنشاء الحساب بنجاح',
                'token': token,
                'student': student.to_dict(),
                'account_type': 'student',
                'auto_login': should_activate,
                'require_phone_verification': has_phone,  # ✅ هل يحتاج تحقق جوال؟
                'phone': verification.phone  # ✅ رقم الجوال للتحقق
            })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في التحقق: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في التحقق'
        }), 500


# ==================== إعادة إرسال الرمز ====================

# ==================== ✅ جديد: تفعيل الحساب بعد التحقق من الجوال ====================
@registration_bp.route('/activate-after-phone', methods=['POST'])
def activate_after_phone():
    """تفعيل الحساب بعد التحقق من رقم الجوال عبر Firebase"""
    try:
        data = request.get_json() or request.form
        
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        firebase_uid = data.get('firebase_uid', '').strip()  # معرف Firebase للتوثيق
        account_type = data.get('account_type', 'student')
        
        if not email or not phone:
            return jsonify({
                'success': False,
                'error': 'الإيميل ورقم الجوال مطلوبان'
            }), 400
        
        if account_type == 'teacher':
            # تفعيل حساب معلم
            user = Teacher.query.filter_by(email=email).first()
        else:
            # تفعيل حساب طالب
            user = Student.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'الحساب غير موجود'
            }), 404
        
        # تفعيل الحساب
        user.is_active = True
        # تحديث رقم الجوال المتحقق منه
        user.phone = phone
        db.session.commit()
        
        # إنشاء التوكن
        if account_type == 'teacher':
            token = create_teacher_token(
                teacher_id=user.id,
                username=user.username
            )
        else:
            token = create_student_token(
                student_id=user.id,
                username=user.username
            )
        
        print(f"✅ تم تفعيل حساب {account_type}: {email} بعد التحقق من الجوال {phone}")
        
        return jsonify({
            'success': True,
            'message': 'تم تفعيل الحساب بنجاح',
            'token': token,
            'is_active': True
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في تفعيل الحساب: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في تفعيل الحساب'
        }), 500


@registration_bp.route('/resend', methods=['POST'])
def resend_code():
    """إعادة إرسال رمز التحقق"""
    try:
        data = request.get_json() or request.form
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'الإيميل مطلوب'
            }), 400
        
        # البحث عن طلب التحقق الأخير
        verification = EmailVerification.query.filter_by(
            email=email,
            is_verified=False
        ).order_by(EmailVerification.created_at.desc()).first()
        
        if not verification:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على طلب تسجيل. يرجى إعادة التسجيل'
            }), 404
        
        # إنشاء رمز جديد
        from datetime import datetime, timedelta
        verification.code = EmailVerification.generate_code()
        verification.expires_at = datetime.utcnow() + timedelta(minutes=3)
        verification.attempts = 0
        db.session.commit()
        
        # إرسال الرمز الجديد
        success, message = email_service.send_verification_code(
            to_email=email,
            code=verification.code,
            student_name=verification.name
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'فشل إرسال رمز التحقق: {message}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم إرسال رمز جديد إلى بريدك الإلكتروني',
            'expires_in': 180
        })
        
    except Exception as e:
        print(f"❌ خطأ في إعادة الإرسال: {e}")
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في إعادة الإرسال'
        }), 500


# ==================== APIs إدارة التسجيل (للأدمن) ====================
from flask_login import login_required, current_user
from functools import wraps

def admin_required(f):
    """التحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'error': 'غير مصرح'}), 403
        return f(*args, **kwargs)
    return decorated_function


@registration_bp.route('/admin/settings', methods=['GET'])
@login_required
@admin_required
def get_admin_settings():
    """جلب إعدادات التسجيل (للأدمن)"""
    try:
        settings = RegistrationSettings.get_settings()
        return jsonify({
            'success': True,
            'settings': settings.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@registration_bp.route('/admin/settings', methods=['POST'])
@login_required
@admin_required
def update_admin_settings():
    """تحديث إعدادات التسجيل (للأدمن)"""
    try:
        data = request.get_json() or request.form
        
        settings = RegistrationSettings.update_settings(
            # إعدادات الطلاب
            is_open=data.get('is_registration_open'),
            message=data.get('closed_message'),
            require_phone=data.get('require_phone'),
            require_school=data.get('require_school'),
            auto_activate=data.get('auto_activate'),
            # ✅ جديد: إعدادات المعلمين
            is_teacher_open=data.get('is_teacher_registration_open'),
            teacher_message=data.get('teacher_closed_message'),
            teacher_require_phone=data.get('teacher_require_phone'),
            teacher_require_school=data.get('teacher_require_school'),
            teacher_auto_activate=data.get('teacher_auto_activate'),
            admin_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': 'تم تحديث الإعدادات بنجاح',
            'settings': settings.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@registration_bp.route('/admin/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_registration():
    """تبديل حالة التسجيل (فتح/إغلاق)"""
    try:
        data = request.get_json() or request.form
        account_type = data.get('type', 'student')  # ✅ جديد: نوع الحساب
        
        settings = RegistrationSettings.get_settings()
        
        if account_type == 'teacher':
            # تبديل تسجيل المعلمين
            new_status = not settings.is_teacher_registration_open
            RegistrationSettings.update_settings(
                is_teacher_open=new_status,
                admin_id=current_user.id
            )
            status_text = 'مفتوح' if new_status else 'مغلق'
            return jsonify({
                'success': True,
                'message': f'تسجيل المعلمين الآن {status_text}',
                'is_open': new_status,
                'type': 'teacher'
            })
        else:
            # تبديل تسجيل الطلاب
            new_status = not settings.is_registration_open
            RegistrationSettings.update_settings(
                is_open=new_status,
                admin_id=current_user.id
            )
            status_text = 'مفتوح' if new_status else 'مغلق'
            return jsonify({
                'success': True,
                'message': f'تسجيل الطلاب الآن {status_text}',
                'is_open': new_status,
                'type': 'student'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
