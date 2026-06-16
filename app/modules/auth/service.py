from fastapi import HTTPException, Request, status

from .roles import KNOWN_ROLES as KNOWN_ROLES
from .roles import ROLE_ADMIN as ROLE_ADMIN
from .roles import ROLE_DEFAULT_PATHS as ROLE_DEFAULT_PATHS
from .roles import ROLE_LABELS as ROLE_LABELS
from .roles import ROLE_OPERATOR as ROLE_OPERATOR
from .roles import ROLE_PLANNING as ROLE_PLANNING
from .roles import ROLE_SUPERVISOR as ROLE_SUPERVISOR
from .roles import ROLE_UTILITY as ROLE_UTILITY
from .roles import authenticate_pin as authenticate_pin
from .roles import default_path_for_role as default_path_for_role
from .roles import role_pins as role_pins
from .session import SESSION_COOKIE_NAME as SESSION_COOKIE_NAME
from .session import SESSION_MAX_AGE_SECONDS as SESSION_MAX_AGE_SECONDS
from .session import create_session_cookie_value as create_session_cookie_value
from .session import is_request_authenticated as is_request_authenticated
from .session import request_role as request_role
from .session import session_payload_from_cookie as session_payload_from_cookie
from .session import set_session_cookie as set_session_cookie
from .session import verify_session_cookie_value as verify_session_cookie_value


def require_api_auth(request: Request) -> None:
    if is_request_authenticated(request):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Oturum a\u00e7man\u0131z gerekiyor.",
    )


__all__ = [
    "KNOWN_ROLES",
    "ROLE_ADMIN",
    "ROLE_DEFAULT_PATHS",
    "ROLE_LABELS",
    "ROLE_OPERATOR",
    "ROLE_PLANNING",
    "ROLE_SUPERVISOR",
    "ROLE_UTILITY",
    "SESSION_COOKIE_NAME",
    "SESSION_MAX_AGE_SECONDS",
    "authenticate_pin",
    "create_session_cookie_value",
    "default_path_for_role",
    "is_request_authenticated",
    "request_role",
    "require_api_auth",
    "role_pins",
    "session_payload_from_cookie",
    "set_session_cookie",
    "verify_session_cookie_value",
]
