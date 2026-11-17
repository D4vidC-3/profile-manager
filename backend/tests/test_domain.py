from datetime import date

from app.domain.colombia import normalize_city, normalize_modality, parse_salary_range, smart_title
from app.domain.completeness import (
    apply_identity,
    apply_preferences,
    cv_completeness,
    detect_cv_gaps,
    is_first_job,
    missing_preferences,
    project_credit,
)
from app.domain.languages import parse_language, parse_languages_text
from app.domain.models import (
    Education,
    Expectations,
    Experience,
    Language,
    LanguageLevel,
    Modality,
    Profile,
    Project,
    Seniority,
    Vacancy,
)
from app.domain.scoring import hard_filter, rank, score_vacancy
from app.domain.skills import extract_skills_from_text, normalize_skill, split_level
from app.domain.skillset import make_skill, merge_skills


def _vac(**kw) -> Vacancy:
    base = dict(id="V1", title="Desarrollador Backend Junior", company="X", city="Medellín",
                modality=Modality.HIBRIDO, salary_min_cop=3_500_000, salary_max_cop=5_000_000,
                seniority=Seniority.JUNIOR, must_have=["Python", "SQL"], nice_to_have=["Docker"],
                sector="Software, informática y telecomunicaciones")
    base.update(kw)
    return Vacancy(**base)


def _profile(**kw) -> Profile:
    p = Profile(full_name="Ana", email="a@b.co", phone="3001234567", city="Medellín",
                skills=["Python", "SQL", "Docker"], seniority=Seniority.JUNIOR,
                expectations=Expectations(desired_roles=["Desarrollador Backend"], city="Medellín",
                                          modality=Modality.HIBRIDO, salary_min_cop=4_000_000))
    return Profile(**{**p.model_dump(), **kw})  # reconstruye para que Pydantic valide (habilidades tipadas)


# ---------------------------------------------------------------- normalizadores e idiomas
def test_skill_synonyms():
    assert normalize_skill("js") == "JavaScript"
    assert normalize_skill("Postgres") == "PostgreSQL"
    assert "Java" not in extract_skills_from_text("Trabajo con JavaScript")
    assert set(extract_skills_from_text("Python, Docker y React.js")) >= {"Python", "Docker", "React"}


def test_skill_kinds_and_levels():
    assert split_level("Excel avanzado") == ("Excel", "avanzado")
    assert split_level("Python (básico)") == ("Python", "basico")
    assert make_skill("Excel avanzado").level.value == "avanzado"
    assert make_skill("Contabilidad").kind.value == "conocimiento"
    soft = make_skill("trabajo colaborativo", level="avanzado")
    assert soft.name == "Trabajo en equipo" and soft.kind.value == "transversal" and soft.level is None
    assert make_skill("Habilidad rara").kind.value == "herramienta"  # fuera del catálogo: por defecto
    merged = merge_skills(["Excel"], [make_skill("Excel intermedio")])
    assert len(merged) == 1 and merged[0].level.value == "intermedio"
    # "Comunicación Social" (texto libre) no es la habilidad blanda "Comunicación"
    assert "Comunicación" not in extract_skills_from_text("Estudié Comunicación Social")


def test_city_modality_salary_and_titles():
    assert normalize_city("bogota d.c.") == "Bogotá"
    assert normalize_modality("Teletrabajo") == Modality.REMOTO
    assert parse_salary_range("4.5M a 6M") == (4_500_000, 6_000_000)
    assert parse_salary_range("A convenir") == (None, None)
    assert smart_title("AUXILIAR DE SOPORTE TI") == "Auxiliar de Soporte TI"


def test_language_levels_and_certificates():
    assert parse_language("Inglés — B1 (intermedio)").level == LanguageLevel.INTERMEDIO
    assert parse_language("Portugués").level is None  # sin nivel => pendiente
    vague = parse_language("Inglés intermedio")  # sin nivel exacto: se propone B1 para confirmar
    assert vague.cefr == "B1" and vague.suggested
    assert Language(name="Inglés", cefr="c1").level == LanguageLevel.AVANZADO  # el MCER manda
    assert Language(name="Español", level=LanguageLevel.NATIVO, cefr="B2").cefr is None
    ielts = parse_language("Inglés IELTS 7.0")
    assert ielts.cefr == "C1" and ielts.suggested and "IELTS" in ielts.evidence
    langs = parse_languages_text("Español — Nativo; Inglés — B2 (intermedio alto)")
    assert [(lang.name, lang.level) for lang in langs] == [("Español", LanguageLevel.NATIVO),
                                                           ("Inglés", LanguageLevel.INTERMEDIO)]


