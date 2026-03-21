# src/routes/learning_routes.py
"""
Learning Content Routes Blueprint
Handles: Lesson Summaries + Concept Maps + Progress Tracking
"""

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from src.extensions import db
from src.models.learning_content import LessonSummary, ConceptMap, StudentLessonProgress
from src.models.curriculum import Lesson, Unit, Course
from datetime import datetime, timedelta
from sqlalchemy import func

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')

# ===================================
# API ENDPOINTS FOR MOBILE APP
# ===================================

@learning_bp.route('/api/lessons/<int:lesson_id>', methods=['GET'])
def api_get_lesson_content(lesson_id):
    """
    API: جلب محتوى الدرس الكامل (ملخص + خريطة مفاهيم + تقدم الطالب)
    """
    from flask import session
    from flask_login import current_user
    from src.models.student import Student
    from src.models.teacher import Teacher

    student_id = None
    is_admin_view = False

    # محاولة 0: أدمن عبر Flask-Login
    if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
        is_admin_view = True

    if not is_admin_view:
        # محاولة 1: معلم عبر X-Session-Token
        session_token = request.headers.get('X-Session-Token')
        if session_token:
            teacher = Teacher.query.filter_by(session_token=session_token, is_active=True).first()
            if teacher:
                is_admin_view = True  # المعلم يرى المحتوى بدون تتبع تقدم

        if not is_admin_view:
            # محاولة 2: Session Cookie للطالب
            if 'user_id' in session:
                student_id = session['user_id']

            # محاولة 3: Device ID من Header
            if not student_id:
                device_id = request.headers.get('X-Device-ID') or request.headers.get('Device-ID')
                if device_id:
                    student = Student.query.filter_by(device_id=device_id).first()
                    if student:
                        student_id = student.id

            if not student_id:
                return jsonify({
                    'success': False,
                    'error': 'يرجى تسجيل الدخول أولاً'
                }), 401

    try:
        # التحقق من وجود الدرس
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({
                'success': False,
                'error': 'الدرس غير موجود'
            }), 404
        
        # جلب الملخص
        summary = LessonSummary.query.filter_by(lesson_id=lesson_id).first()
        
        # جلب خريطة المفاهيم
        concept_map = ConceptMap.query.filter_by(lesson_id=lesson_id).first()
        
        # تحديث عدد المشاهدات
        if concept_map:
            concept_map.view_count += 1
            db.session.commit()
        
        # جلب تقدم الطالب (للطالب فقط، الأدمن لا يحتاج تقدم)
        progress = None
        if student_id:
            progress = StudentLessonProgress.query.filter_by(
                student_id=student_id,
                lesson_id=lesson_id
            ).first()
            if not progress:
                progress = StudentLessonProgress(
                    student_id=student_id,
                    lesson_id=lesson_id,
                    status='reading_summary'
                )
                db.session.add(progress)
                db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'lesson': {
                    'id': lesson.id,
                    'name': lesson.name,
                    'unit_id': lesson.unit_id,
                    'unit_name': lesson.unit.name if lesson.unit else None,
                    'course_name': lesson.unit.course.name if lesson.unit and lesson.unit.course else None
                },
                'summary': summary.to_dict() if summary else None,
                'concept_map': concept_map.to_dict() if concept_map else None,
                'progress': progress.to_dict() if progress else None
            }
        })
        
    except Exception as e:
        print(f"❌ خطأ في جلب محتوى الدرس: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/lessons/<int:lesson_id>/progress', methods=['POST'])
def api_update_progress(lesson_id):
    """
    API: تحديث تقدم الطالب
    Body: {
        "action": "summary_read" | "node_explored" | "complete",
        "time_spent": 30,
        "node_id": "chemistry",
        "total_nodes": 5
    }
    """
    from flask import session
    from src.models.student import Student
    from src.models.teacher import Teacher
    from flask_login import current_user

    student_id = None

    # محاولة 0: أدمن عبر Flask-Login
    if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
        return jsonify({'success': True, 'progress': None, 'message': 'لا يتتبع تقدم الأدمن'})

    # محاولة 1: معلم عبر X-Session-Token
    session_token = request.headers.get('X-Session-Token')
    if session_token:
        teacher = Teacher.query.filter_by(session_token=session_token, is_active=True).first()
        if teacher:
            return jsonify({'success': True, 'progress': None, 'message': 'لا يتتبع تقدم المعلم'})

    # محاولة 1: Session Cookie
    if 'user_id' in session:
        student_id = session['user_id']

    # محاولة 2: Device ID من Header
    if not student_id:
        device_id = request.headers.get('X-Device-ID') or request.headers.get('Device-ID')
        if device_id:
            student = Student.query.filter_by(device_id=device_id).first()
            if student:
                student_id = student.id

    if not student_id:
        return jsonify({
            'success': False,
            'error': 'يرجى تسجيل الدخول أولاً'
        }), 401
    
    try:
        data = request.json
        action = data.get('action')
        
        # جلب التقدم
        progress = StudentLessonProgress.query.filter_by(
            student_id=student_id,
            lesson_id=lesson_id
        ).first()
        
        if not progress:
            progress = StudentLessonProgress(
                student_id=student_id,
                lesson_id=lesson_id
            )
            db.session.add(progress)
        
        # تحديث الوقت
        if 'time_spent' in data:
            progress.total_time_spent += data['time_spent']
        
        # تحديث حسب النوع
        if action == 'summary_read':
            progress.summary_read = True
            progress.summary_reading_time += data.get('reading_time', 0)
            progress.status = 'exploring_map'
            
        elif action == 'node_explored':
            node_id = data.get('node_id')
            if node_id and node_id not in progress.explored_nodes:
                progress.explored_nodes.append(node_id)
            
            progress.concept_map_time += data.get('time', 0)
            
            # تحقق إذا استكشف كل العقد
            total_nodes = data.get('total_nodes', 0)
            if len(progress.explored_nodes) >= total_nodes:
                progress.concept_map_explored = True
                progress.status = 'completed'
                if not progress.completed_at:
                    progress.completed_at = datetime.utcnow()
        
        # تحديث نسبة الإكمال
        progress.update_completion()
        progress.last_activity_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'progress': progress.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في تحديث التقدم: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/lessons', methods=['GET'])
def api_get_all_lessons():
    """
    API: جلب جميع الدروس مع تقدم الطالب (منظمة حسب المناهج والوحدات)
    """
    from flask import session
    from src.models.student import Student
    from src.models.teacher import Teacher
    from flask_login import current_user

    student_id = None
    is_admin_view = False

    # محاولة 0: أدمن عبر Flask-Login
    if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
        is_admin_view = True

    if not is_admin_view:
        # محاولة 1: معلم عبر X-Session-Token
        session_token = request.headers.get('X-Session-Token')
        if session_token:
            teacher = Teacher.query.filter_by(session_token=session_token, is_active=True).first()
            if teacher:
                is_admin_view = True  # المعلم يرى كل الدروس بدون تتبع تقدم

        if not is_admin_view:
            # محاولة 2: Session Cookie للطالب
            if 'user_id' in session:
                student_id = session['user_id']

            # محاولة 3: Device ID من Header
            if not student_id:
                device_id = request.headers.get('X-Device-ID') or request.headers.get('Device-ID')
                if device_id:
                    student = Student.query.filter_by(device_id=device_id).first()
                    if student:
                        student_id = student.id

            if not student_id:
                return jsonify({
                    'success': False,
                    'error': 'يرجى تسجيل الدخول أولاً'
                }), 401
    
    try:
        # جلب الدروس فقط من المناهج المفعلة للطلاب
        lessons = Lesson.query.join(Unit).join(Course).filter(
            Course.show_in_bot == True,   # ✅ فقط المناهج المفعلة
            Unit.show_in_bot == True,     # ✅ فقط الوحدات المفعلة
            Lesson.show_in_bot == True    # ✅ فقط الدروس المفعلة
        ).order_by(
            Course.order_num,  # ✅ الترتيب حسب order_num
            Unit.order_num, 
            Lesson.order_num
        ).all()
        
        # تنظيم الدروس حسب المناهج والوحدات
        organized_lessons = {}
        total_with_content = 0
        
        for lesson in lessons:
            # تحقق من وجود محتوى
            has_summary = LessonSummary.query.filter_by(lesson_id=lesson.id).first() is not None
            has_concept_map = ConceptMap.query.filter_by(lesson_id=lesson.id).first() is not None
            has_content = has_summary or has_concept_map
            
            # ✅ تعطيل الفلترة مؤقتاً - يعرض كل الدروس
            # if not has_content:
            #     continue
            
            total_with_content += 1
            
            # جلب التقدم
            progress = StudentLessonProgress.query.filter_by(
                student_id=student_id,
                lesson_id=lesson.id
            ).first()
            
            # اسم المنهج
            course = lesson.unit.course if lesson.unit and lesson.unit.course else None
            course_name = course.name if course else 'غير محدد'
            course_order = course.order_num if course else 999
            
            # اسم الوحدة
            unit = lesson.unit if lesson.unit else None
            unit_name = unit.name if unit else 'غير محدد'
            unit_order = unit.order_num if unit else 999
            
            # إنشاء هيكل المنهج إذا لم يكن موجوداً
            if course_name not in organized_lessons:
                organized_lessons[course_name] = {}
            
            # إنشاء هيكل الوحدة إذا لم يكن موجوداً
            if unit_name not in organized_lessons[course_name]:
                organized_lessons[course_name][unit_name] = []
            
            # إضافة الدرس
            organized_lessons[course_name][unit_name].append({
                'id': lesson.id,
                'name': lesson.name,
                'order_num': lesson.order_num,  # ✅ أضف order_num
                'unit_id': lesson.unit_id,
                'unit_name': unit_name,
                'unit_order_num': unit_order,  # ✅ أضف unit order
                'course_name': course_name,
                'course_order_num': course_order,  # ✅ أضف course order
                'has_summary': has_summary,
                'has_concept_map': has_concept_map,
                'completion_percentage': progress.completion_percentage if progress else 0,
            })
        
        return jsonify({
            'success': True,
            'lessons': organized_lessons,
            'total': total_with_content
        })
        
    except Exception as e:
        print(f"❌ خطأ في جلب الدروس: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/students/<int:student_id>/stats', methods=['GET'])
@login_required
def api_get_student_stats(student_id):
    """
    API: إحصائيات الطالب في نظام التعلم
    """
    try:
        # التحقق من الصلاحية
        if current_user.id != student_id and not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'غير مصرح'
            }), 403
        
        # جميع التقدمات
        all_progress = StudentLessonProgress.query.filter_by(
            student_id=student_id
        ).all()
        
        completed = sum(1 for p in all_progress if p.status == 'completed')
        in_progress = sum(1 for p in all_progress if p.status in ['reading_summary', 'exploring_map'])
        total_time = sum(p.total_time_spent for p in all_progress)
        
        # متوسط نسبة الإكمال
        avg_completion = sum(p.completion_percentage for p in all_progress) / len(all_progress) if all_progress else 0
        
        return jsonify({
            'success': True,
            'data': {
                'lessons_started': len(all_progress),
                'lessons_completed': completed,
                'lessons_in_progress': in_progress,
                'total_time_spent_seconds': total_time,
                'total_time_spent_minutes': round(total_time / 60, 1),
                'avg_completion_rate': round(avg_completion, 2)
            }
        })
        
    except Exception as e:
        print(f"❌ خطأ في جلب إحصائيات الطالب: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===================================
# ADMIN PANEL ROUTES
# ===================================

@learning_bp.route('/admin', methods=['GET'])
@login_required
def admin_index():
    """صفحة الإدارة الرئيسية"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    # إحصائيات عامة
    total_summaries = LessonSummary.query.count()
    total_concept_maps = ConceptMap.query.count()
    total_lessons = Lesson.query.count()
    lessons_with_content = db.session.query(Lesson.id).join(
        LessonSummary, Lesson.id == LessonSummary.lesson_id, isouter=True
    ).join(
        ConceptMap, Lesson.id == ConceptMap.lesson_id, isouter=True
    ).filter(
        db.or_(LessonSummary.id.isnot(None), ConceptMap.id.isnot(None))
    ).distinct().count()
    
    # أحدث الإضافات
    recent_summaries = LessonSummary.query.order_by(
        LessonSummary.created_at.desc()
    ).limit(5).all()
    
    recent_maps = ConceptMap.query.order_by(
        ConceptMap.created_at.desc()
    ).limit(5).all()
    
    return render_template('learning/admin_index.html',
                         total_summaries=total_summaries,
                         total_concept_maps=total_concept_maps,
                         total_lessons=total_lessons,
                         lessons_with_content=lessons_with_content,
                         recent_summaries=recent_summaries,
                         recent_maps=recent_maps)


@learning_bp.route('/admin/summaries', methods=['GET'])
@login_required
def admin_summaries():
    """إدارة الملخصات"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    summaries = db.session.query(
        LessonSummary, Lesson, Unit, Course
    ).join(
        Lesson, LessonSummary.lesson_id == Lesson.id
    ).join(
        Unit, Lesson.unit_id == Unit.id
    ).join(
        Course, Unit.course_id == Course.id
    ).order_by(
        Course.order_num, Unit.order_num, Lesson.order_num
    ).all()
    
    return render_template('learning/admin_summaries.html',
                         summaries=summaries)


