"""
خدمة إرسال الإيميل - Email Service
لإرسال رموز التحقق للطلاب
متوافق مع Brevo (SendinBlue) SMTP
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


class EmailService:
    """خدمة إرسال الإيميلات"""
    
    def __init__(self, app=None):
        self.mail_server = None
        self.mail_port = None
        self.mail_username = None
        self.mail_password = None
        self.mail_sender_name = None
        self.mail_sender_email = None  # ✅ إضافة إيميل المرسل
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """تهيئة الخدمة مع التطبيق"""
        self.mail_server = app.config.get('MAIL_SERVER', 'smtp-relay.brevo.com')
        self.mail_port = app.config.get('MAIL_PORT', 587)
        self.mail_username = app.config.get('MAIL_USERNAME')
        self.mail_password = app.config.get('MAIL_PASSWORD')
        self.mail_sender_name = app.config.get('MAIL_SENDER_NAME', 'كيم تحصيلي')
        # ✅ إيميل المرسل (لازم يكون مُفعّل في Brevo)
        self.mail_sender_email = app.config.get('MAIL_DEFAULT_SENDER', self.mail_username)
        
        # ✅ طباعة حالة الإعدادات للتشخيص
        print(f"📧 Email Service Configuration:")
        print(f"   Server: {self.mail_server}:{self.mail_port}")
        print(f"   Username: {self.mail_username}")
        print(f"   Password: {'✅ Set' if self.mail_password else '❌ NOT SET'}")
        print(f"   Sender: {self.mail_sender_name} <{self.mail_sender_email}>")
    
    def send_password_reset_code(self, to_email, code, student_name):
        """إرسال رمز إعادة تعيين كلمة المرور"""
        try:
            subject = f'إعادة تعيين كلمة المرور - كيم تحصيلي'
            
            # محتوى HTML للإيميل
            html_content = f'''
            <!DOCTYPE html>
            <html dir="rtl" lang="ar">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
                        background-color: #f5f7fa;
                        margin: 0;
                        padding: 20px;
                        direction: rtl;
                    }}
                    .container {{
                        max-width: 500px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 16px;
                        overflow: hidden;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        text-align: center;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                    }}
                    .content {{
                        padding: 30px;
                        text-align: center;
                    }}
                    .greeting {{
                        font-size: 18px;
                        color: #333;
                        margin-bottom: 20px;
                    }}
                    .code-box {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        font-size: 36px;
                        font-weight: bold;
                        letter-spacing: 12px;
                        padding: 20px 30px;
                        border-radius: 12px;
                        display: inline-block;
                        margin: 20px 0;
                    }}
                    .note {{
                        color: #666;
                        font-size: 14px;
                        margin-top: 20px;
                    }}
                    .warning {{
                        background: #fff3cd;
                        color: #856404;
                        padding: 12px;
                        border-radius: 8px;
                        margin-top: 20px;
                        font-size: 13px;
                    }}
                    .security-note {{
                        background: #e3f2fd;
                        color: #1565c0;
                        padding: 12px;
                        border-radius: 8px;
                        margin-top: 15px;
                        font-size: 13px;
                        border: 1px solid #90caf9;
                    }}
                    .footer {{
                        background: #f8f9fa;
                        padding: 20px;
                        text-align: center;
                        color: #666;
                        font-size: 12px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 كيم تحصيلي</h1>
                    </div>
                    <div class="content">
                        <p class="greeting">مرحباً {student_name} 👋</p>
                        <p>تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بك</p>
                        <p>رمز إعادة التعيين هو:</p>
                        <div class="code-box">{code}</div>
                        <p class="note">أدخل هذا الرمز في التطبيق لإعادة تعيين كلمة المرور</p>
                        <div class="warning">
                            ⚠️ هذا الرمز صالح لمدة <strong>10 دقائق</strong> فقط
                        </div>
                        <div class="security-note">
                            🔒 إذا لم تطلب إعادة تعيين كلمة المرور، تجاهل هذا الإيميل وتأكد من أمان حسابك
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2024 كيم تحصيلي - جميع الحقوق محفوظة</p>
                    </div>
                </div>
            </body>
            </html>
            '''
            
            # محتوى نصي بديل
            text_content = f'''
            مرحباً {student_name}
            
            تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بك
            
            رمز إعادة التعيين: {code}
            
            أدخل هذا الرمز في التطبيق لإعادة تعيين كلمة المرور.
            
            ⚠️ هذا الرمز صالح لمدة 10 دقائق فقط
            
            🔒 إذا لم تطلب إعادة تعيين كلمة المرور، تجاهل هذا الإيميل.
            
            --
            كيم تحصيلي
            '''
            
            return self._send_email(to_email, subject, text_content, html_content)
            
        except Exception as e:
            print(f"❌ خطأ في إرسال رمز إعادة التعيين: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def send_verification_code(self, to_email, code, student_name):
        """إرسال رمز التحقق للطالب"""
        try:
            subject = f'رمز التحقق - كيم تحصيلي'
            
            # محتوى HTML للإيميل
            html_content = f'''
            <!DOCTYPE html>
            <html dir="rtl" lang="ar">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
                        background-color: #f5f7fa;
                        margin: 0;
                        padding: 20px;
                        direction: rtl;
                    }}
                    .container {{
                        max-width: 500px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 16px;
                        overflow: hidden;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        text-align: center;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                    }}
                    .content {{
                        padding: 30px;
                        text-align: center;
                    }}
                    .greeting {{
                        font-size: 18px;
                        color: #333;
                        margin-bottom: 20px;
                    }}
                    .code-box {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        font-size: 36px;
                        font-weight: bold;
                        letter-spacing: 12px;
                        padding: 20px 30px;
                        border-radius: 12px;
                        display: inline-block;
                        margin: 20px 0;
                    }}
                    .note {{
                        color: #666;
                        font-size: 14px;
                        margin-top: 20px;
                    }}
                    .warning {{
                        background: #fff3cd;
                        color: #856404;
                        padding: 12px;
                        border-radius: 8px;
                        margin-top: 20px;
                        font-size: 13px;
                    }}
                    .footer {{
                        background: #f8f9fa;
                        padding: 20px;
                        text-align: center;
                        color: #666;
                        font-size: 12px;
                    }}
                    .spam-notice {{
                        background: #e3f2fd;
                        color: #1565c0;
                        padding: 12px;
                        border-radius: 8px;
                        margin-top: 15px;
                        font-size: 13px;
                        border: 1px solid #90caf9;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🧪 كيم تحصيلي</h1>
                    </div>
                    <div class="content">
                        <p class="greeting">مرحباً {student_name} 👋</p>
                        <p>رمز التحقق الخاص بك هو:</p>
                        <div class="code-box">{code}</div>
                        <p class="note">أدخل هذا الرمز في التطبيق لإكمال التسجيل</p>
                        <div class="warning">
                            ⚠️ هذا الرمز صالح لمدة <strong>3 دقائق</strong> فقط
                        </div>
                        <div class="spam-notice">
                            📬 لم تجد الرسالة؟ تحقق من مجلد <strong>الرسائل غير المرغوب فيها (Spam)</strong>
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2024 كيم تحصيلي - جميع الحقوق محفوظة</p>
                        <p>إذا لم تطلب هذا الرمز، تجاهل هذا الإيميل</p>
                    </div>
                </div>
            </body>
            </html>
            '''
            
            # محتوى نصي بديل
            text_content = f'''
            مرحباً {student_name}
            
            رمز التحقق الخاص بك هو: {code}
            
            أدخل هذا الرمز في التطبيق لإكمال التسجيل.
            
            ⚠️ هذا الرمز صالح لمدة 3 دقائق فقط
            
            📬 لم تجد الرسالة؟ تحقق من مجلد الرسائل غير المرغوب فيها (Spam)
            
            --
            كيم تحصيلي
            '''
            
            return self._send_email(to_email, subject, text_content, html_content)
            
        except Exception as e:
            print(f"❌ خطأ في إرسال رمز التحقق: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def _send_email(self, to_email, subject, text_content, html_content=None):
        """إرسال الإيميل"""
        try:
            # ✅ التحقق من الإعدادات
            if not self.mail_username:
                print("❌ MAIL_USERNAME غير محدد")
                return False, 'إعدادات الإيميل غير مكتملة - MAIL_USERNAME مفقود'
            
            if not self.mail_password:
                print("❌ MAIL_PASSWORD غير محدد")
                return False, 'إعدادات الإيميل غير مكتملة - MAIL_PASSWORD مفقود'
            
            # إنشاء الرسالة
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            # ✅ استخدام إيميل المرسل المُفعّل في Brevo
            msg['From'] = f'{self.mail_sender_name} <{self.mail_sender_email}>'
            msg['To'] = to_email
            
            # إضافة المحتوى النصي
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(part1)
            
            # إضافة محتوى HTML إن وجد
            if html_content:
                part2 = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(part2)
            
            print(f"📤 جاري الاتصال بـ {self.mail_server}:{self.mail_port}...")
            
            # الاتصال بالسيرفر وإرسال الإيميل
            with smtplib.SMTP(self.mail_server, self.mail_port, timeout=30) as server:
                server.set_debuglevel(1)  # ✅ تفعيل التشخيص
                print("📤 جاري تفعيل TLS...")
                server.starttls()
                print(f"📤 جاري تسجيل الدخول بـ {self.mail_username}...")
                server.login(self.mail_username, self.mail_password)
                print(f"📤 جاري إرسال الإيميل إلى {to_email}...")
                server.sendmail(self.mail_sender_email, to_email, msg.as_string())
            
            print(f"✅ تم إرسال الإيميل إلى {to_email}")
            return True, 'تم إرسال الإيميل بنجاح'
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ خطأ في المصادقة: {e}")
            return False, 'خطأ في بيانات الإيميل - تأكد من SMTP Key في Brevo'
        except smtplib.SMTPRecipientsRefused as e:
            print(f"❌ المستلم مرفوض: {e}")
            return False, 'الإيميل المستلم غير صحيح أو مرفوض'
        except smtplib.SMTPSenderRefused as e:
            print(f"❌ المرسل مرفوض: {e}")
            return False, 'إيميل المرسل غير مُفعّل في Brevo - فعّله من لوحة التحكم'
        except smtplib.SMTPException as e:
            print(f"❌ خطأ SMTP: {e}")
            return False, f'خطأ في إرسال الإيميل: {str(e)}'
        except Exception as e:
            print(f"❌ خطأ غير متوقع: {e}")
            import traceback
            traceback.print_exc()
            return False, f'خطأ غير متوقع: {str(e)}'


# إنشاء instance عام
email_service = EmailService()
