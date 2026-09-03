"""
نماذج تتبع الأخطاء التلقائي — كيم تحصيلي
src/models/error_tracking.py

الجداول:
  error_groups    — تجميع الأخطاء المتشابهة (PK: group_hash)
  error_reports   — سجل كل خطأ مُرسَل من التطبيق (FK → error_groups)
  auth_event_logs — عدّادات أحداث المصادقة (401 = session_expired, 403 = permission_denied)
"""

from datetime import datetime
from src.extensions import db


class ErrorGroup(db.Model):
    """مجموعة أخطاء متشابهة — مُجمَّعة بـ MD5(error_message[:100])"""
    __tablename__ = 'error_groups'

    group_hash    = db.Column(db.String(32),  primary_key=True)
    error_summary = db.Column(db.String(200), nullable=False)
    source        = db.Column(db.String(20),  nullable=False)   # auto_crash | api_error | screen_error | user_report
    priority      = db.Column(db.String(10),  nullable=False)   # CRITICAL | HIGH | MEDIUM | LOW
    count         = db.Column(db.Integer,     nullable=False, default=1)
    first_seen    = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    last_seen     = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    is_resolved   = db.Column(db.Boolean,     nullable=False, default=False)
    resolved_at   = db.Column(db.DateTime,    nullable=True)

    # العلاقة مع السجلات الفردية
    reports = db.relationship('ErrorReport', backref='group', lazy='dynamic')

    def __repr__(self):
        return f'<ErrorGroup {self.group_hash[:8]} [{self.priority}] x{self.count}>'

    def to_dict(self):
        return {
            'group_hash'   : self.group_hash,
            'error_summary': self.error_summary,
            'source'       : self.source,
            'priority'     : self.priority,
            'count'        : self.count,
            'first_seen'   : self.first_seen.isoformat() + 'Z' if self.first_seen else None,
            'last_seen'    : self.last_seen.isoformat()  + 'Z' if self.last_seen  else None,
            'is_resolved'  : self.is_resolved,
            'resolved_at'  : self.resolved_at.isoformat() + 'Z' if self.resolved_at else None,
        }


class ErrorReport(db.Model):
    """سجل خطأ فردي مُرسَل من التطبيق"""
    __tablename__ = 'error_reports'

    id            = db.Column(db.Integer,    primary_key=True, autoincrement=True)
    group_hash    = db.Column(db.String(32), db.ForeignKey('error_groups.group_hash'), nullable=True)
    source        = db.Column(db.String(20), nullable=False)
    priority      = db.Column(db.String(10), nullable=False)
    error_message = db.Column(db.Text,       nullable=False)
    stack_trace   = db.Column(db.Text,       nullable=True)
    screen_name   = db.Column(db.String(100),nullable=True)
    error_context = db.Column(db.String(200),nullable=True)
    user_type     = db.Column(db.String(20), nullable=True)   # admin | teacher | student | unknown
    app_version   = db.Column(db.String(20), nullable=True)
    device_model  = db.Column(db.String(100),nullable=True)   # مثل: iPhone 13, SM-G991B (Galaxy S21)
    created_at    = db.Column(db.DateTime,   nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<ErrorReport {self.id} [{self.source}]>'

    def to_dict(self):
        return {
            'id'           : self.id,
            'group_hash'   : self.group_hash,
            'source'       : self.source,
            'priority'     : self.priority,
            'error_message': self.error_message,
            'stack_trace'  : self.stack_trace,
            'screen_name'  : self.screen_name,
            'error_context': self.error_context,
            'user_type'    : self.user_type,
            'app_version'  : self.app_version,
            'device_model' : self.device_model,
            'created_at'   : self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class AuthEventLog(db.Model):
    """أحداث المصادقة — 401 (جلسة منتهية) و403 (رفض صلاحية) من كل الأجهزة"""
    __tablename__ = 'auth_event_logs'

    id         = db.Column(db.Integer,    primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(30), nullable=False)   # session_expired | permission_denied
    user_type  = db.Column(db.String(20), nullable=True)    # admin | teacher | student | unknown
    created_at = db.Column(db.DateTime,  nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<AuthEventLog {self.event_type} [{self.user_type}]>'
