from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import is_request_authenticated
from ..domain.request_settings import settings_from_request
from ..paths import STATIC_DIR, TEMPLATES_DIR

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@router.get("/service-worker.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache",
            "Service-Worker-Allowed": "/",
        },
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    settings = settings_from_request(request)
    if not is_request_authenticated(request, settings):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return TEMPLATES.TemplateResponse(request, "pages/index.html")


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    settings = settings_from_request(request)
    if is_request_authenticated(request, settings):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return TEMPLATES.TemplateResponse(request, "pages/login.html")
