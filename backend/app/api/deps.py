from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.application.services import ProfileManagerService
from app.config import get_settings
from app.infrastructure.security import decode_token

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)
_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: int
    username: str
    role: str


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de autenticación")
    try:
        data = decode_token(cred.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado") from exc
    return CurrentUser(id=int(data["sub"]), username=data["username"], role=data.get("role", "candidate"))


@lru_cache
def get_service() -> ProfileManagerService:
    return ProfileManagerService()
