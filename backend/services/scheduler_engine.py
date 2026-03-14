"""
Scheduler Engine — Core Optimisation
-------------------------------------
Implements the primary scheduling algorithm:

1. Pull unassigned tasks, ranked by composite priority score
2. For each task, find qualified employees (skill match + availability)
3. For each candidate, find the earliest feasible time slot
4. Apply buffer zones
5. Assign the best (highest proficiency, earliest slot) match
6. Commit atomically — all-or-nothing per scheduling run

The algorithm is greedy with priority ordering.  This is intentional:
in appointment-based businesses, real-time responsiveness matters more
than global optimality, and the priority engine ensures high-value
tasks are placed first.
"""
from __future__ import annotations

from datetime import datetime, date, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.models import (
    Task, TaskSchedule, Employee, EmployeeSkill, EmployeeAvailability, Skill,
)
from backend.services.buffer_calculator import get_buffer_minutes
from backend.services.priority_engine import composite_score
from backend.services.conflict_resolver import detect_overlaps


def _schema_dow(py_weekday: int) -> int:
    """
    Convert Python weekday (Mon=0) to schema day_of_week.

    NOTE: The seed data and existing availability records use the same
    convention as Python's datetime (Mon=0, Sun=6), so we simply return
    the incoming value. This keeps the ORM logic aligned with the data.
    """
    return py_weekday


def _get_employee_window(session: Session, employee_id, target_date: date) -> tuple[time, time] | None:
    """
    Return the (start_time, end_time) work window for an employee on a date.
    Override dates take precedence over recurring schedules.
    """
    # Check override first
    override = session.query(EmployeeAvailability).filter(
        EmployeeAvailability.employee_id == employee_id,
        EmployeeAvailability.is_recurring.is_(False),
        EmployeeAvailability.override_date == target_date,
    ).first()

    if override:
        if not override.is_available:
            return None  # employee is off
        return (override.start_time, override.end_time)

    # Recurring
    dow = _schema_dow(target_date.weekday())
    recurring = session.query(EmployeeAvailability).filter(
        EmployeeAvailability.employee_id == employee_id,
        EmployeeAvailability.is_recurring.is_(True),
        EmployeeAvailability.day_of_week == dow,
        EmployeeAvailability.is_available.is_(True),
    ).first()

    if recurring:
        return (recurring.start_time, recurring.end_time)
    return None


def _get_booked_slots(session: Session, employee_id, target_date: date) -> list[tuple[datetime, datetime]]:
    """Return sorted list of (start, end) for existing non-cancelled schedules."""
    scheds = (
        session.query(TaskSchedule)
        .filter(
            TaskSchedule.employee_id == employee_id,
            TaskSchedule.scheduled_date == target_date,
            TaskSchedule.status.notin_(["cancelled", "no_show"]),
        )
        .order_by(TaskSchedule.start_time)
        .all()
    )
    return [(s.start_time, s.end_time) for s in scheds]


def find_earliest_slot(
    session: Session,
    employee_id,
    target_date: date,
    duration_minutes: int,
    buffer_minutes: int,
    preferred_start: datetime | None = None,
) -> datetime | None:
    """
    Find the earliest start time on `target_date` where the employee
    has `duration_minutes + buffer_minutes` contiguous free time.
    Respects preferred_start as a soft lower-bound.
    """
    window = _get_employee_window(session, employee_id, target_date)
    if window is None:
        return None

    win_start_dt = datetime.combine(target_date, window[0])
    win_end_dt = datetime.combine(target_date, window[1])

    total_needed = timedelta(minutes=duration_minutes + buffer_minutes)
    duration_only = timedelta(minutes=duration_minutes)

    # Earliest we'd consider
    earliest = win_start_dt
    if preferred_start and preferred_start > earliest and preferred_start.date() == target_date:
        earliest = preferred_start

    booked = _get_booked_slots(session, employee_id, target_date)

    # Build free gaps
    cursor = earliest
    for (bs, be) in booked:
        if cursor + total_needed <= bs:
            return cursor  # fits before this booking
        if be > cursor:
            cursor = be  # skip past this booking

    # Check after last booking. For the final task of the day we only
    # require that the task itself fits before the end of the window;
    # we don't force an additional buffer *after* closing time.
    if cursor + duration_only <= win_end_dt:
        return cursor

    return None


