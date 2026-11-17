"""Agente de Vacantes: ingesta, normaliza, deduplica y rankea vacantes (reglas explicables)."""

from __future__ import annotations

from collections import Counter

from app.agents.tracing import Tracer
from app.domain.models import Discard, MatchResult, Profile, Vacancy
from app.domain.scoring import WEIGHTS, rank
from app.infrastructure.vacancies.source import VacancySource, normalize_vacancy


class VacancyAgent:
    name = "vacantes"

    def __init__(self, sources: list[VacancySource], threshold: float, limit: int):
        self.sources, self.threshold, self.limit = sources, threshold, limit

    def ingest(self, tracer: Tracer) -> list[Vacancy]:
        vacancies: dict[str, Vacancy] = {}
        invalid = 0
        examples: list[str] = []
        for src in self.sources:
            raw = src.fetch_raw()
            for r in raw:
                v, changes = normalize_vacancy(r)
                if v is None:
                    invalid += 1
                    continue
                key = f"{v.title.lower()}|{v.company.lower()}|{v.city}"
                if key in vacancies:  # duplicada entre fuentes
                    continue
                vacancies[v.id] = v
                if changes and len(examples) < 4:
                    examples.append(f"{v.id}: " + "; ".join(changes[:2]))
            tracer.log(self.name, f"Ingirió {len(raw)} vacantes de '{src.name}'",
                       f"Se normalizaron ciudades, modalidades, salarios a COP y skills a nombres canónicos. "
                       f"{invalid} registros inválidos descartados.",
                       details={"source": src.name, "examples": examples, "valid": len(vacancies)})
        return list(vacancies.values())

    def run(self, profile: Profile, tracer: Tracer, exclude_ids: set[str] | None = None
            ) -> tuple[list[MatchResult], list[Discard]]:
        vacancies = [v for v in self.ingest(tracer) if v.id not in (exclude_ids or set())]
        matches, discards = rank(profile, vacancies, self.threshold, self.limit)
        reasons = Counter(d.reason.split(" y ")[0].split(" (")[0][:60] for d in discards)
        tracer.log(self.name, f"Descartó {len(discards)} vacantes",
                   "Filtros duros (ubicación/modalidad, salario, nivel, skills mínimas, jornada, tipo de "
                   "vinculación) y umbral de puntaje "
                   f"{self.threshold}. Motivos más comunes: "
                   + "; ".join(f"{r} ({n})" for r, n in reasons.most_common(3)),
                   details={"discards": [d.model_dump() for d in discards[:30]]})
        top = [f"{m.vacancy.title} @ {m.vacancy.company} ({m.score})" for m in matches[:5]]
        tracer.log(self.name, f"Recomendó {len(matches)} vacantes",
                   "Puntaje 0-100 con pesos: " + ", ".join(f"{k} {int(w)}" for k, w in WEIGHTS.items())
                   + ". Empates se resuelven por fecha de publicación (timing). Top: " + " | ".join(top),
                   details={"top": top})
        pending = sorted({lang for m in matches for lang in m.pending_languages})
        if pending:
            tracer.log(self.name, "Detectó idiomas por confirmar",
                       f"{sum(1 for m in matches if m.pending_languages)} vacante(s) recomendadas piden "
                       f"{', '.join(pending)} y el nivel del candidato está pendiente: cuentan a medias hasta "
                       "que lo confirme.", details={"languages": pending})
        return matches, discards
