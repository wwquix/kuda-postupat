from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from urllib.parse import quote, urljoin
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .config import Settings
from .telegram import TelegramTransportError, send_telegram_message
from .telegram_watch_models import TelegramWatchDelivery
from .telegram_watch_repository import active_event_link_pairs, delivery_by_event_link
from .watch_service import event_description

SessionFactory = Callable[[], Session]
MAX_DELIVERY_ATTEMPTS = 3


def _prepare_delivery_ids(
    session_factory: SessionFactory,
    source_snapshot_ids: list[int],
) -> list[int]:
    delivery_ids: list[int] = []
    with session_factory() as session:
        for event_id, link_id in active_event_link_pairs(session, source_snapshot_ids):
            delivery = delivery_by_event_link(session, event_id, link_id)
            if delivery is None:
                delivery = TelegramWatchDelivery(
                    watch_event_id=event_id,
                    profile_link_id=link_id,
                    state="pending",
                    attempt_count=0,
                )
                session.add(delivery)
                session.flush()
                delivery_ids.append(delivery.id)
                continue
            if delivery.state == "retryable" and delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
                delivery_ids.append(delivery.id)
            elif delivery.state == "pending" and delivery.attempt_count == 0:
                delivery_ids.append(delivery.id)
        session.commit()
    return delivery_ids


def _event_message(delivery: TelegramWatchDelivery, settings: Settings) -> str:
    event = delivery.watch_event
    program = event.watch.program
    university = program.university
    event_time = event.created_at
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=UTC)
    event_time = event_time.astimezone(ZoneInfo(settings.timezone))
    lines = [
        f"{university.short_name} — {program.name}",
        university.full_name,
        event_description(event),
        f"Изменение зафиксировано: {event_time:%d.%m.%Y %H:%M}",
    ]
    if settings.public_app_base_url:
        program_path = (
            f"universities/{quote(university.slug, safe='')}/programs/"
            f"{quote(program.slug, safe='')}"
        )
        lines.append(urljoin(settings.public_app_base_url, program_path))
    return "\n".join(lines)


def _start_attempt(
    session_factory: SessionFactory,
    delivery_id: int,
    settings: Settings,
) -> tuple[str, str, int] | None:
    with session_factory() as session:
        delivery = session.get(TelegramWatchDelivery, delivery_id)
        if delivery is None or delivery.state in {"confirmed", "failed"}:
            return None
        if delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
            delivery.state = "failed"
            delivery.last_error_summary = "attempt_limit_reached"
            delivery.updated_at = datetime.now(UTC)
            session.commit()
            return None
        if delivery.profile_link.unlinked_at is not None:
            delivery.state = "failed"
            delivery.last_error_summary = "telegram_link_inactive"
            delivery.updated_at = datetime.now(UTC)
            session.commit()
            return None
        message = _event_message(delivery, settings)
        delivery.attempt_count += 1
        delivery.last_attempt_at = datetime.now(UTC)
        delivery.last_error_summary = None
        delivery.state = "pending"
        delivery.updated_at = delivery.last_attempt_at
        attempt_count = delivery.attempt_count
        chat_id = delivery.profile_link.telegram_chat_id
        session.commit()
        return chat_id, message, attempt_count


def _record_failure(
    session_factory: SessionFactory,
    delivery_id: int,
    error: TelegramTransportError,
) -> bool:
    with session_factory() as session:
        delivery = session.get(TelegramWatchDelivery, delivery_id)
        if delivery is None or delivery.state == "confirmed":
            return False
        should_retry = error.retryable and delivery.attempt_count < MAX_DELIVERY_ATTEMPTS
        delivery.state = "retryable" if should_retry else "failed"
        delivery.last_error_summary = error.summary[:200]
        delivery.updated_at = datetime.now(UTC)
        session.commit()
        return should_retry


def _record_confirmation(session_factory: SessionFactory, delivery_id: int) -> None:
    with session_factory() as session:
        delivery = session.get(TelegramWatchDelivery, delivery_id)
        if delivery is None or delivery.state == "confirmed":
            return
        now = datetime.now(UTC)
        delivery.state = "confirmed"
        delivery.confirmed_at = now
        delivery.last_error_summary = None
        delivery.updated_at = now
        session.commit()


async def deliver_watch_events_for_snapshots(
    session_factory: SessionFactory,
    settings: Settings,
    source_snapshot_ids: Iterable[int],
) -> int:
    if not settings.telegram_watch_delivery_enabled or settings.development_safe_mode:
        return 0
    snapshot_ids = sorted(set(source_snapshot_ids))
    if not snapshot_ids:
        return 0
    confirmed = 0
    for delivery_id in _prepare_delivery_ids(session_factory, snapshot_ids):
        while True:
            attempt = _start_attempt(session_factory, delivery_id, settings)
            if attempt is None:
                break
            chat_id, message, _attempt_count = attempt
            try:
                await send_telegram_message(settings, chat_id, message)
            except TelegramTransportError as exc:
                if _record_failure(session_factory, delivery_id, exc):
                    continue
                break
            _record_confirmation(session_factory, delivery_id)
            confirmed += 1
            break
    return confirmed
