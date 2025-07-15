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
                this.updateBackupStatus(data);
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
                this.updateGoogleDriveStatus(data);
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
        
        if (this.lastBackupElement && googleDriveInfo.last_backup) {
            const lastBackupDate = new Date(googleDriveInfo.last_backup);
            this.lastBackupElement.textContent = this.formatDate(lastBackupDate);
        }
        
        if (this.destinationElement) {
            const isGoogleDriveConnected = googleDriveInfo.connected;
            const destinationText = isGoogleDriveConnected ? 'Google Drive' : 'محلي';
            this.destinationElement.textContent = destinationText;
        }
        
        // تحديث مؤشر الحالة
        if (this.statusElement) {
            const isRecent = this.isRecentBackup(googleDriveInfo.last_backup);
            this.statusElement.className = isRecent ? 'status-good' : 'status-warning';
            this.statusElement.textContent = isRecent ? 'نشط' : 'يحتاج تحديث';
        }
    }
    
    updateGoogleDriveStatus(data) {
        if (this.connectionElement) {
            // التحقق من البنية الجديدة للاستجابة
            const isConnected = data.status ? data.status.connected : data.connected;
            
            if (isConnected) {
                this.connectionElement.innerHTML = '✅ متصل';
                this.connectionElement.className = 'status-connected';
            } else {
                this.connectionElement.innerHTML = '❌ غير متصل';
                this.connectionElement.className = 'status-disconnected';
            }
        }
        
        // إظهار/إخفاء أزرار الاتصال
        const isConnected = data.status ? data.status.connected : data.connected;
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
            const response = await fetch('/api/v1/backup/google-drive/connect', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.auth_url) {
                    // فتح نافذة جديدة للتفويض
                    window.open(data.auth_url, 'google-auth', 'width=500,height=600');
                    
                    // مراقبة إغلاق النافذة
                    this.monitorAuthWindow();
                } else {
                    this.showError('فشل في الحصول على رابط التفويض');
                }
            } else {
                this.showError('فشل في بدء عملية الربط');
            }
        } catch (error) {
            console.error('خطأ في ربط Google Drive:', error);
            this.showError('خطأ في الاتصال بالخادم');
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

