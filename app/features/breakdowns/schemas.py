from pydantic import BaseModel, Field


class BreakdownCreate(BaseModel):
    record_date: str = Field(..., min_length=10, max_length=10)
    machine_code: str = Field(..., min_length=1, max_length=16)
    shift: str = Field(..., min_length=1, max_length=16)
    reason: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., ge=1)
    job_order: str | None = None
    produced_product: str | None = None
    stopped_at: str | None = Field(default=None, max_length=64)
    resumed_at: str | None = Field(default=None, max_length=64)
    client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)


class BreakdownResponse(BaseModel):
    id: int
    client_request_id: str | None = None
    client_recorded_at: str | None = None
    record_date: str | None = None
    machine_id: int
    machine_code: str | None = None
    entry_id: int | None = None
    amount_control_shift_id: int | None = None
    job_order: str | None = None
    shift: str | None = None
    produced_product: str | None = None
    reason: str
    stop_reason: str
    duration_minutes: int
    stopped_at: str | None = None
    resumed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class BreakdownCreateResponse(BaseModel):
    id: int
    saved_locally: bool
    breakdown: BreakdownResponse
    idempotent_replay: bool = False


class BreakdownListResponse(BaseModel):
    breakdowns: list[BreakdownResponse]


class BreakdownContextOption(BaseModel):
    machine_code: str
    job_order: str
    produced_product: str | None = None
    entry_id: int
    submitted_at: str | None = None


class BreakdownContextResponse(BaseModel):
    record_date: str
    source: str
    option_count: int
    options: list[BreakdownContextOption]
