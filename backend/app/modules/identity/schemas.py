from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Platform = Literal["youtube", "instagram", "facebook", "tiktok", "x"]
Role = Literal["editor", "viewer"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    email: Email
    password: SecretStr = Field(min_length=12, max_length=1024)


class Named(Input):
    name: Name


class BrandCreate(Named):
    niche_id: UUID
    description: str = Field(default="", max_length=2000)


class BrandUpdate(Named):
    description: str = Field(default="", max_length=2000)


class StyleGuide(Input):
    voice: str = Field(default="", max_length=2000)
    audience: str = Field(default="", max_length=1000)
    typography: str = Field(default="", max_length=120)
    colors: list[Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]] = Field(
        default_factory=list, max_length=8
    )


class AccountCreate(Input):
    platform: Platform
    handle: Name
    display_name: str = Field(default="", max_length=120)
    profile_url: str = Field(default="", max_length=2048)
    timezone: str = Field(default="UTC", max_length=100)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use an IANA time zone, for example UTC or America/New_York") from None
        return value

    @field_validator("profile_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        if value:
            url = urlsplit(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
            ):
                raise ValueError("Use an HTTP(S) profile URL without credentials")
        return value


class MemberGrant(Input):
    email: Email
    role: Literal["owner", "member"]


class PermissionGrant(Input):
    email: Email
    role: Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


class SessionRead(BaseModel):
    user: UserRead
    csrf_token: str
    expires_at: datetime


class WorkspaceRead(BaseModel):
    id: UUID
    name: str
    role: str


class NicheRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    name: str


class BrandRead(BaseModel):
    id: UUID
    workspace_id: UUID
    niche_id: UUID
    name: str
    description: str
    role: str


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    platform: str
    handle: str
    display_name: str
    profile_url: str
    timezone: str
    connection_status: str
    can_edit: bool = False


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: UUID | None
    workspace_id: UUID | None
    brand_id: UUID | None
    event_type: str
    target_id: str | None
    correlation_id: str
    details: dict[str, str]
    created_at: datetime


class GrantRead(BaseModel):
    user_id: UUID
    email: str
    role: str
