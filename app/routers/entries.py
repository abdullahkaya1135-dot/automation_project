from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import Integer, cast, select
from sqlalchemy.orm import selectinload

from ..auth import require_api_auth
from ..database import commit_session, create_session
from ..domain import shifts
from ..domain.entry_payloads import combined_entry_payload
from ..domain.request_settings import settings_from_request
from ..domain.request_values import (
    client_recorded_datetime,
    client_request_id,
    optional_text,
    required_text,
    shift_chief,
    stored_client_recorded_at,
    tour_context_id_from_body,
)
from ..models import (
    SYNC_STATUS_SYNCED,
    Entry,
    ProductionEngineer,
    TourContext,
    utc_now,
)
from ..schemas import TourContextCreate
from ..services.process_records import (
    apply_entry_process_metadata,
    resolve_production_engineer,
    resolve_production_engineer_by_id,
)
from ..services.sync_service import (
    serialize_entry,
    serialize_tour_context,
)
from .validators import validate_sync_status

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post("/tour-context", status_code=status.HTTP_201_CREATED)
def create_tour_context(
    payload: TourContextCreate,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    request_client_id = client_request_id(payload.client_request_id)
    client_recorded_at = client_recorded_datetime(
        payload.client_recorded_at,
        settings,
    )

    with create_session(settings) as session:
        if request_client_id is not None:
            existing_context = session.scalars(
                select(TourContext).where(
                    TourContext.client_request_id == request_client_id
                )
            ).first()
            if existing_context is not None:
                response.status_code = status.HTTP_200_OK
                return {
                    "id": existing_context.id,
                    "tour_context": serialize_tour_context(existing_context),
                    "idempotent_replay": True,
                }

        request_time = client_recorded_at or shifts.request_datetime(settings)
        automatic_timing = shifts.tour_timing_for_datetime(settings, request_time)
        production_engineer = _tour_context_production_engineer(session, payload)
        context = TourContext(
            client_request_id=request_client_id,
            client_recorded_at=stored_client_recorded_at(client_recorded_at),
            date=automatic_timing["date"],
            ambient_temp=required_text(payload.ambient_temp, "ortam sıcaklığı", 64),
            production_engineer=required_text(
                payload.production_engineer,
                "üretim mühendisi",
                255,
            ),
            shift_chief=shift_chief(payload.shift_chief),
            shift=automatic_timing["shift"],
        )
        context.production_engineer = production_engineer.full_name
        session.add(context)
        commit_session(session)
        return {"id": context.id, "tour_context": serialize_tour_context(context)}


@router.post("/entries", status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: dict[str, Any],
    request: Request,
    response: Response,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    context_id = tour_context_id_from_body(payload)
    request_client_id = client_request_id(payload.get("client_request_id"))
    client_recorded_at = client_recorded_datetime(
        payload.get("client_recorded_at"),
        settings,
    )
    stored_recorded_at = stored_client_recorded_at(client_recorded_at)

    with create_session(settings) as session:
        if request_client_id is not None:
            existing_entry = session.scalars(
                select(Entry).where(Entry.client_request_id == request_client_id)
            ).first()
            if existing_entry is not None:
                response.status_code = status.HTTP_200_OK
                return {
                    "saved_locally": True,
                    "synced_to_excel": existing_entry.sync_status
                    == SYNC_STATUS_SYNCED,
                    "entry": serialize_entry(existing_entry),
                    "idempotent_replay": True,
                }

        context = session.get(TourContext, context_id)
        if context is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tur bilgileri bulunamadı.",
            )

        entry_payload = combined_entry_payload(context, payload)
        entry = Entry(
            client_request_id=request_client_id,
            client_recorded_at=stored_recorded_at,
            tour_context_id=context.id,
            status=optional_text(payload.get("status"), "durum", 64),
            notes=optional_text(payload.get("notes"), "notlar"),
            mold_info=optional_text(payload.get("mold_info"), "kalıp bilgisi"),
            sync_status=SYNC_STATUS_SYNCED,
            submitted_at=stored_recorded_at or utc_now(),
            **entry_payload,
        )
        apply_entry_process_metadata(session, entry)
        entry.last_error = None
        entry.synced_at = utc_now()
        session.add(entry)
        commit_session(session)

        return {
            "saved_locally": True,
            "saved_to_database": True,
            "synced_to_excel": False,
            "entry": serialize_entry(entry),
        }


@router.get("/entries")
def list_entries(
    request: Request,
    sync_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    validate_sync_status(sync_status)

    settings = settings_from_request(request)
    query = (
        select(Entry)
        .options(selectinload(Entry.tour_context))
        .order_by(
            Entry.process_date.asc(),
            cast(Entry.machine_code, Integer).asc(),
            Entry.production_engineer_id.asc(),
            Entry.id.asc(),
        )
        .limit(limit)
    )
    if sync_status is not None:
        query = query.where(Entry.sync_status == sync_status)

    with create_session(settings) as session:
        entries = session.scalars(query).all()
        return {"entries": [serialize_entry(entry) for entry in entries]}


@router.post("/sync/retry")
def retry_sync() -> dict[str, Any]:
    return {
        "attempted": 0,
        "synced": 0,
        "failed": 0,
        "remaining": 0,
        "stopped_on_error": False,
        "results": [],
        "database_backed": True,
    }


def _tour_context_production_engineer(
    session,
    payload: TourContextCreate,
) -> ProductionEngineer:
    engineer = resolve_production_engineer_by_id(
        session,
        payload.production_engineer_id,
    )
    if engineer is None:
        engineer = resolve_production_engineer(
            session,
            required_text(payload.production_engineer, "üretim mühendisi", 255),
        )
    if engineer is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Üretim mühendisi veritabanında bulunamadı.",
        )
    return engineer
