from fastapi import Request

from ..core.config import Settings, get_settings
from ..core.database import init_db


def settings_from_request(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
        request.app.state.settings = settings
        init_db(settings)
    return settings
