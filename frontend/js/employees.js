/**
 * Employee Management UI — list, create, edit, delete, and manage skills.
 */
const Employees = (() => {
    let allEmployees = [];
    let allSkills = [];
    let editingId = null;

    const STATUS_CONFIG = {
        active: { label: 'Active', color: 'var(--success)', dot: '●' },
        sick: { label: 'Sick', color: 'var(--warning)', dot: '🤒' },
        holiday: { label: 'Holiday', color: '#38bdf8', dot: '🏖️' },
        inactive: { label: 'Inactive', color: 'var(--text-muted)', dot: '○' },
    };

    async function init() {
        document.getElementById('btn-new-employee').addEventListener('click', openNewModal);
        document.getElementById('employee-form').addEventListener('submit', handleCreateSubmit);
        document.getElementById('employee-edit-form').addEventListener('submit', handleEditSubmit);
        document.querySelectorAll('#modal-employee-edit .modal-close').forEach(btn =>
            btn.addEventListener('click', () => Utils.closeModal('modal-employee-edit'))
        );
        document.getElementById('skill-assign-form').addEventListener('submit', handleSkillAssign);
        render();
    }

    async function render() {
        const container = document.getElementById('employee-list');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            [allEmployees, allSkills] = await Promise.all([
                API.getEmployees('active_only=false'),
                API.getSkills()
            ]);
            if (!allEmployees.length) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">👥</div><p>No employees</p></div>';
                return;
            }

            let html = `<table class="data-table"><thead><tr>
                <th>Name</th><th>Role</th><th>Daily Capacity</th><th>Status</th><th>Skills</th><th>Actions</th>
            </tr></thead><tbody>`;

            allEmployees.forEach(e => {
                const skillList = (e.skills || []).map(s =>
                    `<span style="background:var(--bg-tertiary);border-radius:4px;padding:2px 6px;font-size:11px;" title="Proficiency: ${s.proficiency_level}/5">
                        ${Utils.esc(s.skill_name)} <span style="color:var(--accent)">★${s.proficiency_level}</span>
                    </span>`
                ).join(' ') || '<span style="color:var(--text-muted)">None</span>';

                const st = STATUS_CONFIG[e.status] || STATUS_CONFIG['inactive'];

                // Holiday tooltip with return date
                let statusCell;
                if (e.status === 'holiday' && e.holiday_until) {
                    const d = new Date(e.holiday_until + 'T00:00:00');
                    const formatted = d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
                    statusCell = `<span style="color:${st.color};cursor:help;" title="On Holiday Till ${formatted}">${st.dot} ${st.label} (until ${formatted})</span>`;
                } else {
                    statusCell = `<span style="color:${st.color}">${st.dot} ${st.label}</span>`;
                }

                html += `<tr>
                    <td>
                        <strong>${Utils.esc(e.name)}</strong>
                        ${e.email ? `<br><span style="color:var(--text-muted);font-size:12px;">${Utils.esc(e.email)}</span>` : ''}
                    </td>
                    <td>${Utils.esc(e.role)}</td>
                    <td><span style="font-family: var(--font-mono)">${Utils.durationLabel(e.daily_minutes)}</span></td>
                    <td>${statusCell}</td>
                    <td style="max-width:240px"><div style="display:flex;gap:4px;flex-wrap:wrap;">${skillList}</div></td>
                    <td>
                        <div style="display:flex; gap: 4px;">
                            <button class="btn btn-secondary btn-sm" onclick="Employees.openEdit('${e.id}')" title="Edit">✏️</button>
                            <button class="btn btn-secondary btn-sm" onclick="Employees.openSkillModal('${e.id}')" title="Manage Skills">💡</button>
                            <button class="btn btn-secondary btn-sm" onclick="Employees.deleteEmployee('${e.id}','${Utils.esc(e.name)}')" title="Delete Employee" style="color:var(--danger, #ef4444)">🗑️</button>
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
        f.edit_holiday_until.value = emp.holiday_until || '';

        // Show/hide holiday date
        toggleHolidayField(emp.status);

        document.getElementById('modal-employee-edit-title').textContent = `Edit — ${emp.name}`;
        Utils.openModal('modal-employee-edit');
    }

    function toggleHolidayField(status) {
        const row = document.getElementById('holiday-until-row');
        if (row) row.style.display = status === 'holiday' ? '' : 'none';
    }

    async function openSkillModal(id) {
        const emp = allEmployees.find(e => e.id === id);
        if (!emp) return;

        document.getElementById('skill-modal-title').textContent = `Manage Skills — ${emp.name}`;
        document.getElementById('skill-modal-emp-id').value = id;

        // Populate skill dropdown
        const sel = document.getElementById('skill-assign-select');
        sel.innerHTML = allSkills.map(s => `<option value="${s.id}">${Utils.esc(s.name)}</option>`).join('');

        // Show current skills
        const list = document.getElementById('skill-current-list');
        if (emp.skills && emp.skills.length) {
            list.innerHTML = emp.skills.map(s => `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border);">
                    <span>${Utils.esc(s.skill_name)} <span style="color:var(--accent)">★${s.proficiency_level}/5</span></span>
                    <button class="btn btn-secondary btn-sm" onclick="Employees.removeSkill('${id}','${s.skill_id}')" style="color:var(--danger,#ef4444)">Remove</button>
                </div>`).join('');
        } else {
            list.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">No skills assigned yet.</p>';
        }

        Utils.openModal('modal-skill-assign');
    }

    async function removeSkill(empId, skillId) {
        try {
            await API.removeSkill(empId, skillId);
            Utils.toast('Skill removed', 'success');
            await render();
            openSkillModal(empId);
        } catch (err) {
            Utils.toast(err.error || 'Failed to remove skill', 'error');
        }
    }

    async function deleteEmployee(id, name) {
        if (!confirm(`Delete ${name}? This will also remove all their schedules. This cannot be undone.`)) return;
        try {
            await API.deleteEmployee(id);
            Utils.toast(`${name} deleted`, 'success');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Failed to delete employee', 'error');
        }
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
            if (confirm(`You are changing ${emp.name}'s status to ${newStatus}. Automatically cancel and reassign their upcoming tasks?`)) {
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
            holiday_until: (newStatus === 'holiday' && form.edit_holiday_until.value) ? form.edit_holiday_until.value : null,
            auto_reschedule: autoReschedule
        };
        try {
            await API.updateEmployee(editingId, data);
            Utils.closeModal('modal-employee-edit');
            Utils.toast('Employee updated', 'success');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Failed to update employee', 'error');
        }
    }

    async function handleSkillAssign(e) {
        e.preventDefault();
        const empId = document.getElementById('skill-modal-emp-id').value;
        const skillId = document.getElementById('skill-assign-select').value;
        const proficiency = parseInt(document.getElementById('skill-proficiency').value);
        try {
            await API.assignSkill(empId, { skill_id: skillId, proficiency_level: proficiency });
            Utils.toast('Skill assigned', 'success');
            await render();
            openSkillModal(empId);
        } catch (err) {
            Utils.toast(err.error || 'Failed to assign skill', 'error');
        }
    }

    return { init, render, openEdit, openSkillModal, removeSkill, deleteEmployee };
})();
