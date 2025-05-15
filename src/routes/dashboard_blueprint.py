# dashboard_blueprint.py
from flask import Blueprint, render_template
from .dashboard import get_dashboard_data  # استخدام استيراد نسبي

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('')  # تغيير من '/' إلى ''
def dashboard():
    # جلب بيانات لوحة التحكم
    dashboard_data = get_dashboard_data()
    
    # عرض قالب لوحة التحكم مع البيانات
    return render_template('dashboard.html', **dashboard_data)
