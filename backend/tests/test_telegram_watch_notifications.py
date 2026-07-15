from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.telegram_watch_api as telegram_watch_api_module
import app.telegram_watch_delivery as telegram_watch_delivery_module
from app.catalog_models import InstitutionKind, MonitoringStatus, OwnershipType, Program, University
from app.config import Settings, get_settings
from app.database import get_db
from app.models import AdmissionSnapshot, Specialty
from app.profile_api import router as profile_router
from app.profile_models import AnonymousProfile
from app.profile_security import hash_profile_token
from app.telegram import TelegramTransportError
from app.telegram_watch_api import router as telegram_router
from app.telegram_watch_delivery import deliver_watch_events_for_snapshots
from app.telegram_watch_models import (
    TelegramLinkChallenge,
    TelegramProfileLink,
    TelegramWatchDelivery,
)
from app.telegram_watch_service import TELEGRAM_LINK_LIFETIME, hash_link_token
from app.watch_models import ProgramWatch, ProgramWatchEvent
from app.watch_service import list_program_watch_events


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        telegram_bot_token="test-bot-token",
        telegram_bot_username="bseu_test_bot",
        telegram_webhook_secret="test-webhook-secret",
        telegram_watch_delivery_enabled=True,
        public_app_base_url="https://admission.test/bseu/",
        request_retries=1,
    )


@pytest.fixture
def telegram_api(
    tmp_path: Path,
    test_engine_factory: Callable[[str], Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, sessionmaker[Session], Settings, list[tuple[str, str]]]:
    database = tmp_path / "telegram-linking.db"
    database_url = f"sqlite:///{database.as_posix()}"
    engine = test_engine_factory(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings(database_url)
    confirmations: list[tuple[str, str]] = []

    async def fake_send(_settings: Settings, chat_id: str, message: str) -> None:
        confirmations.append((chat_id, message))

    monkeypatch.setattr(telegram_watch_api_module, "send_telegram_message", fake_send)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(profile_router)
    app.include_router(telegram_router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), factory, settings, confirmations


def create_profile(client: TestClient) -> tuple[str, dict[str, str]]:
    response = client.post("/api/profile")
    assert response.status_code == 201
    token = response.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


def create_challenge(client: TestClient, headers: dict[str, str]) -> tuple[str, dict[str, object]]:
    response = client.post("/api/profile/telegram/challenge", headers=headers)
    assert response.status_code == 201
    payload = response.json()
    token = parse_qs(urlparse(payload["deep_link"]).query)["start"][0]
    return token, payload


def webhook(
    client: TestClient,
    token: str,
    chat_id: int,
    *,
    secret: str = "test-webhook-secret",
) -> object:
    return client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
        json={"message": {"chat": {"id": chat_id}, "text": f"/start {token}"}},
    )


def test_challenge_is_hashed_exactly_fifteen_minutes_and_replaces_previous(
    telegram_api: tuple[TestClient, sessionmaker[Session], Settings, list[tuple[str, str]]],
) -> None:
    client, factory, _settings_value, _confirmations = telegram_api
    profile_token, headers = create_profile(client)
    first_token, first_payload = create_challenge(client, headers)

    assert profile_token not in first_payload["deep_link"]
    assert first_token not in profile_token
    with factory() as session:
        first = session.scalar(select(TelegramLinkChallenge))
        assert first is not None
        assert first.token_hash == hash_link_token(first_token)
        assert first.token_hash != first_token
        assert first.expires_at - first.created_at == TELEGRAM_LINK_LIFETIME
        payload_expiry = datetime.fromisoformat(str(first_payload["expires_at"])).replace(tzinfo=None)
        assert payload_expiry == first.expires_at.replace(tzinfo=None)

    second_token, _second_payload = create_challenge(client, headers)
    assert second_token != first_token
    with factory() as session:
        challenges = session.scalars(
            select(TelegramLinkChallenge).order_by(TelegramLinkChallenge.id)
        ).all()
        assert len(challenges) == 2
        assert challenges[0].consumed_at is not None
        assert challenges[1].consumed_at is None


def test_webhook_secret_start_parsing_invalid_expired_consumed_and_replay(
    telegram_api: tuple[TestClient, sessionmaker[Session], Settings, list[tuple[str, str]]],
) -> None:
    client, factory, _settings_value, confirmations = telegram_api
    _profile_token, headers = create_profile(client)

    assert webhook(client, "invalid-token-value-123456", 100).status_code == 200
    token, _payload = create_challenge(client, headers)
    assert webhook(client, token, 100, secret="wrong-secret").status_code == 401
    assert client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
        json={"callback_query": {"id": "unsupported"}},
    ).json() == {"status": "ignored"}
    assert client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
        json={"message": {"chat": {"id": 100}, "text": "/help"}},
    ).json() == {"status": "ignored"}

    with factory() as session:
        challenge = session.scalar(
            select(TelegramLinkChallenge).where(
                TelegramLinkChallenge.token_hash == hash_link_token(token)
            )
        )
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert webhook(client, token, 100).json() == {"status": "accepted"}
    with factory() as session:
        assert session.query(TelegramProfileLink).count() == 0

    valid_token, _payload = create_challenge(client, headers)
    assert webhook(client, valid_token, 100).json() == {"status": "accepted"}
    assert webhook(client, valid_token, 100).json() == {"status": "accepted"}
    assert len(confirmations) == 1
    with factory() as session:
        assert session.query(TelegramProfileLink).count() == 1
        valid_challenge = session.scalar(
            select(TelegramLinkChallenge).where(
                TelegramLinkChallenge.token_hash == hash_link_token(valid_token)
            )
        )
        assert valid_challenge is not None
        assert valid_challenge.consumed_at is not None


