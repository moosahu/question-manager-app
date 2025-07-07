// ملف script.js مبسط ونظيف - بدون استهلاك موارد

// عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    
    // تهيئة الجسيمات المتحركة
    initParticles();
    
    // تحديث النشاط الأخير والأسئلة الأخيرة إذا كنا في الصفحة الرئيسية
    if (document.getElementById('activity-list')) {
        fetchRecentActivities();
        fetchRecentQuestions();
        setInterval(fetchRecentActivities, 60000);
        setInterval(fetchRecentQuestions, 300000);
    }
    
    // تهيئة الأكورديون إذا وجد
    initAccordion();
    
    // تهيئة المصادقة الثنائية إذا كنا في صفحة الإعدادات
    const twoFactorCheckbox = document.getElementById('two-factor-auth');
    if (twoFactorCheckbox) {
        initTwoFactorAuth();
    }
    
    // تهيئة نظام التبديل البسيط للأسئلة (بدون استهلاك موارد)
    initSimpleViewToggle();
});

// تهيئة نظام التبديل البسيط - بدون استهلاك موارد
function initSimpleViewToggle() {
    const cardViewBtn = document.getElementById('cardViewBtn');
    const tableViewBtn = document.getElementById('tableViewBtn');
    const cardView = document.getElementById('cardView');
    const tableView = document.getElementById('tableView');
    
    // التأكد من وجود العناصر
    if (!cardViewBtn || !tableViewBtn || !cardView || !tableView) {
        return; // لا توجد عناصر تبديل
    }
    
    // دالة التبديل إلى عرض البطاقات
    function showCardView() {
        tableView.style.display = 'none';
        cardView.style.display = 'block';
        
        tableViewBtn.classList.remove('active');
        tableViewBtn.classList.add('btn-outline-primary');
        cardViewBtn.classList.add('active');
        cardViewBtn.classList.remove('btn-outline-primary');
        
        // حفظ الحالة
        try {
            localStorage.setItem('questionViewMode', 'card');
        } catch (e) {
            // تجاهل خطأ localStorage
        }
    }
    
    // دالة التبديل إلى عرض الجدول
    function showTableView() {
        cardView.style.display = 'none';
        tableView.style.display = 'block';
        
        cardViewBtn.classList.remove('active');
        cardViewBtn.classList.add('btn-outline-primary');
        tableViewBtn.classList.add('active');
        tableViewBtn.classList.remove('btn-outline-primary');
        
        // حفظ الحالة
        try {
            localStorage.setItem('questionViewMode', 'table');
        } catch (e) {
            // تجاهل خطأ localStorage
        }
    }
    
    // ربط الأحداث
    cardViewBtn.addEventListener('click', function(e) {
        e.preventDefault();
        showCardView();
    });
    
    tableViewBtn.addEventListener('click', function(e) {
        e.preventDefault();
        showTableView();
    });
    
    // استعادة الحالة المحفوظة
    try {
        const savedMode = localStorage.getItem('questionViewMode');
        if (savedMode === 'card') {
            showCardView();
        } else if (savedMode === 'table') {
            showTableView();
        }
    } catch (e) {
        // تجاهل خطأ localStorage
    }
}

// تهيئة الجسيمات المتحركة
function initParticles() {
    const particles = document.querySelectorAll('.particle');
    particles.forEach(particle => {
        const x = Math.random() * 100;
        const y = Math.random() * 100;
        particle.style.left = `${x}%`;
        particle.style.top = `${y}%`;
        
        const size = Math.random() * 20 + 5;
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        
        const delay = Math.random() * 5;
        particle.style.animationDelay = `${delay}s`;
    });
}

// تهيئة الأكورديون
function initAccordion() {
    const accordionHeaders = document.querySelectorAll('.accordion-header');
    if (accordionHeaders.length > 0) {
        accordionHeaders.forEach(header => {
            header.addEventListener('click', function() {
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                if (content.style.maxHeight) {
                    content.style.maxHeight = null;
                } else {
                    content.style.maxHeight = content.scrollHeight + "px";
                }
            });
        });
    }
}

// دالة لجلب الأنشطة الأخيرة
function fetchRecentActivities() {
    const activityList = document.getElementById('activity-list');
    if (!activityList) return;
    
    fetch('/api/v1/activities/recent?limit=4')
        .then(response => response.json())
        .then(data => {
            if (!data.activities || data.activities.length === 0) {
                activityList.innerHTML = '<div class="no-data">لا توجد أنشطة حديثة</div>';
                return;
            }
            
            let activitiesHTML = '';
            data.activities.forEach(activity => {
                activitiesHTML += `
                    <div class="activity-item">
                        <div class="activity-icon"><i class="${activity.icon}"></i></div>
                        <div class="activity-details">
                            <p>${activity.description}</p>
                            <span class="activity-time">${activity.time_diff}</span>
                        </div>
                    </div>
                `;
            });
            
            activityList.innerHTML = activitiesHTML;
        })
        .catch(error => {
            // خطأ في جلب الأنشطة
        });
}

