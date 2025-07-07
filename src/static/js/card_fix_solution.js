
// نسخة محسّنة من fixCardsLayout.js - تم تنقيحها وتحسين الأداء
console.log('✅ بدء تحميل نسخة مُحسّنة من card_fix_solution.js');

(function() {
    // ========== دالة الإصلاح الأساسية ==========
    function fixCardsLayout() {
        console.log('🔧 تنفيذ fixCardsLayout...');

        const cardsContainer = document.querySelector('#cardView .enhanced-cards-container');
        if (!cardsContainer) {
            console.warn('❗ لم يتم العثور على الحاوية');
            return;
        }

        // إعداد الشبكة الرئيسية
        cardsContainer.style.display = 'grid';
        cardsContainer.style.gridTemplateColumns = 'repeat(auto-fit, minmax(350px, 1fr))';
        cardsContainer.style.gap = '1.5rem';
        cardsContainer.style.justifyContent = 'center';
        cardsContainer.style.alignContent = 'start';

        const cardWrappers = cardsContainer.querySelectorAll('.enhanced-card-wrapper');
        cardWrappers.forEach((wrapper, index) => {
            wrapper.style.width = '100%';
            wrapper.style.maxWidth = '400px';
            wrapper.style.minWidth = '350px';
            wrapper.style.margin = '0';
            wrapper.style.padding = '0';

            const card = wrapper.querySelector('.enhanced-card');
            if (card) {
                card.style.width = '100%';
                card.style.maxWidth = '400px';
                card.style.minWidth = '350px';
                card.style.height = 'auto';
            }
        });

        // دعم الشاشات الصغيرة
        if (window.innerWidth <= 767) {
            cardsContainer.style.gridTemplateColumns = '1fr';
            cardsContainer.style.justifyContent = 'center';
            cardWrappers.forEach(wrapper => {
                wrapper.style.maxWidth = '100%';
                wrapper.style.minWidth = 'auto';
                const card = wrapper.querySelector('.enhanced-card');
                if (card) {
                    card.style.maxWidth = '100%';
                    card.style.minWidth = 'auto';
                }
            });
        }
    }

    // ========== تشغيل الإصلاح عند الأحداث ==========
    function initFixEvents() {
        console.log('🛠️ تهيئة مراقبة الأحداث لإصلاح البطاقات');

        const btn = document.getElementById('cardViewBtn');
        if (btn) {
            btn.addEventListener('click', () => setTimeout(fixCardsLayout, 300));
        }

        window.addEventListener('resize', () => setTimeout(fixCardsLayout, 200));

        const filterForm = document.querySelector('form');
        if (filterForm) {
            filterForm.addEventListener('submit', () => setTimeout(fixCardsLayout, 300));
        }

        setTimeout(fixCardsLayout, 100);
        setTimeout(fixCardsLayout, 500);
        setTimeout(fixCardsLayout, 1000);
    }

    // ========== مراقبة تغييرات DOM ==========
    const observer = new MutationObserver(() => {
        setTimeout(fixCardsLayout, 200);
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // ========== تحميل تلقائي ==========
    document.addEventListener('DOMContentLoaded', initFixEvents);
    window.addEventListener('load', () => setTimeout(fixCardsLayout, 1000));

    // ========== نسخة يدوية ==========
    window.fixCardsLayoutManually = fixCardsLayout;

    console.log('✅ تم تحميل النسخة المحسنة بنجاح');
})();


// ========== دعم التصفية الديناميكية ==========
// تم إضافة هذا القسم لدعم التصفية الديناميكية مع إصلاح البطاقات

(function() {
    // مراقبة تغييرات التصفية
    function setupFilterSupport() {
        console.log('🔍 إعداد دعم التصفية الديناميكية...');
        
        const courseSelect = document.getElementById('course_id');
        const unitSelect = document.getElementById('unit_id');
        const lessonSelect = document.getElementById('lesson_id');
        const filterForm = document.getElementById('filter-form');
        
        if (courseSelect) {
            courseSelect.addEventListener('change', function() {
                console.log('📚 تم تغيير المنهج، إعادة تطبيق إصلاح البطاقات...');
                setTimeout(fixCardsLayout, 200);
            });
        }
        
        if (unitSelect) {
            unitSelect.addEventListener('change', function() {
                console.log('📖 تم تغيير الوحدة، إعادة تطبيق إصلاح البطاقات...');
                setTimeout(fixCardsLayout, 200);
            });
        }
        
        if (lessonSelect) {
            lessonSelect.addEventListener('change', function() {
                console.log('📝 تم تغيير الدرس، إعادة تطبيق إصلاح البطاقات...');
                setTimeout(fixCardsLayout, 200);
            });
        }
        
        if (filterForm) {
            filterForm.addEventListener('submit', function() {
                console.log('🔄 تم إرسال نموذج التصفية، إعادة تطبيق إصلاح البطاقات...');
                setTimeout(fixCardsLayout, 500);
                setTimeout(fixCardsLayout, 1000);
                setTimeout(fixCardsLayout, 1500);
            });
        }
    }
    
    // تحسين إصلاح البطاقات للعمل مع التصفية
    function enhancedFixCardsLayout() {
        console.log('🔧 تطبيق إصلاح البطاقات المحسن مع دعم التصفية...');
        
        // تطبيق الإصلاح الأساسي
        fixCardsLayout();
        
        // إضافة تحسينات خاصة بالتصفية
        const cardsContainer = document.querySelector('#cardView .enhanced-cards-container');
        if (cardsContainer) {
            // إزالة فئة التصفية إذا كانت موجودة
            cardsContainer.classList.remove('filtering');
            
            // التأكد من أن البطاقات مرئية
            const cardWrappers = cardsContainer.querySelectorAll('.enhanced-card-wrapper');
            cardWrappers.forEach(wrapper => {
                wrapper.style.opacity = '1';
                wrapper.style.transform = 'none';
            });
        }
    }
    
    // استبدال الدالة الأصلية بالنسخة المحسنة
    window.fixCardsLayoutManually = enhancedFixCardsLayout;
    
    // إعداد مراقبة التصفية عند التحميل
    document.addEventListener('DOMContentLoaded', setupFilterSupport);
    
    // إعداد مراقبة إضافية للتصفية
    window.addEventListener('load', function() {
        setTimeout(setupFilterSupport, 500);
    });
    
    console.log('✅ تم تحميل دعم التصفية الديناميكية بنجاح');
})();

