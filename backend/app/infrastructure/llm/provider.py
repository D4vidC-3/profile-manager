"""Cadena de proveedores LLM gratuitos con respaldo: gemini -> groq -> mock.

`invoke_structured` intenta cada proveedor en orden y devuelve (resultado, proveedor).
Si ninguno responde (sin keys, sin cuota, sin internet) devuelve (None, "mock") y el
agente usa su lógica de reglas. Así la demo nunca se cae.
"""

from __future__ import annotations

import logging
import re
import time
from typing import TypeVar

from pydantic import BaseModel

from app.config import Settings, get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel):
    provider: str
    duration_ms: int
    errors: list[str] = []


class LLMChain:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._clients: dict[str, object] = {}

    # ------------------------------------------------------------------
    def available(self) -> list[str]:
        """Proveedores configurados (con key) en el orden de la cadena."""
        out = []
        for p in self.settings.provider_chain:
            if p == "gemini" and self.settings.google_api_key:
                out.append(p)
            elif p == "groq" and self.settings.groq_api_key:
                out.append(p)
        return out

    def _client(self, provider: str):
        if provider in self._clients:
            return self._clients[provider]
        s = self.settings
        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI

            client = ChatGoogleGenerativeAI(model=s.gemini_model, google_api_key=s.google_api_key,
                                            temperature=0.1, max_retries=1, timeout=s.llm_timeout_seconds)
        elif provider == "groq":
            from langchain_groq import ChatGroq

            client = ChatGroq(model=s.groq_model, api_key=s.groq_api_key, temperature=0.1,
                              max_retries=1, timeout=s.llm_timeout_seconds)
        else:
            raise ValueError(provider)
        self._clients[provider] = client
        return client

    # ------------------------------------------------------------------
    def invoke_structured(self, schema: type[T], system: str, user: str) -> tuple[T | None, LLMResult]:
        errors: list[str] = []
        for provider in self.available():
            start = time.perf_counter()
            try:
                llm = self._client(provider).with_structured_output(schema)
                result = llm.invoke([("system", system), ("human", user)])
                if isinstance(result, dict):
                    result = schema.model_validate(result)
                if result is None:
                    raise ValueError("respuesta vacía")
                ms = int((time.perf_counter() - start) * 1000)
                return result, LLMResult(provider=provider, duration_ms=ms, errors=errors)
            except Exception as exc:  # cuota, red, JSON inválido... => siguiente proveedor
                # Solo el código y estado HTTP (p. ej. "503 UNAVAILABLE"): nunca contenido del CV
                code = re.search(r"\b([45]\d{2})\b\s*([A-Z_]{4,})?", str(exc))
                detail = f" {code.group(1)} {code.group(2) or ''}".rstrip() if code else ""
                msg = f"{provider}: {type(exc).__name__}{detail}"
                log.warning("Proveedor LLM falló, usando respaldo: %s", msg)
                errors.append(msg)
        return None, LLMResult(provider="mock", duration_ms=0, errors=errors)


_chain: LLMChain | None = None


def get_llm() -> LLMChain:
    global _chain
    if _chain is None:
        _chain = LLMChain()
    return _chain
