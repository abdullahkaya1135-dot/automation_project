from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db
from .paths import STATIC_DIR
from .routers.amount_control import router as amount_control_router
from .routers.auth import router as auth_router
from .routers.auxiliary import router as auxiliary_router
from .routers.bootstrap import router as bootstrap_router
from .routers.entries import router as entries_router
from .routers.health import router as health_router
from .routers.ifs import router as ifs_router
from .routers.pages import router as pages_router
from .routers.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    init_db(settings)
    yield


def create_app() -> FastAPI:
    fastapi_app = FastAPI(
        title="Mobil Proses Veri Girişi MVP",
        lifespan=lifespan,
    )
    fastapi_app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static",
    )
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(bootstrap_router)
    fastapi_app.include_router(entries_router)
    fastapi_app.include_router(amount_control_router)
    fastapi_app.include_router(auxiliary_router)
    fastapi_app.include_router(reports_router)
    fastapi_app.include_router(ifs_router)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(pages_router)

    @fastapi_app.middleware("http")
    async def no_cache_ui_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path in {
            "/",
            "/process",
            "/auxiliary",
            "/amount-control",
            "/reports",
            "/login",
        }:
            response.headers["Cache-Control"] = "no-store, max-age=0"
        elif request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    return fastapi_app


app = create_app()
