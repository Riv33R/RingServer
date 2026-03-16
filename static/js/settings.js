/* settings.js — Settings page: config, audio upload, user management */

// -------- Save settings --------
document.getElementById('settingsForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const payload = {
        BELL_MODE: document.getElementById('sBellMode').value,
        RELAY_SCRIPT: document.getElementById('sRelayScript').value.trim(),
        DEFAULT_SOUND: document.getElementById('sDefaultSound').value,
        BELL_DURATION: parseInt(document.getElementById('sBellDuration').value) || 5,
    };

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast('Настройки сохранены', 'success');
        } else {
            const data = await res.json();
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
});

// -------- Save Telegram Settings --------
async function saveTelegramSettings(e) {
    if (e) e.preventDefault();
    const payload = {
        TELEGRAM_BOT_TOKEN: document.getElementById('sTelegramToken').value.trim(),
        TELEGRAM_BOT_PASSWORD: document.getElementById('sTelegramPassword').value.trim(),
    };

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast('Настройки Telegram сохранены', 'success');
        } else {
            const data = await res.json();
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
}

// -------- Test bell --------
async function testBell() {
    try {
        const res = await fetch('/api/test-bell', {method: 'POST'});
        const data = await res.json();
        if (res.ok) {
            showToast('🔔 Тестовый звонок дан (2 сек.)', 'info');
        } else {
            showToast('Ошибка: ' + (data.error || ''), 'error');
        }
    } catch(e) {
        showToast('Ошибка соединения', 'error');
    }
}

// -------- Upload audio --------
async function uploadAudio(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    showToast('Загружаем файл...', 'info');
    try {
        const res = await fetch('/api/upload-audio', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Файл "${data.filename}" загружен! Путь: ${data.path}`, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast('Ошибка: ' + (data.error || ''), 'error');
        }
    } catch(e) {
        showToast('Ошибка загрузки', 'error');
    }
    input.value = '';
}

// -------- Delete audio --------
async function deleteAudio(filename, elementId) {
    if (!confirm(`Удалить аудиофайл "${filename}"?`)) return;
    
    try {
        const res = await fetch(`/api/upload-audio/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        if (res.ok) {
            showToast(`Файл "${filename}" удален`, 'success');
            const el = document.getElementById(elementId);
            if (el) el.remove();
        } else {
            const data = await res.json();
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch(e) {
        showToast('Ошибка соединения', 'error');
    }
}

// -------- Change password --------
document.getElementById('changePasswordForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const old_password = document.getElementById('cpOld').value;
    const new_password = document.getElementById('cpNew').value;

    if (new_password.length < 4) {
        showToast('Пароль должен быть не менее 4 символов', 'error');
        return;
    }

    try {
        const res = await fetch('/api/change-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({old_password, new_password})
        });
        const data = await res.json();
        if (res.ok) {
            showToast('Пароль изменён', 'success');
            document.getElementById('cpOld').value = '';
            document.getElementById('cpNew').value = '';
        } else {
            showToast('Ошибка: ' + (data.error || ''), 'error');
        }
    } catch(e) {
        showToast('Ошибка соединения', 'error');
    }
});

// -------- User management --------
function openAddUser() {
    document.getElementById('addUserModal').classList.add('open');
    document.getElementById('nuUsername').focus();
}

function closeModal(event) {
    if (!event || event.target.classList.contains('modal-backdrop') || event.currentTarget.classList.contains('modal-close')) {
        document.getElementById('addUserModal').classList.remove('open');
    }
}

document.getElementById('addUserForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const payload = {
        username: document.getElementById('nuUsername').value.trim(),
        password: document.getElementById('nuPassword').value,
        is_admin: document.getElementById('nuIsAdmin').checked,
    };

    if (!payload.username || !payload.password) {
        showToast('Заполните все поля', 'error');
        return;
    }

    try {
        const res = await fetch('/api/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            showToast('Пользователь создан', 'success');
            setTimeout(() => location.reload(), 600);
        } else {
            showToast('Ошибка: ' + (data.error || ''), 'error');
        }
    } catch(e) {
        showToast('Ошибка соединения', 'error');
    }
});

async function deleteUser(uid, username) {
    if (!confirm(`Удалить пользователя "${username}"?`)) return;
    try {
        const res = await fetch(`/api/users/${uid}`, {method: 'DELETE'});
        if (res.ok) {
            showToast('Пользователь удалён', 'success');
            setTimeout(() => location.reload(), 600);
        }
    } catch(e) {
        showToast('Ошибка', 'error');
    }
}

// -------- Backup / Restore --------
function downloadBackup() {
    window.location.href = '/api/backup';
}

async function restoreBackup(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    if (!confirm('ВНИМАНИЕ! Это полностью перезапишет текущую базу данных и настройки. Продолжить?')) {
        event.target.value = '';
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        showToast('Восстановление...', 'info');
        const res = await fetch('/api/backup/restore', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        
        if (res.ok) {
            showToast('Успешно: ' + (data.message || 'система перезапущена'), 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch(e) {
        showToast('Ошибка при загрузке архива', 'error');
    } finally {
        event.target.value = '';
    }
}
