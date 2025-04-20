document.addEventListener('DOMContentLoaded', function() {
    // Get player elements
    const videoPlayer = document.getElementById('video-player');
    const playPauseBtn = document.getElementById('play-pause-btn');
    const playBigBtn = document.getElementById('play-big-btn');
    const volumeBtn = document.getElementById('volume-btn');
    const volumeBar = document.getElementById('volume-bar');
    const volumeLevel = document.getElementById('volume-level');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const bufferBar = document.getElementById('buffer-bar');
    const currentTimeDisplay = document.getElementById('current-time');
    const durationDisplay = document.getElementById('duration');
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const pipBtn = document.getElementById('pip-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsMenu = document.getElementById('settings-menu');
    const playbackSpeedItem = document.getElementById('playback-speed-item');
    const playbackSpeedOptions = document.getElementById('playback-speed-options');
    const qualityItem = document.getElementById('quality-item');
    const qualityOptions = document.getElementById('quality-options');
    const loopItem = document.getElementById('loop-item');
    const loopStatus = document.getElementById('loop-status');
    const currentSpeed = document.getElementById('current-speed');
    const currentQuality = document.getElementById('current-quality');
    const speedOptions = document.querySelectorAll('.speed-option');
    const loadingSpinner = document.getElementById('loading-spinner');
    const videoContainer = document.querySelector('.video-container');
    
    // Early exit if the video player doesn't exist
    if (!videoPlayer) return;
    
    // Get video id and user id from the container data attributes
    const videoId = videoContainer.getAttribute('data-video-id');
    const userId = videoContainer.getAttribute('data-user-id');
    
    // Variables for tracking available qualities
    let availableQualities = [];
    let currentQualitySelection = 'auto';
    
    // Show loading spinner
    loadingSpinner.classList.add('visible');
    
    // Format time function
    function formatTime(seconds) {
        if (isNaN(seconds)) return "0:00";
        
        const minutes = Math.floor(seconds / 60);
        seconds = Math.floor(seconds % 60);
        return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    }
    
    // Update play/pause icon function
    function updatePlayPauseIcon(isPlaying) {
        if (isPlaying) {
            playPauseBtn.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor"/>
                    <rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor"/>
                </svg>
            `;
            playBigBtn.innerHTML = `
                <div class="pause-icon">
                    <div class="pause-bar"></div>
                    <div class="pause-bar"></div>
                </div>
            `;
            playBigBtn.classList.remove('visible');
        } else {
            playPauseBtn.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M8 5V19L19 12L8 5Z" fill="currentColor"/>
                </svg>
            `;
            playBigBtn.innerHTML = `<div class="play-icon"></div>`;
            playBigBtn.classList.add('visible');
        }
    }
    
    // Toggle play/pause function
    function togglePlay() {
        if (videoPlayer.paused) {
            videoPlayer.play();
        } else {
            videoPlayer.pause();
        }
    }
    
    // Update volume icon function
    function updateVolumeIcon() {
        if (videoPlayer.muted || videoPlayer.volume === 0) {
            volumeBtn.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M11 5L6 9H2V15H6L11 19V5Z" fill="currentColor"/>
                    <path d="M23 9L17 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <path d="M17 9L23 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            `;
        } else if (videoPlayer.volume < 0.5) {
            volumeBtn.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M11 5L6 9H2V15H6L11 19V5Z" fill="currentColor"/>
                    <path d="M15.54 8.46C16.47 9.39 17 10.62 17 12C17 13.38 16.47 14.61 15.54 15.54" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            `;
        } else {
            volumeBtn.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M11 5L6 9H2V15H6L11 19V5Z" fill="currentColor"/>
                    <path d="M15.54 8.46C16.47 9.39 17 10.62 17 12C17 13.38 16.47 14.61 15.54 15.54" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <path d="M19.07 4.93C20.91 6.77 22 9.27 22 12C22 14.73 20.91 17.23 19.07 19.07" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            `;
        }
    }
    
    // Show error message function
    function showErrorMessage(message) {
        // Hide loading spinner
        loadingSpinner.classList.remove('visible');
        
        // Create error message element
        const errorElement = document.createElement('div');
        errorElement.className = 'video-error-message';
        errorElement.innerHTML = `
            <div class="error-icon">⚠️</div>
            <div class="error-text">${message}</div>
            <button class="error-retry-btn">Повторить</button>
        `;
        
        // Add retry functionality
        const retryButton = errorElement.querySelector('.error-retry-btn');
        if (retryButton) {
            retryButton.addEventListener('click', function() {
                errorElement.remove();
                loadingSpinner.classList.add('visible');
                fetchVideoUrl(videoId, userId);
            });
        }
        
        // Add error message to video container
        const videoWrapper = document.querySelector('.video-wrapper');
        if (videoWrapper) {
            videoWrapper.appendChild(errorElement);
        }
    }
    
    // Fetch video URL asynchronously with quality selection
    function fetchVideoUrl(videoId, userId, quality = 'auto') {
        // Error handling to make sure videoId and userId are valid
        if (!videoId || !userId) {
            console.error('Missing videoId or userId');
            showErrorMessage('Ошибка загрузки: информация о видео отсутствует');
            return;
        }
        
        // Construct API URL with user_id parameter and quality
        const apiUrl = `/api/get-video-url/${videoId}/?user_id=${encodeURIComponent(userId)}&quality=${quality}`;
        
        fetch(apiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success && data.url) {
                    // Store available qualities
                    availableQualities = data.available_qualities || [];
                    currentQualitySelection = data.quality || 'auto';
                    
                    // Initialize quality selector
                    initializeQualityOptions(availableQualities);
                    
                    // Update current quality display
                    if (currentQuality) {
                        currentQuality.textContent = currentQualitySelection;
                    }
                    
                    // Set video source and start loading
                    const source = document.createElement('source');
                    source.src = data.url;
                    source.type = 'video/mp4';
                    videoPlayer.appendChild(source);
                    videoPlayer.load();
                    
                    // Preload metadata
                    videoPlayer.setAttribute('preload', 'metadata');
                } else {
                    console.error('Error loading video:', data.error || 'Unknown error');
                    showErrorMessage('Не удалось загрузить видео. Пожалуйста, попробуйте позже.');
                }
            })
            .catch(error => {
                console.error('Error fetching video URL:', error);
                showErrorMessage('Ошибка при загрузке видео. Проверьте соединение с интернетом.');
            });
    }
    
    // ===== Event listeners =====
    
    // Metadata loaded - hide spinner and update duration
    videoPlayer.addEventListener('loadedmetadata', function() {
        durationDisplay.textContent = formatTime(videoPlayer.duration);
        loadingSpinner.classList.remove('visible');
    });
    
    // Time update - update progress bar and current time
    videoPlayer.addEventListener('timeupdate', function() {
        currentTimeDisplay.textContent = formatTime(videoPlayer.currentTime);
        const progress = (videoPlayer.currentTime / videoPlayer.duration) * 100;
        progressBar.style.width = `${progress}%`;
    });
    
    // Video progress (buffering) handler
    videoPlayer.addEventListener('progress', function() {
        if (videoPlayer.buffered.length > 0) {
            const bufferedEnd = videoPlayer.buffered.end(videoPlayer.buffered.length - 1);
            const duration = videoPlayer.duration;
            if (duration > 0) {
                const bufferedPercent = (bufferedEnd / duration) * 100;
                bufferBar.style.width = `${bufferedPercent}%`;
            }
        }
    });
    
    // Video waiting handler - show spinner
    videoPlayer.addEventListener('waiting', function() {
        loadingSpinner.classList.add('visible');
    });
    
    // Video playing handler - hide spinner and update play icon
    videoPlayer.addEventListener('playing', function() {
        loadingSpinner.classList.remove('visible');
        updatePlayPauseIcon(true);
    });
    
    // Video paused handler - update play icon
    videoPlayer.addEventListener('pause', function() {
        updatePlayPauseIcon(false);
    });
    
    // Video ended handler - show play icon
    videoPlayer.addEventListener('ended', function() {
        updatePlayPauseIcon(false);
    });
    
    // Error handler - show error message
    videoPlayer.addEventListener('error', function() {
        let errorMessage = 'Ошибка при загрузке видео';
        
        if (videoPlayer.error) {
            switch (videoPlayer.error.code) {
                case MediaError.MEDIA_ERR_ABORTED:
                    errorMessage = 'Воспроизведение прервано пользователем';
                    break;
                case MediaError.MEDIA_ERR_NETWORK:
                    errorMessage = 'Сетевая ошибка при загрузке видео';
                    break;
                case MediaError.MEDIA_ERR_DECODE:
                    errorMessage = 'Ошибка декодирования видео';
                    break;
                case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
                    errorMessage = 'Формат видео не поддерживается';
                    break;
            }
        }
        
        showErrorMessage(errorMessage);
    });
    
    // Play/pause button handler
    playPauseBtn.addEventListener('click', togglePlay);
    
    // Big play button handler
    playBigBtn.addEventListener('click', function() {
        togglePlay();
    });
    
    // Video player click handler
    videoPlayer.addEventListener('click', function(e) {
        // Only toggle if not clicking on controls
        if (e.target === videoPlayer) {
            togglePlay();
        }
    });
    
    // Progress bar click handler
    progressContainer.addEventListener('click', function(e) {
        if (!videoPlayer.duration) return; // Don't do anything if duration is not available
        
        const rect = progressContainer.getBoundingClientRect();
        const position = (e.clientX - rect.left) / rect.width;
        videoPlayer.currentTime = position * videoPlayer.duration;
    });
    
    // Volume bar click handler
    volumeBar.addEventListener('click', function(e) {
        const rect = volumeBar.getBoundingClientRect();
        const position = (e.clientX - rect.left) / rect.width;
        videoPlayer.volume = Math.max(0, Math.min(1, position));
        volumeLevel.style.width = `${videoPlayer.volume * 100}%`;
        
        // Unmute if volume is set manually
        if (videoPlayer.muted && videoPlayer.volume > 0) {
            videoPlayer.muted = false;
        }
        
        updateVolumeIcon();
    });
    
    // Volume button click handler (mute/unmute)
    volumeBtn.addEventListener('click', function() {
        videoPlayer.muted = !videoPlayer.muted;
        if (videoPlayer.muted) {
            volumeLevel.style.width = '0';
        } else {
            volumeLevel.style.width = `${videoPlayer.volume * 100}%`;
        }
        updateVolumeIcon();
    });
    
    // Fullscreen button click handler
    fullscreenBtn.addEventListener('click', function() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            videoContainer.requestFullscreen().catch(err => {
                console.error(`Ошибка при переходе в полноэкранный режим: ${err.message}`);
            });
        }
    });
    
    // PiP button click handler
    pipBtn.addEventListener('click', function() {
        if (document.pictureInPictureElement) {
            document.exitPictureInPicture().catch(err => {
                console.error(`Ошибка при выходе из режима картинка-в-картинке: ${err.message}`);
            });
        } else if (document.pictureInPictureEnabled) {
            videoPlayer.requestPictureInPicture().catch(err => {
                console.error(`Ошибка при входе в режим картинка-в-картинке: ${err.message}`);
            });
        }
    });
    
    // Settings button click handler
    settingsBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        settingsMenu.classList.toggle('active');
    });
    
    // Close settings menu when clicking outside
    document.addEventListener('click', function(e) {
        if (!settingsMenu.contains(e.target) && e.target !== settingsBtn) {
            settingsMenu.classList.remove('active');
            playbackSpeedOptions.classList.remove('active');
            qualityOptions.classList.remove('active');
        }
    });
    
    // Playback speed menu handler
    playbackSpeedItem.addEventListener('click', function() {
        playbackSpeedOptions.classList.toggle('active');
        qualityOptions.classList.remove('active');
    });
    
    // Playback speed options handlers
    speedOptions.forEach(option => {
        option.addEventListener('click', function() {
            const speed = parseFloat(option.getAttribute('data-speed'));
            videoPlayer.playbackRate = speed;
            currentSpeed.textContent = `${speed}x`;
            
            speedOptions.forEach(opt => {
                opt.classList.remove('active');
            });
            option.classList.add('active');
        });
    });
    
    // Quality menu handler
    qualityItem.addEventListener('click', function() {
        qualityOptions.classList.toggle('active');
        playbackSpeedOptions.classList.remove('active');
    });
    
    // Loop toggle handler
    loopItem.addEventListener('click', function() {
        videoPlayer.loop = !videoPlayer.loop;
        loopStatus.textContent = videoPlayer.loop ? 'Вкл' : 'Выкл';
    });
    
    // Keyboard controls
    document.addEventListener('keydown', function(e) {
        // Skip if focus is on an input element
        if (document.activeElement.tagName === 'INPUT') return;
        
        switch (e.key) {
            case ' ':
            case 'k':
                togglePlay();
                e.preventDefault();
                break;
            case 'ArrowLeft':
                videoPlayer.currentTime = Math.max(0, videoPlayer.currentTime - 5);
                e.preventDefault();
                break;
            case 'ArrowRight':
                videoPlayer.currentTime = Math.min(videoPlayer.duration || 0, videoPlayer.currentTime + 5);
                e.preventDefault();
                break;
            case 'f':
                fullscreenBtn.click();
                e.preventDefault();
                break;
            case 'm':
                videoPlayer.muted = !videoPlayer.muted;
                if (videoPlayer.muted) {
                    volumeLevel.style.width = '0';
                } else {
                    volumeLevel.style.width = `${videoPlayer.volume * 100}%`;
                }
                updateVolumeIcon();
                e.preventDefault();
                break;
            case '0':
            case '1':
            case '2':
            case '3':
            case '4':
            case '5':
            case '6':
            case '7':
            case '8':
            case '9':
                if (videoPlayer.duration) {
                    const percent = parseInt(e.key) * 10;
                    videoPlayer.currentTime = videoPlayer.duration * (percent / 100);
                    e.preventDefault();
                }
                break;
        }
    });
    
    // Initialize UI states
    updateVolumeIcon();
    volumeLevel.style.width = `${videoPlayer.volume * 100}%`;
    
    // Initialize async video loading
    // Start video loading immediately (don't wait for any other resources)
    if (videoId && userId) {
        // Initiate video loading immediately with auto quality
        fetchVideoUrl(videoId, userId, 'auto');
    } else {
        showErrorMessage('Ошибка: Не найден идентификатор видео');
    }
    
    // Track view after 5 seconds of playback
    let viewTracked = false;
    videoPlayer.addEventListener('timeupdate', function() {
        if (!viewTracked && videoPlayer.currentTime > 5) {
            viewTracked = true;
            console.log('View tracked');
            // In a real app, you would make an AJAX request to track the view
        }
    });
});