from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://cisrice:cisrice@localhost:5432/cisrice"
    redis_url: str = "redis://localhost:6379/0"
    storage_root: str = "/data"
    dependency_timeout: int = Field(default=2, ge=1, le=10)
