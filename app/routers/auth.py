from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..domain.request_settings import settings_from_request
from ..modules.auth.schemas import LoginRequest
from ..modules.auth.service import (
    authenticate_pin,
    default_path_for_role,
    set_session_cookie,
)

router = APIRouter(prefix="/api")


@router.post("/login")
def api_login(payload: LoginRequest, request: Request) -> JSONResponse:
    settings = settings_from_request(request)
    role = authenticate_pin(payload.pin, settings)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN geçersiz.",
        )

    response = JSONResponse(
        {"ok": True, "role": role, "default_path": default_path_for_role(role)}
    )
    set_session_cookie(response, settings, role=role)
    return response
