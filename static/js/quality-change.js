/**
 * Quality Selection Functions
 */

// Function to fetch video URL for specific quality
function fetchVideoQuality(userId, videoId, quality) {
    return fetch(`/api/get-video-url/${videoId}/?user_id=${encodeURIComponent(userId)}&quality=${quality}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        });
}

// Function to show quality change overlay
function showQualityChangeOverlay() {
    const overlay = document.getElementById('quality-change-overlay');
    if (overlay) {
        overlay.classList.add('visible');
    }
}

// Function to hide quality change overlay
function hideQualityChangeOverlay() {
    const overlay = document.getElementById('quality-change-overlay');
    if (overlay) {
        overlay.classList.remove('visible');
    }
}

// Function to change video quality
function changeVideoQuality(quality) {
    const videoPlayer = document.getElementById('video-player');
    const videoContainer = document.querySelector('.video-container');
    
    if (!videoPlayer || !videoContainer) return;
    
    // Get video ID and user ID
    const videoId = videoContainer.getAttribute('data-video-id');
    const userId = videoContainer.getAttribute('data-user-id');
    
    if (!videoId || !userId) {
        console.error('Missing video ID or user ID');
        return;
    }
    
    // Save current playback state
    const currentTime = videoPlayer.currentTime;
    const wasPlaying = !videoPlayer.paused;
    
    // Pause video and show loading overlay
    videoPlayer.pause();
    showQualityChangeOverlay();
    
    // Fetch video URL for the selected quality
    fetchVideoQuality(userId, videoId, quality)
        .then(data => {
            if (data.success && data.url) {
                // Update current quality display
                const currentQualityDisplay = document.getElementById('current-quality');
                if (currentQualityDisplay) {
                    currentQualityDisplay.textContent = data.quality;
                }
                
                // Update active class on quality options
                const qualityOptions = document.querySelectorAll('.quality-option');
                qualityOptions.forEach(option => {
                    if (option.getAttribute('data-quality') === data.quality ||
                        (option.getAttribute('data-quality') === 'auto' && data.quality === 'auto')) {
                        option.classList.add('active');
                    } else {
                        option.classList.remove('active');
                    }
                });
                
                // Remember current time
                const currentTime = videoPlayer.currentTime;
                
                // Create new source elements
                const source = document.createElement('source');
                source.src = data.url;
                source.type = 'video/mp4';
                
                // Remove existing sources
                while (videoPlayer.firstChild) {
                    videoPlayer.removeChild(videoPlayer.firstChild);
                }
                
                // Add new source
                videoPlayer.appendChild(source);
                
                // Wait for video to load metadata
                videoPlayer.addEventListener('loadedmetadata', function onMetadataLoaded() {
                    // Set time to where we left off
                    videoPlayer.currentTime = currentTime;
                    
                    // Resume playback if it was playing
                    if (wasPlaying) {
                        videoPlayer.play()
                            .then(() => {
                                hideQualityChangeOverlay();
                            })
                            .catch(error => {
                                console.error('Error resuming playback:', error);
                                hideQualityChangeOverlay();
                            });
                    } else {
                        hideQualityChangeOverlay();
                    }
                    
                    // Remove this event listener
                    videoPlayer.removeEventListener('loadedmetadata', onMetadataLoaded);
                });
                
                // Handle loading error
                videoPlayer.addEventListener('error', function onLoadError() {
                    console.error('Error loading video at quality:', data.quality);
                    hideQualityChangeOverlay();
                    videoPlayer.removeEventListener('error', onLoadError);
                });
                
                // Load the video
                videoPlayer.load();
            } else {
                console.error('Failed to get video URL:', data.error || 'Unknown error');
                hideQualityChangeOverlay();
            }
        })
        .catch(error => {
            console.error('Error fetching video URL:', error);
            hideQualityChangeOverlay();
        });
}

// Function to initialize quality options
async function initializeQualityOptions(availableQualities) {
    const qualityOptions = document.getElementById('quality-options');
    const currentQualityDisplay = document.getElementById('current-quality');
    
    if (!qualityOptions || !availableQualities) return;
    
    // Сохраняем опцию auto
    const autoQualityOption = qualityOptions.querySelector('.auto-quality');
    
    // Очищаем все существующие опции кроме auto
    while (qualityOptions.firstChild) {
        qualityOptions.removeChild(qualityOptions.firstChild);
    }
    
    // Добавляем опцию auto обратно
    qualityOptions.appendChild(autoQualityOption);
    
    // Сортируем качества в порядке уменьшения (вначале самое высокое качество)
    const sortedQualities = [...availableQualities].sort((a, b) => {
        const numA = parseInt(a.replace('p', ''));
        const numB = parseInt(b.replace('p', ''));
        return numB - numA;
    });
    
    // Добавляем каждое доступное качество
    sortedQualities.forEach(quality => {
        const option = document.createElement('div');
        option.className = 'quality-option';
        option.setAttribute('data-quality', quality);
        
        // Определяем метку для качества
        let qualityLabel = quality;
        let extraInfo = '';
        
        // Добавляем дополнительную информацию для разных качеств
        if (quality === '360p') {
            extraInfo = 'Мобильное';
        } else if (quality === '720p') {
            extraInfo = 'HD';
        } else if (quality === '1080p') {
            extraInfo = 'Full HD';
        } else if (quality === '2160p') {
            extraInfo = '4K';
        }
        
        option.innerHTML = `
            <span class="quality-label">${qualityLabel}</span>
            ${extraInfo ? `<span class="quality-info">${extraInfo}</span>` : ''}
        `;
        
        // Добавляем обработчик события для смены качества
        option.addEventListener('click', function() {
            const quality = this.getAttribute('data-quality');
            changeVideoQuality(quality);
            
            // Обновляем активное состояние
            document.querySelectorAll('.quality-option').forEach(opt => {
                opt.classList.remove('active');
            });
            this.classList.add('active');
            
            // Закрываем меню настроек
            document.getElementById('settings-menu').classList.remove('active');
            document.getElementById('quality-options').classList.remove('active');
        });
        
        qualityOptions.appendChild(option);
    });
    
    // Устанавливаем текущее качество как "авто" по умолчанию
    if (currentQualityDisplay) {
        currentQualityDisplay.textContent = 'авто';
    }
    
    // Добавляем событие на клик для переключения качества
    qualityItem.addEventListener('click', function() {
        qualityOptions.classList.toggle('active');
        playbackSpeedOptions.classList.remove('active');
    });
}