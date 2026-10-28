from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.discovery.feeds import feed_url
from app.modules.identity.schemas import Input, Name

DEFAULT_WEIGHTS = {
    "relevance": 25.0,
    "engagement_velocity": 20.0,
    "shares": 15.0,
    "saves": 10.0,
    "freshness": 10.0,
    "novelty": 10.0,
    "source_quality": 10.0,
}


class SourceCreate(Input):
    name: Name
    kind: Literal["rss", "youtube"]
    address: str = Field(min_length=1, max_length=2048)
    keywords: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    ] = Field(default_factory=list, max_length=20)
    quality: float = Field(default=0.5, ge=0, le=1)
    policy_note: str = Field(min_length=1, max_length=1000)
    policy_confirmed: Literal[True]
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @model_validator(mode="after")
    def valid_address(self) -> "SourceCreate":
        feed_url(self.kind, self.address)
        Weights.validate_weights(self.weights)
        if not self.policy_note.strip():
            raise ValueError("Document permission or feed usage policy before discovery")
        return self


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    kind: str
    url: str
    keywords: list[str]
    quality: float
    weights: dict[str, float]
    policy_note: str
    enabled: bool
    last_run_at: datetime | None


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_id: UUID
    state: str
    error: str
    found: int
    added: int
    duplicates: int
    created_at: datetime


class CandidateReview(Input):
    status: Literal["INBOX", "APPROVED", "REJECTED"]
    notes: str = Field(default="", max_length=5000)


class RouteCandidate(Input):
    target_brand_id: UUID


class Weights(Input):
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        import math

        if (
            set(value) != set(DEFAULT_WEIGHTS)
            or any(not math.isfinite(v) or v < 0 or v > 100 for v in value.values())
            or sum(value.values()) <= 0
        ):
            raise ValueError("Supply all seven nonnegative weights (0–100), with a positive total")
        return value


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    original_url: str
    summary: str
    topics: list[str]
    published_at: datetime | None
    discovered_at: datetime
    status: str
    notes: str
    score: float | None
    components: dict[str, float | None]
    rights_status: Literal["UNKNOWN"] = "UNKNOWN"
    scoring_version: str = "deterministic-v1"
    duplicate_title: bool = False
    observations: list[dict[str, str]] = Field(default_factory=list)