@learning_bp.route('/admin/concept-maps', methods=['GET'])
@login_required
def admin_concept_maps():
    """إدارة خرائط المفاهيم"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    concept_maps = db.session.query(
        ConceptMap, Lesson, Unit, Course
    ).join(
        Lesson, ConceptMap.lesson_id == Lesson.id
    ).join(
        Unit, Lesson.unit_id == Unit.id
    ).join(
        Course, Unit.course_id == Course.id
    ).order_by(
        Course.order_num, Unit.order_num, Lesson.order_num
    ).all()
    
    return render_template('learning/admin_concept_maps.html',
                         concept_maps=concept_maps)


@learning_bp.route('/admin/concept-map/<int:concept_map_id>', methods=['GET'])
@login_required
def admin_view_concept_map(concept_map_id):
    """عرض خريطة مفاهيم"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    # جلب الخريطة
    concept_map = ConceptMap.query.get_or_404(concept_map_id)
    
    # جلب معلومات الدرس
    lesson = Lesson.query.get(concept_map.lesson_id)
    unit = Unit.query.get(lesson.unit_id) if lesson else None
    course = Course.query.get(unit.course_id) if unit else None
    
    return render_template('learning/admin_view_concept_map.html',
                         concept_map=concept_map,
                         lesson=lesson,
                         unit=unit,
                         course=course)


