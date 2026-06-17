from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import is_request_authenticated
from ..domain.request_settings import settings_from_request
from ..paths import STATIC_DIR, TEMPLATES_DIR

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=TEMPLATES_DIR)

PROTECTED_PAGES = {
    "/": ("pages/index.html", "Ana Sayfa", "dashboard"),
    "/process": ("pages/process.html", "Proses Girisi", "process"),
    "/auxiliary": ("pages/auxiliary.html", "Yardimci Sistemler", "auxiliary"),
    "/amount-control": ("pages/amount_control.html", "Miktar Kontrol", "amount-control"),
    "/reports": ("pages/reports.html", "Senkron & Raporlar", "reports"),
}


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


def protected_page(request: Request, path: str):
    settings = settings_from_request(request)
    if not is_request_authenticated(request, settings):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    template_name, page_title, active_page = PROTECTED_PAGES[path]
    return TEMPLATES.TemplateResponse(
        request,
        template_name,
        {
            "page_title": page_title,
            "active_page": active_page,
        },
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return protected_page(request, "/")


@router.get("/process", response_class=HTMLResponse)
def process(request: Request):
    return protected_page(request, "/process")


@router.get("/auxiliary", response_class=HTMLResponse)
def auxiliary(request: Request):
    return protected_page(request, "/auxiliary")


@router.get("/amount-control", response_class=HTMLResponse)
def amount_control(request: Request):
    return protected_page(request, "/amount-control")


@router.get("/reports", response_class=HTMLResponse)
def reports(request: Request):
    return protected_page(request, "/reports")


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    settings = settings_from_request(request)
    if is_request_authenticated(request, settings):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return TEMPLATES.TemplateResponse(request, "pages/login.html")
