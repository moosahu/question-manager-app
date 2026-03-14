"""
نظام تتبع الأخطاء التلقائي — كيم تحصيلي
src/routes/errors.py

Endpoints:
  POST /api/v1/errors/report        ← يستقبل من Flutter (بدون auth)
  GET  /api/v1/errors/groups        ← قائمة مجموعات الأخطاء (أدمن فقط)
  GET  /api/v1/errors/list          ← سجلات مفصلة (أدمن فقط)
  POST /api/v1/errors/<hash>/resolve ← علّم "تم الحل" (أدمن فقط)
"""

import hashlib
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

errors_bp = Blueprint('errors', __name__, url_prefix='/api/v1/errors')

# ─── استيراد DB ─────────────────────────────────────────────────────────────

try:
    from src.extensions import db
except ImportError:
    from extensions import db

# ─── استيراد النماذج ─────────────────────────────────────────────────────────

try:
    from src.models.error_tracking import ErrorReport, ErrorGroup, AuthEventLog
    from src.models.notification import Notification
    from src.models.user import User
except ImportError:
    from models.error_tracking import ErrorReport, ErrorGroup, AuthEventLog
    from models.notification import Notification
    from models.user import User

# ─── أولوية تلقائية ─────────────────────────────────────────────────────────

_PRIORITY_MAP = {
    'auto_crash'  : 'CRITICAL',
    'api_error'   : 'HIGH',
    'screen_error': 'HIGH',
    'user_report' : 'MEDIUM',
}

def _get_priority(source: str) -> str:
    return _PRIORITY_MAP.get(source, 'MEDIUM')

def _group_hash(error_message: str) -> str:
    key = error_message[:100].strip()
    return hashlib.md5(key.encode('utf-8', errors='replace')).hexdigest()

# ─── إشعار الأدمن (إيميل + صندوق الوارد) ────────────────────────────────────

