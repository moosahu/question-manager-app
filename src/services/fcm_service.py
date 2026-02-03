# src/services/fcm_service.py
"""
خدمة إرسال الإشعارات عبر Firebase Cloud Messaging
"""

import os
import requests
from typing import List, Dict, Optional

try:
    from src.models.student import Student
except ImportError:
    from models.student import Student


class FCMService:
    """خدمة إرسال الإشعارات"""
    
    def __init__(self):
        self.server_key = os.getenv('FCM_SERVER_KEY')
        self.fcm_url = 'https://fcm.googleapis.com/fcm/send'
        self.is_configured = bool(self.server_key)
    
    def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        إرسال إشعار لجهاز واحد
        
        Args:
            token: FCM token للجهاز
            title: عنوان الإشعار
            body: محتوى الإشعار
            data: بيانات إضافية
        
        Returns:
            bool: نجح الإرسال أم لا
        """
        if not self.is_configured:
            print("⚠️ FCM not configured - missing FCM_SERVER_KEY")
            return False
        
        if not token:
            print("⚠️ No FCM token provided")
            return False
        
        try:
            headers = {
                'Authorization': f'key={self.server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': token,
                'notification': {
                    'title': title,
                    'body': body,
                    'sound': 'default',
                    'badge': '1'
                },
                'priority': 'high'
            }
            
            if data:
                payload['data'] = data
            
            response = requests.post(
                self.fcm_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success', 0) > 0:
                    print(f"✅ Notification sent successfully to {token[:20]}...")
                    return True
                else:
                    error = result.get('results', [{}])[0].get('error', 'Unknown')
                    print(f"❌ FCM Error: {error}")
                    return False
            else:
                print(f"❌ FCM HTTP Error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ FCM Exception: {e}")
            return False
    
    def send_notification_to_multiple(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> int:
        """
        إرسال إشعار لعدة أجهزة
        
        Args:
            tokens: قائمة FCM tokens
            title: عنوان الإشعار
            body: محتوى الإشعار
            data: بيانات إضافية
        
        Returns:
            int: عدد الإشعارات المرسلة بنجاح
        """
        if not self.is_configured:
            print("⚠️ FCM not configured")
            return 0
        
        if not tokens:
            print("⚠️ No tokens provided")
            return 0
        
        success_count = 0
        
        # FCM تدعم إرسال حتى 1000 token في طلب واحد
        # لكن نرسل واحد واحد للتحكم الأفضل
        for token in tokens:
            if self.send_notification(token, title, body, data):
                success_count += 1
        
        print(f"✅ Sent {success_count}/{len(tokens)} notifications")
        return success_count


# Instance
fcm_service = FCMService()


# Helper functions
def send_notification_to_student(
    student: Student,
    title: str,
    body: str,
    data: Optional[Dict] = None
) -> bool:
    """
    إرسال إشعار لطالب واحد
    
    Args:
        student: كائن الطالب
        title: عنوان الإشعار
        body: محتوى الإشعار
        data: بيانات إضافية
    
    Returns:
        bool: نجح الإرسال أم لا
    """
    if not student.fcm_token:
        print(f"⚠️ Student {student.name} has no FCM token")
        return False
    
    return fcm_service.send_notification(
        student.fcm_token,
        title,
        body,
        data
    )


def send_notification_to_students(
    students: List[Student],
    title: str,
    body: str,
    data: Optional[Dict] = None
) -> int:
    """
    إرسال إشعار لعدة طلاب
    
    Args:
        students: قائمة الطلاب
        title: عنوان الإشعار
        body: محتوى الإشعار
        data: بيانات إضافية
    
    Returns:
        int: عدد الإشعارات المرسلة بنجاح
    """
    tokens = [s.fcm_token for s in students if s.fcm_token]
    
    if not tokens:
        print("⚠️ No students with FCM tokens")
        return 0
    
    return fcm_service.send_notification_to_multiple(
        tokens,
        title,
        body,
        data
    )


def send_broadcast_notification(
    title: str,
    body: str,
    data: Optional[Dict] = None,
    grade: Optional[str] = None
) -> int:
    """
    إرسال إشعار لجميع الطلاب أو لصف معين
    
    Args:
        title: عنوان الإشعار
        body: محتوى الإشعار
        data: بيانات إضافية
        grade: الصف (اختياري) - إذا كان None يرسل للجميع
    
    Returns:
        int: عدد الإشعارات المرسلة بنجاح
    """
    if grade:
        students = Student.get_students_by_grade(grade)
    else:
        students = Student.get_students_with_fcm_tokens()
    
    return send_notification_to_students(students, title, body, data)
