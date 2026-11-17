# ADR-0002 — Agentes híbridos: reglas + IA

**Estado:** aceptada

**Contexto.** Una IA puede inventar datos y consume cuota; las reglas son exactas pero frágiles con CVs
de formato libre.

**Decisión.**
- Perfil: regex para datos exactos (email, teléfono, cédula, LinkedIn), diccionario de skills con sinónimos,
  cortes por secciones; la IA estructura experiencia, educación y nivel. Los datos exactos de reglas tienen
  prioridad. La **detección de vacíos es siempre por reglas** (determinista y explicable).
- Vacantes y Postulación: solo reglas (scoring explicable; la acción no requiere IA).
- Seguimiento: las reglas deciden **cuándo** y **qué** recordar; la IA redacta **cómo**.
- Se ofrece una plantilla de CV recomendada con la que las reglas extraen casi todo.

**Consecuencias.** + Explicable, barato y robusto (si la IA falla el agente sigue). − Más código que un
enfoque “todo IA”; las reglas requieren mantenimiento del catálogo de skills y ciudades.
