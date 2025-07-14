/**
 * نظام مراقبة النسخ الاحتياطي المحسن
 * Enhanced Backup Monitoring System
 */

class BackupMonitor {
    constructor() {
        this.statusCheckInterval = null;
        this.lastBackupStatus = null;
        this.isMonitoring = false;
        
        // عناصر الواجهة
        this.statusElement = document.getElementById('backup-status');
        this.connectionElement = document.getElementById('google-drive-status');
        this.lastBackupElement = document.getElementById('last-backup-time');
        this.destinationElement = document.getElementById('backup-destination');
        
        this.init();
    }
    
    init() {
        console.log('تهيئة نظام مراقبة النسخ الاحتياطي...');
        
        // بدء المراقبة التلقائية
        this.startMonitoring();
        
        // ربط الأحداث
        this.bindEvents();
        
        // فحص الحالة الأولي
        this.checkBackupStatus();
        this.checkGoogleDriveConnection();
    }
    
    bindEvents() {
        // زر اختبار النسخ
        const testBackupBtn = document.getElementById('test-backup-btn');
        if (testBackupBtn) {
            testBackupBtn.addEventListener('click', () => this.testBackup());
        }
        
        // زر ربط Google Drive
        const connectGoogleBtn = document.getElementById('connect-google-drive');
        if (connectGoogleBtn) {
            connectGoogleBtn.addEventListener('click', () => this.connectGoogleDrive());
        }
        
        // زر قطع الاتصال
        const disconnectBtn = document.getElementById('disconnect-google-drive');
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', () => this.disconnectGoogleDrive());
        }
        
        // زر فحص ملفات Google Drive
        const checkFilesBtn = document.getElementById('check-google-files');
        if (checkFilesBtn) {
            checkFilesBtn.addEventListener('click', () => this.checkGoogleDriveFiles());
        }
        
