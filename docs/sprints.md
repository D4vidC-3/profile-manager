# Sprints y rituales (Scrum ligero)

Equipo de 3 personas. Roles rotativos: Product Owner / Scrum Master / Desarrollador.

## Sprint 1 — “Sistema agéntico completo”
**Objetivo:** el flujo onboarding → recomendaciones → postulación → seguimiento funciona de punta a punta,
con IA gratuita y respaldo por reglas, y es demostrable.

| Historia | Responsable sugerido |
|---|---|
| HU-01, HU-02, HU-03, HU-10 (Agente de Perfil + capa LLM) | Integrante 1 |
| HU-04, HU-05, HU-06 (Vacantes + Postulación) | Integrante 2 |
| HU-07, HU-08, HU-12 (Seguimiento + simulación) | Integrante 2 |
| HU-09, HU-11 (Frontend, trazabilidad, auth) | Integrante 3 |

### Planning
- Se eligió la Idea 2 (arquitectura agéntica). Decisiones: híbrido reglas+IA, IA gratuita con respaldo,
  SQLite por defecto (ADR-0001..0003).

### Daily (plantilla)
| Fecha | Integrante | Ayer | Hoy | Bloqueos |
|---|---|---|---|---|
| | | | | |

### Review
- Demo del guion del README. Feedback: _(completar)_

### Retrospectiva
| Qué salió bien | Qué mejorar | Acción |
|---|---|---|
| | | |

## Sprint 2 — Mejoras (propuesto tras la review)
Candidatas: HU-13 scraper controlado, HU-16 embeddings, persistir checkpoints del grafo en BD,
pruebas e2e del frontend, notificaciones reales.
