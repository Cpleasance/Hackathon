"""Employees CRUD API."""
from flask import Blueprint, request, jsonify
from backend.models import Employee, EmployeeSkill, Skill, get_session
from backend.utils.errors import NotFoundError, ValidationError
from backend.utils.validators import validate_employee_input

bp = Blueprint("employees", __name__, url_prefix="/api/employees")


@bp.route("", methods=["GET"])
def list_employees():
    session = get_session()
    include_skills = request.args.get("include_skills", "false").lower() == "true"
    active_only = request.args.get("active_only", "true").lower() == "true"
    q = session.query(Employee)
    if active_only:
        q = q.filter(Employee.is_active.is_(True))
    employees = q.order_by(Employee.name).all()
    return jsonify([e.to_dict(include_skills=include_skills) for e in employees])


@bp.route("/<employee_id>", methods=["GET"])
def get_employee(employee_id):
    session = get_session()
    e = session.query(Employee).filter_by(id=employee_id).first()
    if not e:
        raise NotFoundError("Employee not found")
    return jsonify(e.to_dict(include_skills=True))


@bp.route("", methods=["POST"])
def create_employee():
    data = request.get_json(force=True)
    clean, errors = validate_employee_input(data)
    if errors:
        raise ValidationError("; ".join(errors))
    session = get_session()
    emp = Employee(**clean)
    session.add(emp)
    session.commit()
    return jsonify(emp.to_dict()), 201


@bp.route("/<employee_id>", methods=["PUT"])
def update_employee(employee_id):
    from backend.models import TaskSchedule, Task
    from backend.services.scheduler_engine import auto_schedule_all
    import datetime

    session = get_session()
    emp = session.query(Employee).filter_by(id=employee_id).first()
    if not emp:
        raise NotFoundError("Employee not found")
        
    data = request.get_json(force=True)
    auto_reschedule = data.pop("auto_reschedule", False)
    
    clean, errors = validate_employee_input(data)
    if errors:
        raise ValidationError("; ".join(errors))
        
    old_status = emp.status
    for k, v in clean.items():
        setattr(emp, k, v)
        
    session.commit()
    
    # Auto-reschedule upcoming tasks if requested and employee is now unavailable
    if auto_reschedule and old_status == "active" and emp.status in ("sick", "holiday", "inactive"):
        today = datetime.date.today()
        upcoming_schedules = session.query(TaskSchedule).filter(
            TaskSchedule.employee_id == emp.id,
            TaskSchedule.scheduled_date >= today,
            TaskSchedule.status.in_(["confirmed", "in_progress"])
        ).all()
        
        affected_dates = set()
        
        for sched in upcoming_schedules:
            sched.status = "cancelled"
            sched.task.status = "unassigned"
            affected_dates.add(sched.scheduled_date)
            
        session.commit()
        
        # Re-run auto-schedule for the affected dates to slot those unassigned tasks
        # elsewhere (or they remain unassigned if no capacity)
        for d in affected_dates:
            auto_schedule_all(session, d)

    return jsonify(emp.to_dict())


@bp.route("/<employee_id>/skills", methods=["POST"])
def assign_skill(employee_id):
    session = get_session()
    emp = session.query(Employee).filter_by(id=employee_id).first()
    if not emp:
        raise NotFoundError("Employee not found")
    data = request.get_json(force=True)
    skill_id = data.get("skill_id")
    if not skill_id:
        raise ValidationError("skill_id is required")
    skill = session.query(Skill).filter_by(id=skill_id).first()
    if not skill:
        raise NotFoundError("Skill not found")
    prof = int(data.get("proficiency_level", 1))
    if prof < 1 or prof > 5:
        raise ValidationError("proficiency_level must be 1–5")
    es = EmployeeSkill(employee_id=emp.id, skill_id=skill.id, proficiency_level=prof)
    session.merge(es)
    session.commit()
    return jsonify({"status": "ok", "employee": emp.name, "skill": skill.name, "proficiency": prof}), 201
