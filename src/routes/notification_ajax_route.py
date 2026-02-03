
from flask import jsonify
from flask_login import login_required, current_user
from models.notification_model import Notification

@home_bp.route('/api/notifications/unread')
@login_required
def get_unread_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    return jsonify([
        {
            "id": n.id,
            "content": n.content,
            "created_at": n.created_at.strftime('%Y-%m-%d %H:%M')
        }
        for n in notifs
    ])
