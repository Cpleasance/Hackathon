-- =============================================================
--  WORKFLOW SCHEDULING SYSTEM — MySQL 8.0+ Schema
--  Designed for appointment-based service businesses
-- =============================================================

CREATE DATABASE IF NOT EXISTS workflow_scheduler;
USE workflow_scheduler;

SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================
--  DROP TABLES (clean slate for re-runs)
-- =============================================================
DROP TABLE IF EXISTS task_schedules;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS employee_availability;
DROP TABLE IF EXISTS employee_skills;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS skills;

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================
--  CORE TABLES
-- =============================================================

-- -----------------------------------------------------------
--  1. SKILLS
--     Normalised skill catalogue — employees and tasks both
--     reference this table.
-- -----------------------------------------------------------
CREATE TABLE skills (
    id          CHAR(36)     NOT NULL DEFAULT (UUID()),
    name        VARCHAR(100) NOT NULL,
    category    VARCHAR(60)  NULL,          -- e.g. 'hair', 'colour', 'clinical'
    description TEXT         NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_skills_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
--  2. EMPLOYEES
-- -----------------------------------------------------------
CREATE TABLE employees (
    id              CHAR(36)     NOT NULL DEFAULT (UUID()),
    name            VARCHAR(150) NOT NULL,
    role            VARCHAR(100) NOT NULL,
    daily_minutes   INT          NOT NULL DEFAULT 480,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    email           VARCHAR(255) NULL,
    phone           VARCHAR(30)  NULL,
    notes           TEXT         NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_employees_email UNIQUE (email),
    CONSTRAINT chk_daily_minutes  CHECK (daily_minutes BETWEEN 60 AND 720)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
--  3. EMPLOYEE_SKILLS  (many-to-many: employees <-> skills)
--     proficiency_level lets the scheduler prefer the best
--     qualified employee for a task when multiple can do it.
-- -----------------------------------------------------------
CREATE TABLE employee_skills (
    employee_id         CHAR(36)  NOT NULL,
    skill_id            CHAR(36)  NOT NULL,
    proficiency_level   TINYINT   NOT NULL DEFAULT 1,
    certified_date      DATE      NULL,
    PRIMARY KEY (employee_id, skill_id),
    CONSTRAINT chk_proficiency CHECK (proficiency_level BETWEEN 1 AND 5),
    CONSTRAINT fk_eskills_employee FOREIGN KEY (employee_id)
        REFERENCES employees(id) ON DELETE CASCADE,
    CONSTRAINT fk_eskills_skill    FOREIGN KEY (skill_id)
        REFERENCES skills(id)    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
--  4. EMPLOYEE_AVAILABILITY
--     Supports both recurring weekly schedules and one-off
--     date-specific overrides (e.g. holiday cover, half-days).
--     is_recurring = 1  -> day_of_week governs the pattern
--     is_recurring = 0  -> override_date is the exact date
-- -----------------------------------------------------------
CREATE TABLE employee_availability (
    id              CHAR(36)   NOT NULL DEFAULT (UUID()),
    employee_id     CHAR(36)   NOT NULL,
    day_of_week     TINYINT    NULL,        -- 0=Sun ... 6=Sat
    start_time      TIME       NOT NULL,
    end_time        TIME       NOT NULL,
    is_recurring    TINYINT(1) NOT NULL DEFAULT 1,
    override_date   DATE       NULL,        -- set only when is_recurring = 0
    is_available    TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    CONSTRAINT chk_dow        CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT chk_time_order CHECK (end_time > start_time),
    -- Enforce that recurring rows have day_of_week and no override_date,
    -- and non-recurring rows have override_date set.
    CONSTRAINT chk_override_xor CHECK (
        (is_recurring = 1 AND day_of_week IS NOT NULL AND override_date IS NULL) OR
        (is_recurring = 0 AND override_date IS NOT NULL)
    ),
    CONSTRAINT fk_avail_employee FOREIGN KEY (employee_id)
        REFERENCES employees(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
--  5. TASKS
--     Each row is a single appointment/work item awaiting
--     scheduling.  priority_weight (1-100) gives the
--     optimisation algorithm a numeric score to maximise.
-- -----------------------------------------------------------
CREATE TABLE tasks (
    id                  CHAR(36)     NOT NULL DEFAULT (UUID()),
    task_name           VARCHAR(200) NOT NULL,
    duration_minutes    INT          NOT NULL,
    priority_level      TINYINT      NOT NULL DEFAULT 3,
    priority_weight     INT          NOT NULL DEFAULT 50,
    required_skill_id   CHAR(36)     NOT NULL,
    preferred_start     DATETIME     NULL,   -- soft preference
    deadline            DATETIME     NULL,   -- hard deadline (NULL = flexible)
    status              ENUM('unassigned','scheduled','in_progress','completed','cancelled')
                                     NOT NULL DEFAULT 'unassigned',
    customer_name       VARCHAR(150) NULL,
    customer_notes      TEXT         NULL,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT chk_duration        CHECK (duration_minutes > 0),
    CONSTRAINT chk_priority_level  CHECK (priority_level BETWEEN 1 AND 5),
    CONSTRAINT chk_priority_weight CHECK (priority_weight BETWEEN 1 AND 100),
    CONSTRAINT fk_tasks_skill FOREIGN KEY (required_skill_id)
        REFERENCES skills(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
--  6. TASK_SCHEDULES
--     One row per assigned task.  The UNIQUE constraint on
--     task_id enforces the "one employee per task" rule.
--
--     NOTE: MySQL does not support range exclusion constraints.
--     Overlap prevention is enforced at the application layer
--     using the query below before every INSERT:
--
--     SELECT id FROM task_schedules
--     WHERE employee_id = ?
--       AND scheduled_date = ?
--       AND status NOT IN ('cancelled', 'no_show')
--       AND start_time < ?   -- new end_time
--       AND end_time   > ?   -- new start_time
--     LIMIT 1;
--
--     If any row is returned, the slot is taken.
-- -----------------------------------------------------------
CREATE TABLE task_schedules (
    id              CHAR(36)   NOT NULL DEFAULT (UUID()),
    task_id         CHAR(36)   NOT NULL,
    employee_id     CHAR(36)   NOT NULL,
    scheduled_date  DATE       NOT NULL,
    start_time      DATETIME   NOT NULL,
    end_time        DATETIME   NOT NULL,
    status          ENUM('confirmed','in_progress','completed','cancelled','no_show')
                               NOT NULL DEFAULT 'confirmed',
    assigned_at     DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME   NULL,
    notes           TEXT       NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_task_schedule  UNIQUE (task_id),   -- one employee per task
    CONSTRAINT chk_sched_order   CHECK (end_time > start_time),
    CONSTRAINT chk_sched_date    CHECK (DATE(start_time) = scheduled_date),
    CONSTRAINT fk_sched_task     FOREIGN KEY (task_id)
        REFERENCES tasks(id)     ON DELETE CASCADE,
    CONSTRAINT fk_sched_employee FOREIGN KEY (employee_id)
        REFERENCES employees(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================
--  INDEXES
-- =============================================================

-- Tasks awaiting assignment — core scheduling queue
CREATE INDEX idx_tasks_unassigned_priority
    ON tasks (status, priority_weight DESC, deadline ASC);

-- Look up tasks by required skill
CREATE INDEX idx_tasks_required_skill
    ON tasks (required_skill_id);

-- Employee schedule lookup by date
CREATE INDEX idx_schedules_employee_date
    ON task_schedules (employee_id, scheduled_date);

-- All appointments for a given date (daily dashboard)
CREATE INDEX idx_schedules_date
    ON task_schedules (scheduled_date);

-- Schedule status filtering
CREATE INDEX idx_schedules_status
    ON task_schedules (status);

-- Employee availability by employee + day (recurring)
CREATE INDEX idx_availability_employee_day
    ON employee_availability (employee_id, day_of_week);

-- Date-specific availability overrides
CREATE INDEX idx_availability_override
    ON employee_availability (employee_id, override_date);

-- Employee skills — find all employees with a given skill
CREATE INDEX idx_employee_skills_skill
    ON employee_skills (skill_id, proficiency_level DESC);


-- =============================================================
--  HELPER VIEW
--  Returns each employee's working window per recurring day.
--  Join to task_schedules at runtime to calculate free minutes.
-- =============================================================
CREATE OR REPLACE VIEW v_employee_daily_windows AS
SELECT
    e.id                                            AS employee_id,
    e.name                                          AS employee_name,
    e.daily_minutes,
    a.day_of_week,
    a.start_time                                    AS window_start,
    a.end_time                                      AS window_end,
    TIMESTAMPDIFF(MINUTE,
        CAST(a.start_time AS DATETIME),
        CAST(a.end_time   AS DATETIME))             AS available_minutes
FROM employees e
JOIN employee_availability a ON a.employee_id = e.id
    AND a.is_recurring = 1
    AND a.is_available = 1
WHERE e.is_active = 1;


-- =============================================================
--  SEED DATA
-- =============================================================

-- -----------------------------------------------------------
--  Skills
-- -----------------------------------------------------------
INSERT INTO skills (id, name, category) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Haircut',           'hair'),
    ('00000000-0000-0000-0000-000000000002', 'Hair Colouring',    'colour'),
    ('00000000-0000-0000-0000-000000000003', 'Beard Trim',        'hair'),
    ('00000000-0000-0000-0000-000000000004', 'Highlights',        'colour'),
    ('00000000-0000-0000-0000-000000000005', 'Deep Conditioning', 'treatment'),
    ('00000000-0000-0000-0000-000000000006', 'Nail Care',         'beauty'),
    ('00000000-0000-0000-0000-000000000007', 'Scalp Treatment',   'treatment');

-- -----------------------------------------------------------
--  Employees
-- -----------------------------------------------------------
INSERT INTO employees (id, name, role, daily_minutes) VALUES
    ('00000000-0001-0000-0000-000000000001', 'Alice Mercer',   'Senior Stylist',    480),
    ('00000000-0001-0000-0000-000000000002', 'Ben Cartwright', 'Barber',            450),
    ('00000000-0001-0000-0000-000000000003', 'Carla Santos',   'Colour Specialist', 480),
    ('00000000-0001-0000-0000-000000000004', 'Darius Obi',     'Junior Stylist',    420),
    ('00000000-0001-0000-0000-000000000005', 'Elena Voss',     'Beauty Therapist',  480);

-- -----------------------------------------------------------
--  Employee Skills
-- -----------------------------------------------------------
INSERT INTO employee_skills (employee_id, skill_id, proficiency_level) VALUES
    -- Alice: cuts, colour, highlights, conditioning
    ('00000000-0001-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 5),
    ('00000000-0001-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', 4),
    ('00000000-0001-0000-0000-000000000001', '00000000-0000-0000-0000-000000000004', 4),
    ('00000000-0001-0000-0000-000000000001', '00000000-0000-0000-0000-000000000005', 3),
    -- Ben: cuts, beard, scalp
    ('00000000-0001-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 5),
    ('00000000-0001-0000-0000-000000000002', '00000000-0000-0000-0000-000000000003', 5),
    ('00000000-0001-0000-0000-000000000002', '00000000-0000-0000-0000-000000000007', 3),
    -- Carla: colour, highlights, conditioning, scalp
    ('00000000-0001-0000-0000-000000000003', '00000000-0000-0000-0000-000000000002', 5),
    ('00000000-0001-0000-0000-000000000003', '00000000-0000-0000-0000-000000000004', 5),
    ('00000000-0001-0000-0000-000000000003', '00000000-0000-0000-0000-000000000005', 4),
    ('00000000-0001-0000-0000-000000000003', '00000000-0000-0000-0000-000000000007', 4),
    -- Darius: cuts only (junior)
    ('00000000-0001-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', 2),
    ('00000000-0001-0000-0000-000000000004', '00000000-0000-0000-0000-000000000003', 2),
    -- Elena: nails, conditioning, scalp
    ('00000000-0001-0000-0000-000000000005', '00000000-0000-0000-0000-000000000006', 5),
    ('00000000-0001-0000-0000-000000000005', '00000000-0000-0000-0000-000000000005', 4),
    ('00000000-0001-0000-0000-000000000005', '00000000-0000-0000-0000-000000000007', 4);

-- -----------------------------------------------------------
--  Employee Availability  (Mon-Sat recurring, 09:00-17:00)
--  day_of_week: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
-- -----------------------------------------------------------
INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time, is_recurring) VALUES
    -- Alice
    ('00000000-0001-0000-0000-000000000001', 1, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000001', 2, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000001', 3, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000001', 4, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000001', 5, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000001', 6, '09:00', '17:00', 1),
    -- Ben
    ('00000000-0001-0000-0000-000000000002', 1, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000002', 2, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000002', 3, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000002', 4, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000002', 5, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000002', 6, '09:00', '17:00', 1),
    -- Carla
    ('00000000-0001-0000-0000-000000000003', 1, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000003', 2, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000003', 3, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000003', 4, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000003', 5, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000003', 6, '09:00', '17:00', 1),
    -- Darius
    ('00000000-0001-0000-0000-000000000004', 1, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000004', 2, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000004', 3, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000004', 4, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000004', 5, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000004', 6, '09:00', '17:00', 1),
    -- Elena
    ('00000000-0001-0000-0000-000000000005', 1, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000005', 2, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000005', 3, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000005', 4, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000005', 5, '09:00', '17:00', 1),
    ('00000000-0001-0000-0000-000000000005', 6, '09:00', '17:00', 1);

-- One-off override: Carla unavailable on 2025-07-16 (Wednesday)
INSERT INTO employee_availability
    (employee_id, day_of_week, start_time, end_time, is_recurring, override_date, is_available)
VALUES
    ('00000000-0001-0000-0000-000000000003', NULL, '09:00', '17:00', 0, '2025-07-16', 0);

-- -----------------------------------------------------------
--  Tasks  (20 appointments, mix of durations and priorities)
-- -----------------------------------------------------------
INSERT INTO tasks
    (id, task_name, duration_minutes, priority_level, priority_weight,
     required_skill_id, preferred_start, deadline, status, customer_name)
VALUES
-- High-priority / time-sensitive
('00000000-0002-0000-0000-000000000001', 'Cut and Style - Priya',           30, 5, 90,
    '00000000-0000-0000-0000-000000000001', '2025-07-14 09:00:00', '2025-07-14 10:30:00', 'unassigned', 'Priya Nair'),
('00000000-0002-0000-0000-000000000002', 'Full Colour - Tom',               60, 5, 85,
    '00000000-0000-0000-0000-000000000002', '2025-07-14 10:00:00', '2025-07-14 12:00:00', 'unassigned', 'Tom Brannigan'),
('00000000-0002-0000-0000-000000000003', 'Highlights - Sophia',             90, 4, 80,
    '00000000-0000-0000-0000-000000000004', '2025-07-14 11:00:00', NULL,                  'unassigned', 'Sophia Chen'),
('00000000-0002-0000-0000-000000000004', 'Beard Trim - Marco',              15, 3, 60,
    '00000000-0000-0000-0000-000000000003', '2025-07-14 09:30:00', NULL,                  'unassigned', 'Marco Ricci'),
('00000000-0002-0000-0000-000000000005', 'Scalp Treatment - Aisha',         45, 4, 75,
    '00000000-0000-0000-0000-000000000007', '2025-07-14 14:00:00', '2025-07-14 16:00:00', 'unassigned', 'Aisha Yusuf'),
-- Medium priority
('00000000-0002-0000-0000-000000000006', 'Junior Cut - Leon',               30, 3, 55,
    '00000000-0000-0000-0000-000000000001', '2025-07-14 09:00:00', NULL,                  'unassigned', 'Leon Petrov'),
('00000000-0002-0000-0000-000000000007', 'Nail Care - Dana',                45, 3, 58,
    '00000000-0000-0000-0000-000000000006', '2025-07-14 10:00:00', NULL,                  'unassigned', 'Dana Walsh'),
('00000000-0002-0000-0000-000000000008', 'Deep Conditioning - Freya',       30, 3, 52,
    '00000000-0000-0000-0000-000000000005', '2025-07-14 13:00:00', NULL,                  'unassigned', 'Freya Lindqvist'),
('00000000-0002-0000-0000-000000000009', 'Colour Refresh - Hassan',         60, 3, 62,
    '00000000-0000-0000-0000-000000000002', '2025-07-14 11:30:00', NULL,                  'unassigned', 'Hassan Al-Farsi'),
('00000000-0002-0000-0000-000000000010', 'Beard and Hair - Kai',            45, 3, 65,
    '00000000-0000-0000-0000-000000000003', '2025-07-14 10:30:00', NULL,                  'unassigned', 'Kai Tanaka'),
-- Lower priority / flexible timing
('00000000-0002-0000-0000-000000000011', 'Quick Trim - Rowan',              15, 2, 40,
    '00000000-0000-0000-0000-000000000001', NULL,                  NULL,                  'unassigned', 'Rowan Hughes'),
('00000000-0002-0000-0000-000000000012', 'Partial Highlights - Mia',        60, 2, 45,
    '00000000-0000-0000-0000-000000000004', NULL,                  NULL,                  'unassigned', 'Mia Sorensen'),
('00000000-0002-0000-0000-000000000013', 'Nail Art - Zara',                 60, 2, 42,
    '00000000-0000-0000-0000-000000000006', NULL,                  NULL,                  'unassigned', 'Zara Okafor'),
('00000000-0002-0000-0000-000000000014', 'Scalp Massage - Ethan',           30, 2, 38,
    '00000000-0000-0000-0000-000000000007', NULL,                  NULL,                  'unassigned', 'Ethan Byrne'),
('00000000-0002-0000-0000-000000000015', 'Cut and Beard - Luca',            45, 3, 60,
    '00000000-0000-0000-0000-000000000003', '2025-07-14 15:00:00', NULL,                  'unassigned', 'Luca Ferrari'),
('00000000-0002-0000-0000-000000000016', 'Full Conditioning - Yuki',        30, 2, 44,
    '00000000-0000-0000-0000-000000000005', NULL,                  NULL,                  'unassigned', 'Yuki Hayashi'),
('00000000-0002-0000-0000-000000000017', 'Cut and Colour - Amara',          90, 4, 78,
    '00000000-0000-0000-0000-000000000002', '2025-07-14 09:30:00', '2025-07-14 12:00:00', 'unassigned', 'Amara Diallo'),
('00000000-0002-0000-0000-000000000018', 'Express Cut - Niall',             15, 1, 25,
    '00000000-0000-0000-0000-000000000001', NULL,                  NULL,                  'unassigned', 'Niall Brennan'),
('00000000-0002-0000-0000-000000000019', 'Toner and Gloss - Petra',         45, 3, 55,
    '00000000-0000-0000-0000-000000000002', NULL,                  NULL,                  'unassigned', 'Petra Novak'),
('00000000-0002-0000-0000-000000000020', 'Manicure and Conditioning - Soo', 60, 3, 58,
    '00000000-0000-0000-0000-000000000006', '2025-07-14 14:00:00', NULL,                  'unassigned', 'Soo-Jin Park');

-- -----------------------------------------------------------
--  Sample Schedules  (a few tasks pre-assigned for demo)
-- -----------------------------------------------------------
INSERT INTO task_schedules
    (task_id, employee_id, scheduled_date, start_time, end_time, status)
VALUES
-- Alice: Cut & Style at 09:00
('00000000-0002-0000-0000-000000000001',
 '00000000-0001-0000-0000-000000000001',
 '2025-07-14', '2025-07-14 09:00:00', '2025-07-14 09:30:00', 'confirmed'),
-- Alice: Junior Cut at 09:30 (back-to-back)
('00000000-0002-0000-0000-000000000006',
 '00000000-0001-0000-0000-000000000001',
 '2025-07-14', '2025-07-14 09:30:00', '2025-07-14 10:00:00', 'confirmed'),
-- Ben: Beard Trim at 09:30
('00000000-0002-0000-0000-000000000004',
 '00000000-0001-0000-0000-000000000002',
 '2025-07-14', '2025-07-14 09:30:00', '2025-07-14 09:45:00', 'confirmed'),
-- Carla: Full Colour at 10:00
('00000000-0002-0000-0000-000000000002',
 '00000000-0001-0000-0000-000000000003',
 '2025-07-14', '2025-07-14 10:00:00', '2025-07-14 11:00:00', 'confirmed'),
-- Elena: Nail Care at 10:00
('00000000-0002-0000-0000-000000000007',
 '00000000-0001-0000-0000-000000000005',
 '2025-07-14', '2025-07-14 10:00:00', '2025-07-14 10:45:00', 'confirmed');