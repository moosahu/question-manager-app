"""
شاشة "مناسبة" (صورة/فيديو) تظهر فوق شاشة السبلاش عند فتح التطبيق — قبل تسجيل الدخول.
admin web CRUD + public API (بدون توثيق، تظهر لأي زائر حتى قبل تسجيل الدخول).
"""
import os
import time
import uuid
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from werkzeug.utils import secure_filename
from src.extensions import db
from src.models.splash_greeting import SplashGreeting

splash_greeting_bp = Blueprint('splash_greeting', __name__)


# ──────────────────────────────────────────────────────
#  Public API — بدون توثيق، تُستدعى قبل تسجيل الدخول
# ──────────────────────────────────────────────────────

@splash_greeting_bp.route('/api/splash-greeting/active', methods=['GET'])
def api_get_active_splash_greeting():
    """المناسبة النشطة الحالية (إن وجدت) — يقرأها التطبيق قبل شاشة الدخول"""
    g = (SplashGreeting.query
         .filter_by(is_active=True)
         .order_by(SplashGreeting.created_at.desc())
         .first())
    if not g:
        return jsonify({'success': True, 'greeting': None})
    return jsonify({'success': True, 'greeting': g.to_dict()})


# ──────────────────────────────────────────────────────
#  Admin Web — رفع الوسائط
# ──────────────────────────────────────────────────────

def _configure_cloudinary():
    import cloudinary
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    if all([cloud_name, api_key, api_secret]):
        cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)
    elif os.environ.get('CLOUDINARY_URL'):
        cloudinary.config()
    else:
        raise RuntimeError('Cloudinary غير مُعد (متغيرات البيئة ناقصة)')


@splash_greeting_bp.route('/admin/splash-greeting/upload-image', methods=['POST'])
@login_required
def admin_upload_splash_image():
    """رفع صورة المناسبة إلى Cloudinary"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم إرسال صورة'}), 400
        file = request.files['image']
        if not file or not file.filename:
            return jsonify({'success': False, 'error': 'الملف فارغ'}), 400

        from src.routes.question import save_upload
        url = save_upload(file, subfolder='splash_greetings')
        if url:
            return jsonify({'success': True, 'url': url})
        return jsonify({'success': False, 'error': 'فشل رفع الصورة'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@splash_greeting_bp.route('/admin/splash-greeting/upload-video', methods=['POST'])
@login_required
def admin_upload_splash_video():
    """رفع فيديو المناسبة إلى Cloudinary (resource_type=video)"""
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم إرسال فيديو'}), 400
        file = request.files['video']
        if not file or not file.filename:
            return jsonify({'success': False, 'error': 'الملف فارغ'}), 400

        ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if ext not in ('mp4', 'mov', 'webm', 'm4v'):
            return jsonify({'success': False, 'error': 'صيغة فيديو غير مدعومة (mp4/mov/webm فقط)'}), 400

        import cloudinary.uploader
        _configure_cloudinary()

        original_filename = secure_filename(file.filename)
        public_id = f"splash_greetings/{int(time.time())}_{uuid.uuid4().hex[:8]}_{os.path.splitext(original_filename)[0]}"

        file.seek(0)
        result = cloudinary.uploader.upload(
            file,
            resource_type='video',
            public_id=public_id,
            folder=None,
            overwrite=True,
        )
        url = result.get('secure_url')
        if not url:
            return jsonify({'success': False, 'error': 'فشل رفع الفيديو'}), 500
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': f'فشل رفع الفيديو: {e}'}), 500


# ──────────────────────────────────────────────────────
#  Admin Web — CRUD
# ──────────────────────────────────────────────────────

@splash_greeting_bp.route('/admin/splash-greeting', methods=['GET'])
@login_required
def admin_splash_greeting_list():
    from datetime import timedelta
    greetings = SplashGreeting.query.order_by(SplashGreeting.created_at.desc()).all()
    for g in greetings:
        g._created_ast = (g.created_at + timedelta(hours=3)) if g.created_at else None
    return render_template('splash_greeting/list.html', greetings=greetings)


@splash_greeting_bp.route('/admin/splash-greeting/create', methods=['GET', 'POST'])
@login_required
def admin_splash_greeting_create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        media_type = request.form.get('media_type', 'image')
        media_url = request.form.get('media_url', '').strip()

        if not title or not media_url:
            flash('العنوان والملف مطلوبان', 'danger')
            return redirect(url_for('splash_greeting.admin_splash_greeting_create'))
        if media_type not in ('image', 'video'):
            media_type = 'image'

        g = SplashGreeting(title=title, media_type=media_type, media_url=media_url, is_active=True)
        db.session.add(g)
        db.session.commit()
        flash('تم إنشاء المناسبة بنجاح', 'success')
        return redirect(url_for('splash_greeting.admin_splash_greeting_list'))

    return render_template('splash_greeting/form.html', g=None)


@splash_greeting_bp.route('/admin/splash-greeting/<int:g_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_splash_greeting_edit(g_id):
    g = SplashGreeting.query.get_or_404(g_id)
    if request.method == 'POST':
        title = request.form.get('title', g.title).strip()
        media_type = request.form.get('media_type', g.media_type)
        media_url = request.form.get('media_url', g.media_url).strip()
        if not title or not media_url:
            flash('العنوان والملف مطلوبان', 'danger')
            return redirect(url_for('splash_greeting.admin_splash_greeting_edit', g_id=g_id))

        g.title = title
        g.media_type = media_type if media_type in ('image', 'video') else g.media_type
        g.media_url = media_url
        db.session.commit()
        flash('تم تحديث المناسبة', 'success')
        return redirect(url_for('splash_greeting.admin_splash_greeting_list'))

    return render_template('splash_greeting/form.html', g=g)


@splash_greeting_bp.route('/admin/splash-greeting/<int:g_id>/toggle', methods=['POST'])
@login_required
def admin_splash_greeting_toggle(g_id):
    g = SplashGreeting.query.get_or_404(g_id)
    # مناسبة واحدة نشطة بأي وقت — تفعيل هذي يوقف البقية تلقائياً
    if not g.is_active:
        SplashGreeting.query.filter(SplashGreeting.id != g.id, SplashGreeting.is_active == True).update(
            {'is_active': False}
        )
    g.is_active = not g.is_active
    db.session.commit()
    status = 'مفعّلة' if g.is_active else 'موقوفة'
    flash(f'المناسبة الآن {status}', 'success')
    return redirect(url_for('splash_greeting.admin_splash_greeting_list'))


def _delete_cloudinary_asset(url: str, resource_type: str):
    try:
        import cloudinary
        import cloudinary.uploader
        import re
        _configure_cloudinary()
        match = re.search(r'/upload/(?:v\d+/)?(.+?)(?:\.[a-zA-Z0-9]{3,4})?$', url)
        if match:
            cloudinary.uploader.destroy(match.group(1), resource_type=resource_type)
    except Exception:
        pass  # الحذف اختياري، لا يوقف العملية


@splash_greeting_bp.route('/admin/splash-greeting/<int:g_id>/delete', methods=['POST'])
@login_required
def admin_splash_greeting_delete(g_id):
    g = SplashGreeting.query.get_or_404(g_id)
    media_url, media_type = g.media_url, g.media_type
    db.session.delete(g)
    db.session.commit()
    if media_url:
        _delete_cloudinary_asset(media_url, 'video' if media_type == 'video' else 'image')
    flash('تم حذف المناسبة وملفها', 'success')
    return redirect(url_for('splash_greeting.admin_splash_greeting_list'))
