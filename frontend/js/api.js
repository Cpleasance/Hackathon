/**
 * API Client — all backend communication routes through here.
 * Every function returns a Promise.  Errors are surfaced with
 * a consistent { error: "..." } shape.
 */
const API = (() => {
    const BASE = '/api';

    async function _req(method, path, body = null) {
        const opts = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'hackathon-secret-key'
            },
        };
        if (body) opts.body = JSON.stringify(body);

        try {
            const res = await fetch(`${BASE}${path}`, opts);
            let data;
            const contentType = res.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                data = await res.json();
            } else {
                data = { error: `Server error (${res.status}): ${await res.text()}` };
            }
            if (!res.ok) throw data;
            return data;
        } catch (err) {
            // Already formatted {error: ...}
            if (err.error) throw err;
            // Native JS errors like Network Error or TypeError
            throw { error: err.message || 'API Communication failed' };
        }
    }

    async function completeTask(id) {
        return _req('PATCH', `/tasks/${id}`, { status: 'completed' });
    }

    return {
        // Skills
        getSkills: () => _req('GET', '/skills'),
        createSkill: (d) => _req('POST', '/skills', d),

        // Employees
        getEmployees: (params = '') => _req('GET', `/employees?include_skills=true&${params}`),
        getEmployee: (id) => _req('GET', `/employees/${id}`),
        createEmployee: (d) => _req('POST', '/employees', d),
        updateEmployee: (id, d) => _req('PUT', `/employees/${id}`, d),
        deleteEmployee: (id) => _req('DELETE', `/employees/${id}`),
        assignSkill: (id, d) => _req('POST', `/employees/${id}/skills`, d),
        removeSkill: (empId, skillId) => _req('DELETE', `/employees/${empId}/skills/${skillId}`),

        // Integrations
        triggerSync: (d) => _req('POST', '/calendar/sync', d),
        triggerEmail: (d) => _req('POST', '/calendar/email', d),

        // Tasks
        getTasks: (status = '') => _req('GET', `/tasks${status ? `?status=${status}` : ''}`),
        getTask: (id) => _req('GET', `/tasks/${id}`),
        createTask: (d) => _req('POST', '/tasks', d),
        updateTask: (id, d) => _req('PUT', `/tasks/${id}`, d),
        cancelTask: (id) => _req('DELETE', `/tasks/${id}`),

        // Schedules
        getSchedules: (params = '') => _req('GET', `/schedules?${params}`),
        getSchedule: (id) => _req('GET', `/schedules/${id}`),
        createSchedule: (d) => _req('POST', '/schedules', d),
        updateStatus: (id, d) => _req('PATCH', `/schedules/${id}/status`, d),
        forceReassign: (id, d) => _req('PUT', `/schedules/${id}/force`, d),
        autoSchedule: (d) => _req('POST', '/schedules/auto-schedule', d),
        reportOverrun: (id, d) => _req('POST', `/schedules/${id}/overrun`, d),

        // Availability
        getAvailability: (empId) => _req('GET', `/availability/${empId}`),
        addAvailability: (empId, d) => _req('POST', `/availability/${empId}`, d),
        deleteAvailability: (recId) => _req('DELETE', `/availability/record/${recId}`),

        // Analytics
        getUtilisation: (params = '') => _req('GET', `/analytics/utilisation?${params}`),
        getDemandHourly: (params = '') => _req('GET', `/analytics/demand/hourly?${params}`),
        getDemandDaily: (params = '') => _req('GET', `/analytics/demand/daily?${params}`),
        getNoShows: (days = 90) => _req('GET', `/analytics/no-shows?lookback_days=${days}`),
        getStaffing: (d) => _req('GET', `/analytics/staffing?date=${d}`),

        // Settings
        getSettings: () => _req('GET', '/settings'),
        saveSettings: (d) => _req('PUT', '/settings', d),

        // Analytics Extras
        getPeaks: (params = '') => _req('GET', `/analytics/peaks?${params}`),
        getRecommendations: (params = '') => _req('GET', `/analytics/recommendations?${params}`),
        getTrends: (params = '') => _req('GET', `/analytics/trends?${params}`),
        getCustomerInsights: (params = '') => _req('GET', `/analytics/customers?${params}`),
    };
})();
