# gunicorn.conf.py
# ملف إعدادات Gunicorn لحل مشكلة Worker Timeout
# ضع هذا الملف في المجلد الرئيسي بجانب main.py

import multiprocessing
import os

# ========================================
# إعدادات المهلة (Timeout)
# ========================================
# زيادة المهلة إلى 5 دقائق (300 ثانية) بدلاً من 30 ثانية
timeout = 300

# مهلة بدء تشغيل Worker
graceful_timeout = 120

# مهلة إبقاء الاتصال حياً
keepalive = 5

# ========================================
# إعدادات Workers
# ========================================
# عدد الـ workers (يفضل 2-4 للتطبيقات المتوسطة)
workers = 2

# نوع الـ worker
worker_class = 'sync'

# عدد الاتصالات المتزامنة لكل worker
worker_connections = 1000

# إعادة تشغيل Worker بعد عدد معين من الطلبات (يمنع تسرب الذاكرة)
max_requests = 1000
max_requests_jitter = 50

# ========================================
# إعدادات الربط والشبكة
# ========================================
# الربط (Render سيتجاوز هذا تلقائياً)
bind = "0.0.0.0:8000"

# السماح بإعادة استخدام المنفذ
reuse_port = True

# ========================================
# إعدادات السجلات (Logging)
# ========================================
# مستوى السجلات: debug, info, warning, error, critical
loglevel = 'info'

# سجلات الوصول (- تعني stdout)
accesslog = '-'

# سجلات الأخطاء
errorlog = '-'

# تنسيق سجلات الوصول
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# ========================================
# إعدادات الأمان
# ========================================
# حد الحجم الأقصى لرأس الطلب (16 KB)
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# ========================================
# إعدادات الأداء
# ========================================
# استخدام preload لتحسين استخدام الذاكرة
preload_app = False

# إعادة تحميل الكود عند التغيير (للتطوير فقط)
reload = False

# ========================================
# رسائل معلومات التشغيل
# ========================================
def on_starting(server):
    """يتم تنفيذها عند بدء تشغيل Gunicorn"""
    print("=" * 60)
    print("🚀 بدء تشغيل Gunicorn")
    print("=" * 60)

def when_ready(server):
    """يتم تنفيذها عندما يكون Gunicorn جاهزاً"""
    print("✅ تم تحميل إعدادات Gunicorn بنجاح")
    print(f"⏱️  المهلة (Timeout): {timeout} ثانية")
    print(f"👷 عدد Workers: {workers}")
    print(f"🔄 نوع Worker: {worker_class}")
    print(f"📊 Max Requests per Worker: {max_requests}")
    print(f"🌐 الربط: {bind}")
    print(f"📝 مستوى السجلات: {loglevel}")
    print("=" * 60)

def on_exit(server):
    """يتم تنفيذها عند إيقاف Gunicorn"""
    print("=" * 60)
    print("🛑 إيقاف Gunicorn")
    print("=" * 60)

# ========================================
# معالجة أخطاء Workers
# ========================================
def worker_exit(server, worker):
    """يتم تنفيذها عند خروج Worker"""
    print(f"⚠️  Worker {worker.pid} تم إيقافه")

def worker_abort(worker):
    """يتم تنفيذها عند إلغاء Worker بسبب timeout"""
    print(f"❌ Worker {worker.pid} تم إلغاؤه بسبب تجاوز المهلة")
    print(f"💡 تأكد من أن العمليات لا تستغرق أكثر من {timeout} ثانية")
