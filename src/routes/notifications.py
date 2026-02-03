"""
مسارات الإشعارات المحسنة مع وظائف القراءة والحذف
إصلاح شامل لجميع مشاكل الأزرار والمسارات
✅ تحديث: عرض إشعارات الأدمن في صفحة الإشعارات
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
                    # ✅ التحقق من نوع المستخدم (أدمن أم طالب)
                    if current_user.is_admin:
                        # ✅ للأدمن: عرض جميع الإشعارات الخاصة به
                        try:
                            # جلب جميع إشعارات الأدمن بدون فلترة معقدة
                            notifications = Notification.query.filter(
                                Notification.user_id == user_id
                            ).order_by(Notification.created_at.desc()).all()
                            
                            current_app.logger.info(f"✅ تم تحميل {len(notifications)} إشعار للأدمن (user_id={user_id})")
                            
                        except Exception as e:
                            current_app.logger.error(f"❌ خطأ في تحميل إشعارات الأدمن: {e}")
                            current_app.logger.error(traceback.format_exc())
                            notifications = []
                    else:
                        # للطالب: جلب الإشعارات المرتبطة بالطالب فقط
                        try:
                            from src.models.notification import StudentNotification
                            student_notifications = StudentNotification.get_student_notifications(
                                user_id, 
                                unread_only=False, 
                                limit=50
                            )
                            # تحويل StudentNotification objects إلى Notification objects
                            notifications = [sn.notification for sn in student_notifications if sn.notification]

                            # إزالة المكررات (للأمان)
                            seen = set()
                            unique_notifications = []
                            for notif in notifications:
                                if notif.id not in seen:
                                    seen.add(notif.id)
                                    unique_notifications.append(notif)
                            notifications = unique_notifications
                        except Exception as e:
                            current_app.logger.error(f"Error loading StudentNotifications: {e}")
                            # fallback: استخدام get_recent_notifications
                            try:
                                notifications = Notification.get_recent_notifications(student_id=user_id, limit=50)
                            except:
                                notifications = []
                    
                    # حساب عدد الإشعارات غير المقروءة
                    if current_user.is_admin:
                        # للأدمن: حساب الإشعارات الإدارية غير المقروءة
                        unread_count = Notification.query.filter(
                            (Notification.user_id == user_id) & 
                            (Notification.is_read == False)
                        ).count()
                    else:
                        # للطالب
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
                    # ✅ للأدمن: جلب الإشعارات الإدارية
                    if current_user.is_admin:
                        query = Notification.query.filter(
                            (Notification.user_id == user_id) | 
                            (Notification.created_by_admin == True)
                        )
                        
                        if filter_type == 'unread':
                            query = query.filter(Notification.is_read == False)
                        elif filter_type == 'read':
                            query = query.filter(Notification.is_read == True)
                        
                        notifications = query.order_by(Notification.created_at.desc()).limit(per_page).all()
                        total = query.count()
                        unread_count = Notification.query.filter(
                            (Notification.user_id == user_id) & 
                            (Notification.is_read == False)
                        ).count()
                    else:
                        # للطالب
                        if filter_type == 'unread':
                            notifications = Notification.get_user_notifications(user_id, limit=per_page, unread_only=True)
                        elif filter_type == 'read':
                            notifications = Notification.get_user_notifications(user_id, limit=per_page, read_only=True)
                        else:
                            notifications = Notification.get_user_notifications(user_id, limit=per_page)
                        
                        total = len(notifications)
                        unread_count = Notification.get_unread_count(user_id)
                else:
                    notifications = Notification.get_all_notifications(limit=per_page)
                    total = len(notifications)
                    unread_count = 0
                
                notifications_data = []
                for notif in notifications:
                    notifications_data.append({
                        'id': notif.id,
                        'title': notif.title if hasattr(notif, 'title') else '',
                        'message': notif.message if hasattr(notif, 'message') else notif.content if hasattr(notif, 'content') else '',
                        'content': notif.content if hasattr(notif, 'content') else notif.message if hasattr(notif, 'message') else '',
                        'is_read': notif.is_read if hasattr(notif, 'is_read') else False,
                        'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(notif, 'created_at') and notif.created_at else '',
                        'read_at': notif.read_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(notif, 'read_at') and notif.read_at else None,
                        'type': notif.type if hasattr(notif, 'type') else 'info'
                    })
                
                return jsonify({
                    'success': True,
                    'notifications': notifications_data,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'unread_count': unread_count,
                    'message': 'تم تحميل الإشعارات بنجاح'
                })
                
            except Exception as e:
                current_app.logger.error(f"Database error loading notifications: {e}")
                return jsonify({
                    'success': False,
                    'error': 'خطأ في قاعدة البيانات',
                    'message': 'حدث خطأ في تحميل الإشعارات',
                    'notifications': [],
                    'total': 0,
                    'unread_count': 0
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'نظام الإشعارات غير متاح حالياً',
                'message': 'يرجى المحاولة لاحقاً',
                'notifications': [],
                'total': 0,
                'unread_count': 0
            }), 503
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error in api_notifications: {e}")
        except:
            print(f"Error in api_notifications: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في النظام',
            'message': 'حدث خطأ غير متوقع',
            'notifications': [],
            'total': 0,
            'unread_count': 0
        }), 500

@notifications_bp.route('/api/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """تحديد إشعار كمقروء"""
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
            
            if user_id:
                # ✅ للأدمن: تحديث الإشعار مباشرة
                if current_user.is_admin:
                    notification = Notification.query.get(notification_id)
                    if notification:
                        notification.is_read = True
                        notification.read_at = datetime.now()
                        db.session.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'تم تحديد الإشعار كمقروء بنجاح'
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'الإشعار غير موجود'
                        }), 404
                else:
                    # للطالب: استخدام الدالة الموجودة
                    result = Notification.mark_as_read(notification_id, user_id)
                    
                    if result:
                        return jsonify({
                            'success': True,
                            'message': 'تم تحديد الإشعار كمقروء بنجاح'
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'فشل في تحديث الإشعار',
                            'message': 'حدث خطأ أثناء تحديث الإشعار'
                        }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'المستخدم غير مصرح له',
                    'message': 'يرجى تسجيل الدخول أولاً'
                }), 401
                
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
            current_app.logger.error(f"Error marking as read: {e}")
        except:
            print(f"Error marking as read: {e}")
        return jsonify({
            'success': False,
            'error': 'خطأ في النظام',
            'message': 'حدث خطأ غير متوقع'
        }), 500

@notifications_bp.route('/api/delete/<int:notification_id>', methods=['DELETE', 'POST'])
@login_required
def delete_notification(notification_id):
    """حذف إشعار"""
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
            from src.extensions import db
            
            user_id = current_user.id if current_user.is_authenticated else None
            
            if user_id:
                notification = Notification.query.get(notification_id)
                
                if notification:
                    # ✅ للأدمن: يمكنه حذف أي إشعار
                    if current_user.is_admin or notification.user_id == user_id:
                        if notification.delete():
                            return jsonify({
                                'success': True,
                                'message': 'تم حذف الإشعار بنجاح'
                            })
                        else:
                            return jsonify({
                                'success': False,
                                'error': 'فشل في حذف الإشعار',
                                'message': 'حدث خطأ أثناء حذف الإشعار'
                            }), 500
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'ليس لديك صلاحية حذف هذا الإشعار'
                        }), 403
                else:
                    return jsonify({
                        'success': False,
                        'error': 'الإشعار غير موجود'
                    }), 404
            else:
                return jsonify({
                    'success': False,
                    'error': 'المستخدم غير مصرح له',
                    'message': 'يرجى تسجيل الدخول أولاً'
                }), 401
                
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
def mark_all_as_read():
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
            from src.extensions import db
            
            user_id = current_user.id if current_user.is_authenticated else None
            
            # ✅ للأدمن: تحديث جميع إشعاراته
            if current_user.is_admin:
                count = Notification.query.filter(
                    (Notification.user_id == user_id) & 
                    (Notification.is_read == False)
                ).update({'is_read': True, 'read_at': datetime.now()})
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'تم تحديد {count} إشعار كمقروء بنجاح',
                    'count': count
                })
            else:
                # للطالب
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
                # ✅ للأدمن: يمكنه حذف أي إشعار
                if notification and (current_user.is_admin or notification.user_id == current_user.id):
                    if notification.delete():
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


# ==================== عرض تفاصيل الإشعار وإحصائيات القراءة (في notifications blueprint) ====================
@notifications_bp.route('/api/admin/notification/<int:notification_id>/read-stats', methods=['GET'])
@login_required
def get_notification_read_stats(notification_id):
    """
    جلب تفاصيل الإشعار وإحصائيات القراءة
    يعرض الطلاب الذين قرأوا والذين لم يقرأوا الإشعار
    """
    try:
        from flask import current_app
        
        if not notifications_model_available:
            return jsonify({
                'success': False,
                'error': 'نظام الإشعارات غير متاح حالياً'
            }), 503
        
        try:
            from src.models.notification import Notification, StudentNotification
            from src.models.student import Student
            
            # جلب الإشعار
            notification = Notification.query.get(notification_id)
            if not notification:
                return jsonify({
                    'success': False,
                    'error': 'الإشعار غير موجود'
                }), 404
            
            # جلب جميع الطلاب النشطين
            all_students = Student.query.filter_by(is_active=True).all()
            
            # جلب الطلاب الذين قرأوا الإشعار
            read_students = []
            unread_students = []
            
            for student in all_students:
                # البحث عن StudentNotification
                student_notif = StudentNotification.query.filter_by(
                    student_id=student.id,
                    notification_id=notification_id
                ).first()
                
                if student_notif and student_notif.is_read:
                    read_students.append({
                        'id': student.id,
                        'name': student.name,
                        'username': student.username,
                        'read_at': student_notif.read_at.isoformat() if student_notif.read_at else None
                    })
                else:
                    unread_students.append({
                        'id': student.id,
                        'name': student.name,
                        'username': student.username
                    })
            
            # حساب الإحصائيات
            total_students = len(all_students)
            read_count = len(read_students)
            unread_count = len(unread_students)
            
            current_app.logger.info(f"Loaded read stats for notification {notification_id}: {read_count} read, {unread_count} unread")
            
            return jsonify({
                'success': True,
                'notification': {
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message or notification.content,
                    'created_at': notification.created_at.isoformat() if notification.created_at else None
                },
                'stats': {
                    'total_students': total_students,
                    'read_count': read_count,
                    'unread_count': unread_count,
                    'read_percentage': round((read_count / total_students * 100) if total_students > 0 else 0, 2)
                },
                'read_students': read_students,
                'unread_students': unread_students
            }), 200
            
        except Exception as e:
            current_app.logger.error(f"Database error loading read stats: {e}")
            current_app.logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f'خطأ في جلب البيانات: {str(e)}'
            }), 500
    
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error in get_notification_read_stats: {e}")
        except:
            print(f"Error in get_notification_read_stats: {e}")
        
        return jsonify({
            'success': False,
            'error': 'حدث خطأ في النظام'
        }), 500
