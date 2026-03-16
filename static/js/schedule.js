/* schedule.js — Bell CRUD for the schedule editor page */

function switchProfile(pid) {
    window.location.href = '/schedule?profile_id=' + pid;
}

// -------- Modal helpers --------
function openAddModal() {
    document.getElementById('modalTitle').textContent = 'Добавить звонок';
    document.getElementById('bellId').value = '';
    document.getElementById('fHour').value = '';
    document.getElementById('fMinute').value = '';
    document.getElementById('fLabel').value = '';
    document.getElementById('fType').value = 'lesson';
    document.getElementById('fSound').value = '';
    document.getElementById('fDuration').value = '5';
    document.getElementById('modalSubmitBtn').textContent = 'Добавить';
    document.getElementById('bellModal').classList.add('open');
    document.getElementById('fHour').focus();
}

function openEditModal(bell) {
    document.getElementById('modalTitle').textContent = 'Редактировать звонок';
    document.getElementById('bellId').value = bell.id;
    document.getElementById('fHour').value = bell.hour;
    document.getElementById('fMinute').value = bell.minute;
    document.getElementById('fLabel').value = bell.label || '';
    document.getElementById('fType').value = bell.bell_type || 'lesson';
    document.getElementById('fSound').value = bell.sound_file || '';
    document.getElementById('fDuration').value = bell.duration || 5;
    document.getElementById('modalSubmitBtn').textContent = 'Сохранить';
    document.getElementById('bellModal').classList.add('open');
}

function closeModal(event) {
    if (!event || event.target.classList.contains('modal-backdrop') || event.currentTarget.classList.contains('modal-close')) {
        document.getElementById('bellModal').classList.remove('open');
    }
}

// -------- Form submission --------
document.getElementById('bellForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    if (!PROFILE_ID) return;

    const bid = document.getElementById('bellId').value;
    const payload = {
        hour: parseInt(document.getElementById('fHour').value),
        minute: parseInt(document.getElementById('fMinute').value),
        label: document.getElementById('fLabel').value.trim(),
        bell_type: document.getElementById('fType').value,
        sound_file: document.getElementById('fSound').value.trim(),
        duration: parseInt(document.getElementById('fDuration').value) || 5,
    };

    try {
        let res;
        if (bid) {
            res = await fetch(`/api/bells/${bid}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch(`/api/profiles/${PROFILE_ID}/bells`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        }

        if (res.ok) {
            showToast(bid ? 'Звонок обновлён' : 'Звонок добавлен', 'success');
            document.getElementById('bellModal').classList.remove('open');
            setTimeout(() => location.reload(), 600);
        } else {
            const data = await res.json();
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
});

// -------- Toggle bell enabled --------
async function toggleBell(bid, enabled) {
    try {
        const res = await fetch(`/api/bells/${bid}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled: enabled ? 1 : 0})
        });
        if (res.ok) {
            const row = document.getElementById(`bell-row-${bid}`);
            if (row) row.classList.toggle('row-disabled', !enabled);
            showToast(enabled ? 'Звонок включён' : 'Звонок выключен', 'info');
        }
    } catch (e) {
        showToast('Ошибка', 'error');
    }
}

// -------- Delete bell --------
async function deleteBell(bid) {
    if (!confirm('Удалить этот звонок?')) return;
    try {
        const res = await fetch(`/api/bells/${bid}`, {method: 'DELETE'});
        if (res.ok) {
            const row = document.getElementById(`bell-row-${bid}`);
            if (row) row.remove();
            showToast('Звонок удалён', 'success');
            // Show empty state if no rows
            const tbody = document.getElementById('bellTableBody');
            if (tbody && tbody.querySelectorAll('tr:not(#emptyRow)').length === 0) {
                location.reload();
            }
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
}

// -------- Export Schedule --------
function exportSchedule(pid) {
    if (!pid) return;
    window.location.href = `/api/profiles/${pid}/export`;
}

// -------- Import Schedule --------
async function importSchedule(pid, event) {
    if (!pid) return;
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        showToast('Загрузка...', 'info');
        const res = await fetch(`/api/profiles/${pid}/import`, {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        
        if (res.ok) {
            showToast(`Успешно импортировано звонков: ${data.count}`, 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast('Ошибка импорта: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch(e) {
        showToast('Ошибка при загрузке файла', 'error');
    } finally {
        // Reset the file input so the same file could be selected again if needed
        event.target.value = '';
    }
}
