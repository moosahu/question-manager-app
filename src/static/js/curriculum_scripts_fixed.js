// وظائف JavaScript لصفحة إدارة المنهج - نسخة مصححة ومدمجة

// متغيرات عامة
const ANIMATION_SPEED = 300; // سرعة الحركات بالمللي ثانية
let courseStates = {}; // لتخزين حالة فتح/إغلاق المناهج
let unitStates = {}; // لتخزين حالة فتح/إغلاق الوحدات
let isProcessing = false; // لمنع النقر المتكرر على أزرار التحريك

// عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // استعادة حالة المناهج والوحدات من التخزين المحلي
    loadStates();
    
    // تطبيق حالة المناهج والوحدات
    applyStates();
    
    // تهيئة وظيفة السحب والإفلات للمناهج
    initSortable();
    
    // التحقق من وجود معلمة t في URL (للتعامل مع إعادة التحميل مع معلمة عشوائية)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('t') || urlParams.has('nocache')) {
        // إزالة معلمات URL دون إعادة تحميل الصفحة
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);
        
        // إظهار رسالة نجاح
        showToast('تم تحديث الترتيب بنجاح', 'success');
    }
    
    // إضافة مستمع حدث للنقر على أزرار التحريك
    document.querySelectorAll('.move-up-btn, .move-down-btn').forEach(button => {
        button.addEventListener('click', function(event) {
            // منع النقر المتكرر
            if (isProcessing) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }
            
            // تعيين حالة المعالجة إلى true
            isProcessing = true;
            
            // إضافة فئة معالجة للزر
            this.classList.add('processing');
        });
    });
});

// تهيئة وظيفة السحب والإفلات
function initSortable() {
    // تهيئة السحب والإفلات للمناهج
    if ($("#courses-list").length) {
        $("#courses-list").sortable({
            handle: ".course-header",
            placeholder: "ui-sortable-placeholder",
            update: function(event, ui) {
                updateOrder('course', null);
            }
        });
    }
    
    // تهيئة السحب والإفلات للوحدات
    $(".units-list").each(function() {
        const courseId = $(this).attr('id').replace('units-list-', '');
        $(this).sortable({
            handle: ".unit-header",
            placeholder: "ui-sortable-placeholder",
            update: function(event, ui) {
                updateOrder('unit', courseId);
            }
        });
    });
    
    // تهيئة السحب والإفلات للدروس
    $(".lessons-list").each(function() {
        const unitId = $(this).attr('id').replace('lessons-list-', '');
        $(this).sortable({
            handle: ".lesson-header",
            placeholder: "ui-sortable-placeholder",
            update: function(event, ui) {
                updateOrder('lesson', unitId);
            }
        });
    });
}

// تحديث ترتيب العناصر بعد السحب والإفلات (محدث ومحسن)
function updateOrder(type, parentId) {
    const listSelector = type === 'course' ? '#courses-list' : 
                        type === 'unit' ? `#units-list-${parentId}` : 
                        `#lessons-list-${parentId}`;
    
    const items = [];
    $(`${listSelector} .${type}-item`).each(function() {
        items.push($(this).data('id'));
    });
    
    // إظهار مؤشر التحميل
    showLoading();
    
    // إرسال الترتيب الجديد إلى الخادم (طريقة محدثة ومحسنة)
    $.ajax({
        url: '/curriculum/update_bulk_order',
        type: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        },
        data: {
            type: type,
            parent_id: parentId, // استخدام parent_id بدلاً من id للتوافق مع الخادم المحدث
            new_order: JSON.stringify(items),
            csrf_token: $('input[name="csrf_token"]').val()
        },
        success: function(response) {
            console.log('✅ Order update successful:', response);
            
            if (response.success) {
                // إخفاء مؤشر التحميل
                hideLoading();
                
                // إظهار رسالة نجاح مع عدد العناصر المحدثة
                const updatedCount = response.updated_count || items.length;
                showToast(`تم تحديث ترتيب ${updatedCount} عنصر بنجاح`, 'success');
                
                // تحديث أرقام الترتيب في الواجهة
                updateOrderBadges(listSelector, type);
                
                // إعادة تعيين حالة المعالجة
                isProcessing = false;
            } else {
                // إخفاء مؤشر التحميل
                hideLoading();
                
                // إظهار رسالة خطأ
                showToast('فشل في تحديث الترتيب: ' + (response.error || 'خطأ غير معروف'), 'danger');
                console.error('Error updating order:', response.error);
                
                // إعادة تعيين حالة المعالجة
                isProcessing = false;
            }
        },
        error: function(xhr, status, error) {
            console.error('❌ Order update failed:', {
                status: xhr.status,
                statusText: xhr.statusText,
                responseText: xhr.responseText,
                error: error
            });
            
            // إخفاء مؤشر التحميل
            hideLoading();
            
            let errorMessage = 'خطأ في الاتصال بالخادم';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMessage = xhr.responseJSON.error;
            } else if (xhr.status === 400) {
                errorMessage = 'بيانات غير صالحة';
            } else if (xhr.status === 500) {
                errorMessage = 'خطأ في الخادم';
            }
            
            // إظهار رسالة خطأ
            showToast('فشل في تحديث الترتيب: ' + errorMessage, 'danger');
            
            // إعادة تعيين حالة المعالجة
            isProcessing = false;
        }
    });
}

