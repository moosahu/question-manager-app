# dashboard_blueprint.py
from flask import Blueprint, render_template
from src.routes.dashboard import get_dashboard_data

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def dashboard():
    # جلب بيانات لوحة التحكم
    dashboard_data = get_dashboard_data()
    
    # عرض قالب لوحة التحكم مع البيانات
    return render_template('dashboard.html', **dashboard_data)
