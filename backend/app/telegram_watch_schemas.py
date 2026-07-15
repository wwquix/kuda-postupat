from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TelegramWatchSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TelegramLinkStatusResponse(TelegramWatchSchema):
    linked: bool
    linked_at: datetime | None
    challenge_expires_at: datetime | None


class TelegramLinkChallengeResponse(TelegramWatchSchema):
    deep_link: str
    expires_at: datetime


class TelegramChatPayload(TelegramWatchSchema):
    id: int


class TelegramMessagePayload(TelegramWatchSchema):
    chat: TelegramChatPayload
    text: str | None = None


class TelegramUpdatePayload(TelegramWatchSchema):
    message: TelegramMessagePayload | None = None


class TelegramWebhookResponse(TelegramWatchSchema):
    status: Literal["accepted", "ignored"]
