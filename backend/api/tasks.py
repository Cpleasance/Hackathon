"""Tasks CRUD API."""
from flask import Blueprint, request, jsonify
from backend.models import Task, get_session
from backend.utils.errors import NotFoundError, ValidationError
from backend.utils.validators import validate_task_input

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@bp.route("", methods=["GET"])
def list_tasks():
    session = get_session()
    status_filter = request.args.get("status")
    q = session.query(Task)
    if status_filter:
        q = q.filter(Task.status == status_filter)
    tasks = q.order_by(Task.priority_weight.desc(), Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])


@bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    session = get_session()
    t = session.query(Task).filter_by(id=task_id).first()
    if not t:
        raise NotFoundError("Task not found")
    return jsonify(t.to_dict())


@bp.route("", methods=["POST"])
def create_task():
    data = request.get_json(force=True)
    clean, errors = validate_task_input(data)
    if errors:
        raise ValidationError("; ".join(errors))
    session = get_session()
    task = Task(**clean)
    session.add(task)
    session.commit()
    return jsonify(task.to_dict()), 201


@bp.route("/<task_id>", methods=["PUT"])
def update_task(task_id):
    session = get_session()
    task = session.query(Task).filter_by(id=task_id).first()
    if not task:
        raise NotFoundError("Task not found")
    data = request.get_json(force=True)
    clean, errors = validate_task_input(data)
    if errors:
        raise ValidationError("; ".join(errors))
    for k, v in clean.items():
        setattr(task, k, v)
    session.commit()
    return jsonify(task.to_dict())


@bp.route("/<task_id>", methods=["DELETE"])
def cancel_task(task_id):
    session = get_session()
    task = session.query(Task).filter_by(id=task_id).first()
    if not task:
        raise NotFoundError("Task not found")
    if task.schedule:
        session.delete(task.schedule)
    session.delete(task)
    session.commit()
    return jsonify({"status": "deleted", "task_id": task_id})
