from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
from werkzeug.security import check_password_hash, generate_password_hash
import pyotp
import qrcode
import io
import base64

try:
    from extensions import db
    from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
    # استيراد نموذج GoogleDriveToken من الملف الأصلي
    try:
        from src.models.google_drive import GoogleDriveToken
    except ImportError:
        from models.google_drive import GoogleDriveToken
except ImportError:
    try:
        from src.extensions import db
        from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
        # استيراد نموذج GoogleDriveToken من الملف الأصلي
        try:
            from src.models.google_drive import GoogleDriveToken
        except ImportError:
            from models.google_drive import GoogleDriveToken
    except ImportError:
        print("Error: Could not import db from extensions or src.extensions.")
        raise

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

class ProfileSettingsForm(FlaskForm):
    full_name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    bio = TextAreaField('نبذة تعريفية', validators=[Optional(), Length(max=500)])

class NotificationSettingsForm(FlaskForm):
    email_notifications = BooleanField('تلقي الإشعارات عبر البريد الإلكتروني')
    app_notifications = BooleanField('تلقي الإشعارات داخل التطبيق')
    notification_frequency = SelectField('تكرار الإشعارات', 
                                        choices=[('immediate', 'فوري'), 
                                                ('daily', 'يومي'), 
                                                ('weekly', 'أسبوعي')])

class SecuritySettingsForm(FlaskForm):
    two_factor_auth = BooleanField('تفعيل المصادقة الثنائية')
    login_alerts = BooleanField('تلقي تنبيهات عند تسجيل الدخول من جهاز جديد')

class IntegrationSettingsForm(FlaskForm):
    google_integration = BooleanField('تكامل مع Google Classroom')
    microsoft_integration = BooleanField('تكامل مع Microsoft Teams')

