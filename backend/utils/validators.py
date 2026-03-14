"""
Input validation and sanitisation helpers.

Every public function returns (cleaned_data, errors) where errors
is an empty list on success.
"""
from datetime import datetime, date, time
from uuid import UUID


def _is_valid_uuid(val: str) -> bool:
    try:
        UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


def validate_task_input(data: dict) -> tuple[dict, list[str]]:
    """Validate and sanitise task creation/update payload."""
    errors = []
    clean = {}

    # task_name
    name = (data.get("task_name") or "").strip()
    if not name:
        errors.append("task_name is required")
    elif len(name) > 200:
        errors.append("task_name must be ≤200 characters")
    clean["task_name"] = name

    # duration_minutes
    dur = data.get("duration_minutes")
    if dur is None:
        errors.append("duration_minutes is required")
    else:
        try:
            dur = int(dur)
            if dur <= 0:
                raise ValueError
            clean["duration_minutes"] = dur
        except (ValueError, TypeError):
            errors.append("duration_minutes must be a positive integer")

    # priority_level
    pl = data.get("priority_level", 3)
    try:
        pl = int(pl)
        if pl < 1 or pl > 5:
            raise ValueError
        clean["priority_level"] = pl
    except (ValueError, TypeError):
        errors.append("priority_level must be 1–5")

    # priority_weight
    pw = data.get("priority_weight", 50)
    try:
        pw = int(pw)
        if pw < 1 or pw > 100:
            raise ValueError
        clean["priority_weight"] = pw
    except (ValueError, TypeError):
        errors.append("priority_weight must be 1–100")

    # required_skill_id
    skill = data.get("required_skill_id", "")
    if not skill or not _is_valid_uuid(skill):
        errors.append("required_skill_id must be a valid UUID")
    else:
        clean["required_skill_id"] = skill

    # optional timestamps
    for field in ("preferred_start", "deadline"):
        val = data.get(field)
        if val:
            try:
                clean[field] = datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                errors.append(f"{field} must be ISO-8601 format")
        else:
            clean[field] = None

    # customer_name
    cname = (data.get("customer_name") or "").strip()
    if len(cname) > 150:
        errors.append("customer_name must be ≤150 characters")
    clean["customer_name"] = cname or None

    clean["customer_notes"] = (data.get("customer_notes") or "").strip() or None

    return clean, errors


def validate_employee_input(data: dict) -> tuple[dict, list[str]]:
    """Validate employee creation/update payload."""
    errors = []
    clean = {}

    name = (data.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    clean["name"] = name

    role = (data.get("role") or "").strip()
    if not role:
        errors.append("role is required")
    clean["role"] = role

    dm = data.get("daily_minutes", 480)
    try:
        dm = int(dm)
        if dm < 60 or dm > 720:
            raise ValueError
        clean["daily_minutes"] = dm
    except (ValueError, TypeError):
        errors.append("daily_minutes must be 60–720")

    clean["email"] = (data.get("email") or "").strip() or None
    clean["phone"] = (data.get("phone") or "").strip() or None
    clean["notes"] = (data.get("notes") or "").strip() or None
    clean["is_active"] = bool(data.get("is_active", True))

    return clean, errors


def validate_schedule_input(data: dict) -> tuple[dict, list[str]]:
    """Validate manual schedule assignment payload."""
    errors = []
    clean = {}

    for field in ("task_id", "employee_id"):
        val = data.get(field, "")
        if not val or not _is_valid_uuid(val):
            errors.append(f"{field} must be a valid UUID")
        else:
            clean[field] = val

    sd = data.get("scheduled_date")
    if not sd:
        errors.append("scheduled_date is required (YYYY-MM-DD)")
    else:
        try:
            clean["scheduled_date"] = date.fromisoformat(str(sd))
        except ValueError:
            errors.append("scheduled_date must be YYYY-MM-DD")

    for field in ("start_time", "end_time"):
        val = data.get(field)
        if not val:
            errors.append(f"{field} is required (ISO-8601)")
        else:
            try:
                clean[field] = datetime.fromisoformat(str(val))
            except ValueError:
                errors.append(f"{field} must be ISO-8601")

    if "start_time" in clean and "end_time" in clean:
        if clean["end_time"] <= clean["start_time"]:
            errors.append("end_time must be after start_time")

    return clean, errors
