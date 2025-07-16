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
        
        // ربط أحداث النسخ التلقائي
        this.bindAutoBackupEvents();
        
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
        
        // زر النسخ الفوري
        const immediateBackupBtn = document.getElementById('immediate-backup-btn');
        if (immediateBackupBtn) {
            immediateBackupBtn.addEventListener('click', () => this.testBackup());
        }
        
        // زر ربط Google Drive
        const connectGoogleBtn = document.getElementById('connect-google-drive');
        if (connectGoogleBtn) {
            connectGoogleBtn.addEventListener('click', () => this.connectGoogleDrive());
        }
        
        // زر ربط Google Drive البديل
        const connectGoogleDriveBtn = document.getElementById('connect-google-drive-btn');
        if (connectGoogleDriveBtn) {
            connectGoogleDriveBtn.addEventListener('click', () => this.connectGoogleDrive());
        }
        
        // زر قطع الاتصال
        const disconnectBtn = document.getElementById('disconnect-google-drive');
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', () => this.disconnectGoogleDrive());
        }
        
        // زر قطع الاتصال البديل
        const disconnectGoogleDriveBtn = document.getElementById('disconnect-google-drive-btn');
        if (disconnectGoogleDriveBtn) {
            disconnectGoogleDriveBtn.addEventListener('click', () => this.disconnectGoogleDrive());
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
        
        // زر تحديث الحالة البديل
        const refreshStatusBtnAlt = document.getElementById('refresh-status-btn');
        if (refreshStatusBtnAlt) {
            refreshStatusBtnAlt.addEventListener('click', () => this.refreshStatus());
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
            // استخدام API للاختبار إذا كان المستخدم غير مسجل دخول
            let apiUrl = '/api/v1/backup/status';
            
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            // إذا فشل الطلب بسبب عدم تسجيل الدخول، استخدم API الاختبار
            if (!response.ok && response.status === 401) {
                console.log('المستخدم غير مسجل دخول، استخدام API الاختبار...');
                const testResponse = await fetch('/api/v1/backup/test-status', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                });
                
                if (testResponse.ok) {
                    const data = await testResponse.json();
                    if (data.success) {
                        this.updateBackupStatus(data);
                        return;
                    }
                }
            }
            
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
                },
                credentials: 'same-origin'
            });
            
            // إذا فشل الطلب بسبب عدم تسجيل الدخول، استخدم API الاختبار
            if (!response.ok && response.status === 401) {
                console.log('المستخدم غير مسجل دخول، استخدام API اختبار Google Drive...');
                const testResponse = await fetch('/api/v1/google-drive/test-connection-status', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                });
                
                if (testResponse.ok) {
                    const data = await testResponse.json();
                    if (data.success) {
                        this.updateGoogleDriveStatus(data);
                        return;
                    }
                }
            }
            
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
        
        // تحديث واجهة الإحصائيات إذا كانت موجودة
        this.updateStatsUI(status);
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
        
        // تحديث واجهة Google Drive إذا كانت موجودة
        this.updateGoogleDriveStatusUI(data);
    }
    
    toggleConnectionButtons(isConnected) {
        const connectBtn = document.getElementById('connect-google-drive');
        const disconnectBtn = document.getElementById('disconnect-google-drive');
        const checkFilesBtn = document.getElementById('check-google-files');
        const connectGoogleDriveBtn = document.getElementById('connect-google-drive-btn');
        const disconnectGoogleDriveBtn = document.getElementById('disconnect-google-drive-btn');
        
        if (connectBtn) {
            connectBtn.style.display = isConnected ? 'none' : 'inline-block';
        }
        
        if (connectGoogleDriveBtn) {
            connectGoogleDriveBtn.style.display = isConnected ? 'none' : 'inline-block';
        }
        
        if (disconnectBtn) {
            disconnectBtn.style.display = isConnected ? 'inline-block' : 'none';
        }
        
        if (disconnectGoogleDriveBtn) {
            disconnectGoogleDriveBtn.style.display = isConnected ? 'inline-block' : 'none';
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
    
    /**
     * تحديث واجهة الإحصائيات الجديدة
     */
    updateStatsUI(status) {
        const container = document.getElementById('backup-stats-container');
        if (!container) return;
        
        const googleDriveInfo = status.google_drive || {};
        const settingsInfo = status.settings || {};
        const totalBackups = googleDriveInfo.backup_count || 0;
        const isConnected = googleDriveInfo.connected || false;
        const autoBackupEnabled = settingsInfo.auto_backup_enabled || false;
        
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
     * تحديث واجهة حالة Google Drive الجديدة
     */
    updateGoogleDriveStatusUI(data) {
        const container = document.getElementById('google-drive-status');
        if (!container) return;
        
        const status = data.status || data;
        const isConnected = status.connected || false;
        const lastBackup = status.last_backup;
        const backupCount = status.backup_count || 0;
        
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
                        <span class="value">${lastBackup ? this.formatDate(new Date(lastBackup)) : 'لا توجد'}</span>
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
            immediateBtn.addEventListener('click', () => this.testBackup());
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshStatus());
        }
    }

    async testBackup() {
        const testBtn = document.getElementById('test-backup-btn') || document.getElementById('immediate-backup-btn');
        if (testBtn) {
            testBtn.disabled = true;
            testBtn.textContent = 'جاري الاختبار...';
        }
        
        try {
            // محاولة استخدام API الأصلي أولاً
            let response = await fetch('/api/v1/backup/immediate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            // إذا فشل بسبب عدم تسجيل الدخول، استخدم API الاختبار
            if (!response.ok && response.status === 401) {
                console.log('المستخدم غير مسجل دخول، استخدام API اختبار النسخ...');
                response = await fetch('/api/v1/backup/test-immediate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                });
            }
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess(data.test_mode ? 
                    'تم النسخ الاحتياطي بنجاح (وضع الاختبار)' : 
                    'تم النسخ الاحتياطي بنجاح');
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
                testBtn.textContent = testBtn.id === 'immediate-backup-btn' ? 'نسخ احتياطي فوري' : 'اختبار النسخ الآن';
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
                },
                credentials: 'same-origin'
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
                },
                credentials: 'same-origin'
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
        let message = 'ملفات النسخ الاحتياطي في Google Drive:\n\n';
        
        if (files.length === 0) {
            message += 'لا توجد ملفات نسخ احتياطي';
        } else {
            files.forEach((file, index) => {
                const date = new Date(file.createdTime).toLocaleString('ar-SA');
                message += `${index + 1}. ${file.name} (${date})\n`;
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
    
    // ===== وظائف تفعيل النسخ التلقائي =====
    
    async enableAutoBackup(settings = {}) {
        try {
            console.log('🔄 تفعيل النسخ التلقائي...', settings);
            
            // الإعدادات الافتراضية
            const defaultSettings = {
                auto_backup_enabled: true,
                backup_frequency: 'daily',
                backup_destination: 'local',
                max_backups: 5
            };
            
            // دمج الإعدادات
            const finalSettings = { ...defaultSettings, ...settings };
            
            const response = await fetch('/api/v1/backup/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(finalSettings),
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('تم تفعيل النسخ التلقائي بنجاح');
                
                // تحديث الحالة فوراً
                setTimeout(() => {
                    this.checkBackupStatus();
                }, 1000);
                
                return true;
            } else {
                this.showError(data.error || 'فشل في تفعيل النسخ التلقائي');
                return false;
            }
            
        } catch (error) {
            console.error('❌ خطأ في تفعيل النسخ التلقائي:', error);
            this.showError('خطأ في الاتصال بالخادم');
            return false;
        }
    }
    
    async disableAutoBackup() {
        try {
            console.log('⏹️ إيقاف النسخ التلقائي...');
            
            const response = await fetch('/api/v1/backup/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    auto_backup_enabled: false
                }),
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('تم إيقاف النسخ التلقائي');
                
                // تحديث الحالة فوراً
                setTimeout(() => {
                    this.checkBackupStatus();
                }, 1000);
                
                return true;
            } else {
                this.showError(data.error || 'فشل في إيقاف النسخ التلقائي');
                return false;
            }
            
        } catch (error) {
            console.error('❌ خطأ في إيقاف النسخ التلقائي:', error);
            this.showError('خطأ في الاتصال بالخادم');
            return false;
        }
    }
    
    async updateBackupSettings(settings) {
        try {
            console.log('⚙️ تحديث إعدادات النسخ الاحتياطي...', settings);
            
            const response = await fetch('/api/v1/backup/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings),
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('تم تحديث إعدادات النسخ الاحتياطي بنجاح');
                
                // تحديث الحالة فوراً
                setTimeout(() => {
                    this.checkBackupStatus();
                }, 1000);
                
                return true;
            } else {
                this.showError(data.error || 'فشل في تحديث إعدادات النسخ الاحتياطي');
                return false;
            }
            
        } catch (error) {
            console.error('❌ خطأ في تحديث إعدادات النسخ الاحتياطي:', error);
            this.showError('خطأ في الاتصال بالخادم');
            return false;
        }
    }
    
    // ===== ربط أحداث تفعيل النسخ التلقائي =====
    
    bindAutoBackupEvents() {
        // checkbox تفعيل النسخ التلقائي
        const autoBackupCheckbox = document.getElementById('تفعيل-النسخ-التلقائي');
        if (autoBackupCheckbox) {
            autoBackupCheckbox.addEventListener('change', async (e) => {
                const isEnabled = e.target.checked;
                
                if (isEnabled) {
                    // جمع الإعدادات من النموذج
                    const settings = this.collectBackupSettings();
                    await this.enableAutoBackup(settings);
                } else {
                    await this.disableAutoBackup();
                }
            });
        }
        
        // أزرار حفظ الإعدادات
        const saveSettingsBtn = document.getElementById('save-backup-settings');
        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener('click', async () => {
                const settings = this.collectBackupSettings();
                await this.updateBackupSettings(settings);
            });
        }
        
        // نموذج إعدادات النسخ الاحتياطي
        const backupSettingsForm = document.getElementById('backup-settings-form');
        if (backupSettingsForm) {
            backupSettingsForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const settings = this.collectBackupSettings();
                await this.updateBackupSettings(settings);
            });
        }
    }
    
    collectBackupSettings() {
        const settings = {};
        
        // تفعيل النسخ التلقائي
        const autoBackupCheckbox = document.getElementById('تفعيل-النسخ-التلقائي');
        if (autoBackupCheckbox) {
            settings.auto_backup_enabled = autoBackupCheckbox.checked;
        }
        
        // تكرار النسخ
        const frequencySelect = document.getElementById('backup-frequency');
        if (frequencySelect) {
            settings.backup_frequency = frequencySelect.value;
        }
        
        // وجهة النسخ
        const destinationSelect = document.getElementById('backup-destination');
        if (destinationSelect) {
            settings.backup_destination = destinationSelect.value;
        }
        
        // الحد الأقصى للنسخ
        const maxBackupsInput = document.getElementById('max-backups');
        if (maxBackupsInput) {
            settings.max_backups = parseInt(maxBackupsInput.value) || 5;
        }
        
        return settings;
    }
}

