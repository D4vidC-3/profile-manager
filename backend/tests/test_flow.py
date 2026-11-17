"""Integración: flujo completo del grafo de agentes a través de la API."""

from fastapi.testclient import TestClient

from app.main import app

PREFS = {"desired_roles": ["Desarrollador Backend"], "sectors": ["Software, informática y telecomunicaciones"],
         "city": "Medellín", "modality": "hibrido", "workday": ["Tiempo completo"], "salary_min_cop": 3000000}
IDENTITY = {"first_names": "Laura", "last_names": "Martínez Gómez", "document_type": "Cédula de ciudadanía",
            "document_id": "1036555444"}


def _client():
    c = TestClient(app)
    c.__enter__()  # dispara lifespan (crea usuario demo)
    return c


def _login(c, username):
    c.post("/api/auth/register", json={"username": username, "password": "secreto123"})
    r = c.post("/api/auth/login", json={"username": username, "password": "secreto123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _levels(c, h, pending):
    """Responde el paso obligatorio de niveles con 'intermedio' para todas las habilidades pendientes."""
    levels = {sk["name"]: "intermedio" for sk in pending["skills"]}
    return c.post("/api/applications/skill-levels", headers=h, json={"levels": levels}).json()


def _upload(c, h, content, name="cv.txt"):
    return c.post("/api/onboarding", headers=h, files={"cv": (name, content, "text/plain")})


def test_requires_auth():
    c = _client()
    assert c.get("/api/state").status_code == 401
    assert c.get("/api/state", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_full_flow_with_template_cv(cv_template):
    c = _client()
    h = _login(c, "laura")
    body = _upload(c, h, cv_template).json()
    # La hoja de vida está completa: solo se sugiere confirmar idiomas (no bloquea)
    if body["stage"] == "cv_gaps":
        assert not [g for g in body["pending"]["gaps"] if g["critical"]]
        body = c.post("/api/onboarding/cv", headers=h, json={"answers": {}}).json()
    assert body["stage"] == "preferences"  # las expectativas NUNCA salen del CV
    assert "desired_roles" in body["pending"]["missing"]

    body = c.post("/api/onboarding/preferences", headers=h, json=PREFS).json()
    assert body["stage"] == "approval"
    matches = body["pending"]["matches"]
    assert matches and matches[0]["score"] >= matches[-1]["score"]
    ids = [m["vacancy"]["id"] for m in matches[:2]]

    body = c.post("/api/applications/approve", headers=h, json={"vacancy_ids": ids + ["VAC-NO-EXISTE"]}).json()
    assert body["stage"] == "skill_levels"  # requisito: cada habilidad técnica con nivel
    assert body["pending"]["skills"] and all(sk["kind"] != "transversal" for sk in body["pending"]["skills"])
    body = _levels(c, h, body["pending"])
    assert body["stage"] == "identity"  # el documento se pide solo al postular
    assert {"document_type", "document_id"} <= set(body["pending"]["missing"])

    body = c.post("/api/applications/identity", headers=h, json=IDENTITY).json()
    assert body["stage"] == "tracking"
    apps = c.get("/api/applications", headers=h).json()
    assert len(apps) == 2 and all(a["status"] == "postulado" for a in apps)
    assert "document_id" not in apps[0]["evidence"]["form"]  # la evidencia no guarda el documento

    assert c.post("/api/simulate/advance", headers=h, json={"days": 10}).json()["sim_day"] == 10
    agents = {t["agent"] for t in c.get("/api/trace", headers=h).json()}
    assert {"perfil", "vacantes", "postulacion", "seguimiento", "candidato"} <= agents


def test_incomplete_cv_asks_only_cv_data(cv_free):
    c = _client()
    h = _login(c, "andres")
    body = _upload(c, h, cv_free).json()
    assert body["stage"] == "cv_gaps"
    fields = {g["field"]: g["critical"] for g in body["pending"]["gaps"]}
    assert fields.get("phone") is True
    assert not any(f.startswith("expectations") for f in fields)  # nada de expectativas en vacíos del CV
    assert c.post("/api/onboarding/cv", headers=h, json={"answers": {"salary": 1}}).status_code == 422

    body = c.post("/api/onboarding/cv", headers=h, json={"answers": {"phone": "3001112233"}}).json()
    assert body["stage"] == "preferences"
    assert c.post("/api/onboarding/cv", headers=h, json={"answers": {}}).status_code == 409  # etapa equivocada


def test_edit_profile_recalculates_and_survives_new_cv(cv_template):
    c = _client()
    h = _login(c, "editor")
    if _upload(c, h, cv_template).json()["stage"] == "cv_gaps":
        c.post("/api/onboarding/cv", headers=h, json={"answers": {}})
    before = c.post("/api/onboarding/preferences", headers=h, json=PREFS).json()["pending"]["matches"]

    skills = [{"name": n, "kind": "herramienta"} for n in ["Python", "SQL", "Docker", "AWS", "Node.js"]]
    skills += [{"name": "REST APIs", "kind": "conocimiento", "level": "avanzado"},
               {"name": "Liderazgo", "kind": "transversal", "level": "avanzado"},
               {"name": "Excel", "kind": "conocimiento"},  # intenta cambiar el tipo de una del catálogo
               {"name": "Storybook", "kind": "conocimiento"}]  # fuera del catálogo: toma el tipo de su sección
    r = c.put("/api/profile", headers=h, json={"skills": skills})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["recalculated"] and out["stage"] == "approval" and out["changed"] == ["skills"]
    saved = {s["name"]: s for s in out["view"]["profile"]["skills"]}
    assert out["view"]["profile"]["provenance"]["skills"] == "usuario"
    assert saved["Excel"]["kind"] == "herramienta"  # el tipo del catálogo no cambia
    assert saved["Storybook"]["kind"] == "conocimiento" and saved["REST APIs"]["level"] == "avanzado"
    assert saved["Liderazgo"]["level"] is None  # las transversales no tienen nivel
    assert out["pending"]["matches"] != before
    assert c.put("/api/profile", headers=h, json={"role": "admin"}).status_code == 422  # lista blanca

    _upload(c, h, cv_template)  # CV nuevo de la misma persona: lo editado a mano se conserva
    view = c.get("/api/profile", headers=h).json()
    assert "AWS" in {s["name"] for s in view["profile"]["skills"]}
    assert view["profile"]["expectations"]["desired_roles"] == []  # "Lo que buscas" se reinicia...
    assert view["preferences"]["score"] == 0


def test_rejects_invalid_upload():
    c = _client()
    h = _login(c, "malo")
    r = c.post("/api/onboarding", headers=h, files={"cv": ("cv.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


def test_new_cv_asks_preferences_again_prefilled(cv_template):
    c = _client()
    h = _login(c, "recargar")
    if _upload(c, h, cv_template).json()["stage"] == "cv_gaps":
        c.post("/api/onboarding/cv", headers=h, json={"answers": {}})
    c.post("/api/onboarding/preferences", headers=h, json=PREFS)

    body = _upload(c, h, cv_template).json()  # se equivocó de CV / sube uno nuevo
    if body["stage"] == "cv_gaps":
        body = c.post("/api/onboarding/cv", headers=h, json={"answers": {}}).json()
    assert body["stage"] == "preferences"  # vuelve a preguntar "¿Qué buscas?"...
    assert body["pending"]["values"]["desired_roles"] == ["Desarrollador Backend"]  # ...pre-llenado
    changed = {**PREFS, "desired_roles": ["Ingeniero de Datos"]}
    assert c.post("/api/onboarding/preferences", headers=h, json=changed).json()["stage"] == "approval"
    view = c.get("/api/profile", headers=h).json()
    assert view["profile"]["expectations"]["desired_roles"] == ["Ingeniero de Datos"]


def test_new_cv_of_other_person_resets_preferences(cv_template, cv_free):
    c = _client()
    h = _login(c, "otra-persona")
    if _upload(c, h, cv_template).json()["stage"] == "cv_gaps":
        c.post("/api/onboarding/cv", headers=h, json={"answers": {}})
    c.post("/api/onboarding/preferences", headers=h, json=PREFS)

    body = _upload(c, h, cv_free).json()  # CV de otra persona
    if body["stage"] == "cv_gaps":
        body = c.post("/api/onboarding/cv", headers=h, json={"answers": {"phone": "3001112233"}}).json()
    assert body["stage"] == "preferences"
    assert body["pending"]["values"]["desired_roles"] == []  # sin pre-llenado de la otra persona
    assert c.get("/api/profile", headers=h).json()["preferences"]["score"] == 0


def test_skill_options_30_per_kind_ranked_by_what_they_look_for(cv_template):
    c = _client()
    h = _login(c, "opciones")
    if _upload(c, h, cv_template).json()["stage"] == "cv_gaps":
        c.post("/api/onboarding/cv", headers=h, json={"answers": {}})
    c.post("/api/onboarding/preferences", headers=h,
           json={**PREFS, "desired_roles": ["Analista de Logística"],
                 "sectors": ["Logística, transporte y almacenamiento"]})
    opts = c.get("/api/skills/options", headers=h).json()
    assert {k: len(v) for k, v in opts.items()} == {"herramienta": 30, "conocimiento": 30, "transversal": 30}
    assert opts["conocimiento"][0] == "Control de inventarios"  # lo que piden las vacantes que busca va primero


def test_refresh_and_apply_more_from_board_with_preparation_plan(cv_template):
    c = _client()
    h = _login(c, "tablero")
    if _upload(c, h, cv_template).json()["stage"] == "cv_gaps":
        c.post("/api/onboarding/cv", headers=h, json={"answers": {}})
    c.post("/api/onboarding/preferences", headers=h, json=PREFS)
    c.post("/api/applications/approve", headers=h, json={"vacancy_ids": []})  # no postula todavía
    assert c.get("/api/state", headers=h).json()["stage"] == "tracking"

    # Cambia lo que busca y actualiza recomendaciones desde el tablero
    c.put("/api/profile", headers=h, json={"expectations": {**PREFS, "modality": "remoto"}})
    assert c.post("/api/matches/refresh", headers=h).status_code == 200
    matches = c.get("/api/matches", headers=h).json()
    with_gaps = [m for m in matches if m["gaps"]]
    assert with_gaps, "debería haber recomendaciones con brechas (no descartadas)"

    # Postula desde el tablero: pide identidad porque aún no la tiene
    body = c.post("/api/applications/approve", headers=h, json={"vacancy_ids": [with_gaps[0]["vacancy"]["id"]]}).json()
    assert body["stage"] == "skill_levels"
    body = _levels(c, h, body["pending"])
    assert body["stage"] == "identity"
    assert c.post("/api/applications/identity", headers=h, json=IDENTITY).json()["stage"] == "tracking"

    app = c.get("/api/applications", headers=h).json()[0]
    assert app["evidence"]["gaps"]  # la brecha viaja con la postulación...
    plans = [r for r in c.get("/api/reminders", headers=h).json() if r["kind"] == "plan_preparacion"]
    assert plans and app["next_steps"]  # ...y el Seguimiento la convierte en plan de preparación


def test_cannot_apply_until_every_technical_skill_has_level(cv_template):
    c = _client()
    h = _login(c, "niveles")
    if _upload(c, h, cv_template).json()["stage"] == "cv_gaps":
        c.post("/api/onboarding/cv", headers=h, json={"answers": {}})
    ids = [m["vacancy"]["id"] for m in c.post("/api/onboarding/preferences", headers=h, json=PREFS)
           .json()["pending"]["matches"][:1]]
    pending = c.post("/api/applications/approve", headers=h, json={"vacancy_ids": ids}).json()["pending"]
    first = pending["skills"][0]["name"]
    body = c.post("/api/applications/skill-levels", headers=h, json={"levels": {first: "avanzado"}}).json()
    assert body["stage"] == "skill_levels"  # siguen faltando: no deja pasar
    assert first not in {sk["name"] for sk in body["pending"]["skills"]}
    assert _levels(c, h, body["pending"])["stage"] == "identity"
    gaps = {g["field"] for g in c.get("/api/profile", headers=h).json()["cv_gaps"]}
    assert "skill_levels" not in gaps
