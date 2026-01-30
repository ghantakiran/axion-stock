"""Webhook System.

Manages webhook registration, event dispatch, and delivery tracking.
"""

import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.api.config import (
    WebhookEvent,
    WebhookConfig,
    DEFAULT_WEBHOOK_CONFIG,
)
from src.api.auth import WebhookSigner

logger = logging.getLogger(__name__)


@dataclass
class Webhook:
    """Registered webhook endpoint."""

    webhook_id: str
    user_id: str
    url: str
    events: list[str]
    secret: str
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_delivery: Optional[datetime] = None
    total_deliveries: int = 0
    successful_deliveries: int = 0


@dataclass
class DeliveryRecord:
    """Record of a webhook delivery attempt."""

    delivery_id: str
    webhook_id: str
    event: str
    payload: dict
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    success: bool = False
    attempts: int = 1
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class WebhookManager:
    """Manages webhook lifecycle and event dispatch.

    Features:
    - Webhook registration with event filtering
    - HMAC payload signing for verification
    - Delivery tracking and retry logic
    - Delivery history per webhook
    """

    def __init__(self, config: Optional[WebhookConfig] = None):
        self.config = config or DEFAULT_WEBHOOK_CONFIG
        self.signer = WebhookSigner()

        # webhook_id -> Webhook
        self._webhooks: dict[str, Webhook] = {}
        # user_id -> list of webhook_ids
        self._user_webhooks: dict[str, list[str]] = {}
        # Delivery history
        self._deliveries: list[DeliveryRecord] = []
        # event -> list of webhook_ids subscribed
        self._event_subscriptions: dict[str, list[str]] = {}

    def register(
        self,
        user_id: str,
        url: str,
        events: list[str],
        secret: Optional[str] = None,
        description: str = "",
    ) -> tuple[Optional[Webhook], str]:
        """Register a new webhook.

        Args:
            user_id: Webhook owner.
            url: Delivery URL.
            events: List of event types to subscribe.
            secret: HMAC signing secret (generated if not provided).
            description: Optional description.

        Returns:
            Tuple of (Webhook or None, error message).
        """
        # Check user's webhook count
        user_hooks = self._user_webhooks.get(user_id, [])
        if len(user_hooks) >= self.config.max_webhooks_per_user:
            return None, f"Maximum webhooks ({self.config.max_webhooks_per_user}) reached"

        webhook_id = secrets.token_hex(8)
        if not secret:
            secret = f"whsec_{secrets.token_hex(16)}"

        webhook = Webhook(
            webhook_id=webhook_id,
            user_id=user_id,
            url=url,
            events=events,
            secret=secret,
            description=description,
        )

        self._webhooks[webhook_id] = webhook

        if user_id not in self._user_webhooks:
            self._user_webhooks[user_id] = []
        self._user_webhooks[user_id].append(webhook_id)

        # Index by event
        for event in events:
            if event not in self._event_subscriptions:
                self._event_subscriptions[event] = []
            self._event_subscriptions[event].append(webhook_id)

        logger.info(f"Webhook registered: {webhook_id} for events {events}")
        return webhook, ""

    def unregister(self, webhook_id: str, user_id: str) -> bool:
        """Remove a webhook.

        Args:
            webhook_id: Webhook to remove.
            user_id: Must match webhook owner.

        Returns:
            True if removed.
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook or webhook.user_id != user_id:
            return False

        # Clean up event subscriptions
        for event in webhook.events:
            subs = self._event_subscriptions.get(event, [])
            if webhook_id in subs:
                subs.remove(webhook_id)

        # Clean up user webhooks
        user_hooks = self._user_webhooks.get(user_id, [])
        if webhook_id in user_hooks:
            user_hooks.remove(webhook_id)

        del self._webhooks[webhook_id]
        logger.info(f"Webhook unregistered: {webhook_id}")
        return True

    def dispatch(self, event: str, payload: dict) -> list[DeliveryRecord]:
        """Dispatch an event to all subscribed webhooks.

        In production, this would make HTTP requests. Here it prepares
        delivery records with signed payloads.

        Args:
            event: Event type (e.g. 'order.filled').
            payload: Event data.

        Returns:
            List of delivery records.
        """
        webhook_ids = self._event_subscriptions.get(event, [])
        records = []

        for wh_id in webhook_ids:
            webhook = self._webhooks.get(wh_id)
            if not webhook or not webhook.is_active:
                continue

            delivery_id = secrets.token_hex(8)
            full_payload = {
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            }
            payload_str = json.dumps(full_payload, default=str)

            # Sign the payload
            signature = self.signer.sign(payload_str, webhook.secret)

            record = DeliveryRecord(
                delivery_id=delivery_id,
                webhook_id=wh_id,
                event=event,
                payload={
                    **full_payload,
                    "_url": webhook.url,
                    "_signature": signature,
                },
                success=True,  # Simulated success
                status_code=200,
                response_time_ms=0.0,
            )

            records.append(record)
            self._deliveries.append(record)

            webhook.total_deliveries += 1
            webhook.successful_deliveries += 1
            webhook.last_delivery = datetime.utcnow()

        if records:
            logger.info(f"Dispatched event '{event}' to {len(records)} webhooks")

        return records

    def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """Get webhook by ID."""
        return self._webhooks.get(webhook_id)

    def list_webhooks(self, user_id: str) -> list[Webhook]:
        """List all webhooks for a user."""
        hook_ids = self._user_webhooks.get(user_id, [])
        return [self._webhooks[wid] for wid in hook_ids if wid in self._webhooks]

    def get_deliveries(
        self,
        webhook_id: str,
        limit: int = 20,
    ) -> list[DeliveryRecord]:
        """Get delivery history for a webhook."""
        records = [d for d in self._deliveries if d.webhook_id == webhook_id]
        records.sort(key=lambda d: d.created_at, reverse=True)
        return records[:limit]

    def get_delivery_stats(self, webhook_id: str) -> dict:
        """Get delivery statistics for a webhook."""
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return {}

        total = webhook.total_deliveries
        success = webhook.successful_deliveries
        rate = success / total if total > 0 else 1.0

        return {
            "webhook_id": webhook_id,
            "total_deliveries": total,
            "successful_deliveries": success,
            "failed_deliveries": total - success,
            "success_rate": rate,
            "last_delivery": (
                webhook.last_delivery.isoformat() if webhook.last_delivery else None
            ),
        }

    def toggle_webhook(self, webhook_id: str, is_active: bool) -> bool:
        """Enable or disable a webhook."""
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return False
        webhook.is_active = is_active
        return True
