from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "bff"
    port: int = 8000

    case_service_url: str = "http://localhost:8001"
    notification_service_url: str = "http://localhost:8002"
    thaid_auth_service_url: str = "http://localhost:8003"


settings = Settings()

