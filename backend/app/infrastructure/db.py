"""Persistencia con SQLAlchemy. SQLite por defecto; PostgreSQL cambiando DATABASE_URL."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="candidate")


class UserStateRow(Base):
    """Estado del flujo por usuario: etapa actual, hilo del grafo y reloj simulado."""
    __tablename__ = "user_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(30), default="onboarding")
    thread_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sim_day: Mapped[int] = mapped_column(Integer, default=0)
    pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProfileRow(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    completeness: Mapped[float] = mapped_column(Float, default=0)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    cv_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class MatchRow(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vacancy_id: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(JSON)


class ApplicationRow(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vacancy_id: Mapped[str] = mapped_column(String(40))
    vacancy_title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200))
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))
    created_day: Mapped[int] = mapped_column(Integer)
    updated_day: Mapped[int] = mapped_column(Integer)
    interview_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON)
    history: Mapped[list] = mapped_column(JSON, default=list)
    next_steps: Mapped[list] = mapped_column(JSON, default=list)


class ReminderRow(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    status_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    due_day: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(20))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TraceRow(Base):
    __tablename__ = "trace_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    agent: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(20))  # llm | rules | human | system
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    sim_day: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
