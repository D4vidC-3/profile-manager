"""Motor de matching explicable (reglas + pesos).

Principios:
  1. Lo que el candidato declara es verdad: una habilidad declarada cuenta completa, tenga o no evidencia
     ("demostrada" es solo una etiqueta informativa).
  2. No cumplir todo NO descarta: las brechas bajan el puntaje y se guardan para que el Agente de
     Seguimiento arme un plan de preparación.
  3. Solo descartan las condiciones que el propio candidato puso: dónde/cómo quiere trabajar, salario
     mínimo, jornada y tipo de vinculación. Y las vacantes que no tienen relación con su perfil.

Nunca se usan datos sensibles (sexo, edad, discapacidad) para calcular el puntaje.
"""

from __future__ import annotations

import re

from app.domain.colombia import education_rank, format_cop, same_metro_area
from app.domain.languages import cefr_rank, effective_cefr
from app.domain.models import (
    SENIORITY_ORDER,
    Discard,
    Gap2Prepare,
    LanguageLevel,
    MatchResult,
    Modality,
    Profile,
    Seniority,
    SkillCheck,
    Vacancy,
)
from app.domain.skills import T, skill_kind, strip_accents
from app.domain.skillset import level_rank

WEIGHTS = {
    "skills_obligatorias": 35.0,
    "skills_deseables": 8.0,
    "transversales": 2.0,
    "rol": 15.0,
    "seniority": 12.0,
    "educacion": 5.0,
    "salario": 8.0,
    "modalidad": 10.0,
    "sector": 5.0,
}
LEVEL_NAME = {"basico": "básico", "intermedio": "intermedio", "avanzado": "avanzado"}
DEDICATION = {"Tiempo completo", "Medio tiempo", "Por horas"}
LANG_CREDIT_BY_DISTANCE = {0: 1.0, 1: 0.75, 2: 0.25}  # B1 cuando piden B2 = 0.75
SKILL_LEVEL_CREDIT = {0: 1.0, 1: 0.75, 2: 0.5}  # intermedio cuando piden avanzado = 0.75

_STOPWORDS = {"de", "del", "la", "el", "en", "y", "para", "con", "jr", "sr", "junior", "senior", "semi", "ssr"}


def _is_soft(name: str) -> bool:
    return skill_kind(name) == T


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9#+.]+", strip_accents(text).lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _lang_label(lang) -> str:
    return "nativo" if lang.level == LanguageLevel.NATIVO else (lang.cefr or "sin nivel")


def candidate_education(profile: Profile) -> tuple[int, bool, str | None]:
    """(rango del nivel más alto, ¿está en curso?, nombre del nivel)."""
    best, in_progress, name = -1, False, None
    for e in profile.education:
        r = education_rank(e.level)
        if r > best or (r == best and e.status != "en_curso"):
            best, in_progress, name = r, e.status == "en_curso", e.level
    return best, in_progress, name


def role_match(profile: Profile, v: Vacancy) -> float:
    roles = profile.expectations.desired_roles or ([profile.headline] if profile.headline else [])
    title_tokens = _tokens(v.title)
    best = 0.0
    for r in roles:
        rt = _tokens(r)
        if rt:
            best = max(best, len(rt & title_tokens) / len(rt))
    return best


