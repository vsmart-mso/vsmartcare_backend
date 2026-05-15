from pathlib import Path

from pydantic import Field

_SERVICE_ROOT_FOLDER = Path(__file__).resolve().parent.parent
_DEFAULT_UPLOAD_ROOT = (_SERVICE_ROOT_FOLDER / "uploads" / "welfare-evidence").resolve()
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = _SERVICE_ROOT_FOLDER
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

    upload_root: str = Field(default=str(_DEFAULT_UPLOAD_ROOT), validation_alias="UPLOAD_ROOT")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, validation_alias="MAX_UPLOAD_BYTES")

    #: ใช้เทียบกับ type_money_category.name_acronym (หลัง normalize ช่องว่าง) สำหรับ GET por-kor-1-detail
    por_kor_1_name_acronym: str = Field(default="ปศค 1", validation_alias="POR_KOR_1_NAME_ACRONYM")


settings = Settings()


def resolved_upload_root() -> Path:
    """ค่า UPLOAD_ROOT — ถ้าเป็น path สัมพัทธ์จะอ้างอิงจากโฟลเดอร์ service (parent ของ `app/`)."""
    p = Path(settings.upload_root)
    return p.resolve() if p.is_absolute() else (_SERVICE_ROOT / p).resolve()
