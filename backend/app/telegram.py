import hashlib
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import AdmissionSnapshot, NotificationLog, Specialty

logger = logging.getLogger(__name__)


class TelegramDeliveryError(RuntimeError):
    """A sanitized Telegram delivery failure that never contains the bot token."""


class TelegramTransportError(TelegramDeliveryError):
    def __init__(self, summary: str, *, retryable: bool):
        super().__init__("Telegram API request failed")
        self.summary = summary[:200]
        self.retryable = retryable


def notification_fingerprint(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def notification_was_sent(session: Session, message: str) -> bool:
    fingerprint = notification_fingerprint(message)
    return session.scalar(select(NotificationLog.id).where(NotificationLog.fingerprint == fingerprint)) is not None


def build_change_message(
    specialty: Specialty, current: AdmissionSnapshot, previous: AdmissionSnapshot | None
) -> str | None:
    if previous is None:
        return None
    meaningful = any(
        (
            current.estimated_cutoff_min != previous.estimated_cutoff_min,
            current.estimated_cutoff_max != previous.estimated_cutoff_max,
            current.applications_total != previous.applications_total,
            (current.applications_total > current.admission_plan)
            != (previous.applications_total > previous.admission_plan),
            current.user_status != previous.user_status,
        )
    )
    if not meaningful:
        return None

    def cutoff(snapshot: AdmissionSnapshot) -> str:
        if snapshot.applications_total <= snapshot.admission_plan:
            return "конкурса нет"
        if snapshot.estimated_cutoff_min is None:
            return "недостаточно данных"
        if snapshot.estimated_cutoff_min == snapshot.estimated_cutoff_max:
            return str(snapshot.estimated_cutoff_min)
        return f"{snapshot.estimated_cutoff_min}–{snapshot.estimated_cutoff_max}"

    fetched_at = current.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    local_time = fetched_at.astimezone(ZoneInfo("Europe/Minsk"))
    return "\n".join(
        (
            f"БГЭУ — {specialty.display_name}",
            f"{specialty.study_form.capitalize()}, {specialty.funding_type}",
            f"Подано: {previous.applications_total} → {current.applications_total}",
            f"План: {current.admission_plan}",
            f"Предполагаемый порог: {cutoff(previous)} → {cutoff(current)}",
            f"Твой балл: {current.user_score}",
            f"Статус: {current.user_status.lower()}",
            f"Обновлено: {local_time:%d.%m.%Y %H:%M}",
        )
    )


async def send_telegram_message(settings: Settings, chat_id: str, message: str) -> None:
    if not settings.telegram_bot_token.strip():
        raise TelegramTransportError("telegram_not_configured", retryable=False)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json={"chat_id": chat_id, "text": message})
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        retryable = status_code == 429 or status_code >= 500
        summary = "telegram_retryable_response" if retryable else "telegram_rejected_request"
        raise TelegramTransportError(summary, retryable=retryable) from exc
    except httpx.RequestError as exc:
        raise TelegramTransportError("telegram_transport_error", retryable=True) from exc


async def send_once(session: Session, settings: Settings, message: str) -> bool:
    if not settings.telegram_enabled or not message:
        return False
    if notification_was_sent(session, message):
        return False
    await send_telegram_message(settings, settings.telegram_chat_id, message)
    session.add(
        NotificationLog(fingerprint=notification_fingerprint(message), sent_at=datetime.now(UTC), message=message)
    )
    session.commit()
    return True
