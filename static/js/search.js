/**
 * Улучшенный скрипт для поиска в интерфейсе
 * Добавляет поддержку AJAX для выпадающих подсказок и асинхронного поиска
 */
document.addEventListener('DOMContentLoaded', function() {
    // Элементы поиска в шапке
    const searchInput = document.getElementById('search-input');
    const searchDropdown = document.getElementById('search-dropdown');
    const searchButton = document.querySelector('.search-button');
    
    if (searchInput && searchDropdown) {
        initializeHeaderSearch(searchInput, searchDropdown, searchButton);
    }
    
    // Элементы поиска на странице поиска (если она открыта)
    const bigSearchInput = document.getElementById('big-search-input');
    if (bigSearchInput) {
        // Фокус на поле поиска при загрузке страницы
        bigSearchInput.focus();
        
        // Обработка формы
        const searchForm = bigSearchInput.closest('form');
        if (searchForm) {
            searchForm.addEventListener('submit', function(e) {
                const query = bigSearchInput.value.trim();
                if (!query) {
                    e.preventDefault();
                }
            });
        }
    }
    
    // Инициализация фильтров на странице результатов поиска
    initializeSearchFilters();
    
    // Инициализация "Загрузить ещё" на странице результатов поиска
    initializeLoadMore();
});

/**
 * Инициализация поиска в шапке
 */
function initializeHeaderSearch(searchInput, searchDropdown, searchButton) {
    // Популярные запросы для подсказок
    const popularSearchTerms = [
        "Программирование Python",
        "Математический анализ",
        "Основы физики",
        "CORE",
        "История"
    ];
    
    // Debouncing для поиска при вводе
    let searchTimeout;
    
    // Обработчик ввода в поисковую строку
    searchInput.addEventListener('input', function() {
        if (searchTimeout) clearTimeout(searchTimeout);
        
        const query = this.value.trim();
        
        // Если запрос пустой, показываем популярные запросы
        if (!query) {
            showPopularSearchTerms(popularSearchTerms, searchDropdown);
            return;
        }
        
        // Добавляем задержку перед поиском
        searchTimeout = setTimeout(() => {
            // Получаем результаты поиска через API
            fetchSearchResults(query, 0, 5)
                .then(results => {
                    showSearchResults(results, searchDropdown, query);
                })
                .catch(error => {
                    console.error('Ошибка при поиске:', error);
                    showSearchError(searchDropdown, query);
                });
        }, 300);
    });
    
    // Показываем популярные запросы при фокусе
    searchInput.addEventListener('focus', function() {
        const query = this.value.trim();
        if (!query) {
            showPopularSearchTerms(popularSearchTerms, searchDropdown);
        } else {
            fetchSearchResults(query, 0, 5)
                .then(results => {
                    showSearchResults(results, searchDropdown, query);
                })
                .catch(error => {
                    console.error('Ошибка при поиске:', error);
                    showSearchError(searchDropdown, query);
                });
        }
    });
    
    // Закрываем выпадающее меню при клике вне его
    document.addEventListener('click', function(e) {
        if (searchInput && searchDropdown && 
            !searchInput.contains(e.target) && 
            !searchDropdown.contains(e.target)) {
            searchDropdown.classList.remove('show');
        }
    });
    
    // Обработчик клика на кнопку поиска
    if (searchButton) {
        searchButton.addEventListener('click', function() {
            if (searchInput.value.trim()) {
                window.location.href = `/search?query=${encodeURIComponent(searchInput.value)}`;
            }
        });
    }
    
    // Обработчик нажатия Enter
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && this.value.trim()) {
            window.location.href = `/search?query=${encodeURIComponent(this.value)}`;
        }
    });
}

/**
 * Получение результатов поиска
 */
