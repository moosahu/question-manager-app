"""
Server Stats - مراقبة موارد السيرفر (RAM, CPU, Uptime)
"""

import os
import time
import psutil
from datetime import timedelta
from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user

server_stats_bp = Blueprint('server_stats', __name__)

_start_time = time.time()


def _get_stats():
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    uptime_secs = int(time.time() - _start_time)
    uptime_str = str(timedelta(seconds=uptime_secs))

    disk = psutil.disk_usage('/')

    return {
        'ram_used_mb': round(mem.used / 1024 / 1024, 1),
        'ram_total_mb': round(mem.total / 1024 / 1024, 1),
        'ram_percent': mem.percent,
        'cpu_percent': cpu,
        'uptime': uptime_str,
        'uptime_seconds': uptime_secs,
        'disk_used_gb': round(disk.used / 1024 / 1024 / 1024, 1),
        'disk_total_gb': round(disk.total / 1024 / 1024 / 1024, 1),
        'disk_percent': disk.percent,
    }


@server_stats_bp.route('/api/admin/server-stats', methods=['GET'])
@login_required
def api_server_stats():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'ليس لديك صلاحية'}), 403
    try:
        stats = _get_stats()
        return jsonify({'success': True, **stats}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@server_stats_bp.route('/api/admin/server-disk-details', methods=['GET'])
@login_required
def api_disk_details():
    """أكبر المجلدات على السيرفر لمعرفة من يأكل المساحة"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'ليس لديك صلاحية'}), 403
    try:
        dirs_to_check = [
            ('/', 'الجذر'),
            ('/app', 'مجلد التطبيق'),
            ('/usr', '/usr'),
            ('/tmp', '/tmp'),
            (os.path.expanduser('~'), 'Home'),
        ]
        results = []
        for path, label in dirs_to_check:
            if not os.path.exists(path):
                continue
            try:
                total = 0
                for dirpath, dirnames, filenames in os.walk(path):
                    # تجنب venv و __pycache__ لتسريع البحث
                    dirnames[:] = [d for d in dirnames if d not in ('venv', '__pycache__', '.git', 'node_modules')]
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            total += os.path.getsize(fp)
                        except OSError:
                            pass
                results.append({'path': path, 'label': label, 'size_mb': round(total / 1024 / 1024, 1)})
            except PermissionError:
                pass
        results.sort(key=lambda x: x['size_mb'], reverse=True)
        return jsonify({'success': True, 'dirs': results}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@server_stats_bp.route('/admin/server-stats', methods=['GET'])
@login_required
def web_server_stats():
    if not current_user.is_admin:
        return jsonify({'error': 'ليس لديك صلاحية'}), 403
    stats = _get_stats()
    return render_template('server_stats.html', stats=stats)
