"""Camino CON IA usando un LLM falso (no requiere API keys)."""

from app.agents.followup_agent import FollowupAgent, PersonalizedBatch, PersonalizedReminder
from app.agents.profile_agent import (
    AIEducation,
    AIExperience,
    AILanguage,
    AIProject,
    AISkill,
    CVExtraction,
    ProfileAgent,
    _merge,
    apply_locked,
)
from app.agents.tracing import Tracer
from app.domain.models import LanguageLevel, Profile
from app.infrastructure.llm.provider import LLMResult
from app.infrastructure.repositories import Repository


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def available(self):
        return ["fake"]

    def invoke_structured(self, schema, system, user):
        self.calls += 1
        return self.response, LLMResult(provider="fake", duration_ms=5)


def _tracer(name: str):
    repo = Repository()
    user = repo.create_user(name, "x")
    return repo, user.id, Tracer(repo, user.id, f"run-{name}")


def test_profile_agent_merges_ai_without_inventing(cv_free):
    repo, uid, tracer = _tracer("llm-perfil")
    ai = CVExtraction(full_name="Nombre Inventado", headline="Desarrollador Frontend", seniority="junior",
                      years_experience=2,
                      skills=[AISkill(name="Figma"), AISkill(name="js"), AISkill(name="No especificado"),
                              AISkill(name="Storybook", kind="herramienta", level="avanzado", evidence="UI kit"),
                              AISkill(name="Empatía", kind="transversal", level="avanzado", evidence="x")],
                      experiences=[AIExperience(title="Frontend Developer", company="Retail Caribe", start="2024")],
                      education=[AIEducation(degree="Tecnólogo en Desarrollo de Software", level="tecnólogo")],
                      languages=[AILanguage(name="Inglés", level="intermedio", evidence="clientes en EE.UU."),
                                 AILanguage(name="Francés", level="avanzado")],  # sin evidencia => sin nivel
                      suggested_roles=["Desarrollador Frontend"], suggested_sectors=["Software, informática y "
                                                                                     "telecomunicaciones", "Otro"])
    profile, _, _ = ProfileAgent(FakeLLM(ai)).run(cv_free.decode(), tracer)
    assert profile.full_name == "Andrés Felipe Rojas"  # dato de reglas se conserva
    assert profile.headline == "Desarrollador Frontend"
    skills = {sk.name: sk for sk in profile.skills}
    assert "Figma" in skills and "JavaScript" in skills and "No especificado" not in skills
    assert skills["Storybook"].level.value == "avanzado" and skills["Storybook"].suggested  # nivel con evidencia
    assert skills["Empatía"].kind.value == "transversal" and skills["Empatía"].level is None
    langs = {lang.name: lang for lang in profile.languages}
    assert langs["Inglés"].suggested and langs["Inglés"].level == LanguageLevel.INTERMEDIO
    assert langs["Francés"].level is None
    assert langs["Español"].level == LanguageLevel.NATIVO and langs["Español"].suggested
    assert profile.suggestions["sectors"] == ["Software, informática y telecomunicaciones"]
    assert profile.expectations.desired_roles == []  # la IA solo SUGIERE, no llena expectativas
    assert any(t.mode == "llm" and t.provider == "fake" for t in repo.list_traces(uid))


def test_ai_can_clean_but_not_replace_name():
    merged, _ = _merge(Profile(full_name="Mateo Ríos Experiencia"), CVExtraction(full_name="Mateo Ríos"))
    assert merged.full_name == "Mateo Ríos"
    merged, _ = _merge(Profile(full_name="Ana Pérez"), CVExtraction(full_name="Otra Persona"))
    assert merged.full_name == "Ana Pérez"


def test_ai_projects_get_specificity_and_evidence():
    merged, _ = _merge(Profile(), CVExtraction(projects=[AIProject(name="Bot", description="API de empleo",
                                                                   technologies=["Python"], specificity=2)]))
    assert merged.projects[0].evidence == "descrito" and merged.projects[0].specificity == 2


def test_new_cv_same_person_keeps_edits_but_not_preferences():
    prev = Profile(email="ana@x.co", skills=["Excel", "SAP"], phone="3001112233", edited_fields=["skills"],
                   document_id="123")
    prev.expectations.desired_roles = ["Analista"]
    new, kept = apply_locked(Profile(email="ANA@x.co", skills=["Basura"], phone="3009998877"), prev)
    assert new.skill_names == ["Excel", "SAP"] and new.phone == "3009998877" and kept == ["skills"]
    assert new.document_id == "123"
    assert new.expectations.desired_roles == []  # "Lo que buscas" se vuelve a preguntar


def test_new_cv_other_person_starts_from_scratch():
    prev = Profile(email="ana@x.co", skills=["Excel"], edited_fields=["skills"], document_id="123")
    new, kept = apply_locked(Profile(email="pedro@x.co", skills=["Python"]), prev)
    assert new.skill_names == ["Python"] and new.document_id is None and kept == []


def test_followup_agent_uses_ai_messages_in_one_call():
    repo, uid, tracer = _tracer("llm-seguimiento")
    tracer.sim_day = 3
    repo.add_application(user_id=uid, vacancy_id="VAC-001", vacancy_title="Dev", company="ACME", score=80,
                         status="en_revision", created_day=0, updated_day=2, evidence={}, history=[])
    batch = PersonalizedBatch(items=[
        PersonalizedReminder(index=0, message="Mensaje personalizado", next_steps=["Paso 1", "Paso 2"]),
        PersonalizedReminder(index=1, message="Mejora tu hoja de vida")])
    llm = FakeLLM(batch)
    n = FollowupAgent(repo, llm).run(uid, Profile(full_name="Ana"), {}, tracer)
    assert n == 2 and llm.calls == 1
    assert {r.mode for r in repo.list_reminders(uid)} == {"llm"}
    assert repo.list_applications(uid)[0].next_steps == ["Paso 1", "Paso 2"]
    assert FollowupAgent(repo, llm).run(uid, Profile(full_name="Ana"), {}, tracer) == 0  # sin duplicados
