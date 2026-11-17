"""Agente de Postulación: llena el formulario del portal demo con los datos del perfil,
guarda evidencia (payload, comprobante, hash) y crea el proceso con estado inicial."""

from __future__ import annotations

from app.agents.tracing import Tracer
from app.domain.colombia import format_cop
from app.domain.models import ApplicationStatus, MatchResult, Profile
from app.infrastructure.portal import PortalRejected, submit_application
from app.infrastructure.repositories import Repository


def build_cover_letter(profile: Profile, m: MatchResult) -> str:
    v = m.vacancy
    have = [s for s in v.must_have if s not in m.missing_skills]
    return (f"Hola equipo de {v.company}: me interesa la vacante {v.title}. "
            f"Cuento con experiencia en {', '.join(have[:4]) or ', '.join(profile.skill_names[:4])}"
            + (f" y {profile.years_experience:g} años de trayectoria" if profile.years_experience else "")
            + ". Quedo atento(a) para conversar. " + (profile.full_name or ""))


class ApplicationAgent:
    name = "postulacion"

    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, user_id: int, profile: Profile, approved: list[MatchResult], tracer: Tracer
            ) -> list[int]:
        already = self.repo.applied_vacancy_ids(user_id)
        created: list[int] = []
        for m in approved:
            v = m.vacancy
            if v.id in already:
                tracer.log(self.name, f"Omitió {v.title}",
                           "Ya existe una postulación a esta vacante (evita duplicados).")
                continue
            form = {
                "vacancy_id": v.id,
                "full_name": profile.full_name,
                "first_names": profile.first_names,
                "last_names": profile.last_names,
                "document_type": profile.document_type,
                "email": profile.email,
                "phone": profile.phone,
                "city": profile.city,
                "document_id": profile.document_id,
                "linkedin": profile.linkedin,
                "salary_expectation_cop": profile.expectations.salary_min_cop,
                "salary_frequency": profile.expectations.salary_frequency,
                "availability": profile.expectations.availability,
                "skills": profile.skill_names,
                "cover_letter": build_cover_letter(profile, m),
            }
            try:
                receipt = submit_application(form)
            except PortalRejected as exc:
                tracer.log(self.name, f"No pudo postular a {v.title}", f"El portal rechazó el formulario: {exc}",
                           details={"vacancy_id": v.id})
                continue
            row = self.repo.add_application(
                user_id=user_id, vacancy_id=v.id, vacancy_title=v.title, company=v.company, score=m.score,
                status=ApplicationStatus.POSTULADO.value, created_day=tracer.sim_day, updated_day=tracer.sim_day,
                # La evidencia NO guarda el número de documento (dato personal): basta el hash del envío
                evidence={"form": {k: val for k, val in form.items() if k not in ("document_id",)},
                          "receipt": receipt, "match_reasons": m.reasons,
                          "gaps": [g.model_dump() for g in m.gaps]},
                history=[{"status": "postulado", "day": tracer.sim_day, "by": "postulacion"}],
                next_steps=["Esperar respuesta de la empresa (5 días hábiles)"],
            )
            created.append(row.id)
            tracer.log(self.name, f"Postuló a {v.title} @ {v.company}",
                       f"Aprobada por el candidato con puntaje {m.score}. Llenó {len(form)} campos del formulario "
                       f"desde el perfil (aspiración {format_cop(profile.expectations.salary_min_cop)}). "
                       f"Comprobante {receipt['receipt_id']}.",
                       details={"application_id": row.id, "receipt": receipt})
        return created
