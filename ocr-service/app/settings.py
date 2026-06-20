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

    gemini_api_key: str = "AIzaSyALzFw-kOAq3liKl2QJuzEEoM7yLCYNsLg"
    gemini_model: str = "gemini-3.1-flash-lite"
    blur_threshold: int = 100
    fuzzy_match_threshold: float = 90.0
    fuzzy_review_threshold: float = 75.0
    max_image_dimension: int = 1600

    # Shared API key for integration clients.
    ocr_api_key: str = ""
    # Enable login + API key + JWT auth flow for OCR routes.
    ocr_auth_enabled: bool = False
    # Custom integration username, not tied to real system users.
    ocr_api_username: str = ""
    # Bcrypt hash of the custom integration password.
    ocr_api_password_hash: str = ""
    # Secret used to sign OCR integration JWTs.
    ocr_jwt_secret: str = ""
    ocr_jwt_expire_minutes: int = 60

    max_upload_bytes: int = 10 * 1024 * 1024

    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/case_service"


settings = Settings()
