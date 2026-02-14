"""
Blueprint لإدارة مواعيد الاختبار التحصيلي
يوفر APIs لإضافة وتعديل وحذف المواعيد المهمة
السنة متغيرة وليست ثابتة
✅ تحديث: error handling محسّن + debugging
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
import logging
import os
import traceback

logger = logging.getLogger(__name__)

exam_dates_bp = Blueprint('exam_dates', __name__, url_prefix='/admin/exam-dates')

# الحصول على Firestore client مع error handling محسّن
# ✅ يستخدم 'default' database تلقائياً (Database Name: default)
try:
    # محاولة الحصول على Firestore client
    # firestore.client() يتصل بـ database اسمه 'default' تلقائياً
    db = firestore.client()
    
    # ✅ اختبار الاتصال
    logger.info("🔍 Testing Firestore connection to 'default' database...")
    test_collection = db.collection('settings')
    
    # محاولة جلب document للتأكد من الاتصال
    try:
        test_doc = test_collection.document('exam_dates').get()
        logger.info(f"✅ Firestore connection successful! Document exists: {test_doc.exists}")
    except Exception as test_error:
        logger.warning(f"⚠️ Firestore connection test warning: {test_error}")
    
    FIRESTORE_AVAILABLE = True
    logger.info("✅ Firestore client initialized successfully")
    
except Exception as e:
    FIRESTORE_AVAILABLE = False
    logger.error(f"❌ Failed to initialize Firestore: {e}")
    logger.error(f"Error type: {type(e).__name__}")
    traceback.print_exc()
    
    # طباعة معلومات إضافية للـ debugging
    try:
        import firebase_admin
        apps = firebase_admin._apps
        logger.info(f"📱 Firebase apps initialized: {list(apps.keys())}")
    except:
        pass


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
            logger.error("❌ Firestore not available in get_all_dates")
            return jsonify({
                'success': False,
                'error': 'Firestore غير متاح - تحقق من الإعدادات'
            }), 500
        
        logger.info("📥 Attempting to fetch exam dates from Firestore...")
        
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
            logger.warning("⚠️ المستند exam_dates غير موجود في Firestore")
            # إرجاع بيانات افتراضية إذا لم يوجد المستند
            return jsonify({
                'success': True,
                'dates': {}
            })
    
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المواعيد: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'خطأ في الاتصال بقاعدة البيانات: {str(e)}'
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
            logger.error("❌ Firestore not available in update_dates")
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
        
        logger.info(f"📝 Updating exam dates with {len(data)} fields...")
        
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
                logger.warning(f"⚠️ Missing required field: {field}")
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
        logger.error(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'خطأ في الحفظ: {str(e)}'
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
        
        logger.info(f"🗑️ Deleting field: {field_name}")
        
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
        traceback.print_exc()
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
            logger.error("❌ Firestore not available in reset_to_defaults")
            return jsonify({
                'success': False,
                'error': 'Firestore غير متاح - لا يمكن إعادة التعيين'
            }), 500
        
        logger.info("🔄 Resetting exam dates to default values...")
        
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
        logger.error(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'خطأ في إعادة التعيين: {str(e)}'
        }), 500