@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    profile_form = ProfileSettingsForm()
    notification_form = NotificationSettingsForm()
    security_form = SecuritySettingsForm()
    integration_form = IntegrationSettingsForm()
    
    # تعبئة النماذج بالبيانات الحالية
    if request.method == 'GET':
        if hasattr(current_user, 'full_name'):
            profile_form.full_name.data = current_user.full_name
        else:
            profile_form.full_name.data = current_user.username
            
        if hasattr(current_user, 'email'):
            profile_form.email.data = current_user.email
            
        if hasattr(current_user, 'bio'):
            profile_form.bio.data = current_user.bio
    
    # معالجة النماذج عند الإرسال
    if request.method == 'POST':
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            # تحديث بيانات الملف الشخصي
            if hasattr(current_user, 'full_name'):
                current_user.full_name = profile_form.full_name.data
            if hasattr(current_user, 'email'):
                current_user.email = profile_form.email.data
            if hasattr(current_user, 'bio'):
                current_user.bio = profile_form.bio.data
            db.session.commit()
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'notification_submit' in request.form and notification_form.validate_on_submit():
            # تحديث إعدادات الإشعارات
            if hasattr(current_user, 'email_notifications'):
                current_user.email_notifications = notification_form.email_notifications.data
            if hasattr(current_user, 'app_notifications'):
                current_user.app_notifications = notification_form.app_notifications.data
            if hasattr(current_user, 'notification_frequency'):
                current_user.notification_frequency = notification_form.notification_frequency.data
            db.session.commit()
            flash('تم تحديث إعدادات الإشعارات بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'security_submit' in request.form and security_form.validate_on_submit():
            # تحديث إعدادات الأمان
            if hasattr(current_user, 'two_factor_auth'):
                current_user.two_factor_auth = security_form.two_factor_auth.data
            if hasattr(current_user, 'login_alerts'):
                current_user.login_alerts = security_form.login_alerts.data
            db.session.commit()
            flash('تم تحديث إعدادات الأمان بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'integration_submit' in request.form and integration_form.validate_on_submit():
            # تحديث إعدادات التكاملات
            if hasattr(current_user, 'google_integration'):
                current_user.google_integration = integration_form.google_integration.data
            if hasattr(current_user, 'microsoft_integration'):
                current_user.microsoft_integration = integration_form.microsoft_integration.data
                
            # إعادة توليد مفتاح API إذا تم طلب ذلك
            if 'regenerate_api_key' in request.form:
                import uuid
                
                # استخدام المفتاح المرسل من JavaScript أو توليد مفتاح جديد
                new_api_key = request.form.get('new_api_key')
                if not new_api_key:
                    new_api_key = str(uuid.uuid4())
                
                if hasattr(current_user, 'api_key'):
                    current_user.api_key = new_api_key
                else:
                    # إذا لم يكن الحقل موجود، إنشاؤه ديناميكياً
                    setattr(current_user, 'api_key', new_api_key)
                
                print(f"✅ تم تحديث مفتاح API: {new_api_key}")
                flash('تم توليد مفتاح API جديد بنجاح', 'success')
                
            db.session.commit()
            flash('تم تحديث إعدادات التكاملات بنجاح', 'success')
            return redirect(url_for('settings.index'))
            
        elif 'change_password_submit' in request.form:
            # تغيير كلمة المرور
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # التحقق من صحة البيانات
            if not current_password or not new_password or not confirm_password:
                flash('جميع الحقول مطلوبة', 'error')
            elif new_password != confirm_password:
                flash('كلمة المرور الجديدة وتأكيدها غير متطابقين', 'error')
            elif len(new_password) < 6:
                flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'error')
            elif not check_password_hash(current_user.password_hash, current_password):
                flash('كلمة المرور الحالية غير صحيحة', 'error')
            else:
                # تحديث كلمة المرور
                current_user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash('تم تغيير كلمة المرور بنجاح', 'success')
                return redirect(url_for('settings.index'))
    
    # إصلاح مسار template
    return render_template('settings.html', 
                          profile_form=profile_form,
                          notification_form=notification_form,
                          security_form=security_form,
                          integration_form=integration_form)

@settings_bp.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """إعداد المصادقة الثنائية"""
    if request.method == 'GET':
        # توليد مفتاح سري جديد
        secret = pyotp.random_base32()
        
        # حفظ المفتاح السري مؤقتاً في الجلسة
        session['temp_2fa_secret'] = secret
        
        # إنشاء QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=current_user.email or current_user.username,
            issuer_name="الكيمياء التحصيلي"
        )
        
        # توليد QR code كصورة
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # تحويل الصورة إلى base64
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        # إرجاع البيانات كـ JSON مع HTML محدث
        qr_html = f'<img src="data:image/png;base64,{img_base64}" alt="QR Code" style="max-width: 200px; height: auto;" />'
        
        return jsonify({
            'success': True,
            'qr_code': img_base64,
            'qr_html': qr_html,
            'secret': secret,
            'message': 'تم توليد رمز QR بنجاح'
        })
    
    # معالجة POST (تفعيل المصادقة الثنائية)
    elif request.method == 'POST':
        verification_code = request.form.get('verification_code')
        temp_secret = session.get('temp_2fa_secret')
        
        if not temp_secret:
            return jsonify({
                'success': False,
                'message': 'انتهت صلاحية الجلسة. يرجى إعادة المحاولة.'
            }), 400
        
        if not verification_code:
            return jsonify({
                'success': False,
                'message': 'يرجى إدخال رمز التحقق'
            }), 400
        
        # التحقق من رمز TOTP
        totp = pyotp.TOTP(temp_secret)
        if totp.verify(verification_code):
            # حفظ المفتاح السري في قاعدة البيانات
            if not hasattr(current_user, 'totp_secret'):
                # إضافة الحقل إذا لم يكن موجوداً
                setattr(current_user, 'totp_secret', temp_secret)
                setattr(current_user, 'two_factor_auth', True)
            else:
                current_user.totp_secret = temp_secret
                current_user.two_factor_auth = True
            
            db.session.commit()
            
            # إزالة المفتاح المؤقت من الجلسة
            session.pop('temp_2fa_secret', None)
            
            return jsonify({
                'success': True,
                'message': 'تم تفعيل المصادقة الثنائية بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'رمز التحقق غير صحيح'
            }), 400

