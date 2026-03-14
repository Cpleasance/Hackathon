/**
 * App Controller — SPA routing & initialisation.
 */
const App = (() => {
    const views = ['schedule', 'tasks', 'employees', 'analytics', 'settings'];
    let currentView = 'schedule';

    function init() {
        // Wire up navigation
        document.querySelectorAll('.nav-item[data-view]').forEach(item => {
            item.addEventListener('click', () => switchView(item.dataset.view));
        });

        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) overlay.classList.remove('active');
            });
        });

        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.closest('.modal-overlay').classList.remove('active');
            });
        });

        // Init all modules
        ScheduleBoard.init();
        Tasks.init();
        Employees.init();
        Analytics.init();
        Settings.init();

        // Set initial view
        switchView('schedule');

        // Update header date
        document.getElementById('header-date').textContent = new Date().toLocaleDateString('en-GB', {
            weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
        });
    }

    function switchView(view) {
        if (!views.includes(view)) return;
        currentView = view;

        // Update nav
        document.querySelectorAll('.nav-item[data-view]').forEach(item => {
            item.classList.toggle('active', item.dataset.view === view);
        });

        // Show/hide views
        document.querySelectorAll('.view').forEach(v => {
            v.classList.toggle('active', v.id === `view-${view}`);
            // Also explicitly set display for robust hiding
            v.style.display = (v.id === `view-${view}`) ? 'block' : 'none';
        });

        // Update header title
        const titles = {
            schedule: 'Schedule Board',
            tasks: 'Task Queue',
            employees: 'Team',
            analytics: 'Analytics',
            settings: 'Settings',
        };
        document.getElementById('header-title').textContent = titles[view] || view;

        // Refresh relevant data
        if (view === 'schedule') ScheduleBoard.render();
        if (view === 'tasks') Tasks.render();
        if (view === 'employees') Employees.render();
        if (view === 'analytics') Analytics.render();
        if (view === 'settings') Settings.render();
    }

    return { init, switchView };
})();

document.addEventListener('DOMContentLoaded', App.init);
