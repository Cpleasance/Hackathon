"""
Weighted Priority Engine
------------------------
Computes a composite scheduling score for each task by combining:
  - priority_weight   (from the task itself, 1–100)
  - urgency factor    (derived from deadline proximity)
  - loyalty tier      (customer loyalty multiplier, when available)
  - revenue potential  (mapped from task duration as proxy)

The engine sorts the unassigned queue so the scheduler processes
the most valuable / urgent tasks first.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

_SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"

_priority_config_cache: dict | None = None


def _load_priority_config() -> dict:
    global _priority_config_cache
    if _priority_config_cache is None:
        with open(_SETTINGS_PATH) as fh:
            _priority_config_cache = json.load(fh).get("priority", {})
    return _priority_config_cache


def urgency_score(deadline: datetime | None, now: datetime | None = None) -> float:
    """
    0.0 – 1.0 urgency score.  Tasks with no deadline get 0.3 (neutral).
    Tasks past deadline get 1.0 (critical).
    """
    if deadline is None:
        return 0.3
    if now is None:
        now = datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    hours_remaining = (deadline - now).total_seconds() / 3600
    if hours_remaining <= 0:
        return 1.0
    if hours_remaining >= 48:
        return 0.1
    # Linear ramp: 48h→0.1  …  0h→1.0
    return round(1.0 - (hours_remaining / 48) * 0.9, 3)


def revenue_proxy(duration_minutes: int) -> float:
    """
    Normalised 0–1 revenue score based on duration.
    Longer appointments generally generate more revenue.
    """
    return min(duration_minutes / 120.0, 1.0)


def composite_score(
    priority_weight: int,
    deadline: datetime | None,
    duration_minutes: int,
    loyalty_tier: str = "new",
    now: datetime | None = None,
) -> float:
    """
    Compute a weighted composite score for scheduling priority.

    Returns a float ≥ 0.  Higher = schedule sooner.
    """
    cfg = _load_priority_config()
    w_urg = cfg.get("urgency_weight", 0.3)
    w_rev = cfg.get("revenue_weight", 0.4)
    w_loy = cfg.get("loyalty_weight", 0.3)

    tiers = cfg.get("loyalty_tiers", {"new": 1, "regular": 2, "vip": 3})
    loyalty_val = tiers.get(loyalty_tier, 1) / max(tiers.values())

    urg = urgency_score(deadline, now)
    rev = revenue_proxy(duration_minutes)

    # Normalise priority_weight to 0–1
    pw_norm = priority_weight / 100.0

    score = pw_norm * 0.4 + urg * w_urg + rev * w_rev + loyalty_val * w_loy
    return round(score, 4)


def rank_tasks(tasks: list[dict], now: datetime | None = None) -> list[dict]:
    """
    Rank a list of task dicts by composite score (descending).
    Each dict must contain: priority_weight, deadline, duration_minutes.
    Optional: loyalty_tier.
    """
    for t in tasks:
        t["_score"] = composite_score(
            priority_weight=t.get("priority_weight", 50),
            deadline=t.get("deadline"),
            duration_minutes=t.get("duration_minutes", 30),
            loyalty_tier=t.get("loyalty_tier", "new"),
            now=now,
        )
    return sorted(tasks, key=lambda t: t["_score"], reverse=True)
