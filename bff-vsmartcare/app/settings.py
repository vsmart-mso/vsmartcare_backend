from pathlib import Path
from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_DIR = Path(__file__).resolve().parent
_SERVICE_ROOT = _APP_DIR.parent

_ENV_CANDIDATES: tuple[Path, ...] = (_SERVICE_ROOT / ".env", _APP_DIR / ".env")
_ENV_FILES: tuple[Path, ...] = tuple(p for p in _ENV_CANDIDATES if p.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES if _ENV_FILES else None,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        env_ignore_empty=True,
    )

    service_name: str = "bff"
    port: int = 8000
    bff_api_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("BFF_API_PASSWORD"),
        description="ถ้าตั้งค่า ทุก endpoint ใต้ /v1/* ต้องส่ง header X-API-Key ให้ตรง",
    )

    # Docker Compose ตั้ง CASE_SERVICE_URL=http://case-service:8000 — รัน BFF บน host ใช้ http://localhost:8001 (พอร์ต map จาก compose)
    case_service_url: str = Field(
        default="http://localhost:8001",
        validation_alias=AliasChoices("CASE_SERVICE_URL"),
    )
    notification_service_url: str = Field(
        default="http://localhost:8002",
        validation_alias=AliasChoices("NOTIFICATION_SERVICE_URL"),
    )
    thaid_auth_service_url: str = Field(
        default="http://localhost:8003",
        validation_alias=AliasChoices("THAID_AUTH_SERVICE_URL"),
    )

    bff_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        validation_alias=AliasChoices("BFF_CORS_ORIGINS"),
        description="ต้นทางที่อนุญาตให้เรียก BFF จากเบราว์เซอร์ (เช่น Vite)",
    )

    @field_validator(
        "case_service_url",
        "notification_service_url",
        "thaid_auth_service_url",
        mode="after",
    )
    @classmethod
    def normalize_service_base_url(cls, v: str) -> str:
        s = v.strip().rstrip("/")
        if not s:
            raise ValueError("service base URL must not be empty")
        return s


settings = Settings()

_DEV_CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def cors_origin_list() -> List[str]:
    raw = settings.bff_cors_origins.strip()
    if not raw:
        return list(_DEV_CORS_ORIGINS)
    parsed = [o.strip() for o in raw.split(",") if o.strip()]
    return parsed if parsed else list(_DEV_CORS_ORIGINS)
