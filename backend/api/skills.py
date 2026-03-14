"""Skills CRUD API."""
from flask import Blueprint, request, jsonify
from backend.models import Skill, get_session
from backend.utils.errors import NotFoundError, ValidationError

bp = Blueprint("skills", __name__, url_prefix="/api/skills")


@bp.route("", methods=["GET"])
def list_skills():
    session = get_session()
    skills = session.query(Skill).order_by(Skill.name).all()
    return jsonify([s.to_dict() for s in skills])


@bp.route("/<skill_id>", methods=["GET"])
def get_skill(skill_id):
    session = get_session()
    s = session.query(Skill).filter_by(id=skill_id).first()
    if not s:
        raise NotFoundError("Skill not found")
    return jsonify(s.to_dict())


@bp.route("", methods=["POST"])
def create_skill():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    session = get_session()
    s = Skill(name=name, category=data.get("category"), description=data.get("description"))
    session.add(s)
    session.commit()
    return jsonify(s.to_dict()), 201
