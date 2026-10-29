from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.network import canonical_url
from app.modules.identity.schemas import Input


class RightsCreate(Input):
    candidate_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2048)
    adapter: Literal["direct", "ytdlp"] = "direct"
    basis: Literal["OWNED", "LICENSED", "PERMISSION"]
    license: str = Field(min_length=1, max_length=300)
    evidence: str = Field(min_length=1, max_length=5000)
    attribution: str = Field(default="", max_length=3000)
    restrictions: str = Field(default="", max_length=3000)
    confirmed: Literal[True]

    @model_validator(mode="after")
    def valid_rights(self) -> "RightsCreate":
        if not all(x.strip() for x in [self.title, self.license, self.evidence]):
            raise ValueError("Provide title, license/ownership basis and permission evidence")
        self.source_url = canonical_url(self.source_url)
        if not self.source_url.startswith("https://"):
            raise ValueError("Acquisition requires HTTPS")
        return self


class RightsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_id: UUID | None
    title: str
    source_url: str
    adapter: str
    basis: str
    license: str
    evidence: str
    attribution: str
    restrictions: str
    status: str
    reviewed_by: UUID
    created_at: datetime


class AcquisitionRequest(Input):
    rights_id: UUID
    idempotency_key: UUID


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_type: str
    state: str
    attempts: int
    max_attempts: int
    progress: int
    error_code: str
    cancel_requested: bool
    created_at: datetime
    updated_at: datetime


class AssetRead(BaseModel):
    id: UUID
    rights_id: UUID
    title: str
    export_name: str
    sha256: str
    size_bytes: int
    duration: float
    width: int
    height: int
    video_codec: str
    audio_codec: str | None
    rights_status: str
    created_at: datetime


class ReuseAsset(Input):
    source_brand_id: UUID
    source_asset_id: UUID
    destination_rights_id: UUID
