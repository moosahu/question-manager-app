// إصلاح شامل لتنسيق البطاقات - 3 بطاقات في كل صف
console.log('🚀 بدء تحميل إصلاح تنسيق البطاقات الشامل');

(function() {
    'use strict';

    // ========== الدالة الرئيسية لإصلاح التنسيق ==========
    function fixCardsLayout() {
        console.log('🔧 تطبيق إصلاح تنسيق البطاقات...');

        // البحث عن جميع حاويات البطاقات المحتملة
        const selectors = [
            '#cardView .enhanced-cards-container',
            '.enhanced-cards-container',
            '.cards-container',
            '#cardView .row',
            '.question-cards-container'
        ];

        let containerFound = false;

        selectors.forEach(selector => {
            const containers = document.querySelectorAll(selector);
            containers.forEach(container => {
                if (container && container.children.length > 0) {
                    containerFound = true;
                    applyGridLayout(container);
                }
            });
        });

        if (!containerFound) {
            console.warn('❗ لم يتم العثور على حاوية البطاقات');
        }
    }

    // ========== تطبيق تنسيق الشبكة ==========
    function applyGridLayout(container) {
        console.log('📐 تطبيق تنسيق الشبكة على:', container);

        // إزالة أي فئات Bootstrap قد تتداخل
        container.classList.remove('d-flex', 'flex-wrap', 'row');
        
        // تطبيق تنسيق الشبكة
        container.style.display = 'grid';
        container.style.gridTemplateColumns = 'repeat(3, 1fr)';
        container.style.gap = '1.5rem';
        container.style.padding = '20px';
        container.style.width = '100%';
        container.style.maxWidth = '1400px';
        container.style.margin = '0 auto';
        container.style.boxSizing = 'border-box';

        // إصلاح البطاقات الفردية
        const cardWrappers = container.children;
        Array.from(cardWrappers).forEach((wrapper, index) => {
            // إزالة فئات Bootstrap
            wrapper.classList.remove('col', 'col-md-6', 'col-lg-4', 'col-xl-3');
            
            // تطبيق الأنماط
            wrapper.style.width = '100%';
            wrapper.style.maxWidth = 'none';
            wrapper.style.minWidth = '0';
            wrapper.style.margin = '0';
            wrapper.style.padding = '0';
            wrapper.style.flex = 'none';
            wrapper.style.boxSizing = 'border-box';

            // إصلاح البطاقة نفسها
            const card = wrapper.querySelector('.enhanced-card, .question-card, .card');
            if (card) {
                card.style.width = '100%';
                card.style.height = 'auto';
                card.style.minHeight = '300px';
                card.style.maxWidth = 'none';
                card.style.margin = '0';
                card.style.boxSizing = 'border-box';
            }
        });

        // تطبيق Media Queries
        applyResponsiveLayout(container);
    }

    // ========== تطبيق التنسيق المتجاوب ==========
    function applyResponsiveLayout(container) {
        const width = window.innerWidth;
        
        if (width <= 767) {
            // شاشات صغيرة - بطاقة واحدة
            container.style.gridTemplateColumns = '1fr';
            container.style.gap = '1rem';
            container.style.padding = '15px';
        } else if (width <= 1199) {
            // شاشات متوسطة - بطاقتان
            container.style.gridTemplateColumns = 'repeat(2, 1fr)';
            container.style.gap = '1.2rem';
        } else {
            // شاشات كبيرة - 3 بطاقات
            container.style.gridTemplateColumns = 'repeat(3, 1fr)';
            container.style.gap = '1.5rem';
        }
    }

    // ========== مراقبة الأحداث ==========
    function setupEventListeners() {
        console.log('🎯 إعداد مراقبة الأحداث...');

        // عند النقر على زر عرض البطاقات
        const cardViewBtn = document.getElementById('cardViewBtn');
        if (cardViewBtn) {
            cardViewBtn.addEventListener('click', function() {
                setTimeout(fixCardsLayout, 100);
                setTimeout(fixCardsLayout, 300);
                setTimeout(fixCardsLayout, 500);
            });
        }

        // عند تغيير حجم النافذة
        let resizeTimeout;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(fixCardsLayout, 200);
        });

        // عند إرسال نموذج التصفية
        const filterForm = document.querySelector('form');
        if (filterForm) {
            filterForm.addEventListener('submit', function() {
                setTimeout(fixCardsLayout, 300);
                setTimeout(fixCardsLayout, 600);
                setTimeout(fixCardsLayout, 1000);
            });
        }

        // عند تغيير قوائم التصفية
        const selects = document.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', function() {
                setTimeout(fixCardsLayout, 300);
            });
        });

        // عند النقر على زر تطبيق التصفية
        const applyFilterBtn = document.querySelector('button[type="submit"]');
        if (applyFilterBtn) {
            applyFilterBtn.addEventListener('click', function() {
                setTimeout(fixCardsLayout, 300);
                setTimeout(fixCardsLayout, 600);
                setTimeout(fixCardsLayout, 1000);
            });
        }
    }

    // ========== مراقبة تغييرات DOM ==========
    function setupMutationObserver() {
        const observer = new MutationObserver(function(mutations) {
            let shouldFix = false;
            
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    // تحقق من إضافة عقد جديدة
                    if (mutation.addedNodes.length > 0) {
                        for (let node of mutation.addedNodes) {
                            if (node.nodeType === 1) { // عقدة عنصر
                                if (node.classList && (
                                    node.classList.contains('enhanced-card-wrapper') ||
                                    node.classList.contains('enhanced-cards-container') ||
                                    node.querySelector('.enhanced-card-wrapper')
                                )) {
                                    shouldFix = true;
                                    break;
                                }
                            }
                        }
                    }
                }
            });

            if (shouldFix) {
                setTimeout(fixCardsLayout, 200);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        console.log('👁️ تم إعداد مراقب تغييرات DOM');
    }

    // ========== التحميل التلقائي ==========
    function initialize() {
        console.log('🏁 تهيئة إصلاح تنسيق البطاقات...');
        
        setupEventListeners();
        setupMutationObserver();
        
        // تطبيق الإصلاح فوراً
        fixCardsLayout();
        
        // تطبيق الإصلاح بعد فترات مختلفة للتأكد
        setTimeout(fixCardsLayout, 100);
        setTimeout(fixCardsLayout, 500);
        setTimeout(fixCardsLayout, 1000);
        setTimeout(fixCardsLayout, 2000);
    }

    // ========== إتاحة الدالة عالمياً ==========
    window.fixCardsLayout = fixCardsLayout;
    window.applyGridLayout = applyGridLayout;

    // ========== بدء التشغيل ==========
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // تطبيق إضافي عند تحميل النافذة
    window.addEventListener('load', function() {
        setTimeout(fixCardsLayout, 500);
    });

    console.log('✅ تم تحميل إصلاح تنسيق البطاقات بنجاح');

})();

