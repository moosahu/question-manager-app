
from flask import redirect, url_for, flash
from flask_login import login_required, current_user
from models.notification_model import Notification
from extensions import db

# داخل Blueprint مثلاً home_bp
@home_bp.route('/notify-test')
@login_required
def notify_test():
    notif = Notification(user_id=current_user.id, content="🔔 هذا إشعار تجريبي!")
    db.session.add(notif)
    db.session.commit()
    flash("تم إنشاء إشعار تجريبي بنجاح", "success")
    return redirect(url_for('home.index'))
