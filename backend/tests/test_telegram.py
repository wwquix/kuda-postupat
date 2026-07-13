from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import NotificationLog
from app.telegram import (
    TelegramDeliveryError,
    notification_fingerprint,
    notification_was_sent,
    send_once,
)


def test_duplicate_telegram_notification_is_detected(test_engine_factory: Callable[[str], Engine]) -> None:
    engine = test_engine_factory()
    message = "Значимое изменение"
    with Session(engine) as session:
        assert notification_was_sent(session, message) is False
        session.add(
            NotificationLog(fingerprint=notification_fingerprint(message), sent_at=datetime.now(UTC), message=message)
        )
        session.commit()
        assert notification_was_sent(session, message) is True


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json):
        self.__class__.calls += 1
        return FakeResponse()


@pytest.mark.asyncio
async def test_send_once_uses_persistent_deduplication(
    monkeypatch, test_engine_factory: Callable[[str], Engine]
) -> None:
    engine = test_engine_factory()
    FakeClient.calls = 0
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    settings = Settings(telegram_enabled=True, telegram_bot_token="test-token", telegram_chat_id="123")
    with Session(engine) as session:
        assert await send_once(session, settings, "Источник восстановлен") is True
        assert await send_once(session, settings, "Источник восстановлен") is False
    assert FakeClient.calls == 1


class FailingClient(FakeClient):
    async def post(self, url, json):
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("network failed", request=request)


@pytest.mark.asyncio
async def test_telegram_failure_is_sanitized(
    monkeypatch, test_engine_factory: Callable[[str], Engine]
) -> None:
    engine = test_engine_factory()
    monkeypatch.setattr(httpx, "AsyncClient", FailingClient)
    secret = "must-not-appear"
    settings = Settings(telegram_enabled=True, telegram_bot_token=secret, telegram_chat_id="123")
    with Session(engine) as session, pytest.raises(TelegramDeliveryError) as error:
        await send_once(session, settings, "Test")
    assert secret not in str(error.value)
