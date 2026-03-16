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
from src.middleware.auth_middleware import create_student_token, create_teacher_token

registration_bp = Blueprint('registration', __name__, url_prefix='/api/registration')

import re
from src.models.notification import Notification


def notify_admin(title, message):
    """إرسال إشعار للأدمن (إيميل + push + حفظ في DB)"""
    admin_email = None
    admin_fcm = None
    admin_user = None

    try:
        from src.models.user import User
        admin_user = User.query.filter_by(is_admin=True).first()
        if admin_user:
            admin_email = admin_user.email
            if admin_user.fcm_token:
                admin_fcm = admin_user.fcm_token
    except Exception as e:
        print(f"⚠️ فشل جلب الأدمن من user: {e}")

    # 1. حفظ في DB
    if admin_user:
        try:
            notif = Notification(
                title=title,
                message=message,
                type='admin_event',
                user_id=admin_user.id,
                is_read=False,
            )
            db.session.add(notif)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ فشل حفظ إشعار الأدمن في DB: {e}")

    # 2. إرسال إيميل
    if admin_email:
        try:
            email_service.send_admin_notification(admin_email, title, message)
        except Exception as e:
            print(f"⚠️ فشل إرسال إيميل الأدمن: {e}")

    # 3. إرسال push notification
    if admin_fcm:
        try:
            from src.services.notification_service import NotificationService
            NotificationService.send_fcm_notification(
                admin_fcm, title, message.replace('\n', ' - ')
            )
        except Exception as e:
            print(f"⚠️ فشل push notification: {e}")

BLOCKED_EMAIL_DOMAINS = [
    'tempmail.org', 'guerrillamail.com', 'yopmail.com', 'throwaway.email',
    'temp-mail.org', 'fakeinbox.com', 'mailinator.com', 'trashmail.com',
    'dispostable.com', 'sharklasers.com', 'guerrillamailblock.com', 'grr.la',
    'tempail.com', 'mohmal.com', 'emailondeck.com', 'tempr.email',
    '10minutemail.com', 'minutemail.com', 'maildrop.cc', 'harakirimail.com',
]

WEAK_PASSWORDS = [
    '12345678', '123456789', '1234567890', 'password1', 'password123',
    'qwerty123', 'abcd1234', 'abcdef12', '11111111', '12341234',
    'iloveyou1', 'admin123', 'welcome1', 'monkey123', 'dragon123',
    'letmein1', 'football1', 'baseball1', 'abc12345', 'trustno1',
    'sunshine1', 'princess1', 'charlie1', 'password12',
]


