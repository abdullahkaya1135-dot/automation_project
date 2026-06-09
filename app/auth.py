import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel

from .config import Settings, get_settings


SESSION_COOKIE_NAME = "process_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


class LoginRequest(BaseModel):
    pin: str


def authenticate_pin(pin: str, settings: Settings) -> bool:
    return secrets.compare_digest(pin.strip(), settings.app_pin)


def _base64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _session_key(settings: Settings) -> bytes:
    return f"process-entry-session:{settings.app_pin}".encode("utf-8")


def _sign(payload: str, settings: Settings) -> str:
    digest = hmac.new(
        _session_key(settings),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _base64_encode(digest)


def create_session_cookie_value(settings: Settings) -> str:
    payload = {
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    encoded_payload = _base64_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    return f"{encoded_payload}.{_sign(encoded_payload, settings)}"


def verify_session_cookie_value(cookie_value: str, settings: Settings) -> bool:
    try:
        encoded_payload, signature = cookie_value.split(".", maxsplit=1)
        expected_signature = _sign(encoded_payload, settings)
        if not secrets.compare_digest(signature, expected_signature):
            return False

        payload: dict[str, Any] = json.loads(_base64_decode(encoded_payload))
        issued_at = int(payload["iat"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False

    age_seconds = int(time.time()) - issued_at
    return -60 <= age_seconds <= SESSION_MAX_AGE_SECONDS


def set_session_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_cookie_value(settings),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def _request_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is not None:
        return settings
    return get_settings()


def is_request_authenticated(
    request: Request,
    settings: Settings | None = None,
) -> bool:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_value:
        return False
    return verify_session_cookie_value(
        cookie_value,
        settings or _request_settings(request),
    )


def require_api_auth(request: Request) -> None:
    if is_request_authenticated(request):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Oturum açmanız gerekiyor.",
    )
