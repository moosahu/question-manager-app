"""
إدارة المعلمين - Routes
يسمح للأدمن بإضافة وتعديل وحذف المعلمين
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from src.extensions import db
from src.models.teacher import Teacher
from src.models.email_verification import RegistrationSettings  # ✅ جديد
from functools import wraps
from datetime import datetime

teachers_bp = Blueprint('teachers', __name__, url_prefix='/teachers')


def admin_required(f):
    """التحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('ليس لديك صلاحية الوصول لهذه الصفحة', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== صفحة قائمة المعلمين ====================
@teachers_bp.route('/')
@login_required
@admin_required
def list_teachers():
    """عرض قائمة المعلمين"""
    search = request.args.get('search', '')
    
    if search:
        teachers = Teacher.search_teachers(search)
    else:
        teachers = Teacher.get_all_teachers()
    
    # إحصائيات
    total = Teacher.query.count()
    active = Teacher.query.filter_by(is_active=True).count()
    inactive = total - active
    
    # ✅ جديد: جلب حالة التسجيل
    settings = RegistrationSettings.get_settings()
    
    return render_template('teachers/list.html', 
                         teachers=teachers,
                         search=search,
                         total=total,
                         active=active,
                         inactive=inactive,
                         is_teacher_registration_open=settings.is_teacher_registration_open)  # ✅ جديد


# ==================== إضافة معلم جديد ====================
@teachers_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_teacher():
    """إضافة معلم جديد"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        school = request.form.get('school', '').strip() or None
        is_active = request.form.get('is_active') == 'on'
        notes = request.form.get('notes', '').strip() or None
        
        # التحقق من البيانات
        if not name or not username or not password:
            flash('الاسم واسم المستخدم وكلمة المرور مطلوبة', 'danger')
            return render_template('teachers/add.html')
        
        # التحقق من عدم تكرار اسم المستخدم
        if Teacher.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return render_template('teachers/add.html')
        
        # التحقق من عدم تكرار البريد
        if email and Teacher.query.filter_by(email=email).first():
            flash('البريد الإلكتروني موجود مسبقاً', 'danger')
            return render_template('teachers/add.html')
        
        # إنشاء المعلم
        teacher = Teacher(
            name=name,
            username=username,
            email=email,
            phone=phone,
            school=school,
            is_active=is_active,
            notes=notes
        )
        teacher.set_password(password)
        
        try:
            db.session.add(teacher)
            db.session.commit()
            flash(f'تم إضافة المعلم "{name}" بنجاح', 'success')
            return redirect(url_for('teachers.list_teachers'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في إضافة المعلم: {str(e)}', 'danger')
    
    return render_template('teachers/add.html')


# ==================== تعديل معلم ====================
@teachers_bp.route('/edit/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_teacher(teacher_id):
    """تعديل بيانات معلم"""
    teacher = Teacher.query.get_or_404(teacher_id)
    
    if request.method == 'POST':
        teacher.name = request.form.get('name', '').strip()
        teacher.email = request.form.get('email', '').strip() or None
        teacher.phone = request.form.get('phone', '').strip() or None
        teacher.school = request.form.get('school', '').strip() or None
        teacher.is_active = request.form.get('is_active') == 'on'
        teacher.notes = request.form.get('notes', '').strip() or None
        
        # تغيير كلمة المرور (اختياري)
        new_password = request.form.get('password', '')
        if new_password:
            teacher.set_password(new_password)
        
        try:
            db.session.commit()
            flash(f'تم تحديث بيانات المعلم "{teacher.name}" بنجاح', 'success')
            return redirect(url_for('teachers.list_teachers'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في تحديث البيانات: {str(e)}', 'danger')
    
    return render_template('teachers/edit.html', teacher=teacher)


# ==================== حذف معلم ====================
@teachers_bp.route('/delete/<int:teacher_id>', methods=['POST'])
@login_required
@admin_required
def delete_teacher(teacher_id):
    """حذف معلم مع بياناته المرتبطة"""
    teacher = Teacher.query.get_or_404(teacher_id)
    name = teacher.name
    email = teacher.email

    try:
        db.session.expunge(teacher)

        # حذف البيانات المرتبطة
        for stmt, params in [
            ("DELETE FROM login_attempts WHERE user_id = :id AND user_type = 'teacher'", {'id': teacher_id}),
            ("DELETE FROM delete_account_otps WHERE user_id = :id AND user_type = 'teacher'", {'id': teacher_id}),
        ]:
            try:
                with db.session.begin_nested():
                    db.session.execute(db.text(stmt), params)
            except Exception:
                pass

        db.session.execute(
            db.text("DELETE FROM teachers WHERE id = :id"),
            {'id': teacher_id}
        )
        db.session.commit()

        # إشعار في صندوق الوارد
        try:
            from src.models.notification import Notification
            from src.models.user import User
            admin_user = User.query.filter_by(is_admin=True).first()
            if admin_user:
                notif = Notification(
                    title='🗑️ تم حذف معلم بواسطة الأدمن',
                    message=f'الاسم: {name}\nالإيميل: {email}',
                    type='admin_event',
                    user_id=admin_user.id,
                    is_read=False,
                )
                db.session.add(notif)
                db.session.commit()
        except Exception:
            pass

        flash(f'تم حذف المعلم "{name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في حذف المعلم: {str(e)}', 'danger')

    return redirect(url_for('teachers.list_teachers'))


# ==================== تبديل حالة المعلم ====================
@teachers_bp.route('/toggle/<int:teacher_id>', methods=['POST'])
@login_required
@admin_required
def toggle_teacher(teacher_id):
    """تفعيل/تعطيل حساب معلم"""
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.is_active = not teacher.is_active
    
    try:
        db.session.commit()
        status = "مفعل" if teacher.is_active else "معطل"
        flash(f'تم تغيير حالة المعلم "{teacher.name}" إلى {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في تغيير الحالة: {str(e)}', 'danger')
    
    return redirect(url_for('teachers.list_teachers'))


# ==================== إعادة تعيين جهاز المعلم ====================
@teachers_bp.route('/reset-device/<int:teacher_id>', methods=['POST'])
@login_required
@admin_required
def reset_teacher_device(teacher_id):
    """إزالة ربط جهاز المعلم"""
    teacher = Teacher.query.get_or_404(teacher_id)
    
    try:
        teacher.clear_device_info()
        flash(f'تم إزالة ربط جهاز المعلم "{teacher.name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في إزالة ربط الجهاز: {str(e)}', 'danger')
    
    return redirect(url_for('teachers.edit_teacher', teacher_id=teacher_id))


# ==================== ✅ جديد: تبديل حالة التسجيل الذاتي ====================
@teachers_bp.route('/toggle-registration', methods=['POST'])
@login_required
@admin_required
def toggle_registration():
    """تبديل حالة التسجيل الذاتي للمعلمين"""
    try:
        settings = RegistrationSettings.get_settings()
        new_status = not settings.is_teacher_registration_open
        
        RegistrationSettings.update_settings(
            is_teacher_open=new_status,
            admin_id=current_user.id
        )
        
        if new_status:
            flash('تم فتح التسجيل الذاتي للمعلمين ✓', 'success')
        else:
            flash('تم إغلاق التسجيل الذاتي للمعلمين', 'warning')
            
    except Exception as e:
        flash(f'خطأ في تغيير حالة التسجيل: {str(e)}', 'danger')
    
    return redirect(url_for('teachers.list_teachers'))


# ==================== Mobile API Endpoints ====================

@teachers_bp.route('/api/mobile/list', methods=['GET'])
@login_required
@admin_required
def api_mobile_list_teachers():
    """قائمة المعلمين للموبايل"""
    from src.models.teacher import Teacher
    search = request.args.get('search', '')
    query = Teacher.query
    if search:
        query = query.filter(
            db.or_(
                Teacher.name.ilike(f'%{search}%'),
                Teacher.username.ilike(f'%{search}%'),
            )
        )
    teachers = query.order_by(Teacher.name).all()
    return jsonify({
        'success': True,
        'teachers': [
            {
                'id': t.id,
                'name': t.name,
                'username': t.username,
                'email': t.email or '',
                'is_active': t.is_active if hasattr(t, 'is_active') else True,
                'created_at': t.created_at.isoformat() if t.created_at else '',
                'last_login': t.last_login.isoformat() if t.last_login else '',
            }
            for t in teachers
        ],
    })


@teachers_bp.route('/api/mobile/add', methods=['POST'])
@login_required
@admin_required
def api_mobile_add_teacher():
    """إضافة معلم جديد"""
    from src.models.teacher import Teacher
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip() or None

    if not name or not username or not password:
        return jsonify({'success': False, 'error': 'الاسم واسم المستخدم وكلمة المرور مطلوبة'}), 400

    if Teacher.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'اسم المستخدم موجود مسبقاً'}), 409

    teacher = Teacher(name=name, username=username, email=email)
    teacher.set_password(password)

    try:
        db.session.add(teacher)
        db.session.commit()
        return jsonify({'success': True, 'message': f'تم إضافة المعلم "{name}"', 'teacher_id': teacher.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/mobile/<int:teacher_id>/edit', methods=['POST'])
@login_required
@admin_required
def api_mobile_edit_teacher(teacher_id):
    """تعديل بيانات معلم"""
    from src.models.teacher import Teacher
    teacher = Teacher.query.get_or_404(teacher_id)
    data = request.get_json() or {}
    if 'name' in data:
        teacher.name = data['name'].strip()
    if 'email' in data:
        teacher.email = data['email'].strip() or None
    new_password = data.get('password', '')
    if new_password:
        teacher.set_password(new_password)
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم التحديث بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/mobile/<int:teacher_id>/delete', methods=['POST'])
@login_required
@admin_required
def api_mobile_delete_teacher(teacher_id):
    """حذف معلم مع بياناته المرتبطة"""
    from src.models.teacher import Teacher
    teacher = Teacher.query.get_or_404(teacher_id)
    name = teacher.name
    email = teacher.email
    try:
        db.session.expunge(teacher)

        for stmt, params in [
            ("DELETE FROM login_attempts WHERE user_id = :id AND user_type = 'teacher'", {'id': teacher_id}),
            ("DELETE FROM delete_account_otps WHERE user_id = :id AND user_type = 'teacher'", {'id': teacher_id}),
        ]:
            try:
                with db.session.begin_nested():
                    db.session.execute(db.text(stmt), params)
            except Exception:
                pass

        db.session.execute(
            db.text("DELETE FROM teachers WHERE id = :id"),
            {'id': teacher_id}
        )
        db.session.commit()

        # إشعار في صندوق الوارد
        try:
            from src.models.notification import Notification
            from src.models.user import User
            admin_user = User.query.filter_by(is_admin=True).first()
            if admin_user:
                notif = Notification(
                    title='🗑️ تم حذف معلم بواسطة الأدمن',
                    message=f'الاسم: {name}\nالإيميل: {email}',
                    type='admin_event',
                    user_id=admin_user.id,
                    is_read=False,
                )
                db.session.add(notif)
                db.session.commit()
        except Exception:
            pass

        return jsonify({'success': True, 'message': f'تم حذف المعلم "{name}"'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/mobile/<int:teacher_id>/toggle', methods=['POST'])
@login_required
@admin_required
def api_mobile_toggle_teacher(teacher_id):
    """تفعيل/تعطيل حساب معلم عبر الموبايل"""
    from src.models.teacher import Teacher
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.is_active = not teacher.is_active
    try:
        db.session.commit()
        status = 'مفعّل' if teacher.is_active else 'معطّل'
        return jsonify({'success': True, 'message': f'تم تغيير حالة المعلم "{teacher.name}" إلى {status}',
                        'is_active': teacher.is_active})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
