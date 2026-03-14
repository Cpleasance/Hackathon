/**
 * Shared UI utility functions.
 */
const Utils = (() => {

    // --- Toasts ---
    function toast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
    }

    // --- Date helpers ---
    function formatDate(d) {
        return new Date(d).toLocaleDateString('en-GB', {
            weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
        });
    }

    function formatTime(iso) {
        return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    }

    function formatDateISO(d) {
        const dt = new Date(d);
        return dt.toISOString().split('T')[0];
    }

    function addDays(dateStr, n) {
        const d = new Date(dateStr);
        d.setDate(d.getDate() + n);
        return formatDateISO(d);
    }

    function todayISO() {
        return formatDateISO(new Date());
    }

    // --- Modal ---
    function openModal(id) {
        document.getElementById(id).classList.add('active');
    }

    function closeModal(id) {
        document.getElementById(id).classList.remove('active');
    }

    // --- Priority colour ---
    function priorityColor(level) {
        const map = { 5: '#f05e5e', 4: '#f5a623', 3: '#6c8cff', 2: '#9598a4', 1: '#62656f' };
        return map[level] || map[3];
    }

    function priorityLabel(level) {
        const map = { 5: 'Critical', 4: 'High', 3: 'Medium', 2: 'Low', 1: 'Minimal' };
        return map[level] || 'Medium';
    }

    // --- Proficiency pips ---
    function proficiencyPips(level) {
        let html = '<div class="prof-bar">';
        for (let i = 1; i <= 5; i++) {
            html += `<div class="pip ${i <= level ? 'filled' : ''}"></div>`;
        }
        html += '</div>';
        return html;
    }

    // --- Status badge ---
    function statusBadge(status) {
        const label = status.replace('_', ' ');
        return `<span class="task-status status-${status}">${label}</span>`;
    }

    // --- Duration label ---
    function durationLabel(mins) {
        if (mins < 60) return `${mins}m`;
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        return m > 0 ? `${h}h ${m}m` : `${h}h`;
    }

    // --- Escape HTML ---
    function esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    return {
        toast, formatDate, formatTime, formatDateISO, addDays, todayISO,
        openModal, closeModal, priorityColor, priorityLabel,
        proficiencyPips, statusBadge, durationLabel, esc,
    };
})();
