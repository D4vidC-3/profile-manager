"""Trazabilidad: cada agente registra QUÉ hizo, POR QUÉ, con qué modo (IA o reglas)
y con qué proveedor. Esto alimenta el panel de trazabilidad."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.infrastructure.repositories import Repository

log = logging.getLogger("trace")

AGENTS = {
    "perfil": "Agente de Perfil",
    "vacantes": "Agente de Vacantes",
    "postulacion": "Agente de Postulación",
    "seguimiento": "Agente de Seguimiento",
    "portal": "Portal de empresas (simulado)",
    "candidato": "Candidato",
    "orquestador": "Orquestador",
}


@dataclass
class Tracer:
    repo: Repository
    user_id: int
    run_id: str
    sim_day: int = 0

    def log(self, agent: str, action: str, reason: str, *, mode: str = "rules",
            provider: str | None = None, details: dict | None = None, duration_ms: int = 0) -> None:
        self.repo.add_trace(user_id=self.user_id, run_id=self.run_id, agent=agent, action=action,
                            reason=reason, details=details or {}, mode=mode, provider=provider,
                            duration_ms=duration_ms, sim_day=self.sim_day)
        # Log técnico sin datos personales: solo agente, acción y modo
        log.info("user=%s agent=%s mode=%s action=%s", self.user_id, agent, mode, action)