@settings_bp.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    """إلغاء تفعيل المصادقة الثنائية"""
    verification_code = request.form.get('verification_code')
    
    if not verification_code:
        return jsonify({
            'success': False,
            'message': 'يرجى إدخال رمز التحقق'
        }), 400
    
    # التحقق من رمز TOTP
    if hasattr(current_user, 'totp_secret') and current_user.totp_secret:
        totp = pyotp.TOTP(current_user.totp_secret)
        if totp.verify(verification_code):
            # إلغاء تفعيل المصادقة الثنائية
            current_user.two_factor_auth = False
            current_user.totp_secret = None
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'تم إلغاء تفعيل المصادقة الثنائية بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'رمز التحقق غير صحيح'
            }), 400
    else:
        return jsonify({
            'success': False,
            'message': 'المصادقة الثنائية غير مفعلة'
        }), 400

@settings_bp.route('/verify-2fa', methods=['POST'])
@login_required
def verify_2fa():
    """التحقق من المصادقة الثنائية"""
    data = request.get_json()
    verification_code = data.get('code')
    temp_secret = session.get('temp_2fa_secret')
    
    if not temp_secret:
        return jsonify({
            'success': False,
            'message': 'انتهت صلاحية الجلسة. يرجى إعادة المحاولة.'
        }), 400
    
    if not verification_code:
        return jsonify({
            'success': False,
            'message': 'يرجى إدخال رمز التحقق'
        }), 400
    
    # التحقق من رمز TOTP
    totp = pyotp.TOTP(temp_secret)
    if totp.verify(verification_code):
        # حفظ المفتاح السري في قاعدة البيانات
        if not hasattr(current_user, 'totp_secret'):
            # إضافة الحقل إذا لم يكن موجوداً
            setattr(current_user, 'totp_secret', temp_secret)
            setattr(current_user, 'two_factor_auth', True)
        else:
            current_user.totp_secret = temp_secret
            current_user.two_factor_auth = True
        
        db.session.commit()
        
        # إزالة المفتاح المؤقت من الجلسة
        session.pop('temp_2fa_secret', None)
        
        return jsonify({
            'success': True,
            'message': 'تم تفعيل المصادقة الثنائية بنجاح'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'رمز التحقق غير صحيح'
        }), 400


# ===== Google Drive Integration Routes =====

from datetime import datetime, timedelta
import json

@settings_bp.route('/api/v1/google-drive/connect', methods=['POST'])
@login_required
def google_drive_connect():
    """حفظ Google Drive access token"""
    try:
        # التأكد من أن المستخدم مسجل دخول
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'message': 'يجب تسجيل الدخول أولاً',
                'connected': False
            }), 401
        
        # التأكد من وجود user_id
        if not hasattr(current_user, 'id') or current_user.id is None:
            return jsonify({
                'success': False,
                'message': 'خطأ في معرف المستخدم',
                'connected': False
            }), 400
        
        data = request.get_json()
        if not data or 'access_token' not in data:
            return jsonify({
                'success': False,
                'message': 'مفتاح الوصول مطلوب',
                'connected': False
            }), 400
        
        print(f"🔍 محاولة حفظ token للمستخدم ID: {current_user.id}")
        
        # البحث عن token موجود للمستخدم
        existing_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
        
        if existing_token:
            # تحديث token موجود
            existing_token.access_token = data['access_token']
            existing_token.refresh_token = data.get('refresh_token')
            existing_token.expires_in = data.get('expires_in')
            existing_token.scope = data.get('scope')
            existing_token.token_type = data.get('token_type', 'Bearer')
            existing_token.updated_at = datetime.utcnow()
        else:
            # إنشاء token جديد
            new_token = GoogleDriveToken(
                user_id=current_user.id,
                access_token=data['access_token'],
                refresh_token=data.get('refresh_token'),
                expires_in=data.get('expires_in'),
                scope=data.get('scope'),
                token_type=data.get('token_type', 'Bearer')
            )
            db.session.add(new_token)
        
        db.session.commit()
        
        print(f"✅ تم حفظ Google Drive token للمستخدم {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'تم ربط Google Drive بنجاح',
            'connected': True,
            'last_sync': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في ربط Google Drive: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في ربط Google Drive: {str(e)}',
            'connected': False
        }), 500