@learning_bp.route('/admin/concept-map/<int:concept_map_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_concept_map(concept_map_id):
    """تعديل خريطة مفاهيم"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    concept_map = ConceptMap.query.get_or_404(concept_map_id)
    
    if request.method == 'POST':
        try:
            layout_type = request.form.get('layout_type', 'radial')
            theme = request.form.get('theme', 'modern')
            animation_type = request.form.get('animation_type', 'fade-in')
            map_data = request.form.get('map_data')
            
            # تحويل JSON
            import json
            map_data_dict = json.loads(map_data)
            
            # تحديث البيانات
            concept_map.layout_type = layout_type
            concept_map.theme = theme
            concept_map.animation_type = animation_type
            concept_map.map_data = map_data_dict
            
            db.session.commit()
            
            flash('تم تحديث خريطة المفاهيم بنجاح!', 'success')
            return redirect(url_for('learning.admin_concept_maps'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في التحديث: {str(e)}', 'error')
            import traceback
            traceback.print_exc()
    
    # GET: عرض نموذج التعديل
    lesson = Lesson.query.get(concept_map.lesson_id)
    unit = Unit.query.get(lesson.unit_id) if lesson else None
    course = Course.query.get(unit.course_id) if unit else None
    
    return render_template('learning/admin_edit_concept_map.html',
                         concept_map=concept_map,
                         lesson=lesson,
                         unit=unit,
                         course=course)


@learning_bp.route('/admin/summary/add', methods=['GET', 'POST'])
@login_required
def admin_add_summary():
    """إضافة ملخص جديد"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            lesson_id = request.form.get('lesson_id', type=int)
            introduction = request.form.get('introduction')
            key_points = request.form.get('key_points')  # JSON string
            examples = request.form.get('examples', '[]')  # JSON string
            vocabulary = request.form.get('vocabulary', '{}')  # JSON string
            
            # تحويل JSON strings
            import json
            key_points_list = json.loads(key_points) if key_points else []
            examples_list = json.loads(examples) if examples else []
            vocabulary_dict = json.loads(vocabulary) if vocabulary else {}
            
            summary = LessonSummary(
                lesson_id=lesson_id,
                introduction=introduction,
                key_points=key_points_list,
                examples=examples_list,
                vocabulary=vocabulary_dict
            )
            
            db.session.add(summary)
            db.session.commit()
            
            flash('تم إضافة الملخص بنجاح!', 'success')
            return redirect(url_for('learning.admin_summaries'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في إضافة الملخص: {str(e)}', 'error')
            print(f"❌ خطأ: {e}")
            import traceback
            traceback.print_exc()
    
    # GET: عرض النموذج
    # جلب الدروس التي ليس لها ملخصات
    lessons = db.session.query(Lesson).outerjoin(
        LessonSummary
    ).filter(
        LessonSummary.id.is_(None)
    ).order_by(Lesson.unit_id, Lesson.order_num).all()
    
    return render_template('learning/admin_add_summary.html',
                         lessons=lessons)


@learning_bp.route('/admin/concept-map/add', methods=['GET', 'POST'])
@login_required
def admin_add_concept_map():
    """إضافة خريطة مفاهيم جديدة"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            lesson_id = request.form.get('lesson_id', type=int)
            layout_type = request.form.get('layout_type', 'radial')
            theme = request.form.get('theme', 'modern')
            animation_type = request.form.get('animation_type', 'fade-in')
            map_data = request.form.get('map_data')  # JSON string
            
            # تحويل JSON
            import json
            map_data_dict = json.loads(map_data)
            
            concept_map = ConceptMap(
                lesson_id=lesson_id,
                layout_type=layout_type,
                theme=theme,
                animation_type=animation_type,
                map_data=map_data_dict
            )
            
            db.session.add(concept_map)
            db.session.commit()
            
            flash('تم إضافة خريطة المفاهيم بنجاح!', 'success')
            return redirect(url_for('learning.admin_concept_maps'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في إضافة خريطة المفاهيم: {str(e)}', 'error')
            print(f"❌ خطأ: {e}")
            import traceback
            traceback.print_exc()
    
    # GET: عرض النموذج
    # جلب الدروس التي ليس لها خرائط
    lessons = db.session.query(Lesson).outerjoin(
        ConceptMap
    ).filter(
        ConceptMap.id.is_(None)
    ).order_by(Lesson.unit_id, Lesson.order_num).all()
    
    return render_template('learning/admin_add_concept_map.html',
                         lessons=lessons)


@learning_bp.route('/admin/reports', methods=['GET'])
@login_required
def admin_reports():
    """تقارير وإحصائيات النظام"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('dashboard'))
    
    # إحصائيات الاستخدام
    total_students = db.session.query(func.count(func.distinct(
        StudentLessonProgress.student_id
    ))).scalar()
    
    active_students = db.session.query(func.count(func.distinct(
        StudentLessonProgress.student_id
    ))).filter(
        StudentLessonProgress.last_activity_at >= datetime.utcnow() - timedelta(days=7)
    ).scalar()
    
    # أكثر الدروس مشاهدة
    top_lessons = db.session.query(
        Lesson.name,
        ConceptMap.view_count
    ).join(
        ConceptMap, Lesson.id == ConceptMap.lesson_id
    ).order_by(
        ConceptMap.view_count.desc()
    ).limit(10).all()
    
    # متوسط نسبة الإكمال
    avg_completion = db.session.query(
        func.avg(StudentLessonProgress.completion_percentage)
    ).scalar() or 0
    
    return render_template('learning/admin_reports.html',
                         total_students=total_students,
                         active_students=active_students,
                         top_lessons=top_lessons,
                         avg_completion=round(avg_completion, 2))


# =====================================================
# Delete Endpoints - حذف المحتوى
# =====================================================

@learning_bp.route('/admin/concept-maps/<int:concept_map_id>/delete', methods=['POST'])
@login_required
def admin_delete_concept_map(concept_map_id):
    """حذف خريطة مفاهيم"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        return jsonify({
            'success': False,
            'error': 'ليس لديك صلاحية الوصول'
        }), 403
    
    try:
        # البحث عن الخريطة
        concept_map = ConceptMap.query.get_or_404(concept_map_id)
        
        # حذف الخريطة
        db.session.delete(concept_map)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حذف خريطة المفاهيم بنجاح'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/admin/summaries/<int:summary_id>/delete', methods=['POST'])
@login_required
def admin_delete_summary(summary_id):
    """حذف ملخص"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        return jsonify({
            'success': False,
            'error': 'ليس لديك صلاحية الوصول'
        }), 403
    
    try:
        # البحث عن الملخص
        summary = LessonSummary.query.get_or_404(summary_id)
        
        # حذف الملخص
        db.session.delete(summary)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حذف الملخص بنجاح'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# AI-Powered Concept Map Generation - جديد
# =====================================================

@learning_bp.route('/admin/concept-map/generate-ai', methods=['POST'])
@login_required
def admin_generate_concept_map_ai():
    """توليد خريطة مفاهيم تلقائياً باستخدام الذكاء الاصطناعي"""
    if not current_user.is_admin:
        return jsonify({
            'success': False,
            'error': 'ليس لديك صلاحية الوصول'
        }), 403
    
    try:
        lesson_id = request.json.get('lesson_id')
        lesson_content = request.json.get('lesson_content', '')
        
        if not lesson_id:
            return jsonify({
                'success': False,
                'error': 'lesson_id مطلوب'
            }), 400
        
        # جلب بيانات الدرس
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({
                'success': False,
                'error': 'الدرس غير موجود'
            }), 404
        
        # جلب بيانات الوحدة والمنهج
        unit = Unit.query.get(lesson.unit_id) if lesson.unit_id else None
        course = Course.query.get(unit.course_id) if unit and unit.course_id else None

        # محاولة استخراج محتوى الكتاب المدرسي كمرجع للذكاء الاصطناعي
        if not lesson_content:
            from src.models.textbook import LessonPages
            lesson_page_map = LessonPages.query.filter_by(lesson_id=lesson_id).first()
            if lesson_page_map and lesson_page_map.textbook and lesson_page_map.textbook.pdf_url:
                try:
                    import fitz
                    import requests as _req
                    import re as _re
                    pdf_url = lesson_page_map.textbook.pdf_url
                    start_p = lesson_page_map.start_page
                    end_p = lesson_page_map.end_page

                    if 'drive.google.com' in pdf_url:
                        if '/file/d/' in pdf_url:
                            file_id = _re.search(r'/file/d/([a-zA-Z0-9_-]+)', pdf_url).group(1)
                        else:
                            file_id = _re.search(r'[?&]id=([a-zA-Z0-9_-]+)', pdf_url).group(1)
                        session = _req.Session()
                        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                        resp = session.get(download_url, timeout=120)
                        if b'%PDF' not in resp.content[:10]:
                            confirm = _re.search(r'confirm=([0-9A-Za-z_]+)', resp.text)
                            uuid = _re.search(r'uuid=([0-9A-Za-z_-]+)', resp.text)
                            if confirm and uuid:
                                download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={confirm.group(1)}&uuid={uuid.group(1)}"
                            else:
                                download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
                            resp = session.get(download_url, timeout=120)
                        resp.raise_for_status()
                        if b'%PDF' not in resp.content[:10]:
                            raise Exception("فشل تحميل PDF من Google Drive")
                    else:
                        resp = _req.get(pdf_url, timeout=60)
                        resp.raise_for_status()

                    doc = fitz.open(stream=resp.content, filetype="pdf")

                    pages_text = []
                    actual_end = min(end_p, len(doc))
                    for page_num in range(start_p - 1, actual_end):
                        page_text = doc[page_num].get_text("text")
                        if page_text.strip():
                            pages_text.append(page_text.strip())

                    if pages_text:
                        lesson_content = "\n\n".join(pages_text)
                        print(f"✅ تم استخراج {len(pages_text)} صفحة من الكتاب (صفحات {start_p}-{end_p})")
                except Exception as pdf_err:
                    print(f"⚠️ فشل استخراج نص الكتاب: {pdf_err}")

        # استيراد AI assistant
        from src.services.ai_assistant import ai_assistant

        # توليد خريطة المفاهيم
        concept_map_data = ai_assistant.generate_concept_map(
            lesson_name=lesson.name,
            lesson_content=lesson_content,
            course_name=course.name if course else None,
            unit_name=unit.name if unit else None
        )
        
        if not concept_map_data:
            return jsonify({
                'success': False,
                'error': 'فشل توليد خريطة المفاهيم'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم توليد خريطة المفاهيم بنجاح',
            'data': concept_map_data
        })
        
    except Exception as e:
        print(f"❌ خطأ في توليد خريطة المفاهيم: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/admin/concept-map/save-ai-generated', methods=['POST'])
@login_required
def admin_save_ai_generated_concept_map():
    """حفظ خريطة مفاهيم تم توليدها بالذكاء الاصطناعي"""
    if not current_user.is_admin:
        return jsonify({
            'success': False,
            'error': 'ليس لديك صلاحية الوصول'
        }), 403
    
    try:
        lesson_id = request.json.get('lesson_id')
        map_data = request.json.get('map_data')
        layout_type = request.json.get('layout_type', 'radial')
        theme = request.json.get('theme', 'modern')
        animation_type = request.json.get('animation_type', 'fade-in')
        
        if not lesson_id or not map_data:
            return jsonify({
                'success': False,
                'error': 'lesson_id و map_data مطلوبان'
            }), 400
        
        # التحقق من وجود خريطة سابقة
        existing_map = ConceptMap.query.filter_by(lesson_id=lesson_id).first()
        
        if existing_map:
            # تحديث الخريطة الموجودة
            existing_map.layout_type = layout_type
            existing_map.theme = theme
            existing_map.animation_type = animation_type
            existing_map.map_data = map_data
            existing_map.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'تم تحديث خريطة المفاهيم بنجاح',
                'data': existing_map.to_dict()
            })
        else:
            # إنشاء خريطة جديدة
            concept_map = ConceptMap(
                lesson_id=lesson_id,
                layout_type=layout_type,
                theme=theme,
                animation_type=animation_type,
                map_data=map_data
            )
            
            db.session.add(concept_map)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'تم حفظ خريطة المفاهيم بنجاح',
                'data': concept_map.to_dict()
            })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في حفظ خريطة المفاهيم: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/admin/concept-map/suggest-branches', methods=['POST'])
