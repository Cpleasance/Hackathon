#!/usr/bin/env python3
"""
Comprehensive seed script for the Scheduler Supabase database.
Populates skills, employees with availability, and lots of realistic tasks.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("FLASK_ENV", "development")

from backend.models.database import init_db, get_session, Skill, Employee, EmployeeSkill, EmployeeAvailability, EmployeeBreak, Task, TaskSchedule
from backend.config import Config
import uuid
from datetime import datetime, date, time, timedelta, timezone
import random

DB_URL = Config.DATABASE_URL
print(f"Connecting to: {DB_URL[:40]}...")
engine = init_db(DB_URL, echo=False)
session = get_session()

def uid():
    return str(uuid.uuid4())

def to_utc(d, h, m=0):
    return datetime(d.year, d.month, d.day, h, m, 0)

# -------------------------------------------------------
# Wipe existing data (cascade)
# -------------------------------------------------------
print("Clearing data...")
try:
    session.query(TaskSchedule).delete(synchronize_session=False)
    session.query(Task).delete(synchronize_session=False)
    session.query(EmployeeAvailability).delete(synchronize_session=False)
    session.query(EmployeeSkill).delete(synchronize_session=False)
    session.query(Employee).delete(synchronize_session=False)
    session.query(Skill).delete(synchronize_session=False)
    session.commit()
    print("  Cleared.")
except Exception as e:
    session.rollback()
    print(f"  Warning during clear: {e}")

# -------------------------------------------------------
# Skills
# -------------------------------------------------------
skills_data = [
    ("Haircut & Style", "hair"),
    ("Hair Colouring", "colour"),
    ("Beard Trim & Shape", "hair"),
    ("Highlights & Balayage", "colour"),
    ("Deep Conditioning Treatment", "treatment"),
    ("Nail Care & Manicure", "beauty"),
    ("Scalp Treatment", "treatment"),
    ("Keratin Straightening", "treatment"),
    ("Eyebrow Threading", "beauty"),
    ("Waxing", "beauty"),
    ("Hair Extensions", "hair"),
    ("Pedicure", "beauty"),
]

skill_objs = {}
print("Creating skills...")
for name, cat in skills_data:
    s = Skill(id=uid(), name=name, category=cat)
    session.add(s)
    skill_objs[name] = s
session.commit()
print(f"  {len(skill_objs)} skills created.")

# -------------------------------------------------------
# Employees
# -------------------------------------------------------
employees_data = [
    ("Alice Mercer",    "Senior Stylist",       480, "active",   "alice@salon.example",  ["Haircut & Style","Hair Colouring","Highlights & Balayage","Keratin Straightening"],  [5,4,4,3]),
    ("Ben Cartwright",  "Barber",               450, "active",   "ben@salon.example",    ["Haircut & Style","Beard Trim & Shape"],                                               [5,5]),
    ("Carla Santos",    "Colour Specialist",    480, "active",   "carla@salon.example",  ["Hair Colouring","Highlights & Balayage","Keratin Straightening"],                    [5,5,4]),
    ("Darius Obi",      "Junior Stylist",       420, "active",   "darius@salon.example", ["Haircut & Style","Beard Trim & Shape","Deep Conditioning Treatment"],                 [3,2,2]),
    ("Elena Voss",      "Beauty Therapist",     480, "active",   "elena@salon.example",  ["Nail Care & Manicure","Eyebrow Threading","Waxing","Pedicure"],                      [5,5,4,4]),
    ("Fatima Malik",    "Colour Technician",    480, "active",   "fatima@salon.example", ["Hair Colouring","Highlights & Balayage"],                                             [4,5]),
    ("George Hartley",  "Senior Barber",        480, "active",   "george@salon.example", ["Haircut & Style","Beard Trim & Shape","Hair Extensions"],                             [4,5,3]),
    ("Hannah Yip",      "Nail Technician",      480, "active",   "hannah@salon.example", ["Nail Care & Manicure","Pedicure","Waxing","Eyebrow Threading"],                      [5,5,3,4]),
    ("Ivan Petrov",     "Treatment Specialist", 480, "sick",     "ivan@salon.example",   ["Scalp Treatment","Deep Conditioning Treatment","Keratin Straightening"],              [5,5,3]),
    ("Julia Novak",     "Stylist",              480, "holiday",  "julia@salon.example",  ["Haircut & Style","Hair Colouring","Hair Extensions"],                                 [4,3,3]),
]

holiday_until_date = date(2026, 3, 25)

emp_objs = {}
print("Creating employees...")
for name, role, dm, status, email, skills, proficiencies in employees_data:
    e = Employee(
        id=uid(), name=name, role=role, daily_minutes=dm,
        status=status, is_active=(status == "active"),
        email=email,
        holiday_until=holiday_until_date if status == "holiday" else None
    )
    session.add(e)
    emp_objs[name] = (e, skills, proficiencies)

session.commit()

# Employee skills
print("Assigning skills...")
for name, (emp, skills, profs) in emp_objs.items():
    for sk, pf in zip(skills, profs):
        es = EmployeeSkill(
            employee_id=emp.id,
            skill_id=skill_objs[sk].id,
            proficiency_level=pf
        )
        session.add(es)
session.commit()


# Availability (Mon–Sat for all active/sick employees, 09:00–17:00)
print("Setting availability...")
work_window = [(0, time(9,0), time(17,0)),   # Mon
               (1, time(9,0), time(17,0)),   # Tue
               (2, time(9,0), time(17,0)),   # Wed
               (3, time(9,0), time(17,0)),   # Thu
               (4, time(9,0), time(17,0)),   # Fri
               (5, time(9,0), time(17,0))]   # Sat (align with weekdays for demo)

for name, (emp, skills, profs) in emp_objs.items():
    if emp.status in ("inactive",):
        continue
    for dow, st, et in work_window:
        av = EmployeeAvailability(
            id=uid(), employee_id=emp.id,
            day_of_week=dow, start_time=st, end_time=et,
            is_recurring=True, is_available=True
        )
        session.add(av)
session.commit()

# Standard breaks (lunch + short breaks) for all non-inactive staff
print("Setting standard breaks (lunch & general)...")
standard_breaks = [
    # Morning break
    (time(11, 0), time(11, 15)),
    # Lunch break
    (time(13, 0), time(14, 0)),
    # Afternoon break
    (time(16, 0), time(16, 15)),
]

for name, (emp, skills, profs) in emp_objs.items():
    if emp.status in ("inactive",):
        continue
    for dow, _, _ in work_window:
        for st, et in standard_breaks:
            br = EmployeeBreak(
                id=uid(), employee_id=emp.id,
                day_of_week=dow, start_time=st, end_time=et,
                is_recurring=True,
            )
            session.add(br)
session.commit()

# -------------------------------------------------------
# Tasks — large realistic dataset
# -------------------------------------------------------
today = date(2026, 3, 14)

task_templates = [
    ("Cut & Style — {}", 45, "Haircut & Style", 3, ["Emma Johnson","Sarah Williams","Mike Brown","David Lee","Sophie Turner","Chris Evans","Linda Carter","James Wilson"]),
    ("Full Colour — {}", 120, "Hair Colouring", 4, ["Rachel Green","Monica Bing","Phoebe Buffay","Zoe Clark","Amy Adams","Claire Frost"]),
    ("Highlights & Balayage — {}", 90, "Highlights & Balayage", 4, ["Jessica Parker","Natalie Stone","Kate Bishop","Wanda Maximoff","Laura Palmer","Marie Curie"]),
    ("Beard Trim — {}", 30, "Beard Trim & Shape", 2, ["Tom Hardy","Chris Pratt","Dave Bautista","Ryan Reynolds","Hugh Jackman","Jason Momoa"]),
    ("Deep Conditioning — {}", 60, "Deep Conditioning Treatment", 3, ["Olivia Spencer","Diana Prince","Pepper Potts","Jane Foster","Betty Ross"]),
    ("Full Set Manicure — {}", 60, "Nail Care & Manicure", 3, ["Scarlett Johansson","Elizabeth Olsen","Tessa Thompson","Lupita Nyongo"]),
    ("Keratin Treatment — {}", 150, "Keratin Straightening", 4, ["Priya Sharma","Maya Angelou","Malala Yousafzai","Nina Simone"]),
    ("Scalp Treatment — {}", 45, "Scalp Treatment", 3, ["James Rhodes","Steve Rogers","Tony Stark","Bruce Banner","Thor Odinson"]),
    ("Eyebrow Threading — {}", 20, "Eyebrow Threading", 2, ["Carol Danvers","Shuri Wakanda","Nakia Okoye","Okoye Wakanda"]),
    ("Pedicure — {}", 50, "Pedicure", 2, ["Audrey Hepburn","Marilyn Monroe","Grace Kelly","Sophia Loren"]),
    ("Wax — Arms — {}", 40, "Waxing", 2, ["Samantha Jones","Charlotte York","Miranda Hobbes","Carrie Bradshaw"]),
    ("Hair Extensions — {}", 120, "Hair Extensions", 4, ["Beyoncé Smith","Rihanna Jones","Taylor Brown","Ariana Grande-Lee"]),
    ("Kids Cut — {}", 30, "Haircut & Style", 2, ["Timmy Turner Sr","Jamie Oliver Jr","Bobby Brown II","Billy Elliot"]),
]

all_tasks = []
statuses_pool = ["unassigned","unassigned","unassigned","scheduled","completed","completed","in_progress","cancelled"]

# Generate tasks across past 30 days + next 14 days
date_range = [today - timedelta(days=d) for d in range(30, 0, -1)] + [today + timedelta(days=d) for d in range(0, 15)]

# Limit number of long-treatment tasks per day so they are spread out
LONG_TREATMENT_SKILLS = {"Hair Colouring", "Highlights & Balayage", "Keratin Straightening", "Hair Extensions"}
MAX_LONG_TREATMENTS_PER_DAY = 4

print("Creating tasks...")
task_count = 0
for task_date in date_range:
    # 3-8 tasks per day
    n_tasks = random.randint(3, 8)
    chosen = random.sample(task_templates, min(n_tasks, len(task_templates)))

    long_count = 0

    for tmpl, dur, skill_name, priority, customers in chosen:
        if skill_name in LONG_TREATMENT_SKILLS and long_count >= MAX_LONG_TREATMENTS_PER_DAY:
            continue  # skip extra long treatments on this day to spread load

        cust = random.choice(customers)
        task_name = tmpl.format(cust)
        # Preferred start within business hours
        pref_hour = random.randint(9, 15)
        pref_start = to_utc(task_date, pref_hour, random.choice([0, 15, 30, 45]))
        deadline = to_utc(task_date, 17, 0)

        t = Task(
            id=uid(),
            task_name=task_name,
            duration_minutes=dur,
            priority_level=priority,
            priority_weight=random.randint(30, 90),
            required_skill_id=skill_objs[skill_name].id,
            preferred_start=pref_start,
            deadline=deadline,
            status="unassigned",
            customer_name=cust,
            customer_notes=random.choice([None, None, "Regular client", "Allergic to latex", "Prefers Alice", "New customer"]),
        )
        session.add(t)
        all_tasks.append((t, task_date, skill_name, pref_hour))
        task_count += 1

        if skill_name in LONG_TREATMENT_SKILLS:
            long_count += 1

session.commit()
print(f"  {task_count} tasks created.")

# -------------------------------------------------------
# Schedule past tasks (completed / no_show)
# -------------------------------------------------------
print("Scheduling historical tasks...")
sched_count = 0
scheduled_task_ids = set()

# Build employee -> skills lookup
emp_skill_lookup = {}
for name, (emp, skills, profs) in emp_objs.items():
    if emp.status not in ("active", "sick"):
        continue
    emp_skill_lookup[emp.id] = set(skills)

for t, task_date, skill_name, pref_hour in all_tasks:
    if task_date >= today:
        continue  # Only schedule past tasks; leave today/future for auto-scheduler
    if t.id in scheduled_task_ids:
        continue

    # Find a capable employee
    capable = [emp for (emp, _, _) in emp_objs.values()
               if skill_name in emp_skill_lookup.get(emp.id, set())]
    if not capable:
        continue

    emp = random.choice(capable)
    start = to_utc(task_date, pref_hour, 0)
    end = start + timedelta(minutes=t.duration_minutes + 10)

    hist_status = random.choices(
        ["completed","completed","completed","no_show","cancelled"],
        weights=[60,10,10,15,5]
    )[0]

    sched = TaskSchedule(
        id=uid(), task_id=t.id, employee_id=emp.id,
        scheduled_date=task_date, start_time=start, end_time=end,
        status=hist_status,
        assigned_at=to_utc(task_date - timedelta(days=1), 10, 0),
        completed_at=end if hist_status == "completed" else None,
    )
    t.status = "completed" if hist_status == "completed" else ("cancelled" if hist_status == "cancelled" else "scheduled")
    session.add(sched)
    scheduled_task_ids.add(t.id)
    sched_count += 1

session.commit()
print(f"  {sched_count} historical schedules created.")

# -------------------------------------------------------
# Normalise breaks vs appointments (no overlaps, within hours)
# -------------------------------------------------------
print("Normalising breaks vs appointments (no overlaps, respect hours)...")
biz = Config.BUSINESS or {}
open_str = biz.get("default_open", "09:00")
close_str = biz.get("default_close", "17:00")
open_h, open_m = map(int, open_str.split(":"))
close_h, close_m = map(int, close_str.split(":"))

for name, (emp, _, _) in emp_objs.items():
    # All dates this employee has schedules on
    emp_scheds = session.query(TaskSchedule).filter_by(employee_id=emp.id).all()
    dates = sorted({s.scheduled_date for s in emp_scheds})

    for d in dates:
        day_start = to_utc(d, open_h, open_m)
        day_end = to_utc(d, close_h, close_m)

        # Clamp schedules to business hours
        day_scheds = [
            s for s in emp_scheds
            if s.scheduled_date == d and s.status not in ("cancelled", "no_show")
        ]
        for s in day_scheds:
            if s.start_time < day_start:
                s.start_time = day_start
            if s.end_time > day_end:
                s.end_time = day_end

        # Adjust breaks so they don't overlap any schedules
        dow = d.weekday()
        br_recur = session.query(EmployeeBreak).filter_by(
            employee_id=emp.id, day_of_week=dow, is_recurring=True
        ).all()
        br_override = session.query(EmployeeBreak).filter_by(
            employee_id=emp.id, override_date=d, is_recurring=False
        ).all()
        for br in list(br_recur) + list(br_override):
            start_dt = datetime(d.year, d.month, d.day, br.start_time.hour, br.start_time.minute)
            end_dt = datetime(d.year, d.month, d.day, br.end_time.hour, br.end_time.minute)
            orig_dur = end_dt - start_dt

            # Move break to after any overlapping schedules (cascade)
            moved = True
            while moved:
                moved = False
                for s in day_scheds:
                    if s.start_time < end_dt and s.end_time > start_dt:
                        start_dt = s.end_time
                        end_dt = start_dt + orig_dur
                        moved = True

            # If break ends after closing, clip or drop
            if start_dt >= day_end:
                session.delete(br)
                continue
            if end_dt > day_end:
                end_dt = day_end

            br.start_time = start_dt.time()
            br.end_time = end_dt.time()

session.commit()

print("\n✅ Seed complete!")
print(f"   Skills: {len(skill_objs)}")
print(f"   Employees: {len(emp_objs)}")
print(f"   Tasks: {task_count}")
print(f"   Historical schedules: {sched_count}")