        // زر تحديث الحالة
        const refreshStatusBtn = document.getElementById('refresh-status');
        if (refreshStatusBtn) {
            refreshStatusBtn.addEventListener('click', () => this.refreshStatus());
        }
    }
    
    startMonitoring() {
        if (this.isMonitoring) return;
        
        this.isMonitoring = true;
        
        // فحص الحالة كل 30 ثانية
        this.statusCheckInterval = setInterval(() => {
            this.checkBackupStatus();
            this.checkGoogleDriveConnection();
        }, 30000);
        
        console.log('تم بدء مراقبة النسخ الاحتياطي');
    }
    
    stopMonitoring() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
        this.isMonitoring = false;
        console.log('تم إيقاف مراقبة النسخ الاحتياطي');
    }
    
    async checkBackupStatus() {
        try {
            const response = await fetch('/api/v1/backup/status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.updateBackupStatus(data);
                } else {
                    console.error('فشل في الحصول على حالة النسخ الاحتياطي:', data.error);
                    this.showError('فشل في الحصول على حالة النسخ الاحتياطي');
                }
            } else {
                console.error('فشل في الحصول على حالة النسخ الاحتياطي');
                this.showError('فشل في الحصول على حالة النسخ الاحتياطي');
            }
        } catch (error) {
            console.error('خطأ في فحص حالة النسخ الاحتياطي:', error);
            this.showError('خطأ في الاتصال بالخادم');
        }
    }
    
    async checkGoogleDriveConnection() {
        try {
            const response = await fetch('/api/v1/google-drive/connection-status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.updateGoogleDriveStatus(data);
                } else {
                    console.error('فشل في فحص اتصال Google Drive:', data.error);
                }
            } else {
                console.error('فشل في فحص اتصال Google Drive');
            }
        } catch (error) {
            console.error('خطأ في فحص اتصال Google Drive:', error);
        }
    }
    
    updateBackupStatus(data) {
        // التعامل مع البنية الجديدة للاستجابة
        const status = data.status || data;
        const googleDriveInfo = status.google_drive || {};
        const settingsInfo = status.settings || {};
        
        // تحديث تاريخ آخر نسخة
        if (this.lastBackupElement) {
            let lastBackupTime = null;
            
            // البحث عن تاريخ آخر نسخة من مصادر متعددة
            if (settingsInfo.last_backup_time) {
                lastBackupTime = settingsInfo.last_backup_time;
            } else if (googleDriveInfo.last_backup) {
                lastBackupTime = googleDriveInfo.last_backup;
            }
            
            if (lastBackupTime) {
                const lastBackupDate = new Date(lastBackupTime);
                this.lastBackupElement.textContent = this.formatDate(lastBackupDate);
                this.lastBackupElement.style.color = '#4CAF50';
            } else {
                this.lastBackupElement.textContent = 'لم يتم إنشاء نسخة احتياطية بعد';
                this.lastBackupElement.style.color = '#ff9800';
            }
        }
        
        // تحديث وجهة النسخ الاحتياطي
        if (this.destinationElement) {
            const isGoogleDriveConnected = googleDriveInfo.connected;
            const backupDestination = settingsInfo.backup_destination || 'local';
            
            let destinationText = 'محلي';
            if (isGoogleDriveConnected && backupDestination === 'google_drive') {
                destinationText = 'Google Drive';
            } else if (backupDestination === 'google_drive' && !isGoogleDriveConnected) {
                destinationText = 'Google Drive (غير متصل)';
            }
            
            this.destinationElement.textContent = destinationText;
        }
        
        // تحديث مؤشر الحالة العامة
        if (this.statusElement) {
            const lastBackupTime = settingsInfo.last_backup_time || googleDriveInfo.last_backup;
            const isRecent = this.isRecentBackup(lastBackupTime);
            const autoBackupEnabled = settingsInfo.auto_backup_enabled;
            
            if (autoBackupEnabled && isRecent) {
                this.statusElement.className = 'status-good';
                this.statusElement.textContent = 'نشط';
            } else if (autoBackupEnabled && !isRecent) {
                this.statusElement.className = 'status-warning';
                this.statusElement.textContent = 'يحتاج تحديث';
            } else {
                this.statusElement.className = 'status-warning';
                this.statusElement.textContent = 'غير مفعل';
            }
        }
        
        // تحديث معلومات إضافية
        this.updateAdditionalInfo(status);
    }
    
    updateGoogleDriveStatus(data) {
        if (this.connectionElement) {
            // التحقق من البنية الجديدة للاستجابة
            const status = data.status || data;
            const isConnected = status.connected || false;
            
            if (isConnected) {
                this.connectionElement.innerHTML = '✅ متصل';
                this.connectionElement.className = 'status-connected';
            } else {
                this.connectionElement.innerHTML = '❌ غير متصل';
                this.connectionElement.className = 'status-disconnected';
            }
        }
        
        // إظهار/إخفاء أزرار الاتصال
        const status = data.status || data;
        const isConnected = status.connected || false;
        this.toggleConnectionButtons(isConnected);
    }
    
    toggleConnectionButtons(isConnected) {
        const connectBtn = document.getElementById('connect-google-drive');
        const disconnectBtn = document.getElementById('disconnect-google-drive');
        const checkFilesBtn = document.getElementById('check-google-files');
        
        if (connectBtn) {
            connectBtn.style.display = isConnected ? 'none' : 'inline-block';
        }
        
        if (disconnectBtn) {
            disconnectBtn.style.display = isConnected ? 'inline-block' : 'none';
        }
        
        if (checkFilesBtn) {
            checkFilesBtn.style.display = isConnected ? 'inline-block' : 'none';
        }
    }
    
    updateAdditionalInfo(status) {
        // تحديث معلومات الجدولة
        const schedulerInfo = status.scheduler || {};
        const schedulerStatusElement = document.getElementById('scheduler-status');
        if (schedulerStatusElement) {
            if (schedulerInfo.user_scheduled) {
                schedulerStatusElement.textContent = 'مجدول';
                schedulerStatusElement.className = 'status-good';
            } else {
                schedulerStatusElement.textContent = 'غير مجدول';
                schedulerStatusElement.className = 'status-warning';
            }
        }
        
        // تحديث موعد النسخة التالية
        const nextBackupElement = document.getElementById('next-backup-time');
        if (nextBackupElement && schedulerInfo.next_backup) {
            const nextBackupDate = new Date(schedulerInfo.next_backup);
            nextBackupElement.textContent = this.formatDate(nextBackupDate);
        } else if (nextBackupElement) {
            nextBackupElement.textContent = 'غير محدد';
        }
        
        // تحديث تكرار النسخ
        const frequencyElement = document.getElementById('backup-frequency');
        if (frequencyElement) {
            const settings = status.settings || {};
            const frequency = settings.backup_frequency || 'daily';
            const frequencyText = {
                'daily': 'يومي',
                'weekly': 'أسبوعي',
                'monthly': 'شهري'
            };
            frequencyElement.textContent = frequencyText[frequency] || frequency;
        }
        
        // تحديث عدد النسخ المحفوظة (من إعدادات الحد الأقصى)
        const countElement = document.getElementById('backup-count');
        if (countElement && status.settings) {
            countElement.textContent = `الحد الأقصى: ${status.settings.max_backups || 5}`;
        }
        
        // تحديث آخر نسخة احتياطية (من Google Drive أو إعدادات)
        const lastBackupElement = document.getElementById('last-backup-time');
        if (lastBackupElement) {
            let lastBackupTime = null;
            
            // البحث عن آخر نسخة من Google Drive
            if (status.google_drive && status.google_drive.last_backup) {
                lastBackupTime = status.google_drive.last_backup;
            }
            // أو من إعدادات النظام
            else if (status.settings && status.settings.updated_at) {
                lastBackupTime = status.settings.updated_at;
            }
            
            if (lastBackupTime) {
                const lastDate = new Date(lastBackupTime);
                lastBackupElement.textContent = this.formatDate(lastDate);
            } else {
                lastBackupElement.textContent = 'لم يتم إنشاء نسخة بعد';
            }
        }
        
        // تحديث وجهة النسخ
        const destinationElement = document.getElementById('backup-destination');
        if (destinationElement && status.settings) {
            destinationElement.textContent = status.settings.backup_destination === 'google_drive' ? 'Google Drive' : 'محلي';
        }
        
        // تحديث حالة Google Drive
        const googleDriveElement = document.getElementById('google-drive-status');
        if (googleDriveElement && status.google_drive) {
            if (status.google_drive.connected) {
                googleDriveElement.textContent = '✅ متصل';
                googleDriveElement.className = 'status-good';
            } else {
                googleDriveElement.textContent = '❌ غير متصل';
                googleDriveElement.className = 'status-error';
            }
        }
    }

    async testBackup() {
        const testBtn = document.getElementById('test-backup-btn');
        if (testBtn) {
            testBtn.disabled = true;
            testBtn.textContent = 'جاري الاختبار...';
        }
        
        try {
            const response = await fetch('/api/v1/backup/immediate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('تم النسخ الاحتياطي بنجاح');
                // تحديث الحالة فوراً
                setTimeout(() => this.checkBackupStatus(), 1000);
            } else {
                this.showError(data.error || 'فشل في النسخ الاحتياطي');
            }
        } catch (error) {
            console.error('خطأ في اختبار النسخ الاحتياطي:', error);
            this.showError('خطأ في الاتصال بالخادم');
        } finally {
            if (testBtn) {
                testBtn.disabled = false;
                testBtn.textContent = 'اختبار النسخ الآن';
            }
        }
    }
    
    async connectGoogleDrive() {
        try {
            console.log('🔗 بدء عملية ربط Google Drive...');
            
            // الحصول على إعدادات Google OAuth
            const configResponse = await fetch('/api/v1/google-oauth/config');
            const config = await configResponse.json();
            
            if (!config.success || !config.client_id) {
                this.showError('إعدادات Google OAuth غير متوفرة');
                return;
            }
            
            // إعداد معاملات OAuth
            const clientId = config.client_id;
            const redirectUri = `${window.location.origin}/auth/google/callback`;
            const scope = 'https://www.googleapis.com/auth/drive.file';
            const responseType = 'code';
            const accessType = 'offline';
            const prompt = 'consent';
            
            // إضافة user_id كـ state parameter
            let state = '';
            try {
                const userResponse = await fetch('/api/v1/user/info');
                if (userResponse.ok) {
                    const userData = await userResponse.json();
                    if (userData.success && userData.user) {
                        state = userData.user.id.toString();
                    }
                }
            } catch (e) {
                console.warn('لا يمكن الحصول على معلومات المستخدم:', e);
            }
            
            // بناء URL للمصادقة
            const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
                `client_id=${encodeURIComponent(clientId)}&` +
                `redirect_uri=${encodeURIComponent(redirectUri)}&` +
                `scope=${encodeURIComponent(scope)}&` +
                `response_type=${responseType}&` +
                `access_type=${accessType}&` +
                `prompt=${prompt}&` +
                `state=${state}`;
            
            console.log('🌐 فتح نافذة المصادقة...');
            console.log('📍 Redirect URI:', redirectUri);
            
            // فتح نافذة المصادقة
            const authWindow = window.open(
                authUrl,
                'google-auth',
                'width=500,height=600,scrollbars=yes,resizable=yes'
            );
            
            if (!authWindow) {
                this.showError('لا يمكن فتح نافذة المصادقة. تأكد من السماح للنوافذ المنبثقة');
                return;
            }
            
            // الاستماع لرسائل من نافذة المصادقة
            const messageHandler = (event) => {
                // التحقق من مصدر الرسالة للأمان
                if (event.origin !== window.location.origin) {
                    return;
                }
                
                console.log('📨 تم استلام رسالة من نافذة OAuth:', event.data);
                
                if (event.data.type === 'google-auth-success') {
                    console.log('✅ نجح ربط Google Drive');
                    this.showSuccess('تم ربط Google Drive بنجاح');
                    
                    // تحديث الحالة
                    setTimeout(() => {
                        this.checkGoogleDriveConnection();
                        this.checkBackupStatus();
                    }, 1000);
                    
                    // إزالة مستمع الأحداث
                    window.removeEventListener('message', messageHandler);
                    
                } else if (event.data.type === 'google-auth-error') {
                    console.error('❌ فشل في ربط Google Drive:', event.data);
                    this.showError(event.data.message || 'فشل في ربط Google Drive');
                    
                    // إزالة مستمع الأحداث
                    window.removeEventListener('message', messageHandler);
                }
            };
            
            // إضافة مستمع الأحداث
            window.addEventListener('message', messageHandler);
            
            // مراقبة إغلاق النافذة
            const checkClosed = setInterval(() => {
                if (authWindow.closed) {
                    clearInterval(checkClosed);
                    window.removeEventListener('message', messageHandler);
                    console.log('🔒 تم إغلاق نافذة المصادقة');
                }
            }, 1000);
            
        } catch (error) {
            console.error('❌ خطأ في ربط Google Drive:', error);
            this.showError('خطأ في ربط Google Drive: ' + error.message);
        }
    }
    
    monitorAuthWindow() {
        // إضافة مستمع لرسائل النافذة
        const messageHandler = (event) => {
            if (event.data && event.data.type === 'google-auth-success') {
                this.showSuccess('تم ربط Google Drive بنجاح');
                setTimeout(() => this.checkGoogleDriveConnection(), 1000);
                window.removeEventListener('message', messageHandler);
            } else if (event.data && event.data.type === 'google-auth-error') {
                this.showError('فشل في ربط Google Drive');
                window.removeEventListener('message', messageHandler);
            }
        };
        
        window.addEventListener('message', messageHandler);
        
        // إزالة المستمع بعد 5 دقائق
        setTimeout(() => {
            window.removeEventListener('message', messageHandler);
        }, 300000);
    }
    
    async disconnectGoogleDrive() {
        if (!confirm('هل أنت متأكد من قطع الاتصال مع Google Drive؟')) {
            return;
        }
        
        try {
            const response = await fetch('/api/v1/backup/google-drive/disconnect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                this.showSuccess('تم قطع الاتصال مع Google Drive');
                setTimeout(() => this.checkGoogleDriveConnection(), 1000);
            } else {
                this.showError('فشل في قطع الاتصال');
            }
        } catch (error) {
            console.error('خطأ في قطع الاتصال:', error);
            this.showError('خطأ في الاتصال بالخادم');
        }
    }
    
    async checkGoogleDriveFiles() {
        try {
            const response = await fetch('/api/v1/backup/google-drive/backups', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showGoogleDriveFiles(data.backups || []);
            } else {
                this.showError('فشل في الحصول على ملفات Google Drive');
            }
        } catch (error) {
            console.error('خطأ في فحص ملفات Google Drive:', error);
            this.showError('خطأ في الاتصال بالخادم');
        }
    }
    
    showGoogleDriveFiles(files) {
        let message = 'ملفات النسخ الاحتياطي في Google Drive:\\n\\n';
        
        if (files.length === 0) {
            message += 'لا توجد ملفات نسخ احتياطي';
        } else {
            files.forEach((file, index) => {
                const date = new Date(file.createdTime).toLocaleString('ar-SA');
                message += `${index + 1}. ${file.name} (${date})\\n`;
            });
        }
        
        alert(message);
    }
    
    refreshStatus() {
        this.checkBackupStatus();
        this.checkGoogleDriveConnection();
        this.showSuccess('تم تحديث الحالة');
    }
    
    isRecentBackup(lastBackupTime) {
        if (!lastBackupTime) return false;
        
        const lastBackup = new Date(lastBackupTime);
        const now = new Date();
        const diffHours = (now - lastBackup) / (1000 * 60 * 60);
        
        // اعتبار النسخة حديثة إذا كانت خلال آخر 25 ساعة
        return diffHours < 25;
    }
    
    formatDate(date) {
        return date.toLocaleString('ar-SA', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showNotification(message, type) {
        // إنشاء عنصر الإشعار
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // إضافة الإشعار للصفحة
        document.body.appendChild(notification);
        
        // إزالة الإشعار بعد 5 ثوان
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
        
        // إضافة إمكانية الإغلاق بالنقر
        notification.addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }
}

// تهيئة النظام عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // التحقق من وجود عناصر النسخ الاحتياطي في الصفحة
    if (document.getElementById('backup-status') || 
        document.querySelector('.backup-section')) {
        
        window.backupMonitor = new BackupMonitor();
        console.log('تم تهيئة نظام مراقبة النسخ الاحتياطي');
    }
});

// إضافة أنماط CSS للإشعارات
const style = document.createElement('style');
style.textContent = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        z-index: 10000;
        cursor: pointer;
        max-width: 300px;
        word-wrap: break-word;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: opacity 0.3s ease;
    }
    
    .notification-success {
        background-color: #4CAF50;
    }
    
    .notification-error {
        background-color: #f44336;
    }
    
    .status-good {
        color: #4CAF50;
        font-weight: bold;
    }
    
    .status-warning {
        color: #ff9800;
        font-weight: bold;
    }
    
    .status-connected {
        color: #4CAF50;
    }
    
    .status-disconnected {
        color: #f44336;
    }
    
    .backup-section {
        margin: 20px 0;
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: #f9f9f9;
    }
    
    .backup-section h4 {
        margin-top: 0;
        color: #333;
    }
    
    .backup-controls {
        margin-top: 10px;
    }
    
    .backup-controls button {
        margin-right: 10px;
        margin-bottom: 5px;
        padding: 8px 15px;
        border: none;
        border-radius: 3px;
        cursor: pointer;
        font-size: 14px;
    }
    
    .backup-controls button:hover {
        opacity: 0.8;
    }
    
    .backup-controls button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
`;
document.head.appendChild(style);

