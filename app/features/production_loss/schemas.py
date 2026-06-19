from typing import Any

from pydantic import BaseModel, Field


class ProductionLossReportCreate(BaseModel):
    date_from: str = Field(..., min_length=10, max_length=10)
    date_to: str = Field(..., min_length=10, max_length=10)
    refresh_ifs: bool = True


class ProductionLossReportSummaryResponse(BaseModel):
    id: int
    date_from: str
    date_to: str
    generated_at: str | None = None
    output_path: str | None = None
    row_count: int
    warning_count: int
    source_summary: dict[str, Any] = Field(default_factory=dict)


class ProductionLossReportListResponse(BaseModel):
    reports: list[ProductionLossReportSummaryResponse]
