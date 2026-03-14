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
│   │   ├── analytics.py            # Forecasting & utilisation
│   │   └── calendar_sync.py        # External calendar integration
│   ├── services/
│   │   ├── scheduler_engine.py     # Core greedy scheduling algorithm
│   │   ├── conflict_resolver.py    # Overlap detection + auto-reassignment
│   │   ├── buffer_calculator.py    # Prep/cleanup buffer computation
│   │   ├── priority_engine.py      # Weighted composite scoring
│   │   └── analytics_engine.py     # Demand forecasting & staffing
│   ├── models/
│   │   └── database.py             # SQLAlchemy ORM (mirrors PG schema)
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
│       └── utils.js                # Shared UI utilities
├── config/
│   └── settings.json               # Operational configuration
├── migrations/
│   └── 001_initial_schema.sql      # PostgreSQL schema + seed data
├── tests/
│   ├── test_scheduler.py           # 20 unit tests (priority, buffers)
│   └── test_api.py                 # 15 validation tests
└── requirements.txt
```

## Quick Start

### 1. Database Setup
```bash
# Create the PostgreSQL database
createdb scheduler

# Apply the schema + seed data
psql -d scheduler -f migrations/001_initial_schema.sql
```

### 2. Environment
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/scheduler"
export FLASK_ENV=development
```

### 3. Install & Run
```bash
pip install -r requirements.txt
python backend/app.py
```

Open `http://localhost:5000` in your browser.

### 4. Run Tests
```bash
pip install pytest
python -m pytest tests/ -v
```

## Core Features

### Scheduling Engine (`services/scheduler_engine.py`)
- **Greedy priority-ordered allocation**: processes highest-value tasks first
- **Skill-based matching**: only assigns tasks to employees with the required skill
- **Proficiency preference**: higher-proficiency employees are preferred
- **Availability-aware**: respects recurring schedules and date overrides
- **Buffer zones**: automatic prep/cleanup time between appointments

### Conflict Resolution (`services/conflict_resolver.py`)
- **Overlap detection**: queries for time-range intersections
- **Overrun handling**: extends overrunning tasks and cascade-checks downstream
- **Auto-reassignment**: finds alternative qualified employees when conflicts arise
- **PostgreSQL exclusion constraint**: hardware-level overlap prevention as last defence

### Priority Engine (`services/priority_engine.py`)
- **Composite scoring**: combines priority weight, urgency, revenue proxy, and loyalty tier
- **Configurable weights**: adjust urgency/revenue/loyalty emphasis in settings.json
- **Deadline-aware urgency**: linear ramp from 48h→0h

### Analytics (`services/analytics_engine.py`)
- **Employee utilisation**: booked vs available minutes
- **Demand by hour/day**: historical appointment distribution
- **No-show rate tracking**: configurable lookback period
- **Staffing recommendations**: compare current bookings to historical averages

### Smart Buffers (`services/buffer_calculator.py`)
- **Category-specific**: colour and treatment tasks get longer buffers
- **Configurable**: all buffer durations in settings.json
- **Cascading protection**: prevents one overrun from derailing the full day

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
| GET | `/api/schedules` | List schedules (filterable) |
| POST | `/api/schedules` | Manual schedule assignment |
| PATCH | `/api/schedules/:id/status` | Update schedule status |
| POST | `/api/schedules/auto-schedule` | Run auto-scheduler for a date |
| POST | `/api/schedules/:id/overrun` | Report task overrun |
| GET | `/api/availability/:empId` | Get employee availability |
| POST | `/api/availability/:empId` | Add availability record |
| GET | `/api/analytics/utilisation` | Employee utilisation metrics |
| GET | `/api/analytics/demand/hourly` | Hourly demand distribution |
| GET | `/api/analytics/demand/daily` | Daily demand distribution |
| GET | `/api/analytics/no-shows` | No-show rate |
| GET | `/api/analytics/staffing?date=` | Staffing recommendation |
| GET | `/api/settings` | Current settings |

## Safety-Critical Design Decisions

1. **ACID transactions** — all schedule mutations commit atomically
2. **PostgreSQL exclusion constraint** — `no_employee_overlap` enforced at DB level
3. **Application-level overlap check** — `detect_overlaps()` before every assignment
4. **Input validation** — every endpoint validates and sanitises before processing
5. **Buffer zones** — configurable prep/cleanup time prevents cascading delays
6. **Automatic conflict resolution** — overruns trigger cascade reassignment
7. **Status-aware queries** — cancelled/no-show schedules excluded from conflict checks
8. **35 unit tests** — priority logic, buffer calculation, and validation all tested

## Configuration

Edit `config/settings.json` to customise:
- Business hours and operating days
- Buffer durations per skill category
- Priority weights (urgency, revenue, loyalty)
- Analytics lookback periods
- Peak/off-peak hour definitions
