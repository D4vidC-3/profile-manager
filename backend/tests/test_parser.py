"""Parser por reglas con los CVs de ejemplo del equipo (samples/1) y la plantilla recomendada."""

import pytest

from app.domain.completeness import cv_completeness
from app.domain.models import LanguageLevel
from app.infrastructure.cv.extractor import CVReadError, extract_text, parse_cv_rules

JUNK = ("especific", "faltante", "disponible", "cargo objetivo", "preferencias", "ficticio", "sintético",
        "modalidad", "aspiración")


def _parse(samples_dir, rel):
    path = samples_dir / rel
    return parse_cv_rules(extract_text(path.name, path.read_bytes()))


@pytest.mark.parametrize("name", ["01_CV_Completo_Desarrollador_Software", "02_CV_Completo_Analista_Datos",
                                  "03_CV_Completo_Administracion_Logistica", "04_CV_Incompleto_Marketing",
                                  "05_CV_Incompleto_Soporte_TI"])
def test_no_junk_skills_and_no_expectations(samples_dir, name):
    p = _parse(samples_dir, f"1/{name}.pdf")
    assert not [s for s in p.skill_names if any(j in s.lower() for j in JUNK)], p.skill_names
    assert p.expectations.desired_roles == [] and p.expectations.salary_min_cop is None  # un CV no trae expectativas


def test_dates_on_next_line_format(samples_dir):
    p = _parse(samples_dir, "1/01_CV_Completo_Desarrollador_Software.pdf")
    assert p.headline == "Desarrollador de Software Junior"
    assert (p.first_names, p.last_names) == ("Mateo Andrés", "Restrepo Gómez")
    assert [(e.title, e.company, e.city, e.start) for e in p.experiences] == [
        ("Desarrollador web junior", "Nube Andina S.A.S.", "Medellín", "Enero 2024"),
        ("Practicante de desarrollo", "Código Local", "Medellín", "Julio 2023")]
    assert p.education[0].degree == "Tecnología en Análisis y Desarrollo de Software"
    assert p.education[0].institution == "SENA" and p.education[0].status == "finalizado"
    assert {(lang.name, lang.level) for lang in p.languages} == {("Español", LanguageLevel.NATIVO),
                                                                 ("Inglés", LanguageLevel.INTERMEDIO)}
    assert p.years_experience == 2.3 and cv_completeness(p).score >= 95


def test_institution_with_city_name_and_diploma_as_course(samples_dir):
    p = _parse(samples_dir, "1/03_CV_Completo_Administracion_Logistica.pdf")
    assert p.education[0].institution == "Universidad Santiago de Cali"
    assert p.certifications[0].name.startswith("Diplomado en Gestión")
    kinds = {s.name: (s.kind.value, s.level) for s in p.skills}
    assert kinds["Excel"] == ("herramienta", "avanzado")  # "Excel avanzado" captura el nivel
    assert kinds["SAP"] == ("herramienta", "basico")
    assert kinds["Control de inventarios"][0] == "conocimiento"
    assert kinds["Comunicación"][0] == "transversal" and kinds["Organización"][0] == "transversal"


def test_incomplete_cv_keeps_what_exists(samples_dir):
    p = _parse(samples_dir, "1/05_CV_Incompleto_Soporte_TI.pdf")
    assert p.headline == "Auxiliar de Soporte TI" and p.phone is None
    assert p.experiences[0].title == "Soporte informal a equipos de conocidos"
    assert set(p.skill_names) == {"Soporte técnico", "Mantenimiento de computadores", "Instalación de software"}
    assert "Inglés" not in {lang.name for lang in p.languages}  # "no se especifica nivel de inglés" es negación


def test_soft_skills_only_from_skills_section(samples_dir):
    p = _parse(samples_dir, "1/02_CV_Completo_Analista_Datos.pdf")
    soft = {s.name for s in p.skills if s.kind.value == "transversal"}
    assert soft == {"Pensamiento analítico", "Comunicación", "Atención al detalle", "Trabajo en equipo"}
    assert all(s.level is None for s in p.skills if s.kind.value == "transversal")


def test_template_format(samples_dir):
    p = _parse(samples_dir, "plantilla_hoja_de_vida.txt")
    assert p.experiences[0].city == "Medellín" and p.experiences[0].current
    assert p.projects[0].name == "Bot de recomendaciones de empleo" and "FastAPI" in p.projects[0].technologies
    assert [c.name for c in p.certifications] == ["AWS Cloud Practitioner", "Scrum Fundamentals"]
    assert p.github and p.linkedin and p.document_id is None
    assert cv_completeness(p).score == 100.0


def test_extract_text_rejects_bad_files():
    with pytest.raises(CVReadError):
        extract_text("cv.exe", b"MZ....")
    with pytest.raises(CVReadError):
        extract_text("cv.pdf", b"no soy un pdf")
