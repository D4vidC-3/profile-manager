# Profile Manager — Arquitectura agéntica con LangGraph

MVP del reto **Profile Manager (Magneto · EAFIT)**, Idea 2: un conjunto de **agentes especializados**
orquestados con **LangGraph** que gestionan la búsqueda de empleo del candidato, con un **panel de
trazabilidad** que muestra qué hizo cada agente y **por qué**.

> “Dame tu hoja de vida y tus expectativas; nosotros gestionamos tu búsqueda.”

Flujo principal: **onboarding → recomendaciones → acciones → tablero de proceso**.

| Agente | Qué hace | Modo |
|---|---|---|
| **Perfil** | Estructura el CV (PDF/TXT), detecta vacíos y pregunta solo lo necesario | Híbrido: reglas + IA |
| **Vacantes** | Ingesta el dataset, normaliza (ciudad, modalidad, salario COP, skills), filtra y rankea con puntaje explicable | Reglas |
| **Postulación** | Con aprobación del candidato, llena el formulario del portal demo, guarda evidencia y estado | Reglas |
| **Seguimiento** | Reglas deciden cuándo recordar; la IA redacta mensajes y próximos pasos personalizados | Híbrido: reglas + IA |

La IA es **100% gratuita** y tiene respaldo automático: **Gemini → Groq → solo reglas**. Sin API keys
la aplicación funciona completa en modo reglas.

---

## Requisitos

| Herramienta | Versión | Descarga |
|---|---|---|
| Python | 3.11, 3.12 o 3.13 (probado también con 3.14) | https://www.python.org/downloads/ — en Windows marca **"Add python.exe to PATH"** |
| Node.js | 20 o 22 (LTS) | https://nodejs.org |
| Git | cualquiera reciente | https://git-scm.com |

