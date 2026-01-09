# ==================== Backend - Flask Reports Routes (Integrated Version) ====================
# routes/reports.py
"""
نظام التقارير المتكامل - يستفيد من البنية الموجودة
✅ متوافق مع students.py
✅ يستخدم نظام التوقيت الذكي
✅ APIs للتطبيق وصفحات للويب
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
from src.extensions import db
from src.models.student import Student
from src.models.result import Result
from src.models.quiz import Quiz
from src.models.course import Course
from datetime import datetime, timedelta
import pytz
import io

reports_bp = Blueprint('reports', __name__)


# ==================== نظام التوقيت (مطابق لـ students.py) ====================
def get_utc_time():
    """الحصول على الوقت الحالي بتوقيت UTC"""
    return datetime.now(pytz.utc)


def convert_utc_to_timezone(utc_dt, timezone_str='Asia/Riyadh'):
    """تحويل وقت UTC إلى أي منطقة زمنية"""
    if utc_dt is None:
        return None
    
    try:
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        
        target_tz = pytz.timezone(timezone_str)
        return utc_dt.astimezone(target_tz)
    except Exception as e:
        print(f"⚠️ خطأ في تحويل التوقيت: {e}")
        return utc_dt


def get_user_timezone_from_request():
    """الحصول على المنطقة الزمنية من الـ request"""
    timezone = request.headers.get('X-Timezone', 'Asia/Riyadh')
    
    try:
        pytz.timezone(timezone)
        return timezone
    except:
        return 'Asia/Riyadh'


# ==================== Middleware ====================
def admin_required(f):
    """التحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Unauthorized'}), 403
            flash('ليس لديك صلاحية الوصول لهذه الصفحة', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 1. تقرير الطلاب الشامل (API) ====================
@reports_bp.route('/api/students-performance', methods=['GET'])
@login_required
@admin_required
def api_students_performance_report():
    """
    API: تقرير شامل عن أداء جميع الطلاب
    يستخدم من التطبيق (Flutter)
    """
    try:
        # الحصول على timezone المستخدم
        user_timezone = get_user_timezone_from_request()
        
        # جلب جميع الطلاب
        students = Student.query.all()
        report = []
        
        for student in students:
            # جلب نتائج الطالب
            results = Result.query.filter_by(student_id=student.id).order_by(Result.created_at.desc()).all()
            
            if not results:
                # طالب بدون اختبارات
                created_at_local = convert_utc_to_timezone(student.created_at, user_timezone) if student.created_at else None
                
                report.append({
                    'student_id': student.id,
                    'student_name': student.name,
                    'email': student.email or '',
                    'phone': student.phone or '',
                    'total_quizzes': 0,
                    'avg_score': 0,
                    'total_time_spent': 0,
                    'last_activity': None,
                    'best_score': 0,
                    'worst_score': 0,
                    'improvement_trend': 0,
                    'active_status': 'غير نشط',
                    'performance_level': 'لا توجد بيانات',
                    'created_at': created_at_local.isoformat() if created_at_local else None,
                    'strengths': [],
                    'weaknesses': [],
                    'recent_scores': [],
                })
                continue
            
            # حساب الإحصائيات
            total_quizzes = len(results)
            scores = [r.score_percentage for r in results]
            avg_score = sum(scores) / len(scores) if scores else 0
            total_time = sum(r.time_spent or 0 for r in results)
            best_score = max(scores) if scores else 0
            worst_score = min(scores) if scores else 0
            
            # تحويل آخر نشاط للتوقيت المحلي
            last_activity_utc = results[0].created_at
            last_activity_local = convert_utc_to_timezone(last_activity_utc, user_timezone)
            
            # حساب اتجاه التحسن
            improvement = calculate_improvement_trend(results)
            
            # تحديد حالة النشاط
            active_status = get_activity_status(last_activity_utc)
            
            # تحديد مستوى الأداء
            performance_level = get_performance_level(avg_score)
            
            # تحليل نقاط القوة والضعف
            strengths, weaknesses = analyze_topics(student.id)
            
            # تحويل تاريخ التسجيل
            created_at_local = convert_utc_to_timezone(student.created_at, user_timezone) if student.created_at else None
            
            report.append({
                'student_id': student.id,
                'student_name': student.name,
                'email': student.email or '',
                'phone': student.phone or '',
                'total_quizzes': total_quizzes,
                'avg_score': round(avg_score, 2),
                'total_time_spent': total_time,
                'avg_time_per_quiz': round(total_time / total_quizzes, 1) if total_quizzes > 0 else 0,
                'last_activity': last_activity_local.isoformat() if last_activity_local else None,
                'best_score': round(best_score, 2),
                'worst_score': round(worst_score, 2),
                'improvement_trend': round(improvement, 2),
                'active_status': active_status,
                'performance_level': performance_level,
                'strengths': strengths[:3],
                'weaknesses': weaknesses[:3],
                'recent_scores': scores[:10],
                'created_at': created_at_local.isoformat() if created_at_local else None,
            })
        
        # حساب الإحصائيات العامة
        total_students = len(students)
        active_students = sum(1 for s in report if s['active_status'] in ['نشط جداً', 'نشط'])
        avg_all_score = sum(s['avg_score'] for s in report) / len(report) if report else 0
        total_quizzes_all = sum(s['total_quizzes'] for s in report)
        
        # توزيع مستويات الأداء
        performance_distribution = {
            'excellent': sum(1 for s in report if s['avg_score'] >= 90),
            'very_good': sum(1 for s in report if 80 <= s['avg_score'] < 90),
            'good': sum(1 for s in report if 70 <= s['avg_score'] < 80),
            'acceptable': sum(1 for s in report if 60 <= s['avg_score'] < 70),
            'weak': sum(1 for s in report if 0 < s['avg_score'] < 60),
            'no_data': sum(1 for s in report if s['avg_score'] == 0),
        }
        
        return jsonify({
            'success': True,
            'report': report,
            'summary': {
                'total_students': total_students,
                'active_students': active_students,
                'inactive_students': total_students - active_students,
                'avg_all_score': round(avg_all_score, 2),
                'total_quizzes_all': total_quizzes_all,
                'performance_distribution': performance_distribution,
            },
            'timezone': user_timezone,
        })
        
    except Exception as e:
        print(f'❌ Error in students performance report: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 2. تقرير الطلاب المتميزين (API) ====================
@reports_bp.route('/api/top-performers', methods=['GET'])
@login_required
@admin_required
def api_top_performers():
    """API: تقرير الطلاب المتميزين"""
    try:
        limit = request.args.get('limit', 10, type=int)
        user_timezone = get_user_timezone_from_request()
        
        students = Student.query.filter_by(is_active=True).all()
        students_with_avg = []
        
        for student in students:
            results = Result.query.filter_by(student_id=student.id).all()
            if results:
                avg_score = sum(r.score_percentage for r in results) / len(results)
                students_with_avg.append({
                    'student': student,
                    'avg_score': avg_score,
                    'total_quizzes': len(results),
                    'last_activity': max(r.created_at for r in results)
                })
        
        # ترتيب حسب المعدل
        top_students = sorted(students_with_avg, key=lambda x: x['avg_score'], reverse=True)[:limit]
        
        result = []
        for idx, item in enumerate(top_students, 1):
            student = item['student']
            last_activity_local = convert_utc_to_timezone(item['last_activity'], user_timezone)
            
            result.append({
                'rank': idx,
                'student_id': student.id,
                'student_name': student.name,
                'email': student.email or '',
                'avg_score': round(item['avg_score'], 2),
                'total_quizzes': item['total_quizzes'],
                'badge': get_badge(idx),
                'last_activity': last_activity_local.isoformat() if last_activity_local else None,
            })
        
        return jsonify({
            'success': True,
            'top_performers': result,
            'total': len(result)
        })
        
    except Exception as e:
        print(f'❌ Error in top performers: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 3. تقرير الطلاب المحتاجين للمساعدة (API) ====================
@reports_bp.route('/api/need-help', methods=['GET'])
@login_required
@admin_required
def api_students_need_help():
    """API: تقرير الطلاب المحتاجين للمساعدة"""
    try:
        user_timezone = get_user_timezone_from_request()
        students = Student.query.filter_by(is_active=True).all()
        need_help = []
        
        current_time_utc = get_utc_time()
        
        for student in students:
            results = Result.query.filter_by(student_id=student.id).order_by(Result.created_at.desc()).all()
            
            if not results:
                # طالب بدون اختبارات منذ التسجيل
                if student.created_at:
                    days_since_registration = (current_time_utc - student.created_at).days
                    if days_since_registration > 7:
                        need_help.append({
                            'student_id': student.id,
                            'student_name': student.name,
                            'email': student.email or '',
                            'issue': 'لم يبدأ الاختبارات بعد',
                            'severity': 'high',
                            'avg_score': 0,
                            'total_quizzes': 0,
                            'last_activity': None,
                            'recommendation': 'تواصل مع الطالب لتشجيعه على البدء',
                            'days_inactive': days_since_registration
                        })
                continue
            
            avg_score = sum(r.score_percentage for r in results) / len(results)
            last_activity_utc = results[0].created_at
            last_activity_local = convert_utc_to_timezone(last_activity_utc, user_timezone)
            days_since_activity = (current_time_utc - last_activity_utc).days
            
            issue = None
            severity = 'low'
            recommendation = ''
            
            # 1. أداء ضعيف جداً
            if avg_score < 50:
                issue = f'أداء ضعيف جداً - المعدل {avg_score:.1f}%'
                severity = 'high'
                recommendation = 'يحتاج لمتابعة مكثفة ومراجعة المناهج الأساسية'
            
            # 2. أداء ضعيف
            elif avg_score < 60:
                issue = f'أداء ضعيف - المعدل {avg_score:.1f}%'
                severity = 'medium'
                recommendation = 'مراجعة المواضيع الصعبة والتدرب أكثر'
            
            # 3. تراجع مستمر
            elif len(results) >= 3:
                recent_scores = [r.score_percentage for r in results[:3]]
                if all(recent_scores[i] > recent_scores[i+1] for i in range(len(recent_scores)-1)):
                    issue = 'تراجع مستمر في الأداء'
                    severity = 'medium'
                    recommendation = 'مراجعة الأسباب والمواضيع الصعبة'
            
            # 4. غير نشط
            elif days_since_activity > 14:
                issue = f'لم يختبر منذ {days_since_activity} يوم'
                severity = 'high' if days_since_activity > 30 else 'medium'
                recommendation = 'إرسال تذكير للطالب'
            
            if issue:
                need_help.append({
                    'student_id': student.id,
                    'student_name': student.name,
                    'email': student.email or '',
                    'phone': student.phone or '',
                    'issue': issue,
                    'severity': severity,
                    'avg_score': round(avg_score, 2),
                    'total_quizzes': len(results),
                    'last_activity': last_activity_local.isoformat() if last_activity_local else None,
                    'recommendation': recommendation,
                    'days_inactive': days_since_activity
                })
        
        # ترتيب حسب الأولوية
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        need_help.sort(key=lambda x: (severity_order[x['severity']], -x['days_inactive']))
        
        return jsonify({
            'success': True,
            'students_need_help': need_help,
            'total': len(need_help),
            'high_priority': sum(1 for s in need_help if s['severity'] == 'high'),
            'medium_priority': sum(1 for s in need_help if s['severity'] == 'medium'),
            'low_priority': sum(1 for s in need_help if s['severity'] == 'low'),
        })
        
    except Exception as e:
        print(f'❌ Error in students need help: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 4. تقرير المناهج (API) ====================
@reports_bp.route('/api/courses-analysis', methods=['GET'])
@login_required
@admin_required
def api_courses_analysis():
    """API: تحليل أداء المناهج"""
    try:
        courses = Course.query.all()
        analysis = []
        
        for course in courses:
            quizzes = Quiz.query.filter_by(course_id=course.id).all()
            
            if not quizzes:
                continue
            
            all_results = []
            for quiz in quizzes:
                results = Result.query.filter_by(quiz_id=quiz.id).all()
                all_results.extend(results)
            
            if not all_results:
                continue
            
            avg_score = sum(r.score_percentage for r in all_results) / len(all_results)
            total_attempts = len(all_results)
            unique_students = len(set(r.student_id for r in all_results))
            
            # تحديد مستوى الصعوبة
            if avg_score >= 80:
                difficulty = 'سهل'
                difficulty_color = 'green'
            elif avg_score >= 60:
                difficulty = 'متوسط'
                difficulty_color = 'orange'
            else:
                difficulty = 'صعب'
                difficulty_color = 'red'
            
            analysis.append({
                'course_id': course.id,
                'course_name': course.name,
                'total_quizzes': len(quizzes),
                'total_attempts': total_attempts,
                'unique_students': unique_students,
                'avg_score': round(avg_score, 2),
                'difficulty': difficulty,
                'difficulty_color': difficulty_color,
                'popularity_rank': total_attempts,
            })
        
        # ترتيب حسب الشعبية
        analysis.sort(key=lambda x: x['popularity_rank'], reverse=True)
        for idx, item in enumerate(analysis, 1):
            item['popularity_rank'] = idx
        
        difficulty_analysis = sorted(analysis, key=lambda x: x['avg_score'])
        
        return jsonify({
            'success': True,
            'courses_analysis': analysis,
            'most_popular': analysis[:5] if len(analysis) >= 5 else analysis,
            'most_difficult': difficulty_analysis[:5] if len(difficulty_analysis) >= 5 else difficulty_analysis,
            'easiest': difficulty_analysis[-5:] if len(difficulty_analysis) >= 5 else difficulty_analysis,
        })
        
    except Exception as e:
        print(f'❌ Error in courses analysis: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 5. تقرير النشاط (API) ====================
@reports_bp.route('/api/activity', methods=['GET'])
@login_required
@admin_required
def api_activity_report():
    """API: تقرير النشاط اليومي/الأسبوعي/الشهري"""
    try:
        period = request.args.get('period', 'week')
        user_timezone = get_user_timezone_from_request()
        
        # تحديد الفترة الزمنية بتوقيت UTC
        current_time_utc = get_utc_time()
        if period == 'day':
            start_date_utc = current_time_utc - timedelta(days=1)
        elif period == 'week':
            start_date_utc = current_time_utc - timedelta(weeks=1)
        else:  # month
            start_date_utc = current_time_utc - timedelta(days=30)
        
        results = Result.query.filter(Result.created_at >= start_date_utc).all()
        
        # تجميع البيانات حسب التاريخ (بالتوقيت المحلي للمستخدم)
        daily_stats = {}
        for result in results:
            # تحويل للتوقيت المحلي
            local_dt = convert_utc_to_timezone(result.created_at, user_timezone)
            date_key = local_dt.date().isoformat()
            
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    'date': date_key,
                    'total_quizzes': 0,
                    'total_students': set(),
                    'avg_score': [],
                    'total_time': 0,
                }
            
            daily_stats[date_key]['total_quizzes'] += 1
            daily_stats[date_key]['total_students'].add(result.student_id)
            daily_stats[date_key]['avg_score'].append(result.score_percentage)
            daily_stats[date_key]['total_time'] += result.time_spent or 0
        
        activity_data = []
        for date_key, stats in sorted(daily_stats.items()):
            activity_data.append({
                'date': date_key,
                'total_quizzes': stats['total_quizzes'],
                'unique_students': len(stats['total_students']),
                'avg_score': round(sum(stats['avg_score']) / len(stats['avg_score']), 2) if stats['avg_score'] else 0,
                'total_time_minutes': round(stats['total_time'] / 60, 1),
            })
        
        total_quizzes = sum(d['total_quizzes'] for d in activity_data)
        all_students = set()
        for result in results:
            all_students.add(result.student_id)
        
        return jsonify({
            'success': True,
            'period': period,
            'activity_data': activity_data,
            'summary': {
                'total_quizzes': total_quizzes,
                'unique_students': len(all_students),
                'avg_daily_quizzes': round(total_quizzes / len(activity_data), 1) if activity_data else 0,
            },
            'timezone': user_timezone,
        })
        
    except Exception as e:
        print(f'❌ Error in activity report: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 6. تفاصيل طالب واحد (API) ====================
@reports_bp.route('/api/student/<int:student_id>', methods=['GET'])
@login_required
@admin_required
def api_student_report(student_id):
    """API: تقرير تفصيلي عن طالب واحد"""
    try:
        user_timezone = get_user_timezone_from_request()
        
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        results = Result.query.filter_by(student_id=student_id).order_by(Result.created_at.desc()).all()
        
        # تحويل تاريخ التسجيل
        created_at_local = convert_utc_to_timezone(student.created_at, user_timezone) if student.created_at else None
        
        if not results:
            return jsonify({
                'success': True,
                'student': {
                    'id': student.id,
                    'name': student.name,
                    'email': student.email or '',
                    'phone': student.phone or '',
                    'school': student.school or '',
                    'grade': student.grade or '',
                    'created_at': created_at_local.isoformat() if created_at_local else None,
                    'is_active': student.is_active,
                },
                'stats': {
                    'total_quizzes': 0,
                    'avg_score': 0,
                    'message': 'لم يقم الطالب بأي اختبار بعد'
                },
                'timezone': user_timezone,
            })
        
        # حساب الإحصائيات
        scores = [r.score_percentage for r in results]
        avg_score = sum(scores) / len(scores)
        total_time = sum(r.time_spent or 0 for r in results)
        
        # تحليل الأداء عبر الوقت (آخر 20 اختبار)
        performance_timeline = []
        for result in reversed(results[-20:]):
            quiz = Quiz.query.get(result.quiz_id)
            result_time_local = convert_utc_to_timezone(result.created_at, user_timezone)
            
            performance_timeline.append({
                'date': result_time_local.isoformat() if result_time_local else None,
                'quiz_name': quiz.name if quiz else 'Unknown',
                'score': round(result.score_percentage, 2),
                'time_spent': result.time_spent or 0,
            })
        
        # تحليل نقاط القوة والضعف
        strengths, weaknesses = analyze_topics(student_id)
        
        # حساب الاتجاه
        improvement_trend = calculate_improvement_trend(results)
        
        # آخر نشاط
        last_activity_local = convert_utc_to_timezone(results[0].created_at, user_timezone)
        
        # توزيع الدرجات
        score_distribution = {
            'excellent': sum(1 for s in scores if s >= 90),
            'very_good': sum(1 for s in scores if 80 <= s < 90),
            'good': sum(1 for s in scores if 70 <= s < 80),
            'acceptable': sum(1 for s in scores if 60 <= s < 70),
            'weak': sum(1 for s in scores if s < 60),
        }
        
        # آخر 10 نتائج
        recent_results = []
        for r in results[:10]:
            quiz = Quiz.query.get(r.quiz_id)
            result_time_local = convert_utc_to_timezone(r.created_at, user_timezone)
            
            recent_results.append({
                'quiz_id': r.quiz_id,
                'quiz_name': quiz.name if quiz else 'Unknown',
                'score': round(r.score_percentage, 2),
                'correct_answers': r.correct_answers,
                'total_questions': r.total_questions,
                'time_spent': r.time_spent or 0,
                'date': result_time_local.isoformat() if result_time_local else None,
            })
        
        return jsonify({
            'success': True,
            'student': {
                'id': student.id,
                'name': student.name,
                'email': student.email or '',
                'phone': student.phone or '',
                'school': student.school or '',
                'grade': student.grade or '',
                'created_at': created_at_local.isoformat() if created_at_local else None,
                'is_active': student.is_active,
            },
            'stats': {
                'total_quizzes': len(results),
                'avg_score': round(avg_score, 2),
                'best_score': round(max(scores), 2),
                'worst_score': round(min(scores), 2),
                'total_time_spent': total_time,
                'avg_time_per_quiz': round(total_time / len(results), 1),
                'last_activity': last_activity_local.isoformat() if last_activity_local else None,
                'improvement_trend': round(improvement_trend, 2),
                'performance_level': get_performance_level(avg_score),
                'active_status': get_activity_status(results[0].created_at),
            },
            'performance_timeline': performance_timeline,
            'score_distribution': score_distribution,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'recent_results': recent_results,
            'timezone': user_timezone,
        })
        
    except Exception as e:
        print(f'❌ Error in student detail: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 7. تصدير Excel (API) ====================
@reports_bp.route('/api/export-excel', methods=['POST'])
@login_required
@admin_required
def api_export_excel():
    """API: تصدير التقرير كملف Excel"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        
        data = request.get_json() or {}
        students = data.get('students', [])
        
        if not students:
            return jsonify({'success': False, 'error': 'No data to export'}), 400
        
        # إنشاء Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "تقرير الطلاب"
        
        # تعريف الأنماط
        header_font = Font(bold=True, size=12, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        cell_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # تعريف الأعمدة
        headers = [
            'م', 'اسم الطالب', 'البريد الإلكتروني', 'الجوال',
            'عدد الاختبارات', 'المعدل العام', 'أفضل نتيجة', 'أسوأ نتيجة',
            'إجمالي الوقت', 'متوسط الوقت/اختبار', 'آخر نشاط',
            'حالة النشاط', 'مستوى الأداء', 'اتجاه التحسن'
        ]
        
        # كتابة الهيدر
        for col, header in enumerate(headers, 1):
            cell = ws.cell(1, col, header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        # كتابة البيانات
        for row_idx, student in enumerate(students, 2):
            ws.cell(row_idx, 1, row_idx - 1).alignment = cell_alignment
            ws.cell(row_idx, 1).border = border
            
            ws.cell(row_idx, 2, student.get('student_name', '')).border = border
            ws.cell(row_idx, 2).alignment = Alignment(horizontal='right', vertical='center')
            
            ws.cell(row_idx, 3, student.get('email', '')).border = border
            ws.cell(row_idx, 3).alignment = Alignment(horizontal='right', vertical='center')
            
            ws.cell(row_idx, 4, student.get('phone', '')).border = border
            ws.cell(row_idx, 4).alignment = cell_alignment
            
            ws.cell(row_idx, 5, student.get('total_quizzes', 0)).alignment = cell_alignment
            ws.cell(row_idx, 5).border = border
            
            # المعدل العام مع تنسيق لوني
            avg_score = student.get('avg_score', 0)
            cell = ws.cell(row_idx, 6, f"{avg_score:.1f}%")
            cell.alignment = cell_alignment
            cell.border = border
            if avg_score >= 80:
                cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            elif avg_score >= 60:
                cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
            elif avg_score > 0:
                cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            
            ws.cell(row_idx, 7, f"{student.get('best_score', 0):.1f}%").alignment = cell_alignment
            ws.cell(row_idx, 7).border = border
            
            ws.cell(row_idx, 8, f"{student.get('worst_score', 0):.1f}%").alignment = cell_alignment
            ws.cell(row_idx, 8).border = border
            
            # الوقت
            total_time = student.get('total_time_spent', 0)
            ws.cell(row_idx, 9, format_time_arabic(total_time)).alignment = cell_alignment
            ws.cell(row_idx, 9).border = border
            
            avg_time = student.get('avg_time_per_quiz', 0)
            ws.cell(row_idx, 10, f"{avg_time:.1f} ث").alignment = cell_alignment
            ws.cell(row_idx, 10).border = border
            
            # آخر نشاط
            last_activity = student.get('last_activity', '')
            if last_activity:
                try:
                    dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                    ws.cell(row_idx, 11, dt.strftime('%Y-%m-%d %H:%M')).alignment = cell_alignment
                except:
                    ws.cell(row_idx, 11, 'غير متاح').alignment = cell_alignment
            else:
                ws.cell(row_idx, 11, 'غير متاح').alignment = cell_alignment
            ws.cell(row_idx, 11).border = border
            
            ws.cell(row_idx, 12, student.get('active_status', '')).alignment = cell_alignment
            ws.cell(row_idx, 12).border = border
            
            ws.cell(row_idx, 13, student.get('performance_level', '')).alignment = cell_alignment
            ws.cell(row_idx, 13).border = border
            
            # اتجاه التحسن
            trend = student.get('improvement_trend', 0)
            trend_text = f"+{trend:.1f}%" if trend > 0 else f"{trend:.1f}%"
            cell = ws.cell(row_idx, 14, trend_text)
            cell.alignment = cell_alignment
            cell.border = border
            if trend > 5:
                cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            elif trend < -5:
                cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        
        # ضبط عرض الأعمدة
        column_widths = [5, 25, 30, 15, 15, 15, 15, 15, 18, 18, 20, 15, 15, 15]
        for idx, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(idx)].width = width
        
        # حفظ في memory
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        
        filename = f'students_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f'❌ Error exporting Excel: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Helper Functions ====================

def calculate_improvement_trend(results):
    """حساب اتجاه التحسن"""
    if len(results) < 3:
        return 0
    
    recent = [r.score_percentage for r in results[:min(5, len(results))]]
    older = [r.score_percentage for r in results[-min(5, len(results)):]]
    
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    
    return avg_recent - avg_older


def get_activity_status(last_activity_utc):
    """تحديد حالة النشاط"""
    if not last_activity_utc:
        return 'غير نشط'
    
    current_time_utc = get_utc_time()
    days_since = (current_time_utc - last_activity_utc).days
    
    if days_since <= 1:
        return 'نشط جداً'
    elif days_since <= 7:
        return 'نشط'
    elif days_since <= 14:
        return 'خامل'
    else:
        return 'غير نشط'


def get_performance_level(avg_score):
    """تحديد مستوى الأداء"""
    if avg_score >= 90:
        return 'ممتاز'
    elif avg_score >= 80:
        return 'جيد جداً'
    elif avg_score >= 70:
        return 'جيد'
    elif avg_score >= 60:
        return 'مقبول'
    elif avg_score > 0:
        return 'ضعيف'
    else:
        return 'لا توجد بيانات'


def get_badge(rank):
    """الحصول على شارة حسب الترتيب"""
    badges = {
        1: '🏆 المركز الأول',
        2: '🥈 المركز الثاني',
        3: '🥉 المركز الثالث'
    }
    return badges.get(rank, f'⭐ المركز {rank}')


def analyze_topics(student_id):
    """تحليل نقاط القوة والضعف حسب المواضيع"""
    results = Result.query.filter_by(student_id=student_id).all()
    
    if not results:
        return [], []
    
    # تجميع النتائج حسب المنهج
    course_scores = {}
    for result in results:
        quiz = Quiz.query.get(result.quiz_id)
        if quiz and quiz.course_id:
            course = Course.query.get(quiz.course_id)
            if course:
                if course.name not in course_scores:
                    course_scores[course.name] = []
                course_scores[course.name].append(result.score_percentage)
    
    # حساب المتوسطات
    course_averages = []
    for course_name, scores in course_scores.items():
        avg = sum(scores) / len(scores)
        course_averages.append({
            'course': course_name,
            'avg_score': round(avg, 2),
            'total_attempts': len(scores)
        })
    
    # ترتيب
    course_averages.sort(key=lambda x: x['avg_score'], reverse=True)
    
    strengths = course_averages[:3]
    weaknesses = list(reversed(course_averages[-3:]))
    
    return strengths, weaknesses


def format_time_arabic(seconds):
    """تنسيق الوقت بالعربية"""
    if seconds < 60:
        return f'{seconds} ثانية'
    elif seconds < 3600:
        minutes = seconds // 60
        return f'{minutes} دقيقة'
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f'{hours} ساعة و {minutes} دقيقة'
        return f'{hours} ساعة'
