from __future__ import annotations

from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "Liga VPV API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database — individual vars (preferred, auto-escapes password)
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "vpv"
    pg_password: str = ""
    pg_database: str = "ligavpv"
    # If DATABASE_URL is set explicitly, it takes precedence
    database_url: str = ""

    @model_validator(mode="after")
    def build_database_url(self) -> Settings:
        if not self.database_url:
            password = quote_plus(self.pg_password)
            self.database_url = (
                f"postgresql+asyncpg://{self.pg_user}:{password}"
                f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
            )
        return self

    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Auth
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Invites
    invite_expiry_days: int = 7
    invite_base_url: str = "http://localhost:3000/registro"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:3003",
    ]

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False

    # Logging
    log_level: str = "INFO"

    def validate_production(self) -> None:
        """Fail fast if critical secrets are not configured in production."""
        if self.environment != "production":
            return
        if self.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION":
            raise RuntimeError("JWT_SECRET_KEY must be set in production")
        if len(self.jwt_secret_key) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters in production")
        if "localhost" in self.invite_base_url:
            raise RuntimeError("INVITE_BASE_URL must not point to localhost in production")
        if self.telegram_enabled and not self.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN required when TELEGRAM_ENABLED=true")
        if self.debug:
            raise RuntimeError("DEBUG must be false in production")


settings = Settings()
settings.validate_production()
