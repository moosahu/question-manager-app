/**
 * نظام مراقبة النسخ الاحتياطي المحسن
 * Enhanced Backup Monitoring System
 */

// حماية من التعارضات والأخطاء
(function() {
    'use strict';
    
    // التحقق من وجود الكلاس مسبقاً لتجنب التعارضات
    if (typeof window.BackupMonitor !== 'undefined') {
        console.warn('BackupMonitor already exists, skipping redefinition');
        return;
    }
    
    try {

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
    
    // ===== دوال مساعدة للشبكة =====
    
    async fetchWithTimeout(url, options = {}, timeout = 10000) {
        /**
         * دالة fetch مع timeout
         */
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeout}ms`);
            }
            throw error;
        }
    }
    
    async parseJsonResponse(response) {
        /**
         * تحليل استجابة JSON مع معالجة محسنة للأخطاء
         */
        try {
            const contentType = response.headers.get('content-type');
            
            // التحقق من نوع المحتوى
            if (contentType && contentType.includes('application/json')) {
                const text = await response.text();
                
                // التحقق من أن المحتوى ليس HTML
                if (text.trim().startsWith('<!DOCTYPE') || text.trim().startsWith('<html')) {
                    console.warn('⚠️ تم استلام HTML بدلاً من JSON:', text.substring(0, 100));
                    
                    // محاولة استخراج رسالة الخطأ من HTML
                    const errorMessage = this.extractErrorFromHTML(text);
                    return {
                        success: false,
                        error: errorMessage || 'الخادم أرجع HTML بدلاً من JSON',
                        html_response: true
                    };
                }
                
                // محاولة تحليل JSON
                try {
                    return JSON.parse(text);
                } catch (jsonError) {
                    console.error('❌ خطأ في تحليل JSON:', jsonError);
                    console.error('📝 محتوى الاستجابة:', text.substring(0, 200));
                    
                    return {
                        success: false,
                        error: 'خطأ في تحليل استجابة الخادم',
                        json_error: true,
                        raw_response: text.substring(0, 200)
                    };
                }
            } else {
                // إذا لم يكن JSON، اقرأ كنص
                const text = await response.text();
                console.warn('⚠️ استجابة غير JSON:', contentType);
                console.warn('📝 محتوى الاستجابة:', text.substring(0, 200));
                
                // محاولة استخراج رسالة الخطأ
                const errorMessage = this.extractErrorFromHTML(text);
                
                return {
                    success: false,
                    error: errorMessage || 'استجابة غير متوقعة من الخادم',
                    content_type: contentType,
                    raw_response: text.substring(0, 200)
                };
            }
        } catch (error) {
            console.error('❌ خطأ في معالجة الاستجابة:', error);
            return {
                success: false,
                error: 'خطأ في معالجة استجابة الخادم',
                processing_error: true
            };
        }
    }
    
    extractErrorFromHTML(htmlText) {
        /**
         * استخراج رسالة الخطأ من HTML response
         */
        try {
            // البحث عن رسائل خطأ شائعة
            if (htmlText.includes('400 Bad Request')) {
                if (htmlText.includes('CSRF token is missing')) {
                    return 'CSRF token مفقود - يرجى إعادة تحميل الصفحة';
                }
                return 'طلب غير صحيح (400)';
            }
            
            if (htmlText.includes('404 Not Found')) {
                return 'API غير موجود (404)';
            }
            
            if (htmlText.includes('500 Internal Server Error')) {
                return 'خطأ في الخادم (500)';
            }
            
            if (htmlText.includes('403 Forbidden')) {
                return 'غير مسموح (403)';
            }
            
            if (htmlText.includes('401 Unauthorized')) {
                return 'غير مصرح (401) - يرجى تسجيل الدخول';
            }
            
            // محاولة استخراج عنوان الصفحة
            const titleMatch = htmlText.match(/<title>(.*?)<\/title>/i);
            if (titleMatch && titleMatch[1]) {
                return titleMatch[1].trim();
            }
            
            return null;
        } catch (error) {
            console.error('خطأ في استخراج رسالة الخطأ:', error);
            return null;
        }
    }
    
    async checkBackupStatusFallback() {
        /**
         * دالة احتياطية لفحص حالة النسخ الاحتياطي
         */
        try {
            // محاولة استخدام endpoint بديل
            const response = await this.fetchWithTimeout('/api/v1/backup/health', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            }, 5000);
            
            if (response.ok) {
                const data = await this.parseJsonResponse(response);
                if (data && data.success) {
                    // تحويل بيانات health إلى تنسيق status
                    const statusData = {
                        success: true,
                        status: {
                            google_drive: {
                                connected: data.google_drive_connected || false,
                                last_backup: null,
                                backup_count: 0
                            },
                            settings: {
                                auto_backup_enabled: false,
                                backup_frequency: 'daily',
                                backup_destination: 'local',
                                max_backups: 5
                            },
                            scheduler: {
                                available: data.scheduler_available || false,
                                running: false
                            }
                        }
                    };
                    this.updateBackupStatus(statusData);
                    return;
                }
            }
            
            // إذا فشل كل شيء، استخدم بيانات افتراضية
            this.updateBackupStatusWithDefaults();
            
        } catch (error) {
            console.error('خطأ في fallback:', error);
            this.updateBackupStatusWithDefaults();
        }
    }
    
    updateBackupStatusWithDefaults() {
        /**
         * تحديث الحالة ببيانات افتراضية
         */
        const defaultStatus = {
            success: true,
            status: {
                google_drive: {
                    connected: false,
                    last_backup: null,
                    backup_count: 0
                },
                settings: {
                    auto_backup_enabled: false,
                    backup_frequency: 'daily',
                    backup_destination: 'local',
                    max_backups: 5,
                    last_backup_time: null
                },
                scheduler: {
                    available: false,
                    running: false,
                    next_backup: null
                }
            }
        };
        
        this.updateBackupStatus(defaultStatus);
        
        // عرض رسالة للمستخدم
        if (this.statusElement) {
            this.statusElement.textContent = 'غير متاح';
            this.statusElement.className = 'status-warning';
        }
    }
    
    // ===== نهاية الدوال المساعدة =====
    
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
    
    async checkBackupStatus(retryCount = 0) {
        const maxRetries = 3;
        const retryDelay = 1000 * (retryCount + 1); // تأخير متزايد
        
        try {
            // استخدام API للاختبار إذا كان المستخدم غير مسجل دخول
            let apiUrl = '/api/v1/backup/status';
            
            const response = await this.fetchWithTimeout(apiUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            }, 10000); // timeout 10 ثوان
            
            // إذا فشل الطلب بسبب عدم تسجيل الدخول، استخدم API الاختبار
            if (!response.ok && response.status === 401) {
                console.log('المستخدم غير مسجل دخول، استخدام API الاختبار...');
                const testResponse = await this.fetchWithTimeout('/api/v1/backup/test-status', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                }, 10000);
                
                if (testResponse.ok) {
                    const data = await this.parseJsonResponse(testResponse);
                    if (data && data.success) {
                        this.updateBackupStatus(data);
                        return;
                    }
                }
            }
            
            if (response.ok) {
                const data = await this.parseJsonResponse(response);
                if (data && data.success) {
                    this.updateBackupStatus(data);
                } else {
                    console.error('فشل في الحصول على حالة النسخ الاحتياطي:', data?.error);
                    // لا نعرض خطأ للمستخدم هنا لأن هذا فحص دوري
                }
            } else if (response.status === 404) {
                console.warn('API endpoint غير موجود، محاولة استخدام endpoint بديل...');
                // محاولة استخدام endpoint بديل
                await this.checkBackupStatusFallback();
            } else {
                console.error('فشل في الحصول على حالة النسخ الاحتياطي:', response.status);
                
                // إعادة المحاولة في حالة أخطاء الشبكة
                if (retryCount < maxRetries && (response.status >= 500 || response.status === 0)) {
                    console.log(`إعادة المحاولة ${retryCount + 1}/${maxRetries} بعد ${retryDelay}ms...`);
                    setTimeout(() => {
                        this.checkBackupStatus(retryCount + 1);
                    }, retryDelay);
                }
            }
        } catch (error) {
            console.error('خطأ في فحص حالة النسخ الاحتياطي:', error);
            
            // إعادة المحاولة في حالة أخطاء الشبكة
            if (retryCount < maxRetries && (error.name === 'TypeError' || error.message.includes('fetch'))) {
                console.log(`إعادة المحاولة ${retryCount + 1}/${maxRetries} بعد ${retryDelay}ms...`);
                setTimeout(() => {
                    this.checkBackupStatus(retryCount + 1);
                }, retryDelay);
            }
        }
    }
    
    async checkGoogleDriveConnection(retryCount = 0) {
        const maxRetries = 3;
        const retryDelay = 1000 * (retryCount + 1);
        
        try {
            const response = await this.fetchWithTimeout('/api/v1/google-drive/connection-status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            }, 10000);
            
            // إذا فشل الطلب بسبب عدم تسجيل الدخول، استخدم API الاختبار
            if (!response.ok && response.status === 401) {
                console.log('المستخدم غير مسجل دخول، استخدام API اختبار Google Drive...');
                const testResponse = await this.fetchWithTimeout('/api/v1/google-drive/test-connection-status', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                }, 10000);
                
                if (testResponse.ok) {
                    const data = await this.parseJsonResponse(testResponse);
                    if (data && data.success) {
                        this.updateGoogleDriveStatus(data);
                        return;
                    }
                }
            }
            
            if (response.ok) {
                const data = await this.parseJsonResponse(response);
                if (data && data.success) {
                    this.updateGoogleDriveStatus(data);
                    
                    // إذا كان الاتصال منقطعاً، محاولة تحديث Token
                    if (!data.status.connected && data.status.storage_method === 'database') {
                        console.log('🔄 محاولة تحديث Google Drive Token...');
                        await this.refreshGoogleDriveToken();
                    }
                } else {
                    console.error('فشل في فحص اتصال Google Drive:', data?.error);
                    // في حالة الفشل، عرض حالة منقطعة
                    this.updateGoogleDriveStatus({
                        success: true,
                        status: { connected: false }
                    });
                }
            } else if (response.status === 404) {
                console.warn('Google Drive API endpoint غير موجود، استخدام بيانات افتراضية...');
                this.updateGoogleDriveStatus({
                    success: true,
                    status: { connected: false }
                });
            } else {
                console.error('فشل في فحص اتصال Google Drive - HTTP:', response.status);
                
                // إعادة المحاولة في حالة أخطاء الخادم
                if (retryCount < maxRetries && response.status >= 500) {
                    console.log(`إعادة المحاولة ${retryCount + 1}/${maxRetries} بعد ${retryDelay}ms...`);
                    setTimeout(() => {
                        this.checkGoogleDriveConnection(retryCount + 1);
                    }, retryDelay);
                    return;
                }
                
                // في حالة فشل HTTP، عرض حالة منقطعة
                this.updateGoogleDriveStatus({
                    success: true,
                    status: { connected: false }
                });
            }
        } catch (error) {
            console.error('خطأ في فحص اتصال Google Drive:', error);
            
            // إعادة المحاولة في حالة أخطاء الشبكة
            if (retryCount < maxRetries && (error.name === 'TypeError' || error.message.includes('fetch') || error.message.includes('timeout'))) {
                console.log(`إعادة المحاولة ${retryCount + 1}/${maxRetries} بعد ${retryDelay}ms...`);
                setTimeout(() => {
                    this.checkGoogleDriveConnection(retryCount + 1);
                }, retryDelay);
                return;
            }
            
            // في حالة خطأ الشبكة، عرض حالة منقطعة
            this.updateGoogleDriveStatus({
                success: true,
                status: { connected: false }
            });
        }
    }
    
    async refreshGoogleDriveToken() {
        try {
            console.log('🔄 محاولة تحديث Google Drive Token...');
            
            const response = await fetch('/api/v1/google-drive/refresh-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    console.log('✅ تم تحديث Token بنجاح');
                    this.showSuccess('تم تحديث اتصال Google Drive');
                    
                    // إعادة فحص الاتصال
                    setTimeout(() => {
                        this.checkGoogleDriveConnection();
                    }, 1000);
                } else if (data.requires_reauth) {
                    console.log('🔐 يتطلب إعادة مصادقة');
                    this.showError('انتهت صلاحية الاتصال. يرجى إعادة ربط Google Drive');
                    
                    // عرض حالة منقطعة
                    this.updateGoogleDriveStatus({
                        success: true,
                        status: { connected: false }
                    });
                } else {
                    console.error('فشل في تحديث Token:', data.message);
                }
            } else {
                console.error('فشل في طلب تحديث Token:', response.status);
            }
        } catch (error) {
            console.error('خطأ في تحديث Token:', error);
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
            const backupCount = status.backup_count || 0;
            const lastBackup = status.last_backup;
            
            if (isConnected) {
                this.connectionElement.innerHTML = `✅ متصل (${backupCount} نسخة)`;
                this.connectionElement.className = 'status-connected';
                
                // إضافة معلومات آخر نسخة إذا كانت متوفرة
                if (lastBackup) {
                    const lastBackupDate = new Date(lastBackup);
                    const timeAgo = this.getTimeAgo(lastBackupDate);
                    this.connectionElement.innerHTML += `<br><small>آخر نسخة: ${timeAgo}</small>`;
                }
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
        
        // حفظ حالة الاتصال للاستخدام في وظائف أخرى
        this.googleDriveConnected = isConnected;
    }
    
    getTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'الآن';
        if (diffMins < 60) return `منذ ${diffMins} دقيقة`;
        if (diffHours < 24) return `منذ ${diffHours} ساعة`;
        if (diffDays < 7) return `منذ ${diffDays} يوم`;
        
        return date.toLocaleDateString('ar-SA');
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
        
        // تحديث تكرار النسخ (stat-backup-frequency لتجنب التعارض مع select النموذج)
        const frequencyElement = document.getElementById('stat-backup-frequency');
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

        // تحديث عدد النسخ المحفوظة
        const countElement = document.getElementById('backup-count');
        if (countElement && status.settings) {
            const backupCount = status.settings.backup_count || 0;
            const maxBackups = status.settings.max_backups || 5;
            countElement.textContent = `${backupCount} / ${maxBackups}`;
        }

        // تحديث آخر نسخة احتياطية
        const lastBackupElement = document.getElementById('last-backup-time');
        if (lastBackupElement) {
            let lastBackupTime = null;

            // أولاً: وقت النسخة الأخيرة الفعلية من settings
            if (status.settings && status.settings.last_backup_time) {
                lastBackupTime = status.settings.last_backup_time;
            }
            // ثانياً: من Google Drive
            else if (status.google_drive && status.google_drive.last_backup) {
                lastBackupTime = status.google_drive.last_backup;
            }

            if (lastBackupTime) {
                const lastDate = new Date(lastBackupTime);
                lastBackupElement.textContent = this.formatDate(lastDate);
            } else {
                lastBackupElement.textContent = 'لم يتم إنشاء نسخة بعد';
            }
        }

        // تحديث وجهة النسخ (backup-destination-display لتجنب التعارض مع select النموذج)
        const destinationElement = document.getElementById('backup-destination-display');
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
            testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري النسخ...';
        }
        
        try {
            console.log('🔄 بدء اختبار النسخ الاحتياطي...');

            // التحقق من الوجهة - إذا google_drive يجب الاتصال أولاً
            const destSelect = document.getElementById('backup-destination');
            const destination = destSelect ? destSelect.value : 'local';
            if (destination === 'google_drive' && !this.googleDriveConnected) {
                this.showError('يجب ربط Google Drive أولاً قبل إنشاء نسخة احتياطية');
                if (testBtn) {
                    testBtn.disabled = false;
                    testBtn.innerHTML = '<i class="fas fa-play"></i> اختبار النسخ الآن';
                }
                return;
            }
            
            // الحصول على CSRF token
            let csrfToken = this.getCSRFToken();
            
            // إذا كان CSRF token فارغ، محاولة الحصول عليه من الخادم
            if (!csrfToken || csrfToken === '') {
                console.log('🔄 محاولة الحصول على CSRF token من الخادم...');
                csrfToken = await this.fetchCSRFToken();
            }
            
            // إعداد headers مع CSRF token
            const headers = {
                'Content-Type': 'application/json'
            };
            
            if (csrfToken && csrfToken !== '') {
                headers['X-CSRFToken'] = csrfToken;
                console.log('✅ تم إضافة CSRF token للطلب');
            } else {
                console.warn('⚠️ لم يتم العثور على CSRF token - المتابعة بدونه');
            }
            
            // محاولة استخدام API الأصلي أولاً
            let response = await this.fetchWithTimeout('/api/v1/backup/immediate', {
                method: 'POST',
                headers: headers,
                credentials: 'same-origin',
                body: JSON.stringify({
                    test_mode: false,
                    destination: 'google_drive'
                })
            }, 30000); // timeout أطول للنسخ الاحتياطي
            
            console.log('📡 استجابة الخادم:', response.status, response.statusText);
            
            // إذا فشل بسبب عدم تسجيل الدخول، استخدم API الاختبار
            if (!response.ok && response.status === 401) {
                console.log('المستخدم غير مسجل دخول، استخدام API اختبار النسخ...');
                response = await this.fetchWithTimeout('/api/v1/backup/test-immediate', {
                    method: 'POST',
                    headers: headers,
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        test_mode: true,
                        destination: 'google_drive'
                    })
                }, 30000);
            }
            
            // إذا فشل بسبب CSRF، محاولة الحصول على token جديد وإعادة المحاولة
            if (!response.ok && response.status === 400) {
                const errorText = await response.text();
                if (errorText.includes('CSRF token is missing')) {
                    console.log('🔄 CSRF token مفقود، محاولة الحصول على token جديد...');
                    
                    // الحصول على token جديد
                    const newToken = await this.fetchCSRFToken();
                    if (newToken) {
                        headers['X-CSRFToken'] = newToken;
                        
                        // إعادة المحاولة مع token جديد
                        response = await this.fetchWithTimeout('/api/v1/backup/immediate', {
                            method: 'POST',
                            headers: headers,
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                test_mode: false,
                                destination: 'google_drive'
                            })
                        }, 30000);
                        
                        console.log('📡 استجابة الخادم بعد إعادة المحاولة:', response.status, response.statusText);
                    }
                }
            }
            
            // معالجة الاستجابة
            let data = null;
            if (response.ok) {
                data = await this.parseJsonResponse(response);
            } else {
                // محاولة قراءة رسالة الخطأ
                data = await this.parseJsonResponse(response);
            }
            
            if (response.ok && data && data.success) {
                console.log('✅ نجح إنشاء النسخة الاحتياطية');
                
                const message = data.test_mode ? 
                    'تم إنشاء النسخة الاحتياطية بنجاح (وضع الاختبار)' : 
                    'تم إنشاء النسخة الاحتياطية ورفعها إلى Google Drive بنجاح';
                
                this.showSuccess(message);
                
                // تحديث الحالة فوراً مع تأخير قصير للسماح للخادم بالتحديث
                setTimeout(() => {
                    this.checkBackupStatus();
                    this.checkGoogleDriveConnection();
                }, 2000);
                
                // إضافة إشعار بصري إضافي
                if (!data.test_mode) {
                    setTimeout(() => {
                        this.showSuccess('تم تحديث عدد النسخ في Google Drive');
                    }, 3000);
                }
            } else {
                console.error('❌ فشل في إنشاء النسخة الاحتياطية:', data);
                
                // معالجة أنواع مختلفة من الأخطاء
                let errorMessage = 'فشل في إنشاء النسخة الاحتياطية';
                
                if (data && data.error) {
                    errorMessage = data.error;
                } else if (response.status === 400) {
                    errorMessage = 'طلب غير صحيح - تحقق من إعدادات النسخ الاحتياطي';
                } else if (response.status === 401) {
                    errorMessage = 'غير مصرح - يرجى تسجيل الدخول مرة أخرى';
                } else if (response.status === 403) {
                    errorMessage = 'غير مسموح - تحقق من صلاحيات Google Drive';
                } else if (response.status === 404) {
                    errorMessage = 'API غير موجود - تحقق من إعدادات الخادم';
                } else if (response.status === 500) {
                    errorMessage = 'خطأ في الخادم - تحقق من اتصال Google Drive';
                }
                
                this.showError(errorMessage);
            }
        } catch (error) {
            console.error('❌ خطأ في إنشاء النسخة الاحتياطية:', error);
            
            // معالجة أنواع مختلفة من الأخطاء
            let errorMessage = 'خطأ في إنشاء النسخة الاحتياطية';
            
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                errorMessage = 'فشل في الاتصال بالخادم. تحقق من اتصال الإنترنت.';
            } else if (error.message.includes('timeout')) {
                errorMessage = 'انتهت مهلة العملية. قد تكون النسخة الاحتياطية كبيرة الحجم.';
            } else if (error.message.includes('SyntaxError') || error.message.includes('JSON')) {
                errorMessage = 'خطأ في استجابة الخادم. قد يكون هناك مشكلة في إعدادات API.';
            } else if (error.message.includes('Google Drive')) {
                errorMessage = 'مشكلة في اتصال Google Drive. تحقق من الربط وأعد المحاولة.';
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            this.showError(errorMessage);
        } finally {
            if (testBtn) {
                testBtn.disabled = false;
                testBtn.innerHTML = testBtn.id === 'immediate-backup-btn' ? 
                    '<i class="fas fa-cloud-upload-alt"></i> نسخ احتياطي فوري' : 
                    '<i class="fas fa-play"></i> اختبار النسخ الآن';
            }
        }
    }
    
    getCSRFToken() {
        // البحث عن CSRF token في عدة أماكن مع معالجة محسنة
        try {
            // 1. البحث في input hidden
            const csrfInput = document.querySelector('input[name="csrf_token"]');
            if (csrfInput && csrfInput.value && csrfInput.value !== '') {
                console.log('✅ تم العثور على CSRF token من input');
                return csrfInput.value;
            }
            
            // 2. البحث في meta tag
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            if (csrfMeta) {
                const metaContent = csrfMeta.getAttribute('content');
                if (metaContent && metaContent !== '' && metaContent !== 'dummy-token') {
                    console.log('✅ تم العثور على CSRF token من meta tag');
                    return metaContent;
                }
            }
            
            // 3. البحث في cookies
            const csrfCookie = document.cookie.split('; ').find(row => row.startsWith('csrf_token='));
            if (csrfCookie) {
                const cookieValue = csrfCookie.split('=')[1];
                if (cookieValue && cookieValue !== '') {
                    console.log('✅ تم العثور على CSRF token من cookie');
                    return cookieValue;
                }
            }
            
            // 4. محاولة الحصول على token من الخادم
            console.warn('⚠️ لم يتم العثور على CSRF token، محاولة الحصول عليه من الخادم...');
            return this.fetchCSRFToken();
            
        } catch (error) {
            console.error('❌ خطأ في الحصول على CSRF token:', error);
            return '';
        }
    }
    
    async fetchCSRFToken() {
        /**
         * محاولة الحصول على CSRF token من الخادم
         */
        try {
            const response = await fetch('/api/v1/csrf-token', {
                method: 'GET',
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.csrf_token) {
                    console.log('✅ تم الحصول على CSRF token من الخادم');
                    return data.csrf_token;
                }
            }
        } catch (error) {
            console.error('❌ فشل في الحصول على CSRF token من الخادم:', error);
        }
        
        // إذا فشل كل شيء، إرجاع قيمة فارغة
        console.warn('⚠️ لم يتم العثور على CSRF token - سيتم إرسال الطلب بدون token');
        return '';
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
            
            // إعداد معاملات OAuth المحسنة
            const clientId = config.client_id;
            const redirectUri = `${window.location.origin}/auth/google/callback`;
            const scope = 'https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.email';
            const responseType = 'code';
            const accessType = 'offline';
            const prompt = 'consent';
            const includeGrantedScopes = 'true';
            
            // إضافة user_id كـ state parameter مع تشفير إضافي
            let state = '';
            try {
                const userResponse = await fetch('/api/v1/user/info');
                if (userResponse.ok) {
                    const userData = await userResponse.json();
                    if (userData.success && userData.user) {
                        state = btoa(userData.user.id.toString() + '_' + Date.now());
                    }
                }
            } catch (e) {
                console.warn('لا يمكن الحصول على معلومات المستخدم:', e);
                state = btoa('guest_' + Date.now());
            }
            
            // بناء URL للمصادقة المحسن
            const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
                `client_id=${encodeURIComponent(clientId)}&` +
                `redirect_uri=${encodeURIComponent(redirectUri)}&` +
                `scope=${encodeURIComponent(scope)}&` +
                `response_type=${responseType}&` +
                `access_type=${accessType}&` +
                `prompt=${prompt}&` +
                `include_granted_scopes=${includeGrantedScopes}&` +
                `state=${state}`;
            
            console.log('🌐 فتح نافذة المصادقة...');
            console.log('📍 Redirect URI:', redirectUri);
            console.log('🔑 Client ID:', clientId.substring(0, 20) + '...');
            
            // فتح نافذة المصادقة مع معاملات محسنة
            const authWindow = window.open(
                authUrl,
                'google-auth',
                'width=600,height=700,scrollbars=yes,resizable=yes,location=yes,status=yes'
            );
            
            if (!authWindow) {
                this.showError('لا يمكن فتح نافذة المصادقة. تأكد من السماح للنوافذ المنبثقة');
                return;
            }
            
            // الاستماع لرسائل من نافذة المصادقة مع timeout
            const messageHandler = (event) => {
                // التحقق من مصدر الرسالة للأمان
                if (event.origin !== window.location.origin) {
                    console.warn('⚠️ رسالة من مصدر غير موثوق:', event.origin);
                    return;
                }
                
                console.log('📨 تم استلام رسالة من نافذة OAuth:', event.data);
                
                if (event.data.type === 'google-auth-success') {
                    console.log('✅ نجح ربط Google Drive');
                    this.showSuccess('تم ربط Google Drive بنجاح');
                    
                    // تحديث الحالة فوراً
                    this.checkGoogleDriveConnection();
                    this.checkBackupStatus();
                    
                    // إزالة مستمع الأحداث
                    window.removeEventListener('message', messageHandler);
                    clearTimeout(authTimeout);
                    
                } else if (event.data.type === 'google-auth-error') {
                    console.error('❌ فشل في ربط Google Drive:', event.data);
                    this.showError(event.data.message || 'فشل في ربط Google Drive');
                    
                    // إزالة مستمع الأحداث
                    window.removeEventListener('message', messageHandler);
                    clearTimeout(authTimeout);
                }
            };
            
            // إضافة مستمع الأحداث
            window.addEventListener('message', messageHandler);
            
            // إضافة timeout للمصادقة (5 دقائق)
            const authTimeout = setTimeout(() => {
                window.removeEventListener('message', messageHandler);
                if (!authWindow.closed) {
                    authWindow.close();
                }
                console.log('⏰ انتهت مهلة المصادقة');
                this.showError('انتهت مهلة المصادقة. يرجى المحاولة مرة أخرى');
            }, 300000);
            
            // مراقبة إغلاق النافذة
            const checkClosed = setInterval(() => {
                if (authWindow.closed) {
                    clearInterval(checkClosed);
                    clearTimeout(authTimeout);
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

        // ===== أحداث الخيارات المتقدمة =====
        
        // زر عرض النسخ المتاحة
        const listBackupsBtn = document.getElementById('list-backups-btn');
        if (listBackupsBtn) {
            listBackupsBtn.addEventListener('click', () => this.listAvailableBackups());
        }
        
        // زر رفع نسخة احتياطية
        const uploadBackupBtn = document.getElementById('upload-backup-btn');
        if (uploadBackupBtn) {
            uploadBackupBtn.addEventListener('click', () => this.uploadBackupFile());
        }
        
        // مراقبة تغيير وجهة النسخ الاحتياطي
        const destinationSelect = document.getElementById('backup-destination');
        if (destinationSelect) {
            destinationSelect.addEventListener('change', (e) => {
                this.handleDestinationChange(e.target.value);
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

        // ===== الخيارات المتقدمة =====
        
        // تضمين الصور
        const includeImagesCheckbox = document.getElementById('include-images');
        if (includeImagesCheckbox) {
            settings.include_images = includeImagesCheckbox.checked;
        }
        
        // ضغط النسخة
        const compressBackupCheckbox = document.getElementById('compress-backup');
        if (compressBackupCheckbox) {
            settings.compress_backup = compressBackupCheckbox.checked;
        }
        
        // تشفير النسخة
        const encryptBackupCheckbox = document.getElementById('encrypt-backup');
        if (encryptBackupCheckbox) {
            settings.encrypt_backup = encryptBackupCheckbox.checked;
        }
        
        return settings;
    }

    // ===== وظائف إدارة النسخ الاحتياطية المتقدمة =====
    
    async listAvailableBackups() {
        try {
            this.showNotification('جاري تحميل قائمة النسخ الاحتياطية...', 'info');
            
            const response = await fetch('/api/v1/backup/list', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.displayBackupsList(data.backups);
                } else {
                    this.showError(data.error || 'فشل في تحميل قائمة النسخ الاحتياطية');
                }
            } else {
                this.showError('فشل في الاتصال بالخادم');
            }
        } catch (error) {
            console.error('خطأ في تحميل قائمة النسخ:', error);
            this.showError('خطأ في تحميل قائمة النسخ الاحتياطية');
        }
    }
    
    displayBackupsList(backups) {
        if (!backups || backups.length === 0) {
            this.showNotification('لا توجد نسخ احتياطية متاحة', 'warning');
            return;
        }
        
        let backupsList = 'النسخ الاحتياطية المتاحة:\n\n';
        backups.forEach((backup, index) => {
            const date = new Date(backup.created_at).toLocaleString('ar-SA');
            const size = this.formatFileSize(backup.size);
            const destination = backup.destination === 'google_drive' ? 'Google Drive' : 'محلي';
            
            backupsList += `${index + 1}. ${backup.name}\n`;
            backupsList += `   التاريخ: ${date}\n`;
            backupsList += `   الحجم: ${size}\n`;
            backupsList += `   الوجهة: ${destination}\n\n`;
        });
        
        // إنشاء نافذة منبثقة لعرض القائمة
        this.showBackupsModal(backups);
    }
    
    showBackupsModal(backups) {
        // إنشاء نافذة منبثقة
        const modal = document.createElement('div');
        modal.className = 'backup-modal';
        modal.innerHTML = `
            <div class="backup-modal-content">
                <div class="backup-modal-header">
                    <h3><i class="fas fa-list"></i> النسخ الاحتياطية المتاحة</h3>
                    <button class="close-modal" onclick="this.closest('.backup-modal').remove()">&times;</button>
                </div>
                <div class="backup-modal-body">
                    <div class="backups-list">
                        ${backups.map((backup, index) => `
                            <div class="backup-item">
                                <div class="backup-info">
                                    <h4>${backup.name}</h4>
                                    <p><i class="fas fa-calendar"></i> ${new Date(backup.created_at).toLocaleString('ar-SA')}</p>
                                    <p><i class="fas fa-hdd"></i> ${this.formatFileSize(backup.size)}</p>
                                    <p><i class="fas fa-cloud"></i> ${backup.destination === 'google_drive' ? 'Google Drive' : 'محلي'}</p>
                                </div>
                                <div class="backup-actions">
                                    <button class="btn btn-primary" onclick="backupMonitor.downloadBackup('${backup.id}')">
                                        <i class="fas fa-download"></i> تحميل
                                    </button>
                                    <button class="btn btn-warning" onclick="backupMonitor.restoreBackup('${backup.id}')">
                                        <i class="fas fa-undo"></i> استعادة
                                    </button>
                                    <button class="btn btn-danger" onclick="backupMonitor.deleteBackup('${backup.id}')">
                                        <i class="fas fa-trash"></i> حذف
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
    
    async downloadBackup(backupId) {
        try {
            this.showNotification('جاري تحميل النسخة الاحتياطية...', 'info');
            
            const response = await fetch(`/api/v1/backup/download/${backupId}`, {
                method: 'GET',
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `backup_${backupId}.zip`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showSuccess('تم تحميل النسخة الاحتياطية بنجاح');
            } else {
                this.showError('فشل في تحميل النسخة الاحتياطية');
            }
        } catch (error) {
            console.error('خطأ في تحميل النسخة:', error);
            this.showError('خطأ في تحميل النسخة الاحتياطية');
        }
    }
    
    async restoreBackup(backupId) {
        if (!confirm('هل أنت متأكد من استعادة هذه النسخة الاحتياطية؟ سيتم استبدال جميع البيانات الحالية.')) {
            return;
        }
        
        try {
            this.showNotification('جاري استعادة النسخة الاحتياطية...', 'info');
            
            const response = await fetch(`/api/v1/backup/restore/${backupId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('تم استعادة النسخة الاحتياطية بنجاح. سيتم إعادة تحميل الصفحة.');
                setTimeout(() => {
                    window.location.reload();
                }, 3000);
            } else {
                this.showError(data.error || 'فشل في استعادة النسخة الاحتياطية');
            }
        } catch (error) {
            console.error('خطأ في استعادة النسخة:', error);
            this.showError('خطأ في استعادة النسخة الاحتياطية');
        }
    }
    
    async deleteBackup(backupId) {
        if (!confirm('هل أنت متأكد من حذف هذه النسخة الاحتياطية؟ لا يمكن التراجع عن هذا الإجراء.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/backup/delete/${backupId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('تم حذف النسخة الاحتياطية بنجاح');
                // إعادة تحميل قائمة النسخ
                setTimeout(() => {
                    this.listAvailableBackups();
                }, 1000);
            } else {
                this.showError(data.error || 'فشل في حذف النسخة الاحتياطية');
            }
        } catch (error) {
            console.error('خطأ في حذف النسخة:', error);
            this.showError('خطأ في حذف النسخة الاحتياطية');
        }
    }
    
    uploadBackupFile() {
        // إنشاء input للملف
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.zip,.tar.gz,.backup';
        fileInput.style.display = 'none';
        
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            try {
                this.showNotification('جاري رفع النسخة الاحتياطية...', 'info');
                
                const formData = new FormData();
                formData.append('backup_file', file);
                
                const response = await fetch('/api/v1/backup/upload', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin'
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    this.showSuccess('تم رفع النسخة الاحتياطية بنجاح');
                    // تحديث الحالة
                    setTimeout(() => {
                        this.checkBackupStatus();
                    }, 1000);
                } else {
                    this.showError(data.error || 'فشل في رفع النسخة الاحتياطية');
                }
            } catch (error) {
                console.error('خطأ في رفع النسخة:', error);
                this.showError('خطأ في رفع النسخة الاحتياطية');
            }
            
            // إزالة input
            document.body.removeChild(fileInput);
        });
        
        document.body.appendChild(fileInput);
        fileInput.click();
    }
    
    handleDestinationChange(destination) {
        const googleDriveWarning = document.getElementById('google-drive-warning');
        
        if (destination === 'google_drive') {
            // التحقق من حالة الاتصال بـ Google Drive
            this.checkGoogleDriveConnection().then(() => {
                if (!this.googleDriveConnected) {
                    this.showNotification('يجب ربط Google Drive أولاً لاستخدام هذه الوجهة', 'warning');
                    // إعادة تعيين الخيار إلى محلي
                    const destinationSelect = document.getElementById('backup-destination');
                    if (destinationSelect) {
                        destinationSelect.value = 'local';
                    }
                }
            });
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // ===== تحسين تحميل الإعدادات =====
    
    async loadBackupSettings() {
        try {
            const response = await fetch('/api/v1/backup/settings', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.applyBackupSettings(data.settings);
                } else {
                    console.error('فشل في تحميل إعدادات النسخ الاحتياطي:', data.error);
                }
            }
        } catch (error) {
            console.error('خطأ في تحميل إعدادات النسخ الاحتياطي:', error);
        }
    }
    
    applyBackupSettings(settings) {
        // تطبيق الإعدادات على النموذج
        const autoBackupCheckbox = document.getElementById('تفعيل-النسخ-التلقائي');
        if (autoBackupCheckbox && settings.auto_backup_enabled !== undefined) {
            autoBackupCheckbox.checked = settings.auto_backup_enabled;
        }
        
        const frequencySelect = document.getElementById('backup-frequency');
        if (frequencySelect && settings.backup_frequency) {
            frequencySelect.value = settings.backup_frequency;
        }
        
        const destinationSelect = document.getElementById('backup-destination');
        if (destinationSelect && settings.backup_destination) {
            destinationSelect.value = settings.backup_destination;
        }
        
        const maxBackupsInput = document.getElementById('max-backups');
        if (maxBackupsInput && settings.max_backups) {
            maxBackupsInput.value = settings.max_backups;
        }
        
        // الخيارات المتقدمة
        const includeImagesCheckbox = document.getElementById('include-images');
        if (includeImagesCheckbox && settings.include_images !== undefined) {
            includeImagesCheckbox.checked = settings.include_images;
        }
        
        const compressBackupCheckbox = document.getElementById('compress-backup');
        if (compressBackupCheckbox && settings.compress_backup !== undefined) {
            compressBackupCheckbox.checked = settings.compress_backup;
        }
        
        const encryptBackupCheckbox = document.getElementById('encrypt-backup');
        if (encryptBackupCheckbox && settings.encrypt_backup !== undefined) {
            encryptBackupCheckbox.checked = settings.encrypt_backup;
        }
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

    // إتاحة الكلاس عالمياً
    window.BackupMonitor = BackupMonitor;
    
    } catch (error) {
        console.error('خطأ في تحميل BackupMonitor:', error);
        // في حالة الخطأ، إنشاء كلاس فارغ لتجنب كسر الموقع
        window.BackupMonitor = class {
            constructor() {
                console.warn('BackupMonitor loaded in fallback mode');
            }
        };
    }
    
})();
