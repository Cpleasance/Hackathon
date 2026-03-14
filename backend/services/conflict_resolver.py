"""
Conflict Resolution Engine
---------------------------
Detects and resolves scheduling conflicts in real-time:
  1. Overlap detection  — two tasks on the same employee overlap
  2. Overrun handling   — a task exceeds its scheduled end time
  3. Unavailability     — employee becomes unavailable mid-day
  4. Auto-reassignment  — find the next best employee and reschedule
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.models import (
    Task, TaskSchedule, Employee, EmployeeSkill, EmployeeAvailability,
)


def detect_overlaps(session: Session, employee_id: str, start: datetime, end: datetime,
                    exclude_schedule_id: str | None = None) -> list[dict]:
    """
    Return any existing schedules for `employee_id` that overlap [start, end).
    """
    q = session.query(TaskSchedule).filter(
        TaskSchedule.employee_id == employee_id,
        TaskSchedule.status.notin_(["cancelled", "no_show"]),
        TaskSchedule.start_time < end,
        TaskSchedule.end_time > start,
    )
    if exclude_schedule_id:
        q = q.filter(TaskSchedule.id != exclude_schedule_id)
    return [s.to_dict() for s in q.all()]


def find_alternative_employee(
    session: Session,
    skill_id: str,
    target_date,
    start: datetime,
    end: datetime,
    exclude_employee_id: str | None = None,
) -> dict | None:
    """
    Find the best available employee who:
      - has the required skill
      - is available on target_date during [start, end)
      - has no overlapping schedules
    Returns employee dict or None.
    """
    dow = start.weekday()
    # Python weekday: Mon=0 … Sun=6  →  schema: Sun=0 … Sat=6
    schema_dow = (dow + 1) % 7

    candidates = (
        session.query(Employee, EmployeeSkill)
        .join(EmployeeSkill, Employee.id == EmployeeSkill.employee_id)
        .filter(
            EmployeeSkill.skill_id == skill_id,
            Employee.is_active.is_(True),
        )
    )
    if exclude_employee_id:
        candidates = candidates.filter(Employee.id != exclude_employee_id)

    candidates = candidates.order_by(EmployeeSkill.proficiency_level.desc()).all()

    for emp, es in candidates:
        # Check recurring availability
        avail = session.query(EmployeeAvailability).filter(
            EmployeeAvailability.employee_id == emp.id,
            EmployeeAvailability.is_recurring.is_(True),
            EmployeeAvailability.day_of_week == schema_dow,
            EmployeeAvailability.is_available.is_(True),
            EmployeeAvailability.start_time <= start.time(),
            EmployeeAvailability.end_time >= end.time(),
        ).first()

        if not avail:
            continue

        # Check for date-specific unavailability override
        override = session.query(EmployeeAvailability).filter(
            EmployeeAvailability.employee_id == emp.id,
            EmployeeAvailability.is_recurring.is_(False),
            EmployeeAvailability.override_date == target_date,
            EmployeeAvailability.is_available.is_(False),
        ).first()

        if override:
            continue

        # Check for overlapping schedules
        overlaps = detect_overlaps(session, str(emp.id), start, end)
        if not overlaps:
            return {
                "employee_id": str(emp.id),
                "employee_name": emp.name,
                "proficiency_level": es.proficiency_level,
            }

    return None


def resolve_overrun(session: Session, schedule_id: str, new_end: datetime) -> dict:
    """
    Handle a task overrun: extend the schedule and cascade-check
    subsequent appointments.  If a conflict arises, attempt
    auto-reassignment of the affected downstream task.
    """
    sched = session.query(TaskSchedule).filter_by(id=schedule_id).first()
    if not sched:
        return {"status": "error", "message": "Schedule not found"}

    old_end = sched.end_time
    sched.end_time = new_end
    sched.status = "in_progress"

    # Find downstream schedules that now overlap
    downstream = (
        session.query(TaskSchedule)
        .filter(
            TaskSchedule.employee_id == sched.employee_id,
            TaskSchedule.id != sched.id,
            TaskSchedule.status.notin_(["cancelled", "no_show", "completed"]),
            TaskSchedule.start_time < new_end,
            TaskSchedule.start_time >= old_end,
        )
        .order_by(TaskSchedule.start_time)
        .all()
    )

    reassigned = []
    failed = []

    for ds in downstream:
        task = ds.task
        alt = find_alternative_employee(
            session,
            skill_id=str(task.required_skill_id),
            target_date=ds.scheduled_date,
            start=ds.start_time,
            end=ds.end_time,
            exclude_employee_id=str(sched.employee_id),
        )
        if alt:
            ds.employee_id = alt["employee_id"]
            reassigned.append({
                "task_id": str(ds.task_id),
                "task_name": task.task_name,
                "new_employee": alt["employee_name"],
            })
        else:
            failed.append({
                "task_id": str(ds.task_id),
                "task_name": task.task_name,
                "reason": "No alternative employee available",
            })

    session.commit()

    return {
        "status": "resolved" if not failed else "partial",
        "extended_schedule": schedule_id,
        "reassigned": reassigned,
        "unresolved": failed,
    }
