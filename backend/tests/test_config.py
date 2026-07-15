import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings, resolve_database_url


def test_direct_xml_source_is_not_modified() -> None:
    settings = Settings(source_url="https://example.test/data.xml")
    assert settings.data_url == "https://example.test/data.xml"


def test_html_source_derives_xml_endpoint() -> None:
    settings = Settings(source_url="https://example.test/abiturient/")
    assert settings.data_url == "https://example.test/abiturient/xml/1.xml"


def test_telegram_disabled_allows_empty_token() -> None:
    settings = Settings(telegram_enabled=False, telegram_bot_token="", telegram_chat_id="")
    assert settings.telegram_enabled is False


@pytest.mark.parametrize(
    ("token", "chat_id", "expected"),
    [("", "123", "TELEGRAM_BOT_TOKEN"), ("secret", "", "TELEGRAM_CHAT_ID")],
)
def test_telegram_enabled_requires_complete_configuration(
    token: str, chat_id: str, expected: str
) -> None:
    with pytest.raises(ValidationError, match=expected):
        Settings(telegram_enabled=True, telegram_bot_token=token, telegram_chat_id=chat_id)


def test_telegram_watch_delivery_is_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.telegram_watch_delivery_enabled is False
    assert settings.telegram_bot_username == ""
    assert settings.telegram_webhook_secret == ""
    assert settings.public_app_base_url == ""


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"telegram_bot_token": ""},
            "TELEGRAM_BOT_TOKEN",
        ),
        (
            {"telegram_bot_username": ""},
            "TELEGRAM_BOT_USERNAME",
        ),
        (
            {"telegram_webhook_secret": ""},
            "TELEGRAM_WEBHOOK_SECRET",
        ),
    ],
)
def test_telegram_watch_delivery_requires_linking_configuration(
    overrides: dict[str, str], expected: str
) -> None:
    values = {
        "telegram_watch_delivery_enabled": True,
        "telegram_bot_token": "secret",
        "telegram_bot_username": "@bseu_test_bot",
        "telegram_webhook_secret": "webhook_secret",
    }
    values.update(overrides)
    with pytest.raises(ValidationError, match=expected):
        Settings(_env_file=None, **values)


def test_telegram_watch_public_values_are_normalized_and_validated() -> None:
    settings = Settings(
        _env_file=None,
        telegram_bot_username="@bseu_test_bot",
        telegram_webhook_secret="safe-secret_123",
        public_app_base_url="https://admission.test/bseu",
    )
    assert settings.telegram_bot_username == "bseu_test_bot"
    assert settings.public_app_base_url == "https://admission.test/bseu/"
    with pytest.raises(ValidationError, match="PUBLIC_APP_BASE_URL"):
        Settings(_env_file=None, public_app_base_url="javascript:alert(1)")
    with pytest.raises(ValidationError, match="TELEGRAM_WEBHOOK_SECRET"):
        Settings(_env_file=None, telegram_webhook_secret="unsafe secret")


def test_relative_database_url_is_resolved_against_backend(monkeypatch, tmp_path) -> None:
    expected = f"sqlite:///{(BACKEND_DIR / 'data/admission.db').resolve().as_posix()}"
    monkeypatch.chdir(tmp_path)
    assert resolve_database_url("sqlite:///./data/admission.db") == expected


def test_absolute_production_database_url_is_unchanged() -> None:
    production_url = "sqlite:////var/lib/bseu-admission-monitor/admission.db"
    assert resolve_database_url(production_url) == production_url


def test_development_safe_mode_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVELOPMENT_SAFE_MODE", raising=False)
    assert Settings(_env_file=None).development_safe_mode is False


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("false", False)])
def test_development_safe_mode_parses_only_explicit_environment_value(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("DEVELOPMENT_SAFE_MODE", value)
    assert Settings(_env_file=None).development_safe_mode is expected


def test_invalid_development_safe_mode_does_not_activate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_SAFE_MODE", "development")
    with pytest.raises(ValidationError, match="development_safe_mode"):
        Settings(_env_file=None)
