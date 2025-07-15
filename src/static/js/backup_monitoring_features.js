/**
 * نظام مراقبة النسخ الاحتياطي المحسن
 * يوفر واجهة شاملة لمراقبة وإدارة النسخ الاحتياطية
 */

class BackupMonitoringSystem {
    constructor() {
        this.isInitialized = false;
        this.refreshInterval = null;
        this.lastUpdateTime = null;
        
        // إعدادات النظام
        this.settings = {
            autoRefresh: true,
            refreshIntervalMs: 30000, // 30 ثانية
            maxRetries: 3,
            retryDelay: 2000 // 2 ثانية
        };
        
        // حالة النظام
        this.state = {
            isConnected: false,
            lastBackupTime: null,
            backupCount: 0,
            connectionStatus: 'disconnected'
        };
        
        console.log('🔧 تم تهيئة نظام مراقبة النسخ الاحتياطي');
    }

    /**
     * تهيئة النظام وربط الأحداث
     */
    async init() {
        try {
            console.log('🚀 بدء تهيئة نظام مراقبة النسخ الاحتياطي...');
            
            // التحقق من وجود العناصر المطلوبة
            if (!this.checkRequiredElements()) {
                console.warn('⚠️ بعض العناصر المطلوبة غير موجودة');
                return false;
            }
            
            // ربط الأحداث
            this.bindEvents();
            
            // تحديث الحالة الأولية
            await this.updateStatus();
            
            // بدء التحديث التلقائي
            if (this.settings.autoRefresh) {
                this.startAutoRefresh();
            }
            
            this.isInitialized = true;
            console.log('✅ تم تهيئة نظام مراقبة النسخ الاحتياطي بنجاح');
            return true;
            
        } catch (error) {
            console.error('❌ خطأ في تهيئة نظام مراقبة النسخ الاحتياطي:', error);
            return false;
        }
    }

    /**
     * التحقق من وجود العناصر المطلوبة في DOM
     */
    checkRequiredElements() {
        const requiredElements = [
            'backup-status-container',
            'google-drive-status',
            'backup-stats-container'
        ];
        
        let allFound = true;
        requiredElements.forEach(id => {
            const element = document.getElementById(id);
            if (!element) {
                console.warn(`⚠️ العنصر غير موجود: ${id}`);
                allFound = false;
            }
        });
        
        return allFound;
    }

    /**
     * ربط الأحداث بالعناصر
     */
    bindEvents() {
        // زر النسخ الفوري
        const immediateBackupBtn = document.getElementById('immediate-backup-btn');
        if (immediateBackupBtn) {
            immediateBackupBtn.addEventListener('click', () => this.triggerImmediateBackup());
        }
        
        // زر تحديث الحالة
        const refreshStatusBtn = document.getElementById('refresh-status-btn');
        if (refreshStatusBtn) {
            refreshStatusBtn.addEventListener('click', () => this.updateStatus());
        }
        
        // زر ربط Google Drive
        const connectDriveBtn = document.getElementById('connect-google-drive-btn');
        if (connectDriveBtn) {
            connectDriveBtn.addEventListener('click', () => this.connectGoogleDrive());
        }
        
        console.log('🔗 تم ربط الأحداث بالعناصر');
    }

    /**
     * تحديث حالة النسخ الاحتياطي
     */
    async updateStatus() {
        try {
            console.log('🔄 تحديث حالة النسخ الاحتياطي...');
            
            // عرض مؤشر التحميل
            this.showLoadingState();
            
            // جلب حالة النسخ الاحتياطي
            const backupStatus = await this.fetchBackupStatus();
            
            // جلب حالة Google Drive
            const driveStatus = await this.fetchGoogleDriveStatus();
            
            // تحديث الواجهة
            this.updateBackupStatusUI(backupStatus);
            this.updateGoogleDriveStatusUI(driveStatus);
            this.updateStatsUI(backupStatus, driveStatus);
            
            // تحديث الحالة الداخلية
            this.updateInternalState(backupStatus, driveStatus);
            
            // إخفاء مؤشر التحميل
            this.hideLoadingState();
            
            this.lastUpdateTime = new Date();
            console.log('✅ تم تحديث الحالة بنجاح');
            
        } catch (error) {
            console.error('❌ خطأ في تحديث الحالة:', error);
            this.showErrorState(error.message);
        }
    }

