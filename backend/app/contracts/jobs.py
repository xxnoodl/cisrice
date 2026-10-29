from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class JobLease:
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    actor_id: UUID
    job_type: str
    schema_version: int
    correlation_id: str
    payload: Mapping[str, str]
    lease_token: UUID
