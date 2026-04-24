from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_NAME: str = "Football Analytics Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173"]

    # Rate limiting
    RATE_LIMIT_LOGIN: str = "5/minute"

    # MFA
    MFA_ISSUER: str = "FootballAnalytics"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
