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
        // Set up show/hide replies functionality
        setupShowHideReplies();
    }

    /**
     * Set up show/hide replies functionality
     */
    function setupShowHideReplies() {
        console.log("Setting up show/hide replies functionality");
        
        // Find all show replies buttons
        const showRepliesBtns = document.querySelectorAll('.show-replies-btn');
        console.log(`Found ${showRepliesBtns.length} show/hide buttons`);
        
        // Add click handlers to each button
        showRepliesBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                // Get the current state
                const isShown = this.getAttribute('data-shown') === 'true';
                
                // Find the related replies container
                // It's the next element if it has the qa-replies class
                const repliesContainer = this.nextElementSibling;
                
                if (repliesContainer && repliesContainer.classList.contains('qa-replies')) {
                    const replyCount = repliesContainer.querySelectorAll('.qa-reply').length;
                    
                    if (isShown) {
                        // Hide replies
                        repliesContainer.style.display = 'none';
                        this.innerHTML = `Показать ответы (${replyCount})`;
                        this.setAttribute('data-shown', 'false');
                    } else {
                        // Show replies
                        repliesContainer.style.display = 'block';
                        this.innerHTML = 'Скрыть ответы';
                        this.setAttribute('data-shown', 'true');
                    }
                } else {
                    console.error("Could not find replies container after button");
                }
            });
        });
        
        // Also set up event delegation for dynamically added buttons
        document.addEventListener('click', function(e) {
            const btn = e.target.closest('.show-replies-btn');
            if (!btn) return; // Not a show replies button
            
            // Prevent handling if the button already has a direct event handler
            if (btn.getAttribute('data-has-handler') === 'true') return;
            
            // Mark this button as handled via delegation
            btn.setAttribute('data-has-handler', 'true');
            
            // Get current state
            const isShown = btn.getAttribute('data-shown') === 'true';
            
            // Find replies container (should be the next element)
            const repliesContainer = btn.nextElementSibling;
            
            if (repliesContainer && repliesContainer.classList.contains('qa-replies')) {
                const replyCount = repliesContainer.querySelectorAll('.qa-reply').length;
                
                if (isShown) {
                    // Hide replies
                    repliesContainer.style.display = 'none';
                    btn.innerHTML = `Показать ответы (${replyCount})`;
                    btn.setAttribute('data-shown', 'false');
                } else {
                    // Show replies
                    repliesContainer.style.display = 'block';
                    btn.innerHTML = 'Скрыть ответы';
                    btn.setAttribute('data-shown', 'true');
                }
            }
        });
    }

    function setupReplyButtonDelegation() {
        console.log("Setting up reply button delegation...");
        qaList.addEventListener('click', function(e) {
            // Handle direct comment reply buttons
            const replyBtn = e.target.closest('.qa-reply-btn');
            if (replyBtn && isAuthenticated) {
                e.preventDefault();
                const commentId = replyBtn.getAttribute('data-comment-id');
                console.log(`Reply button clicked for comment ${commentId}`);
                toggleReplyForm(commentId);
                return;
            }
            
            // Handle reply to reply buttons
            const replyToReplyBtn = e.target.closest('.qa-reply-to-reply-btn');
            if (replyToReplyBtn && isAuthenticated) {
                e.preventDefault();
                const commentId = replyToReplyBtn.getAttribute('data-comment-id');
                const username = replyToReplyBtn.getAttribute('data-username');
                
                console.log(`Reply to reply clicked - comment: ${commentId}, username: ${username}`);
                
                // Show the reply form
                toggleReplyForm(commentId);
                
                // Add username to input field
                const replyInput = document.getElementById(`reply-input-${commentId}`);
                if (replyInput) {
                    replyInput.value = `@${username} `;
                    replyInput.focus();
                    // Put cursor at the end
                    replyInput.selectionStart = replyInput.selectionEnd = replyInput.value.length;
                }
            }
            
            // Handle show/hide replies buttons created dynamically
            const showRepliesBtn = e.target.closest('.show-replies-btn');
            if (showRepliesBtn) {
                const isShown = showRepliesBtn.getAttribute('data-shown') === 'true';
                const repliesSection = showRepliesBtn.nextElementSibling;
                
                if (repliesSection && repliesSection.classList.contains('qa-replies')) {
                    const replyCount = repliesSection.querySelectorAll('.qa-reply').length;
                    
                    if (isShown) {
                        // Hide replies
                        repliesSection.style.display = 'none';
                        showRepliesBtn.innerHTML = `Показать ответы (${replyCount})`;
                        showRepliesBtn.setAttribute('data-shown', 'false');
                    } else {
                        // Show replies
                        repliesSection.style.display = 'block';
                        showRepliesBtn.innerHTML = 'Скрыть ответы';
                        showRepliesBtn.setAttribute('data-shown', 'true');
                    }
                }
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
            
            // Set up reply-to-reply buttons for existing replies
            const replies = comment.querySelectorAll('.qa-reply');
            replies.forEach(reply => {
                setupReplyToReplyButtons(reply);
            });
        });
    }
    
    /**
     * Set up reply-to-reply buttons for a specific reply
     */
    function setupReplyToReplyButtons(replyElement) {
        // Add reply button only if not already present
        if (!replyElement.querySelector('.qa-reply-to-reply-btn')) {
            const actionsDiv = replyElement.querySelector('.qa-actions');
            if (actionsDiv) {
                // Use user_id instead of display name for the mention
                const username = replyElement.querySelector('.qa-author').getAttribute('data-username') || 
                                replyElement.getAttribute('data-user-id');
                const commentId = replyElement.closest('.qa-item').getAttribute('data-comment-id');
                
                const replyBtn = document.createElement('button');
                replyBtn.className = 'qa-reply-to-reply-btn';
                replyBtn.textContent = 'Ответить';
                replyBtn.setAttribute('data-comment-id', commentId);
                replyBtn.setAttribute('data-username', username);
                
                actionsDiv.appendChild(replyBtn);
            }
        }    
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
                <div class="qa-text">${replyText}</div>
                <div class="qa-meta">${formattedDate}</div>
                <div class="qa-actions">
                    <button class="qa-like" data-liked="false">👍 <span>${reply.likes || 0}</span></button>
                    <button class="qa-reply-to-reply-btn" data-username="${displayName}">Ответить</button>
                </div>
            </div>
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
        
        // Add parent comment ID to the reply object
        reply.parentCommentId = commentId;
        
        // Create the reply element
        const replyElement = createReplyElement(reply);
        
        // Check if there's already a "show replies" button
        let showRepliesBtn = commentElement.querySelector('.show-replies-btn');
        
        // If replies were previously hidden, show them now for the new reply
        if (showRepliesBtn) {
            // Show replies container
            repliesContainer.style.display = 'block';
            
            // Update button text
            const replyCount = repliesContainer.querySelectorAll('.qa-reply').length + 1; // +1 for the new reply
            showRepliesBtn.innerHTML = 'Скрыть ответы';
            showRepliesBtn.setAttribute('data-shown', 'true');
        } else if (repliesContainer.querySelectorAll('.qa-reply').length === 0) {
            // This is the first reply, we'll add a show/hide button after adding the reply
            showRepliesBtn = document.createElement('button');
            showRepliesBtn.className = 'show-replies-btn';
            showRepliesBtn.innerHTML = 'Скрыть ответы';
            showRepliesBtn.setAttribute('data-shown', 'true');
            
            // Insert button before replies container
            commentElement.querySelector('.qa-content').insertBefore(showRepliesBtn, repliesContainer);
        }
        
        // Ensure replies container is visible when adding a new reply
        repliesContainer.style.display = 'block';
        
        // Add the reply to container
        repliesContainer.appendChild(replyElement);
        
        // Set up like functionality for the reply
        const likeButton = replyElement.querySelector('.qa-like');
        if (likeButton && isAuthenticated) {
            likeButton.addEventListener('click', function() {
                toggleLike(this);
            });
        }
        
        // Add click handler for reply-to-reply button
        const replyToReplyBtn = replyElement.querySelector('.qa-reply-to-reply-btn');
        if (replyToReplyBtn && isAuthenticated) {
            replyToReplyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                const parentCommentId = this.getAttribute('data-comment-id');
                const username = this.getAttribute('data-username');
                
                // Show the reply form
                toggleReplyForm(parentCommentId);
                
                // Add username to input field
                const replyInput = document.getElementById(`reply-input-${parentCommentId}`);
                if (replyInput) {
                    replyInput.value = `@${username} `;
                    replyInput.focus();
                    // Put cursor at the end
                    replyInput.selectionStart = replyInput.selectionEnd = replyInput.value.length;
                }
            });
        }

        document.querySelectorAll('.qa-reply-to-reply-btn').forEach(button => {
            button.addEventListener('click', function() {
                const commentId = this.getAttribute('data-comment-id');
                const username = this.getAttribute('data-username');
                
                // Show the reply form
                const replyForm = document.getElementById(`reply-form-${commentId}`);
                if (replyForm) {
                    replyForm.style.display = 'flex';
                    
                    // Add username to input field - ensure only one @ is added
                    const replyInput = document.getElementById(`reply-input-${commentId}`);
                    if (replyInput) {
                        // Remove any @ from the username if present
                        const cleanUsername = username.startsWith('@') ? username.substring(1) : username;
                        replyInput.value = `@${cleanUsername} `;
                        replyInput.focus();
                        // Put cursor at the end
                        replyInput.selectionStart = replyInput.selectionEnd = replyInput.value.length;
                    }
                }
            });
        });
        
        // Update the reply count if needed
        updateReplyCount(commentId);
    }
    
    /**
     * Update the reply count for a comment
     */
    function updateReplyCount(commentId) {
        const commentElement = document.querySelector(`.qa-item[data-comment-id="${commentId}"]`);
        if (!commentElement) return;
        
        const repliesContainer = commentElement.querySelector('.qa-replies');
        const showRepliesBtn = commentElement.querySelector('.show-replies-btn');
        
        if (repliesContainer && showRepliesBtn) {
            const replyCount = repliesContainer.querySelectorAll('.qa-reply').length;
            
            // Only update if currently showing the count
            if (showRepliesBtn.getAttribute('data-shown') === 'false') {
                showRepliesBtn.innerHTML = `Показать ответы (${replyCount})`;
            }
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
        div.setAttribute('data-user-id', reply.user_id); // Store user_id for referencing
        
        const displayName = reply.display_name || 'User';
        const username = reply.user_id || 'user'; // Get actual username for @mentions
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
        
        // Process text to handle @username replies
        let replyText = reply.text;
        if (replyText.startsWith('@')) {
            // Format @username mentions with a highlight
            const parts = replyText.split(' ');
            if (parts.length > 0 && parts[0].startsWith('@')) {
                const mention = parts[0];
                replyText = replyText.replace(mention, `<span class="user-mention">${mention}</span>`);
            }
        }
        
        // We need to get the parent comment ID from the calling context
        const parentCommentId = reply.parentCommentId; // This will be set by addReplyToComment
        
        div.innerHTML = `
            <div class="user-avatar ${isAuthor ? 'author-avatar' : ''}">
                ${avatarContent}
            </div>
            <div class="qa-content">
                <div class="qa-author ${isAuthor ? 'is-author' : ''}" data-username="${username}">
                    ${displayName}
                    ${isAuthor ? '<span class="author-badge">Автор</span>' : ''}
                </div>
                <div class="qa-text">${replyText}</div>
                <div class="qa-meta">${formattedDate}</div>
                <div class="qa-actions">
                    <button class="qa-like" data-liked="false">👍 <span>${reply.likes || 0}</span></button>
                    <button class="qa-reply-to-reply-btn" data-comment-id="${parentCommentId || ''}" data-username="${username}">Ответить</button>
                </div>
            </div>
        `;
        
        return div;
    }
});