/* profiles.js — Profile and week assignment management */

// -------- Modal helpers --------
function openCreateProfile() {
    document.getElementById('profileModalTitle').textContent = 'Создать профиль';
    document.getElementById('profileId').value = '';
    document.getElementById('fProfileName').value = '';
    document.getElementById('fProfileDesc').value = '';
    document.getElementById('fProfileColor').value = '#3b82f6';
    document.getElementById('profileModal').classList.add('open');
    document.getElementById('fProfileName').focus();
}

function openEditProfile(profile) {
    document.getElementById('profileModalTitle').textContent = 'Редактировать профиль';
    document.getElementById('profileId').value = profile.id;
    document.getElementById('fProfileName').value = profile.name;
    document.getElementById('fProfileDesc').value = profile.description || '';
    document.getElementById('fProfileColor').value = profile.color || '#3b82f6';
    document.getElementById('profileModal').classList.add('open');
    document.getElementById('fProfileName').focus();
}

function closeModal(event) {
    if (!event || event.target.classList.contains('modal-backdrop') || event.currentTarget.classList.contains('modal-close')) {
        document.getElementById('profileModal').classList.remove('open');
    }
}

function setColor(hex) {
    document.getElementById('fProfileColor').value = hex;
}

// -------- Form submission --------
document.getElementById('profileForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const pid = document.getElementById('profileId').value;
    const payload = {
        name: document.getElementById('fProfileName').value.trim(),
        description: document.getElementById('fProfileDesc').value.trim(),
        color: document.getElementById('fProfileColor').value,
    };

    if (!payload.name) {
        showToast('Введите название профиля', 'error');
        return;
    }

    try {
        let res;
        if (pid) {
            res = await fetch(`/api/profiles/${pid}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch('/api/profiles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        }
        if (res.ok) {
            showToast(pid ? 'Профиль обновлён' : 'Профиль создан', 'success');
            setTimeout(() => location.reload(), 600);
        } else {
            const data = await res.json();
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
});

// -------- Activate profile --------
async function activateProfile(pid) {
    try {
        const res = await fetch(`/api/profiles/${pid}/activate`, {method: 'POST'});
        if (res.ok) {
            showToast('Профиль активирован', 'success');
            setTimeout(() => location.reload(), 600);
        }
    } catch(e) {
        showToast('Ошибка', 'error');
    }
}

// -------- Delete profile --------
async function deleteProfile(pid, name) {
    if (!confirm(`Удалить профиль "${name}"? Все звонки в нём тоже будут удалены.`)) return;
    try {
        const res = await fetch(`/api/profiles/${pid}`, {method: 'DELETE'});
        if (res.ok) {
            const card = document.getElementById(`profile-card-${pid}`);
            if (card) card.remove();
            showToast('Профиль удалён', 'success');
        }
    } catch(e) {
        showToast('Ошибка соединения', 'error');
    }
}

// -------- Week assignment --------
async function setWeekAssignment(weekday, profileIdStr) {
    const profileId = profileIdStr === '' ? null : parseInt(profileIdStr);
    try {
        const res = await fetch('/api/week-assignments', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({weekday: weekday, profile_id: profileId})
        });
        if (res.ok) {
            const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
            showToast(`${dayNames[weekday]}: профиль обновлён`, 'info');
        }
    } catch(e) {
        showToast('Ошибка', 'error');
    }
}