    /**
     * جلب حالة النسخ الاحتياطي من الخادم
     */
    async fetchBackupStatus() {
        try {
            const response = await fetch('/api/v1/backup/status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('📊 حالة النسخ الاحتياطي:', data);
            return data;
            
        } catch (error) {
            console.error('❌ خطأ في جلب حالة النسخ الاحتياطي:', error);
            throw error;
        }
    }

    /**
     * جلب حالة Google Drive من الخادم
     */
    async fetchGoogleDriveStatus() {
        try {
            const response = await fetch('/api/v1/google-drive/connection-status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('☁️ حالة Google Drive:', data);
            return data;
            
        } catch (error) {
            console.error('❌ خطأ في جلب حالة Google Drive:', error);
            throw error;
        }
    }

    /**
     * تحديث واجهة حالة النسخ الاحتياطي
     */
    updateBackupStatusUI(status) {
        const container = document.getElementById('backup-status-container');
        if (!container) return;
        
        const isEnabled = status?.status?.settings?.auto_backup_enabled || false;
        const lastBackup = status?.status?.settings?.last_backup_time;
        const frequency = status?.status?.settings?.backup_frequency || 'daily';
        
        container.innerHTML = `
            <div class="backup-status-card">
                <div class="status-header">
                    <h4>حالة النسخ الاحتياطي</h4>
                    <span class="status-badge ${isEnabled ? 'enabled' : 'disabled'}">
                        ${isEnabled ? 'مفعل' : 'معطل'}
                    </span>
                </div>
                <div class="status-details">
                    <div class="detail-item">
                        <span class="label">التكرار:</span>
                        <span class="value">${this.getFrequencyText(frequency)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">آخر نسخة:</span>
                        <span class="value">${lastBackup ? this.formatDate(lastBackup) : 'لا توجد'}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * تحديث واجهة حالة Google Drive
     */
    updateGoogleDriveStatusUI(status) {
        const container = document.getElementById('google-drive-status');
        if (!container) return;
        
        const isConnected = status?.status?.connected || false;
        const lastBackup = status?.status?.last_backup;
        const backupCount = status?.status?.backup_count || 0;
        
        container.innerHTML = `
            <div class="drive-status-card">
                <div class="status-header">
                    <h4>Google Drive</h4>
                    <span class="connection-badge ${isConnected ? 'connected' : 'disconnected'}">
                        ${isConnected ? 'متصل' : 'غير متصل'}
                    </span>
                </div>
                <div class="status-details">
                    <div class="detail-item">
                        <span class="label">عدد النسخ:</span>
                        <span class="value">${backupCount}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">آخر نسخة:</span>
                        <span class="value">${lastBackup ? this.formatDate(lastBackup) : 'لا توجد'}</span>
                    </div>
                </div>
                <div class="action-buttons">
                    ${!isConnected ? 
                        '<button id="connect-google-drive-btn" class="btn btn-primary">ربط Google Drive</button>' :
                        '<button id="disconnect-google-drive-btn" class="btn btn-secondary">قطع الاتصال</button>'
                    }
                </div>
            </div>
        `;
        
        // إعادة ربط الأحداث للأزرار الجديدة
        this.rebindDriveButtons();
    }

    /**
     * تحديث واجهة الإحصائيات
     */
    updateStatsUI(backupStatus, driveStatus) {
        const container = document.getElementById('backup-stats-container');
        if (!container) return;
        
        const totalBackups = (driveStatus?.status?.backup_count || 0);
        const isConnected = driveStatus?.status?.connected || false;
        const autoBackupEnabled = backupStatus?.status?.settings?.auto_backup_enabled || false;
        
        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">${totalBackups}</div>
                    <div class="stat-label">إجمالي النسخ</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${isConnected ? '1' : '0'}</div>
                    <div class="stat-label">الخدمات المتصلة</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${autoBackupEnabled ? 'مفعل' : 'معطل'}</div>
                    <div class="stat-label">النسخ التلقائي</div>
                </div>
            </div>
            <div class="action-section">
                <button id="immediate-backup-btn" class="btn btn-success" ${!isConnected ? 'disabled' : ''}>
                    نسخ احتياطي فوري
                </button>
                <button id="refresh-status-btn" class="btn btn-outline-primary">
                    تحديث الحالة
                </button>
            </div>
        `;
        
        // إعادة ربط الأحداث للأزرار الجديدة
        this.rebindActionButtons();
    }

    /**
     * إعادة ربط أحداث أزرار Google Drive
     */
    rebindDriveButtons() {
        const connectBtn = document.getElementById('connect-google-drive-btn');
        const disconnectBtn = document.getElementById('disconnect-google-drive-btn');
        
        if (connectBtn) {
            connectBtn.addEventListener('click', () => this.connectGoogleDrive());
        }
        
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', () => this.disconnectGoogleDrive());
        }
    }

    /**
     * إعادة ربط أحداث أزرار الإجراءات
     */
    rebindActionButtons() {
        const immediateBtn = document.getElementById('immediate-backup-btn');
        const refreshBtn = document.getElementById('refresh-status-btn');
        
        if (immediateBtn) {
            immediateBtn.addEventListener('click', () => this.triggerImmediateBackup());
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.updateStatus());
        }
    }

