from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AcquisitionCandidate:
    id: UUID
    title: str
    source_url: str
