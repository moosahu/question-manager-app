"""
notification_admin_routes.py

إدارة الإشعارات - واجهة ويب + API للتطبيق
✅ مع دعم badge لـ iOS + حذف الإشعارات + تعليم الكل كمقروء
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, Blueprint
from flask_login import login_required, current_user

# ✅ استخدم نفس نموذج Notification الذي يستخدمه نظام AI
from src.models.notification import Notification
from src.models.student_notification import StudentNotification

from extensions import db
from datetime import datetime
import os

# محاولة تحميل Firebase
FCM_ENABLED = False

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    import json

    # تحقق إذا Firebase مهيأ بالفعل
    try:
        firebase_admin.get_app()
        FCM_ENABLED = True
        print("✅ Firebase already initialized - Push Notifications enabled")
    except ValueError:
        # Firebase لم يتم تهيئته - حاول تهيئته من متغير البيئة
        firebase_config = os.getenv('FIREBASE_CONFIG')
        if firebase_config:
            try:
                creds_dict = json.loads(firebase_config)
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred)
                FCM_ENABLED = True
                print("✅ Firebase initialized from FIREBASE_CONFIG - Push Notifications enabled")
            except Exception as e:
                print(f"⚠️ Failed to initialize Firebase: {e}")
                FCM_ENABLED = False
        else:
            print("⚠️ FIREBASE_CONFIG environment variable not found")
            print("💡 Notifications will be saved to database only (no push notifications)")
            FCM_ENABLED = False
except ImportError:
    print("⚠️ Firebase Admin SDK not installed (pip install firebase-admin)")
    FCM_ENABLED = False

# Blueprint للـ API (للتطبيق)
api_bp = Blueprint('notifications_api', __name__, url_prefix='/api')

# =============================================================================
# واجهة الويب (للأدمن) - الكود الأصلي
# =============================================================================

@home_bp.route('/notifications')
@login_required
def view_notifications():
    """عرض الإشعارات في واجهة الويب"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    return render_template('notifications_admin.html', notifications=notifications)


@home_bp.route('/notifications', methods=['POST'])
@login_required
def bulk_notifications_action():
    """إجراءات جماعية على الإشعارات (قراءة/حذف)"""
    ids = request.form.getlist('notif_ids')
    action = request.form.get('action')

    if not ids:
        flash("لم يتم تحديد أي إشعار.", "warning")
        return redirect(url_for('home.view_notifications'))

    if action == "mark_read":
        Notification.query.filter(
            Notification.id.in_(ids),
            Notification.user_id == current_user.id
        ).update({Notification.is_read: True}, synchronize_session=False)
        flash("تم تحديد الإشعارات كمقروءة", "success")
    elif action == "delete":
        Notification.query.filter(
            Notification.id.in_(ids),
            Notification.user_id == current_user.id
        ).delete(synchronize_session=False)
        flash("تم حذف الإشعارات المحددة", "success")
    else:
        flash("إجراء غير معروف", "danger")

    db.session.commit()
    return redirect(url_for('home.view_notifications'))

# =============================================================================
# API للتطبيق (Flutter)
# =============================================================================

# ==================== إرسال إشعار (للأدمن فقط) ====================

