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
                func.extract("epoch", TaskSchedule.end_time - TaskSchedule.start_time) / 60
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
            func.extract("dow", TaskSchedule.scheduled_date).label("dow"),
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
            func.extract("dow", TaskSchedule.scheduled_date) == schema_dow,
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


def get_peak_times(session: Session, start_date: date, end_date: date) -> dict:
    """
    Identify the top peak hours and peak days from real schedule data.
    Returns top 3 peak hours and top 3 peak days with appointment counts.
    """
    hourly = get_demand_by_hour(session, start_date, end_date)
    daily = get_demand_by_day(session, start_date, end_date)

    # Sort by appointment count descending
    sorted_hours = sorted(hourly, key=lambda x: x["appointments"], reverse=True)
    sorted_days = sorted(daily, key=lambda x: x["appointments"], reverse=True)

    peak_hours = sorted_hours[:3]
    off_peak_hours = sorted_hours[-3:] if len(sorted_hours) >= 3 else []
    peak_days = sorted_days[:3]
    quiet_days = sorted_days[-3:] if len(sorted_days) >= 3 else []

    return {
        "peak_hours": peak_hours,
        "off_peak_hours": list(reversed(off_peak_hours)),
        "peak_days": peak_days,
        "quiet_days": list(reversed(quiet_days)),
    }


def get_recommendations(session: Session, start_date: date, end_date: date) -> dict:
    """
    Generate actionable recommendations for the calendar manager based on
    utilisation, demand patterns, and no-show rates.
    """
    utilisation = get_utilisation_by_employee(session, start_date, end_date)
    hourly = get_demand_by_hour(session, start_date, end_date)
    daily = get_demand_by_day(session, start_date, end_date)
    no_show = get_no_show_rate(session, 90)
    peaks = get_peak_times(session, start_date, end_date)

    advisories = []

    # Utilisation-based advisories
    overloaded = [e for e in utilisation if e["utilisation_pct"] > 85]
    underused = [e for e in utilisation if e["utilisation_pct"] < 40]

    if overloaded:
        names = ", ".join(e["employee_name"] for e in overloaded[:3])
        advisories.append({
            "type": "warning",
            "category": "Staff Capacity",
            "message": f"{names} {'are' if len(overloaded) > 1 else 'is'} over 85% utilised. "
                       f"Consider redistributing appointments or adding capacity.",
        })

    if underused:
        names = ", ".join(e["employee_name"] for e in underused[:3])
        advisories.append({
            "type": "info",
            "category": "Staff Efficiency",
            "message": f"{names} {'are' if len(underused) > 1 else 'is'} under 40% utilised. "
                       f"Consider consolidating their appointments or adjusting hours.",
        })

    # No-show advisory
    if no_show["no_show_rate_pct"] > 10:
        advisories.append({
            "type": "warning",
            "category": "No-Show Rate",
            "message": f"No-show rate is {no_show['no_show_rate_pct']}% over the last {no_show['period_days']} days "
                       f"({no_show['no_shows']} of {no_show['total_appointments']} appointments). "
                       f"Consider implementing reminder notifications or a cancellation policy.",
        })
    elif no_show["no_show_rate_pct"] <= 5 and no_show["total_appointments"] > 0:
        advisories.append({
            "type": "success",
            "category": "No-Show Rate",
            "message": f"Excellent no-show rate of {no_show['no_show_rate_pct']}%. "
                       f"Your reminder and booking policies are working well.",
        })

    # Peak hour advisory
    if peaks["peak_hours"]:
        top_hour = peaks["peak_hours"][0]
        advisories.append({
            "type": "info",
            "category": "Peak Demand",
            "message": f"Busiest time slot is {top_hour['hour']}:00 with {top_hour['appointments']} appointments. "
                       f"Ensure adequate staffing during this window.",
        })

    # Peak day advisory
    if peaks["peak_days"]:
        top_day = peaks["peak_days"][0]
        advisories.append({
            "type": "info",
            "category": "Busiest Day",
            "message": f"{top_day['day']} is your busiest day with {top_day['appointments']} appointments. "
                       f"Prioritise scheduling your most skilled staff on this day.",
        })

    # Quiet day opportunity
    if peaks["quiet_days"]:
        quiet = peaks["quiet_days"][0]
        advisories.append({
            "type": "tip",
            "category": "Growth Opportunity",
            "message": f"{quiet['day']} has the lowest demand ({quiet['appointments']} appointments). "
                       f"Consider promotions or discounted slots to drive bookings on this day.",
        })

    if not advisories:
        advisories.append({
            "type": "success",
            "category": "Overall Health",
            "message": "Scheduling patterns look healthy. No significant issues detected in the selected period.",
        })

    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "advisories": advisories,
        "peaks": peaks,
    }


