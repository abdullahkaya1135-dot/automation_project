from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..auth import LoginRequest, authenticate_pin, set_session_cookie
from ..domain.request_settings import settings_from_request

router = APIRouter(prefix="/api")


@router.post("/login")
def api_login(payload: LoginRequest, request: Request) -> JSONResponse:
    settings = settings_from_request(request)
    if not authenticate_pin(payload.pin, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN geçersiz.",
        )

    response = JSONResponse({"ok": True})
    set_session_cookie(response, settings)
    return response
