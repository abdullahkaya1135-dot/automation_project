from collections.abc import Mapping, Sequence
from typing import Any


def identity_value(value: Any) -> str:
    return str(value or "").strip()


def cleaned_order_numbers(order_numbers: Sequence[str]) -> list[str]:
    return list(
        dict.fromkeys(
            order_no
            for value in order_numbers
            if (order_no := str(value or "").strip()) and order_no != "0"
        )
    )


def material_has_part_number(material: Mapping[str, Any]) -> bool:
    return bool(identity_value(material.get("PartNo")))


def flatten_material_groups(
    material_groups: Sequence[Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    return [
        dict(material)
        for group in material_groups
        for material in group
        if material_has_part_number(material)
    ]


def flatten_operation_groups(
    operation_groups: Sequence[Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    return [
        dict(operation)
        for group in operation_groups
        for operation in group
    ]


def deduplicated_rows(
    rows: Sequence[Mapping[str, Any]],
    key_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    deduplicated: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(identity_value(row.get(field_name)) for field_name in key_fields)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(dict(row))
    return deduplicated


def deduplicated_operations(
    operations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return deduplicated_rows(
        operations,
        ("OrderNo", "ReleaseNo", "SequenceNo", "OperationNo"),
    )


def deduplicated_materials(
    materials: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return deduplicated_rows(
        materials,
        ("OrderNo", "ReleaseNo", "SequenceNo", "OperationNo", "LineItemNo", "PartNo"),
    )