// دالة لجلب الأسئلة الأخيرة
function fetchRecentQuestions() {
    const questionsTable = document.getElementById('recent-questions-table');
    if (!questionsTable) return;
    
    fetch('/api/v1/questions/recent?limit=4')
        .then(response => response.json())
        .then(data => {
            if (!data.questions || data.questions.length === 0) {
                questionsTable.innerHTML = '<div class="no-data">لا توجد أسئلة حديثة</div>';
                return;
            }
            
            let tableHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>نص السؤال</th>
                            <th>الدرس</th>
                            <th>الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            data.questions.forEach((question, index) => {
                tableHTML += `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${question.text}</td>
                        <td>${question.lesson_name || 'غير محدد'}</td>
                        <td>
                            <a href="/questions/edit/${question.id}" class="btn btn-edit">تعديل</a>
                            <a href="#" class="btn btn-delete" onclick="confirmDelete(${question.id}, event)">حذف</a>
                        </td>
                    </tr>
                `;
            });
            
            tableHTML += `</tbody></table>`;
            questionsTable.innerHTML = tableHTML;
        })
        .catch(error => {
            // خطأ في جلب الأسئلة
        });
}

// دالة لتأكيد حذف سؤال
function confirmDelete(questionId, event) {
    event.preventDefault();
    if (confirm('هل أنت متأكد من حذف هذا السؤال؟')) {
        window.location.href = `/questions/delete/${questionId}`;
    }
}

// تهيئة المصادقة الثنائية
function initTwoFactorAuth() {
    const twoFactorCheckbox = document.getElementById('two-factor-auth');
    if (!twoFactorCheckbox) return;
    
    const originalState = twoFactorCheckbox.checked;
    
    twoFactorCheckbox.addEventListener('change', function(e) {
        e.preventDefault();
        
        if (this.checked && !originalState) {
            showTwoFactorSetupModal();
        } else if (!this.checked && originalState) {
            showTwoFactorDisableModal();
        }
        
        this.checked = originalState;
    });
}

// عرض نافذة إعداد المصادقة الثنائية
function showTwoFactorSetupModal() {
    const modal = document.getElementById('two-factor-setup-modal');
    if (!modal) {
        showNotification('خطأ في النظام', 'error');
        return;
    }
    
    modal.style.display = 'block';
    document.body.classList.add('modal-open');
    
    // جلب البيانات من الخادم
    fetch('/settings/setup-2fa', {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // تحديث QR Code
            const qrContainer = document.querySelector('#qr-code-container, .qr-code-container, [id*="qr"]');
            if (qrContainer && data.qr_html) {
                qrContainer.innerHTML = data.qr_html;
            }
            
            // تحديث المفتاح السري
            const secretElement = document.getElementById('secret-key');
            if (secretElement && data.secret) {
                if (secretElement.tagName === 'INPUT') {
                    secretElement.value = data.secret;
                } else {
                    secretElement.textContent = data.secret;
                }
            }
            
            // إنشاء QR Code يدوياً إذا لم يعمل التحديث التلقائي
            if (!qrContainer || !data.qr_html) {
                createQRCodeManually(data.qr_code, data.secret);
            }
            
            showNotification('تم تحميل بيانات المصادقة الثنائية بنجاح', 'success');
        } else {
            showNotification('فشل في تحميل بيانات المصادقة الثنائية', 'error');
        }
    })
    .catch(error => {
        console.error('خطأ:', error);
        showNotification('حدث خطأ في الاتصال', 'error');
    });
}

// إنشاء QR Code يدوياً
function createQRCodeManually(qrCodeBase64, secret) {
    const modal = document.getElementById('two-factor-setup-modal');
    if (!modal) return;
    
    let targetElement = modal.querySelector('.qr-code-placeholder, .qr-section, .modal-body');
    if (!targetElement) {
        targetElement = modal.querySelector('.modal-content');
    }
    
    if (targetElement && qrCodeBase64) {
        const qrHTML = `
            <div class="qr-code-section" style="text-align: center; margin: 20px 0;">
                <h4>رمز QR:</h4>
                <img src="data:image/png;base64,${qrCodeBase64}" alt="QR Code" style="max-width: 200px; height: auto; border: 1px solid #ddd; padding: 10px;" />
                <h4 style="margin-top: 20px;">المفتاح السري:</h4>
                <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; font-family: monospace; word-break: break-all;">
                    ${secret}
                </div>
            </div>
        `;
        
        const existingQR = targetElement.querySelector('.qr-code-section');
        if (existingQR) {
            existingQR.outerHTML = qrHTML;
        } else {
            targetElement.insertAdjacentHTML('afterbegin', qrHTML);
        }
    }
}

