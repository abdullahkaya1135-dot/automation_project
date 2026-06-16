import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Request, Response

from ...config import Settings, get_settings
from .roles import KNOWN_ROLES, ROLE_ADMIN

SESSION_COOKIE_NAME = "process_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


def base64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def base64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def session_key(settings: Settings) -> bytes:
    return f"process-entry-session:{settings.session_secret}".encode()


def sign(payload: str, settings: Settings) -> str:
    digest = hmac.new(
        session_key(settings),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64_encode(digest)


def create_session_cookie_value(
    settings: Settings,
    *,
    role: str = ROLE_ADMIN,
) -> str:
    payload = {
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
        "role": role if role in KNOWN_ROLES else ROLE_ADMIN,
    }
    encoded_payload = base64_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    return f"{encoded_payload}.{sign(encoded_payload, settings)}"


def session_payload_from_cookie(
    cookie_value: str,
    settings: Settings,
) -> dict[str, Any] | None:
    try:
        encoded_payload, signature = cookie_value.split(".", maxsplit=1)
        expected_signature = sign(encoded_payload, settings)
        if not secrets.compare_digest(signature, expected_signature):
            return None

        payload: dict[str, Any] = json.loads(base64_decode(encoded_payload))
        issued_at = int(payload["iat"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    age_seconds = int(time.time()) - issued_at
    if not -60 <= age_seconds <= SESSION_MAX_AGE_SECONDS:
        return None
    if payload.get("role") not in KNOWN_ROLES:
        payload["role"] = ROLE_ADMIN
    return payload


def verify_session_cookie_value(cookie_value: str, settings: Settings) -> bool:
    return session_payload_from_cookie(cookie_value, settings) is not None


def set_session_cookie(
    response: Response,
    settings: Settings,
    *,
    role: str = ROLE_ADMIN,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_cookie_value(settings, role=role),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def request_settings(request: Request) -> Settings:
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
        settings or request_settings(request),
    )


def request_role(
    request: Request,
    settings: Settings | None = None,
) -> str | None:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_value:
        return None
    payload = session_payload_from_cookie(
        cookie_value,
        settings or request_settings(request),
    )
    if payload is None:
        return None
    role = payload.get("role")
    if isinstance(role, str) and role in KNOWN_ROLES:
        return role
    return None