# ---------------------------------------------------------------- completitud del CV
def test_cv_completeness_ignores_expectations():
    p = _profile(headline="Dev", summary="Resumen", education=[Education(degree="Ing", institution="U", year="2020")],
                 experiences=[Experience(title="Dev", company="X", start="2021")],
                 skills=["Python", "SQL", "Docker", "Git", "Linux"],
                 languages=[Language(name="Español", level=LanguageLevel.NATIVO)], linkedin="in/ana")
    assert cv_completeness(p).score == 97.0  # solo faltan cursos (3): las expectativas no cuentan
    assert cv_completeness(p.model_copy(update={"expectations": Expectations()})).score == 97.0


def test_first_job_redistributes_experience_weight():
    p = Profile(full_name="Juan", email="j@x.co", phone="3001112233", city="Cali", headline="Dev", summary="s",
                education=[Education(degree="Tecnología en Sistemas", institution="USC", year="2025",
                                     status="finalizado")],
                skills=["Python", "Django", "MySQL", "HTML", "CSS"])
    first, reason = is_first_job(p, today=date(2026, 11, 1))
    assert first and "2025" in reason
    s = cv_completeness(p, today=date(2026, 11, 1))
    assert s.mode == "primer_empleo" and "experience" not in {b["key"] for b in s.breakdown}
    assert s.score > cv_completeness(p.model_copy(update={"education": []}), today=date(2026, 11, 1)).score
    gaps = {g.field for g in detect_cv_gaps(p, today=date(2026, 11, 1))}
    assert "projects" in gaps and "experience" not in gaps


def test_projects_scored_by_evidence_not_truth():
    assert project_credit(Project(name="Bot")) == 0.25
    assert project_credit(Project(name="Bot", description="API", technologies=["Python"])) == 0.75
    assert project_credit(Project(name="Bot", description="API", technologies=["Python"], url="github.com/a/b")) == 1


def test_soft_skills_alone_do_not_complete_skills_block():
    soft_only = Profile(skills=["Comunicación", "Liderazgo", "Trabajo en equipo", "Creatividad", "Empatía"])
    tech = Profile(skills=["Excel", "SAP", "Contabilidad", "Power BI", "Siigo"])
    credit = {b["key"]: b["got"] for b in cv_completeness(soft_only).breakdown}
    assert credit["skills"] < 3
    assert {b["key"]: b["got"] for b in cv_completeness(tech).breakdown}["skills"] == 10
    assert next(g for g in detect_cv_gaps(soft_only) if g.field == "skills").critical


def test_only_contact_and_skills_block():
    critical = {g.field for g in detect_cv_gaps(Profile(email="a@b.co")) if g.critical}
    assert critical == {"full_name", "phone", "skills"}


# ---------------------------------------------------------------- preferencias e identidad
def test_preferences_validated_against_catalogs():
    p, updated = apply_preferences(Profile(), {
        "desired_roles": ["Analista de datos"], "sectors": ["Software, informática y telecomunicaciones", "Inventado"],
        "city": "medellin", "modality": "remoto", "workday": ["Tiempo completo", "Nunca"],
        "salary_min_cop": "4.000.000"})
    e = p.expectations
    assert e.sectors == ["Software, informática y telecomunicaciones"] and e.workday == ["Tiempo completo"]
    assert e.city == "Medellín" and e.salary_min_cop == 4_000_000
    assert missing_preferences(p) == []


def test_identity_and_sensitive_require_consent():
    p, _ = apply_identity(Profile(), {"document_type": "Cédula de ciudadanía", "document_id": "1.234.567",
                                      "sensitive": {"consent": False, "sex": "Mujer"}})
    assert p.document_id == "1234567" and p.sensitive.sex is None
    p, _ = apply_identity(p, {"sensitive": {"consent": True, "sex": "Mujer", "disability": False}})
    assert p.sensitive.sex == "Mujer" and p.sensitive.consent


# ---------------------------------------------------------------- matching
def test_perfect_match_scores_high_and_explains():
    m = score_vacancy(_profile(), _vac())
    assert m.score >= 80 and any("2 de 2" in r for r in m.reasons)


def test_declared_skills_count_fully_evidence_is_only_informative():
    declared = score_vacancy(_profile(), _vac())
    shown = score_vacancy(_profile(demonstrated_skills=["Python", "SQL"]), _vac())
    assert shown.score == declared.score  # lo declarado es verdad
    assert {d.name: d.demonstrated for d in shown.skills_detail} == {"Python": True, "SQL": True}


