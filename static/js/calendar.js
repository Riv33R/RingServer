/* calendar.js — Exception calendar logic */

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth(); // 0-11
let overridesData = {}; // map of date "YYYY-MM-DD" -> override object

const monthNames = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
];

function fmtDate(y, m, d) {
    return `${y}-${String(m+1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

async function fetchOverrides(year, month) {
    try {
        const res = await fetch(`/api/calendar/${year}/${month + 1}`);
        if(res.ok) {
            const list = await res.json();
            overridesData = {};
            list.forEach(item => {
                overridesData[item.date] = item;
            });
            renderCalendar();
        }
    } catch(e) {
        showToast("Ошибка загрузки данных календаря", "error");
    }
}

function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    } else if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    }
    updateView();
}

function goToday() {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth();
    updateView();
}

function updateView() {
    document.getElementById('currentMonthLabel').textContent = `${monthNames[currentMonth]} ${currentYear}`;
    fetchOverrides(currentYear, currentMonth);
}

function renderCalendar() {
    const container = document.getElementById('calendarDays');
    container.innerHTML = '';
    
    // First day of month
    const firstDay = new Date(currentYear, currentMonth, 1);
    // 0 = Sun, 1 = Mon, ..., 6 = Sat
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek < 0) startDayOfWeek = 6; // Make Monday = 0
    
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    
    const todayStr = fmtDate(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
    
    // Empty cells before start of month
    for (let i = 0; i < startDayOfWeek; i++) {
        const div = document.createElement('div');
        div.className = 'cal-day empty';
        container.appendChild(div);
    }
    
    // Days
    for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = fmtDate(currentYear, currentMonth, d);
        const div = document.createElement('div');
        div.className = 'cal-day';
        
        if (dateStr === todayStr) div.classList.add('today');
        
        let html = `<div class="cal-day-num">${d}</div>`;
        
        const ovr = overridesData[dateStr];
        if (ovr) {
            div.classList.add('has-override');
            if (ovr.profile_id === null) {
                html += `<div class="cal-badge badge-none">🔕 Нет звонков</div>`;
            } else {
                html += `<div class="cal-badge" style="--bg:${ovr.color}">${ovr.profile_name}</div>`;
            }
            if (ovr.description) {
                html += `<div class="cal-desc">${ovr.description}</div>`;
            }
        }
        
        div.innerHTML = html;
        div.onclick = () => openModal(dateStr, ovr);
        container.appendChild(div);
    }
}

// -------- Modal --------
function openModal(dateStr, overrideData) {
    document.getElementById('overrideModal').classList.add('open');
    document.getElementById('fDate').value = dateStr;
    document.getElementById('modalDateLabel').textContent = dateStr;
    
    const select = document.getElementById('fProfile');
    const desc = document.getElementById('fDesc');
    const btnDel = document.getElementById('btnDeleteOverride');
    
    if (overrideData) {
        select.value = overrideData.profile_id === null ? "" : overrideData.profile_id;
        desc.value = overrideData.description || "";
        btnDel.style.display = 'inline-block';
    } else {
        select.value = "_default";
        desc.value = "";
        btnDel.style.display = 'none';
    }
    toggleDesc();
}

function closeModal(event) {
    if (!event || event.target.classList.contains('modal-backdrop') || event.currentTarget.classList.contains('modal-close')) {
        document.getElementById('overrideModal').classList.remove('open');
    }
}

function toggleDesc() {
    const val = document.getElementById('fProfile').value;
    document.getElementById('descGroup').style.display = (val === "_default") ? "none" : "block";
}

document.getElementById('overrideForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const dateStr = document.getElementById('fDate').value;
    const profileVal = document.getElementById('fProfile').value;
    const desc = document.getElementById('fDesc').value;
    
    if (profileVal === "_default") {
        // Just delete any existing override
        await doDelete(dateStr);
        return;
    }
    
    const payload = {
        date: dateStr,
        profile_id: profileVal === "" ? null : parseInt(profileVal),
        description: desc
    };
    
    try {
        const res = await fetch('/api/calendar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeModal();
            updateView();
            showToast('Сохранено', 'success');
        } else {
            showToast('Ошибка сохранения', 'error');
        }
    } catch(e) {
        showToast('Ошибка сети', 'error');
    }
});

async function deleteOverride() {
    const dateStr = document.getElementById('fDate').value;
    await doDelete(dateStr);
}

async function doDelete(dateStr) {
    try {
        const res = await fetch(`/api/calendar/${dateStr}`, {method: 'DELETE'});
        if (res.ok) {
            closeModal();
            updateView();
            showToast('Исключение удалено', 'success');
        }
    } catch(e) {
        showToast('Ошибка сети', 'error');
    }
}

// Init
document.addEventListener('DOMContentLoaded', updateView);
