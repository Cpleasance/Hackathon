"""Employee breaks (lunch / general) management API."""
from datetime import time, date
from flask import Blueprint, request, jsonify
from backend.models import EmployeeBreak, Employee, get_session
from backend.utils.errors import NotFoundError, ValidationError

bp = Blueprint("breaks", __name__, url_prefix="/api/breaks")


@bp.route("/<employee_id>", methods=["GET"])
def get_breaks(employee_id):
    """Get all break records for an employee."""
    session = get_session()
    emp = session.query(Employee).filter_by(id=employee_id).first()
    if not emp:
        raise NotFoundError("Employee not found")
    records = (
        session.query(EmployeeBreak)
        .filter_by(employee_id=employee_id)
        .order_by(EmployeeBreak.day_of_week, EmployeeBreak.start_time)
        .all()
    )
    return jsonify({
        "employee_id": employee_id,
        "employee_name": emp.name,
        "breaks": [r.to_dict() for r in records],
    })


@bp.route("/<employee_id>", methods=["POST"])
def add_break(employee_id):
    """Add a recurring or override break record."""
    session = get_session()
    emp = session.query(Employee).filter_by(id=employee_id).first()
    if not emp:
        raise NotFoundError("Employee not found")

    data = request.get_json(force=True)
    errors = []

    is_recurring = data.get("is_recurring", True)

    # Parse times
    try:
        st = time.fromisoformat(data["start_time"])
    except (KeyError, ValueError):
        errors.append("start_time required (HH:MM)")
    try:
        et = time.fromisoformat(data["end_time"])
    except (KeyError, ValueError):
        errors.append("end_time required (HH:MM)")

    if not errors and et <= st:
        errors.append("end_time must be after start_time")

    day_of_week = None
    override_date = None

    if is_recurring:
        dow = data.get("day_of_week")
        if dow is None:
            errors.append("day_of_week required for recurring (0=Mon…6=Sun)")
        else:
            try:
                day_of_week = int(dow)
                if day_of_week < 0 or day_of_week > 6:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append("day_of_week must be 0–6")
    else:
        od = data.get("override_date")
        if not od:
            errors.append("override_date required for non-recurring (YYYY-MM-DD)")
        else:
            try:
                override_date = date.fromisoformat(od)
            except ValueError:
                errors.append("override_date must be YYYY-MM-DD")

    if errors:
        raise ValidationError("; ".join(errors))

    record = EmployeeBreak(
        employee_id=emp.id,
        day_of_week=day_of_week,
        start_time=st,
        end_time=et,
        is_recurring=is_recurring,
        override_date=override_date,
    )
    session.add(record)
    session.commit()
    return jsonify(record.to_dict()), 201


@bp.route("/record/<record_id>", methods=["DELETE"])
def delete_break(record_id):
    """Delete a break record."""
    session = get_session()
    record = session.query(EmployeeBreak).filter_by(id=record_id).first()
    if not record:
        raise NotFoundError("Break record not found")
    session.delete(record)
    session.commit()
    return jsonify({"status": "deleted", "id": record_id})