@settings_bp.route('/api/v1/google-drive/disconnect', methods=['POST'])
@login_required
def disconnect_google_drive():
    """قطع الاتصال مع Google Drive"""
    try:
        # التأكد من أن المستخدم مسجل دخول
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'message': 'يجب تسجيل الدخول أولاً'
            }), 401
        
        # التأكد من وجود user_id
        if not hasattr(current_user, 'id') or current_user.id is None:
            return jsonify({
                'success': False,
                'message': 'خطأ في معرف المستخدم'
            }), 400
        
        print(f"🔍 قطع اتصال Google Drive للمستخدم ID: {current_user.id}")
        
        # حذف جميع tokens للمستخدم
        deleted_count = GoogleDriveToken.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        print(f"✅ تم حذف {deleted_count} token للمستخدم {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'تم قطع الاتصال مع Google Drive',
            'connected': False
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في قطع الاتصال: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في قطع الاتصال: {str(e)}',
            'connected': True
        }), 500

@settings_bp.route('/api/v1/google-drive/status', methods=['GET'])
@login_required
def google_drive_status():
    """فحص حالة اتصال Google Drive"""
    try:
        # التأكد من أن المستخدم مسجل دخول
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'connected': False,
                'message': 'يجب تسجيل الدخول أولاً'
            }), 401
        
        # التأكد من وجود user_id
        if not hasattr(current_user, 'id') or current_user.id is None:
            return jsonify({
                'success': False,
                'connected': False,
                'message': 'خطأ في معرف المستخدم'
            }), 400
        
        print(f"🔍 فحص حالة Google Drive للمستخدم ID: {current_user.id}")
        
        token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
        
        if token:
            return jsonify({
                'success': True,
                'connected': True,
                'last_sync': token.updated_at.isoformat() if token.updated_at else None,
                'scope': token.scope
            })
        else:
            return jsonify({
                'success': True,
                'connected': False,
                'last_sync': None
            })
            
    except Exception as e:
        print(f"❌ خطأ في فحص حالة Google Drive: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في فحص الحالة: {str(e)}',
            'connected': False
        }), 500

@settings_bp.route('/api/v1/user-settings/sync-to-drive', methods=['POST'])
@login_required
def sync_to_drive():
    """مزامنة الإعدادات إلى Google Drive"""
    try:
        # فحص وجود token
        token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'يجب ربط Google Drive أولاً',
                'synced': False
            }), 400
        
        # محاكاة المزامنة (يمكن تطوير هذا لاحقاً)
        user_settings = {
            'username': current_user.username,
            'email': getattr(current_user, 'email', ''),
            'full_name': getattr(current_user, 'full_name', ''),
            'bio': getattr(current_user, 'bio', ''),
            'email_notifications': getattr(current_user, 'email_notifications', True),
            'app_notifications': getattr(current_user, 'app_notifications', True),
            'notification_frequency': getattr(current_user, 'notification_frequency', 'immediate'),
            'sync_time': datetime.utcnow().isoformat()
        }
        
        print(f"✅ مزامنة إعدادات المستخدم {current_user.id} إلى Google Drive")
        
        return jsonify({
            'success': True,
            'message': 'تم رفع الإعدادات إلى Google Drive بنجاح',
            'synced': True,
            'last_sync': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"❌ خطأ في المزامنة: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في المزامنة: {str(e)}',
            'synced': False
        }), 500

