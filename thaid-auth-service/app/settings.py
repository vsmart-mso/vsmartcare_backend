from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "thaid-auth-service"
    port: int = 8000

    # Starter config placeholders (for real ThaiD OIDC integration)
    thaid_client_id: str = "change-me"
    thaid_redirect_uri: str = "http://localhost:8000/v1/auth/thaid/callback"


settings = Settings()

