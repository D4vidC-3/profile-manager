"""Verificación ligera de proyectos con enlace a GitHub (API pública, sin API key).

No prueba que el candidato sea el autor: solo que el repositorio existe y qué lenguajes usa.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.config import get_settings
from app.domain.models import Project
from app.domain.skills import normalize_skill

log = logging.getLogger(__name__)
REPO_RE = re.compile(r"github\.com/([\w-]+)/([\w.-]+)", re.I)


def verify_project(pr: Project, client: httpx.Client | None = None) -> Project:
    pr = pr.model_copy()
    m = REPO_RE.search(pr.url or "")
    if not m or not get_settings().verify_github:
        return pr
    owner, repo = m.group(1), m.group(2).removesuffix(".git")
    try:
        c = client or httpx.Client(timeout=6, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "profile-manager-demo"})
        r = c.get(f"https://api.github.com/repos/{owner}/{repo}/languages")
    except httpx.HTTPError as exc:
        pr.note = f"No se pudo consultar GitHub ({type(exc).__name__})"
        return pr
    if r.status_code != 200:
        pr.note = ("El repositorio no existe o es privado" if r.status_code == 404
                   else f"GitHub respondió {r.status_code}")
        return pr
    langs = [normalize_skill(k) for k in r.json().keys()]
    pr.verified_languages = langs
    declared = {t.lower() for t in pr.technologies}
    if not declared or declared & {lang.lower() for lang in langs} or not langs:
        pr.evidence = "verificado"
        pr.note = f"Repositorio público encontrado. Lenguajes: {', '.join(langs) or 'sin código detectado'}"
    else:
        pr.note = f"El repositorio existe pero sus lenguajes ({', '.join(langs)}) no coinciden con lo declarado"
    return pr