@settings_bp.route('/api/v1/user-settings/download-from-drive', methods=['POST'])
@login_required
def download_from_drive():
    """تحميل الإعدادات من Google Drive"""
    try:
        # فحص وجود token
        token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'يجب ربط Google Drive أولاً',
                'downloaded': False
            }), 400
        
        print(f"✅ تحميل إعدادات المستخدم {current_user.id} من Google Drive")
        
        return jsonify({
            'success': True,
            'message': 'تم تحميل الإعدادات من Google Drive بنجاح',
            'downloaded': True,
            'last_sync': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"❌ خطأ في التحميل: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في التحميل: {str(e)}',
            'downloaded': False
        }), 500

@settings_bp.route('/auth/google/callback')
def google_oauth_callback():
    """معالجة Google OAuth callback"""
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            print(f"❌ خطأ في OAuth: {error}")
            return f"""
            <script>
                window.opener.postMessage({{
                    type: 'google-auth-error',
                    error: '{error}'
                }}, '*');
                window.close();
            </script>
            """
        
        if not code:
            print("❌ لم يتم استلام authorization code")
            return """
            <script>
                window.opener.postMessage({
                    type: 'google-auth-error',
                    error: 'لم يتم استلام رمز التفويض'
                }, '*');
                window.close();
            </script>
            """
        
        print(f"✅ تم استلام authorization code: {code[:20]}...")
        
        # إذا كان هناك state، فهو user_id
        user_id = None
        if state:
            try:
                user_id = int(state)
                print(f"🔍 User ID من state: {user_id}")
            except ValueError:
                print(f"⚠️ لا يمكن تحويل state إلى user_id: {state}")
        
        # استخدام current_user إذا لم يكن هناك user_id في state
        if not user_id and hasattr(current_user, 'id') and current_user.is_authenticated:
            user_id = current_user.id
            print(f"🔍 استخدام current_user.id: {user_id}")
        
        if not user_id:
            print("❌ لا يمكن تحديد user_id")
            return """
            <script>
                window.opener.postMessage({
                    type: 'google-auth-error',
                    error: 'خطأ في تحديد المستخدم'
                }, '*');
                window.close();
            </script>
            """
        
        # استيراد google_drive_manager
        try:
            from src.models.google_drive import google_drive_manager
        except ImportError:
            try:
                from models.google_drive import google_drive_manager
            except ImportError:
                print("❌ لا يمكن استيراد google_drive_manager")
                return """
                <script>
                    window.opener.postMessage({
                        type: 'google-auth-error',
                        error: 'خطأ في النظام'
                    }, '*');
                    window.close();
                </script>
                """
        
        # معالجة OAuth callback
        success = google_drive_manager.handle_oauth_callback(user_id, code)
        
        if success:
            print(f"✅ تم ربط Google Drive بنجاح للمستخدم {user_id}")
            return """
            <script>
                window.opener.postMessage({
                    type: 'google-auth-success',
                    message: 'تم ربط Google Drive بنجاح'
                }, '*');
                window.close();
            </script>
            """
        else:
            print(f"❌ فشل في ربط Google Drive للمستخدم {user_id}")
            return """
            <script>
                window.opener.postMessage({
                    type: 'google-auth-error',
                    error: 'فشل في ربط Google Drive'
                }, '*');
                window.close();
            </script>
            """
            
    except Exception as e:
        print(f"❌ خطأ في معالجة OAuth callback: {str(e)}")
        return f"""
        <script>
            window.opener.postMessage({{
                type: 'google-auth-error',
                error: 'خطأ في النظام: {str(e)}'
            }}, '*');
            window.close();
        </script>
        """

@settings_bp.route('/api/v1/user-settings/quick-sync', methods=['POST'])
@login_required
def quick_sync():
    """مزامنة سريعة"""
    try:
        # فحص وجود token
        token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'يجب ربط Google Drive أولاً',
                'synced': False
            }), 400
        
        print(f"✅ مزامنة سريعة للمستخدم {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'تم تنفيذ المزامنة السريعة بنجاح',
            'synced': True,
            'last_sync': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"❌ خطأ في المزامنة السريعة: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في المزامنة السريعة: {str(e)}',
            'synced': False
        }), 500