def test_gaps_lower_score_but_never_discard():
    v = _vac(must_have=["Python", "SQL", "Kubernetes"], seniority=Seniority.SENIOR, min_education="profesional")
    assert hard_filter(_profile(), v) is None  # antes: descartaba por nivel
    m = score_vacancy(_profile(), v)
    kinds = {g.kind for g in m.gaps}
    assert {"habilidad", "experiencia", "educacion"} <= kinds
    assert next(d for d in m.skills_detail if d.name == "Kubernetes").status == "falta"


def test_not_applicable_components_are_not_penalized():
    m = score_vacancy(_profile(), _vac(nice_to_have=[]))
    assert {"skills_deseables", "transversales", "educacion"} <= set(m.not_applicable)
    assert m.breakdown["transversales"] == 2.0 and m.breakdown["skills_deseables"] == 8.0


def test_language_partial_credit_and_cefr_message():
    v = _vac(languages={"Inglés": "B2"})
    b1 = score_vacancy(_profile(languages=[Language(name="Inglés", cefr="B1")]), v)
    a2 = score_vacancy(_profile(languages=[Language(name="Inglés", cefr="A2")]), v)
    b2 = score_vacancy(_profile(languages=[Language(name="Inglés", cefr="B2")]), v)
    assert b2.score > b1.score > a2.score
    assert any("tienes B1" in g.message for g in b1.gaps)


def test_sensitive_data_never_changes_score():
    base = score_vacancy(_profile(), _vac()).score
    p = _profile()
    p.sensitive.consent, p.sensitive.sex, p.sensitive.disability = True, "Mujer", True
    assert score_vacancy(p, _vac()).score == base


def test_soft_skills_never_discard_and_weigh_little():
    v = _vac(must_have=["Python", "SQL", "Liderazgo", "Comunicación"])
    assert hard_filter(_profile(), v) is None  # le faltan las transversales, pero no descarta
    with_soft = score_vacancy(_profile(skills=["Python", "SQL", "Docker", "Liderazgo", "Comunicación"]), v)
    without = score_vacancy(_profile(), v)
    assert 0 < with_soft.score - without.score <= 2


def test_skill_level_required_by_vacancy():
    v = _vac(skill_levels={"Python": "avanzado"})
    unknown = score_vacancy(_profile(), v)
    low = score_vacancy(_profile(skills=["Python básico", "SQL", "Docker"]), v)
    ok = score_vacancy(_profile(skills=["Python avanzado", "SQL", "Docker"]), v)
    assert ok.score == unknown.score > low.score  # sin nivel declarado no resta; un nivel menor sí
    assert any("confirma tu nivel" in g.message for g in unknown.gaps)
    assert any("tienes básico" in g.message for g in low.gaps)


def test_language_requirements():
    v = _vac(languages={"Inglés": "B2"})
    pending = score_vacancy(_profile(languages=[Language(name="Inglés")]), v)
    ok = score_vacancy(_profile(languages=[Language(name="Inglés", level=LanguageLevel.AVANZADO)]), v)
    assert pending.pending_languages == ["Inglés B2"] and ok.score > pending.score


def test_hard_filters():
    assert hard_filter(_profile(), _vac(city="Cali", modality=Modality.PRESENCIAL)) is not None
    assert hard_filter(_profile(), _vac(city="Envigado")) is None  # área metropolitana
    assert "salario" in hard_filter(_profile(), _vac(salary_max_cop=2_000_000)).lower()
    assert hard_filter(_profile(), _vac(seniority=Seniority.SENIOR)) is None  # brecha, no condición
    half = _profile()
    half.expectations.workday = ["Medio tiempo"]
    assert "tiempo completo" in hard_filter(half, _vac())
    services = _profile()
    services.expectations.contract_types = ["Prestación de servicios"]
    assert hard_filter(services, _vac()) is not None


def test_rank_orders_and_discards():
    good = _vac(id="A")
    weak = _vac(id="B", must_have=["Java", "Kotlin", "Swift"], title="Desarrollador Móvil")
    far = _vac(id="C", city="Cali", modality=Modality.PRESENCIAL)
    matches, discards = rank(_profile(), [weak, good, far], threshold=45, limit=10)
    assert [m.vacancy.id for m in matches] == ["A"]
    assert {d.vacancy_id for d in discards} == {"B", "C"}
