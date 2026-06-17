from pydantic import BaseModel, Field


class TourContextCreate(BaseModel):
    date: str | None = Field(default=None, max_length=32)
    ambient_temp: str = Field(..., min_length=1, max_length=64)
    production_engineer_id: int | None = None
    production_engineer: str = Field(..., min_length=1, max_length=255)
    shift_chief: str = Field(..., min_length=1, max_length=255)
    shift: str | None = Field(default=None, max_length=64)
    client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)


class AmountControlBreakdownCreate(BaseModel):
    produced_product: str = Field(..., min_length=1)
    stop_reason: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., ge=1)
    stopped_at: str | None = Field(default=None, max_length=64)
    resumed_at: str | None = Field(default=None, max_length=64)


class AmountControlShiftCreate(BaseModel):
    record_date: str = Field(..., min_length=10, max_length=10)
    machine_code: str = Field(..., min_length=1, max_length=16)
    job_order: str = Field(..., min_length=1)
    shift: str = Field(..., min_length=1, max_length=16)
    worker_names: str = Field(..., min_length=1)
    produced_quantity: int = Field(..., ge=0)
    breakdowns: list[AmountControlBreakdownCreate] = Field(default_factory=list)
    client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)


class AmountControlBreakdownResponse(BaseModel):
    id: int
    machine_id: int
    machine_code: str | None = None
    entry_id: int | None = None
    amount_control_shift_id: int | None = None
    produced_product: str
    stop_reason: str
    duration_minutes: int
    stopped_at: str | None = None
    resumed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AmountControlShiftResponse(BaseModel):
    id: int
    client_request_id: str | None = None
    client_recorded_at: str | None = None
    record_date: str
    machine_id: int
    machine_code: str
    job_order: str
    shift: str
    worker_names: str
    produced_quantity: int
    breakdowns: list[AmountControlBreakdownResponse] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class AmountControlShiftCreateResponse(BaseModel):
    id: int
    saved_locally: bool
    shift: AmountControlShiftResponse
    idempotent_replay: bool = False


class AmountControlShiftListResponse(BaseModel):
    shifts: list[AmountControlShiftResponse]