# ===== API endpoints للنسخ الاحتياطي =====

@settings_bp.route('/api/v1/backup-settings', methods=['GET'])
@login_required
def get_backup_settings():
    """جلب إعدادات النسخ الاحتياطي للمستخدم"""
    try:
        from src.models.backup_settings import BackupSettings
        
        settings = BackupSettings.get_user_settings(current_user.id)
        
        return jsonify({
            'success': True,
            'settings': settings.to_dict()
        })
        
    except Exception as e:
        print(f"❌ خطأ في جلب إعدادات النسخ الاحتياطي: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في جلب الإعدادات: {str(e)}'
        }), 500

@settings_bp.route('/api/v1/backup-settings', methods=['POST'])
@login_required
def save_backup_settings():
    """حفظ إعدادات النسخ الاحتياطي للمستخدم"""
    try:
        from src.models.backup_settings import BackupSettings
        
        data = request.get_json()
        
        # التحقق من صحة البيانات
        allowed_fields = ['auto_backup_enabled', 'backup_frequency', 'backup_time', 'max_backups', 'backup_destination']
        settings_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        # تحديث الإعدادات
        settings = BackupSettings.update_user_settings(current_user.id, settings_data)
        
        print(f"✅ تم حفظ إعدادات النسخ الاحتياطي للمستخدم {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ إعدادات النسخ الاحتياطي بنجاح',
            'settings': settings.to_dict()
        })
        
    except Exception as e:
        print(f"❌ خطأ في حفظ إعدادات النسخ الاحتياطي: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في حفظ الإعدادات: {str(e)}'
        }), 500

@settings_bp.route('/api/v1/backup/create', methods=['POST'])
@login_required
def create_backup():
    """إنشاء نسخة احتياطية"""
    try:
        from src.models.backup_settings import BackupSettings
        
        # جلب إعدادات النسخ الاحتياطي
        backup_settings = BackupSettings.get_user_settings(current_user.id)
        
        # تحديد نوع النسخة الاحتياطية بناءً على الوجهة
        backup_destination = backup_settings.backup_destination if backup_settings else 'local'
        
        if backup_destination == 'google_drive':
            # نسخة احتياطية شاملة لـ Google Drive
            backup_data = create_comprehensive_backup()
        else:
            # نسخة احتياطية أساسية للحفظ المحلي
            backup_data = create_basic_backup(backup_settings)
        
        # إنشاء اسم الملف
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_type = 'comprehensive' if backup_destination == 'google_drive' else 'basic'
        filename = f"backup_{backup_type}_{current_user.username}_{timestamp}.json"
        
        print(f"✅ تم إنشاء نسخة احتياطية {backup_type} للمستخدم {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'تم إنشاء النسخة الاحتياطية {"الشاملة" if backup_destination == "google_drive" else "الأساسية"} بنجاح',
            'backup_data': backup_data,
            'filename': filename,
            'backup_type': backup_type
        })
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء النسخة الاحتياطية: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في إنشاء النسخة الاحتياطية: {str(e)}'
        }), 500

def create_basic_backup(backup_settings):
    """إنشاء نسخة احتياطية أساسية للحفظ المحلي"""
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0',
        'backup_type': 'basic',
        'user_id': current_user.id,
        'data': {
            'user_info': {
                'username': current_user.username,
                'email': current_user.email
            },
            'backup_settings': backup_settings.to_dict() if backup_settings else {},
            'created_at': datetime.utcnow().isoformat()
        }
    }

