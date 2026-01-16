def create_app():
    app = Flask(__name__)
    
    # ... all your configuration ...
    
    # Register blueprints
    from src.routes.admin_ai import admin_ai_bp
    app.register_blueprint(admin_ai_bp, url_prefix='/api/admin/ai')
    
    # ... other blueprints ...
# ============================================
    # بدء جدولة الرسائل التلقائية
    # ============================================
    print("🔥 DEBUG: بدء تهيئة automation_scheduler...")
    try:
        from src.automation_scheduler import start_automation_scheduler
        print("✅ DEBUG: تم استيراد start_automation_scheduler")
        
        @app.before_first_request
        def initialize_automation():
            print("🔥 DEBUG: تشغيل initialize_automation...")
            try:
                start_automation_scheduler(app)
                print("✅ DEBUG: تم تشغيل start_automation_scheduler")
                app.logger.info("✅ تم تهيئة النظام التلقائي بنجاح")
            except Exception as e:
                print(f"❌ DEBUG: خطأ في start_automation_scheduler: {e}")
                app.logger.error(f"❌ فشل تهيئة النظام التلقائي: {e}")
                import traceback
                traceback.print_exc()
    except ImportError as e:
        print(f"❌ DEBUG: فشل استيراد automation_scheduler: {e}")
        app.logger.error(f"❌ فشل استيراد automation_scheduler: {e}")
        import traceback
        traceback.print_exc()
    
    print("🔥 DEBUG: انتهى قسم automation_scheduler")
    return app