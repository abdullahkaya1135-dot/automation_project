from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Entry, ProductionEngineer
from .normalization import (
    normalize_machine_code,
    normalize_process_date,
    normalize_production_engineer_name,
)


def production_engineer_options(session: Session) -> list[dict[str, Any]]:
    engineers = session.scalars(
        select(ProductionEngineer)
        .where(ProductionEngineer.active.is_(True))
        .order_by(ProductionEngineer.display_order, ProductionEngineer.full_name)
    ).all()
    return [
        {
            "id": engineer.id,
            "full_name": engineer.full_name,
            "display_order": engineer.display_order,
        }
        for engineer in engineers
    ]


def resolve_production_engineer(
    session: Session,
    value: Any,
) -> ProductionEngineer | None:
    canonical_name = normalize_production_engineer_name(value)
    if canonical_name is None:
        return None
    return session.scalars(
        select(ProductionEngineer).where(
            ProductionEngineer.full_name == canonical_name,
            ProductionEngineer.active.is_(True),
        )
    ).first()


def resolve_production_engineer_by_id(
    session: Session,
    engineer_id: int | None,
) -> ProductionEngineer | None:
    if engineer_id is None:
        return None
    return session.scalars(
        select(ProductionEngineer).where(
            ProductionEngineer.id == engineer_id,
            ProductionEngineer.active.is_(True),
        )
    ).first()


def apply_entry_process_metadata(
    session: Session,
    entry: Entry,
) -> None:
    engineer = resolve_production_engineer(session, entry.col_c)
    canonical_name = (
        engineer.full_name if engineer is not None else normalize_production_engineer_name(entry.col_c)
    )
    entry.col_c = canonical_name
    entry.production_engineer = engineer
    entry.process_date = normalize_process_date(entry.col_a)
    entry.machine_code = normalize_machine_code(entry.col_f)
