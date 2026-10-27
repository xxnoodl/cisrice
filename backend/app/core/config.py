from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://cisrice:cisrice@localhost:5432/cisrice"
    redis_url: str = "redis://localhost:6379/0"
    storage_root: str = "/data"
    dependency_timeout: int = Field(default=2, ge=1, le=10)

    session_seconds: int = Field(default=28800, ge=600, le=86400)
    cookie_secure: bool = False
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_origins: list[str] = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    rate_namespace: str = "cisrice:rate"
    login_ip_limit: int = Field(default=30, ge=1)
    login_email_limit: int = Field(default=10, ge=1)
    mutation_limit: int = Field(default=120, ge=1)
