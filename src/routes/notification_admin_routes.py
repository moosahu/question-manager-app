
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.notification_model import Notification
from extensions import db

@home_bp.route('/notifications')
@login_required
def view_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications_admin.html', notifications=notifications)

@home_bp.route('/notifications', methods=['POST'])
@login_required
def bulk_notifications_action():
    ids = request.form.getlist('notif_ids')
    action = request.form.get('action')

    if not ids:
        flash("لم يتم تحديد أي إشعار.", "warning")
        return redirect(url_for('home.view_notifications'))

    if action == "mark_read":
        Notification.query.filter(Notification.id.in_(ids), Notification.user_id == current_user.id).update({Notification.is_read: True}, synchronize_session=False)
        flash("تم تحديد الإشعارات كمقروءة", "success")
    elif action == "delete":
        Notification.query.filter(Notification.id.in_(ids), Notification.user_id == current_user.id).delete(synchronize_session=False)
        flash("تم حذف الإشعارات المحددة", "success")
    else:
        flash("إجراء غير معروف", "danger")

    db.session.commit()
    return redirect(url_for('home.view_notifications'))
