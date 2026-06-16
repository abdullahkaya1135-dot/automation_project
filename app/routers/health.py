from typing import Any

from fastapi import APIRouter, Request

from ..domain.request_settings import settings_from_request
from ..modules.health.service import health_payload
from ..schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> dict[str, Any]:
    return health_payload(settings_from_request(request))
