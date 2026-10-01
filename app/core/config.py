"""Central configuration. All values come from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "change-me-in-real-env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ai-banking-api"
    app_version: str = "1.0.0"
    environment: str = "development"

    # SQLite locally, PostgreSQL on Render (set DATABASE_URL there).
    database_url: str = "sqlite:///./banking.db"

    # Auth (used by Rick's auth module)
    secret_key: str = DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Rate limiting (slowapi). Disabled in tests via RATE_LIMIT_ENABLED=false.
    rate_limit_enabled: bool = True
    login_rate_limit: str = "10/minute"
    register_rate_limit: str = "5/minute"

    # Comma-separated list of allowed origins
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # AI risk model bundle (joblib). If the file is missing, the rule-based placeholder is used.
    risk_model_path: str = "app/ml/risk_model.pkl"

    @model_validator(mode="after")
    def _reject_weak_secret_in_production(self):
        if self.environment.lower() == "production" and (
            self.secret_key == DEFAULT_SECRET or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY must be set to a random string of 32+ characters in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
