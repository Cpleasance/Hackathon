"""
Centralised error types and error-response helper.
"""
from flask import jsonify


class SchedulerError(Exception):
    """Base exception for all scheduler-domain errors."""
    status_code = 400

    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload or {}


class NotFoundError(SchedulerError):
    status_code = 404


class ConflictError(SchedulerError):
    """Raised when a scheduling conflict is detected."""
    status_code = 409


class ValidationError(SchedulerError):
    status_code = 422


def register_error_handlers(app):
    """Attach JSON error handlers to the Flask app."""

    @app.errorhandler(SchedulerError)
    def handle_scheduler_error(exc):
        resp = {"error": exc.message, **exc.payload}
        return jsonify(resp), exc.status_code

    @app.errorhandler(404)
    def handle_404(_):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def handle_500(_):
        return jsonify({"error": "Internal server error"}), 500
