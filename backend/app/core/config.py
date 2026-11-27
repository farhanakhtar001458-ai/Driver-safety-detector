"""Application configuration.

Every secret is read from the environment (or a local .env file). Secrets are
never hard-coded and never returned to the frontend.
"""

from functools import lru_cache
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Application -------------------------------------------------------
    APP_NAME: str = "SafeWay AI API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Security ----------------------------------------------------------
    SECRET_KEY: str = "change-me-in-production-32-bytes-minimum"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEVICE_TOKEN_BYTES: int = 24
    # Fernet key used to encrypt personally identifiable fields at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FIELD_ENCRYPTION_KEY: str = ""

    # --- Data --------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./data/safeway.db"
    REDIS_URL: str = ""
    DATA_RETENTION_DAYS: int = 365
    RATE_LIMIT_PER_MINUTE: int = 300

    # --- Demo / simulation -------------------------------------------------
    DEMO_MODE: bool = False
    SEED_DEMO_DATA: bool = False
    SIMULATOR_ENABLED: bool = False
    SIMULATOR_INTERVAL_SECONDS: int = 3
    SIMULATOR_VEHICLE_COUNT: int = 6

    # --- AI ----------------------------------------------------------------
    LLM_PROVIDER: str = "openai-compatible"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 30
    RISK_MODEL_VERSION: str = "risk-hgb-1.0.0"
    SCORING_MODEL_VERSION: str = "score-exp-1.1.0"

    # --- Email / SMS -------------------------------------------------------
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@safeway.local"
    SMS_PROVIDER: str = "none"
    SMS_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return [str(origin) for origin in self.CORS_ORIGINS]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod", "staging"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
