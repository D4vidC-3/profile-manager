"""Configuración central leída de variables de entorno / archivo .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- IA (cadena gratuita con respaldo) ---
    # Orden de proveedores separados por coma. "mock" = solo reglas, sin IA.
    llm_providers: str = "gemini,groq,mock"
    google_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 40.0

    # --- Persistencia ---
    database_url: str = f"sqlite:///{BASE_DIR / 'profile_manager.db'}"

    # --- Seguridad ---
    jwt_secret: str = "cambia-esto-en-.env"
    jwt_expire_minutes: int = 480
    demo_username: str = "demo"
    demo_password: str = "demo1234"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_cv_bytes: int = 5 * 1024 * 1024
    rate_limit_enabled: bool = True  # se desactiva solo en las pruebas automáticas

    # --- Verificación de repositorios de proyectos (API pública de GitHub, sin key) ---
    verify_github: bool = True

    # --- Reglas de negocio ---
    match_threshold: float = 45.0
    max_matches: int = 10

    @property
    def provider_chain(self) -> list[str]:
        return [p.strip().lower() for p in self.llm_providers.split(",") if p.strip()]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
