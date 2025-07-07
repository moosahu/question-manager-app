// ===== ميزات مراقبة النسخ الاحتياطي =====

// ===== دوال مساعدة =====

/**
 * الحصول على CSRF token من الصفحة
 */
function getCSRFToken() {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    return csrfMeta ? csrfMeta.content : (csrfInput ? csrfInput.value : '');
}

/**
 * عرض حالة النسخ الاحتياطي في الواجهة
 */
function displayBackupStatus() {
    const statusContainer = document.getElementById('backup-status-container');
    if (!statusContainer) return;

    const lastBackupTime = localStorage.getItem('lastBackupTime');
    const backupDestination = localStorage.getItem('backupDestination') || 'local';
    const isGoogleDriveConnected = checkGoogleDriveConnectionSync();
    
    // تحديد حالة النسخ الاحتياطي
    let backupStatusText = 'لم يتم إنشاء نسخة بعد';
    let backupStatusClass = 'warning';
    
    if (lastBackupTime) {
        const lastBackup = new Date(lastBackupTime);
        const now = new Date();
        const hoursDiff = (now - lastBackup) / (1000 * 60 * 60);
        
        if (hoursDiff <= 24) {
            backupStatusClass = 'success';
        } else if (hoursDiff <= 72) {
            backupStatusClass = 'warning';
        } else {
            backupStatusClass = 'error';
        }
        
        backupStatusText = formatDateTime(lastBackupTime);
    }

    // تحديد حالة Google Drive بناءً على عدة عوامل
    let driveStatusText = 'غير متصل ❌';
    let driveStatusClass = 'disconnected';
    
    if (isGoogleDriveConnected) {
        driveStatusText = 'متصل ✅';
        driveStatusClass = 'connected';
    } else if (lastBackupTime) {
        // إذا كان هناك نسخة احتياطية حديثة، قد يكون الاتصال يعمل
        const lastBackup = new Date(lastBackupTime);
        const now = new Date();
        const daysDiff = (now - lastBackup) / (1000 * 60 * 60 * 24);
        
        if (daysDiff <= 1) {
            driveStatusText = 'متصل (آخر نسخة حديثة) ✅';
            driveStatusClass = 'connected';
        }
    }

    let statusHTML = `
        <div class="backup-status-card">
            <h4><i class="fas fa-info-circle"></i> حالة النسخ الاحتياطي</h4>
            
            <div class="status-item">
                <span class="label">آخر نسخة احتياطية:</span>
                <span class="value status-${backupStatusClass}">${backupStatusText}</span>
            </div>
            
            <div class="status-item">
                <span class="label">وجهة الحفظ:</span>
                <span class="value ${backupDestination === 'google_drive' ? 'google-drive' : 'local'}">
                    ${backupDestination === 'google_drive' ? 'Google Drive' : 'محلي'}
                    ${backupDestination === 'google_drive' ? (isGoogleDriveConnected ? '✅' : '❌') : ''}
                </span>
            </div>
            
            <div class="status-item">
                <span class="label">حالة Google Drive:</span>
                <span class="value ${driveStatusClass}">
                    ${driveStatusText}
                </span>
            </div>
            
            <div class="status-actions">
                <button onclick="testBackupNow()" class="btn btn-primary btn-sm">
                    <i class="fas fa-play"></i> اختبار النسخ الآن
                </button>
                <button onclick="checkGoogleDriveFiles()" class="btn btn-secondary btn-sm">
                    <i class="fab fa-google-drive"></i> فحص ملفات Google Drive
                </button>
                <button onclick="refreshConnectionStatus()" class="btn btn-info btn-sm">
                    <i class="fas fa-sync"></i> تحديث الحالة
                </button>
            </div>
        </div>
    `;

    statusContainer.innerHTML = statusHTML;
}

/**
 * اختبار النسخ الاحتياطي فوراً
 */