// تهيئة النظام عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // التحقق من وجود عناصر النسخ الاحتياطي في الصفحة
    if (document.getElementById('backup-status') || 
        document.querySelector('.backup-section') ||
        document.getElementById('backup-stats-container') ||
        document.getElementById('google-drive-status')) {
        
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
    
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 15px;
        margin-bottom: 20px;
    }
    
    .stat-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #e9ecef;
    }
    
    .stat-number {
        font-size: 24px;
        font-weight: bold;
        color: #495057;
        margin-bottom: 5px;
    }
    
    .stat-label {
        font-size: 14px;
        color: #6c757d;
    }
    
    .action-section {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    
    .btn {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        text-decoration: none;
        display: inline-block;
        transition: all 0.2s;
    }
    
    .btn-success {
        background-color: #28a745;
        color: white;
    }
    
    .btn-success:hover {
        background-color: #218838;
    }
    
    .btn-outline-primary {
        background-color: transparent;
        color: #007bff;
        border: 1px solid #007bff;
    }
    
    .btn-outline-primary:hover {
        background-color: #007bff;
        color: white;
    }
    
    .btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    
    .drive-status-card {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 15px;
    }
    
    .status-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }
    
    .status-header h4 {
        margin: 0;
        color: #495057;
    }
    
    .connection-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }
    
    .connection-badge.connected {
        background-color: #d4edda;
        color: #155724;
    }
    
    .connection-badge.disconnected {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    .status-details {
        margin-bottom: 15px;
    }
    
    .detail-item {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
    }
    
    .detail-item .label {
        color: #6c757d;
        font-size: 14px;
    }
    
    .detail-item .value {
        color: #495057;
        font-weight: 500;
        font-size: 14px;
    }
    
    .action-buttons {
        display: flex;
        gap: 10px;
    }
    
    .btn-primary {
        background-color: #007bff;
        color: white;
    }
    
    .btn-primary:hover {
        background-color: #0056b3;
    }
    
    .btn-secondary {
        background-color: #6c757d;
        color: white;
    }
    
    .btn-secondary:hover {
        background-color: #545b62;
    }
`;
document.head.appendChild(style);

