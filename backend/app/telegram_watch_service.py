import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import Settings
from .profile_models import AnonymousProfile
from .telegram_watch_models import TelegramLinkChallenge, TelegramProfileLink
from .telegram_watch_repository import (
    active_link_for_chat,
    active_link_for_profile,
    challenge_by_hash,
    invalidate_unused_challenges,
    pending_challenge_for_profile,
)
from .telegram_watch_schemas import (
    TelegramLinkChallengeResponse,
    TelegramLinkStatusResponse,
)

TELEGRAM_LINK_TOKEN_BYTES = 24
TELEGRAM_LINK_LIFETIME = timedelta(minutes=15)
START_COMMAND_PATTERN = re.compile(
    r"^/start(?:@[A-Za-z0-9_]{5,32})?\s+([A-Za-z0-9_-]{20,128})$"
)


class TelegramLinkError(RuntimeError):
    pass


class TelegramLinkUnavailableError(TelegramLinkError):
    pass


class TelegramLinkConflictError(TelegramLinkError):
    pass


def hash_link_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_start_token(text: str | None) -> str | None:
    if text is None:
        return None
    match = START_COMMAND_PATTERN.fullmatch(text.strip())
    return match.group(1) if match else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def telegram_link_status(
    session: Session, profile: AnonymousProfile, *, now: datetime | None = None
) -> TelegramLinkStatusResponse:
    current_time = now or datetime.now(UTC)
    link = active_link_for_profile(session, profile.id)
    challenge = pending_challenge_for_profile(session, profile.id, current_time)
    return TelegramLinkStatusResponse(
        linked=link is not None,
        linked_at=link.linked_at if link is not None else None,
        challenge_expires_at=(
            challenge.expires_at if challenge is not None and link is None else None
        ),
    )


def create_link_challenge(
    session: Session,
    profile: AnonymousProfile,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> TelegramLinkChallengeResponse:
    if not settings.telegram_bot_username:
        raise TelegramLinkUnavailableError("Подключение Telegram временно недоступно")
    current_time = now or datetime.now(UTC)
    token = secrets.token_urlsafe(TELEGRAM_LINK_TOKEN_BYTES)
    expires_at = current_time + TELEGRAM_LINK_LIFETIME
    invalidate_unused_challenges(session, profile.id, current_time)
    session.add(
        TelegramLinkChallenge(
            profile_id=profile.id,
            token_hash=hash_link_token(token),
            created_at=current_time,
            expires_at=expires_at,
        )
    )
    session.commit()
    return TelegramLinkChallengeResponse(
        deep_link=f"https://t.me/{settings.telegram_bot_username}?start={token}",
        expires_at=expires_at,
    )


def consume_link_token(
    session: Session,
    token: str,
    telegram_chat_id: int,
    *,
    now: datetime | None = None,
) -> TelegramProfileLink | None:
    current_time = now or datetime.now(UTC)
    challenge = challenge_by_hash(session, hash_link_token(token))
    if challenge is None or challenge.consumed_at is not None:
        return None
    if _as_utc(challenge.expires_at) <= current_time:
        challenge.consumed_at = current_time
        session.commit()
        return None

    challenge.consumed_at = current_time
    chat_id = str(telegram_chat_id)
    profile_link = active_link_for_profile(session, challenge.profile_id)
    chat_link = active_link_for_chat(session, chat_id)
    if chat_link is not None and chat_link.profile_id != challenge.profile_id:
        session.commit()
        raise TelegramLinkConflictError("Этот Telegram chat уже связан с другим профилем")
    if profile_link is not None:
        session.commit()
        if profile_link.telegram_chat_id == chat_id:
            return profile_link
        raise TelegramLinkConflictError("Профиль уже связан с другим Telegram chat")

    link = TelegramProfileLink(
        profile_id=challenge.profile_id,
        telegram_chat_id=chat_id,
        linked_at=current_time,
    )
    session.add(link)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        replay_guard = challenge_by_hash(session, hash_link_token(token))
        if replay_guard is not None and replay_guard.consumed_at is None:
            replay_guard.consumed_at = current_time
            session.commit()
        raise TelegramLinkConflictError("Не удалось безопасно связать Telegram chat") from exc
    session.refresh(link)
    return link


def unlink_telegram(
    session: Session,
    profile: AnonymousProfile,
    *,
    now: datetime | None = None,
) -> TelegramLinkStatusResponse:
    current_time = now or datetime.now(UTC)
    link = active_link_for_profile(session, profile.id)
    if link is not None:
        link.unlinked_at = current_time
    invalidate_unused_challenges(session, profile.id, current_time)
    session.commit()
    return TelegramLinkStatusResponse(
        linked=False,
        linked_at=None,
        challenge_expires_at=None,
    )