// تحديث أرقام الترتيب في الواجهة (وظيفة جديدة)
function updateOrderBadges(listSelector, type) {
    $(`${listSelector} .${type}-item`).each(function(index) {
        $(this).find('.order-badge').text(index + 1);
    });
}

// تبديل حالة المنهج (فتح/إغلاق)
function toggleCourse(courseId) {
    const contentElement = document.getElementById(`course-content-${courseId}`);
    
    if (contentElement.classList.contains('active')) {
        // إغلاق المنهج
        $(contentElement).slideUp(ANIMATION_SPEED, function() {
            contentElement.classList.remove('active');
            courseStates[courseId] = false;
            saveStates();
        });
    } else {
        // فتح المنهج
        $(contentElement).slideDown(ANIMATION_SPEED, function() {
            contentElement.classList.add('active');
            courseStates[courseId] = true;
            saveStates();
        });
    }
}

// تبديل حالة الوحدة (فتح/إغلاق)
function toggleUnit(unitId, event) {
    // منع انتشار الحدث لتجنب تبديل حالة المنهج
    if (event) {
        event.stopPropagation();
    }
    
    const contentElement = document.getElementById(`unit-content-${unitId}`);
    
    if (contentElement.classList.contains('active')) {
        // إغلاق الوحدة
        $(contentElement).slideUp(ANIMATION_SPEED, function() {
            contentElement.classList.remove('active');
            unitStates[unitId] = false;
            saveStates();
        });
    } else {
        // فتح الوحدة
        $(contentElement).slideDown(ANIMATION_SPEED, function() {
            contentElement.classList.add('active');
            unitStates[unitId] = true;
            saveStates();
        });
    }
}

// تحريك عنصر لأعلى أو لأسفل
function moveItem(type, itemId, direction, event) {
    // منع انتشار الحدث لتجنب فتح/إغلاق المنهج أو الوحدة
    if (event) {
        event.stopPropagation();
    }
    
    // منع النقر المتكرر
    if (isProcessing) {
        return false;
    }
    
    // تعيين حالة المعالجة إلى true
    isProcessing = true;
    
    // تحديد المسار الصحيح بناءً على نوع العنصر
    let url;
    if (type === 'course') {
        url = `/curriculum/course/order/${itemId}/${direction}`;
    } else if (type === 'unit') {
        url = `/curriculum/unit/order/${itemId}/${direction}`;
    } else {
        url = `/curriculum/lesson/order/${itemId}/${direction}`;
    }
    
    // إظهار مؤشر التحميل
    showLoading();
    
    // إضافة سجل تفصيلي
    console.log(`Moving ${type} ${itemId} ${direction}`);
    console.log(`URL: ${url}`);
    
    // إرسال طلب تحديث الترتيب
    $.ajax({
        url: url,
        type: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        },
        data: {
            csrf_token: $('input[name="csrf_token"]').val()
        },
        success: function(response) {
            console.log('Response:', response);
            
            if (response.success) {
                // مسح التخزين المؤقت للمتصفح
                clearCache();
                
                // إعادة تحميل الصفحة مع معلمة عشوائية لمنع التخزين المؤقت
                const timestamp = response.timestamp || new Date().getTime();
                window.location.href = window.location.pathname + '?t=' + timestamp + '&nocache=' + Math.random();
            } else {
                // إخفاء مؤشر التحميل
                hideLoading();
                
                // إظهار رسالة خطأ
                showToast('حدث خطأ أثناء تحديث الترتيب', 'danger');
                console.error('Error updating order:', response.error);
                
                // إعادة تعيين حالة المعالجة
                isProcessing = false;
            }
        },
        error: function(xhr, status, error) {
            // إخفاء مؤشر التحميل
            hideLoading();
            
            // إظهار رسالة خطأ
            showToast('حدث خطأ أثناء الاتصال بالخادم', 'danger');
            console.error('AJAX error:', status, error);
            console.log('Response:', xhr.responseText);
            console.log('URL used:', url);
            
            // إعادة تعيين حالة المعالجة
            isProcessing = false;
        }
    });
}

