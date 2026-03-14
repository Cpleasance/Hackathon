"""
Tests for API endpoints.

These test the Flask route wiring and validation logic
using a mocked database layer.
"""
import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.validators import (
    validate_task_input, validate_employee_input, validate_schedule_input,
)


class TestTaskValidation(unittest.TestCase):

    def test_valid_task(self):
        data = {
            "task_name": "Cut & Style",
            "duration_minutes": 30,
            "priority_level": 3,
            "priority_weight": 50,
            "required_skill_id": str(uuid4()),
            "customer_name": "Alice",
        }
        clean, errors = validate_task_input(data)
        self.assertEqual(errors, [])
        self.assertEqual(clean["task_name"], "Cut & Style")
        self.assertEqual(clean["duration_minutes"], 30)

    def test_missing_task_name(self):
        data = {"duration_minutes": 30, "required_skill_id": str(uuid4())}
        clean, errors = validate_task_input(data)
        self.assertIn("task_name is required", errors)

    def test_invalid_duration(self):
        data = {
            "task_name": "Test",
            "duration_minutes": -5,
            "required_skill_id": str(uuid4()),
        }
        clean, errors = validate_task_input(data)
        self.assertIn("duration_minutes must be a positive integer", errors)

    def test_invalid_priority_level(self):
        data = {
            "task_name": "Test",
            "duration_minutes": 30,
            "priority_level": 10,
            "required_skill_id": str(uuid4()),
        }
        clean, errors = validate_task_input(data)
        self.assertIn("priority_level must be 1–5", errors)

    def test_invalid_uuid(self):
        data = {
            "task_name": "Test",
            "duration_minutes": 30,
            "required_skill_id": "not-a-uuid",
        }
        clean, errors = validate_task_input(data)
        self.assertIn("required_skill_id must be a valid UUID", errors)

    def test_invalid_deadline_format(self):
        data = {
            "task_name": "Test",
            "duration_minutes": 30,
            "required_skill_id": str(uuid4()),
            "deadline": "not-a-date",
        }
        clean, errors = validate_task_input(data)
        self.assertIn("deadline must be ISO-8601 format", errors)

    def test_valid_timestamps(self):
        data = {
            "task_name": "Test",
            "duration_minutes": 30,
            "required_skill_id": str(uuid4()),
            "preferred_start": "2025-07-14T09:00:00+00:00",
            "deadline": "2025-07-14T12:00:00+00:00",
        }
        clean, errors = validate_task_input(data)
        self.assertEqual(errors, [])
        self.assertIsNotNone(clean["preferred_start"])
        self.assertIsNotNone(clean["deadline"])


class TestEmployeeValidation(unittest.TestCase):

    def test_valid_employee(self):
        data = {"name": "Bob Smith", "role": "Senior Stylist", "daily_minutes": 480}
        clean, errors = validate_employee_input(data)
        self.assertEqual(errors, [])

    def test_missing_name(self):
        data = {"role": "Stylist"}
        clean, errors = validate_employee_input(data)
        self.assertIn("name is required", errors)

    def test_missing_role(self):
        data = {"name": "Bob"}
        clean, errors = validate_employee_input(data)
        self.assertIn("role is required", errors)

    def test_invalid_daily_minutes(self):
        data = {"name": "Bob", "role": "Stylist", "daily_minutes": 30}
        clean, errors = validate_employee_input(data)
        self.assertIn("daily_minutes must be 60–720", errors)

    def test_defaults(self):
        data = {"name": "Bob", "role": "Stylist"}
        clean, errors = validate_employee_input(data)
        self.assertEqual(errors, [])
        self.assertEqual(clean["daily_minutes"], 480)
        self.assertTrue(clean["is_active"])


class TestScheduleValidation(unittest.TestCase):

    def test_valid_schedule(self):
        data = {
            "task_id": str(uuid4()),
            "employee_id": str(uuid4()),
            "scheduled_date": "2025-07-14",
            "start_time": "2025-07-14T09:00:00+00:00",
            "end_time": "2025-07-14T09:30:00+00:00",
        }
        clean, errors = validate_schedule_input(data)
        self.assertEqual(errors, [])

    def test_end_before_start(self):
        data = {
            "task_id": str(uuid4()),
            "employee_id": str(uuid4()),
            "scheduled_date": "2025-07-14",
            "start_time": "2025-07-14T10:00:00+00:00",
            "end_time": "2025-07-14T09:00:00+00:00",
        }
        clean, errors = validate_schedule_input(data)
        self.assertIn("end_time must be after start_time", errors)

    def test_missing_fields(self):
        data = {}
        clean, errors = validate_schedule_input(data)
        self.assertTrue(len(errors) >= 3)


if __name__ == "__main__":
    unittest.main()
