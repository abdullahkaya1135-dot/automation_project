from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .core.config import get_settings
from .core.database import init_db
from .core.paths import STATIC_DIR
from .features.amount_control.api import router as amount_control_router
from .features.auth.api import router as auth_router
from .features.auxiliary_systems.api import router as auxiliary_router
from .features.bootstrap.api import router as bootstrap_router
from .features.cycle_reports.api import router as reports_router
from .features.health.api import router as health_router
from .features.ifs.api import router as ifs_router
from .features.process_entries.api import router as entries_router
from .features.production_loss.api import router as production_loss_router
from .web import pages


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
    fastapi_app.include_router(production_loss_router)
    fastapi_app.include_router(ifs_router)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(pages.router)

    @fastapi_app.middleware("http")
    async def no_cache_ui_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path in pages.NO_CACHE_PAGE_PATHS:
            response.headers["Cache-Control"] = "no-store, max-age=0"
        elif request.url.path.startswith(pages.STATIC_URL_PREFIX):
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    return fastapi_app


app = create_app()
