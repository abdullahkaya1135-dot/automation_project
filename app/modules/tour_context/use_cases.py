from fastapi import status

from ...config import Settings
from ...database import commit_session, create_session
from ...schemas import TourContextCreate
from ..sync.serializers import serialize_tour_context
from ..use_case_result import UseCaseResult
from .service import save_tour_context


def create_tour_context(
    settings: Settings,
    payload: TourContextCreate,
) -> UseCaseResult:
    body = payload.model_dump(mode="python")

    with create_session(settings) as session:
        saved_context = save_tour_context(session, settings, body)
        context = saved_context.context
        response_payload = {
            "id": context.id,
            "tour_context": serialize_tour_context(context),
        }
        if saved_context.idempotent_replay:
            response_payload["idempotent_replay"] = True
            return UseCaseResult(status.HTTP_200_OK, response_payload)

        commit_session(session)
        return UseCaseResult(status.HTTP_201_CREATED, response_payload)
