"""Reglas del proceso de postulación: simulación de respuestas de empresas y
reglas de seguimiento (qué recordatorio corresponde y cuándo)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.domain.models import ApplicationStatus as S


def _roll(*parts: object) -> float:
    """Número pseudoaleatorio determinista en [0,1) para que la demo sea reproducible."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def simulate_company_response(app_id: int, status: S, days_in_status: int, day: int,
                              score: float) -> S:
    """Simula lo que haría la empresa. Cada postulación tiene UN desenlace determinista
    (no se tira el dado cada día). Mejor puntaje de match => más probabilidad de entrevista.
    `day` se conserva en la firma por compatibilidad; el resultado no depende de él."""
    boost = (score - 50) / 200  # entre -0.25 y +0.25
    if status == S.POSTULADO:
        wait = 1 + int(_roll(app_id, "revision") * 3)  # 1-3 días
        return S.EN_REVISION if days_in_status >= wait else status
    if status == S.EN_REVISION:
        wait = 2 + int(_roll(app_id, "espera") * 3)  # 2-4 días
        if days_in_status < wait:
            return status
        r = _roll(app_id, "desenlace")
        if r < 0.55 + boost:
            return S.ENTREVISTA
        if r > 0.85 + boost / 2:
            return S.DESCARTADO
        return status  # la empresa no responde: el Agente de Seguimiento sugerirá contactar
    return status


@dataclass
class FollowupTrigger:
    kind: str
    application_id: int | None
    title: str
    template: str
    due_in_days: int
    reason: str


def followup_triggers(app: dict, day: int) -> list[FollowupTrigger]:
    """Reglas que deciden CUÁNDO y QUÉ recordar. `app` trae id, status, updated_day,
    interview_day, vacancy_title, company."""
    out: list[FollowupTrigger] = []
    st = S(app["status"])
    gaps = app.get("gaps") or []
    if st == S.POSTULADO and gaps:
        items = "; ".join(g["message"] for g in gaps[:4])
        out.append(FollowupTrigger(
            "plan_preparacion", app["id"], f"Plan de preparación: {app['vacancy_title']}",
            f"Te postulaste aunque te faltan algunas cosas, y está bien: prepárate mientras responden. {items}.",
            1, f"la vacante tiene {len(gaps)} brecha(s) con tu perfil (no descartan: se convierten en preparación)"))
    days = day - app["updated_day"]
    title, company = app["vacancy_title"], app["company"]
    if st == S.POSTULADO and days >= 5:
        out.append(FollowupTrigger(
            "seguimiento", app["id"], f"Haz seguimiento a {company}",
            f"Tu postulación a {title} lleva {days} días sin respuesta. Envía un mensaje corto "
            f"reiterando tu interés.", 0, f"postulado hace {days} días (regla: ≥5 días sin respuesta)"))
    if st == S.EN_REVISION and days >= 5:
        out.append(FollowupTrigger(
            "seguimiento", app["id"], f"{company} no responde: escríbeles",
            f"Tu proceso para {title} lleva {days} días en revisión sin novedades. Envía un mensaje "
            f"cordial preguntando por el estado.", 0, f"en revisión hace {days} días (regla: ≥5 días)"))
    if st == S.EN_REVISION:
        out.append(FollowupTrigger(
            "preparacion", app["id"], f"Prepárate: {company} revisa tu perfil",
            f"{company} está revisando tu postulación a {title}. Repasa los requisitos de la vacante "
            f"y ten listos ejemplos de tus proyectos.", 1, "estado cambió a en revisión"))
    if st == S.ENTREVISTA:
        due = max(0, (app.get("interview_day") or day + 2) - day)
        out.append(FollowupTrigger(
            "entrevista", app["id"], f"Entrevista con {company} en {due} día(s)",
            f"Tienes entrevista para {title}. Investiga la empresa, repasa las skills que pide la "
            f"vacante y prepara 2 preguntas para el entrevistador."
            + (f" Llega preparado en: {', '.join(g['item'] for g in gaps[:3])}." if gaps else ""), due,
            "estado cambió a entrevista (regla: preparar 2 días antes)"))
    if st == S.DESCARTADO:
        out.append(FollowupTrigger(
            "alternativas", app["id"], f"{company} no continuó: revisa alternativas",
            f"No avanzaste en {title}. No te desanimes: revisa las vacantes similares recomendadas "
            f"y las skills que te faltaron.", 0, "estado cambió a descartado"))
    return out
