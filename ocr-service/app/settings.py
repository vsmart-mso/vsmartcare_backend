from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        env_ignore_empty=True,
    )

    service_name: str = "ocr-service"
    port: int = 8000

    # ── Gemini / OCR ──────────────────────────────────────────────
    gemini_api_key: str = "AIzaSyALzFw-kOAq3liKl2QJuzEEoM7yLCYNsLg"
    gemini_model: str = "gemini-3.1-flash-lite"
    blur_threshold: int = 100
    fuzzy_match_threshold: float = 90.0
    fuzzy_review_threshold: float = 75.0

    # ขนาดสูงสุดของรูปก่อนส่ง Gemini (px) — ลดขนาดเพื่อให้ส่ง base64 เร็วขึ้น
    max_image_dimension: int = 1600

    # API key สำหรับเข้าใช้ OCR service (เว้นว่าง = dev mode ไม่ตรวจสอบ)
    ocr_api_key: str = ""

    # ขนาดไฟล์สูงสุด
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    # ── Database ────────────────────────────────────────────────
    # แชร์ DATABASE เดียวกับ case-service (คนละตาราง)
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/case_service"


settings = Settings()
