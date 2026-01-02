"""
خدمة إرسال الإيميل - Email Service
لإرسال رموز التحقق للطلاب
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
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """تهيئة الخدمة مع التطبيق"""
        self.mail_server = app.config.get('MAIL_SERVER', 'smtp.gmail.com')
        self.mail_port = app.config.get('MAIL_PORT', 587)
        self.mail_username = app.config.get('MAIL_USERNAME')
        self.mail_password = app.config.get('MAIL_PASSWORD')
        self.mail_sender_name = app.config.get('MAIL_SENDER_NAME', 'كيم تحصيلي')
    
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
            
            --
            كيم تحصيلي
            '''
            
            return self._send_email(to_email, subject, text_content, html_content)
            
        except Exception as e:
            print(f"❌ خطأ في إرسال رمز التحقق: {e}")
            return False, str(e)
    
    def _send_email(self, to_email, subject, text_content, html_content=None):
        """إرسال الإيميل"""
        try:
            if not self.mail_username or not self.mail_password:
                return False, 'إعدادات الإيميل غير مكتملة'
            
            # إنشاء الرسالة
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f'{self.mail_sender_name} <{self.mail_username}>'
            msg['To'] = to_email
            
            # إضافة المحتوى النصي
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(part1)
            
            # إضافة محتوى HTML إن وجد
            if html_content:
                part2 = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(part2)
            
            # الاتصال بالسيرفر وإرسال الإيميل
            with smtplib.SMTP(self.mail_server, self.mail_port) as server:
                server.starttls()
                server.login(self.mail_username, self.mail_password)
                server.sendmail(self.mail_username, to_email, msg.as_string())
            
            print(f"✅ تم إرسال الإيميل إلى {to_email}")
            return True, 'تم إرسال الإيميل بنجاح'
            
        except smtplib.SMTPAuthenticationError:
            return False, 'خطأ في بيانات الإيميل'
        except smtplib.SMTPException as e:
            return False, f'خطأ في إرسال الإيميل: {str(e)}'
        except Exception as e:
            return False, f'خطأ غير متوقع: {str(e)}'


# إنشاء instance عام
email_service = EmailService()