def schedule_task(session: Session, task: Task, target_date: date) -> dict | None:
    """
    Attempt to schedule a single task on `target_date`.
    Returns schedule dict on success, None on failure.
    """
    skill = session.query(Skill).get(task.required_skill_id)
    buffer_min = get_buffer_minutes(skill.category if skill else None)

    # Find qualified employees, ordered by proficiency desc.
    # Skip employees who are sick, on holiday (until date hasn't passed), or inactive.
    today = date.today()
    candidates = (
        session.query(Employee, EmployeeSkill)
        .join(EmployeeSkill, Employee.id == EmployeeSkill.employee_id)
        .filter(
            EmployeeSkill.skill_id == task.required_skill_id,
            Employee.is_active.is_(True),
            Employee.status.in_(["active"]),  # only active employees
        )
        .order_by(EmployeeSkill.proficiency_level.desc())
        .all()
    )
    # Also skip employees on holiday whose return date is in the future
    candidates = [
        (emp, es) for emp, es in candidates
        if not (emp.status == "holiday" and emp.holiday_until and emp.holiday_until > target_date)
    ]

    best_slot = None
    best_emp = None

    for emp, es in candidates:
        slot = find_earliest_slot(
            session, emp.id, target_date,
            task.duration_minutes, buffer_min,
            preferred_start=task.preferred_start,
        )
        if slot is not None:
            # Take first available from highest-proficiency employee
            if best_slot is None or slot < best_slot:
                best_slot = slot
                best_emp = emp
            break  # highest proficiency with a slot wins

    if best_slot is None or best_emp is None:
        return None

    end_time = best_slot + timedelta(minutes=task.duration_minutes)

    sched = TaskSchedule(
        task_id=task.id,
        employee_id=best_emp.id,
        scheduled_date=target_date,
        start_time=best_slot,
        end_time=end_time,
        status="confirmed",
    )
    session.add(sched)
    task.status = "scheduled"
    task.updated_at = datetime.now(timezone.utc)
    session.flush()

    return sched.to_dict()


def auto_schedule_all(session: Session, target_date: date) -> dict:
    """
    Run the full scheduling pass for all unassigned tasks on `target_date`.
    Tasks are processed in priority order.

    Returns: { scheduled: [...], failed: [...] }
    """
    # Start from all unassigned tasks, then restrict to those that are
    # actually intended for the target date. This prevents the scheduler
    # from attempting to cram historical/future backlog from other days
    # into a single date on the board.
    unassigned = (
        session.query(Task)
        .filter(Task.status == "unassigned")
        .order_by(Task.priority_weight.desc(), Task.deadline.asc().nullslast())
        .all()
    )

    # Only consider tasks whose preferred_start (if set) falls on
    # target_date. Tasks without a preferred_start are also eligible.
    unassigned = [
        t for t in unassigned
        if (t.preferred_start is None) or (t.preferred_start.date() == target_date)
    ]

    # Compute composite scores and sort
    scored = []
    for t in unassigned:
        score = composite_score(
            t.priority_weight,
            t.deadline,
            t.duration_minutes,
        )
        scored.append((score, t))
    scored.sort(key=lambda x: x[0], reverse=True)

    scheduled = []
    failed = []

    for _score, task in scored:
        # Check deadline compatibility
        if task.deadline and task.deadline.date() < target_date:
            failed.append({
                "task_id": str(task.id),
                "task_name": task.task_name,
                "reason": "Deadline is before target date",
            })
            continue
            
        # preferred_start is a soft hint — used as a lower-bound by find_earliest_slot.
        # Do NOT reject tasks just because preferred_start is on a different date;
        # unassigned tasks from any day can be scheduled onto target_date.

        result = schedule_task(session, task, target_date)
        if result:
            scheduled.append(result)
        else:
            failed.append({
                "task_id": str(task.id),
                "task_name": task.task_name,
                "reason": "No qualified employee with available slot",
            })

    session.commit()

    return {
        "date": target_date.isoformat(),
        "scheduled_count": len(scheduled),
        "failed_count": len(failed),
        "scheduled": scheduled,
        "failed": failed,
    }
