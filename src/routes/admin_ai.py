# src/routes/admin_ai.py
"""
Admin AI Routes - واجهات API للأدمن للتحكم في نظام AI
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime

from src.services.ai_assistant import ai_assistant
from src.services.smart_notifications import smart_notifications
from src.tasks.student_analyzer import student_analyzer
from src.models.ai_analysis import AIAnalysis, AIAction, AILog, AISetting
from src.models.student import Student
from src.extensions import db

# إنشاء Blueprint
admin_ai_bp = Blueprint('admin_ai', __name__, url_prefix='/api/admin/ai')


# ============================================
# Decorators
# ============================================

def admin_required(f):
    """Decorator للتحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TODO: تحقق من JWT token أو session
        # للتبسيط، نفترض أن الأدمن مسجل دخول
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# Analysis Routes
# ============================================

@admin_ai_bp.route('/analyze/student/<int:student_id>', methods=['POST'])
@admin_required
def analyze_single_student(student_id):
    """
    تحليل طالب واحد
    
    POST /api/admin/ai/analyze/student/1
    """
    try:
        # التحقق من وجود الطالب
        student = Student.query.get(student_id)
        if not student:
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
        # تحليل الطالب
        result = ai_assistant.analyze_student(
            student_id=student_id,
            analysis_type='manual'
        )
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'فشل التحليل'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'تم التحليل بنجاح',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/analyze/all', methods=['POST'])
@admin_required
def analyze_all():
    """
    تحليل جميع الطلاب
    
    POST /api/admin/ai/analyze/all
    """
    try:
        result = student_analyzer.analyze_all_students()
        
        return jsonify({
            'success': True,
            'message': 'تم التحليل بنجاح',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/analysis/latest/<int:student_id>', methods=['GET'])
@admin_required
def get_latest_analysis(student_id):
    """
    جلب آخر تحليل لطالب
    
    GET /api/admin/ai/analysis/latest/1
    """
    try:
        analysis = AIAnalysis.get_latest_for_student(student_id)
        
        if not analysis:
            return jsonify({
                'success': False,
                'error': 'لا يوجد تحليل'
            }), 404
        
        return jsonify({
            'success': True,
            'data': analysis.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/analysis/history/<int:student_id>', methods=['GET'])
@admin_required
def get_analysis_history(student_id):
    """
    جلب تاريخ تحليلات طالب
    
    GET /api/admin/ai/analysis/history/1?limit=10
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        
        analyses = AIAnalysis.query.filter_by(student_id=student_id)\
            .order_by(AIAnalysis.created_at.desc())\
            .limit(limit).all()
        
        return jsonify({
            'success': True,
            'data': [a.to_dict() for a in analyses]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Dashboard Routes
# ============================================

@admin_ai_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    """
    إحصائيات Dashboard
    
    GET /api/admin/ai/dashboard/stats
    """
    try:
        # إحصائيات عامة
        total_students = Student.query.filter_by(is_active=True).count()
        
        # آخر تحليل لكل طالب
        latest_analyses = db.session.query(
            AIAnalysis.student_id,
            db.func.max(AIAnalysis.id).label('latest_id')
        ).group_by(AIAnalysis.student_id).subquery()
        
        analyses = db.session.query(AIAnalysis).join(
            latest_analyses,
            AIAnalysis.id == latest_analyses.c.latest_id
        ).all()
        
        # تجميع حسب الخطورة
        severity_counts = {
            'green': 0,
            'yellow': 0,
            'orange': 0,
            'red': 0
        }
        
        for analysis in analyses:
            severity = analysis.severity_level
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # الطلاب الذين يحتاجون انتباه
        needs_attention = [a for a in analyses if a.severity_level in ['orange', 'red']]
        
        return jsonify({
            'success': True,
            'data': {
                'total_students': total_students,
                'analyzed_students': len(analyses),
                'severity_distribution': severity_counts,
                'needs_attention': len(needs_attention),
                'critical': severity_counts['red'],
                'last_update': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/dashboard/students-need-attention', methods=['GET'])
@admin_required
def get_students_need_attention():
    """
    قائمة الطلاب الذين يحتاجون انتباه
    
    GET /api/admin/ai/dashboard/students-need-attention
    """
    try:
        # جلب الطلاب حسب الخطورة
        orange = AIAnalysis.get_students_by_severity('orange')
        red = AIAnalysis.get_students_by_severity('red')
        
        all_students = red + orange
        
        result = []
        for analysis in all_students:
            student = Student.query.get(analysis.student_id)
            if student:
                result.append({
                    'student_id': student.id,
                    'student_name': student.name,
                    'grade': student.grade,
                    'severity': analysis.severity_level,
                    'status': analysis.student_status,
                    'average_score': analysis.average_score,
                    'days_inactive': analysis.days_since_last_quiz,
                    'issues': analysis.issues_detected,
                    'last_analysis': analysis.created_at.isoformat()
                })
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Notifications Routes
# ============================================

@admin_ai_bp.route('/notification/send', methods=['POST'])
@admin_required
def send_notification():
    """
    إرسال إشعار لطلاب محددين
    
    POST /api/admin/ai/notification/send
    Body:
    {
        "student_ids": [1, 2, 3],
        "title": "عنوان",
        "body": "محتوى",
        "type": "info"
    }
    """
    try:
        data = request.get_json()
        
        student_ids = data.get('student_ids', [])
        title = data.get('title', '')
        body = data.get('body', '')
        notification_type = data.get('type', 'info')
        
        if not student_ids or not title or not body:
            return jsonify({
                'success': False,
                'error': 'بيانات ناقصة'
            }), 400
        
        result = smart_notifications.send_bulk_notification(
            student_ids=student_ids,
            title=title,
            body=body,
            notification_type=notification_type
        )
        
        return jsonify({
            'success': True,
            'message': 'تم إرسال الإشعار',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# AI Chat Routes
# ============================================

@admin_ai_bp.route('/chat', methods=['POST'])
@admin_required
def chat_with_ai():
    """
    محادثة مع AI
    
    POST /api/admin/ai/chat
    Body:
    {
        "message": "كيف أحسن أداء الطلاب؟",
        "context": {...}  // اختياري
    }
    """
    try:
        data = request.get_json()
        
        message = data.get('message', '')
        context = data.get('context', None)
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'الرسالة مطلوبة'
            }), 400
        
        response = ai_assistant.chat_with_ai(message, context)
        
        return jsonify({
            'success': True,
            'data': {
                'response': response
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Settings Routes
# ============================================

@admin_ai_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    """
    جلب جميع الإعدادات
    
    GET /api/admin/ai/settings
    """
    try:
        settings = AISetting.query.all()
        
        result = {}
        for setting in settings:
            result[setting.setting_key] = {
                'value': setting.get_typed_value(),
                'type': setting.setting_type,
                'description': setting.description
            }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/settings/<setting_key>', methods=['PUT'])
@admin_required
def update_setting(setting_key):
    """
    تحديث إعداد
    
    PUT /api/admin/ai/settings/analysis_interval_hours
    Body:
    {
        "value": "12"
    }
    """
    try:
        data = request.get_json()
        value = data.get('value')
        
        if value is None:
            return jsonify({
                'success': False,
                'error': 'القيمة مطلوبة'
            }), 400
        
        setting = AISetting.query.filter_by(setting_key=setting_key).first()
        
        if not setting:
            return jsonify({
                'success': False,
                'error': 'الإعداد غير موجود'
            }), 404
        
        # تحديث القيمة
        setting.setting_value = str(value)
        setting.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم التحديث بنجاح',
            'data': {
                'key': setting.setting_key,
                'value': setting.get_typed_value()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Logs Routes
# ============================================

@admin_ai_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """
    جلب السجلات
    
    GET /api/admin/ai/logs?limit=50&operation_type=analyze_student
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        operation_type = request.args.get('operation_type', None)
        
        query = AILog.query.order_by(AILog.created_at.desc())
        
        if operation_type:
            query = query.filter_by(operation_type=operation_type)
        
        logs = query.limit(limit).all()
        
        return jsonify({
            'success': True,
            'data': [log.to_dict() for log in logs]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Reports Routes
# ============================================

@admin_ai_bp.route('/report/daily', methods=['GET'])
@admin_required
def get_daily_report():
    """
    التقرير اليومي
    
    GET /api/admin/ai/report/daily
    """
    try:
        report = student_analyzer.generate_daily_report()
        
        return jsonify({
            'success': True,
            'data': report
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# System Status Routes
# ============================================

@admin_ai_bp.route('/status', methods=['GET'])
@admin_required
def get_system_status():
    """
    حالة النظام
    
    GET /api/admin/ai/status
    """
    try:
        return jsonify({
            'success': True,
            'data': {
                'ai_configured': ai_assistant.is_configured,
                'ai_provider': ai_assistant.provider,
                'ai_model': ai_assistant.model_name,
                'scheduler_running': not student_analyzer.is_running,
                'current_time': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
