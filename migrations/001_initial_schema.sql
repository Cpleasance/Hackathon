-- =============================================================
--  WORKFLOW SCHEDULING SYSTEM — PostgreSQL Schema
--  Migration 001: Initial schema
--  Apply with: psql -d scheduler -f 001_initial_schema.sql
-- =============================================================

-- NOTE: This file should contain the complete schema provided
-- in the project specification document. Copy the full SQL from
-- the design document into this file before running.

-- The schema includes:
--   - Extensions: pgcrypto, btree_gist
--   - Enumerations: task_status, schedule_status, day_of_week
--   - Tables: skills, employees, employee_skills, employee_availability,
--             tasks, task_schedules
--   - Exclusion constraint: no_employee_overlap
--   - Indexes for performance
--   - Helper view: v_employee_daily_windows
--   - Seed data: skills, employees, employee_skills, availability, tasks, sample schedules

-- Paste the complete schema SQL here.
