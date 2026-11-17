import httpx
import pytest

from app.config import get_settings
from app.domain.models import ApplicationStatus, Project
from app.domain.process import simulate_company_response
from app.infrastructure.github import verify_project
from app.infrastructure.llm.provider import LLMChain
from app.infrastructure.portal import PortalRejected, submit_application
from app.infrastructure.vacancies.source import JsonDatasetSource, normalize_vacancy


def test_llm_chain_falls_back_to_mock():
    result, meta = LLMChain().invoke_structured(type("X", (), {}), "s", "u")  # type: ignore[arg-type]
    assert result is None and meta.provider == "mock"


def test_dataset_normalization_separates_languages():
    raw = JsonDatasetSource().fetch_raw()
    assert len(raw) >= 60
    assert all(normalize_vacancy(r)[0] is not None for r in raw)
    v, changes = normalize_vacancy({
        "id": "Z", "titulo": "Desarrollador", "ubicacion": "bogota", "modalidad": "Teletrabajo",
        "salario": "4M a 5M", "nivel": "SSr", "requisitos": "js, postgres, Inglés B2",
        "tipo_contrato": "Contrato de aprendizaje", "jornada": "Medio tiempo"})
    assert v.city == "Bogotá" and v.modality.value == "remoto" and v.must_have == ["JavaScript", "PostgreSQL"]
    assert v.languages == {"Inglés": "B2"} and v.contract == "Práctica / etapa productiva"
    assert v.workday == "Medio tiempo" and v.sector == "Software, informática y telecomunicaciones"


def test_portal_requires_identity():
    with pytest.raises(PortalRejected):
        submit_application({"vacancy_id": "X", "full_name": "A", "email": "a@b.co"})


def test_company_simulation_is_deterministic():
    a = simulate_company_response(1, ApplicationStatus.EN_REVISION, 9, 5, 80)
    b = simulate_company_response(1, ApplicationStatus.EN_REVISION, 9, 9, 80)
    assert a == b
    assert simulate_company_response(1, ApplicationStatus.POSTULADO, 0, 1, 80) == ApplicationStatus.POSTULADO


def test_better_match_gets_fewer_rejections():
    def rejected(score):
        return sum(simulate_company_response(i, ApplicationStatus.EN_REVISION, 9, 9, score)
                   == ApplicationStatus.DESCARTADO for i in range(1, 401))
    assert rejected(90) < rejected(50)


@pytest.fixture
def github_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "verify_github", True)


def _client(status: int, langs: dict):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status, json=langs)))


def test_github_verified_when_repo_exists_and_languages_match(github_on):
    pr = Project(name="Bot", technologies=["Python"], url="https://github.com/ana/bot", evidence="con_enlace")
    out = verify_project(pr, client=_client(200, {"Python": 1200, "HTML": 300}))
    assert out.evidence == "verificado" and out.verified_languages == ["Python", "HTML"]


def test_github_not_verified_when_missing_or_mismatch(github_on):
    pr = Project(name="Bot", technologies=["Java"], url="github.com/ana/bot", evidence="con_enlace")
    assert verify_project(pr, client=_client(404, {})).evidence == "con_enlace"
    assert verify_project(pr, client=_client(200, {"Python": 10})).evidence == "con_enlace"
