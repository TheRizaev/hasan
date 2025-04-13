document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the profile settings page
    const isProfileSettingsPage = window.location.href.includes('/profile/settings/');
    
    // Only initialize profile image handling on the settings page
    if (document.querySelector('.profile-avatar') && isProfileSettingsPage) {
        initProfileImageHandling();
    }
    
    // Подключение обработчика для кнопки настроек профиля
    const settingsButton = document.querySelector('.dropdown-item.settings-btn');
    if (settingsButton) {
        settingsButton.addEventListener('click', function() {
            window.location.href = '/profile/settings/';
        });
    }
});

function initProfileImageHandling() {
    // Находим форму загрузки профиля
    const profilePictureInput = document.getElementById('id_profile_picture');
    const profileAvatar = document.querySelector('.profile-avatar');
    const avatarPlaceholder = profileAvatar.querySelector('.avatar-placeholder');
    const avatarImage = profileAvatar.querySelector('img');
    
    // Добавляем визуальное оформление для загрузки даже если есть изображение
    createAvatarUploadInterface();
    
    // Обработчик изменения изображения
    if (profilePictureInput) {
        profilePictureInput.addEventListener('change', function(e) {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                
                // Проверяем тип файла
                if (!file.type.match('image.*')) {
                    showErrorMessage('Пожалуйста, выберите изображение');
                    return;
                }
                
                // Ограничение размера (5 МБ)
                if (file.size > 5 * 1024 * 1024) {
                    showErrorMessage('Размер изображения не должен превышать 5 МБ');
                    return;
                }
                
                // Создаем превью
                const reader = new FileReader();
                reader.onload = function(e) {
                    updateAvatarPreview(e.target.result);
                    
                    // Показываем кнопку подтверждения
                    const saveBtn = document.querySelector('.avatar-save-btn');
                    const selectBtn = document.querySelector('.avatar-select-btn');
                    if (saveBtn) saveBtn.style.display = 'block';
                    if (selectBtn) selectBtn.style.display = 'none';
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    function createAvatarUploadInterface() {
        // Если интерфейс уже существует, не создаем его снова
        if (document.querySelector('.avatar-upload-interface')) {
            return;
        }
        
        // Создаем интерфейс для загрузки аватара
        const uploadInterface = document.createElement('div');
        uploadInterface.className = 'avatar-upload-interface';
        
        // Добавляем иконку загрузки и текст
        uploadInterface.innerHTML = `
            <div class="avatar-upload-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 5V19" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M5 12H19" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </div>
            <div class="avatar-upload-text">Загрузить фото</div>
        `;
        
        // Добавляем интерфейс к аватару
        profileAvatar.appendChild(uploadInterface);
        
        // Стили для интерфейса загрузки
        const style = document.createElement('style');
        style.textContent = `
            .profile-avatar {
                position: relative;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .profile-avatar:hover {
                box-shadow: 0 8px 25px rgba(159, 37, 88, 0.4);
            }
            
            .avatar-upload-interface {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
                border-radius: 50%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            .profile-avatar:hover .avatar-upload-interface {
                opacity: 1;
            }
            
            .avatar-upload-icon {
                margin-bottom: 5px;
            }
            
            .avatar-upload-text {
                color: white;
                font-size: 12px;
                text-align: center;
                padding: 0 10px;
            }
            
            .avatar-preview-container {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s ease;
            }
            
            .avatar-preview-container.active {
                opacity: 1;
                visibility: visible;
            }
            
            .avatar-preview-content {
                background-color: var(--light-bg);
                border-radius: 15px;
                padding: 20px;
                max-width: 90%;
                width: 400px;
                text-align: center;
                position: relative;
            }
            
            .dark-theme .avatar-preview-content {
                background-color: var(--medium-bg);
                color: var(--text-light);
            }
            
            .avatar-preview {
                width: 150px;
                height: 150px;
                border-radius: 50%;
                margin: 20px auto;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
            
            .avatar-preview img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            
            .avatar-actions {
                display: flex;
                justify-content: center;
                gap: 10px;
                margin-top: 20px;
            }
            
            .avatar-action-btn {
                padding: 10px 20px;
                border-radius: 30px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s;
                font-size: 14px;
            }

            .avatar-select-btn {
                background-color: var(--accent-color);
                color: white;
                border: none;
            }
            
            .avatar-select-btn:hover {
                background-color: #7d1e46;
                transform: translateY(-3px);
            }

            .avatar-save-btn {
                background-color: #00a013;
                color: white;
                border: none;
            }
            
            .avatar-save-btn:hover {
                background-color: #00d419;
                transform: translateY(-3px);
            }
            
            .avatar-cancel-btn {
                background-color: transparent;
                color: var(--gray-color);
                border: 1px solid var(--gray-color);
            }
            
            .avatar-cancel-btn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                transform: translateY(-3px);
            }
            
            .avatar-remove-btn {
                background-color: #ff4757;
                color: white;
                border: none;
            }
            
            .avatar-remove-btn:hover {
                background-color: #d63031;
                transform: translateY(-3px);
            }
            
            .avatar-close {
                position: absolute;
                top: 10px;
                right: 10px;
                font-size: 24px;
                cursor: pointer;
                color: var(--gray-color);
                line-height: 1;
            }
            
            .error-message {
                color: #ff4757;
                margin-top: 10px;
                font-size: 14px;
            }
        `;
        document.head.appendChild(style);
        
        // Добавляем контейнер для превью аватара, если его еще нет
        if (!document.querySelector('.avatar-preview-container')) {
            const previewContainer = document.createElement('div');
            previewContainer.className = 'avatar-preview-container';
            
            // Определим изображение для предпросмотра 
            let previewImgSrc = '/static/default.png';
            if (avatarImage) {
                previewImgSrc = avatarImage.src;
            }
            
            previewContainer.innerHTML = `
                <div class="avatar-preview-content">
                    <div class="avatar-close">&times;</div>
                    <h3>Загрузка фото профиля</h3>
                    <div class="avatar-preview">
                        <img src="${previewImgSrc}" alt="Предпросмотр">
                    </div>
                    <div class="avatar-actions">
                        <label for="id_profile_picture" class="avatar-action-btn avatar-select-btn">Выбрать фото</label>
                        <button class="avatar-action-btn avatar-save-btn" style="display: none;">Подтвердить</button>
                        <button class="avatar-action-btn avatar-cancel-btn">Отмена</button>
                        <button class="avatar-action-btn avatar-remove-btn">Удалить фото</button>
                    </div>
                    <div class="error-message"></div>
                </div>
            `;
            document.body.appendChild(previewContainer);
            
            // Привязываем обработчики событий
            profileAvatar.addEventListener('click', function() {
                previewContainer.classList.add('active');
            });
            
            previewContainer.querySelector('.avatar-close').addEventListener('click', function() {
                previewContainer.classList.remove('active');
                resetAvatarButtons();
            });
            
            previewContainer.querySelector('.avatar-cancel-btn').addEventListener('click', function() {
                previewContainer.classList.remove('active');
                resetAvatarButtons();
            });
            
            // Обработчик для кнопки подтверждения
            const saveBtn = previewContainer.querySelector('.avatar-save-btn');
            if (saveBtn) {
                saveBtn.addEventListener('click', function() {
                    // Автоматически подтверждаем и отправляем форму
                    const settingsForm = document.querySelector('.profile-form');
                    if (settingsForm) {
                        // Создаем и показываем сообщение о сохранении
                        const saveMsg = document.createElement('div');
                        saveMsg.className = 'save-notification';
                        saveMsg.textContent = 'Сохранение изменений...';
                        saveMsg.style.position = 'fixed';
                        saveMsg.style.top = '20px';
                        saveMsg.style.right = '20px';
                        saveMsg.style.padding = '10px 20px';
                        saveMsg.style.backgroundColor = 'rgba(159, 37, 88, 0.9)';
                        saveMsg.style.color = 'white';
                        saveMsg.style.borderRadius = '5px';
                        saveMsg.style.zIndex = '9999';
                        document.body.appendChild(saveMsg);
                        
                        // Отправляем форму
                        settingsForm.submit();
                    } else {
                        // Если мы на странице просмотра профиля, а не настроек
                        const avatarForm = document.getElementById('avatar-form');
                        if (avatarForm) {
                            avatarForm.submit();
                        }
                    }
                    
                    // Закрываем превью
                    previewContainer.classList.remove('active');
                });
            }
            
            // Обработчик для удаления фото
            previewContainer.querySelector('.avatar-remove-btn').addEventListener('click', function() {
                // Обновляем превью до дефолтного изображения
                const previewImg = previewContainer.querySelector('.avatar-preview img');
                previewImg.src = '/static/default.png';
                
                // Очищаем input файла
                if (profilePictureInput) {
                    profilePictureInput.value = '';
                    
                    // Создаем скрытое поле для указания, что аватар нужно удалить
                    let removeAvatarInput = document.querySelector('input[name="remove_avatar"]');
                    if (!removeAvatarInput) {
                        removeAvatarInput = document.createElement('input');
                        removeAvatarInput.type = 'hidden';
                        removeAvatarInput.name = 'remove_avatar';
                        removeAvatarInput.value = 'true';
                        profilePictureInput.parentNode.appendChild(removeAvatarInput);
                    }
                }
                
                // Закрываем превью
                previewContainer.classList.remove('active');
                
                // При нахождении на странице настроек, можно автоматически сохранить изменения
                const settingsForm = document.querySelector('.profile-form');
                if (settingsForm && window.location.href.includes('/settings/')) {
                    // Создаем и показываем сообщение о сохранении
                    const saveMsg = document.createElement('div');
                    saveMsg.className = 'save-notification';
                    saveMsg.textContent = 'Сохранение изменений...';
                    saveMsg.style.position = 'fixed';
                    saveMsg.style.top = '20px';
                    saveMsg.style.right = '20px';
                    saveMsg.style.padding = '10px 20px';
                    saveMsg.style.backgroundColor = 'rgba(159, 37, 88, 0.9)';
                    saveMsg.style.color = 'white';
                    saveMsg.style.borderRadius = '5px';
                    saveMsg.style.zIndex = '9999';
                    document.body.appendChild(saveMsg);
                    
                    // Отправляем форму
                    settingsForm.submit();
                } else {
                    // Если мы на странице просмотра профиля, а не настроек
                    const avatarForm = document.getElementById('avatar-form');
                    if (avatarForm) {
                        avatarForm.submit();
                    }
                }
                
                // Сбрасываем кнопки
                resetAvatarButtons();
            });
            
            // Предотвращаем закрытие по клику на контент
            previewContainer.querySelector('.avatar-preview-content').addEventListener('click', function(e) {
                e.stopPropagation();
            });
            
            // Закрытие при клике на фон
            previewContainer.addEventListener('click', function() {
                previewContainer.classList.remove('active');
            });
        }
    }
    
    function updateAvatarPreview(src) {
        // Обновляем изображение в превью модального окна
        const previewImg = document.querySelector('.avatar-preview img');
        if (previewImg) {
            previewImg.src = src;
            
            // Показываем превью если оно не активно
            const previewContainer = document.querySelector('.avatar-preview-container');
            if (!previewContainer.classList.contains('active')) {
                previewContainer.classList.add('active');
            }
            
            // Очищаем сообщение об ошибке
            document.querySelector('.error-message').textContent = '';
            
            // Удаляем флаг удаления аватара, если он был
            const removeAvatarInput = document.querySelector('input[name="remove_avatar"]');
            if (removeAvatarInput) {
                removeAvatarInput.remove();
            }
        }
    }
    
    function resetAvatarButtons() {
        // Сбрасываем кнопки выбора и сохранения аватара
        const saveBtn = document.querySelector('.avatar-save-btn');
        const selectBtn = document.querySelector('.avatar-select-btn');
        if (saveBtn) saveBtn.style.display = 'none';
        if (selectBtn) selectBtn.style.display = 'block';
    }
    
    function showErrorMessage(message) {
        const errorElement = document.querySelector('.error-message');
        if (errorElement) {
            errorElement.textContent = message;
            
            // Показываем модальное окно, если оно не активно
            const previewContainer = document.querySelector('.avatar-preview-container');
            if (!previewContainer.classList.contains('active')) {
                previewContainer.classList.add('active');
            }
        }
    }
}