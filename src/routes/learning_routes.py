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
from datetime import datetime
from sqlalchemy import func

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')

# ===================================
# API ENDPOINTS FOR MOBILE APP
# ===================================

@learning_bp.route('/api/lessons/<int:lesson_id>', methods=['GET'])
@login_required
def api_get_lesson_content(lesson_id):
    """
    API: جلب محتوى الدرس الكامل (ملخص + خريطة مفاهيم + تقدم الطالب)
    """
    try:
        # التحقق من وجود الدرس
        lesson = Lesson.query.get_or_404(lesson_id)
        
        # جلب الملخص
        summary = LessonSummary.query.filter_by(lesson_id=lesson_id).first()
        
        # جلب خريطة المفاهيم
        concept_map = ConceptMap.query.filter_by(lesson_id=lesson_id).first()
        
        # تحديث عدد المشاهدات
        if concept_map:
            concept_map.view_count += 1
            db.session.commit()
        
        # جلب أو إنشاء تقدم الطالب
        progress = StudentLessonProgress.query.filter_by(
            student_id=current_user.id,
            lesson_id=lesson_id
        ).first()
        
        if not progress:
            progress = StudentLessonProgress(
                student_id=current_user.id,
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
                'progress': progress.to_dict()
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
@login_required
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
    try:
        data = request.json
        action = data.get('action')
        
        # جلب التقدم
        progress = StudentLessonProgress.query.filter_by(
            student_id=current_user.id,
            lesson_id=lesson_id
        ).first()
        
        if not progress:
            progress = StudentLessonProgress(
                student_id=current_user.id,
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
@login_required
def api_get_all_lessons():
    """
    API: جلب جميع الدروس مع تقدم الطالب
    Query params: ?unit_id=1 or ?course_id=1
    """
    try:
        unit_id = request.args.get('unit_id', type=int)
        course_id = request.args.get('course_id', type=int)
        
        query = Lesson.query
        
        if unit_id:
            query = query.filter_by(unit_id=unit_id)
        elif course_id:
            query = query.join(Unit).filter(Unit.course_id == course_id)
        
        lessons = query.order_by(Lesson.order_num).all()
        
        result = []
        for lesson in lessons:
            # تحقق من وجود محتوى
            has_summary = LessonSummary.query.filter_by(lesson_id=lesson.id).first() is not None
            has_concept_map = ConceptMap.query.filter_by(lesson_id=lesson.id).first() is not None
            
            # جلب التقدم
            progress = StudentLessonProgress.query.filter_by(
                student_id=current_user.id,
                lesson_id=lesson.id
            ).first()
            
            result.append({
                'id': lesson.id,
                'name': lesson.name,
                'unit_id': lesson.unit_id,
                'unit_name': lesson.unit.name if lesson.unit else None,
                'has_content': has_summary or has_concept_map,
                'has_summary': has_summary,
                'has_concept_map': has_concept_map,
                'progress': progress.to_dict() if progress else {
                    'status': 'not_started',
                    'completion_percentage': 0
                }
            })
        
        return jsonify({
            'success': True,
            'data': result
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
