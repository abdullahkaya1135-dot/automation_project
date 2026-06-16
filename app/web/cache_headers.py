from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from .workspaces import WORKSPACES

UI_NO_STORE_PATHS = frozenset(
    {
        "/",
        "/login",
        *(workspace.path for workspace in WORKSPACES),
    }
)


async def apply_cache_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    if request.url.path in UI_NO_STORE_PATHS:
        response.headers["Cache-Control"] = "no-store, max-age=0"
    elif request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response
