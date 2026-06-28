from pathlib import Path
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_SERVICE_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "thaid-auth-service"
    port: int = 8000

    # ถ้ามี — หลังล็อกอินสำเร็จจะพยายาม insert `persons` เมื่อยังไม่มี cid (เดียวกับ case-service / postgres)
    database_url: str = Field(
        default="",
        description="postgresql+asyncpg://... — ว่าง = ไม่บันทึก persons (ตัวแปรแวดล้อม DATABASE_URL)",
    )

    # ThaiD OIDC (see THAID_FASTAPI_INTEGRATION.md)
    thaid_client_id: str = Field(default="change-me", description="OAuth2 client_id")
    thaid_client_secret: str = Field(default="", description="OAuth2 client_secret")
    thaid_server_metadata_url: str = Field(
        default="",
        description="OpenID Provider metadata URL e.g. .../.well-known/openid-configuration",
    )
    thaid_redirect_uri: str = Field(
        default="http://localhost:8003/v1/auth/thaid/callback",
        description="Must match redirect URI registered with ThaiD exactly",
    )
    thaid_scope: str = Field(
        default="openid pid title given_name family_name address birthdate",
        description="Space-separated OAuth scopes",
    )
    # If true (or metadata URL empty), use mock authorize/callback for local dev without ThaiD
    thaid_use_mock: bool = False
    # Base URL ที่เบราว์เซอร์เข้าถึง service ได้ (ใช้สร้างลิงก์ขั้นตอน mock); ว่าง = ใช้จากคำขอ (Request)
    thaid_public_base_url: str = Field(
        default="",
        description="e.g. http://localhost:8003 when behind Docker port mapping",
    )
    # ค่า user จำลอง (รูปแบบเดียวกับ userinfo หลังล็อกอิน ThaiD จริง) — ใช้เมื่อ mock OIDC
    thaid_mock_pid: str = Field(default="1103701234561", description="Mock 13-digit-style pid for dev")
    thaid_mock_title_th: str = Field(default="นาย", description="Mock Thai title")
    thaid_mock_given_name: str = Field(default="ทดสอบ", description="Mock given_name")
    thaid_mock_family_name: str = Field(default="ระบบจำลอง", description="Mock family_name")
    thaid_mock_birthdate: str = Field(
        default="1990-01-01",
        description="Mock birthdate — รองรับทั้ง YYYY-MM-DD (เช่น 1990-01-01) และปีเดียว (เช่น 1952) สำหรับทดสอบกรณีผู้สูงอายุที่ ThaID ส่งวันเกิดไม่ครบ",
    )
    thaid_mock_address: str = Field(
        default="11 ต.ลาดกระบัง อ.ลาดกระบัง จ.กรุงเทพมหานคร 10520",
        description="Mock ที่อยู่รูปแบบ DOPA (เหมือน ThaID จริง) เช่น '11 ต.ลาดกระบัง อ.ลาดกระบัง จ.กรุงเทพมหานคร 10520'",
    )
    thaid_mock_address_postcode: str = Field(
        default="10520",
        description="Mock รหัสไปรษณีย์ — ต้องตรงกับที่อยู่ใน THAID_MOCK_ADDRESS",
    )
    thaid_mock_gender: str = Field(
        default="",
        description="Mock gender (M / F / ว่าง) — ThaID มักส่งว่างสำหรับบัตรเก่า",
    )

    # Optional: issue signed JWT access tokens (HS256). If empty, opaque in-memory tokens are used.
    thaid_jwt_secret: str = Field(default="", description="Secret for signing app access JWTs")
    thaid_jwt_expire_minutes: int = 60

    # After successful OIDC callback, redirect browser here (query: access_token, token_type, expires_in)
    # Leave empty to return JSON (API / SPA that fetches this URL with XHR)
    thaid_post_login_redirect: str = Field(
        default="",
        description="If set, callback returns 302 to this URL with token query params",
    )

    # Comma-separated (env THAID_CORS_ORIGINS). ว่าง = ใช้ชุด dev ด้านล่าง (เรียก thaid-auth ตรงจาก Vite)
    thaid_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list",
    )

    @field_validator(
        "thaid_client_id",
        "thaid_client_secret",
        "thaid_server_metadata_url",
        "thaid_redirect_uri",
        "thaid_scope",
        "thaid_post_login_redirect",
        "thaid_cors_origins",
        "thaid_public_base_url",
        "thaid_mock_pid",
        "thaid_mock_title_th",
        "thaid_mock_given_name",
        "thaid_mock_family_name",
        "thaid_mock_birthdate",
        "thaid_mock_address",
        "thaid_mock_address_postcode",
        "thaid_mock_gender",
        "database_url",
        mode="before",
    )
    @classmethod
    def _strip_ws(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()

_DEV_CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def cors_origin_list() -> List[str]:
    raw = settings.thaid_cors_origins.strip()
    if not raw:
        return list(_DEV_CORS_ORIGINS)
    parsed = [o.strip() for o in raw.split(",") if o.strip()]
    return parsed if parsed else list(_DEV_CORS_ORIGINS)