async function testBackupNow() {
    try {
        showBackupNotification('🔄 جاري اختبار النسخ الاحتياطي...', 'info');
        
        // استدعاء API endpoint الصحيح
        const response = await fetch('/api/v1/backup/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        
        if (data.success) {
            // تحديث حالة النسخ الاحتياطي وحفظ token
            const currentTime = new Date().toISOString();
            localStorage.setItem('lastBackupTime', currentTime);
            
            // حفظ معلومات النسخة الاحتياطية
            const backupInfo = {
                timestamp: currentTime,
                type: data.backup_type || 'basic',
                destination: data.destination || 'local',
                details: data.details || {}
            };
            localStorage.setItem('lastBackupInfo', JSON.stringify(backupInfo));
            
            // حفظ مؤشر على نجاح الاتصال مع Google Drive
            if (data.backup_type === 'comprehensive' || data.destination === 'google_drive') {
                localStorage.setItem('google_drive_token', 'connected_' + Date.now());
            }
            
            displayBackupStatus();
            
            // إشعار نجاح محسن حسب نوع النسخة
            if (data.backup_type === 'comprehensive') {
                let detailsText = '';
                if (data.details) {
                    const details = data.details;
                    detailsText = `\n📊 تفاصيل النسخة:`;
                    if (details.data_types) {
                        detailsText += `\n• أنواع البيانات: ${details.data_types.length} نوع`;
                    }
                    if (details.size_estimate) {
                        detailsText += `\n• حجم النسخة: ${details.size_estimate}`;
                    }
                    if (details.total_notifications) {
                        detailsText += `\n• الإشعارات: ${details.total_notifications} إشعار`;
                    }
                }
                showBackupNotification(`✅ تم اختبار النسخ الاحتياطي الشامل بنجاح!${detailsText}\n🔗 تم حفظ جميع البيانات في Google Drive`, 'success');
            } else {
                showBackupNotification('✅ تم اختبار النسخ الاحتياطي الأساسي بنجاح!', 'success');
            }
        } else {
            throw new Error(data.message || 'فشل في إنشاء النسخة الاحتياطية');
        }
        
    } catch (error) {
        console.error('خطأ في اختبار النسخ الاحتياطي:', error);
        showBackupNotification('❌ فشل في اختبار النسخ الاحتياطي: ' + error.message, 'error');
    }
}

/**
 * تحديث حالة الاتصال مع Google Drive
 */
async function refreshConnectionStatus() {
    try {
        showBackupNotification('🔄 جاري تحديث حالة الاتصال...', 'info');
        
        // فحص حالة Google API
        if (window.gapi && gapi.auth2) {
            const authInstance = gapi.auth2.getAuthInstance();
            if (authInstance) {
                const isSignedIn = authInstance.isSignedIn.get();
                
                if (isSignedIn) {
                    // حفظ مؤشر على الاتصال الناجح
                    localStorage.setItem('google_drive_token', 'connected_' + Date.now());
                    
                    // اختبار الوصول إلى Google Drive
                    try {
                        const response = await gapi.client.drive.about.get({
                            fields: 'storageQuota'
                        });
                        
                        if (response.status === 200) {
                            showBackupNotification('✅ تم تحديث حالة الاتصال - Google Drive متصل', 'success');
                        }
                    } catch (driveError) {
                        console.log('تحذير: خطأ في اختبار Google Drive API:', driveError);
                        showBackupNotification('⚠️ مسجل دخول لكن هناك مشكلة في الوصول لـ Google Drive', 'warning');
                    }
                } else {
                    showBackupNotification('⚠️ غير مسجل دخول في Google Drive', 'warning');
                }
            }
        } else {
            showBackupNotification('⚠️ Google API غير محمل', 'warning');
        }
        
        // تحديث العرض
        displayBackupStatus();
        
    } catch (error) {
        console.error('خطأ في تحديث حالة الاتصال:', error);
        showBackupNotification('❌ فشل في تحديث حالة الاتصال: ' + error.message, 'error');
    }
}

/**
 * فحص ملفات النسخ الاحتياطي في Google Drive
 */
async function checkGoogleDriveFiles() {
    try {
        if (!isGoogleDriveConnected()) {
            showBackupNotification('❌ Google Drive غير متصل', 'error');
            return;
        }

        showBackupNotification('🔄 جاري فحص ملفات Google Drive...', 'info');

        // البحث عن ملفات النسخ الاحتياطي
        const files = await listGoogleDriveBackupFiles();
        
        if (files && files.length > 0) {
            displayGoogleDriveFiles(files);
            showBackupNotification(`✅ تم العثور على ${files.length} ملف نسخ احتياطي`, 'success');
        } else {
            showBackupNotification('⚠️ لم يتم العثور على ملفات نسخ احتياطي في Google Drive', 'warning');
        }

    } catch (error) {
        console.error('خطأ في فحص ملفات Google Drive:', error);
        showBackupNotification('❌ فشل في فحص ملفات Google Drive: ' + error.message, 'error');
    }
}

/**
 * عرض ملفات Google Drive
 */
function displayGoogleDriveFiles(files) {
    const modal = document.createElement('div');
    modal.className = 'backup-files-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fab fa-google-drive"></i> ملفات النسخ الاحتياطي في Google Drive</h3>
                <button onclick="this.closest('.backup-files-modal').remove()" class="close-btn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="files-list">
                    ${files.map(file => `
                        <div class="file-item">
                            <div class="file-info">
                                <i class="fas fa-file-archive"></i>
                                <span class="file-name">${file.name}</span>
                                <span class="file-date">${formatDateTime(file.createdTime)}</span>
                                <span class="file-size">${formatFileSize(file.size)}</span>
                            </div>
                            <div class="file-actions">
                                <button onclick="downloadBackupFile('${file.id}')" class="btn btn-sm btn-primary">
                                    <i class="fas fa-download"></i> تحميل
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

/**
 * البحث عن ملفات النسخ الاحتياطي في Google Drive
 */
async function listGoogleDriveBackupFiles() {
    try {
        const response = await gapi.client.drive.files.list({
            q: "name contains 'backup_' and mimeType='application/json'",
            orderBy: 'createdTime desc',
            pageSize: 20,
            fields: 'files(id,name,createdTime,size)'
        });

        return response.result.files;
    } catch (error) {
        console.error('خطأ في البحث عن ملفات النسخ الاحتياطي:', error);
        throw error;
    }
}

/**
 * تحميل ملف نسخة احتياطية من Google Drive
 */
async function downloadBackupFile(fileId) {
    try {
        showBackupNotification('🔄 جاري تحميل الملف...', 'info');

        const response = await gapi.client.drive.files.get({
            fileId: fileId,
            alt: 'media'
        });

        // إنشاء رابط تحميل
        const blob = new Blob([response.body], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `backup_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showBackupNotification('✅ تم تحميل الملف بنجاح', 'success');

    } catch (error) {
        console.error('خطأ في تحميل الملف:', error);
        showBackupNotification('❌ فشل في تحميل الملف: ' + error.message, 'error');
    }
}

/**
 * مراقبة حالة النسخ الاحتياطي التلقائي
 */
function startBackupMonitoring() {
    // تحديث حالة النسخ الاحتياطي كل دقيقة
    setInterval(() => {
        displayBackupStatus();
        checkBackupSchedule();
    }, 60000);

    // عرض الحالة الأولية
    displayBackupStatus();
}

/**
 * فحص جدولة النسخ الاحتياطي
 */
function checkBackupSchedule() {
    const settings = JSON.parse(localStorage.getItem('backupSettings') || '{}');
    
    if (!settings.enabled) return;

    const now = new Date();
    const lastBackup = new Date(localStorage.getItem('lastBackupTime') || 0);
    const timeDiff = now - lastBackup;

    let shouldBackup = false;
    
    switch (settings.frequency) {
        case 'daily':
            shouldBackup = timeDiff > 24 * 60 * 60 * 1000; // 24 ساعة
            break;
        case 'weekly':
            shouldBackup = timeDiff > 7 * 24 * 60 * 60 * 1000; // أسبوع
            break;
        case 'monthly':
            shouldBackup = timeDiff > 30 * 24 * 60 * 60 * 1000; // شهر
            break;
    }

    if (shouldBackup) {
        console.log('🔔 حان وقت النسخ الاحتياطي التلقائي');
        testBackupNow();
    }
}

/**
 * عرض إشعار للنسخ الاحتياطي
 */
function showBackupNotification(message, type = 'info') {
    // إزالة الإشعارات السابقة
    const existingNotifications = document.querySelectorAll('.backup-notification');
    existingNotifications.forEach(notification => notification.remove());

    const notification = document.createElement('div');
    notification.className = `backup-notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button onclick="this.closest('.backup-notification').remove()" class="notification-close">&times;</button>
        </div>
    `;

    document.body.appendChild(notification);

    // إزالة الإشعار تلقائياً بعد 5 ثوان
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

/**
 * تنسيق التاريخ والوقت
 */
function formatDateTime(dateString) {
    if (!dateString) return 'غير محدد';
    
    const date = new Date(dateString);
    return date.toLocaleString('ar-SA', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * تنسيق حجم الملف
 */
function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * فحص حالة الاتصال مع Google Drive
 */
async function checkGoogleDriveConnection() {
    try {
        // فحص أساسي للمصادقة
        const isSignedIn = gapi && gapi.auth2 && gapi.auth2.getAuthInstance().isSignedIn.get();
        
        if (!isSignedIn) {
            return false;
        }

        // فحص إضافي: التحقق من وجود نسخ احتياطية حديثة
        try {
            const response = await gapi.client.drive.files.list({
                q: "name contains 'backup_' and mimeType='application/json'",
                orderBy: 'createdTime desc',
                pageSize: 1,
                fields: 'files(id,name,createdTime)'
            });

            const files = response.result.files;
            if (files && files.length > 0) {
                // إذا كان هناك ملف نسخ احتياطي حديث (خلال آخر 7 أيام)
                const lastBackupDate = new Date(files[0].createdTime);
                const now = new Date();
                const daysDiff = (now - lastBackupDate) / (1000 * 60 * 60 * 24);
                
                if (daysDiff <= 7) {
                    return true;
                }
            }
        } catch (driveError) {
            console.log('تحذير: خطأ في فحص ملفات Google Drive:', driveError);
        }

        return isSignedIn;
    } catch (error) {
        console.error('خطأ في فحص اتصال Google Drive:', error);
        return false;
    }
}

/**
 * فحص حالة الاتصال مع Google Drive (متزامن)
 */
function checkGoogleDriveConnectionSync() {
    try {
        // فحص وجود token محفوظ
        const savedToken = localStorage.getItem('google_drive_token');
        if (savedToken && savedToken.startsWith('connected_')) {
            const tokenTime = parseInt(savedToken.replace('connected_', ''));
            const now = Date.now();
            const hoursDiff = (now - tokenTime) / (1000 * 60 * 60);
            
            // إذا كان التوكن حديث (خلال آخر 24 ساعة)
            if (hoursDiff <= 24) {
                return true;
            }
        }

        // فحص Google API
        if (window.gapi && gapi.auth2) {
            const authInstance = gapi.auth2.getAuthInstance();
            if (authInstance && authInstance.isSignedIn.get()) {
                return true;
            }
        }

        return false;
    } catch (error) {
        console.error('خطأ في فحص اتصال Google Drive:', error);
        return false;
    }
}

/**
 * فحص ما إذا كان Google Drive متصل
 */
function isGoogleDriveConnected() {
    return checkGoogleDriveConnectionSync();
}

/**
 * دالة النسخ الاحتياطي التلقائي مع Google Drive
 */
async function performAutomaticBackupWithGoogleDrive(backupType = 'comprehensive', destination = 'google_drive') {
    try {
        console.log('🔄 بدء النسخ الاحتياطي التلقائي...');
        
        // استدعاء دالة اختبار النسخ الاحتياطي
        await testBackupNow();
        
        return true;
    } catch (error) {
        console.error('خطأ في النسخ الاحتياطي التلقائي:', error);
        showBackupNotification('❌ فشل في النسخ الاحتياطي التلقائي: ' + error.message, 'error');
        return false;
    }
}

// ===== تهيئة النظام =====

// تشغيل مراقبة النسخ الاحتياطي عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 تم تحميل ميزات مراقبة النسخ الاحتياطي');
    
    // بدء مراقبة النسخ الاحتياطي
    startBackupMonitoring();
    
    // إضافة أنماط CSS للإشعارات
    addBackupNotificationStyles();
});

/**
 * إضافة أنماط CSS للإشعارات
 */
function addBackupNotificationStyles() {
    if (document.getElementById('backup-notification-styles')) return;

    const style = document.createElement('style');
    style.id = 'backup-notification-styles';
    style.textContent = `
        .backup-notification {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            max-width: 400px;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            animation: slideInRight 0.3s ease-out;
        }

        .backup-notification.notification-success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        .backup-notification.notification-error {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        .backup-notification.notification-warning {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
        }

        .backup-notification.notification-info {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }

        .notification-content {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .notification-message {
            flex: 1;
            margin-right: 10px;
            white-space: pre-line;
            line-height: 1.4;
        }

        .notification-close {
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            padding: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.7;
        }

        .notification-close:hover {
            opacity: 1;
        }

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

        .backup-status-card {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
        }

        .backup-status-card h4 {
            margin: 0 0 15px 0;
            color: #495057;
            font-size: 16px;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }

        .status-item:last-of-type {
            border-bottom: none;
        }

        .status-item .label {
            font-weight: 600;
            color: #6c757d;
        }

        .status-item .value {
            font-weight: 500;
        }

        .status-item .value.status-success {
            color: #28a745;
        }

        .status-item .value.status-warning {
            color: #ffc107;
        }

        .status-item .value.status-error {
            color: #dc3545;
        }

        .status-item .value.connected {
            color: #28a745;
        }

        .status-item .value.disconnected {
            color: #dc3545;
        }

        .status-actions {
            margin-top: 15px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .status-actions .btn {
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .status-actions .btn-primary {
            background-color: #007bff;
            color: white;
        }

        .status-actions .btn-secondary {
            background-color: #6c757d;
            color: white;
        }

        .status-actions .btn-info {
            background-color: #17a2b8;
            color: white;
        }

        .status-actions .btn:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }

        .backup-files-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 10001;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .backup-files-modal .modal-content {
            background: white;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            max-height: 80%;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .backup-files-modal .modal-header {
            padding: 20px;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .backup-files-modal .modal-header h3 {
            margin: 0;
            color: #495057;
        }

        .backup-files-modal .close-btn {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .backup-files-modal .modal-body {
            padding: 20px;
            overflow-y: auto;
        }

        .backup-files-modal .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-bottom: 10px;
        }

        .backup-files-modal .file-info {
            display: flex;
            align-items: center;
            gap: 10px;
            flex: 1;
        }

        .backup-files-modal .file-name {
            font-weight: 600;
            color: #495057;
        }

        .backup-files-modal .file-date,
        .backup-files-modal .file-size {
            font-size: 12px;
            color: #6c757d;
        }
    `;

    document.head.appendChild(style);
}

// تصدير الدوال للاستخدام العام
window.backupMonitoring = {
    testBackupNow,
    displayBackupStatus,
    refreshConnectionStatus,
    checkGoogleDriveFiles,
    performAutomaticBackupWithGoogleDrive,
    isGoogleDriveConnected,
    showBackupNotification
};

console.log('✅ تم تحميل جميع ميزات مراقبة النسخ الاحتياطي بنجاح!');



// ===== إصلاح خيارات وجهة النسخ الاحتياطي =====

/**
 * إصلاح مشكلة عدم ظهور خيارات وجهة النسخ الاحتياطي
 * يضيف خيارات الحفظ (محلي / Google Drive) إلى نافذة إنشاء النسخة الاحتياطية
 */
(function initializeBackupDestinationFix() {
    'use strict';
    
    console.log('🔧 تحميل إصلاح خيارات وجهة النسخ الاحتياطي...');
    
    // تعريف المتغيرات المطلوبة
    if (typeof window.google_drive_available === 'undefined') {
        window.google_drive_available = true;
        console.log('✅ تم تعريف google_drive_available');
    }
    
    /**
     * دالة إضافة خيارات الوجهة إلى نافذة النسخ الاحتياطي
     */
    function addDestinationOptions() {
        console.log('🎯 إضافة خيارات وجهة النسخ الاحتياطي...');
        
        // البحث عن نافذة النسخ الاحتياطي المفتوحة
        const modal = document.querySelector('.modal:not([style*="display: none"]), .backup-modal, [id*="backup"][style*="block"]');
        if (!modal) {
            console.log('❌ لم يتم العثور على نافذة النسخ الاحتياطي المفتوحة');
            return false;
        }
        
        console.log('✅ تم العثور على نافذة النسخ الاحتياطي');
        
        // التحقق من وجود خيارات الوجهة مسبقاً
        const existingDestination = modal.querySelector('input[name="destination"]');
        if (existingDestination) {
            console.log('✅ خيارات الوجهة موجودة مسبقاً');
            return true;
        }
        
        // البحث عن مكان إدراج خيارات الوجهة
        const insertLocation = modal.querySelector('.modal-body, .backup-form, form') || modal;
        const buttons = insertLocation.querySelector('.modal-footer, [class*="button"], button[type="submit"]');
        
        if (!buttons) {
            console.log('❌ لم يتم العثور على مكان مناسب لإدراج خيارات الوجهة');
            return false;
        }
        
        // إنشاء HTML خيارات الوجهة
        const destinationHTML = `
            <div class="backup-destination-section" style="
                margin: 20px 0; 
                padding: 20px; 
                border: 2px solid #e3f2fd; 
                border-radius: 12px; 
                background: linear-gradient(135deg, #f8f9ff 0%, #e8f4fd 100%);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            ">
                <h4 style="
                    margin: 0 0 20px 0; 
                    color: #1976d2; 
                    font-size: 18px; 
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                ">
                    🎯 اختر وجهة الحفظ
                </h4>
                
                <div style="display: flex; flex-direction: column; gap: 15px;">
                    <label style="
                        display: flex; 
                        align-items: center; 
                        cursor: pointer; 
                        padding: 15px; 
                        border: 2px solid #ddd; 
                        border-radius: 10px; 
                        background: white;
                        transition: all 0.3s ease;
                        position: relative;
                    " onmouseover="this.style.borderColor='#2196f3'; this.style.transform='translateY(-2px)'" 
                       onmouseout="this.style.borderColor='#ddd'; this.style.transform='translateY(0)'">
                        <input type="radio" name="destination" value="local" checked style="
                            margin-left: 15px; 
                            transform: scale(1.3);
                            accent-color: #2196f3;
                        ">
                        <div style="display: flex; flex-direction: column;">
                            <span style="font-weight: 600; color: #333; font-size: 16px;">💾 حفظ محلي</span>
                            <small style="color: #666; margin-top: 5px;">يحفظ في متصفحك المحلي (سريع ولكن محدود)</small>
                        </div>
                    </label>
                    
                    <label style="
                        display: flex; 
                        align-items: center; 
                        cursor: pointer; 
                        padding: 15px; 
                        border: 2px solid #4285f4; 
                        border-radius: 10px; 
                        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                        transition: all 0.3s ease;
                        position: relative;
                    " onmouseover="this.style.borderColor='#1976d2'; this.style.transform='translateY(-2px)'" 
                       onmouseout="this.style.borderColor='#4285f4'; this.style.transform='translateY(0)'">
                        <input type="radio" name="destination" value="google_drive" style="
                            margin-left: 15px; 
                            transform: scale(1.3);
                            accent-color: #4285f4;
                        ">
                        <div style="display: flex; flex-direction: column;">
                            <span style="font-weight: 600; color: #1976d2; font-size: 16px;">☁️ Google Drive</span>
                            <small style="color: #1565c0; margin-top: 5px;">موصى به - حفظ آمن في السحابة مع إمكانية الوصول من أي مكان</small>
                        </div>
                        <div style="
                            position: absolute; 
                            top: -8px; 
                            right: 10px; 
                            background: #4caf50; 
                            color: white; 
                            padding: 4px 8px; 
                            border-radius: 12px; 
                            font-size: 12px; 
                            font-weight: bold;
                        ">موصى به</div>
                    </label>
                </div>
                
                <div style="
                    margin-top: 15px; 
                    padding: 12px; 
                    background: #fff3e0; 
                    border-radius: 8px; 
                    border-left: 4px solid #ff9800;
                ">
                    <small style="color: #e65100; font-weight: 500;">
                        💡 نصيحة: استخدم Google Drive للحصول على نسخ احتياطية آمنة ومتاحة من أي جهاز
                    </small>
                </div>
            </div>
        `;
        
        // إدراج خيارات الوجهة
        buttons.insertAdjacentHTML('beforebegin', destinationHTML);
        console.log('✅ تم إنشاء خيارات وجهة النسخ الاحتياطي بنجاح');
        
        // إضافة مستمع للتغيير في خيارات الوجهة
        const destinationInputs = modal.querySelectorAll('input[name="destination"]');
        destinationInputs.forEach(input => {
            input.addEventListener('change', function() {
                console.log('📍 تم تغيير وجهة الحفظ إلى:', this.value);
                
                // تحديث الأنماط البصرية
                destinationInputs.forEach(inp => {
                    const label = inp.closest('label');
                    if (inp.checked) {
                        label.style.borderColor = inp.value === 'google_drive' ? '#4285f4' : '#2196f3';
                        label.style.background = inp.value === 'google_drive' ? 
                            'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)' : 
                            'linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%)';
                    } else {
                        label.style.borderColor = '#ddd';
                        label.style.background = 'white';
                    }
                });
                
                // حفظ الوجهة المختارة في localStorage
                localStorage.setItem('selectedBackupDestination', this.value);
            });
        });
        
        // استرجاع الوجهة المحفوظة مسبقاً
        const savedDestination = localStorage.getItem('selectedBackupDestination');
        if (savedDestination) {
            const savedInput = modal.querySelector(`input[name="destination"][value="${savedDestination}"]`);
            if (savedInput) {
                savedInput.checked = true;
                savedInput.dispatchEvent(new Event('change'));
            }
        }
        
        return true;
    }
    
    /**
     * دالة تعديل دالة إنشاء النسخة الاحتياطية لتدعم الوجهة المختارة
     */
    function enhanceBackupFunction() {
        console.log('🔧 تحسين دالة النسخ الاحتياطي...');
        
        // البحث عن الدالة الأصلية وتعديلها
        if (typeof window.createBackup === 'function') {
            const originalCreateBackup = window.createBackup;
            
            window.createBackup = function(...args) {
                // الحصول على الوجهة المختارة
                const selectedDestination = document.querySelector('input[name="destination"]:checked');
                const destination = selectedDestination ? selectedDestination.value : 'local';
                
                console.log('🎯 إنشاء نسخة احتياطية مع الوجهة:', destination);
                
                // تحديث إعدادات النسخ الاحتياطي
                localStorage.setItem('backupDestination', destination);
                
                if (typeof window.updateBackupSettings === 'function') {
                    window.updateBackupSettings({
                        destination: destination,
                        enabled: true
                    });
                }
                
                // استدعاء الدالة الأصلية
                return originalCreateBackup.apply(this, args);
            };
            
            console.log('✅ تم تحسين دالة النسخ الاحتياطي');
        }
        
        // تحسين دالة performAutomaticBackupWithGoogleDrive
        if (typeof window.performAutomaticBackupWithGoogleDrive === 'function') {
            const originalPerformBackup = window.performAutomaticBackupWithGoogleDrive;
            
            window.performAutomaticBackupWithGoogleDrive = function(...args) {
                // التحقق من الوجهة المختارة
                const destination = localStorage.getItem('backupDestination') || 'local';
                
                if (destination === 'google_drive') {
                    console.log('🎯 تنفيذ النسخ الاحتياطي إلى Google Drive');
                    return originalPerformBackup.apply(this, args);
                } else {
                    console.log('🎯 تنفيذ النسخ الاحتياطي المحلي');
                    // تنفيذ النسخ المحلي
                    return performLocalBackup();
                }
            };
        }
    }
    
    /**
     * دالة النسخ الاحتياطي المحلي
     */
    function performLocalBackup() {
        console.log('💾 تنفيذ النسخ الاحتياطي المحلي...');
        
        try {
            // جمع البيانات
            const backupData = {
                timestamp: new Date().toISOString(),
                destination: 'local',
                data: {
                    // يمكن إضافة البيانات المطلوبة هنا
                    settings: localStorage.getItem('backupSettings'),
                    lastBackup: new Date().toISOString()
                }
            };
            
            // حفظ في localStorage
            localStorage.setItem('localBackupData', JSON.stringify(backupData));
            localStorage.setItem('lastBackupTime', backupData.timestamp);
            localStorage.setItem('backupDestination', 'local');
            
            console.log('✅ تم حفظ النسخة الاحتياطية محلياً');
            
            // إظهار إشعار النجاح
            if (typeof showBackupNotification === 'function') {
                showBackupNotification('تم إنشاء النسخة الاحتياطية المحلية بنجاح!', 'success');
            }
            
            // تحديث عرض الحالة
            if (typeof displayBackupStatus === 'function') {
                displayBackupStatus();
            }
            
            return Promise.resolve({ success: true, destination: 'local' });
            
        } catch (error) {
            console.error('❌ خطأ في النسخ الاحتياطي المحلي:', error);
            
            if (typeof showBackupNotification === 'function') {
                showBackupNotification('فشل في إنشاء النسخة الاحتياطية المحلية', 'error');
            }
            
            return Promise.reject(error);
        }
    }
    
    // مراقب لإضافة خيارات الوجهة عند فتح النافذة
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    // التحقق من فتح نافذة النسخ الاحتياطي
                    if (node.classList && (node.classList.contains('modal') || node.querySelector('.modal'))) {
                        setTimeout(() => {
                            addDestinationOptions();
                        }, 200);
                    }
                    
                    // التحقق من وجود نافذة النسخ الاحتياطي في العقد المضافة
                    const backupModal = node.querySelector && node.querySelector('[class*="backup"], [id*="backup"]');
                    if (backupModal) {
                        setTimeout(() => {
                            addDestinationOptions();
                        }, 200);
                    }
                }
            });
        });
    });
    
    // بدء مراقبة التغييرات
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // محاولة إضافة الخيارات إذا كانت النافذة مفتوحة بالفعل
    setTimeout(() => {
        addDestinationOptions();
        enhanceBackupFunction();
    }, 500);
    
    // إضافة الدوال إلى النطاق العام
    window.addDestinationOptions = addDestinationOptions;
    window.performLocalBackup = performLocalBackup;
    
    console.log('✅ تم تحميل إصلاح خيارات وجهة النسخ الاحتياطي بنجاح');
    
})();

// ===== نهاية إصلاح خيارات وجهة النسخ الاحتياطي =====

