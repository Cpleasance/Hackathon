"""
SQLAlchemy ORM models — mirrors the PostgreSQL schema exactly.

Every model uses explicit table names, column types, and constraints
so that the ORM layer and the raw SQL schema stay in lock-step.
"""
from datetime import datetime, date, time, timezone
from uuid import uuid4

from sqlalchemy import (
    create_engine, Column, String, Integer, SmallInteger, Boolean, Text,
    Date, Time, DateTime, ForeignKey, UniqueConstraint, CheckConstraint,
    Enum as SAEnum, Index, text, Uuid,
)

TIMESTAMP = DateTime  # store timestamps as DateTime
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Session, sessionmaker, scoped_session,
)

# ---------------------------------------------------------------------------
#  Enumerations
# ---------------------------------------------------------------------------
TASK_STATUSES = ("unassigned", "scheduled", "in_progress", "completed", "cancelled")
SCHEDULE_STATUSES = ("confirmed", "in_progress", "completed", "cancelled", "no_show")


# ---------------------------------------------------------------------------
#  Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
#  Skills
# ---------------------------------------------------------------------------
class Skill(Base):
    __tablename__ = "skills"

    id = Column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(60))
    description = Column(Text)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    employee_skills = relationship("EmployeeSkill", back_populates="skill", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="required_skill")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "category": self.category,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
#  Employees
# ---------------------------------------------------------------------------
class Employee(Base):
    __tablename__ = "employees"

    id = Column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(150), nullable=False)
    role = Column(String(100), nullable=False)
    daily_minutes = Column(Integer, nullable=False, default=480)
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="active")  # active | inactive | sick | holiday
    holiday_until = Column(Date)   # only relevant when status == 'holiday'
    email = Column(String(255), unique=True)
    phone = Column(String(30))
    notes = Column(Text)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    skills = relationship("EmployeeSkill", back_populates="employee", cascade="all, delete-orphan")
    availability = relationship("EmployeeAvailability", back_populates="employee", cascade="all, delete-orphan")
    breaks = relationship("EmployeeBreak", back_populates="employee", cascade="all, delete-orphan")
    schedules = relationship("TaskSchedule", back_populates="employee")

    def to_dict(self, include_skills=False):
        d = {
            "id": str(self.id),
            "name": self.name,
            "role": self.role,
            "daily_minutes": self.daily_minutes,
            "is_active": self.is_active,
            "status": self.status or ("active" if self.is_active else "inactive"),
            "holiday_until": self.holiday_until.isoformat() if self.holiday_until else None,
            "email": self.email,
            "phone": self.phone,
            "notes": self.notes,
        }
        if include_skills:
            d["skills"] = [es.to_dict() for es in self.skills]
        return d


# ---------------------------------------------------------------------------
#  Employee Skills (junction)
# ---------------------------------------------------------------------------
class EmployeeSkill(Base):
    __tablename__ = "employee_skills"

    employee_id = Column(
        Uuid(as_uuid=False), ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True,
    )
    skill_id = Column(
        Uuid(as_uuid=False), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True,
    )
    proficiency_level = Column(SmallInteger, nullable=False, default=1)
    certified_date = Column(Date)

    employee = relationship("Employee", back_populates="skills")
    skill = relationship("Skill", back_populates="employee_skills")

    def to_dict(self):
        return {
            "skill_id": str(self.skill_id),
            "skill_name": self.skill.name if self.skill else None,
            "proficiency_level": self.proficiency_level,
            "certified_date": self.certified_date.isoformat() if self.certified_date else None,
        }


# ---------------------------------------------------------------------------
#  Employee Availability
# ---------------------------------------------------------------------------
class EmployeeAvailability(Base):
    __tablename__ = "employee_availability"

    id = Column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    employee_id = Column(
        Uuid(as_uuid=False), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False,
    )
    day_of_week = Column(SmallInteger)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_recurring = Column(Boolean, nullable=False, default=True)
    override_date = Column(Date)
    is_available = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_emp_avail_emp_recurring_dow", "employee_id", "is_recurring", "day_of_week"),
    )

    employee = relationship("Employee", back_populates="availability")

    def to_dict(self):
        return {
            "id": str(self.id),
            "employee_id": str(self.employee_id),
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "is_recurring": self.is_recurring,
            "override_date": self.override_date.isoformat() if self.override_date else None,
            "is_available": self.is_available,
        }


