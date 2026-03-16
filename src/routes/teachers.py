"""
إدارة المعلمين - Routes
يسمح للأدمن بإضافة وتعديل وحذف المعلمين
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from src.extensions import db
from src.models.teacher import Teacher
from src.models.email_verification import RegistrationSettings  # ✅ جديد
from src.middleware.auth_middleware import verify_teacher_token
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


# ==================== Teacher-Student Link Endpoints ====================

@teachers_bp.route('/api/mobile/<int:teacher_id>/class-code', methods=['GET'])
@login_required
@admin_required
def api_get_teacher_class_code(teacher_id):
    """جلب كود الربط الخاص بالمعلم (للأدمن)"""
    from src.models.teacher import Teacher
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.ensure_class_code()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({
        'success': True,
        'class_code': teacher.class_code,
        'teacher_name': teacher.name,
    })


@teachers_bp.route('/api/mobile/<int:teacher_id>/students', methods=['GET'])
@login_required
@admin_required
def api_get_teacher_students(teacher_id):
    """قائمة طلاب المعلم مع آخر نشاط ومتوسط الدرجات (للأدمن)"""
    from src.models.teacher import Teacher
    from src.models.teacher_student import TeacherStudent
    from src.models.student import Student
    from src.models.student_result import StudentResult
    from sqlalchemy import func

    teacher = Teacher.query.get_or_404(teacher_id)
    links = TeacherStudent.query.filter_by(teacher_id=teacher_id).all()

    result = []
    for link in links:
        s = link.student
        if not s:
            continue
        # متوسط الدرجات
        avg = db.session.query(func.avg(StudentResult.score_percentage))\
            .filter_by(student_id=s.id).scalar()
        # عدد الاختبارات
        count = StudentResult.query.filter_by(student_id=s.id).count()
        result.append({
            'student_id': s.id,
            'name': s.name,
            'username': s.username,
            'grade': s.grade or '',
            'school': s.school or '',
            'is_active': s.is_active,
            'last_login': s.last_login.isoformat() if s.last_login else '',
            'joined_at': link.joined_at.isoformat() if link.joined_at else '',
            'avg_score': round(avg, 1) if avg is not None else None,
            'quiz_count': count,
        })

    return jsonify({
        'success': True,
        'teacher_name': teacher.name,
        'class_code': teacher.class_code or '',
        'students': result,
    })


def _build_student_results_response(student_id):
    """دالة مساعدة: تبني response النتائج المحسّن لأي طالب"""
    from src.models.student_result import StudentResult
    from src.models.student import Student

    student = Student.query.get_or_404(student_id)
    results = StudentResult.query.filter_by(student_id=student_id)\
        .order_by(StudentResult.created_at.desc()).limit(100).all()

    # إحصائيات عامة
    scores = [r.score_percentage for r in results if r.score_percentage is not None]
    if scores:
        avg_score = round(sum(scores) / len(scores), 1)
        max_score = max(scores)
        min_score = min(scores)
        last_score = scores[0] if scores else None
    else:
        avg_score = max_score = min_score = last_score = None

    # حساب trend (آخر 5 مقارنةً بالـ 5 السابقة)
    trend = 'stable'
    if len(scores) >= 6:
        recent_avg = sum(scores[:5]) / 5
        older_avg = sum(scores[5:10]) / len(scores[5:10])
        if recent_avg > older_avg + 5:
            trend = 'improving'
        elif recent_avg < older_avg - 5:
            trend = 'declining'

    # تجميع حسب quiz_name
    topics_map = {}
    for r in results:
        name = r.quiz_name or 'غير محدد'
        if name not in topics_map:
            topics_map[name] = {'scores': [], 'last_score': None}
        if r.score_percentage is not None:
            topics_map[name]['scores'].append(r.score_percentage)
        if topics_map[name]['last_score'] is None and r.score_percentage is not None:
            topics_map[name]['last_score'] = r.score_percentage

    topics = [
        {
            'name': name,
            'count': len(data['scores']),
            'avg': round(sum(data['scores']) / len(data['scores']), 1) if data['scores'] else None,
            'last_score': data['last_score'],
        }
        for name, data in topics_map.items()
    ]

    # آخر 10 اختبارات للرسم البياني (من الأقدم للأحدث)
    chart_results = [r for r in reversed(results[:10]) if r.score_percentage is not None]
    chart_data = [
        {
            'score': r.score_percentage,
            'date': f"{r.created_at.day}/{r.created_at.month}" if r.created_at else '',
        }
        for r in chart_results
    ]

    return {
        'success': True,
        'student': {
            'id': student.id,
            'name': student.name,
            'grade': student.grade or '',
        },
        'stats': {
            'avg_score': avg_score,
            'max_score': max_score,
            'min_score': min_score,
            'last_score': last_score,
            'total_quizzes': len(results),
            'trend': trend,
            'chart_data': chart_data,
        },
        'topics': topics,
        'results': [
            {
                'id': r.id,
                'quiz_name': r.quiz_name,
                'score_percentage': r.score_percentage,
                'correct_answers': r.correct_answers,
                'total_questions': r.total_questions,
                'wrong_answers': r.wrong_answers,
                'time_spent': r.time_spent,
                'quiz_type': r.quiz_type,
                'created_at': r.created_at.isoformat() if r.created_at else '',
            }
            for r in results
        ],
    }


@teachers_bp.route('/api/mobile/<int:teacher_id>/students/<int:student_id>/results', methods=['GET'])
@login_required
@admin_required
def api_get_teacher_student_results(teacher_id, student_id):
    """نتائج طالب معين تابع لمعلم (للأدمن)"""
    from src.models.teacher_student import TeacherStudent

    # تحقق أن الطالب فعلاً مرتبط بهذا المعلم
    TeacherStudent.query.filter_by(
        teacher_id=teacher_id, student_id=student_id).first_or_404()

    return jsonify(_build_student_results_response(student_id))


@teachers_bp.route('/api/mobile/<int:teacher_id>/students/<int:student_id>/remove', methods=['POST'])
@login_required
@admin_required
def api_remove_teacher_student(teacher_id, student_id):
    """إزالة طالب من قائمة المعلم"""
    from src.models.teacher_student import TeacherStudent
    link = TeacherStudent.query.filter_by(
        teacher_id=teacher_id, student_id=student_id).first_or_404()
    try:
        db.session.delete(link)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم إزالة الطالب من قائمتك'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/mobile/assign-by-code', methods=['POST'])
@login_required
@admin_required
def api_admin_assign_by_code():
    """
    الأدمن يربط طالب بمعلم عن طريق الكود (بدون تحديد teacher_id)
    Body: { student_id, class_code }
    """
    from src.models.teacher import Teacher
    from src.models.student import Student
    from src.models.teacher_student import TeacherStudent

    data = request.get_json() or {}
    student_id = data.get('student_id')
    class_code = (data.get('class_code') or '').strip().upper()

    if not student_id or not class_code:
        return jsonify({'success': False, 'error': 'student_id والكود مطلوبان'}), 400

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'error': 'الطالب غير موجود'}), 404

    # البحث بالكود في المعلمين أو الأدمن
    from src.models.user import User
    teacher = Teacher.query.filter_by(class_code=class_code).first()
    admin_owner = None
    if not teacher:
        admin_owner = User.query.filter_by(class_code=class_code, is_admin=True).first()
    if not teacher and not admin_owner:
        return jsonify({'success': False, 'error': 'الكود غير صحيح'}), 404

    owner_name = teacher.name if teacher else admin_owner.username

    existing = TeacherStudent.query.filter_by(student_id=student_id).first()
    if existing:
        same = (teacher and existing.teacher_id == teacher.id) or \
               (admin_owner and existing.admin_id == admin_owner.id)
        if same:
            return jsonify({'success': False, 'error': 'الطالب مرتبط بهذا الكود بالفعل'}), 409
        existing.teacher_id = teacher.id if teacher else None
        existing.admin_id = admin_owner.id if admin_owner else None
        existing.joined_at = datetime.utcnow()
        try:
            db.session.commit()
            return jsonify({'success': True,
                            'message': f'تم نقل الطالب "{student.name}" إلى "{owner_name}"'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    link = TeacherStudent(
        teacher_id=teacher.id if teacher else None,
        admin_id=admin_owner.id if admin_owner else None,
        student_id=student_id,
    )
    try:
        db.session.add(link)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'تم ربط الطالب "{student.name}" بـ "{owner_name}"',
            'teacher_name': owner_name,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/mobile/<int:teacher_id>/students/assign', methods=['POST'])
@login_required
@admin_required
def api_admin_assign_student(teacher_id):
    """
    الأدمن يربط طالب بمعلم مباشرة (بدون كود)
    Body: { student_id }
    """
    from src.models.teacher import Teacher
    from src.models.student import Student
    from src.models.teacher_student import TeacherStudent

    teacher = Teacher.query.get_or_404(teacher_id)
    data = request.get_json() or {}
    student_id = data.get('student_id')

    if not student_id:
        return jsonify({'success': False, 'error': 'student_id مطلوب'}), 400

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'error': 'الطالب غير موجود'}), 404

    # هل مرتبط بمعلم آخر؟
    existing = TeacherStudent.query.filter_by(student_id=student_id).first()
    if existing:
        if existing.teacher_id == teacher_id:
            return jsonify({'success': False, 'error': 'الطالب مرتبط بهذا المعلم بالفعل'}), 409
        # الأدمن يقدر يغيّر المعلم مباشرة
        existing.teacher_id = teacher_id
        existing.joined_at = datetime.utcnow()
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'تم نقل الطالب "{student.name}" إلى المعلم "{teacher.name}"',
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    link = TeacherStudent(teacher_id=teacher_id, student_id=student_id)
    try:
        db.session.add(link)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'تم ربط الطالب "{student.name}" بالمعلم "{teacher.name}"',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Admin Class Endpoints (الأدمن يتابع طلابه) ====================

@teachers_bp.route('/api/mobile/admin/class-code', methods=['GET'])
@login_required
@admin_required
def api_get_admin_class_code():
    """جلب كود الأدمن (يُولَّد تلقائياً عند أول طلب)"""
    from src.models.user import User
    admin = User.query.filter_by(is_admin=True).first_or_404()
    admin.ensure_class_code()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({
        'success': True,
        'class_code': admin.class_code,
        'admin_name': admin.username,
    })


@teachers_bp.route('/api/mobile/admin/students', methods=['GET'])
@login_required
@admin_required
def api_get_admin_students():
    """قائمة الطلاب المرتبطين بالأدمن مع إحصائياتهم"""
    from src.models.user import User
    from src.models.teacher_student import TeacherStudent
    from src.models.student_result import StudentResult
    from sqlalchemy import func

    admin = User.query.filter_by(is_admin=True).first_or_404()
    links = TeacherStudent.query.filter_by(admin_id=admin.id).all()

    result = []
    for link in links:
        s = link.student
        if not s:
            continue
        avg = db.session.query(func.avg(StudentResult.score_percentage))\
            .filter_by(student_id=s.id).scalar()
        count = StudentResult.query.filter_by(student_id=s.id).count()
        result.append({
            'student_id': s.id,
            'name': s.name,
            'username': s.username,
            'grade': s.grade or '',
            'school': s.school or '',
            'is_active': s.is_active,
            'last_login': s.last_login.isoformat() if s.last_login else '',
            'joined_at': link.joined_at.isoformat() if link.joined_at else '',
            'avg_score': round(avg, 1) if avg is not None else None,
            'quiz_count': count,
        })

    return jsonify({
        'success': True,
        'class_code': admin.class_code or '',
        'students': result,
    })


@teachers_bp.route('/api/mobile/admin/students/<int:student_id>/results', methods=['GET'])
@login_required
@admin_required
def api_get_admin_student_results(student_id):
    """نتائج طالب مرتبط بالأدمن"""
    from src.models.teacher_student import TeacherStudent
    from src.models.user import User

    admin = User.query.filter_by(is_admin=True).first_or_404()
    TeacherStudent.query.filter_by(
        admin_id=admin.id, student_id=student_id).first_or_404()

    return jsonify(_build_student_results_response(student_id))


@teachers_bp.route('/api/mobile/admin/students/<int:student_id>/remove', methods=['POST'])
@login_required
@admin_required
def api_remove_admin_student(student_id):
    """إزالة طالب من قائمة الأدمن"""
    from src.models.teacher_student import TeacherStudent
    from src.models.user import User

    admin = User.query.filter_by(is_admin=True).first_or_404()
    link = TeacherStudent.query.filter_by(
        admin_id=admin.id, student_id=student_id).first_or_404()
    try:
        db.session.delete(link)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم إزالة الطالب من قائمتك'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Teacher Self-Service Endpoints (توكن المعلم) ====================

@teachers_bp.route('/api/my/class-code', methods=['GET'])
@verify_teacher_token
def api_teacher_my_class_code():
    """المعلم يجلب كوده الخاص"""
    teacher = Teacher.query.get_or_404(request.teacher_id)
    teacher.ensure_class_code()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({
        'success': True,
        'class_code': teacher.class_code,
        'teacher_name': teacher.name,
    })


@teachers_bp.route('/api/my/students', methods=['GET'])
@verify_teacher_token
def api_teacher_my_students():
    """المعلم يجلب قائمة طلابه"""
    from src.models.teacher_student import TeacherStudent
    from src.models.student_result import StudentResult
    from sqlalchemy import func

    teacher = Teacher.query.get_or_404(request.teacher_id)
    links = TeacherStudent.query.filter_by(teacher_id=teacher.id).all()

    result = []
    for link in links:
        s = link.student
        if not s:
            continue
        avg = db.session.query(func.avg(StudentResult.score_percentage))\
            .filter_by(student_id=s.id).scalar()
        count = StudentResult.query.filter_by(student_id=s.id).count()
        result.append({
            'student_id': s.id,
            'name': s.name,
            'grade': s.grade or '',
            'school': s.school or '',
            'is_active': s.is_active,
            'last_login': s.last_login.isoformat() if s.last_login else '',
            'joined_at': link.joined_at.isoformat() if link.joined_at else '',
            'avg_score': round(avg, 1) if avg is not None else None,
            'quiz_count': count,
        })

    return jsonify({
        'success': True,
        'teacher_name': teacher.name,
        'class_code': teacher.class_code or '',
        'students': result,
    })


@teachers_bp.route('/api/my/students/<int:student_id>/results', methods=['GET'])
@verify_teacher_token
def api_teacher_my_student_results(student_id):
    """المعلم يجلب نتائج طالب من قائمته"""
    from src.models.teacher_student import TeacherStudent

    TeacherStudent.query.filter_by(
        teacher_id=request.teacher_id, student_id=student_id).first_or_404()

    return jsonify(_build_student_results_response(student_id))


@teachers_bp.route('/api/my/students/<int:student_id>/remove', methods=['POST'])
@verify_teacher_token
def api_teacher_remove_my_student(student_id):
    """المعلم يزيل طالباً من قائمته"""
    from src.models.teacher_student import TeacherStudent

    link = TeacherStudent.query.filter_by(
        teacher_id=request.teacher_id, student_id=student_id).first_or_404()
    try:
        db.session.delete(link)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم إزالة الطالب من قائمتك'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/my/fcm-token', methods=['POST'])
@verify_teacher_token
def api_teacher_save_fcm_token():
    """المعلم يحفظ FCM Token للإشعارات"""
    data = request.get_json() or {}
    fcm_token = data.get('fcm_token', '').strip()
    if not fcm_token:
        return jsonify({'success': False, 'error': 'fcm_token مطلوب'}), 400

    teacher = Teacher.query.get_or_404(request.teacher_id)
    try:
        teacher.update_fcm_token(fcm_token)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم حفظ FCM Token'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/my/fcm-token', methods=['DELETE'])
@verify_teacher_token
def api_teacher_delete_fcm_token():
    """المعلم يحذف FCM Token عند تسجيل الخروج"""
    teacher = Teacher.query.get_or_404(request.teacher_id)
    try:
        teacher.clear_fcm_token()
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم حذف FCM Token'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Teacher Notifications Endpoints ====================

@teachers_bp.route('/api/my/notifications', methods=['GET'])
@verify_teacher_token
def api_teacher_my_notifications():
    """المعلم يجلب إشعاراته مع عدد غير المقروء"""
    from src.models.teacher_notification import TeacherNotification

    teacher_id = request.teacher_id
    notifications = (
        TeacherNotification.query
        .filter_by(teacher_id=teacher_id)
        .order_by(TeacherNotification.created_at.desc())
        .limit(50)
        .all()
    )
    unread_count = (
        TeacherNotification.query
        .filter_by(teacher_id=teacher_id, is_read=False)
        .count()
    )
    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': unread_count,
    })


@teachers_bp.route('/api/my/notifications/read', methods=['POST'])
@verify_teacher_token
def api_teacher_mark_notifications_read():
    """تعليم كل إشعارات المعلم كمقروءة"""
    from src.models.teacher_notification import TeacherNotification

    try:
        TeacherNotification.query.filter_by(
            teacher_id=request.teacher_id, is_read=False
        ).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@teachers_bp.route('/api/my/notifications/<int:notif_id>', methods=['DELETE'])
@verify_teacher_token
def api_teacher_delete_notification(notif_id):
    """حذف إشعار واحد (يخص المعلم الحالي فقط)"""
    from src.models.teacher_notification import TeacherNotification

    notif = TeacherNotification.query.filter_by(
        id=notif_id, teacher_id=request.teacher_id
    ).first_or_404()
    try:
        db.session.delete(notif)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Admin → Teacher Notify Endpoints ====================

@teachers_bp.route('/api/admin/notify/<int:teacher_id>', methods=['POST'])
@login_required
@admin_required
def api_admin_notify_teacher(teacher_id):
    """الأدمن يرسل إشعاراً لمعلم معين"""
    from src.models.teacher_notification import TeacherNotification

    teacher = Teacher.query.get_or_404(teacher_id)
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    message = (data.get('message') or '').strip()

    if not title or not message:
        return jsonify({'success': False, 'error': 'title و message مطلوبان'}), 400

    notif = TeacherNotification.create(
        teacher_id=teacher.id,
        title=title,
        message=message,
        type='system',
    )
    if notif is None:
        return jsonify({'success': False, 'error': 'فشل في إرسال الإشعار'}), 500

    return jsonify({'success': True})


@teachers_bp.route('/api/admin/notify-all', methods=['POST'])
@login_required
@admin_required
def api_admin_notify_all_teachers():
    """الأدمن يرسل إشعاراً لجميع المعلمين"""
    from src.models.teacher_notification import TeacherNotification

    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    message = (data.get('message') or '').strip()

    if not title or not message:
        return jsonify({'success': False, 'error': 'title و message مطلوبان'}), 400

    teachers = Teacher.query.filter_by(is_active=True).all()
    count = 0
    try:
        for t in teachers:
            notif = TeacherNotification(
                teacher_id=t.id,
                title=title,
                message=message,
                type='system',
            )
            db.session.add(notif)
            count += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True, 'count': count})
