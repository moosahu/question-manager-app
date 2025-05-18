from datetime import datetime, timedelta
try:
    from src.extensions import db
except ImportError:
    # Fallback if running in a different structure or directly
    try:
        from extensions import db
    except ImportError:
        try:
            from main import db # Adjust if your db instance is elsewhere
        except ImportError:
            print("Error: Database object 'db' could not be imported.")
            raise

class Activity(db.Model):
    """
    نموذج لتسجيل الأنشطة والأحداث في النظام
    يستخدم لعرض النشاط الأخير في لوحة التحكم
    """
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String(50), nullable=False)  # إضافة، تعديل، حذف، استيراد
    entity_type = db.Column(db.String(50), nullable=False)  # سؤال، درس، وحدة، دورة
    entity_id = db.Column(db.Integer, nullable=True)  # معرف الكيان المتأثر
    description = db.Column(db.Text, nullable=False)  # وصف النشاط
    lesson_name = db.Column(db.String(255), nullable=True)  # اسم الدرس المرتبط
    unit_name = db.Column(db.String(255), nullable=True)  # اسم الوحدة المرتبطة
    course_name = db.Column(db.String(255), nullable=True)  # اسم الدورة المرتبطة
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # معرف المستخدم الذي قام بالنشاط
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # وقت النشاط

    # العلاقة مع المستخدم
    user = db.relationship("User", backref=db.backref("activities", lazy=True))

    def __repr__(self):
        return f"<Activity {self.id}: {self.action_type} {self.entity_type} at {self.timestamp}>"

    @staticmethod
    def log_activity(action_type, entity_type, entity_id=None, description=None, 
                    lesson_name=None, unit_name=None, course_name=None, user_id=None):
        """
        تسجيل نشاط جديد في قاعدة البيانات
        
        Parameters:
        - action_type: نوع الإجراء (إضافة، تعديل، حذف، استيراد)
        - entity_type: نوع الكيان (سؤال، درس، وحدة، دورة)
        - entity_id: معرف الكيان (اختياري)
        - description: وصف النشاط
        - lesson_name: اسم الدرس (اختياري)
        - unit_name: اسم الوحدة (اختياري)
        - course_name: اسم الدورة (اختياري)
        - user_id: معرف المستخدم (اختياري)
        
        Returns:
        - كائن النشاط المسجل
        """
        activity = Activity(
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            lesson_name=lesson_name,
            unit_name=unit_name,
            course_name=course_name,
            user_id=user_id
        )
        
        try:
            db.session.add(activity)
            db.session.commit()
            return activity
        except Exception as e:
            db.session.rollback()
            print(f"Error logging activity: {e}")
            return None

    @staticmethod
    def get_recent_activities(limit=10):
        """
        استرجاع أحدث الأنشطة من قاعدة البيانات
        
        Parameters:
        - limit: عدد الأنشطة المراد استرجاعها (الافتراضي: 10)
        
        Returns:
        - قائمة بأحدث الأنشطة
        """
        return Activity.query.order_by(Activity.timestamp.desc()).limit(limit).all()
        
    @staticmethod
    def get_time_diff_text(timestamp):
        """
        حساب الفرق الزمني بين الوقت الحالي والوقت المعطى بصيغة نصية
        
        Parameters:
        - timestamp: الوقت المراد حساب الفرق منه
        
        Returns:
        - نص يصف الفرق الزمني (منذ X دقائق، منذ X ساعات، إلخ)
        """
        now = datetime.utcnow()
        diff = now - timestamp
        
        if diff < timedelta(minutes=1):
            return "منذ لحظات"
        elif diff < timedelta(hours=1):
            minutes = diff.seconds // 60
            return f"منذ {minutes} دقيقة" if minutes == 1 else f"منذ {minutes} دقائق"
        elif diff < timedelta(days=1):
            hours = diff.seconds // 3600
            return f"منذ {hours} ساعة" if hours == 1 else f"منذ {hours} ساعات"
        elif diff < timedelta(days=30):
            days = diff.days
            return f"منذ {days} يوم" if days == 1 else f"منذ {days} أيام"
        elif diff < timedelta(days=365):
            months = diff.days // 30
            return f"منذ {months} شهر" if months == 1 else f"منذ {months} أشهر"
        else:
            years = diff.days // 365
            return f"منذ {years} سنة" if years == 1 else f"منذ {years} سنوات"
