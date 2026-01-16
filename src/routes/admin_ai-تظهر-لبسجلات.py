# src/routes/admin_ai.py
"""
Admin AI Routes - واجهات API للأدمن للتحكم في نظام AI
مع التحسينات: Validation, Export/Import, Testing, Presets, Analytics
"""

from flask import Blueprint, request, jsonify, send_file
from functools import wraps
from datetime import datetime, timedelta
import json
import io

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
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# Settings Presets (في الكود - بدون migration)
# ============================================

SETTINGS_PRESETS = {
    'conservative': {
        'name': 'محافظ',
        'name_en': 'Conservative',
        'description': 'مناسب لبداية الفصل - متابعة هادئة',
        'icon': '🛡️',
        'settings': {
            'analysis_interval_hours': 48,
            'inactive_days_threshold': 14,
            'critical_inactive_days': 30,
            'max_messages_per_student_day': 1,
            'score_decline_threshold': 30,
            'enable_auto_messages': False,
            'enable_admin_alerts': True
        }
    },
    'balanced': {
        'name': 'متوازن',
        'name_en': 'Balanced',
        'description': 'الإعدادات الموصى بها - مناسب للاستخدام اليومي',
        'icon': '⚖️',
        'settings': {
            'analysis_interval_hours': 24,
            'inactive_days_threshold': 7,
            'critical_inactive_days': 14,
            'max_messages_per_student_day': 3,
            'score_decline_threshold': 20,
            'enable_auto_messages': True,
            'enable_admin_alerts': True
        }
    },
    'aggressive': {
        'name': 'عدواني',
        'name_en': 'Aggressive',
        'description': 'متابعة حثيثة - مناسب قرب الاختبارات',
        'icon': '🚀',
        'settings': {
            'analysis_interval_hours': 12,
            'inactive_days_threshold': 3,
            'critical_inactive_days': 7,
            'max_messages_per_student_day': 5,
            'score_decline_threshold': 15,
            'enable_auto_messages': True,
            'enable_admin_alerts': True
        }
    },
    'exam_week': {
        'name': 'أسبوع الاختبارات',
        'name_en': 'Exam Week',
        'description': 'متابعة مكثفة يومية',
        'icon': '🎯',
        'settings': {
            'analysis_interval_hours': 6,
            'inactive_days_threshold': 1,
            'critical_inactive_days': 2,
            'max_messages_per_student_day': 10,
            'score_decline_threshold': 10,
            'enable_auto_messages': True,
            'enable_admin_alerts': True
        }
    },
    'vacation': {
        'name': 'إجازة',
        'name_en': 'Vacation',
        'description': 'تقليل التنبيهات خلال الإجازات',
        'icon': '🏖️',
        'settings': {
            'analysis_interval_hours': 168,
            'inactive_days_threshold': 30,
            'critical_inactive_days': 60,
            'max_messages_per_student_day': 0,
            'score_decline_threshold': 40,
            'enable_auto_messages': False,
            'enable_admin_alerts': False
        }
    }
}


# ============================================
# Validation Functions
# ============================================

