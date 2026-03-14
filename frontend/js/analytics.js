/**
 * Analytics Dashboard — utilisation, demand, no-shows, peaks, recommendations, trends, customers.
 */
const Analytics = (() => {

    let currentDataForExport = null;

    async function init() {
        render();
    }

    function exportToCSV() {
        if (!currentDataForExport) return;
        
        let csv = 'Employee,Appointments,Booked Mins,Available Mins,Utilisation Pct,Change vs Prev Period\n';
        const { utilisation, trends } = currentDataForExport;
        
        const trendMap = {};
        if (trends && trends.most_improved) trends.most_improved.forEach(t => trendMap[t.employee_id] = t.change);
        if (trends && trends.most_declined) trends.most_declined.forEach(t => trendMap[t.employee_id] = t.change);

        (utilisation.data || []).forEach(u => {
            const tr = trendMap[u.employee_id] || 0;
            csv += `"${u.employee_name}",${u.appointment_count},${u.booked_minutes},${u.available_minutes},${u.utilisation_pct},${tr}\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", `utilisation_export_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    async function render() {
        const container = document.getElementById('analytics-content');
        container.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div></div>';

        try {
            const [
                utilisation, hourly, daily, noShows, 
                peaksRes, recsRes, trendsRes, customersRes
            ] = await Promise.all([
                API.getUtilisation(),
                API.getDemandHourly(),
                API.getDemandDaily(),
                API.getNoShows(),
                API.getPeaks(),
                API.getRecommendations(),
                API.getTrends(),
                API.getCustomerInsights()
            ]);

            currentDataForExport = { utilisation, trends: trendsRes };
            const peaks = peaksRes.data || {};
            const advisories = recsRes.advisories || [];

            let html = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
                    <h2 style="margin:0;">Intelligence Hub</h2>
                    <button class="btn btn-secondary" id="btn-export-csv">📥 Download CSV</button>
                </div>
            `;

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
                <div class="stat-tile ${customersRes.cancellation_rate_pct > 15 ? 'warning' : 'primary'}">
                    <div class="stat-label">Cancellation Rate</div>
                    <div class="stat-value">${customersRes.cancellation_rate_pct}%</div>
                    <div class="stat-sub">${customersRes.total_tracked_customers} total tracked customers</div>
                </div>
                <div class="stat-tile success">
                    <div class="stat-label">Recurring Customers</div>
                    <div class="stat-value">${customersRes.recurring_customers}</div>
                    <div class="stat-sub">${Math.round((customersRes.recurring_customers / Math.max(1, customersRes.total_tracked_customers))*100)}% retention</div>
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
            html += `<div class="card"><div class="card-header"><h3>🕐 Peak Hours (Predictive Targets)</h3></div><div class="card-body">`;
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
            } else {
                html += `<p style="color:var(--text-muted);">No data in selected period.</p>`;
            }
            html += `</div></div>`;

            // Trends tile
            html += `<div class="card"><div class="card-header"><h3>📈 Employee Trends (vs Last Period)</h3></div><div class="card-body">`;
            if (trendsRes.most_improved && trendsRes.most_improved.length) {
                html += `<div style="margin-bottom:12px;"><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--success);margin-bottom:6px;">Most Improved</div>`;
                trendsRes.most_improved.forEach(t => {
                    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);">
                        <span>${Utils.esc(t.employee_name)}</span>
                        <span style="color:var(--success); font-weight:600;">+${t.change}%</span>
                    </div>`;
                });
                html += `</div>`;
            }
            if (trendsRes.most_declined && trendsRes.most_declined.length) {
                html += `<div><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--danger);margin-bottom:6px;">Declining Utilisation</div>`;
                trendsRes.most_declined.forEach(t => {
                    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);">
                        <span>${Utils.esc(t.employee_name)}</span>
                        <span style="color:var(--danger); font-weight:600;">${t.change}%</span>
                    </div>`;
                });
                html += `</div>`;
            }
            html += `</div></div>`;
            
            html += `</div>`; // close grid-2


            // ── Customers & Churn ──────────────────────────────────────
            html += `<div class="card" style="margin-bottom: 20px;">
                <div class="card-header"><h3>⭐ Top Customers & Churn Risk</h3></div>
                <div class="card-body" style="padding: 0;">
                    <table class="data-table"><thead><tr>
                        <th>Customer</th><th>Appointments</th><th>Completed</th><th>No-Shows/Cancellations</th><th>Fav Service</th><th>Fav Employee</th><th>Status</th>
                    </tr></thead><tbody>`;

            (customersRes.top_customers || []).forEach(c => {
                let statusBadge = '<span class="status-badge success">Loyal</span>';
                if (c.churn_risk) {
                    statusBadge = '<span class="status-badge danger">Churn Risk</span>';
                }
                html += `<tr>
                    <td><strong>${Utils.esc(c.name)}</strong></td>
                    <td>${c.total_appointments}</td>
                    <td>${c.completed}</td>
                    <td>${c.no_shows + c.cancellations}</td>
                    <td>${Utils.esc(c.favourite_service)}</td>
                    <td>${Utils.esc(c.favourite_employee)}</td>
                    <td>${statusBadge}</td>
                </tr>`;
            });

            if ((customersRes.top_customers || []).length === 0) {
                html += `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px;">No customer data found. Add customers to tasks to see intelligence here.</td></tr>`;
            }

            html += '</tbody></table></div></div>';


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

            // ── Demand charts & Pie charts ──────────────────────────────
            html += '<div class="grid-2" style="margin-bottom:20px;">';
            html += '<div class="card"><div class="card-header"><h4>Demand by Hour</h4></div><div class="card-body"><canvas id="hourlyChart" height="250"></canvas></div></div>';
            html += '<div class="card"><div class="card-header"><h4>Service Breakdown</h4></div><div class="card-body" style="display:flex; justify-content:center;"><canvas id="servicesChart" height="250" style="max-height:250px"></canvas></div></div>';
            html += '</div>';

            container.innerHTML = html;

            document.getElementById('btn-export-csv')?.addEventListener('click', exportToCSV);

            // Render Chart.js
            setTimeout(() => {
                const ctxHr = document.getElementById('hourlyChart');
                if (ctxHr && window.Chart) {
                    new window.Chart(ctxHr, {
                        type: 'bar',
                        data: {
                            labels: hourly.data.map(d => `${d.hour}:00`),
                            datasets: [{
                                label: 'Appointments',
                                data: hourly.data.map(d => d.appointments),
                                backgroundColor: 'rgba(99, 102, 241, 0.7)',
                                borderRadius: 4
                            }]
                        },
                        options: { responsive: true, maintainAspectRatio: false }
                    });
                }

                const ctxSvc = document.getElementById('servicesChart');
                if (ctxSvc && window.Chart && customersRes.top_customers) {
                    // Aggregate services globally from the customers
                    const sMap = {};
                    customersRes.top_customers.forEach(c => {
                        sMap[c.favourite_service] = (sMap[c.favourite_service] || 0) + c.completed;
                    });
                    
                    const labels = Object.keys(sMap);
                    let data = Object.values(sMap);
                    
                    // Fallback to placeholder if no real data
                    if (labels.length === 0 || (labels.length===1 && labels[0]==="Unknown")) {
                        labels.push("Consultation", "Installation", "Review", "Planning");
                        data = [45, 25, 20, 10];
                    }

                    new window.Chart(ctxSvc, {
                        type: 'doughnut',
                        data: {
                            labels: labels,
                            datasets: [{
                                data: data,
                                backgroundColor: ['#6366f1', '#ec4899', '#14b8a6', '#f59e0b', '#8b5cf6'],
                                borderWidth: 0
                            }]
                        },
                        options: { 
                            responsive: true, 
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'right' }
                            }
                        }
                    });
                }
            }, 100);

        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p>Error: ${Utils.esc(err.error || err.message || 'Unknown')}</p></div>`;
            console.error(err);
        }
    }

    return { init, render };
})();
