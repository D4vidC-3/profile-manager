# Backlog de producto

Formato: *Como … quiero … para …* · Criterios de aceptación (CA) · Prioridad (MoSCoW) · Estado

| ID | Historia | CA principales | Prioridad | Estado |
|---|---|---|---|---|
| HU-01 | Como candidato quiero subir mi CV para no llenar formularios largos | PDF/TXT ≤5 MB; extrae contacto, experiencia, educación y skills; rechaza archivos inválidos con mensaje claro | Must | Hecho |
| HU-02 | Como candidato quiero que el sistema me diga qué le falta a mi perfil | % de completitud; lista de vacíos; preguntas solo por campos críticos; marca obligatorios | Must | Hecho |
| HU-03 | Como candidato quiero declarar mis expectativas (cargo, ciudad, modalidad, salario, disponibilidad) | Lo declarado tiene prioridad sobre lo inferido; salario en COP normalizado | Must | Hecho |
| HU-04 | Como candidato quiero ver vacantes recomendadas con su explicación | Puntaje 0–100 desglosado; razones y skills faltantes; descartes con motivo en trazabilidad | Must | Hecho |
| HU-05 | Como candidato quiero aprobar a qué vacantes postularme | Nada se postula sin aprobación; ids inválidos se ignoran | Must | Hecho |
| HU-06 | Como candidato quiero que el sistema postule por mí y guarde evidencia | Formulario llenado desde el perfil; comprobante + hash; sin duplicados | Must | Hecho |
| HU-07 | Como candidato quiero un tablero con el estado de mis procesos | Columnas postulado / en revisión / entrevista / descartado; historial por proceso | Must | Hecho |
| HU-08 | Como candidato quiero recordatorios y próximos pasos | Reglas por estado y días; mensaje personalizado con IA o plantilla; marcar como hecho | Must | Hecho |
| HU-09 | Como evaluador quiero ver qué hizo cada agente y por qué | Línea de tiempo filtrable por agente; modo IA/reglas y proveedor; detalles JSON | Must | Hecho |
| HU-10 | Como equipo queremos que la demo funcione sin pagar IA | Cadena Gemini → Groq → reglas; funciona sin keys | Must | Hecho |
| HU-11 | Como candidato quiero iniciar sesión de forma segura | JWT; contraseñas con hash; rate limiting | Should | Hecho |
| HU-12 | Como equipo queremos simular el paso del tiempo para la demo | Botón +3/+7 días; respuestas deterministas; más match ⇒ más entrevistas | Should | Hecho |
| HU-17 | Como candidato quiero confirmar el nivel de mis idiomas con un clic | Escala Básico/Intermedio/Avanzado/Nativo guardada como MCER; certificados (IELTS, TOEFL) convertidos; sugerencias de IA marcadas | Must | Hecho |
| HU-18 | Como candidato quiero corregir lo que el agente entendió de mi CV | Edición por sección; procedencia (CV/IA/editado); lo editado se conserva al subir otro CV; recalcula recomendaciones | Must | Hecho |
| HU-19 | Como candidato quiero que mis preferencias no se mezclen con mi hoja de vida | Dos indicadores (hoja de vida / lo que buscas); formulario "¿Qué estás buscando?" con sectores, jornada, vinculación | Must | Hecho |
| HU-20 | Como recién graduado no quiero que me castiguen por no tener experiencia | Tabla de pesos "primer empleo"; proyectos con evidencia (GitHub verificado) | Must | Hecho |
| HU-21 | Como candidato quiero dar mi documento solo cuando voy a postular | Paso de identidad tras aprobar; datos sensibles opcionales con autorización | Must | Hecho |
| HU-13 | Como candidato quiero que se ingesten vacantes de un scraper controlado | Nueva `VacancySource`; respeta términos y límites | Could | Pendiente |
| HU-14 | Como candidato quiero recibir recordatorios por WhatsApp/correo | Canal de notificación real | Could | Pendiente |
| HU-15 | Como candidato quiero reutilizar respuestas de cuestionarios | Banco de respuestas con trazabilidad | Could | Pendiente |
| HU-16 | Como equipo queremos matching semántico con embeddings | Similaridad complementa el puntaje por reglas | Could | Pendiente |

## Definition of Done
- Código en rama `feat/*` integrado por Pull Request con revisión de otro integrante.
- Pruebas automáticas que cubren el criterio de aceptación; `pytest` y `ruff` en verde en CI.
- Frontend compila (`npm run build`) y lint en verde.
- Decisión registrada en la trazabilidad (si la historia involucra un agente).
- Sin secretos en el repositorio; README actualizado si cambia la instalación o el uso.
