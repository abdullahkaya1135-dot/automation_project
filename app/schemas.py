from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TourContextCreate(BaseModel):
    date: str | None = Field(default=None, max_length=32)
    ambient_temp: str = Field(..., min_length=1, max_length=64)
    production_engineer: str = Field(..., min_length=1, max_length=255)
    shift_chief: str = Field(..., min_length=1, max_length=255)
    shift: str | None = Field(default=None, max_length=64)
    client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)


class ProcessEntryCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    tour_context_id: int | str | None = None
    client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)
    payload_schema_version: int | str | None = None
    entry_payload_schema_version: int | str | None = None
    payload: dict[str, Any] | None = None
    status: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    mold_info: str | None = None


class AuxiliarySubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)
    recorded_date: str | None = Field(default=None, max_length=32)
    date: str | None = Field(default=None, max_length=32)
    payload: dict[str, Any] | None = None


class OfflineRecordEnvelope(BaseModel):
    client_request_id: str | None = Field(default=None, max_length=64)
    depends_on_client_request_id: str | None = Field(default=None, max_length=64)
    client_recorded_at: str | None = Field(default=None, max_length=64)


class TourContextBulkRecord(OfflineRecordEnvelope):
    type: Literal["tour_context"]
    body: TourContextCreate


class ProcessEntryBulkRecord(OfflineRecordEnvelope):
    type: Literal["entry"]
    body: ProcessEntryCreate = Field(default_factory=ProcessEntryCreate)


class AuxiliarySubmissionBulkRecord(OfflineRecordEnvelope):
    type: Literal["auxiliary_submission"]
    body: AuxiliarySubmissionCreate = Field(default_factory=AuxiliarySubmissionCreate)


type OfflineBulkRecord = Annotated[
    TourContextBulkRecord | ProcessEntryBulkRecord | AuxiliarySubmissionBulkRecord,
    Field(discriminator="type"),
]


class OfflineBulkSyncRequest(BaseModel):
    records: list[OfflineBulkRecord] = Field(default_factory=list, max_length=500)
    sync_excel: bool = True


class OfflineBulkRecordResult(BaseModel):
    type: str
    client_request_id: str | None = None
    server_id: int | None = None
    saved_locally: bool = True
    synced_to_excel: bool | None = None
    idempotent_replay: bool = False
    tour_context: dict[str, Any] | None = None
    entry: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None


class OfflineBulkSyncResponse(BaseModel):
    saved_count: int
    synced_count: int
    failed_count: int
    excel_pending: bool
    excel_error: str | None = None
    records: list[OfflineBulkRecordResult]


class SQLiteHealth(BaseModel):
    ok: bool
    error: str | None = None


class ExcelHealth(BaseModel):
    ok: bool
    error: str | None = None


class AuxiliarySystemsHealth(BaseModel):
    form_ok: bool
    target_ok: bool
    form_error: str | None = None
    target_error: str | None = None


class ExcelWriteLockHealth(BaseModel):
    locked: bool
    waiting: int
    active_operation: str | None = None
    total_acquired: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    sqlite: SQLiteHealth
    excel: ExcelHealth
    auxiliary_systems: AuxiliarySystemsHealth
    excel_write_lock: ExcelWriteLockHealth
    last_sync_error: str | None = None
    last_auxiliary_sync_error: str | None = None


class SyncRetryItem(BaseModel):
    entry_id: int | None = None
    submission_id: int | None = None
    success: bool
    sync_status: str
    excel_row_number: int | None = None
    excel_start_row: int | None = None
    excel_end_row: int | None = None
    last_error: str | None = None


class SyncRetryResponse(BaseModel):
    attempted: int
    synced: int
    failed: int
    remaining: int
    stopped_on_error: bool
    results: list[SyncRetryItem]
