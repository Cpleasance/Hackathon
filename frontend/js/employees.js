/**
 * Employee Management UI — list, create, and edit employees.
 */
const Employees = (() => {
    let allEmployees = [];
    let editingId = null;

    const STATUS_CONFIG = {
        active:   { label: 'Active',   color: 'var(--success)', dot: '●' },
        sick:     { label: 'Sick',     color: 'var(--warning)', dot: '🤒' },
        holiday:  { label: 'Holiday',  color: '#38bdf8',        dot: '🏖️' },
        inactive: { label: 'Inactive', color: 'var(--text-muted)', dot: '○' },
    };

    async function init() {
        document.getElementById('btn-new-employee').addEventListener('click', openNewModal);
        document.getElementById('employee-form').addEventListener('submit', handleCreateSubmit);

        // Edit modal wiring
        document.getElementById('employee-edit-form').addEventListener('submit', handleEditSubmit);
        document.querySelectorAll('#modal-employee-edit .modal-close').forEach(btn =>
            btn.addEventListener('click', () => Utils.closeModal('modal-employee-edit'))
        );

        render();
    }

    async function render() {
        const container = document.getElementById('employee-list');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            allEmployees = await API.getEmployees('active_only=false');
            if (!allEmployees.length) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">👥</div><p>No employees</p></div>';
                return;
            }

            let html = `<table class="data-table"><thead><tr>
                <th>Name</th><th>Role</th><th>Daily Capacity</th><th>Status</th><th>Actions</th>
            </tr></thead><tbody>`;

            allEmployees.forEach(e => {
                const skillList = (e.skills || []).map(s =>
                    `<span title="Proficiency: ${s.proficiency_level}">${Utils.esc(s.skill_name)}</span>`
                ).join(', ') || '—';

                const st = STATUS_CONFIG[e.status] || STATUS_CONFIG['inactive'];

                html += `<tr>
                    <td>
                        <strong>${Utils.esc(e.name)}</strong>
                        ${e.email ? `<br><span style="color:var(--text-muted);font-size:12px;">${Utils.esc(e.email)}</span>` : ''}
                        <div style="font-size:11px; margin-top:4px; color:var(--text-secondary)">💡 Skills: ${skillList}</div>
                    </td>
                    <td>${Utils.esc(e.role)}</td>
                    <td><span style="font-family: var(--font-mono)">${Utils.durationLabel(e.daily_minutes)}</span></td>
                    <td><span style="color:${st.color}">${st.dot} ${st.label}</span></td>
                    <td>
                        <div style="display:flex; gap: 4px; flex-wrap: wrap; max-width: 140px;">
                            <button class="btn btn-secondary btn-sm" onclick="Employees.openEdit('${e.id}')" title="Edit Employee">✏️</button>
                            <button class="btn btn-secondary btn-sm" onclick="Employees.triggerSync('${e.id}')" title="Sync Google Calendar">📅</button>
                            <button class="btn btn-secondary btn-sm" onclick="Employees.triggerEmail('${e.id}')" title="Send Weekly Stats Email" ${!e.email ? 'disabled style="opacity:0.5"' : ''}>📧</button>
                        </div>
                    </td>
                </tr>`;
            });

            html += '</tbody></table>';
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p>Error: ${Utils.esc(err.error || 'Unknown')}</p></div>`;
        }
    }

    async function triggerSync(id) {
        try {
            const res = await API.triggerSync({ employee_id: id, provider: 'google' });
            Utils.toast(res.message, 'success');
        } catch (err) {
            Utils.toast(err.error || 'Failed to sync calendar', 'error');
        }
    }
    
    async function triggerEmail(id) {
        try {
            const res = await API.triggerEmail({ employee_id: id, type: 'weekly_stats' });
            Utils.toast(res.message, 'success');
        } catch (err) {
            Utils.toast(err.error || 'Failed to send email', 'error');
        }
    }

    function openNewModal() {
        document.getElementById('employee-form').reset();
        Utils.openModal('modal-employee');
    }

    async function openEdit(id) {
        editingId = id;
        const emp = allEmployees.find(e => e.id === id);
        if (!emp) return;

        const f = document.getElementById('employee-edit-form');
        f.edit_name.value = emp.name || '';
        f.edit_role.value = emp.role || '';
        f.edit_daily_minutes.value = emp.daily_minutes || 480;
        f.edit_email.value = emp.email || '';
        f.edit_phone.value = emp.phone || '';
        f.edit_notes.value = emp.notes || '';
        f.edit_status.value = emp.status || 'active';

        document.getElementById('modal-employee-edit-title').textContent = `Edit — ${emp.name}`;
        Utils.openModal('modal-employee-edit');
    }

    async function handleCreateSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const data = {
            name: form.emp_name.value,
            role: form.emp_role.value,
            daily_minutes: parseInt(form.daily_minutes.value),
            email: form.emp_email.value || null,
            phone: form.emp_phone.value || null,
            status: 'active',
        };
        try {
            await API.createEmployee(data);
            Utils.closeModal('modal-employee');
            Utils.toast('Employee created');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Failed to create employee', 'error');
        }
    }

    async function handleEditSubmit(e) {
        e.preventDefault();
        if (!editingId) return;
        const form = e.target;
        
        const newStatus = form.edit_status.value;
        const emp = allEmployees.find(emp => emp.id === editingId);
        let autoReschedule = false;
        
        if (emp && emp.status === 'active' && ['sick', 'holiday', 'inactive'].includes(newStatus)) {
            // They are going offline. Ask if we should reschedule.
            if (confirm(`You are changing ${emp.name}'s status to ${newStatus}. Do you want to automatically cancel and reassign their upcoming scheduled tasks?`)) {
                autoReschedule = true;
            }
        }
        
        const data = {
            name: form.edit_name.value,
            role: form.edit_role.value,
            daily_minutes: parseInt(form.edit_daily_minutes.value),
            email: form.edit_email.value || null,
            phone: form.edit_phone.value || null,
            notes: form.edit_notes.value || null,
            status: newStatus,
            auto_reschedule: autoReschedule
        };
        try {
            await API.updateEmployee(editingId, data);
            Utils.closeModal('modal-employee-edit');
            Utils.toast(autoReschedule ? 'Employee updated and tasks rescheduled' : 'Employee updated', 'success');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Failed to update employee', 'error');
        }
    }

    return { init, render, openEdit, triggerSync, triggerEmail };
})();
