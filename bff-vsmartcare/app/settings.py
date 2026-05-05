from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_DIR = Path(__file__).resolve().parent
_SERVICE_ROOT = _APP_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[_SERVICE_ROOT / ".env", _APP_DIR / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "bff"
    port: int = 8000
    bff_api_password: Optional[str] = Field(
        default=None,
        description="ถ้าตั้งค่า (env BFF_API_PASSWORD) ทุก endpoint ใต้ /v1/* ต้องส่ง header X-API-Key ให้ตรง",
    )

    case_service_url: str = "http://localhost:8001"
    notification_service_url: str = "http://localhost:8002"
    thaid_auth_service_url: str = "http://localhost:8003"

    # Comma-separated (env BFF_CORS_ORIGINS). ถ้าว่างหรือ parse ไม่ได้ผล จะใช้ค่า dev ด้านล่างอัตโนมัติ
    bff_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        description="ต้นทางที่อนุญาตให้เรียก BFF จากเบราว์เซอร์ (เช่น Vite)",
    )


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

