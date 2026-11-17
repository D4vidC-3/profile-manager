"""Fuentes de vacantes. Hoy: dataset curado (JSON). La interfaz permite agregar un
scraper controlado o una API mock sin tocar el agente."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.domain.colombia import (
    WORKDAYS,
    contract_category,
    infer_sector,
    normalize_city,
    normalize_education,
    normalize_modality,
    normalize_seniority,
    parse_salary_range,
)
from app.domain.languages import parse_language
from app.domain.models import Modality, Seniority, Vacancy
from app.domain.skills import normalize_skill, normalize_skills, split_level

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "vacancies_raw.json"


class VacancySource(Protocol):
    name: str

    def fetch_raw(self) -> list[dict]: ...


class JsonDatasetSource:
    name = "dataset_curado"

    def __init__(self, path: Path = DATA_FILE):
        self.path = path

    def fetch_raw(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8"))


def _split(v: str | list | None) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return v
    return [x.strip() for x in str(v).split(",") if x.strip()]


def normalize_vacancy(raw: dict) -> tuple[Vacancy | None, list[str]]:
    """Convierte un registro crudo al formato canónico. Devuelve (vacante, cambios aplicados)."""
    changes: list[str] = []
    try:
        city_raw = raw.get("ubicacion") or raw.get("city")
        city = normalize_city(city_raw)
        if city_raw and city != city_raw:
            changes.append(f"ciudad '{city_raw}' → '{city}'")
        mod_raw = raw.get("modalidad") or raw.get("modality")
        modality = normalize_modality(mod_raw) or Modality.PRESENCIAL
        if mod_raw and modality.value != str(mod_raw).lower():
            changes.append(f"modalidad '{mod_raw}' → '{modality.value}'")
        sal_raw = raw.get("salario") or raw.get("salary")
        smin, smax = parse_salary_range(sal_raw)
        if sal_raw:
            changes.append(f"salario '{sal_raw}' → {smin}-{smax}")
        must_items = _split(raw.get("requisitos") or raw.get("must_have"))
        # Los idiomas no son skills: "Inglés B2" pasa a requisitos de idioma
        languages: dict[str, str] = {}
        must_raw = []
        skill_levels: dict[str, str] = {}
        for item in must_items:
            lang = parse_language(item)
            if lang:
                languages[lang.name] = lang.cefr or "B1"
                changes.append(f"idioma requerido {lang.name} {languages[lang.name]}")
            else:
                base, level = split_level(item)  # "Excel avanzado" -> Excel + nivel requerido
                must_raw.append(base)
                if level:
                    skill_levels[normalize_skill(base)] = level
        must = normalize_skills(must_raw)
        if [m.lower() for m in must_raw] != [m.lower() for m in must]:
            changes.append(f"skills {must_raw} → {must}")
        v = Vacancy(
            id=str(raw["id"]),
            title=str(raw.get("titulo") or raw["title"]).strip(),
            company=str(raw.get("empresa") or raw.get("company") or "Empresa confidencial"),
            city=city,
            modality=modality,
            salary_min_cop=smin,
            salary_max_cop=smax,
            seniority=normalize_seniority(raw.get("nivel") or raw.get("seniority")) or Seniority.JUNIOR,
            must_have=must,
            languages=languages,
            skill_levels=skill_levels,
            sector=raw.get("sector") or infer_sector(str(raw.get("titulo") or raw.get("title") or "")),
            workday=next((w for w in WORKDAYS if w.lower() == str(raw.get("jornada", "")).lower()), "Tiempo completo"),
            contract=contract_category(raw.get("tipo_contrato") or raw.get("contract")),
            min_education=normalize_education(raw.get("educacion_minima") or raw.get("min_education")),
            requires_travel=bool(raw.get("requiere_viajar") or raw.get("requires_travel")),
            nice_to_have=normalize_skills(_split(raw.get("deseables") or raw.get("nice_to_have"))),
            description=str(raw.get("descripcion") or raw.get("description") or "")[:2000],
            posted_at=raw.get("fecha_publicacion") or raw.get("posted_at"),
            source=str(raw.get("fuente") or "dataset"),
        )
        return v, changes
    except (KeyError, ValueError, TypeError) as exc:
        return None, [f"registro inválido: {type(exc).__name__}"]


def load_catalog(sources: list[VacancySource]) -> dict[str, Vacancy]:
    """Catálogo normalizado (sin trazas), para consultas de la API y del seguimiento."""
    out: dict[str, Vacancy] = {}
    for src in sources:
        for r in src.fetch_raw():
            v, _ = normalize_vacancy(r)
            if v:
                out[v.id] = v
    return out