# ---------------------------------------------------------------------------
#  Employee Breaks
# ---------------------------------------------------------------------------
class EmployeeBreak(Base):
    __tablename__ = "employee_breaks"

    id = Column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    employee_id = Column(
        Uuid(as_uuid=False), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False,
    )
    day_of_week = Column(SmallInteger)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_recurring = Column(Boolean, nullable=False, default=True)
    override_date = Column(Date)

    __table_args__ = (
        Index("ix_emp_breaks_emp_recurring_dow", "employee_id", "is_recurring", "day_of_week"),
    )

    employee = relationship("Employee", back_populates="breaks")

    def to_dict(self):
        return {
            "id": str(self.id),
            "employee_id": str(self.employee_id),
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "is_recurring": self.is_recurring,
            "override_date": self.override_date.isoformat() if self.override_date else None,
        }


# ---------------------------------------------------------------------------
#  Tasks
# ---------------------------------------------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_name = Column(String(200), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    priority_level = Column(SmallInteger, nullable=False, default=3)
    priority_weight = Column(Integer, nullable=False, default=50)
    required_skill_id = Column(
        Uuid(as_uuid=False), ForeignKey("skills.id"), nullable=False,
    )
    preferred_start = Column(DateTime)
    deadline = Column(DateTime)
    status = Column(String(20), nullable=False, default="unassigned")
    customer_name = Column(String(150))
    customer_notes = Column(Text)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    required_skill = relationship("Skill", back_populates="tasks")
    schedule = relationship("TaskSchedule", back_populates="task", uselist=False)

    __table_args__ = (
        Index("ix_tasks_status", "status"),
    )

    def to_dict(self):
        def fmt(dt): return dt.isoformat() + "Z" if dt else None
        return {
            "id": str(self.id),
            "task_name": self.task_name,
            "duration_minutes": self.duration_minutes,
            "priority_level": self.priority_level,
            "priority_weight": self.priority_weight,
            "required_skill_id": str(self.required_skill_id),
            "required_skill_name": self.required_skill.name if self.required_skill else None,
            "preferred_start": fmt(self.preferred_start),
            "deadline": fmt(self.deadline),
            "status": self.status,
            "customer_name": self.customer_name,
            "customer_notes": self.customer_notes,
            "created_at": fmt(self.created_at),
        }


# ---------------------------------------------------------------------------
#  Task Schedules
# ---------------------------------------------------------------------------
class TaskSchedule(Base):
    __tablename__ = "task_schedules"

    id = Column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(
        Uuid(as_uuid=False), ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    employee_id = Column(
        Uuid(as_uuid=False), ForeignKey("employees.id"), nullable=False,
    )
    scheduled_date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="confirmed")
    assigned_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime)
    notes = Column(Text)

    __table_args__ = (
        Index("ix_task_schedules_emp_date", "employee_id", "scheduled_date"),
        Index("ix_task_schedules_emp_date_status", "employee_id", "scheduled_date", "status"),
    )

    task = relationship("Task", back_populates="schedule")
    employee = relationship("Employee", back_populates="schedules")

    def to_dict(self):
        def fmt(dt): return dt.isoformat() + "Z" if dt else None
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "task_name": self.task.task_name if self.task else None,
            "employee_id": str(self.employee_id),
            "employee_name": self.employee.name if self.employee else None,
            "scheduled_date": self.scheduled_date.isoformat(),
            "start_time": fmt(self.start_time),
            "end_time": fmt(self.end_time),
            "status": self.status,
            "customer_name": self.task.customer_name if self.task else None,
            "duration_minutes": self.task.duration_minutes if self.task else None,
            "priority_level": self.task.priority_level if self.task else None,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
#  Engine & Session factory
# ---------------------------------------------------------------------------
_engine = None
_SessionFactory = None


def init_db(database_url: str, echo: bool = False):
    """Initialise the database engine and session factory."""
    global _engine, _SessionFactory
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, pool_pre_ping=True, echo=echo, connect_args=connect_args)
    Base.metadata.create_all(_engine)
    _SessionFactory = scoped_session(sessionmaker(bind=_engine))
    return _engine


def get_session() -> Session:
    """Return a thread-local scoped session."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _SessionFactory()


def remove_session():
    """Remove the current scoped session (call at end of request)."""
    if _SessionFactory:
        _SessionFactory.remove()
