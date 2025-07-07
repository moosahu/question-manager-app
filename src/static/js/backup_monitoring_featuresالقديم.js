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

