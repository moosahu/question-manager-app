/**
 * إدارة مواعيد الاختبار التحصيلي
 * يتعامل مع APIs لجلب وحفظ وحذف المواعيد
 * السنة متغيرة وليست ثابتة
 */

// ==================== دوال عرض الإشعارات ====================

function showLoading() {
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}

function showSuccess(message) {
    toastr.success(message);
}

function showError(message) {
    toastr.error(message);
}

function showInfo(message) {
    toastr.info(message);
}

function showWarning(message) {
    toastr.warning(message);
}

// ==================== جلب المواعيد من السيرفر ====================

async function loadDates() {
    try {
        showLoading();
        showInfo('جاري تحميل المواعيد...');

        const response = await fetch('/admin/exam-dates/api/dates', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const data = await response.json();

        if (data.success) {
            // تعبئة الحقول بالبيانات
            populateFields(data.dates);
            showSuccess('تم تحميل المواعيد بنجاح');
        } else {
            showError('فشل تحميل المواعيد: ' + (data.error || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('خطأ في تحميل المواعيد:', error);
        showError('حدث خطأ في الاتصال بالسيرفر');
    } finally {
        hideLoading();
    }
}

// ==================== تعبئة الحقول بالبيانات ====================

function populateFields(dates) {
    // تعبئة السنة
    if (dates.exam_year) {
        document.getElementById('exam_year').value = dates.exam_year;
    }

    // تعبئة مواعيد التسجيل
    if (dates.registration_start_male) {
        document.getElementById('registration_start_male').value = formatDateForInput(dates.registration_start_male);
    }
    if (dates.registration_end_male) {
        document.getElementById('registration_end_male').value = formatDateForInput(dates.registration_end_male);
    }
    if (dates.registration_start_female) {
        document.getElementById('registration_start_female').value = formatDateForInput(dates.registration_start_female);
    }
    if (dates.registration_end_female) {
        document.getElementById('registration_end_female').value = formatDateForInput(dates.registration_end_female);
    }

    // تعبئة فترات الاختبار
    if (dates.exam_period1_start) {
        document.getElementById('exam_period1_start').value = formatDateForInput(dates.exam_period1_start);
    }
    if (dates.exam_period1_end) {
        document.getElementById('exam_period1_end').value = formatDateForInput(dates.exam_period1_end);
    }
    if (dates.exam_period2_start) {
        document.getElementById('exam_period2_start').value = formatDateForInput(dates.exam_period2_start);
    }
    if (dates.exam_period2_end) {
        document.getElementById('exam_period2_end').value = formatDateForInput(dates.exam_period2_end);
    }
}

// ==================== تنسيق التاريخ للإدخال ====================

function formatDateForInput(dateString) {
    if (!dateString) return '';
    
    try {
        // تحويل التاريخ إلى صيغة datetime-local
        const date = new Date(dateString);
        
        // التحقق من صحة التاريخ
        if (isNaN(date.getTime())) {
            console.error('Invalid date:', dateString);
            return '';
        }
        
        // تنسيق التاريخ: YYYY-MM-DDTHH:MM
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    } catch (error) {
        console.error('خطأ في تنسيق التاريخ:', error);
        return '';
    }
}

// ==================== تنسيق التاريخ للإرسال ====================

function formatDateForSave(dateString) {
    if (!dateString) return null;
    
    try {
        const date = new Date(dateString);
        
        // التحقق من صحة التاريخ
        if (isNaN(date.getTime())) {
            console.error('Invalid date:', dateString);
            return null;
        }
        
        // إرجاع بصيغة ISO
        return date.toISOString();
    } catch (error) {
        console.error('خطأ في تنسيق التاريخ للحفظ:', error);
        return null;
    }
}

// ==================== جمع البيانات من الحقول ====================

function collectDatesData() {
    const data = {
        // السنة
        exam_year: document.getElementById('exam_year').value.trim(),
        
        // مواعيد التسجيل
        registration_start_male: formatDateForSave(document.getElementById('registration_start_male').value),
        registration_end_male: formatDateForSave(document.getElementById('registration_end_male').value),
        registration_start_female: formatDateForSave(document.getElementById('registration_start_female').value),
        registration_end_female: formatDateForSave(document.getElementById('registration_end_female').value),
        
        // فترات الاختبار
        exam_period1_start: formatDateForSave(document.getElementById('exam_period1_start').value),
        exam_period1_end: formatDateForSave(document.getElementById('exam_period1_end').value),
        exam_period2_start: formatDateForSave(document.getElementById('exam_period2_start').value),
        exam_period2_end: formatDateForSave(document.getElementById('exam_period2_end').value),
    };

    return data;
}

// ==================== التحقق من صحة البيانات ====================

function validateDates(data) {
    const errors = [];

    // التحقق من السنة
    if (!data.exam_year || data.exam_year === '') {
        errors.push('السنة مطلوبة');
    } else {
        const year = parseInt(data.exam_year);
        if (isNaN(year) || year < 2024 || year > 2030) {
            errors.push('السنة يجب أن تكون بين 2024 و 2030');
        }
    }

    // التحقق من وجود جميع الحقول المطلوبة
    const requiredFields = [
        { key: 'registration_start_male', label: 'بداية تسجيل الطلاب' },
        { key: 'registration_end_male', label: 'نهاية تسجيل الطلاب' },
        { key: 'registration_start_female', label: 'بداية تسجيل الطالبات' },
        { key: 'registration_end_female', label: 'نهاية تسجيل الطالبات' },
        { key: 'exam_period1_start', label: 'بداية الفترة الأولى' },
        { key: 'exam_period1_end', label: 'نهاية الفترة الأولى' },
        { key: 'exam_period2_start', label: 'بداية الفترة الثانية' },
        { key: 'exam_period2_end', label: 'نهاية الفترة الثانية' },
    ];

    requiredFields.forEach(field => {
        if (!data[field.key]) {
            errors.push(`${field.label} مطلوب`);
        }
    });

    // التحقق المنطقي من التواريخ
    if (data.registration_start_male && data.registration_end_male) {
        if (new Date(data.registration_start_male) >= new Date(data.registration_end_male)) {
            errors.push('نهاية تسجيل الطلاب يجب أن تكون بعد البداية');
        }
    }

    if (data.registration_start_female && data.registration_end_female) {
        if (new Date(data.registration_start_female) >= new Date(data.registration_end_female)) {
            errors.push('نهاية تسجيل الطالبات يجب أن تكون بعد البداية');
        }
    }

    if (data.exam_period1_start && data.exam_period1_end) {
        if (new Date(data.exam_period1_start) >= new Date(data.exam_period1_end)) {
            errors.push('نهاية الفترة الأولى يجب أن تكون بعد البداية');
        }
    }

    if (data.exam_period2_start && data.exam_period2_end) {
        if (new Date(data.exam_period2_start) >= new Date(data.exam_period2_end)) {
            errors.push('نهاية الفترة الثانية يجب أن تكون بعد البداية');
        }
    }

    return errors;
}

// ==================== حفظ المواعيد ====================

async function saveDates() {
    try {
        // جمع البيانات
        const data = collectDatesData();

        // التحقق من صحة البيانات
        const errors = validateDates(data);
        if (errors.length > 0) {
            showError('خطأ في البيانات:\n' + errors.join('\n'));
            return;
        }

        showLoading();
        showInfo('جاري حفظ المواعيد...');

        const response = await fetch('/admin/exam-dates/api/dates', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showSuccess('تم حفظ المواعيد بنجاح! سيشاهدها الطلاب فوراً في التطبيق');
        } else {
            showError('فشل حفظ المواعيد: ' + (result.error || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('خطأ في حفظ المواعيد:', error);
        showError('حدث خطأ في الاتصال بالسيرفر');
    } finally {
        hideLoading();
    }
}

// ==================== إعادة تعيين للقيم الافتراضية ====================

async function resetToDefaults() {
    // تأكيد من المستخدم
    if (!confirm('هل أنت متأكد من إعادة تعيين جميع المواعيد إلى القيم الافتراضية؟\n\nالقيم الافتراضية (2026):\n- تسجيل الطلاب: 23 فبراير - 2 مارس 2026\n- تسجيل الطالبات: 23 فبراير - 2 مارس 2026\n- الفترة الأولى: 13-17 مايو 2026\n- الفترة الثانية: 5-9 يونيو 2026')) {
        return;
    }

    try {
        showLoading();
        showInfo('جاري إعادة التعيين...');

        const response = await fetch('/admin/exam-dates/api/dates/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (result.success) {
            // تعبئة الحقول بالقيم الافتراضية
            if (result.dates) {
                populateFields(result.dates);
            }
            showSuccess('تم إعادة تعيين المواعيد بنجاح إلى قيم 2026!');
        } else {
            showError('فشل إعادة التعيين: ' + (result.error || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('خطأ في إعادة التعيين:', error);
        showError('حدث خطأ في الاتصال بالسيرفر');
    } finally {
        hideLoading();
    }
}

// ==================== إضافة أحداث لتحسين تجربة المستخدم ====================

document.addEventListener('DOMContentLoaded', function() {
    // إضافة اختصارات لوحة المفاتيح
    document.addEventListener('keydown', function(e) {
        // Ctrl + S للحفظ
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            saveDates();
        }
        // Ctrl + R لإعادة التحميل
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            loadDates();
        }
    });

    // إضافة تلميحات عند التركيز على الحقول
    document.querySelectorAll('.date-input, .year-input').forEach(input => {
        input.addEventListener('focus', function() {
            showInfo('استخدم Ctrl+S للحفظ السريع');
        });
    });

    // تحديث عنوان الصفحة عند تغيير السنة
    document.getElementById('exam_year').addEventListener('change', function() {
        const year = this.value;
        if (year && year.trim() !== '') {
            document.querySelector('.dates-header h1').innerHTML = 
                `<i class="fas fa-calendar-alt"></i> إدارة مواعيد الاختبار التحصيلي ${year}`;
        } else {
            document.querySelector('.dates-header h1').innerHTML = 
                `<i class="fas fa-calendar-alt"></i> إدارة مواعيد الاختبار التحصيلي`;
        }
    });
});
