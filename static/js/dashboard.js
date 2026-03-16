/* dashboard.js — Live clock, countdown, manual bell trigger */

let nextBellSeconds = null;
let nextBellTotalSeconds = null;
let bellTimeouts = [];

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        updateDashboard(data);
    } catch (e) {
        console.warn('Status fetch failed:', e);
    }
}

function updateDashboard(data) {
    // Profile badge
    const badge = document.getElementById('profileBadge');
    const profileName = document.getElementById('profileName');
    if (badge && data.active_profile) {
        badge.style.setProperty('--profile-color', data.active_profile.color);
        profileName.textContent = data.active_profile.name;
    } else if (profileName) {
        profileName.textContent = 'Нет профиля';
    }

    // Next bell
    const nbData = data.next_bell;
    const nbTime = document.getElementById('nextBellTime');
    const nbLabel = document.getElementById('nextBellLabel');
    const nbCard = document.getElementById('nextBellCard');

    if (nbData) {
        if (nbTime) nbTime.textContent = nbData.time;
        if (nbLabel) nbLabel.textContent = nbData.label || 'Следующий звонок';
        nextBellSeconds = nbData.seconds_left;
        if (!nextBellTotalSeconds || nextBellSeconds > nextBellTotalSeconds) {
            nextBellTotalSeconds = nextBellSeconds;
        }
    } else {
        if (nbTime) nbTime.textContent = '—:—';
        if (nbLabel) nbLabel.textContent = 'Звонков на сегодня больше нет';
        nextBellSeconds = null;
        nextBellTotalSeconds = null;
        updateCountdown();
    }

    // Highlight today's bell list
    highlightBells();
}

function updateCountdown() {
    const bar = document.getElementById('countdownBar');
    const text = document.getElementById('countdownText');
    if (!bar || !text) return;

    if (nextBellSeconds === null || nextBellSeconds <= 0) {
        bar.style.width = '0%';
        text.textContent = '—';
        return;
    }

    const pct = nextBellTotalSeconds > 0
        ? Math.max(0, Math.min(100, (1 - nextBellSeconds / nextBellTotalSeconds) * 100))
        : 0;

    bar.style.width = pct + '%';

    const h = Math.floor(nextBellSeconds / 3600);
    const m = Math.floor((nextBellSeconds % 3600) / 60);
    const s = nextBellSeconds % 60;

    if (h > 0) {
        text.textContent = `${h}ч ${m}м ${s}с`;
    } else if (m > 0) {
        text.textContent = `${m}м ${s}с`;
    } else {
        text.textContent = `${s}с`;
    }

    nextBellSeconds--;
}

function updateClock() {
    const timeEl = document.getElementById('clockTime');
    const dateEl = document.getElementById('clockDate');
    if (!timeEl || !dateEl) return;

    const now = new Date();
    timeEl.textContent = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    // Only update date if it changed to save DOM updates
    const dateStr = now.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    if (dateEl.textContent !== dateStr) {
        dateEl.textContent = dateStr;
    }
}

function highlightBells() {
    const now = new Date();
    const curMin = now.getHours() * 60 + now.getMinutes();

    const items = document.querySelectorAll('.bell-item');
    let foundNext = false;
    for (const item of items) {
        const h = parseInt(item.dataset.hour);
        const m = parseInt(item.dataset.minute);
        const bellMin = h * 60 + m;
        const indicator = item.querySelector('.bell-passed-indicator');

        item.classList.remove('bell-passed', 'bell-next');
        if (indicator) indicator.textContent = '';

        if (bellMin < curMin) {
            item.classList.add('bell-passed');
            if (indicator) indicator.textContent = '✓';
        } else if (!foundNext && bellMin >= curMin) {
            item.classList.add('bell-next');
            if (indicator) indicator.textContent = '▶';
            foundNext = true;
        }
    }
}

async function ringNow() {
    const btn = document.getElementById('btnRingNow');
    if (btn.disabled) return;

    btn.disabled = true;
    btn.classList.add('ringing');
    btn.querySelector('span:last-child').textContent = 'Звоним...';

    try {
        const res = await fetch('/api/ring-now', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (res.ok) {
            showToast('🔔 ' + (data.message || 'Звонок дан!'), 'success');
        } else {
            showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }

    setTimeout(() => {
        btn.disabled = false;
        btn.classList.remove('ringing');
        btn.querySelector('span:last-child').textContent = 'Дать звонок сейчас';
    }, 5000);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    // Re-fetch status from server every 30 seconds
    setInterval(fetchStatus, 30000);
    // Tick countdown every second
    setInterval(updateCountdown, 1000);
    // Tick big clock every second
    setInterval(updateClock, 1000);
    updateClock();
    // Refresh bell highlights every minute
    setInterval(highlightBells, 60000);
    highlightBells();
});
