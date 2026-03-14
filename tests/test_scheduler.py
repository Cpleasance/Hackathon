"""
Tests for core scheduling services.

Run with: python -m pytest tests/ -v
(Requires a test database — set TEST_DATABASE_URL)
"""
import sys
import os
import unittest
from datetime import datetime, date, time, timedelta, timezone
from unittest.mock import patch, MagicMock

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.priority_engine import urgency_score, revenue_proxy, composite_score, rank_tasks
from backend.services.buffer_calculator import get_buffer_minutes, calculate_effective_end


class TestUrgencyScore(unittest.TestCase):
    """Test the urgency scoring function."""

    def test_no_deadline_returns_neutral(self):
        self.assertAlmostEqual(urgency_score(None), 0.3)

    def test_past_deadline_returns_max(self):
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(urgency_score(past, now), 1.0)

    def test_far_future_deadline_returns_low(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(hours=72)
        score = urgency_score(deadline, now)
        self.assertLessEqual(score, 0.15)

    def test_imminent_deadline_returns_high(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(hours=1)
        score = urgency_score(deadline, now)
        self.assertGreater(score, 0.9)

    def test_24h_deadline_is_midrange(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(hours=24)
        score = urgency_score(deadline, now)
        self.assertGreater(score, 0.4)
        self.assertLess(score, 0.7)


class TestRevenueProxy(unittest.TestCase):
    """Test the revenue proxy from duration."""

    def test_short_task(self):
        self.assertAlmostEqual(revenue_proxy(15), 15 / 120.0)

    def test_long_task_caps_at_one(self):
        self.assertEqual(revenue_proxy(180), 1.0)

    def test_standard_task(self):
        self.assertAlmostEqual(revenue_proxy(60), 0.5)


class TestCompositeScore(unittest.TestCase):
    """Test the weighted composite scoring."""

    def test_high_priority_scores_higher(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        high = composite_score(90, None, 60, "vip", now)
        low = composite_score(20, None, 60, "new", now)
        self.assertGreater(high, low)

    def test_urgent_deadline_boosts_score(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        urgent = composite_score(50, now + timedelta(hours=1), 30, "new", now)
        relaxed = composite_score(50, now + timedelta(hours=72), 30, "new", now)
        self.assertGreater(urgent, relaxed)

    def test_vip_scores_higher_than_new(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        vip = composite_score(50, None, 30, "vip", now)
        new = composite_score(50, None, 30, "new", now)
        self.assertGreater(vip, new)

    def test_score_is_positive(self):
        score = composite_score(1, None, 15, "new")
        self.assertGreater(score, 0)


class TestRankTasks(unittest.TestCase):
    """Test task ranking by composite score."""

    def test_ranking_order(self):
        now = datetime(2025, 7, 14, 9, 0, tzinfo=timezone.utc)
        tasks = [
            {"priority_weight": 20, "deadline": None, "duration_minutes": 15, "name": "low"},
            {"priority_weight": 90, "deadline": now + timedelta(hours=1), "duration_minutes": 60, "name": "critical"},
            {"priority_weight": 50, "deadline": None, "duration_minutes": 30, "name": "medium"},
        ]
        ranked = rank_tasks(tasks, now)
        self.assertEqual(ranked[0]["name"], "critical")
        self.assertEqual(ranked[-1]["name"], "low")

    def test_all_tasks_get_scores(self):
        tasks = [
            {"priority_weight": 50, "deadline": None, "duration_minutes": 30},
        ]
        ranked = rank_tasks(tasks)
        self.assertIn("_score", ranked[0])
        self.assertIsInstance(ranked[0]["_score"], float)


class TestBufferCalculator(unittest.TestCase):
    """Test buffer zone computation."""

    def test_default_buffer(self):
        buf = get_buffer_minutes(None)
        self.assertEqual(buf, 5)

    def test_colour_buffer(self):
        buf = get_buffer_minutes("colour")
        self.assertEqual(buf, 10)

    def test_treatment_buffer(self):
        buf = get_buffer_minutes("treatment")
        self.assertEqual(buf, 10)

    def test_unknown_category_uses_default(self):
        buf = get_buffer_minutes("unknown_category_xyz")
        self.assertEqual(buf, 5)

    def test_effective_end_calculation(self):
        result = calculate_effective_end("2025-07-14T09:00:00+00:00", 30, "hair")
        self.assertEqual(result["buffer_minutes"], 5)
        task_end = datetime.fromisoformat(result["task_end"])
        buffer_end = datetime.fromisoformat(result["buffer_end"])
        self.assertEqual((buffer_end - task_end).total_seconds(), 5 * 60)

    def test_colour_effective_end(self):
        result = calculate_effective_end("2025-07-14T10:00:00+00:00", 60, "colour")
        self.assertEqual(result["buffer_minutes"], 10)
        task_end = datetime.fromisoformat(result["task_end"])
        # task_end should be 11:00
        self.assertEqual(task_end.hour, 11)
        buffer_end = datetime.fromisoformat(result["buffer_end"])
        # buffer_end should be 11:10
        self.assertEqual(buffer_end.minute, 10)


if __name__ == "__main__":
    unittest.main()
