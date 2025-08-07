from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/hermes"
    SMTP_HOST: str = "0.0.0.0"
    SMTP_PORT: int = 2525
    SMTP_DOMAIN: str = "example.com"
    OUTBOUND_SMTP_HOST: Optional[str] = None
    OUTBOUND_SMTP_PORT: int = 587
    OUTBOUND_SMTP_USER: Optional[str] = None
    OUTBOUND_SMTP_PASSWORD: Optional[str] = None
    OUTBOUND_SMTP_USE_TLS: bool = True
    DKIM_PRIVATE_KEY_PATH: Optional[str] = None
    DKIM_SELECTOR: str = "default"
    API_KEY: str = "development-key"
    
    class Config:
        env_file = ".env"


settings = Settings()