# ADR-0003 — Persistencia: SQLite por defecto, PostgreSQL opcional

**Estado:** aceptada

**Contexto.** Entrega en 2 días, 3 integrantes con equipos distintos; el reto valora PostgreSQL.

**Decisión.** SQLAlchemy con `DATABASE_URL`. Por defecto SQLite (cero instalación); `compose.yaml` levanta
PostgreSQL para quien lo quiera. Los checkpoints de LangGraph se guardan en memoria (`InMemorySaver`);
perfil, matches, postulaciones, recordatorios y trazas se persisten en la BD.

**Consecuencias.** + Todos corren el proyecto en minutos. − Si el backend se reinicia a mitad de una
pausa del grafo, el candidato debe volver a subir el CV (mejora futura: checkpointer en BD).