def test_link_idempotency_chat_takeover_prevention_status_and_unlink_isolation(
    telegram_api: tuple[TestClient, sessionmaker[Session], Settings, list[tuple[str, str]]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, factory, _settings_value, _confirmations = telegram_api
    first_profile_token, first_headers = create_profile(client)
    second_profile_token, second_headers = create_profile(client)
    first_link_token, _payload = create_challenge(client, first_headers)
    assert webhook(client, first_link_token, 200).status_code == 200

    idempotent_token, _payload = create_challenge(client, first_headers)
    assert webhook(client, idempotent_token, 200).status_code == 200
    takeover_token, _payload = create_challenge(client, second_headers)
    with caplog.at_level("WARNING"):
        assert webhook(client, takeover_token, 200).status_code == 200

    assert client.get("/api/profile/telegram", headers=first_headers).json()["linked"] is True
    assert client.get("/api/profile/telegram", headers=second_headers).json() == {
        "linked": False,
        "linked_at": None,
        "challenge_expires_at": None,
    }
    assert client.delete("/api/profile/telegram", headers=second_headers).status_code == 200
    assert client.get("/api/profile/telegram", headers=first_headers).json()["linked"] is True
    assert client.delete("/api/profile/telegram", headers=first_headers).json()["linked"] is False
    assert client.delete("/api/profile/telegram", headers=first_headers).json()["linked"] is False

    captured = caplog.text
    for secret_value in (
        first_profile_token,
        second_profile_token,
        first_link_token,
        idempotent_token,
        takeover_token,
        "test-webhook-secret",
        "test-bot-token",
        "200",
    ):
        assert secret_value not in captured
    with factory() as session:
        assert session.query(TelegramProfileLink).count() == 1
        assert session.scalar(select(TelegramProfileLink)).unlinked_at is not None


def test_development_safe_mode_links_without_real_confirmation_request(
    telegram_api: tuple[TestClient, sessionmaker[Session], Settings, list[tuple[str, str]]],
) -> None:
    client, _factory, settings, confirmations = telegram_api
    settings.development_safe_mode = True
    _profile_token, headers = create_profile(client)
    token, _payload = create_challenge(client, headers)
    assert webhook(client, token, 300).status_code == 200
    assert confirmations == []
    assert client.get("/api/profile/telegram", headers=headers).json()["linked"] is True


@pytest.fixture
def delivery_context(
    tmp_path: Path,
    test_engine_factory: Callable[[str], Engine],
) -> tuple[sessionmaker[Session], Settings, dict[str, int]]:
    database = tmp_path / "telegram-delivery.db"
    database_url = f"sqlite:///{database.as_posix()}"
    engine = test_engine_factory(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings(database_url)
    now = datetime.now(UTC)
    with factory() as session:
        university = University(
            code="bseu",
            slug="bseu",
            short_name="БГЭУ",
            full_name="Белорусский государственный экономический университет",
            institution_kind=InstitutionKind.UNIVERSITY,
            ownership_type=OwnershipType.STATE,
            official_site_url="https://bseu.by",
            monitoring_status=MonitoringStatus.ONLINE,
            source_url="https://edu.gov.by/registry",
            source_checked_at=now,
        )
        program = Program(
            university=university,
            slug="economic-informatics",
            name="Экономическая информатика",
            official_url="https://bseu.by/program",
            source_checked_at=now,
        )
        specialty = Specialty(
            normalized_name="экономическая информатика",
            display_name="Экономическая информатика",
            study_form="дневная",
            funding_type="платная",
            source_url="https://bseu.by/xml",
            active=True,
        )
        profile = AnonymousProfile(token_hash=hash_profile_token("delivery-profile-token"))
        session.add_all([university, program, specialty, profile])
        session.flush()
        snapshot = AdmissionSnapshot(
            specialty_id=specialty.id,
            fetched_at=now,
            admission_plan=3,
            applications_total=6,
            competition=2.0,
            estimated_cutoff_min=290,
            estimated_cutoff_max=299,
            user_score=276,
            estimated_user_position=4,
            user_status="Пограничная ситуация",
            distribution_json='{"290-299": 6}',
            raw_data_hash="a" * 64,
        )
        watch = ProgramWatch(profile_id=profile.id, program_id=program.id, enabled=True)
        link = TelegramProfileLink(profile_id=profile.id, telegram_chat_id="400", linked_at=now)
        session.add_all([snapshot, watch, link])
        session.flush()
        event = ProgramWatchEvent(
            watch_id=watch.id,
            source_snapshot_id=snapshot.id,
            event_kind="applications_total_changed",
            previous_value=5,
            current_value=6,
            created_at=now,
        )
        session.add(event)
        session.commit()
        ids = {
            "profile": profile.id,
            "snapshot": snapshot.id,
            "event": event.id,
            "link": link.id,
        }
    return factory, settings, ids


@pytest.mark.asyncio
async def test_new_event_delivery_confirmed_deduplicated_and_public_only(
    delivery_context: tuple[sessionmaker[Session], Settings, dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, settings, ids = delivery_context
    sent: list[tuple[str, str]] = []

    async def success(_settings: Settings, chat_id: str, message: str) -> None:
        sent.append((chat_id, message))

    monkeypatch.setattr(telegram_watch_delivery_module, "send_telegram_message", success)
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 1
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 0
    assert len(sent) == 1
    chat_id, message = sent[0]
    assert chat_id == "400"
    assert "Экономическая информатика" in message
    assert "Белорусский государственный экономический университет" in message
    assert "Количество заявлений изменилось: 5 → 6." in message
    assert "https://admission.test/bseu/universities/bseu/programs/economic-informatics" in message
    assert "delivery-profile-token" not in message
    assert "watch_event_id" not in message

    with factory() as session:
        delivery = session.scalar(select(TelegramWatchDelivery))
        assert delivery is not None
        assert delivery.state == "confirmed"
        assert delivery.attempt_count == 1
        assert delivery.confirmed_at is not None
        profile = session.get(AnonymousProfile, ids["profile"])
        events = list_program_watch_events(session, profile)
        assert events[0].telegram_delivery_status == "confirmed"


@pytest.mark.asyncio
async def test_no_link_no_event_and_development_safe_mode_make_no_request(
    delivery_context: tuple[sessionmaker[Session], Settings, dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, settings, ids = delivery_context
    calls = 0

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("real Telegram request attempted")

    monkeypatch.setattr(telegram_watch_delivery_module, "send_telegram_message", forbidden)
    settings.development_safe_mode = True
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 0
    settings.development_safe_mode = False
    with factory() as session:
        session.get(TelegramProfileLink, ids["link"]).unlinked_at = datetime.now(UTC)
        session.commit()
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 0
    assert await deliver_watch_events_for_snapshots(factory, settings, []) == 0
    assert calls == 0
    with factory() as session:
        assert session.query(TelegramWatchDelivery).count() == 0


@pytest.mark.asyncio
async def test_retryable_delivery_retries_to_three_and_does_not_roll_back_event(
    delivery_context: tuple[sessionmaker[Session], Settings, dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, settings, ids = delivery_context
    attempts = 0

    async def retryable(_settings: Settings, _chat_id: str, _message: str) -> None:
        nonlocal attempts
        attempts += 1
        raise TelegramTransportError("telegram_transport_error", retryable=True)

    monkeypatch.setattr(telegram_watch_delivery_module, "send_telegram_message", retryable)
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 0
    assert attempts == 3
    with factory() as session:
        delivery = session.scalar(select(TelegramWatchDelivery))
        assert delivery is not None
        assert delivery.state == "failed"
        assert delivery.attempt_count == 3
        assert delivery.last_error_summary == "telegram_transport_error"
        assert session.get(ProgramWatchEvent, ids["event"]) is not None
        assert session.get(AdmissionSnapshot, ids["snapshot"]) is not None


@pytest.mark.asyncio
async def test_retryable_then_success_and_permanent_failure_policy(
    delivery_context: tuple[sessionmaker[Session], Settings, dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, settings, ids = delivery_context
    attempts = 0

    async def flaky(_settings: Settings, _chat_id: str, _message: str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TelegramTransportError("telegram_retryable_response", retryable=True)

    monkeypatch.setattr(telegram_watch_delivery_module, "send_telegram_message", flaky)
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 1
    with factory() as session:
        delivery = session.scalar(select(TelegramWatchDelivery))
        assert delivery.state == "confirmed"
        assert delivery.attempt_count == 3

        second_event = ProgramWatchEvent(
            watch_id=delivery.watch_event.watch_id,
            source_snapshot_id=ids["snapshot"],
            event_kind="estimated_cutoff_changed",
            previous_value={"has_competition": True, "minimum": 280, "maximum": 289},
            current_value={"has_competition": True, "minimum": 290, "maximum": 299},
        )
        session.add(second_event)
        session.commit()

    permanent_attempts = 0

    async def permanent(_settings: Settings, _chat_id: str, _message: str) -> None:
        nonlocal permanent_attempts
        permanent_attempts += 1
        raise TelegramTransportError("telegram_rejected_request", retryable=False)

    monkeypatch.setattr(telegram_watch_delivery_module, "send_telegram_message", permanent)
    assert await deliver_watch_events_for_snapshots(factory, settings, [ids["snapshot"]]) == 0
    assert permanent_attempts == 1
    with factory() as session:
        deliveries = session.scalars(
            select(TelegramWatchDelivery).order_by(TelegramWatchDelivery.id)
        ).all()
        assert [delivery.state for delivery in deliveries] == ["confirmed", "failed"]
        assert deliveries[1].attempt_count == 1
        assert deliveries[1].last_error_summary == "telegram_rejected_request"
