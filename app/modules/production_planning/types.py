from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningOrder:
    order_no: str
    sheet_name: str
    row_number: int
    cell_value: str
