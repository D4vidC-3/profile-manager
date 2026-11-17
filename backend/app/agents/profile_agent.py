"""Agente de Perfil (híbrido): estructura la hoja de vida y detecta vacíos.

1. Reglas: datos exactos (email, teléfono, LinkedIn/GitHub), secciones, fechas, skills e idiomas.
2. IA: lo semántico (experiencia, educación, proyectos, nombres/apellidos, sugerencias de nivel de idioma).
3. Fusión: los datos exactos de reglas tienen prioridad; la IA completa y estructura.
4. Evidencia: verifica repositorios de GitHub y marca skills "demostradas" por experiencia o proyectos.
5. Reglas: completitud del CV (tabla "experiencia" o "primer empleo") y vacíos. Siempre determinista.

Una hoja de vida NO trae expectativas: la IA solo puede SUGERIR cargos/sectores para pre-llenar el
formulario "¿Qué estás buscando?", que el candidato confirma.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.agents.tracing import Tracer
from app.domain.colombia import (
    SECTORS,
    department_for,
    normalize_city,
    normalize_seniority,
    seniority_from_years,
)
from app.domain.completeness import (
    cv_completeness,
    demonstrated_skills,
    detect_cv_gaps,
    is_first_job,
    project_evidence,
)
from app.domain.languages import LEVEL_TO_CEFR, language_name, suggest_spanish_native
from app.domain.models import (
    Certification,
    Education,
    Experience,
    Gap,
    Language,
    LanguageLevel,
    Profile,
    Project,
    Seniority,
    SkillKind,
    SkillLevel,
)
from app.domain.skills import normalize_skills, strip_accents
from app.domain.skillset import merge_skills
from app.infrastructure.cv.extractor import parse_cv_rules, split_full_name, valid_skill
from app.infrastructure.github import verify_project
from app.infrastructure.llm.provider import LLMChain


# ---------------------------------------------------------------- salida estructurada de la IA
class AILanguage(BaseModel):
    name: str
    level: str | None = Field(None, description="basico, intermedio, avanzado o nativo. Vacío si el CV no lo dice")
    cefr: str | None = Field(None, description="A1..C2 solo si el CV lo indica o hay un certificado")
    evidence: str | None = Field(None, description="Frase del CV que justifica el nivel. Vacío si no hay evidencia")


class AISkill(BaseModel):
    name: str
    kind: str | None = Field(None, description="herramienta (software/tecnología), conocimiento (técnico) "
                                               "o transversal (habilidad blanda)")
    level: str | None = Field(None, description="basico, intermedio o avanzado SOLO si el CV lo dice; nunca "
                                                "para transversales")
    evidence: str | None = Field(None, description="Frase del CV que justifica el nivel")


class AIExperience(BaseModel):
    title: str
    company: str | None = None
    city: str | None = None
    start: str | None = Field(None, description="Fecha de inicio tal como aparece, ej. 'Enero 2024'")
    end: str | None = Field(None, description="Fecha de fin o 'Actual'")
    current: bool = False
    description: str | None = None


class AIEducation(BaseModel):
    degree: str
    institution: str | None = None
    level: str | None = Field(None, description="bachiller, técnico, tecnólogo, profesional, especialización, "
                                                "maestría o doctorado")
    year: str | None = None
    status: str | None = Field(None, description="finalizado o en_curso")
    semester: int | None = None


class AIProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    role: str | None = Field(None, description="individual o equipo")
    url: str | None = None
    specificity: int | None = Field(None, description="0-3: 0 genérico, 3 dice qué hizo, con qué y qué resultado")


class CVExtraction(BaseModel):
    """Esquema que la IA debe llenar. Solo información que ESTÁ en la hoja de vida."""
    full_name: str | None = None
    first_names: str | None = Field(None, description="Nombre(s) de pila")
    last_names: str | None = Field(None, description="Apellido(s); en Colombia suelen ser dos")
    headline: str | None = Field(None, description="Titular profesional corto, ej. 'Auxiliar de soporte TI'")
    summary: str | None = Field(None, description="Resumen profesional de 2-3 frases en español")
    profession: str | None = Field(None, description="Profesión u oficio según su título, ej. 'Estadística'")
    city: str | None = None
    years_experience: float | None = Field(None, description="Años de experiencia LABORAL (no estudios)")
    seniority: str | None = Field(None, description="practicante, junior, semi-senior o senior")
    skills: list[AISkill] = Field(default_factory=list)
    languages: list[AILanguage] = Field(default_factory=list)
    experiences: list[AIExperience] = Field(default_factory=list)
    education: list[AIEducation] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    projects: list[AIProject] = Field(default_factory=list)
    suggested_roles: list[str] = Field(default_factory=list,
                                       description="Hasta 3 cargos a los que podría aspirar según su trayectoria")
    suggested_sectors: list[str] = Field(default_factory=list, description="Hasta 2 sectores de la lista dada")


SYSTEM_PROMPT = (
    "Eres el Agente de Perfil de una plataforma de empleo colombiana. Extrae SOLO información que esté en la "
    "hoja de vida; si algo no aparece, déjalo vacío. Ignora textos como 'No especificado' o 'pendiente'. "
    "Una hoja de vida no contiene expectativas salariales ni preferencias: no las extraigas. "
    "Idiomas: pon nivel solo si el CV lo dice o si hay evidencia clara (certificado, haber vivido o trabajado "
    "en ese idioma) y escribe esa evidencia; si no hay, deja el nivel vacío. "
    "Habilidades: clasifícalas en herramienta, conocimiento o transversal; nivel solo si el CV lo dice. "
    "Proyectos: solo los que estén en el CV (académicos o personales); califica 'specificity' de 0 a 3. "
    "Para 'suggested_sectors' usa únicamente estos valores: " + "; ".join(SECTORS) + ". Responde en español."
)
_SPANISH_HINTS = re.compile(r"\b(de|la|el|en|y|con|para|experiencia|educacion|habilidades)\b")


def _cv_in_spanish(text: str) -> bool:
    return len(_SPANISH_HINTS.findall(strip_accents(text).lower())) >= 15


def _merge(rules: Profile, ai: CVExtraction | None) -> tuple[Profile, list[str]]:
    """Fusiona reglas + IA. Devuelve el perfil y qué campos aportó la IA."""
    if ai is None:
        return rules, []
    p = rules.model_copy(deep=True)
    from_ai: list[str] = []

    def mark(name: str) -> None:
        from_ai.append(name)
        p.provenance[name] = "ia"

    if ai.full_name and not p.full_name:
        p.full_name = ai.full_name
        mark("full_name")
    # La IA puede "limpiar" un nombre mal cortado por reglas, pero no reemplazarlo por otro
    elif ai.full_name and p.full_name and ai.full_name != p.full_name:
        if set(ai.full_name.lower().split()) < set(p.full_name.lower().split()):
            p.full_name = ai.full_name
            mark("full_name")
    if ai.first_names and ai.last_names and p.full_name:
        tokens = set(f"{ai.first_names} {ai.last_names}".lower().split())
        if tokens <= set(p.full_name.lower().split()):
            p.first_names, p.last_names = ai.first_names, ai.last_names
            mark("first_names")
    if ai.headline:
        if ai.headline != p.headline:
            mark("headline")
        p.headline = ai.headline[:150]
    for attr in ("summary", "profession"):
        if getattr(ai, attr) and not getattr(p, attr):
            setattr(p, attr, getattr(ai, attr))
            mark(attr)
    if ai.city and not p.city:
        p.city = normalize_city(ai.city)
        p.department = department_for(p.city)
        mark("city")
    if ai.experiences and len(ai.experiences) >= len(p.experiences):
        p.experiences = [Experience(**e.model_dump()) for e in ai.experiences
                         if e.title and "no especific" not in e.title.lower()]
        mark("experiences")
    if ai.education and len(ai.education) >= len(p.education):
        p.education = [Education(**e.model_dump()) for e in ai.education]
        mark("education")
    if ai.certifications and len(ai.certifications) > len(p.certifications):
        p.certifications = ai.certifications
        mark("certifications")
    # Proyectos: se enriquecen los de reglas o se toman los de la IA
    if ai.projects:
        by_name = {pr.name.lower(): pr for pr in p.projects}
        merged: list[Project] = []
        for ap in ai.projects:
            base = by_name.get(ap.name.lower())
            pr = base.model_copy() if base else Project(name=ap.name)
            pr.description = pr.description or ap.description
            pr.technologies = normalize_skills(pr.technologies + ap.technologies)
            pr.role = pr.role or (ap.role if ap.role in ("individual", "equipo") else None)
            pr.url = pr.url or ap.url
            pr.specificity = ap.specificity
            pr.evidence = project_evidence(pr)
            merged.append(pr)
        p.projects = merged or p.projects
        mark("projects")
    if ai.years_experience is not None and p.experiences:
        p.years_experience = ai.years_experience
    sen = normalize_seniority(ai.seniority) or seniority_from_years(p.years_experience)
    if sen:
        p.seniority = sen
    ai_skills = []
    for a in ai.skills:
        sk = valid_skill(a.name, a.kind)
        if sk is None:
            continue
        if a.level and a.evidence and sk.kind != SkillKind.TRANSVERSAL and sk.level is None:
            sk.level = SkillLevel(a.level) if a.level in SkillLevel._value2member_map_ else None
            sk.suggested, sk.evidence = sk.level is not None, a.evidence
        ai_skills.append(sk)
    new_skills = merge_skills(p.skills, ai_skills)
    if len(new_skills) > len(p.skills):
        mark("skills")
    p.skills = new_skills[:40]
    # Idiomas: la IA solo propone nivel con evidencia y queda como "sugerido"
    langs = {lang.name: lang for lang in p.languages}
    for al in ai.languages:
        name = language_name(al.name) or al.name.strip().title()
        level = al.level if al.level in LanguageLevel._value2member_map_ else None
        cefr = (al.cefr or "").upper() or (LEVEL_TO_CEFR[LanguageLevel(level)] if level and level != "nativo" else None)
        has = bool((level or cefr) and al.evidence)  # sin evidencia no hay nivel
        cur = langs.get(name)
        if cur is None:
            langs[name] = Language(name=name, level=LanguageLevel.NATIVO if has and level == "nativo" else None,
                                   cefr=cefr if has else None, suggested=has, evidence=al.evidence if has else None)
        elif cur.level is None and has:
            cur.level = LanguageLevel.NATIVO if level == "nativo" else None
            cur.cefr, cur.suggested, cur.evidence = cefr if level != "nativo" else None, True, al.evidence
            langs[name] = Language(**cur.model_dump())  # re-valida para derivar el nivel desde el MCER
    if list(langs.values()) != p.languages:
        p.languages = list(langs.values())
        mark("languages")
    p.suggestions = {"roles": ai.suggested_roles[:3], "sectors": [s for s in ai.suggested_sectors if s in SECTORS][:2]}
    return p, from_ai


# Datos que no vienen en un CV y se conservan solo si el CV nuevo es de la MISMA persona
SAME_PERSON_KEEP = ("sensitive", "document_type", "document_id")


def same_person(new: Profile, previous: Profile) -> bool:
    """Mismo correo, o mismo nombre completo si alguno de los dos CV no trae correo."""
    if new.email and previous.email:
        return new.email.lower() == previous.email.lower()
    if new.full_name and previous.full_name:
        return set(new.full_name.lower().split()) == set(previous.full_name.lower().split())
    return False


def apply_locked(new: Profile, previous: Profile | None) -> tuple[Profile, list[str]]:
    """CV nuevo de la misma persona: se conserva lo que editó a mano y su identidad. CV de otra persona:
    perfil desde cero. Las preferencias ("Lo que buscas") NUNCA se copian: se vuelven a preguntar."""
    if previous is None or not same_person(new, previous):
        return new, []
    p = new.model_copy(deep=True)
    kept: list[str] = []
    for field in [*previous.edited_fields, *SAME_PERSON_KEEP]:
        root = field.split(".")[0]
        if root == "expectations":
            continue
        value = getattr(previous, root, None)
        if value not in (None, "", [], {}) and hasattr(p, root):
            setattr(p, root, value)
            if root in previous.edited_fields:
                p.provenance[root] = "usuario"
                kept.append(root)
    p.edited_fields = [f for f in previous.edited_fields if f != "expectations"]
    return p, kept


class ProfileAgent:
    name = "perfil"

    def __init__(self, llm: LLMChain):
        self.llm = llm

    def run(self, cv_text: str, tracer: Tracer, previous: Profile | None = None
            ) -> tuple[Profile, float, list[Gap]]:
        rules_profile = parse_cv_rules(cv_text)
        exact = [f for f in ("email", "phone", "linkedin", "github", "city") if getattr(rules_profile, f)]
        tracer.log(self.name, "Extrajo datos exactos con reglas",
                   f"Encontró: {', '.join(exact) or 'ningún dato de contacto'}; {len(rules_profile.skills)} skills, "
                   f"{len(rules_profile.experiences)} experiencias, {len(rules_profile.education)} estudios, "
                   f"{len(rules_profile.languages)} idiomas, {len(rules_profile.projects)} proyectos. Textos como "
                   "'No especificado' y secciones que no son de una hoja de vida (preferencias) se ignoran.",
                   mode="rules", details={"fields": exact, "skills": rules_profile.skill_names})

        ai, meta = self.llm.invoke_structured(CVExtraction, SYSTEM_PROMPT, f"Hoja de vida:\n\n{cv_text[:12000]}")
        profile, from_ai = _merge(rules_profile, ai)
        if ai is not None:
            tracer.log(self.name, "Estructuró el CV con IA",
                       f"La IA completó: {', '.join(from_ai) or 'nada nuevo'}. Los datos exactos de reglas se "
                       "conservaron. Cargos y sectores sugeridos solo pre-llenan el formulario de preferencias.",
                       mode="llm", provider=meta.provider, duration_ms=meta.duration_ms,
                       details={"fields_from_ai": from_ai, "suggestions": profile.suggestions,
                                "fallback_errors": meta.errors})
        else:
            tracer.log(self.name, "Continuó solo con reglas",
                       "Ningún proveedor de IA disponible (sin API key, sin cuota o sin red). Se usa el resultado de "
                       "reglas; se preguntará más al candidato.",
                       mode="rules", details={"fallback_errors": meta.errors})

        if not profile.first_names and profile.full_name:
            profile.first_names, profile.last_names = split_full_name(profile.full_name)
        profile.languages = suggest_spanish_native(profile.languages, _cv_in_spanish(cv_text))
        sugg = [f"{lang.name}: {lang.evidence}" for lang in profile.languages if lang.suggested]
        pending = [lang.name for lang in profile.languages if lang.level is None]
        if sugg or pending:
            tracer.log(self.name, "Revisó niveles de idioma",
                       ("Sugerencias (el candidato debe confirmarlas): " + "; ".join(sugg) + ". " if sugg else "")
                       + (f"Sin nivel en el CV: {', '.join(pending)}. Se le pedirá confirmarlo." if pending else ""),
                       details={"suggested": sugg, "pending": pending})

        # Evidencia de proyectos (GitHub público)
        checked = []
        for i, pr in enumerate(profile.projects):
            if pr.url and "github.com" in pr.url:
                profile.projects[i] = verify_project(pr)
                checked.append(f"{pr.name}: {profile.projects[i].note or profile.projects[i].evidence}")
        if checked:
            tracer.log(self.name, f"Verificó {len(checked)} repositorio(s) en GitHub",
                       "Se consulta la API pública de GitHub: confirma que el repositorio existe y qué lenguajes "
                       "usa (no prueba autoría). " + " | ".join(checked), details={"projects": checked})

        profile, kept = apply_locked(profile, previous)
        if kept:
            tracer.log(self.name, f"Conservó {len(kept)} campo(s) editados por el candidato",
                       f"Campos protegidos: {', '.join(kept)}. Un CV nuevo no sobrescribe correcciones manuales.",
                       details={"kept": kept})

        profile.demonstrated_skills = demonstrated_skills(profile)
        profile.first_job, reason = is_first_job(profile)
        if profile.first_job and profile.seniority in (None, Seniority.SEMI_SENIOR, Seniority.SENIOR):
            profile.seniority = (Seniority.PRACTICANTE if any(e.status == "en_curso" for e in profile.education)
                                 else Seniority.JUNIOR)
        cv = cv_completeness(profile)
        gaps = detect_cv_gaps(profile)
        crit = [g.label for g in gaps if g.critical]
        tracer.log(self.name, f"Completitud de la hoja de vida: {cv.score}%",
                   f"Tabla de pesos '{cv.mode.replace('_', ' ')}' ({reason}). Bloquean: {', '.join(crit) or 'nada'}; "
                   f"sugerencias: {', '.join(g.label for g in gaps if not g.critical) or 'ninguna'}. "
                   f"Skills demostradas: {', '.join(profile.demonstrated_skills) or 'ninguna'}.",
                   details={"breakdown": cv.breakdown, "mode": cv.mode, "gaps": [g.field for g in gaps]})
        return profile, cv.score, gaps
