"""
خدمة إرسال الإيميل - Email Service
لإرسال رموز التحقق للطلاب
متوافق مع Brevo (SendinBlue) SMTP
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime


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
    
    def send_delete_account_code(self, to_email, code, user_name):
        """إرسال رمز تأكيد حذف الحساب"""
        try:
            subject = f'تأكيد حذف الحساب - كيم تحصيلي'
            
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
                        background: linear-gradient(135deg, #e53935 0%, #b71c1c 100%);
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
                        background: linear-gradient(135deg, #e53935 0%, #b71c1c 100%);
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
                        background: #ffebee;
                        color: #c62828;
                        padding: 12px;
                        border-radius: 8px;
                        margin-top: 20px;
                        font-size: 13px;
                        border: 1px solid #ef9a9a;
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
                        <h1>⚠️ حذف الحساب - كيم تحصيلي</h1>
                    </div>
                    <div class="content">
                        <p class="greeting">مرحباً {user_name} 👋</p>
                        <p>تلقينا طلباً لحذف حسابك في كيم تحصيلي</p>
                        <p>رمز تأكيد الحذف هو:</p>
                        <div class="code-box">{code}</div>
                        <p class="note">أدخل هذا الرمز في التطبيق لتأكيد حذف حسابك</p>
                        <div class="warning">
                            🗑️ سيتم حذف جميع بياناتك بشكل <strong>نهائي</strong> ولا يمكن التراجع عن ذلك
                            <br><br>
                            ⏱️ هذا الرمز صالح لمدة <strong>10 دقائق</strong> فقط
                        </div>
                        <div class="security-note">
                            🔒 إذا لم تطلب حذف حسابك، تجاهل هذا الإيميل وتأكد من أمان حسابك
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2024 كيم تحصيلي - جميع الحقوق محفوظة</p>
                    </div>
                </div>
            </body>
            </html>
            '''
            
            text_content = f'''
            مرحباً {user_name}
            
            تلقينا طلباً لحذف حسابك في كيم تحصيلي.
            
            رمز تأكيد الحذف: {code}
            
            أدخل هذا الرمز في التطبيق لتأكيد حذف حسابك.
            
            ⚠️ سيتم حذف جميع بياناتك بشكل نهائي ولا يمكن التراجع عن ذلك.
            هذا الرمز صالح لمدة 10 دقائق فقط.
            
            🔒 إذا لم تطلب حذف حسابك، تجاهل هذا الإيميل.
            
            --
            كيم تحصيلي
            '''
            
            return self._send_email(to_email, subject, text_content, html_content)
            
        except Exception as e:
            print(f"❌ خطأ في إرسال رمز حذف الحساب: {e}")
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


    def send_admin_login_otp(self, to_email, code, admin_name):
        """إرسال كود تسجيل دخول الأدمن عبر الإيميل"""
        try:
            subject = 'كود تسجيل الدخول - لوحة التحكم'
            html_content = f'''
            <!DOCTYPE html>
            <html dir="rtl" lang="ar">
            <head><meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background:#f5f7fa; margin:0; padding:20px; direction:rtl; }}
                .container {{ max-width:500px; margin:0 auto; background:white; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,.1); }}
                .header {{ background:linear-gradient(135deg,#1565c0 0%,#0d47a1 100%); color:white; padding:30px; text-align:center; }}
                .header h1 {{ margin:0; font-size:22px; }}
                .content {{ padding:30px; text-align:center; }}
                .code-box {{ background:linear-gradient(135deg,#1565c0 0%,#0d47a1 100%); color:white; font-size:38px; font-weight:bold; letter-spacing:14px; padding:20px 30px; border-radius:12px; display:inline-block; margin:20px 0; }}
                .note {{ color:#666; font-size:13px; margin-top:16px; }}
                .warning {{ background:#fff3e0; color:#e65100; padding:12px; border-radius:8px; margin-top:16px; font-size:13px; border:1px solid #ffb74d; }}
            </style></head>
            <body>
            <div class="container">
              <div class="header"><h1>🔐 كيم تحصيلي — لوحة التحكم</h1></div>
              <div class="content">
                <p style="font-size:17px;color:#333;">مرحباً <strong>{admin_name}</strong></p>
                <p style="color:#555;">كود تسجيل الدخول الخاص بك:</p>
                <div class="code-box">{code}</div>
                <p class="note">⏱️ صالح لمدة <strong>5 دقائق</strong> فقط</p>
                <div class="warning">⚠️ لا تشارك هذا الكود مع أحد. إذا لم تطلبه، تجاهل هذا الإيميل.</div>
              </div>
            </div>
            </body></html>'''

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.sender_email, to_email, msg.as_string())

            print(f"✅ كود الأدمن أُرسل إلى: {to_email}")
            return True, 'تم إرسال الكود'

        except Exception as e:
            print(f"❌ خطأ في إرسال كود الأدمن: {e}")
            return False, str(e)


    def send_admin_notification(self, to_email, title, message):
        """إرسال إشعار للأدمن (تسجيل جديد / حذف حساب)"""
        try:
            subject = f'{title} - كيم تحصيلي'
            # تحويل الرسالة لسطور HTML
            message_html = message.replace('\n', '<br>')

            html_content = f'''
            <!DOCTYPE html>
            <html dir="rtl" lang="ar">
            <head><meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background:#f5f7fa; margin:0; padding:20px; direction:rtl; }}
                .container {{ max-width:500px; margin:0 auto; background:white; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,.1); }}
                .header {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; padding:25px; text-align:center; }}
                .header h1 {{ margin:0; font-size:20px; }}
                .content {{ padding:25px; text-align:right; }}
                .info {{ background:#f0f4ff; padding:15px; border-radius:10px; font-size:15px; color:#333; line-height:1.8; }}
                .footer {{ background:#f8f9fa; padding:15px; text-align:center; color:#999; font-size:12px; }}
            </style></head>
            <body>
            <div class="container">
              <div class="header"><h1>{title}</h1></div>
              <div class="content">
                <div class="info">{message_html}</div>
              </div>
              <div class="footer">كيم تحصيلي &copy; {datetime.utcnow().year}</div>
            </div>
            </body></html>'''

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f'{self.mail_sender_name} <{self.mail_sender_email}>'
            msg['To'] = to_email
            msg.attach(MIMEText(message_html, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            with smtplib.SMTP(self.mail_server, self.mail_port) as server:
                server.starttls()
                server.login(self.mail_username, self.mail_password)
                server.sendmail(self.mail_sender_email, to_email, msg.as_string())

            print(f"✅ إشعار أدمن أُرسل إلى: {to_email} [{title}]")
            return True, 'تم الإرسال'

        except Exception as e:
            print(f"❌ خطأ في إرسال إشعار الأدمن: {e}")
            return False, str(e)


# إنشاء instance عام
email_service = EmailService()
