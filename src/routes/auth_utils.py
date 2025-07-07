
import pyotp

def verify_code(code, secret_key):
    """
    التحقق من صحة رمز TOTP المولد من تطبيق المصادقة
    """
    try:
        totp = pyotp.TOTP(secret_key)
        return totp.verify(code)
    except Exception as e:
        print(f"خطأ أثناء التحقق من الكود: {e}")
        return False
