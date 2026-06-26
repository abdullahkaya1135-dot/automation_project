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
    required_text,
    stored_client_recorded_at,
    validation_error,
)
from .domain import (
    amount_control_breakdown_times,
    amount_control_quantity,
    amount_control_record_date,
    amount_control_shift,
)
from .models import AmountControlShift, Machine, MachineBreakdown
from .schemas import (
    AmountControlShiftCreate,
    AmountControlShiftCreateResponse,
    AmountControlShiftListResponse,
    AmountControlShiftResponse,
)
from .service import serialize_amount_control_shift

router = APIRouter(
    prefix="/api/amount-control",
    dependencies=[Depends(require_api_auth)],
)


def _amount_control_load_options():
    return (
        selectinload(AmountControlShift.machine),
        selectinload(AmountControlShift.machine_breakdowns).selectinload(
            MachineBreakdown.machine
        ),
    )


@router.post(
    "/shifts",
    status_code=status.HTTP_201_CREATED,
    response_model=AmountControlShiftCreateResponse,
)
def create_amount_control_shift(
    payload: AmountControlShiftCreate,
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
    record_date = amount_control_record_date(payload.record_date)
    machine_code = required_text(payload.machine_code, "makine", 16)
    job_order = required_text(payload.job_order, "is emri", 255)
    shift = amount_control_shift(payload.shift)
    worker_names = required_text(payload.worker_names, "calisanlar", 1000)
    produced_quantity = amount_control_quantity(payload.produced_quantity)

    with create_session(settings) as session:
        if request_client_id is not None:
            existing_shift = session.scalars(
                select(AmountControlShift)
                .options(*_amount_control_load_options())
                .where(AmountControlShift.client_request_id == request_client_id)
            ).first()
            if existing_shift is not None:
                response.status_code = status.HTTP_200_OK
                return {
                    "id": existing_shift.id,
                    "saved_locally": True,
                    "shift": serialize_amount_control_shift(existing_shift),
                    "idempotent_replay": True,
                }

        machine = session.scalars(
            select(Machine).where(Machine.machine_code == machine_code)
        ).first()
        if machine is None:
            raise validation_error("makine veritabaninda bulunamadi.")

        duplicate_shift = session.scalars(
            select(AmountControlShift)
            .where(AmountControlShift.record_date == record_date)
            .where(AmountControlShift.machine_id == machine.id)
            .where(AmountControlShift.job_order == job_order)
            .where(AmountControlShift.shift == shift)
        ).first()
        if duplicate_shift is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Bu tarih, makine, is emri ve vardiya icin miktar kontrol "
                    "kaydi zaten var."
                ),
            )

        amount_shift = AmountControlShift(
            client_request_id=request_client_id,
            client_recorded_at=stored_recorded_at,
            record_date=record_date,
            machine=machine,
            job_order=job_order,
            shift=shift,
            worker_names=worker_names,
            produced_quantity=produced_quantity,
        )
        session.add(amount_shift)
        for breakdown_payload in payload.breakdowns:
            stopped_at, resumed_at = amount_control_breakdown_times(
                breakdown_payload.stopped_at,
                breakdown_payload.resumed_at,
                settings,
            )
            amount_shift.machine_breakdowns.append(
                MachineBreakdown(
                    machine=machine,
                    record_date=record_date,
                    shift=shift,
                    job_order=job_order,
                    produced_product=required_text(
                        breakdown_payload.produced_product,
                        "uretilen urun",
                        1000,
                    ),
                    stop_reason=required_text(
                        breakdown_payload.stop_reason,
                        "durus nedeni",
                        1000,
                    ),
                    duration_minutes=amount_control_quantity(
                        breakdown_payload.duration_minutes
                    ),
                    stopped_at=stopped_at,
                    resumed_at=resumed_at,
                )
            )

        try:
            commit_session(session)
        except DatabaseCommitError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Miktar kontrol kaydi kaydedilemedi; kayit zaten var olabilir.",
            ) from exc

        return {
            "id": amount_shift.id,
            "saved_locally": True,
            "shift": serialize_amount_control_shift(amount_shift),
        }


@router.get(
    "/shifts",
    response_model=AmountControlShiftListResponse,
)
def list_amount_control_shifts(
    request: Request,
    record_date: str | None = None,
    machine_code: str | None = None,
    job_order: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    query = (
        select(AmountControlShift)
        .options(*_amount_control_load_options())
        .join(AmountControlShift.machine)
        .order_by(
            AmountControlShift.record_date.desc(),
            AmountControlShift.created_at.desc(),
            AmountControlShift.id.desc(),
        )
        .limit(limit)
    )

    if record_date is not None:
        query = query.where(
            AmountControlShift.record_date == amount_control_record_date(record_date)
        )
    if machine_code is not None:
        query = query.where(
            Machine.machine_code == required_text(machine_code, "makine", 16)
        )
    if job_order is not None:
        query = query.where(
            AmountControlShift.job_order == required_text(job_order, "is emri", 255)
        )

    with create_session(settings) as session:
        shifts = session.scalars(query).all()
        return {
            "shifts": [
                serialize_amount_control_shift(amount_shift)
                for amount_shift in shifts
            ]
        }


@router.get(
    "/shifts/{shift_id}",
    response_model=AmountControlShiftResponse,
)
def get_amount_control_shift(
    shift_id: int,
    request: Request,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    with create_session(settings) as session:
        amount_shift = session.scalars(
            select(AmountControlShift)
            .options(*_amount_control_load_options())
            .where(AmountControlShift.id == shift_id)
        ).first()
        if amount_shift is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Miktar kontrol kaydi bulunamadi.",
            )
        return serialize_amount_control_shift(amount_shift)
