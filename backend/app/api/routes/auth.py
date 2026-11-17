from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, current_user, get_service, limiter
from app.api.schemas import LoginIn, TokenOut
from app.application.services import ProfileManagerService
from app.infrastructure.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, svc: ProfileManagerService = Depends(get_service)):
    user = svc.repo.get_user(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    return TokenOut(access_token=create_token(user.id, user.username, user.role), username=user.username)


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: LoginIn, svc: ProfileManagerService = Depends(get_service)):
    if svc.repo.get_user(body.username):
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario ya existe")
    user = svc.repo.create_user(body.username, hash_password(body.password))
    return TokenOut(access_token=create_token(user.id, user.username, user.role), username=user.username)


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}
