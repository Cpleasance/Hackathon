"""
Analytics Engine — Predictive Forecasting
------------------------------------------
Processes historical scheduling data to:
  - Forecast demand by day-of-week and hour
  - Detect no-show patterns
  - Recommend staffing adjustments
  - Identify peak/off-peak utilisation
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date, timedelta, timezone

from sqlalchemy import func, extract, and_
from sqlalchemy.orm import Session

from backend.models import Task, TaskSchedule, Employee


def get_utilisation_by_employee(session: Session, start_date: date, end_date: date) -> list[dict]:
    """
    Calculate utilisation % for each employee over a date range.
    Utilisation = booked_minutes / available_minutes * 100
    """
    results = (
        session.query(
            TaskSchedule.employee_id,
            Employee.name,
            Employee.daily_minutes,
            func.count(TaskSchedule.id).label("appointment_count"),
            func.sum(
                extract("epoch", TaskSchedule.end_time - TaskSchedule.start_time) / 60
            ).label("booked_minutes"),
        )
        .join(Employee, TaskSchedule.employee_id == Employee.id)
        .filter(
            TaskSchedule.scheduled_date.between(start_date, end_date),
            TaskSchedule.status.notin_(["cancelled"]),
        )
        .group_by(TaskSchedule.employee_id, Employee.name, Employee.daily_minutes)
        .all()
    )

    working_days = (end_date - start_date).days + 1
    output = []
    for r in results:
        total_avail = r.daily_minutes * working_days
        booked = float(r.booked_minutes or 0)
        output.append({
            "employee_id": str(r.employee_id),
            "employee_name": r.name,
            "appointment_count": r.appointment_count,
            "booked_minutes": round(booked, 1),
            "available_minutes": total_avail,
            "utilisation_pct": round((booked / total_avail * 100) if total_avail > 0 else 0, 1),
        })

    return sorted(output, key=lambda x: x["utilisation_pct"], reverse=True)


def get_demand_by_hour(session: Session, start_date: date, end_date: date) -> list[dict]:
    """
    Aggregate appointment counts by hour-of-day for demand forecasting.
    """
    results = (
        session.query(
            extract("hour", TaskSchedule.start_time).label("hour"),
            func.count(TaskSchedule.id).label("count"),
        )
        .filter(
            TaskSchedule.scheduled_date.between(start_date, end_date),
            TaskSchedule.status.notin_(["cancelled"]),
        )
        .group_by("hour")
        .order_by("hour")
        .all()
    )

    return [{"hour": int(r.hour), "appointments": r.count} for r in results]


def get_demand_by_day(session: Session, start_date: date, end_date: date) -> list[dict]:
    """
    Aggregate appointment counts by day-of-week.
    """
    results = (
        session.query(
            extract("dow", TaskSchedule.scheduled_date).label("dow"),
            func.count(TaskSchedule.id).label("count"),
        )
        .filter(
            TaskSchedule.scheduled_date.between(start_date, end_date),
            TaskSchedule.status.notin_(["cancelled"]),
        )
        .group_by("dow")
        .order_by("dow")
        .all()
    )

    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    return [{"day": day_names[int(r.dow)], "appointments": r.count} for r in results]


def get_no_show_rate(session: Session, lookback_days: int = 90) -> dict:
    """
    Calculate no-show rate over the lookback period.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    total = session.query(func.count(TaskSchedule.id)).filter(
        TaskSchedule.scheduled_date >= cutoff,
    ).scalar() or 0

    no_shows = session.query(func.count(TaskSchedule.id)).filter(
        TaskSchedule.scheduled_date >= cutoff,
        TaskSchedule.status == "no_show",
    ).scalar() or 0

    return {
        "period_days": lookback_days,
        "total_appointments": total,
        "no_shows": no_shows,
        "no_show_rate_pct": round((no_shows / total * 100) if total > 0 else 0, 1),
    }


def get_staffing_recommendation(session: Session, target_date: date) -> dict:
    """
    Based on historical patterns, recommend whether staffing should
    be increased or decreased for target_date.
    """
    # Get average demand for this day-of-week over past 8 weeks
    dow = target_date.weekday()
    schema_dow = (dow + 1) % 7

    lookback_start = target_date - timedelta(weeks=8)
    avg_result = (
        session.query(func.count(TaskSchedule.id).label("cnt"))
        .filter(
            TaskSchedule.scheduled_date >= lookback_start,
            TaskSchedule.scheduled_date < target_date,
            extract("dow", TaskSchedule.scheduled_date) == schema_dow,
            TaskSchedule.status.notin_(["cancelled"]),
        )
        .scalar()
    ) or 0

    weeks = 8
    avg_daily = avg_result / weeks if weeks > 0 else 0

    # Count already scheduled for target
    current = session.query(func.count(TaskSchedule.id)).filter(
        TaskSchedule.scheduled_date == target_date,
        TaskSchedule.status.notin_(["cancelled", "no_show"]),
    ).scalar() or 0

    # Count active employees
    active = session.query(func.count(Employee.id)).filter(
        Employee.is_active.is_(True),
    ).scalar() or 0

    recommendation = "adequate"
    if current > avg_daily * 1.2:
        recommendation = "consider_adding_staff"
    elif current < avg_daily * 0.6 and active > 2:
        recommendation = "consider_reducing_staff"

    return {
        "target_date": target_date.isoformat(),
        "historical_avg_appointments": round(avg_daily, 1),
        "current_bookings": current,
        "active_employees": active,
        "recommendation": recommendation,
    }
