"""
نظام الإعلانات — admin web CRUD + student public API
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from src.extensions import db
from src.models.announcement import Announcement
from src.middleware.auth_middleware import verify_student_token

announcements_bp = Blueprint('announcements', __name__)


# ──────────────────────────────────────────────────────
#  Student Public API
# ──────────────────────────────────────────────────────

@announcements_bp.route('/api/announcements/active', methods=['GET'])
@verify_student_token
def api_get_active_announcement(student=None, student_id=None):
    """الطالب يجلب الإعلان النشط عند فتح التطبيق"""
    ann = (Announcement.query
           .filter_by(is_active=True)
           .order_by(Announcement.created_at.desc())
           .first())
    if not ann:
        return jsonify({'success': True, 'announcement': None})
    return jsonify({'success': True, 'announcement': ann.to_dict()})


# ──────────────────────────────────────────────────────
#  Admin Web — Image Upload
# ──────────────────────────────────────────────────────

@announcements_bp.route('/admin/announcements/upload-image', methods=['POST'])
@login_required
def admin_upload_announcement_image():
    """رفع صورة لإعلان إلى Cloudinary"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم إرسال صورة'}), 400
        file = request.files['image']
        if not file or not file.filename:
            return jsonify({'success': False, 'error': 'الملف فارغ'}), 400

        from src.routes.question import save_upload
        url = save_upload(file, subfolder='announcements')
        if url:
            return jsonify({'success': True, 'url': url})
        return jsonify({'success': False, 'error': 'فشل رفع الصورة'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────────────
#  Admin Web — CRUD
# ──────────────────────────────────────────────────────

@announcements_bp.route('/admin/announcements', methods=['GET'])
@login_required
def admin_announcements_list():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('announcements/list.html', announcements=announcements)


@announcements_bp.route('/admin/announcements/create', methods=['GET', 'POST'])
@login_required
def admin_announcements_create():
    if request.method == 'POST':
        title  = request.form.get('title', '').strip()
        body   = request.form.get('body', '').strip()
        images = request.form.getlist('images')  # روابط مرسلة من JS بعد الرفع

        if not title:
            flash('العنوان مطلوب', 'danger')
            return redirect(url_for('announcements.admin_announcements_create'))

        ann = Announcement(title=title, body=body, images=images, is_active=True)
        db.session.add(ann)
        db.session.commit()
        flash('تم إنشاء الإعلان بنجاح', 'success')
        return redirect(url_for('announcements.admin_announcements_list'))

    return render_template('announcements/form.html', ann=None)


@announcements_bp.route('/admin/announcements/<int:ann_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_announcements_edit(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    if request.method == 'POST':
        ann.title  = request.form.get('title', ann.title).strip()
        ann.body   = request.form.get('body', '').strip()
        ann.images = request.form.getlist('images')
        db.session.commit()
        flash('تم تحديث الإعلان', 'success')
        return redirect(url_for('announcements.admin_announcements_list'))

    return render_template('announcements/form.html', ann=ann)


@announcements_bp.route('/admin/announcements/<int:ann_id>/toggle', methods=['POST'])
@login_required
def admin_announcements_toggle(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    # عند تفعيل إعلان → وقّف الباقين (إعلان نشط واحد فقط)
    if not ann.is_active:
        Announcement.query.update({'is_active': False})
    ann.is_active = not ann.is_active
    db.session.commit()
    status = 'مفعّل' if ann.is_active else 'موقوف'
    flash(f'الإعلان الآن {status}', 'success')
    return redirect(url_for('announcements.admin_announcements_list'))


@announcements_bp.route('/admin/announcements/<int:ann_id>/delete', methods=['POST'])
@login_required
def admin_announcements_delete(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    flash('تم حذف الإعلان', 'success')
    return redirect(url_for('announcements.admin_announcements_list'))