// عرض نافذة إلغاء تفعيل المصادقة الثنائية
function showTwoFactorDisableModal() {
    const modal = document.getElementById('two-factor-disable-modal');
    if (modal) {
        modal.style.display = 'block';
        document.body.classList.add('modal-open');
    }
}

// إغلاق النوافذ
function closeTwoFactorModal() {
    const modal = document.getElementById('two-factor-setup-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.classList.remove('modal-open');
    }
}

function closeTwoFactorDisableModal() {
    const modal = document.getElementById('two-factor-disable-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.classList.remove('modal-open');
    }
}

// تفعيل المصادقة الثنائية
function enableTwoFactor() {
    const codeInput = document.getElementById('verification-code');
    if (!codeInput) return;
    
    const code = codeInput.value.trim();
    if (!code || code.length !== 6) {
        showNotification('يرجى إدخال رمز التحقق المكون من 6 أرقام', 'error');
        return;
    }

    fetch('/settings/verify-2fa', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code: code })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('تم تفعيل المصادقة الثنائية بنجاح', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification(data.message || 'حدث خطأ', 'error');
        }
    })
    .catch(error => {
        console.error('خطأ:', error);
        showNotification('حدث خطأ في الاتصال', 'error');
    });
}

// إلغاء تفعيل المصادقة الثنائية
function disableTwoFactor() {
    const codeInput = document.getElementById('disable-verification-code');
    if (!codeInput) return;
    
    const code = codeInput.value.trim();
    if (!code || code.length !== 6) {
        showNotification('يرجى إدخال رمز التحقق المكون من 6 أرقام', 'error');
        return;
    }

    if (!confirm('هل أنت متأكد من إلغاء تفعيل المصادقة الثنائية؟')) {
        return;
    }

    const formData = new FormData();
    formData.append('verification_code', code);

    fetch('/settings/disable-2fa', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('تم إلغاء تفعيل المصادقة الثنائية بنجاح', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification(data.message || 'حدث خطأ', 'error');
        }
    })
    .catch(error => {
        console.error('خطأ:', error);
        showNotification('حدث خطأ في الاتصال', 'error');
    });
}

