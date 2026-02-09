"""Multi-Channel Notification Delivery (PRD-142).

Concrete delivery channels for sending alerts.
Each channel supports demo mode when credentials aren't configured.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ChannelKind(Enum):
    """Available notification channel types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


@dataclass
class NotificationPayload:
    """Payload for a notification."""
    title: str = ""
    body: str = ""
    symbol: str = ""
    severity: str = "info"
    action_url: str = ""
    extra_data: dict = field(default_factory=dict)


@dataclass
class ChannelResult:
    """Result of a channel delivery attempt."""
    channel: ChannelKind = ChannelKind.IN_APP
    success: bool = False
    message_id: str = ""
    error: str = ""
    delivered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "channel": self.channel.value,
            "success": self.success,
            "message_id": self.message_id,
            "error": self.error,
        }


@runtime_checkable
class NotificationChannel(Protocol):
    """Protocol for notification channels."""

    @property
    def kind(self) -> ChannelKind: ...

    async def send(self, payload: NotificationPayload) -> ChannelResult: ...

    def is_configured(self) -> bool: ...


class EmailChannel:
    """Email notification channel (demo mode)."""

    def __init__(self, smtp_host: str = "", **kwargs):
        self._demo = not bool(smtp_host)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind.EMAIL

    def is_configured(self) -> bool:
        return not self._demo

    async def send(self, payload: NotificationPayload) -> ChannelResult:
        logger.info(f"[EMAIL] {payload.title}: {payload.body}")
        return ChannelResult(channel=self.kind, success=True,
                             message_id=f"email_{id(payload)}")


class SMSChannel:
    """SMS notification channel (demo mode)."""

    def __init__(self, account_sid: str = "", **kwargs):
        self._demo = not bool(account_sid)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind.SMS

    def is_configured(self) -> bool:
        return not self._demo

    async def send(self, payload: NotificationPayload) -> ChannelResult:
        logger.info(f"[SMS] {payload.title}: {payload.body[:160]}")
        return ChannelResult(channel=self.kind, success=True,
                             message_id=f"sms_{id(payload)}")


class PushChannel:
    """Push notification channel (demo mode)."""

    def __init__(self, api_key: str = "", **kwargs):
        self._demo = not bool(api_key)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind.PUSH

    def is_configured(self) -> bool:
        return not self._demo

    async def send(self, payload: NotificationPayload) -> ChannelResult:
        logger.info(f"[PUSH] {payload.title}: {payload.body}")
        return ChannelResult(channel=self.kind, success=True,
                             message_id=f"push_{id(payload)}")


class SlackChannel:
    """Slack webhook notification channel (demo mode)."""

    def __init__(self, webhook_url: str = ""):
        self._demo = not bool(webhook_url)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind.SLACK

    def is_configured(self) -> bool:
        return not self._demo

    async def send(self, payload: NotificationPayload) -> ChannelResult:
        logger.info(f"[SLACK] {payload.title}: {payload.body}")
        return ChannelResult(channel=self.kind, success=True,
                             message_id=f"slack_{id(payload)}")


class DiscordChannel:
    """Discord webhook notification channel (demo mode)."""

    def __init__(self, webhook_url: str = ""):
        self._demo = not bool(webhook_url)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind.DISCORD

    def is_configured(self) -> bool:
        return not self._demo

    async def send(self, payload: NotificationPayload) -> ChannelResult:
        logger.info(f"[DISCORD] {payload.title}: {payload.body}")
        return ChannelResult(channel=self.kind, success=True,
                             message_id=f"discord_{id(payload)}")


class TelegramChannel:
    """Telegram Bot API notification channel (demo mode)."""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self._demo = not bool(bot_token)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind.TELEGRAM

    def is_configured(self) -> bool:
        return not self._demo

    async def send(self, payload: NotificationPayload) -> ChannelResult:
        logger.info(f"[TELEGRAM] {payload.title}: {payload.body}")
        return ChannelResult(channel=self.kind, success=True,
                             message_id=f"tg_{id(payload)}")


class ChannelRegistry:
    """Registry of notification channels with auto-dispatch."""

    def __init__(self):
        self._channels: dict[ChannelKind, NotificationChannel] = {
            ChannelKind.EMAIL: EmailChannel(),
            ChannelKind.SMS: SMSChannel(),
            ChannelKind.PUSH: PushChannel(),
            ChannelKind.SLACK: SlackChannel(),
            ChannelKind.DISCORD: DiscordChannel(),
            ChannelKind.TELEGRAM: TelegramChannel(),
        }

    def register(self, channel: NotificationChannel) -> None:
        self._channels[channel.kind] = channel

    def get(self, kind: ChannelKind) -> Optional[NotificationChannel]:
        return self._channels.get(kind)

    async def send_to(self, kind: ChannelKind, payload: NotificationPayload) -> ChannelResult:
        channel = self._channels.get(kind)
        if not channel:
            return ChannelResult(channel=kind, success=False, error=f"Not registered: {kind.value}")
        return await channel.send(payload)

    async def send_to_all(self, kinds: list[ChannelKind], payload: NotificationPayload) -> list[ChannelResult]:
        return [await self.send_to(kind, payload) for kind in kinds]

    @property
    def available_channels(self) -> list[ChannelKind]:
        return list(self._channels.keys())
