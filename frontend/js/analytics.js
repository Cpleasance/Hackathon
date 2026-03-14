/**
 * Analytics Dashboard — utilisation, demand, no-shows, staffing.
 */
const Analytics = (() => {

    async function init() {
        render();
    }

    async function render() {
        const container = document.getElementById('analytics-content');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            const [utilisation, hourly, daily, noShows] = await Promise.all([
                API.getUtilisation(),
                API.getDemandHourly(),
                API.getDemandDaily(),
                API.getNoShows(),
            ]);

            let html = '';

            // No-show summary tile row
            html += `<div class="stat-grid">
                <div class="stat-tile accent">
                    <div class="stat-label">Period analysed</div>
                    <div class="stat-value" style="font-size:18px">${utilisation.start_date} → ${utilisation.end_date}</div>
                </div>
                <div class="stat-tile ${noShows.no_show_rate_pct > 10 ? 'danger' : 'success'}">
                    <div class="stat-label">No-show rate (${noShows.period_days}d)</div>
                    <div class="stat-value">${noShows.no_show_rate_pct}%</div>
                    <div class="stat-sub">${noShows.no_shows} of ${noShows.total_appointments} appointments</div>
                </div>
            </div>`;

            // Utilisation table
            html += `<div class="card" style="margin-bottom: 20px;">
                <div class="card-header"><h3>Employee Utilisation</h3></div>
                <div class="card-body" style="padding: 0;">
                    <table class="data-table"><thead><tr>
                        <th>Employee</th><th>Appointments</th><th>Booked</th><th>Available</th><th>Utilisation</th><th></th>
                    </tr></thead><tbody>`;

            (utilisation.data || []).forEach(u => {
                const pct = u.utilisation_pct;
                const color = pct > 85 ? 'var(--danger)' : pct > 60 ? 'var(--warning)' : 'var(--success)';
                html += `<tr>
                    <td><strong>${Utils.esc(u.employee_name)}</strong></td>
                    <td>${u.appointment_count}</td>
                    <td style="font-family: var(--font-mono)">${Utils.durationLabel(Math.round(u.booked_minutes))}</td>
                    <td style="font-family: var(--font-mono)">${Utils.durationLabel(u.available_minutes)}</td>
                    <td style="font-family: var(--font-mono); font-weight: 600">${pct}%</td>
                    <td><div class="util-bar-track"><div class="util-bar-fill" style="width: ${pct}%; background: ${color}"></div></div></td>
                </tr>`;
            });

            html += '</tbody></table></div></div>';

            // Charts row
            html += '<div class="grid-2">';

            // Hourly demand
            html += '<div class="chart-container"><h4>Demand by Hour</h4><div class="bar-chart">';
            const maxH = Math.max(1, ...hourly.data.map(d => d.appointments));
            hourly.data.forEach(d => {
                const h = Math.round((d.appointments / maxH) * 150);
                html += `<div class="bar-wrapper">
                    <div class="bar" style="height: ${h}px"></div>
                    <div class="bar-label">${d.hour}:00</div>
                </div>`;
            });
            html += '</div></div>';

            // Daily demand
            html += '<div class="chart-container"><h4>Demand by Day</h4><div class="bar-chart">';
            const maxD = Math.max(1, ...daily.data.map(d => d.appointments));
            daily.data.forEach(d => {
                const h = Math.round((d.appointments / maxD) * 150);
                html += `<div class="bar-wrapper">
                    <div class="bar" style="height: ${h}px"></div>
                    <div class="bar-label">${d.day}</div>
                </div>`;
            });
            html += '</div></div>';

            html += '</div>'; // close grid-2

            container.innerHTML = html;

        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p>Error: ${Utils.esc(err.error || 'Unknown')}</p></div>`;
        }
    }

    return { init, render };
})();
