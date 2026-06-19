from pydantic import BaseModel, Field


class ProductionLossReportCreate(BaseModel):
    date_from: str = Field(..., min_length=10, max_length=10)
    date_to: str = Field(..., min_length=10, max_length=10)
    refresh_ifs: bool = True


class ProductionLossReportListResponse(BaseModel):
    reports: list[dict]

