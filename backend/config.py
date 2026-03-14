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


_SUPABASE_URL = "postgresql://postgres.wjnykbqpwodjxsumqcoe:P9rStDvUmWvWRWRF@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"


class Config:
    """Base configuration — always inherits from this."""
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    DATABASE_URL = os.environ.get("DATABASE_URL", _SUPABASE_URL)
    SQLALCHEMY_ECHO = False
    SETTINGS = _load_settings()
    BUFFER_DEFAULTS = SETTINGS.get("scheduling", {})
    PRIORITY_WEIGHTS = SETTINGS.get("priority", {})
    BUSINESS = SETTINGS.get("business", {})
    ANALYTICS = SETTINGS.get("analytics", {})
    # Operating days as 1–7 (Mon=1…Sun=7); fall back to Mon–Sat if not set
    OPERATING_DAYS = BUSINESS.get("operating_days_1_7") or [1, 2, 3, 4, 5, 6]


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _SUPABASE_URL)


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
