"""Agente de Seguimiento (híbrido).

- Reglas deciden CUÁNDO y QUÉ recordar (según estado y días transcurridos).
- IA redacta el CÓMO: mensaje personalizado y checklist de próximos pasos usando la
  vacante y el perfil. Si no hay IA, se usa la plantilla de la regla.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.tracing import Tracer
from app.domain.completeness import cv_completeness
from app.domain.models import Profile, Vacancy
from app.domain.process import FollowupTrigger, followup_triggers
from app.infrastructure.llm.provider import LLMChain
from app.infrastructure.repositories import Repository


class PersonalizedReminder(BaseModel):
    index: int = Field(description="Índice del recordatorio recibido")
    message: str = Field(description="Mensaje personalizado, máximo 3 frases, en español y en segunda persona")
    next_steps: list[str] = Field(default_factory=list, description="2 a 4 pasos concretos y accionables")


class PersonalizedBatch(BaseModel):
    items: list[PersonalizedReminder]


SYSTEM_PROMPT = (
    "Eres el Agente de Seguimiento de una plataforma de empleo colombiana. Recibes recordatorios "
    "generados por reglas y debes personalizarlos para el candidato usando su perfil y la vacante. "
    "Sé concreto: menciona skills que pide la vacante y que el candidato tiene o le faltan. "
    "Las brechas NO son motivo para desanimar: conviértelas en pasos de preparación concretos y realistas. "
    "Si el recordatorio es de perfil, menciona SOLO los campos faltantes indicados en el texto base. "
    "Tono cercano y motivador, sin inventar datos de la empresa."
)


class FollowupAgent:
    name = "seguimiento"

    def __init__(self, repo: Repository, llm: LLMChain):
        self.repo, self.llm = repo, llm

    def run(self, user_id: int, profile: Profile, vacancies: dict[str, Vacancy], tracer: Tracer) -> int:
        day = tracer.sim_day
        apps = self.repo.list_applications(user_id)
        pending: list[tuple[FollowupTrigger, str, object]] = []
        for a in apps:
            for t in followup_triggers({"id": a.id, "status": a.status, "updated_day": a.updated_day,
                                        "interview_day": a.interview_day, "vacancy_title": a.vacancy_title,
                                        "company": a.company, "gaps": (a.evidence or {}).get("gaps", [])}, day):
                status_key = f"{t.kind}:{a.status}"
                if not self.repo.reminder_exists(user_id, a.id, status_key):
                    pending.append((t, status_key, a))

        cv = cv_completeness(profile)
        score = cv.score
        lacking = [b["label"] for b in cv.breakdown if b["got"] < b["weight"]]
        if score < 90 and not self.repo.reminder_exists(user_id, None, "perfil:incompleto"):
            pending.append((FollowupTrigger(
                "perfil", None, "Mejora tu hoja de vida",
                f"Tu hoja de vida está al {score}%. Te falta: "
                f"{', '.join(lacking) or 'detalles menores'}. "
                "Un perfil completo mejora tus recomendaciones.", 0,
                f"completitud {score}% < 90% (regla)"), "perfil:incompleto", None))

        if not pending:
            tracer.log(self.name, "Revisó procesos: sin novedades",
                       f"{len(apps)} procesos revisados; ninguna regla de recordatorio se activó en el día {day}.")
            return 0

        tracer.log(self.name, f"Reglas activaron {len(pending)} recordatorio(s)",
                   "; ".join(f"{t.title} ← {t.reason}" for t, _, _ in pending),
                   details={"triggers": [t.reason for t, _, _ in pending]})

        # --- IA: personaliza en UN solo llamado (ahorra cuota gratuita)
        context = []
        for i, (t, _, a) in enumerate(pending):
            v = vacancies.get(a.vacancy_id) if a else None
            gaps = (a.evidence or {}).get("gaps", []) if a else []
            context.append(
                f"[{i}] tipo={t.kind} | texto_base={t.template}"
                + (f" | brechas={'; '.join(g['message'] for g in gaps[:5])}" if gaps else "")
                + (f" | vacante={v.title} en {v.company}; skills obligatorias={', '.join(v.must_have)};"
                   f" deseables={', '.join(v.nice_to_have)}" if v else ""))
        user_msg = (f"Perfil del candidato: {profile.headline or ''}; seniority={profile.seniority}; "
                    f"skills={', '.join(profile.skill_names[:20])}; años de experiencia={profile.years_experience}.\n\n"
                    "Recordatorios:\n" + "\n".join(context))
        ai, meta = self.llm.invoke_structured(PersonalizedBatch, SYSTEM_PROMPT, user_msg)
        by_index = {it.index: it for it in (ai.items if ai else [])}

        for i, (t, status_key, a) in enumerate(pending):
            personalized = by_index.get(i)
            mode = "llm" if personalized else "rules"
            message = personalized.message if personalized else t.template
            self.repo.add_reminder(user_id=user_id, application_id=t.application_id, kind=t.kind,
                                   status_key=status_key, title=t.title, message=message,
                                   due_day=day + t.due_in_days, mode=mode)
            if a is not None:
                gap_steps = [g["message"] for g in (a.evidence or {}).get("gaps", [])[:4]]
                fallback = gap_steps if t.kind == "plan_preparacion" and gap_steps else [t.template]
                steps = personalized.next_steps if personalized and personalized.next_steps else fallback
                self.repo.update_application(a.id, next_steps=steps)

        if ai:
            tracer.log(self.name, "Personalizó los recordatorios con IA",
                       f"{len(by_index)} de {len(pending)} mensajes redactados con base en la vacante y el perfil "
                       "(un solo llamado para ahorrar cuota).",
                       mode="llm", provider=meta.provider, duration_ms=meta.duration_ms,
                       details={"fallback_errors": meta.errors})
        else:
            tracer.log(self.name, "Usó plantillas de reglas",
                       "IA no disponible; se guardaron los mensajes base de cada regla.",
                       details={"fallback_errors": meta.errors})
        return len(pending)
