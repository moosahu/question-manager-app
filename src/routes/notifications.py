"""
مسارات الإشعارات المحسنة مع وظائف القراءة والحذف
إصلاح شامل لجميع مشاكل الأزرار والمسارات
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import traceback

# إنشاء البلوبرينت
notifications_bp = Blueprint('notifications', __name__, template_folder='../templates')

# متغيرات للتحقق من توفر المكونات
notifications_model_available = False

def init_notifications():
    """تهيئة نظام الإشعارات مع التحقق من توفر المكونات"""
    global notifications_model_available
    
    try:
        from flask import has_app_context, current_app
        
        if not has_app_context():
            print("Warning: No app context available for notifications init")
            return
        
        # محاولة استيراد النموذج المتوافق
        try:
            from src.models.notification import Notification
            notifications_model_available = True
            current_app.logger.info("Compatible notification model loaded successfully")
        except ImportError:
            try:
                from models.notification import Notification
                notifications_model_available = True
                current_app.logger.info("Compatible notification model loaded successfully (fallback)")
            except ImportError:
                current_app.logger.warning("Notification model not available")
                
    except Exception as e:
        print(f"Error initializing notifications: {e}")

@notifications_bp.route('/')
@login_required
def index():
    """صفحة الإشعارات الرئيسية مع معالجة أخطاء قاعدة البيانات"""
    try:
        from flask import current_app
        
        notifications = []
        unread_count = 0
        total_count = 0
        error_message = None
        
        if notifications_model_available:
            try:
                from src.models.notification import Notification
                
                # الحصول على إشعارات المستخدم الحالي
                user_id = current_user.id if current_user.is_authenticated else None
                
                if user_id:
                    notifications = Notification.get_user_notifications(user_id, limit=50)
                    unread_count = Notification.get_unread_count(user_id)
                else:
                    # إذا لم يكن هناك مستخدم، نحصل على الإشعارات العامة
                    notifications = Notification.get_all_notifications(limit=50)
                    unread_count = Notification.get_unread_count()
                
                total_count = len(notifications)
                
                current_app.logger.info(f"Loaded {total_count} notifications for user {user_id}")
                
            except Exception as e:
                current_app.logger.error(f"Database error loading notifications: {e}")
                current_app.logger.error(traceback.format_exc())
                error_message = "حدث خطأ في تحميل الإشعارات من قاعدة البيانات"
                
                # إنشاء إشعارات تجريبية في حالة الخطأ
                notifications = create_sample_notifications()
                unread_count = 2
                total_count = len(notifications)
        else:
            # إذا لم يكن النموذج متاحاً، نستخدم إشعارات تجريبية
            notifications = create_sample_notifications()
            unread_count = 2
            total_count = len(notifications)
            error_message = "نظام الإشعارات في وضع التجريب"
        
        return render_template('notifications.html', 
                             notifications=notifications,
                             unread_count=unread_count,
                             total_count=total_count,
                             error=error_message)
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error in notifications index: {e}")
            current_app.logger.error(traceback.format_exc())
        except:
            print(f"Error in notifications index: {e}")
        
        # في حالة الخطأ الشديد، نعرض صفحة بسيطة
        return render_template('notifications.html', 
                             notifications=[],
                             unread_count=0,
                             total_count=0,
                             error="حدث خطأ في تحميل صفحة الإشعارات")

def create_sample_notifications():
    """إنشاء إشعارات تجريبية للعرض"""
    sample_notifications = []
    
    # إشعار ترحيبي
    sample_notifications.append({
        'id': 1,
        'title': 'مرحباً بك في نظام الإشعارات',
        'message': 'تم تفعيل نظام الإشعارات بنجاح. ستتلقى إشعارات حول جميع الأنشطة المهمة.',
        'content': 'تم تفعيل نظام الإشعارات بنجاح. ستتلقى إشعارات حول جميع الأنشطة المهمة.',
        'user_id': None,
        'is_read': False,
        'created_at': datetime.now(),
        'read_at': None,
        'type': 'success'
    })
    
    # إشعار معلوماتي
    sample_notifications.append({
        'id': 2,
        'title': 'نظام الإشعارات جاهز',
        'message': 'يمكنك الآن متابعة جميع الأنشطة والتحديثات من خلال صفحة الإشعارات.',
        'content': 'يمكنك الآن متابعة جميع الأنشطة والتحديثات من خلال صفحة الإشعارات.',
        'user_id': None,
        'is_read': False,
        'created_at': datetime.now(),
        'read_at': None,
        'type': 'info'
    })
    
    # إشعار تحديث
    sample_notifications.append({
        'id': 3,
        'title': 'تحديث النظام',
        'message': 'تم تحديث نظام إدارة الأسئلة الكيميائية بميزات جديدة.',
        'content': 'تم تحديث نظام إدارة الأسئلة الكيميائية بميزات جديدة.',
        'user_id': None,
        'is_read': True,
        'created_at': datetime.now(),
        'read_at': datetime.now(),
        'type': 'info'
    })
    
    return sample_notifications

@notifications_bp.route('/api/notifications')
@login_required
def api_notifications():
    """API للحصول على الإشعارات مع معالجة أخطاء قاعدة البيانات"""
    try:
        from flask import current_app
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        filter_type = request.args.get('filter', 'all')  # all, unread, read
        
        notifications = []
        total = 0
        unread_count = 0
        
        if notifications_model_available:
            try:
                from src.models.notification import Notification
                
                user_id = current_user.id if current_user.is_authenticated else None
                
                if user_id:
                    if filter_type == 'unread':
                        notifications = Notification.get_user_notifications(user_id, limit=per_page, unread_only=True)
                    elif filter_type == 'read':
                        all_notifications = Notification.get_user_notifications(user_id, limit=100)
                        notifications = [n for n in all_notifications if n.is_read][:per_page]
                    else:
                        notifications = Notification.get_user_notifications(user_id, limit=per_page)
                    
                    unread_count = Notification.get_unread_count(user_id)
                else:
                    notifications = Notification.get_all_notifications(limit=per_page, filter_type=filter_type)
                    unread_count = Notification.get_unread_count()
                
                total = len(notifications)
                notifications_data = [n.to_dict() for n in notifications]
                
            except Exception as e:
                current_app.logger.error(f"Database error in API: {e}")
                # استخدام البيانات التجريبية في حالة الخطأ
                sample_notifications = create_sample_notifications()
                
                if filter_type == 'unread':
                    notifications_data = [n for n in sample_notifications if not n['is_read']]
                elif filter_type == 'read':
                    notifications_data = [n for n in sample_notifications if n['is_read']]
                else:
                    notifications_data = sample_notifications
                
                total = len(notifications_data)
                unread_count = len([n for n in sample_notifications if not n['is_read']])
        else:
            # استخدام البيانات التجريبية
            sample_notifications = create_sample_notifications()
            
            if filter_type == 'unread':
                notifications_data = [n for n in sample_notifications if not n['is_read']]
            elif filter_type == 'read':
                notifications_data = [n for n in sample_notifications if n['is_read']]
            else:
                notifications_data = sample_notifications
            
            total = len(notifications_data)
            unread_count = len([n for n in sample_notifications if not n['is_read']])
        
        return jsonify({
            'notifications': notifications_data,
            'total': total,
            'unread_count': unread_count,
            'page': page,
            'per_page': per_page,
            'total_pages': max(1, (total + per_page - 1) // per_page)
        })
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error in api_notifications: {e}")
        except:
            print(f"Error in api_notifications: {e}")
        return jsonify({'error': 'حدث خطأ في تحميل الإشعارات'}), 500

@notifications_bp.route('/api/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_read(notification_id):
    """تحديد إشعار كمقروء مع معالجة أخطاء قاعدة البيانات"""
    try:
        from flask import current_app
        
        if not notifications_model_available:
            return jsonify({
                'success': False,
                'error': 'نظام الإشعارات غير متاح حالياً',
                'message': 'يرجى المحاولة لاحقاً'
            }), 503
        
        try:
            from src.models.notification import Notification
            notification = Notification.query.get(notification_id)
            
            if not notification:
                return jsonify({
                    'success': False,
                    'error': 'الإشعار غير موجود',
                    'message': 'لم يتم العثور على الإشعار المطلوب'
                }), 404
            
            if notification.mark_as_read():
                return jsonify({
                    'success': True,
                    'message': 'تم تحديد الإشعار كمقروء بنجاح',
                    'notification_id': notification_id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'فشل في تحديث الإشعار',
                    'message': 'حدث خطأ أثناء تحديث حالة الإشعار'
                }), 500
                
        except Exception as e:
            current_app.logger.error(f"Database error marking as read: {e}")
            return jsonify({
                'success': False,
                'error': 'خطأ في قاعدة البيانات',
                'message': 'حدث خطأ في الاتصال بقاعدة البيانات'
            }), 500
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error marking notification as read: {e}")
        except:
            print(f"Error marking notification as read: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في النظام',
            'message': 'حدث خطأ غير متوقع'
        }), 500

@notifications_bp.route('/api/delete/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """حذف إشعار واحد"""
    try:
        from flask import current_app
        
        if not notifications_model_available:
            return jsonify({
                'success': False,
                'error': 'نظام الإشعارات غير متاح حالياً',
                'message': 'يرجى المحاولة لاحقاً'
            }), 503
        
        try:
            from src.models.notification import Notification
            notification = Notification.query.get(notification_id)
            
            if not notification:
                return jsonify({
                    'success': False,
                    'error': 'الإشعار غير موجود',
                    'message': 'لم يتم العثور على الإشعار المطلوب'
                }), 404
            
            if notification.delete():
                return jsonify({
                    'success': True,
                    'message': 'تم حذف الإشعار بنجاح',
                    'notification_id': notification_id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'فشل في حذف الإشعار',
                    'message': 'حدث خطأ أثناء حذف الإشعار'
                }), 500
                
        except Exception as e:
            current_app.logger.error(f"Database error deleting notification: {e}")
            return jsonify({
                'success': False,
                'error': 'خطأ في قاعدة البيانات',
                'message': 'حدث خطأ في الاتصال بقاعدة البيانات'
            }), 500
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error deleting notification: {e}")
        except:
            print(f"Error deleting notification: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في النظام',
            'message': 'حدث خطأ غير متوقع'
        }), 500

@notifications_bp.route('/api/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """تحديد جميع الإشعارات كمقروءة"""
    try:
        from flask import current_app
        
        if not notifications_model_available:
            return jsonify({
                'success': False,
                'error': 'نظام الإشعارات غير متاح حالياً',
                'message': 'يرجى المحاولة لاحقاً'
            }), 503
        
        try:
            from src.models.notification import Notification
            
            user_id = current_user.id if current_user.is_authenticated else None
            count = Notification.mark_all_as_read(user_id)
            
            if count is not False:
                return jsonify({
                    'success': True,
                    'message': f'تم تحديد {count} إشعار كمقروء بنجاح',
                    'count': count
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'فشل في تحديث الإشعارات',
                    'message': 'حدث خطأ أثناء تحديث الإشعارات'
                }), 500
                
        except Exception as e:
            current_app.logger.error(f"Database error marking all as read: {e}")
            return jsonify({
                'success': False,
                'error': 'خطأ في قاعدة البيانات',
                'message': 'حدث خطأ في الاتصال بقاعدة البيانات'
            }), 500
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error marking all as read: {e}")
        except:
            print(f"Error marking all as read: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في النظام',
            'message': 'حدث خطأ غير متوقع'
        }), 500

@notifications_bp.route('/api/delete-multiple', methods=['POST'])
@login_required
def delete_multiple():
    """حذف إشعارات متعددة"""
    try:
        from flask import current_app
        
        if not notifications_model_available:
            return jsonify({
                'success': False,
                'error': 'نظام الإشعارات غير متاح حالياً',
                'message': 'يرجى المحاولة لاحقاً'
            }), 503
        
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if not notification_ids:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد إشعارات للحذف',
                'message': 'يرجى تحديد إشعار واحد على الأقل'
            }), 400
        
        try:
            from src.models.notification import Notification
            
            deleted_count = 0
            for notification_id in notification_ids:
                notification = Notification.query.get(notification_id)
                if notification and notification.delete():
                    deleted_count += 1
            
            return jsonify({
                'success': True,
                'message': f'تم حذف {deleted_count} إشعار بنجاح',
                'deleted_count': deleted_count,
                'total_requested': len(notification_ids)
            })
                
        except Exception as e:
            current_app.logger.error(f"Database error deleting multiple: {e}")
            return jsonify({
                'success': False,
                'error': 'خطأ في قاعدة البيانات',
                'message': 'حدث خطأ في الاتصال بقاعدة البيانات'
            }), 500
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error deleting multiple notifications: {e}")
        except:
            print(f"Error deleting multiple notifications: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في النظام',
            'message': 'حدث خطأ غير متوقع'
        }), 500

# تهيئة النظام عند تحميل البلوبرينت
try:
    init_notifications()
except Exception as e:
    print(f"Error during notifications blueprint initialization: {e}")

