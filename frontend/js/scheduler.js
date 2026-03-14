/**
 * Schedule Board — renders a Gantt-style timeline for a single day.
 */
const ScheduleBoard = (() => {
    let currentDate = Utils.todayISO();
    const HOUR_START = 9;
    const HOUR_END = 17;
    const HOURS = [];
    for (let h = HOUR_START; h <= HOUR_END; h++) HOURS.push(h);

    function init() {
        document.getElementById('board-prev').addEventListener('click', () => navigate(-1));
        document.getElementById('board-next').addEventListener('click', () => navigate(1));
        document.getElementById('board-today').addEventListener('click', () => { currentDate = Utils.todayISO(); render(); });
        document.getElementById('btn-auto-schedule').addEventListener('click', runAutoSchedule);
        render();
    }

    function navigate(offset) {
        currentDate = Utils.addDays(currentDate, offset);
        render();
    }

    async function render() {
        document.getElementById('board-date').textContent = Utils.formatDate(currentDate);

        const container = document.getElementById('schedule-rows');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            const [employees, schedules] = await Promise.all([
                API.getEmployees(),
                API.getSchedules(`date=${currentDate}`),
            ]);

            // Group schedules by employee
            const byEmp = {};
            schedules.forEach(s => {
                if (!byEmp[s.employee_id]) byEmp[s.employee_id] = [];
                byEmp[s.employee_id].push(s);
            });

            let html = '';
            employees.forEach(emp => {
                const empScheds = byEmp[emp.id] || [];
                html += renderEmployeeRow(emp, empScheds);
            });

            if (!employees.length) {
                html = '<div class="empty-state"><div class="empty-icon">📋</div><p>No employees found</p></div>';
            }

            container.innerHTML = html;
            updateStats(employees, schedules);
        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p>Error loading schedule: ${Utils.esc(err.error || 'Unknown')}</p></div>`;
        }
    }

    function renderEmployeeRow(emp, schedules) {
        const totalMinutes = (HOUR_END - HOUR_START) * 60;

        let blocks = '';
        schedules.forEach(s => {
            const startDt = new Date(s.start_time);
            const endDt = new Date(s.end_time);
            const startMin = (startDt.getUTCHours() - HOUR_START) * 60 + startDt.getUTCMinutes();
            const endMin = (endDt.getUTCHours() - HOUR_START) * 60 + endDt.getUTCMinutes();
            const left = Math.max(0, (startMin / totalMinutes) * 100);
            const width = Math.max(2, ((endMin - startMin) / totalMinutes) * 100);
            const pl = s.priority_level || 3;

            blocks += `
                <div class="appt-block priority-${pl} status-${s.status}"
                     style="left: ${left}%; width: ${width}%;"
                     title="${Utils.esc(s.task_name)} — ${Utils.esc(s.customer_name || '')}\n${Utils.formatTime(s.start_time)}–${Utils.formatTime(s.end_time)}"
                     data-schedule-id="${s.id}">
                    <div class="appt-name">${Utils.esc(s.customer_name || s.task_name)}</div>
                    <div class="appt-time">${Utils.formatTime(s.start_time)}</div>
                </div>`;
        });

        const skillNames = (emp.skills || []).map(s => s.skill_name).join(', ');
        return `
            <div class="employee-row">
                <div class="emp-info">
                    <div class="emp-name">${Utils.esc(emp.name)}</div>
                    <div class="emp-role">${Utils.esc(emp.role)}</div>
                </div>
                <div class="timeline">${blocks}</div>
            </div>`;
    }

    function updateStats(employees, schedules) {
        const active = schedules.filter(s => s.status !== 'cancelled' && s.status !== 'no_show');
        const bookedMins = active.reduce((sum, s) => sum + (s.duration_minutes || 0), 0);
        const totalAvail = employees.reduce((sum, e) => sum + (e.daily_minutes || 480), 0);

        document.getElementById('stat-appointments').textContent = active.length;
        document.getElementById('stat-booked-mins').textContent = Utils.durationLabel(bookedMins);
        document.getElementById('stat-utilisation').textContent =
            totalAvail > 0 ? Math.round((bookedMins / totalAvail) * 100) + '%' : '—';
        document.getElementById('stat-employees').textContent = employees.length;
    }

    async function runAutoSchedule() {
        const btn = document.getElementById('btn-auto-schedule');
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> Running…';
        try {
            const result = await API.autoSchedule({ date: currentDate });
            Utils.toast(`Scheduled ${result.scheduled_count} tasks (${result.failed_count} failed)`,
                        result.failed_count > 0 ? 'warning' : 'success');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Auto-schedule failed', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '⚡ Auto-Schedule';
        }
    }

    return { init, render, getCurrentDate: () => currentDate };
})();
