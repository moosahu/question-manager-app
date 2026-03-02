# src/gunicorn.conf.py

workers = 2
threads = 4
worker_class = 'gthread'
timeout = 600
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True

daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None


def post_worker_init(worker):
    worker.log.info(f"🔄 Worker {worker.pid} initialized - starting automation scheduler")
    try:
        from src.automation_scheduler import start_automation_scheduler
        app = worker.app.callable
        start_automation_scheduler(app)
        worker.log.info(f"✅ Worker {worker.pid}: Automation scheduler started successfully")
    except Exception as e:
        worker.log.error(f"❌ Worker {worker.pid}: Failed to start automation scheduler: {e}")
        import traceback
        traceback.print_exc()


def worker_exit(server, worker):
    worker.log.info(f"👋 Worker {worker.pid} exiting")