_NAME_BLACKLIST = {
    # تحيات وعبارات ترحيب
    'أهلا', 'اهلا', 'وسهلا', 'مرحبا', 'هلا', 'يهلا', 'هلو', 'اهلين', 'يسلم',
    'حياك', 'حياكم', 'تسلم', 'تسلمين',
    # عبارات شائعة
    'كيفك', 'زين', 'تمام', 'حسنا', 'اوكي', 'اوك', 'يلا', 'ياله', 'شكرا', 'عفوا',
    'ماشي', 'خلاص', 'واجد', 'حيل', 'شلون', 'واو', 'لول', 'هيهي', 'لالا', 'هاها',
    # ضمائر منفصلة
    'انا', 'أنا', 'انت', 'أنت', 'انتي', 'أنتي', 'هو', 'هي', 'هم', 'نحن', 'انتم', 'أنتم',
    'هما', 'انتما', 'أنتما',
    # أسماء إشارة
    'هذا', 'هذي', 'هذه', 'ذاك', 'ذلك', 'تلك', 'هؤلاء', 'أولئك',
    # ظروف مكان وزمان
    'هنا', 'هناك', 'الان', 'الآن', 'اليوم', 'امس', 'أمس', 'غدا', 'غداً',
    'دائما', 'دائماً', 'أبدا', 'أبداً', 'أحيانا',
    # أدوات استفهام
    'ماذا', 'متى', 'اين', 'أين', 'لماذا', 'لمن', 'كيفما',
    # نعم/لا وردود
    'نعم', 'لا', 'بلى', 'ايه', 'ايوه', 'آه', 'اوف', 'اوه',
    # حروف جر وأدوات (لا تكون أسماء)
    'في', 'على', 'عن', 'مع', 'عند', 'الى', 'إلى', 'حتى', 'بين', 'عبر',
    'قبل', 'بعد', 'فوق', 'تحت', 'امام', 'أمام', 'خلف', 'يمين', 'يسار',
    'لكن', 'لكنه', 'لكنها', 'اذا', 'إذا', 'لأن', 'لان', 'لأنه', 'لأنها',
    # ضمائر متصلة (بدون الاسم)
    'بك', 'لك', 'منك', 'معك', 'عنك', 'فيك', 'عليك', 'اليك', 'إليك', 'الك', 'معاك',
    'بهم', 'لهم', 'منهم', 'معهم', 'بها', 'لها', 'منها', 'معها',
    # أرقام مكتوبة
    'واحد', 'اثنين', 'اثنان', 'ثلاثة', 'اربعة', 'أربعة', 'خمسة', 'ستة',
    'سبعة', 'ثمانية', 'تسعة', 'عشرة', 'مئة', 'مائة', 'الف', 'ألف',
    # عائلي (ليس أسماء)
    'ابوي', 'اخوي', 'اختي', 'امي', 'أمي', 'عمي', 'خالي', 'جدي', 'جدتي',
    'خالتي', 'عمتي', 'ابني', 'بنتي',
    # كلمات عشوائية/اختبار
    'تجربة', 'اختبار', 'مجهول', 'معروف', 'شخص', 'مستخدم',
    'test', 'hello', 'welcome', 'admin', 'user', 'fake', 'name',
    'null', 'none', 'password', 'pass', 'guest', 'unknown',
}

_SCHOOL_BLACKLIST = _NAME_BLACKLIST | {
    # كلمات خاصة بالمدارس لا معنى لها كاسم مدرسة
    'بيتي', 'منزلي', 'شارع', 'حارة', 'طريق', 'حي', 'منطقة',
}


def validate_arabic_name(name):
    """التحقق من صحة الاسم - يرجع None لو صحيح، أو رسالة الخطأ"""
    if len(name) > 40:
        return 'الاسم يجب أن يكون 40 حرف كحد أقصى'
    name_parts = name.split()
    if len(name_parts) < 3:
        return 'يجب كتابة الاسم الثلاثي على الأقل (مثال: أحمد محمد علي)'
    if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', name):
        return 'الاسم يجب أن يحتوي على حروف فقط'
    # منع خلط العربي والإنجليزي
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', name))
    has_english = bool(re.search(r'[a-zA-Z]', name))
    if has_arabic and has_english:
        return 'يرجى كتابة الاسم بلغة واحدة (عربي أو إنجليزي)'
    if name_parts[0] in ['ابو', 'أبو', 'ام', 'أم']:
        return 'يرجى كتابة الاسم الحقيقي بدون ألقاب (ابو/ام)'
    # منع تكرار أي كلمتين متطابقتين
    if len(set(name_parts)) < len(name_parts):
        return 'الاسم يحتوي على كلمات متكررة'
    if any(len(part) < 2 for part in name_parts):
        return 'كل جزء من الاسم يجب أن يكون حرفين على الأقل'
    # منع الأحرف المكررة (ااااا أو hhhhh)
    if re.search(r'(.)\1{3,}', name):
        return 'الرجاء إدخال اسم صحيح'
    # منع كلمات كلها نفس الحرف (هه، كك، للل)
    for part in name_parts:
        if re.match(r'^(.)\1+$', part):
            return 'الرجاء إدخال اسم صحيح'
    # منع الكلمات غير الأسماء
    for part in name_parts:
        if part in _NAME_BLACKLIST:
            return 'الرجاء إدخال الاسم الحقيقي'
    return None