    /**
     * تشغيل نسخ احتياطي فوري
     */
    async triggerImmediateBackup() {
        try {
            console.log('⚡ تشغيل نسخ احتياطي فوري...');
            
            const button = document.getElementById('immediate-backup-btn');
            if (button) {
                button.disabled = true;
                button.textContent = 'جاري النسخ...';
            }
            
            const response = await fetch('/api/v1/backup/immediate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccessMessage('تم تشغيل النسخ الاحتياطي الفوري بنجاح');
                // تحديث الحالة بعد النسخ
                setTimeout(() => this.updateStatus(), 2000);
            } else {
                throw new Error(data.message || 'فشل في تشغيل النسخ الاحتياطي');
            }
            
        } catch (error) {
            console.error('❌ خطأ في النسخ الاحتياطي الفوري:', error);
            this.showErrorMessage('فشل في تشغيل النسخ الاحتياطي: ' + error.message);
        } finally {
            const button = document.getElementById('immediate-backup-btn');
            if (button) {
                button.disabled = false;
                button.textContent = 'نسخ احتياطي فوري';
            }
        }
    }

    /**
     * ربط Google Drive
     */
    async connectGoogleDrive() {
        try {
            console.log('🔗 محاولة ربط Google Drive...');
            this.showInfoMessage('جاري ربط Google Drive...');
            
            // هنا يجب تنفيذ عملية OAuth مع Google
            // للآن سنعرض رسالة تنبيه
            alert('ميزة ربط Google Drive قيد التطوير. يرجى المحاولة لاحقاً.');
            
        } catch (error) {
            console.error('❌ خطأ في ربط Google Drive:', error);
            this.showErrorMessage('فشل في ربط Google Drive: ' + error.message);
        }
    }

    /**
     * قطع اتصال Google Drive
     */
    async disconnectGoogleDrive() {
        try {
            console.log('🔌 قطع اتصال Google Drive...');
            
            const response = await fetch('/api/v1/google-drive/disconnect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccessMessage('تم قطع الاتصال مع Google Drive');
                this.updateStatus();
            } else {
                throw new Error(data.message || 'فشل في قطع الاتصال');
            }
            
        } catch (error) {
            console.error('❌ خطأ في قطع اتصال Google Drive:', error);
            this.showErrorMessage('فشل في قطع الاتصال: ' + error.message);
        }
    }

    /**
     * تحديث الحالة الداخلية
     */
    updateInternalState(backupStatus, driveStatus) {
        this.state.isConnected = driveStatus?.status?.connected || false;
        this.state.lastBackupTime = driveStatus?.status?.last_backup;
        this.state.backupCount = driveStatus?.status?.backup_count || 0;
        this.state.connectionStatus = this.state.isConnected ? 'connected' : 'disconnected';
    }