def get_trends(session: Session, start_date: date, end_date: date) -> dict:
    """
    Compare current period utilisation to the previous period of the same length
    to find most improved and most declined employees, as well as high/low demand.
    """
    period_days = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)

    current_util = get_utilisation_by_employee(session, start_date, end_date)
    prev_util = get_utilisation_by_employee(session, prev_start, prev_end)

    prev_map = {u["employee_id"]: u["utilisation_pct"] for u in prev_util}

    trends = []
    for cur in current_util:
        prev_pct = prev_map.get(cur["employee_id"], 0)
        diff = cur["utilisation_pct"] - prev_pct
        trends.append({
            "employee_id": cur["employee_id"],
            "employee_name": cur["employee_name"],
            "current_pct": cur["utilisation_pct"],
            "previous_pct": prev_pct,
            "change": round(diff, 1),
        })

    # Sort by change
    trends.sort(key=lambda x: x["change"], reverse=True)

    most_improved = [t for t in trends if t["change"] > 0][:3]
    most_declined = [t for t in reversed(trends) if t["change"] < 0][:3]

    # Sort by pure demand (appointments)
    demand_sorted = sorted(current_util, key=lambda x: x["appointment_count"], reverse=True)
    high_demand = demand_sorted[:3]
    low_demand = demand_sorted[-3:] if len(demand_sorted) >= 3 else []

    return {
        "period_days": period_days,
        "most_improved": most_improved,
        "most_declined": most_declined,
        "highest_demand": high_demand,
        "lowest_demand": low_demand,
    }


def get_customer_insights(session: Session, start_date: date, end_date: date) -> dict:
    """
    Analyse customer behaviour: recurring customers, top customers, preferred services,
    and cancellation/churn metrics.
    """
    from sqlalchemy.orm import aliased
    from backend.models import Skill

    # All tasks with a customer name in the period
    query = (
        session.query(
            Task.customer_name,
            TaskSchedule.status,
            Skill.name.label("service_name"),
            Employee.name.label("employee_name"),
        )
        .join(TaskSchedule, Task.id == TaskSchedule.task_id)
        .join(Skill, Task.required_skill_id == Skill.id)
        .join(Employee, TaskSchedule.employee_id == Employee.id)
        .filter(
            Task.customer_name.isnot(None),
            Task.customer_name != "",
            TaskSchedule.scheduled_date.between(start_date, end_date),
        )
    )

    records = query.all()

    customer_stats = defaultdict(lambda: {
        "total": 0, "completed": 0, "cancelled": 0, "no_show": 0,
        "services": {}, "employees": {}
    })

    total_appointments = len(records)
    total_cancelled = 0

    for r in records:
        cust = r.customer_name
        st = r.status
        svc = r.service_name
        emp = r.employee_name

        customer_stats[cust]["total"] += 1
        if st == "cancelled":
            customer_stats[cust]["cancelled"] += 1
            total_cancelled += 1
        elif st == "no_show":
            customer_stats[cust]["no_show"] += 1
        else:
            customer_stats[cust]["completed"] += 1

        customer_stats[cust]["services"][svc] = customer_stats[cust]["services"].get(svc, 0) + 1
        customer_stats[cust]["employees"][emp] = customer_stats[cust]["employees"].get(emp, 0) + 1

    # Format the top customers
    customers_list = []
    for name, stats in customer_stats.items():
        # Find top service
        fav_svc = max(stats["services"].items(), key=lambda x: x[1])[0] if stats["services"] else "Unknown"
        # Find top employee
        fav_emp = max(stats["employees"].items(), key=lambda x: x[1])[0] if stats["employees"] else "Unknown"

        churn_risk = False
        # Simple proxy for churn risk: Multiple cancellations/no-shows or high cancel rate
        fail_rate = (stats["cancelled"] + stats["no_show"]) / stats["total"]
        if stats["total"] > 1 and fail_rate >= 0.5:
            churn_risk = True

        customers_list.append({
            "name": name,
            "total_appointments": stats["total"],
            "completed": stats["completed"],
            "cancellations": stats["cancelled"],
            "no_shows": stats["no_show"],
            "favourite_service": fav_svc,
            "favourite_employee": fav_emp,
            "churn_risk": churn_risk,
        })

    # Sort by total appointments to find "Top/Recurring"
    customers_list.sort(key=lambda x: x["total_appointments"], reverse=True)
    top_customers = customers_list[:10]
    returning = [c for c in customers_list if c["total_appointments"] > 1]
    at_risk = [c for c in customers_list if c["churn_risk"]]

    cancellation_rate = round((total_cancelled / total_appointments * 100) if total_appointments > 0 else 0, 1)

    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "total_tracked_customers": len(customer_stats),
        "recurring_customers": len(returning),
        "cancellation_rate_pct": cancellation_rate,
        "top_customers": top_customers,
        "churn_risk_customers": at_risk,
    }
