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

from collections import defaultdict
from datetime import datetime, date, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.config import Config
from backend.models import (
    Task, TaskSchedule, Employee, EmployeeSkill, EmployeeAvailability, EmployeeBreak, Skill,
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


def _get_employee_window(
    session: Session,
    employee_id,
    target_date: date,
    avail_cache: dict | None = None,
) -> tuple[time, time] | None:
    """
    Return the (start_time, end_time) work window for an employee on a date.
    Override dates take precedence over recurring schedules.
    avail_cache: optional pre-loaded dict keyed by employee_id.
    """
    if avail_cache is not None and employee_id in avail_cache:
        records = avail_cache[employee_id]
    else:
        records = session.query(EmployeeAvailability).filter(
            EmployeeAvailability.employee_id == employee_id,
        ).all()

    # Check override first
    for r in records:
        if not r.is_recurring and r.override_date == target_date:
            if not r.is_available:
                return None
            return (r.start_time, r.end_time)

    # Recurring
    dow = _schema_dow(target_date.weekday())
    for r in records:
        if r.is_recurring and r.day_of_week == dow and r.is_available:
            return (r.start_time, r.end_time)

    return None


def _get_booked_slots(
    session: Session,
    employee_id,
    target_date: date,
    breaks_cache: dict | None = None,
    schedules_cache: dict | None = None,
) -> list[tuple[datetime, datetime]]:
    """
    Return sorted list of (start, end) for *occupied* time on a day.
    Accepts optional pre-loaded caches to avoid repeated queries.
    """
    if schedules_cache is not None and employee_id in schedules_cache:
        booked: list[tuple[datetime, datetime]] = list(schedules_cache[employee_id])
    else:
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
        booked = [(s.start_time, s.end_time) for s in scheds]

    # Add breaks
    dow = _schema_dow(target_date.weekday())

    if breaks_cache is not None and employee_id in breaks_cache:
        all_breaks = breaks_cache[employee_id]
    else:
        all_breaks = session.query(EmployeeBreak).filter(
            EmployeeBreak.employee_id == employee_id,
        ).all()

    for b in all_breaks:
        if b.is_recurring and b.day_of_week == dow:
            booked.append((datetime.combine(target_date, b.start_time), datetime.combine(target_date, b.end_time)))
        elif not b.is_recurring and b.override_date == target_date:
            booked.append((datetime.combine(target_date, b.start_time), datetime.combine(target_date, b.end_time)))

    booked.sort(key=lambda t: t[0])
    return booked


def find_earliest_slot(
    session: Session,
    employee_id,
    target_date: date,
    duration_minutes: int,
    buffer_minutes: int,
    preferred_start: datetime | None = None,
    avail_cache: dict | None = None,
    breaks_cache: dict | None = None,
    schedules_cache: dict | None = None,
) -> datetime | None:
    """
    Find the earliest start time on `target_date` where the employee
    has `duration_minutes + buffer_minutes` contiguous free time.
    Respects preferred_start as a soft lower-bound.
    """
    window = _get_employee_window(session, employee_id, target_date, avail_cache=avail_cache)
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

    booked = _get_booked_slots(
        session, employee_id, target_date,
        breaks_cache=breaks_cache,
        schedules_cache=schedules_cache,
    )

    # Build free gaps — try fitting with buffer first, then without (last slot of day)
    cursor = earliest
    for (bs, be) in booked:
        if cursor + total_needed <= bs:
            return cursor  # fits with buffer before this booking
        if cursor + duration_only <= bs:
            return cursor  # fits without buffer (last task before this booking)
        if be > cursor:
            cursor = be  # skip past this booking

    # Check after last booking — no buffer needed after the final task
    if cursor + duration_only <= win_end_dt:
        return cursor

    return None


def schedule_task(
    session: Session,
    task: Task,
    target_date: date,
    skill_cache: dict | None = None,
    avail_cache: dict | None = None,
    breaks_cache: dict | None = None,
    schedules_cache: dict | None = None,
) -> dict | None:
    """
    Attempt to schedule a single task on `target_date`.
    Returns schedule dict on success, None on failure.
    """
    if skill_cache is not None and task.required_skill_id in skill_cache:
        skill = skill_cache[task.required_skill_id]
    else:
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
            avail_cache=avail_cache,
            breaks_cache=breaks_cache,
            schedules_cache=schedules_cache,
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

    # Keep the in-memory schedules cache up to date so subsequent tasks
    # in the same run see this newly booked slot.
    if schedules_cache is not None:
        schedules_cache.setdefault(best_emp.id, []).append((best_slot, end_time))

    return sched.to_dict()


def auto_schedule_all(session: Session, target_date: date) -> dict:
    """
    Run the full scheduling pass for all unassigned tasks, placing as many
    as possible on `target_date`. Tasks are processed in priority order.

    Will not schedule on non-operational days as defined in config.

    Returns: { scheduled: [...], failed: [...] }
    """
    # Respect global operational days (1=Mon…7=Sun as per Config/business rules)
    operating_days = getattr(Config, "OPERATING_DAYS", None)
    if operating_days:
        # Convert Python weekday (Mon=0) to 1–7 (Mon=1…Sun=7)
        weekday_1_7 = target_date.weekday() + 1
        if weekday_1_7 not in operating_days:
            return {
                "date": target_date.isoformat(),
                "scheduled_count": 0,
                "failed_count": 0,
                "scheduled": [],
                "failed": [],
                "closed": True,
            }
    unassigned = (
        session.query(Task)
        .filter(
            Task.status == "unassigned",
            # Only schedule tasks that are due today or overdue — not future tasks
            Task.deadline <= datetime.combine(target_date, time(23, 59, 59)),
        )
        .order_by(Task.priority_weight.desc(), Task.deadline.asc().nullslast())
        .all()
    )

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

    # --- Batch-load per-employee data once for the whole run ---
    all_avail = session.query(EmployeeAvailability).all()
    avail_cache: dict = defaultdict(list)
    for a in all_avail:
        avail_cache[a.employee_id].append(a)

    all_breaks = session.query(EmployeeBreak).all()
    breaks_cache: dict = defaultdict(list)
    for b in all_breaks:
        breaks_cache[b.employee_id].append(b)

    existing_scheds = (
        session.query(TaskSchedule)
        .filter(
            TaskSchedule.scheduled_date == target_date,
            TaskSchedule.status.notin_(["cancelled", "no_show"]),
        )
        .all()
    )
    schedules_cache: dict = defaultdict(list)
    for s in existing_scheds:
        schedules_cache[s.employee_id].append((s.start_time, s.end_time))

    all_skills = session.query(Skill).all()
    skill_cache: dict = {s.id: s for s in all_skills}
    # -----------------------------------------------------------

    for _score, task in scored:
        # Skip only if deadline has passed AND we're not trying to catch up.
        # Overdue tasks (deadline < today) are still scheduled — urgency_score
        # already gives them the maximum score so they're processed first.

        # preferred_start is a soft hint — used as a lower-bound by find_earliest_slot.
        # Do NOT reject tasks just because preferred_start is on a different date;
        # unassigned tasks from any day can be scheduled onto target_date.

        result = schedule_task(
            session, task, target_date,
            skill_cache=skill_cache,
            avail_cache=avail_cache,
            breaks_cache=breaks_cache,
            schedules_cache=schedules_cache,
        )
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