    /**
     * بدء التحديث التلقائي
     */
    startAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        this.refreshInterval = setInterval(() => {
            this.updateStatus();
        }, this.settings.refreshIntervalMs);
        
        console.log(`🔄 تم بدء التحديث التلقائي كل ${this.settings.refreshIntervalMs / 1000} ثانية`);
    }

    /**
     * إيقاف التحديث التلقائي
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            console.log('⏹️ تم إيقاف التحديث التلقائي');
        }
    }

    /**
     * عرض حالة التحميل
     */
    showLoadingState() {
        const containers = ['backup-status-container', 'google-drive-status', 'backup-stats-container'];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.classList.add('loading');
            }
        });
    }

    /**
     * إخفاء حالة التحميل
     */
    hideLoadingState() {
        const containers = ['backup-status-container', 'google-drive-status', 'backup-stats-container'];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.classList.remove('loading');
            }
        });
    }

    /**
     * عرض حالة الخطأ
     */
    showErrorState(message) {
        const containers = ['backup-status-container', 'google-drive-status', 'backup-stats-container'];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.innerHTML = `
                    <div class="error-state">
                        <div class="error-icon">⚠️</div>
                        <div class="error-message">${message}</div>
                        <button onclick="backupMonitor.updateStatus()" class="btn btn-sm btn-outline-primary">
                            إعادة المحاولة
                        </button>
                    </div>
                `;
            }
        });
    }

    /**
     * عرض رسالة نجاح
     */
    showSuccessMessage(message) {
        this.showNotification(message, 'success');
    }

    /**
     * عرض رسالة خطأ
     */
    showErrorMessage(message) {
        this.showNotification(message, 'error');
    }

    /**
     * عرض رسالة معلومات
     */
    showInfoMessage(message) {
        this.showNotification(message, 'info');
    }

    /**
     * عرض إشعار
     */
    showNotification(message, type = 'info') {
        // إنشاء عنصر الإشعار
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;
        
        // إضافة الإشعار للصفحة
        document.body.appendChild(notification);
        
        // ربط حدث الإغلاق
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            notification.remove();
        });
        
        // إزالة الإشعار تلقائياً بعد 5 ثوان
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    /**
     * تحويل تكرار النسخ إلى نص
     */
    getFrequencyText(frequency) {
        const frequencies = {
            'daily': 'يومي',
            'weekly': 'أسبوعي',
            'monthly': 'شهري'
        };
        return frequencies[frequency] || frequency;
    }

    /**
     * تنسيق التاريخ
     */
    formatDate(dateString) {
        if (!dateString) return 'غير محدد';
        
        try {
            const date = new Date(dateString);
            return date.toLocaleString('ar-SA', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (error) {
            return 'تاريخ غير صحيح';
        }
    }

    /**
     * تنظيف الموارد
     */
    destroy() {
        this.stopAutoRefresh();
        this.isInitialized = false;
        console.log('🧹 تم تنظيف نظام مراقبة النسخ الاحتياطي');
    }
}

// إنشاء مثيل النظام
let backupMonitor = null;

// تهيئة النظام عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', async function() {
    console.log('📄 تم تحميل الصفحة، بدء تهيئة نظام مراقبة النسخ الاحتياطي...');
    
    try {
        backupMonitor = new BackupMonitoringSystem();
        const success = await backupMonitor.init();
        
        if (success) {
            console.log('✅ تم تهيئة نظام مراقبة النسخ الاحتياطي بنجاح');
        } else {
            console.warn('⚠️ فشل في تهيئة نظام مراقبة النسخ الاحتياطي');
        }
    } catch (error) {
        console.error('❌ خطأ في تهيئة نظام مراقبة النسخ الاحتياطي:', error);
    }
});

// تنظيف الموارد عند مغادرة الصفحة
window.addEventListener('beforeunload', function() {
    if (backupMonitor) {
        backupMonitor.destroy();
    }
});

// تصدير النظام للاستخدام العام
window.BackupMonitoringSystem = BackupMonitoringSystem;
window.backupMonitor = backupMonitor;

