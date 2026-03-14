"""
Buffer Zone Calculator
---------------------
Computes automatic prep/cleanup buffers between appointments to
prevent cascading delays.  Buffer duration varies by skill category.
"""
from __future__ import annotations

import json
from pathlib import Path

_SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"

_buffer_config_cache: dict | None = None


def _load_buffer_config() -> dict:
    global _buffer_config_cache
    if _buffer_config_cache is None:
        with open(_SETTINGS_PATH) as fh:
            _buffer_config_cache = json.load(fh).get("scheduling", {})
    return _buffer_config_cache


def get_buffer_minutes(skill_category: str | None) -> int:
    """
    Return the buffer minutes to add after a task of the given skill category.

    Falls back to the default buffer if no category-specific override exists.
    """
    cfg = _load_buffer_config()
    if skill_category:
        key = f"buffer_minutes_{skill_category.lower()}"
        if key in cfg:
            return int(cfg[key])
    return int(cfg.get("buffer_minutes_default", 5))


def calculate_effective_end(start_iso: str, duration_minutes: int, skill_category: str | None) -> dict:
    """
    Given a start time, task duration, and skill category, return:
      - task_end     : when the task itself finishes
      - buffer_end   : when the buffer period ends (next slot available)
      - buffer_minutes: the buffer applied
    """
    from datetime import datetime, timedelta

    start = datetime.fromisoformat(start_iso)
    buf = get_buffer_minutes(skill_category)
    task_end = start + timedelta(minutes=duration_minutes)
    buffer_end = task_end + timedelta(minutes=buf)
    return {
        "task_end": task_end.isoformat(),
        "buffer_end": buffer_end.isoformat(),
        "buffer_minutes": buf,
    }