// دالة لعرض الإشعارات
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
        </div>
    `;
    
    // إضافة الأنماط
    if (!document.querySelector('#notification-styles')) {
        const styles = document.createElement('style');
        styles.id = 'notification-styles';
        styles.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                min-width: 300px;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                animation: slideInRight 0.3s ease-out;
                direction: rtl;
            }
            .notification-success {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .notification-error {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .notification-info {
                background-color: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }
            .notification-content {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .notification-close {
                background: none;
                border: none;
                font-size: 18px;
                cursor: pointer;
                margin-right: auto;
            }
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(styles);
    }
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// إغلاق النوافذ عند النقر خارجها
window.addEventListener('click', function(event) {
    const setupModal = document.getElementById('two-factor-setup-modal');
    const disableModal = document.getElementById('two-factor-disable-modal');
    
    if (event.target === setupModal) {
        closeTwoFactorModal();
    }
    if (event.target === disableModal) {
        closeTwoFactorDisableModal();
    }
});

// إغلاق النوافذ بمفتاح Escape
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeTwoFactorModal();
        closeTwoFactorDisableModal();
    }
});

// دالة تأكيد الحذف للمناهج والوحدات والدروس
function confirmDelete(type, itemId, event) {
    if (event) event.stopPropagation();

    let title = '', message = '';
    if (type === 'course') {
        title = 'تأكيد حذف المنهج';
        message = 'هل أنت متأكد من رغبتك في حذف هذا المنهج وجميع الوحدات والدروس المرتبطة به؟';
    } else if (type === 'unit') {
        title = 'تأكيد حذف الوحدة';
        message = 'هل أنت متأكد من رغبتك في حذف هذه الوحدة وجميع الدروس المرتبطة بها؟';
    } else {
        title = 'تأكيد حذف الدرس';
        message = 'هل أنت متأكد من رغبتك في حذف هذا الدرس وجميع الأسئلة المرتبطة به؟';
    }

    const deleteUrl = `/curriculum/${type}/delete/${itemId}`;
    document.getElementById('deleteModalLabel').textContent = title;
    document.querySelector('#deleteModal .modal-body').textContent = message;
    document.getElementById('confirmDeleteBtn').href = deleteUrl;

    const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    deleteModal.show();
}

// تصفية بسيطة بدون AJAX
document.addEventListener('DOMContentLoaded', function () {
    const filterForm = document.getElementById('filter-form');
    
    if (filterForm) {
        // تأكد من أن النموذج يرسل GET request للخادم
        filterForm.method = 'GET';
        filterForm.addEventListener('submit', function() {
            // السماح للنموذج بالإرسال العادي للخادم
            return true;
        });
    }
});

// ===== ملاحظة مهمة =====
/*
هذا الملف لا يحتوي على:
- أي دوال إصلاح للبطاقات
- أي MutationObserver
- أي setTimeout أو setInterval للبطاقات
- أي عمليات مراقبة مستمرة للبطاقات

استهلاك الموارد للبطاقات: صفر ✅
*/

// أضف في نهاية static/js/script.js
document.addEventListener("DOMContentLoaded", function() {
  document.querySelectorAll(".question-text, .choice-text, .explanation-text").forEach(el => {
    const t = el.textContent.trim();
    if (/^[\[\(0-9]/.test(t) && /[A-Za-z]/.test(t)) {
      el.style.direction   = "ltr";
      el.style.unicodeBidi = "bidi-override";
      el.style.fontFamily  = "Courier New, monospace";
      el.style.whiteSpace  = "nowrap";
    }
  });
});

document.querySelectorAll('textarea, input[type="text"]').forEach((el) => {
  el.addEventListener('input', function () {
    const value = el.value.trim();
    if (value.length === 0) return;

    const firstChar = value.charAt(0);
    const isArabic = /[\u0600-\u06FF]/.test(firstChar);
    
    el.style.direction = isArabic ? 'rtl' : 'ltr';
    el.style.textAlign = isArabic ? 'right' : 'left';
  });
});

// ========== التصفية الديناميكية للوحدات والدروس ==========
// الحل المتكامل والصحيح للتصفية

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 بدء تهيئة التصفية الديناميكية...');
    initDynamicFiltering();
});

function initDynamicFiltering() {
    const courseSelect = document.getElementById('course_id');
    const unitSelect = document.getElementById('unit_id');
    const lessonSelect = document.getElementById('lesson_id');
    
    if (!courseSelect || !unitSelect || !lessonSelect) {
        console.warn('❌ عناصر التصفية غير موجودة');
        return;
    }
    
    console.log('✅ تم العثور على عناصر التصفية');
    
    // عند تغيير المنهج
    courseSelect.addEventListener('change', function() {
        const selectedCourseId = this.value;
        console.log('📚 تم اختيار المنهج:', selectedCourseId);
        
        // إعادة تعيين الوحدات والدروس
        resetSelect(unitSelect, 'اختر الوحدة');
        resetSelect(lessonSelect, 'اختر الدرس');
        
        if (selectedCourseId) {
            fetchUnitsForCourse(selectedCourseId);
        }
    });
    
    // عند تغيير الوحدة
    unitSelect.addEventListener('change', function() {
        const selectedUnitId = this.value;
        console.log('📖 تم اختيار الوحدة:', selectedUnitId);
        
        // إعادة تعيين الدروس
        resetSelect(lessonSelect, 'اختر الدرس');
        
        if (selectedUnitId) {
            fetchLessonsForUnit(selectedUnitId);
        }
    });
    
    console.log('✅ تم تهيئة التصفية الديناميكية بنجاح');
}

// دالة لإعادة تعيين قائمة منسدلة
function resetSelect(selectElement, placeholder) {
    selectElement.innerHTML = `<option value="">-- ${placeholder} --</option>`;
}

// دالة لإضافة خيار تحميل
function addLoadingOption(selectElement, message = 'جاري التحميل...') {
    selectElement.innerHTML = `<option value="" disabled>${message}</option>`;
}

// جلب الوحدات من API
function fetchUnitsForCourse(courseId) {
    console.log('🔄 جلب الوحدات للمنهج:', courseId);
    const unitSelect = document.getElementById('unit_id');
    
    // إضافة مؤشر التحميل
    addLoadingOption(unitSelect, 'جاري تحميل الوحدات...');
    
    // استدعاء API
    fetch(`/api/v1/courses/${courseId}/units`)
        .then(response => {
            console.log('📡 استجابة API للوحدات:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('📦 بيانات الوحدات المستلمة:', data);
            
            // إعادة تعيين القائمة
            resetSelect(unitSelect, 'اختر الوحدة');
            
            if (data && Array.isArray(data) && data.length > 0) {
                data.forEach(unit => {
                    const option = document.createElement('option');
                    option.value = unit.id;
                    option.textContent = unit.name;
                    unitSelect.appendChild(option);
                });
                console.log(`✅ تم تحميل ${data.length} وحدة بنجاح`);
            } else {
                unitSelect.innerHTML = '<option value="" disabled>لا توجد وحدات متاحة</option>';
                console.log('⚠️ لا توجد وحدات متاحة لهذا المنهج');
            }
        })
        .catch(error => {
            console.error('❌ خطأ في جلب الوحدات:', error);
            unitSelect.innerHTML = '<option value="" disabled>خطأ في تحميل الوحدات</option>';
            
            // محاولة عرض تفاصيل الخطأ
            console.error('تفاصيل الخطأ:', {
                message: error.message,
                courseId: courseId,
                url: `/api/v1/courses/${courseId}/units`
            });
        });
}

// جلب الدروس من API
function fetchLessonsForUnit(unitId) {
    console.log('🔄 جلب الدروس للوحدة:', unitId);
    const lessonSelect = document.getElementById('lesson_id');
    
    // إضافة مؤشر التحميل
    addLoadingOption(lessonSelect, 'جاري تحميل الدروس...');
    
    // استدعاء API
    fetch(`/api/v1/units/${unitId}/lessons`)
        .then(response => {
            console.log('📡 استجابة API للدروس:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('📦 بيانات الدروس المستلمة:', data);
            
            // إعادة تعيين القائمة
            resetSelect(lessonSelect, 'اختر الدرس');
            
            if (data && Array.isArray(data) && data.length > 0) {
                data.forEach(lesson => {
                    const option = document.createElement('option');
                    option.value = lesson.id;
                    option.textContent = lesson.name;
                    lessonSelect.appendChild(option);
                });
                console.log(`✅ تم تحميل ${data.length} درس بنجاح`);
            } else {
                lessonSelect.innerHTML = '<option value="" disabled>لا توجد دروس متاحة</option>';
                console.log('⚠️ لا توجد دروس متاحة لهذه الوحدة');
            }
        })
        .catch(error => {
            console.error('❌ خطأ في جلب الدروس:', error);
            lessonSelect.innerHTML = '<option value="" disabled>خطأ في تحميل الدروس</option>';
            
            // محاولة عرض تفاصيل الخطأ
            console.error('تفاصيل الخطأ:', {
                message: error.message,
                unitId: unitId,
                url: `/api/v1/units/${unitId}/lessons`
            });
        });
}

// دالة اختبار للتحقق من API endpoints
function testAPIEndpoints() {
    console.log('🧪 اختبار API endpoints...');
    
    // اختبار endpoint المناهج
    fetch('/api/v1/courses')
        .then(response => response.json())
        .then(data => {
            console.log('✅ API المناهج يعمل:', data.length, 'منهج');
            if (data.length > 0) {
                console.log('أول منهج:', data[0]);
            }
        })
        .catch(error => {
            console.error('❌ خطأ في API المناهج:', error);
        });
}

// تشغيل اختبار API (يمكن إزالته في الإنتاج)
setTimeout(testAPIEndpoints, 1000);



// متغير لتتبع حالة إظهار/إخفاء العلامات الصحيحة
var correctAnswersVisible = true;

// وظيفة تبديل إظهار/إخفاء جميع العلامات الصحيحة
function toggleCorrectAnswers() {
    const button = document.getElementById('toggleCorrectAnswersBtn');
    const buttonIcon = button.querySelector('i');
    
    if (correctAnswersVisible) {
        // إخفاء العلامات الصحيحة
        hideCorrectAnswers();
        correctAnswersVisible = false;
        
        // تغيير نص وأيقونة الزر
        button.innerHTML = '<i class="fas fa-eye"></i> إظهار العلامات الصحيحة';
        button.classList.remove('btn-info');
        button.classList.add('btn-success');
        
        showNotification('تم إخفاء العلامات الصحيحة', 'info');
    } else {
        // إظهار العلامات الصحيحة
        showCorrectAnswers();
        correctAnswersVisible = true;
        
        // تغيير نص وأيقونة الزر
        button.innerHTML = '<i class="fas fa-eye-slash"></i> إخفاء العلامات الصحيحة';
        button.classList.remove('btn-success');
        button.classList.add('btn-info');
        
        showNotification('تم إظهار العلامات الصحيحة', 'success');
    }
}

// وظيفة إخفاء العلامات الصحيحة
function hideCorrectAnswers() {
    const cardView = document.getElementById('cardView');
    if (cardView && cardView.style.display !== 'none') {
        // البحث عن جميع الخيارات الصحيحة في البطاقات
        const correctOptions = cardView.querySelectorAll('.option-item.correct-option');
        
        correctOptions.forEach(option => {
            // إخفاء المؤشرات البصرية للإجابة الصحيحة مؤقتاً
            option.style.backgroundColor = 'white !important';
            option.style.borderColor = '#dee2e6 !important';
            
            // إضافة class لإخفاء الخلفية الخضراء
            option.classList.add('correct-answer-hidden');
            
            // إخفاء أيقونة الصح
            const checkIcon = option.querySelector('.fas.fa-check');
            if (checkIcon) {
                checkIcon.style.display = 'none';
            }
            
            // تغيير لون النص إلى اللون العادي
            const optionText = option.querySelector('.option-text');
            if (optionText) {
                optionText.style.color = '#333 !important';
                optionText.style.fontWeight = 'normal !important';
            }
            
            // إضافة علامة مخفية للتعرف على الخيارات المخفية
            option.setAttribute('data-correct-hidden', 'true');
        });
        
        // إخفاء مؤشرات "الإجابة الصحيحة" من النوافذ المنبثقة
        const correctIndicators = cardView.querySelectorAll('.correct-indicator');
        correctIndicators.forEach(indicator => {
            indicator.style.display = 'none';
            indicator.setAttribute('data-hidden', 'true');
        });
    }
    
    // إضافة CSS لإخفاء الخلفية الخضراء إذا لم يكن موجوداً
    addHiddenCorrectAnswerStyles();
}

// وظيفة إظهار العلامات الصحيحة
function showCorrectAnswers() {
    const cardView = document.getElementById('cardView');
    if (cardView && cardView.style.display !== 'none') {
        // البحث عن جميع الخيارات المخفية
        const hiddenCorrectOptions = cardView.querySelectorAll('.option-item[data-correct-hidden="true"]');
        
        hiddenCorrectOptions.forEach(option => {
            // إزالة class الإخفاء
            option.classList.remove('correct-answer-hidden');
            
            // إعادة المؤشرات البصرية للإجابة الصحيحة
            option.style.backgroundColor = '';
            option.style.borderColor = '';
            
            // إظهار أيقونة الصح
            const checkIcon = option.querySelector('.fas.fa-check');
            if (checkIcon) {
                checkIcon.style.display = 'inline';
            }
            
            // إعادة لون النص للإجابة الصحيحة
            const optionText = option.querySelector('.option-text');
            if (optionText) {
                optionText.style.color = '';
                optionText.style.fontWeight = '';
            }
            
            // إزالة العلامة المخفية
            option.removeAttribute('data-correct-hidden');
        });
        
        // إظهار مؤشرات "الإجابة الصحيحة" في النوافذ المنبثقة
        const hiddenIndicators = cardView.querySelectorAll('.correct-indicator[data-hidden="true"]');
        hiddenIndicators.forEach(indicator => {
            indicator.style.display = 'block';
            indicator.removeAttribute('data-hidden');
        });
    }
}

// وظيفة لإضافة CSS لإخفاء الخلفية الخضراء
function addHiddenCorrectAnswerStyles() {
    // التحقق من وجود الأنماط مسبقاً
    if (document.getElementById('hidden-correct-answer-styles')) {
        return;
    }
    
    const style = document.createElement('style');
    style.id = 'hidden-correct-answer-styles';
    style.textContent = `
        .correct-answer-hidden {
            background-color: white !important;
            border-color: #dee2e6 !important;
        }
        .correct-answer-hidden .option-text {
            color: #333 !important;
            font-weight: normal !important;
        }
        .correct-answer-hidden .fas.fa-check {
            display: none !important;
        }
    `;
    document.head.appendChild(style);
}

// وظيفة لإخفاء/إظهار العلامة الصحيحة من سؤال واحد (يمكن استخدامها لاحقاً)
function toggleCorrectAnswerForQuestion(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    if (!questionCard) return;
    
    const correctOptions = questionCard.querySelectorAll('.option-item.correct-option');
    const isHidden = correctOptions[0] && correctOptions[0].getAttribute('data-correct-hidden') === 'true';
    
    // إضافة CSS لإخفاء الخلفية الخضراء إذا لم يكن موجوداً
    addHiddenCorrectAnswerStyles();
    
    correctOptions.forEach(option => {
        if (isHidden) {
            // إظهار العلامة
            option.classList.remove('correct-answer-hidden');
            option.style.backgroundColor = '';
            option.style.borderColor = '';
            
            const checkIcon = option.querySelector('.fas.fa-check');
            if (checkIcon) {
                checkIcon.style.display = 'inline';
            }
            
            const optionText = option.querySelector('.option-text');
            if (optionText) {
                optionText.style.color = '';
                optionText.style.fontWeight = '';
            }
            
            option.removeAttribute('data-correct-hidden');
        } else {
            // إخفاء العلامة
            option.classList.add('correct-answer-hidden');
            option.style.backgroundColor = 'white !important';
            option.style.borderColor = '#dee2e6 !important';
            
            const checkIcon = option.querySelector('.fas.fa-check');
            if (checkIcon) {
                checkIcon.style.display = 'none';
            }
            
            const optionText = option.querySelector('.option-text');
            if (optionText) {
                optionText.style.color = '#333 !important';
                optionText.style.fontWeight = 'normal !important';
            }
            
            option.setAttribute('data-correct-hidden', 'true');
        }
    });
    
    const action = isHidden ? 'إظهار' : 'إخفاء';
    showNotification(`تم ${action} العلامة الصحيحة للسؤال`, 'success');
}


// ===== نظام البحث المتقدم في الأسئلة والمحتوى =====

// متغيرات البحث
let searchTimeout;
let originalQuestions = [];
let filteredQuestions = [];

// تهيئة نظام البحث عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    initializeSearchSystem();
});

// تهيئة نظام البحث
function initializeSearchSystem() {
    const searchInput = document.getElementById('search_input');
    const searchType = document.getElementById('search_type');
    const caseSensitive = document.getElementById('case_sensitive');
    const wholeWord = document.getElementById('whole_word');
    const clearSearch = document.getElementById('clear_search');
    
    if (!searchInput) return; // إذا لم توجد عناصر البحث، اخرج من الدالة
    
    // حفظ الأسئلة الأصلية
    saveOriginalQuestions();
    
    // ربط الأحداث
    searchInput.addEventListener('input', handleSearchInput);
    searchType.addEventListener('change', performSearch);
    caseSensitive.addEventListener('change', performSearch);
    wholeWord.addEventListener('change', performSearch);
    clearSearch.addEventListener('click', clearSearchResults);
    
    // البحث عند الضغط على Enter
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            performSearch();
        }
    });
}

// حفظ الأسئلة الأصلية
function saveOriginalQuestions() {
    const cardView = document.getElementById('cardView');
    const tableView = document.getElementById('tableView');
    
    originalQuestions = [];
    
    // حفظ بيانات البطاقات
    if (cardView) {
        const cards = cardView.querySelectorAll('.enhanced-card-wrapper');
        cards.forEach((card, index) => {
            const questionData = extractQuestionData(card);
            questionData.index = index;
            questionData.element = card;
            questionData.type = 'card';
            originalQuestions.push(questionData);
        });
    }
    
    // حفظ بيانات الجدول
    if (tableView) {
        const rows = tableView.querySelectorAll('tbody tr');
        rows.forEach((row, index) => {
            const questionData = extractTableRowData(row);
            questionData.index = index;
            questionData.element = row;
            questionData.type = 'table';
            originalQuestions.push(questionData);
        });
    }
}

// استخراج بيانات السؤال من البطاقة
function extractQuestionData(card) {
    const questionText = card.querySelector('.question-text')?.textContent || '';
    const options = [];
    const correctOptions = [];
    
    const optionElements = card.querySelectorAll('.option-item');
    optionElements.forEach(option => {
        const optionText = option.querySelector('.option-text')?.textContent || '';
        options.push(optionText);
        
        if (option.classList.contains('correct-option')) {
            correctOptions.push(optionText);
        }
    });
    
    const lesson = card.querySelector('.detail-value')?.textContent || '';
    const unit = card.querySelectorAll('.detail-value')[1]?.textContent || '';
    
    return {
        questionText,
        options,
        correctOptions,
        lesson,
        unit,
        allText: [questionText, ...options, lesson, unit].join(' ').toLowerCase()
    };
}

// استخراج بيانات السؤال من صف الجدول
function extractTableRowData(row) {
    const cells = row.querySelectorAll('td');
    const questionText = cells[1]?.textContent || '';
    const lesson = cells[2]?.textContent || '';
    const unit = cells[3]?.textContent || '';
    const course = cells[4]?.textContent || '';
    
    return {
        questionText,
        options: [],
        correctOptions: [],
        lesson,
        unit,
        course,
        allText: [questionText, lesson, unit, course].join(' ').toLowerCase()
    };
}

// معالجة إدخال البحث مع تأخير
function handleSearchInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(performSearch, 300); // تأخير 300ms للبحث الفوري
}

// تنفيذ البحث
function performSearch() {
    const searchInput = document.getElementById('search_input');
    const searchType = document.getElementById('search_type');
    const caseSensitive = document.getElementById('case_sensitive');
    const wholeWord = document.getElementById('whole_word');
    
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.trim();
    
    if (searchTerm === '') {
        showAllQuestions();
        updateSearchResultsCount(0, true);
        return;
    }
    
    const searchOptions = {
        term: searchTerm,
        type: searchType.value,
        caseSensitive: caseSensitive.checked,
        wholeWord: wholeWord.checked
    };
    
    filteredQuestions = filterQuestions(searchOptions);
    displayFilteredQuestions();
    highlightSearchResults(searchOptions);
    updateSearchResultsCount(filteredQuestions.length, false);
}

// تصفية الأسئلة حسب معايير البحث
function filterQuestions(options) {
    const { term, type, caseSensitive, wholeWord } = options;
    
    let searchTerm = caseSensitive ? term : term.toLowerCase();
    
    if (wholeWord) {
        searchTerm = `\\b${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`;
    }
    
    const regex = new RegExp(searchTerm, wholeWord ? (caseSensitive ? 'g' : 'gi') : (caseSensitive ? 'g' : 'gi'));
    
    return originalQuestions.filter(question => {
        let searchText = '';
        
        switch (type) {
            case 'question':
                searchText = caseSensitive ? question.questionText : question.questionText.toLowerCase();
                break;
            case 'options':
                searchText = caseSensitive ? question.options.join(' ') : question.options.join(' ').toLowerCase();
                break;
            case 'correct':
                searchText = caseSensitive ? question.correctOptions.join(' ') : question.correctOptions.join(' ').toLowerCase();
                break;
            default: // 'all'
                searchText = caseSensitive ? question.allText : question.allText.toLowerCase();
        }
        
        if (wholeWord) {
            return regex.test(searchText);
        } else {
            return searchText.includes(searchTerm);
        }
    });
}

// عرض الأسئلة المفلترة
function displayFilteredQuestions() {
    const cardView = document.getElementById('cardView');
    const tableView = document.getElementById('tableView');
    
    // إخفاء جميع الأسئلة أولاً
    originalQuestions.forEach(question => {
        question.element.style.display = 'none';
    });
    
    // إظهار الأسئلة المفلترة فقط
    filteredQuestions.forEach(question => {
        question.element.style.display = '';
    });
    
    // إضافة رسالة إذا لم توجد نتائج
    showNoResultsMessage(filteredQuestions.length === 0);
}

// إظهار جميع الأسئلة
function showAllQuestions() {
    originalQuestions.forEach(question => {
        question.element.style.display = '';
    });
    
    removeHighlights();
    showNoResultsMessage(false);
}

// تمييز نتائج البحث
function highlightSearchResults(options) {
    const { term, caseSensitive } = options;
    
    if (!term) return;
    
    removeHighlights();
    
    const searchTerm = caseSensitive ? term : term.toLowerCase();
    
    filteredQuestions.forEach(question => {
        const element = question.element;
        const textElements = element.querySelectorAll('.question-text, .option-text, .detail-value, td');
        
        textElements.forEach(textElement => {
            const originalText = textElement.textContent;
            const searchText = caseSensitive ? originalText : originalText.toLowerCase();
            
            if (searchText.includes(searchTerm)) {
                const highlightedText = highlightText(originalText, term, caseSensitive);
                textElement.innerHTML = highlightedText;
                textElement.classList.add('search-highlighted');
            }
        });
    });
}

// تمييز النص
function highlightText(text, searchTerm, caseSensitive) {
    const flags = caseSensitive ? 'g' : 'gi';
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, flags);
    return text.replace(regex, '<mark class="search-highlight">$1</mark>');
}

// إزالة التمييز
function removeHighlights() {
    const highlightedElements = document.querySelectorAll('.search-highlighted');
    highlightedElements.forEach(element => {
        element.innerHTML = element.textContent;
        element.classList.remove('search-highlighted');
    });
    
    const highlights = document.querySelectorAll('.search-highlight');
    highlights.forEach(highlight => {
        const parent = highlight.parentNode;
        parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
        parent.normalize();
    });
}

// مسح نتائج البحث
function clearSearchResults() {
    const searchInput = document.getElementById('search_input');
    if (searchInput) {
        searchInput.value = '';
        showAllQuestions();
        updateSearchResultsCount(0, true);
    }
}

// تحديث عداد النتائج
function updateSearchResultsCount(count, isCleared) {
    const countElement = document.getElementById('search_results_count');
    if (!countElement) return;
    
    if (isCleared) {
        countElement.textContent = '';
        countElement.style.display = 'none';
    } else {
        countElement.textContent = `${count} نتيجة`;
        countElement.style.display = 'inline-block';
        
        // تغيير لون الشارة حسب عدد النتائج
        countElement.className = 'badge ' + (count > 0 ? 'bg-success' : 'bg-warning');
    }
}

// إظهار رسالة عدم وجود نتائج
function showNoResultsMessage(show) {
    let noResultsElement = document.getElementById('no-search-results');
    
    if (show && !noResultsElement) {
        noResultsElement = document.createElement('div');
        noResultsElement.id = 'no-search-results';
        noResultsElement.className = 'text-center text-muted py-5';
        noResultsElement.innerHTML = `
            <i class="fas fa-search fa-3x mb-3"></i>
            <h4>لا توجد نتائج مطابقة</h4>
            <p>جرب تغيير كلمات البحث أو معايير البحث</p>
        `;
        
        // إضافة الرسالة بعد أزرار التبديل
        const viewToggle = document.querySelector('.view-toggle');
        if (viewToggle) {
            viewToggle.parentNode.insertBefore(noResultsElement, viewToggle.nextSibling);
        }
    } else if (!show && noResultsElement) {
        noResultsElement.remove();
    }
}

// دالة لإعادة تهيئة البحث عند تغيير المحتوى
function reinitializeSearch() {
    saveOriginalQuestions();
    clearSearchResults();
}