def hard_filter(profile: Profile, v: Vacancy) -> str | None:
    """Solo condiciones que el candidato puso o vacantes sin relación con él. Nunca brechas de habilidades."""
    exp = profile.expectations
    city = exp.city or profile.city
    if v.modality != Modality.REMOTO and city and v.city and not same_metro_area(city, v.city) \
            and exp.willing_to_relocate is not True:
        return f"Es {v.modality.value} en {v.city} y vives en {city} sin disposición a reubicarte"
    if exp.modality == Modality.REMOTO and v.modality == Modality.PRESENCIAL:
        return "Buscas trabajo remoto y la vacante es 100% presencial"
    if exp.salary_min_cop and v.salary_max_cop and v.salary_max_cop < exp.salary_min_cop * 0.85:
        return (f"El salario máximo ({format_cop(v.salary_max_cop)}) está más de 15% por debajo "
                f"de tu aspiración ({format_cop(exp.salary_min_cop)})")
    wanted = DEDICATION & set(exp.workday)
    if wanted and v.workday in DEDICATION and v.workday not in wanted:
        return f"La vacante es de {v.workday.lower()} y buscas {', '.join(sorted(wanted)).lower()}"
    if exp.contract_types and v.contract not in exp.contract_types:
        return f"Es '{v.contract}' y estás disponible para: {', '.join(exp.contract_types)}"
    skills = {s.lower() for s in profile.skill_names}
    tech_must = [s for s in v.must_have if not _is_soft(s)]
    # Relevancia mínima (no es una brecha): si no tiene NINGUNA habilidad técnica pedida, solo se recomienda
    # cuando el cargo coincide del todo con lo que busca.
    if tech_must and not any(s.lower() in skills for s in tech_must) and role_match(profile, v) < 1.0:
        return "No tienes ninguna de las habilidades técnicas que pide y el cargo no es el que buscas"
    return None


