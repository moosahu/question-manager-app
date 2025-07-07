// JavaScript محسن للإشعارات مع إصلاح المسارات والرسائل

// متغيرات عامة
let allNotifications = [];

// تحميل الإشعارات عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    loadNotificationsFromPage();
    setupEventListeners();
});

// إعداد مستمعي الأحداث
function setupEventListeners() {
    // تصفية الإشعارات
    const filterStatus = document.getElementById('filter-status');
    if (filterStatus) {
        filterStatus.addEventListener('change', filterNotifications);
    }
    
    // أزرار الإجراءات
    const markAllReadBtn = document.getElementById('mark-all-read');
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', markAllAsRead);
    }
    
    const refreshBtn = document.getElementById('refresh-notifications');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            location.reload();
        });
    }
}

// دالة تحميل الإشعارات من الصفحة
function loadNotificationsFromPage() {
    const notificationItems = document.querySelectorAll('.notification-item');
    allNotifications = Array.from(notificationItems);
}

// دالة تصفية الإشعارات
function filterNotifications() {
    const statusFilter = document.getElementById('filter-status').value;
    
    allNotifications.forEach(item => {
        const isRead = item.dataset.read === 'true';
        let shouldShow = true;
        
        if (statusFilter === 'read' && !isRead) shouldShow = false;
        if (statusFilter === 'unread' && isRead) shouldShow = false;
        
        item.style.display = shouldShow ? 'block' : 'none';
    });
}

// دالة عرض رسالة للمستخدم
function showMessage(message, type = 'info') {
    // إنشاء عنصر الرسالة
    const messageDiv = document.createElement('div');
    messageDiv.className = `alert alert-${type} notification-message`;
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        animation: slideInRight 0.3s ease-out;
        max-width: 400px;
        word-wrap: break-word;
    `;
    
    // تحديد لون الخلفية حسب النوع
    switch(type) {
        case 'success':
            messageDiv.style.background = 'linear-gradient(135deg, #27ae60, #229954)';
            break;
        case 'error':
            messageDiv.style.background = 'linear-gradient(135deg, #e74c3c, #c0392b)';
            break;
        case 'warning':
            messageDiv.style.background = 'linear-gradient(135deg, #f39c12, #e67e22)';
            break;
        default:
            messageDiv.style.background = 'linear-gradient(135deg, #3498db, #2980b9)';
    }
    
    messageDiv.textContent = message;
    
    // إضافة الرسالة للصفحة
    document.body.appendChild(messageDiv);
    
    // إزالة الرسالة بعد 4 ثوانٍ
    setTimeout(() => {
        messageDiv.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 300);
    }, 4000);
}

// دالة تحديد إشعار كمقروء
function markAsRead(notificationId) {
    // إظهار مؤشر التحميل
    const button = event.target.closest('button');
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التحديث...';
    button.disabled = true;
    
    fetch(`/notifications/api/mark-read/${notificationId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(data.message || 'تم تحديد الإشعار كمقروء بنجاح', 'success');
            // تحديث الصفحة بعد ثانية واحدة
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            showMessage(data.message || data.error || 'فشل في تحديث الإشعار', 'error');
            // استعادة الزر
            button.innerHTML = originalText;
            button.disabled = false;
        }
    })
    .catch(error => {
        console.error('خطأ في تحديث الإشعار:', error);
        showMessage('حدث خطأ في الاتصال بالخادم', 'error');
        // استعادة الزر
        button.innerHTML = originalText;
        button.disabled = false;
    });
}

// دالة حذف إشعار
function deleteNotification(notificationId) {
    if (confirm('هل أنت متأكد من حذف هذا الإشعار؟\nلا يمكن التراجع عن هذا الإجراء.')) {
        // إظهار مؤشر التحميل
        const button = event.target.closest('button');
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الحذف...';
        button.disabled = true;
        
        fetch(`/notifications/api/delete/${notificationId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(data.message || 'تم حذف الإشعار بنجاح', 'success');
                // تحديث الصفحة بعد ثانية واحدة
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                showMessage(data.message || data.error || 'فشل في حذف الإشعار', 'error');
                // استعادة الزر
                button.innerHTML = originalText;
                button.disabled = false;
            }
        })
        .catch(error => {
            console.error('خطأ في حذف الإشعار:', error);
            showMessage('حدث خطأ في الاتصال بالخادم', 'error');
            // استعادة الزر
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }
}

// دالة تحديد جميع الإشعارات كمقروءة
function markAllAsRead() {
    const unreadItems = allNotifications.filter(item => item.dataset.read === 'false');
    if (unreadItems.length === 0) {
        showMessage('جميع الإشعارات مقروءة بالفعل', 'info');
        return;
    }
    
    if (confirm(`هل تريد تحديد جميع الإشعارات كمقروءة؟\nسيتم تحديد ${unreadItems.length} إشعار.`)) {
        // إظهار مؤشر التحميل
        const button = document.getElementById('mark-all-read');
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التحديث...';
        button.disabled = true;
        
        fetch('/notifications/api/mark-all-read', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(data.message || `تم تحديد ${data.count} إشعار كمقروء بنجاح`, 'success');
                // تحديث الصفحة بعد ثانية واحدة
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                showMessage(data.message || data.error || 'فشل في تحديث الإشعارات', 'error');
                // استعادة الزر
                button.innerHTML = originalText;
                button.disabled = false;
            }
        })
        .catch(error => {
            console.error('خطأ في تحديث الإشعارات:', error);
            showMessage('حدث خطأ في الاتصال بالخادم', 'error');
            // استعادة الزر
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }
}

// دالة الحصول على رمز CSRF
function getCSRFToken() {
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    return csrfInput ? csrfInput.value : '';
}

// إضافة أنيميشن CSS للرسائل
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .notification-message {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        direction: rtl;
        text-align: right;
    }
`;
document.head.appendChild(style);

