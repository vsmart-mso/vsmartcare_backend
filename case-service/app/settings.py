from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILES: tuple[Path, ...] = tuple(
    p
    for p in (
        _SERVICE_ROOT / ".env",
        _SERVICE_ROOT / ".env.local",
    )
    if p.is_file()
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES if _ENV_FILES else None,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        env_ignore_empty=True,
    )

    service_name: str = Field(validation_alias="SERVICE_NAME")
    port: int = Field(validation_alias="PORT")
    database_url: str = Field(validation_alias="DATABASE_URL")


settings = Settings()
