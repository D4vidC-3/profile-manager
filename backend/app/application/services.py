"""Casos de uso: puente entre la API y el grafo de agentes."""

from __future__ import annotations

import hashlib
import uuid
from collections import Counter
from typing import Any

from langgraph.types import Command

from app.agents.application_agent import ApplicationAgent
from app.agents.followup_agent import FollowupAgent
from app.agents.graph import GRAPH, RESUME_FROM, Deps, save_profile
from app.agents.profile_agent import ProfileAgent
from app.agents.tracing import Tracer
from app.agents.vacancy_agent import VacancyAgent
from app.config import get_settings
from app.domain.colombia import department_for, normalize_city
from app.domain.completeness import (
    apply_identity,
    apply_skill_levels,
    cv_completeness,
    demonstrated_skills,
    detect_cv_gaps,
    identity_form,
    identity_gaps,
    is_first_job,
    preferences_completeness,
    preferences_form,
    projects_from_answer,
    skill_levels_form,
    skills_without_level,
    user_skills,
)
from app.domain.models import ApplicationStatus, MatchResult, Profile
from app.domain.process import simulate_company_response
from app.domain.skills import KINDS, SKILL_CATALOG, strip_accents
from app.infrastructure.cv.extractor import extract_text, years_of_experience
from app.infrastructure.github import verify_project
from app.infrastructure.llm.provider import LLMChain, get_llm
from app.infrastructure.repositories import Repository
from app.infrastructure.vacancies.source import JsonDatasetSource, load_catalog

# Campos que el candidato puede editar desde su perfil (lista blanca)
EDITABLE = ["full_name", "first_names", "last_names", "email", "phone", "city", "linkedin", "github", "portfolio",
            "headline", "summary", "skills", "languages", "experiences", "projects", "education",
            "certifications", "expectations"]


class FlowError(Exception):
    """Acción inválida para la etapa actual del flujo."""


