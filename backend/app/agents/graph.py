"""Orquestación con LangGraph.

  START → perfil → completar_cv* → expectativas* → vacantes → aprobar* → niveles* → identidad* → postulacion
        → seguimiento → END

  (*) nodos con `interrupt()`: el grafo se pausa y la API muestra un formulario.
  - completar_cv:  vacíos de la HOJA DE VIDA (solo contacto y ≥3 skills bloquean; idiomas y proyectos se sugieren).
  - expectativas:  "¿Qué estás buscando?" (no viene del CV). Obligatorio para recomendar.
  - aprobar:       el candidato elige a qué vacantes postular (human-in-the-loop).
  - niveles:       requisito para postular: nivel de cada herramienta y conocimiento técnico.
  - identidad:     documento y nombres/apellidos, solo cuando va a postular.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.application_agent import ApplicationAgent
from app.agents.followup_agent import FollowupAgent
from app.agents.profile_agent import ProfileAgent, same_person
from app.agents.tracing import Tracer
from app.agents.vacancy_agent import VacancyAgent
from app.domain.colombia import (
    AVAILABILITY_OPTIONS,
    CONTRACT_TYPES,
    SALARY_FREQUENCIES,
    SECTORS,
    WORKDAYS,
)
from app.domain.completeness import (
    apply_cv_answers,
    apply_identity,
    apply_preferences,
    apply_skill_levels,
    career_change_skills,
    critical_cv_gaps,
    cv_completeness,
    detect_cv_gaps,
    identity_form,
    identity_gaps,
    is_first_job,
    missing_preferences,
    preferences_form,
    skill_levels_form,
    skills_without_level,
)
from app.domain.models import Expectations, MatchResult, Profile, Vacancy
from app.domain.skills import strip_accents
from app.infrastructure.repositories import Repository


class AgentState(TypedDict, total=False):
    cv_text: str
    cv_sha256: str
    previous: dict | None
    profile: dict
    cv_reviewed: bool
    prefs_confirmed: bool
    prefs_prefill: dict | None
    matches: list[dict]
    approved_ids: list[str]
    application_ids: list[int]
    reminders_created: int


@dataclass
class Deps:
    user_id: int
    repo: Repository
    tracer: Tracer
    profile_agent: ProfileAgent
    vacancy_agent: VacancyAgent
    application_agent: ApplicationAgent
    followup_agent: FollowupAgent
    catalog: dict[str, Vacancy]


CATALOGS = {"sectors": SECTORS, "workdays": WORKDAYS, "contract_types": CONTRACT_TYPES,
            "availability": AVAILABILITY_OPTIONS, "salary_frequencies": SALARY_FREQUENCIES,
            "modalities": ["presencial", "hibrido", "remoto"]}


def _deps(config: RunnableConfig) -> Deps:
    return config["configurable"]["deps"]


def save_profile(d: Deps, profile: Profile, sha: str | None = None) -> dict:
    profile.first_job, _ = is_first_job(profile)
    cv = cv_completeness(profile)
    gaps = [g.model_dump() for g in detect_cv_gaps(profile)]
    data = profile.model_dump(mode="json")
    d.repo.save_profile(d.user_id, data, cv.score, gaps, sha)
    return data


def role_skills(profile: Profile, catalog: dict[str, Vacancy], top: int = 6) -> list[str]:
    """Skills más pedidas por las vacantes cuyos cargos coinciden con lo que busca el candidato."""
    roles = [set(strip_accents(r).lower().split()) for r in profile.expectations.desired_roles]
    counter: Counter[str] = Counter()
    for v in catalog.values():
        title = set(strip_accents(v.title).lower().split())
        if any(len(r & title) >= max(1, len(r) // 2) for r in roles if r):
            counter.update(v.must_have)
    return [s for s, _ in counter.most_common(top)]


# ---------------------------------------------------------------- nodos
def perfil_node(state: AgentState, config: RunnableConfig) -> dict:
    d = _deps(config)
    previous = Profile(**state["previous"]) if state.get("previous") else None
    profile, _, _ = d.profile_agent.run(state["cv_text"], d.tracer, previous)
    prefill = None
    if previous is not None:
        if same_person(profile, previous) and not missing_preferences(previous):
            prefill = previous.expectations.model_dump(mode="json")
        d.tracer.log("orquestador", "Reinició 'Lo que buscas' por el CV nuevo",
                     ("Es la misma persona: se pre-llenan sus respuestas anteriores para que las confirme o cambie."
                      if prefill else "El CV es de otra persona: el perfil y sus preferencias empiezan de cero."),
                     mode="system", details={"same_person": prefill is not None})
    return {"profile": save_profile(d, profile, state.get("cv_sha256")), "cv_reviewed": False,
            "prefs_confirmed": False, "prefs_prefill": prefill}


def _cv_step_needed(profile: Profile) -> bool:
    return any(g.input_type != "info" for g in detect_cv_gaps(profile))


def route_after_profile(state: AgentState) -> str:
    profile = Profile(**state["profile"])
    if critical_cv_gaps(profile) or (not state.get("cv_reviewed") and _cv_step_needed(profile)):
        return "completar_cv"
    return "expectativas"


def completar_cv_node(state: AgentState, config: RunnableConfig) -> dict:
    profile = Profile(**state["profile"])
    cv = cv_completeness(profile)
    answers: dict[str, Any] = interrupt({
        "type": "cv_gaps",
        "gaps": [g.model_dump() for g in detect_cv_gaps(profile) if g.input_type != "info"],
        "cv": {"score": cv.score, "mode": cv.mode, "reason": cv.reason, "breakdown": cv.breakdown},
    })
    d = _deps(config)
    profile, updated = apply_cv_answers(profile, answers or {})
    data = save_profile(d, profile)
    d.tracer.log("candidato", f"Completó {len(updated)} dato(s) de su hoja de vida",
                 f"Campos: {', '.join(updated) or 'ninguno (omitió las sugerencias)'}. "
                 f"Completitud del CV: {cv_completeness(profile).score}%.", mode="human", details={"updated": updated})
    return {"profile": data, "cv_reviewed": True}


def route_after_cv(state: AgentState) -> str:
    return "completar_cv" if critical_cv_gaps(Profile(**state["profile"])) else "expectativas"


def expectativas_node(state: AgentState, config: RunnableConfig) -> dict:
    profile = Profile(**state["profile"])
    d = _deps(config)
    # Con cada CV nuevo se vuelve a preguntar (pre-llenado con lo anterior) para que pueda actualizarlo
    if not state.get("prefs_confirmed") or missing_preferences(profile):
        prefill = Expectations(**state["prefs_prefill"]) if state.get("prefs_prefill") else None
        data: dict[str, Any] = interrupt({"type": "preferences", **preferences_form(profile, prefill),
                                          "catalogs": CATALOGS})
        profile, updated = apply_preferences(profile, data or {})
        d.tracer.log("candidato", "Definió lo que está buscando",
                     f"Preferencias completadas: {', '.join(updated) or 'ninguna'}. Esto NO sale del CV: lo declara "
                     "el candidato.", mode="human", details={"updated": updated})
    if missing_preferences(profile):
        return {"profile": save_profile(d, profile), "prefs_confirmed": False}
    # Cambio de carrera: tiene experiencia, pero no en lo que piden los cargos que busca
    gap_skills = career_change_skills(profile, role_skills(profile, d.catalog))
    have = {s.lower() for s in profile.skill_names}
    unbacked = [s for s in gap_skills if s.lower() in have]  # dice saberlas, pero su experiencia no lo respalda
    profile.suggestions["projects_for"] = unbacked[:4]
    if unbacked and len(unbacked) >= 2:
        d.tracer.log("perfil", "Sugirió agregar proyectos (cambio de carrera)",
                     f"Los cargos que busca piden {', '.join(gap_skills)}; su experiencia laboral no respalda "
                     f"{', '.join(unbacked)}. Un proyecto convertiría esas skills en 'demostradas'. No bloquea.",
                     details={"skills": unbacked})
    return {"profile": save_profile(d, profile), "prefs_confirmed": True}


def route_after_expectations(state: AgentState) -> str:
    return "expectativas" if missing_preferences(Profile(**state["profile"])) else "vacantes"


def vacantes_node(state: AgentState, config: RunnableConfig) -> dict:
    d = _deps(config)
    profile = Profile(**state["profile"])
    exclude = d.repo.applied_vacancy_ids(d.user_id)
    matches, _ = d.vacancy_agent.run(profile, d.tracer, exclude_ids=exclude)
    data = [m.model_dump(mode="json") for m in matches]
    d.repo.replace_matches(d.user_id, data)
    return {"matches": data}


def aprobar_node(state: AgentState, config: RunnableConfig) -> dict:
    approved: list[str] = interrupt({"type": "approval", "matches": state.get("matches", [])})
    d = _deps(config)
    valid = {m["vacancy"]["id"] for m in state.get("matches", [])}
    approved = [a for a in (approved or []) if a in valid]
    d.tracer.log("candidato", f"Aprobó {len(approved)} postulación(es)",
                 "Human-in-the-loop: el sistema nunca postula sin la aprobación explícita del candidato.",
                 mode="human", details={"approved": approved})
    return {"approved_ids": approved}


def _next_before_applying(profile: Profile) -> str:
    if skills_without_level(profile):
        return "niveles"
    return "identidad" if identity_gaps(profile) else "postulacion"


def route_after_approval(state: AgentState) -> str:
    if not state.get("approved_ids"):
        return "seguimiento"
    return _next_before_applying(Profile(**state["profile"]))


def niveles_node(state: AgentState, config: RunnableConfig) -> dict:
    """Requisito para postular: cada herramienta y conocimiento debe tener nivel confirmado."""
    profile = Profile(**state["profile"])
    data: dict[str, Any] = interrupt({"type": "skill_levels", **skill_levels_form(profile)})
    d = _deps(config)
    profile, updated = apply_skill_levels(profile, (data or {}).get("levels", {}))
    d.tracer.log("candidato", f"Confirmó el nivel de {len(updated)} habilidad(es)",
                 "Requisito para postular: las empresas necesitan saber qué tan bien maneja cada herramienta o "
                 f"conocimiento. Pendientes: {len(skills_without_level(profile))}.", mode="human",
                 details={"updated": updated})
    return {"profile": save_profile(d, profile)}


def route_after_levels(state: AgentState) -> str:
    return _next_before_applying(Profile(**state["profile"]))


def identidad_node(state: AgentState, config: RunnableConfig) -> dict:
    profile = Profile(**state["profile"])
    data: dict[str, Any] = interrupt({"type": "identity", **identity_form(profile)})
    d = _deps(config)
    profile, updated = apply_identity(profile, data or {})
    d.tracer.log("candidato", "Completó sus datos de identidad para postular",
                 f"Campos: {', '.join(f for f in updated if f != 'sensitive') or 'ninguno'}"
                 + (". Autorizó datos sensibles opcionales (no se usan en el puntaje)"
                    if "sensitive" in updated else "")
                 + ". Se piden solo al postular porque el portal los exige.", mode="human",
                 details={"updated": [f for f in updated if f != "sensitive"]})
    return {"profile": save_profile(d, profile)}


def route_after_identity(state: AgentState) -> str:
    return "identidad" if identity_gaps(Profile(**state["profile"])) else "postulacion"


def postulacion_node(state: AgentState, config: RunnableConfig) -> dict:
    d = _deps(config)
    profile = Profile(**state["profile"])
    approved = [MatchResult(**m) for m in state.get("matches", [])
                if m["vacancy"]["id"] in set(state.get("approved_ids", []))]
    ids = d.application_agent.run(d.user_id, profile, approved, d.tracer)
    return {"application_ids": ids}


def seguimiento_node(state: AgentState, config: RunnableConfig) -> dict:
    d = _deps(config)
    n = d.followup_agent.run(d.user_id, Profile(**state["profile"]), d.catalog, d.tracer)
    return {"reminders_created": n}


# Nodo "anterior" a cada pausa: al editar el perfil se reanuda desde ahí (LangGraph update_state)
RESUME_FROM = {"cv_gaps": "perfil", "preferences": "completar_cv", "approval": "expectativas",
               "skill_levels": "aprobar", "identity": "aprobar"}


def build_graph():
    g = StateGraph(AgentState)
    for name, fn in (("perfil", perfil_node), ("completar_cv", completar_cv_node),
                     ("expectativas", expectativas_node), ("vacantes", vacantes_node), ("aprobar", aprobar_node),
                     ("niveles", niveles_node), ("identidad", identidad_node), ("postulacion", postulacion_node),
                     ("seguimiento", seguimiento_node)):
        g.add_node(name, fn)
    g.add_edge(START, "perfil")
    g.add_conditional_edges("perfil", route_after_profile, ["completar_cv", "expectativas"])
    g.add_conditional_edges("completar_cv", route_after_cv, ["completar_cv", "expectativas"])
    g.add_conditional_edges("expectativas", route_after_expectations, ["expectativas", "vacantes"])
    g.add_edge("vacantes", "aprobar")
    g.add_conditional_edges("aprobar", route_after_approval, ["niveles", "identidad", "postulacion", "seguimiento"])
    g.add_conditional_edges("niveles", route_after_levels, ["niveles", "identidad", "postulacion"])
    g.add_conditional_edges("identidad", route_after_identity, ["identidad", "postulacion"])
    g.add_edge("postulacion", "seguimiento")
    g.add_edge("seguimiento", END)
    return g.compile(checkpointer=InMemorySaver())


GRAPH = build_graph()
