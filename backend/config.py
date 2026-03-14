"""
Environment-based configuration for the Scheduler application.
"""
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.json"


def _load_settings():
    """Load operational settings from JSON config."""
    with open(SETTINGS_PATH, "r") as fh:
        return json.load(fh)


class Config:
    """Base configuration — always inherits from this."""
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR}/scheduler.db",
    )
    SQLALCHEMY_ECHO = False
    SETTINGS = _load_settings()
    # Scheduling
    BUFFER_DEFAULTS = SETTINGS.get("scheduling", {})
    PRIORITY_WEIGHTS = SETTINGS.get("priority", {})
    BUSINESS = SETTINGS.get("business", {})
    ANALYTICS = SETTINGS.get("analytics", {})


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://scheduler:scheduler@localhost:5432/scheduler_test",
    )


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
