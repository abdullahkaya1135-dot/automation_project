from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .auth import (
    LoginRequest,
    authenticate_pin,
    is_request_authenticated,
    require_api_auth,
    set_session_cookie,
)
from .config import Settings, get_settings
from .cycle_report_service import (
    CycleReportError,
    NoTodayRowsError,
    create_cycle_report,
)
from .database import commit_session, create_session, init_db, sqlite_health
from .excel_service import ENTRY_FIELD_NAMES, check_excel_reachable
from .models import (
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUSES,
    Entry,
    TourContext,
    utc_now,
)
from .schemas import TourContextCreate
from .shop_order_source import shop_order_source_payload
from .sync_service import (
    attempt_excel_append,
    latest_sync_error,
    latest_tour_context,
    retry_unsynced_entries,
    serialize_entry,
    serialize_tour_context,
)

APP_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=APP_DIR / "templates")
DISPLAY_DATE_FORMAT = "%d.%m.%Y"
SHIFT_OPTIONS = ("24.00-08.00", "08.00-16.00", "16.00-24.00")
SHIFT_CHIEF_OPTIONS = ("Selman", "Serkan", "Hakan")
FIXED_TIMEZONE_OFFSETS = {
    "Europe/Istanbul": timezone(timedelta(hours=3), "Europe/Istanbul"),
}
public_api_router = APIRouter(prefix="/api")
api_router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


def _settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
        request.app.state.settings = settings
        init_db(settings)
    return settings


def _bootstrap_payload(settings: Settings) -> dict[str, Any]:
    excel = check_excel_reachable(settings)
    return {
        "excel": {
            "available": excel.available,
            "last_error": excel.error or None,
        },
        "shop_order_source": shop_order_source_payload(
            settings.shop_order_source_path,
        ),
    }


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    )


def _required_text(value: Any, field_name: str, max_length: int) -> str:
    text = str(value).strip()
    if not text:
        raise _validation_error(f"{field_name} zorunludur.")
    if len(text) > max_length:
        raise _validation_error(
            f"{field_name} en fazla {max_length} karakter olabilir."
        )
    return text


def _shift_chief(value: Any) -> str:
    text = _required_text(value, "vardiya amiri", 255)
    for option in SHIFT_CHIEF_OPTIONS:
        if text.casefold() == option.casefold():
            return option
    raise _validation_error(
        "vardiya amiri "
        + ", ".join(SHIFT_CHIEF_OPTIONS)
        + " seçeneklerinden biri olmalıdır."
    )


def _recorded_date(value: Date) -> str:
    return value.strftime(DISPLAY_DATE_FORMAT)


def _recorded_date_text(value: str) -> str:
    try:
        return _recorded_date(Date.fromisoformat(value))
    except ValueError:
        return value


def _request_timezone(settings: Settings):
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        if settings.timezone in FIXED_TIMEZONE_OFFSETS:
            return FIXED_TIMEZONE_OFFSETS[settings.timezone]
        local_timezone = datetime.now().astimezone().tzinfo
        return local_timezone or timezone.utc


def _request_datetime(settings: Settings) -> datetime:
    return datetime.now(_request_timezone(settings))


def _shift_for_request_time(value: datetime) -> str:
    if value.hour < 8:
        return SHIFT_OPTIONS[0]
    if value.hour < 16:
        return SHIFT_OPTIONS[1]
    return SHIFT_OPTIONS[2]


def _automatic_tour_timing(settings: Settings) -> dict[str, str]:
    request_time = _request_datetime(settings)
    return {
        "date": _recorded_date(request_time.date()),
        "shift": _shift_for_request_time(request_time),
        "timezone": settings.timezone,
        "generated_at": request_time.isoformat(timespec="seconds"),
    }


