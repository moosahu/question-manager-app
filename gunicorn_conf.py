# gunicorn_conf.py
# ✅ تكوين gunicorn لبدء Scheduler في كل worker

import multiprocessing
import os

# Worker settings
workers = 2  # 2 workers - Render Standard 2GB RAM
threads = 4
worker_class = 'gthread'
worker_connections = 1000
timeout = 600  # 10 دقائق - يكفي لأطول عملية AI
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# ============================================
# ✅ Worker Hooks - بدء Scheduler في كل worker
# ============================================

def post_worker_init(worker):
    """
    يُستدعى بعد تهيئة كل worker
    نبدأ الـ Scheduler هنا عشان يشتغل في كل worker
    """
    worker.log.info(f"🔄 Worker {worker.pid} initialized - starting automation scheduler")

    try:
        from src.automation_scheduler import start_automation_scheduler

        # الحصول على app instance
        app = worker.app.callable

        # بدء الـ Scheduler
        start_automation_scheduler(app)
        worker.log.info(f"✅ Worker {worker.pid}: Automation scheduler started successfully")

    except Exception as e:
        worker.log.error(f"❌ Worker {worker.pid}: Failed to start automation scheduler: {e}")
        import traceback
        traceback.print_exc()


def worker_exit(server, worker):
    """
    يُستدعى عند إيقاف worker
    """
    worker.log.info(f"👋 Worker {worker.pid} exiting")
