"""Contratos de la API (DTOs). Pydantic valida y limita todas las entradas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import Certification, Education, Expectations, Experience, Language, Project, Skill


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class FlowOut(BaseModel):
    stage: str
    pending: dict | None = None


class CvAnswersIn(BaseModel):
    """Respuestas a vacíos de la hoja de vida (contacto, skills, idiomas, proyectos)."""
    answers: dict[str, Any]

    @field_validator("answers")
    @classmethod
    def limit(cls, v: dict[str, Any]) -> dict[str, Any]:
        allowed = {"full_name", "email", "phone", "city", "headline", "summary", "skills", "languages", "projects"}
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(f"Campos no permitidos: {', '.join(sorted(unknown))}")
        for key, val in v.items():
            if isinstance(val, str) and len(val) > 800:
                raise ValueError(f"'{key}' es demasiado largo")
            if isinstance(val, list) and len(val) > 40:
                raise ValueError(f"'{key}' tiene demasiados elementos")
        return v


class PreferencesIn(BaseModel):
    """Formulario "¿Qué estás buscando?". Las listas cerradas se validan contra catálogos en el dominio."""
    model_config = ConfigDict(extra="forbid")
    desired_roles: list[str] = Field(default_factory=list, max_length=5)
    sectors: list[str] = Field(default_factory=list, max_length=5)
    city: str | None = Field(None, max_length=80)
    modality: str | None = Field(None, max_length=20)
    workday: list[str] = Field(default_factory=list, max_length=9)
    contract_types: list[str] = Field(default_factory=list, max_length=4)
    salary_min_cop: int | None = Field(None, ge=0, le=200_000_000)
    salary_frequency: str = Field("mensual", max_length=20)
    availability: str | None = Field(None, max_length=30)
    willing_to_travel: bool | None = None
    willing_to_relocate: bool | None = None


class SkillLevelsIn(BaseModel):
    """{"Excel": "avanzado", "SQL": "intermedio"} — nivel de cada herramienta/conocimiento."""
    levels: dict[str, str] = Field(max_length=40)


class SensitiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool = False
    sex: str | None = Field(None, max_length=30)
    birth_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    disability: bool | None = None
    disability_type: str | None = Field(None, max_length=30)


class IdentityIn(BaseModel):
    """Datos para postular. Se piden solo cuando el candidato aprueba postulaciones."""
    model_config = ConfigDict(extra="forbid")
    first_names: str | None = Field(None, max_length=80)
    last_names: str | None = Field(None, max_length=80)
    document_type: str | None = Field(None, max_length=60)
    document_id: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=20)
    sensitive: SensitiveIn | None = None


class ProfileEditIn(BaseModel):
    """Edición del perfil por secciones. Solo se envían las secciones que cambian."""
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(None, max_length=120)
    first_names: str | None = Field(None, max_length=80)
    last_names: str | None = Field(None, max_length=80)
    email: str | None = Field(None, max_length=120, pattern=r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
    phone: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=80)
    linkedin: str | None = Field(None, max_length=200)
    github: str | None = Field(None, max_length=200)
    portfolio: str | None = Field(None, max_length=200)
    headline: str | None = Field(None, max_length=150)
    summary: str | None = Field(None, max_length=800)
    skills: list[Skill] | None = Field(None, max_length=40)
    languages: list[Language] | None = Field(None, max_length=10)
    experiences: list[Experience] | None = Field(None, max_length=20)
    projects: list[Project] | None = Field(None, max_length=10)
    education: list[Education] | None = Field(None, max_length=15)
    certifications: list[Certification] | None = Field(None, max_length=20)
    expectations: Expectations | None = None


class ApproveIn(BaseModel):
    vacancy_ids: list[str] = Field(max_length=20)


class AdvanceIn(BaseModel):
    days: int = Field(default=3, ge=1, le=30)


class ReminderPatch(BaseModel):
    done: bool


class StateOut(BaseModel):
    stage: str
    sim_day: int
    pending: dict | None
    llm_providers: list[str]