def _optional_text(
    value: Any,
    field_name: str,
    max_length: int | None = None,
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length is not None and len(text) > max_length:
        raise _validation_error(
            f"{field_name} en fazla {max_length} karakter olabilir."
        )
    return text


def _entry_payload_from_body(body: dict[str, Any]) -> dict[str, str | None]:
    raw_payload = body.get("payload", {})
    if raw_payload is None:
        raw_payload = {}
    if not isinstance(raw_payload, dict):
        raise _validation_error("payload bir nesne olmalıdır.")

    payload = {
        field_name: _optional_text(raw_payload.get(field_name), field_name)
        for field_name in ENTRY_FIELD_NAMES
    }
    for field_name in ENTRY_FIELD_NAMES:
        if field_name in body:
            payload[field_name] = _optional_text(body.get(field_name), field_name)
    return payload


def _tour_context_id_from_body(body: dict[str, Any]) -> int:
    raw_context_id = body.get("tour_context_id")
    if raw_context_id is None:
        raise _validation_error("tour_context_id zorunludur.")
    try:
        context_id = int(raw_context_id)
    except (TypeError, ValueError) as exc:
        raise _validation_error("tour_context_id tam sayı olmalıdır.") from exc
    if context_id < 1:
        raise _validation_error("tour_context_id pozitif tam sayı olmalıdır.")
    return context_id


def _combined_entry_payload(
    context: TourContext,
    body: dict[str, Any],
) -> dict[str, str | None]:
    payload = _entry_payload_from_body(body)
    payload.update(
        {
            "col_a": _recorded_date_text(context.date),
            "col_b": context.ambient_temp,
            "col_c": context.production_engineer,
            "col_d": context.shift_chief,
            "col_e": context.shift,
        }
    )

    required_fields = {
        "col_f": "makine",
        "col_g": "iş emri",
    }
    missing = [
        label
        for field_name, label in required_fields.items()
        if not payload.get(field_name)
    ]
    if missing:
        raise _validation_error(
            "Eksik zorunlu kayıt alanı/alanları: " + ", ".join(missing)
        )
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    init_db(settings)
    yield


@public_api_router.post("/login")
def api_login(payload: LoginRequest, request: Request) -> JSONResponse:
    settings = _settings(request)
    if not authenticate_pin(payload.pin, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN geçersiz.",
        )

    response = JSONResponse({"ok": True})
    set_session_cookie(response, settings)
    return response


@api_router.get("/bootstrap")
def bootstrap(request: Request) -> dict[str, Any]:
    settings = _settings(request)
    payload = _bootstrap_payload(settings)
    payload["current_tour_timing"] = _automatic_tour_timing(settings)
    with create_session(settings) as session:
        payload["latest_tour_context"] = serialize_tour_context(
            latest_tour_context(session)
        )
        payload["last_sync_error"] = latest_sync_error(session)
    return payload


@api_router.get("/tour-context/defaults")
def tour_context_defaults(request: Request) -> dict[str, str]:
    return _automatic_tour_timing(_settings(request))


@api_router.post("/tour-context", status_code=status.HTTP_201_CREATED)
def create_tour_context(
    payload: TourContextCreate,
    request: Request,
) -> dict[str, Any]:
    settings = _settings(request)
    automatic_timing = _automatic_tour_timing(settings)
    context = TourContext(
        date=automatic_timing["date"],
        ambient_temp=_required_text(payload.ambient_temp, "ortam sıcaklığı", 64),
        production_engineer=_required_text(
            payload.production_engineer,
            "üretim mühendisi",
            255,
        ),
        shift_chief=_shift_chief(payload.shift_chief),
        shift=automatic_timing["shift"],
    )

    with create_session(settings) as session:
        session.add(context)
        commit_session(session)
        return {"id": context.id, "tour_context": serialize_tour_context(context)}


@api_router.post("/entries", status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    settings = _settings(request)
    context_id = _tour_context_id_from_body(payload)

    with create_session(settings) as session:
        context = session.get(TourContext, context_id)
        if context is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tur bilgileri bulunamadı.",
            )

        entry_payload = _combined_entry_payload(context, payload)
        entry = Entry(
            tour_context_id=context.id,
            status=_optional_text(payload.get("status"), "durum", 64),
            notes=_optional_text(payload.get("notes"), "notlar"),
            mold_info=_optional_text(payload.get("mold_info"), "kalıp bilgisi"),
            sync_status=SYNC_STATUS_PENDING_EXCEL,
            submitted_at=utc_now(),
            **entry_payload,
        )
        session.add(entry)
        commit_session(session)

        sync_result = attempt_excel_append(
            settings,
            session,
            entry,
            failure_status=SYNC_STATUS_PENDING_EXCEL,
        )
        return {
            "saved_locally": True,
            "synced_to_excel": sync_result["success"],
            "entry": serialize_entry(entry),
        }


@api_router.get("/entries")
def list_entries(
    request: Request,
    sync_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    if sync_status is not None and sync_status not in SYNC_STATUSES:
        raise _validation_error(
            "sync_status şunlardan biri olmalıdır: " + ", ".join(SYNC_STATUSES)
        )

    settings = _settings(request)
    query = (
        select(Entry)
        .options(selectinload(Entry.tour_context))
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .limit(limit)
    )
    if sync_status is not None:
        query = query.where(Entry.sync_status == sync_status)

    with create_session(settings) as session:
        entries = session.scalars(query).all()
        return {"entries": [serialize_entry(entry) for entry in entries]}


@api_router.post("/sync/retry")
def retry_sync(request: Request) -> dict[str, Any]:
    return retry_unsynced_entries(_settings(request))


@api_router.post("/cycle-report/today")
def create_today_cycle_report(request: Request) -> dict[str, Any]:
    settings = _settings(request)
    report_date = _request_datetime(settings).date()
    try:
        return create_cycle_report(settings, report_date).as_dict()
    except NoTodayRowsError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CycleReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def create_app() -> FastAPI:
    fastapi_app = FastAPI(
        title="Mobil Proses Veri Girişi MVP",
        lifespan=lifespan,
    )
    fastapi_app.mount(
        "/static",
        StaticFiles(directory=APP_DIR / "static"),
        name="static",
    )
    fastapi_app.include_router(public_api_router)
    fastapi_app.include_router(api_router)

    @fastapi_app.middleware("http")
    async def no_cache_ui_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path in {"/", "/login"} or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @fastapi_app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        settings = _settings(request)
        if not is_request_authenticated(request, settings):
            return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        return TEMPLATES.TemplateResponse(request, "index.html")

    @fastapi_app.get("/login", response_class=HTMLResponse)
    def login(request: Request):
        settings = _settings(request)
        if is_request_authenticated(request, settings):
            return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        return TEMPLATES.TemplateResponse(request, "login.html")

    @fastapi_app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        settings = _settings(request)
        sqlite = sqlite_health(settings)
        excel = check_excel_reachable(settings)
        last_error = None
        if sqlite["ok"]:
            with create_session(settings) as session:
                last_error = latest_sync_error(session)
        return {
            "status": "ok" if sqlite["ok"] and excel.available else "degraded",
            "sqlite": sqlite,
            "excel": {
                "ok": excel.available,
                "error": excel.error or None,
            },
            "last_sync_error": last_error,
        }

    return fastapi_app


app = create_app()
