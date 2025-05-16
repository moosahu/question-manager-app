// تحديث ملف script.js لدعم تحديث النشاط الأخير والأسئلة الأخيرة

// عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // تهيئة الجسيمات المتحركة
    initParticles();
    
    // تحديث النشاط الأخير والأسئلة الأخيرة إذا كنا في الصفحة الرئيسية
    if (document.getElementById('activity-list')) {
        // جلب الأنشطة الأخيرة
        fetchRecentActivities();
        
        // جلب الأسئلة الأخيرة
        fetchRecentQuestions();
        
        // تحديث الأنشطة كل دقيقة
        setInterval(fetchRecentActivities, 60000);
        
        // تحديث الأسئلة كل 5 دقائق
        setInterval(fetchRecentQuestions, 300000);
    }
    
    // تهيئة الأكورديون إذا وجد
    initAccordion();
});

// تهيئة الجسيمات المتحركة
function initParticles() {
    const particles = document.querySelectorAll('.particle');
    particles.forEach(particle => {
        // تعيين موقع عشوائي
        const x = Math.random() * 100;
        const y = Math.random() * 100;
        particle.style.left = `${x}%`;
        particle.style.top = `${y}%`;
        
        // تعيين حجم عشوائي
        const size = Math.random() * 20 + 5;
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        
        // تعيين تأخير عشوائي للحركة
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
        .then(response => {
            if (!response.ok) {
                throw new Error('فشل في جلب الأنشطة الأخيرة');
            }
            return response.json();
        })
        .then(data => {
            // إذا لم تكن هناك أنشطة
            if (!data.activities || data.activities.length === 0) {
                activityList.innerHTML = '<div class="no-data">لا توجد أنشطة حديثة</div>';
                return;
            }
            
            // إنشاء HTML للأنشطة
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
            console.error('خطأ في جلب الأنشطة:', error);
            activityList.innerHTML = 
                '<div class="error-message">حدث خطأ أثناء تحميل الأنشطة. يرجى تحديث الصفحة.</div>';
        });
}

// دالة لجلب الأسئلة الأخيرة
function fetchRecentQuestions() {
    const questionsTable = document.getElementById('recent-questions-table');
    if (!questionsTable) return;
    
    fetch('/api/v1/questions/recent?limit=4')
        .then(response => {
            if (!response.ok) {
                throw new Error('فشل في جلب الأسئلة الأخيرة');
            }
            return response.json();
        })
        .then(data => {
            // إذا لم تكن هناك أسئلة
            if (!data.questions || data.questions.length === 0) {
                questionsTable.innerHTML = '<div class="no-data">لا توجد أسئلة حديثة</div>';
                return;
            }
            
            // إنشاء جدول الأسئلة
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
            
            tableHTML += `
                    </tbody>
                </table>
            `;
            
            questionsTable.innerHTML = tableHTML;
        })
        .catch(error => {
            console.error('خطأ في جلب الأسئلة:', error);
            questionsTable.innerHTML = 
                '<div class="error-message">حدث خطأ أثناء تحميل الأسئلة. يرجى تحديث الصفحة.</div>';
        });
}

// دالة لتأكيد حذف سؤال
function confirmDelete(questionId, event) {
    event.preventDefault();
    if (confirm('هل أنت متأكد من حذف هذا السؤال؟')) {
        window.location.href = `/questions/delete/${questionId}`;
    }
}
