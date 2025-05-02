from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Define db and login_manager here without initializing with app
db = SQLAlchemy()
login_manager = LoginManager()

# You can add other extensions here if needed later
