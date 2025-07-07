from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# تعريف db و login_manager هنا بدون تهيئة التطبيق
db = SQLAlchemy()
login_manager = LoginManager()

# يمكنك إضافة امتدادات أخرى هنا إذا لزم الأمر لاحقاً