function fetchSearchResults(query, offset = 0, limit = 5) {
    // Log the search attempt
    console.log(`Performing search for: "${query}", offset=${offset}, limit=${limit}`);
    
    // Make request to list_all_videos API without any filtering
    // We'll handle the filtering on client side to ensure results
    return fetch(`/api/list-all-videos/?offset=0&limit=100`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`API Error: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data.success || !data.videos) {
                console.warn("API returned no videos or success=false", data);
                return [];
            }
            
            // Log the raw count of videos from API
            console.log(`API returned ${data.videos.length} total videos`);
            
            // Convert query to lowercase for case-insensitive matching
            const queryLower = query.toLowerCase();
            
            // Filter videos by query with debugging
            const filteredVideos = data.videos.filter(video => {
                // Check for necessary properties with fallbacks
                const title = (video.title || '').toLowerCase();
                const description = (video.description || '').toLowerCase();
                const channel = (video.channel || video.display_name || video.user_id || '').toLowerCase();
                
                // Check if any matches
                const titleMatches = title.includes(queryLower);
                const descriptionMatches = description.includes(queryLower);
                const channelMatches = channel.includes(queryLower);
                
                // Debug individual video
                if (titleMatches || descriptionMatches || channelMatches) {
                    console.log(`Match found - Title: "${video.title}", matches: [title=${titleMatches}, desc=${descriptionMatches}, channel=${channelMatches}]`);
                }
                
                // Return true if any field matches the query
                return titleMatches || descriptionMatches || channelMatches;
            });
            
            console.log(`Found ${filteredVideos.length} videos matching "${query}"`);
            
            // If no videos found, log a warning with more details
            if (filteredVideos.length === 0) {
                console.warn(`No matches found for "${query}". Sample of available videos:`, 
                    data.videos.slice(0, 3).map(v => ({
                        title: v.title,
                        user_id: v.user_id,
                        video_id: v.video_id
                    }))
                );
            }
            
            // Sort by relevance
            filteredVideos.sort((a, b) => {
                const aTitle = (a.title || '').toLowerCase();
                const bTitle = (b.title || '').toLowerCase();
                
                // Exact title match goes first
                if (aTitle === queryLower && bTitle !== queryLower) return -1;
                if (bTitle === queryLower && aTitle !== queryLower) return 1;
                
                // Title starts with query goes second
                if (aTitle.startsWith(queryLower) && !bTitle.startsWith(queryLower)) return -1;
                if (bTitle.startsWith(queryLower) && !aTitle.startsWith(queryLower)) return 1;
                
                // Default sort by upload date (newer first)
                return new Date(b.upload_date || 0) - new Date(a.upload_date || 0);
            });
            
            // Apply pagination
            return filteredVideos.slice(offset, offset + limit);
        })
        .catch(error => {
            console.error('Search API error:', error);
            // Provide better error handling - return empty array but log error
            return [];
        });
}

/**
 * Показать популярные поисковые запросы
 */
function showPopularSearchTerms(terms, searchDropdown) {
    if (!searchDropdown) return;
    
    searchDropdown.innerHTML = '';
    
    // Создаем заголовок для популярных запросов
    const header = document.createElement('div');
    header.className = 'search-header';
    header.textContent = 'Популярные запросы';
    searchDropdown.appendChild(header);
    
    // Добавляем каждый запрос
    terms.forEach(term => {
        const termItem = document.createElement('div');
        termItem.className = 'search-term';
        termItem.innerHTML = `
            <div class="search-term-icon">🔍</div>
            <div class="search-term-text">${term}</div>
        `;
        
        termItem.addEventListener('click', function() {
            // Устанавливаем запрос в поле поиска и перенаправляем на поиск
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.value = term;
                window.location.href = `/search?query=${encodeURIComponent(term)}`;
            }
        });
        
        searchDropdown.appendChild(termItem);
    });
    
    searchDropdown.classList.add('show');
}

/**
 * Показать результаты поиска
 */
function showSearchResults(results, searchDropdown, query) {
    if (!searchDropdown) return;
    
    searchDropdown.innerHTML = '';
    
    if (results.length === 0) {
        showSearchError(searchDropdown, query);
        return;
    }
    
    // Сначала добавляем пункт "Искать <запрос>"
    const searchItem = document.createElement('div');
    searchItem.className = 'search-term';
    searchItem.innerHTML = `
        <div class="search-term-icon">🔍</div>
        <div class="search-term-text">Искать <strong>${query}</strong></div>
    `;
    
    searchItem.addEventListener('click', function() {
        window.location.href = `/search?query=${encodeURIComponent(query)}`;
    });
    
    searchDropdown.appendChild(searchItem);
    
    // Затем добавляем заголовок для результатов
    const resultsHeader = document.createElement('div');
    resultsHeader.className = 'search-header';
    resultsHeader.textContent = 'Видео';
    searchDropdown.appendChild(resultsHeader);
    
    // Добавляем результаты
    results.forEach(video => {
        // Определяем путь к превью с запасным вариантом
        const previewPath = video.thumbnail_url ? 
            video.thumbnail_url : 
            `/static/placeholder.jpg`;
        
        // Определяем имя канала для отображения
        const channelName = video.display_name || video.channel || video.user_id || '';
            
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result';
        resultItem.innerHTML = `
            <div class="search-thumbnail">
                <img src="${previewPath}" loading="lazy" onerror="this.src='/static/placeholder.jpg'" alt="${video.title}">
            </div>
            <div class="search-info">
                <div class="search-title">${video.title}</div>
                <div class="search-channel">${channelName}</div>
            </div>
        `;
        
        resultItem.addEventListener('click', function() {
            window.location.href = `/video/${video.user_id}__${video.video_id}/`;
        });
        
        searchDropdown.appendChild(resultItem);
    });
    
    // Если есть еще результаты, добавляем ссылку "Показать все"
    if (results.length >= 5) {
        const showMore = document.createElement('div');
        showMore.className = 'search-more';
        showMore.textContent = 'Показать все результаты';
        
        showMore.addEventListener('click', function() {
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                window.location.href = `/search?query=${encodeURIComponent(searchInput.value)}`;
            }
        });
        
        searchDropdown.appendChild(showMore);
    }
    
    searchDropdown.classList.add('show');
}

/**
 * Показать сообщение об ошибке поиска
 */
function showSearchError(searchDropdown, query) {
    if (!searchDropdown) return;
    
    searchDropdown.innerHTML = '';
    
    // Сообщение "Ничего не найдено"
    const noResults = document.createElement('div');
    noResults.className = 'search-no-results';
    noResults.textContent = `Нет результатов для "${query}"`;
    searchDropdown.appendChild(noResults);
    
    // Пункт "Искать <запрос>"
    const searchAllItem = document.createElement('div');
    searchAllItem.className = 'search-all-item';
    searchAllItem.innerHTML = `
        <div class="search-all-icon">🔍</div>
        <div class="search-all-text">Искать <strong>${query}</strong></div>
    `;
    
    searchAllItem.addEventListener('click', function() {
        window.location.href = `/search?query=${encodeURIComponent(query)}`;
    });
    
    searchDropdown.appendChild(searchAllItem);
    searchDropdown.classList.add('show');
}

/**
 * Инициализация фильтров на странице результатов поиска
 */
function initializeSearchFilters() {
    const filterItems = document.querySelectorAll('.filter-item');
    const resultItems = document.querySelectorAll('.search-result-item');
    
    if (!filterItems.length || !resultItems.length) return;
    
    filterItems.forEach(item => {
        item.addEventListener('click', function() {
            // Снимаем активный класс со всех фильтров
            filterItems.forEach(filter => filter.classList.remove('active'));
            
            // Добавляем активный класс выбранному фильтру
            this.classList.add('active');
            
            // Получаем тип фильтра
            const filterType = this.getAttribute('data-filter');
            
            // Показываем/скрываем результаты в зависимости от фильтра
            resultItems.forEach(result => {
                if (filterType === 'all' || result.getAttribute('data-type') === filterType) {
                    result.style.display = 'flex';
                } else {
                    result.style.display = 'none';
                }
            });
        });
    });
}

/**
 * Инициализация кнопки "Загрузить ещё" на странице результатов поиска
 */
function initializeLoadMore() {
    const loadMoreBtn = document.getElementById('load-more-btn');
    
    if (!loadMoreBtn) return;
    
    // Получаем параметры из URL
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('query');
    
    // Определяем начальное смещение для следующей порции
    let currentOffset = parseInt(document.querySelectorAll('.search-result-item').length);
    
    loadMoreBtn.addEventListener('click', function() {
        this.textContent = 'Загрузка...';
        this.disabled = true;
        
        // Запрашиваем следующую порцию результатов
        fetch(`/search?query=${encodeURIComponent(query)}&offset=${currentOffset}&format=json`)
            .then(response => response.json())
            .then(data => {
                if (data.videos && data.videos.length > 0) {
                    // Добавляем новые результаты
                    appendSearchResults(data.videos);
                    
                    // Обновляем смещение
                    currentOffset += data.videos.length;
                    
                    // Активируем кнопку, если есть еще результаты
                    if (data.videos.length < 20 || currentOffset >= data.total) {
                        loadMoreBtn.style.display = 'none';
                    } else {
                        loadMoreBtn.textContent = 'Загрузить ещё';
                        loadMoreBtn.disabled = false;
                    }
                } else {
                    loadMoreBtn.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки результатов:', error);
                loadMoreBtn.textContent = 'Ошибка загрузки';
                setTimeout(() => {
                    loadMoreBtn.textContent = 'Попробовать снова';
                    loadMoreBtn.disabled = false;
                }, 2000);
            });
    });
}

/**
 * Добавляет результаты поиска на страницу
 */
function appendSearchResults(videos) {
    const container = document.getElementById('search-results-container');
    if (!container) return;
    
    videos.forEach(video => {
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result-item';
        resultItem.setAttribute('data-type', 'videos');
        resultItem.onclick = function() {
            window.location.href = `/video/${video.user_id}__${video.video_id}/`;
        };
        
        const thumbnailUrl = video.thumbnail_url || '/static/placeholder.jpg';
        const displayName = video.display_name || video.channel || 'Unknown';
        const firstLetter = displayName.charAt(0);
        
        resultItem.innerHTML = `
            <div class="result-thumbnail">
                <img src="${thumbnailUrl}" alt="${video.title}" loading="lazy" onerror="this.src='/static/placeholder.jpg'" ${!video.thumbnail_url ? `data-user-id="${video.user_id}" data-video-id="${video.video_id}" class="lazy-thumbnail"` : ''}>
                <div class="result-duration">${video.duration || '00:00'}</div>
            </div>
            <div class="result-details">
                <h3 class="result-title">${video.title}</h3>
                <div class="result-meta">${video.views_formatted || '0 просмотров'} • ${video.upload_date_formatted || 'Недавно'}</div>
                <div class="result-channel">
                    <div class="channel-avatar">${firstLetter}</div>
                    <div class="channel-name">${displayName}</div>
                </div>
                <div class="result-description">
                    ${video.description ? (video.description.length > 150 ? video.description.substring(0, 147) + '...' : video.description) : ''}
                </div>
            </div>
        `;
        
        container.appendChild(resultItem);
    });
    
    // Инициализируем отложенную загрузку миниатюр
    initializeLazyLoading();
}

/**
 * Инициализация отложенной загрузки миниатюр
 */
function initializeLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    const videoId = img.getAttribute('data-video-id');
                    const userId = img.getAttribute('data-user-id');
                    
                    if (videoId && userId) {
                        // Проверяем, есть ли URL в sessionStorage
                        const cachedUrl = sessionStorage.getItem(`thumbnail_${userId}__${videoId}`);
                        
                        if (cachedUrl) {
                            img.src = cachedUrl;
                            img.classList.remove('lazy-thumbnail', 'loading');
                            imageObserver.unobserve(img);
                        } else {
                            // Отмечаем как загружаемый
                            img.classList.add('loading');
                            
                            // Запрашиваем URL миниатюры
                            fetch(`/api/get-thumbnail-url/${userId}__${videoId}/`)
                                .then(response => response.json())
                                .then(data => {
                                    if (data.success && data.url) {
                                        // Кэшируем URL
                                        sessionStorage.setItem(`thumbnail_${userId}__${videoId}`, data.url);
                                        
                                        // Устанавливаем источник изображения
                                        img.src = data.url;
                                        img.classList.remove('lazy-thumbnail', 'loading');
                                        
                                        // Прекращаем наблюдение
                                        imageObserver.unobserve(img);
                                    }
                                })
                                .catch(error => {
                                    console.error('Ошибка загрузки миниатюры:', error);
                                    img.classList.remove('loading');
                                });
                        }
                    }
                }
            });
        }, {
            rootMargin: '200px 0px',
            threshold: 0.01
        });
        
        // Наблюдаем за всеми ленивыми миниатюрами
        document.querySelectorAll('.lazy-thumbnail').forEach(img => {
            imageObserver.observe(img);
        });
    }
}