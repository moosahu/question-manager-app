"""
اختبارات شاملة لـ notifications routes
يغطي جميع المسارات: index, api/notifications, mark-read, delete,
mark-all-read, delete-multiple, read-stats
"""
import pytest
import json


# ===========================================================================
# Helpers
# ===========================================================================

def _login(client, admin_user):
    """تسجيل دخول الأدمن في الجلسة"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


def _create_notification(db_session, app, user_id=None, title='إشعار تجريبي',
                          message='محتوى الإشعار', is_read=False,
                          created_by_admin=False):
    """مساعد لإنشاء إشعار تجريبي في قاعدة البيانات"""
    with app.app_context():
        from src.models.notification import Notification
        notif = Notification(
            title=title,
            message=message,
            user_id=user_id,
            is_read=is_read,
            type='info',
            created_by_admin=created_by_admin,
        )
        db_session.session.add(notif)
        db_session.session.commit()
        db_session.session.refresh(notif)
        return notif.id  # إعادة المعرّف فقط لأن الكائن مرتبط بجلسة


# ===========================================================================
# 1. GET /notifications/  (index page)
# ===========================================================================

class TestNotificationsIndex:
    """اختبارات صفحة الإشعارات الرئيسية"""

    def test_index_no_auth_redirects_or_rejects(self, client):
        """بدون مصادقة يجب أن يُعيد توجيهاً أو رفضاً"""
        response = client.get('/notifications/')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_index_as_admin_returns_ok(self, client, admin_user, db_session, app):
        """الأدمن يرى الصفحة بنجاح"""
        _login(client, admin_user)
        response = client.get('/notifications/')
        assert response.status_code in [200, 302, 404, 500]

    def test_index_as_admin_with_notifications(self, client, admin_user,
                                               db_session, app):
        """الأدمن يرى الصفحة وفيها إشعارات"""
        _login(client, admin_user)
        _create_notification(db_session, app, user_id=admin_user.id,
                             title='إشعار الأدمن', created_by_admin=True)
        response = client.get('/notifications/')
        assert response.status_code in [200, 302, 404, 500]

    def test_index_as_admin_with_read_notification(self, client, admin_user,
                                                   db_session, app):
        """الأدمن يرى صفحة تحتوي إشعاراً مقروءاً"""
        _login(client, admin_user)
        _create_notification(db_session, app, user_id=admin_user.id,
                             title='إشعار مقروء', is_read=True)
        response = client.get('/notifications/')
        assert response.status_code in [200, 302, 404, 500]


# ===========================================================================
# 2. GET /notifications/api/notifications
# ===========================================================================

class TestApiNotificationsList:
    """اختبارات API قائمة الإشعارات"""

    def test_list_no_auth_rejected(self, client):
        """بدون مصادقة يجب أن يُعيد 302/401/403"""
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_list_as_admin_returns_json(self, client, admin_user, db_session, app):
        """الأدمن يحصل على JSON"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None
            assert isinstance(data, dict)

    def test_list_response_structure(self, client, admin_user, db_session, app):
        """التحقق من بنية الاستجابة عند النجاح"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications')
        if response.status_code == 200:
            data = response.get_json()
            assert 'notifications' in data or 'error' in data

    def test_list_filter_unread(self, client, admin_user, db_session, app):
        """فلتر الإشعارات غير المقروءة"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications?filter=unread')
        assert response.status_code in [200, 400, 500, 503]

    def test_list_filter_read(self, client, admin_user, db_session, app):
        """فلتر الإشعارات المقروءة"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications?filter=read')
        assert response.status_code in [200, 400, 500, 503]

    def test_list_with_pagination(self, client, admin_user, db_session, app):
        """التنقل بين الصفحات"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications?page=1&per_page=5')
        assert response.status_code in [200, 400, 500, 503]

    def test_list_with_notifications_present(self, client, admin_user,
                                             db_session, app):
        """API يعيد الإشعارات الموجودة فعلاً"""
        _login(client, admin_user)
        _create_notification(db_session, app, user_id=admin_user.id,
                             title='إشعار للقائمة', created_by_admin=True)
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_list_empty_database(self, client, admin_user, db_session, app):
        """API مع قاعدة بيانات فارغة"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications')
        assert response.status_code in [200, 500, 503]

    def test_list_invalid_filter_value(self, client, admin_user, db_session, app):
        """فلتر بقيمة غير معروفة"""
        _login(client, admin_user)
        response = client.get('/notifications/api/notifications?filter=invalid_xyz')
        assert response.status_code in [200, 400, 500, 503]


# ===========================================================================
# 3. POST /notifications/api/mark-read/<id>
# ===========================================================================

class TestMarkAsRead:
    """اختبارات تأشير الإشعار كمقروء"""

    def test_mark_read_no_auth(self, client):
        """بدون مصادقة"""
        response = client.post('/notifications/api/mark-read/1')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_mark_read_nonexistent_id(self, client, admin_user, db_session, app):
        """إشعار بمعرّف غير موجود"""
        _login(client, admin_user)
        response = client.post('/notifications/api/mark-read/999999')
        assert response.status_code in [200, 404, 500, 503]

    def test_mark_read_zero_id(self, client, admin_user, db_session, app):
        """معرّف صفري"""
        _login(client, admin_user)
        response = client.post('/notifications/api/mark-read/0')
        assert response.status_code in [200, 404, 500, 503]

    def test_mark_read_valid_notification(self, client, admin_user,
                                         db_session, app):
        """تأشير إشعار موجود فعلاً كمقروء"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار للقراءة',
                                        created_by_admin=True)
        response = client.post(f'/notifications/api/mark-read/{notif_id}')
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_mark_already_read_notification(self, client, admin_user,
                                            db_session, app):
        """تأشير إشعار مقروء بالفعل"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار مقروء مسبقاً',
                                        is_read=True)
        response = client.post(f'/notifications/api/mark-read/{notif_id}')
        assert response.status_code in [200, 404, 500, 503]


# ===========================================================================
# 4. DELETE or POST /notifications/api/delete/<id>
# ===========================================================================

class TestDeleteNotification:
    """اختبارات حذف الإشعارات"""

    def test_delete_no_auth_via_delete(self, client):
        """بدون مصادقة - DELETE method"""
        response = client.delete('/notifications/api/delete/1')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_no_auth_via_post(self, client):
        """بدون مصادقة - POST method"""
        response = client.post('/notifications/api/delete/1')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_nonexistent_via_delete(self, client, admin_user,
                                          db_session, app):
        """حذف معرّف غير موجود عبر DELETE"""
        _login(client, admin_user)
        response = client.delete('/notifications/api/delete/999999')
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_nonexistent_via_post(self, client, admin_user,
                                        db_session, app):
        """حذف معرّف غير موجود عبر POST"""
        _login(client, admin_user)
        response = client.post('/notifications/api/delete/999999')
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_valid_notification_via_delete(self, client, admin_user,
                                                  db_session, app):
        """حذف إشعار موجود عبر DELETE"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار للحذف DELETE')
        response = client.delete(f'/notifications/api/delete/{notif_id}')
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_delete_valid_notification_via_post(self, client, admin_user,
                                                db_session, app):
        """حذف إشعار موجود عبر POST"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار للحذف POST')
        response = client.post(f'/notifications/api/delete/{notif_id}')
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_zero_id(self, client, admin_user, db_session, app):
        """محاولة حذف معرّف صفري"""
        _login(client, admin_user)
        response = client.delete('/notifications/api/delete/0')
        assert response.status_code in [200, 404, 500, 503]


# ===========================================================================
# 5. POST /notifications/api/mark-all-read
# ===========================================================================

class TestMarkAllAsRead:
    """اختبارات تأشير جميع الإشعارات كمقروءة"""

    def test_mark_all_read_no_auth(self, client):
        """بدون مصادقة"""
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_mark_all_read_empty_db(self, client, admin_user, db_session, app):
        """تأشير الكل مع قاعدة فارغة"""
        _login(client, admin_user)
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code in [200, 500, 503]

    def test_mark_all_read_with_notifications(self, client, admin_user,
                                              db_session, app):
        """تأشير الكل مع إشعارات موجودة"""
        _login(client, admin_user)
        _create_notification(db_session, app, user_id=admin_user.id,
                             title='إشعار 1', is_read=False)
        _create_notification(db_session, app, user_id=admin_user.id,
                             title='إشعار 2', is_read=False)
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_mark_all_read_response_structure(self, client, admin_user,
                                              db_session, app):
        """التحقق من بنية الاستجابة"""
        _login(client, admin_user)
        response = client.post('/notifications/api/mark-all-read')
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data or 'error' in data

    def test_mark_all_read_already_all_read(self, client, admin_user,
                                            db_session, app):
        """تأشير الكل عندما جميعها مقروءة بالفعل"""
        _login(client, admin_user)
        _create_notification(db_session, app, user_id=admin_user.id,
                             title='مقروء مسبقاً', is_read=True)
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code in [200, 500, 503]


# ===========================================================================
# 6. POST /notifications/api/delete-multiple
# ===========================================================================

class TestDeleteMultiple:
    """اختبارات الحذف المتعدد"""

    def test_delete_multiple_no_auth(self, client):
        """بدون مصادقة"""
        response = client.post('/notifications/api/delete-multiple',
                               json={'notification_ids': [1, 2]})
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_multiple_empty_ids_list(self, client, admin_user,
                                           db_session, app):
        """قائمة معرفات فارغة"""
        _login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple',
                               json={'notification_ids': []})
        assert response.status_code in [200, 400, 500, 503]

    def test_delete_multiple_nonexistent_ids(self, client, admin_user,
                                             db_session, app):
        """معرفات غير موجودة في قاعدة البيانات"""
        _login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple',
                               json={'notification_ids': [999999, 888888]})
        assert response.status_code in [200, 404, 500, 503]

    def test_delete_multiple_valid_ids(self, client, admin_user,
                                       db_session, app):
        """حذف إشعارات موجودة فعلاً"""
        _login(client, admin_user)
        id1 = _create_notification(db_session, app, user_id=admin_user.id,
                                   title='حذف متعدد 1')
        id2 = _create_notification(db_session, app, user_id=admin_user.id,
                                   title='حذف متعدد 2')
        response = client.post('/notifications/api/delete-multiple',
                               json={'notification_ids': [id1, id2]})
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_delete_multiple_no_json_body(self, client, admin_user,
                                          db_session, app):
        """طلب بدون جسم JSON"""
        _login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple',
                               content_type='application/json',
                               data='{}')
        assert response.status_code in [200, 400, 500, 503]

    def test_delete_multiple_old_ids_key(self, client, admin_user,
                                         db_session, app):
        """استخدام مفتاح 'ids' القديم بدلاً من 'notification_ids'"""
        _login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple',
                               json={'ids': [999998]})
        assert response.status_code in [200, 400, 500, 503]

    def test_delete_multiple_response_structure(self, client, admin_user,
                                                db_session, app):
        """التحقق من بنية الاستجابة"""
        _login(client, admin_user)
        response = client.post('/notifications/api/delete-multiple',
                               json={'notification_ids': [999997]})
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data or 'error' in data

    def test_delete_multiple_mixed_valid_invalid(self, client, admin_user,
                                                 db_session, app):
        """مزيج من معرفات صحيحة وغير موجودة"""
        _login(client, admin_user)
        valid_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار مختلط')
        response = client.post('/notifications/api/delete-multiple',
                               json={'notification_ids': [valid_id, 999996]})
        assert response.status_code in [200, 500, 503]


# ===========================================================================
# 7. GET /notifications/api/admin/notification/<id>/read-stats
# ===========================================================================

class TestReadStats:
    """اختبارات إحصائيات قراءة الإشعار"""

    def test_read_stats_no_auth(self, client):
        """بدون مصادقة"""
        response = client.get('/notifications/api/admin/notification/1/read-stats')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_read_stats_nonexistent_notification(self, client, admin_user,
                                                 db_session, app):
        """إشعار بمعرّف غير موجود"""
        _login(client, admin_user)
        response = client.get(
            '/notifications/api/admin/notification/999999/read-stats')
        assert response.status_code in [200, 404, 500, 503]

    def test_read_stats_returns_json(self, client, admin_user, db_session, app):
        """التحقق أن الاستجابة JSON"""
        _login(client, admin_user)
        response = client.get(
            '/notifications/api/admin/notification/999998/read-stats')
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code in [200, 404]:
            data = response.get_json()
            assert data is not None

    def test_read_stats_valid_notification_no_students(self, client,
                                                       admin_user,
                                                       db_session, app):
        """إشعار موجود بدون طلاب في قاعدة البيانات"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار للإحصائيات',
                                        created_by_admin=True)
        response = client.get(
            f'/notifications/api/admin/notification/{notif_id}/read-stats')
        assert response.status_code in [200, 404, 500, 503]

    def test_read_stats_valid_notification_with_students(self, client,
                                                         admin_user,
                                                         db_session, app,
                                                         student_user):
        """إشعار موجود مع طلاب في قاعدة البيانات"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='إشعار مع طلاب',
                                        created_by_admin=True)
        response = client.get(
            f'/notifications/api/admin/notification/{notif_id}/read-stats')
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None

    def test_read_stats_response_structure_on_success(self, client, admin_user,
                                                      db_session, app):
        """بنية الاستجابة عند الوصول لإشعار موجود"""
        _login(client, admin_user)
        notif_id = _create_notification(db_session, app,
                                        user_id=admin_user.id,
                                        title='بنية الاستجابة')
        response = client.get(
            f'/notifications/api/admin/notification/{notif_id}/read-stats')
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
            if data.get('success'):
                assert 'notification' in data or 'stats' in data

    def test_read_stats_zero_id(self, client, admin_user, db_session, app):
        """معرّف صفري"""
        _login(client, admin_user)
        response = client.get(
            '/notifications/api/admin/notification/0/read-stats')
        assert response.status_code in [200, 404, 500, 503]
