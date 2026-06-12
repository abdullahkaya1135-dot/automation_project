from fastapi import Request

from ..config import Settings, get_settings
from ..database import init_db


def settings_from_request(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
        request.app.state.settings = settings
        init_db(settings)
    return settings
