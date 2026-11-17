"""Punto de entrada FastAPI. Documentación OpenAPI en /docs."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import get_service, limiter
from app.api.routes import auth, candidate, portal
from app.config import get_settings
from app.infrastructure.db import init_db
from app.infrastructure.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    init_db()
    repo = get_service().repo
    if repo.get_user(s.demo_username) is None:
        repo.create_user(s.demo_username, hash_password(s.demo_password))
        log.info("Usuario demo creado: %s", s.demo_username)
    if s.jwt_secret == "cambia-esto-en-.env":
        log.warning("JWT_SECRET por defecto: define uno propio en .env")
    log.info("Proveedores de IA activos: %s", get_service().llm.available() or ["solo reglas (mock)"])
    yield


app = FastAPI(
    title="Profile Manager API",
    version="1.0.0",
    description="MVP agéntico (LangGraph) del reto Profile Manager - Magneto/EAFIT. "
                "Agentes: Perfil, Vacantes, Postulación y Seguimiento, con trazabilidad.",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH"], allow_headers=["Authorization", "Content-Type"])
app.include_router(auth.router)
app.include_router(candidate.router)
app.include_router(portal.router)


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok", "llm": get_service().llm.available() or ["mock"]}
