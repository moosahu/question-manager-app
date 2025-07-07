
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.notification_model import Notification

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
@login_required
def index():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
    return render_template('index.html', notifications=notifications)
