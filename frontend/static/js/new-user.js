/**
 * NeutArr - Account Settings
 * Handles account and API management inside the Settings section
 */

(function() {
    document.addEventListener('DOMContentLoaded', function() {
        if (!document.getElementById('accountSettingsPanel')) {
            return;
        }

        initAccountSettings();
        setupEventHandlers();
    });

    function initAccountSettings() {
        fetchUserInfo();
        fetchApiKey();
    }

    function setupEventHandlers() {
        const saveUsernameBtn = document.getElementById('saveUsername');
        if (saveUsernameBtn) {
            saveUsernameBtn.addEventListener('click', handleUsernameChange);
        }

        const savePasswordBtn = document.getElementById('savePassword');
        if (savePasswordBtn) {
            savePasswordBtn.addEventListener('click', handlePasswordChange);
        }

        const toggleApiKeyBtn = document.getElementById('toggleApiKey');
        if (toggleApiKeyBtn) {
            toggleApiKeyBtn.addEventListener('click', function() {
                const display = document.getElementById('apiKeyDisplay');
                if (!display) return;
                const isVisible = display.type === 'text';
                display.type = isVisible ? 'password' : 'text';
                this.innerHTML = isVisible
                    ? '<i class="fas fa-eye"></i> Show'
                    : '<i class="fas fa-eye-slash"></i> Hide';
            });
        }

        const copyApiKeyBtn = document.getElementById('copyApiKey');
        if (copyApiKeyBtn) {
            copyApiKeyBtn.addEventListener('click', handleCopyApiKey);
        }

        const rotateApiKeyBtn = document.getElementById('rotateApiKey');
        if (rotateApiKeyBtn) {
            rotateApiKeyBtn.addEventListener('click', handleRotateApiKey);
        }

    }

    async function handleUsernameChange() {
        const newUsername = document.getElementById('newUsername').value.trim();
        const currentPassword = document.getElementById('currentPasswordForUsernameChange').value;
        const statusElement = document.getElementById('usernameStatus');

        if (!newUsername || !currentPassword) {
            showStatus(statusElement, 'Please fill in all fields', 'error');
            return;
        }
        if (newUsername.length < 3) {
            showStatus(statusElement, 'Username must be at least 3 characters long', 'error');
            return;
        }

        try {
            const response = await authFetch('/api/auth/change-username', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: newUsername, password: currentPassword }),
            });
            const data = await response.json();

            if (response.ok) {
                // Server issues new tokens with the new username — store them
                if (data.access_token && data.refresh_token) {
                    AuthManager.setTokens(data.access_token, data.refresh_token, data.username || newUsername);
                }
                showStatus(statusElement, 'Username updated successfully', 'success');
                updateUsernameElements(newUsername);
                document.getElementById('newUsername').value = '';
                document.getElementById('currentPasswordForUsernameChange').value = '';
            } else {
                showStatus(statusElement, data.error || 'Failed to update username', 'error');
            }
        } catch (err) {
            console.error('Error updating username:', err);
            showStatus(statusElement, 'Error updating username: ' + err.message, 'error');
        }
    }

    async function handlePasswordChange() {
        const currentPassword = document.getElementById('currentPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const statusElement = document.getElementById('passwordStatus');

        if (!currentPassword || !newPassword || !confirmPassword) {
            showStatus(statusElement, 'Please fill in all fields', 'error');
            return;
        }
        if (newPassword !== confirmPassword) {
            showStatus(statusElement, 'New passwords do not match', 'error');
            return;
        }
        if (newPassword.length < 8) {
            showStatus(statusElement, 'Password must be at least 8 characters long', 'error');
            return;
        }

        try {
            const response = await authFetch('/api/auth/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
            });
            const data = await response.json();

            if (response.ok) {
                showStatus(statusElement, 'Password updated successfully', 'success');
                document.getElementById('currentPassword').value = '';
                document.getElementById('newPassword').value = '';
                document.getElementById('confirmPassword').value = '';
            } else {
                showStatus(statusElement, data.error || 'Failed to update password', 'error');
            }
        } catch (err) {
            console.error('Error updating password:', err);
            showStatus(statusElement, 'Error updating password: ' + err.message, 'error');
        }
    }

    function showStatus(element, message, type) {
        if (!element) return;
        element.textContent = message;
        element.className = 'status-message ' + (type === 'success' ? 'success' : 'error');
        element.style.display = 'block';
        setTimeout(() => { element.style.display = 'none'; }, 5000);
    }

    async function fetchUserInfo() {
        try {
            const response = await authFetch('/api/auth/user');
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            const data = await response.json();
            updateUsernameElements(data.username);
        } catch (err) {
            console.error('Error loading user info:', err);
            const usernameElement = document.getElementById('currentUsername');
            if (usernameElement) usernameElement.textContent = 'Error loading username';
        }
    }

    function updateUsernameElements(username) {
        if (!username) return;
        ['username', 'currentUsername'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = username;
        });
    }

    async function fetchApiKey() {
        try {
            const response = await authFetch('/api/auth/apikey');
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            const display = document.getElementById('apiKeyDisplay');
            if (display) display.value = data.api_key;
        } catch (err) {
            console.error('Error loading API key:', err);
        }
    }

    async function handleCopyApiKey() {
        const display = document.getElementById('apiKeyDisplay');
        const statusElement = document.getElementById('apiKeyStatus');
        if (!display || !display.value) return;
        try {
            await navigator.clipboard.writeText(display.value);
            showStatus(statusElement, 'API key copied to clipboard', 'success');
        } catch (err) {
            // Fallback for browsers without Clipboard API
            const prevType = display.type;
            display.type = 'text';
            display.select();
            document.execCommand('copy');
            display.type = prevType;
            showStatus(statusElement, 'API key copied to clipboard', 'success');
        }
    }

    async function handleRotateApiKey() {
        const statusElement = document.getElementById('apiKeyStatus');
        if (!confirm('Rotate the API key? Any scripts using the current key will need to be updated.')) return;
        try {
            const response = await authFetch('/api/auth/apikey/rotate', { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                const display = document.getElementById('apiKeyDisplay');
                if (display) display.value = data.api_key;
                if (typeof AuthManager !== 'undefined' && typeof AuthManager.setApiKey === 'function') {
                    AuthManager.setApiKey(data.api_key);
                }
                showStatus(statusElement, 'API key rotated — update any scripts using the old key', 'success');
            } else {
                showStatus(statusElement, data.error || 'Failed to rotate API key', 'error');
            }
        } catch (err) {
            console.error('Error rotating API key:', err);
            showStatus(statusElement, 'Error rotating API key: ' + err.message, 'error');
        }
    }

})();
