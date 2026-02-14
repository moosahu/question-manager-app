"""
Blueprint لإدارة مواعيد الاختبار التحصيلي
يوفر APIs لإضافة وتعديل وحذف المواعيد المهمة
السنة متغيرة وليست ثابتة
✅ إصلاح: استخدام database_id='(default)' للاتصال بـ Firestore
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)

exam_dates_bp = Blueprint('exam_dates', __name__, url_prefix='/admin/exam-dates')

# ✅ الحصول على Firestore client مع تحديد database بشكل صريح
try:
    db = firestore.client(database_id='(default)')
    FIRESTORE_AVAILABLE = True
    logger.info("✅ Firestore client initialized successfully with database (default)")
except Exception as e:
    FIRESTORE_AVAILABLE = False
    logger.error(f"❌ Failed to initialize Firestore: {e}")


# ==================== عرض صفحة الإدارة ====================

@exam_dates_bp.route('/')
@login_required
def index():
    """صفحة إدارة مواعيد الاختبار"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        return "غير مصرح", 403
    
    return render_template('admin/exam_dates.html')


# ==================== API: جلب جميع المواعيد ====================

@exam_dates_bp.route('/api/dates', methods=['GET'])
@login_required
def get_all_dates():
    """جلب جميع المواعيد المخزنة في Firestore"""
    try:
        if not FIRESTORE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Firestore غير متاح'
            }), 500
        
        # جلب المستند من Firestore
        doc_ref = db.collection('settings').document('exam_dates')
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            logger.info(f"✅ تم جلب المواعيد بنجاح: {len(data)} حقل")
            return jsonify({
                'success': True,
                'dates': data
            })
        else:
            logger.warning("⚠️ المستند exam_dates غير موجود")
            # إرجاع بيانات افتراضية إذا لم يوجد المستند
            return jsonify({
                'success': True,
                'dates': {}
            })
    
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المواعيد: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== API: تحديث/إضافة موعد ====================

@exam_dates_bp.route('/api/dates', methods=['POST'])
@login_required
def update_dates():
    """تحديث أو إضافة مواعيد الاختبار"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية'
            }), 403
        
        if not FIRESTORE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Firestore غير متاح'
            }), 500
        
        # استقبال البيانات من الطلب
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'لا توجد بيانات'
            }), 400
        
        # التحقق من صحة التواريخ
        required_fields = [
            'exam_year',
            'registration_start_male',
            'registration_end_male',
            'registration_start_female',
            'registration_end_female',
            'exam_period1_start',
            'exam_period1_end',
            'exam_period2_start',
            'exam_period2_end'
        ]
        
        # التحقق من وجود الحقول المطلوبة
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'الحقل {field} مطلوب'
                }), 400
        
        # إضافة معلومات التحديث
        data['last_updated'] = datetime.now().isoformat()
        data['updated_by'] = current_user.username
        
        # حفظ البيانات في Firestore
        doc_ref = db.collection('settings').document('exam_dates')
        doc_ref.set(data, merge=True)
        
        logger.info(f"✅ تم تحديث مواعيد الاختبار بواسطة {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ المواعيد بنجاح',
            'dates': data
        })
    
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث المواعيد: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== API: حذف موعد معين ====================

@exam_dates_bp.route('/api/dates/<field_name>', methods=['DELETE'])
@login_required
def delete_date(field_name):
    """حذف موعد معين"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية'
            }), 403
        
        if not FIRESTORE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Firestore غير متاح'
            }), 500
        
        # حذف الحقل من Firestore
        doc_ref = db.collection('settings').document('exam_dates')
        doc_ref.update({
            field_name: firestore.DELETE_FIELD
        })
        
        logger.info(f"✅ تم حذف الموعد {field_name} بواسطة {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'تم حذف {field_name} بنجاح'
        })
    
    except Exception as e:
        logger.error(f"❌ خطأ في حذف الموعد: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== API: إعادة تعيين إلى القيم الافتراضية ====================

@exam_dates_bp.route('/api/dates/reset', methods=['POST'])
@login_required
def reset_to_defaults():
    """إعادة تعيين المواعيد إلى القيم الافتراضية من الصورة"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': 'ليس لديك صلاحية'
            }), 403
        
        if not FIRESTORE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Firestore غير متاح'
            }), 500
        
        # القيم الافتراضية من الصورة
        default_dates = {
            # السنة (متغيرة)
            'exam_year': '2026',
            'exam_name': 'الاختبار التحصيلي الدراسي للفترتين',
            
            # مواعيد التسجيل
            'registration_start_male': '2026-02-23T00:00:00',  # 23 فبراير 2026 (الطلاب)
            'registration_end_male': '2026-03-02T23:59:59',    # 2 مارس 2026 (الطلاب)
            'registration_start_female': '2026-02-23T00:00:00', # 23 فبراير 2026 (الطالبات)
            'registration_end_female': '2026-03-02T23:59:59',   # 2 مارس 2026 (الطالبات)
            
            # فترات الاختبار
            'exam_period1_start': '2026-05-13T00:00:00',  # 13 مايو (الفترة الأولى - بداية)
            'exam_period1_end': '2026-05-17T23:59:59',    # 17 مايو (الفترة الأولى - نهاية)
            'exam_period2_start': '2026-06-05T00:00:00',  # 5 يونيو (الفترة الثانية - بداية)
            'exam_period2_end': '2026-06-09T23:59:59',    # 9 يونيو (الفترة الثانية - نهاية)
            
            # معلومات إضافية
            'last_updated': datetime.now().isoformat(),
            'updated_by': current_user.username,
            'is_default': True
        }
        
        # حفظ في Firestore
        doc_ref = db.collection('settings').document('exam_dates')
        doc_ref.set(default_dates)
        
        logger.info(f"✅ تم إعادة تعيين المواعيد للقيم الافتراضية بواسطة {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'تم إعادة تعيين المواعيد بنجاح',
            'dates': default_dates
        })
    
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة التعيين: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
