document.addEventListener('DOMContentLoaded', function() {
    // Only run on registration page
    if (!document.getElementById('id_username') || !document.querySelector('.auth-form')) return;
    
    // ===== USERNAME VALIDATION REMOVAL =====
    // Get the username input element
    const usernameInput = document.getElementById('id_username');
    
if (usernameInput) {
        usernameInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\s{2,}/g, ' ');

            if (value !== e.target.value) {
                e.target.value = value;
            }
        });
        
        if (!document.querySelector('.username-help')) {
            const usernameHelpText = document.createElement('small');
            usernameHelpText.className = 'form-help username-help';
            usernameInput.parentNode.appendChild(usernameHelpText);
        }
    }

    // ===== DATE OF BIRTH INPUT MASK =====
    const dateInput = document.getElementById('id_date_of_birth');
    
    if (dateInput) {
        // Apply input mask for date format: dd.mm.yyyy
        dateInput.setAttribute('placeholder', 'ДД.ММ.ГГГГ');
        
        // Add the masked input functionality
        dateInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, ''); // Remove non-digits
            
            // Insert dots automatically
            if (value.length > 0) {
                // Build the formatted date string
                let formattedDate = '';
                
                // Add day portion (max 2 digits)
                if (value.length > 0) {
                    let day = value.substring(0, 2);
                    // Validate day (1-31)
                    if (day.length === 1) {
                        formattedDate = day;
                    } else {
                        let dayNum = parseInt(day);
                        if (dayNum > 31) day = '31';
                        if (dayNum < 1) day = '01';
                        formattedDate = day;
                    }
                }
                
                // Add month portion (max 2 digits)
                if (value.length > 2) {
                    let month = value.substring(2, 4);
                    // Validate month (1-12)
                    let monthNum = parseInt(month);
                    if (monthNum > 12) month = '12';
                    if (monthNum < 1) month = '01';
                    formattedDate += '.' + month;
                } else if (value.length === 2) {
                    formattedDate += '.';
                }
                
                // Add year portion (max 4 digits)
                if (value.length > 4) {
                    let year = value.substring(4, 8);
                    formattedDate += '.' + year;
                } else if (value.length === 4) {
                    formattedDate += '.';
                }
                
                e.target.value = formattedDate;
            }
        });
        
        // Convert the date format from DD.MM.YYYY to YYYY-MM-DD for form submission
        const form = dateInput.closest('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                // Don't convert if empty
                if (!dateInput.value) return;
                
                // Parse the DD.MM.YYYY format
                const dateParts = dateInput.value.split('.');
                if (dateParts.length === 3) {
                    const day = dateParts[0];
                    const month = dateParts[1];
                    const year = dateParts[2];
                    
                    // Validate all parts have expected lengths
                    if (day.length === 2 && month.length === 2 && year.length === 4) {
                        // Convert to YYYY-MM-DD for backend processing
                        const isoDate = `${year}-${month}-${day}`;
                        
                        // Create a hidden input with the ISO format
                        const hiddenInput = document.createElement('input');
                        hiddenInput.type = 'hidden';
                        hiddenInput.name = 'date_of_birth_iso';
                        hiddenInput.value = isoDate;
                        form.appendChild(hiddenInput);
                    }
                }
            });
        }
    }

    // ===== PASSWORD STRENGTH INDICATOR =====
    const passwordInput = document.getElementById('id_password1');
    
    if (passwordInput) {
        // Create password strength indicator elements
        const strengthContainer = document.createElement('div');
        strengthContainer.className = 'password-strength-container';
        
        const strengthBar = document.createElement('div');
        strengthBar.className = 'password-strength-bar';
        
        const strengthLabel = document.createElement('div');
        strengthLabel.className = 'password-strength-label';
        strengthLabel.textContent = 'Надежность пароля';
        
        // Add elements to the DOM
        strengthContainer.appendChild(strengthBar);
        strengthContainer.appendChild(strengthLabel);
        passwordInput.parentNode.appendChild(strengthContainer);
        
        // Add CSS for the strength indicator
        const style = document.createElement('style');
        style.textContent = `
            .password-strength-container {
                margin-top: 10px;
                margin-bottom: 15px;
            }
            
            .password-strength-bar {
                height: 6px;
                border-radius: 3px;
                background-color: #e1e1e1;
                margin-bottom: 5px;
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
            }
            
            .password-strength-bar::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                height: 100%;
                width: 0;
                border-radius: 3px;
                transition: all 0.5s ease;
            }
            
            .password-strength-label {
                font-size: 12px;
                color: #666;
                display: flex;
                justify-content: space-between;
                transition: color 0.3s ease;
            }
            
            .password-strength-bar.weak::before {
                width: 25%;
                background-color: #ff4757;
                animation: pulse-red 2s infinite;
            }
            
            .password-strength-bar.medium::before {
                width: 50%;
                background-color: #ffa502;
                animation: pulse-yellow 2s infinite;
            }
            
            .password-strength-bar.good::before {
                width: 75%;
                background-color: #2ed573;
                animation: pulse-green 2s infinite;
            }
            
            .password-strength-bar.excellent::before {
                width: 100%;
                background: linear-gradient(90deg, #ffd700, #ff9f1a,rgb(166, 255, 0));
                background-size: 200% 100%;
                animation: gradient 2s ease infinite;
            }
            
            .password-strength-label.weak {
                color: #ff4757;
            }
            
            .password-strength-label.medium {
                color: #c4830a;
            }
            
            .password-strength-label.good {
                color: #2ed573;
            }
            
            .password-strength-label.excellent {
                color: #ffd700;
                font-weight: bold;
            }
            
            @keyframes pulse-red {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.7; }
            }
            
            @keyframes pulse-yellow {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.8; }
            }
            
            @keyframes pulse-green {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.8; }
            }
            
            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
        `;
        document.head.appendChild(style);
        
        // Function to calculate password strength
        function calculatePasswordStrength(password) {
            if (!password) return { score: 0, message: 'Введите пароль' };
            
            let score = 0;
            
            // Length check
            if (password.length >= 8) score += 1;
            if (password.length >= 12) score += 1;
            
            // Character type checks
            if (/[A-Z]/.test(password)) score += 1;
            if (/[a-z]/.test(password)) score += 1;
            if (/[0-9]/.test(password)) score += 1;
            if (/[^A-Za-z0-9]/.test(password)) score += 1;
            
            // Variety check
            const uniqueChars = new Set(password).size;
            if (uniqueChars > password.length * 0.7) score += 1;
            
            // Common patterns check (negative score)
            if (/123|abc|qwerty|password|admin/i.test(password)) score -= 2;
            
            // Define score ranges and labels
            let strength = '';
            let message = '';
            
            if (score <= 2) {
                strength = 'weak';
                message = 'Слабый - не рекомендуется';
            } else if (score <= 4) {
                strength = 'medium';
                message = 'Средний - допустимо';
            } else if (score <= 6) {
                strength = 'good';
                message = 'Хороший - рекомендуется';
            } else {
                strength = 'excellent';
                message = 'Отличный - даже хакер не взломает';
            }
            
            return { score, strength, message };
        }
        
        // Update password strength indicator
        function updateStrengthIndicator() {
            const password = passwordInput.value;
            const { strength, message } = calculatePasswordStrength(password);
            
            // Clear all classes
            strengthBar.className = 'password-strength-bar';
            strengthLabel.className = 'password-strength-label';
            
            // Add appropriate class
            if (strength) {
                strengthBar.classList.add(strength);
                strengthLabel.classList.add(strength);
                strengthLabel.innerHTML = `Надежность: <span>${message}</span>`;
                
                // Disable submit button for weak passwords
                const submitButton = document.querySelector('.auth-button[type="submit"]');
                if (submitButton) {
                    if (strength === 'weak' && password.length > 0) {
                        submitButton.disabled = true;
                        submitButton.title = 'Пароль слишком слабый';
                        submitButton.style.opacity = '0.7';
                    } else {
                        submitButton.disabled = false;
                        submitButton.title = '';
                        submitButton.style.opacity = '1';
                    }
                }
            } else {
                strengthLabel.textContent = 'Надежность пароля';
            }
        }
        
        // Listen for input changes
        passwordInput.addEventListener('input', updateStrengthIndicator);
        
        // Initial check
        updateStrengthIndicator();
    }
});