// ========== إصلاح إضافي للتصفية ==========
document.addEventListener('DOMContentLoaded', function() {
    // مراقبة تغييرات URL (للتصفية)
    let currentURL = window.location.href;
    setInterval(function() {
        if (window.location.href !== currentURL) {
            currentURL = window.location.href;
            setTimeout(function() {
                if (typeof window.fixCardsLayout === 'function') {
                    window.fixCardsLayout();
                }
            }, 500);
        }
    }, 1000);
});


// ========== تحسينات التصفية الديناميكية ==========
// تم إضافة هذا القسم لتحسين دعم التصفية الديناميكية

(function() {
    'use strict';

    // ========== مراقبة أحداث التصفية ==========
    function setupAdvancedFilterSupport() {
        console.log('🔍 إعداد دعم التصفية المتقدم...');
        
        const selectors = ['#course_id', '#unit_id', '#lesson_id'];
        
        selectors.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                element.addEventListener('change', function() {
                    console.log(`🔄 تغيير في ${selector}, إعادة تطبيق التخطيط...`);
                    
                    // إضافة مؤشر التحميل
                    addLoadingIndicator(element);
                    
                    // تطبيق الإصلاح مع تأخير
                    setTimeout(() => {
                        fixCardsLayout();
                        removeLoadingIndicator(element);
                    }, 300);
                });
            }
        });
        
        // مراقبة إرسال النموذج
        const filterForm = document.querySelector('#filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', function() {
                console.log('📤 إرسال نموذج التصفية...');
                
                // إضافة تأثير التصفية
                addFilteringEffect();
                
                // تطبيق الإصلاح بعد التحديث
                setTimeout(fixCardsLayout, 500);
                setTimeout(fixCardsLayout, 1000);
                setTimeout(() => {
                    removeFilteringEffect();
                    fixCardsLayout();
                }, 1500);
            });
        }
    }
    
    // ========== إضافة مؤشر التحميل ==========
    function addLoadingIndicator(element) {
        element.classList.add('filter-loading');
    }
    
    function removeLoadingIndicator(element) {
        element.classList.remove('filter-loading');
    }
    
    // ========== إضافة تأثير التصفية ==========
    function addFilteringEffect() {
        const containers = document.querySelectorAll('.enhanced-cards-container, .table-responsive');
        containers.forEach(container => {
            container.classList.add('filtering');
        });
    }
    
    function removeFilteringEffect() {
        const containers = document.querySelectorAll('.enhanced-cards-container, .table-responsive');
        containers.forEach(container => {
            container.classList.remove('filtering');
        });
    }
    
    // ========== تحسين دالة إصلاح التخطيط ==========
    const originalFixCardsLayout = window.fixCardsLayout;
    
    window.fixCardsLayout = function() {
        console.log('🔧 تطبيق إصلاح التخطيط المحسن...');
        
        // تطبيق الإصلاح الأصلي
        if (typeof originalFixCardsLayout === 'function') {
            originalFixCardsLayout();
        }
        
        // تحسينات إضافية للتصفية
        const cardsContainer = document.querySelector('#cardView .enhanced-cards-container');
        if (cardsContainer) {
            // التأكد من الرؤية
            cardsContainer.style.opacity = '1';
            cardsContainer.style.visibility = 'visible';
            
            // إعادة تطبيق التخطيط
            applyGridLayout(cardsContainer);
            
            // تحسين الانتقالات
            const cardWrappers = cardsContainer.querySelectorAll('.enhanced-card-wrapper');
            cardWrappers.forEach((wrapper, index) => {
                wrapper.style.transition = 'all 0.3s ease';
                wrapper.style.animationDelay = `${index * 0.1}s`;
            });
        }
    };
    
    // ========== مراقبة تغييرات URL للتصفية ==========
    function setupURLMonitoring() {
        let currentURL = window.location.href;
        
        setInterval(() => {
            if (window.location.href !== currentURL) {
                currentURL = window.location.href;
                console.log('🔗 تغيير في URL، إعادة تطبيق التخطيط...');
                
                setTimeout(() => {
                    if (typeof window.fixCardsLayout === 'function') {
                        window.fixCardsLayout();
                    }
                }, 500);
            }
        }, 1000);
    }
    
    // ========== تهيئة التحسينات ==========
    function initializeEnhancements() {
        setupAdvancedFilterSupport();
        setupURLMonitoring();
        
        // تطبيق إصلاح فوري
        setTimeout(() => {
            if (typeof window.fixCardsLayout === 'function') {
                window.fixCardsLayout();
            }
        }, 100);
    }
    
    // ========== بدء التشغيل ==========
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeEnhancements);
    } else {
        initializeEnhancements();
    }
    
    window.addEventListener('load', () => {
        setTimeout(initializeEnhancements, 500);
    });
    
    console.log('✅ تم تحميل تحسينات التصفية الديناميكية بنجاح');
})();