@api_bp.route('/admin/send-notification', methods=['POST'])
@login_required
def send_notification():
    """إرسال إشعار من الأدمن إلى الطلاب"""

    # التحقق من أن المستخدم أدمن
    if not current_user.is_admin:  # عدل هذا حسب نظامك
        return jsonify({
            'success': False,
            'message': 'غير مصرح لك بإرسال الإشعارات'
        }), 403

    try:
        data = request.get_json()
        title = data.get('title')
        body = data.get('body')
        recipient_type = data.get('recipient_type', 'all')
        recipient_id = data.get('recipient_id')
        level = data.get('level')

        print("\n🔍 ========== Send Notification Request ==========")
        print(f"Title: {title}")
        print(f"Body: {body}")
        print(f"Recipient Type: {recipient_type}")
        print(f"Recipient ID: {recipient_id}")
        print(f"Level: {level}")

        if not title or not body:
            return jsonify({
                'success': False,
                'message': 'العنوان والمحتوى مطلوبان'
            }), 400

        # استيراد نموذج Student
        from models.student_model import Student  # عدل هذا حسب موقع النموذج

        student_ids_raw = data.get('student_ids', '')

        # جلب الطلاب المستهدفين
        if recipient_type == 'all':
            students = Student.query.filter_by(is_active=True).all()
        elif recipient_type == 'student_id' and recipient_id:
            students = Student.query.filter_by(id=recipient_id, is_active=True).all()
        elif recipient_type == 'level' and level:
            students = Student.query.filter_by(grade=level, is_active=True).all()
        elif recipient_type == 'multiple' and student_ids_raw:
            id_list = [int(x) for x in str(student_ids_raw).split(',') if x.strip().isdigit()]
            students = Student.query.filter(Student.id.in_(id_list), Student.is_active == True).all()
        else:
            return jsonify({
                'success': False,
                'message': 'نوع المستلم غير صحيح'
            }), 400

        if not students:
            return jsonify({
                'success': False,
                'message': 'لا يوجد طلاب مستهدفين',
                'total': 0,
                'sent_count': 0,
                'success_count': 0,
                'failed_count': 0
            }), 404

        total = len(students)
        print(f"🔍 إرسال ل{'لجميع' if recipient_type == 'all' else recipient_type}: {total} طالب")

        sent_count = 0
        success_count = 0
        failed_count = 0
        failed_tokens = []

        # إنشاء الإشعار الرئيسي (مرتبط بالأدمن)
        notification = Notification(
            title=title,
            body=body,
            user_id=current_user.id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            level=level,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.flush()  # للحصول على ID

        for student in students:
            try:
                # إضافة الإشعار للطالب في StudentNotification
                student_notification = StudentNotification(
                    notification_id=notification.id,
                    student_id=student.id,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(student_notification)
                sent_count += 1

                # إرسال Push Notification عبر FCM (إذا كان مفعل)
                if not getattr(student, 'fcm_token', None):
                    print(f"⚠️ الطالب {student.username} لا يملك FCM Token")
                    # يعتبر نجاح لأن الإشعار محفوظ في DB
                    success_count += 1
                elif FCM_ENABLED:
                    try:
                        # ✅ حساب عدد الإشعارات غير المقروءة لهذا الطالب
                        unread_count = StudentNotification.query.filter_by(
                            student_id=student.id,
                            is_read=False
                        ).count() + 1  # +1 للإشعار الجديد اللي لسه ما انحفظ

                        message = messaging.Message(
                            notification=messaging.Notification(
                                title=title,
                                body=body,
                            ),
                            token=student.fcm_token,
                            android=messaging.AndroidConfig(
                                priority='high',
                                notification=messaging.AndroidNotification(
                                    channel_id='chem_tahsili_channel',
                                    sound='default',
                                ),
                            ),
                            apns=messaging.APNSConfig(
                                payload=messaging.APNSPayload(
                                    aps=messaging.Aps(
                                        sound='default',
                                        badge=unread_count,  # ✅ عدد الإشعارات غير المقروءة على أيقونة التطبيق
                                    ),
                                ),
                            ),
                        )
                        response = messaging.send(message)
                        print(f'✅ Push notification sent to {student.username} (badge: {unread_count})')
                        success_count += 1
                    except messaging.UnregisteredError:
                        print(f'⚠️ Invalid FCM token for {student.username}')
                        failed_tokens.append(student.id)
                        success_count += 1  # الإشعار محفوظ في DB
                    except messaging.SenderIdMismatchError:
                        print(f'⚠️ Sender ID mismatch for {student.username}')
                        failed_tokens.append(student.id)
                        success_count += 1
                    except Exception as fcm_error:
                        print(f'⚠️ FCM error for {student.username}: {fcm_error}')
                        failed_count += 1
                else:
                    # FCM غير مفعل لكن الإشعار محفوظ
                    success_count += 1

            except Exception as student_error:
                print(f'❌ Error sending to student {student.id}: {student_error}')
                failed_count += 1

        # حفظ كل شيء
        db.session.commit()

        # ✅ تسجيل النشاط في سجل الأدمن
        try:
            from src.models.audit_log import AuditLog
            target_desc = {
                'all': 'جميع الطلاب',
                'student_id': f'طالب (ID: {recipient_id})',
                'level': f'مستوى {level}',
                'multiple': f'{total} طالب',
            }.get(recipient_type, recipient_type)
            AuditLog.log(
                action='send_notification',
                description=f'إرسال إشعار "{title}" إلى {target_desc} ({success_count} طالب)',
                admin_name=getattr(current_user, 'username', 'الادمن'),
                target_type='notification',
                target_id=notification.id,
            )
            db.session.commit()
        except Exception as log_err:
            print(f'⚠️ AuditLog error: {log_err}')

        # تنظيف FCM tokens غير صالحة
        if failed_tokens:
            for student_id in failed_tokens:
                student_obj = Student.query.get(student_id)
                if student_obj:
                    student_obj.fcm_token = None
            db.session.commit()

        message = f'تم إرسال {success_count} إشعار بنجاح'
        if failed_count > 0:
            message += f' ({failed_count} فشل)'

        print(f'✅ تم إرسال {success_count} إشعار بنجاح')
        if failed_count > 0:
            print(f'❌ فشل إرسال {failed_count} إشعار')
        print("========== End Send Notification Request ==========\n")

        return jsonify({
            'success': True,
            'message': message,
            'notification_id': notification.id,
            'total': total,
            'sent_count': sent_count,
            'success_count': success_count,
            'failed_count': failed_count
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f'❌ خطأ في إرسال الإشعار: {e}')
        import traceback
        traceback.print_exc()
        print("========== End Send Notification Request ==========\n")
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}'
        }), 500

