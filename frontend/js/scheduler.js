/**
 * Schedule Board — renders a Gantt-style timeline for a single day.
 */
const ScheduleBoard = (() => {
    let currentDate = Utils.todayISO();
    const HOUR_START = 9;
    const HOUR_END = 17;
    const HOURS = [];
    for (let h = HOUR_START; h <= HOUR_END; h++) HOURS.push(h);

    let activeEmployees = [];
    let currentOverrideSchedule = null;

    function init() {
        document.getElementById('board-prev').addEventListener('click', () => navigate(-1));
        document.getElementById('board-next').addEventListener('click', () => navigate(1));
        document.getElementById('board-today').addEventListener('click', () => { currentDate = Utils.todayISO(); render(); });
        document.getElementById('btn-auto-schedule').addEventListener('click', runAutoSchedule);
        
        document.getElementById('override-form').addEventListener('submit', handleOverrideSubmit);
        
        // Use event delegation for clicking on appt blocks
        document.getElementById('schedule-rows').addEventListener('click', e => {
            const block = e.target.closest('.appt-block');
            if (block) {
                const schedId = block.dataset.scheduleId;
                if (schedId) openOverrideModal(schedId);
            }
        });

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
            
            activeEmployees = employees; // cache for the override dropdown

            // Fetch breaks for all employees, filtered to current day-of-week
            const breaksByEmp = {};
            const dow = (new Date(currentDate + 'T12:00:00Z').getUTCDay() + 6) % 7; // Mon=0
            await Promise.all(employees.map(async emp => {
                try {
                    const res = await API.getBreaks(emp.id);
                    breaksByEmp[emp.id] = (res.breaks || []).filter(b =>
                        b.is_recurring ? b.day_of_week === dow : b.override_date === currentDate
                    );
                } catch { breaksByEmp[emp.id] = []; }
            }));

            // Group schedules by employee
            const byEmp = {};
            schedules.forEach(s => {
                if (!byEmp[s.employee_id]) byEmp[s.employee_id] = [];
                byEmp[s.employee_id].push(s);
            });

            let html = '';
            employees.forEach(emp => {
                const empScheds = byEmp[emp.id] || [];
                html += renderEmployeeRow(emp, empScheds, breaksByEmp[emp.id] || []);
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

    function renderEmployeeRow(emp, schedules, breaks = []) {
        const totalMinutes = (HOUR_END - HOUR_START) * 60;

        let blocks = '';

        // Render break blocks first (underneath appointments)
        breaks.forEach(b => {
            const [sh, sm] = b.start_time.split(':').map(Number);
            const [eh, em] = b.end_time.split(':').map(Number);
            const startMin = (sh - HOUR_START) * 60 + sm;
            const endMin = (eh - HOUR_START) * 60 + em;
            const left = Math.max(0, (startMin / totalMinutes) * 100);
            const width = Math.max(1, ((endMin - startMin) / totalMinutes) * 100);
            blocks += `
                <div class="break-block"
                     style="left: ${left}%; width: ${width}%;"
                     title="Break: ${b.start_time}–${b.end_time}">
                    <div class="appt-name">Break</div>
                    <div class="appt-time">${b.start_time}–${b.end_time}</div>
                </div>`;
        });

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
                     style="left: ${left}%; width: ${width}%; cursor: pointer;"
                     title="Click to manually override\n\n${Utils.esc(s.task_name)} — ${Utils.esc(s.customer_name || '')}\n${Utils.formatTime(s.start_time)}–${Utils.formatTime(s.end_time)}"
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
            if (result.failed_count > 0) {
                const reasons = result.failed.map(f => `${f.task_name}: ${f.reason}`).join('\n');
                alert(`Scheduled ${result.scheduled_count} tasks. ${result.failed_count} tasks failed:\n\n${reasons}`);
            } else {
                Utils.toast(`Successfully scheduled ${result.scheduled_count} tasks.`, 'success');
            }
            render();
        } catch (err) {
            Utils.toast(err.error || 'Auto-schedule failed', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '⚡ Auto-Schedule';
        }
    }
    
    async function openOverrideModal(scheduleId) {
        try {
            const sched = await API.getSchedule(scheduleId);
            currentOverrideSchedule = sched;
            
            document.getElementById('override_task_name').value = sched.task_name + (sched.customer_name ? ` (${sched.customer_name})` : '');
            
            const empSelect = document.getElementById('override_employee');
            empSelect.innerHTML = activeEmployees.map(e => 
                `<option value="${e.id}" ${e.id === sched.employee_id ? 'selected' : ''}>${Utils.esc(e.name)}</option>`
            ).join('');
            
            // Format time correctly for input type="time"
            const st = new Date(sched.start_time);
            const et = new Date(sched.end_time);
            document.getElementById('override_start').value = Utils.formatTime(st);
            document.getElementById('override_end').value = Utils.formatTime(et);
            
            Utils.openModal('modal-override');
        } catch (err) {
            Utils.toast('Failed to load schedule details for override', 'error');
        }
    }
    
    async function handleOverrideSubmit(e) {
        e.preventDefault();
        if (!currentOverrideSchedule) return;
        
        const empId = document.getElementById('override_employee').value;
        const stStr = document.getElementById('override_start').value;
        const etStr = document.getElementById('override_end').value;
        
        // combine original date with new times
        const baseDate = currentDate; // YYYY-MM-DD
        const startIso = `${baseDate}T${stStr}:00Z`;
        const endIso = `${baseDate}T${etStr}:00Z`;
        
        try {
            await API.forceReassign(currentOverrideSchedule.id, {
                employee_id: empId,
                start_time: startIso,
                end_time: endIso
            });
            Utils.toast('Task reassigned successfully.', 'success');
            Utils.closeModal('modal-override');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Failed to force reassign', 'error');
        }
    }

    return { init, render, getCurrentDate: () => currentDate };
})();
