# ADR-0001 — IA gratuita con cadena de respaldo

**Estado:** aceptada

**Contexto.** Proyecto académico sin presupuesto. Los planes gratuitos tienen límites de cuota y pueden
fallar; la demo no puede depender de un solo proveedor ni de internet.

**Decisión.** Capa `LLMChain` que intenta los proveedores en orden configurable (`LLM_PROVIDERS`):
Gemini (Google AI Studio) → Groq → modo reglas. Se usa salida estructurada (Pydantic) para que la
respuesta sea validable. Solo 2 agentes usan IA y el de Seguimiento personaliza todos los recordatorios en
un único llamado para ahorrar cuota.

**Consecuencias.** + Costo cero, sin punto único de falla, demo garantizada. − Calidad variable entre
proveedores; en el plan gratuito el proveedor puede usar los datos para entrenar ⇒ usar solo CVs ficticios.
