"""Analytics & forecasting API."""
from datetime import date, timedelta
from flask import Blueprint, request, jsonify
from backend.models import get_session
from backend.utils.errors import ValidationError
from backend.services.analytics_engine import (
    get_utilisation_by_employee, get_demand_by_hour, get_demand_by_day,
    get_no_show_rate, get_staffing_recommendation, get_peak_times,
    get_recommendations,
)

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def _parse_date_range():
    """Parse start_date / end_date from query params with sensible defaults."""
    today = date.today()
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    try:
        start_date = date.fromisoformat(start) if start else today - timedelta(days=30)
        end_date = date.fromisoformat(end) if end else today
    except ValueError:
        raise ValidationError("Dates must be YYYY-MM-DD")
    return start_date, end_date


@bp.route("/utilisation", methods=["GET"])
def utilisation():
    start_date, end_date = _parse_date_range()
    session = get_session()
    data = get_utilisation_by_employee(session, start_date, end_date)
    return jsonify({"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "data": data})


@bp.route("/demand/hourly", methods=["GET"])
def demand_hourly():
    start_date, end_date = _parse_date_range()
    session = get_session()
    data = get_demand_by_hour(session, start_date, end_date)
    return jsonify({"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "data": data})


@bp.route("/demand/daily", methods=["GET"])
def demand_daily():
    start_date, end_date = _parse_date_range()
    session = get_session()
    data = get_demand_by_day(session, start_date, end_date)
    return jsonify({"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "data": data})


@bp.route("/no-shows", methods=["GET"])
def no_shows():
    lookback = int(request.args.get("lookback_days", 90))
    session = get_session()
    data = get_no_show_rate(session, lookback)
    return jsonify(data)


@bp.route("/staffing", methods=["GET"])
def staffing():
    d = request.args.get("date")
    if not d:
        raise ValidationError("date query parameter required (YYYY-MM-DD)")
    try:
        target = date.fromisoformat(d)
    except ValueError:
        raise ValidationError("date must be YYYY-MM-DD")
    session = get_session()
    data = get_staffing_recommendation(session, target)
    return jsonify(data)


@bp.route("/peaks", methods=["GET"])
def peaks():
    start_date, end_date = _parse_date_range()
    session = get_session()
    data = get_peak_times(session, start_date, end_date)
    return jsonify({"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "data": data})


@bp.route("/recommendations", methods=["GET"])
def recommendations():
    start_date, end_date = _parse_date_range()
    session = get_session()
    data = get_recommendations(session, start_date, end_date)
    return jsonify(data)
