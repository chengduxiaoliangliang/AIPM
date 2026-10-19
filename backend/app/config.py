"""
Application settings — all secrets come from environment variables / .env.

No credential is ever hardcoded here. Copy `.env.example` to `.env` and fill it in,
or inject the variables through your orchestrator (Docker Compose / K8s / systemd).
"""
import logging
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Dev-only fallback so a fresh clone still boots. NEVER use this in production.
_DEV_SECRET_KEY = "dev-only-insecure-secret-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Look next to the backend, then fall back to the repo root (local dev).
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────
    PROJECT_NAME: str = "AIPM - 智能项目管理系统"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"          # development | production
    DEBUG: bool = False
    # Timezone used when telling the LLM what "today" is.
    APP_TIMEZONE: str = "Asia/Shanghai"

    # ── MySQL ─────────────────────────────────────────────────────────────
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "aipm"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "aipm_db"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @property
    def SQLALCHEMY_SERVER_URI(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}?charset=utf8mb4"
        )

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ── JWT ───────────────────────────────────────────────────────────────
    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ── DeepSeek / LangChain LLM ──────────────────────────────────────────
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_MAX_TOKENS: int = 4096
    DEEPSEEK_TEMPERATURE: float = 0.7
    AI_ENABLED: bool = True

    # ── AI session management (Redis-backed) ──────────────────────────────
    AI_SESSION_TTL: int = 60 * 60 * 24 * 7
    AI_MAX_HISTORY_TURNS: int = 20
    AI_MAX_SESSIONS_PER_USER: int = 10

    # ── CORS: comma-separated origins, or "*" for any ─────────────────────
    BACKEND_CORS_ORIGINS: str = "*"

    @property
    def cors_origins(self) -> List[str]:
        raw = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in ("production", "prod")

    # ── Validation ────────────────────────────────────────────────────────
    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_not_trivial(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters long")
        return v

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        if self.is_production:
            if self.SECRET_KEY == _DEV_SECRET_KEY:
                raise ValueError(
                    "Refusing to start in production with the default SECRET_KEY. "
                    "Set SECRET_KEY in the environment."
                )
            if not self.MYSQL_PASSWORD:
                raise ValueError("MYSQL_PASSWORD must be set in production")
        else:
            if self.SECRET_KEY == _DEV_SECRET_KEY:
                logger.warning(
                    "Using the built-in development SECRET_KEY. "
                    "Set SECRET_KEY before deploying."
                )
        return self


settings = Settings()