def validate_school_name(school):
    """التحقق من صحة اسم المدرسة - يرجع None لو صحيح، أو رسالة الخطأ"""
    if len(school) < 10:
        return 'اسم المدرسة يجب أن يكون 10 أحرف على الأقل'
    if len(school) > 80:
        return 'اسم المدرسة يجب أن يكون 80 حرف كحد أقصى'
    if not re.match(r'^[\u0600-\u06FFa-zA-Z0-9\s]+$', school):
        return 'اسم المدرسة يحتوي على رموز غير مسموحة'
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', school))
    has_english = bool(re.search(r'[a-zA-Z]', school))
    if has_arabic and has_english:
        return 'اسم المدرسة يجب أن يكون بلغة واحدة'
    school_parts = school.split()
    if len(school_parts) < 2:
        return 'اسم المدرسة يجب أن يكون كلمتين على الأقل'
    if re.search(r'(.)\1{3,}', school):
        return 'الرجاء إدخال اسم مدرسة صحيح'
    for part in school_parts:
        if re.match(r'^(.)\1+$', part):
            return 'الرجاء إدخال اسم مدرسة صحيح'
        if part in _SCHOOL_BLACKLIST:
            return 'الرجاء إدخال اسم مدرسة صحيح'
    return None


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

        # التحقق من صحة الاسم
        name_error = validate_arabic_name(name)
        if name_error:
            return jsonify({'success': False, 'error': name_error}), 400

        # التحقق من اسم المدرسة لو مُدخَل
        if school:
            school_error = validate_school_name(school)
            if school_error:
                return jsonify({'success': False, 'error': school_error}), 400

        # التحقق من اسم المستخدم
        if len(username) < 4 or len(username) > 20:
            return jsonify({'success': False, 'error': 'اسم المستخدم يجب أن يكون بين 4 و 20 حرف'}), 400
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]+$', username):
            return jsonify({'success': False, 'error': 'اسم المستخدم: حروف إنجليزية وأرقام فقط، يبدأ بحرف'}), 400

        # التحقق من كلمة المرور
        if len(password) < 8:
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'}), 400
        if not re.search(r'[a-zA-Z]', password):
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تحتوي على حرف واحد على الأقل'}), 400
        if not re.search(r'[0-9]', password):
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تحتوي على رقم واحد على الأقل'}), 400
        if password.lower() in WEAK_PASSWORDS:
            return jsonify({'success': False, 'error': 'كلمة المرور ضعيفة جداً، اختر كلمة مرور أقوى'}), 400

        # التحقق من صيغة الإيميل
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'success': False, 'error': 'صيغة الإيميل غير صحيحة'}), 400
        # منع الإيميلات المؤقتة
        email_domain = email.split('@')[-1]
        if email_domain in BLOCKED_EMAIL_DOMAINS:
            return jsonify({'success': False, 'error': 'هذا النوع من الإيميلات غير مسموح، استخدم إيميل حقيقي'}), 400
        
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

        # التحقق من صحة الاسم
        name_error = validate_arabic_name(name)
        if name_error:
            return jsonify({'success': False, 'error': name_error}), 400

        # التحقق من اسم المدرسة لو مُدخَل
        if school:
            school_error = validate_school_name(school)
            if school_error:
                return jsonify({'success': False, 'error': school_error}), 400

        # التحقق من اسم المستخدم
        if len(username) < 4 or len(username) > 20:
            return jsonify({'success': False, 'error': 'اسم المستخدم يجب أن يكون بين 4 و 20 حرف'}), 400
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]+$', username):
            return jsonify({'success': False, 'error': 'اسم المستخدم: حروف إنجليزية وأرقام فقط، يبدأ بحرف'}), 400

        # التحقق من كلمة المرور
        if len(password) < 8:
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'}), 400
        if not re.search(r'[a-zA-Z]', password):
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تحتوي على حرف واحد على الأقل'}), 400
        if not re.search(r'[0-9]', password):
            return jsonify({'success': False, 'error': 'كلمة المرور يجب أن تحتوي على رقم واحد على الأقل'}), 400
        if password.lower() in WEAK_PASSWORDS:
            return jsonify({'success': False, 'error': 'كلمة المرور ضعيفة جداً، اختر كلمة مرور أقوى'}), 400

        # التحقق من صيغة الإيميل
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'success': False, 'error': 'صيغة الإيميل غير صحيحة'}), 400
        # منع الإيميلات المؤقتة
        email_domain = email.split('@')[-1]
        if email_domain in BLOCKED_EMAIL_DOMAINS:
            return jsonify({'success': False, 'error': 'هذا النوع من الإيميلات غير مسموح، استخدم إيميل حقيقي'}), 400
        
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
        
        # ✅ نقطة القرار: هل أدخل المستخدم رقم جوال؟
        has_phone = bool(verification.phone)
        
        # ✅ فحص إضافي: إذا الجوال إجباري ولكن المستخدم ما أدخله
        require_phone = settings.teacher_require_phone if is_teacher else settings.require_phone
        if require_phone and not has_phone:
            return jsonify({
                'success': False,
                'error': 'رقم الجوال مطلوب لإكمال التسجيل'
            }), 400
        
        # =================================================================
        #  السيناريو 1: المستخدم أدخل رقم جوال (التحقق عبر Firebase)
        #  → ننشئ الحساب بـ is_active=False وننتظر التحقق من الجوال
        # =================================================================
        if has_phone:
            if is_teacher:
                if Teacher.query.filter_by(username=verification.username).first():
                    return jsonify({'success': False, 'error': 'اسم المستخدم أصبح محجوزاً'}), 400
                if Teacher.query.filter_by(email=verification.email).first():
                    return jsonify({'success': False, 'error': 'الإيميل أصبح مسجلاً'}), 400
                
                teacher = Teacher(
                    name=verification.name,
                    username=verification.username,
                    email=verification.email,
                    password_hash=verification.password_hash,
                    phone=verification.phone,
                    school=verification.school,
                    is_active=False  # ❌ غير مفعّل حتى يتحقق من الجوال
                )
                db.session.add(teacher)
                db.session.commit()
                
                token = create_teacher_token(teacher_id=teacher.id, username=teacher.username)
                print(f"🐞 Teacher created (inactive): phone='{verification.phone}', waiting for phone verification")
                
                return jsonify({
                    'success': True,
                    'message': 'تم التحقق من الإيميل. يرجى التحقق من رقم الجوال.',
                    'require_phone_verification': True,
                    'phone': verification.phone,
                    'token': token,
                    'teacher': teacher.to_dict(),
                    'account_type': 'teacher',
                    'auto_login': False
                })
            else:
                if Student.query.filter_by(username=verification.username).first():
                    return jsonify({'success': False, 'error': 'اسم المستخدم أصبح محجوزاً'}), 400
                if Student.query.filter_by(email=verification.email).first():
                    return jsonify({'success': False, 'error': 'الإيميل أصبح مسجلاً'}), 400
                
                student = Student(
                    name=verification.name,
                    username=verification.username,
                    email=verification.email,
                    password_hash=verification.password_hash,
                    phone=verification.phone,
                    school=verification.school,
                    grade=verification.grade,
                    is_active=False  # ❌ غير مفعّل حتى يتحقق من الجوال
                )
                db.session.add(student)
                db.session.commit()
                
                token = create_student_token(student_id=student.id, username=student.username)
                print(f"🐞 Student created (inactive): phone='{verification.phone}', waiting for phone verification")
                
                return jsonify({
                    'success': True,
                    'message': 'تم التحقق من الإيميل. يرجى التحقق من رقم الجوال.',
                    'require_phone_verification': True,
                    'phone': verification.phone,
                    'token': token,
                    'student': student.to_dict(),
                    'account_type': 'student',
                    'auto_login': False
                })
        
        # =================================================================
        #  السيناريو 2: المستخدم لم يدخل رقم جوال (تفعيل مباشر)
        # =================================================================
        
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
            
            # ✅ إذا أدخل رقم جوال → لا يُفعّل إلا بعد التحقق من الجوال
            has_phone = bool(verification.phone)
            should_activate = settings.teacher_auto_activate
            if has_phone:
                should_activate = False
            
            print(f"🐞 Teacher verify: phone='{verification.phone}', has_phone={has_phone}, should_activate={should_activate}")
            
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
            
            # إشعار الأدمن
            notify_admin(
                '👨‍🏫 معلم جديد سجّل',
                f'الاسم: {teacher.name}\nالإيميل: {teacher.email}\nالمدرسة: {teacher.school or "غير محدد"}'
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
            
            # ✅ إذا أدخل رقم جوال → لا يُفعّل إلا بعد التحقق من الجوال
            has_phone = bool(verification.phone)
            should_activate = settings.auto_activate
            if has_phone:
                should_activate = False  # ينتظر التحقق من الجوال
            
            print(f"🐞 Student verify: phone='{verification.phone}', has_phone={has_phone}, should_activate={should_activate}")
            
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
            
            # إشعار الأدمن
            notify_admin(
                '🎓 طالب جديد سجّل',
                f'الاسم: {student.name}\nالإيميل: {student.email}\nالمدرسة: {student.school or "غير محدد"}'
            )

            return jsonify({
                'success': True,
                'message': 'تم إنشاء الحساب بنجاح',
                'token': token,
                'student': student.to_dict(),
                'account_type': 'student',
                'auto_login': should_activate,
                'require_phone_verification': has_phone,
                'phone': verification.phone
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

# ==================== ✅ جديد: التحقق من رمز الجوال وإنشاء الحساب ====================
@registration_bp.route('/verify-phone', methods=['POST'])
def verify_phone_code():
    """التحقق من رمز الجوال وإنشاء الحساب وتفعيله"""
    try:
        data = request.get_json() or request.form
        email = data.get('email', '').strip().lower()
        phone_code = data.get('code', '').strip()
        account_type = data.get('account_type', 'student')

        if not email or not phone_code:
            return jsonify({
                'success': False,
                'error': 'الإيميل ورمز التحقق من الجوال مطلوبان'
            }), 400

        # البحث عن طلب التحقق الذي تم فيه التحقق من الإيميل
        verification = EmailVerification.query.filter_by(
            email=email,
            is_verified=True
        ).order_by(EmailVerification.created_at.desc()).first()

        if not verification or not verification.phone:
            return jsonify({
                'success': False,
                'error': 'لم يتم العثور على طلب تسجيل صالح للتحقق من الجوال.'
            }), 404

        # التحقق من رمز الجوال
        success, message = verification.verify_phone_code(phone_code)
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400

        # الآن يمكننا إنشاء الحساب وتفعيله
        settings = RegistrationSettings.get_settings()
        is_teacher = verification.grade == 'teacher' or account_type == 'teacher'

        if is_teacher:
            # ==================== إنشاء حساب معلم ====================
            if Teacher.query.filter_by(username=verification.username).first() or \
               Teacher.query.filter_by(email=verification.email).first():
                return jsonify({
                    'success': False,
                    'error': 'اسم المستخدم أو الإيميل أصبح محجوزاً.'
                }), 400

            teacher = Teacher(
                name=verification.name,
                username=verification.username,
                email=verification.email,
                password_hash=verification.password_hash,
                phone=verification.phone,
                school=verification.school,
                is_active=True  # ✅ تفعيل الحساب
            )
            db.session.add(teacher)
            db.session.commit()
            
            token = create_teacher_token(teacher_id=teacher.id, username=teacher.username)

            return jsonify({
                'success': True,
                'message': 'تم إنشاء حساب المعلم بنجاح',
                'token': token,
                'teacher': teacher.to_dict(),
                'account_type': 'teacher',
                'auto_login': True
            })
        else:
            # ==================== إنشاء حساب طالب ====================
            if Student.query.filter_by(username=verification.username).first() or \
               Student.query.filter_by(email=verification.email).first():
                return jsonify({
                    'success': False,
                    'error': 'اسم المستخدم أو الإيميل أصبح محجوزاً.'
                }), 400

            student = Student(
                name=verification.name,
                username=verification.username,
                email=verification.email,
                password_hash=verification.password_hash,
                phone=verification.phone,
                school=verification.school,
                grade=verification.grade,
                is_active=True  # ✅ تفعيل الحساب
            )
            db.session.add(student)
            db.session.commit()
            student.update_last_login()
            
            token = create_student_token(student_id=student.id, username=student.username)

            return jsonify({
                'success': True,
                'message': 'تم إنشاء الحساب بنجاح',
                'token': token,
                'student': student.to_dict(),
                'account_type': 'student',
                'auto_login': True
            })

    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في التحقق من الجوال: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في التحقق من الجوال'
        }), 500


# ==================== تفعيل الحساب بعد التحقق من الجوال عبر Firebase ====================
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
