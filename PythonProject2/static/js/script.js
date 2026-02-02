// Простые JavaScript функции для улучшения UX
document.addEventListener('DOMContentLoaded', function() {
    // Автоматическое скрытие alert через 5 секунд
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Подтверждение выхода
    const logoutLinks = document.querySelectorAll('a[href*="logout"]');
    logoutLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите выйти?')) {
                e.preventDefault();
            }
        });
    });

    // Плавная прокрутка для якорей
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    const calendar = document.querySelector('.calendar');
    if (calendar) {
        const months = Array.from(calendar.querySelectorAll('.calendar-month'));
        const label = document.querySelector('.calendar-nav-label');
        const prevButton = document.querySelector('.calendar-nav-prev');
        const nextButton = document.querySelector('.calendar-nav-next');
        let activeIndex = 0;

        const updateCalendar = () => {
            months.forEach((month, index) => {
                month.classList.toggle('is-active', index === activeIndex);
            });
            if (label && months[activeIndex]) {
                label.textContent = months[activeIndex].dataset.monthLabel || '';
            }
            if (prevButton) {
                prevButton.disabled = activeIndex === 0;
            }
            if (nextButton) {
                nextButton.disabled = activeIndex === months.length - 1;
            }
        };

        if (months.length > 0) {
            updateCalendar();
            if (prevButton) {
                prevButton.addEventListener('click', () => {
                    if (activeIndex > 0) {
                        activeIndex -= 1;
                        updateCalendar();
                    }
                });
            }
            if (nextButton) {
                nextButton.addEventListener('click', () => {
                    if (activeIndex < months.length - 1) {
                        activeIndex += 1;
                        updateCalendar();
                    }
                });
            }
        }
    }
});
