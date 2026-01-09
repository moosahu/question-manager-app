
from flask import redirect, url_for, request, flash
from flask_login import login_required, current_user
from models.notification_model import Notification
from extensions import db

# داخل blueprint home

@home_bp.route('/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({Notification.is_read: True})
    db.session.commit()
    flash("تم تحديد كل الإشعارات كمقروءة", "success")
    return redirect(request.referrer or url_for('home.index'))