def _notify_admin(group: 'ErrorGroup', report: 'ErrorReport') -> None:
    try:
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            return

        priority_ar = {'CRITICAL': '🔴 حرج', 'HIGH': '🟠 عالي',
                       'MEDIUM': '🟡 متوسط', 'LOW': '🟢 منخفض'}.get(group.priority, group.priority)
        source_ar   = {'auto_crash': 'كراش تلقائي', 'api_error': 'خطأ API',
                       'screen_error': 'خطأ شاشة', 'user_report': 'بلاغ مستخدم'}.get(report.source, report.source)

        title = f'🚨 خطأ {priority_ar} — {source_ar}'
        message = (
            f'الخطأ: {group.error_summary}\n'
            f'الشاشة: {report.screen_name or "غير محدد"}\n'
            f'نوع المستخدم: {report.user_type or "غير معروف"}\n'
            f'الإصدار: {report.app_version or "غير معروف"}\n'
            f'التكرار: {group.count} مرة\n'
            f'السياق: {report.error_context or "-"}'
        )

        # ① صندوق الوارد
        notif = Notification(
            title=title,
            message=message,
            type='admin_event',
            user_id=admin.id,
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()

        # ② إيميل
        try:
            from src.services.email_service import email_service
            if admin.email:
                email_service.send_admin_notification(admin.email, title, message)
        except Exception as _e:
            logger.warning(f'Error notification email failed: {_e}')

    except Exception as _e:
        logger.warning(f'_notify_admin failed: {_e}')

# ─── Endpoints ───────────────────────────────────────────────────────────────

@errors_bp.route('/report', methods=['POST'])
def report_error():
    """يستقبل تقرير خطأ من Flutter — بدون auth (مثل /bug-report)"""
    try:
        data = request.get_json(silent=True) or {}

        source        = (data.get('source') or 'unknown').strip()[:20]
        error_message = (data.get('error_message') or '').strip()
        stack_trace   = (data.get('stack_trace') or '').strip() or None
        screen_name   = (data.get('screen_name') or '').strip()[:100] or None
        error_context = (data.get('error_context') or '').strip()[:200] or None
        user_type     = (data.get('user_type') or 'unknown').strip()[:20]
        app_version   = (data.get('app_version') or '').strip()[:20]

        if not error_message:
            return jsonify({'success': False, 'error': 'error_message مطلوب'}), 400

        priority = _get_priority(source)
        g_hash   = _group_hash(error_message)
        summary  = error_message[:200]
        now      = datetime.utcnow()

        # ── تحديث أو إنشاء المجموعة ────────────────────────────
        group = ErrorGroup.query.get(g_hash)
        is_new_group = group is None

        if group:
            group.count    += 1
            group.last_seen = now
            # رفّع الأولوية إذا جاء crash على مجموعة كانت أقل أولوية
            if priority == 'CRITICAL' and group.priority != 'CRITICAL':
                group.priority = 'CRITICAL'
        else:
            group = ErrorGroup(
                group_hash    = g_hash,
                error_summary = summary,
                source        = source,
                priority      = priority,
                count         = 1,
                first_seen    = now,
                last_seen     = now,
                is_resolved   = False,
            )
            db.session.add(group)

        # ── حفظ السجل الفردي ────────────────────────────────────
        report = ErrorReport(
            group_hash    = g_hash,
            source        = source,
            priority      = priority,
            error_message = error_message,
            stack_trace   = stack_trace,
            screen_name   = screen_name,
            error_context = error_context,
            user_type     = user_type,
            app_version   = app_version,
            created_at    = now,
        )
        db.session.add(report)
        db.session.commit()

        # ── إشعار الأدمن عند: crash جديد أو تكرار ≥ 5 ──────────
        should_notify = (
            priority == 'CRITICAL' and is_new_group
        ) or (
            group.count in (5, 10, 25, 50, 100)
        )
        if should_notify:
            _notify_admin(group, report)

        return jsonify({'success': True, 'group_hash': g_hash})

    except Exception as e:
        logger.exception(f'report_error failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@errors_bp.route('/auth-event', methods=['POST'])
def log_auth_event():
    """يستقبل أحداث المصادقة (401/403) من Flutter — بدون auth"""
    try:
        data       = request.get_json(silent=True) or {}
        event_type = (data.get('event_type') or '').strip()[:30]
        user_type  = (data.get('user_type')  or 'unknown').strip()[:20]

        if event_type not in ('session_expired', 'permission_denied'):
            return jsonify({'success': False, 'error': 'event_type غير صالح'}), 400

        log = AuthEventLog(event_type=event_type, user_type=user_type)
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        logger.exception(f'log_auth_event failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@errors_bp.route('/groups', methods=['GET'])
@login_required
def get_groups():
    """قائمة مجموعات الأخطاء — أدمن فقط"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403

    resolved  = request.args.get('resolved', 'false').lower() == 'true'
    source    = request.args.get('source')
    priority  = request.args.get('priority')
    page      = int(request.args.get('page', 1))
    per_page  = int(request.args.get('per_page', 50))

    q = ErrorGroup.query.filter_by(is_resolved=resolved)
    if source:
        q = q.filter_by(source=source)
    if priority:
        q = q.filter_by(priority=priority)

    # ترتيب: CRITICAL أولاً ثم الأحدث
    priority_order = db.case(
        (ErrorGroup.priority == 'CRITICAL', 1),
        (ErrorGroup.priority == 'HIGH',     2),
        (ErrorGroup.priority == 'MEDIUM',   3),
        else_=4,
    )
    groups = (q.order_by(priority_order, ErrorGroup.last_seen.desc())
               .offset((page - 1) * per_page)
               .limit(per_page)
               .all())

    return jsonify({
        'success': True,
        'total'  : q.count(),
        'groups' : [g.to_dict() for g in groups],
    })


@errors_bp.route('/list', methods=['GET'])
@login_required
def get_reports():
    """سجلات مفصلة — أدمن فقط"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403

    group_hash = request.args.get('group_hash')
    page       = int(request.args.get('page', 1))
    per_page   = int(request.args.get('per_page', 30))

    q = ErrorReport.query
    if group_hash:
        q = q.filter_by(group_hash=group_hash)

    reports = (q.order_by(ErrorReport.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all())

    return jsonify({
        'success': True,
        'total'  : q.count(),
        'reports': [r.to_dict() for r in reports],
    })


@errors_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """إحصائيات الأخطاء — آخر 7 أيام + أكثر الشاشات + مقارنة الإصدارات"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403

    try:
        from sqlalchemy import func, cast, Date
        now = datetime.utcnow()
        week_ago = now - timedelta(days=6)

        # ── إحصائيات آخر 7 أيام ─────────────────────────────────
        daily_rows = (
            db.session.query(
                cast(ErrorReport.created_at, Date).label('day'),
                func.count(ErrorReport.id).label('cnt')
            )
            .filter(ErrorReport.created_at >= week_ago)
            .group_by(cast(ErrorReport.created_at, Date))
            .order_by(cast(ErrorReport.created_at, Date))
            .all()
        )
        # نبني قاموس يوم → عدد ونملأ الأيام السبعة كاملة
        daily_map = {str(r.day): r.cnt for r in daily_rows}
        daily = []
        for i in range(6, -1, -1):
            day = (now - timedelta(days=i)).date()
            daily.append({'date': str(day), 'count': daily_map.get(str(day), 0)})

        # ── أكثر 5 شاشات بها أخطاء ──────────────────────────────
        top_screens_rows = (
            db.session.query(
                ErrorReport.screen_name,
                func.count(ErrorReport.id).label('cnt')
            )
            .filter(ErrorReport.screen_name.isnot(None))
            .group_by(ErrorReport.screen_name)
            .order_by(func.count(ErrorReport.id).desc())
            .limit(5)
            .all()
        )
        top_screens = [{'screen': r.screen_name, 'count': r.cnt} for r in top_screens_rows]

        # ── مقارنة الإصدارات ─────────────────────────────────────
        versions_rows = (
            db.session.query(
                ErrorReport.app_version,
                func.count(ErrorReport.id).label('cnt')
            )
            .filter(ErrorReport.app_version.isnot(None))
            .group_by(ErrorReport.app_version)
            .order_by(func.count(ErrorReport.id).desc())
            .limit(5)
            .all()
        )
        versions = [{'version': r.app_version, 'count': r.cnt} for r in versions_rows]

        # ── ملخص الأولويات (غير محلولة) ─────────────────────────
        priority_rows = (
            db.session.query(
                ErrorGroup.priority,
                func.sum(ErrorGroup.count).label('cnt')
            )
            .filter_by(is_resolved=False)
            .group_by(ErrorGroup.priority)
            .all()
        )
        priorities = {r.priority: r.cnt for r in priority_rows}

        # ── إجمالي ───────────────────────────────────────────────
        total_unresolved = ErrorGroup.query.filter_by(is_resolved=False).count()
        total_week       = sum(d['count'] for d in daily)

        # ── عدّادات المصادقة (كل الوقت + تفصيل حسب نوع المستخدم) ──
        try:
            auth_rows = (
                db.session.query(
                    AuthEventLog.event_type,
                    AuthEventLog.user_type,
                    func.count(AuthEventLog.id).label('cnt')
                )
                .group_by(AuthEventLog.event_type, AuthEventLog.user_type)
                .all()
            )
            auth_counters = {}
            auth_by_type  = {}   # {event_type: {user_type: count}}
            for row in auth_rows:
                auth_counters[row.event_type] = auth_counters.get(row.event_type, 0) + row.cnt
                auth_by_type.setdefault(row.event_type, {})[row.user_type or 'unknown'] = row.cnt
        except Exception:
            auth_counters = {}
            auth_by_type  = {}

        return jsonify({
            'success'         : True,
            'daily'           : daily,
            'top_screens'     : top_screens,
            'versions'        : versions,
            'priorities'      : priorities,
            'total_unresolved': total_unresolved,
            'total_week'      : total_week,
            'auth_counters'   : auth_counters,
            'auth_by_type'    : auth_by_type,
        })

    except Exception as e:
        logger.exception(f'get_stats failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@errors_bp.route('/dashboard', methods=['GET'])
@login_required
def errors_dashboard():
    """صفحة لوحة تحكم الأخطاء — أدمن فقط"""
    if not current_user.is_admin:
        from flask import abort
        abort(403)
    from flask import render_template
    return render_template('admin/errors.html')


@errors_bp.route('/<group_hash>/resolve', methods=['POST'])
@login_required
def resolve_group(group_hash):
    """علّم المجموعة كـ 'تم الحل' — أدمن فقط"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403

    group = ErrorGroup.query.get(group_hash)
    if not group:
        return jsonify({'success': False, 'error': 'المجموعة غير موجودة'}), 404

    group.is_resolved = True
    group.resolved_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True})
