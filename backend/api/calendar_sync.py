"""
External Calendar Synchronisation API
--------------------------------------
Provides endpoints for bi-directional sync with Google Calendar / Outlook.
This module defines the contract; actual OAuth + calendar provider
integration requires API keys configured at deployment.
"""
from flask import Blueprint, request, jsonify
from backend.utils.errors import ValidationError

bp = Blueprint("calendar_sync", __name__, url_prefix="/api/calendar")


@bp.route("/sync", methods=["POST"])
def trigger_sync():
    """
    Trigger a sync for a given employee's external calendar.
    Body: { "employee_id": "...", "provider": "google|outlook" }
    """
    data = request.get_json(force=True)
    employee_id = data.get("employee_id")
    provider = data.get("provider")
    if not employee_id or not provider:
        raise ValidationError("employee_id and provider are required")
    if provider not in ("google", "outlook"):
        raise ValidationError("provider must be 'google' or 'outlook'")

    # Placeholder — in production, this calls the OAuth-authenticated
    # calendar API and upserts availability overrides.
    return jsonify({
        "status": "sync_initiated",
        "employee_id": employee_id,
        "provider": provider,
        "message": "Calendar sync requires OAuth configuration. See deployment docs.",
    })


@bp.route("/webhook", methods=["POST"])
def calendar_webhook():
    """
    Receive push notifications from calendar providers for real-time
    availability updates.
    """
    # Placeholder — validates signature, parses event, updates availability
    return jsonify({"status": "received"}), 200