# ==================== جلب الإشعارات الخاصة بالطالب ====================

@api_bp.route('/students/api/notifications/<int:student_id>', methods=['GET'])
def get_student_notifications(student_id):
    """جلب الإشعارات الخاصة بطالب معين (من StudentNotification + Notification)"""

    try:
        from models.student_model import Student

        # التحقق من وجود الطالب
        student = Student.query.get(student_id)
        if not student:
            return jsonify({
                'success': False,
                'message': 'الطالب غير موجود',
                'notifications': []
            }), 404

        print(f"\n🔍 ========== Get Notifications Request ==========")
        print(f"user_id: {student_id}")

        # جلب الإشعارات
        student_notifications = StudentNotification.query.filter_by(
            student_id=student_id
        ).join(Notification).order_by(
            Notification.created_at.desc()
        ).limit(100).all()

        notifications = []
        for sn in student_notifications:
            notifications.append({
                'id': sn.notification.id,
                'title': sn.notification.title,
                'body': sn.notification.body,
                'created_at': sn.notification.created_at.isoformat() if sn.notification.created_at else None,
                'is_read': sn.is_read,
                'read_at': sn.read_at.isoformat() if sn.read_at else None
            })

        print(f'✅ تم جلب {len(notifications)} إشعار للطالب {student_id}')
        print("========== End Get Notifications Request ==========\n")

        return jsonify({
            'success': True,
            'notifications': notifications
        }), 200

    except Exception as e:
        print(f'❌ خطأ في جلب الإشعارات: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}',
            'notifications': []
        }), 500

# ==================== تحديد الإشعار كمقروء ====================

@api_bp.route('/students/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_as_read(notification_id):
    """تحديد الإشعار كمقروء"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')

        if not student_id:
            return jsonify({
                'success': False,
                'message': 'student_id مطلوب'
            }), 400

        student_notification = StudentNotification.query.filter_by(
            notification_id=notification_id,
            student_id=student_id
        ).first()

        if not student_notification:
            return jsonify({
                'success': False,
                'message': 'الإشعار غير موجود'
            }), 404

        student_notification.is_read = True
        student_notification.read_at = datetime.utcnow()
        db.session.commit()

        print(f'✅ تم تحديد الإشعار {notification_id} كمقروء للطالب {student_id}')
        return jsonify({'success': True}), 200

    except Exception as e:
        db.session.rollback()
        print(f'❌ خطأ في تحديد الإشعار كمقروء: {e}')
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}'
        }), 500

# ==================== ✅ تعليم كل الإشعارات كمقروءة ====================

@api_bp.route('/students/api/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_as_read():
    """تعليم كل إشعارات الطالب كمقروءة دفعة واحدة"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')

        if not student_id:
            return jsonify({
                'success': False,
                'message': 'student_id مطلوب'
            }), 400

        # تحديث كل الإشعارات غير المقروءة دفعة واحدة
        updated = StudentNotification.query.filter_by(
            student_id=student_id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        }, synchronize_session=False)

        db.session.commit()

        print(f'✅ تم تعليم {updated} إشعار كمقروء للطالب {student_id}')
        return jsonify({
            'success': True,
            'updated_count': updated
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f'❌ خطأ في تعليم الكل كمقروء: {e}')
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}'
        }), 500

# ==================== ✅ حذف إشعار (للطالب) ====================

