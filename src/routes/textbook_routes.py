"""
Textbook Routes - إدارة الكتب الدراسية وربط الصفحات بالدروس
"""
from flask import Blueprint, request, jsonify, send_file
from flask_login import current_user
from functools import wraps
from datetime import datetime
import os
import io
import logging

from src.extensions import db
from src.models.textbook import Textbook, LessonPages
from src.models.curriculum import Course, Unit, Lesson

logger = logging.getLogger(__name__)

textbook_bp = Blueprint('textbook', __name__, url_prefix='/api/admin/textbooks')


def admin_required(f):
    """Decorator للتحقق من صلاحيات الأدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'صلاحيات غير كافية'}), 403
        return f(*args, **kwargs)
    return decorated_function


@textbook_bp.route('', methods=['GET'])
@admin_required
def get_textbooks():
    """قائمة الكتب الدراسية"""
    try:
        course_id = request.args.get('course_id', type=int)
        query = Textbook.query.filter_by(is_active=True)
        if course_id:
            query = query.filter_by(course_id=course_id)
        textbooks = query.order_by(Textbook.created_at.desc()).all()
        return jsonify({
            'success': True,
            'data': [t.to_dict() for t in textbooks]
        })
    except Exception as e:
        logger.error(f"خطأ في جلب الكتب: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@textbook_bp.route('/upload', methods=['POST'])
@admin_required
def upload_textbook():
    """رفع كتاب PDF جديد"""
    try:
        if 'pdf' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم إرفاق ملف PDF'}), 400

        pdf_file = request.files['pdf']
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'الملف يجب أن يكون PDF'}), 400

        course_id = request.form.get('course_id', type=int)
        title = request.form.get('title', '').strip()
        edition_year = request.form.get('edition_year', '').strip()

        if not course_id or not title:
            return jsonify({'success': False, 'error': 'المقرر والعنوان مطلوبان'}), 400

        course = Course.query.get(course_id)
        if not course:
            return jsonify({'success': False, 'error': 'المقرر غير موجود'}), 404

        # حساب عدد الصفحات
        pdf_bytes = pdf_file.read()
        total_pages = 0
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            doc.close()
        except Exception as e:
            logger.warning(f"لم نتمكن من حساب عدد الصفحات: {e}")

        # رفع على Cloudinary
        pdf_url = None
        try:
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                io.BytesIO(pdf_bytes),
                resource_type='raw',
                folder='textbooks',
                public_id=f"textbook_{course_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            )
            pdf_url = result.get('secure_url') or result.get('url')
        except Exception as e:
            logger.warning(f"فشل رفع Cloudinary: {e}, سيتم الحفظ محلياً")

        # حفظ محلي كـ fallback
        if not pdf_url:
            upload_dir = os.path.join(os.getcwd(), 'uploads', 'textbooks')
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"textbook_{course_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(pdf_bytes)
            pdf_url = f"/uploads/textbooks/{filename}"

        textbook = Textbook(
            course_id=course_id,
            title=title,
            edition_year=edition_year,
            pdf_url=pdf_url,
            total_pages=total_pages,
            uploaded_by=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(textbook)
        db.session.commit()

        logger.info(f"تم رفع كتاب: {title} (ID: {textbook.id}, صفحات: {total_pages})")
        return jsonify({
            'success': True,
            'data': textbook.to_dict(),
            'message': f'تم رفع الكتاب بنجاح ({total_pages} صفحة)'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"خطأ في رفع الكتاب: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@textbook_bp.route('/<int:textbook_id>', methods=['DELETE'])
@admin_required
def delete_textbook(textbook_id):
    """حذف كتاب"""
    try:
        textbook = Textbook.query.get(textbook_id)
        if not textbook:
            return jsonify({'success': False, 'error': 'الكتاب غير موجود'}), 404

        textbook.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم حذف الكتاب'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@textbook_bp.route('/<int:textbook_id>/pages', methods=['POST'])
@admin_required
def set_lesson_pages(textbook_id):
    """ربط الدروس بصفحات الكتاب (bulk)"""
    try:
        textbook = Textbook.query.get(textbook_id)
        if not textbook:
            return jsonify({'success': False, 'error': 'الكتاب غير موجود'}), 404

        data = request.get_json()
        mappings = data.get('mappings', [])
        # كل mapping: { lesson_id, start_page, end_page }

        if not mappings:
            return jsonify({'success': False, 'error': 'لا توجد بيانات ربط'}), 400

        saved = 0
        for m in mappings:
            lesson_id = m.get('lesson_id')
            start_page = m.get('start_page')
            end_page = m.get('end_page')

            if not all([lesson_id, start_page is not None, end_page is not None]):
                continue

            if start_page < 1 or end_page < start_page:
                continue

            if end_page > textbook.total_pages and textbook.total_pages > 0:
                continue

            # تحديث أو إنشاء
            existing = LessonPages.query.filter_by(
                lesson_id=lesson_id, textbook_id=textbook_id
            ).first()

            if existing:
                existing.start_page = start_page
                existing.end_page = end_page
            else:
                lp = LessonPages(
                    lesson_id=lesson_id,
                    textbook_id=textbook_id,
                    start_page=start_page,
                    end_page=end_page,
                )
                db.session.add(lp)
            saved += 1

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'تم ربط {saved} درس بالصفحات',
            'saved_count': saved,
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"خطأ في ربط الصفحات: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@textbook_bp.route('/<int:textbook_id>/pages', methods=['GET'])
@admin_required
def get_lesson_pages(textbook_id):
    """جلب ربط الصفحات لكتاب معين"""
    try:
        textbook = Textbook.query.get(textbook_id)
        if not textbook:
            return jsonify({'success': False, 'error': 'الكتاب غير موجود'}), 404

        pages = LessonPages.query.filter_by(textbook_id=textbook_id).all()
        return jsonify({
            'success': True,
            'data': {
                'textbook': textbook.to_dict(),
                'pages': [p.to_dict() for p in pages],
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== endpoint للمعلم =====

@textbook_bp.route('/lesson/<int:lesson_id>/pages', methods=['GET'])
def get_lesson_page_info(lesson_id):
    """جلب صفحات درس معين (للمعلم والأدمن)"""
    try:
        pages = LessonPages.query.filter_by(lesson_id=lesson_id).all()
        if not pages:
            return jsonify({
                'success': True,
                'data': [],
                'message': 'لا توجد صفحات مرتبطة بهذا الدرس'
            })

        result = []
        for p in pages:
            item = p.to_dict()
            item['textbook_title'] = p.textbook.title if p.textbook else None
            item['textbook_pdf_url'] = p.textbook.pdf_url if p.textbook else None
            result.append(item)

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@textbook_bp.route('/courses-with-textbooks', methods=['GET'])
def get_courses_with_textbooks():
    """جلب المقررات التي لها كتب مرفوعة مع الوحدات والدروس"""
    try:
        textbooks = Textbook.query.filter_by(is_active=True).all()
        course_ids = list(set(t.course_id for t in textbooks))

        courses = Course.query.filter(Course.id.in_(course_ids)).all() if course_ids else []

        result = []
        for course in courses:
            course_data = {
                'id': course.id,
                'name': course.name,
                'textbooks': [t.to_dict() for t in course.textbooks if t.is_active],
                'units': []
            }
            for unit in course.units:
                unit_data = {
                    'id': unit.id,
                    'name': unit.name,
                    'lessons': []
                }
                for lesson in unit.lessons:
                    lesson_data = {
                        'id': lesson.id,
                        'name': lesson.name,
                        'pages': [p.to_dict() for p in lesson.page_mappings] if lesson.page_mappings else []
                    }
                    unit_data['lessons'].append(lesson_data)
                course_data['units'].append(unit_data)
            result.append(course_data)

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
