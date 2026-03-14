"""
Scheduler — Flask Application Factory
"""
import os
import sys

# Ensure the project root is on sys.path so `backend.*` imports work
# regardless of the working directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.config import config_map
from backend.models import init_db, remove_session
from backend.api import ALL_BLUEPRINTS
from backend.utils.errors import register_error_handlers


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    cfg = config_map.get(config_name, config_map["development"])

    app = Flask(
        __name__,
        static_folder=os.path.join(_PROJECT_ROOT, "frontend"),
        static_url_path="",
    )
    app.config.from_object(cfg)

    # CORS for API routes
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Database
    init_db(cfg.DATABASE_URL, echo=cfg.SQLALCHEMY_ECHO)

    # Teardown — release scoped session after each request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        remove_session()

    # Register error handlers
    register_error_handlers(app)

    # Register API blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Serve the frontend SPA
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    # Settings endpoint (read-only)
    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        from flask import jsonify
        return jsonify(cfg.SETTINGS)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
