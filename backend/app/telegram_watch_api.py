import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .telegram import TelegramDeliveryError, send_telegram_message
from .telegram_watch_schemas import TelegramUpdatePayload, TelegramWebhookResponse
from .telegram_watch_service import (
    TelegramLinkConflictError,
    consume_link_token,
    parse_start_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram-webhook"])


def _webhook_authenticated(provided: str | None, configured: str) -> bool:
    if not provided or not configured:
        return False
    return secrets.compare_digest(provided, configured)


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def telegram_webhook(
    payload: TelegramUpdatePayload,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    webhook_secret: Annotated[
        str | None,
        Header(alias="X-Telegram-Bot-Api-Secret-Token"),
    ] = None,
) -> TelegramWebhookResponse:
    if not _webhook_authenticated(webhook_secret, settings.telegram_webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram webhook authentication failed",
        )
    if payload.message is None:
        return TelegramWebhookResponse(status="ignored")
    token = parse_start_token(payload.message.text)
    if token is None:
        return TelegramWebhookResponse(status="ignored")
    try:
        link = consume_link_token(session, token, payload.message.chat.id)
    except TelegramLinkConflictError:
        logger.warning("Telegram link conflict rejected")
        return TelegramWebhookResponse(status="accepted")
    if link is None:
        return TelegramWebhookResponse(status="accepted")
    if not settings.development_safe_mode and settings.telegram_bot_token.strip():
        try:
            await send_telegram_message(
                settings,
                link.telegram_chat_id,
                "Telegram подключён. Новые изменения по включённым наблюдениям будут приходить сюда.",
            )
        except TelegramDeliveryError:
            logger.warning("Telegram link confirmation failed")
    return TelegramWebhookResponse(status="accepted")