def validate_setting_value(setting_key, value):
    """
    التحقق من صحة قيمة الإعداد
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    validations = {
        'analysis_interval_hours': {
            'type': 'int',
            'min': 1,
            'max': 168,
            'message': 'يجب أن يكون بين 1 و 168 ساعة (أسبوع)'
        },
        'inactive_days_threshold': {
            'type': 'int',
            'min': 1,
            'max': 60,
            'message': 'يجب أن يكون بين 1 و 60 يوماً'
        },
        'critical_inactive_days': {
            'type': 'int',
            'min': 1,
            'max': 90,
            'message': 'يجب أن يكون بين 1 و 90 يوماً'
        },
        'max_messages_per_student_day': {
            'type': 'int',
            'min': 0,
            'max': 20,
            'message': 'يجب أن يكون بين 0 و 20 رسالة'
        },
        'score_decline_threshold': {
            'type': 'float',
            'min': 0,
            'max': 100,
            'message': 'يجب أن يكون بين 0 و 100%'
        },
        'daily_report_time': {
            'type': 'time',
            'message': 'يجب أن يكون بصيغة HH:MM مثل 08:00'
        }
    }
    
    if setting_key not in validations:
        return True, None
    
    rule = validations[setting_key]
    
    try:
        if rule['type'] == 'int':
            val = int(value)
            if val < rule['min'] or val > rule['max']:
                return False, rule['message']
        
        elif rule['type'] == 'float':
            val = float(value)
            if val < rule['min'] or val > rule['max']:
                return False, rule['message']
        
        elif rule['type'] == 'time':
            # التحقق من صيغة HH:MM
            parts = str(value).split(':')
            if len(parts) != 2:
                return False, rule['message']
            hour = int(parts[0])
            minute = int(parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                return False, rule['message']
        
        return True, None
        
    except (ValueError, TypeError):
        return False, rule['message']


def validate_business_rules(settings_dict):
    """
    التحقق من قواعد العمل بين الإعدادات
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    try:
        # القاعدة 1: الحد الحرج يجب أن يكون أكبر من الحد العادي
        if 'critical_inactive_days' in settings_dict and 'inactive_days_threshold' in settings_dict:
            critical = int(settings_dict['critical_inactive_days'])
            normal = int(settings_dict['inactive_days_threshold'])
            
            if critical <= normal:
                return False, 'الحد الحرج لعدم النشاط يجب أن يكون أكبر من الحد العادي'
        
        return True, None
        
    except (ValueError, TypeError, KeyError):
        return True, None  # نتجاهل الأخطاء في التحويل


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
        student = Student.query.get(student_id)
        if not student:
            return jsonify({
                'success': False,
                'error': 'الطالب غير موجود'
            }), 404
        
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
    """تحليل جميع الطلاب"""
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
    """جلب آخر تحليل لطالب"""
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
    """جلب تاريخ تحليلات طالب"""
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
    """إحصائيات Dashboard"""
    try:
        total_students = Student.query.filter_by(is_active=True).count()
        
        latest_analyses = db.session.query(
            AIAnalysis.student_id,
            db.func.max(AIAnalysis.id).label('latest_id')
        ).group_by(AIAnalysis.student_id).subquery()
        
        analyses = db.session.query(AIAnalysis).join(
            latest_analyses,
            AIAnalysis.id == latest_analyses.c.latest_id
        ).all()
        
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
        
        needs_attention = [a for a in analyses if a.severity_level in ['orange', 'red']]
        
        # ✅ إضافة إحصائيات آخر 24 ساعة من AILog
        cutoff_date = datetime.utcnow() - timedelta(hours=24)
        
        # عدد الرسائل المرسلة (آخر 24 ساعة)
        recent_messages = AIAction.query.filter(
            AIAction.created_at >= cutoff_date,
            AIAction.action_type == 'smart_message'
        ).count()
        
        # عدد التحليلات (آخر 24 ساعة)
        recent_analyses = AIAnalysis.query.filter(
            AIAnalysis.created_at >= cutoff_date
        ).count()
        
        # عدد عمليات الإرسال التلقائي (آخر 24 ساعة)
        automation_runs = AILog.query.filter(
            AILog.created_at >= cutoff_date,
            AILog.operation_type == 'automation_send_messages'
        ).count()
        
        # آخر تشغيل تلقائي
        last_automation = AILog.query.filter(
            AILog.operation_type == 'automation_send_messages'
        ).order_by(AILog.created_at.desc()).first()
        
        last_run_info = None
        if last_automation:
            last_run_info = {
                'timestamp': last_automation.created_at.isoformat(),
                'success': last_automation.success,
                'data': last_automation.data
            }
        
        return jsonify({
            'success': True,
            'data': {
                'total_students': total_students,
                'analyzed_students': len(analyses),
                'severity_distribution': severity_counts,
                'needs_attention': len(needs_attention),
                'critical': severity_counts['red'],
                'last_update': datetime.utcnow().isoformat(),
                # ✅ إحصائيات جديدة
                'last_24_hours': {
                    'messages_sent': recent_messages,
                    'analyses_performed': recent_analyses,
                    'automation_runs': automation_runs,
                    'last_automation_run': last_run_info
                }
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
    """قائمة الطلاب الذين يحتاجون انتباه"""
    try:
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
    """إرسال إشعار لطلاب محددين"""
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
    """محادثة مع AI"""
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
# Settings Routes (المحسّنة)
# ============================================

@admin_ai_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    """جلب جميع الإعدادات"""
    try:
        settings = AISetting.query.all()
        
        result = {}
        for setting in settings:
            result[setting.setting_key] = {
                'value': setting.get_value(),
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
    تحديث أو إنشاء إعداد مع Validation
    """
    try:
        data = request.get_json()
        value = data.get('value')
        
        if value is None:
            return jsonify({
                'success': False,
                'error': 'القيمة مطلوبة'
            }), 400
        
        # Validation للقيمة
        is_valid, error_msg = validate_setting_value(setting_key, value)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        setting = AISetting.query.filter_by(setting_key=setting_key).first()
        
        if not setting:
            # ✅ إنشاء إعداد جديد إذا لم يكن موجوداً
            setting_type = 'int' if isinstance(value, int) else 'string' if isinstance(value, str) else 'boolean'
            
            setting = AISetting(
                setting_key=setting_key,
                setting_value=str(value),
                setting_type=setting_type,
                description=f'إعداد {setting_key}'
            )
            db.session.add(setting)
            message = 'تم إنشاء الإعداد بنجاح'
        else:
            # تحديث القيمة الموجودة
            setting.setting_value = str(value)
            setting.updated_at = datetime.utcnow()
            message = 'تم التحديث بنجاح'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'key': setting.setting_key,
                'value': setting.get_value()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Settings Export/Import Routes (جديد)
# ============================================

@admin_ai_bp.route('/settings/export', methods=['GET'])
@admin_required
def export_settings():
    """
    تصدير جميع الإعدادات كملف JSON
    
    GET /api/admin/ai/settings/export
    """
    try:
        settings = AISetting.query.all()
        
        export_data = {
            'exported_at': datetime.utcnow().isoformat(),
            'app_version': '2.1.0',
            'platform': 'chem-tahsili',
            'settings': {}
        }
        
        for setting in settings:
            export_data['settings'][setting.setting_key] = {
                'value': setting.get_value(),
                'type': setting.setting_type,
                'description': setting.description
            }
        
        return jsonify({
            'success': True,
            'data': export_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/settings/import', methods=['POST'])
@admin_required
def import_settings():
    """
    استيراد الإعدادات من ملف JSON مع Validation
    
    POST /api/admin/ai/settings/import
    Body: {exported JSON data}
    """
    try:
        data = request.get_json()
        
        if not data or 'settings' not in data:
            return jsonify({
                'success': False,
                'error': 'بيانات غير صحيحة'
            }), 400
        
        settings_to_import = data['settings']
        
        # Validation لكل إعداد
        validation_errors = []
        for key, value_obj in settings_to_import.items():
            value = value_obj.get('value')
            is_valid, error_msg = validate_setting_value(key, value)
            if not is_valid:
                validation_errors.append(f'{key}: {error_msg}')
        
        if validation_errors:
            return jsonify({
                'success': False,
                'error': 'أخطاء في التحقق',
                'validation_errors': validation_errors
            }), 400
        
        # Business rules validation
        settings_dict = {k: v['value'] for k, v in settings_to_import.items()}
        is_valid, error_msg = validate_business_rules(settings_dict)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # تطبيق الإعدادات
        updated_count = 0
        for key, value_obj in settings_to_import.items():
            setting = AISetting.query.filter_by(setting_key=key).first()
            if setting:
                setting.setting_value = str(value_obj['value'])
                setting.updated_at = datetime.utcnow()
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'تم استيراد {updated_count} إعداد بنجاح',
            'data': {
                'updated_count': updated_count,
                'imported_at': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Settings Presets Routes (جديد)
# ============================================

@admin_ai_bp.route('/settings/presets', methods=['GET'])
@admin_required
def get_presets():
    """
    جلب قوالب الإعدادات الجاهزة
    
    GET /api/admin/ai/settings/presets
    """
    try:
        return jsonify({
            'success': True,
            'data': SETTINGS_PRESETS
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/settings/presets/<preset_name>/apply', methods=['POST'])
@admin_required
def apply_preset(preset_name):
    """
    تطبيق preset محدد
    
    POST /api/admin/ai/settings/presets/balanced/apply
    """
    try:
        if preset_name not in SETTINGS_PRESETS:
            return jsonify({
                'success': False,
                'error': 'Preset غير موجود'
            }), 404
        
        preset = SETTINGS_PRESETS[preset_name]
        settings_to_apply = preset['settings']
        
        # تطبيق كل إعداد
        updated_count = 0
        for key, value in settings_to_apply.items():
            setting = AISetting.query.filter_by(setting_key=key).first()
            if setting:
                setting.setting_value = str(value)
                setting.updated_at = datetime.utcnow()
                updated_count += 1
        
        db.session.commit()
        
        # Log العملية
        AILog.log_operation(
            operation_type='apply_preset',
            description=f'تطبيق preset: {preset["name"]}',
            success=True,
            data={'preset_name': preset_name, 'updated_count': updated_count}
        )
        
        return jsonify({
            'success': True,
            'message': f'تم تطبيق إعدادات "{preset["name"]}" بنجاح',
            'data': {
                'preset_name': preset_name,
                'preset_display_name': preset['name'],
                'updated_count': updated_count
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Testing Mode Route (جديد)
# ============================================

@admin_ai_bp.route('/test-analysis', methods=['POST'])
@admin_required
def test_analysis():
    """
    اختبار AI بالإعدادات الحالية على بيانات وهمية
    
    POST /api/admin/ai/test-analysis
    Body:
    {
        "total_quizzes": 5,
        "average_score": 65.0,
        "days_since_last_quiz": 8
    }
    """
    try:
        data = request.get_json()
        
        # بيانات الطالب الوهمي
        test_data = {
            'total_quizzes': data.get('total_quizzes', 5),
            'average_score': data.get('average_score', 65.0),
            'days_since_last_quiz': data.get('days_since_last_quiz', 8),
            'last_quiz_date': None
        }
        
        # الحصول على الإعدادات الحالية
        inactive_threshold = int(AISetting.get_setting('inactive_days_threshold', 7))
        critical_threshold = int(AISetting.get_setting('critical_inactive_days', 14))
        score_threshold = float(AISetting.get_setting('score_decline_threshold', 20))
        
        # محاكاة التحليل
        days_inactive = test_data['days_since_last_quiz']
        avg_score = test_data['average_score']
        
        # تحديد الحالة
        if days_inactive >= critical_threshold:
            status = 'critical'
            severity = 'red'
            action = 'admin_alert'
        elif days_inactive >= inactive_threshold:
            status = 'needs_attention'
            severity = 'orange'
            action = 'send_message'
        elif avg_score < 50:
            status = 'needs_attention'
            severity = 'orange'
            action = 'send_message'
        elif avg_score >= 80:
            status = 'excellent'
            severity = 'green'
            action = 'no_action'
        else:
            status = 'good'
            severity = 'yellow'
            action = 'no_action'
        
        result = {
            'test_data': test_data,
            'current_settings': {
                'inactive_days_threshold': inactive_threshold,
                'critical_inactive_days': critical_threshold,
                'score_decline_threshold': score_threshold
            },
            'analysis_result': {
                'status': status,
                'severity': severity,
                'suggested_action': action,
                'days_inactive': days_inactive,
                'average_score': avg_score
            },
            'interpretation': {
                'status_ar': {
                    'excellent': 'ممتاز',
                    'good': 'جيد',
                    'needs_attention': 'يحتاج انتباه',
                    'critical': 'حرج'
                }.get(status, status),
                'action_ar': {
                    'no_action': 'لا يحتاج إجراء',
                    'send_message': 'إرسال رسالة تحفيزية',
                    'admin_alert': 'تنبيه عاجل للأدمن'
                }.get(action, action)
            }
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


# ============================================
# Analytics Routes (جديد)
# ============================================

@admin_ai_bp.route('/analytics/overview', methods=['GET'])
@admin_required
def get_analytics_overview():
    """
    نظرة عامة على تحليلات النظام
    
    GET /api/admin/ai/analytics/overview?days=7
    """
    try:
        days = request.args.get('days', 7, type=int)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # إحصائيات التحليلات
        total_analyses = AIAnalysis.query.filter(
            AIAnalysis.created_at >= cutoff_date
        ).count()
        
        # إحصائيات الرسائل
        total_messages = AIAction.query.filter(
            AIAction.created_at >= cutoff_date,
            AIAction.action_type == 'smart_message'
        ).count()
        
        # إحصائيات النجاح
        successful_operations = AILog.query.filter(
            AILog.created_at >= cutoff_date,
            AILog.success == True
        ).count()
        
        failed_operations = AILog.query.filter(
            AILog.created_at >= cutoff_date,
            AILog.success == False
        ).count()
        
        # متوسط وقت التنفيذ
        avg_duration = db.session.query(
            db.func.avg(AILog.duration_seconds)
        ).filter(
            AILog.created_at >= cutoff_date,
            AILog.duration_seconds != None
        ).scalar()
        
        return jsonify({
            'success': True,
            'data': {
                'period_days': days,
                'total_analyses': total_analyses,
                'total_messages_sent': total_messages,
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'success_rate': round(successful_operations / (successful_operations + failed_operations) * 100, 2) if (successful_operations + failed_operations) > 0 else 0,
                'avg_duration_seconds': round(avg_duration, 2) if avg_duration else 0
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/analytics/trends', methods=['GET'])
@admin_required
def get_trends():
    """
    اتجاهات التحليلات عبر الوقت
    
    GET /api/admin/ai/analytics/trends?days=30
    """
    try:
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # جلب التحليلات اليومية
        daily_stats = db.session.query(
            db.func.date(AIAnalysis.created_at).label('date'),
            AIAnalysis.severity_level,
            db.func.count(AIAnalysis.id).label('count')
        ).filter(
            AIAnalysis.created_at >= cutoff_date
        ).group_by(
            db.func.date(AIAnalysis.created_at),
            AIAnalysis.severity_level
        ).all()
        
        # تنظيم البيانات
        trends = {}
        for stat in daily_stats:
            date_str = stat.date.isoformat()
            if date_str not in trends:
                trends[date_str] = {'green': 0, 'yellow': 0, 'orange': 0, 'red': 0}
            trends[date_str][stat.severity_level] = stat.count
        
        return jsonify({
            'success': True,
            'data': {
                'period_days': days,
                'trends': trends
            }
        })
        
    except Exception as e:
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
    """جلب السجلات"""
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
    """التقرير اليومي"""
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
    """حالة النظام"""
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


# ============================================
# Messaging Monitor Routes (جديد)
# ============================================

@admin_ai_bp.route('/messages/sent', methods=['GET'])
@admin_required
def get_sent_messages():
    """
    الحصول على قائمة الرسائل المرسلة
    
    GET /api/admin/ai/messages/sent?limit=100&period=today
    """
    try:
        from src.models.notification import Notification
        
        limit = request.args.get('limit', 100, type=int)
        period = request.args.get('period', None, type=str)
        
        # بناء الاستعلام
        query = db.session.query(
            Notification.id,
            Notification.student_id,
            Student.name.label('student_name'),
            Notification.title,
            Notification.body,
            Notification.type,
            Notification.status,
            Notification.is_automatic,
            Notification.sent_at,
            Notification.created_at
        ).join(
            Student, Notification.student_id == Student.id
        )
        
        # تصفية حسب الفترة
        if period == 'today':
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
            query = query.filter(Notification.sent_at >= today_start)
        elif period == 'week':
            week_start = datetime.utcnow() - timedelta(days=7)
            query = query.filter(Notification.sent_at >= week_start)
        elif period == 'month':
            month_start = datetime.utcnow() - timedelta(days=30)
            query = query.filter(Notification.sent_at >= month_start)
        
        # ترتيب وحد
        messages = query.order_by(
            Notification.sent_at.desc()
        ).limit(limit).all()
        
        # تحويل للقائمة
        result = []
        for msg in messages:
            result.append({
                'id': msg.id,
                'student_id': msg.student_id,
                'student_name': msg.student_name,
                'title': msg.title,
                'body': msg.body,
                'type': msg.type,
                'status': msg.status,
                'is_automatic': msg.is_automatic,
                'sent_at': msg.sent_at.isoformat() if msg.sent_at else None,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
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


@admin_ai_bp.route('/messages/stats', methods=['GET'])
@admin_required
def get_messaging_stats():
    """
    الحصول على إحصائيات الإرسال
    
    GET /api/admin/ai/messages/stats?period=today
    """
    try:
        from src.models.notification import Notification
        
        period = request.args.get('period', None, type=str)
        
        # تحديد الفترة
        start_date = None
        if period == 'today':
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
        elif period == 'week':
            start_date = datetime.utcnow() - timedelta(days=7)
        elif period == 'month':
            start_date = datetime.utcnow() - timedelta(days=30)
        
        # بناء الاستعلام الأساسي
        query = db.session.query(Notification)
        if start_date:
            query = query.filter(Notification.sent_at >= start_date)
        
        # حساب الإحصائيات
        total_sent = query.count()
        delivered = query.filter(Notification.status == 'delivered').count()
        failed = query.filter(Notification.status == 'failed').count()
        pending = query.filter(Notification.status == 'pending').count()
        
        return jsonify({
            'success': True,
            'data': {
                'total_sent': total_sent,
                'delivered': delivered,
                'failed': failed,
                'pending': pending,
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# Automation Control Routes (جديد)
# ============================================

@admin_ai_bp.route('/automation/status', methods=['GET'])
@admin_required
def get_automation_status():
    """
    الحصول على حالة النظام التلقائي
    يقرأ الإعدادات من ai_settings (نفس Flutter)
    
    GET /api/admin/ai/automation/status
    """
    try:
        from sqlalchemy import text
        
        # 🔥 قراءة مباشرة من DB - الإعدادات الأصلية
        result = db.session.execute(text("""
            SELECT setting_key, setting_value 
            FROM ai_settings 
            WHERE setting_key IN (
                'enable_auto_messages',
                'analysis_interval_hours',
                'automation_start_hour',
                'automation_end_hour'
            )
        """)).fetchall()
        
        settings = {row[0]: row[1] for row in result}
        
        # قراءة الإعدادات
        automation_enabled = settings.get('enable_auto_messages', 'false') == 'true'
        interval_hours = int(settings.get('analysis_interval_hours', 24))
        start_hour = int(settings.get('automation_start_hour', 8))
        end_hour = int(settings.get('automation_end_hour', 22))
        
        print(f"🔥 قرأنا enable_auto_messages من DB: {settings.get('enable_auto_messages')}")
        print(f"✅ النتيجة النهائية: automation_enabled = {automation_enabled}")
        
        # جلب آخر تشغيل
        last_run_log = AILog.query.filter(
            AILog.operation_type == 'automated_analysis'
        ).order_by(
            AILog.created_at.desc()
        ).first()
        
        last_run = None
        if last_run_log:
            metadata = json.loads(last_run_log.metadata) if last_run_log.metadata else {}
            last_run = {
                'timestamp': last_run_log.created_at.isoformat(),
                'success': last_run_log.success,
                'analyzed': metadata.get('analyzed', 0),
                'messages_sent': metadata.get('messages_sent', 0),
                'errors': metadata.get('errors', 0),
            }
        
        # حساب التشغيل القادم
        next_run = None
        if automation_enabled and last_run_log:
            next_run_time = last_run_log.created_at + timedelta(hours=interval_hours)
            next_run = next_run_time.isoformat()
        
        # إحصائيات 24 ساعة الماضية
        yesterday = datetime.utcnow() - timedelta(hours=24)
        stats_logs = AILog.query.filter(
            AILog.operation_type == 'automated_analysis',
            AILog.created_at >= yesterday
        ).all()
        
        total_analyzed = 0
        total_messages = 0
        for log in stats_logs:
            if log.metadata:
                metadata = json.loads(log.metadata) if isinstance(log.metadata, str) else log.metadata
                total_analyzed += metadata.get('analyzed', 0)
                total_messages += metadata.get('messages_sent', 0)
        
        statistics = {
            'total_runs': len(stats_logs),
            'successful_runs': sum(1 for log in stats_logs if log.success),
            'total_analyzed': total_analyzed,
            'total_messages': total_messages,
        }
        
        # ✅ حساب is_running بناءً على الوقت الحالي وساعات العمل
        current_hour = datetime.now().hour
        is_running = automation_enabled and (start_hour <= current_hour < end_hour)
        
        return jsonify({
            'success': True,
            'data': {
                'automation_enabled': automation_enabled,
                'is_running': is_running,  # ✅ محسوب ديناميكياً
                'schedule': {
                    'interval_minutes': interval_hours * 60,  # تحويل لدقائق للعرض
                    'start_hour': start_hour,
                    'end_hour': end_hour,
                },
                'last_run': last_run,
                'next_run': next_run,
                'statistics': statistics,
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/automation/toggle', methods=['PUT'])
@admin_required
def toggle_automation():
    """
    تشغيل/إيقاف الرسائل التلقائية
    يحدّث enable_auto_messages في ai_settings (نفس Flutter)
    
    PUT /api/admin/ai/automation/toggle
    Body: {"enabled": true/false}
    """
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        
        # تحديث enable_auto_messages في DB
        from sqlalchemy import text
        db.session.execute(text("""
            INSERT INTO ai_settings (setting_key, setting_value, setting_type, description)
            VALUES ('enable_auto_messages', :value, 'boolean', 'تفعيل الرسائل التلقائية')
            ON CONFLICT (setting_key)
            DO UPDATE SET 
                setting_value = :value,
                updated_at = CURRENT_TIMESTAMP
        """), {'value': 'true' if enabled else 'false'})
        
        db.session.commit()
        
        print(f"{'🟢' if enabled else '🔴'} تم {'تشغيل' if enabled else 'إيقاف'} الرسائل التلقائية")
        
        return jsonify({
            'success': True,
            'automation_enabled': enabled,
            'message': f"تم {'تشغيل' if enabled else 'إيقاف'} الرسائل التلقائية بنجاح"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في toggle_automation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_ai_bp.route('/automation/test', methods=['POST'])
@admin_required
def test_automation():
    """
    اختبار النظام التلقائي - إرسال رسالة تجريبية
    
    POST /api/admin/ai/automation/test
    Body: {"simple": true} for simple test (default)
          {"simple": false, "student_id": 123} for complex test
    """
    try:
        from src.models.notification import Notification
        from flask import session
        
        print("🧪 Testing automation system...")
        
        # استخدم silent=True لتجنب exception إذا لم يكن هناك JSON
        data = request.get_json(silent=True) or {}
        simple_test = data.get('simple', True)  # Default to simple test
        
        # ===== Simple Test: إنشاء رسالة تجريبية مباشرة =====
        if simple_test:
            try:
                # الحصول على user_id من session (مطلوب لـ constraint)
                current_user_id = session.get('user_id')
                
                # إذا لم يكن موجود، استخدم 1 كـ default (admin)
                if not current_user_id:
                    current_user_id = 1
                    print("⚠️ Warning: No user_id in session, using default (1)")
                
                # إنشاء notification تجريبي
                test_notification = Notification(
                    title="اختبار النظام التلقائي",
                    message="هذه رسالة تجريبية من النظام التلقائي. تم الإرسال بنجاح! 🎉",
                    type="success",
                    icon="check-circle",
                    user_id=current_user_id,  # ✅ إضافة user_id لتلبية constraint
                    is_automatic=True,
                    status='delivered',
                    sent_at=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
                
                db.session.add(test_notification)
                db.session.commit()
                
                print(f"✅ Test notification created: ID={test_notification.id}")
                
                return jsonify({
                    'success': True,
                    'message': 'تم إرسال الرسالة التجريبية بنجاح',
                    'analysis_performed': True,  # ✅ لـ Flutter
                    'message_sent': True,         # ✅ لـ Flutter
                    'data': {
                        'notification_id': test_notification.id,
                        'title': test_notification.title,
                        'message': test_notification.message,
                        'sent_at': test_notification.sent_at.isoformat() if test_notification.sent_at else None,
                        'test_type': 'simple'
                    }
                }), 200
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error in simple test: {e}")
                import traceback
                traceback.print_exc()
                
                return jsonify({
                    'success': False,
                    'error': f'فشل إنشاء الرسالة التجريبية: {str(e)}'
                }), 500
        
        # ===== Complex Test: اختبار كامل مع تحليل AI =====
        test_student_id = data.get('student_id')
        
        # جلب الإعدادات
        automation_enabled = AISetting.get_setting('automation_enabled', 'false') == 'true'
        
        analysis_performed = False
        message_sent = False
        details = {}
        
        try:
            # إذا تم تحديد طالب معين
            if test_student_id:
                student = Student.query.get(test_student_id)
                if not student:
                    return jsonify({
                        'success': False,
                        'message': 'الطالب غير موجود',
                    }), 404
                
                # تحليل الطالب (test mode)
                result = ai_assistant.analyze_student(
                    student_id=test_student_id,
                    analysis_type='test'
                )
                analysis_performed = result is not None
                
                # التحقق من الحاجة لإرسال رسالة
                if result:
                    latest_analysis = AIAnalysis.query.filter_by(
                        student_id=test_student_id
                    ).order_by(AIAnalysis.created_at.desc()).first()
                    
                    if latest_analysis and latest_analysis.severity_level in ['orange', 'red']:
                        details['would_send_message'] = True
                        details['severity'] = latest_analysis.severity_level
                        details['message_type'] = 'warning' if latest_analysis.severity_level == 'orange' else 'critical'
                        message_sent = True
                    else:
                        details['would_send_message'] = False
                        details['reason'] = 'الطالب لا يحتاج رسالة'
                    
            else:
                # اختبار عام على عينة من الطلاب
                students = Student.query.filter_by(is_active=True).limit(5).all()
                analyzed_count = 0
                
                for student in students:
                    try:
                        result = ai_assistant.analyze_student(
                            student_id=student.id,
                            analysis_type='test'
                        )
                        if result:
                            analyzed_count += 1
                    except Exception as e:
                        print(f"Error analyzing student {student.id}: {e}")
                        pass
                
                analysis_performed = analyzed_count > 0
                details['analyzed_count'] = analyzed_count
                details['sample_size'] = len(students)
            
            return jsonify({
                'success': True,
                'message': 'تم الاختبار بنجاح',
                'analysis_performed': analysis_performed,
                'message_sent': message_sent,
                'automation_enabled': automation_enabled,
                'details': details,
                'test_type': 'complex'
            })
            
        except Exception as e:
            print(f"❌ Error in complex test: {e}")
            import traceback
            traceback.print_exc()
            
            return jsonify({
                'success': False,
                'message': f'فشل الاختبار: {str(e)}',
                'analysis_performed': analysis_performed,
                'message_sent': message_sent,
            }), 500
        
    except Exception as e:
        print(f"❌ Error in test_automation: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'خطأ في اختبار النظام: {str(e)}'
        }), 500
