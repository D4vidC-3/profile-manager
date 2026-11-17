"""Endpoints del flujo principal: onboarding → recomendaciones → acciones → tablero."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentUser, current_user, get_service, limiter
from app.api.schemas import (
    AdvanceIn,
    ApproveIn,
    CvAnswersIn,
    FlowOut,
    IdentityIn,
    PreferencesIn,
    ProfileEditIn,
    ReminderPatch,
    SkillLevelsIn,
    StateOut,
)
from app.application.services import FlowError, ProfileManagerService
from app.config import get_settings
from app.domain.colombia import (
    AVAILABILITY_OPTIONS,
    CONTRACT_TYPES,
    DISABILITY_TYPES,
    DOCUMENT_TYPES,
    SALARY_FREQUENCIES,
    SECTORS,
    SEX_OPTIONS,
    WORKDAYS,
)
from app.domain.languages import CEFR_OPTIONS, LANGUAGE_NAMES
from app.infrastructure.cv.extractor import CVReadError

router = APIRouter(prefix="/api", tags=["candidato"])


def _flow(fn, *args):
    try:
        return fn(*args)
    except FlowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get("/state", response_model=StateOut)
def get_state(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    st = svc.repo.get_state(user.id)
    return StateOut(stage=st.stage, sim_day=st.sim_day, pending=st.pending,
                    llm_providers=svc.llm.available() + ["mock"])


@router.get("/catalogs")
def catalogs():
    """Listas cerradas para los formularios (sectores, jornadas, documentos...)."""
    return {"sectors": SECTORS, "workdays": WORKDAYS, "contract_types": CONTRACT_TYPES,
            "availability": AVAILABILITY_OPTIONS, "salary_frequencies": SALARY_FREQUENCIES,
            "modalities": ["presencial", "hibrido", "remoto"], "document_types": DOCUMENT_TYPES,
            "sex_options": SEX_OPTIONS, "disability_types": DISABILITY_TYPES,
            "language_levels": CEFR_OPTIONS,
            "languages": list(LANGUAGE_NAMES),
            "skill_kinds": [{"value": "herramienta", "label": "Herramientas y tecnologías"},
                            {"value": "conocimiento", "label": "Conocimientos técnicos"},
                            {"value": "transversal", "label": "Habilidades transversales"}],
            "skill_levels": [{"value": "basico", "label": "Básico"}, {"value": "intermedio", "label": "Intermedio"},
                             {"value": "avanzado", "label": "Avanzado"}]}


@router.get("/skills/options")
def skill_options(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    """Hasta 30 habilidades por tipo para elegir, ordenadas por lo que piden las vacantes que busca."""
    return svc.skill_options(user.id)


@router.post("/onboarding", response_model=FlowOut)
@limiter.limit("6/minute")
def onboarding(request: Request, cv: UploadFile = File(...), user: CurrentUser = Depends(current_user),
               svc: ProfileManagerService = Depends(get_service)):
    """Sube la hoja de vida (PDF/TXT). Ejecuta el grafo hasta la primera pausa. Lo editado a mano y las
    preferencias del candidato se conservan si sube un CV nuevo."""
    content = cv.file.read(get_settings().max_cv_bytes + 1)
    if len(content) > get_settings().max_cv_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "El CV supera 5 MB")
    try:
        return svc.start_onboarding(user.id, cv.filename or "cv.txt", content)
    except CVReadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.post("/onboarding/cv", response_model=FlowOut)
def cv_answers(body: CvAnswersIn, user: CurrentUser = Depends(current_user),
               svc: ProfileManagerService = Depends(get_service)):
    """Completa vacíos de la hoja de vida (contacto, skills, niveles de idioma, proyectos)."""
    return _flow(svc.answer_cv, user.id, body.answers)


@router.post("/onboarding/preferences", response_model=FlowOut)
def preferences(body: PreferencesIn, user: CurrentUser = Depends(current_user),
                svc: ProfileManagerService = Depends(get_service)):
    """Formulario "¿Qué estás buscando?" (no viene del CV)."""
    return _flow(svc.set_preferences, user.id, body.model_dump())


@router.post("/applications/approve", response_model=FlowOut)
def approve(body: ApproveIn, user: CurrentUser = Depends(current_user),
            svc: ProfileManagerService = Depends(get_service)):
    return _flow(svc.approve, user.id, body.vacancy_ids)


@router.post("/matches/refresh", response_model=FlowOut)
def refresh_matches(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    """Vuelve a ejecutar el Agente de Vacantes con el perfil y las preferencias actuales."""
    return _flow(svc.refresh_matches, user.id)


@router.post("/applications/skill-levels", response_model=FlowOut)
def skill_levels(body: SkillLevelsIn, user: CurrentUser = Depends(current_user),
                 svc: ProfileManagerService = Depends(get_service)):
    """Requisito para postular: nivel de cada herramienta y conocimiento técnico."""
    return _flow(svc.set_skill_levels, user.id, body.levels)


@router.post("/applications/identity", response_model=FlowOut)
def identity(body: IdentityIn, user: CurrentUser = Depends(current_user),
             svc: ProfileManagerService = Depends(get_service)):
    """Documento y nombres/apellidos: se piden solo al postular. Datos sensibles opcionales con autorización."""
    return _flow(svc.set_identity, user.id, body.model_dump())


@router.get("/profile")
def profile(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    view = svc.profile_view(user.id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aún no hay perfil")
    return view


@router.put("/profile")
def edit_profile(body: ProfileEditIn, user: CurrentUser = Depends(current_user),
                 svc: ProfileManagerService = Depends(get_service)):
    """Edición por secciones. Lo editado queda protegido; si el flujo está en pausa, se recalcula."""
    data = body.model_dump(mode="json", exclude_unset=True)
    result = _flow(svc.update_profile, user.id, data)
    return result | {"view": svc.profile_view(user.id)}


@router.get("/matches")
def matches(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    return svc.repo.list_matches(user.id)


@router.get("/vacancies")
def vacancies(svc: ProfileManagerService = Depends(get_service), _: CurrentUser = Depends(current_user)):
    return [v.model_dump(mode="json") for v in svc.catalog.values()]


@router.get("/applications")
def applications(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    return [{"id": a.id, "vacancy_id": a.vacancy_id, "vacancy_title": a.vacancy_title, "company": a.company,
             "score": a.score, "status": a.status, "created_day": a.created_day, "updated_day": a.updated_day,
             "interview_day": a.interview_day, "evidence": a.evidence, "history": a.history,
             "next_steps": a.next_steps} for a in svc.repo.list_applications(user.id)]


@router.get("/reminders")
def reminders(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    return [{"id": r.id, "application_id": r.application_id, "kind": r.kind, "title": r.title,
             "message": r.message, "due_day": r.due_day, "mode": r.mode, "done": r.done}
            for r in svc.repo.list_reminders(user.id)]


@router.patch("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, body: ReminderPatch, user: CurrentUser = Depends(current_user),
                    svc: ProfileManagerService = Depends(get_service)):
    if not svc.repo.set_reminder_done(user.id, reminder_id, body.done):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recordatorio no encontrado")
    return {"ok": True}


@router.post("/simulate/advance")
def advance(body: AdvanceIn, user: CurrentUser = Depends(current_user),
            svc: ProfileManagerService = Depends(get_service)):
    return _flow(svc.advance_time, user.id, body.days)


@router.get("/trace")
def trace(agent: str | None = None, user: CurrentUser = Depends(current_user),
          svc: ProfileManagerService = Depends(get_service)):
    return [{"id": t.id, "run_id": t.run_id, "agent": t.agent, "action": t.action, "reason": t.reason,
             "details": t.details, "mode": t.mode, "provider": t.provider, "duration_ms": t.duration_ms,
             "sim_day": t.sim_day, "created_at": t.created_at.isoformat()}
            for t in svc.repo.list_traces(user.id, agent)]


@router.post("/reset", status_code=204)
def reset(user: CurrentUser = Depends(current_user), svc: ProfileManagerService = Depends(get_service)):
    svc.reset(user.id)