def score_vacancy(profile: Profile, v: Vacancy) -> MatchResult:
    skills = {s.lower() for s in profile.skill_names}
    levels = {s.name.lower(): s.level for s in profile.skills}
    shown = {s.lower() for s in profile.demonstrated_skills}
    reasons: list[str] = []
    gaps: list[Gap2Prepare] = []
    detail: list[SkillCheck] = []
    na: list[str] = []
    b: dict[str, float] = {}

    # ---------------- habilidades obligatorias técnicas + idiomas requeridos
    must = [s for s in v.must_have if not _is_soft(s)]
    got = 0.0
    for sk in must:
        required = v.skill_levels.get(sk)
        if sk.lower() not in skills:
            detail.append(SkillCheck(name=sk, status="falta", required_level=required))
            gaps.append(Gap2Prepare(kind="habilidad", item=sk, required=required,
                                    message=f"Piden {sk}{f' {LEVEL_NAME[required]}' if required else ''} y no lo "
                                            "tienes en tu perfil: es lo primero que conviene aprender o repasar"))
            continue
        have = levels.get(sk.lower())
        check = SkillCheck(name=sk, status="ok", required_level=required, demonstrated=sk.lower() in shown,
                           have_level=have.value if have else None)
        credit = 1.0  # lo declarado es verdad
        if required and have is None:
            check.status = "nivel_por_confirmar"
            gaps.append(Gap2Prepare(kind="nivel_habilidad", item=sk, required=required,
                                    message=f"Piden {sk} {LEVEL_NAME[required]}: confirma tu nivel y prepárate para "
                                            "demostrarlo en una prueba técnica"))
        elif required and level_rank(have) < level_rank(required):
            dist = level_rank(required) - level_rank(have)
            credit = SKILL_LEVEL_CREDIT.get(dist, 0.5)
            check.status = "nivel_menor"
            gaps.append(Gap2Prepare(kind="nivel_habilidad", item=sk, required=required, have=have.value,
                                    message=f"Piden {sk} {LEVEL_NAME[required]} y tienes {LEVEL_NAME[have.value]}: "
                                            "refuerza ese nivel antes de la entrevista"))
        detail.append(check)
        got += credit

    langs = {lang.name: lang for lang in profile.languages}
    pending_langs: list[str] = []
    for name, required in v.languages.items():
        lang = langs.get(name)
        label = f"{name} {required}"
        if lang is None:
            gaps.append(Gap2Prepare(kind="idioma", item=name, required=required,
                                    message=f"Piden {label} y no registraste ese idioma"))
            continue
        cefr = effective_cefr(lang)
        if cefr is None:
            got += 0.5
            pending_langs.append(label)
            gaps.append(Gap2Prepare(kind="idioma", item=name, required=required,
                                    message=f"Piden {label}: confirma tu nivel en tu perfil"))
            continue
        dist = max(0, cefr_rank(required) - cefr_rank(cefr))
        got += LANG_CREDIT_BY_DISTANCE.get(dist, 0.0)
        if dist == 0:
            reasons.append(f"Cumples el idioma requerido: {label}")
        else:
            gaps.append(Gap2Prepare(kind="idioma", item=name, required=required, have=_lang_label(lang),
                                    message=f"Piden {label} y tienes {_lang_label(lang)}: practica conversación y "
                                            "vocabulario técnico en ese idioma"))
    total_req = len(must) + len(v.languages)
    b["skills_obligatorias"] = WEIGHTS["skills_obligatorias"] * (got / total_req if total_req else 1.0)
    have_must = [d.name for d in detail if d.status != "falta"]
    if must:
        reasons.insert(0, f"Tienes {len(have_must)} de {len(must)} habilidades obligatorias"
                       + (f" ({', '.join(have_must)})" if have_must else ""))

    # ---------------- deseables y transversales (si la vacante no las pide: "no aplica", sin penalizar)
    nice = [s for s in v.nice_to_have if not _is_soft(s)]
    if nice:
        have_nice = [s for s in nice if s.lower() in skills]
        b["skills_deseables"] = WEIGHTS["skills_deseables"] * len(have_nice) / len(nice)
        if have_nice:
            reasons.append(f"Suma puntos: {', '.join(have_nice)}")
    else:
        b["skills_deseables"] = WEIGHTS["skills_deseables"]
        na.append("skills_deseables")
    soft = [s for s in [*v.must_have, *v.nice_to_have] if _is_soft(s)]
    if soft:
        have_soft = [s for s in soft if s.lower() in skills]
        b["transversales"] = WEIGHTS["transversales"] * len(have_soft) / len(soft)
        if have_soft:
            reasons.append(f"Habilidades transversales que valoran: {', '.join(have_soft)}")
        for s in soft:
            if s.lower() not in skills:
                gaps.append(Gap2Prepare(kind="habilidad", item=s,
                                        message=f"Valoran {s}: prepara un ejemplo concreto de cómo la aplicas"))
    else:
        b["transversales"] = WEIGHTS["transversales"]
        na.append("transversales")

    # ---------------- cargo
    best = role_match(profile, v)
    b["rol"] = WEIGHTS["rol"] * best
    if best >= 0.5:
        reasons.append("El cargo coincide con lo que buscas")

    # ---------------- nivel de experiencia (nunca descarta)
    if profile.first_job:
        idx = SENIORITY_ORDER.index(v.seniority)
        factor = 1.0 if v.seniority in (Seniority.PRACTICANTE, Seniority.JUNIOR) else 0.4 if idx == 2 else 0.1
        if factor == 1.0:
            reasons.append("Vacante adecuada para primer empleo")
        else:
            gaps.append(Gap2Prepare(kind="experiencia", item="Nivel", required=v.seniority.value, have="primer empleo",
                                    message=f"Buscan nivel {v.seniority.value}: destaca tus proyectos y prácticas "
                                            "para compensar la experiencia"))
    elif profile.seniority:
        diff = SENIORITY_ORDER.index(v.seniority) - SENIORITY_ORDER.index(profile.seniority)
        factor = 1.0 if diff == 0 else 0.5 if abs(diff) == 1 else 0.15
        if diff == 0:
            reasons.append(f"Nivel {v.seniority.value} acorde a tu experiencia")
        elif diff > 0:
            gaps.append(Gap2Prepare(kind="experiencia", item="Nivel", required=v.seniority.value,
                                    have=profile.seniority.value,
                                    message=f"Buscan nivel {v.seniority.value} y tu experiencia es "
                                            f"{profile.seniority.value}: prepara logros concretos que muestren "
                                            "responsabilidades de ese nivel"))
    else:
        factor = 0.5
    b["seniority"] = WEIGHTS["seniority"] * factor

    # ---------------- educación (nunca descarta)
    if v.min_education:
        rank, in_progress, have_level = candidate_education(profile)
        req = education_rank(v.min_education)
        if rank < 0:
            factor = 0.5
            gaps.append(Gap2Prepare(kind="educacion", item="Nivel educativo", required=v.min_education,
                                    message=f"Piden mínimo {v.min_education}: registra tu formación en tu perfil"))
        elif rank >= req and not (rank == req and in_progress):
            factor = 1.0
            reasons.append(f"Cumples la formación mínima ({v.min_education})")
        elif rank == req and in_progress:
            factor = 0.75
            gaps.append(Gap2Prepare(kind="educacion", item="Nivel educativo", required=v.min_education,
                                    have=f"{have_level} en curso",
                                    message=f"Piden {v.min_education} y lo estás cursando: menciona tu avance "
                                            "y fecha estimada de grado"))
        else:
            factor = 0.5 if req - rank == 1 else 0.2
            gaps.append(Gap2Prepare(kind="educacion", item="Nivel educativo", required=v.min_education,
                                    have=have_level,
                                    message=f"Piden {v.min_education} y tu nivel es {have_level}: resalta cursos, "
                                            "certificaciones y experiencia equivalente"))
    else:
        factor = 1.0
        na.append("educacion")
    b["educacion"] = WEIGHTS["educacion"] * factor

    # ---------------- salario, modalidad, sector
    sal_min = profile.expectations.salary_min_cop
    if sal_min and v.salary_max_cop:
        factor = 1.0 if v.salary_max_cop >= sal_min else 0.4
        if factor == 1.0:
            reasons.append(f"Salario hasta {format_cop(v.salary_max_cop)} cubre tu aspiración")
    else:
        factor = 0.5
    b["salario"] = WEIGHTS["salario"] * factor

    pref = profile.expectations.modality
    if pref is None:
        factor = 0.5
    elif pref == v.modality:
        factor = 1.0
        reasons.append(f"Modalidad {v.modality.value}, como prefieres")
    elif v.modality == Modality.HIBRIDO or pref == Modality.HIBRIDO:
        factor = 0.6
    else:
        factor = 0.3
    b["modalidad"] = WEIGHTS["modalidad"] * factor

    sectors = profile.expectations.sectors
    if not sectors:
        factor = 0.5
    elif v.sector in sectors:
        factor = 1.0
        reasons.append(f"Sector {v.sector}, de tu interés")
    else:
        factor = 0.0
    b["sector"] = WEIGHTS["sector"] * factor

    # ---------------- viajes (informativo: no cambia el puntaje)
    if v.requires_travel and profile.expectations.willing_to_travel is False:
        gaps.append(Gap2Prepare(kind="viaje", item="Viajes", required="sí", have="no",
                                message="La vacante requiere viajar y marcaste que no: confírmalo con la empresa"))

    total = round(sum(b.values()), 1)
    return MatchResult(vacancy=v, score=total, breakdown={k: round(x, 1) for k, x in b.items()},
                       reasons=reasons, missing_skills=[d.name for d in detail if d.status == "falta"],
                       pending_languages=pending_langs, skills_detail=detail, gaps=gaps, not_applicable=na)


def rank(profile: Profile, vacancies: list[Vacancy], threshold: float, limit: int
         ) -> tuple[list[MatchResult], list[Discard]]:
    matches: list[MatchResult] = []
    discards: list[Discard] = []
    for v in vacancies:
        reason = hard_filter(profile, v)
        if reason:
            discards.append(Discard(vacancy_id=v.id, title=v.title, reason=reason))
            continue
        m = score_vacancy(profile, v)
        if m.score < threshold:
            top = "; ".join(g.item for g in m.gaps[:3]) or "poca coincidencia"
            discards.append(Discard(vacancy_id=v.id, title=v.title,
                                    reason=f"Puntaje {m.score} < {threshold}. Brechas principales: {top}"))
            continue
        matches.append(m)
    # Desempate por timing: a igual puntaje, primero la vacante más reciente
    matches.sort(key=lambda m: m.vacancy.posted_at or "", reverse=True)
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit], discards

