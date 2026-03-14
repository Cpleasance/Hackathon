/**
 * Task Queue — list, create, and manage tasks.
 */
const Tasks = (() => {
    let allTasks = [];
    let skills = [];

    async function init() {
        document.getElementById('btn-new-task').addEventListener('click', openNewTaskModal);
        document.getElementById('task-filter').addEventListener('change', render);
        document.getElementById('task-form').addEventListener('submit', handleSubmit);
        skills = await API.getSkills();
        populateSkillSelect();
        render();
    }

    function populateSkillSelect() {
        const sel = document.getElementById('task-skill');
        sel.innerHTML = '<option value="">Select skill…</option>';
        skills.forEach(s => {
            sel.innerHTML += `<option value="${s.id}">${Utils.esc(s.name)}</option>`;
        });
    }

    async function render() {
        const filter = document.getElementById('task-filter').value;
        const container = document.getElementById('task-list');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            allTasks = await API.getTasks(filter);
            if (!allTasks.length) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📝</div><p>No tasks found</p></div>';
                return;
            }

            let html = '';
            allTasks.forEach(t => {
                const pc = Utils.priorityColor(t.priority_level);
                html += `
                <div class="task-item" data-id="${t.id}">
                    <div class="priority-dot" style="background: ${pc}"></div>
                    <div class="task-info">
                        <div class="task-title">${Utils.esc(t.task_name)}</div>
                        <div class="task-meta">
                            <span>${Utils.esc(t.customer_name || '—')}</span>
                            <span>${Utils.esc(t.required_skill_name || '')}</span>
                            ${t.preferred_start ? `<span style="color:var(--primary)">Prefers: ${Utils.formatDateTime(t.preferred_start)}</span>` : ''}
                            ${t.deadline ? `<span style="color:var(--warning)">Due: ${Utils.formatDateTime(t.deadline)}</span>` : ''}
                        </div>
                    </div>
                    <div class="task-duration">${Utils.durationLabel(t.duration_minutes)}</div>
                    ${Utils.statusBadge(t.status)}
                    <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">w${t.priority_weight}</div>
                </div>`;
            });
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p>Error: ${Utils.esc(err.error || 'Unknown')}</p></div>`;
        }
    }

    function openNewTaskModal() {
        document.getElementById('task-form').reset();
        Utils.openModal('modal-task');
    }

    async function handleSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const data = {
            task_name: form.task_name.value,
            duration_minutes: parseInt(form.duration_minutes.value),
            priority_level: parseInt(form.priority_level.value),
            priority_weight: parseInt(form.priority_weight.value),
            required_skill_id: form.required_skill_id.value,
            customer_name: form.customer_name.value,
            customer_notes: form.customer_notes.value,
            preferred_start: form.preferred_start.value ? new Date(form.preferred_start.value).toISOString().replace('Z', '+00:00') : null,
            deadline: form.deadline.value ? new Date(form.deadline.value).toISOString().replace('Z', '+00:00') : null,
        };

        try {
            await API.createTask(data);
            Utils.closeModal('modal-task');
            Utils.toast('Task created');
            render();
        } catch (err) {
            Utils.toast(err.error || 'Failed to create task', 'error');
        }
    }

    return { init, render };
})();
