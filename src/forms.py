from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Email

class LoginForm(FlaskForm):
    username    = StringField('اسم المستخدم', validators=[DataRequired()])
    password    = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit      = SubmitField('تسجيل الدخول')

class TwoFactorForm(FlaskForm):
    otp_code = StringField(
        'رمز التحقق',
        validators=[DataRequired(), Length(min=6, max=6)]
    )
    submit   = SubmitField('تأكيد')
