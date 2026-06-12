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

    # --- ตรวจรายใหม่/รายเดิม (app.api.check_case) — ว่าง URL = ข้ามแหล่งนั้น ---
    #: MSO logbook — URL เต็ม (ถ้าตั้ง จะไม่ใช้ BASE_URL + CHECK_PATH)
    mso_logbook_url: str = Field(default="", validation_alias="MSO_LOGBOOK_URL")
    mso_logbook_base_url: str = Field(default="", validation_alias="MSO_LOGBOOK_BASE_URL")
    mso_logbook_check_path: str = Field(
        default="/vapi/api-convert/logbook/get-problem/",
        validation_alias="MSO_LOGBOOK_CHECK_PATH",
    )
    #: POST body ``{"national_id": "<cid>"}`` — ชื่อฟิลด์ JSON ปรับได้
    mso_logbook_body_field: str = Field(
        default="national_id",
        validation_alias="MSO_LOGBOOK_BODY_FIELD",
    )
    mso_logbook_api_key: str | None = Field(default=None, validation_alias="MSO_LOGBOOK_API_KEY")
    mso_logbook_api_key_header: str = Field(
        default="Api-Key",
        validation_alias="MSO_LOGBOOK_API_KEY_HEADER",
    )

    #: vsmart_main — เช็ค CID ในฐานคำร้อง VSmart หลัก (ว่าง = ข้าม)
    vsmart_main_base_url: str = Field(default="", validation_alias="VSMART_MAIN_BASE_URL")
    vsmart_main_check_path: str = Field(
        default="/api/v1/people/check-cid",
        validation_alias="VSMART_MAIN_CHECK_PATH",
    )
    vsmart_main_cid_query_param: str = Field(
        default="cid",
        validation_alias="VSMART_MAIN_CID_QUERY_PARAM",
    )
    vsmart_main_api_key: str | None = Field(default=None, validation_alias="VSMART_MAIN_API_KEY")
    vsmart_main_api_key_header: str = Field(
        default="X-API-Key",
        validation_alias="VSMART_MAIN_API_KEY_HEADER",
    )

    external_check_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="EXTERNAL_CHECK_TIMEOUT_SECONDS",
    )

    #: แจ้งอีเมลเมื่อเจ้าหน้าที่เปลี่ยนสถานะ — เรียก notification-service โดยตรง
    notification_service_url: str = Field(
        default="http://notification-service:8000",
        validation_alias="NOTIFICATION_SERVICE_URL",
    )
    status_email_enabled: bool = Field(default=True, validation_alias="STATUS_EMAIL_ENABLED")
    status_email_timeout_seconds: float = Field(
        default=5.0,
        validation_alias="STATUS_EMAIL_TIMEOUT_SECONDS",
    )

    #: จำกัดยื่นคำขอซ้ำ — วันปฏิทินหลังส่งสำเร็จ (0 = ยื่นได้ทันที, ใช้ทดสอบ)
    cooldown_days: int = Field(default=30, ge=0, validation_alias="COOLDOWN_DAYS")

    #: --- Admin (TASK-v-care-12062026-01) — เปิด/ปิดบริการรายจังหวัด ---
    #: secret สำหรับเซ็น admin JWT (HS256) — ต้องตั้งใน production, แยกจาก THAID_JWT_SECRET
    admin_jwt_secret: str = Field(default="", validation_alias="ADMIN_JWT_SECRET")
    #: อายุ admin token (นาที) — default 8 ชั่วโมง
    admin_jwt_expire_minutes: int = Field(
        default=480, ge=1, validation_alias="ADMIN_JWT_EXPIRE_MINUTES"
    )


settings = Settings()


def resolved_upload_root() -> Path:
    """ค่า UPLOAD_ROOT — ถ้าเป็น path สัมพัทธ์จะอ้างอิงจากโฟลเดอร์ service (parent ของ `app/`)."""
    p = Path(settings.upload_root)
    return p.resolve() if p.is_absolute() else (_SERVICE_ROOT / p).resolve()
