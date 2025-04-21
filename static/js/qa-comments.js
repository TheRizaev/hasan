/**
 * Q&A and Comments System for Video Platform
 * This file handles all the functionality related to the Q&A section on video pages
 */

// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Main elements
    const qaSection = document.querySelector('.qa-section');
    const qaForm = document.getElementById('qa-form');
    const qaInput = document.getElementById('qa-input');
    const qaSubmit = document.getElementById('qa-submit');
    const qaList = document.getElementById('qa-list');
    
    // Get video container to extract video and user IDs
    const videoContainer = document.querySelector('.video-container');
    const videoId = videoContainer ? videoContainer.getAttribute('data-video-id') : null;
    const videoUserId = videoContainer ? videoContainer.getAttribute('data-user-id') : null;
    
    // Check if user is authenticated
    const isAuthenticated = qaSubmit ? !qaSubmit.disabled : false;
    
    // Initialize the comment system
    initQASystem();
    
    /**
     * Main initialization function
     */
    function initQASystem() {
        console.log("Initializing QA system...");
        console.log("isAuthenticated:", isAuthenticated);
        
        // Register event listeners for non-authenticated users
        if (!isAuthenticated) {
            setupNonAuthenticatedHandlers();
        } else {
            // Set up comment submission
            setupCommentSubmission();
            // Set up like buttons
            setupLikeButtons();
        }
        
        // Set up event delegation for reply buttons
        setupReplyButtonDelegation();
        // Apply event handlers to existing comments
        setupExistingComments();
    }

    function setupReplyButtonDelegation() {
        console.log("Setting up reply button delegation...");
        qaList.addEventListener('click', function(e) {
            const replyBtn = e.target.closest('.qa-reply-btn');
            if (replyBtn && isAuthenticated) {
                e.preventDefault();
                const commentId = replyBtn.getAttribute('data-comment-id');
                console.log(`Reply button clicked for comment ${commentId}`);
                toggleReplyForm(commentId);
            }
        });
    }
    
    /**
     * Setup event handlers for existing comments
     */
    function setupExistingComments() {
        console.log("Setting up existing comments...");
        const existingComments = document.querySelectorAll('.qa-item');
        console.log(`Found ${existingComments.length} existing comments`);
        
        existingComments.forEach(comment => {
            const commentId = comment.getAttribute('data-comment-id');
            console.log(`Setting up comment ID: ${commentId}`);
            
            // Set up cancel buttons
            const cancelBtn = comment.querySelector('.cancel-reply');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    hideReplyForm(commentId);
                });
            }
            
            // Set up reply submission
            const replySubmitBtn = comment.querySelector('.reply-submit');
            if (replySubmitBtn && isAuthenticated) {
                replySubmitBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    submitReply(commentId);
                });
                
                // Also allow submit on Enter key
                const replyInput = comment.querySelector(`#reply-input-${commentId}`);
                if (replyInput) {
                    replyInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            submitReply(commentId);
                        }
                    });
                }
            }
            
            // Set up like buttons
            setupCommentLikes(comment);
        });
    }
    
    /**
     * Set up handlers for non-authenticated users
     */
    function setupNonAuthenticatedHandlers() {
        // Redirect to login when trying to interact with comment box
        const inputs = qaSection.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('click', function(e) {
                e.preventDefault();
                showLoginModal();
            });
        });
        
        // Redirect likes to login
        document.querySelectorAll('.qa-like').forEach(likeBtn => {
            likeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                showLoginModal();
            });
        });
    }
    
    /**
     * Set up comment submission
     */
    function setupCommentSubmission() {
        if (!qaForm || !qaInput || !qaSubmit) return;
        
        // Form submission handler
        qaForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitComment();
        });
        
        // Submit button click handler
        qaSubmit.addEventListener('click', function(e) {
            e.preventDefault();
            submitComment();
        });
        
        // Enter key handler
        qaInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitComment();
            }
        });
    }
    
    /**
     * Function to submit a new comment
     */
    function submitComment() {
        const commentText = qaInput.value.trim();
        
        if (commentText === '') return;
        
        // Show loading state
        qaSubmit.disabled = true;
        qaSubmit.textContent = 'Отправка...';
        
        // Get CSRF token for Django
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Create a proper video ID for API
        let apiVideoId = videoId;
        if (videoUserId) {
            // Make sure we use the composite ID format for the API
            apiVideoId = `${videoUserId}__${videoId}`;
        }
        
        // Prepare data for submission
        const formData = new FormData();
        formData.append('text', commentText);
        formData.append('video_id', apiVideoId);
        
        // Using fetch to send the request
        fetch('/api/add-comment/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Clear input
                qaInput.value = '';
                
                // Create and add the new comment
                addNewComment(data.comment);
                
                // Display success message
                showStatusMessage('Комментарий успешно добавлен', 'success');
            } else {
                showStatusMessage(data.error || 'Ошибка при добавлении комментария', 'error');
            }
        })
        .catch(error => {
            console.error('Error adding comment:', error);
            
            // If API is not available, use mock comment for demonstration
            if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                addMockComment(commentText);
                showStatusMessage('Комментарий добавлен (демо-режим)', 'success');
            } else {
                showStatusMessage('Ошибка при отправке комментария. Пожалуйста, попробуйте позже.', 'error');
            }
        })
        .finally(() => {
            // Reset button state
            qaSubmit.disabled = false;
            qaSubmit.textContent = 'Отправить';
        });
    }
    
    /**
     * Add a mock comment (for demonstration when API is not available)
     */
    function addMockComment(commentText) {
        // Clear input
        qaInput.value = '';
        
        // Create a mock comment object
        const mockComment = {
            id: 'mock-' + Date.now(),
            user_id: 'current-user',
            display_name: getCurrentUserName(),
            text: commentText,
            date: new Date().toISOString(),
            likes: 0,
            replies: []
        };
        
        // Add the mock comment to the DOM
        addNewComment(mockComment);
    }
    
    /**
     * Add a new comment to the DOM
     */
    function addNewComment(comment) {
        // Create the comment element
        const commentElement = createCommentElement(comment);
        
        // If there's a "no comments" message, remove it
        const noQaMessage = qaList.querySelector('.no-qa');
        if (noQaMessage) {
            noQaMessage.remove();
        }
        
        // Add new comment to the top of the list
        qaList.prepend(commentElement);
        
        // Set up event handlers for the new comment
        setupCommentHandlers(commentElement, comment.id);
    }
    
    /**
     * Create a DOM element for a comment
     */
    function createCommentElement(comment) {
        const isAuthor = comment.user_id === videoUserId;
        
        const div = document.createElement('div');
        div.className = 'qa-item';
        div.setAttribute('data-comment-id', comment.id);
        
        const displayName = comment.display_name || 'User';
        const firstLetter = displayName.charAt(0);
        
        // Format date in a user-friendly way
        const date = new Date(comment.date);
        const formattedDate = formatDate(date);
        
        // Determine avatar content - either image or first letter
        let avatarContent = '';
        if (comment.avatar_url) {
            avatarContent = `<img src="${comment.avatar_url}" alt="${displayName}">`;
        } else {
            avatarContent = firstLetter;
        }
        
        // Get current user initial for reply form
        const currentUserInitial = getCurrentUserInitial();
        // Get current user avatar for reply form
        const currentUserAvatar = getCurrentUserAvatar();
        
        div.innerHTML = `
            <div class="user-avatar ${isAuthor ? 'author-avatar' : ''}">
                ${avatarContent}
            </div>
            <div class="qa-content">
                <div class="qa-author ${isAuthor ? 'is-author' : ''}">
                    ${displayName}
                    ${isAuthor ? '<span class="author-badge">Автор</span>' : ''}
                </div>
                <div class="qa-text">${comment.text}</div>
                <div class="qa-meta">${formattedDate}</div>
                <div class="qa-actions">
                    <button class="qa-like" data-liked="false">👍 <span>${comment.likes || 0}</span></button>
                    <button class="qa-reply-btn" data-comment-id="${comment.id}">Ответить</button>
                </div>
                
                <!-- Reply form (initially hidden) -->
                <div class="reply-form" id="reply-form-${comment.id}" style="display: none;">
                    <div class="user-avatar">${currentUserAvatar}</div>
                    <input type="text" id="reply-input-${comment.id}" placeholder="Ответить на вопрос...">
                    <button class="reply-submit" data-comment-id="${comment.id}">Ответить</button>
                    <button class="cancel-reply" data-comment-id="${comment.id}">Отмена</button>
                </div>
                
                <div class="qa-replies"></div>
            </div>
        `;
        
        return div;
    }
    
    /**
     * Set up event handlers for a comment element
     */
    function setupCommentHandlers(commentElement, commentId) {
        // Set up reply button
        const replyBtn = commentElement.querySelector('.qa-reply-btn');
        if (replyBtn) {
            replyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                console.log(`Reply button clicked for comment ${commentId}`);
                toggleReplyForm(commentId);
            });
        }
        
        // Set up cancel button
        const cancelBtn = commentElement.querySelector('.cancel-reply');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function(e) {
                e.preventDefault();
                hideReplyForm(commentId);
            });
        }
        
        // Set up reply submission
        const replySubmitBtn = commentElement.querySelector('.reply-submit');
        if (replySubmitBtn) {
            replySubmitBtn.addEventListener('click', function(e) {
                e.preventDefault();
                submitReply(commentId);
            });
            
            // Also allow submit on Enter key
            const replyInput = commentElement.querySelector(`#reply-input-${commentId}`);
            if (replyInput) {
                replyInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        submitReply(commentId);
                    }
                });
            }
        }
        
        // Set up like button
        setupCommentLikes(commentElement);
    }
    
    /**
     * Set up all reply buttons
     */
    function setupReplyButtons() {
        console.log("Setting up reply buttons...");
        document.querySelectorAll('.qa-reply-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const commentId = this.getAttribute('data-comment-id');
                console.log(`Reply button clicked for comment ${commentId}`);
                toggleReplyForm(commentId);
            });
        });
    }
    
    /**
     * Set up like buttons
     */
    function setupLikeButtons() {
        document.querySelectorAll('.qa-item').forEach(comment => {
            setupCommentLikes(comment);
        });
    }
    
    /**
     * Set up like functionality for a specific comment
     */
    function setupCommentLikes(commentElement) {
        const likeButton = commentElement.querySelector('.qa-like');
        if (likeButton && isAuthenticated) {
            likeButton.addEventListener('click', function() {
                toggleLike(this);
            });
        }
    }
    
    /**
     * Toggle like state on a comment/reply
     */
    function toggleLike(likeButton) {
        // Toggle the liked state
        const isLiked = likeButton.getAttribute('data-liked') === 'true';
        likeButton.setAttribute('data-liked', !isLiked);
        
        // Update the visual state
        if (!isLiked) {
            likeButton.classList.add('liked');
            likeButton.style.color = 'var(--accent-color)';
        } else {
            likeButton.classList.remove('liked');
            likeButton.style.color = '';
        }
        
        // Update the count
        const countSpan = likeButton.querySelector('span');
        let count = parseInt(countSpan.textContent) || 0;
        
        if (!isLiked) {
            count++;
        } else {
            count = Math.max(0, count - 1);
        }
        
        countSpan.textContent = count;
        
        // In a real implementation, you would send this to the server
        // This is just a frontend simulation for now
        const commentId = likeButton.closest('.qa-item').getAttribute('data-comment-id');
        console.log(`Like toggled for comment ${commentId}, new state: ${!isLiked}`);
    }
    
    /**
     * Toggle visibility of the reply form
     */
    function toggleReplyForm(commentId) {
        console.log(`Toggling reply form for comment ${commentId}`);
        const replyForm = document.getElementById(`reply-form-${commentId}`);
        
        if (!replyForm) {
            console.error(`Reply form not found for comment ${commentId}`);
            showStatusMessage('Ошибка: форма ответа не найдена', 'error');
            return;
        }
        
        // Hide all other reply forms
        document.querySelectorAll('.reply-form').forEach(form => {
            if (form.id !== `reply-form-${commentId}` && form.style.display !== 'none') {
                form.style.display = 'none';
                const input = form.querySelector('input');
                if (input) input.value = '';
            }
        });
        
        // Toggle this form
        const isHidden = replyForm.style.display === 'none' || replyForm.style.display === '';
        replyForm.style.display = isHidden ? 'flex' : 'none';
        console.log(`New reply form display: ${replyForm.style.display}`);
        
        // Focus the input field if showing
        if (isHidden) {
            const input = replyForm.querySelector('input');
            if (input) {
                input.focus();
            }
        }
    }
    
    /**
     * Hide a specific reply form
     */
    function hideReplyForm(commentId) {
        const replyForm = document.getElementById(`reply-form-${commentId}`);
        if (replyForm) {
            replyForm.style.display = 'none';
            const input = replyForm.querySelector('input');
            if (input) input.value = '';
        }
    }
    
    /**
     * Submit a reply to a comment
     */
    function submitReply(commentId) {
        const replyForm = document.getElementById(`reply-form-${commentId}`);
        const replyInput = document.getElementById(`reply-input-${commentId}`);
        const replySubmitBtn = replyForm.querySelector('.reply-submit');
        
        const replyText = replyInput.value.trim();
        if (replyText === '') return;
        
        // Show loading state
        replySubmitBtn.disabled = true;
        replySubmitBtn.textContent = 'Отправка...';
        
        // Get CSRF token for Django
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Create a proper video ID for API
        let apiVideoId = videoId;
        if (videoUserId) {
            // Make sure we use the composite ID format for the API
            apiVideoId = `${videoUserId}__${videoId}`;
        }
        
        // Prepare data for submission
        const formData = new FormData();
        formData.append('text', replyText);
        formData.append('comment_id', commentId);
        formData.append('video_id', apiVideoId);
        
        // Send request to the server
        fetch('/api/add-reply/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Clear input and hide form
                replyInput.value = '';
                replyForm.style.display = 'none';
                
                // Add the reply to the DOM
                addReplyToComment(commentId, data.reply);
                
                // Show success message
                showStatusMessage('Ответ успешно добавлен', 'success');
            } else {
                showStatusMessage(data.error || 'Ошибка при добавлении ответа', 'error');
            }
        })
        .catch(error => {
            console.error('Error adding reply:', error);
            
            // If API is not available, use mock reply for demonstration
            if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                addMockReply(commentId, replyText);
                showStatusMessage('Ответ добавлен (демо-режим)', 'success');
            } else {
                showStatusMessage('Ошибка при отправке ответа. Пожалуйста, попробуйте позже.', 'error');
            }
        })
        .finally(() => {
            // Reset button state
            replySubmitBtn.disabled = false;
            replySubmitBtn.textContent = 'Ответить';
        });
    }
    
    /**
     * Add a mock reply (for demonstration when API is not available)
     */
    function addMockReply(commentId, replyText) {
        // Clear input and hide form
        const replyForm = document.getElementById(`reply-form-${commentId}`);
        const replyInput = document.getElementById(`reply-input-${commentId}`);
        
        replyInput.value = '';
        replyForm.style.display = 'none';
        
        // Create a mock reply object
        const mockReply = {
            id: 'mock-reply-' + Date.now(),
            user_id: 'current-user',
            display_name: getCurrentUserName(),
            text: replyText,
            date: new Date().toISOString(),
            likes: 0
        };
        
        // Add the mock reply to the DOM
        addReplyToComment(commentId, mockReply);
    }
    
    /**
     * Add a reply to a comment in the DOM
     */
    function addReplyToComment(commentId, reply) {
        // Find the comment
        const commentElement = document.querySelector(`.qa-item[data-comment-id="${commentId}"]`);
        if (!commentElement) return;
        
        // Find or create the replies container
        let repliesContainer = commentElement.querySelector('.qa-replies');
        if (!repliesContainer) {
            repliesContainer = document.createElement('div');
            repliesContainer.className = 'qa-replies';
            commentElement.querySelector('.qa-content').appendChild(repliesContainer);
        }
        
        // Create the reply element
        const replyElement = createReplyElement(reply);
        
        // Add it to the container
        repliesContainer.appendChild(replyElement);
        
        // Set up like functionality for the reply
        const likeButton = replyElement.querySelector('.qa-like');
        if (likeButton && isAuthenticated) {
            likeButton.addEventListener('click', function() {
                toggleLike(this);
            });
        }
    }
    
    /**
     * Create a DOM element for a reply
     */
    function createReplyElement(reply) {
        const isAuthor = reply.user_id === videoUserId;
        
        const div = document.createElement('div');
        div.className = 'qa-reply';
        div.setAttribute('data-reply-id', reply.id);
        
        const displayName = reply.display_name || 'User';
        const firstLetter = displayName.charAt(0);
        
        // Format date
        const date = new Date(reply.date);
        const formattedDate = formatDate(date);
        
        // Determine avatar content - either image or first letter
        let avatarContent = '';
        if (reply.avatar_url) {
            avatarContent = `<img src="${reply.avatar_url}" alt="${displayName}">`;
        } else {
            avatarContent = firstLetter;
        }
        
        div.innerHTML = `
            <div class="user-avatar ${isAuthor ? 'author-avatar' : ''}">
                ${avatarContent}
            </div>
            <div class="qa-content">
                <div class="qa-author ${isAuthor ? 'is-author' : ''}">
                    ${displayName}
                    ${isAuthor ? '<span class="author-badge">Автор</span>' : ''}
                </div>
                <div class="qa-text">${reply.text}</div>
                <div class="qa-meta">${formattedDate}</div>
                <div class="qa-actions">
                    <button class="qa-like" data-liked="false">👍 <span>${reply.likes || 0}</span></button>
                </div>
            </div>
        `;
        
        return div;
    }
    
    /**
     * Show a login modal for non-authenticated users
     */
    function showLoginModal() {
        // Check if modal already exists
        if (document.getElementById('login-modal')) return;
        
        // Create modal element
        const modal = document.createElement('div');
        modal.id = 'login-modal';
        modal.className = 'login-modal';
        
        modal.innerHTML = `
            <div class="login-modal-content">
                <div class="login-modal-header">
                    <h3>Авторизация требуется</h3>
                    <span class="close-modal">&times;</span>
                </div>
                <div class="login-modal-body">
                    <p>Чтобы оставлять комментарии и вопросы, необходимо авторизоваться.</p>
                    <div class="login-modal-buttons">
                        <a href="/login/?next=${encodeURIComponent(window.location.pathname)}" class="login-btn">Войти</a>
                        <a href="/register/" class="register-btn">Зарегистрироваться</a>
                    </div>
                </div>
            </div>
        `;
        
        // Add to body
        document.body.appendChild(modal);
        
        // Add close button functionality
        const closeBtn = modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', function() {
            closeLoginModal(modal);
        });
        
        // Close when clicking outside
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeLoginModal(modal);
            }
        });
        
        // Add modal styles if they don't exist
        if (!document.getElementById('login-modal-styles')) {
            const style = document.createElement('style');
            style.id = 'login-modal-styles';
            style.textContent = `
                .login-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.7);
                    z-index: 1000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    animation: fadeIn 0.3s ease;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                
                .login-modal.fade-out {
                    animation: fadeOut 0.3s ease;
                }
                
                @keyframes fadeOut {
                    from { opacity: 1; }
                    to { opacity: 0; }
                }
                
                .login-modal-content {
                    background-color: var(--medium-bg, #07181f);
                    border-radius: 10px;
                    width: 90%;
                    max-width: 400px;
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
                }
                
                .login-modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 15px 20px;
                    border-bottom: 1px solid rgba(159, 37, 88, 0.2);
                }
                
                .login-modal-header h3 {
                    margin: 0;
                    color: var(--accent-color, #9f2558);
                }
                
                .close-modal {
                    font-size: 24px;
                    cursor: pointer;
                    color: var(--gray-color, #7a6563);
                    transition: color 0.3s;
                }
                
                .close-modal:hover {
                    color: var(--accent-color, #9f2558);
                }
                
                .login-modal-body {
                    padding: 20px;
                    color: var(--text-light, #fff8fa);
                }
                
                .login-modal-buttons {
                    display: flex;
                    gap: 10px;
                    margin-top: 20px;
                    justify-content: center;
                }
                
                .login-btn, .register-btn {
                    padding: 10px 20px;
                    border-radius: 20px;
                    text-decoration: none;
                    font-weight: bold;
                    transition: all 0.3s;
                }
                
                .login-btn {
                    background-color: transparent;
                    border: 2px solid var(--primary-color, #9f2558);
                    color: var(--primary-color, #9f2558);
                }
                
                .login-btn:hover {
                    background-color: rgba(159, 37, 88, 0.1);
                    transform: translateY(-3px);
                }
                
                .register-btn {
                    background-color: var(--accent-color, #9f2558);
                    border: none;
                    color: white;
                    box-shadow: 0 3px 10px rgba(159, 37, 88, 0.3);
                }
                
                .register-btn:hover {
                    background-color: #7d1e46;
                    transform: translateY(-3px);
                    box-shadow: 0 5px 15px rgba(159, 37, 88, 0.4);
                }
            `;
            
            document.head.appendChild(style);
        }
    }
    
    /**
     * Close login modal with animation
     */
    function closeLoginModal(modal) {
        modal.classList.add('fade-out');
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 300);
    }
    
    /**
     * Show a status message (success or error)
     */
    function showStatusMessage(message, type = 'info') {
        // Create message element
        const messageEl = document.createElement('div');
        messageEl.className = `status-message ${type}`;
        messageEl.textContent = message;
        
        // Style based on type
        if (type === 'error') {
            messageEl.style.backgroundColor = 'rgba(255, 71, 87, 0.1)';
            messageEl.style.color = '#ff4757';
            messageEl.style.borderLeft = '3px solid #ff4757';
        } else if (type === 'success') {
            messageEl.style.backgroundColor = 'rgba(46, 213, 115, 0.1)';
            messageEl.style.color = '#2ed573';
            messageEl.style.borderLeft = '3px solid #2ed573';
        } else {
            messageEl.style.backgroundColor = 'rgba(54, 162, 235, 0.1)';
            messageEl.style.color = '#36a2eb';
            messageEl.style.borderLeft = '3px solid #36a2eb';
        }
        
        // Apply common styles
        messageEl.style.padding = '10px 15px';
        messageEl.style.borderRadius = '8px';
        messageEl.style.marginBottom = '20px';
        messageEl.style.animation = 'fadeIn 0.3s ease';
        
        // Find insertion point (before the QA form)
        const insertBefore = qaForm || qaList;
        
        if (insertBefore && insertBefore.parentNode) {
            insertBefore.parentNode.insertBefore(messageEl, insertBefore);
            
            // Remove after 5 seconds
            setTimeout(() => {
                messageEl.style.animation = 'fadeOut 0.3s ease';
                setTimeout(() => {
                    if (messageEl.parentNode) {
                        messageEl.parentNode.removeChild(messageEl);
                    }
                }, 300);
            }, 5000);
        }
    }
    
    /**
     * Get the current user's display name
     */
    function getCurrentUserName() {
        // Try to get from the user dropdown if it exists
        const userNameEl = document.querySelector('.user-dropdown .user-name');
        if (userNameEl) {
            return userNameEl.textContent.trim();
        }
        
        // Fallback to username from avatar
        const userAvatar = document.querySelector('.comment-form .user-avatar');
        if (userAvatar) {
            return userAvatar.textContent.trim();
        }
        
        return 'User';
    }
    
    /**
     * Get the current user's initial for avatar
     */
    function getCurrentUserInitial() {
        // Try to get from the comment form avatar
        const userAvatar = document.querySelector('.comment-form .user-avatar');
        if (userAvatar) {
            return userAvatar.textContent.trim();
        }
        
        // Try to get from display name
        const displayName = getCurrentUserName();
        if (displayName) {
            return displayName.charAt(0);
        }
        
        return 'U';
    }
    
    /**
     * Get the current user's avatar (HTML content)
     */
    function getCurrentUserAvatar() {
        // Try to get avatar from the comment form
        const userAvatar = document.querySelector('.comment-form .user-avatar');
        if (userAvatar) {
            return userAvatar.innerHTML;
        }
        
        return getCurrentUserInitial();
    }
    
    /**
     * Format a date in a user-friendly way
     */
    function formatDate(date) {
        if (!(date instanceof Date) || isNaN(date)) {
            return 'Недавно';
        }
        
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);
        
        // Just now
        if (diffSec < 60) {
            return 'Только что';
        }
        
        // Minutes ago
        if (diffMin < 60) {
            return `${diffMin} ${getWordForm(diffMin, ['минуту', 'минуты', 'минут'])} назад`;
        }
        
        // Hours ago
        if (diffHour < 24) {
            return `${diffHour} ${getWordForm(diffHour, ['час', 'часа', 'часов'])} назад`;
        }
        
        // Days ago
        if (diffDay < 7) {
            return `${diffDay} ${getWordForm(diffDay, ['день', 'дня', 'дней'])} назад`;
        }
        
        // Regular date for older dates
        return date.toLocaleDateString();
    }
    
    /**
     * Get correct word form for Russian language based on number
     */
    function getWordForm(number, forms) {
        const cases = [2, 0, 1, 1, 1, 2];
        const mod100 = number % 100;
        const mod10 = number % 10;
        
        if (mod100 > 4 && mod100 < 20) {
            return forms[2];
        }
        
        return forms[cases[Math.min(mod10, 5)]];
    }
    
    /**
     * Create CSS animations for status messages if they don't exist
     */
    function createCssAnimations() {
        if (document.getElementById('qa-animations-style')) return;
        
        const style = document.createElement('style');
        style.id = 'qa-animations-style';
        
        style.textContent = `
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            @keyframes fadeOut {
                from { opacity: 1; transform: translateY(0); }
                to { opacity: 0; transform: translateY(-10px); }
            }
            
            .qa-like.liked {
                color: var(--accent-color, #9f2558);
                font-weight: bold;
            }
            
            .qa-like.liked span {
                font-weight: bold;
            }
            
            .reply-form {
                display: none;
            }
            
            .reply-form.visible {
                display: flex !important;
            }
        `;
        
        document.head.appendChild(style);
    }
    
    // Initialize CSS animations
    createCssAnimations();
});