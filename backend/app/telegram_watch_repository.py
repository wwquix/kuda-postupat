from datetime import datetime

from sqlalchemy import and_, desc, select, update
from sqlalchemy.orm import Session

from .telegram_watch_models import (
    TelegramLinkChallenge,
    TelegramProfileLink,
    TelegramWatchDelivery,
)
from .watch_models import ProgramWatch, ProgramWatchEvent


def active_link_for_profile(session: Session, profile_id: int) -> TelegramProfileLink | None:
    return session.scalar(
        select(TelegramProfileLink)
        .where(
            TelegramProfileLink.profile_id == profile_id,
            TelegramProfileLink.unlinked_at.is_(None),
        )
        .order_by(desc(TelegramProfileLink.linked_at), desc(TelegramProfileLink.id))
        .limit(1)
    )


def active_link_for_chat(session: Session, chat_id: str) -> TelegramProfileLink | None:
    return session.scalar(
        select(TelegramProfileLink)
        .where(
            TelegramProfileLink.telegram_chat_id == chat_id,
            TelegramProfileLink.unlinked_at.is_(None),
        )
        .order_by(desc(TelegramProfileLink.linked_at), desc(TelegramProfileLink.id))
        .limit(1)
    )


def pending_challenge_for_profile(
    session: Session, profile_id: int, _now: datetime
) -> TelegramLinkChallenge | None:
    return session.scalar(
        select(TelegramLinkChallenge)
        .where(
            TelegramLinkChallenge.profile_id == profile_id,
            TelegramLinkChallenge.consumed_at.is_(None),
        )
        .order_by(desc(TelegramLinkChallenge.created_at), desc(TelegramLinkChallenge.id))
        .limit(1)
    )


def challenge_by_hash(session: Session, token_hash: str) -> TelegramLinkChallenge | None:
    return session.scalar(
        select(TelegramLinkChallenge).where(TelegramLinkChallenge.token_hash == token_hash)
    )


def invalidate_unused_challenges(session: Session, profile_id: int, now: datetime) -> None:
    session.execute(
        update(TelegramLinkChallenge)
        .where(
            TelegramLinkChallenge.profile_id == profile_id,
            TelegramLinkChallenge.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )


def active_event_link_pairs(
    session: Session, source_snapshot_ids: list[int]
) -> list[tuple[int, int]]:
    if not source_snapshot_ids:
        return []
    return list(
        session.execute(
            select(ProgramWatchEvent.id, TelegramProfileLink.id)
            .join(ProgramWatch, ProgramWatch.id == ProgramWatchEvent.watch_id)
            .join(
                TelegramProfileLink,
                and_(
                    TelegramProfileLink.profile_id == ProgramWatch.profile_id,
                    TelegramProfileLink.unlinked_at.is_(None),
                ),
            )
            .where(ProgramWatchEvent.source_snapshot_id.in_(source_snapshot_ids))
            .order_by(ProgramWatchEvent.id, TelegramProfileLink.id)
        ).all()
    )


def delivery_by_event_link(
    session: Session, event_id: int, link_id: int
) -> TelegramWatchDelivery | None:
    return session.scalar(
        select(TelegramWatchDelivery).where(
            TelegramWatchDelivery.watch_event_id == event_id,
            TelegramWatchDelivery.profile_link_id == link_id,
        )
    )
