document.addEventListener('DOMContentLoaded', function() {
    // Get the share button
    const shareButton = document.querySelector('.action-button[id="shareButton"]');
    
    if (!shareButton) return;
    
    // Initialize share popup
    initSharePopup();
    
    // Add click event to share button
    shareButton.addEventListener('click', function() {
        // Get video information from the page
        const videoContainer = document.querySelector('.video-container');
        const videoTitle = document.querySelector('.video-details h1').textContent;
        const videoId = videoContainer.getAttribute('data-video-id');
        const userId = videoContainer.getAttribute('data-user-id');
        
        // Show share popup
        showSharePopup(videoTitle, `${userId}__${videoId}`);
    });
    
    /**
     * Initialize share popup by adding it to the DOM
     */
    function initSharePopup() {
        // Create popup element
        const popup = document.createElement('div');
        popup.className = 'share-popup';
        popup.id = 'sharePopup';
        popup.innerHTML = `
            <div class="share-popup-content">
                <div class="share-popup-header">
                    <h3>Поделиться видео</h3>
                    <button class="share-popup-close">&times;</button>
                </div>
                <div class="share-popup-body">
                    <div class="share-url-container">
                        <input type="text" class="share-url" id="shareUrl" readonly>
                        <button class="copy-url-btn" id="copyUrlBtn">Копировать</button>
                    </div>
                    <p class="share-popup-title" id="shareTitle"></p>
                    <div class="share-social">
                        <h4>Поделиться в соцсетях</h4>
                        <div class="share-social-buttons">
                            <a href="#" class="share-social-btn" data-platform="telegram" title="Telegram">
                                <img src="/static/icons/telegram.svg" alt="Telegram" onerror="this.src='/static/icons/share.svg'">
                            </a>
                            <a href="#" class="share-social-btn" data-platform="vk" title="VKontakte">
                                <img src="/static/icons/vk.svg" alt="VKontakte" onerror="this.src='/static/icons/share.svg'">
                            </a>
                            <a href="#" class="share-social-btn" data-platform="whatsapp" title="WhatsApp">
                                <img src="/static/icons/whatsapp.svg" alt="WhatsApp" onerror="this.src='/static/icons/share.svg'">
                            </a>
                            <a href="#" class="share-social-btn" data-platform="email" title="Email">
                                <img src="/static/icons/email.svg" alt="Email" onerror="this.src='/static/icons/share.svg'">
                            </a>
                        </div>
                    </div>
                    <div class="share-embed" id="shareEmbed">
                        <h4>Код для встраивания</h4>
                        <textarea id="embedCode" readonly></textarea>
                        <button class="copy-embed-btn" id="copyEmbedBtn">Копировать код</button>
                    </div>
                </div>
            </div>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .share-popup {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.7);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s, visibility 0.3s;
            }
            
            .share-popup.active {
                opacity: 1;
                visibility: visible;
            }
            
            .share-popup-content {
                background-color: var(--light-bg);
                border-radius: 15px;
                width: 90%;
                max-width: 500px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                overflow: hidden;
                transform: translateY(20px);
                transition: transform 0.3s;
            }
            
            .dark-theme .share-popup-content {
                background-color: var(--medium-bg);
                color: var(--text-light);
            }
            
            .share-popup.active .share-popup-content {
                transform: translateY(0);
            }
            
            .share-popup-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px 20px;
                border-bottom: 1px solid rgba(159, 37, 88, 0.1);
            }
            
            .share-popup-header h3 {
                margin: 0;
                color: var(--primary-color);
            }
            
            .share-popup-close {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: var(--gray-color);
                transition: color 0.3s;
            }
            
            .share-popup-close:hover {
                color: var(--primary-color);
            }
            
            .share-popup-body {
                padding: 20px;
            }
            
            .share-url-container {
                display: flex;
                margin-bottom: 15px;
            }
            
            .share-url {
                flex-grow: 1;
                padding: 10px 15px;
                border: 1px solid rgba(159, 37, 88, 0.2);
                border-radius: 8px 0 0 8px;
                font-size: 14px;
                color: inherit;
                background-color: rgba(255, 255, 255, 0.1);
            }
            
            .copy-url-btn {
                padding: 10px 15px;
                background-color: var(--accent-color);
                color: white;
                border: none;
                border-radius: 0 8px 8px 0;
                cursor: pointer;
                transition: background-color 0.3s;
            }
            
            .copy-url-btn:hover {
                background-color: #7d1e46;
            }
            
            .share-popup-title {
                font-size: 14px;
                margin: 0 0 20px;
                color: var(--gray-color);
            }
            
            .share-social h4, .share-embed h4 {
                margin: 0 0 10px;
                font-size: 16px;
                color: var(--primary-color);
            }
            
            .share-social-buttons {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
            }
            
            .share-social-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background-color: rgba(159, 37, 88, 0.1);
                transition: all 0.3s;
            }
            
            .share-social-btn:hover {
                background-color: var(--accent-color);
                transform: translateY(-3px);
            }
            
            .share-social-btn img {
                width: 20px;
                height: 20px;
            }
            
            .share-embed textarea {
                width: 100%;
                height: 80px;
                padding: 10px;
                margin-bottom: 10px;
                border: 1px solid rgba(159, 37, 88, 0.2);
                border-radius: 8px;
                resize: none;
                font-family: monospace;
                font-size: 12px;
                background-color: rgba(255, 255, 255, 0.1);
                color: inherit;
            }
            
            .copy-embed-btn {
                padding: 8px 15px;
                background-color: transparent;
                color: var(--primary-color);
                border: 1px solid var(--primary-color);
                border-radius: 20px;
                cursor: pointer;
                transition: all 0.3s;
            }
            
            .copy-embed-btn:hover {
                background-color: rgba(159, 37, 88, 0.1);
                transform: translateY(-2px);
            }
            
            .copy-success {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 10px 20px;
                background-color: var(--accent-color);
                color: white;
                border-radius: 5px;
                font-size: 14px;
                opacity: 0;
                transform: translateY(-20px);
                transition: all 0.3s;
                z-index: 1001;
            }
            
            .copy-success.show {
                opacity: 1;
                transform: translateY(0);
            }
            
            @media (max-width: 576px) {
                .share-popup-content {
                    width: 95%;
                }
                
                .share-url-container {
                    flex-direction: column;
                }
                
                .share-url {
                    border-radius: 8px;
                    margin-bottom: 10px;
                }
                
                .copy-url-btn {
                    border-radius: 8px;
                    width: 100%;
                }
                
                .share-social-buttons {
                    flex-wrap: wrap;
                    justify-content: center;
                }
            }
        `;
        
        // Add popup and styles to the document
        document.head.appendChild(style);
        document.body.appendChild(popup);
        
        // Close popup when clicking close button
        const closeButton = popup.querySelector('.share-popup-close');
        closeButton.addEventListener('click', function() {
            popup.classList.remove('active');
        });
        
        // Close popup when clicking outside
        popup.addEventListener('click', function(e) {
            if (e.target === popup) {
                popup.classList.remove('active');
            }
        });
        
        // Copy URL functionality
        const copyUrlBtn = document.getElementById('copyUrlBtn');
        const shareUrl = document.getElementById('shareUrl');
        
        copyUrlBtn.addEventListener('click', function() {
            shareUrl.select();
            document.execCommand('copy');
            showCopySuccess('URL скопирован в буфер обмена');
        });
        
        // Copy embed code functionality
        const copyEmbedBtn = document.getElementById('copyEmbedBtn');
        const embedCode = document.getElementById('embedCode');
        
        copyEmbedBtn.addEventListener('click', function() {
            embedCode.select();
            document.execCommand('copy');
            showCopySuccess('Код встраивания скопирован');
        });
        
        // Social media sharing
        const socialButtons = document.querySelectorAll('.share-social-btn');
        
        socialButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const platform = this.getAttribute('data-platform');
                const url = shareUrl.value;
                const title = document.getElementById('shareTitle').textContent;
                
                let shareUrl;
                
                switch (platform) {
                    case 'telegram':
                        shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`;
                        break;
                    case 'vk':
                        shareUrl = `https://vk.com/share.php?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`;
                        break;
                    case 'whatsapp':
                        shareUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(title + ' ' + url)}`;
                        break;
                    case 'email':
                        shareUrl = `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(title + '\n' + url)}`;
                        break;
                    default:
                        return;
                }
                
                // Open share URL in new window
                window.open(shareUrl, '_blank', 'width=600,height=400');
            });
        });
    }
    
    /**
     * Show share popup with video information
     */
    function showSharePopup(title, videoId) {
        const popup = document.getElementById('sharePopup');
        const shareUrl = document.getElementById('shareUrl');
        const shareTitle = document.getElementById('shareTitle');
        const embedCode = document.getElementById('embedCode');
        
        // Set video URL
        const url = window.location.origin + '/video/' + videoId + '/';
        shareUrl.value = url;
        
        // Set video title
        shareTitle.textContent = title;
        
        // Set embed code
        const embedHtml = `<iframe width="560" height="315" src="${window.location.origin}/video/${videoId}/?embed=1" frameborder="0" allowfullscreen></iframe>`;
        embedCode.value = embedHtml;
        
        // Show popup
        popup.classList.add('active');
    }
    
    /**
     * Show copy success message
     */
    function showCopySuccess(message) {
        // Create or get message element
        let successMsg = document.querySelector('.copy-success');
        
        if (!successMsg) {
            successMsg = document.createElement('div');
            successMsg.className = 'copy-success';
            document.body.appendChild(successMsg);
        }
        
        // Set message and show
        successMsg.textContent = message;
        successMsg.classList.add('show');
        
        // Hide after 2 seconds
        setTimeout(function() {
            successMsg.classList.remove('show');
        }, 2000);
    }
});