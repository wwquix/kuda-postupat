import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .admission_score import MAX_ADMISSION_SCORE, MIN_ADMISSION_SCORE

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    source_url: str = "https://bseu.by/abiturient/xml/1.xml"
    source_data_url: str | None = None
    source_page_url: str = "https://bseu.by/abiturient/"
    target_specialties: str = "Экономическая информатика"
    study_form: str = "дневная"
    funding_type: str = "платная"
    user_score: int = Field(default=276, ge=MIN_ADMISSION_SCORE, le=MAX_ADMISSION_SCORE)
    poll_interval_minutes: int = Field(default=10, ge=5)
    timezone: str = "Europe/Minsk"
    database_url: str = "sqlite:///./data/admission.db"
    development_safe_mode: bool = False
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_bot_username: str = ""
    telegram_webhook_secret: str = ""
    telegram_watch_delivery_enabled: bool = False
    public_app_base_url: str = ""
    manual_refresh_token: str = "change-me"
    request_timeout_seconds: float = Field(default=20, gt=0, le=120)
    request_retries: int = Field(default=3, ge=1, le=6)
    stale_after_minutes: int = Field(default=30, ge=5)
    cors_origins: str = "http://localhost:5173|http://localhost:8080"

    @field_validator("target_specialties")
    @classmethod
    def specialties_must_not_be_empty(cls, value: str) -> str:
        if not any(part.strip() for part in value.split("|")):
            raise ValueError("TARGET_SPECIALTIES must contain at least one name")
        return value

    @field_validator("telegram_bot_username")
    @classmethod
    def normalize_telegram_bot_username(cls, value: str) -> str:
        value = value.strip().removeprefix("@")
        if value and re.fullmatch(r"[A-Za-z0-9_]{5,32}", value) is None:
            raise ValueError("TELEGRAM_BOT_USERNAME must be a valid Telegram username")
        return value

    @field_validator("telegram_webhook_secret")
    @classmethod
    def validate_telegram_webhook_secret(cls, value: str) -> str:
        value = value.strip()
        if value and (len(value) > 256 or not all(character.isalnum() or character in "_-" for character in value)):
            raise ValueError("TELEGRAM_WEBHOOK_SECRET may contain only letters, digits, underscore and hyphen")
        return value

    @field_validator("public_app_base_url")
    @classmethod
    def validate_public_app_base_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_APP_BASE_URL must be an absolute HTTP(S) URL without query or fragment")
        return value.rstrip("/") + "/"

    @model_validator(mode="after")
    def validate_telegram_configuration(self) -> "Settings":
        if self.telegram_enabled and not self.telegram_bot_token.strip():
            raise ValueError("TELEGRAM_ENABLED=true requires TELEGRAM_BOT_TOKEN")
        if self.telegram_enabled and not self.telegram_chat_id.strip():
            raise ValueError("TELEGRAM_ENABLED=true requires TELEGRAM_CHAT_ID")
        if self.telegram_watch_delivery_enabled and not self.telegram_bot_token.strip():
            raise ValueError("TELEGRAM_WATCH_DELIVERY_ENABLED=true requires TELEGRAM_BOT_TOKEN")
        if self.telegram_watch_delivery_enabled and not self.telegram_bot_username:
            raise ValueError("TELEGRAM_WATCH_DELIVERY_ENABLED=true requires TELEGRAM_BOT_USERNAME")
        if self.telegram_watch_delivery_enabled and not self.telegram_webhook_secret:
            raise ValueError("TELEGRAM_WATCH_DELIVERY_ENABLED=true requires TELEGRAM_WEBHOOK_SECRET")
        return self

    @property
    def specialty_names(self) -> list[str]:
        return [part.strip() for part in self.target_specialties.split("|") if part.strip()]

    @property
    def data_url(self) -> str:
        if self.source_data_url:
            return self.source_data_url
        if self.source_url.lower().split("?", 1)[0].endswith(".xml"):
            return self.source_url
        return urljoin(self.source_url.rstrip("/") + "/", "xml/1.xml")

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split("|") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_database_url(database_url: str) -> str:
    """Resolve the legacy relative SQLite URL against backend, independent of process CWD."""
    prefix = "sqlite:///./"
    if not database_url.startswith(prefix):
        return database_url
    database_path = (BACKEND_DIR / database_url.removeprefix(prefix)).resolve()
    return f"sqlite:///{database_path.as_posix()}"
