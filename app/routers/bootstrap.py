from typing import Any

from fastapi import APIRouter, Depends, Request

from ..domain.request_settings import settings_from_request
from ..modules.auth.service import require_api_auth
from ..modules.bootstrap.field_definitions import field_definitions_payload
from ..modules.bootstrap.service import (
    bootstrap_payload,
)
from ..modules.bootstrap.service import (
    tour_context_defaults as tour_context_defaults_payload,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.get("/bootstrap")
async def bootstrap(request: Request) -> dict[str, Any]:
    return await bootstrap_payload(settings_from_request(request))


@router.get("/tour-context/defaults")
def tour_context_defaults(request: Request) -> dict[str, str]:
    return tour_context_defaults_payload(settings_from_request(request))


@router.get("/field-definitions")
def field_definitions() -> dict[str, Any]:
    return field_definitions_payload()
