"""Schedule management API — assignment, auto-scheduling, conflict resolution."""
from datetime import date, datetime, timezone
from flask import Blueprint, request, jsonify
from backend.models import Task, TaskSchedule, get_session
from backend.utils.errors import NotFoundError, ValidationError, ConflictError
from backend.utils.validators import validate_schedule_input
from backend.services.scheduler_engine import auto_schedule_all, schedule_task
from backend.services.conflict_resolver import detect_overlaps, resolve_overrun

bp = Blueprint("schedules", __name__, url_prefix="/api/schedules")


@bp.route("", methods=["GET"])
def list_schedules():
    """List schedules, filterable by date and employee."""
    session = get_session()
    q = session.query(TaskSchedule)
    d = request.args.get("date")
    if d:
        try:
            q = q.filter(TaskSchedule.scheduled_date == date.fromisoformat(d))
        except ValueError:
            raise ValidationError("date must be YYYY-MM-DD")
    emp = request.args.get("employee_id")
    if emp:
        q = q.filter(TaskSchedule.employee_id == emp)
    status = request.args.get("status")
    if status:
        q = q.filter(TaskSchedule.status == status)
    schedules = q.order_by(TaskSchedule.start_time).all()
    return jsonify([s.to_dict() for s in schedules])


@bp.route("/<schedule_id>", methods=["GET"])
def get_schedule(schedule_id):
    session = get_session()
    s = session.query(TaskSchedule).filter_by(id=schedule_id).first()
    if not s:
        raise NotFoundError("Schedule not found")
    return jsonify(s.to_dict())


@bp.route("", methods=["POST"])
def create_schedule():
    """Manually assign a task to an employee at a specific time."""
    data = request.get_json(force=True)
    clean, errors = validate_schedule_input(data)
    if errors:
        raise ValidationError("; ".join(errors))

    session = get_session()

    # Check task exists and is unassigned
    task = session.query(Task).filter_by(id=clean["task_id"]).first()
    if not task:
        raise NotFoundError("Task not found")
    if task.status != "unassigned":
        raise ConflictError(f"Task is already {task.status}")

    # Enforce task duration
    scheduled_duration = (clean["end_time"] - clean["start_time"]).total_seconds() / 60
    if scheduled_duration < task.duration_minutes:
        raise ValidationError(f"Scheduled time ({int(scheduled_duration)}m) is less than task duration ({task.duration_minutes}m)")

    # Check employee skill
    from backend.models import EmployeeSkill
    es = session.query(EmployeeSkill).filter_by(
        employee_id=clean["employee_id"], 
        skill_id=task.required_skill_id
    ).first()
    if not es:
        raise ValidationError("Employee does not have the required skill for this task")

    # Check for overlaps
    overlaps = detect_overlaps(
        session, clean["employee_id"], clean["start_time"], clean["end_time"]
    )
    if overlaps:
        raise ConflictError(
            "Employee has overlapping schedule(s)",
            payload={"conflicts": overlaps},
        )

    sched = TaskSchedule(
        task_id=clean["task_id"],
        employee_id=clean["employee_id"],
        scheduled_date=clean["scheduled_date"],
        start_time=clean["start_time"],
        end_time=clean["end_time"],
        status="confirmed",
    )
    session.add(sched)
    task.status = "scheduled"
    task.updated_at = datetime.now(timezone.utc)
    session.commit()
    return jsonify(sched.to_dict()), 201


@bp.route("/<schedule_id>/status", methods=["PATCH"])
def update_status(schedule_id):
    """Update schedule status (in_progress, completed, cancelled, no_show)."""
    session = get_session()
    sched = session.query(TaskSchedule).filter_by(id=schedule_id).first()
    if not sched:
        raise NotFoundError("Schedule not found")
    data = request.get_json(force=True)
    new_status = data.get("status")
    valid = ("confirmed", "in_progress", "completed", "cancelled", "no_show")
    if new_status not in valid:
        raise ValidationError(f"status must be one of {valid}")
    sched.status = new_status
    if new_status == "completed":
        sched.completed_at = datetime.now(timezone.utc)
        sched.task.status = "completed"
    elif new_status == "cancelled":
        sched.task.status = "unassigned"
    elif new_status == "in_progress":
        sched.task.status = "in_progress"
    elif new_status in ("confirmed", "no_show"):
        sched.task.status = "scheduled"
    sched.task.updated_at = datetime.now(timezone.utc)
    session.commit()
    return jsonify(sched.to_dict())


@bp.route("/auto-schedule", methods=["POST"])
def run_auto_schedule():
    """
    Trigger the auto-scheduler for a given date.
    Body: { "date": "YYYY-MM-DD" }
    """
    data = request.get_json(force=True)
    d = data.get("date")
    if not d:
        raise ValidationError("date is required (YYYY-MM-DD)")
    try:
        target = date.fromisoformat(d)
    except ValueError:
        raise ValidationError("date must be YYYY-MM-DD")

    session = get_session()
    result = auto_schedule_all(session, target)
    return jsonify(result)


@bp.route("/<schedule_id>/overrun", methods=["POST"])
def handle_overrun(schedule_id):
    """
    Report that a task is overrunning. The conflict resolver
    will extend the schedule and cascade-reassign if needed.
    Body: { "new_end_time": "ISO-8601" }
    """
    data = request.get_json(force=True)
    new_end = data.get("new_end_time")
    if not new_end:
        raise ValidationError("new_end_time is required (ISO-8601)")
    try:
        new_end_dt = datetime.fromisoformat(new_end)
    except ValueError:
        raise ValidationError("new_end_time must be ISO-8601")
    session = get_session()
    result = resolve_overrun(session, schedule_id, new_end_dt)
    return jsonify(result)


@bp.route("/<schedule_id>/force", methods=["PUT"])
def force_reassign(schedule_id):
    """
    Manual Takeover (Admin Override).
    Bypass the rules engine to force-assign a schedule to any time/employee.
    """
    data = request.get_json(force=True)
    session = get_session()
    
    sched = session.query(TaskSchedule).filter_by(id=schedule_id).first()
    if not sched:
        raise NotFoundError("Schedule not found")
        
    new_emp_id = data.get("employee_id")
    new_start = data.get("start_time")
    new_end = data.get("end_time")
    
    if not new_emp_id or not new_start or not new_end:
        raise ValidationError("employee_id, start_time, and end_time are required")
        
    try:
        start_dt = datetime.fromisoformat(new_start)
        end_dt = datetime.fromisoformat(new_end)
    except ValueError:
        raise ValidationError("Dates must be ISO-8601")
        
    sched.employee_id = new_emp_id
    sched.start_time = start_dt
    sched.end_time = end_dt
    sched.scheduled_date = start_dt.date()
    
    session.commit()
    return jsonify(sched.to_dict())
