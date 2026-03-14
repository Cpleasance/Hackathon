# Scheduler — Intelligent Workflow Scheduling Platform

An advanced resource optimisation system designed for appointment-based service businesses. Dynamically allocates tasks to employees based on skills, availability, priority, and real-time conflict resolution.

## Architecture

```
scheduler/
├── backend/
│   ├── app.py                      # Flask entry point & SPA serving
│   ├── config.py                   # Environment configuration
│   ├── api/
│   │   ├── skills.py               # Skills CRUD
│   │   ├── employees.py            # Employee CRUD + skill assignment
│   │   ├── tasks.py                # Task CRUD
│   │   ├── schedules.py            # Schedule management + auto-scheduler
│   │   ├── availability.py         # Employee availability management
│   │   ├── breaks.py               # Employee breaks management
│   │   ├── analytics.py            # Forecasting & utilisation
│   │   └── calendar_sync.py        # External calendar integration
│   ├── services/
│   │   ├── scheduler_engine.py     # Core greedy scheduling algorithm
│   │   ├── conflict_resolver.py    # Overlap detection + auto-reassignment
│   │   ├── buffer_calculator.py    # Prep/cleanup buffer computation
│   │   ├── priority_engine.py      # Weighted composite scoring
│   │   └── analytics_engine.py     # Demand forecasting & staffing
│   ├── models/
│   │   └── database.py             # SQLAlchemy ORM + indexes
│   └── utils/
│       ├── validators.py           # Input validation & sanitisation
│       └── errors.py               # Centralised error handling
├── frontend/
│   ├── index.html                  # SPA shell
│   ├── css/main.css                # Full stylesheet
│   └── js/
│       ├── app.js                  # SPA router & initialisation
│       ├── api.js                  # Backend API client
│       ├── scheduler.js            # Gantt-style schedule board
│       ├── tasks.js                # Task queue management
│       ├── employees.js            # Employee table
│       ├── analytics.js            # Analytics dashboard
│       ├── settings.js             # Settings management
│       └── utils.js                # Shared UI utilities
├── config/
│   └── settings.json               # Operational configuration
├── migrations/
│   └── 001_initial_schema.sql      # Database schema
├── tests/
│   ├── test_scheduler.py           # Unit tests (priority, buffers)
│   └── test_api.py                 # Validation tests
├── seed_data.py                    # Demo data seeding script
└── requirements.txt
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment
```bash
# SQLite (default, no setup needed)
# Or set a custom DB:
# export DATABASE_URL="sqlite:///scheduler.db"
```

### 3. Seed demo data
```bash
python seed_data.py
```

### 4. Run
```bash
python backend/app.py
```

Open `http://localhost:5000` in your browser.

### 5. Run Tests
```bash
python -m pytest tests/ -v
```

## Core Features

### Scheduling Engine (`services/scheduler_engine.py`)
- **Greedy priority-ordered allocation**: processes highest-value tasks first
- **Skill-based matching**: only assigns tasks to employees with the required skill
- **Proficiency preference**: higher-proficiency employees are preferred
- **Availability-aware**: respects recurring schedules and date-specific overrides
- **Buffer zones**: automatic prep/cleanup time between appointments
- **Deadline-scoped**: auto-schedule only picks up tasks due today or overdue, leaving future tasks in the queue
- **Batch-loaded caches**: availability, breaks, and existing schedules are loaded in bulk once per run — not per task — for fast execution

### Conflict Resolution (`services/conflict_resolver.py`)
- **Overlap detection**: queries for time-range intersections before every assignment
- **Overrun handling**: extends overrunning tasks and cascade-checks downstream appointments
- **Auto-reassignment**: finds the next best qualified employee when conflicts arise

### Priority Engine (`services/priority_engine.py`)
- **Composite scoring**: combines priority weight, urgency, revenue proxy, and loyalty tier
- **Configurable weights**: adjust urgency/revenue/loyalty emphasis in `settings.json`
- **Deadline-aware urgency**: linear ramp from 48h → 0h remaining; overdue tasks score maximum

### Analytics (`services/analytics_engine.py`)
- **Employee utilisation**: booked vs available minutes
- **Demand by hour/day**: historical appointment distribution
- **No-show rate tracking**: configurable lookback period
- **Staffing recommendations**: compare current bookings to historical averages

### Smart Buffers (`services/buffer_calculator.py`)
- **Category-specific**: colour and treatment tasks get longer buffers (10 min vs 5 min default)
- **Configurable**: all buffer durations in `settings.json`
- **End-of-day aware**: buffer is not required after the last task of the day

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills` | List all skills |
| POST | `/api/skills` | Create skill |
| GET | `/api/employees` | List employees |
| POST | `/api/employees` | Create employee |
| POST | `/api/employees/:id/skills` | Assign skill to employee |
| GET | `/api/tasks` | List tasks (filterable by status) |
| POST | `/api/tasks` | Create task |
| PUT | `/api/tasks/:id` | Update task |
| DELETE | `/api/tasks/:id` | Cancel task |
| GET | `/api/schedules` | List schedules (filterable by date/employee/status) |
| POST | `/api/schedules` | Manual schedule assignment |
| PATCH | `/api/schedules/:id/status` | Update schedule status |
| PUT | `/api/schedules/:id/force` | Force-reassign (admin override) |
| POST | `/api/schedules/auto-schedule` | Run auto-scheduler for a date |
| POST | `/api/schedules/:id/overrun` | Report task overrun |
| GET | `/api/availability/:empId` | Get employee availability |
| POST | `/api/availability/:empId` | Add availability record |
| GET | `/api/breaks/:empId` | Get employee breaks |
| POST | `/api/breaks/:empId` | Add break record |
| GET | `/api/analytics/utilisation` | Employee utilisation metrics |
| GET | `/api/analytics/demand/hourly` | Hourly demand distribution |
| GET | `/api/analytics/demand/daily` | Daily demand distribution |
| GET | `/api/analytics/no-shows` | No-show rate |
| GET | `/api/analytics/staffing?date=` | Staffing recommendation |
| GET | `/api/settings` | Current settings |

## Safety-Critical Design Decisions

1. **ACID transactions** — all schedule mutations commit atomically
2. **Application-level overlap check** — `detect_overlaps()` before every assignment prevents double-booking
3. **Input validation** — every endpoint validates and sanitises before processing
4. **Buffer zones** — configurable prep/cleanup time prevents cascading delays
5. **Automatic conflict resolution** — overruns trigger cascade reassignment
6. **Status-aware queries** — cancelled/no-show schedules excluded from all conflict checks
7. **Composite indexes** — `(employee_id, scheduled_date)` on task_schedules and `(employee_id, is_recurring, day_of_week)` on availability/breaks for fast lookups

## Configuration

Edit `config/settings.json` to customise:
- Business hours and operating days
- Buffer durations per skill category
- Priority weights (urgency, revenue, loyalty)
- Analytics lookback periods
- Peak/off-peak hour definitions

## Stack

- **Backend**: Python 3.11+, Flask 3.1, SQLAlchemy 2.0
- **Database**: SQLite (default) — compatible with PostgreSQL
- **Frontend**: Vanilla JS SPA (no framework), CSS Grid/Flexbox
- **Tests**: Python `unittest` (stdlib, no extra dependencies)
