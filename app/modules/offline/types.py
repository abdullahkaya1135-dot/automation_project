from dataclasses import dataclass, field

from ...models import AuxiliarySystemsSubmission, Entry, TourContext


@dataclass(frozen=True)
class ProcessedOfflineRecord:
    record_type: str
    client_id: str | None
    item: TourContext | Entry | AuxiliarySystemsSubmission
    idempotent_replay: bool


@dataclass
class OfflineProcessingResult:
    processed: list[ProcessedOfflineRecord] = field(default_factory=list)
    entries_to_sync: list[Entry] = field(default_factory=list)
    auxiliary_to_sync: list[AuxiliarySystemsSubmission] = field(default_factory=list)
