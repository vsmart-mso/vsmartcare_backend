"""ค่าตั้งค่า dashboard-service — อ่านอย่างเดียวจาก DB เดียวกับ case-service."""

from __future__ import annotations

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

    service_name: str = Field(default="dashboard-service", validation_alias="SERVICE_NAME")
    port: int = Field(default=8000, validation_alias="PORT")

    #: DB เดียวกับ case-service (อ่านอย่างเดียว — dashboard-service ไม่มี migration/เขียนข้อมูลของตัวเอง)
    database_url: str = Field(validation_alias="DATABASE_URL")

    #: ค่าเริ่มต้น/สูงสุดของ pagination ใน GET /v1/dashboard/districts
    default_page_size: int = Field(default=10, ge=1, validation_alias="DASHBOARD_DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=100, ge=1, validation_alias="DASHBOARD_MAX_PAGE_SIZE")


settings = Settings()
