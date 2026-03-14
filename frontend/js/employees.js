/**
 * Employee Management UI
 */
const Employees = (() => {
    let allEmployees = [];

    async function init() {
        document.getElementById('btn-new-employee').addEventListener('click', openNewModal);
        document.getElementById('employee-form').addEventListener('submit', handleSubmit);
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
                <th>Name</th><th>Role</th><th>Daily Capacity</th><th>Skills</th><th>Status</th>
            </tr></thead><tbody>`;

            allEmployees.forEach(e => {
                const skillList = (e.skills || []).map(s =>
                    `<span title="Proficiency: ${s.proficiency_level}">${Utils.esc(s.skill_name)}</span>`
                ).join(', ') || '—';

                html += `<tr>
                    <td><strong>${Utils.esc(e.name)}</strong></td>
                    <td>${Utils.esc(e.role)}</td>
                    <td><span style="font-family: var(--font-mono)">${Utils.durationLabel(e.daily_minutes)}</span></td>
                    <td>${skillList}</td>
                    <td>${e.is_active
                        ? '<span style="color: var(--success)">● Active</span>'
                        : '<span style="color: var(--text-muted)">○ Inactive</span>'
                    }</td>
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

    async function handleSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const data = {
            name: form.emp_name.value,
            role: form.emp_role.value,
            daily_minutes: parseInt(form.daily_minutes.value),
            email: form.emp_email.value || null,
            phone: form.emp_phone.value || null,
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

    return { init, render };
})();
