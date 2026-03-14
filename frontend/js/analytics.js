/**
 * Analytics Dashboard — utilisation, demand, no-shows, peaks, recommendations.
 */
const Analytics = (() => {

    async function init() {
        render();
    }

    async function render() {
        const container = document.getElementById('analytics-content');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            const [utilisation, hourly, daily, noShows, peaksRes, recsRes] = await Promise.all([
                API.getUtilisation(),
                API.getDemandHourly(),
                API.getDemandDaily(),
                API.getNoShows(),
                API.getPeaks(),
                API.getRecommendations(),
            ]);

            const peaks = peaksRes.data || {};
            const advisories = recsRes.advisories || [];

            let html = '';

            // ── Summary tiles ──────────────────────────────────────────
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

            // ── Recommendations ────────────────────────────────────────
            if (advisories.length) {
                html += `<div class="card" style="margin-bottom: 20px;">
                    <div class="card-header"><h3>📋 Calendar Manager Recommendations</h3></div>
                    <div class="card-body" style="display: flex; flex-direction: column; gap: 12px;">`;
                advisories.forEach(a => {
                    const colors = {
                        warning: { bg: 'rgba(255,165,0,0.08)', border: 'var(--warning)', icon: '⚠️' },
                        info:    { bg: 'rgba(99,102,241,0.08)', border: 'var(--primary)', icon: 'ℹ️' },
                        success: { bg: 'rgba(34,197,94,0.08)',  border: 'var(--success)', icon: '✅' },
                        tip:     { bg: 'rgba(56,189,248,0.08)', border: '#38bdf8',       icon: '💡' },
                    };
                    const c = colors[a.type] || colors.info;
                    html += `<div style="background:${c.bg};border-left:3px solid ${c.border};border-radius:8px;padding:12px 16px;">
                        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:${c.border};margin-bottom:4px;">${c.icon} ${Utils.esc(a.category)}</div>
                        <div style="color:var(--text-primary);line-height:1.5;">${Utils.esc(a.message)}</div>
                    </div>`;
                });
                html += `</div></div>`;
            }

            // ── Peak Times + Days ──────────────────────────────────────
            html += `<div class="grid-2" style="margin-bottom:20px;">`;

            // Peak hours tile
            html += `<div class="card"><div class="card-header"><h3>🕐 Peak Hours</h3></div><div class="card-body">`;
            if (peaks.peak_hours && peaks.peak_hours.length) {
                html += `<div style="margin-bottom:12px;"><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:6px;">Busiest</div>`;
                peaks.peak_hours.forEach((h, i) => {
                    const badges = ['🥇','🥈','🥉'];
                    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);">
                        <span>${badges[i] || ''} ${h.hour}:00 – ${h.hour+1}:00</span>
                        <span class="nav-badge" style="display:inline-block;">${h.appointments}</span>
                    </div>`;
                });
                html += `</div>`;
                if (peaks.off_peak_hours && peaks.off_peak_hours.length) {
                    html += `<div><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:6px;">Quietest</div>`;
                    peaks.off_peak_hours.forEach(h => {
                        html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);color:var(--text-secondary);">
                            <span>${h.hour}:00 – ${h.hour+1}:00</span>
                            <span>${h.appointments}</span>
                        </div>`;
                    });
                    html += `</div>`;
                }
            } else {
                html += `<p style="color:var(--text-muted);">No data in selected period.</p>`;
            }
            html += `</div></div>`;

            // Peak days tile
            html += `<div class="card"><div class="card-header"><h3>📅 Peak Days</h3></div><div class="card-body">`;
            if (peaks.peak_days && peaks.peak_days.length) {
                html += `<div style="margin-bottom:12px;"><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:6px;">Busiest</div>`;
                peaks.peak_days.forEach((d, i) => {
                    const badges = ['🥇','🥈','🥉'];
                    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);">
                        <span>${badges[i] || ''} ${d.day}</span>
                        <span class="nav-badge" style="display:inline-block;">${d.appointments}</span>
                    </div>`;
                });
                html += `</div>`;
                if (peaks.quiet_days && peaks.quiet_days.length) {
                    html += `<div><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:6px;">Quietest</div>`;
                    peaks.quiet_days.forEach(d => {
                        html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);color:var(--text-secondary);">
                            <span>${d.day}</span>
                            <span>${d.appointments}</span>
                        </div>`;
                    });
                    html += `</div>`;
                }
            } else {
                html += `<p style="color:var(--text-muted);">No data in selected period.</p>`;
            }
            html += `</div></div>`;

            html += `</div>`; // close grid-2

            // ── Utilisation table ──────────────────────────────────────
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

            // ── Demand charts ──────────────────────────────────────────
            html += '<div class="grid-2">';

            html += '<div class="chart-container"><h4>Demand by Hour</h4><div class="bar-chart">';
            const maxH = Math.max(1, ...hourly.data.map(d => d.appointments));
            hourly.data.forEach(d => {
                const h = Math.round((d.appointments / maxH) * 150);
                const isPeak = peaks.peak_hours && peaks.peak_hours.some(p => p.hour === d.hour);
                html += `<div class="bar-wrapper">
                    <div class="bar" style="height: ${h}px; background: ${isPeak ? 'var(--primary)' : ''}"></div>
                    <div class="bar-label">${d.hour}:00</div>
                </div>`;
            });
            html += '</div></div>';

            html += '<div class="chart-container"><h4>Demand by Day</h4><div class="bar-chart">';
            const maxD = Math.max(1, ...daily.data.map(d => d.appointments));
            daily.data.forEach(d => {
                const h = Math.round((d.appointments / maxD) * 150);
                const isPeak = peaks.peak_days && peaks.peak_days.some(p => p.day === d.day);
                html += `<div class="bar-wrapper">
                    <div class="bar" style="height: ${h}px; background: ${isPeak ? 'var(--primary)' : ''}"></div>
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
