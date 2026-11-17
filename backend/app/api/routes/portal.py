"""Portal de empresas demo: el endpoint público que "recibiría" postulaciones."""

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import limiter
from app.infrastructure.portal import PortalRejected, submit_application

router = APIRouter(prefix="/api/demo-portal", tags=["portal demo"])


@router.post("/apply")
@limiter.limit("30/minute")
def apply(request: Request, form: dict):
    try:
        return submit_application(form)
    except PortalRejected as exc:
        raise HTTPException(422, str(exc)) from exc
