from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..domain.request_settings import settings_from_request
from ..paths import STATIC_DIR, TEMPLATES_DIR
from ..web.permissions import (
    WorkspaceForbiddenError,
    authenticated_default_path,
    workspace_template_context,
)
from ..web.workspaces import workspace_by_page_id

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
    default_path = authenticated_default_path(request, settings)
    if default_path is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(default_path, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    settings = settings_from_request(request)
    default_path = authenticated_default_path(request, settings)
    if default_path is not None:
        return RedirectResponse(default_path, status_code=status.HTTP_303_SEE_OTHER)
    return TEMPLATES.TemplateResponse(request, "pages/login.html")


@router.get("/operator", response_class=HTMLResponse)
def operator_workspace(request: Request):
    return _workspace_response(
        request,
        "operator",
    )


@router.get("/utility", response_class=HTMLResponse)
def utility_workspace(request: Request):
    return _workspace_response(
        request,
        "utility",
    )


@router.get("/supervisor", response_class=HTMLResponse)
def supervisor_workspace(request: Request):
    return _workspace_response(
        request,
        "supervisor",
    )


@router.get("/planning", response_class=HTMLResponse)
def planning_workspace(request: Request):
    return _workspace_response(
        request,
        "planning",
    )


def _workspace_response(
    request: Request,
    page_id: str,
):
    settings = settings_from_request(request)
    workspace = workspace_by_page_id(page_id)
    try:
        context = workspace_template_context(
            request,
            settings,
            workspace=workspace,
        )
    except WorkspaceForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu sayfa icin yetkiniz yok.",
        ) from exc

    if context is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    return TEMPLATES.TemplateResponse(
        request,
        workspace.template_name,
        context,
    )