@login_required
def admin_suggest_branches():
    """اقتراح فروع جديدة بناءً على العقدة المركزية"""
    if not current_user.is_admin:
        return jsonify({
            'success': False,
            'error': 'ليس لديك صلاحية الوصول'
        }), 403
    
    try:
        center_text = request.json.get('center_text')
        existing_branches = request.json.get('existing_branches', [])
        
        if not center_text:
            return jsonify({
                'success': False,
                'error': 'center_text مطلوب'
            }), 400
        
        # استيراد AI assistant
        from src.services.ai_assistant import ai_assistant
        
        # التأكد من تهيئة AI
        if not ai_assistant._ensure_configured():
            return jsonify({
                'success': False,
                'error': 'نظام الذكاء الاصطناعي غير مفعل'
            }), 503
        
        # بناء prompt لاقتراح الفروع
        existing_text = ', '.join([b.get('text', '') for b in existing_branches]) if existing_branches else 'لا يوجد'
        
        prompt = f"""
أنت خبير في تصميم خرائط المفاهيم التعليمية.

المفهوم المركزي: {center_text}
الفروع الموجودة حالياً: {existing_text}

المطلوب: اقترح 3 فروع جديدة مختلفة ومكملة للفروع الموجودة.

الرد يجب أن يكون بصيغة JSON فقط:
{{
  "suggestions": [
    {{
      "text": "فرع مقترح 1",
      "color": "#4A90E2",
      "description": "وصف مختصر"
    }},
    {{
      "text": "فرع مقترح 2",
      "color": "#50C878",
      "description": "وصف مختصر"
    }},
    {{
      "text": "فرع مقترح 3",
      "color": "#FF6B6B",
      "description": "وصف مختصر"
    }}
  ]
}}

تعليمات:
- كل فرع يجب أن يكون مختصراً (4 كلمات كحد أقصى)
- استخدم ألوان متنوعة
- لا تكرر الفروع الموجودة
- الرد JSON فقط بدون نص إضافي
- إذا كان الفرع يتعلق بمعادلة كيميائية أو قانون، أضفها في الوصف باستخدام Unicode (مثل: H₂O، CO₂، →، ⇌، Δ)
"""
        
        response = ai_assistant.model.generate_content(prompt)
        ai_text = response.text
        
        # استخراج JSON
        suggestions_data = ai_assistant._extract_json_from_response(ai_text)
        
        if not suggestions_data or 'suggestions' not in suggestions_data:
            return jsonify({
                'success': False,
                'error': 'فشل استخراج الاقتراحات'
            }), 500
        
        return jsonify({
            'success': True,
            'data': suggestions_data['suggestions']
        })
        
    except Exception as e:
        print(f"❌ خطأ في اقتراح الفروع: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/admin/concept-map/export/<int:concept_map_id>/<format>', methods=['GET'])
@login_required
def admin_export_concept_map(concept_map_id, format):
    """تصدير خريطة المفاهيم بصيغ متعددة (JSON, PNG, SVG)"""
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول', 'error')
        return redirect(url_for('learning.admin_concept_maps'))
    
    try:
        concept_map = ConceptMap.query.get_or_404(concept_map_id)
        lesson = Lesson.query.get(concept_map.lesson_id)
        
        if format == 'json':
            # تصدير JSON
            import io
            output = io.BytesIO()
            json_data = json.dumps(concept_map.map_data, ensure_ascii=False, indent=2)
            output.write(json_data.encode('utf-8'))
            output.seek(0)
            
            filename = f"concept_map_{lesson.name}_{concept_map_id}.json"
            
            return send_file(
                output,
                mimetype='application/json',
                as_attachment=True,
                download_name=filename
            )
        
        elif format in ['png', 'svg']:
            # للتصدير كصورة، نحتاج إلى استخدام مكتبة خارجية
            # هذا يتطلب تطوير إضافي
            flash(f'تصدير {format.upper()} قيد التطوير', 'info')
            return redirect(url_for('learning.admin_view_concept_map', concept_map_id=concept_map_id))
        
        else:
            flash('صيغة غير مدعومة', 'error')
            return redirect(url_for('learning.admin_view_concept_map', concept_map_id=concept_map_id))
        
    except Exception as e:
        flash(f'خطأ في التصدير: {str(e)}', 'error')
        return redirect(url_for('learning.admin_concept_maps'))