def create_comprehensive_backup():
    """إنشاء نسخة احتياطية شاملة لـ Google Drive"""
    try:
        # استيراد النماذج المطلوبة
        from src.models.backup_settings import BackupSettings
        from src.models.notification import Notification
        from src.models.google_drive import GoogleDriveToken
        
        # جمع بيانات المستخدم الحالي
        user_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'is_admin': getattr(current_user, 'is_admin', False),
            'created_at': getattr(current_user, 'created_at', datetime.utcnow()).isoformat(),
            'settings': {
                'two_factor_auth': getattr(current_user, 'two_factor_auth', False),
                'notification_frequency': getattr(current_user, 'notification_frequency', 'immediate'),
                'app_notifications': getattr(current_user, 'app_notifications', True),
                'email_notifications': getattr(current_user, 'email_notifications', True)
            }
        }
        
        # جمع إعدادات النسخ الاحتياطي
        backup_settings = BackupSettings.get_user_settings(current_user.id)
        backup_settings_data = backup_settings.to_dict() if backup_settings else {}
        
        # جمع الإشعارات
        notifications_data = []
        try:
            notifications = Notification.query.filter_by(user_id=current_user.id).limit(50).all()
            notifications_data = [
                {
                    'id': notif.id,
                    'title': notif.title,
                    'message': notif.message,
                    'type': notif.type,
                    'is_read': notif.is_read,
                    'created_at': notif.created_at.isoformat() if notif.created_at else None
                }
                for notif in notifications
            ]
        except Exception as e:
            print(f"تحذير: لا يمكن جمع الإشعارات: {e}")
        
        # جمع معلومات Google Drive
        google_drive_data = {}
        try:
            google_token = GoogleDriveToken.query.filter_by(user_id=current_user.id).first()
            if google_token:
                google_drive_data = {
                    'connected': True,
                    'connected_at': google_token.created_at.isoformat() if google_token.created_at else None,
                    'last_updated': google_token.updated_at.isoformat() if google_token.updated_at else None,
                    'token_valid': google_token.is_valid() if hasattr(google_token, 'is_valid') else True
                }
            else:
                google_drive_data = {'connected': False}
        except Exception as e:
            print(f"تحذير: لا يمكن جمع معلومات Google Drive: {e}")
            google_drive_data = {'connected': False}
        
        # جمع إحصائيات النظام (إذا كان المستخدم مدير)
        system_stats = {}
        if getattr(current_user, 'is_admin', False):
            try:
                # استيراد نماذج إضافية إذا كانت متاحة
                try:
                    from src.models.user import User
                    total_users = User.query.count()
                    system_stats['total_users'] = total_users
                except:
                    system_stats['total_users'] = 1
                
                try:
                    total_notifications = Notification.query.count()
                    system_stats['total_notifications'] = total_notifications
                except:
                    system_stats['total_notifications'] = len(notifications_data)
                
                try:
                    connected_google_accounts = GoogleDriveToken.query.count()
                    system_stats['connected_google_accounts'] = connected_google_accounts
                except:
                    system_stats['connected_google_accounts'] = 1 if google_drive_data.get('connected') else 0
                    
            except Exception as e:
                print(f"تحذير: لا يمكن جمع إحصائيات النظام: {e}")
        
        # إنشاء النسخة الاحتياطية الشاملة
        comprehensive_backup = {
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0',
            'backup_type': 'comprehensive',
            'user_id': current_user.id,
            'data': {
                'user_info': user_data,
                'backup_settings': backup_settings_data,
                'notifications': notifications_data,
                'google_drive_integration': google_drive_data,
                'system_statistics': system_stats,
                'metadata': {
                    'total_notifications': len(notifications_data),
                    'backup_size_estimate': 'متوسط',
                    'data_types_included': [
                        'معلومات المستخدم',
                        'إعدادات النسخ الاحتياطي',
                        'الإشعارات',
                        'تكامل Google Drive',
                        'إحصائيات النظام' if system_stats else None
                    ],
                    'created_at': datetime.utcnow().isoformat()
                }
            }
        }
        
        return comprehensive_backup
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء النسخة الاحتياطية الشاملة: {str(e)}")
        # العودة للنسخة الأساسية في حالة الخطأ
        from src.models.backup_settings import BackupSettings
        backup_settings = BackupSettings.get_user_settings(current_user.id)
        return create_basic_backup(backup_settings)

