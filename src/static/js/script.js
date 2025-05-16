// script.js
document.addEventListener('DOMContentLoaded', function() {
    // تحريك الذرة والإلكترونات
    const nucleus = document.querySelector('.nucleus');
    const electrons = document.querySelectorAll('.electron');
    
    // إضافة تأثير نبض للنواة
    setInterval(() => {
        nucleus.style.boxShadow = '0 0 15px var(--primary-color)';
        setTimeout(() => {
            nucleus.style.boxShadow = '0 0 10px var(--primary-color)';
        }, 500);
    }, 1000);
    
    // تفاعل القوائم
    const navItems = document.querySelectorAll('nav ul li a');
    navItems.forEach(item => {
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px)';
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // تفاعل بطاقات الإحصائيات
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-8px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(-5px)';
        });
    });
});
