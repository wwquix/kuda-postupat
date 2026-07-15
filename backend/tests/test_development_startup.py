import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.main as main
import app.scraper as scraper_module
from app.adapters import BSEU_ADAPTER_KEY
from app.config import Settings


class FakeScheduler:
    def __init__(self) -> None:
        self.add_job_calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []
        self.start_calls = 0
        self.shutdown_calls: list[bool] = []
        self.running = False

    def add_job(self, function, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.add_job_calls.append((function, args, kwargs))

    def start(self) -> None:
        self.start_calls += 1
        self.running = True

    def shutdown(self, *, wait: bool) -> None:
        self.shutdown_calls.append(wait)
        self.running = False

    def get_job(self, _job_id: str):  # type: ignore[no-untyped-def]
        return None


@pytest.fixture
def isolated_main_app(
    monkeypatch: pytest.MonkeyPatch,
    test_engine_factory,
    tmp_path: Path,
) -> Iterator[tuple[Engine, FakeScheduler, AsyncMock, AsyncMock]]:  # type: ignore[no-untyped-def]
    database = tmp_path / "development-startup.db"
    engine = test_engine_factory(f"sqlite:///{database.as_posix()}")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    scheduler = FakeScheduler()
    refresh = AsyncMock()
    telegram_send = AsyncMock()
    monkeypatch.setattr(main, "settings", Settings(
        _env_file=None,
        development_safe_mode=True,
        telegram_enabled=True,
        telegram_bot_token="not-a-secret",
        telegram_chat_id="test-chat",
    ))
    monkeypatch.setattr(main, "scheduler", scheduler)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main.scraper, "refresh", refresh)
    monkeypatch.setattr(scraper_module, "send_once", telegram_send)
    main.app.dependency_overrides[main.get_db] = override_db
    try:
        yield engine, scheduler, refresh, telegram_send
    finally:
        main.app.dependency_overrides.clear()


def test_development_safe_lifespan_skips_all_background_side_effects_and_serves_reads(
    isolated_main_app: tuple[Engine, FakeScheduler, AsyncMock, AsyncMock],
) -> None:
    _engine, scheduler, refresh, telegram_send = isolated_main_app

    with TestClient(main.app) as client:
        health = client.get("/api/health")
        catalog = client.get("/api/universities")
        config = client.get("/api/config")

    assert health.status_code == catalog.status_code == config.status_code == 200
    assert health.json()["scheduler_running"] is False
    assert catalog.json()["items"] == []
    assert scheduler.add_job_calls == []
    assert scheduler.start_calls == 0
    assert scheduler.shutdown_calls == []
    refresh.assert_not_awaited()
    telegram_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_default_lifespan_preserves_production_scheduler_and_initial_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = FakeScheduler()
    refresh = AsyncMock()
    monkeypatch.setattr(main, "settings", Settings(_env_file=None, development_safe_mode=False))
    monkeypatch.setattr(main, "scheduler", scheduler)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main.scraper, "refresh", refresh)

    async with main.lifespan(FastAPI()):
        await asyncio.sleep(0)

    assert len(scheduler.add_job_calls) == 1
    function, args, kwargs = scheduler.add_job_calls[0]
    assert function is main.scheduled_refresh
    assert args == ("interval",)
    assert kwargs["id"] == "admission-refresh"
    assert scheduler.start_calls == 1
    refresh.assert_awaited_once_with(BSEU_ADAPTER_KEY)
    assert scheduler.shutdown_calls == [False]
