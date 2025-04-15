document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем Intersection Observer для ленивой загрузки миниатюр
    if ('IntersectionObserver' in window) {
        setupLazyLoadingObserver();
    } else {
        // Для браузеров без поддержки IntersectionObserver используем обычный scroll listener
        window.addEventListener('scroll', throttledLazyLoad);
    }
});

// Настройка IntersectionObserver для отслеживания видимости элементов
function setupLazyLoadingObserver() {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                const src = img.getAttribute('data-src');
                if (src) {
                    img.src = src;
                    img.removeAttribute('data-src');
                    observer.unobserve(img);
                }
            }
        });
    }, {
        rootMargin: '300px 0px', // Загружаем изображения, как только они приближаются к 300px от видимой области
        threshold: 0.01
    });
    
    // Находим все плейсхолдеры изображений и наблюдаем за ними
    document.querySelectorAll('.lazy-load-thumbnail').forEach(img => {
        imageObserver.observe(img);
    });
}

// Троттлинг функции загрузки для производительности
let throttleTimeout;
function throttledLazyLoad() {
    if (throttleTimeout) {
        clearTimeout(throttleTimeout);
    }
    
    throttleTimeout = setTimeout(() => {
        const scrollTop = window.pageYOffset;
        const windowHeight = window.innerHeight;
        
        document.querySelectorAll('.lazy-load-thumbnail').forEach(img => {
            const rect = img.getBoundingClientRect();
            
            // Если изображение приближается к видимой области
            if (rect.top <= windowHeight + 300) {
                const src = img.getAttribute('data-src');
                if (src) {
                    img.src = src;
                    img.removeAttribute('data-src');
                    img.classList.remove('lazy-load-thumbnail');
                }
            }
        });
    }, 200);
}

// Функция для загрузки URL миниатюры по запросу
function loadThumbnailUrl(cardElement, userId, videoId) {
    // Создаем идентификатор запроса
    const requestId = `${userId}__${videoId}`;
    
    // Проверяем, есть ли уже URL в кэше браузера
    const cachedUrl = sessionStorage.getItem(`thumbnail_${requestId}`);
    if (cachedUrl) {
        updateThumbnail(cardElement, cachedUrl);
        return;
    }
    
    // Создаем запрос к API
    fetch(`/api/get-thumbnail-url/${requestId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.url) {
                // Сохраняем URL в кэше браузера
                sessionStorage.setItem(`thumbnail_${requestId}`, data.url);
                
                // Обновляем изображение
                updateThumbnail(cardElement, data.url);
            }
        })
        .catch(error => {
            console.error('Error loading thumbnail:', error);
        });
}

// Обновление изображения миниатюры
function updateThumbnail(cardElement, url) {
    const img = cardElement.querySelector('img');
    if (img) {
        if (img.classList.contains('lazy-load-thumbnail')) {
            img.setAttribute('data-src', url);
        } else {
            img.src = url;
        }
    }
}

// Очистка кэша миниатюр при закрытии вкладки (опционально)
window.addEventListener('beforeunload', () => {
    // Очищаем кэш миниатюр из sessionStorage
    Object.keys(sessionStorage).forEach(key => {
        if (key.startsWith('thumbnail_')) {
            sessionStorage.removeItem(key);
        }
    });
});