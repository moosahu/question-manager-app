# src/models/ai_analysis.py
"""
نموذج تحليلات الذكاء الاصطناعي للطلاب
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import text

try:
    from src.extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()


class AIAnalysis(db.Model):
    """نموذج تحليلات AI للطلاب"""
    __tablename__ = 'ai_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # نوع التحليل
    analysis_type = db.Column(db.String(50), nullable=False)  # daily, weekly, on_demand, alert
    
    # البيانات المحللة
    total_quizzes = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    last_quiz_date = db.Column(db.DateTime, nullable=True)
    days_since_last_quiz = db.Column(db.Integer, default=0)
    
    # اتجاه الأداء
    performance_trend = db.Column(db.String(20), nullable=True)  # improving, declining, stable, unknown
    trend_percentage = db.Column(db.Float, default=0.0)
    
    # التصنيف
    student_status = db.Column(db.String(20), nullable=False)  # excellent, good, needs_attention, critical
    severity_level = db.Column(db.String(20), nullable=False)  # green, yellow, orange, red
    
    # المشاكل والقوة
    issues_detected = db.Column(ARRAY(db.Text), nullable=True)
    strengths = db.Column(ARRAY(db.Text), nullable=True)
    
    # التوصيات
    ai_recommendations = db.Column(db.Text, nullable=True)
    suggested_action = db.Column(db.String(50), nullable=True)  # send_message, admin_alert, no_action
    
    # النتيجة الكاملة من AI
    full_analysis = db.Column(JSONB, default={})
    
    # حالة التنفيذ
    action_taken = db.Column(db.Boolean, default=False)
    action_type = db.Column(db.String(50), nullable=True)
    action_at = db.Column(db.DateTime, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    student = db.relationship('Student', backref=db.backref('ai_analyses', lazy='dynamic'))
    ai_actions = db.relationship('AIAction', backref='analysis', cascade='all, delete-orphan', lazy='dynamic')
    
    def __repr__(self):
        return f'<AIAnalysis {self.id}: S{self.student_id} - {self.student_status}>'
    
    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else None,
            'analysis_type': self.analysis_type,
            'total_quizzes': self.total_quizzes,
            'average_score': self.average_score,
            'last_quiz_date': self.last_quiz_date.isoformat() if self.last_quiz_date else None,
            'days_since_last_quiz': self.days_since_last_quiz,
            'performance_trend': self.performance_trend,
            'trend_percentage': self.trend_percentage,
            'student_status': self.student_status,
            'severity_level': self.severity_level,
            'issues_detected': self.issues_detected,
            'strengths': self.strengths,
            'ai_recommendations': self.ai_recommendations,
            'suggested_action': self.suggested_action,
            'action_taken': self.action_taken,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def mark_action_taken(self, action_type):
        """تعليم الإجراء كمنفذ"""
        self.action_taken = True
        self.action_type = action_type
        self.action_at = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def create_analysis(student_id, analysis_type, data):
        """إنشاء تحليل جديد"""
        analysis = AIAnalysis(
            student_id=student_id,
            analysis_type=analysis_type,
            total_quizzes=data.get('total_quizzes', 0),
            average_score=data.get('average_score', 0.0),
            last_quiz_date=data.get('last_quiz_date'),
            days_since_last_quiz=data.get('days_since_last_quiz', 0),
            performance_trend=data.get('performance_trend'),
            trend_percentage=data.get('trend_percentage', 0.0),
            student_status=data.get('student_status', 'unknown'),
            severity_level=data.get('severity_level', 'green'),
            issues_detected=data.get('issues_detected', []),
            strengths=data.get('strengths', []),
            ai_recommendations=data.get('ai_recommendations'),
            suggested_action=data.get('suggested_action'),
            full_analysis=data.get('full_analysis', {})
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis
    
    @staticmethod
    def get_latest_for_student(student_id):
        """جلب أحدث تحليل لطالب"""
        return AIAnalysis.query.filter_by(student_id=student_id)\
            .order_by(AIAnalysis.created_at.desc()).first()
    
    @staticmethod
    def get_students_by_severity(severity_level, limit=None):
        """جلب الطلاب حسب مستوى الخطورة"""
        # جلب أحدث تحليل لكل طالب
        subquery = db.session.query(
            AIAnalysis.student_id,
            db.func.max(AIAnalysis.id).label('latest_id')
        ).group_by(AIAnalysis.student_id).subquery()
        
        query = AIAnalysis.query.join(
            subquery,
            AIAnalysis.id == subquery.c.latest_id
        ).filter(AIAnalysis.severity_level == severity_level)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_critical_students():
        """جلب الطلاب في حالة حرجة"""
        return AIAnalysis.get_students_by_severity('red')
    
    @staticmethod
    def get_needs_attention_students():
        """جلب الطلاب الذين يحتاجون انتباه"""
        return AIAnalysis.get_students_by_severity('orange')


class AIAction(db.Model):
    """نموذج إجراءات AI التلقائية"""
    __tablename__ = 'ai_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    ai_analysis_id = db.Column(db.Integer, db.ForeignKey('ai_analysis.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # نوع الإجراء
    action_type = db.Column(db.String(50), nullable=False)  # smart_message, admin_alert, no_action
    action_description = db.Column(db.Text, nullable=True)
    
    # الرسالة المرسلة
    message_title = db.Column(db.String(200), nullable=True)
    message_body = db.Column(db.Text, nullable=True)
    message_sent = db.Column(db.Boolean, default=False)
    message_sent_at = db.Column(db.DateTime, nullable=True)
    
    # التنبيه للأدمن
    admin_notified = db.Column(db.Boolean, default=False)
    admin_notified_at = db.Column(db.DateTime, nullable=True)
    admin_id = db.Column(db.Integer, nullable=True)
    
    # النتيجة
    success = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    student = db.relationship('Student', backref=db.backref('ai_actions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<AIAction {self.id}: {self.action_type} for S{self.student_id}>'
    
    def execute(self):
        """تنفيذ الإجراء"""
        self.executed_at = datetime.utcnow()
        db.session.commit()
    
    def mark_success(self):
        """تعليم الإجراء كناجح"""
        self.success = True
        self.executed_at = datetime.utcnow()
        db.session.commit()
    
    def mark_failed(self, error_message):
        """تعليم الإجراء كفاشل"""
        self.success = False
        self.error_message = error_message
        self.executed_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """تحويل إلى dictionary"""
        return {
            'id': self.id,
            'ai_analysis_id': self.ai_analysis_id,
            'student_id': self.student_id,
            'action_type': self.action_type,
            'action_description': self.action_description,
            'message_title': self.message_title,
            'message_body': self.message_body,
            'message_sent': self.message_sent,
            'admin_notified': self.admin_notified,
            'success': self.success,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
        }


class AILog(db.Model):
    """نموذج سجل عمليات AI"""
    __tablename__ = 'ai_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String(50), nullable=False)
    student_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    data = db.Column(JSONB, default={})
    duration_seconds = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AILog {self.id}: {self.operation_type}>'
    
    @staticmethod
    def log_operation(operation_type, description=None, student_id=None, 
                     success=True, error_message=None, data=None, duration_seconds=None):
        """تسجيل عملية"""
        log = AILog(
            operation_type=operation_type,
            description=description,
            student_id=student_id,
            success=success,
            error_message=error_message,
            data=data or {},
            duration_seconds=duration_seconds
        )
        db.session.add(log)
        db.session.commit()
        return log


class AISetting(db.Model):
    """نموذج إعدادات AI"""
    __tablename__ = 'ai_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    setting_type = db.Column(db.String(20), default='string')
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<AISetting {self.setting_key}: {self.setting_value}>'
    
    def get_value(self):
        """الحصول على القيمة بالنوع الصحيح"""
        if self.setting_type == 'int':
            return int(self.setting_value)
        elif self.setting_type == 'float':
            return float(self.setting_value)
        elif self.setting_type == 'boolean':
            return self.setting_value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'json':
            import json
            return json.loads(self.setting_value)
        return self.setting_value
    
    @staticmethod
    def get_setting(key, default=None):
        """جلب إعداد"""
        setting = AISetting.query.filter_by(setting_key=key).first()
        if setting:
            return setting.get_value()
        return default
    
    @staticmethod
    def set_setting(key, value, setting_type='string', description=None):
        """تعيين إعداد"""
        setting = AISetting.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = AISetting(
                setting_key=key,
                setting_value=str(value),
                setting_type=setting_type,
                description=description
            )
            db.session.add(setting)
        db.session.commit()
        return setting
