"""
خدمة الإشعارات - إرسال الإشعارات عبر Firebase Cloud Messaging (FCM)
"""

import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
from datetime import datetime

class NotificationService:
    """خدمة إدارة الإشعارات عبر Firebase"""

    _initialized = False

    @classmethod
    def initialize(cls):
        """تهيئة Firebase Admin SDK"""
        if cls._initialized:
            return True

        try:
            # ✅ تحقق من Firebase المُهيأ مسبقاً
            try:
                firebase_admin.get_app()
                cls._initialized = True
                print("✅ Firebase مُهيأ مسبقاً")
                return True
            except ValueError:
                # لم يتم التهيئة بعد، نكمل التهيئة
                pass

            # الطريقة 1: قراءة من FIREBASE_CONFIG أو FIREBASE_CREDENTIALS_JSON
            firebase_creds_json = os.getenv('FIREBASE_CONFIG') or os.getenv('FIREBASE_CREDENTIALS_JSON')

            if firebase_creds_json:
                print("📝 قراءة بيانات Firebase من متغير البيئة...")
                try:
                    creds_dict = json.loads(firebase_creds_json)
                    creds = credentials.Certificate(creds_dict)
                    firebase_admin.initialize_app(creds)
                    cls._initialized = True
                    print("✅ تم تهيئة Firebase بنجاح من JSON")
                    return True
                except json.JSONDecodeError as e:
                    print(f"❌ خطأ في قراءة JSON: {e}")
                    return False

            # الطريقة 2: قراءة من ملف (احتياطية)
            firebase_creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
            if firebase_creds_path and os.path.exists(firebase_creds_path):
                print(f"📁 قراءة بيانات Firebase من ملف: {firebase_creds_path}")
                creds = credentials.Certificate(firebase_creds_path)
                firebase_admin.initialize_app(creds)
                cls._initialized = True
                print("✅ تم تهيئة Firebase بنجاح من ملف")
                return True

            # إذا لم تنجح أي طريقة
            print("⚠️ تحذير: لم يتم العثور على FIREBASE_CONFIG أو FIREBASE_CREDENTIALS_JSON أو FIREBASE_CREDENTIALS_PATH")
            return False

        except Exception as e:
            print(f"❌ خطأ في تهيئة Firebase: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def send_fcm_notification(fcm_token, title, body, data=None):
        """
        إرسال إشعار عبر FCM

        Args:
            fcm_token (str): توكن FCM للجهاز
            title (str): عنوان الإشعار
            body (str): نص الرسالة
            data (dict): بيانات إضافية (اختياري)

        Returns:
            bool: True إذا نجح الإرسال، False إذا فشل
        """
        try:
            # إذا لم يتم تهيئة Firebase، حاول التهيئة
            if not NotificationService._initialized:
                if not NotificationService.initialize():
                    print("❌ فشل في تهيئة Firebase")
                    return False

            # إذا فشلت التهيئة، أرجع False
            if not NotificationService._initialized:
                print("❌ لم يتم تهيئة Firebase")
                return False

            # إنشاء الرسالة
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=fcm_token,
            )

            # إرسال الرسالة
            response = messaging.send(message)
            print(f"✅ تم إرسال الإشعار بنجاح: {response}")
            return True

        except Exception as e:
            print(f"❌ خطأ في إرسال الإشعار: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def send_multicast_notification(fcm_tokens, title, body, data=None):
        """
        إرسال إشعار لعدة أجهزة

        Args:
            fcm_tokens (list): قائمة توكنات FCM
            title (str): عنوان الإشعار
            body (str): نص الرسالة
            data (dict): بيانات إضافية (اختياري)

        Returns:
            dict: {
                'success_count': عدد الإشعارات المرسلة بنجاح,
                'failure_count': عدد الإشعارات الفاشلة
            }
        """
        try:
            if not NotificationService._initialized:
                NotificationService.initialize()

            if not NotificationService._initialized:
                return {'success_count': 0, 'failure_count': len(fcm_tokens)}

            # إنشاء الرسالة
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                tokens=fcm_tokens,
            )

            # إرسال الرسالة
            response = messaging.send_multicast(message)
            print(f"✅ تم إرسال {response.success_count} إشعار بنجاح")
            print(f"❌ فشل إرسال {response.failure_count} إشعار")

            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count
            }

        except Exception as e:
            print(f"❌ خطأ في إرسال الإشعارات المتعددة: {e}")
            return {'success_count': 0, 'failure_count': len(fcm_tokens)}

    @staticmethod
    def send_topic_notification(topic, title, body, data=None):
        """
        إرسال إشعار لموضوع (topic)

        Args:
            topic (str): اسم الموضوع
            title (str): عنوان الإشعار
            body (str): نص الرسالة
            data (dict): بيانات إضافية (اختياري)

        Returns:
            bool: True إذا نجح، False إذا فشل
        """
        try:
            if not NotificationService._initialized:
                NotificationService.initialize()

            if not NotificationService._initialized:
                return False

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                topic=topic,
            )

            response = messaging.send(message)
            print(f"✅ تم إرسال الإشعار للموضوع '{topic}': {response}")
            return True

        except Exception as e:
            print(f"❌ خطأ في إرسال إشعار الموضوع: {e}")
            return False


# دالة مساعدة للاستخدام المباشر
def send_fcm_notification(fcm_token, title, body, data=None):
    """دالة مساعدة لإرسال إشعار واحد"""
    return NotificationService.send_fcm_notification(fcm_token, title, body, data)

def send_multicast_notification(fcm_tokens, title, body, data=None):
    """دالة مساعدة لإرسال إشعارات متعددة"""
    return NotificationService.send_multicast_notification(fcm_tokens, title, body, data)

def send_topic_notification(topic, title, body, data=None):
    """دالة مساعدة لإرسال إشعار لموضوع"""
    return NotificationService.send_topic_notification(topic, title, body, data)
