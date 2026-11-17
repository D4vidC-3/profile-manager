"""Reglas de completitud. Todo es determinista: explicable y sin gastar cuota de IA.

Se separan TRES cosas que antes estaban mezcladas:
  1. Completitud del CV        -> lo que debe tener una hoja de vida (lo lee el Agente de Perfil).
  2. Preferencias de búsqueda  -> lo que el candidato busca (formulario "¿Qué estás buscando?").
  3. Identidad para postular   -> documento y nombres/apellidos (se pide solo al postular).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.domain.colombia import (
    AVAILABILITY_OPTIONS,
    CONTRACT_TYPES,
    DISABILITY_TYPES,
    DOCUMENT_TYPES,
    SECTORS,
    SEX_OPTIONS,
    WORKDAYS,
    department_for,
    normalize_city,
    normalize_modality,
    parse_cop_amount,
)
from app.domain.languages import parse_language
from app.domain.models import (
    Expectations,
    Gap,
    Language,
    LanguageLevel,
    Profile,
    Project,
    Skill,
    SkillKind,
    SkillLevel,
)
from app.domain.skills import extract_skills_from_text, normalize_skill, normalize_skills
from app.domain.skillset import make_skill, merge_skills

# =================================================================== 1. CV
WEIGHTS_EXPERIENCED = {
    "full_name": 10, "email": 10, "phone": 10, "city": 5, "headline": 5, "summary": 5,
    "experience": 20, "projects": 0, "education": 15, "skills": 10,
    "languages": 5, "certifications": 3, "links": 2,
}
# Primer empleo: los 20 puntos de experiencia se reparten entre proyectos, educación y habilidades
WEIGHTS_FIRST_JOB = {**WEIGHTS_EXPERIENCED, "experience": 0, "projects": 8, "education": 22, "skills": 15}

LABELS = {
    "full_name": "Nombre completo", "email": "Correo electrónico", "phone": "Teléfono / celular",
    "city": "Ciudad de residencia", "headline": "Titular profesional", "summary": "Resumen profesional",
    "experience": "Experiencia laboral", "projects": "Proyectos, prácticas o voluntariado",
    "education": "Educación", "skills": "Habilidades", "languages": "Idiomas con nivel",
    "certifications": "Cursos y certificaciones", "links": "LinkedIn / portafolio / GitHub",
}
CRITICAL_CV = {"full_name", "email", "phone", "skills"}


@dataclass
class CVScore:
    score: float
    mode: str  # experiencia | primer_empleo
    reason: str
    breakdown: list[dict] = field(default_factory=list)


def is_first_job(p: Profile, today: date | None = None) -> tuple[bool, str]:
    """Primer empleo: sin experiencia laboral y (estudia, se graduó hace ≤1 año o busca práctica)."""
    if p.experiences:
        return False, "tiene experiencia laboral"
    year = (today or date.today()).year
    if any(e.status == "en_curso" for e in p.education):
        return True, "sin experiencia laboral y con estudios en curso"
    years = [int(e.year) for e in p.education if e.year and e.year.isdigit() and e.level != "bachiller"]
    if years and max(years) >= year - 1:
        return True, f"sin experiencia laboral y graduado en {max(years)}"
    if "Práctica / etapa productiva" in p.expectations.contract_types:
        return True, "sin experiencia laboral y busca práctica"
    return False, "sin experiencia laboral registrada"


def _skills_credit(p: Profile) -> float:
    """≥5 técnicas (herramientas + conocimientos) = completo; ≥3 = parcial. Las transversales suman un
    pequeño bonus pero solas no completan el bloque."""
    tech = len(p.technical_skills)
    soft = len(p.skills) - tech
    base = 1.0 if tech >= 5 else 0.6 if tech >= 3 else 0.15 * tech
    return min(1.0, base + 0.05 * min(soft, 4))


def _ratio(*flags: Any) -> float:
    return sum(1 for f in flags if f) / len(flags)


def _experience_credit(p: Profile) -> float:
    if not p.experiences:
        return 0.0
    return max(_ratio(e.title, e.company, e.start) for e in p.experiences)


def _education_credit(p: Profile) -> float:
    formal = [e for e in p.education if e.level != "curso"]
    if not formal:
        return 0.0
    return max(_ratio(e.degree, e.institution, e.year or e.status) for e in formal)


def project_credit(pr: Project) -> float:
    """Sobre 8: nombre+descripción 4, tecnologías 2, enlace 2 (evidencia, no "verdad")."""
    pts = 4 if (pr.name and pr.description) else 2 if pr.name else 0
    pts += 2 if pr.technologies else 0
    pts += 2 if pr.url else 0
    return pts / 8


def project_evidence(pr: Project) -> str:
    if pr.evidence == "verificado":
        return "verificado"
    if pr.url:
        return "con_enlace"
    if pr.description and pr.technologies:
        return "descrito"
    return "declarado"


def cv_completeness(p: Profile, today: date | None = None) -> CVScore:
    first, reason = is_first_job(p, today)
    weights = WEIGHTS_FIRST_JOB if first else WEIGHTS_EXPERIENCED
    langs = p.languages
    credit = {
        "full_name": 1.0 if p.full_name else 0.0,
        "email": 1.0 if p.email else 0.0,
        "phone": 1.0 if p.phone else 0.0,
        "city": 1.0 if p.city else 0.0,
        "headline": 1.0 if p.headline else 0.0,
        "summary": 1.0 if p.summary else 0.0,
        "experience": _experience_credit(p),
        "projects": max((project_credit(pr) for pr in p.projects), default=0.0),
        "education": _education_credit(p),
        "skills": _skills_credit(p),
        "languages": (sum(1 for lang in langs if lang.level) / len(langs)) if langs else 0.0,
        "certifications": 1.0 if p.certifications else 0.0,
        "links": 1.0 if (p.linkedin or p.github or p.portfolio) else 0.0,
    }
    breakdown = [{"key": k, "label": LABELS[k], "weight": w, "got": round(w * credit[k], 1)}
                 for k, w in weights.items() if w]
    score = round(sum(b["got"] for b in breakdown), 1)
    return CVScore(score=score, mode="primer_empleo" if first else "experiencia", reason=reason,
                   breakdown=breakdown)


def detect_cv_gaps(p: Profile, today: date | None = None) -> list[Gap]:
    """Vacíos de la hoja de vida. Solo los de contacto y ≥3 skills bloquean; lo demás son sugerencias."""
    first, _ = is_first_job(p, today)
    gaps: list[Gap] = []
    simple = {
        "full_name": ("¿Cuál es tu nombre completo?", "text"),
        "email": ("¿A qué correo te pueden contactar las empresas?", "text"),
        "phone": ("¿Cuál es tu número de celular? (ej. 300 123 4567)", "text"),
        "city": ("¿En qué ciudad vives?", "text"),
        "headline": ("¿Cómo te describirías en una línea? (ej. Auxiliar de soporte TI)", "text"),
        "summary": ("Escribe un resumen profesional de 2–3 líneas", "text"),
    }
    for key, (question, itype) in simple.items():
        if not getattr(p, key):
            gaps.append(Gap(field=key, label=LABELS[key], question=question, input_type=itype,
                            critical=key in CRITICAL_CV))
    tech = len(p.technical_skills)
    if tech < 5:
        gaps.append(Gap(field="skills", label=LABELS["skills"], input_type="skills", critical=tech < 3,
                        question="Agrega tus herramientas y conocimientos técnicos (mínimo 3, ideal 5 o más). "
                                 "Las habilidades blandas suman, pero no reemplazan a las técnicas.",
                        items=[sk.model_dump(mode="json") for sk in p.skills]))
    pending = [lang for lang in p.languages if lang.level is None or lang.suggested]
    if not p.languages or pending:
        gaps.append(Gap(field="languages", label=LABELS["languages"], input_type="languages",
                        question=("Encontramos estos idiomas en tu CV. Confirma tu nivel:" if p.languages
                                  else "¿Qué idiomas hablas? (Español ya cuenta)"),
                        items=[lang.model_dump(mode="json") for lang in p.languages]))
    if first and not p.projects:
        gaps.append(Gap(field="projects", label=LABELS["projects"], input_type="projects",
                        question="Aún no tienes experiencia laboral: cuéntanos un proyecto (académico o personal) "
                                 "para mostrar lo que sabes hacer"))
    if not first and not p.experiences:
        gaps.append(Gap(field="experience", label=LABELS["experience"], input_type="info",
                        question="No encontramos experiencia laboral. Agrégala desde 'Editar' o en tu CV."))
    no_level = skills_without_level(p)
    if no_level:
        gaps.append(Gap(field="skill_levels", label=f"Nivel de {len(no_level)} habilidad(es)", input_type="info",
                        question="Ponle nivel a tus herramientas y conocimientos: es necesario para postular."))
    if not p.education:
        gaps.append(Gap(field="education", label=LABELS["education"], input_type="info",
                        question="No encontramos tu formación académica. Agrégala desde 'Editar'."))
    return gaps


def critical_cv_gaps(p: Profile) -> list[Gap]:
    return [g for g in detect_cv_gaps(p) if g.critical]


# =================================================================== 2. Preferencias
PREF_FIELDS: list[tuple[str, str, float, bool]] = [
    # (campo, etiqueta, peso, obligatorio para recomendar)
    ("desired_roles", "Cargos deseados", 20, True),
    ("sectors", "Sectores laborales", 15, True),
    ("city", "Dónde quieres trabajar", 10, True),
    ("modality", "Modalidad", 15, True),
    ("workday", "Jornada", 10, True),
    ("salary_min_cop", "Salario mínimo aceptado", 15, True),
    ("contract_types", "Disponible para (tipo de vinculación)", 5, False),
    ("availability", "¿Cuándo puedes empezar?", 5, False),
    ("willing_to_travel", "Disponible para viajar", 2.5, False),
    ("willing_to_relocate", "Disponible para cambio de domicilio", 2.5, False),
]


def _filled(v: Any) -> bool:
    return v not in (None, "", [], {})


def preferences_completeness(p: Profile) -> float:
    e = p.expectations
    return round(sum(w for f, _, w, _ in PREF_FIELDS if _filled(getattr(e, f))), 1)


def missing_preferences(p: Profile, only_required: bool = True) -> list[str]:
    e = p.expectations
    return [f for f, _, _, req in PREF_FIELDS if (req or not only_required) and not _filled(getattr(e, f))]


def preferences_form(p: Profile, prefill: Expectations | None = None) -> dict:
    """Payload del paso "¿Qué estás buscando?": valores actuales (o las respuestas anteriores de la misma
    persona como pre-llenado) + sugerencias de la IA basadas en el CV actual."""
    e = p.expectations if not missing_preferences(p) or prefill is None else prefill
    return {
        "values": e.model_dump(mode="json") | {"city": e.city or p.city},
        "suggestions": p.suggestions,
        "required": [f for f, _, _, req in PREF_FIELDS if req],
        "missing": missing_preferences(p),
        "labels": {f: label for f, label, _, _ in PREF_FIELDS},
        "completeness": preferences_completeness(p),
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in re.split(r"[,;]", str(value or "")) if v.strip()]


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("si", "sí", "true", "1", "yes")


def apply_preferences(p: Profile, data: dict[str, Any]) -> tuple[Profile, list[str]]:
    """Aplica el formulario de preferencias. Solo valores de catálogo para listas cerradas."""
    p = p.model_copy(deep=True)
    e = p.expectations
    updated: list[str] = []

    def put(name: str, value: Any) -> None:
        if _filled(value) or isinstance(value, bool):
            setattr(e, name, value)
            updated.append(name)

    if "desired_roles" in data:
        put("desired_roles", [r[:80] for r in _as_list(data["desired_roles"])][:5])
    if "sectors" in data:
        put("sectors", [s for s in _as_list(data["sectors"]) if s in SECTORS][:5])
    if "city" in data and data["city"]:
        put("city", normalize_city(str(data["city"])[:80]))
    if "modality" in data and data["modality"]:
        put("modality", normalize_modality(str(data["modality"])))
    if "workday" in data:
        put("workday", [w for w in _as_list(data["workday"]) if w in WORKDAYS])
    if "contract_types" in data:
        put("contract_types", [c for c in _as_list(data["contract_types"]) if c in CONTRACT_TYPES])
    if data.get("salary_min_cop") not in (None, ""):
        raw = data["salary_min_cop"]
        put("salary_min_cop", raw if isinstance(raw, int) else parse_cop_amount(str(raw)))
    if data.get("salary_frequency") in ("mensual", "quincenal", "por hora", "por proyecto"):
        put("salary_frequency", data["salary_frequency"])
    if data.get("availability") in AVAILABILITY_OPTIONS:
        put("availability", data["availability"])
    for b in ("willing_to_travel", "willing_to_relocate"):
        if b in data and _as_bool(data[b]) is not None:
            put(b, _as_bool(data[b]))
    return p, updated


# =================================================================== Niveles de habilidades (al postular)
def skills_without_level(p: Profile) -> list[Skill]:
    """Herramientas y conocimientos sin nivel confirmado. Requisito para postular (las transversales no
    tienen nivel). Un nivel sugerido por la IA cuenta como pendiente hasta que el candidato lo confirme."""
    return [s for s in p.technical_skills if s.level is None or s.suggested]


def skill_levels_form(p: Profile) -> dict:
    return {"skills": [s.model_dump(mode="json") for s in skills_without_level(p)],
            "levels": [{"value": "basico", "label": "Básico"}, {"value": "intermedio", "label": "Intermedio"},
                       {"value": "avanzado", "label": "Avanzado"}]}


def apply_skill_levels(p: Profile, levels: dict[str, str]) -> tuple[Profile, list[str]]:
    p = p.model_copy(deep=True)
    wanted = {k.lower(): v for k, v in (levels or {}).items() if v in SkillLevel._value2member_map_}
    updated: list[str] = []
    for sk in p.skills:
        lv = wanted.get(sk.name.lower())
        if lv and sk.kind != SkillKind.TRANSVERSAL:
            sk.level, sk.suggested, sk.evidence = SkillLevel(lv), False, None
            updated.append(sk.name)
    if updated:
        p.provenance["skills"] = "usuario"
        if "skills" not in p.edited_fields:
            p.edited_fields.append("skills")
    return p, updated


# =================================================================== 3. Identidad (al postular)
IDENTITY_FIELDS = [
    ("first_names", "Nombre(s)", "text", []),
    ("last_names", "Apellido(s)", "text", []),
    ("document_type", "Tipo de documento", "select", DOCUMENT_TYPES),
    ("document_id", "Número de documento", "text", []),
    ("email", "Correo electrónico", "text", []),
    ("phone", "Teléfono / celular", "text", []),
]


def identity_gaps(p: Profile) -> list[Gap]:
    return [Gap(field=f, label=label, question=label, input_type=t, options=opts, critical=True, group="identity")
            for f, label, t, opts in IDENTITY_FIELDS if not getattr(p, f)]


def identity_form(p: Profile) -> dict:
    return {
        "values": {f: getattr(p, f) for f, *_ in IDENTITY_FIELDS},
        "missing": [g.field for g in identity_gaps(p)],
        "fields": [{"field": f, "label": label, "input_type": t, "options": o} for f, label, t, o in IDENTITY_FIELDS],
        "sensitive": {"sex_options": SEX_OPTIONS, "disability_types": DISABILITY_TYPES,
                      "values": p.sensitive.model_dump(mode="json")},
    }


def apply_identity(p: Profile, data: dict[str, Any]) -> tuple[Profile, list[str]]:
    p = p.model_copy(deep=True)
    updated: list[str] = []
    for f in ("first_names", "last_names"):
        if data.get(f):
            setattr(p, f, str(data[f]).strip()[:80])
            updated.append(f)
    if data.get("document_type") in DOCUMENT_TYPES:
        p.document_type = data["document_type"]
        updated.append("document_type")
    if data.get("document_id"):
        doc = re.sub(r"[^0-9A-Za-z]", "", str(data["document_id"]))
        if 5 <= len(doc) <= 15:
            p.document_id = doc
            updated.append("document_id")
    if data.get("email") and re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", str(data["email"]).strip()):
        p.email = str(data["email"]).strip().lower()
        updated.append("email")
    if data.get("phone") and len(re.sub(r"\D", "", str(data["phone"]))) >= 7:
        p.phone = re.sub(r"[^\d+]", "", str(data["phone"]))
        updated.append("phone")
    if p.first_names and p.last_names and "full_name" not in p.edited_fields:
        p.full_name = f"{p.first_names} {p.last_names}"
    sens = data.get("sensitive") or {}
    if sens.get("consent") is True:  # Ley 1581: solo con autorización expresa
        p.sensitive.consent = True
        if sens.get("sex") in SEX_OPTIONS:
            p.sensitive.sex = sens["sex"]
        if sens.get("birth_date") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(sens["birth_date"])):
            p.sensitive.birth_date = sens["birth_date"]
        if _as_bool(sens.get("disability")) is not None:
            p.sensitive.disability = _as_bool(sens["disability"])
            p.sensitive.disability_type = (sens.get("disability_type") if p.sensitive.disability
                                           and sens.get("disability_type") in DISABILITY_TYPES else None)
        updated.append("sensitive")
    elif sens.get("consent") is False:
        p.sensitive = type(p.sensitive)()  # retira la autorización: se borran
    return p, updated


# =================================================================== Respuestas a vacíos del CV
def _languages_from_answer(value: Any) -> list[Language]:
    out: list[Language] = []
    for item in value or []:
        if isinstance(item, str):
            lang = parse_language(item)
            if lang:
                out.append(lang)
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        level = item.get("level")
        cefr = str(item.get("cefr") or "").upper() or None
        out.append(Language(name=name[:40], cefr=cefr,
                            level=LanguageLevel.NATIVO if level == "nativo" else None if cefr
                            else LanguageLevel(level) if level in LanguageLevel._value2member_map_ else None))
    return out


def projects_from_answer(value: Any) -> list[Project]:
    out: list[Project] = []
    for item in value or []:
        if not isinstance(item, dict) or not str(item.get("name", "")).strip():
            continue
        pr = Project(name=str(item["name"]).strip()[:120],
                     description=(str(item.get("description") or "").strip()[:300] or None),
                     technologies=normalize_skills(_as_list(item.get("technologies")))[:15],
                     role=item.get("role") if item.get("role") in ("individual", "equipo") else None,
                     url=(str(item.get("url") or "").strip()[:200] or None),
                     evidence=item.get("evidence") if item.get("evidence") == "verificado" else "declarado",
                     specificity=item.get("specificity"),
                     verified_languages=item.get("verified_languages") or [])
        pr.evidence = project_evidence(pr)
        out.append(pr)
    return out[:10]


def apply_cv_answers(p: Profile, answers: dict[str, Any]) -> tuple[Profile, list[str]]:
    """Respuestas a vacíos del CV (lista blanca de campos)."""
    p = p.model_copy(deep=True)
    updated: list[str] = []
    for key in ("full_name", "headline", "summary"):
        if answers.get(key):
            setattr(p, key, str(answers[key]).strip()[:800 if key == "summary" else 150])
            updated.append(key)
    if answers.get("email") and re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", str(answers["email"]).strip()):
        p.email = str(answers["email"]).strip().lower()
        updated.append("email")
    if answers.get("phone") and len(re.sub(r"\D", "", str(answers["phone"]))) >= 7:
        p.phone = re.sub(r"[^\d+]", "", str(answers["phone"]))
        updated.append("phone")
    if answers.get("city"):
        p.city = normalize_city(str(answers["city"])[:80])
        p.department = department_for(p.city) or p.department
        updated.append("city")
    if answers.get("skills"):
        raw = answers["skills"]
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):  # lista completa editada por el candidato
            p.skills = user_skills(raw)
        else:
            p.skills = merge_skills(p.skills, [make_skill(x) for x in _as_list(raw)])[:40]
        updated.append("skills")
    if "languages" in answers:
        p.languages = _languages_from_answer(answers["languages"])
        updated.append("languages")
    if answers.get("projects"):
        p.projects = projects_from_answer(answers["projects"])
        updated.append("projects")
    for key in updated:
        p.provenance[key] = "usuario"
        if key not in p.edited_fields:
            p.edited_fields.append(key)  # lo que responde el candidato queda protegido ante un CV nuevo
    p.demonstrated_skills = demonstrated_skills(p)
    return p, updated


def user_skills(items: list[Any]) -> list[Skill]:
    """Habilidades editadas por el candidato. Las del catálogo conservan su tipo; las que no están en el
    catálogo toman el tipo de la sección donde el candidato las agregó."""
    out: dict[str, Skill] = {}
    for it in items[:40]:
        data = it.model_dump() if isinstance(it, Skill) else dict(it) if isinstance(it, dict) else {"name": str(it)}
        name = normalize_skill(str(data.get("name", "")).strip())[:60]
        if not name:
            continue
        kind = data.get("kind") if data.get("kind") in SkillKind._value2member_map_ else None
        sk = make_skill(name, kind)  # si está en el catálogo, su tipo es el del catálogo (no se puede mover)
        level = data.get("level")
        sk.level = (SkillLevel(level) if level in SkillLevel._value2member_map_ and sk.kind != SkillKind.TRANSVERSAL
                    else None)
        out.setdefault(name.lower(), sk)
    return list(out.values())


# =================================================================== Skills demostradas
def demonstrated_skills(p: Profile) -> list[str]:
    """Skills del candidato que aparecen respaldadas en su experiencia o en sus proyectos."""
    evidence_text = " ".join(f"{e.title} {e.description or ''}" for e in p.experiences)
    evidence_text += " " + " ".join(f"{pr.name} {pr.description or ''} {' '.join(pr.technologies)}"
                                    for pr in p.projects)
    backed = {s.lower() for s in extract_skills_from_text(evidence_text)}
    backed |= {t.lower() for pr in p.projects for t in pr.technologies}
    return [s.name for s in p.technical_skills if s.name.lower() in backed]


def career_change_skills(p: Profile, role_skills: list[str]) -> list[str]:
    """Skills que piden los cargos deseados y que la experiencia NO respalda (cambio de carrera)."""
    if not p.experiences or not role_skills:
        return []
    backed = {s.lower() for s in p.demonstrated_skills}
    return [s for s in role_skills if s.lower() not in backed]