class ProfileManagerService:
    def __init__(self, repo: Repository | None = None, llm: LLMChain | None = None):
        s = get_settings()
        self.repo = repo or Repository()
        self.llm = llm or get_llm()
        self.sources = [JsonDatasetSource()]
        self.profile_agent = ProfileAgent(self.llm)
        self.vacancy_agent = VacancyAgent(self.sources, s.match_threshold, s.max_matches)
        self.application_agent = ApplicationAgent(self.repo)
        self.followup_agent = FollowupAgent(self.repo, self.llm)
        self._catalog = None

    @property
    def catalog(self):
        if self._catalog is None:
            self._catalog = load_catalog(self.sources)
        return self._catalog

    # ------------------------------------------------------------ helpers
    def _deps(self, user_id: int, thread_id: str) -> Deps:
        st = self.repo.get_state(user_id)
        tracer = Tracer(self.repo, user_id, thread_id, st.sim_day)
        return Deps(user_id, self.repo, tracer, self.profile_agent, self.vacancy_agent,
                    self.application_agent, self.followup_agent, self.catalog)

    def _config(self, user_id: int, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id, "deps": self._deps(user_id, thread_id)}}

    def _finish(self, user_id: int, thread_id: str, result: dict) -> dict:
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            value = interrupts[0].value
            stage = value["type"]  # cv_gaps | preferences | approval | identity
            self.repo.update_state(user_id, stage=stage, thread_id=thread_id, pending=value)
            return {"stage": stage, "pending": value}
        self.repo.update_state(user_id, stage="tracking", thread_id=thread_id, pending=None)
        return {"stage": "tracking", "pending": None}

    def _run(self, user_id: int, thread_id: str, payload: Any) -> dict:
        return self._finish(user_id, thread_id, GRAPH.invoke(payload, self._config(user_id, thread_id)))

    def _require_stage(self, user_id: int, stage: str) -> str:
        st = self.repo.get_state(user_id)
        if st.stage != stage or not st.thread_id:
            raise FlowError(f"Acción no válida en la etapa actual ({st.stage})")
        snapshot = GRAPH.get_state({"configurable": {"thread_id": st.thread_id}})
        if not snapshot.next:
            raise FlowError("La sesión del flujo expiró (el servidor se reinició). Vuelve a subir tu CV.")
        return st.thread_id

    def current_profile(self, user_id: int) -> Profile | None:
        row = self.repo.get_profile(user_id)
        return Profile(**row.data) if row else None

    # ------------------------------------------------------------ casos de uso del flujo
    def start_onboarding(self, user_id: int, filename: str, content: bytes) -> dict:
        text = extract_text(filename, content)
        previous = self.current_profile(user_id)  # lo editado a mano y las preferencias se conservan
        self.repo.reset_user(user_id)
        thread_id = f"u{user_id}-{uuid.uuid4().hex[:8]}"
        Tracer(self.repo, user_id, thread_id, 0).log(
            "orquestador", "Inició flujo de onboarding",
            f"CV recibido ({len(text)} caracteres). Etapas: perfil → completar CV → ¿qué buscas? → vacantes → "
            "aprobación → identidad → postulación → seguimiento.", mode="system")
        payload = {"cv_text": text, "cv_sha256": hashlib.sha256(content).hexdigest(),
                   "previous": previous.model_dump(mode="json") if previous else None}
        return self._run(user_id, thread_id, payload)

    def answer_cv(self, user_id: int, answers: dict[str, Any]) -> dict:
        thread_id = self._require_stage(user_id, "cv_gaps")
        return self._run(user_id, thread_id, Command(resume=answers))

    def set_preferences(self, user_id: int, data: dict[str, Any]) -> dict:
        thread_id = self._require_stage(user_id, "preferences")
        return self._run(user_id, thread_id, Command(resume=data))

    def approve(self, user_id: int, vacancy_ids: list[str]) -> dict:
        st = self.repo.get_state(user_id)
        if st.stage == "tracking":  # postular a más vacantes desde el tablero (tras "Actualizar recomendaciones")
            return self._approve_more(user_id, vacancy_ids)
        thread_id = self._require_stage(user_id, "approval")
        return self._run(user_id, thread_id, Command(resume=vacancy_ids))

    def set_skill_levels(self, user_id: int, levels: dict[str, str]) -> dict:
        st = self.repo.get_state(user_id)
        if st.stage == "skill_levels" and (st.pending or {}).get("approve_ids") is not None:
            profile, _ = apply_skill_levels(self.current_profile(user_id) or Profile(), levels)
            save_profile(self._deps(user_id, st.thread_id or "tracking"), profile)
            self.repo.update_state(user_id, stage="tracking", pending=None)
            return self._approve_more(user_id, st.pending["approve_ids"])
        thread_id = self._require_stage(user_id, "skill_levels")
        return self._run(user_id, thread_id, Command(resume={"levels": levels}))

    def set_identity(self, user_id: int, data: dict[str, Any]) -> dict:
        st = self.repo.get_state(user_id)
        if st.stage == "identity" and (st.pending or {}).get("approve_ids") is not None:
            profile, _ = apply_identity(self.current_profile(user_id) or Profile(), data)
            deps = self._deps(user_id, st.thread_id or "tracking")
            save_profile(deps, profile)
            if identity_gaps(profile):
                raise FlowError("Faltan datos de identidad para postular")
            self.repo.update_state(user_id, stage="tracking", pending=None)
            return self._approve_more(user_id, st.pending["approve_ids"])
        thread_id = self._require_stage(user_id, "identity")
        return self._run(user_id, thread_id, Command(resume=data))

    def _approve_more(self, user_id: int, vacancy_ids: list[str]) -> dict:
        profile = self.current_profile(user_id) or Profile()
        st = self.repo.get_state(user_id)
        if skills_without_level(profile):  # requisito para postular
            pending = {"type": "skill_levels", **skill_levels_form(profile), "approve_ids": vacancy_ids}
            self.repo.update_state(user_id, stage="skill_levels", pending=pending)
            return {"stage": "skill_levels", "pending": pending}
        if identity_gaps(profile):
            pending = {"type": "identity", **identity_form(profile), "approve_ids": vacancy_ids}
            self.repo.update_state(user_id, stage="identity", pending=pending)
            return {"stage": "identity", "pending": pending}
        matches = {m["vacancy"]["id"]: MatchResult(**m) for m in self.repo.list_matches(user_id)}
        approved = [matches[i] for i in vacancy_ids if i in matches]
        tracer = Tracer(self.repo, user_id, st.thread_id or "tracking", st.sim_day)
        tracer.log("candidato", f"Aprobó {len(approved)} postulación(es) adicionales",
                   "Desde el tablero, tras actualizar recomendaciones. El sistema nunca postula sin aprobación.",
                   mode="human", details={"approved": [m.vacancy.id for m in approved]})
        self.application_agent.run(user_id, profile, approved, tracer)
        self.followup_agent.run(user_id, profile, self.catalog, tracer)
        self.repo.update_state(user_id, stage="tracking", pending=None)
        return {"stage": "tracking", "pending": None}

    def refresh_matches(self, user_id: int) -> dict:
        """Recalcula las recomendaciones con el perfil y las preferencias actuales."""
        st = self.repo.get_state(user_id)
        profile = self.current_profile(user_id)
        if profile is None or st.stage in ("onboarding", "cv_gaps", "preferences", "skill_levels", "identity"):
            raise FlowError("Primero completa tu perfil y '¿Qué estás buscando?'")
        if st.stage == "approval" and st.thread_id:
            config = self._config(user_id, st.thread_id)
            if GRAPH.get_state(config).next:
                GRAPH.update_state(config, {"profile": profile.model_dump(mode="json")}, as_node="expectativas")
                return self._finish(user_id, st.thread_id, GRAPH.invoke(None, config))
        tracer = Tracer(self.repo, user_id, st.thread_id or "tracking", st.sim_day)
        tracer.log("candidato", "Pidió actualizar recomendaciones",
                   "Se vuelve a ejecutar el Agente de Vacantes con el perfil y las preferencias actuales.",
                   mode="human")
        matches, _ = self.vacancy_agent.run(profile, tracer, exclude_ids=self.repo.applied_vacancy_ids(user_id))
        self.repo.replace_matches(user_id, [m.model_dump(mode="json") for m in matches])
        return {"stage": st.stage, "pending": st.pending}

    # ------------------------------------------------------------ edición del perfil
    def profile_view(self, user_id: int) -> dict | None:
        p = self.current_profile(user_id)
        if p is None:
            return None
        cv = cv_completeness(p)
        form = preferences_form(p)
        return {
            "profile": p.model_dump(mode="json"),
            "cv": {"score": cv.score, "mode": cv.mode, "reason": cv.reason, "breakdown": cv.breakdown},
            "cv_gaps": [g.model_dump() for g in detect_cv_gaps(p)],
            "preferences": {"score": preferences_completeness(p), "missing": form["missing"],
                            "labels": form["labels"]},
        }

    def update_profile(self, user_id: int, data: dict[str, Any]) -> dict:
        """El candidato corrige su perfil. Lo editado queda protegido y, si hay un flujo en pausa,
        el grafo se reanuda desde el paso anterior para recalcular (p. ej. las recomendaciones)."""
        old = self.current_profile(user_id)
        if old is None:
            raise FlowError("Aún no hay perfil: sube tu hoja de vida primero")
        merged = old.model_dump(mode="json")
        changed: list[str] = []
        for key in EDITABLE:
            if key in data and data[key] != merged.get(key):
                merged[key] = data[key]
                changed.append(key)
        new = Profile(**merged)  # Pydantic valida tipos y estructura
        if "skills" in changed:  # el candidato puede mover una habilidad de tipo o ajustar su nivel
            new.skills = user_skills(new.skills)
        if "city" in changed:
            new.city = normalize_city(new.city)
            new.department = department_for(new.city)
        if "projects" in changed:
            new.projects = [verify_project(pr) if pr.url and "github.com" in (pr.url or "") else pr
                            for pr in projects_from_answer([pr.model_dump() for pr in new.projects])]
        if "experiences" in changed:
            new.years_experience = years_of_experience(new.experiences)
        if "languages" in changed:  # confirmados por el candidato: dejan de ser "sugeridos"
            for lang in new.languages:
                lang.suggested = False
        for key in changed:
            new.provenance[key] = "usuario"
            if key not in new.edited_fields and key != "expectations":
                new.edited_fields.append(key)
        new.demonstrated_skills = demonstrated_skills(new)
        new.first_job, _ = is_first_job(new)

        st = self.repo.get_state(user_id)
        thread = st.thread_id or "edicion"
        deps = self._deps(user_id, thread)
        save_profile(deps, new)
        deps.tracer.log("candidato", f"Editó su perfil: {', '.join(changed) or 'sin cambios'}",
                        "Corrección manual. Estos campos quedan protegidos: un CV nuevo no los sobrescribe. "
                        "(Por privacidad, la traza registra qué campos cambiaron, no sus valores.)",
                        mode="human", details={"fields": changed})
        result: dict[str, Any] = {"stage": st.stage, "pending": st.pending, "recalculated": False}
        if changed and st.stage in RESUME_FROM and st.thread_id:
            config = self._config(user_id, st.thread_id)
            if GRAPH.get_state(config).next:
                GRAPH.update_state(config, {"profile": new.model_dump(mode="json")}, as_node=RESUME_FROM[st.stage])
                result = self._finish(user_id, st.thread_id, GRAPH.invoke(None, config)) | {"recalculated": True}
        return result | {"changed": changed}

    # ------------------------------------------------------------ opciones de habilidades
    def skill_options(self, user_id: int, per_kind: int = 30) -> dict[str, list[str]]:
        """Hasta 30 habilidades por tipo para elegir con un clic. Primero las que piden las vacantes de los
        cargos/sectores que busca el candidato, luego las más pedidas en general, luego el resto del catálogo."""
        p = self.current_profile(user_id) or Profile()
        roles = [set(strip_accents(r).lower().split()) for r in p.expectations.desired_roles]
        relevant: Counter[str] = Counter()
        general: Counter[str] = Counter()
        for v in self.catalog.values():
            items = [*v.must_have, *v.nice_to_have, *v.skill_levels]
            general.update(items)
            title = set(strip_accents(v.title).lower().split())
            if (v.sector and v.sector in p.expectations.sectors) or any(
                    len(r & title) >= max(1, len(r) // 2) for r in roles if r):
                relevant.update(items)
        order = {name: i for i, name in enumerate(SKILL_CATALOG)}
        ranked = sorted(SKILL_CATALOG, key=lambda n: (-relevant[n], -general[n], order[n]))
        out: dict[str, list[str]] = {k: [] for k in KINDS}
        for name in ranked:
            kind = SKILL_CATALOG[name][0]
            if len(out[kind]) < per_kind:
                out[kind].append(name)
        return out

    # ------------------------------------------------------------ simulación del tiempo
    def advance_time(self, user_id: int, days: int) -> dict:
        st = self.repo.get_state(user_id)
        if st.stage != "tracking":
            raise FlowError("Primero completa el onboarding y aprueba postulaciones")
        new_day = st.sim_day + days
        self.repo.update_state(user_id, sim_day=new_day)
        tracer = Tracer(self.repo, user_id, st.thread_id or "tracking", new_day)
        tracer.log("orquestador", f"Avanzó el reloj simulado {days} día(s)",
                   f"Día simulado {st.sim_day} → {new_day}. Las empresas (simuladas) responden y "
                   "luego se ejecuta el Agente de Seguimiento.", mode="system")
        changes = 0
        for a in self.repo.list_applications(user_id):
            status = ApplicationStatus(a.status)
            for d in range(st.sim_day + 1, new_day + 1):
                new = simulate_company_response(a.id, status, d - a.updated_day, d, a.score)
                if new != status:
                    hist = [*a.history, {"status": new.value, "day": d, "by": "portal"}]
                    fields: dict[str, Any] = {"status": new.value, "updated_day": d, "history": hist}
                    if new == ApplicationStatus.ENTREVISTA:
                        fields["interview_day"] = d + 2
                    self.repo.update_application(a.id, **fields)
                    tracer.log("portal", f"{a.company}: {status.value} → {new.value}",
                               f"Respuesta simulada de la empresa para {a.vacancy_title} (día {d}). "
                               f"La probabilidad de avanzar depende del puntaje de match ({a.score}).",
                               mode="system", details={"application_id": a.id})
                    a.status, a.updated_day, a.history = new.value, d, hist
                    if new == ApplicationStatus.ENTREVISTA:
                        a.interview_day = d + 2
                    status = new
                    changes += 1
        profile = self.current_profile(user_id) or Profile()
        created = self.followup_agent.run(user_id, profile, self.catalog, tracer)
        return {"sim_day": new_day, "status_changes": changes, "reminders_created": created}

    def reset(self, user_id: int) -> None:
        self.repo.reset_user(user_id)
