"""Entidades del dominio (sin dependencias de infraestructura)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class Modality(StrEnum):
    PRESENCIAL = "presencial"
    REMOTO = "remoto"
    HIBRIDO = "hibrido"


class Seniority(StrEnum):
    PRACTICANTE = "practicante"
    JUNIOR = "junior"
    SEMI_SENIOR = "semi-senior"
    SENIOR = "senior"


SENIORITY_ORDER = [Seniority.PRACTICANTE, Seniority.JUNIOR, Seniority.SEMI_SENIOR, Seniority.SENIOR]


class ApplicationStatus(StrEnum):
    POSTULADO = "postulado"
    EN_REVISION = "en_revision"
    ENTREVISTA = "entrevista"
    DESCARTADO = "descartado"


class LanguageLevel(StrEnum):
    BASICO = "basico"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"
    NATIVO = "nativo"


class SkillKind(StrEnum):
    HERRAMIENTA = "herramienta"  # herramientas y tecnologías
    CONOCIMIENTO = "conocimiento"  # conocimientos técnicos
    TRANSVERSAL = "transversal"  # habilidades blandas


class SkillLevel(StrEnum):
    BASICO = "basico"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


SKILL_LEVEL_ORDER = [SkillLevel.BASICO, SkillLevel.INTERMEDIO, SkillLevel.AVANZADO]


# ---------------------------------------------------------------- Hoja de vida
class Skill(BaseModel):
    name: str
    kind: SkillKind = SkillKind.HERRAMIENTA
    level: SkillLevel | None = None  # solo herramientas y conocimientos; opcional
    suggested: bool = False  # nivel/tipo sugerido por la IA, pendiente de confirmar
    evidence: str | None = None

    @model_validator(mode="after")
    def _no_level_for_soft(self):
        if self.kind == SkillKind.TRANSVERSAL:
            self.level = None  # las transversales no tienen nivel
        return self


_CEFR_LEVEL = {"A1": "basico", "A2": "basico", "B1": "intermedio", "B2": "intermedio", "C1": "avanzado",
               "C2": "avanzado"}


class Language(BaseModel):
    """Nivel con la escala internacional MCER (A1..C2) o Nativo. `level` (básico/intermedio/avanzado/nativo)
    se deriva del MCER y se usa para mostrar y comparar."""
    name: str
    level: LanguageLevel | None = None  # None = pendiente de confirmar
    cefr: str | None = None  # A1..C2
    suggested: bool = False  # True = nivel sugerido por el agente, falta que el candidato lo confirme
    evidence: str | None = None  # por qué se sugirió (certificado, texto del CV...)

    @model_validator(mode="after")
    def _sync_level(self):
        if self.level == LanguageLevel.NATIVO:
            self.cefr = None
        elif self.cefr:
            self.cefr = self.cefr.upper()
            if self.cefr in _CEFR_LEVEL:
                self.level = LanguageLevel(_CEFR_LEVEL[self.cefr])
            else:
                self.cefr = None
        return self


class Experience(BaseModel):
    title: str
    company: str | None = None
    city: str | None = None
    start: str | None = None
    end: str | None = None
    current: bool = False
    description: str | None = None


class Education(BaseModel):
    degree: str
    institution: str | None = None
    level: str | None = None  # bachiller, técnico, tecnólogo, profesional, especialización, maestría, doctorado
    year: str | None = None
    status: str | None = None  # finalizado | en_curso
    semester: int | None = None


class Certification(BaseModel):
    name: str
    issuer: str | None = None
    year: str | None = None


class Project(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    role: str | None = None  # individual | equipo
    url: str | None = None
    evidence: str = "declarado"  # declarado | descrito | con_enlace | verificado
    specificity: int | None = None  # 0-3 (lo evalúa la IA)
    verified_languages: list[str] = Field(default_factory=list)
    note: str | None = None


# ---------------------------------------------------------------- Fuera del CV
class Expectations(BaseModel):
    """Lo que el candidato BUSCA. Nunca viene del CV: se pregunta en "¿Qué estás buscando?"."""
    desired_roles: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    city: str | None = None
    modality: Modality | None = None
    workday: list[str] = Field(default_factory=list)  # jornada: tiempo completo, medio tiempo...
    contract_types: list[str] = Field(default_factory=list)  # "disponible para"
    salary_min_cop: int | None = None
    salary_frequency: str = "mensual"
    availability: str | None = None  # cuándo puede empezar
    willing_to_travel: bool | None = None
    willing_to_relocate: bool | None = None


class Sensitive(BaseModel):
    """Datos sensibles OPCIONALES (Ley 1581 de 2012). Nunca se usan para el puntaje de match."""
    consent: bool = False
    sex: str | None = None
    birth_date: str | None = None
    disability: bool | None = None
    disability_type: str | None = None


class Profile(BaseModel):
    # Identidad y contacto
    full_name: str | None = None
    first_names: str | None = None
    last_names: str | None = None
    document_type: str | None = None  # se pide al postular
    document_id: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    department: str | None = None
    country: str = "Colombia"
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    # Perfil profesional
    headline: str | None = None
    summary: str | None = None
    profession: str | None = None
    years_experience: float | None = None
    seniority: Seniority | None = None
    skills: list[Skill] = Field(default_factory=list)
    demonstrated_skills: list[str] = Field(default_factory=list)  # nombres respaldados por experiencia/proyectos
    languages: list[Language] = Field(default_factory=list)
    # Trayectoria
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    # Fuera del CV
    expectations: Expectations = Field(default_factory=Expectations)
    sensitive: Sensitive = Field(default_factory=Sensitive)
    # Metadatos del agente
    first_job: bool = False
    suggestions: dict[str, list[str]] = Field(default_factory=dict)  # roles/sectores sugeridos por la IA
    provenance: dict[str, str] = Field(default_factory=dict)  # campo -> reglas | ia | usuario
    edited_fields: list[str] = Field(default_factory=list)  # protegidos ante un CV nuevo

    @field_validator("skills", mode="before")
    @classmethod
    def _legacy_skills(cls, v):
        # Compatibilidad: antes las habilidades eran texto plano
        if isinstance(v, list) and any(isinstance(x, str) for x in v):
            from app.domain.skillset import make_skill

            return [make_skill(x) if isinstance(x, str) else x for x in v]
        return v

    @property
    def skill_names(self) -> list[str]:
        return [s.name for s in self.skills]

    @property
    def technical_skills(self) -> list[Skill]:
        return [s for s in self.skills if s.kind != SkillKind.TRANSVERSAL]

    @field_validator("languages", mode="before")
    @classmethod
    def _legacy_languages(cls, v):
        # Compatibilidad: versiones anteriores guardaban idiomas como texto ("Inglés B2")
        if isinstance(v, list) and v and isinstance(v[0], str):
            from app.domain.languages import parse_language

            return [lang for lang in (parse_language(s) for s in v) if lang]
        return v


class Gap(BaseModel):
    field: str
    label: str
    question: str
    input_type: str  # text | number | select | multiselect | tags | boolean | languages | projects | info
    options: list[str] = Field(default_factory=list)
    critical: bool = False
    group: str = "cv"  # cv | preferences | identity
    items: list[dict] = Field(default_factory=list)  # para tarjetas de lista (idiomas, proyectos)


# ---------------------------------------------------------------- Vacantes
class Vacancy(BaseModel):
    id: str
    title: str
    company: str
    city: str | None
    modality: Modality
    salary_min_cop: int | None
    salary_max_cop: int | None
    seniority: Seniority
    must_have: list[str]
    nice_to_have: list[str] = Field(default_factory=list)
    languages: dict[str, str] = Field(default_factory=dict)  # {"Inglés": "B2"}
    skill_levels: dict[str, str] = Field(default_factory=dict)  # {"Excel": "avanzado"}
    sector: str | None = None
    workday: str = "Tiempo completo"
    contract: str = "Empleo (contrato laboral)"
    min_education: str | None = None  # bachiller, técnico, tecnólogo, profesional, especialización...
    requires_travel: bool = False
    description: str = ""
    posted_at: str | None = None
    source: str = "dataset"


class Gap2Prepare(BaseModel):
    """Brecha entre el candidato y la vacante. No descarta: el Agente de Seguimiento la convierte en un
    plan de preparación."""
    kind: str  # habilidad | nivel_habilidad | idioma | educacion | experiencia | viaje
    item: str
    required: str | None = None
    have: str | None = None
    message: str


class SkillCheck(BaseModel):
    name: str
    status: str  # ok | falta | nivel_menor | nivel_por_confirmar
    required_level: str | None = None
    have_level: str | None = None
    demonstrated: bool = False  # solo informativo: no cambia el puntaje


class MatchResult(BaseModel):
    vacancy: Vacancy
    score: float
    breakdown: dict[str, float]
    reasons: list[str]
    missing_skills: list[str] = Field(default_factory=list)
    pending_languages: list[str] = Field(default_factory=list)
    skills_detail: list[SkillCheck] = Field(default_factory=list)
    gaps: list[Gap2Prepare] = Field(default_factory=list)
    not_applicable: list[str] = Field(default_factory=list)  # componentes que la vacante no pide


class Discard(BaseModel):
    vacancy_id: str
    title: str
    reason: str