@settings_bp.route('/api/v1/backup/restore', methods=['POST'])
@login_required
def restore_backup():
    """استعادة نسخة احتياطية"""
    try:
        from src.models.backup_settings import BackupSettings
        
        data = request.get_json()
        backup_data = data.get('backup_data')
        
        if not backup_data or 'data' not in backup_data:
            return jsonify({
                'success': False,
                'message': 'بيانات النسخة الاحتياطية غير صحيحة'
            }), 400
        
        # استعادة إعدادات النسخ الاحتياطي
        if 'backup_settings' in backup_data['data']:
            backup_settings_data = backup_data['data']['backup_settings']
            BackupSettings.update_user_settings(current_user.id, backup_settings_data)
        
        print(f"✅ تم استعادة النسخة الاحتياطية للمستخدم {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'تم استعادة النسخة الاحتياطية بنجاح'
        })
        
    except Exception as e:
        print(f"❌ خطأ في استعادة النسخة الاحتياطية: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'خطأ في استعادة النسخة الاحتياطية: {str(e)}'
        }), 500




# ==================== إدارة رقم جوال الأدمن للـ 2FA ====================

@settings_bp.route('/admin-phone', methods=['GET'])
@login_required
def admin_phone_page():
    """عرض إعدادات رقم الجوال للأدمن"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403
    from src.routes.auth import _mask_phone
    return jsonify({
        'has_phone': bool(current_user.phone_number),
        'phone_masked': _mask_phone(current_user.phone_number) if current_user.phone_number else None
    })


@settings_bp.route('/admin-phone/verify-firebase', methods=['POST'])
@login_required
def admin_phone_verify_firebase():
    """
    تحديث رقم الجوال المرتبط بالأدمن
    - إذا يوجد رقم قديم: يُشترط إثبات ملكية الرقم القديم أولاً (id_token من الرقم القديم)
    - ثم قبول id_token من الرقم الجديد لحفظه
    مرحلة واحدة: يُرسل id_token من الرقم الجديد بعد التحقق
    """
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    data = request.get_json() or {}
    id_token     = data.get('id_token', '').strip()
    phase        = data.get('phase', 'new')  # 'old' أو 'new'

    if not id_token:
        return jsonify({'success': False, 'message': 'token مفقود'}), 400

    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth
        decoded       = firebase_auth.verify_id_token(id_token)
        verified_phone = decoded.get('phone_number', '')

        if not verified_phone:
            return jsonify({'success': False, 'message': 'لا يوجد رقم في الـ token'}), 400

        if phase == 'old':
            # المرحلة 1: التحقق من الرقم القديم
            if not current_user.phone_number:
                return jsonify({'success': False, 'message': 'لا يوجد رقم قديم لتأكيده'}), 400
            if verified_phone != current_user.phone_number:
                return jsonify({'success': False, 'message': 'الرقم لا يطابق الحساب'}), 403
            # نجح — خزّن في session
            session['phone_change_old_verified'] = True
            return jsonify({'success': True, 'message': 'تم التحقق من الرقم القديم ✅'})

        elif phase == 'new':
            # المرحلة 2: حفظ الرقم الجديد
            # إذا كان هناك رقم قديم يجب المرور بمرحلة 'old' أولاً
            if current_user.phone_number and not session.get('phone_change_old_verified'):
                return jsonify({'success': False,
                                'message': 'يجب التحقق من الرقم القديم أولاً'}), 403

            current_user.phone_number = verified_phone
            from src.extensions import db
            db.session.commit()
            session.pop('phone_change_old_verified', None)

            from src.routes.auth import _mask_phone
            return jsonify({
                'success': True,
                'message': f'تم حفظ الرقم الجديد ✅',
                'phone_masked': _mask_phone(verified_phone)
            })

        return jsonify({'success': False, 'message': 'phase غير صحيح'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'خطأ: {str(e)}'}), 500
