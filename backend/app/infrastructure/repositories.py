"""Repositorio: única puerta de acceso a la BD para agentes y servicios."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.db import (
    ApplicationRow,
    MatchRow,
    ProfileRow,
    ReminderRow,
    SessionLocal,
    TraceRow,
    UserRow,
    UserStateRow,
)


class Repository:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal):
        self._sf = session_factory

    @contextmanager
    def _s(self):
        s = self._sf()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ------------------------------------------------------------ usuarios
    def get_user(self, username: str) -> UserRow | None:
        with self._s() as s:
            return s.scalar(select(UserRow).where(UserRow.username == username))

    def create_user(self, username: str, password_hash: str, role: str = "candidate") -> UserRow:
        with self._s() as s:
            u = UserRow(username=username, password_hash=password_hash, role=role)
            s.add(u)
            s.flush()
            s.add(UserStateRow(user_id=u.id))
            return u

    def get_state(self, user_id: int) -> UserStateRow:
        with self._s() as s:
            st = s.get(UserStateRow, user_id)
            if st is None:
                st = UserStateRow(user_id=user_id, stage="onboarding", sim_day=0)
                s.add(st)
            return st

    def update_state(self, user_id: int, **fields: Any) -> None:
        with self._s() as s:
            st = s.get(UserStateRow, user_id) or UserStateRow(user_id=user_id)
            for k, v in fields.items():
                setattr(st, k, v)
            s.add(st)

    def reset_user(self, user_id: int) -> None:
        with self._s() as s:
            for model in (MatchRow, ApplicationRow, ReminderRow, TraceRow):
                s.execute(delete(model).where(model.user_id == user_id))
            s.execute(delete(ProfileRow).where(ProfileRow.user_id == user_id))
            st = s.get(UserStateRow, user_id)
            if st:
                st.stage, st.thread_id, st.sim_day, st.pending = "onboarding", None, 0, None

    # ------------------------------------------------------------ perfil
    def save_profile(self, user_id: int, data: dict, completeness: float, gaps: list,
                     cv_sha256: str | None = None) -> None:
        with self._s() as s:
            row = s.get(ProfileRow, user_id) or ProfileRow(user_id=user_id)
            row.data, row.completeness, row.gaps = data, completeness, gaps
            if cv_sha256:
                row.cv_sha256 = cv_sha256
            s.add(row)

    def get_profile(self, user_id: int) -> ProfileRow | None:
        with self._s() as s:
            return s.get(ProfileRow, user_id)

    # ------------------------------------------------------------ matches
    def replace_matches(self, user_id: int, matches: list[dict]) -> None:
        with self._s() as s:
            s.execute(delete(MatchRow).where(MatchRow.user_id == user_id))
            for m in matches:
                s.add(MatchRow(user_id=user_id, vacancy_id=m["vacancy"]["id"], score=m["score"], data=m))

    def list_matches(self, user_id: int) -> list[dict]:
        with self._s() as s:
            rows = s.scalars(select(MatchRow).where(MatchRow.user_id == user_id)
                             .order_by(MatchRow.score.desc())).all()
            return [r.data for r in rows]

    # ------------------------------------------------------------ postulaciones
    def applied_vacancy_ids(self, user_id: int) -> set[str]:
        with self._s() as s:
            return set(s.scalars(select(ApplicationRow.vacancy_id).where(ApplicationRow.user_id == user_id)))

    def add_application(self, **fields: Any) -> ApplicationRow:
        with self._s() as s:
            row = ApplicationRow(**fields)
            s.add(row)
            s.flush()
            return row

    def list_applications(self, user_id: int) -> list[ApplicationRow]:
        with self._s() as s:
            return list(s.scalars(select(ApplicationRow).where(ApplicationRow.user_id == user_id)
                                  .order_by(ApplicationRow.id)))

    def update_application(self, app_id: int, **fields: Any) -> None:
        with self._s() as s:
            row = s.get(ApplicationRow, app_id)
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)

    # ------------------------------------------------------------ recordatorios
    def reminder_exists(self, user_id: int, application_id: int | None, status_key: str) -> bool:
        with self._s() as s:
            return s.scalar(select(ReminderRow.id).where(
                ReminderRow.user_id == user_id,
                ReminderRow.application_id == application_id,
                ReminderRow.status_key == status_key)) is not None

    def add_reminder(self, **fields: Any) -> ReminderRow:
        with self._s() as s:
            row = ReminderRow(**fields)
            s.add(row)
            s.flush()
            return row

    def list_reminders(self, user_id: int) -> list[ReminderRow]:
        with self._s() as s:
            return list(s.scalars(select(ReminderRow).where(ReminderRow.user_id == user_id)
                                  .order_by(ReminderRow.done, ReminderRow.due_day, ReminderRow.id.desc())))

    def set_reminder_done(self, user_id: int, reminder_id: int, done: bool) -> bool:
        with self._s() as s:
            row = s.get(ReminderRow, reminder_id)
            if row is None or row.user_id != user_id:
                return False
            row.done = done
            return True

    # ------------------------------------------------------------ trazas
    def add_trace(self, **fields: Any) -> TraceRow:
        with self._s() as s:
            row = TraceRow(**fields)
            s.add(row)
            s.flush()
            return row

    def list_traces(self, user_id: int, agent: str | None = None) -> list[TraceRow]:
        with self._s() as s:
            q = select(TraceRow).where(TraceRow.user_id == user_id)
            if agent:
                q = q.where(TraceRow.agent == agent)
            return list(s.scalars(q.order_by(TraceRow.id)))