Opcional: API keys **gratuitas** de [Google AI Studio](https://aistudio.google.com/apikey) y/o
[Groq](https://console.groq.com/keys). **Sin keys la aplicación funciona completa en modo reglas.**
No se necesita base de datos instalada (usa SQLite por defecto).

## Puesta en marcha

Se usan **dos terminales**: una para el backend (API + agentes) y otra para el frontend (página web).

### 1. Clonar y configurar (una sola vez)

**Linux / macOS**
```bash
git clone https://github.com/D4vidC-3/profile-manager.git
cd profile-manager
cp .env.example .env          # abre .env y pega tus API keys (opcional)
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/D4vidC-3/profile-manager.git
cd profile-manager
Copy-Item .env.example .env   # abre .env con el Bloc de notas y pega tus API keys (opcional)
```

### 2. Backend — terminal 1

**Linux / macOS**
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Windows (PowerShell)**
```powershell
cd backend
py -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Listo cuando veas `Uvicorn running on http://127.0.0.1:8000`. Documentación de la API: http://localhost:8000/docs

> Usamos el ejecutable del entorno virtual directamente (`.venv/bin/...` o `.venv\Scripts\...`), así no hace
> falta "activar" el entorno ni cambiar la política de ejecución de scripts de PowerShell.
> Si `py` no existe en Windows, usa `python` en su lugar.

### 3. Frontend — terminal 2 (igual en Linux y Windows)

```bash
cd frontend
npm install
npm run dev
```

Abre **http://localhost:3000** e ingresa con usuario **`demo`** y contraseña **`demo1234`**.

### Detener, reiniciar y problemas comunes

| Situación | Linux / macOS | Windows (PowerShell) |
|---|---|---|
| Detener un servidor | `Ctrl + C` | `Ctrl + C` |
| Empezar con datos limpios | `rm backend/profile_manager.db` | `Remove-Item backend\profile_manager.db` |
| Puerto 8000 ocupado | `fuser -k 8000/tcp` | `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess \| Stop-Process` |
| La página dice "No se pudo conectar con el backend" | El backend (terminal 1) no está corriendo | Igual |
| En el log aparece `solo reglas (mock)` | El `.env` no está en la carpeta raíz `profile-manager/` o no tiene keys | Igual |
| "La sesión del flujo expiró" | El backend se reinició a mitad del onboarding: vuelve a subir el CV | Igual |
| Error 500 en el frontend tras `npm run build` | Detén `npm run dev`, borra `frontend/.next` y vuelve a `npm run dev` | Igual (`Remove-Item -Recurse frontend\.next`) |

### Guion de demo (5 minutos)
1. Ingresa con `demo / demo1234`.
2. **Perfil → sube tu hoja de vida**: `samples/1/05_CV_Incompleto_Soporte_TI.pdf` (incompleta). El Agente de
   Perfil pide solo lo que falta en la **hoja de vida** (teléfono, habilidades, nivel de idiomas).
   - Alternativa: `samples/cv_plantilla_laura.pdf` (plantilla completa, proyecto con GitHub verificado).
3. **¿Qué estás buscando?**: cargos, sectores, modalidad, jornada, salario… (no vienen del CV; la IA sugiere).
4. **Recomendaciones**: puntaje desglosado y "¿por qué?". Prueba **✏️ Editar** una sección del perfil:
   las recomendaciones se recalculan solas. Aprueba 1–3.
5. **Identidad**: documento y nombres/apellidos se piden solo ahora, al postular.
6. **Tablero**: evidencia de cada postulación; **Simular +3 días** → respuestas de empresas y recordatorios.
7. **Trazabilidad**: qué hizo cada agente, por qué, y si usó **IA** (qué proveedor) o **reglas**.

### ¿Qué cuenta como hoja de vida completa?
| Bloque | Con experiencia | Primer empleo |
|---|---|---|
| Nombre, correo, teléfono, ciudad | 35 | 35 |
| Titular + resumen | 10 | 10 |
| Experiencia laboral | 20 | 0 |
| Proyectos / prácticas / voluntariado | 0 (suman en el matching) | 8 |
| Educación | 15 | 22 |
| Habilidades (≥3 parcial, ≥5 completo) | 10 | 15 |
| Idiomas con nivel · cursos · enlaces | 5 · 3 · 2 | 5 · 3 · 2 |

Fuera del CV: **preferencias** (formulario propio), **documento** (al postular) y **datos sensibles**
(opcionales, con autorización, nunca usados en el puntaje). Formato recomendado: `samples/plantilla_hoja_de_vida.pdf`.

## Pruebas y calidad

```bash
# Linux / macOS
cd backend && .venv/bin/pytest -q && .venv/bin/ruff check app tests scripts
# Windows (PowerShell)
cd backend; .venv\Scripts\pytest -q; .venv\Scripts\ruff check app tests scripts
# Frontend (ambos)
cd frontend && npm run lint && npm run build
```
Las pruebas corren siempre sin IA (modo reglas) y con una base de datos temporal.
CI (GitHub Actions) ejecuta todo lo anterior en cada push/PR: `.github/workflows/ci.yml`.

## Estructura

```
backend/
  app/domain/          Entidades y reglas puras (completitud, scoring, proceso, normalizadores CO)
  app/agents/          Los 4 agentes + grafo LangGraph + trazabilidad
  app/application/     Casos de uso (puente API ↔ grafo)
  app/infrastructure/  BD (SQLAlchemy), LLM (cadena gratuita), lector de CV, dataset, portal demo, seguridad
  app/api/             Endpoints FastAPI (OpenAPI en /docs)
  tests/               Pruebas unitarias e integración
  scripts/             Generador del dataset y de PDFs de ejemplo
frontend/              Next.js + Tailwind: login, perfil, recomendaciones, tablero, trazabilidad
samples/               CVs ficticios (plantilla recomendada y CV libre)
docs/                  Arquitectura, backlog, sprints, decisiones (ADR)
```

## Decisiones y trade-offs (resumen)

- **Híbrido reglas + IA** ([ADR-0002](docs/adr/0002-hibrido-reglas-ia.md)): datos exactos (email, teléfono, cédula) y detección de vacíos con reglas; la IA solo para lo semántico. Más barato, explicable y robusto.
- **IA gratuita con respaldo** ([ADR-0001](docs/adr/0001-llm-gratuito-con-respaldo.md)): ningún proveedor es punto único de falla.
- **Human-in-the-loop**: el sistema nunca postula sin aprobación (`interrupt()` de LangGraph).
- **SQLite por defecto, PostgreSQL opcional** ([ADR-0003](docs/adr/0003-persistencia.md)).
- **Datos simulados**: vacantes y empresas son ficticias (no hay acceso a datos reales de Magneto, §6.1 del reto). Las respuestas de las empresas se simulan de forma determinista con un reloj de demo.

Limitaciones conocidas: el estado de pausa del grafo vive en memoria (si el backend se reinicia a mitad
del onboarding hay que volver a subir el CV); no hay scraper real (la interfaz `VacancySource` lo permite).

## Seguridad (OWASP básico)
JWT + contraseñas con PBKDF2 · validación Pydantic y lista blanca de campos · límite de tamaño y tipo de
archivo · rate limiting (slowapi) en login, registro, carga de CV y portal · secretos solo en `.env` ·
logs sin datos personales (solo ids, agente y acción) · CORS restringido. Más en [docs/arquitectura.md](docs/arquitectura.md).

## Equipo y proceso
Scrum ligero: ver [docs/backlog.md](docs/backlog.md) y [docs/sprints.md](docs/sprints.md).
Trabajo en ramas `feat/*` con Pull Requests revisados por otro integrante antes de integrar a `main`.