// تأكيد حذف عنصر
function confirmDelete(type, itemId, event) {
    // منع انتشار الحدث لتجنب فتح/إغلاق المنهج أو الوحدة
    if (event) {
        event.stopPropagation();
    }
    
    // تحديد عنوان نافذة الحوار
    let title = '';
    if (type === 'course') {
        title = 'تأكيد حذف المنهج';
    } else if (type === 'unit') {
        title = 'تأكيد حذف الوحدة';
    } else {
        title = 'تأكيد حذف الدرس';
    }
    
    // تحديد نص نافذة الحوار
    let message = '';
    if (type === 'course') {
        message = 'هل أنت متأكد من رغبتك في حذف هذا المنهج وجميع الوحدات والدروس المرتبطة به؟';
    } else if (type === 'unit') {
        message = 'هل أنت متأكد من رغبتك في حذف هذه الوحدة وجميع الدروس المرتبطة بها؟';
    } else {
        message = 'هل أنت متأكد من رغبتك في حذف هذا الدرس وجميع الأسئلة المرتبطة به؟';
    }
    
    // تحديد رابط الحذف
    const deleteUrl = `/curriculum/${type}/delete/${itemId}`;
    
    // تحديث نافذة الحوار
    document.getElementById('deleteModalLabel').textContent = title;
    document.querySelector('#deleteModal .modal-body').textContent = message;
    document.getElementById('confirmDeleteBtn').href = deleteUrl;
    
    // عرض نافذة الحوار
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    deleteModal.show();
}

// حفظ حالة المناهج والوحدات في التخزين المحلي
function saveStates() {
    localStorage.setItem('courseStates', JSON.stringify(courseStates));
    localStorage.setItem('unitStates', JSON.stringify(unitStates));
}

// استعادة حالة المناهج والوحدات من التخزين المحلي
function loadStates() {
    const savedCourseStates = localStorage.getItem('courseStates');
    const savedUnitStates = localStorage.getItem('unitStates');
    
    if (savedCourseStates) {
        courseStates = JSON.parse(savedCourseStates);
    }
    
    if (savedUnitStates) {
        unitStates = JSON.parse(savedUnitStates);
    }
}

// تطبيق حالة المناهج والوحدات
function applyStates() {
    // تطبيق حالة المناهج
    for (const courseId in courseStates) {
        const contentElement = document.getElementById(`course-content-${courseId}`);
        if (contentElement) {
            if (courseStates[courseId]) {
                contentElement.classList.add('active');
                $(contentElement).show();
            } else {
                contentElement.classList.remove('active');
                $(contentElement).hide();
            }
        }
    }
    
    // تطبيق حالة الوحدات
    for (const unitId in unitStates) {
        const contentElement = document.getElementById(`unit-content-${unitId}`);
        if (contentElement) {
            if (unitStates[unitId]) {
                contentElement.classList.add('active');
                $(contentElement).show();
            } else {
                contentElement.classList.remove('active');
                $(contentElement).hide();
            }
        }
    }
}

// إظهار رسالة توست (محدثة ومحسنة)
function showToast(message, type) {
    // إنشاء عنصر التوست
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} flash alert-dismissible fade show`;
    toast.setAttribute('role', 'alert');
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.style.minWidth = '300px';
    
    // إضافة النص
    const textNode = document.createTextNode(message);
    toast.appendChild(textNode);
    
    // إضافة زر الإغلاق
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');
    toast.appendChild(closeButton);
    
    // إضافة التوست إلى الصفحة
    document.body.appendChild(toast);
    
    // إزالة التوست بعد 5 ثوان
    setTimeout(function() {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 5000);
}

// مسح التخزين المؤقت للمتصفح
function clearCache() {
    // محاولة مسح التخزين المؤقت للصفحة
    if (window.caches) {
        caches.keys().then(function(names) {
            for (let name of names) {
                caches.delete(name);
            }
        });
    }
    
    // مسح التخزين المؤقت للصور
    const images = document.querySelectorAll('img');
    for (let img of images) {
        const src = img.src;
        img.src = '';
        img.src = src;
    }
    
    // مسح التخزين المؤقت للأنماط
    const links = document.querySelectorAll('link[rel="stylesheet"]');
    for (let link of links) {
        const href = link.href;
        link.href = href.split('?')[0] + '?v=' + new Date().getTime();
    }
    
    // مسح التخزين المؤقت للنصوص
    const scripts = document.querySelectorAll('script[src]');
    for (let script of scripts) {
        const src = script.src;
        script.src = src.split('?')[0] + '?v=' + new Date().getTime();
    }
}

// إظهار مؤشر التحميل
function showLoading() {
    // إنشاء عنصر مؤشر التحميل إذا لم يكن موجوداً
    if (!document.getElementById('loadingIndicator')) {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loadingIndicator';
        loadingDiv.style.position = 'fixed';
        loadingDiv.style.top = '0';
        loadingDiv.style.left = '0';
        loadingDiv.style.width = '100%';
        loadingDiv.style.height = '100%';
        loadingDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        loadingDiv.style.display = 'flex';
        loadingDiv.style.justifyContent = 'center';
        loadingDiv.style.alignItems = 'center';
        loadingDiv.style.zIndex = '9999';
        
        const spinner = document.createElement('div');
        spinner.className = 'spinner-border text-light';
        spinner.setAttribute('role', 'status');
        
        const span = document.createElement('span');
        span.className = 'visually-hidden';
        span.textContent = 'جاري التحميل...';
        
        spinner.appendChild(span);
        loadingDiv.appendChild(spinner);
        document.body.appendChild(loadingDiv);
    } else {
        document.getElementById('loadingIndicator').style.display = 'flex';
    }
}

// إخفاء مؤشر التحميل
function hideLoading() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

