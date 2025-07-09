"""
Enhanced Backup APIs
APIs النسخ الاحتياطي المحسنة مع دعم Google Drive والجدولة التلقائية
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إنشاء Blueprint
backup_api_bp = Blueprint('backup_api', __name__, url_prefix='/api/v1/backup')

# استيراد الوحدات المطلوبة
try:
    from src.models.google_drive import (
        get_authorization_url,
        handle_oauth_callback,
        disconnect_user,
        get_connection_status,
        upload_backup,
        list_user_backups,
        delete_backup_file
    )
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    try:
        from models.google_drive import (
            get_authorization_url,
            handle_oauth_callback,
            disconnect_user,
            get_connection_status,
            upload_backup,
            list_user_backups,
            delete_backup_file
        )
        GOOGLE_DRIVE_AVAILABLE = True
    except ImportError:
        logger.warning("Google Drive module not available")
        GOOGLE_DRIVE_AVAILABLE = False

try:
    from backup_scheduler_fixed import (
        schedule_user_backup,
        remove_user_backup_schedule,
        trigger_immediate_backup,
        get_scheduled_backup_jobs,
        get_scheduler_status
    )
    SCHEDULER_AVAILABLE = True
except ImportError:
    try:
        from backup_scheduler import (
            schedule_user_backup,
            remove_user_backup_schedule,
            trigger_immediate_backup,
            get_scheduled_backup_jobs
        )
        SCHEDULER_AVAILABLE = True
    except ImportError:
        logger.warning("Backup scheduler not available")
        SCHEDULER_AVAILABLE = False

try:
    from backup_logic import perform_backup_for_user, create_backup_data
    BACKUP_LOGIC_AVAILABLE = True
except ImportError:
    logger.warning("Backup logic not available")
    BACKUP_LOGIC_AVAILABLE = False

@backup_api_bp.route('/status', methods=['GET'])
@login_required
def get_backup_status():
    """الحصول على حالة النسخ الاحتياطي الشاملة"""
    try:
        user_id = current_user.id
        status = {
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'scheduler': {
                'available': SCHEDULER_AVAILABLE,
                'running': False,
                'jobs_count': 0,
                'user_scheduled': False,
                'next_backup': None
            },
            'google_drive': {
                'available': GOOGLE_DRIVE_AVAILABLE,
                'connected': False,
                'last_backup': None,
                'backup_count': 0
            },
            'backup_logic': {
                'available': BACKUP_LOGIC_AVAILABLE
            }
        }
        
        # حالة الجدولة
        if SCHEDULER_AVAILABLE:
            try:
                scheduler_status = get_scheduler_status()
                status['scheduler']['running'] = scheduler_status.get('is_running', False)
                status['scheduler']['jobs_count'] = scheduler_status.get('jobs_count', 0)
                
                # البحث عن مهمة المستخدم الحالي
                jobs = get_scheduled_backup_jobs()
                user_job = next((job for job in jobs if job.get('user_id') == user_id), None)
                
                if user_job:
                    status['scheduler']['user_scheduled'] = True
                    status['scheduler']['next_backup'] = user_job.get('next_run')
                    
            except Exception as e:
                logger.error(f"Error getting scheduler status: {e}")
        
        # حالة Google Drive
        if GOOGLE_DRIVE_AVAILABLE:
            try:
                drive_status = get_connection_status(user_id)
                status['google_drive'].update({
                    'connected': drive_status.get('connected', False),
                    'last_backup': drive_status.get('last_backup'),
                    'backup_count': drive_status.get('backup_count', 0),
                    'message': drive_status.get('message', '')
                })
            except Exception as e:
                logger.error(f"Error getting Google Drive status: {e}")
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting backup status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/enable', methods=['POST'])
@login_required
def enable_auto_backup():
    """تفعيل النسخ الاحتياطي التلقائي"""
    try:
        user_id = current_user.id
        data = request.get_json() or {}
        
        # إعدادات النسخ الاحتياطي
        backup_settings = {
            'auto_backup_enabled': True,
            'backup_frequency': data.get('frequency', 'daily'),
            'backup_time': data.get('time', '02:00'),
            'backup_destination': data.get('destination', 'local')
        }
        
        # التحقق من توفر الجدولة
        if not SCHEDULER_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'نظام الجدولة غير متوفر'
            }), 503
        
        # جدولة النسخ الاحتياطي
        success = schedule_user_backup(user_id, backup_settings)
        
        if success:
            logger.info(f"Auto backup enabled for user {user_id}")
            return jsonify({
                'success': True,
                'message': 'تم تفعيل النسخ الاحتياطي التلقائي بنجاح',
                'settings': backup_settings
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في تفعيل النسخ الاحتياطي التلقائي'
            }), 500
            
    except Exception as e:
        logger.error(f"Error enabling auto backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/disable', methods=['POST'])
@login_required
def disable_auto_backup():
    """تعطيل النسخ الاحتياطي التلقائي"""
    try:
        user_id = current_user.id
        
        if not SCHEDULER_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'نظام الجدولة غير متوفر'
            }), 503
        
        # إزالة جدولة النسخ الاحتياطي
        success = remove_user_backup_schedule(user_id)
        
        if success:
            logger.info(f"Auto backup disabled for user {user_id}")
            return jsonify({
                'success': True,
                'message': 'تم تعطيل النسخ الاحتياطي التلقائي'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في تعطيل النسخ الاحتياطي التلقائي'
            }), 500
            
    except Exception as e:
        logger.error(f"Error disabling auto backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/immediate', methods=['POST'])
@login_required
def create_immediate_backup():
    """إنشاء نسخة احتياطية فورية"""
    try:
        user_id = current_user.id
        
        if SCHEDULER_AVAILABLE:
            # استخدام الجدولة للنسخ الفوري
            success = trigger_immediate_backup(user_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'تم بدء النسخ الاحتياطي الفوري'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'فشل في بدء النسخ الاحتياطي الفوري'
                }), 500
        
        elif BACKUP_LOGIC_AVAILABLE:
            # تنفيذ النسخ الاحتياطي مباشرة
            try:
                perform_backup_for_user(user_id)
                return jsonify({
                    'success': True,
                    'message': 'تم إنشاء النسخة الاحتياطية بنجاح'
                })
            except Exception as e:
                logger.error(f"Direct backup failed: {e}")
                return jsonify({
                    'success': False,
                    'error': f'فشل في إنشاء النسخة الاحتياطية: {str(e)}'
                }), 500
        
        else:
            return jsonify({
                'success': False,
                'error': 'نظام النسخ الاحتياطي غير متوفر'
            }), 503
            
    except Exception as e:
        logger.error(f"Error creating immediate backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/google-drive/connect', methods=['GET'])
@login_required
def connect_google_drive():
    """الحصول على رابط ربط Google Drive"""
    try:
        user_id = current_user.id
        
        if not GOOGLE_DRIVE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'خدمة Google Drive غير متوفرة'
            }), 503
        
        auth_url = get_authorization_url(user_id)
        
        if auth_url:
            return jsonify({
                'success': True,
                'auth_url': auth_url,
                'message': 'يرجى زيارة الرابط لربط Google Drive'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في إنشاء رابط التفويض'
            }), 500
            
    except Exception as e:
        logger.error(f"Error connecting Google Drive: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/google-drive/callback', methods=['POST'])
@login_required
def google_drive_callback():
    """معالجة callback من Google Drive"""
    try:
        user_id = current_user.id
        data = request.get_json() or {}
        authorization_code = data.get('code')
        
        if not authorization_code:
            return jsonify({
                'success': False,
                'error': 'رمز التفويض مطلوب'
            }), 400
        
        if not GOOGLE_DRIVE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'خدمة Google Drive غير متوفرة'
            }), 503
        
        success = handle_oauth_callback(user_id, authorization_code)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'تم ربط Google Drive بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في ربط Google Drive'
            }), 500
            
    except Exception as e:
        logger.error(f"Error handling Google Drive callback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/google-drive/disconnect', methods=['POST'])
@login_required
def disconnect_google_drive():
    """قطع اتصال Google Drive"""
    try:
        user_id = current_user.id
        
        if not GOOGLE_DRIVE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'خدمة Google Drive غير متوفرة'
            }), 503
        
        success = disconnect_user(user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'تم قطع اتصال Google Drive'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في قطع اتصال Google Drive'
            }), 500
            
    except Exception as e:
        logger.error(f"Error disconnecting Google Drive: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/google-drive/status', methods=['GET'])
@login_required
def google_drive_status():
    """الحصول على حالة Google Drive"""
    try:
        user_id = current_user.id
        
        if not GOOGLE_DRIVE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'خدمة Google Drive غير متوفرة'
            }), 503
        
        status = get_connection_status(user_id)
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting Google Drive status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/google-drive/backups', methods=['GET'])
@login_required
def list_google_drive_backups():
    """قائمة النسخ الاحتياطية في Google Drive"""
    try:
        user_id = current_user.id
        
        if not GOOGLE_DRIVE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'خدمة Google Drive غير متوفرة'
            }), 503
        
        backups = list_user_backups(user_id)
        
        return jsonify({
            'success': True,
            'backups': backups,
            'count': len(backups)
        })
        
    except Exception as e:
        logger.error(f"Error listing Google Drive backups: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/google-drive/backups/<file_id>', methods=['DELETE'])
@login_required
def delete_google_drive_backup(file_id):
    """حذف نسخة احتياطية من Google Drive"""
    try:
        user_id = current_user.id
        
        if not GOOGLE_DRIVE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'خدمة Google Drive غير متوفرة'
            }), 503
        
        success = delete_backup_file(user_id, file_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'تم حذف النسخة الاحتياطية'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في حذف النسخة الاحتياطية'
            }), 500
            
    except Exception as e:
        logger.error(f"Error deleting Google Drive backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/settings', methods=['GET'])
@login_required
def get_backup_settings():
    """الحصول على إعدادات النسخ الاحتياطي"""
    try:
        user_id = current_user.id
        
        # إعدادات افتراضية
        settings = {
            'auto_backup_enabled': False,
            'backup_frequency': 'daily',
            'backup_time': '02:00',
            'backup_destination': 'local',
            'max_backups': 5,
            'notifications_enabled': True
        }
        
        # محاولة الحصول على الإعدادات الفعلية
        if SCHEDULER_AVAILABLE:
            try:
                jobs = get_scheduled_backup_jobs()
                user_job = next((job for job in jobs if job.get('user_id') == user_id), None)
                
                if user_job:
                    settings.update({
                        'auto_backup_enabled': True,
                        'backup_frequency': user_job.get('frequency', 'daily'),
                        'backup_time': user_job.get('time', '02:00'),
                        'backup_destination': user_job.get('destination', 'local')
                    })
            except Exception as e:
                logger.error(f"Error getting user job settings: {e}")
        
        return jsonify({
            'success': True,
            'settings': settings
        })
        
    except Exception as e:
        logger.error(f"Error getting backup settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/settings', methods=['POST'])
@login_required
def update_backup_settings():
    """تحديث إعدادات النسخ الاحتياطي"""
    try:
        user_id = current_user.id
        data = request.get_json() or {}
        
        # التحقق من صحة البيانات
        frequency = data.get('backup_frequency', 'daily')
        if frequency not in ['daily', 'weekly', 'monthly']:
            return jsonify({
                'success': False,
                'error': 'تكرار النسخ غير صحيح'
            }), 400
        
        backup_time = data.get('backup_time', '02:00')
        try:
            # التحقق من صحة الوقت
            datetime.strptime(backup_time, '%H:%M')
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'صيغة الوقت غير صحيحة'
            }), 400
        
        # إعدادات النسخ الاحتياطي
        backup_settings = {
            'auto_backup_enabled': data.get('auto_backup_enabled', False),
            'backup_frequency': frequency,
            'backup_time': backup_time,
            'backup_destination': data.get('backup_destination', 'local')
        }
        
        if not SCHEDULER_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'نظام الجدولة غير متوفر'
            }), 503
        
        # تحديث الجدولة
        if backup_settings['auto_backup_enabled']:
            success = schedule_user_backup(user_id, backup_settings)
        else:
            success = remove_user_backup_schedule(user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'تم تحديث إعدادات النسخ الاحتياطي',
                'settings': backup_settings
            })
        else:
            return jsonify({
                'success': False,
                'error': 'فشل في تحديث إعدادات النسخ الاحتياطي'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating backup settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@backup_api_bp.route('/test', methods=['POST'])
@login_required
def test_backup_system():
    """اختبار نظام النسخ الاحتياطي"""
    try:
        user_id = current_user.id
        
        test_results = {
            'scheduler': {
                'available': SCHEDULER_AVAILABLE,
                'status': 'غير متوفر'
            },
            'google_drive': {
                'available': GOOGLE_DRIVE_AVAILABLE,
                'status': 'غير متوفر'
            },
            'backup_logic': {
                'available': BACKUP_LOGIC_AVAILABLE,
                'status': 'غير متوفر'
            }
        }
        
        # اختبار الجدولة
        if SCHEDULER_AVAILABLE:
            try:
                status = get_scheduler_status()
                test_results['scheduler']['status'] = 'يعمل' if status.get('is_running') else 'متوقف'
            except Exception as e:
                test_results['scheduler']['status'] = f'خطأ: {str(e)}'
        
        # اختبار Google Drive
        if GOOGLE_DRIVE_AVAILABLE:
            try:
                drive_status = get_connection_status(user_id)
                test_results['google_drive']['status'] = 'متصل' if drive_status.get('connected') else 'غير متصل'
            except Exception as e:
                test_results['google_drive']['status'] = f'خطأ: {str(e)}'
        
        # اختبار منطق النسخ الاحتياطي
        if BACKUP_LOGIC_AVAILABLE:
            test_results['backup_logic']['status'] = 'متوفر'
        
        # تقييم النتائج
        all_working = (
            test_results['scheduler']['available'] and 
            test_results['backup_logic']['available']
        )
        
        return jsonify({
            'success': True,
            'test_results': test_results,
            'overall_status': 'يعمل بشكل كامل' if all_working else 'يعمل جزئياً',
            'recommendations': _get_recommendations(test_results)
        })
        
    except Exception as e:
        logger.error(f"Error testing backup system: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _get_recommendations(test_results: Dict[str, Any]) -> List[str]:
    """الحصول على توصيات بناءً على نتائج الاختبار"""
    recommendations = []
    
    if not test_results['scheduler']['available']:
        recommendations.append("تثبيت وتفعيل نظام الجدولة APScheduler")
    
    if not test_results['google_drive']['available']:
        recommendations.append("تثبيت مكتبة Google APIs لدعم Google Drive")
    
    if not test_results['backup_logic']['available']:
        recommendations.append("تثبيت وحدة منطق النسخ الاحتياطي")
    
    if test_results['google_drive']['available'] and test_results['google_drive']['status'] == 'غير متصل':
        recommendations.append("ربط حساب Google Drive لتفعيل النسخ السحابي")
    
    if not recommendations:
        recommendations.append("النظام يعمل بشكل مثالي!")
    
    return recommendations

# تسجيل Blueprint
def register_backup_apis(app):
    """تسجيل APIs النسخ الاحتياطي"""
    app.register_blueprint(backup_api_bp)
    logger.info("Backup APIs registered successfully")

