
from models.notification_model import Notification
from extensions import db

def create_notification(user_id, content):
    notif = Notification(user_id=user_id, content=content)
    db.session.add(notif)
    db.session.commit()
