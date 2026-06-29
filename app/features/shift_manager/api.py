from __future__ import annotations

import importlib
import inspect
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ...core.database import DatabaseCommitError, commit_session, create_session
from ...core.security import require_api_auth
from ...domain.request_settings import settings_from_request
from ...domain.request_values import required_text
from ...models import ShiftManagerNotification, utc_now
from ..serialization import timestamp as _timestamp

router = APIRouter(
    prefix="/api/shift-manager",
    dependencies=[Depends(require_api_auth)],
)

_SERVICE_MODULE = "app.features.shift_manager.service"
_NEAR_COMPLETE_FUNCTION_NAMES = (
    "build_shift_manager_payload",
    "near_complete_orders",
    "get_near_complete_orders",
)
_MACHINE_CODE_FIELDS = ("machine_code", "machine", "resource_id", "work_center_no")
_CURRENT_ORDER_FIELDS = (
    "current_order_no",
    "current_order",
    "current_job_order",
    "job_order",
)
_NEXT_ORDER_FIELDS = ("next_order_no", "next_order", "next_job_order")


class ShiftManagerNotificationUpdate(BaseModel):
    machine_code: str = Field(..., min_length=1, max_length=16)
    current_order_no: str = Field(..., min_length=1)
    next_order_no: str = Field(..., min_length=1)
    informed: bool


@router.get("/near-complete")
async def near_complete_orders(
    request: Request,
    threshold: int = Query(3, ge=0, le=1000),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        service_result = await _call_near_complete_service(settings, threshold)
    except Exception as exc:
        if exc.__class__.__name__ in {
            "ProductionPlanningError",
            "ShiftManagerServiceError",
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        raise
    summary, rows = _coerce_near_complete_payload(service_result)
    keys = {key for row in rows if (key := _row_key(row)) is not None}

    with create_session(settings) as session:
        notifications = _notifications_by_key(session, keys)

    rows = _join_notification_state(rows, notifications)
    informed_count = sum(1 for row in rows if row["informed"])
    summary = dict(summary)
    summary.setdefault("threshold", threshold)
    summary["row_count"] = len(rows)
    summary["informed_count"] = informed_count
    summary["uninformed_count"] = len(rows) - informed_count
    return {"summary": summary, "rows": rows}


@router.put("/notifications")
def upsert_notification(
    payload: ShiftManagerNotificationUpdate,
    request: Request,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    machine_code = required_text(payload.machine_code, "makine", 16)
    current_order_no = required_text(payload.current_order_no, "mevcut is emri", 255)
    next_order_no = required_text(payload.next_order_no, "sonraki is emri", 255)
    now = utc_now()

    with create_session(settings) as session:
        notification = session.scalars(
            select(ShiftManagerNotification)
            .where(ShiftManagerNotification.machine_code == machine_code)
            .where(ShiftManagerNotification.current_order_no == current_order_no)
            .where(ShiftManagerNotification.next_order_no == next_order_no)
        ).first()
        created = notification is None
        if notification is None:
            notification = ShiftManagerNotification(
                machine_code=machine_code,
                current_order_no=current_order_no,
                next_order_no=next_order_no,
                created_at=now,
            )
            session.add(notification)

        notification.informed = payload.informed
        notification.informed_at = now if payload.informed else None
        notification.updated_at = now

        try:
            commit_session(session)
        except DatabaseCommitError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Shift Manager bildirimi kaydedilemedi.",
            ) from exc

        return {
            "created": created,
            "notification": _serialize_notification(notification),
        }


async def _call_near_complete_service(settings, threshold: int) -> Any:
    service = _shift_manager_service()
    near_complete = _near_complete_function(service)
    result = near_complete(settings, threshold=threshold)
    if inspect.isawaitable(result):
        return await result
    return result


def _shift_manager_service():
    try:
        return importlib.import_module(_SERVICE_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == _SERVICE_MODULE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Shift Manager service is not available.",
            ) from exc
        raise


def _near_complete_function(service):
    for function_name in _NEAR_COMPLETE_FUNCTION_NAMES:
        function = getattr(service, function_name, None)
        if callable(function):
            return function
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Shift Manager service must expose build_shift_manager_payload(settings, "
            "threshold=...)."
        ),
    )


def _coerce_near_complete_payload(
    result: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = _object_to_dict(result)
    if isinstance(result, Mapping):
        summary = _object_to_dict(result.get("summary", {}))
        rows = result.get("rows", result.get("items", []))
    else:
        summary = {}
        rows = result

    if not isinstance(summary, Mapping):
        summary = {}
    return dict(summary), _coerce_rows(rows)


def _coerce_rows(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, (str, bytes, Mapping)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shift Manager service rows must be a list.",
        )

    try:
        row_values = list(rows)
    except TypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shift Manager service rows must be iterable.",
        ) from exc
    return [_coerce_row(row) for row in row_values]


def _coerce_row(row: Any) -> dict[str, Any]:
    row = _object_to_dict(row)
    if not isinstance(row, Mapping):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shift Manager service row format is not supported.",
        )
    return dict(row)


def _object_to_dict(value: Any) -> Any:
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return value.as_dict()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


def _notifications_by_key(
    session,
    keys: set[tuple[str, str, str]],
) -> dict[tuple[str, str, str], ShiftManagerNotification]:
    if not keys:
        return {}

    machine_codes = {machine_code for machine_code, _current, _next in keys}
    notifications = session.scalars(
        select(ShiftManagerNotification).where(
            ShiftManagerNotification.machine_code.in_(machine_codes)
        )
    ).all()
    return {
        key: notification
        for notification in notifications
        if (
            key := (
                notification.machine_code,
                notification.current_order_no,
                notification.next_order_no,
            )
        )
        in keys
    }


def _join_notification_state(
    rows: list[dict[str, Any]],
    notifications: dict[tuple[str, str, str], ShiftManagerNotification],
) -> list[dict[str, Any]]:
    joined_rows: list[dict[str, Any]] = []
    for row in rows:
        row = dict(row)
        key = _row_key(row)
        notification = notifications.get(key) if key is not None else None
        if key is not None:
            row.setdefault("machine_code", key[0])
            row.setdefault("current_order_no", key[1])
            row.setdefault("next_order_no", key[2])
        row["notification_id"] = notification.id if notification is not None else None
        row["informed"] = bool(notification.informed) if notification else False
        row["informed_at"] = (
            _timestamp(notification.informed_at) if notification is not None else None
        )
        row["notification_updated_at"] = (
            _timestamp(notification.updated_at) if notification is not None else None
        )
        joined_rows.append(row)
    return joined_rows


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    machine_code = _first_text(row, _MACHINE_CODE_FIELDS)
    current_order_no = _first_text(row, _CURRENT_ORDER_FIELDS)
    next_order_no = _first_text(row, _NEXT_ORDER_FIELDS)
    if machine_code is None or current_order_no is None or next_order_no is None:
        return None
    return machine_code, current_order_no, next_order_no


def _first_text(row: Mapping[str, Any], field_names: tuple[str, ...]) -> str | None:
    for field_name in field_names:
        if field_name not in row:
            continue
        value = row[field_name]
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value:
            return text_value
    return None


def _serialize_notification(
    notification: ShiftManagerNotification,
) -> dict[str, Any]:
    return {
        "id": notification.id,
        "machine_code": notification.machine_code,
        "current_order_no": notification.current_order_no,
        "next_order_no": notification.next_order_no,
        "informed": bool(notification.informed),
        "informed_at": _timestamp(notification.informed_at),
        "created_at": _timestamp(notification.created_at),
        "updated_at": _timestamp(notification.updated_at),
    }
