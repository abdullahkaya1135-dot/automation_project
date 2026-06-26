from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...core.database import DatabaseCommitError, commit_session, create_session
from ...core.security import require_api_auth
from ...domain.request_settings import settings_from_request
from ...domain.request_values import (
    client_recorded_datetime,
    client_request_id,
    optional_text,
    required_text,
    stored_client_recorded_at,
    validation_error,
)
from .domain import (
    breakdown_duration_minutes,
    breakdown_record_date,
    breakdown_shift,
    breakdown_times,
)
from .models import Machine, MachineBreakdown
from .schemas import (
    BreakdownContextResponse,
    BreakdownCreate,
    BreakdownCreateResponse,
    BreakdownListResponse,
    BreakdownResponse,
)
from .service import breakdown_context_options, serialize_breakdown

router = APIRouter(
    prefix="/api/breakdowns",
    dependencies=[Depends(require_api_auth)],
)


def _breakdown_load_options():
    return (selectinload(MachineBreakdown.machine),)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BreakdownCreateResponse,
)
def create_breakdown(
    payload: BreakdownCreate,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    request_client_id = client_request_id(payload.client_request_id)
    client_recorded_at = client_recorded_datetime(
        payload.client_recorded_at,
        settings,
    )
    stored_recorded_at = stored_client_recorded_at(client_recorded_at)
    record_date = breakdown_record_date(payload.record_date)
    machine_code = required_text(payload.machine_code, "makine", 16)
    shift = breakdown_shift(payload.shift)
    reason = required_text(payload.reason, "durus nedeni", 1000)
    duration_minutes = breakdown_duration_minutes(payload.duration_minutes)
    job_order = optional_text(payload.job_order, "is emri", 255)
    produced_product = optional_text(payload.produced_product, "uretilen urun", 1000)
    stopped_at, resumed_at = breakdown_times(
        payload.stopped_at,
        payload.resumed_at,
        settings,
    )

    with create_session(settings) as session:
        if request_client_id is not None:
            existing_breakdown = session.scalars(
                select(MachineBreakdown)
                .options(*_breakdown_load_options())
                .where(MachineBreakdown.client_request_id == request_client_id)
            ).first()
            if existing_breakdown is not None:
                response.status_code = status.HTTP_200_OK
                return {
                    "id": existing_breakdown.id,
                    "saved_locally": True,
                    "breakdown": serialize_breakdown(existing_breakdown),
                    "idempotent_replay": True,
                }

        machine = session.scalars(
            select(Machine).where(Machine.machine_code == machine_code)
        ).first()
        if machine is None:
            raise validation_error("makine veritabaninda bulunamadi.")

        breakdown = MachineBreakdown(
            client_request_id=request_client_id,
            client_recorded_at=stored_recorded_at,
            record_date=record_date,
            machine=machine,
            shift=shift,
            job_order=job_order,
            produced_product=produced_product,
            stop_reason=reason,
            duration_minutes=duration_minutes,
            stopped_at=stopped_at,
            resumed_at=resumed_at,
        )
        session.add(breakdown)
        try:
            commit_session(session)
        except DatabaseCommitError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Durus kaydi kaydedilemedi; kayit zaten var olabilir.",
            ) from exc

        return {
            "id": breakdown.id,
            "saved_locally": True,
            "breakdown": serialize_breakdown(breakdown),
        }


@router.get("", response_model=BreakdownListResponse)
def list_breakdowns(
    request: Request,
    record_date: str | None = None,
    machine_code: str | None = None,
    shift: str | None = None,
    job_order: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    query = (
        select(MachineBreakdown)
        .options(*_breakdown_load_options())
        .join(MachineBreakdown.machine)
        .order_by(
            MachineBreakdown.record_date.desc(),
            MachineBreakdown.created_at.desc(),
            MachineBreakdown.id.desc(),
        )
        .limit(limit)
    )

    if record_date is not None:
        query = query.where(
            MachineBreakdown.record_date == breakdown_record_date(record_date)
        )
    if machine_code is not None:
        query = query.where(
            Machine.machine_code == required_text(machine_code, "makine", 16)
        )
    if shift is not None:
        query = query.where(MachineBreakdown.shift == breakdown_shift(shift))
    if job_order is not None:
        query = query.where(
            MachineBreakdown.job_order == required_text(job_order, "is emri", 255)
        )

    with create_session(settings) as session:
        breakdowns = session.scalars(query).all()
        return {
            "breakdowns": [
                serialize_breakdown(breakdown) for breakdown in breakdowns
            ]
        }


@router.get("/context", response_model=BreakdownContextResponse)
def get_breakdown_context(
    request: Request,
    record_date: str = Query(..., min_length=10, max_length=10),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    normalized_record_date = breakdown_record_date(record_date)
    with create_session(settings) as session:
        options = breakdown_context_options(session, normalized_record_date)
    return {
        "record_date": normalized_record_date,
        "source": "process_entries",
        "option_count": len(options),
        "options": options,
    }


@router.get("/{breakdown_id}", response_model=BreakdownResponse)
def get_breakdown(
    breakdown_id: int,
    request: Request,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    with create_session(settings) as session:
        breakdown = session.scalars(
            select(MachineBreakdown)
            .options(*_breakdown_load_options())
            .where(MachineBreakdown.id == breakdown_id)
        ).first()
        if breakdown is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Durus kaydi bulunamadi.",
            )
        return serialize_breakdown(breakdown)
