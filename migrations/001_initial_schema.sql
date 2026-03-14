-- =============================================================
-- WORKFLOW SCHEDULING SYSTEM — POSTGRESQL / SUPABASE VERSION
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================
-- ENUM TYPES
-- =============================================================

CREATE TYPE task_status AS ENUM (
  'unassigned','scheduled','in_progress','completed','cancelled'
);

CREATE TYPE schedule_status AS ENUM (
  'confirmed','in_progress','completed','cancelled','no_show'
);

-- =============================================================
-- DROP TABLES
-- =============================================================

DROP TABLE IF EXISTS task_schedules CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS employee_availability CASCADE;
DROP TABLE IF EXISTS employee_skills CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS skills CASCADE;

-- =============================================================
-- SKILLS
-- =============================================================

CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(60),
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================
-- EMPLOYEES
-- =============================================================

CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    role VARCHAR(100) NOT NULL,
    daily_minutes INT NOT NULL DEFAULT 480 CHECK (daily_minutes BETWEEN 60 AND 720),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(30),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================
-- EMPLOYEE SKILLS
-- =============================================================

CREATE TABLE employee_skills (
    employee_id UUID NOT NULL,
    skill_id UUID NOT NULL,
    proficiency_level SMALLINT NOT NULL DEFAULT 1 CHECK (proficiency_level BETWEEN 1 AND 5),
    certified_date DATE,
    PRIMARY KEY (employee_id, skill_id),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

-- =============================================================
-- EMPLOYEE AVAILABILITY
-- =============================================================

CREATE TABLE employee_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL,
    day_of_week SMALLINT,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_recurring BOOLEAN NOT NULL DEFAULT TRUE,
    override_date DATE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,

    CHECK (day_of_week BETWEEN 0 AND 6),
    CHECK (end_time > start_time),

    CHECK (
        (is_recurring = TRUE AND day_of_week IS NOT NULL AND override_date IS NULL) OR
        (is_recurring = FALSE AND override_date IS NOT NULL)
    ),

    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

-- =============================================================
-- TASKS
-- =============================================================

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(200) NOT NULL,
    duration_minutes INT NOT NULL CHECK (duration_minutes > 0),
    priority_level SMALLINT NOT NULL DEFAULT 3 CHECK (priority_level BETWEEN 1 AND 5),
    priority_weight INT NOT NULL DEFAULT 50 CHECK (priority_weight BETWEEN 1 AND 100),
    required_skill_id UUID NOT NULL,
    preferred_start TIMESTAMP,
    deadline TIMESTAMP,
    status task_status NOT NULL DEFAULT 'unassigned',
    customer_name VARCHAR(150),
    customer_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (required_skill_id) REFERENCES skills(id)
);

-- =============================================================
-- TASK SCHEDULES
-- =============================================================

CREATE TABLE task_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID UNIQUE NOT NULL,
    employee_id UUID NOT NULL,
    scheduled_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status schedule_status NOT NULL DEFAULT 'confirmed',
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    notes TEXT,

    CHECK (end_time > start_time),
    CHECK (DATE(start_time) = scheduled_date),

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

-- =============================================================
-- INDEXES
-- =============================================================

CREATE INDEX idx_tasks_unassigned_priority
ON tasks (status, priority_weight DESC, deadline ASC);

CREATE INDEX idx_tasks_required_skill
ON tasks (required_skill_id);

CREATE INDEX idx_schedules_employee_date
ON task_schedules (employee_id, scheduled_date);

CREATE INDEX idx_schedules_date
ON task_schedules (scheduled_date);

CREATE INDEX idx_schedules_status
ON task_schedules (status);

CREATE INDEX idx_availability_employee_day
ON employee_availability (employee_id, day_of_week);

CREATE INDEX idx_availability_override
ON employee_availability (employee_id, override_date);

CREATE INDEX idx_employee_skills_skill
ON employee_skills (skill_id, proficiency_level DESC);

-- =============================================================
-- HELPER VIEW
-- =============================================================

CREATE OR REPLACE VIEW v_employee_daily_windows AS
SELECT
    e.id AS employee_id,
    e.name AS employee_name,
    e.daily_minutes,
    a.day_of_week,
    a.start_time AS window_start,
    a.end_time AS window_end,
    EXTRACT(EPOCH FROM (a.end_time - a.start_time)) / 60 AS available_minutes
FROM employees e
JOIN employee_availability a
    ON a.employee_id = e.id
    AND a.is_recurring = TRUE
    AND a.is_available = TRUE
WHERE e.is_active = TRUE;

-- =============================================================
-- SEED DATA
-- =============================================================

INSERT INTO skills (id, name, category) VALUES
('00000000-0000-0000-0000-000000000001','Haircut','hair'),
('00000000-0000-0000-0000-000000000002','Hair Colouring','colour'),
('00000000-0000-0000-0000-000000000003','Beard Trim','hair'),
('00000000-0000-0000-0000-000000000004','Highlights','colour'),
('00000000-0000-0000-0000-000000000005','Deep Conditioning','treatment'),
('00000000-0000-0000-0000-000000000006','Nail Care','beauty'),
('00000000-0000-0000-0000-000000000007','Scalp Treatment','treatment');

INSERT INTO employees (id, name, role, daily_minutes) VALUES
('00000000-0001-0000-0000-000000000001','Alice Mercer','Senior Stylist',480),
('00000000-0001-0000-0000-000000000002','Ben Cartwright','Barber',450),
('00000000-0001-0000-0000-000000000003','Carla Santos','Colour Specialist',480),
('00000000-0001-0000-0000-000000000004','Darius Obi','Junior Stylist',420),
('00000000-0001-0000-0000-000000000005','Elena Voss','Beauty Therapist',480);