@api_bp.route('/students/api/notifications/<int:notification_id>/delete', methods=['POST'])
def delete_student_notification(notification_id):
    """حذف إشعار للطالب (يُستخدم للحذف التلقائي بعد القراءة بيومين)"""
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')

        if not student_id:
            return jsonify({
                'success': False,
                'message': 'student_id مطلوب'
            }), 400

        # حذف من StudentNotification
        student_notification = StudentNotification.query.filter_by(
            notification_id=notification_id,
            student_id=student_id
        ).first()

        if student_notification:
            db.session.delete(student_notification)

        # حذف الإشعار الأصلي إذا ما فيه طلاب ثانيين مرتبطين فيه
        notification = Notification.query.get(notification_id)
        if notification:
            other_links = StudentNotification.query.filter(
                StudentNotification.notification_id == notification_id,
                StudentNotification.student_id != student_id
            ).count()

            if other_links == 0:
                db.session.delete(notification)

        db.session.commit()
        print(f'🗑️ تم حذف الإشعار {notification_id} للطالب {student_id}')
        return jsonify({'success': True}), 200

    except Exception as e:
        db.session.rollback()
        print(f'❌ خطأ في حذف الإشعار: {e}')
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}'
        }), 500

# ==================== حفظ FCM Token ====================

@api_bp.route('/students/api/fcm-token', methods=['POST'])
def save_fcm_token():
    """حفظ FCM Token للطالب"""
    try:
        data = request.get_json()
        fcm_token = data.get('fcm_token')
        student_id = data.get('student_id')
        username = data.get('username')

        if not fcm_token:
            return jsonify({
                'success': False,
                'message': 'FCM token مطلوب'
            }), 400

        from models.student_model import Student

        # البحث عن الطالب
        if student_id:
            student = Student.query.get(student_id)
        elif username:
            student = Student.query.filter_by(username=username).first()
        else:
            return jsonify({
                'success': False,
                'message': 'student_id أو username مطلوب'
            }), 400

        if not student:
            return jsonify({
                'success': False,
                'message': 'الطالب غير موجود'
            }), 404

        # حفظ أو تحديث FCM Token
        student.fcm_token = fcm_token
        student.fcm_token_updated_at = datetime.utcnow()
        db.session.commit()

        print(f'✅ تم حفظ FCM Token للطالب {student.id}')
        return jsonify({
            'success': True,
            'message': 'تم حفظ FCM Token بنجاح'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f'❌ خطأ في حفظ FCM Token: {e}')
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}'
        }), 500

# ==================== حذف FCM Token ====================

@api_bp.route('/students/api/delete-fcm-token', methods=['POST'])
def delete_fcm_token():
    """حذف FCM Token للطالب (عند تسجيل الخروج)"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')

        if not student_id:
            return jsonify({
                'success': False,
                'message': 'student_id مطلوب'
            }), 400

        from models.student_model import Student

        student = Student.query.get(student_id)
        if student:
            student.fcm_token = None
            db.session.commit()

        print(f'✅ تم حذف FCM Token للطالب {student_id}')
        return jsonify({'success': True}), 200

    except Exception as e:
        db.session.rollback()
        print(f'❌ خطأ في حذف FCM Token: {e}')
        return jsonify({
            'success': False,
            'message': f'خطأ في الخادم: {str(e)}'
        }), 500

# ==================== ✅ نظرة عامة على الإشعارات (للأدمن) ====================

@api_bp.route('/admin/notifications/overview', methods=['GET'])
@login_required
def get_admin_notifications_overview():
    """جلب نظرة عامة على الإشعارات للأدمن"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'غير مصرح'
            }), 403

        notifications = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(
            Notification.created_at.desc()
        ).limit(50).all()

        notifications_list = []
        for n in notifications:
            # عدد الطلاب اللي وصلهم هذا الإشعار
            total_sent = StudentNotification.query.filter_by(
                notification_id=n.id
            ).count()
            total_read = StudentNotification.query.filter_by(
                notification_id=n.id,
                is_read=True
            ).count()

            notifications_list.append({
                'id': n.id,
                'title': n.title,
                'body': n.body,
                'created_at': n.created_at.isoformat() if n.created_at else None,
                'recipient_type': n.recipient_type,
                'total_sent': total_sent,
                'total_read': total_read,
            })

        return jsonify({
            'success': True,
            'notifications': notifications_list,
            'stats': {
                'total': len(notifications_list),
            }
        }), 200

    except Exception as e:
        print(f'❌ خطأ في جلب إشعارات Admin: {e}')
        return jsonify({
            'success': False,
            'message': f'خطأ: {str(e)}',
            'notifications': []
        }), 500

# =============================================================================
# تسجيل Blueprint في app.py
# =============================================================================
"""
في app.py أو __init__.py:

from routes.notification_admin_routes import api_bp
app.register_blueprint(api_bp)
"""
