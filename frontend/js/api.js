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
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(`${BASE}${path}`, opts);
        const data = await res.json();
        if (!res.ok) throw data;
        return data;
    }

    return {
        // Skills
        getSkills:          ()          => _req('GET', '/skills'),
        createSkill:        (d)         => _req('POST', '/skills', d),

        // Employees
        getEmployees:       (params='') => _req('GET', `/employees?include_skills=true&${params}`),
        getEmployee:        (id)        => _req('GET', `/employees/${id}`),
        createEmployee:     (d)         => _req('POST', '/employees', d),
        updateEmployee:     (id, d)     => _req('PUT', `/employees/${id}`, d),
        assignSkill:        (id, d)     => _req('POST', `/employees/${id}/skills`, d),

        // Tasks
        getTasks:           (status='') => _req('GET', `/tasks${status ? `?status=${status}` : ''}`),
        getTask:            (id)        => _req('GET', `/tasks/${id}`),
        createTask:         (d)         => _req('POST', '/tasks', d),
        updateTask:         (id, d)     => _req('PUT', `/tasks/${id}`, d),
        cancelTask:         (id)        => _req('DELETE', `/tasks/${id}`),

        // Schedules
        getSchedules:       (params='') => _req('GET', `/schedules?${params}`),
        createSchedule:     (d)         => _req('POST', '/schedules', d),
        updateStatus:       (id, d)     => _req('PATCH', `/schedules/${id}/status`, d),
        autoSchedule:       (d)         => _req('POST', '/schedules/auto-schedule', d),
        reportOverrun:      (id, d)     => _req('POST', `/schedules/${id}/overrun`, d),

        // Availability
        getAvailability:    (empId)     => _req('GET', `/availability/${empId}`),
        addAvailability:    (empId, d)  => _req('POST', `/availability/${empId}`, d),
        deleteAvailability: (recId)     => _req('DELETE', `/availability/record/${recId}`),

        // Analytics
        getUtilisation:     (params='') => _req('GET', `/analytics/utilisation?${params}`),
        getDemandHourly:    (params='') => _req('GET', `/analytics/demand/hourly?${params}`),
        getDemandDaily:     (params='') => _req('GET', `/analytics/demand/daily?${params}`),
        getNoShows:         (days=90)   => _req('GET', `/analytics/no-shows?lookback_days=${days}`),
        getStaffing:        (d)         => _req('GET', `/analytics/staffing?date=${d}`),

        // Settings
        getSettings:        ()          => _req('GET', '/settings'),
    };
})();
