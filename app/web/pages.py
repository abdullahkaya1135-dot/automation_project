import json
from dataclasses import dataclass

from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..core.paths import STATIC_DIR, TEMPLATES_DIR
from ..core.security import is_request_authenticated
from ..domain.request_settings import settings_from_request

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=TEMPLATES_DIR)

MANIFEST_URL = "/manifest.webmanifest"
SERVICE_WORKER_URL = "/service-worker.js"
STATIC_URL_PREFIX = "/static/"
STATIC_ASSET_VERSION = "20260626-breakdowns-paper-fields"
SERVICE_WORKER_CACHE_NAME = f"process-offline-shell-{STATIC_ASSET_VERSION}"


@dataclass(frozen=True)
class PageRoute:
    path: str
    template_name: str
    title: str
    active_page: str


DASHBOARD_PAGE = PageRoute("/", "pages/index.html", "Ana Sayfa", "dashboard")
PROCESS_PAGE = PageRoute("/process", "pages/process.html", "Proses Girisi", "process")
AUXILIARY_PAGE = PageRoute(
    "/auxiliary",
    "pages/auxiliary.html",
    "Yardimci Sistemler",
    "auxiliary",
)
AMOUNT_CONTROL_PAGE = PageRoute(
    "/amount-control",
    "pages/amount_control.html",
    "Miktar Kontrol",
    "amount-control",
)
BREAKDOWNS_PAGE = PageRoute(
    "/breakdowns",
    "pages/breakdowns.html",
    "Ariza Kaydi",
    "breakdowns",
)
REPORTS_PAGE = PageRoute("/reports", "pages/reports.html", "Senkron & Raporlar", "reports")
LOGIN_PAGE_PATH = "/login"

PROTECTED_PAGE_ROUTES = (
    DASHBOARD_PAGE,
    PROCESS_PAGE,
    AUXILIARY_PAGE,
    AMOUNT_CONTROL_PAGE,
    BREAKDOWNS_PAGE,
    REPORTS_PAGE,
)
PROTECTED_PAGE_PATHS = tuple(route.path for route in PROTECTED_PAGE_ROUTES)
NO_CACHE_PAGE_PATHS = (*PROTECTED_PAGE_PATHS, LOGIN_PAGE_PATH)
APP_ROUTE_URLS = NO_CACHE_PAGE_PATHS
PROTECTED_PAGES = {route.path: route for route in PROTECTED_PAGE_ROUTES}


def static_asset_url(path: str) -> str:
    return f"{STATIC_URL_PREFIX}{path}?v={STATIC_ASSET_VERSION}"


def _static_js_module_asset_urls() -> tuple[str, ...]:
    modules_dir = STATIC_DIR / "js" / "modules"
    return tuple(
        static_asset_url(module_path.relative_to(STATIC_DIR).as_posix())
        for module_path in sorted(modules_dir.glob("*.js"))
    )


APP_STYLESHEET_URL = static_asset_url("css/app.css")
APP_SCRIPT_URL = static_asset_url("js/app.js")
SHARED_PAGE_ASSET_URLS = (
    APP_STYLESHEET_URL,
    APP_SCRIPT_URL,
)
APP_SHELL_URLS = (
    MANIFEST_URL,
    APP_STYLESHEET_URL,
    static_asset_url("js/api.js"),
    APP_SCRIPT_URL,
    *_static_js_module_asset_urls(),
)

TEMPLATES.env.globals.update(
    app_script_url=APP_SCRIPT_URL,
    app_stylesheet_url=APP_STYLESHEET_URL,
)


@router.get(MANIFEST_URL, include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@router.get(SERVICE_WORKER_URL, include_in_schema=False)
def service_worker() -> Response:
    source = (STATIC_DIR / "service-worker.js").read_text(encoding="utf-8")
    route_urls = json.dumps(APP_ROUTE_URLS, indent=2)
    shell_urls = json.dumps(APP_SHELL_URLS, indent=2)
    cache_name = json.dumps(SERVICE_WORKER_CACHE_NAME)
    return Response(
        "\n".join(
            (
                f"const APP_ROUTE_URLS = {route_urls};",
                f"const APP_SHELL_URLS = {shell_urls};",
                f"const CACHE_NAME = {cache_name};",
                "",
                source,
            )
        ),
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache",
            "Service-Worker-Allowed": "/",
        },
    )


def protected_page(request: Request, path: str):
    settings = settings_from_request(request)
    if not is_request_authenticated(request, settings):
        return RedirectResponse(LOGIN_PAGE_PATH, status_code=status.HTTP_303_SEE_OTHER)
    page = PROTECTED_PAGES[path]
    return TEMPLATES.TemplateResponse(
        request,
        page.template_name,
        {
            "page_title": page.title,
            "active_page": page.active_page,
        },
    )


@router.get(DASHBOARD_PAGE.path, response_class=HTMLResponse)
def index(request: Request):
    return protected_page(request, DASHBOARD_PAGE.path)


@router.get(PROCESS_PAGE.path, response_class=HTMLResponse)
def process(request: Request):
    return protected_page(request, PROCESS_PAGE.path)


@router.get(AUXILIARY_PAGE.path, response_class=HTMLResponse)
def auxiliary(request: Request):
    return protected_page(request, AUXILIARY_PAGE.path)


@router.get(AMOUNT_CONTROL_PAGE.path, response_class=HTMLResponse)
def amount_control(request: Request):
    return protected_page(request, AMOUNT_CONTROL_PAGE.path)


@router.get(BREAKDOWNS_PAGE.path, response_class=HTMLResponse)
def breakdowns(request: Request):
    return protected_page(request, BREAKDOWNS_PAGE.path)


@router.get(REPORTS_PAGE.path, response_class=HTMLResponse)
def reports(request: Request):
    return protected_page(request, REPORTS_PAGE.path)


@router.get(LOGIN_PAGE_PATH, response_class=HTMLResponse)
def login(request: Request):
    settings = settings_from_request(request)
    if is_request_authenticated(request, settings):
        return RedirectResponse(DASHBOARD_PAGE.path, status_code=status.HTTP_303_SEE_OTHER)
    return TEMPLATES.TemplateResponse(request, "pages/login.html")
